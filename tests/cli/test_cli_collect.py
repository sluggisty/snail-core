"""
CLI tests for the 'snail collect' command.

Tests collection execution, output formats, and collector selection.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


@pytest.mark.cli


class TestCliCollect(unittest.TestCase):
    """Test the 'snail collect' command."""

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

    def test_collect_command_runs_successfully(self):
        """Test that collect command runs without errors."""
        # Mock the actual collection to avoid running real collectors
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"test": {"data": "value"}},
            )
            mock_collect.return_value = mock_report

            result = self.runner.invoke(self.main, ["collect"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Collection Results", result.output)
            mock_collect.assert_called_once()

    def test_collect_command_with_specific_collectors(self):
        """Test collect command with specific collector selection."""
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"system": {"os": "Linux"}, "hardware": {"cpu": "Intel"}},
            )
            mock_collect.return_value = mock_report

            result = self.runner.invoke(self.main, ["collect", "-C", "system", "-C", "hardware"])

            self.assertEqual(result.exit_code, 0)
            mock_collect.assert_called_once_with(["system", "hardware"])

    def test_collect_command_json_output(self):
        """Test collect command with JSON output format."""
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"test": {"data": "value"}},
            )
            mock_collect.return_value = mock_report

            result = self.runner.invoke(self.main, ["collect", "--format", "json"])

            self.assertEqual(result.exit_code, 0)
            # Find the JSON part (it comes after rich formatting)
            output_lines = result.output.strip().split('\n')
            json_start = None
            for i, line in enumerate(output_lines):
                if line.strip().startswith('{'):
                    json_start = i
                    break

            self.assertIsNotNone(json_start, "No JSON found in output")
            # Combine JSON lines
            json_lines = output_lines[json_start:]
            json_content = '\n'.join(json_lines)

            try:
                parsed = json.loads(json_content)
                self.assertIn("meta", parsed)
                self.assertIn("data", parsed)
                self.assertIn("errors", parsed)
            except json.JSONDecodeError as e:
                self.fail(f"Output contains invalid JSON: {e}")

    def test_collect_command_pretty_output(self):
        """Test collect command with pretty (default) output format."""
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"system": {"os": "Linux"}, "hardware": {"cpu": "Intel"}},
            )
            mock_collect.return_value = mock_report

            result = self.runner.invoke(self.main, ["collect", "--format", "pretty"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Collection Results", result.output)
            self.assertIn("system", result.output)
            self.assertIn("hardware", result.output)

    def test_collect_command_output_to_file(self):
        """Test collect command writing output to file."""
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"test": {"data": "value"}},
            )
            mock_collect.return_value = mock_report

            with self.runner.isolated_filesystem():
                result = self.runner.invoke(self.main, ["collect", "--output", "output.json"])

                self.assertEqual(result.exit_code, 0)
                self.assertIn("Report saved to:", result.output)

                # Check that file was created and contains valid JSON
                self.assertTrue(Path("output.json").exists())
                with open("output.json", "r") as f:
                    content = f.read()
                    try:
                        parsed = json.loads(content)
                        self.assertIn("meta", parsed)
                        self.assertIn("data", parsed)
                    except json.JSONDecodeError:
                        self.fail("Output file does not contain valid JSON")

    def test_collect_command_with_upload_flag_no_url(self):
        """Test collect command with upload flag but no upload URL configured."""
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"test": {"data": "value"}},
            )
            mock_collect.return_value = mock_report

            result = self.runner.invoke(self.main, ["collect", "--upload"])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Warning: No upload URL configured", result.output)
            self.assertIn("Skipping upload", result.output)

    def test_collect_command_invalid_collector(self):
        """Test collect command with invalid collector name."""
        result = self.runner.invoke(self.main, ["collect", "-C", "invalid_collector"])

        # Should still succeed but may show warnings
        self.assertEqual(result.exit_code, 0)

    def test_collect_command_multiple_collectors(self):
        """Test collect command with multiple collector options."""
        with patch('snail_core.core.SnailCore.collect') as mock_collect:
            from snail_core.core import CollectionReport
            mock_report = CollectionReport(
                hostname="test-host",
                host_id="test-id-123",
                collection_id="test-collection-456",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results={"system": {"os": "Linux"}, "network": {"interfaces": []}},
            )
            mock_collect.return_value = mock_report

            result = self.runner.invoke(self.main, [
                "collect",
                "-C", "system",
                "-C", "network",
                "--format", "json"
            ])

            self.assertEqual(result.exit_code, 0)
            mock_collect.assert_called_once_with(["system", "network"])

            # Verify JSON contains both collectors
            output_lines = result.output.strip().split('\n')
            json_start = None
            for i, line in enumerate(output_lines):
                if line.strip().startswith('{'):
                    json_start = i
                    break

            self.assertIsNotNone(json_start, "No JSON found in output")
            # Combine JSON lines
            json_lines = output_lines[json_start:]
            json_content = '\n'.join(json_lines)

            try:
                parsed = json.loads(json_content)
                self.assertIn("data", parsed)
                self.assertIn("system", parsed["data"])
                self.assertIn("network", parsed["data"])
            except json.JSONDecodeError as e:
                self.fail(f"Output contains invalid JSON: {e}")
