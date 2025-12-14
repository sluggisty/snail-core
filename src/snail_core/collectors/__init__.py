"""
System data collectors for Snail Core.

Each collector is responsible for gathering specific system information.
Collectors follow a plugin architecture and are auto-discovered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from snail_core.collectors.base import BaseCollector
from snail_core.collectors.filesystem import FilesystemCollector
from snail_core.collectors.hardware import HardwareCollector
from snail_core.collectors.logs import LogsCollector
from snail_core.collectors.network import NetworkCollector
from snail_core.collectors.packages import PackagesCollector
from snail_core.collectors.security import SecurityCollector
from snail_core.collectors.services import ServicesCollector
from snail_core.collectors.system import SystemCollector

if TYPE_CHECKING:
    pass

# Registry of all available collectors (excluding vulnerabilities and compliance)
COLLECTORS: dict[str, type[BaseCollector]] = {
    "system": SystemCollector,
    "hardware": HardwareCollector,
    "network": NetworkCollector,
    "packages": PackagesCollector,
    "services": ServicesCollector,
    "filesystem": FilesystemCollector,
    "security": SecurityCollector,
    "logs": LogsCollector,
}


def get_all_collectors() -> dict[str, type[BaseCollector]]:
    """Return all registered collectors."""
    return COLLECTORS.copy()


def get_collector(name: str) -> type[BaseCollector] | None:
    """Get a specific collector by name."""
    return COLLECTORS.get(name)


def list_collectors() -> list[str]:
    """List all available collector names."""
    return list(COLLECTORS.keys())


__all__ = [
    "BaseCollector",
    "SystemCollector",
    "HardwareCollector",
    "NetworkCollector",
    "PackagesCollector",
    "ServicesCollector",
    "FilesystemCollector",
    "SecurityCollector",
    "LogsCollector",
    "get_all_collectors",
    "get_collector",
    "list_collectors",
    "COLLECTORS",
]
