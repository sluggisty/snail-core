"""
Hardware information collector.

Collects CPU, memory, disk, and other hardware details.
"""

from __future__ import annotations

import os
from typing import Any

import psutil

from snail_core.collectors.base import BaseCollector


class HardwareCollector(BaseCollector):
    """Collects hardware information."""

    name = "hardware"
    description = "CPU, memory, disk, and hardware information"

    def collect(self) -> dict[str, Any]:
        """Collect hardware information."""
        return {
            "cpu": self._get_cpu_info(),
            "memory": self._get_memory_info(),
            "swap": self._get_swap_info(),
            "disks": self._get_disk_info(),
            "block_devices": self._get_block_devices(),
            "pci": self._get_pci_devices(),
            "usb": self._get_usb_devices(),
            "dmi": self._get_dmi_info(),
        }

    def _get_cpu_info(self) -> dict[str, Any]:
        """Get CPU information."""
        cpu_info: dict[str, Any] = {}

        # Parse /proc/cpuinfo
        cpuinfo_content = self.read_file("/proc/cpuinfo")
        if cpuinfo_content:
            for line in cpuinfo_content.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()
                    if key == "model_name":
                        cpu_info["model"] = value
                    elif key == "vendor_id":
                        cpu_info["vendor"] = value
                    elif key == "cpu_mhz":
                        cpu_info["current_mhz"] = float(value)
                    elif key == "cache_size":
                        cpu_info["cache_size"] = value
                    elif key == "flags":
                        cpu_info["flags"] = value.split()

        # Get CPU counts
        cpu_info["physical_cores"] = psutil.cpu_count(logical=False) or 0
        cpu_info["logical_cores"] = psutil.cpu_count(logical=True) or 0

        # Get CPU frequency
        freq = psutil.cpu_freq()
        if freq:
            cpu_info["frequency"] = {
                "current": freq.current,
                "min": freq.min,
                "max": freq.max,
            }

        # Get CPU times percentage
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_info["usage_percent"] = {
            "per_cpu": cpu_percent,
            "average": sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0,
        }

        # Get load average
        load = os.getloadavg()
        cpu_info["load_average"] = {
            "1min": load[0],
            "5min": load[1],
            "15min": load[2],
        }

        return cpu_info

    def _get_memory_info(self) -> dict[str, Any]:
        """Get memory information."""
        mem = psutil.virtual_memory()

        # Parse /proc/meminfo for additional details
        meminfo = {}
        for line in self.read_file_lines("/proc/meminfo"):
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().split()[0]  # Remove 'kB' suffix
                try:
                    meminfo[key] = int(value) * 1024  # Convert to bytes
                except ValueError:
                    pass

        return {
            "total": mem.total,
            "total_human": self._bytes_to_human(mem.total),
            "available": mem.available,
            "available_human": self._bytes_to_human(mem.available),
            "used": mem.used,
            "used_human": self._bytes_to_human(mem.used),
            "free": mem.free,
            "percent_used": mem.percent,
            "buffers": meminfo.get("Buffers", 0),
            "cached": meminfo.get("Cached", 0),
            "shared": meminfo.get("Shmem", 0),
            "slab": meminfo.get("Slab", 0),
            "hugepages_total": meminfo.get("HugePages_Total", 0),
            "hugepages_free": meminfo.get("HugePages_Free", 0),
        }

    def _get_swap_info(self) -> dict[str, Any]:
        """Get swap information."""
        swap = psutil.swap_memory()

        return {
            "total": swap.total,
            "total_human": self._bytes_to_human(swap.total),
            "used": swap.used,
            "free": swap.free,
            "percent_used": swap.percent,
            "sin": swap.sin,
            "sout": swap.sout,
        }

    def _get_disk_info(self) -> dict[str, Any]:
        """Get mounted disk information."""
        partitions = []

        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append(
                    {
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "opts": part.opts,
                        "total": usage.total,
                        "total_human": self._bytes_to_human(usage.total),
                        "used": usage.used,
                        "free": usage.free,
                        "percent_used": usage.percent,
                    }
                )
            except (PermissionError, OSError):
                partitions.append(
                    {
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "opts": part.opts,
                        "error": "Could not get usage stats",
                    }
                )

        # Get disk I/O counters
        io_counters = {}
        try:
            counters = psutil.disk_io_counters(perdisk=True)
            if counters:
                for disk, stats in counters.items():
                    io_counters[disk] = {
                        "read_count": stats.read_count,
                        "write_count": stats.write_count,
                        "read_bytes": stats.read_bytes,
                        "write_bytes": stats.write_bytes,
                        "read_time": stats.read_time,
                        "write_time": stats.write_time,
                    }
        except Exception:
            pass

        return {
            "partitions": partitions,
            "io_counters": io_counters,
        }

    def _get_block_devices(self) -> list[dict[str, Any]]:
        """Get block device information using lsblk."""
        devices = []
        stdout, _, rc = self.run_command(
            [
                "lsblk",
                "-J",
                "-o",
                "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL,ROTA,RO",
            ]
        )

        if rc == 0 and stdout:
            import json

            try:
                data = json.loads(stdout)
                devices = data.get("blockdevices", [])
            except json.JSONDecodeError:
                pass

        return devices

    def _get_pci_devices(self) -> list[dict[str, str]]:
        """Get PCI device information."""
        devices = []
        stdout, _, rc = self.run_command(["lspci", "-mm"])

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split('"')
                    if len(parts) >= 7:
                        devices.append(
                            {
                                "slot": parts[0].strip(),
                                "class": parts[1],
                                "vendor": parts[3],
                                "device": parts[5],
                            }
                        )

        return devices[:50]  # Limit to first 50 devices

    def _get_usb_devices(self) -> list[dict[str, str]]:
        """Get USB device information."""
        devices = []
        stdout, _, rc = self.run_command(["lsusb"])

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    # Parse: Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
                    parts = line.split(":")
                    if len(parts) >= 2:
                        bus_dev = parts[0]
                        rest = ":".join(parts[1:]).strip()

                        id_parts = rest.split(" ", 1)
                        device_id = id_parts[0] if id_parts else ""
                        description = id_parts[1] if len(id_parts) > 1 else ""

                        devices.append(
                            {
                                "bus_device": bus_dev,
                                "id": device_id,
                                "description": description,
                            }
                        )

        return devices

    def _get_dmi_info(self) -> dict[str, str]:
        """Get DMI/SMBIOS information."""
        dmi_paths = {
            "bios_vendor": "/sys/class/dmi/id/bios_vendor",
            "bios_version": "/sys/class/dmi/id/bios_version",
            "bios_date": "/sys/class/dmi/id/bios_date",
            "board_name": "/sys/class/dmi/id/board_name",
            "board_vendor": "/sys/class/dmi/id/board_vendor",
            "board_version": "/sys/class/dmi/id/board_version",
            "chassis_type": "/sys/class/dmi/id/chassis_type",
            "chassis_vendor": "/sys/class/dmi/id/chassis_vendor",
            "product_name": "/sys/class/dmi/id/product_name",
            "product_version": "/sys/class/dmi/id/product_version",
            "sys_vendor": "/sys/class/dmi/id/sys_vendor",
        }

        dmi = {}
        for key, path in dmi_paths.items():
            value = self.read_file(path).strip()
            if value:
                dmi[key] = value

        return dmi

    @staticmethod
    def _bytes_to_human(size: int) -> str:
        """Convert bytes to human readable string."""
        size_float = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size_float) < 1024.0:
                return f"{size_float:.1f} {unit}"
            size_float /= 1024.0
        return f"{size_float:.1f} PB"
