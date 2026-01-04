"""
CLI tests for the 'snail list' command.

Tests collector listing functionality.
"""

from __future__ import annotations

import sys
import unittest

import pytest
from click.testing import CliRunner

from snail_core.collectors import COLLECTORS


@pytest.mark.cli


class TestCliList(unittest.TestCase):
    """Test the 'snail list' command."""

    def setUp(self):
        """Set up test runner."""
        self.runner = CliRunner()
        # Completely fresh import to avoid any module state issues
        if 'snail_core.cli' in sys.modules:
            del sys.modules['snail_core.cli']
        if 'snail_core' in sys.modules:
            del sys.modules['snail_core']
        # Fresh import
        import snail_core.cli
        self.main = snail_core.cli.main

    def test_list_command_shows_all_collectors(self):
        """Test that list command displays all available collectors."""
        result = self.runner.invoke(self.main, ["list"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Available Collectors", result.output)

        # Check that all expected collectors are listed
        expected_collectors = ["system", "hardware", "network", "packages",
                              "services", "filesystem", "security", "logs"]

        for collector_name in expected_collectors:
            self.assertIn(collector_name, result.output)

    def test_list_command_table_format(self):
        """Test that list command uses proper table format."""
        result = self.runner.invoke(self.main, ["list"])

        self.assertEqual(result.exit_code, 0)
        # Should contain table formatting
        self.assertIn("Name", result.output)
        self.assertIn("Description", result.output)

    def test_list_command_shows_descriptions(self):
        """Test that list command shows collector descriptions."""
        result = self.runner.invoke(self.main, ["list"])

        self.assertEqual(result.exit_code, 0)

        # Check that descriptions are shown for some collectors
        self.assertIn("system information", result.output.lower())
        self.assertIn("hardware information", result.output.lower())
        self.assertIn("network", result.output.lower())

    def test_list_command_collector_count(self):
        """Test that list command shows the correct number of collectors."""
        result = self.runner.invoke(self.main, ["list"])

        self.assertEqual(result.exit_code, 0)

        # Should show all collectors from COLLECTORS dict
        expected_count = len(COLLECTORS)

        # Count occurrences of collector names in output
        output_lines = result.output.split('\n')
        collector_lines = [line for line in output_lines if any(name in line for name in COLLECTORS.keys())]

        # Should have at least the expected number (may have header/footer lines)
        self.assertGreaterEqual(len(collector_lines), expected_count)

    def test_list_command_output_structure(self):
        """Test the overall structure of list command output."""
        result = self.runner.invoke(self.main, ["list"])

        self.assertEqual(result.exit_code, 0)

        # Should start with empty line then table
        lines = result.output.strip().split('\n')
        self.assertTrue(len(lines) > 5)  # Should have multiple lines

        # Should contain the title
        self.assertIn("Available Collectors", result.output)
