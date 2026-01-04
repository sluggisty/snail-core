"""
Unit tests for SnailCore class.

Tests core orchestration, collector execution, and report generation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4


from snail_core.config import Config
from snail_core.core import CollectionReport, SnailCore


class TestSnailCoreInitialization:
    """Test SnailCore class initialization."""

    def test_init_with_config(self):
        """Test initialization with Config object."""
        config = Config(upload_url="https://test.com/api")
        core = SnailCore(config)

        assert core.config is config
        assert hasattr(core, "collectors")
        assert hasattr(core, "uploader")

    def test_init_without_config(self):
        """Test initialization without config (uses defaults)."""
        core = SnailCore()

        assert isinstance(core.config, Config)
        assert hasattr(core, "collectors")
        assert hasattr(core, "uploader")

    def test_collector_discovery(self):
        """Test that collectors are properly discovered."""
        core = SnailCore()
        assert hasattr(core, "collectors")
        assert isinstance(core.collectors, dict)
        assert len(core.collectors) > 0

    @patch("snail_core.core.Uploader")
    def test_uploader_init_with_upload_url(self, mock_uploader_class):
        """Test uploader initialization when upload URL is configured."""
        mock_uploader = MagicMock()
        mock_uploader_class.return_value = mock_uploader

        config = Config(upload_url="https://test.com/api")
        core = SnailCore(config)

        mock_uploader_class.assert_called_once_with(config)
        assert core.uploader is mock_uploader

    def test_uploader_none_without_upload_url(self):
        """Test that uploader is None when no upload URL configured."""
        config = Config(upload_url=None)
        core = SnailCore(config)

        assert core.uploader is None

    @patch("snail_core.core.Uploader")
    def test_uploader_init_with_env_var_url(self, mock_uploader_class):
        """Test uploader initialization when upload URL comes from env var."""
        mock_uploader = MagicMock()
        mock_uploader_class.return_value = mock_uploader

        config = Config(upload_url=None)  # No URL in config

        with patch.dict("os.environ", {"SNAIL_UPLOAD_URL": "https://env.com/api"}):
            core = SnailCore(config)

        # Should update config.upload_url and create uploader
        assert core.config.upload_url == "https://env.com/api"
        mock_uploader_class.assert_called_once_with(core.config)


class TestSnailCoreCollect:
    """Test SnailCore.collect() method."""

    def test_collect_returns_collection_report(self):
        """Test that collect() returns a CollectionReport."""
        core = SnailCore()
        result = core.collect()

        assert isinstance(result, CollectionReport)
        assert hasattr(result, "hostname")
        assert hasattr(result, "host_id")
        assert hasattr(result, "collection_id")
        assert hasattr(result, "timestamp")
        assert hasattr(result, "snail_version")
        assert hasattr(result, "results")
        assert hasattr(result, "errors")

    def test_collect_with_all_collectors(self):
        """Test collection with all collectors (default)."""
        core = SnailCore()

        # Mock collector class and execution
        mock_collector_class = MagicMock()
        mock_collector_instance = MagicMock()
        mock_collector_instance.collect.return_value = {"test": "data"}
        mock_collector_class.return_value = mock_collector_instance

        with patch.object(core, "collectors", {"test": mock_collector_class}):
            report = core.collect()

        assert "test" in report.results
        assert report.results["test"] == {"test": "data"}
        mock_collector_instance.collect.assert_called_once()

    def test_collect_with_specific_collectors(self):
        """Test collection with specific collectors only."""
        core = SnailCore()

        # Mock collector classes and instances
        mock_class1 = MagicMock()
        mock_instance1 = MagicMock()
        mock_instance1.collect.return_value = {"c1": "data1"}
        mock_class1.return_value = mock_instance1

        mock_class2 = MagicMock()
        mock_instance2 = MagicMock()
        mock_instance2.collect.return_value = {"c2": "data2"}
        mock_class2.return_value = mock_instance2

        collectors = {
            "collector1": mock_class1,
            "collector2": mock_class2,
            "collector3": MagicMock(),  # Not selected
        }

        with patch.object(core, "collectors", collectors):
            report = core.collect(collector_names=["collector1", "collector2"])

        assert "collector1" in report.results
        assert "collector2" in report.results
        assert "collector3" not in report.results
        assert report.results["collector1"] == {"c1": "data1"}
        assert report.results["collector2"] == {"c2": "data2"}

        mock_instance1.collect.assert_called_once()
        mock_instance2.collect.assert_called_once()

    def test_collect_with_invalid_collector_names(self):
        """Test collection with invalid collector names (should be ignored)."""
        core = SnailCore()

        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.collect.return_value = {"valid": "data"}
        mock_class.return_value = mock_instance

        with patch.object(core, "collectors", {"valid": mock_class}):
            report = core.collect(collector_names=["valid", "invalid1", "invalid2"])

        assert "valid" in report.results
        assert report.results["valid"] == {"valid": "data"}
        mock_instance.collect.assert_called_once()

    def test_collect_handles_collector_exceptions(self):
        """Test that collector exceptions are caught and added to errors."""
        core = SnailCore()

        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.collect.side_effect = Exception("Collector failed")
        mock_class.return_value = mock_instance

        with patch.object(core, "collectors", {"failing": mock_class}):
            report = core.collect()

        assert "failing" not in report.results
        assert len(report.errors) > 0
        assert "failing" in " ".join(report.errors) or "Exception" in " ".join(report.errors)

    def test_collect_report_metadata(self):
        """Test that report contains correct metadata."""
        core = SnailCore()

        # Mock host_id to ensure consistency
        with patch("snail_core.core.get_host_id", return_value="test-host-id"):
            with patch.object(core, "collectors", {}):  # No collectors
                report = core.collect()

        assert report.host_id == "test-host-id"
        assert isinstance(report.collection_id, str)
        assert len(report.collection_id) > 0
        assert isinstance(report.timestamp, str)
        assert len(report.timestamp) > 0
        # Version should be a string (like "0.5.4")
        assert isinstance(report.snail_version, str)
        assert len(report.snail_version) > 0
        assert isinstance(report.hostname, str)
        assert len(report.hostname) > 0

    def test_collect_empty_collector_list(self):
        """Test collection with empty collector names (should run all)."""
        core = SnailCore()

        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.collect.return_value = {"test": "data"}
        mock_class.return_value = mock_instance

        with patch.object(core, "collectors", {"test": mock_class}):
            report = core.collect(collector_names=[])

        assert "test" in report.results
        mock_instance.collect.assert_called_once()


class TestCollectionReport:
    """Test CollectionReport class."""

    def test_collection_report_creation(self):
        """Test CollectionReport creation and basic properties."""
        hostname = "test-host"
        host_id = "test-host-id"
        collection_id = str(uuid4())
        timestamp = "2024-01-01T00:00:00Z"
        snail_version = "0.1.0"
        results = {"test": {"data": "value"}}
        errors = ["error message"]

        report = CollectionReport(
            hostname=hostname,
            host_id=host_id,
            collection_id=collection_id,
            timestamp=timestamp,
            snail_version=snail_version,
            results=results,
            errors=errors,
        )

        assert report.hostname == hostname
        assert report.host_id == host_id
        assert report.collection_id == collection_id
        assert report.timestamp == timestamp
        assert report.snail_version == snail_version
        assert report.results == results
        assert report.errors == errors

    def test_to_dict(self):
        """Test CollectionReport.to_dict() method."""
        hostname = "test-host"
        host_id = "test-host-id"
        collection_id = str(uuid4())
        timestamp = "2024-01-01T00:00:00Z"
        snail_version = "0.1.0"
        results = {"test": {"data": "value"}}
        errors = ["error message"]

        report = CollectionReport(
            hostname=hostname,
            host_id=host_id,
            collection_id=collection_id,
            timestamp=timestamp,
            snail_version=snail_version,
            results=results,
            errors=errors,
        )

        data = report.to_dict()

        assert "meta" in data
        assert "data" in data
        assert "errors" in data

        assert data["meta"]["hostname"] == hostname
        assert data["meta"]["host_id"] == host_id
        assert data["meta"]["collection_id"] == collection_id
        assert data["meta"]["timestamp"] == timestamp
        assert data["meta"]["snail_version"] == snail_version
        assert data["data"] == results
        assert data["errors"] == errors

    def test_to_json(self):
        """Test CollectionReport.to_json() method."""
        hostname = "test-host"
        host_id = "test-host-id"
        collection_id = str(uuid4())
        timestamp = "2024-01-01T00:00:00Z"
        snail_version = "0.1.0"
        results = {"test": {"data": "value"}}
        errors = ["error message"]

        report = CollectionReport(
            hostname=hostname,
            host_id=host_id,
            collection_id=collection_id,
            timestamp=timestamp,
            snail_version=snail_version,
            results=results,
            errors=errors,
        )

        json_str = report.to_json()
        assert isinstance(json_str, str)

        # Should be valid JSON
        import json

        data = json.loads(json_str)
        assert "meta" in data
        assert "data" in data
        assert "errors" in data
