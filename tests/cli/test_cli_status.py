"""
CLI tests for the 'snail status' command.

Tests configuration display and connection testing.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest
from click.testing import CliRunner

# Ensure snail_core modules are imported


@pytest.mark.cli
class TestCliStatus(unittest.TestCase):
    """Test the 'snail status' command."""

    def setUp(self):
        """Set up test runner."""
        self.runner = CliRunner()
        # Import CLI module and ensure submodules are loaded
        import snail_core.cli
        import snail_core.config
        import snail_core.uploader

        self.main = snail_core.cli.main

    def test_status_command_shows_configuration(self):
        """Test that status command displays current configuration."""
        result = self.runner.invoke(self.main, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core Status", result.output)

        # Check that configuration items are displayed
        self.assertIn("Upload URL", result.output)
        self.assertIn("Upload Enabled", result.output)
        self.assertIn("API Key", result.output)
        self.assertIn("Output Dir", result.output)
        self.assertIn("Log Level", result.output)

    def test_status_command_with_upload_url_tests_connection(self):
        """Test that status command tests connection when upload URL is configured."""
        from snail_core.config import Config
        from snail_core.uploader import Uploader

        mock_config = Config(upload_url="https://test.example.com/api")

        with (
            patch.object(Config, "load", return_value=mock_config),
            patch.object(Uploader, "test_connection", return_value=True),
        ):
            result = self.runner.invoke(self.main, ["status"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Server is reachable", result.output)

    def test_status_command_connection_failure(self):
        """Test status command when connection test fails."""
        from snail_core.config import Config
        from snail_core.uploader import Uploader

        mock_config = Config(upload_url="https://test.example.com/api")

        with (
            patch.object(Config, "load", return_value=mock_config),
            patch.object(Uploader, "test_connection", return_value=False),
        ):
            result = self.runner.invoke(self.main, ["status"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Server is not reachable", result.output)

    def test_status_command_no_upload_url_skips_connection_test(self):
        """Test that status command skips connection test when no upload URL."""
        result = self.runner.invoke(self.main, ["status"])

        self.assertEqual(result.exit_code, 0)
        # Should not contain connection test messages
        self.assertNotIn("Server is reachable", result.output)
        self.assertNotIn("Server is not reachable", result.output)
        self.assertNotIn("Testing connection", result.output)

    def test_status_command_config_values_display(self):
        """Test that status command correctly displays configuration values."""
        result = self.runner.invoke(self.main, ["status"])

        self.assertEqual(result.exit_code, 0)

        # Check for default values
        self.assertIn("Not configured", result.output)  # Upload URL default
        self.assertIn("Yes", result.output)  # Upload Enabled default
        self.assertIn("Not set", result.output)  # API Key default
        self.assertIn("/var/lib/snail-core", result.output)  # Output Dir default
        self.assertIn("INFO", result.output)  # Log Level default

    def test_status_command_table_format(self):
        """Test that status command uses proper table format."""
        result = self.runner.invoke(self.main, ["status"])

        self.assertEqual(result.exit_code, 0)

        # Should contain table-like formatting
        lines = result.output.split("\n")
        self.assertTrue(len(lines) > 10)  # Should have multiple lines

        # Should have the title
        self.assertIn("Snail Core Status", result.output)
