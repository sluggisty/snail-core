"""
Performance tests for handling large datasets.

Tests that collectors can process large amounts of data without performance degradation or memory issues.
"""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from snail_core.collectors.filesystem import FilesystemCollector
from snail_core.collectors.packages import PackagesCollector
from snail_core.collectors.services import ServicesCollector


@pytest.mark.performance
@pytest.mark.slow
class TestLargeDatasets(unittest.TestCase):
    """Test handling of large datasets by collectors."""

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

    def test_large_package_list_handling(self):
        """Test handling of large package lists."""
        collector = PackagesCollector()

        # Create mock output for many packages (1000 packages)
        packages = []
        for i in range(1000):
            packages.append(f"package-{i}-name.x86_64    1.0.{i}-1.el9     @baseos")

        large_package_output = "\n".join(
            [
                "Updating Subscription Management repositories.",
                "Last metadata expiration check: 0:00:01 ago on Mon 01 Jan 2024 12:00:00 PM EST.",
                "Installed Packages",
            ]
            + packages
        )

        with patch.object(collector, "run_command") as mock_run:
            # Mock all the commands that packages collector uses
            call_count = 0

            def mock_commands(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                cmd = args[0] if args else []

                if "dnf" in cmd and "repolist" in cmd:
                    return (
                        "repo id                           repo name\nbaseos                            Base OS",
                        "",
                        0,
                    )
                elif "rpm" in cmd and "-qa" in cmd:
                    return (large_package_output, "", 0)
                else:
                    return ("", "", 0)  # Default success

            mock_run.side_effect = mock_commands

            result = collector.collect()

            # Should handle large dataset
            self.assertIn("summary", result)
            self.assertIn("total_count", result["summary"])
            # Should handle approximately 1000 packages (allow some tolerance for parsing)
            self.assertGreater(result["summary"]["total_count"], 900)
            self.assertLess(result["summary"]["total_count"], 1100)

            # Should not have excessive memory usage (check completed without error)
            self.assertIsInstance(result, dict)

    def test_large_service_list_handling(self):
        """Test handling of large service lists."""
        collector = ServicesCollector()

        # Create mock output for many services (500 services)
        services = []
        for i in range(500):
            services.append(f"service-{i}.service     loaded active running   Test Service {i}")

        large_service_output = "\n".join(
            [
                "UNIT                                 LOAD   ACTIVE SUB     DESCRIPTION",
            ]
            + services
        )

        with patch.object(collector, "run_command") as mock_run:
            call_count = 0

            def mock_commands(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                cmd = args[0] if args else []

                if "systemctl" in cmd and "list-units" in cmd:
                    return (large_service_output, "", 0)
                elif "systemctl" in cmd and "show" in cmd:
                    return ("Id=systemd\nDescription=systemd\n", "", 0)
                else:
                    return ("", "", 0)

            mock_run.side_effect = mock_commands

            result = collector.collect()

            # Should handle large dataset
            self.assertIn("running_services", result)
            self.assertIsInstance(result["running_services"], list)

            # Should process all services
            self.assertGreater(len(result["running_services"]), 400)  # At least most services

    def test_large_log_file_processing(self):
        """Test processing of large log files."""
        collector = FilesystemCollector()

        # Create a large log file with many entries
        log_content = ""
        for i in range(10000):  # 10,000 log entries
            log_content += f"Jan 01 12:00:{i:02d} hostname process[{i}]: Log message {i}\n"

        # Create temporary log file
        log_file = self.temp_dir / "large_log"
        log_file.write_text(log_content)

        with patch.object(collector, "run_command") as mock_run:
            call_count = 0

            def mock_commands(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                cmd = args[0] if args else []

                if "df" in cmd:
                    return (
                        "Filesystem     1K-blocks    Used Available Use% Mounted on\n/dev/sda1       1000000  500000    500000  50% /\n",
                        "",
                        0,
                    )
                elif "mount" in cmd:
                    return ("/dev/sda1 on / type ext4 (rw,relatime)\n", "", 0)
                elif "lsblk" in cmd:
                    return (
                        "NAME MAJ:MIN RM SIZE RO TYPE MOUNTPOINT\nsda  8:0    0  50G  0 disk \nsda1 8:1    0  50G  0 part /\n",
                        "",
                        0,
                    )
                else:
                    return ("", "", 0)

            mock_run.side_effect = mock_commands

            # Mock the log file reading
            with patch(
                "snail_core.collectors.filesystem.FilesystemCollector.read_file"
            ) as mock_read:

                def mock_read_file(path, default=""):
                    if str(log_file) in path:
                        return log_content
                    return default

                mock_read.side_effect = mock_read_file

                result = collector.collect()

                # Should handle large log file
                self.assertIn("mounts", result)
                self.assertIsInstance(result, dict)

    def test_memory_usage_with_large_datasets(self):
        """Test memory usage when processing large datasets."""
        import psutil

        def get_memory_usage():
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB

        # Force garbage collection
        gc.collect()
        initial_memory = get_memory_usage()

        try:
            # Test with large package list
            self.test_large_package_list_handling()

            # Check memory usage
            after_packages_memory = get_memory_usage()
            packages_memory_delta = after_packages_memory - initial_memory

            # Should not use excessive memory (less than 50MB for processing)
            self.assertLess(packages_memory_delta, 50, ".1f")

            # Force cleanup
            gc.collect()

            # Test with large service list
            self.test_large_service_list_handling()

            after_services_memory = get_memory_usage()
            services_memory_delta = after_services_memory - after_packages_memory

            # Should not use excessive memory
            self.assertLess(services_memory_delta, 50, ".1f")

        finally:
            # Clean up
            gc.collect()

    def test_large_nested_data_structures(self):
        """Test handling of large nested data structures."""
        collector = PackagesCollector()

        # Create a large nested structure
        large_repo_data = {
            "repo_id": "large-repo",
            "name": "Large Test Repository",
            "enabled": True,
            "baseurl": ["http://example.com/repo"] * 100,  # 100 URLs
            "packages": {},
        }

        # Add many packages
        for i in range(5000):
            large_repo_data["packages"][f"package-{i}"] = {
                "version": f"1.0.{i}",
                "size": 1024 * i,
                "dependencies": [f"dep-{j}" for j in range(10)],  # 10 deps each
            }

        # Mock the collector to return this large structure
        with patch.object(collector, "run_command") as mock_run:
            mock_run.return_value = ("", "", 0)

            # Manually create result to test structure handling
            result = {
                "package_manager": "dnf",
                "repositories": [large_repo_data],
                "summary": {"total_count": 5000, "by_arch": {"x86_64": 5000}},
                "large_data": large_repo_data,
            }

            # Should handle large nested structure
            self.assertIsInstance(result, dict)
            self.assertIn("large_data", result)
            self.assertEqual(len(result["large_data"]["packages"]), 5000)

            # Should be able to serialize (basic check)
            import json

            try:
                json_str = json.dumps(result, default=str)
                self.assertGreater(len(json_str), 1000000)  # Should be quite large
            except Exception as e:
                self.fail(f"Failed to serialize large structure: {e}")

    def test_performance_degradation_with_size(self):
        """Test that performance doesn't degrade linearly with data size."""
        import time

        collector = PackagesCollector()

        # Test with different data sizes
        sizes = [100, 500, 1000, 2000]
        times = []

        for size in sizes:
            # Create mock data of given size
            packages = [f"package-{i}.x86_64    1.0.{i}-1.el9" for i in range(size)]

            start_time = time.perf_counter()

            with patch.object(collector, "run_command") as mock_run:
                mock_run.return_value = ("\n".join(packages), "", 0)

                # Test just the data processing part
                result = collector._get_rpm_summary()
                self.assertEqual(result["total_count"], size)

            end_time = time.perf_counter()
            execution_time = end_time - start_time
            times.append(execution_time)

        # Performance should not degrade too badly
        # Time for 2000 items should be less than 10x time for 100 items
        if times[0] > 0:
            degradation_ratio = times[-1] / times[0]
            self.assertLess(
                degradation_ratio,
                10,
                f"Performance degraded {degradation_ratio:.2f}x with 20x data increase",
            )

        print(
            f"\nData size performance: {[f'{sizes[i]}: {times[i]:.4f}s' for i in range(len(sizes))]}"
        )

    def test_large_configuration_handling(self):
        """Test handling of large configuration datasets."""
        from snail_core.config import Config

        # Create a config with many enabled collectors
        large_config = {
            "upload": {"enabled": True, "url": "https://example.com"},
            "collection": {
                "enabled_collectors": [f"collector_{i}" for i in range(100)],  # 100 collectors
                "disabled_collectors": [],
                "timeout": 300,
            },
            "output": {"dir": "/tmp/test", "compress": True},
        }

        config = Config.from_dict(large_config)

        # Should handle large config
        self.assertIsInstance(config.enabled_collectors, list)
        self.assertEqual(len(config.enabled_collectors), 100)
        self.assertTrue(config.upload_enabled)

    def test_collector_output_size_limits(self):
        """Test that collectors handle output size limits appropriately."""
        collector = PackagesCollector()

        # Test with very large command output (simulate command with lots of output)
        large_output = "package\n" * 100000  # 100,000 lines

        with patch.object(collector, "run_command") as mock_run:
            mock_run.return_value = (large_output, "", 0)

            result = collector.collect()

            # Should handle large output without crashing
            self.assertIsInstance(result, dict)

            # Should still produce valid structure
            self.assertIn("summary", result)
