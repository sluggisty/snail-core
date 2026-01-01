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

from snail_core.config import Config, DEFAULT_CONFIG_PATHS


class TestConfigDefaults:
    """Test Config class initialization with default values."""

    def test_default_values(self):
        """Test that all default values are set correctly when creating Config with no arguments."""
        config = Config()

        # Upload settings defaults
        assert config.upload_url is None
        assert config.upload_enabled is True
        assert config.upload_timeout == 30
        assert config.upload_retries == 3

        # Authentication defaults
        assert config.api_key is None
        assert config.auth_cert_path is None
        assert config.auth_key_path is None

        # Collection settings defaults
        assert config.enabled_collectors == []
        assert config.disabled_collectors == []
        assert config.collection_timeout == 300

        # Output settings defaults
        assert config.output_dir == "/var/lib/snail-core"
        assert config.keep_local_copy is False
        assert config.compress_output is True

        # Logging defaults
        assert config.log_level == "INFO"
        assert config.log_file is None

        # Privacy defaults
        assert config.anonymize_hostnames is False
        assert config.redact_passwords is True
        assert config.exclude_paths == []


class TestConfigFromDict:
    """Test Config creation from dictionary."""

    def test_from_dict_flat_structure(self):
        """Test creating Config from flat dictionary."""
        data = {
            "upload_url": "https://example.com/api",
            "upload_enabled": False,
            "upload_timeout": 60,
            "log_level": "DEBUG",
        }
        config = Config.from_dict(data)

        assert config.upload_url == "https://example.com/api"
        assert config.upload_enabled is False
        assert config.upload_timeout == 60
        assert config.log_level == "DEBUG"

    def test_from_dict_nested_structure(self):
        """Test creating Config from nested dictionary (flattening)."""
        data = {
            "upload": {
                "url": "https://example.com/api",
                "enabled": False,
                "timeout": 60,
            },
            "logging": {
                "level": "DEBUG",
            },
        }
        config = Config.from_dict(data)

        assert config.upload_url == "https://example.com/api"
        assert config.upload_enabled is False
        assert config.upload_timeout == 60
        assert config.log_level == "DEBUG"

    def test_from_dict_unknown_fields_filtered(self):
        """Test that unknown fields are filtered out."""
        data = {
            "upload_url": "https://example.com/api",
            "unknown_field": "should be ignored",
            "another_unknown": 12345,
        }
        config = Config.from_dict(data)

        assert config.upload_url == "https://example.com/api"
        assert not hasattr(config, "unknown_field")
        assert not hasattr(config, "another_unknown")

    def test_from_dict_list_fields(self):
        """Test creating Config with list fields."""
        data = {
            "enabled_collectors": ["system", "network"],
            "disabled_collectors": ["logs"],
            "exclude_paths": ["/tmp", "/var/tmp"],
        }
        config = Config.from_dict(data)

        assert config.enabled_collectors == ["system", "network"]
        assert config.disabled_collectors == ["logs"]
        assert config.exclude_paths == ["/tmp", "/var/tmp"]

    def test_from_dict_empty_dict(self):
        """Test creating Config from empty dictionary (uses defaults)."""
        config = Config.from_dict({})
        # Should have all defaults
        assert config.upload_url is None
        assert config.upload_enabled is True
        assert config.log_level == "INFO"


class TestConfigFromFile:
    """Test Config creation from YAML file."""

    def test_from_file_valid_yaml(self):
        """Test loading Config from valid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://example.com/api",
                    "enabled": True,
                },
                "log_level": "DEBUG",
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)
            assert config.upload_url == "https://example.com/api"
            assert config.upload_enabled is True
            assert config.log_level == "DEBUG"
        finally:
            os.unlink(temp_path)

    def test_from_file_missing_file(self):
        """Test that loading from missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            Config.from_file("/nonexistent/path/config.yaml")

    def test_from_file_empty_file(self):
        """Test loading from empty YAML file (uses defaults)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)
            # Should have defaults
            assert config.upload_url is None
            assert config.upload_enabled is True
        finally:
            os.unlink(temp_path)

    def test_from_file_invalid_yaml(self):
        """Test loading from invalid YAML file raises appropriate error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML
            temp_path = f.name

        try:
            with pytest.raises(yaml.YAMLError):
                Config.from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_from_file_nested_structure_flattening(self):
        """Test that from_file() correctly flattens nested configuration structures."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://nested.example.com/api",
                    "enabled": False,
                    "timeout": 60,
                    "retries": 5,
                },
                "auth": {
                    "api_key": "test-key",
                    "cert_path": "/path/to/cert.pem",
                    "key_path": "/path/to/key.pem",
                },
                "collection": {
                    "enabled_collectors": ["system", "network"],
                    "disabled_collectors": ["logs"],
                    "timeout": 600,
                },
                "output": {
                    "dir": "/tmp/snail",
                    "keep_local": True,
                    "compress": False,
                },
                "logging": {
                    "level": "DEBUG",
                    "file": "/var/log/snail.log",
                },
                "privacy": {
                    "anonymize_hostnames": True,
                    "redact_passwords": False,
                    "exclude_paths": ["/tmp", "/var/tmp"],
                },
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)

            # Verify nested upload section is flattened
            assert config.upload_url == "https://nested.example.com/api"
            assert config.upload_enabled is False
            assert config.upload_timeout == 60
            assert config.upload_retries == 5

            # Verify nested auth section is flattened
            assert config.api_key == "test-key"
            assert config.auth_cert_path == "/path/to/cert.pem"
            assert config.auth_key_path == "/path/to/key.pem"

            # Verify nested collection section is flattened
            assert config.enabled_collectors == ["system", "network"]
            assert config.disabled_collectors == ["logs"]
            assert config.collection_timeout == 600

            # Verify nested output section is flattened
            assert config.output_dir == "/tmp/snail"
            assert config.keep_local_copy is True
            assert config.compress_output is False

            # Verify nested logging section is flattened
            assert config.log_level == "DEBUG"
            assert config.log_file == "/var/log/snail.log"

            # Verify nested privacy section is flattened
            assert config.anonymize_hostnames is True
            assert config.redact_passwords is False
            assert config.exclude_paths == ["/tmp", "/var/tmp"]
        finally:
            os.unlink(temp_path)

    def test_from_file_field_filtering(self):
        """Test that from_file() filters out unknown fields, keeping only known config fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://example.com/api",
                },
                "log_level": "DEBUG",
                # Unknown fields that should be filtered out
                "unknown_field": "should be ignored",
                "another_unknown": 12345,
                "nested_unknown": {
                    "sub_field": "also ignored",
                },
                "yet_another_unknown": ["list", "of", "unknown", "values"],
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)

            # Known fields should be present
            assert config.upload_url == "https://example.com/api"
            assert config.log_level == "DEBUG"

            # Unknown fields should not be present
            assert not hasattr(config, "unknown_field")
            assert not hasattr(config, "another_unknown")
            assert not hasattr(config, "nested_unknown")
            assert not hasattr(config, "yet_another_unknown")
        finally:
            os.unlink(temp_path)

    def test_from_file_mixed_nested_and_flat(self):
        """Test from_file() with mixed nested and flat structures."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                # Nested structure
                "upload": {
                    "url": "https://example.com/api",
                    "enabled": True,
                },
                # Flat structure at same level
                "log_level": "WARNING",
                "output_dir": "/custom/output",
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)

            # Nested values should be flattened and accessible
            assert config.upload_url == "https://example.com/api"
            assert config.upload_enabled is True

            # Flat values should be accessible directly
            assert config.log_level == "WARNING"
            assert config.output_dir == "/custom/output"
        finally:
            os.unlink(temp_path)


class TestConfigEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_env_override_string(self):
        """Test environment variable overrides for string values."""
        config = Config()
        with patch.dict(os.environ, {"SNAIL_UPLOAD_URL": "https://env.example.com/api"}):
            config._apply_env_overrides()
            assert config.upload_url == "https://env.example.com/api"

    def test_env_override_bool_true(self):
        """Test environment variable overrides for boolean values (true variants)."""
        config = Config()
        for true_value in ["true", "TRUE", "True", "1", "yes", "YES"]:
            with patch.dict(os.environ, {"SNAIL_UPLOAD_ENABLED": true_value}, clear=True):
                config.upload_enabled = False  # Reset to False
                config._apply_env_overrides()
                assert config.upload_enabled is True, f"Failed for value: {true_value}"

    def test_env_override_bool_false(self):
        """Test environment variable overrides for boolean values (false variants)."""
        config = Config()
        for false_value in ["false", "FALSE", "False", "0", "no", "NO", "anything"]:
            with patch.dict(os.environ, {"SNAIL_UPLOAD_ENABLED": false_value}, clear=True):
                config.upload_enabled = True  # Reset to True
                config._apply_env_overrides()
                assert config.upload_enabled is False, f"Failed for value: {false_value}"

    def test_env_override_int(self):
        """Test environment variable overrides for integer values."""
        config = Config()
        with patch.dict(os.environ, {"SNAIL_UPLOAD_TIMEOUT": "120"}):
            config._apply_env_overrides()
            assert config.upload_timeout == 120
            assert isinstance(config.upload_timeout, int)

    def test_env_override_int_various_values(self):
        """Test integer environment variable overrides with various valid values."""
        config = Config()
        test_cases = [
            ("0", 0),
            ("1", 1),
            ("30", 30),
            ("300", 300),
            ("12345", 12345),
        ]
        for env_value, expected_int in test_cases:
            with patch.dict(os.environ, {"SNAIL_UPLOAD_TIMEOUT": env_value}, clear=True):
                config._apply_env_overrides()
                assert config.upload_timeout == expected_int
                assert isinstance(config.upload_timeout, int)

    def test_env_override_int_invalid_value(self):
        """Test that invalid integer environment variables raise ValueError."""
        config = Config()
        with patch.dict(os.environ, {"SNAIL_UPLOAD_TIMEOUT": "not-an-int"}):
            with pytest.raises(ValueError, match="invalid literal"):
                config._apply_env_overrides()

    def test_env_override_string_multiple(self):
        """Test multiple string environment variables are handled correctly."""
        config = Config()
        with patch.dict(
            os.environ,
            {
                "SNAIL_UPLOAD_URL": "https://string1.example.com/api",
                "SNAIL_API_KEY": "test-api-key-456",
                "SNAIL_AUTH_CERT": "/path/to/cert.pem",
                "SNAIL_AUTH_KEY": "/path/to/key.pem",
                "SNAIL_OUTPUT_DIR": "/tmp/test-output",
                "SNAIL_LOG_LEVEL": "DEBUG",
                "SNAIL_LOG_FILE": "/var/log/test.log",
            },
        ):
            config._apply_env_overrides()

        assert config.upload_url == "https://string1.example.com/api"
        assert config.api_key == "test-api-key-456"
        assert config.auth_cert_path == "/path/to/cert.pem"
        assert config.auth_key_path == "/path/to/key.pem"
        assert config.output_dir == "/tmp/test-output"
        assert config.log_level == "DEBUG"
        assert config.log_file == "/var/log/test.log"

    def test_env_override_bool_explicit_no(self):
        """Test that 'no' explicitly sets boolean to False."""
        config = Config()
        config.upload_enabled = True
        with patch.dict(os.environ, {"SNAIL_UPLOAD_ENABLED": "no"}):
            config._apply_env_overrides()
            assert config.upload_enabled is False

    def test_env_override_bool_explicit_yes(self):
        """Test that 'yes' explicitly sets boolean to True."""
        config = Config()
        config.upload_enabled = False
        with patch.dict(os.environ, {"SNAIL_UPLOAD_ENABLED": "yes"}):
            config._apply_env_overrides()
            assert config.upload_enabled is True

    def test_env_override_all_variables(self):
        """Test all supported environment variables."""
        env_vars = {
            "SNAIL_UPLOAD_URL": "https://env.example.com/api",
            "SNAIL_UPLOAD_ENABLED": "false",
            "SNAIL_UPLOAD_TIMEOUT": "45",
            "SNAIL_API_KEY": "test-api-key-123",
            "SNAIL_AUTH_CERT": "/path/to/cert.pem",
            "SNAIL_AUTH_KEY": "/path/to/key.pem",
            "SNAIL_OUTPUT_DIR": "/tmp/snail-output",
            "SNAIL_LOG_LEVEL": "ERROR",
            "SNAIL_LOG_FILE": "/var/log/snail.log",
        }
        config = Config()

        with patch.dict(os.environ, env_vars):
            config._apply_env_overrides()

        assert config.upload_url == "https://env.example.com/api"
        assert config.upload_enabled is False
        assert config.upload_timeout == 45
        assert config.api_key == "test-api-key-123"
        assert config.auth_cert_path == "/path/to/cert.pem"
        assert config.auth_key_path == "/path/to/key.pem"
        assert config.output_dir == "/tmp/snail-output"
        assert config.log_level == "ERROR"
        assert config.log_file == "/var/log/snail.log"

    def test_env_override_missing_variables(self):
        """Test that missing environment variables don't override defaults."""
        config = Config()
        original_values = {
            "upload_url": config.upload_url,
            "upload_enabled": config.upload_enabled,
            "log_level": config.log_level,
        }

        with patch.dict(os.environ, {}, clear=True):
            config._apply_env_overrides()

        assert config.upload_url == original_values["upload_url"]
        assert config.upload_enabled == original_values["upload_enabled"]
        assert config.log_level == original_values["log_level"]


class TestConfigPrecedence:
    """Test configuration precedence order."""

    def test_precedence_defaults_only(self):
        """Test that defaults are used when no other sources are provided."""
        config = Config()
        assert config.upload_url is None
        assert config.upload_enabled is True
        assert config.log_level == "INFO"

    def test_precedence_file_over_defaults(self):
        """Test that config file values override defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://file.example.com/api",
                    "enabled": False,
                },
                "log_level": "WARNING",
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {}, clear=True):
                config = Config.from_file(temp_path)
                assert config.upload_url == "https://file.example.com/api"
                assert config.upload_enabled is False
                assert config.log_level == "WARNING"
        finally:
            os.unlink(temp_path)

    def test_precedence_env_over_file(self):
        """Test that environment variables override config file values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://file.example.com/api",
                    "enabled": False,
                },
                "log_level": "WARNING",
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            env_vars = {
                "SNAIL_UPLOAD_URL": "https://env.example.com/api",
                "SNAIL_UPLOAD_ENABLED": "true",
                "SNAIL_LOG_LEVEL": "DEBUG",
            }
            with patch.dict(os.environ, env_vars):
                config = Config.from_file(temp_path)
                config._apply_env_overrides()

                # Env vars should override file values
                assert config.upload_url == "https://env.example.com/api"
                assert config.upload_enabled is True
                assert config.log_level == "DEBUG"
        finally:
            os.unlink(temp_path)


class TestConfigSerialization:
    """Test Config serialization methods (to_dict() and save())."""

    def test_to_dict_structure_validation(self):
        """Test that to_dict() returns correct nested structure."""
        config = Config(
            upload_url="https://example.com/api",
            upload_enabled=True,
            upload_timeout=60,
            upload_retries=5,
            api_key="test-key",
            auth_cert_path="/path/to/cert.pem",
            auth_key_path="/path/to/key.pem",
            enabled_collectors=["system", "network"],
            disabled_collectors=["logs"],
            collection_timeout=600,
            output_dir="/tmp/snail",
            keep_local_copy=True,
            compress_output=False,
            log_level="DEBUG",
            log_file="/var/log/snail.log",
            anonymize_hostnames=True,
            redact_passwords=False,
            exclude_paths=["/tmp", "/var/tmp"],
        )

        result = config.to_dict()

        # Verify top-level structure
        assert isinstance(result, dict)
        assert "upload" in result
        assert "auth" in result
        assert "collection" in result
        assert "output" in result
        assert "logging" in result
        assert "privacy" in result

        # Verify upload section
        assert result["upload"]["url"] == "https://example.com/api"
        assert result["upload"]["enabled"] is True
        assert result["upload"]["timeout"] == 60
        assert result["upload"]["retries"] == 5

        # Verify auth section
        assert result["auth"]["api_key"] == "***"  # Redacted
        assert result["auth"]["cert_path"] == "/path/to/cert.pem"
        assert result["auth"]["key_path"] == "/path/to/key.pem"

        # Verify collection section
        assert result["collection"]["enabled_collectors"] == ["system", "network"]
        assert result["collection"]["disabled_collectors"] == ["logs"]
        assert result["collection"]["timeout"] == 600

        # Verify output section
        assert result["output"]["dir"] == "/tmp/snail"
        assert result["output"]["keep_local"] is True
        assert result["output"]["compress"] is False

        # Verify logging section
        assert result["logging"]["level"] == "DEBUG"
        assert result["logging"]["file"] == "/var/log/snail.log"

        # Verify privacy section
        assert result["privacy"]["anonymize_hostnames"] is True
        assert result["privacy"]["redact_passwords"] is False
        assert result["privacy"]["exclude_paths"] == ["/tmp", "/var/tmp"]

    def test_to_dict_with_defaults(self):
        """Test to_dict() with default values."""
        config = Config()
        result = config.to_dict()

        # Verify structure exists even with defaults
        assert "upload" in result
        assert "auth" in result
        assert "collection" in result
        assert "output" in result
        assert "logging" in result
        assert "privacy" in result

        # Verify default values
        assert result["upload"]["url"] is None
        assert result["upload"]["enabled"] is True
        assert result["upload"]["timeout"] == 30
        assert result["upload"]["retries"] == 3
        assert result["auth"]["api_key"] is None
        assert result["logging"]["level"] == "INFO"

    def test_to_dict_password_redaction_with_key(self):
        """Test that to_dict() redacts API key when present."""
        config = Config(api_key="secret-api-key-12345")
        result = config.to_dict()

        # API key should be redacted
        assert result["auth"]["api_key"] == "***"
        assert result["auth"]["api_key"] != "secret-api-key-12345"
        # Original config should still have the key
        assert config.api_key == "secret-api-key-12345"

    def test_to_dict_password_redaction_without_key(self):
        """Test that to_dict() shows None when API key is not set."""
        config = Config(api_key=None)
        result = config.to_dict()

        # API key should be None (not redacted, just not set)
        assert result["auth"]["api_key"] is None

    def test_to_dict_password_redaction_empty_string(self):
        """Test that to_dict() handles empty API key string."""
        config = Config(api_key="")
        result = config.to_dict()

        # Empty string is falsy in Python, so it should be None (not redacted)
        # The check is "if self.api_key", and "" is falsy
        assert result["auth"]["api_key"] is None

    def test_save_creates_file(self):
        """Test that save() creates a YAML file correctly."""
        config = Config(
            upload_url="https://example.com/api",
            upload_enabled=True,
            log_level="DEBUG",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Save config
            config.save(temp_path)

            # Verify file exists
            assert Path(temp_path).exists()

            # Verify file is valid YAML
            with open(temp_path) as f:
                data = yaml.safe_load(f)

            assert isinstance(data, dict)
            assert "upload" in data
            assert "logging" in data
        finally:
            os.unlink(temp_path)

    def test_save_creates_directory(self):
        """Test that save() creates parent directories if they don't exist."""
        config = Config()
        temp_dir = tempfile.mkdtemp()
        config_path = Path(temp_dir) / "subdir" / "config.yaml"

        try:
            # Save to path with non-existent parent directory
            config.save(config_path)

            # Verify file and directory were created
            assert config_path.exists()
            assert config_path.parent.exists()
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_save_file_contents(self):
        """Test that save() writes correct content to file."""
        config = Config(
            upload_url="https://test.example.com/api",
            upload_enabled=False,
            upload_timeout=120,
            log_level="WARNING",
            output_dir="/custom/output",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            config.save(temp_path)

            # Load and verify contents
            with open(temp_path) as f:
                data = yaml.safe_load(f)

            assert data["upload"]["url"] == "https://test.example.com/api"
            assert data["upload"]["enabled"] is False
            assert data["upload"]["timeout"] == 120
            assert data["logging"]["level"] == "WARNING"
            assert data["output"]["dir"] == "/custom/output"
        finally:
            os.unlink(temp_path)

    def test_save_round_trip_basic(self):
        """Test round-trip: save() -> load() -> compare (basic values)."""
        original_config = Config(
            upload_url="https://roundtrip.example.com/api",
            upload_enabled=False,
            upload_timeout=90,
            log_level="ERROR",
            output_dir="/tmp/roundtrip",
            keep_local_copy=True,
            compress_output=False,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Save config
            original_config.save(temp_path)

            # Load config
            loaded_config = Config.from_file(temp_path)

            # Compare values (excluding API key which is redacted)
            assert loaded_config.upload_url == original_config.upload_url
            assert loaded_config.upload_enabled == original_config.upload_enabled
            assert loaded_config.upload_timeout == original_config.upload_timeout
            assert loaded_config.log_level == original_config.log_level
            assert loaded_config.output_dir == original_config.output_dir
            assert loaded_config.keep_local_copy == original_config.keep_local_copy
            assert loaded_config.compress_output == original_config.compress_output
        finally:
            os.unlink(temp_path)

    def test_save_round_trip_complex(self):
        """Test round-trip with complex values (lists, nested structures)."""
        original_config = Config(
            enabled_collectors=["system", "network", "packages"],
            disabled_collectors=["logs"],
            exclude_paths=["/tmp", "/var/tmp", "/dev/shm"],
            collection_timeout=900,
            auth_cert_path="/path/to/cert.pem",
            auth_key_path="/path/to/key.pem",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Save config
            original_config.save(temp_path)

            # Load config
            loaded_config = Config.from_file(temp_path)

            # Compare complex values
            assert loaded_config.enabled_collectors == original_config.enabled_collectors
            assert loaded_config.disabled_collectors == original_config.disabled_collectors
            assert loaded_config.exclude_paths == original_config.exclude_paths
            assert loaded_config.collection_timeout == original_config.collection_timeout
            assert loaded_config.auth_cert_path == original_config.auth_cert_path
            assert loaded_config.auth_key_path == original_config.auth_key_path
        finally:
            os.unlink(temp_path)

    def test_save_round_trip_all_fields(self):
        """Test round-trip with all config fields set."""
        original_config = Config(
            upload_url="https://full.example.com/api",
            upload_enabled=True,
            upload_timeout=60,
            upload_retries=5,
            auth_cert_path="/full/cert.pem",
            auth_key_path="/full/key.pem",
            enabled_collectors=["system"],
            disabled_collectors=["logs", "network"],
            collection_timeout=300,
            output_dir="/full/output",
            keep_local_copy=True,
            compress_output=True,
            log_level="DEBUG",
            log_file="/full/log.log",
            anonymize_hostnames=True,
            redact_passwords=True,
            exclude_paths=["/tmp"],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Save config
            original_config.save(temp_path)

            # Load config
            loaded_config = Config.from_file(temp_path)

            # Compare all fields (except api_key which is redacted)
            assert loaded_config.upload_url == original_config.upload_url
            assert loaded_config.upload_enabled == original_config.upload_enabled
            assert loaded_config.upload_timeout == original_config.upload_timeout
            assert loaded_config.upload_retries == original_config.upload_retries
            assert loaded_config.auth_cert_path == original_config.auth_cert_path
            assert loaded_config.auth_key_path == original_config.auth_key_path
            assert loaded_config.enabled_collectors == original_config.enabled_collectors
            assert loaded_config.disabled_collectors == original_config.disabled_collectors
            assert loaded_config.collection_timeout == original_config.collection_timeout
            assert loaded_config.output_dir == original_config.output_dir
            assert loaded_config.keep_local_copy == original_config.keep_local_copy
            assert loaded_config.compress_output == original_config.compress_output
            assert loaded_config.log_level == original_config.log_level
            assert loaded_config.log_file == original_config.log_file
            assert loaded_config.anonymize_hostnames == original_config.anonymize_hostnames
            assert loaded_config.redact_passwords == original_config.redact_passwords
            assert loaded_config.exclude_paths == original_config.exclude_paths
        finally:
            os.unlink(temp_path)

    def test_save_overwrites_existing_file(self):
        """Test that save() overwrites an existing file."""
        config1 = Config(upload_url="https://first.example.com/api", log_level="INFO")
        config2 = Config(upload_url="https://second.example.com/api", log_level="DEBUG")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Save first config
            config1.save(temp_path)

            # Verify first config is saved
            with open(temp_path) as f:
                data1 = yaml.safe_load(f)
            assert data1["upload"]["url"] == "https://first.example.com/api"

            # Save second config (should overwrite)
            config2.save(temp_path)

            # Verify second config overwrote first
            with open(temp_path) as f:
                data2 = yaml.safe_load(f)
            assert data2["upload"]["url"] == "https://second.example.com/api"
            assert data2["logging"]["level"] == "DEBUG"
        finally:
            os.unlink(temp_path)

    def test_precedence_programmatic_over_all(self):
        """Test that programmatic values override env vars and file values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://file.example.com/api",
                },
                "log_level": "WARNING",
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            env_vars = {
                "SNAIL_UPLOAD_URL": "https://env.example.com/api",
                "SNAIL_LOG_LEVEL": "DEBUG",
            }
            with patch.dict(os.environ, env_vars):
                # Load from file and apply env overrides
                config = Config.from_file(temp_path)
                config._apply_env_overrides()

                # Now override programmatically
                config.upload_url = "https://programmatic.example.com/api"
                config.log_level = "ERROR"

                # Programmatic values should win
                assert config.upload_url == "https://programmatic.example.com/api"
                assert config.log_level == "ERROR"
        finally:
            os.unlink(temp_path)

    def test_precedence_load_method(self):
        """Test that Config.load() applies correct precedence (file -> env)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_data = {
                "upload": {
                    "url": "https://file.example.com/api",
                },
                "log_level": "WARNING",
            }
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            env_vars = {
                "SNAIL_UPLOAD_URL": "https://env.example.com/api",
                "SNAIL_LOG_LEVEL": "DEBUG",
            }
            with patch.dict(os.environ, env_vars):
                config = Config.load(temp_path)

                # Env vars should override file values
                assert config.upload_url == "https://env.example.com/api"
                assert config.log_level == "DEBUG"
        finally:
            os.unlink(temp_path)

