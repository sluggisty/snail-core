"""
Integration tests for collector execution in SnailCore context.

Tests that collectors work together and produce valid CollectionReport output.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from snail_core.config import Config
from snail_core.core import CollectionReport, SnailCore


class TestCollectorIntegration(unittest.TestCase):
    """Integration tests for collector execution in SnailCore context."""

    def setUp(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up temporary directory."""
        # Clean up any files created during tests
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def create_test_config(self) -> Config:
        """Create a test configuration."""
        return Config(
            output_dir=str(self.temp_dir),
            upload_enabled=False,  # Disable upload for tests
            collection_timeout=30,  # Short timeout for tests
        )

    def test_collect_with_system_and_hardware_collectors(self):
        """Test collection with system and hardware collectors (fast collectors)."""
        config = self.create_test_config()
        core = SnailCore(config)

        # Mock host_id to avoid file system operations
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                report = core.collect(collector_names=["system", "hardware"])

        # Verify report structure
        self.assertIsInstance(report, CollectionReport)
        self.assertEqual(report.hostname, "test-host")
        self.assertEqual(report.host_id, "test-host-id-123")
        self.assertIsInstance(report.collection_id, str)
        self.assertIsInstance(report.timestamp, str)
        self.assertIsInstance(report.snail_version, str)

        # Verify collectors ran
        self.assertIn("system", report.results)
        self.assertIn("hardware", report.results)
        self.assertEqual(len(report.results), 2)

        # Verify data structure
        for collector_name in ["system", "hardware"]:
            self.assertIsInstance(report.results[collector_name], dict)
            self.assertGreater(len(report.results[collector_name]), 0)

        # Should have no errors for these collectors
        self.assertEqual(len(report.errors), 0)

    def test_collect_with_all_collectors_structure(self):
        """Test collection structure with all collectors (mocked for speed)."""
        config = self.create_test_config()

        # Mock all collectors to return minimal data quickly
        mock_collectors = {}
        expected_collectors = ["system", "hardware", "network", "packages",
                              "services", "filesystem", "security", "logs"]
        for name in expected_collectors:
            from snail_core.collectors.base import BaseCollector
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect()

        # Verify report structure
        self.assertIsInstance(report, CollectionReport)
        self.assertEqual(report.hostname, "test-host")
        self.assertEqual(report.host_id, "test-host-id-123")

        # Should have results for all collectors
        for collector_name in expected_collectors:
            self.assertIn(collector_name, report.results)
            self.assertIsInstance(report.results[collector_name], dict)

        # Should have no errors (all mocked to succeed)
        self.assertEqual(len(report.errors), 0)

    def test_collect_handles_collector_errors(self):
        """Test that collector errors are captured properly."""
        config = self.create_test_config()

        # Create collectors where one fails
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        expected_collectors = ["system", "hardware", "network", "packages",
                              "services", "filesystem", "security", "logs"]
        for name in expected_collectors:
            if name == "system":
                # Make system collector fail
                mock_collectors[name] = self._create_failing_mock_collector(BaseCollector, name)
            else:
                mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect()

        # Verify report structure
        self.assertIsInstance(report, CollectionReport)

        # System collector should not be in results (failed)
        self.assertNotIn("system", report.results)

        # Other collectors should be in results
        self.assertIn("hardware", report.results)
        self.assertIn("network", report.results)

        # Should have one error
        self.assertEqual(len(report.errors), 1)
        self.assertIn("system", report.errors[0])
        self.assertIn("Test failure", report.errors[0])

    def test_collect_with_specific_collector_names(self):
        """Test collection with specific collector names."""
        config = self.create_test_config()

        # Mock collectors
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        expected_collectors = ["system", "hardware", "network", "packages",
                              "services", "filesystem", "security", "logs"]
        for name in expected_collectors:
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect(collector_names=["system", "hardware"])

        # Should only have results for requested collectors
        self.assertIn("system", report.results)
        self.assertIn("hardware", report.results)
        self.assertNotIn("network", report.results)
        self.assertNotIn("packages", report.results)

        self.assertEqual(len(report.results), 2)
        self.assertEqual(len(report.errors), 0)

    def test_collect_with_invalid_collector_names(self):
        """Test collection with invalid collector names (should be ignored)."""
        config = self.create_test_config()

        # Mock collectors
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        expected_collectors = ["system", "hardware", "network", "packages",
                              "services", "filesystem", "security", "logs"]
        for name in expected_collectors:
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect(collector_names=["system", "nonexistent", "hardware", "also_invalid"])

        # Should only have results for valid collectors
        self.assertIn("system", report.results)
        self.assertIn("hardware", report.results)
        self.assertNotIn("nonexistent", report.results)
        self.assertNotIn("also_invalid", report.results)

        self.assertEqual(len(report.results), 2)
        self.assertEqual(len(report.errors), 0)

    def test_collect_empty_collector_list(self):
        """Test collection with empty collector names (should run all)."""
        config = self.create_test_config()

        # Mock collectors
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        expected_collectors = ["system", "hardware", "network", "packages",
                              "services", "filesystem", "security", "logs"]
        for name in expected_collectors:
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect(collector_names=[])

        # Should have results for all collectors
        for collector_name in expected_collectors:
            self.assertIn(collector_name, report.results)

        self.assertEqual(len(report.results), len(expected_collectors))
        self.assertEqual(len(report.errors), 0)

    def test_collection_report_serialization(self):
        """Test that CollectionReport can be serialized to dict and JSON."""
        config = self.create_test_config()
        core = SnailCore(config)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                report = core.collect(collector_names=["system", "hardware"])

        # Test to_dict() method
        report_dict = report.to_dict()
        self.assertIsInstance(report_dict, dict)

        # Verify structure - should have meta, data, errors keys
        self.assertIn("meta", report_dict)
        self.assertIn("data", report_dict)
        self.assertIn("errors", report_dict)

        # Verify meta contains expected fields
        meta = report_dict["meta"]
        self.assertIn("hostname", meta)
        self.assertIn("host_id", meta)
        self.assertIn("collection_id", meta)
        self.assertIn("timestamp", meta)
        self.assertIn("snail_version", meta)

        # Verify data contains expected collectors
        data = report_dict["data"]
        self.assertIn("system", data)
        self.assertIn("hardware", data)

        # Verify errors is a list
        self.assertIsInstance(report_dict["errors"], list)

        # Test JSON serialization (should not raise)
        import json
        json_str = report.to_json()
        self.assertIsInstance(json_str, str)

        # Verify it can be parsed back
        parsed = json.loads(json_str)
        self.assertEqual(parsed["meta"]["hostname"], "test-host")
        self.assertEqual(parsed["meta"]["host_id"], "test-host-id-123")

    def _create_mock_collector(self, collector_cls, name):
        """Create a mock collector class that returns test data."""
        class MockCollector(collector_cls):
            def collect(self):
                return {
                    "collector": name,
                    "status": "success",
                    "test_data": f"data_from_{name}",
                    "items": ["item1", "item2"],
                }
        return MockCollector

    def _create_failing_mock_collector(self, collector_cls, name):
        """Create a mock collector class that raises an exception."""
        class FailingMockCollector(collector_cls):
            def collect(self):
                raise Exception("Test failure for collector integration testing")
        return FailingMockCollector


class TestCollectorFiltering(unittest.TestCase):
    """Integration tests for collector filtering functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up temporary directory."""
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def test_collector_names_filtering(self):
        """Test filtering collectors by specific names."""
        config = self.create_test_config()

        # Mock collectors
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        all_collectors = ["system", "hardware", "network", "packages",
                         "services", "filesystem", "security", "logs"]
        for name in all_collectors:
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect(collector_names=["system", "hardware", "network"])

        # Should only have results for specified collectors
        self.assertIn("system", report.results)
        self.assertIn("hardware", report.results)
        self.assertIn("network", report.results)

        # Should not have results for other collectors
        other_collectors = ["packages", "services", "filesystem", "security", "logs"]
        for collector_name in other_collectors:
            self.assertNotIn(collector_name, report.results)

        self.assertEqual(len(report.results), 3)
        self.assertEqual(len(report.errors), 0)

    def test_collector_subset_filtering(self):
        """Test filtering to a small subset of collectors."""
        config = self.create_test_config()

        # Mock collectors
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        all_collectors = ["system", "hardware", "network", "packages",
                         "services", "filesystem", "security", "logs"]
        for name in all_collectors:
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect(collector_names=["system"])

        # Should only have results for system collector
        self.assertIn("system", report.results)
        self.assertEqual(len(report.results), 1)

        # Should not have results for other collectors
        other_collectors = ["hardware", "network", "packages", "services", "filesystem", "security", "logs"]
        for collector_name in other_collectors:
            self.assertNotIn(collector_name, report.results)

        self.assertEqual(len(report.errors), 0)

    def test_mixed_valid_invalid_collector_names(self):
        """Test filtering with mix of valid and invalid collector names."""
        config = self.create_test_config()

        # Mock collectors
        from snail_core.collectors.base import BaseCollector
        mock_collectors = {}
        valid_collectors = ["system", "hardware", "network"]
        for name in valid_collectors:
            mock_collectors[name] = self._create_mock_collector(BaseCollector, name)

        # Mock host_id and hostname
        with patch("snail_core.core.get_host_id", return_value="test-host-id-123"):
            with patch("socket.gethostname", return_value="test-host"):
                with patch("snail_core.core.get_all_collectors", return_value=mock_collectors):
                    core = SnailCore(config)
                    report = core.collect(collector_names=["system", "invalid1", "hardware", "invalid2", "network"])

        # Should only have results for valid collectors
        self.assertIn("system", report.results)
        self.assertIn("hardware", report.results)
        self.assertIn("network", report.results)

        self.assertEqual(len(report.results), 3)
        self.assertEqual(len(report.errors), 0)

    def create_test_config(self):
        """Create a test configuration."""
        return Config(
            output_dir=str(self.temp_dir),
            upload_enabled=False,
            collection_timeout=30,
        )

    def _create_mock_collector(self, collector_cls, name):
        """Create a mock collector class that returns test data."""
        class MockCollector(collector_cls):
            def collect(self):
                return {
                    "collector": name,
                    "status": "success",
                    "test_data": f"data_from_{name}",
                }
        return MockCollector
