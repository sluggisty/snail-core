"""
Services and systemd information collector.

Collects information about running services, systemd units, and targets.
"""

from __future__ import annotations

import json
from typing import Any

from snail_core.collectors.base import BaseCollector


class ServicesCollector(BaseCollector):
    """Collects systemd services and units information."""

    name = "services"
    description = "Systemd services, units, and targets information"

    def collect(self) -> dict[str, Any]:
        """Collect services information."""
        return {
            "systemd": self._get_systemd_info(),
            "running_services": self._get_running_services(),
            "failed_units": self._get_failed_units(),
            "targets": self._get_targets(),
            "timers": self._get_timers(),
            "sockets": self._get_listening_sockets(),
        }

    def _get_systemd_info(self) -> dict[str, Any]:
        """Get general systemd information."""
        info: dict[str, Any] = {}

        # Get systemd version
        stdout, _, rc = self.run_command(["systemctl", "--version"])
        if rc == 0 and stdout:
            lines = stdout.strip().split("\n")
            if lines:
                info["version"] = lines[0]

        # Get system state
        stdout, _, rc = self.run_command(["systemctl", "is-system-running"])
        if rc == 0:
            info["system_state"] = stdout.strip()
        else:
            info["system_state"] = stdout.strip() if stdout else "unknown"

        # Get default target
        stdout, _, rc = self.run_command(["systemctl", "get-default"])
        if rc == 0:
            info["default_target"] = stdout.strip()

        # Count units by type
        stdout, _, rc = self.run_command(
            ["systemctl", "list-units", "--all", "--no-legend", "--plain"]
        )
        if rc == 0 and stdout:
            units = stdout.strip().split("\n")
            type_counts: dict[str, int] = {}
            for unit_line in units:
                if unit_line:
                    parts = unit_line.split()
                    if parts:
                        unit_name = parts[0]
                        if "." in unit_name:
                            unit_type = unit_name.rsplit(".", 1)[1]
                            type_counts[unit_type] = type_counts.get(unit_type, 0) + 1
            info["units_by_type"] = type_counts

        return info

    def _get_running_services(self) -> list[dict[str, Any]]:
        """Get list of running services."""
        services = []

        stdout, _, rc = self.run_command(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-legend",
                "--plain",
                "--output=json",
            ]
        )

        if rc == 0 and stdout:
            try:
                data = json.loads(stdout)
                for svc in data:
                    services.append(
                        {
                            "name": svc.get("unit", ""),
                            "load": svc.get("load", ""),
                            "active": svc.get("active", ""),
                            "sub": svc.get("sub", ""),
                            "description": svc.get("description", ""),
                        }
                    )
                return services
            except json.JSONDecodeError:
                pass

        # Fallback to text parsing
        stdout, _, rc = self.run_command(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-legend",
                "--plain",
            ]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        services.append(
                            {
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": parts[4] if len(parts) > 4 else "",
                            }
                        )

        return services

    def _get_failed_units(self) -> list[dict[str, Any]]:
        """Get list of failed units."""
        failed = []

        stdout, _, rc = self.run_command(
            [
                "systemctl",
                "list-units",
                "--state=failed",
                "--no-legend",
                "--plain",
                "--output=json",
            ]
        )

        if rc == 0 and stdout:
            try:
                data = json.loads(stdout)
                for unit in data:
                    failed.append(
                        {
                            "name": unit.get("unit", ""),
                            "load": unit.get("load", ""),
                            "active": unit.get("active", ""),
                            "sub": unit.get("sub", ""),
                            "description": unit.get("description", ""),
                        }
                    )
                return failed
            except json.JSONDecodeError:
                pass

        # Fallback to text parsing
        stdout, _, rc = self.run_command(
            ["systemctl", "list-units", "--state=failed", "--no-legend", "--plain"]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        failed.append(
                            {
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": parts[4] if len(parts) > 4 else "",
                            }
                        )

        return failed

    def _get_targets(self) -> dict[str, Any]:
        """Get systemd targets information."""
        targets: dict[str, Any] = {
            "active": [],
            "default": "",
        }

        # Get default target
        stdout, _, rc = self.run_command(["systemctl", "get-default"])
        if rc == 0:
            targets["default"] = stdout.strip()

        # Get active targets
        stdout, _, rc = self.run_command(
            [
                "systemctl",
                "list-units",
                "--type=target",
                "--state=active",
                "--no-legend",
                "--plain",
            ]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if parts:
                        targets["active"].append(parts[0])

        return targets

    def _get_timers(self) -> list[dict[str, Any]]:
        """Get systemd timers information."""
        timers = []

        stdout, _, rc = self.run_command(
            ["systemctl", "list-timers", "--all", "--no-legend", "--plain"]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line and not line.startswith("NEXT"):
                    parts = line.split()
                    if len(parts) >= 7:
                        # NEXT LEFTPASSED LAST UNIT ACTIVATES
                        timers.append(
                            {
                                "unit": parts[-2] if len(parts) > 1 else "",
                                "activates": parts[-1] if parts else "",
                                "next": " ".join(parts[:3]) if len(parts) >= 3 else "",
                                "last": " ".join(parts[4:7]) if len(parts) >= 7 else "",
                            }
                        )

        return timers

    def _get_listening_sockets(self) -> list[dict[str, Any]]:
        """Get systemd socket units that are listening."""
        sockets = []

        stdout, _, rc = self.run_command(["systemctl", "list-sockets", "--no-legend", "--plain"])

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split(None, 2)
                    if len(parts) >= 2:
                        sockets.append(
                            {
                                "listen": parts[0],
                                "unit": parts[1],
                                "activates": parts[2] if len(parts) > 2 else "",
                            }
                        )

        return sockets
