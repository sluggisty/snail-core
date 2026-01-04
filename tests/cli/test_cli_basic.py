"""
Basic CLI tests for Snail Core.

Tests help, version, and basic command structure.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import pytest
from click.testing import CliRunner


@pytest.mark.cli
class TestCliBasic(unittest.TestCase):
    """Test basic CLI functionality."""

    def setUp(self):
        """Set up test runner."""
        self.runner = CliRunner()
        # Completely fresh import to avoid any module state issues
        if "snail_core.cli" in sys.modules:
            del sys.modules["snail_core.cli"]
        if "snail_core" in sys.modules:
            del sys.modules["snail_core"]
        # Fresh import
        import snail_core.cli

        self.main = snail_core.cli.main

    def test_cli_help(self):
        """Test that --help displays help information."""
        result = self.runner.invoke(self.main, ["--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core", result.output)
        self.assertIn("System information collection", result.output)
        self.assertIn("--config", result.output)
        self.assertIn("--verbose", result.output)
        self.assertIn("collect", result.output)
        self.assertIn("list", result.output)
        self.assertIn("status", result.output)

    def test_cli_version(self):
        """Test that --version displays version information."""
        result = self.runner.invoke(self.main, ["--version"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("snail-core", result.output)
        # Should contain version number
        self.assertRegex(result.output, r"\d+\.\d+\.\d+")

    def test_cli_no_args_shows_help(self):
        """Test that running without args shows help."""
        result = self.runner.invoke(self.main, [])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core", result.output)

    def test_cli_invalid_command(self):
        """Test that invalid commands show error."""
        result = self.runner.invoke(self.main, ["invalid-command"])

        self.assertEqual(result.exit_code, 2)  # Click error exit code
        self.assertIn("No such command", result.output)

    def test_cli_verbose_flag(self):
        """Test that --verbose flag is accepted."""
        result = self.runner.invoke(self.main, ["--verbose", "list"])

        # Should not fail (list command should work)
        self.assertEqual(result.exit_code, 0)

    def test_cli_config_flag_with_invalid_path(self):
        """Test that --config with invalid path shows error."""
        result = self.runner.invoke(self.main, ["--config", "/nonexistent/config.yaml", "list"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("does not exist", result.output)

    def test_cli_config_flag_with_valid_path(self):
        """Test that --config with valid path works (creates temp file)."""
        import tempfile
        import os

        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
upload:
  url: https://test.example.com/api
"""
            )
            temp_config_path = f.name

        try:
            result = self.runner.invoke(self.main, ["--config", temp_config_path, "list"])

            # Should not fail (list command should work with config)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Available Collectors", result.output)

        finally:
            # Clean up temp file
            os.unlink(temp_config_path)

    def test_list_command_structure(self):
        """Test that list command shows available collectors."""
        result = self.runner.invoke(self.main, ["list"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Available Collectors", result.output)

        # Should show collector names
        collector_names = [
            "system",
            "hardware",
            "network",
            "packages",
            "services",
            "filesystem",
            "security",
            "logs",
        ]
        for name in collector_names:
            self.assertIn(name, result.output)

    def test_version_command(self):
        """Test the version subcommand."""
        result = self.runner.invoke(self.main, ["version"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core", result.output)
        self.assertIn("Version:", result.output)
        self.assertRegex(result.output, r"\d+\.\d+\.\d+")

    def test_status_command_basic(self):
        """Test the status command shows configuration."""
        result = self.runner.invoke(self.main, ["status"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core Status", result.output)
        self.assertIn("Upload URL", result.output)
        self.assertIn("Upload Enabled", result.output)
        self.assertIn("API Key", result.output)

    def test_init_config_command(self):
        """Test the init-config command creates a sample file."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(self.main, ["init-config", "sample-config.yaml"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Configuration file created", result.output)

            # Check that file was created with content
            import os

            self.assertTrue(os.path.exists("sample-config.yaml"))

            with open("sample-config.yaml", "r") as f:
                content = f.read()
                self.assertIn("upload:", content)
                self.assertIn("auth:", content)
                self.assertIn("Snail Core Configuration", content)

    def test_host_id_command_display(self):
        """Test the host-id command displays current ID."""
        result = self.runner.invoke(self.main, ["host-id"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Host ID:", result.output)

        # Should be a valid UUID

        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        self.assertRegex(result.output, uuid_pattern)

    @patch("click.confirm")
    def test_host_id_command_reset(self, mock_confirm):
        """Test the host-id --reset command."""
        mock_confirm.return_value = True  # User confirms reset

        result = self.runner.invoke(self.main, ["host-id", "--reset"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Host ID reset to:", result.output)
        mock_confirm.assert_called_once()

    @patch("click.confirm")
    def test_host_id_command_reset_cancelled(self, mock_confirm):
        """Test that host-id --reset can be cancelled."""
        mock_confirm.return_value = False  # User cancels reset

        result = self.runner.invoke(self.main, ["host-id", "--reset"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cancelled", result.output)
        mock_confirm.assert_called_once()
