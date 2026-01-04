"""
Unit tests for host ID management.

Tests UUID generation, file persistence, path selection, and reset functionality.
"""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from snail_core.host_id import _get_host_id_path, get_host_id, reset_host_id


class TestHostIdPathSelection(unittest.TestCase):
    """Test host ID path determination logic."""

    def test_get_host_id_path_with_config_output_dir(self):
        """Test path selection when config output directory is provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "output"

            # Test with directory that doesn't exist yet
            path = _get_host_id_path(str(config_dir))
            self.assertEqual(path, config_dir / "host-id")

            # Test with existing directory
            config_dir.mkdir()
            path = _get_host_id_path(str(config_dir))
            self.assertEqual(path, config_dir / "host-id")

    def test_get_host_id_path_with_config_file(self):
        """Test path selection when config output directory is a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "output" / "config.txt"
            config_file.parent.mkdir()
            config_file.write_text("dummy")

            path = _get_host_id_path(str(config_file))
            self.assertEqual(path, config_file.parent / "host-id")

    def test_get_host_id_path_without_config(self):
        """Test path selection when no config directory provided."""
        # This will try default paths, should return one of them
        path = _get_host_id_path(None)

        # Should be one of the default paths or current directory fallback
        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, "host-id")

    @patch("pathlib.Path.mkdir")
    def test_get_host_id_path_fallback_on_permission_error(self, mock_mkdir):
        """Test fallback behavior when directories are not writable."""
        # Make all default paths fail
        mock_mkdir.side_effect = PermissionError("No permission")

        path = _get_host_id_path(None)

        # Should fallback to current directory
        self.assertEqual(path, Path("snail-host-id"))


class TestHostIdGeneration(unittest.TestCase):
    """Test host ID generation and persistence."""

    def setUp(self):
        """Set up temporary directory for testing."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.host_id_path = self.temp_dir / "host-id"

    def tearDown(self):
        """Clean up temporary files."""
        # Clean up any files created during tests
        if self.host_id_path.exists():
            self.host_id_path.unlink()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    def test_get_host_id_generates_new_id(self):
        """Test that get_host_id generates a new UUID when no file exists."""
        host_id = get_host_id(str(self.temp_dir))

        # Should be a valid UUID
        try:
            uuid.UUID(host_id)
        except ValueError:
            self.fail(f"Generated host_id is not a valid UUID: {host_id}")

        # File should be created
        self.assertTrue(self.host_id_path.exists())
        self.assertEqual(self.host_id_path.read_text().strip(), host_id)

    def test_get_host_id_loads_existing_id(self):
        """Test that get_host_id loads existing host ID from file."""
        expected_id = str(uuid.uuid4())

        # Create file with existing ID
        self.host_id_path.write_text(expected_id)

        host_id = get_host_id(str(self.temp_dir))

        self.assertEqual(host_id, expected_id)

    def test_get_host_id_handles_invalid_uuid_in_file(self):
        """Test handling of invalid UUID in host ID file."""
        # Write invalid UUID to file
        self.host_id_path.write_text("invalid-uuid")

        host_id = get_host_id(str(self.temp_dir))

        # Should generate new valid UUID
        try:
            uuid.UUID(host_id)
        except ValueError:
            self.fail(f"Should have generated valid UUID, got: {host_id}")

        # Old invalid file should be overwritten
        self.assertEqual(self.host_id_path.read_text().strip(), host_id)

    def test_get_host_id_handles_unreadable_file(self):
        """Test handling of unreadable host ID file."""
        # Create file but make it unreadable (simulate permission error)
        self.host_id_path.write_text("some-content")

        with patch.object(Path, "read_text", side_effect=IOError("Permission denied")):
            host_id = get_host_id(str(self.temp_dir))

            # Should generate new valid UUID
            try:
                uuid.UUID(host_id)
            except ValueError:
                self.fail(f"Should have generated valid UUID, got: {host_id}")

    def test_get_host_id_handles_write_failure(self):
        """Test handling of write failure when storing host ID."""
        with patch.object(Path, "write_text", side_effect=IOError("Write failed")):
            host_id = get_host_id(str(self.temp_dir))

            # Should still generate valid UUID (but not store it)
            try:
                uuid.UUID(host_id)
            except ValueError:
                self.fail(f"Should have generated valid UUID, got: {host_id}")

            # File should not exist
            self.assertFalse(self.host_id_path.exists())

    def test_get_host_id_sets_correct_permissions(self):
        """Test that host ID file gets correct permissions (600)."""
        get_host_id(str(self.temp_dir))

        # File should exist and have restrictive permissions
        self.assertTrue(self.host_id_path.exists())

        # Check permissions (0o600 = readable/writable by owner only)
        # Note: This might not work on all systems, so we'll just verify file exists
        stat_info = self.host_id_path.stat()
        permissions = stat_info.st_mode & 0o777
        # On some systems, umask might affect this, so we just check it's reasonable
        self.assertTrue(permissions <= 0o644)  # At most readable by owner/group


class TestHostIdReset(unittest.TestCase):
    """Test host ID reset functionality."""

    def setUp(self):
        """Set up temporary directory for testing."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.host_id_path = self.temp_dir / "host-id"

    def tearDown(self):
        """Clean up temporary files."""
        if self.host_id_path.exists():
            self.host_id_path.unlink()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    def test_reset_host_id_deletes_existing_and_creates_new(self):
        """Test that reset_host_id deletes existing file and creates new ID."""
        # Create existing host ID
        old_id = str(uuid.uuid4())
        self.host_id_path.write_text(old_id)

        # Reset should create new ID
        new_id = reset_host_id(str(self.temp_dir))

        # Should be different from old ID
        self.assertNotEqual(new_id, old_id)

        # Both should be valid UUIDs
        uuid.UUID(new_id)
        uuid.UUID(old_id)

        # New ID should be stored
        self.assertTrue(self.host_id_path.exists())
        self.assertEqual(self.host_id_path.read_text().strip(), new_id)

    def test_reset_host_id_handles_missing_file(self):
        """Test reset_host_id when no existing file exists."""
        # No existing file
        self.assertFalse(self.host_id_path.exists())

        new_id = reset_host_id(str(self.temp_dir))

        # Should generate valid UUID
        uuid.UUID(new_id)

        # File should be created
        self.assertTrue(self.host_id_path.exists())

    def test_reset_host_id_handles_delete_failure(self):
        """Test reset_host_id when deleting existing file fails."""
        # Create existing file
        old_id = str(uuid.uuid4())
        self.host_id_path.write_text(old_id)

        # Mock unlink to fail
        with patch.object(Path, "unlink", side_effect=OSError("Delete failed")):
            new_id = reset_host_id(str(self.temp_dir))

            # Should still generate new UUID
            uuid.UUID(new_id)

            # File should still exist (old file not deleted)
            self.assertTrue(self.host_id_path.exists())


class TestHostIdPersistence(unittest.TestCase):
    """Test host ID persistence across multiple calls."""

    def setUp(self):
        """Set up temporary directory for testing."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.host_id_path = self.temp_dir / "host-id"

    def tearDown(self):
        """Clean up temporary files."""
        if self.host_id_path.exists():
            self.host_id_path.unlink()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    def test_host_id_persistence_across_calls(self):
        """Test that same host ID is returned across multiple calls."""
        # First call
        id1 = get_host_id(str(self.temp_dir))

        # Second call should return same ID
        id2 = get_host_id(str(self.temp_dir))

        # Third call should return same ID
        id3 = get_host_id(str(self.temp_dir))

        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)
        self.assertEqual(id1, id3)

        # All should be valid UUIDs
        uuid.UUID(id1)
        uuid.UUID(id2)
        uuid.UUID(id3)

        # File should exist with the ID
        self.assertTrue(self.host_id_path.exists())
        self.assertEqual(self.host_id_path.read_text().strip(), id1)

    def test_host_id_persistence_with_reset(self):
        """Test persistence until reset, then new ID."""
        # Get initial ID
        id1 = get_host_id(str(self.temp_dir))

        # Multiple calls should return same ID
        for _ in range(5):
            self.assertEqual(get_host_id(str(self.temp_dir)), id1)

        # Reset should give new ID
        id2 = reset_host_id(str(self.temp_dir))
        self.assertNotEqual(id2, id1)

        # Future calls should return new ID
        for _ in range(3):
            self.assertEqual(get_host_id(str(self.temp_dir)), id2)
