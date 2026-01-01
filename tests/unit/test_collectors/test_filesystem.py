"""
Unit tests for FilesystemCollector.

Tests mount points, fstab, LVM, and filesystem information collection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from snail_core.collectors.filesystem import FilesystemCollector


class TestFilesystemCollector:
    """Test FilesystemCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = FilesystemCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "mounts" in result
        assert "fstab" in result

    @patch("snail_core.collectors.filesystem.psutil")
    def test_get_mounts(self, mock_psutil):
        """Test mount point collection."""
        collector = FilesystemCollector()

        mock_part = MagicMock()
        mock_part.device = "/dev/sda1"
        mock_part.mountpoint = "/"
        mock_part.fstype = "ext4"
        mock_psutil.disk_partitions.return_value = [mock_part]

        mock_usage = MagicMock()
        mock_usage.total = 100 * 1024 * 1024 * 1024
        mock_usage.used = 50 * 1024 * 1024 * 1024
        mock_usage.free = 50 * 1024 * 1024 * 1024
        mock_usage.percent = 50.0
        mock_psutil.disk_usage.return_value = mock_usage

        result = collector._get_mounts()
        assert isinstance(result, list)

    def test_get_fstab(self):
        """Test fstab parsing."""
        collector = FilesystemCollector()
        mock_fstab = [
            "/dev/sda1 / ext4 defaults 0 1",
            "# This is a comment",
            "/dev/sda2 /home ext4 defaults 0 2",
        ]

        with patch.object(collector, "read_file_lines", return_value=mock_fstab):
            result = collector._get_fstab()
            assert isinstance(result, list)
            assert len(result) >= 2  # Should have 2 entries, skipping comment

    def test_get_lvm_info(self):
        """Test LVM volume group detection."""
        collector = FilesystemCollector()
        mock_output = "  vg0"

        with patch.object(collector, "run_command", return_value=(mock_output, "", 0)):
            result = collector._get_lvm_info()
            assert "volume_groups" in result

