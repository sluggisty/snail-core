"""
Authentication helper for Snail Core.

Handles API key retrieval and configuration updates.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import requests
import yaml

if TYPE_CHECKING:
    from snail_core.config import Config

DEFAULT_CONFIG_PATHS = [
    Path("/etc/snail-core/config.yaml"),
    Path.home() / ".config" / "snail-core" / "config.yaml",
    Path("snail-config.yaml"),
]


def get_api_key_from_server(
    upload_url: str,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """
    Request an API key from the server using username/password.

    Args:
        upload_url: The upload endpoint URL (e.g., http://localhost:8080/api/v1/ingest)
        username: Username for authentication
        password: Password for authentication

    Returns:
        API key string if successful, None otherwise
    """
    # Extract base URL from upload URL
    # e.g., http://localhost:8080/api/v1/ingest -> http://localhost:8080/api/v1
    if "/ingest" in upload_url:
        base_url = upload_url.rsplit("/ingest", 1)[0]
    else:
        # Fallback: remove last path component
        parts = upload_url.rstrip("/").rsplit("/", 1)
        base_url = parts[0] if len(parts) > 1 else upload_url

    # Ensure base_url ends with /api/v1
    if not base_url.endswith("/api/v1"):
        if base_url.endswith("/api"):
            base_url = base_url + "/v1"
        elif "/api" not in base_url:
            # Assume we need to add /api/v1
            base_url = base_url.rstrip("/") + "/api/v1"

    api_key_endpoint = urljoin(base_url + "/", "auth/api-key")

    if not username or not password:
        return None

    try:
        response = requests.post(
            api_key_endpoint,
            json={"username": username, "password": password},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        api_key = data.get("key")
        if isinstance(api_key, str):
            return api_key
        return None
    except requests.exceptions.RequestException:
        return None


def ensure_api_key(config: "Config", upload_url: str | None = None) -> bool:
    """
    Ensure API key is configured. If missing, try to get it from server.

    Args:
        config: The configuration object
        upload_url: Optional upload URL (if not in config)

    Returns:
        True if API key is available, False otherwise
    """
    # If API key already exists, we're good
    if config.api_key:
        return True

    # Need upload URL to determine server endpoint
    url = upload_url or config.upload_url
    if not url:
        return False

    # Try to get credentials from environment
    username = os.environ.get("SNAIL_USERNAME")
    password = os.environ.get("SNAIL_PASSWORD")

    if not username or not password:
        return False

    # Request API key from server
    api_key = get_api_key_from_server(url, username, password)
    if not api_key:
        return False

    # Save API key to config file
    config.api_key = api_key
    save_api_key_to_config(api_key)

    return True


def save_api_key_to_config(api_key: str, config_path: Path | None = None) -> bool:
    """
    Save API key to the configuration file.

    Args:
        api_key: The API key to save
        config_path: Optional explicit config path

    Returns:
        True if saved successfully, False otherwise
    """
    # Find config file
    if config_path:
        config_file = config_path
    else:
        config_file = None
        for path in DEFAULT_CONFIG_PATHS:
            if path.exists():
                config_file = path
                break

    if not config_file:
        # Use default system config path
        config_file = DEFAULT_CONFIG_PATHS[0]
        config_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or create new
    config_data: dict = {}
    if config_file.exists():
        with open(config_file) as f:
            config_data = yaml.safe_load(f) or {}

    # Update API key in config
    if "auth" not in config_data:
        config_data["auth"] = {}
    config_data["auth"]["api_key"] = api_key

    # Save config
    try:
        with open(config_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        return True
    except (OSError, PermissionError):
        # Can't write to config file (e.g., /etc/snail-core/config.yaml)
        # This is OK, the API key will be used from memory
        return False
