"""
Unit tests for HardwareCollector.

Tests CPU, memory, disk, and hardware device collection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from snail_core.collectors.hardware import HardwareCollector


class TestHardwareCollector:
    """Test HardwareCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = HardwareCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "cpu" in result
        assert "memory" in result
        assert "swap" in result
        assert "disks" in result

    @patch("snail_core.collectors.hardware.psutil")
    def test_get_cpu_info(self, mock_psutil):
        """Test CPU info collection."""
        collector = HardwareCollector()
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_freq.return_value = MagicMock(current=2400.0, min=800.0, max=2400.0)
        mock_psutil.cpu_percent.return_value = [10.0, 20.0, 30.0, 40.0]

        with patch.object(
            collector, "read_file", return_value="model_name\t: Test CPU\nvendor_id\t: GenuineIntel"
        ):
            result = collector._get_cpu_info()

            assert "physical_cores" in result
            assert "logical_cores" in result
            assert "frequency" in result

    @patch("snail_core.collectors.hardware.psutil")
    def test_get_memory_info(self, mock_psutil):
        """Test memory info collection."""
        collector = HardwareCollector()
        mock_mem = MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_mem.available = 4 * 1024 * 1024 * 1024  # 4GB
        mock_mem.used = 4 * 1024 * 1024 * 1024
        mock_mem.free = 4 * 1024 * 1024 * 1024
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        with patch.object(
            collector,
            "read_file_lines",
            return_value=["MemTotal:       8192 kB", "MemFree:        4096 kB"],
        ):
            result = collector._get_memory_info()

            assert "total" in result
            assert "available" in result
            assert "used" in result
            assert "percent_used" in result

    def test_bytes_to_human(self):
        """Test bytes to human readable conversion."""
        assert HardwareCollector._bytes_to_human(1024) == "1.0 KB"
        assert HardwareCollector._bytes_to_human(1024 * 1024) == "1.0 MB"
        assert HardwareCollector._bytes_to_human(1024 * 1024 * 1024) == "1.0 GB"

    @patch("snail_core.collectors.hardware.psutil")
    def test_get_disk_info(self, mock_psutil):
        """Test disk info collection."""
        collector = HardwareCollector()
        mock_partition = MagicMock()
        mock_partition.device = "/dev/sda1"
        mock_partition.mountpoint = "/"
        mock_partition.fstype = "ext4"
        mock_partition.opts = "rw,relatime"
        mock_psutil.disk_partitions.return_value = [mock_partition]

        mock_usage = MagicMock()
        mock_usage.total = 100 * 1024 * 1024 * 1024  # 100GB
        mock_usage.used = 50 * 1024 * 1024 * 1024
        mock_usage.free = 50 * 1024 * 1024 * 1024
        mock_usage.percent = 50.0
        mock_psutil.disk_usage.return_value = mock_usage

        result = collector._get_disk_info()
        assert "partitions" in result
        assert len(result["partitions"]) > 0
