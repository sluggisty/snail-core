"""
Base collector class that all collectors inherit from.
"""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Abstract base class for all data collectors.

    Subclasses must implement the `collect` method to gather
    their specific data.
    """

    name: str = "base"
    description: str = "Base collector"

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        """
        Collect and return data.

        Returns:
            Dictionary of collected data. Structure depends on collector type.
        """
        pass

    def run_command(
        self,
        cmd: list[str],
        timeout: int = 30,
        check: bool = False,
    ) -> tuple[str, str, int]:
        """
        Run a shell command and return output.

        Args:
            cmd: Command and arguments as list.
            timeout: Timeout in seconds.
            check: If True, raise on non-zero exit.

        Returns:
            Tuple of (stdout, stderr, returncode).
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Command timed out: {' '.join(cmd)}")
            return "", "Command timed out", -1
        except FileNotFoundError:
            self.logger.warning(f"Command not found: {cmd[0]}")
            return "", f"Command not found: {cmd[0]}", -1
        except subprocess.CalledProcessError as e:
            return e.stdout or "", e.stderr or "", e.returncode

    def read_file(self, path: str, default: str = "") -> str:
        """
        Read a file and return its contents.

        Args:
            path: Path to the file.
            default: Default value if file cannot be read.

        Returns:
            File contents or default value.
        """
        try:
            with open(path) as f:
                return f.read()
        except OSError as e:
            self.logger.debug(f"Could not read {path}: {e}")
            return default

    def read_file_lines(self, path: str) -> list[str]:
        """Read a file and return lines as list."""
        content = self.read_file(path)
        if content:
            return content.strip().split("\n")
        return []

    def parse_key_value_file(
        self,
        path: str,
        separator: str = "=",
        strip_quotes: bool = True,
    ) -> dict[str, str]:
        """
        Parse a key=value style file.

        Args:
            path: Path to the file.
            separator: Key-value separator character.
            strip_quotes: Whether to strip surrounding quotes from values.

        Returns:
            Dictionary of key-value pairs.
        """
        result = {}
        for line in self.read_file_lines(path):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if separator in line:
                key, _, value = line.partition(separator)
                key = key.strip()
                value = value.strip()
                if strip_quotes and len(value) >= 2:
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                result[key] = value
        return result

    def detect_distro(self) -> dict[str, str]:
        """
        Detect Linux distribution information.

        Returns:
            Dictionary with 'id', 'version', 'name' keys.
        """
        try:
            import distro

            return {
                "id": distro.id(),
                "version": distro.version(),
                "name": distro.name(pretty=True),
                "like": distro.like(),
            }
        except ImportError:
            # Fallback to /etc/os-release
            os_release = self.parse_key_value_file("/etc/os-release")
            return {
                "id": os_release.get("ID", "unknown"),
                "version": os_release.get("VERSION_ID", ""),
                "name": os_release.get("PRETTY_NAME", os_release.get("NAME", "Unknown")),
                "like": os_release.get("ID_LIKE", ""),
            }
