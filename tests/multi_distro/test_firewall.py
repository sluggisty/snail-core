"""
Multi-distribution tests for firewall detection.

Tests SecurityCollector firewall functionality across different Linux distributions.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from snail_core.collectors.security import SecurityCollector
import pytest


@pytest.mark.integration


class TestFirewall(unittest.TestCase):
    """Test firewall detection and reporting."""

    def setUp(self):
        """Set up test collector."""
        self.collector = SecurityCollector()

    def test_firewalld_detection_running(self):
        """Test firewalld detection when service is running."""
        call_count = 0

        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("active", "", 0)
            elif cmd == ["firewall-cmd", "--get-zones"]:
                return ("block dmz drop external home internal public trusted work", "", 0)
            elif cmd == ["firewall-cmd", "--get-default-zone"]:
                return ("public", "", 0)
            else:
                return ("", "", 1)

        with patch.object(self.collector, "run_command", side_effect=mock_run):

            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "firewalld")
            self.assertTrue(result["enabled"])
            self.assertTrue(result["running"])
            self.assertEqual(result["zones"], ["block", "dmz", "drop", "external", "home",
                                              "internal", "public", "trusted", "work"])
            self.assertEqual(result["default_zone"], "public")

    def test_firewalld_not_running(self):
        """Test firewalld detection when service is not running."""
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []
            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)  # Service not active
            # For all other commands, simulate failure
            return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "none")
            self.assertFalse(result["enabled"])
            self.assertFalse(result["running"])

    def test_ufw_detection_enabled(self):
        """Test UFW detection when enabled."""
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)  # firewalld not running
            elif cmd == ["ufw", "status"]:
                return ("Status: active\n\n     To                         Action      From\n     --                         ------      ----\n22/tcp                     ALLOW        Anywhere\n80,443/tcp                ALLOW        Anywhere\n", "", 0)
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "ufw")
            self.assertTrue(result["enabled"])
            self.assertTrue(result["running"])

    def test_ufw_detection_disabled(self):
        """Test UFW detection when disabled."""
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)  # firewalld not running
            elif cmd == ["ufw", "status"]:
                return ("Status: disabled", "", 0)
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "ufw")
            self.assertFalse(result["enabled"])
            self.assertFalse(result["running"])

    def test_iptables_detection_legacy(self):
        """Test iptables detection as fallback."""
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)  # firewalld not running
            elif cmd == ["ufw", "status"]:
                return ("", "command not found", 127)  # ufw not available
            elif cmd == ["iptables", "-L", "-n"]:
                return ("Chain INPUT (policy ACCEPT)\nChain FORWARD (policy ACCEPT)\nChain OUTPUT (policy ACCEPT)\n", "", 0)
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "iptables")
            self.assertFalse(result["enabled"])  # Current code doesn't set enabled for iptables
            self.assertTrue(result["running"])

    def test_fallback_to_none_when_no_firewall(self):
        """Test fallback to 'none' when no firewall tools are available."""
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)
            elif cmd == ["ufw", "status"]:
                return ("", "command not found", 127)
            elif cmd == ["iptables", "-L", "-n"]:
                return ("", "", 1)  # iptables not available
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "none")
            self.assertFalse(result["enabled"])
            self.assertFalse(result["running"])

    def test_no_firewall_detected(self):
        """Test when no firewall is detected."""
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []
            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)
            elif cmd == ["ufw", "status"]:
                return ("", "command not found", 127)
            elif cmd == ["iptables", "-L", "-n"]:
                return ("", "", 1)
            elif cmd == ["nft", "list", "tables"]:
                return ("", "", 1)
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "none")
            self.assertFalse(result["enabled"])
            self.assertFalse(result["running"])

    def test_firewalld_command_failures(self):
        """Test firewalld detection when commands fail."""
        call_count = 0

        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("active", "", 0)
            elif cmd == ["firewall-cmd", "--get-zones"]:
                return ("", "command failed", 1)
            elif cmd == ["firewall-cmd", "--get-default-zone"]:
                return ("", "command failed", 1)
            else:
                return ("", "", 1)

        with patch.object(self.collector, "run_command", side_effect=mock_run):

            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "firewalld")
            self.assertTrue(result["enabled"])
            self.assertTrue(result["running"])
            # Should not have zones/default_zone due to command failures
            self.assertNotIn("zones", result)
            self.assertNotIn("default_zone", result)

    def test_ufw_parsing_complex_rules(self):
        """Test UFW parsing with complex rules."""
        ufw_output = """Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 22/tcp                     ALLOW IN    Anywhere
[ 2] 80,443/tcp                 ALLOW IN    Anywhere
[ 3] 53/udp                     ALLOW IN    192.168.1.0/24
[ 4] 22/tcp (v6)               ALLOW IN    Anywhere (v6)
[ 5] 80,443/tcp (v6)           ALLOW IN    Anywhere (v6)
[ 6] 53/udp (v6)               ALLOW IN    2001:db8::/32"""

        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)
            elif cmd == ["ufw", "status"]:
                return (ufw_output, "", 0)
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            self.assertEqual(result["type"], "ufw")
            self.assertTrue(result["enabled"])
            self.assertTrue(result["running"])

    def test_firewall_detection_priority(self):
        """Test that firewall detection follows priority order."""
        # Test that firewalld is checked first, then ufw, then iptables, then nftables
        call_log = []

        def mock_run(*args, **kwargs):
            cmd = args[0] if args else []
            call_log.append(cmd)

            if cmd == ["systemctl", "is-active", "firewalld"]:
                return ("failed", "", 3)  # Not running
            elif cmd == ["ufw", "status"]:
                return ("", "command not found", 127)  # Not available
            elif cmd == ["iptables", "-L", "-n"]:
                return ("Chain INPUT (policy ACCEPT)\n", "", 0)  # iptables available
            else:
                return ("", "command not found", 127)

        with patch.object(self.collector, "run_command", side_effect=mock_run):
            result = self.collector._get_firewall_status()

            # Should detect iptables as the fallback
            self.assertEqual(result["type"], "iptables")
            self.assertFalse(result["enabled"])  # Current code doesn't set enabled for iptables
            self.assertTrue(result["running"])

            # Verify the call order
            expected_calls = [
                ["systemctl", "is-active", "firewalld"],
                ["ufw", "status"],
                ["iptables", "-L", "-n"]
            ]
            self.assertEqual(call_log, expected_calls)
