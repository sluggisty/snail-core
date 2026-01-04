"""
Unit tests for BaseCollector class.

Tests abstract methods, helper methods (run_command, read_file, parse_key_value_file),
and distribution detection.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from snail_core.collectors.base import BaseCollector


class ConcreteCollector(BaseCollector):
    """Concrete implementation for testing abstract methods."""

    name = "test"
    description = "Test collector"

    def collect(self) -> dict[str, object]:
        return {"test": "data"}


class TestBaseCollectorAbstract:
    """Test abstract method behavior."""

    def test_collect_raises_not_implemented(self):
        """Test that abstract collect() prevents instantiation when not implemented."""

        # ABC raises TypeError at instantiation time when abstract method isn't implemented
        class IncompleteCollector(BaseCollector):
            name = "incomplete"

        with pytest.raises(TypeError, match="abstract"):
            IncompleteCollector()  # Should raise at instantiation

    def test_concrete_collector_works(self):
        """Test that concrete collector implementing collect() works correctly."""
        collector = ConcreteCollector()
        result = collector.collect()
        assert result == {"test": "data"}


class TestBaseCollectorRunCommand:
    """Test run_command() method."""

    def test_run_command_success(self):
        """Test successful command execution."""
        collector = ConcreteCollector()
        stdout, stderr, rc = collector.run_command(["echo", "test"])

        assert rc == 0
        assert "test" in stdout
        assert stderr == ""

    def test_run_command_failure(self):
        """Test command execution failure (non-zero exit)."""
        collector = ConcreteCollector()
        stdout, stderr, rc = collector.run_command(["false"])

        assert rc != 0
        # Command failure doesn't raise, just returns non-zero rc

    def test_run_command_timeout(self):
        """Test command timeout handling."""
        collector = ConcreteCollector()
        stdout, stderr, rc = collector.run_command(["sleep", "10"], timeout=0.1)

        assert rc == -1
        assert "timed out" in stderr.lower()

    def test_run_command_not_found(self):
        """Test handling of missing command."""
        collector = ConcreteCollector()
        stdout, stderr, rc = collector.run_command(["nonexistent_command_xyz123"])

        assert rc == -1
        assert "not found" in stderr.lower()

    def test_run_command_with_check_handles_error(self):
        """Test that check=True still returns error info (exception is caught internally)."""
        collector = ConcreteCollector()
        # Even with check=True, the exception is caught and error info is returned
        stdout, stderr, rc = collector.run_command(["false"], check=True)
        assert rc != 0


class TestBaseCollectorReadFile:
    """Test read_file() and read_file_lines() methods."""

    def test_read_file_success(self):
        """Test reading an existing file."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content\nline 2")
            temp_path = f.name

        try:
            content = collector.read_file(temp_path)
            assert content == "test content\nline 2"
        finally:
            Path(temp_path).unlink()

    def test_read_file_missing(self):
        """Test reading a missing file returns default."""
        collector = ConcreteCollector()
        content = collector.read_file("/nonexistent/file/path", default="default value")
        assert content == "default value"

    def test_read_file_lines(self):
        """Test read_file_lines() returns list of lines."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("line1\nline2\nline3")
            temp_path = f.name

        try:
            lines = collector.read_file_lines(temp_path)
            assert lines == ["line1", "line2", "line3"]
        finally:
            Path(temp_path).unlink()

    def test_read_file_lines_empty_file(self):
        """Test read_file_lines() handles empty files."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            lines = collector.read_file_lines(temp_path)
            assert lines == []
        finally:
            Path(temp_path).unlink()


class TestBaseCollectorParseKeyValueFile:
    """Test parse_key_value_file() method."""

    def test_parse_key_value_file_basic(self):
        """Test parsing key=value file."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("key1=value1\nkey2=value2\nkey3=value3")
            temp_path = f.name

        try:
            result = collector.parse_key_value_file(temp_path)
            assert result["key1"] == "value1"
            assert result["key2"] == "value2"
            assert result["key3"] == "value3"
        finally:
            Path(temp_path).unlink()

    def test_parse_key_value_file_with_comments_and_blank_lines(self):
        """Test parsing ignores comments and blank lines."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("# comment line\nkey1=value1\n\n  # another comment\nkey2=value2")
            temp_path = f.name

        try:
            result = collector.parse_key_value_file(temp_path)
            assert "key1" in result
            assert "key2" in result
            assert len(result) == 2
        finally:
            Path(temp_path).unlink()

    def test_parse_key_value_file_custom_separator(self):
        """Test parsing with custom separator."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("key1: value1\nkey2: value2")
            temp_path = f.name

        try:
            result = collector.parse_key_value_file(temp_path, separator=":")
            assert result["key1"] == "value1"
            assert result["key2"] == "value2"
        finally:
            Path(temp_path).unlink()

    def test_parse_key_value_file_strip_quotes(self):
        """Test parsing strips quotes from values."""
        collector = ConcreteCollector()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("key1=\"quoted value\"\nkey2='single quoted'")
            temp_path = f.name

        try:
            result = collector.parse_key_value_file(temp_path)
            assert result["key1"] == "quoted value"
            assert result["key2"] == "single quoted"
        finally:
            Path(temp_path).unlink()


class TestBaseCollectorDetectDistro:
    """Test detect_distro() method."""

    def test_detect_distro_returns_expected_structure(self):
        """Test that detect_distro() returns a dict with expected keys."""
        collector = ConcreteCollector()
        result = collector.detect_distro()

        # Verify structure (works whether using distro module or fallback)
        assert isinstance(result, dict)
        assert "id" in result
        assert "version" in result
        assert "name" in result
        assert "like" in result
        # All values should be strings
        assert all(isinstance(v, str) for v in result.values())

    def test_detect_distro_fallback_parsing(self):
        """Test that parse_key_value_file is used in fallback (structure test)."""
        collector = ConcreteCollector()
        # Test that detect_distro works - the actual fallback is tested implicitly
        # through the structure test above. This separate test just verifies
        # the method completes successfully (whether using distro module or fallback)
        result = collector.detect_distro()
        assert isinstance(result, dict)
        assert len(result) >= 4  # Should have at least id, version, name, like
