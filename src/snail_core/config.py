"""
Configuration management for Snail Core.

Supports configuration via YAML files, environment variables, and programmatic access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATHS = [
    Path("/etc/snail-core/config.yaml"),
    Path.home() / ".config" / "snail-core" / "config.yaml",
    Path("snail-config.yaml"),
]


@dataclass
class Config:
    """
    Configuration container for Snail Core.

    Priority (highest to lowest):
    1. Programmatic values passed to __init__
    2. Environment variables (prefixed with SNAIL_)
    3. Config file values
    4. Default values
    """

    # Upload settings
    upload_url: str | None = None
    upload_enabled: bool = True
    upload_timeout: int = 30
    upload_retries: int = 3

    # Authentication
    api_key: str | None = None
    auth_cert_path: str | None = None
    auth_key_path: str | None = None

    # Collection settings
    enabled_collectors: list[str] = field(default_factory=list)
    disabled_collectors: list[str] = field(default_factory=list)
    collection_timeout: int = 300

    # Output settings
    output_dir: str = "/var/lib/snail-core"
    keep_local_copy: bool = False
    compress_output: bool = True

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None

    # Privacy
    anonymize_hostnames: bool = False
    redact_passwords: bool = True
    exclude_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> Config:
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create config from a dictionary."""
        # Flatten nested structure if present
        flat = {}
        for key, value in data.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    flat[subkey] = subvalue
            else:
                flat[key] = value

        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in flat.items() if k in known_fields}

        return cls(**filtered)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """
        Load configuration with full resolution order.

        Args:
            config_path: Explicit path to config file. If None, searches
                        default locations.

        Returns:
            Fully resolved Config instance.
        """
        base_config: dict[str, Any] = {}

        # Find and load config file
        if config_path:
            path = Path(config_path)
            if path.exists():
                with open(path) as f:
                    base_config = yaml.safe_load(f) or {}
        else:
            for path in DEFAULT_CONFIG_PATHS:
                if path.exists():
                    with open(path) as f:
                        base_config = yaml.safe_load(f) or {}
                    break

        # Create config from file
        config = cls.from_dict(base_config) if base_config else cls()

        # Override with environment variables
        config._apply_env_overrides()

        return config

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        env_mappings = {
            "SNAIL_UPLOAD_URL": "upload_url",
            "SNAIL_UPLOAD_ENABLED": "upload_enabled",
            "SNAIL_UPLOAD_TIMEOUT": "upload_timeout",
            "SNAIL_API_KEY": "api_key",
            "SNAIL_AUTH_CERT": "auth_cert_path",
            "SNAIL_AUTH_KEY": "auth_key_path",
            "SNAIL_OUTPUT_DIR": "output_dir",
            "SNAIL_LOG_LEVEL": "log_level",
            "SNAIL_LOG_FILE": "log_file",
        }

        for env_var, attr in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Type coercion
                current = getattr(self, attr)
                if isinstance(current, bool):
                    setattr(self, attr, value.lower() in ("true", "1", "yes"))
                elif isinstance(current, int):
                    setattr(self, attr, int(value))
                else:
                    setattr(self, attr, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "upload": {
                "url": self.upload_url,
                "enabled": self.upload_enabled,
                "timeout": self.upload_timeout,
                "retries": self.upload_retries,
            },
            "auth": {
                "api_key": "***" if self.api_key else None,
                "cert_path": self.auth_cert_path,
                "key_path": self.auth_key_path,
            },
            "collection": {
                "enabled_collectors": self.enabled_collectors,
                "disabled_collectors": self.disabled_collectors,
                "timeout": self.collection_timeout,
            },
            "output": {
                "dir": self.output_dir,
                "keep_local": self.keep_local_copy,
                "compress": self.compress_output,
            },
            "logging": {
                "level": self.log_level,
                "file": self.log_file,
            },
            "privacy": {
                "anonymize_hostnames": self.anonymize_hostnames,
                "redact_passwords": self.redact_passwords,
                "exclude_paths": self.exclude_paths,
            },
        }

    def save(self, path: str | Path) -> None:
        """Save configuration to a YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
