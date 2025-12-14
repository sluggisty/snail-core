"""
Filesystem information collector.

Collects filesystem mounts, fstab configuration, and storage information.
"""

from __future__ import annotations

from typing import Any

import psutil

from snail_core.collectors.base import BaseCollector


class FilesystemCollector(BaseCollector):
    """Collects filesystem and mount information."""

    name = "filesystem"
    description = "Filesystem mounts, fstab, and storage configuration"

    def collect(self) -> dict[str, Any]:
        """Collect filesystem information."""
        return {
            "mounts": self._get_mounts(),
            "fstab": self._get_fstab(),
            "lvm": self._get_lvm_info(),
            "btrfs": self._get_btrfs_info(),
            "tmpfs": self._get_tmpfs_info(),
            "inodes": self._get_inode_usage(),
        }

    def _get_mounts(self) -> list[dict[str, Any]]:
        """Get current mount information."""
        mounts = []

        # Parse /proc/mounts for current mounts
        for line in self.read_file_lines("/proc/mounts"):
            parts = line.split()
            if len(parts) >= 4:
                device, mountpoint, fstype, options = (
                    parts[0],
                    parts[1],
                    parts[2],
                    parts[3],
                )

                # Skip pseudo filesystems for basic info
                if fstype in (
                    "proc",
                    "sysfs",
                    "devpts",
                    "cgroup",
                    "cgroup2",
                    "securityfs",
                    "debugfs",
                    "tracefs",
                    "fusectl",
                    "configfs",
                    "pstore",
                    "efivarfs",
                    "bpf",
                ):
                    continue

                mount: dict[str, Any] = {
                    "device": device,
                    "mountpoint": mountpoint,
                    "fstype": fstype,
                    "options": options.split(","),
                }

                # Try to get usage info
                try:
                    usage = psutil.disk_usage(mountpoint)
                    mount["size"] = usage.total
                    mount["used"] = usage.used
                    mount["free"] = usage.free
                    mount["percent_used"] = usage.percent
                except (OSError, PermissionError):
                    pass

                mounts.append(mount)

        return mounts

    def _get_fstab(self) -> list[dict[str, Any]]:
        """Parse /etc/fstab."""
        entries = []

        for line in self.read_file_lines("/etc/fstab"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) >= 4:
                entries.append(
                    {
                        "spec": parts[0],
                        "mountpoint": parts[1],
                        "fstype": parts[2],
                        "options": parts[3].split(","),
                        "dump": int(parts[4]) if len(parts) > 4 else 0,
                        "pass": int(parts[5]) if len(parts) > 5 else 0,
                    }
                )

        return entries

    def _get_lvm_info(self) -> dict[str, Any]:
        """Get LVM (Logical Volume Manager) information."""
        lvm: dict[str, Any] = {
            "installed": False,
            "volume_groups": [],
            "logical_volumes": [],
            "physical_volumes": [],
        }

        # Check for LVM tools
        _, _, rc = self.run_command(["which", "lvm"])
        if rc != 0:
            return lvm

        lvm["installed"] = True

        # Get volume groups
        stdout, _, rc = self.run_command(
            [
                "vgs",
                "--noheadings",
                "--units",
                "b",
                "-o",
                "vg_name,vg_size,vg_free,pv_count,lv_count",
            ]
        )
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 5:
                        lvm["volume_groups"].append(
                            {
                                "name": parts[0],
                                "size": parts[1],
                                "free": parts[2],
                                "pv_count": int(parts[3]),
                                "lv_count": int(parts[4]),
                            }
                        )

        # Get logical volumes
        stdout, _, rc = self.run_command(
            [
                "lvs",
                "--noheadings",
                "--units",
                "b",
                "-o",
                "lv_name,vg_name,lv_size,lv_attr",
            ]
        )
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        lvm["logical_volumes"].append(
                            {
                                "name": parts[0],
                                "vg": parts[1],
                                "size": parts[2],
                                "attr": parts[3],
                            }
                        )

        # Get physical volumes
        stdout, _, rc = self.run_command(
            [
                "pvs",
                "--noheadings",
                "--units",
                "b",
                "-o",
                "pv_name,vg_name,pv_size,pv_free",
            ]
        )
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        lvm["physical_volumes"].append(
                            {
                                "name": parts[0],
                                "vg": parts[1],
                                "size": parts[2],
                                "free": parts[3],
                            }
                        )

        return lvm

    def _get_btrfs_info(self) -> dict[str, Any]:
        """Get Btrfs filesystem information."""
        btrfs: dict[str, Any] = {
            "filesystems": [],
        }

        stdout, _, rc = self.run_command(["btrfs", "filesystem", "show"])
        if rc == 0 and stdout:
            current_fs: dict[str, Any] = {}
            for line in stdout.strip().split("\n"):
                if line.startswith("Label:"):
                    if current_fs:
                        btrfs["filesystems"].append(current_fs)

                    # Parse: Label: 'fedora'  uuid: abc-123
                    parts = line.split()
                    current_fs = {
                        "label": parts[1].strip("'") if len(parts) > 1 else "",
                        "uuid": parts[3] if len(parts) > 3 else "",
                        "devices": [],
                    }
                elif "devid" in line and current_fs:
                    # Parse device line
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "path":
                            current_fs["devices"].append(parts[i + 1] if i + 1 < len(parts) else "")

            if current_fs:
                btrfs["filesystems"].append(current_fs)

        return btrfs

    def _get_tmpfs_info(self) -> list[dict[str, Any]]:
        """Get tmpfs mount information."""
        tmpfs_mounts = []

        for line in self.read_file_lines("/proc/mounts"):
            parts = line.split()
            if len(parts) >= 3 and parts[2] == "tmpfs":
                mountpoint = parts[1]
                try:
                    usage = psutil.disk_usage(mountpoint)
                    tmpfs_mounts.append(
                        {
                            "mountpoint": mountpoint,
                            "size": usage.total,
                            "used": usage.used,
                            "percent_used": usage.percent,
                        }
                    )
                except (OSError, PermissionError):
                    tmpfs_mounts.append(
                        {
                            "mountpoint": mountpoint,
                            "error": "Could not get usage stats",
                        }
                    )

        return tmpfs_mounts

    def _get_inode_usage(self) -> list[dict[str, Any]]:
        """Get inode usage for mounted filesystems."""
        inodes = []

        stdout, _, rc = self.run_command(["df", "-i"])
        if rc == 0 and stdout:
            lines = stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 6:
                    # Skip if inode count is "-" (pseudo filesystems)
                    if parts[1] == "-":
                        continue

                    try:
                        inodes.append(
                            {
                                "filesystem": parts[0],
                                "inodes_total": int(parts[1]),
                                "inodes_used": int(parts[2]),
                                "inodes_free": int(parts[3]),
                                "percent_used": parts[4].rstrip("%"),
                                "mountpoint": parts[5],
                            }
                        )
                    except ValueError:
                        pass

        return inodes
