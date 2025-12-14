"""
System logs collector.

Collects recent log entries from journald and important log files.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from snail_core.collectors.base import BaseCollector


class LogsCollector(BaseCollector):
    """Collects recent system log information."""

    name = "logs"
    description = "Recent system logs and journald entries"

    # Maximum log entries to collect
    MAX_ENTRIES = 100

    def collect(self) -> dict[str, Any]:
        """Collect log information."""
        return {
            "journald": self._get_journald_info(),
            "boot_logs": self._get_boot_logs(),
            "kernel_errors": self._get_kernel_errors(),
            "auth_failures": self._get_auth_failures(),
            "service_failures": self._get_service_failures(),
            "disk_errors": self._get_disk_errors(),
        }

    def _get_journald_info(self) -> dict[str, Any]:
        """Get journald status and statistics."""
        info: dict[str, Any] = {}

        # Get journal disk usage
        stdout, _, rc = self.run_command(["journalctl", "--disk-usage"])
        if rc == 0 and stdout:
            # Parse: "Archived and active journals take up 512.0M in the file system."
            parts = stdout.strip().split()
            for i, part in enumerate(parts):
                if part in ("M", "G", "K", "B") or part.endswith(("M", "G", "K", "B")):
                    # Handle "512.0M" format
                    if part[-1] in "MGKB":
                        info["disk_usage"] = part
                    elif i > 0:
                        info["disk_usage"] = f"{parts[i - 1]}{part}"
                    break
                elif "take" in parts and i > 0:
                    info["disk_usage"] = parts[i - 1]
                    break

        # Get number of boots
        stdout, _, rc = self.run_command(["journalctl", "--list-boots", "--no-pager"])
        if rc == 0 and stdout:
            boots = [line for line in stdout.strip().split("\n") if line.strip()]
            info["boot_count"] = len(boots)

        # Get journald configuration
        config = self.parse_key_value_file("/etc/systemd/journald.conf")
        info["config"] = {
            "storage": config.get("Storage", "auto"),
            "compress": config.get("Compress", "yes"),
            "max_use": config.get("SystemMaxUse", ""),
            "max_file_size": config.get("SystemMaxFileSize", ""),
        }

        return info

    def _get_boot_logs(self) -> list[dict[str, Any]]:
        """Get recent boot log entries."""
        entries = []

        stdout, _, rc = self.run_command(
            [
                "journalctl",
                "-b",
                "-p",
                "warning",
                "-n",
                str(self.MAX_ENTRIES),
                "-o",
                "json",
                "--no-pager",
            ]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(
                            {
                                "timestamp": self._format_journal_timestamp(
                                    entry.get("__REALTIME_TIMESTAMP")
                                ),
                                "priority": entry.get("PRIORITY", ""),
                                "unit": entry.get("_SYSTEMD_UNIT", ""),
                                "message": entry.get("MESSAGE", "")[:500],  # Truncate
                            }
                        )
                    except json.JSONDecodeError:
                        pass

        return entries[: self.MAX_ENTRIES]

    def _get_kernel_errors(self) -> list[dict[str, Any]]:
        """Get recent kernel error/warning messages."""
        entries = []

        stdout, _, rc = self.run_command(
            ["journalctl", "-k", "-p", "err", "-n", "50", "-o", "json", "--no-pager"]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(
                            {
                                "timestamp": self._format_journal_timestamp(
                                    entry.get("__REALTIME_TIMESTAMP")
                                ),
                                "message": entry.get("MESSAGE", "")[:500],
                            }
                        )
                    except json.JSONDecodeError:
                        pass

        return entries

    def _get_auth_failures(self) -> dict[str, Any]:
        """Get authentication failure summary."""
        result: dict[str, Any] = {
            "recent_count": 0,
            "recent_entries": [],
        }

        # Get auth failures from last 24 hours
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        stdout, _, rc = self.run_command(
            [
                "journalctl",
                "-u",
                "sshd",
                "-u",
                "systemd-logind",
                "--since",
                since,
                "-g",
                "fail|invalid|error",
                "-o",
                "json",
                "--no-pager",
                "-n",
                "50",
            ]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    try:
                        entry = json.loads(line)
                        msg = entry.get("MESSAGE", "").lower()
                        if "fail" in msg or "invalid" in msg or "error" in msg:
                            result["recent_entries"].append(
                                {
                                    "timestamp": self._format_journal_timestamp(
                                        entry.get("__REALTIME_TIMESTAMP")
                                    ),
                                    "unit": entry.get("_SYSTEMD_UNIT", ""),
                                    "message": entry.get("MESSAGE", "")[:200],
                                }
                            )
                    except json.JSONDecodeError:
                        pass

            result["recent_count"] = len(result["recent_entries"])

        # Get failed login count from lastb if available
        stdout, _, rc = self.run_command(["lastb", "-n", "100"])
        if rc == 0 and stdout:
            lines = [line for line in stdout.strip().split("\n") if line and "btmp" not in line]
            result["failed_logins_lastb"] = len(lines)

        return result

    def _get_service_failures(self) -> list[dict[str, Any]]:
        """Get recent service failure entries."""
        entries = []

        stdout, _, rc = self.run_command(
            ["journalctl", "-p", "err", "-n", "50", "-o", "json", "--no-pager"]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    try:
                        entry = json.loads(line)
                        unit = entry.get("_SYSTEMD_UNIT", "")
                        if unit and unit.endswith(".service"):
                            entries.append(
                                {
                                    "timestamp": self._format_journal_timestamp(
                                        entry.get("__REALTIME_TIMESTAMP")
                                    ),
                                    "unit": unit,
                                    "message": entry.get("MESSAGE", "")[:300],
                                }
                            )
                    except json.JSONDecodeError:
                        pass

        # Deduplicate by unit, keeping most recent
        seen_units: dict[str, dict[str, Any]] = {}
        for entry in entries:
            unit = entry["unit"]
            if unit not in seen_units:
                seen_units[unit] = entry

        return list(seen_units.values())[:20]

    def _get_disk_errors(self) -> list[dict[str, Any]]:
        """Get disk-related error messages."""
        entries = []

        # Search for disk/storage related errors
        stdout, _, rc = self.run_command(
            [
                "journalctl",
                "-k",
                "-n",
                "100",
                "-g",
                "error|fail|i/o|ata|scsi|nvme|sata",
                "-o",
                "json",
                "--no-pager",
            ]
        )

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    try:
                        entry = json.loads(line)
                        msg = entry.get("MESSAGE", "")
                        msg_lower = msg.lower()

                        # Filter for disk-related messages
                        if any(
                            kw in msg_lower
                            for kw in [
                                "disk",
                                "sda",
                                "sdb",
                                "nvme",
                                "ata",
                                "scsi",
                                "i/o error",
                                "sector",
                                "block",
                                "drive",
                            ]
                        ):
                            entries.append(
                                {
                                    "timestamp": self._format_journal_timestamp(
                                        entry.get("__REALTIME_TIMESTAMP")
                                    ),
                                    "message": msg[:500],
                                }
                            )
                    except json.JSONDecodeError:
                        pass

        return entries[:20]

    @staticmethod
    def _format_journal_timestamp(timestamp: str | int | None) -> str:
        """Format journald timestamp to ISO format."""
        if not timestamp:
            return ""

        try:
            # Journald timestamps are in microseconds since epoch
            ts = int(timestamp) / 1000000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError, OSError):
            return str(timestamp)
