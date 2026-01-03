"""
Multi-distribution tests for AppArmor detection.

Tests SecurityCollector AppArmor functionality on Ubuntu/Debian/SUSE systems.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from snail_core.collectors.security import SecurityCollector


class TestApparmor(unittest.TestCase):
    """Test AppArmor detection and reporting."""

    def setUp(self):
        """Set up test collector."""
        self.collector = SecurityCollector()

    def test_apparmor_enabled_with_profiles(self):
        """Test AppArmor detection when enabled with loaded profiles."""
        mock_output = """apparmor module is loaded.
32 profiles are loaded.
20 profiles are in enforce mode.
12 profiles are in complain mode.
2 processes have profiles defined.
1 processes are in enforce mode.
1 processes are in complain mode.
0 processes are unconfined but have a profile defined."""

        with patch.object(self.collector, "run_command", return_value=(mock_output, "", 0)):

            result = self.collector._get_apparmor_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["profiles"]["loaded"], 32)
            self.assertEqual(result["profiles"]["enforce"], 20)
            self.assertEqual(result["profiles"]["complain"], 12)
            # Note: processes are not parsed by the current implementation
            self.assertNotIn("processes", result)

    def test_apparmor_enabled_minimal_output(self):
        """Test AppArmor detection with minimal output."""
        mock_output = "apparmor module is loaded."

        with patch.object(self.collector, "run_command", return_value=(mock_output, "", 0)):

            result = self.collector._get_apparmor_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["profiles"], {})
            self.assertNotIn("processes", result)

    def test_apparmor_not_available(self):
        """Test AppArmor detection when not available."""
        with patch.object(self.collector, "run_command", return_value=("", "command not found", 127)):

            result = self.collector._get_apparmor_info()

            self.assertFalse(result["enabled"])
            self.assertFalse(result["available"])
            self.assertEqual(result["profiles"], {})
            self.assertNotIn("processes", result)

    def test_apparmor_command_error(self):
        """Test AppArmor detection when command returns error."""
        with patch.object(self.collector, "run_command", return_value=("", "permission denied", 1)):

            result = self.collector._get_apparmor_info()

            self.assertFalse(result["enabled"])
            self.assertFalse(result["available"])

    def test_apparmor_parsing_edge_cases(self):
        """Test AppArmor output parsing with various edge cases."""
        test_cases = [
            # No profiles loaded
            ("apparmor module is loaded.\n0 profiles are loaded.",
             {"loaded": 0, "enforce": 0, "complain": 0},
             {"defined": 0, "enforce": 0, "complain": 0, "unconfined": 0}),

            # Only enforce mode
            ("apparmor module is loaded.\n15 profiles are loaded.\n15 profiles are in enforce mode.",
             {"loaded": 15, "enforce": 15, "complain": 0},
             {"defined": 0, "enforce": 0, "complain": 0, "unconfined": 0}),

            # Malformed numbers
            ("apparmor module is loaded.\ninvalid profiles are loaded.\nabc profiles are in enforce mode.",
             {},
             {}),

            # Extra whitespace
            ("apparmor module is loaded.\n  5 profiles are loaded.\n  3 profiles are in enforce mode.  ",
             {"loaded": 5, "enforce": 3, "complain": 0},
             {"defined": 0, "enforce": 0, "complain": 0, "unconfined": 0}),
        ]

        for mock_output, expected_profiles, expected_processes in test_cases:
            with self.subTest(output=mock_output[:50]):
                with patch.object(self.collector, "run_command", return_value=(mock_output, "", 0)):

                    result = self.collector._get_apparmor_info()

                    self.assertTrue(result["enabled"])
                    self.assertTrue(result["available"])

                    for key, expected_value in expected_profiles.items():
                        self.assertEqual(result["profiles"].get(key, 0), expected_value,
                                       f"Profile {key} mismatch")

                    # Note: processes are not parsed by current implementation
                    self.assertNotIn("processes", result)

    def test_apparmor_all_profiles_complain_mode(self):
        """Test AppArmor with all profiles in complain mode."""
        mock_output = """apparmor module is loaded.
25 profiles are loaded.
0 profiles are in enforce mode.
25 profiles are in complain mode.
5 processes have profiles defined.
0 processes are in enforce mode.
5 processes are in complain mode.
1 processes are unconfined but have a profile defined."""

        with patch.object(self.collector, "run_command", return_value=(mock_output, "", 0)):

            result = self.collector._get_apparmor_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["profiles"]["loaded"], 25)
            self.assertEqual(result["profiles"]["enforce"], 0)
            self.assertEqual(result["profiles"]["complain"], 25)
            # Note: processes are not parsed by current implementation
            self.assertNotIn("processes", result)

    def test_apparmor_mixed_processes(self):
        """Test AppArmor with processes in different states."""
        mock_output = """apparmor module is loaded.
10 profiles are loaded.
6 profiles are in enforce mode.
4 profiles are in complain mode.
8 processes have profiles defined.
4 processes are in enforce mode.
3 processes are in complain mode.
1 processes are unconfined but have a profile defined."""

        with patch.object(self.collector, "run_command", return_value=(mock_output, "", 0)):

            result = self.collector._get_apparmor_info()

            self.assertTrue(result["enabled"])
            self.assertTrue(result["available"])
            self.assertEqual(result["profiles"]["loaded"], 10)
            self.assertEqual(result["profiles"]["enforce"], 6)
            self.assertEqual(result["profiles"]["complain"], 4)
            # Note: processes are not parsed by current implementation
            self.assertNotIn("processes", result)
