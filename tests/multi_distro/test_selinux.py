"""
Multi-distribution tests for SELinux detection.

Tests SecurityCollector SELinux functionality on RHEL/Fedora/CentOS systems.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from snail_core.collectors.security import SecurityCollector
import pytest


@pytest.mark.integration


class TestSelinux(unittest.TestCase):
    """Test SELinux detection and reporting."""

    def setUp(self):
        """Set up test collector."""
        self.collector = SecurityCollector()

    def test_selinux_enabled_and_enforcing(self):
        """Test SELinux detection when enabled and in enforcing mode."""
        with patch.object(self.collector, "read_file", return_value="1"), \
             patch.object(self.collector, "run_command") as mock_run, \
             patch.object(self.collector, "parse_key_value_file", return_value={
                 "SELINUX": "enforcing",
                 "SELINUXTYPE": "targeted"
             }):

            mock_run.return_value = ("Enforcing", "", 0)

            result = self.collector._get_selinux_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["mode"], "enforcing")
            self.assertEqual(result["configured_mode"], "enforcing")
            self.assertEqual(result["policy"], "targeted")

    def test_selinux_enabled_and_permissive(self):
        """Test SELinux detection when enabled but in permissive mode."""
        with patch.object(self.collector, "read_file", return_value="0"), \
             patch.object(self.collector, "run_command") as mock_run, \
             patch.object(self.collector, "parse_key_value_file", return_value={
                 "SELINUX": "permissive",
                 "SELINUXTYPE": "mls"
             }):

            mock_run.return_value = ("Permissive", "", 0)

            result = self.collector._get_selinux_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["mode"], "permissive")
            self.assertEqual(result["configured_mode"], "permissive")
            self.assertEqual(result["policy"], "mls")

    def test_selinux_disabled(self):
        """Test SELinux detection when disabled."""
        with patch.object(self.collector, "read_file", return_value=""), \
             patch.object(self.collector, "run_command") as mock_run, \
             patch.object(self.collector, "parse_key_value_file", return_value={
                 "SELINUX": "disabled"
             }):

            mock_run.return_value = ("Disabled", "", 0)

            result = self.collector._get_selinux_info()

            self.assertFalse(result["enabled"])
            self.assertFalse(result["available"])
            self.assertEqual(result["mode"], "disabled")
            # configured_mode is not set when SELinux is not available
            self.assertNotIn("configured_mode", result)

    def test_selinux_getenforce_command_failure(self):
        """Test SELinux detection when getenforce command fails."""
        with patch.object(self.collector, "read_file", return_value="1"), \
             patch.object(self.collector, "run_command") as mock_run, \
             patch.object(self.collector, "parse_key_value_file", return_value={
                 "SELINUX": "enforcing",
                 "SELINUXTYPE": "targeted"
             }):

            # getenforce command fails
            mock_run.return_value = ("", "command not found", 127)

            result = self.collector._get_selinux_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["mode"], "disabled")  # Default when command fails
            self.assertEqual(result["configured_mode"], "enforcing")
            self.assertEqual(result["policy"], "targeted")

    def test_selinux_config_file_missing(self):
        """Test SELinux detection when config file is missing or unparseable."""
        with patch.object(self.collector, "read_file", return_value="1"), \
             patch.object(self.collector, "run_command") as mock_run, \
             patch.object(self.collector, "parse_key_value_file", return_value={}):

            mock_run.return_value = ("Enforcing", "", 0)

            result = self.collector._get_selinux_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["mode"], "enforcing")
            self.assertEqual(result["configured_mode"], "")
            self.assertEqual(result["policy"], "")

    def test_selinux_not_available(self):
        """Test SELinux detection when SELinux is not available on the system."""
        with patch.object(self.collector, "read_file", return_value=""), \
             patch.object(self.collector, "run_command") as mock_run, \
             patch.object(self.collector, "parse_key_value_file", return_value={}):

            # Should not even call run_command if file doesn't exist
            mock_run.return_value = ("Disabled", "", 0)

            result = self.collector._get_selinux_info()

            self.assertFalse(result["enabled"])
            self.assertFalse(result["available"])
            self.assertEqual(result["mode"], "disabled")
            # configured_mode is not set when SELinux is not available
            self.assertNotIn("configured_mode", result)
            self.assertEqual(result["policy"], "")

    def test_selinux_config_parsing_edge_cases(self):
        """Test SELinux config parsing with various edge cases."""
        test_cases = [
            # Empty config
            ({}, ""),
            # Only SELINUX
            ({"SELINUX": "enforcing"}, "enforcing"),
            # Only SELINUXTYPE
            ({"SELINUXTYPE": "targeted"}, ""),
            # Both present
            ({"SELINUX": "permissive", "SELINUXTYPE": "mls"}, "permissive"),
        ]

        for config_data, expected_mode in test_cases:
            with self.subTest(config=config_data):
                with patch.object(self.collector, "read_file", return_value="1"), \
                     patch.object(self.collector, "run_command", return_value=("Enforcing", "", 0)), \
                     patch.object(self.collector, "parse_key_value_file", return_value=config_data):

                    result = self.collector._get_selinux_info()

                    self.assertEqual(result.get("configured_mode", ""), expected_mode)
                    if "SELINUXTYPE" in config_data:
                        self.assertEqual(result["policy"], config_data["SELINUXTYPE"])
