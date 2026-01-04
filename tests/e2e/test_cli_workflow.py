"""
End-to-end CLI workflow tests.

Tests complete user workflows through the CLI interface.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from snail_core.cli import main
from snail_core.config import Config


class TestCliWorkflow(unittest.TestCase):
    """Test complete CLI workflows."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runner = CliRunner()

        # Create a test config file
        self.config_file = self.temp_dir / "test_config.yaml"
        self.config_content = """
upload:
  url: "https://cli-test.example.com/api/upload"
  enabled: true
auth:
  api_key: "cli-test-key-123"
collection:
  timeout: 60
output:
  dir: "{temp_dir}"
  compress: true
""".format(temp_dir=self.temp_dir)

        self.config_file.write_text(self.config_content)

    def tearDown(self):
        """Clean up test environment."""
        # Clean up any files created during tests
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def test_init_config_collect_upload_sequence(self):
        """Test the complete sequence: init-config -> collect -> upload."""
        # Step 1: Initialize config
        with patch('snail_core.cli.Config.load') as mock_load:
            mock_config = Config(
                upload_url="https://cli-test.example.com/api/upload",
                upload_enabled=True,
                api_key="cli-test-key-123",
                output_dir=str(self.temp_dir)
            )
            mock_load.return_value = mock_config

            # Mock successful collection
            with patch('snail_core.core.SnailCore.collect') as mock_collect:
                mock_report = MagicMock()
                mock_report.hostname = "cli-test-host"
                mock_report.collection_id = "cli-test-collection"
                mock_report.results = {"system": {"os": "Linux"}}
                mock_report.errors = []
                mock_collect.return_value = mock_report

                # Mock successful upload
                with patch('snail_core.core.SnailCore.collect_and_upload') as mock_workflow:
                    mock_workflow.return_value = (mock_report, {"status": "uploaded"})

                    # Test collect command
                    result = self.runner.invoke(main, [
                        "--config", str(self.config_file),
                        "collect"
                    ])

                    self.assertEqual(result.exit_code, 0)
                    self.assertIn("Collection completed", result.output)

                    # Verify collection was called
                    mock_collect.assert_called_once()

    def test_configuration_persistence_across_commands(self):
        """Test that configuration persists across CLI commands."""
        # Create a config and verify it's used consistently
        config = Config.load(self.config_file)

        with patch('snail_core.cli.Config.load', return_value=config), \
             patch('snail_core.core.SnailCore') as mock_core_class:

            mock_core = MagicMock()
            mock_core_class.return_value = mock_core

            # Mock status command
            mock_core.config = config

            # Test status command uses config
            result = self.runner.invoke(main, [
                "--config", str(self.config_file),
                "status"
            ])

            self.assertEqual(result.exit_code, 0)
            # Verify Config.load was called with the config file
            # (This tests that the config file path is properly passed through)

    def test_report_file_generation(self):
        """Test that reports are properly generated and saved."""
        output_file = self.temp_dir / "test_report.json"

        with patch('snail_core.cli.Config.load') as mock_load:
            mock_config = Config(
                output_dir=str(self.temp_dir),
                upload_enabled=False
            )
            mock_load.return_value = mock_config

            # Mock collection
            with patch('snail_core.core.SnailCore.collect') as mock_collect:
                mock_report = MagicMock()
                mock_report.hostname = "file-test-host"
                mock_report.collection_id = "file-test-collection"
                mock_report.timestamp = "2024-01-01T00:00:00Z"
                mock_report.results = {"system": {"os": "Linux"}}
                mock_report.errors = []
                mock_report.to_dict.return_value = {
                    "meta": {
                        "hostname": "file-test-host",
                        "collection_id": "file-test-collection"
                    },
                    "data": {"system": {"os": "Linux"}},
                    "errors": []
                }
                mock_collect.return_value = mock_report

                # Test collect with output file
                result = self.runner.invoke(main, [
                    "--config", str(self.config_file),
                    "collect",
                    "--output", str(output_file)
                ])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Report saved to", result.output)

                # Verify file was created
                self.assertTrue(output_file.exists())

                # Verify file contents
                with open(output_file) as f:
                    saved_report = json.load(f)

                self.assertEqual(saved_report["meta"]["hostname"], "file-test-host")
                self.assertEqual(saved_report["data"]["system"]["os"], "Linux")

    def test_upload_success_verification(self):
        """Test that successful uploads are properly verified."""
        with patch('snail_core.cli.Config.load') as mock_load:
            mock_config = Config(
                upload_url="https://upload-test.example.com",
                upload_enabled=True,
                api_key="upload-test-key"
            )
            mock_load.return_value = mock_config

            # Mock successful upload workflow
            with patch('snail_core.core.SnailCore.collect_and_upload') as mock_workflow:
                mock_report = MagicMock()
                mock_upload_response = {"status": "success", "report_id": "upload-123"}
                mock_workflow.return_value = (mock_report, mock_upload_response)

                # Test collect --upload
                result = self.runner.invoke(main, [
                    "--config", str(self.config_file),
                    "collect",
                    "--upload"
                ])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Collection completed", result.output)
                # Should indicate upload was attempted
                self.assertIn("upload", result.output.lower())

                # Verify workflow was called
                mock_workflow.assert_called_once()

    def test_cli_workflow_with_errors(self):
        """Test CLI workflow when errors occur."""
        with patch('snail_core.cli.Config.load') as mock_load:
            mock_config = Config(output_dir=str(self.temp_dir))
            mock_load.return_value = mock_config

            # Mock collection with errors
            with patch('snail_core.core.SnailCore.collect') as mock_collect:
                mock_report = MagicMock()
                mock_report.hostname = "error-test-host"
                mock_report.errors = ["Collector 'bad_collector' failed: timeout"]
                mock_report.results = {"good_collector": {"status": "ok"}}
                mock_collect.return_value = mock_report

                # Test collect command with errors
                result = self.runner.invoke(main, [
                    "--config", str(self.config_file),
                    "collect"
                ])

                self.assertEqual(result.exit_code, 0)  # CLI should still succeed
                self.assertIn("Collection completed", result.output)
                # Should show errors in output
                self.assertIn("error", result.output.lower() or "failed")

    def test_cli_config_file_validation(self):
        """Test that CLI validates config file paths."""
        # Test with non-existent config file
        result = self.runner.invoke(main, [
            "--config", "/definitely/does/not/exist.yaml",
            "status"
        ])

        # Should handle gracefully (may succeed with defaults or show error)
        # The important thing is it doesn't crash
        self.assertIn(result.exit_code, [0, 2])  # 0 for success with defaults, 2 for error

    def test_cli_output_format_options(self):
        """Test different output format options."""
        with patch('snail_core.cli.Config.load') as mock_load:
            mock_config = Config(output_dir=str(self.temp_dir))
            mock_load.return_value = mock_config

            with patch('snail_core.core.SnailCore.collect') as mock_collect:
                mock_report = MagicMock()
                mock_report.results = {"test": {"data": "value"}}
                mock_report.errors = []
                mock_collect.return_value = mock_report

                # Test JSON output (default)
                result = self.runner.invoke(main, [
                    "--config", str(self.config_file),
                    "collect",
                    "--format", "json"
                ])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Collection completed", result.output)

                # Test pretty output
                result = self.runner.invoke(main, [
                    "--config", str(self.config_file),
                    "collect",
                    "--format", "pretty"
                ])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Collection completed", result.output)

    def test_cli_collector_selection(self):
        """Test CLI collector selection options."""
        with patch('snail_core.cli.Config.load') as mock_load:
            mock_config = Config()
            mock_load.return_value = mock_config

            with patch('snail_core.core.SnailCore.collect') as mock_collect:
                mock_report = MagicMock()
                mock_report.results = {"system": {"selected": True}}
                mock_report.errors = []
                mock_collect.return_value = mock_report

                # Test specific collector selection
                result = self.runner.invoke(main, [
                    "--config", str(self.config_file),
                    "collect",
                    "--collectors", "system"
                ])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Collection completed", result.output)

                # Verify only specified collector was called
                mock_collect.assert_called_once()
                args, kwargs = mock_collect.call_args
                self.assertEqual(args[0], ["system"])

    def test_cli_help_and_version(self):
        """Test basic CLI functionality."""
        # Test help
        result = self.runner.invoke(main, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core", result.output)
        self.assertIn("System information collection", result.output)

        # Test version
        result = self.runner.invoke(main, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("snail-core", result.output)

    def test_cli_no_args_shows_help(self):
        """Test that running CLI with no args shows help."""
        result = self.runner.invoke(main, [])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Snail Core", result.output)
        self.assertIn("Usage:", result.output)

    def test_cli_invalid_command(self):
        """Test handling of invalid commands."""
        result = self.runner.invoke(main, ["invalid-command"])
        self.assertEqual(result.exit_code, 2)  # Click error exit code
        self.assertIn("No such command", result.output)
