"""
End-to-end tests for complete collection and upload workflow.

Tests the full system workflow from configuration to upload verification.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from snail_core.config import Config
from snail_core.core import CollectionReport, SnailCore


class TestFullWorkflow(unittest.TestCase):
    """Test complete collection and upload workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config(
            upload_enabled=True,
            upload_url="https://test.example.com/api/upload",
            api_key="test-key-123",
            upload_timeout=30,
            compress_output=True,
            output_dir=str(self.temp_dir),
        )

    def tearDown(self):
        """Clean up test environment."""
        # Clean up any files created during tests
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def test_complete_collection_and_upload_flow(self):
        """Test the complete workflow: config -> collect -> upload."""
        core = SnailCore(self.config)

        # Mock successful collection
        mock_report = CollectionReport(
            hostname="test-host",
            host_id="test-host-id",
            collection_id="test-collection-id",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={
                "system": {"os": "Linux", "hostname": "test-host"},
                "hardware": {"cpu": "Intel", "memory": "8GB"}
            }
        )

        # Mock successful upload
        mock_upload_response = {"status": "success", "report_id": "12345"}

        with patch.object(core, 'collect', return_value=mock_report), \
             patch.object(core.uploader.session, 'post') as mock_post, \
             patch('snail_core.core.ensure_api_key', return_value=True):

            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = json.dumps(mock_upload_response)
            mock_response.ok = True
            mock_response.json.return_value = mock_upload_response
            mock_post.return_value = mock_response

            # Execute the full workflow
            report, upload_response = core.collect_and_upload()

            # Verify collection worked
            self.assertIsInstance(report, CollectionReport)
            self.assertEqual(report.hostname, "test-host")
            self.assertEqual(len(report.results), 2)
            self.assertIn("system", report.results)
            self.assertIn("hardware", report.results)

            # Verify upload worked
            self.assertIsNotNone(upload_response)
            self.assertEqual(upload_response["status"], "success")
            self.assertEqual(upload_response["report_id"], "12345")

            # Verify the HTTP call was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check that the URL was called
            self.assertEqual(call_args[0][0], "https://test.example.com/api/upload")

            # Check that headers were passed
            headers = call_args[1]['headers']
            self.assertIn("Content-Encoding", headers)
            self.assertEqual(headers["Content-Encoding"], "gzip")

    def test_report_structure_validation(self):
        """Test that generated reports have correct structure."""
        core = SnailCore(self.config)

        # Mock minimal collection
        with patch('snail_core.core.get_all_collectors', return_value={
            'system': lambda: MockCollector("system", {"os": "Linux"}),
            'hardware': lambda: MockCollector("hardware", {"cpu": "Intel"})
        }):
            report = core.collect()

            # Validate report structure
            self.assertIsInstance(report, CollectionReport)
            self.assertIsInstance(report.hostname, str)
            self.assertIsInstance(report.host_id, str)
            self.assertIsInstance(report.collection_id, str)
            self.assertIsInstance(report.timestamp, str)
            self.assertIsInstance(report.snail_version, str)
            self.assertIsInstance(report.results, dict)
            self.assertIsInstance(report.errors, list)

            # Should have collected data
            self.assertGreater(len(report.results), 0)
            self.assertEqual(len(report.errors), 0)  # No errors expected

            # Should be serializable to dict
            report_dict = report.to_dict()
            self.assertIn("meta", report_dict)
            self.assertIn("data", report_dict)
            self.assertIn("errors", report_dict)

            # Meta should have all required fields
            meta = report_dict["meta"]
            self.assertIn("hostname", meta)
            self.assertIn("host_id", meta)
            self.assertIn("collection_id", meta)
            self.assertIn("timestamp", meta)
            self.assertIn("snail_version", meta)

    def test_upload_payload_validation(self):
        """Test that upload payloads are correctly formatted."""
        core = SnailCore(self.config)

        # Create a test report
        test_report = CollectionReport(
            hostname="test-host",
            host_id="test-host-id",
            collection_id="test-collection-id",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={"test": {"data": "value"}}
        )

        # Get the payload that would be uploaded
        payload_dict = test_report.to_dict()

        # Validate payload structure
        self.assertIn("meta", payload_dict)
        self.assertIn("data", payload_dict)
        self.assertIn("errors", payload_dict)

        # Validate meta section
        meta = payload_dict["meta"]
        self.assertEqual(meta["hostname"], "test-host")
        self.assertEqual(meta["host_id"], "test-host-id")
        self.assertEqual(meta["collection_id"], "test-collection-id")

        # Validate data section
        data = payload_dict["data"]
        self.assertEqual(data, {"test": {"data": "value"}})

        # Should be JSON serializable
        json_str = json.dumps(payload_dict, default=str)
        self.assertIsInstance(json_str, str)

        # Should be deserializable
        parsed = json.loads(json_str)
        self.assertEqual(parsed["meta"]["hostname"], "test-host")
        self.assertEqual(parsed["data"], {"test": {"data": "value"}})

    def test_authentication_verification(self):
        """Test that authentication headers are properly set."""
        config = Config(
            upload_url="https://test.example.com",
            api_key="test-api-key-123",
            upload_enabled=True
        )

        from snail_core.uploader import Uploader
        uploader = Uploader(config)

        # Check that API key is set in session headers
        self.assertIn("X-API-Key", uploader.session.headers)
        self.assertEqual(uploader.session.headers["X-API-Key"], "test-api-key-123")

        # Check other default headers
        self.assertEqual(uploader.session.headers["User-Agent"], f"snail-core/{uploader._get_version()}")
        self.assertEqual(uploader.session.headers["Content-Type"], "application/json")
        self.assertEqual(uploader.session.headers["Accept"], "application/json")

    def test_compression_verification(self):
        """Test that compression is applied correctly."""
        import gzip

        config = Config(
            upload_url="https://test.example.com",
            api_key="test-key",
            compress_output=True
        )

        from snail_core.uploader import Uploader
        uploader = Uploader(config)

        test_data = {"test": "data", "numbers": [1, 2, 3], "nested": {"key": "value"}}
        json_data = json.dumps(test_data, default=str)

        # Compress the data
        compressed_data = gzip.compress(json_data.encode("utf-8"))

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.ok = True
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(uploader.session, 'post', return_value=mock_response) as mock_post:
            result = uploader.upload(CollectionReport(
                hostname="test",
                host_id="test-id",
                collection_id="test-collection",
                timestamp="2024-01-01T00:00:00Z",
                snail_version="1.0.0",
                results=test_data
            ))

            # Verify upload was called
            self.assertEqual(result["status"], "ok")

            # Verify compression was applied
            call_args = mock_post.call_args
            sent_headers = call_args[1]['headers']

            # Should be compressed
            self.assertIn("Content-Encoding", sent_headers)
            self.assertEqual(sent_headers["Content-Encoding"], "gzip")

            # Should be able to decompress the sent data
            sent_data = call_args[1]['data']  # data is in kwargs
            decompressed = gzip.decompress(sent_data).decode("utf-8")
            parsed_data = json.loads(decompressed)
            self.assertEqual(parsed_data["data"], test_data)

    def test_workflow_with_upload_failure(self):
        """Test complete workflow when upload fails."""
        core = SnailCore(self.config)

        # Mock successful collection
        mock_report = CollectionReport(
            hostname="test-host",
            host_id="test-host-id",
            collection_id="test-collection-id",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0",
            results={"system": {"os": "Linux"}}
        )

        with patch.object(core, 'collect', return_value=mock_report), \
             patch.object(core.uploader, 'upload', side_effect=Exception("Upload failed")):

            # Execute workflow
            report, upload_response = core.collect_and_upload()

            # Collection should still succeed
            self.assertIsInstance(report, CollectionReport)
            self.assertEqual(report.hostname, "test-host")

            # Upload should fail gracefully
            self.assertIsNone(upload_response)

            # Error should be recorded in report
            self.assertGreater(len(report.errors), 0)
            self.assertIn("Upload failed", report.errors[0])

    def test_workflow_with_collection_failure(self):
        """Test workflow when collection partially fails."""
        # Mock collectors before SnailCore initialization
        with patch('snail_core.core.get_all_collectors', return_value={
            'success_collector': SuccessCollector,
            'failing_collector': FailingCollector
        }):
            core = SnailCore(self.config)
            report, upload_response = core.collect_and_upload()

            # Should have partial results
            self.assertIn("success_collector", report.results)
            self.assertNotIn("failing_collector", report.results)

            # Should have errors recorded
            self.assertGreater(len(report.errors), 0)

            # Upload should still attempt (since some data was collected)
            # But will be None due to upload being disabled in test

    def test_workflow_configuration_persistence(self):
        """Test that configuration changes persist through workflow."""
        # Create a config file
        config_content = """
        upload:
          url: "https://workflow-test.example.com"
          enabled: true
        auth:
          api_key: "workflow-key-123"
        collection:
          timeout: 120
        """

        config_file = self.temp_dir / "workflow_config.yaml"
        config_file.write_text(config_content)

        # Load config and create core
        config = Config.load(config_file)
        core = SnailCore(config)

        # Verify config was loaded correctly
        self.assertEqual(core.config.upload_url, "https://workflow-test.example.com")
        self.assertTrue(core.config.upload_enabled)
        self.assertEqual(core.config.api_key, "workflow-key-123")
        self.assertEqual(core.config.collection_timeout, 120)

        # Run workflow (will fail on upload but that's ok)
        with patch.object(core, 'collect', return_value=CollectionReport(
            hostname="test",
            host_id="test-id",
            collection_id="test-collection",
            timestamp="2024-01-01T00:00:00Z",
            snail_version="1.0.0"
        )):
            report, upload_response = core.collect_and_upload()

            # Should use the configured upload URL
            self.assertEqual(core.config.upload_url, "https://workflow-test.example.com")


# Helper classes for testing
class MockCollector:
    """Mock collector for testing."""

    def __init__(self):
        self.name = "mock_collector"

    def collect(self):
        return {"mock": "data"}


class SuccessCollector:
    """Mock collector that succeeds."""

    def __init__(self):
        self.name = "success_collector"

    def collect(self):
        return {"data": "good"}


class FailingCollector:
    """Mock collector that always fails."""

    def __init__(self):
        self.name = "failing"

    def collect(self):
        raise Exception("Mock collector failure")
