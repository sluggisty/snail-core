"""
Unit tests for SecurityCollector.

Tests SELinux, AppArmor, firewall, and security configuration detection.
"""

from __future__ import annotations

from unittest.mock import patch

from snail_core.collectors.security import SecurityCollector


class TestSecurityCollector:
    """Test SecurityCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = SecurityCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "selinux" in result
        assert "apparmor" in result
        assert "firewall" in result

    def test_get_selinux_info_enabled(self):
        """Test SELinux status detection when enabled."""
        collector = SecurityCollector()

        with patch.object(collector, "read_file", return_value="1"):
            with patch.object(collector, "run_command", return_value=("Enforcing", "", 0)):
                with patch.object(
                    collector, "parse_key_value_file", return_value={"SELINUX": "enforcing"}
                ):
                    result = collector._get_selinux_info()

                    assert result["available"] is True
                    assert result["enabled"] is True
                    assert "mode" in result

    def test_get_selinux_info_disabled(self):
        """Test SELinux status when not available."""
        collector = SecurityCollector()

        with patch.object(collector, "read_file", return_value=""):
            result = collector._get_selinux_info()
            assert result["available"] is False

    def test_get_apparmor_info(self):
        """Test AppArmor status detection."""
        collector = SecurityCollector()
        mock_output = "10 profiles are loaded\n5 profiles are in enforce mode"

        with patch.object(collector, "run_command", return_value=(mock_output, "", 0)):
            result = collector._get_apparmor_info()
            assert result["available"] is True
            assert "profiles" in result

    def test_get_firewall_status_firewalld(self):
        """Test firewall detection for firewalld."""
        collector = SecurityCollector()

        with patch.object(collector, "run_command", return_value=("active", "", 0)):
            result = collector._get_firewall_status()
            assert result["type"] == "firewalld"
            assert result["running"] is True

    def test_get_firewall_status_ufw(self):
        """Test firewall detection for ufw."""
        collector = SecurityCollector()

        with patch.object(
            collector,
            "run_command",
            side_effect=[
                ("inactive", "", 1),  # firewalld check fails
                ("Status: active", "", 0),  # ufw status
            ],
        ):
            result = collector._get_firewall_status()
            assert result["type"] == "ufw"

    def test_get_sshd_config(self):
        """Test SSH daemon configuration parsing."""
        collector = SecurityCollector()
        mock_config = [
            "Port 22",
            "PermitRootLogin no",
            "PasswordAuthentication yes",
        ]

        with patch.object(collector, "run_command", return_value=("active", "", 0)):
            with patch.object(collector, "read_file_lines", return_value=mock_config):
                result = collector._get_sshd_config()
                assert result["port"] == "22"
                assert result["permit_root_login"] == "no"
