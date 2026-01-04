"""
Error handling tests for collector command execution failures.

Tests that collectors handle command failures gracefully.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

from snail_core.collectors.base import BaseCollector
from snail_core.collectors.system import SystemCollector


@pytest.mark.integration
class FailingCollector(BaseCollector):
    """Test collector that simulates command failures."""

    name = "failing_test"
    description = "Test collector for command failures"

    def collect(self):
        # Try to run a command that will fail
        stdout, stderr, rc = self.run_command(["nonexistent_command_12345"])
        if rc != 0:
            # This should not crash the collector
            return {
                "command_result": "failed_gracefully",
                "stdout": stdout,
                "stderr": stderr,
                "returncode": rc,
            }
        return {"status": "unexpected_success"}


class CommandErrorCollector(BaseCollector):
    """Test collector that handles various command error scenarios."""

    name = "command_error_test"
    description = "Test collector for command error handling"

    def collect(self):
        result = {}

        # Test 1: Missing command
        stdout, stderr, rc = self.run_command(["this_command_does_not_exist"])
        result["missing_command"] = {"stdout": stdout, "stderr": stderr, "returncode": rc}

        # Test 2: Command with non-zero exit
        stdout, stderr, rc = self.run_command(["false"])  # Command that always fails
        result["false_command"] = {"stdout": stdout, "stderr": stderr, "returncode": rc}

        # Test 3: Permission denied (try to access /root)
        stdout, stderr, rc = self.run_command(["cat", "/root/secret_file"])
        result["permission_denied"] = {"stdout": stdout, "stderr": stderr, "returncode": rc}

        # Test 4: Invalid output parsing (should not crash)
        try:
            # This might produce output that can't be parsed as expected
            stdout, stderr, rc = self.run_command(["echo", "invalid output format"])
            # Try to parse as if it were structured data
            if stdout.strip():
                parsed = stdout.strip().split(" ")
                result["parsing_test"] = {"parsed": parsed, "success": True}
            else:
                result["parsing_test"] = {"success": False, "reason": "empty_output"}
        except Exception as e:
            result["parsing_test"] = {"success": False, "exception": str(e)}

        return result


class TestCollectorErrors(unittest.TestCase):
    """Test collector command error handling."""

    def test_missing_command_handling(self):
        """Test that missing commands are handled gracefully."""
        collector = FailingCollector()

        result = collector.collect()

        self.assertEqual(result["command_result"], "failed_gracefully")
        self.assertEqual(result["returncode"], -1)
        self.assertIn("Command not found", result["stderr"])

    def test_command_execution_failure_handling(self):
        """Test that command execution failures are handled."""
        collector = CommandErrorCollector()

        result = collector.collect()

        # Check missing command
        self.assertEqual(result["missing_command"]["returncode"], -1)
        self.assertIn("Command not found", result["missing_command"]["stderr"])

        # Check false command (should fail with exit code)
        false_result = result["false_command"]
        self.assertNotEqual(false_result["returncode"], 0)  # Should be non-zero

        # Check permission denied
        perm_result = result["permission_denied"]
        self.assertNotEqual(perm_result["returncode"], 0)  # Should fail

    def test_invalid_output_parsing_does_not_crash(self):
        """Test that invalid output parsing doesn't crash the collector."""
        collector = CommandErrorCollector()

        result = collector.collect()

        # Parsing test should complete without crashing
        self.assertIn("parsing_test", result)
        parsing_result = result["parsing_test"]
        self.assertIn("success", parsing_result)
        # Should either succeed or fail gracefully
        if parsing_result["success"]:
            self.assertIn("parsed", parsing_result)

    def test_real_collector_with_missing_commands(self):
        """Test that real collectors handle missing commands gracefully."""
        # Test SystemCollector with mocked missing commands
        collector = SystemCollector()

        # Mock run_command to simulate missing commands
        original_run_command = collector.run_command

        def mock_run_command(cmd, **kwargs):
            if cmd == ["hostname"]:
                return ("", "command not found: hostname", -1)
            elif cmd == ["uptime"]:
                return ("", "command not found: uptime", -1)
            else:
                return original_run_command(cmd, **kwargs)

        with patch.object(collector, "run_command", side_effect=mock_run_command):
            result = collector.collect()

            # Should still return a result structure
            self.assertIsInstance(result, dict)
            # SystemCollector returns data directly, not under a "system" key
            self.assertIn("os", result)  # Check for one of the expected keys

    def test_collector_continues_after_command_failures(self):
        """Test that collector continues collecting data after command failures."""
        collector = CommandErrorCollector()

        result = collector.collect()

        # Should have all test results despite failures
        self.assertIn("missing_command", result)
        self.assertIn("false_command", result)
        self.assertIn("permission_denied", result)
        self.assertIn("parsing_test", result)

        # All should have been executed
        self.assertEqual(len(result), 4)

    def test_run_command_with_check_false_allows_failures(self):
        """Test that run_command with check=False allows command failures."""
        collector = FailingCollector()

        # This should not raise an exception
        stdout, stderr, rc = collector.run_command(["false"], check=False)

        self.assertNotEqual(rc, 0)  # Command should fail
        # But no exception should be raised

    def test_run_command_preserves_output_on_failure(self):
        """Test that run_command preserves stdout/stderr even on failure."""
        collector = FailingCollector()

        with patch("subprocess.run") as mock_run:
            from subprocess import CalledProcessError

            mock_run.side_effect = CalledProcessError(
                1, ["failing_cmd"], "some output", "some error"
            )

            stdout, stderr, rc = collector.run_command(["failing_cmd"])

            self.assertEqual(stdout, "some output")
            self.assertEqual(stderr, "some error")
            self.assertEqual(rc, 1)

    def test_collector_error_does_not_prevent_other_data_collection(self):
        """Test that one command failure doesn't prevent other data collection."""
        collector = CommandErrorCollector()

        # Mock some commands to fail, others to succeed
        original_run_command = collector.run_command

        call_count = 0

        def mock_run_command(cmd, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:  # First call (missing command) fails
                return ("", "command not found", -1)
            elif call_count == 2:  # Second call (false) fails
                return ("", "", 1)
            else:  # Subsequent calls succeed
                return original_run_command(cmd, **kwargs)

        with patch.object(collector, "run_command", side_effect=mock_run_command):
            result = collector.collect()

            # Should still collect all data
            self.assertIn("missing_command", result)
            self.assertIn("false_command", result)
            self.assertIn("permission_denied", result)
            self.assertIn("parsing_test", result)

    def test_command_error_messages_are_informative(self):
        """Test that command error messages provide useful information."""
        collector = FailingCollector()

        stdout, stderr, rc = collector.run_command(["nonexistent_command_12345"])

        self.assertEqual(rc, -1)
        self.assertIn("nonexistent_command_12345", stderr)
        self.assertIn("Command not found", stderr)
