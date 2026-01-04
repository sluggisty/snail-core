"""
Unit tests for ServicesCollector.

Tests systemd unit listing, status, and failed services detection.
"""

from __future__ import annotations

from unittest.mock import patch


from snail_core.collectors.services import ServicesCollector


class TestServicesCollector:
    """Test ServicesCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = ServicesCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "systemd" in result
        assert "running_services" in result
        assert "failed_units" in result
        assert "targets" in result
        assert "timers" in result
        assert "sockets" in result

    def test_get_systemd_info(self):
        """Test systemd info collection."""
        collector = ServicesCollector()
        mock_version = "systemd 250"
        mock_state = "running"
        mock_default = "multi-user.target"
        mock_units = "sshd.service loaded active running"

        def mock_run_command(cmd):
            if "--version" in cmd:
                return (mock_version, "", 0)
            elif "is-system-running" in cmd:
                return (mock_state, "", 0)
            elif "get-default" in cmd:
                return (mock_default, "", 0)
            elif "list-units" in cmd:
                return (mock_units, "", 0)
            return ("", "", 1)

        with patch.object(collector, "run_command", side_effect=mock_run_command):
            result = collector._get_systemd_info()
            assert "version" in result or "system_state" in result

    def test_get_failed_units(self):
        """Test failed units detection."""
        collector = ServicesCollector()
        mock_output = "UNIT          LOAD   ACTIVE SUB\nfailed.service loaded failed failed"

        with patch.object(collector, "run_command", return_value=(mock_output, "", 0)):
            result = collector._get_failed_units()
            assert isinstance(result, list)

    def test_get_running_services(self):
        """Test running services detection."""
        collector = ServicesCollector()
        mock_output = "UNIT          LOAD   ACTIVE SUB\nsshd.service  loaded active running"

        with patch.object(collector, "run_command", return_value=(mock_output, "", 0)):
            result = collector._get_running_services()
            assert isinstance(result, list)
