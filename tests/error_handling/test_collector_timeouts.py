"""
Error handling tests for collector timeout scenarios.

Tests that collectors handle timeouts correctly and errors are properly captured.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from snail_core.collectors.base import BaseCollector
import pytest

from snail_core.config import Config
from snail_core.core import SnailCore


@pytest.mark.integration
class TimeoutCollector(BaseCollector):
    """Test collector that simulates timeout behavior."""

    name = "timeout_test"
    description = "Test collector for timeout scenarios"

    def collect(self):
        # Simulate a timeout by raising an exception
        # In a real scenario, this would be due to command timeouts or other issues
        raise Exception("Collector timed out after 30 seconds")


class SuccessCollector(BaseCollector):
    """Test collector that succeeds."""

    name = "success_test"
    description = "Test collector that succeeds"

    def collect(self):
        return {"status": "success", "data": "test_data"}


class FailingCollector(BaseCollector):
    """Test collector that fails."""

    name = "fail_test"
    description = "Test collector that fails"

    def collect(self):
        raise Exception("Simulated collector failure")


class TestCollectorTimeouts(unittest.TestCase):
    """Test collector timeout handling."""

    def setUp(self):
        """Set up test environment."""
        self.config = Config()
        self.config.collection_timeout = 1  # 1 second timeout for testing

    def test_collector_timeout_error_capture(self):
        """Test that collector timeouts are captured in error list."""
        # Mock the collectors before SnailCore initialization
        with patch(
            "snail_core.core.get_all_collectors", return_value={"timeout_test": TimeoutCollector}
        ):
            core = SnailCore(self.config)
            report = core.collect(["timeout_test"])

            # Should have error in the errors list
            self.assertTrue(len(report.errors) > 0)
            error_found = any(
                "timeout" in error.lower() or "timed out" in error.lower()
                for error in report.errors
            )
            self.assertTrue(error_found, f"Timeout error not found in: {report.errors}")

            # Should not have successful data
            self.assertNotIn("timeout_test", report.results)

    def test_collector_timeout_continues_with_other_collectors(self):
        """Test that collection continues with other collectors after timeout."""
        with patch(
            "snail_core.core.get_all_collectors",
            return_value={"timeout_test": TimeoutCollector, "success_test": SuccessCollector},
        ):
            core = SnailCore(self.config)
            report = core.collect(["timeout_test", "success_test"])

            # Should have one error for timeout
            self.assertEqual(len(report.errors), 1)

            # Should have successful data for the non-timeout collector
            self.assertIn("success_test", report.results)
            self.assertEqual(report.results["success_test"]["status"], "success")

            # Should not have data for timeout collector
            self.assertNotIn("timeout_test", report.results)

    def test_collector_exception_error_capture(self):
        """Test that collector exceptions are captured in error list."""
        with patch(
            "snail_core.core.get_all_collectors", return_value={"fail_test": FailingCollector}
        ):
            core = SnailCore(self.config)
            report = core.collect(["fail_test"])

            # Should have error in the errors list
            self.assertEqual(len(report.errors), 1)
            self.assertIn("Simulated collector failure", report.errors[0])

            # Should not have successful data
            self.assertNotIn("fail_test", report.results)

    def test_successful_collector_not_affected_by_timeout(self):
        """Test that successful collectors work normally."""
        with patch(
            "snail_core.core.get_all_collectors", return_value={"success_test": SuccessCollector}
        ):
            core = SnailCore(self.config)
            report = core.collect(["success_test"])

            # Should have no errors
            self.assertEqual(len(report.errors), 0)

            # Should have successful data
            self.assertIn("success_test", report.results)
            self.assertEqual(report.results["success_test"]["status"], "success")

    def test_run_command_timeout_handling(self):
        """Test that run_command handles timeouts correctly."""
        collector = TimeoutCollector()

        # Mock subprocess.run to raise TimeoutExpired
        with patch("subprocess.run") as mock_run:
            from subprocess import TimeoutExpired

            mock_run.side_effect = TimeoutExpired(["sleep", "10"], 30)

            stdout, stderr, returncode = collector.run_command(["sleep", "10"], timeout=1)

            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "Command timed out")
            self.assertEqual(returncode, -1)

    def test_run_command_file_not_found(self):
        """Test that run_command handles missing commands."""
        collector = TimeoutCollector()

        stdout, stderr, returncode = collector.run_command(["nonexistent_command"])

        self.assertEqual(stdout, "")
        self.assertIn("Command not found", stderr)
        self.assertEqual(returncode, -1)

    def test_run_command_called_process_error(self):
        """Test that run_command handles command failures."""
        collector = TimeoutCollector()

        with patch("subprocess.run") as mock_run:
            from subprocess import CalledProcessError

            mock_run.side_effect = CalledProcessError(1, ["failing_cmd"], "out", "err")

            stdout, stderr, returncode = collector.run_command(["failing_cmd"])

            self.assertEqual(stdout, "out")
            self.assertEqual(stderr, "err")
            self.assertEqual(returncode, 1)

    def test_multiple_collector_errors_accumulate(self):
        """Test that multiple collector errors are all captured."""
        with patch(
            "snail_core.core.get_all_collectors",
            return_value={
                "fail1": FailingCollector,
                "fail2": FailingCollector,
                "success": SuccessCollector,
            },
        ):
            core = SnailCore(self.config)
            report = core.collect(["fail1", "fail2", "success"])

            # Should have 2 errors
            self.assertEqual(len(report.errors), 2)

            # Should have successful data
            self.assertIn("success", report.results)
            self.assertNotIn("fail1", report.results)
            self.assertNotIn("fail2", report.results)

    def test_timeout_error_message_format(self):
        """Test that timeout error messages are properly formatted."""
        with patch(
            "snail_core.core.get_all_collectors", return_value={"timeout_test": TimeoutCollector}
        ):
            core = SnailCore(self.config)
            report = core.collect(["timeout_test"])

            self.assertEqual(len(report.errors), 1)
            error_msg = report.errors[0]
            self.assertIn("timeout_test", error_msg)
            self.assertIn("failed", error_msg.lower())

    def test_collection_report_structure_with_errors(self):
        """Test that collection report maintains proper structure with errors."""
        with patch(
            "snail_core.core.get_all_collectors", return_value={"mixed_test": SuccessCollector}
        ):
            core = SnailCore(self.config)
            report = core.collect(["mixed_test"])

            # Check report has all required fields
            self.assertIsInstance(report.hostname, str)
            self.assertIsInstance(report.host_id, str)
            self.assertIsInstance(report.collection_id, str)
            self.assertIsInstance(report.timestamp, str)
            self.assertIsInstance(report.snail_version, str)
            self.assertIsInstance(report.results, dict)
            self.assertIsInstance(report.errors, list)

            # Should have successful results
            self.assertIn("mixed_test", report.results)
            self.assertEqual(len(report.errors), 0)
