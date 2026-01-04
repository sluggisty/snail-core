"""
Error handling tests for configuration loading and validation.

Tests that configuration system handles invalid files, missing fields, and type errors gracefully.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from snail_core.config import Config


@pytest.mark.integration
class TestConfigErrors(unittest.TestCase):
    """Test configuration error handling."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test environment."""
        # Clean up any files created during tests
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def create_test_file(self, content: str, filename: str = "test.yaml"):
        """Create a test config file."""
        file_path = self.temp_dir / filename
        file_path.write_text(content)
        return file_path

    def test_invalid_yaml_syntax(self):
        """Test handling of invalid YAML syntax."""
        invalid_yaml = """
        upload:
          url: "https://example.com"
          enabled: true
        invalid: yaml: syntax: here
        [unclosed bracket
        """

        config_file = self.create_test_file(invalid_yaml)

        # Should raise YAML error when trying to load invalid YAML
        with self.assertRaises(yaml.YAMLError):
            Config.load(config_file)

    def test_missing_config_file_uses_defaults(self):
        """Test that missing config files fall back to defaults."""
        # Test with non-existent file
        config = Config.load("/definitely/does/not/exist.yaml")

        # Should return default config
        self.assertIsInstance(config, Config)
        self.assertIsNone(config.upload_url)
        self.assertTrue(config.upload_enabled)
        self.assertEqual(config.upload_timeout, 30)
        self.assertEqual(config.upload_retries, 3)

    def test_empty_config_file(self):
        """Test handling of empty config files."""
        config_file = self.create_test_file("")

        config = Config.load(config_file)

        # Should return default config
        self.assertIsInstance(config, Config)
        self.assertIsNone(config.upload_url)

    def test_invalid_field_values_type_conversion(self):
        """Test handling of invalid field values and type conversion."""
        config_content = """
        upload:
          url: "https://example.com"
          enabled: "not_a_boolean"
          timeout: "not_a_number"
          retries: "also_not_a_number"
        collection:
          timeout: "invalid_timeout"
        """

        config_file = self.create_test_file(config_content)

        # The config system preserves invalid types since dataclass doesn't validate
        config = Config.load(config_file)

        self.assertIsInstance(config, Config)
        # Valid string should be preserved
        self.assertEqual(config.upload_url, "https://example.com")
        # Invalid values are preserved as-is (no type validation in dataclass)
        self.assertEqual(config.upload_enabled, "not_a_boolean")
        self.assertEqual(config.upload_timeout, "not_a_number")
        self.assertEqual(config.upload_retries, "also_not_a_number")
        self.assertEqual(config.collection_timeout, "invalid_timeout")

    def test_unknown_field_filtering(self):
        """Test that unknown fields are filtered out."""
        config_content = """
        upload:
          url: "https://example.com"
          unknown_field: "should_be_filtered"
        completely_unknown_section:
          field1: value1
          field2: value2
        known_field_with_unknown_subfield:
          known_sub: "keep_this"
          unknown_sub: "filter_this"
        """

        config_file = self.create_test_file(config_content)

        config = Config.load(config_file)

        # Should preserve known fields
        self.assertEqual(config.upload_url, "https://example.com")

        # Should filter out unknown fields - check that config only has known attributes
        known_fields = {f.name for f in Config.__dataclass_fields__.values()}
        config_dict = config.__dict__

        for field in config_dict.keys():
            self.assertIn(field, known_fields, f"Unknown field {field} should have been filtered")

    def test_nested_vs_flat_structure_conversion(self):
        """Test conversion between nested and flat configuration structures."""
        # Test nested structure (preferred)
        nested_config = """
        upload:
          url: "https://nested.example.com"
          enabled: true
          timeout: 60
        auth:
          api_key: "nested_key"
        collection:
          timeout: 120
        output:
          dir: "/tmp/nested"
        """

        # Test flat structure (also supported)
        flat_config = """
        upload_url: "https://flat.example.com"
        upload_enabled: false
        upload_timeout: 90
        api_key: "flat_key"
        collection_timeout: 180
        output_dir: "/tmp/flat"
        """

        # Test nested
        nested_file = self.create_test_file(nested_config, "nested.yaml")
        nested_config_obj = Config.load(nested_file)

        self.assertEqual(nested_config_obj.upload_url, "https://nested.example.com")
        self.assertTrue(nested_config_obj.upload_enabled)
        self.assertEqual(nested_config_obj.upload_timeout, 60)
        self.assertEqual(nested_config_obj.api_key, "nested_key")
        self.assertEqual(nested_config_obj.collection_timeout, 120)
        self.assertEqual(nested_config_obj.output_dir, "/tmp/nested")

        # Test flat
        flat_file = self.create_test_file(flat_config, "flat.yaml")
        flat_config_obj = Config.load(flat_file)

        self.assertEqual(flat_config_obj.upload_url, "https://flat.example.com")
        self.assertFalse(flat_config_obj.upload_enabled)
        self.assertEqual(flat_config_obj.upload_timeout, 90)
        self.assertEqual(flat_config_obj.api_key, "flat_key")
        self.assertEqual(flat_config_obj.collection_timeout, 180)
        self.assertEqual(flat_config_obj.output_dir, "/tmp/flat")

    def test_environment_variable_overrides(self):
        """Test that environment variables override config file values."""
        config_content = """
        upload:
          url: "https://config.example.com"
          enabled: true
        auth:
          api_key: "config_key"
        """

        config_file = self.create_test_file(config_content)

        # Set environment variables
        env_vars = {
            "SNAIL_UPLOAD_URL": "https://env.example.com",
            "SNAIL_UPLOAD_ENABLED": "false",
            "SNAIL_API_KEY": "env_key",
            "SNAIL_UPLOAD_TIMEOUT": "120",
        }

        with patch.dict(os.environ, env_vars):
            config = Config.load(config_file)

            # Environment variables should override config file
            self.assertEqual(config.upload_url, "https://env.example.com")
            self.assertFalse(config.upload_enabled)
            self.assertEqual(config.api_key, "env_key")
            self.assertEqual(config.upload_timeout, 120)

    def test_invalid_environment_variable_values(self):
        """Test handling of invalid environment variable values."""
        config_content = """
        upload:
          timeout: 30
          retries: 3
        """

        config_file = self.create_test_file(config_content)

        # Set invalid environment variables
        env_vars = {
            "SNAIL_UPLOAD_TIMEOUT": "not_a_number",
            "SNAIL_UPLOAD_ENABLED": "not_a_boolean",
        }

        with patch.dict(os.environ, env_vars):
            config = Config.load(config_file)

            # Invalid env vars should be ignored, use config file values
            self.assertEqual(config.upload_timeout, 30)  # From config file
            self.assertFalse(
                config.upload_enabled
            )  # Overridden by invalid env var (converted to False)

    def test_config_file_search_order(self):
        """Test that config files are searched in the correct order."""
        # Create config files in different locations
        default_config = """
        upload:
          url: "https://default.example.com"
        """

        explicit_config = """
        upload:
          url: "https://explicit.example.com"
        """

        # Create files
        default_file = self.create_test_file(default_config, "default.yaml")
        explicit_file = self.create_test_file(explicit_config, "explicit.yaml")

        # Test explicit path
        config = Config.load(explicit_file)
        self.assertEqual(config.upload_url, "https://explicit.example.com")

        # Test default path search
        with patch("snail_core.config.DEFAULT_CONFIG_PATHS", [default_file]):
            config = Config.load()
            self.assertEqual(config.upload_url, "https://default.example.com")

    def test_config_with_comments_and_empty_lines(self):
        """Test that config files with comments and empty lines are handled."""
        config_content = """
        # This is a comment
        upload:
          # Another comment
          url: "https://example.com"

          enabled: true

        # Empty line above
        collection:
          timeout: 600
        """

        config_file = self.create_test_file(config_content)

        config = Config.load(config_file)

        self.assertEqual(config.upload_url, "https://example.com")
        self.assertTrue(config.upload_enabled)
        self.assertEqual(config.collection_timeout, 600)

    def test_config_with_special_characters(self):
        """Test handling of special characters in config values."""
        config_content = """
        upload:
          url: "https://user:password@example.com/path?query=value#fragment"
        auth:
          api_key: "special_chars:!@#$%^&*()"
        output:
          dir: "/path/with spaces/and/symbols-_.~"
        """

        config_file = self.create_test_file(config_content)

        config = Config.load(config_file)

        self.assertEqual(
            config.upload_url, "https://user:password@example.com/path?query=value#fragment"
        )
        self.assertEqual(config.api_key, "special_chars:!@#$%^&*()")
        self.assertEqual(config.output_dir, "/path/with spaces/and/symbols-_.~")

    def test_from_dict_with_invalid_data_types(self):
        """Test Config.from_dict with various invalid data types."""
        # Test with None values
        config_dict = {
            "upload_url": None,
            "upload_enabled": None,
            "upload_timeout": None,
        }

        config = Config.from_dict(config_dict)

        # Should handle None values gracefully
        self.assertIsNone(config.upload_url)
        self.assertIsNone(config.upload_enabled)  # Will be None, not converted to bool
        self.assertIsNone(config.upload_timeout)

    def test_config_validation_edge_cases(self):
        """Test various edge cases in config validation."""
        test_cases = [
            # Empty dict
            ({}, lambda c: c.upload_url is None),
            # Only unknown fields
            ({"unknown_field": "value", "another_unknown": 123}, lambda c: c.upload_url is None),
            # Mix of known and unknown
            (
                {
                    "upload_url": "https://example.com",
                    "unknown_field": "filtered",
                    "upload_enabled": False,
                },
                lambda c: c.upload_url == "https://example.com" and c.upload_enabled is False,
            ),
        ]

        for config_dict, validator in test_cases:
            with self.subTest(config_dict=config_dict):
                config = Config.from_dict(config_dict)
                self.assertTrue(validator(config))

    def test_config_round_trip_serialization(self):
        """Test that config can be serialized and deserialized."""
        original_config = Config(
            upload_url="https://test.example.com",
            upload_enabled=False,
            upload_timeout=120,
            api_key="test_key",
            output_dir="/tmp/test",
        )

        # Convert to dict
        config_dict = original_config.__dict__

        # Create new config from dict
        restored_config = Config(**config_dict)

        # Should be identical
        self.assertEqual(original_config.upload_url, restored_config.upload_url)
        self.assertEqual(original_config.upload_enabled, restored_config.upload_enabled)
        self.assertEqual(original_config.upload_timeout, restored_config.upload_timeout)
        self.assertEqual(original_config.api_key, restored_config.api_key)
        self.assertEqual(original_config.output_dir, restored_config.output_dir)
