"""
Unit tests for LogsCollector.

Tests journald logs, boot logs, kernel errors, and auth failures collection.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from snail_core.collectors.logs import LogsCollector


class TestLogsCollector:
    """Test LogsCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = LogsCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "journald" in result
        assert "boot_logs" in result
        assert "kernel_errors" in result

    def test_get_journald_info(self):
        """Test journald status collection."""
        collector = LogsCollector()
        mock_usage = "Archived and active journals take up 512.0M in the file system."
        mock_boots = "0 abc123 2024-01-01 10:00:00\n1 def456 2024-01-02 11:00:00"

        with patch.object(collector, "run_command", side_effect=[
            (mock_usage, "", 0),  # disk-usage
            (mock_boots, "", 0),  # list-boots
        ]):
            with patch.object(collector, "parse_key_value_file", return_value={}):
                result = collector._get_journald_info()
                assert "disk_usage" in result
                assert "boot_count" in result

    def test_get_boot_logs(self):
        """Test boot log parsing."""
        collector = LogsCollector()
        mock_json = '{"__REALTIME_TIMESTAMP": "1704110400000000", "PRIORITY": "4", "MESSAGE": "test"}'

        with patch.object(collector, "run_command", return_value=(mock_json, "", 0)):
            result = collector._get_boot_logs()
            assert isinstance(result, list)

    def test_get_kernel_errors(self):
        """Test kernel error collection."""
        collector = LogsCollector()
        mock_json = '{"__REALTIME_TIMESTAMP": "1704110400000000", "MESSAGE": "kernel error"}'

        with patch.object(collector, "run_command", return_value=(mock_json, "", 0)):
            result = collector._get_kernel_errors()
            assert isinstance(result, list)

    def test_format_journal_timestamp(self):
        """Test journal timestamp formatting."""
        collector = LogsCollector()
        # Test with microsecond timestamp
        result = LogsCollector._format_journal_timestamp("1704110400000000")
        assert isinstance(result, str)
        assert len(result) > 0

        # Test with None
        result = LogsCollector._format_journal_timestamp(None)
        assert result == ""

