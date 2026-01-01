"""
Unit tests for Config class.

Tests configuration loading, defaults, environment variable overrides,
and configuration precedence.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from snail_core.config import Config


class TestConfigDefaults:
    """Test Config class initialization with default values."""

    def test_default_values(self):
        """Test that all default values are set correctly."""
        config = Config()
        assert config.upload_url is None
        assert config.upload_enabled is True
        assert config.upload_timeout == 30
        assert config.log_level == "INFO"
        assert config.output_dir == "/var/lib/snail-core"


class TestConfigFromDict:
    """Test Config creation from dictionary."""

    def test_from_dict_flat_structure(self):
        """Test creating Config from flat dictionary."""
        config = Config.from_dict(
            {
                "upload_url": "https://example.com/api",
                "upload_enabled": False,
                "log_level": "DEBUG",
            }
        )
        assert config.upload_url == "https://example.com/api"
        assert config.upload_enabled is False
        assert config.log_level == "DEBUG"

    def test_from_dict_nested_structure(self):
        """Test creating Config from nested dictionary (flattening)."""
        config = Config.from_dict(
            {
                "upload": {"url": "https://example.com/api", "enabled": False},
                "logging": {"level": "DEBUG"},
            }
        )
        assert config.upload_url == "https://example.com/api"
        assert config.upload_enabled is False
        assert config.log_level == "DEBUG"

    def test_from_dict_unknown_fields_filtered(self):
        """Test that unknown fields are filtered out."""
        config = Config.from_dict(
            {
                "upload_url": "https://example.com/api",
                "unknown_field": "ignored",
            }
        )
        assert config.upload_url == "https://example.com/api"
        assert not hasattr(config, "unknown_field")


class TestConfigFromFile:
    """Test Config creation from YAML file."""

    def test_from_file_valid_yaml(self):
        """Test loading Config from valid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"upload": {"url": "https://example.com/api"}}, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)
            assert config.upload_url == "https://example.com/api"
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_file(self):
        """Test that loading from missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Config.from_file("/nonexistent/path/config.yaml")

    def test_from_file_invalid_yaml(self):
        """Test loading from invalid YAML file raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: [")
            temp_path = f.name

        try:
            with pytest.raises(yaml.YAMLError):
                Config.from_file(temp_path)
        finally:
            os.unlink(temp_path)


class TestConfigEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_env_override_string_and_int(self):
        """Test environment variable overrides for string and int values."""
        config = Config()
        with patch.dict(
            os.environ,
            {
                "SNAIL_UPLOAD_URL": "https://env.example.com/api",
                "SNAIL_UPLOAD_TIMEOUT": "120",
                "SNAIL_LOG_LEVEL": "DEBUG",
            },
        ):
            config._apply_env_overrides()
            assert config.upload_url == "https://env.example.com/api"
            assert config.upload_timeout == 120
            assert config.log_level == "DEBUG"

    def test_env_override_bool(self):
        """Test environment variable overrides for boolean values."""
        config = Config()
        # Test true variants
        for true_val in ["true", "1", "yes"]:
            with patch.dict(os.environ, {"SNAIL_UPLOAD_ENABLED": true_val}, clear=True):
                config.upload_enabled = False
                config._apply_env_overrides()
                assert config.upload_enabled is True

        # Test false variants
        for false_val in ["false", "0", "no"]:
            with patch.dict(os.environ, {"SNAIL_UPLOAD_ENABLED": false_val}, clear=True):
                config.upload_enabled = True
                config._apply_env_overrides()
                assert config.upload_enabled is False

    def test_env_override_all_variables(self):
        """Test all supported environment variables."""
        config = Config()
        with patch.dict(
            os.environ,
            {
                "SNAIL_UPLOAD_URL": "https://test.com/api",
                "SNAIL_UPLOAD_ENABLED": "false",
                "SNAIL_UPLOAD_TIMEOUT": "45",
                "SNAIL_API_KEY": "test-key",
                "SNAIL_LOG_LEVEL": "ERROR",
            },
        ):
            config._apply_env_overrides()
            assert config.upload_url == "https://test.com/api"
            assert config.upload_enabled is False
            assert config.upload_timeout == 45
            assert config.api_key == "test-key"
            assert config.log_level == "ERROR"

    def test_env_override_missing_variables(self):
        """Test that missing environment variables don't override defaults."""
        config = Config()
        original_values = {
            "upload_url": config.upload_url,
            "upload_enabled": config.upload_enabled,
        }

        with patch.dict(os.environ, {}, clear=True):
            config._apply_env_overrides()

        assert config.upload_url == original_values["upload_url"]
        assert config.upload_enabled == original_values["upload_enabled"]


class TestConfigPrecedence:
    """Test configuration precedence order."""

    def test_precedence_env_over_file(self):
        """Test that environment variables override config file values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"upload": {"url": "https://file.example.com/api"}}, f)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"SNAIL_UPLOAD_URL": "https://env.example.com/api"}):
                config = Config.from_file(temp_path)
                config._apply_env_overrides()
                # Env vars should override file values
                assert config.upload_url == "https://env.example.com/api"
        finally:
            os.unlink(temp_path)


class TestConfigSerialization:
    """Test Config serialization methods (to_dict() and save())."""

    def test_to_dict_structure(self):
        """Test that to_dict() returns correct nested structure."""
        config = Config(
            upload_url="https://example.com/api",
            upload_enabled=True,
            log_level="DEBUG",
        )
        result = config.to_dict()

        assert "upload" in result
        assert "logging" in result
        assert result["upload"]["url"] == "https://example.com/api"
        assert result["upload"]["enabled"] is True
        assert result["logging"]["level"] == "DEBUG"

    def test_to_dict_password_redaction(self):
        """Test that to_dict() redacts API key."""
        config = Config(api_key="secret-key-123")
        result = config.to_dict()
        assert result["auth"]["api_key"] == "***"
        # Original config should still have the key
        assert config.api_key == "secret-key-123"

        # Test None API key
        config2 = Config(api_key=None)
        result2 = config2.to_dict()
        assert result2["auth"]["api_key"] is None

    def test_save_and_load_round_trip(self):
        """Test round-trip: save() -> load() -> compare."""
        original_config = Config(
            upload_url="https://test.com/api",
            upload_enabled=False,
            upload_timeout=90,
            log_level="ERROR",
            output_dir="/tmp/test",
            enabled_collectors=["system", "network"],
            disabled_collectors=["logs"],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Save config
            original_config.save(temp_path)
            assert Path(temp_path).exists()

            # Load config
            loaded_config = Config.from_file(temp_path)

            # Compare values (excluding API key which is redacted)
            assert loaded_config.upload_url == original_config.upload_url
            assert loaded_config.upload_enabled == original_config.upload_enabled
            assert loaded_config.upload_timeout == original_config.upload_timeout
            assert loaded_config.log_level == original_config.log_level
            assert loaded_config.output_dir == original_config.output_dir
            assert loaded_config.enabled_collectors == original_config.enabled_collectors
            assert loaded_config.disabled_collectors == original_config.disabled_collectors
        finally:
            os.unlink(temp_path)
