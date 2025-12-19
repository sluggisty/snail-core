"""
Host ID management for Snail Core.

Generates and stores a persistent UUID for each host to uniquely identify
it across all collections and uploads.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Default locations for storing host ID (in order of preference)
DEFAULT_HOST_ID_PATHS = [
    Path("/var/lib/snail-core/host-id"),  # System-wide
    Path.home() / ".config" / "snail-core" / "host-id",  # User-specific
    Path("snail-host-id"),  # Current directory (fallback)
]


def get_host_id(config_output_dir: str | None = None) -> str:
    """
    Get or create a persistent host ID for this system.

    The host ID is a UUID that uniquely identifies this host across all
    collections. It is stored persistently and reused for all uploads.

    Args:
        config_output_dir: Optional output directory from config. If provided,
                         will use {output_dir}/host-id for storage.

    Returns:
        The host UUID as a string.
    """
    # Determine where to store the host ID
    host_id_path = _get_host_id_path(config_output_dir)

    # Try to read existing host ID
    if host_id_path.exists():
        try:
            host_id = host_id_path.read_text().strip()
            # Validate it's a valid UUID
            uuid.UUID(host_id)
            logger.debug(f"Using existing host ID from {host_id_path}")
            return host_id
        except (ValueError, IOError) as e:
            logger.warning(f"Invalid or unreadable host ID file: {e}. Generating new ID.")

    # Generate new host ID
    host_id = str(uuid.uuid4())

    # Store it
    try:
        host_id_path.parent.mkdir(parents=True, exist_ok=True)
        host_id_path.write_text(host_id)
        # Set restrictive permissions (readable only by owner)
        host_id_path.chmod(0o600)
        logger.info(f"Generated and stored new host ID: {host_id} at {host_id_path}")
    except (IOError, OSError) as e:
        logger.warning(
            f"Failed to write host ID to {host_id_path}: {e}. "
            f"Using ephemeral ID for this session."
        )

    return host_id


def _get_host_id_path(config_output_dir: str | None = None) -> Path:
    """
    Determine the path where the host ID should be stored.

    Args:
        config_output_dir: Optional output directory from config.

    Returns:
        Path to the host ID file.
    """
    # If config specifies output_dir, use that location
    if config_output_dir:
        output_path = Path(config_output_dir)
        # Ensure it's a directory
        if output_path.is_dir() or not output_path.exists():
            return output_path / "host-id"
        # If it's a file, use parent directory
        return output_path.parent / "host-id"

    # Otherwise, try default locations in order
    for path in DEFAULT_HOST_ID_PATHS:
        # Check if we can write to this location
        try:
            # Try to create parent directory to test permissions
            path.parent.mkdir(parents=True, exist_ok=True)
            # If we can create parent, we can likely write here
            return path
        except (OSError, PermissionError):
            continue

    # Fallback to current directory
    return Path("snail-host-id")


def reset_host_id(config_output_dir: str | None = None) -> str:
    """
    Reset the host ID by generating a new one.

    This will delete the existing host ID file and create a new UUID.
    Use with caution as this will make the host appear as a new system
    to the server.

    Args:
        config_output_dir: Optional output directory from config.

    Returns:
        The new host UUID as a string.
    """
    host_id_path = _get_host_id_path(config_output_dir)

    # Delete existing file if it exists
    if host_id_path.exists():
        try:
            host_id_path.unlink()
            logger.info(f"Deleted existing host ID file: {host_id_path}")
        except OSError as e:
            logger.warning(f"Failed to delete existing host ID file: {e}")

    # Generate and store new ID
    return get_host_id(config_output_dir)
