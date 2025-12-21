"""
System information collector.

Collects OS version, kernel, hostname, uptime, and general system info.
"""

from __future__ import annotations

import os
import platform
import socket
from datetime import datetime, timezone
from typing import Any

import distro
import psutil

from snail_core.collectors.base import BaseCollector


class SystemCollector(BaseCollector):
    """Collects general system and OS information."""

    name = "system"
    description = "Operating system and general system information"

    def collect(self) -> dict[str, Any]:
        """Collect system information."""
        return {
            "os": self._get_os_info(),
            "kernel": self._get_kernel_info(),
            "hostname": self._get_hostname_info(),
            "uptime": self._get_uptime_info(),
            "boot": self._get_boot_info(),
            "users": self._get_users_info(),
            "locale": self._get_locale_info(),
            "timezone": self._get_timezone_info(),
            "virtualization": self._get_virtualization_info(),
        }

    def _get_os_info(self) -> dict[str, Any]:
        """Get operating system information."""

        os_release = self.parse_key_value_file("/etc/os-release")

        distro_id = distro.id()
        version_id = distro.version()
        version_pretty = distro.version(pretty=True)

        # Parse version into major, minor, and patch components based on distribution
        version_parts = self._parse_version(distro_id, version_id, version_pretty)

        return {
            "name": distro.name(pretty=True),
            "id": distro_id,
            "version": version_pretty,
            "version_id": version_id,
            "version_major": version_parts.get("major"),
            "version_minor": version_parts.get("minor"),
            "version_patch": version_parts.get("patch"),
            "codename": distro.codename(),
            "like": distro.like(),
            "variant": os_release.get("VARIANT", ""),
            "variant_id": os_release.get("VARIANT_ID", ""),
            "platform_id": os_release.get("PLATFORM_ID", ""),
            "architecture": platform.machine(),
            "platform": platform.platform(),
        }

    def _parse_version(
        self, distro_id: str, version_id: str, version_pretty: str
    ) -> dict[str, str | None]:
        """
        Parse version string into major, minor, and patch components.

        Handles different versioning schemes:
        - RHEL/CentOS: major.minor (e.g., 9.2, 8.5)
        - Fedora: sequential number (e.g., 38, 39)
        - Debian: major.minor (e.g., 11.7, 12.2)
        - Ubuntu: year.month (e.g., 22.04, 23.10)
        - openSUSE Leap: major.minor (e.g., 15.4, 15.5)
        """
        import re

        if not version_id:
            return {"major": None, "minor": None, "patch": None}

        # Normalize version_id - remove any non-numeric prefixes/suffixes
        version_clean = re.sub(r"[^\d.]", "", str(version_id))

        # Split by dots
        parts = version_clean.split(".")

        major = parts[0] if len(parts) > 0 and parts[0] else None
        minor = parts[1] if len(parts) > 1 and parts[1] else None
        patch = parts[2] if len(parts) > 2 and parts[2] else None

        # Special handling for Ubuntu (year.month format)
        if distro_id in ("ubuntu", "ubuntu-core"):
            # For Ubuntu, major is year, minor is month
            # e.g., 22.04 -> major=22, minor=04
            pass  # Already handled by split

        # Special handling for Fedora (single number)
        elif distro_id in ("fedora",):
            # Fedora uses single number, treat as major
            # e.g., 38 -> major=38, minor=None
            minor = None
            patch = None

        # For distributions with major.minor format (RHEL, Debian, CentOS, openSUSE)
        # Already handled by split

        return {
            "major": major,
            "minor": minor,
            "patch": patch,
        }

    def _get_kernel_info(self) -> dict[str, Any]:
        """Get kernel information."""
        uname = platform.uname()

        # Get kernel parameters
        cmdline = self.read_file("/proc/cmdline").strip()

        # Get kernel modules count
        modules_output, _, _ = self.run_command(["lsmod"])
        modules_count = len(modules_output.strip().split("\n")) - 1 if modules_output else 0

        return {
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "cmdline": cmdline,
            "modules_loaded": modules_count,
        }

    def _get_hostname_info(self) -> dict[str, Any]:
        """Get hostname information."""
        hostname = socket.gethostname()

        try:
            fqdn = socket.getfqdn()
        except Exception:
            fqdn = hostname

        # Try to get hostnamectl info
        hostnamectl = {}
        stdout, _, rc = self.run_command(["hostnamectl", "status", "--json=short"])
        if rc == 0 and stdout:
            import json

            try:
                hostnamectl = json.loads(stdout)
            except json.JSONDecodeError:
                pass

        return {
            "hostname": hostname,
            "fqdn": fqdn,
            "static_hostname": hostnamectl.get("StaticHostname", hostname),
            "icon_name": hostnamectl.get("IconName", ""),
            "chassis": hostnamectl.get("Chassis", ""),
            "deployment": hostnamectl.get("Deployment", ""),
            "location": hostnamectl.get("Location", ""),
        }

    def _get_uptime_info(self) -> dict[str, Any]:
        """Get system uptime information."""
        boot_time = psutil.boot_time()
        boot_datetime = datetime.fromtimestamp(boot_time, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        uptime_seconds = (now - boot_datetime).total_seconds()

        # Calculate human-readable uptime
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        return {
            "seconds": uptime_seconds,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "human_readable": f"{days}d {hours}h {minutes}m",
            "boot_time": boot_datetime.isoformat(),
        }

    def _get_boot_info(self) -> dict[str, Any]:
        """Get boot-related information."""
        # Check if system uses UEFI or BIOS
        is_uefi = os.path.isdir("/sys/firmware/efi")

        # Get secure boot status
        secure_boot = False
        if is_uefi:
            sb_content = self.read_file("/sys/firmware/efi/efivars/SecureBoot-*", "")
            if sb_content:
                secure_boot = sb_content[-1:] == "\x01"

        return {
            "firmware": "UEFI" if is_uefi else "BIOS",
            "secure_boot": secure_boot,
        }

    def _get_users_info(self) -> dict[str, Any]:
        """Get current users information."""
        users = psutil.users()

        return {
            "logged_in_count": len(users),
            "users": [
                {
                    "name": u.name,
                    "terminal": u.terminal or "",
                    "host": u.host or "local",
                    "started": datetime.fromtimestamp(u.started, tz=timezone.utc).isoformat(),
                }
                for u in users
            ],
        }

    def _get_locale_info(self) -> dict[str, Any]:
        """Get locale settings."""
        locale_vars = {
            "LANG": os.environ.get("LANG", ""),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "LC_CTYPE": os.environ.get("LC_CTYPE", ""),
            "LC_MESSAGES": os.environ.get("LC_MESSAGES", ""),
        }

        # Also check /etc/locale.conf
        locale_conf = self.parse_key_value_file("/etc/locale.conf")
        locale_vars.update({k: v for k, v in locale_conf.items() if k.startswith("L")})

        return locale_vars

    def _get_timezone_info(self) -> dict[str, Any]:
        """Get timezone information."""
        # Read /etc/localtime symlink target
        tz_name = ""
        try:
            link = os.readlink("/etc/localtime")
            if "zoneinfo/" in link:
                tz_name = link.split("zoneinfo/")[-1]
        except OSError:
            pass

        # Also check /etc/timezone if it exists
        if not tz_name:
            tz_name = self.read_file("/etc/timezone").strip()

        return {
            "name": tz_name,
            "offset": datetime.now().astimezone().strftime("%z"),
        }

    def _get_virtualization_info(self) -> dict[str, Any]:
        """Detect virtualization environment."""
        virt_type = "none"
        container = "none"

        # Check systemd-detect-virt
        stdout, _, rc = self.run_command(["systemd-detect-virt"])
        if rc == 0 and stdout.strip() and stdout.strip() != "none":
            virt_type = stdout.strip()

        # Check for container
        stdout, _, rc = self.run_command(["systemd-detect-virt", "--container"])
        if rc == 0 and stdout.strip() and stdout.strip() != "none":
            container = stdout.strip()
            virt_type = container

        # Check specific virtualization indicators
        dmi_vendor = self.read_file("/sys/class/dmi/id/sys_vendor").strip().lower()
        product_name = self.read_file("/sys/class/dmi/id/product_name").strip().lower()

        hypervisor = ""
        if "vmware" in dmi_vendor or "vmware" in product_name:
            hypervisor = "vmware"
        elif "virtualbox" in dmi_vendor or "virtualbox" in product_name:
            hypervisor = "virtualbox"
        elif "kvm" in dmi_vendor or "qemu" in product_name:
            hypervisor = "kvm"
        elif "microsoft" in dmi_vendor and "virtual" in product_name:
            hypervisor = "hyperv"
        elif "xen" in dmi_vendor:
            hypervisor = "xen"

        return {
            "type": virt_type,
            "container": container,
            "hypervisor": hypervisor,
            "is_virtual": virt_type != "none" or hypervisor != "",
        }
