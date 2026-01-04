"""
Integration tests for configuration loading and precedence.

Tests config file loading, environment variable overrides, and programmatic overrides.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from snail_core.config import Config, DEFAULT_CONFIG_PATHS


@pytest.mark.integration


class TestConfigIntegration(unittest.TestCase):
    """Integration tests for configuration loading and precedence."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

        # Clean up temp files
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def test_config_file_loading_flat_structure(self):
        """Test loading configuration from YAML file with flat structure."""
        config_file = self.temp_dir / "config.yaml"
        config_content = """
upload_url: https://test.example.com/api
upload_enabled: false
upload_timeout: 60
api_key: test-key-123
output_dir: /tmp/test-output
log_level: DEBUG
"""
        config_file.write_text(config_content)

        config = Config.load(config_file)

        self.assertEqual(config.upload_url, "https://test.example.com/api")
        self.assertEqual(config.upload_enabled, False)
        self.assertEqual(config.upload_timeout, 60)
        self.assertEqual(config.api_key, "test-key-123")
        self.assertEqual(config.output_dir, "/tmp/test-output")
        self.assertEqual(config.log_level, "DEBUG")

        # Defaults should still apply for unset values
        self.assertEqual(config.upload_retries, 3)
        self.assertEqual(config.compress_output, True)

    def test_config_file_loading_nested_structure(self):
        """Test loading configuration from YAML file with nested structure."""
        config_file = self.temp_dir / "config.yaml"
        config_content = """
upload:
  url: https://nested.example.com/api
  enabled: false
  timeout: 45
auth:
  api_key: nested-key-456
output:
  dir: /tmp/nested-output
  compress: false
logging:
  level: WARNING
"""
        config_file.write_text(config_content)

        config = Config.load(config_file)

        self.assertEqual(config.upload_url, "https://nested.example.com/api")
        self.assertEqual(config.upload_enabled, False)
        self.assertEqual(config.upload_timeout, 45)
        self.assertEqual(config.api_key, "nested-key-456")
        self.assertEqual(config.output_dir, "/tmp/nested-output")
        self.assertEqual(config.compress_output, False)
        self.assertEqual(config.log_level, "WARNING")

    def test_environment_variable_overrides_config_file(self):
        """Test that environment variables override config file values."""
        config_file = self.temp_dir / "config.yaml"
        config_content = """
upload_url: https://file.example.com/api
upload_enabled: false
upload_timeout: 30
api_key: file-key
"""
        config_file.write_text(config_content)

        # Set environment variables to override
        os.environ["SNAIL_UPLOAD_URL"] = "https://env.example.com/api"
        os.environ["SNAIL_UPLOAD_ENABLED"] = "true"
        os.environ["SNAIL_UPLOAD_TIMEOUT"] = "90"
        os.environ["SNAIL_API_KEY"] = "env-key"

        config = Config.load(config_file)

        # Environment variables should take precedence
        self.assertEqual(config.upload_url, "https://env.example.com/api")
        self.assertEqual(config.upload_enabled, True)
        self.assertEqual(config.upload_timeout, 90)
        self.assertEqual(config.api_key, "env-key")

    def test_programmatic_override_takes_highest_precedence(self):
        """Test that programmatic values override everything else."""
        config_file = self.temp_dir / "config.yaml"
        config_content = """
upload_url: https://file.example.com/api
upload_timeout: 30
"""
        config_file.write_text(config_content)

        # Set environment variable
        os.environ["SNAIL_UPLOAD_URL"] = "https://env.example.com/api"
        os.environ["SNAIL_UPLOAD_TIMEOUT"] = "60"

        # Create config with programmatic overrides
        config = Config(
            upload_url="https://programmatic.example.com/api",
            upload_timeout=120,
        )

        # Programmatic values should take precedence
        self.assertEqual(config.upload_url, "https://programmatic.example.com/api")
        self.assertEqual(config.upload_timeout, 120)

    def test_config_file_search_order(self):
        """Test that config files are searched in the correct priority order."""
        # Create config files in different locations (simulating the search order)
        system_config = self.temp_dir / "system.yaml"
        user_config = self.temp_dir / "user.yaml"
        local_config = self.temp_dir / "local.yaml"

        system_config.write_text("upload_url: https://system.example.com/api\nlog_level: ERROR")
        user_config.write_text("upload_url: https://user.example.com/api\nlog_level: WARNING")
        local_config.write_text("upload_url: https://local.example.com/api\nlog_level: INFO")

        # Mock the DEFAULT_CONFIG_PATHS to use our test files
        with patch("snail_core.config.DEFAULT_CONFIG_PATHS", [system_config, user_config, local_config]):
            config = Config.load()

            # Should load from first existing file (system_config)
            self.assertEqual(config.upload_url, "https://system.example.com/api")
            self.assertEqual(config.log_level, "ERROR")

    def test_explicit_config_path_overrides_search(self):
        """Test that explicitly specified config path overrides automatic search."""
        # Create multiple config files
        auto_config = self.temp_dir / "auto.yaml"
        explicit_config = self.temp_dir / "explicit.yaml"

        auto_config.write_text("upload_url: https://auto.example.com/api")
        explicit_config.write_text("upload_url: https://explicit.example.com/api")

        # Mock DEFAULT_CONFIG_PATHS to include auto_config
        with patch("snail_core.config.DEFAULT_CONFIG_PATHS", [auto_config]):
            config = Config.load(explicit_config)

            # Should load from explicit path, not auto-discovered
            self.assertEqual(config.upload_url, "https://explicit.example.com/api")

    def test_environment_variable_type_coercion(self):
        """Test that environment variables are properly type-coerced."""
        config_file = self.temp_dir / "config.yaml"
        config_content = """
upload_enabled: false
upload_timeout: 30
"""
        config_file.write_text(config_content)

        # Set environment variables with string values
        os.environ["SNAIL_UPLOAD_ENABLED"] = "true"
        os.environ["SNAIL_UPLOAD_TIMEOUT"] = "120"
        os.environ["SNAIL_UPLOAD_URL"] = "https://env.example.com/api"

        config = Config.load(config_file)

        # Should be properly coerced to correct types
        self.assertIsInstance(config.upload_enabled, bool)
        self.assertEqual(config.upload_enabled, True)
        self.assertIsInstance(config.upload_timeout, int)
        self.assertEqual(config.upload_timeout, 120)
        self.assertIsInstance(config.upload_url, str)
        self.assertEqual(config.upload_url, "https://env.example.com/api")

    def test_environment_variable_boolean_variants(self):
        """Test various boolean representations in environment variables."""
        test_cases = [
            ("true", True), ("TRUE", True), ("True", True), ("1", True), ("yes", True), ("YES", True),
            ("false", False), ("FALSE", False), ("False", False), ("0", False), ("no", False), ("NO", False),
            ("anything_else", False)
        ]

        for env_value, expected_bool in test_cases:
            with self.subTest(env_value=env_value):
                # Clear previous env var
                os.environ.pop("SNAIL_UPLOAD_ENABLED", None)

                # Set new value
                os.environ["SNAIL_UPLOAD_ENABLED"] = env_value

                config = Config.load()
                self.assertEqual(config.upload_enabled, expected_bool)
                self.assertIsInstance(config.upload_enabled, bool)

    def test_missing_config_file_returns_defaults(self):
        """Test that missing config file gracefully falls back to defaults."""
        config = Config.load()

        # Should have default values
        self.assertIsNone(config.upload_url)
        self.assertEqual(config.upload_enabled, True)
        self.assertEqual(config.upload_timeout, 30)
        self.assertEqual(config.upload_retries, 3)
        self.assertIsNone(config.api_key)
        self.assertEqual(config.output_dir, "/var/lib/snail-core")
        self.assertEqual(config.log_level, "INFO")

    def test_invalid_config_file_raises_error(self):
        """Test that invalid config file path raises FileNotFoundError."""
        nonexistent_file = self.temp_dir / "nonexistent.yaml"

        with self.assertRaises(FileNotFoundError):
            Config.from_file(nonexistent_file)

    def test_config_file_with_unknown_fields_ignored(self):
        """Test that unknown fields in config file are ignored."""
        config_file = self.temp_dir / "config.yaml"
        config_content = """
upload_url: https://test.example.com/api
unknown_field: some_value
nested:
  unknown_nested: another_value
  known_field: should_work
"""
        config_file.write_text(config_content)

        config = Config.load(config_file)

        # Known fields should work
        self.assertEqual(config.upload_url, "https://test.example.com/api")

        # Unknown fields should be ignored (no errors)

    def test_config_round_trip_serialization(self):
        """Test that config can be serialized and deserialized correctly."""
        # Create config with non-sensitive values only (to avoid redaction issues)
        original_config = Config(
            upload_url="https://test.example.com/api",
            upload_enabled=False,
            upload_timeout=60,
            output_dir="/tmp/test",
            log_level="DEBUG",
            compress_output=False,
        )

        # Test round-trip serialization for non-sensitive values
        config_dict = original_config.to_dict()
        restored_config = Config.from_dict(config_dict)

        # All non-sensitive fields should be preserved
        self.assertEqual(original_config.upload_url, restored_config.upload_url)
        self.assertEqual(original_config.upload_enabled, restored_config.upload_enabled)
        self.assertEqual(original_config.upload_timeout, restored_config.upload_timeout)
        self.assertEqual(original_config.output_dir, restored_config.output_dir)
        self.assertEqual(original_config.log_level, restored_config.log_level)
        self.assertEqual(original_config.compress_output, restored_config.compress_output)

        # API key should be None (not set) and redacted in dict
        self.assertIsNone(original_config.api_key)
        self.assertIsNone(restored_config.api_key)
        self.assertEqual(config_dict["auth"]["api_key"], None)

    def test_config_serialization_redacts_sensitive_values(self):
        """Test that sensitive values are redacted in serialization."""
        config = Config(api_key="secret-key-123")

        config_dict = config.to_dict()

        # API key should be redacted
        self.assertEqual(config_dict["auth"]["api_key"], "***")

        # But the actual config should still have the real value
        self.assertEqual(config.api_key, "secret-key-123")

    def test_config_to_dict_structure(self):
        """Test that to_dict() returns correct nested structure."""
        config = Config(
            upload_url="https://test.example.com/api",
            upload_enabled=False,
            api_key="test-key",
            output_dir="/tmp/test",
        )

        config_dict = config.to_dict()

        # Should have nested structure
        self.assertIn("upload", config_dict)
        self.assertIn("auth", config_dict)
        self.assertIn("output", config_dict)

        # Upload section
        upload = config_dict["upload"]
        self.assertEqual(upload["url"], "https://test.example.com/api")
        self.assertEqual(upload["enabled"], False)

        # Auth section - API key should be redacted
        auth = config_dict["auth"]
        self.assertEqual(auth["api_key"], "***")  # Redacted for security

        # Output section
        output = config_dict["output"]
        self.assertEqual(output["dir"], "/tmp/test")
