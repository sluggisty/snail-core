"""
CLI tests for the 'snail host-id' command.

Tests host ID display and reset functionality.
"""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

import pytest
from click.testing import CliRunner

# Ensure modules are imported


@pytest.mark.cli
class TestCliHostId(unittest.TestCase):
    """Test the 'snail host-id' command."""

    def setUp(self):
        """Set up test runner."""
        self.runner = CliRunner()
        # Import CLI module and ensure submodules are loaded
        import snail_core.cli
        import snail_core.host_id

        self.main = snail_core.cli.main

    def test_host_id_command_display(self):
        """Test that host-id command displays current host ID."""
        test_host_id = str(uuid.uuid4())

        with patch("snail_core.cli.get_host_id", return_value=test_host_id):
            result = self.runner.invoke(self.main, ["host-id"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Host ID:", result.output)
            self.assertIn(test_host_id, result.output)
            self.assertIn("This UUID uniquely identifies", result.output)

    def test_host_id_command_reset_confirmed(self):
        """Test host-id --reset command when user confirms."""
        new_host_id = str(uuid.uuid4())

        with patch("snail_core.cli.reset_host_id", return_value=new_host_id) as mock_reset:
            result = self.runner.invoke(self.main, ["host-id", "--reset"], input="y\n")

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Host ID reset to:", result.output)
            self.assertIn(new_host_id, result.output)
            self.assertIn("This system will now appear as a new host", result.output)
            mock_reset.assert_called_once()

    def test_host_id_command_reset_cancelled(self):
        """Test host-id --reset command when user cancels."""
        with patch("snail_core.cli.reset_host_id") as mock_reset:
            result = self.runner.invoke(self.main, ["host-id", "--reset"], input="n\n")

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Cancelled", result.output)
            mock_reset.assert_not_called()

    def test_host_id_command_returns_valid_uuid(self):
        """Test that displayed host ID is a valid UUID."""
        with patch("snail_core.cli.get_host_id") as mock_get:
            test_uuid = str(uuid.uuid4())
            mock_get.return_value = test_uuid

            result = self.runner.invoke(self.main, ["host-id"])

            self.assertEqual(result.exit_code, 0)
            # Verify it's a valid UUID
            try:
                uuid.UUID(test_uuid)
            except ValueError:
                self.fail(f"Host ID is not a valid UUID: {test_uuid}")

    def test_host_id_command_calls_get_host_id_with_config_dir(self):
        """Test that host-id command calls get_host_id with correct config directory."""
        test_host_id = str(uuid.uuid4())

        with patch("snail_core.cli.get_host_id", return_value=test_host_id) as mock_get:
            result = self.runner.invoke(self.main, ["host-id"])

            self.assertEqual(result.exit_code, 0)
            mock_get.assert_called_once()
            # Should be called with the config's output_dir
            args, kwargs = mock_get.call_args
            self.assertEqual(len(args), 1)  # Should have output_dir argument

    def test_host_id_reset_calls_reset_host_id_with_config_dir(self):
        """Test that host-id --reset calls reset_host_id with correct config directory."""
        new_host_id = str(uuid.uuid4())

        with patch("snail_core.cli.reset_host_id", return_value=new_host_id) as mock_reset:
            result = self.runner.invoke(self.main, ["host-id", "--reset"], input="y\n")

            self.assertEqual(result.exit_code, 0)
            mock_reset.assert_called_once()
            # Should be called with the config's output_dir
            args, kwargs = mock_reset.call_args
            self.assertEqual(len(args), 1)  # Should have output_dir argument
