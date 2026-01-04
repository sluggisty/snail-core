"""
Error handling tests for file read operations.

Tests that collectors handle file read errors gracefully.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from snail_core.collectors.base import BaseCollector


@pytest.mark.integration
class FileErrorCollector(BaseCollector):
    """Test collector that exercises file reading functionality."""

    name = "file_error_test"
    description = "Test collector for file read error handling"

    def collect(self):
        result = {}

        # Test 1: Read existing file
        result["existing_file"] = self.read_file("/etc/hostname", "default_hostname")

        # Test 2: Read missing file
        result["missing_file"] = self.read_file("/does/not/exist", "default_value")

        # Test 3: Read file with permission issues
        result["permission_file"] = self.read_file("/etc/shadow", "no_permission")

        # Test 4: Read file lines from existing file
        lines = self.read_file_lines("/etc/hostname")
        result["existing_file_lines"] = lines

        # Test 5: Read file lines from missing file
        lines = self.read_file_lines("/does/not/exist")
        result["missing_file_lines"] = lines

        # Test 6: Parse key-value file that exists
        try:
            kv_data = self.parse_key_value_file("/etc/os-release")
            result["kv_parse_success"] = bool(kv_data)
            result["kv_sample"] = list(kv_data.keys())[:3] if kv_data else []
        except Exception as e:
            result["kv_parse_error"] = str(e)

        # Test 7: Parse key-value file that doesn't exist
        kv_data = self.parse_key_value_file("/does/not/exist.conf")
        result["kv_parse_missing"] = kv_data

        # Test 8: Parse malformed key-value file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f:
            f.write("INVALID LINE WITHOUT EQUALS\nKEY1=value1\n=incomplete\nKEY2=value2\n")
            temp_file = f.name

        try:
            kv_data = self.parse_key_value_file(temp_file)
            result["kv_parse_malformed"] = kv_data
        finally:
            Path(temp_file).unlink(missing_ok=True)

        return result


class TestFileErrors(unittest.TestCase):
    """Test file read error handling."""

    def test_missing_file_returns_default(self):
        """Test that missing files return default values."""
        collector = FileErrorCollector()

        result = collector.read_file("/definitely/does/not/exist", "my_default")

        self.assertEqual(result, "my_default")

    def test_permission_denied_returns_default(self):
        """Test that permission denied returns default values."""
        collector = FileErrorCollector()

        result = collector.read_file("/etc/shadow", "access_denied")

        self.assertEqual(result, "access_denied")

    def test_read_file_lines_missing_file(self):
        """Test that read_file_lines handles missing files."""
        collector = FileErrorCollector()

        lines = collector.read_file_lines("/definitely/does/not/exist")

        self.assertEqual(lines, [])

    def test_parse_key_value_missing_file(self):
        """Test that parse_key_value_file handles missing files."""
        collector = FileErrorCollector()

        data = collector.parse_key_value_file("/definitely/does/not/exist")

        self.assertEqual(data, {})

    def test_parse_key_value_malformed_content(self):
        """Test that parse_key_value_file handles malformed content."""
        collector = FileErrorCollector()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f:
            f.write("INVALID LINE\nKEY1=value1\n=incomplete key\nKEY2=value2\n")
            temp_file = f.name

        try:
            data = collector.parse_key_value_file(temp_file)

            # Should parse valid lines and ignore invalid ones
            self.assertIn("KEY1", data)
            self.assertIn("KEY2", data)
            self.assertEqual(data["KEY1"], "value1")
            self.assertEqual(data["KEY2"], "value2")
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_parse_key_value_with_quotes(self):
        """Test that parse_key_value_file handles quoted values."""
        collector = FileErrorCollector()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f:
            f.write("KEY1=\"quoted value\"\nKEY2='single quoted'\nKEY3=unquoted\n")
            temp_file = f.name

        try:
            data = collector.parse_key_value_file(temp_file)

            self.assertEqual(data["KEY1"], "quoted value")
            self.assertEqual(data["KEY2"], "single quoted")
            self.assertEqual(data["KEY3"], "unquoted")
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_parse_key_value_custom_separator(self):
        """Test that parse_key_value_file works with custom separators."""
        collector = FileErrorCollector()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f:
            f.write("KEY1: value1\nKEY2 :value2\nKEY3:value3\n")
            temp_file = f.name

        try:
            data = collector.parse_key_value_file(temp_file, separator=":")

            self.assertEqual(data["KEY1"], "value1")
            self.assertEqual(data["KEY2"], "value2")
            self.assertEqual(data["KEY3"], "value3")
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_file_operations_dont_crash_collector(self):
        """Test that file operation failures don't crash the collector."""
        collector = FileErrorCollector()

        # This should not raise an exception
        result = collector.collect()

        # Should return a result dict
        self.assertIsInstance(result, dict)
        self.assertIn("missing_file", result)
        self.assertIn("missing_file_lines", result)
        self.assertIn("kv_parse_missing", result)

    def test_empty_file_handling(self):
        """Test handling of empty files."""
        collector = FileErrorCollector()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            # Create empty file
            temp_file = f.name

        try:
            content = collector.read_file(temp_file, "default")
            self.assertEqual(content, "")  # Empty file returns empty string

            lines = collector.read_file_lines(temp_file)
            self.assertEqual(lines, [])  # Empty file returns empty list

            kv_data = collector.parse_key_value_file(temp_file)
            self.assertEqual(kv_data, {})  # Empty file returns empty dict
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_file_read_preserves_content(self):
        """Test that successful file reads preserve content."""
        collector = FileErrorCollector()

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_content = "line 1\nline 2\nline 3"
            f.write(test_content)
            temp_file = f.name

        try:
            content = collector.read_file(temp_file)
            self.assertEqual(content, test_content)

            lines = collector.read_file_lines(temp_file)
            self.assertEqual(lines, ["line 1", "line 2", "line 3"])
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_binary_file_handling(self):
        """Test handling of binary files (should not crash)."""
        collector = FileErrorCollector()

        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"\x00\x01\x02\x03binary data\x04\x05")
            temp_file = f.name

        try:
            content = collector.read_file(temp_file, "default")
            # Should return the binary data as string (may include replacement chars)
            self.assertIsInstance(content, str)
            self.assertIn("binary", content)  # Should contain readable parts
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_file_path_edge_cases(self):
        """Test file operations with edge case paths."""
        collector = FileErrorCollector()

        # Empty path
        result = collector.read_file("", "default")
        self.assertEqual(result, "default")

        # None path (should handle gracefully)
        try:
            result = collector.read_file(None, "default")  # type: ignore
        except (TypeError, AttributeError):
            # Expected to fail with None
            pass

        # Very long path
        long_path = "/nonexistent/" + "a" * 200
        result = collector.read_file(long_path, "default")
        self.assertEqual(result, "default")
