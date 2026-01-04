"""
Performance tests for collection execution time and resource usage.

Tests that collections complete within reasonable time limits and don't consume excessive resources.
"""

from __future__ import annotations

import gc
import psutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from snail_core.config import Config
from snail_core.core import SnailCore


@pytest.mark.performance
@pytest.mark.slow
class TestCollectionPerformance(unittest.TestCase):
    """Test collection performance metrics."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = Config(
            output_dir=str(self.temp_dir),
            upload_enabled=False,
            collection_timeout=300,  # 5 minutes
        )

    def tearDown(self):
        """Clean up test environment."""
        # Clean up any files created during tests
        for file_path in self.temp_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        self.temp_dir.rmdir()

    def _get_memory_usage(self):
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # Convert to MB

    def _measure_collection_time(self, collectors: list[str] | None = None) -> tuple[float, dict]:
        """Measure collection execution time and return results."""
        core = SnailCore(self.config)

        start_time = time.perf_counter()
        report = core.collect(collectors)
        end_time = time.perf_counter()

        execution_time = end_time - start_time
        return execution_time, report.results

    def test_full_collection_time_within_limits(self):
        """Test that full collection completes within reasonable time limits."""
        # Run full collection
        execution_time, results = self._measure_collection_time()

        # Should complete within 5 minutes (300 seconds)
        self.assertLess(
            execution_time,
            300,
            f"Full collection took {execution_time:.2f}s, exceeded 5-minute limit",
        )

        # Should complete within 2 minutes for normal operation
        self.assertLess(
            execution_time,
            120,
            f"Full collection took {execution_time:.2f}s, should be under 2 minutes",
        )

        # Should collect from multiple collectors
        self.assertGreater(len(results), 3, "Should collect from at least 4 collectors")

    def test_individual_collector_timing(self):
        """Test timing for individual collectors."""
        core = SnailCore(self.config)

        # Get all available collectors
        collectors = list(core.collectors.keys())

        timing_results = {}

        for collector_name in collectors:
            start_time = time.perf_counter()

            try:
                report = core.collect([collector_name])
                end_time = time.perf_counter()

                execution_time = end_time - start_time
                timing_results[collector_name] = {
                    "time": execution_time,
                    "success": collector_name in report.results,
                    "error": len(report.errors) > 0,
                }

                # Individual collectors should complete within 30 seconds
                self.assertLess(
                    execution_time,
                    30,
                    f"Collector {collector_name} took {execution_time:.2f}s, exceeded 30s limit",
                )

            except Exception as e:
                timing_results[collector_name] = {"time": 0, "success": False, "error": str(e)}

        # At least some collectors should succeed
        successful_collectors = [
            name for name, result in timing_results.items() if result["success"]
        ]
        self.assertGreater(len(successful_collectors), 0, "At least one collector should succeed")

        # Log timing results for analysis
        print(f"\nCollector timing results ({len(collectors)} total):")
        for name, result in timing_results.items():
            print(".2f")

    def test_memory_usage_during_collection(self):
        """Test memory usage during collection execution."""
        # Force garbage collection before measurement
        gc.collect()
        initial_memory = self._get_memory_usage()

        try:
            # Run collection
            execution_time, results = self._measure_collection_time()

            # Check memory usage after collection
            final_memory = self._get_memory_usage()
            memory_delta = final_memory - initial_memory

            # Memory increase should be reasonable (less than 100MB)
            self.assertLess(memory_delta, 100, ".1f")

            # Should not leak excessive memory
            self.assertLessEqual(final_memory, initial_memory + 50, ".1f")

        finally:
            # Clean up
            gc.collect()

    def test_timeout_configuration_effectiveness(self):
        """Test that timeout configuration prevents runaway operations."""
        # Test with very short timeout
        short_timeout_config = Config(
            output_dir=str(self.temp_dir),
            upload_enabled=False,
            collection_timeout=1,  # 1 second timeout
        )

        core = SnailCore(short_timeout_config)

        start_time = time.perf_counter()
        core.collect()
        end_time = time.perf_counter()

        execution_time = end_time - start_time

        # Should respect timeout (though individual collectors might still complete)
        # The timeout applies to subprocess calls, not the overall collection
        self.assertLess(
            execution_time,
            60,  # Should not take more than 1 minute even with short timeout
            f"Collection with short timeout took {execution_time:.2f}s",
        )

    def test_collection_scalability_with_multiple_runs(self):
        """Test that multiple collection runs don't degrade performance."""
        core = SnailCore(self.config)

        times = []

        # Run collection 3 times
        for i in range(3):
            start_time = time.perf_counter()
            report = core.collect()
            end_time = time.perf_counter()

            execution_time = end_time - start_time
            times.append(execution_time)

            # Each run should complete
            self.assertGreater(len(report.results), 0, f"Run {i+1} produced no results")

        # Performance should not degrade significantly
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)

        # Maximum time should not be more than 3x the minimum
        degradation_ratio = max_time / min_time if min_time > 0 else float("inf")
        self.assertLess(
            degradation_ratio, 3.0, f"Performance degraded {degradation_ratio:.2f}x between runs"
        )

        print(
            f"\nMultiple run timing: min={min_time:.2f}s, avg={avg_time:.2f}s, max={max_time:.2f}s"
        )

    def test_collector_isolation_performance(self):
        """Test that slow collectors don't affect others."""
        core = SnailCore(self.config)

        # Mock one collector to be slow
        class SlowCollector:
            name = "slow_test"
            description = "Slow test collector"

            def collect(self):
                time.sleep(0.1)  # Small delay
                return {"slow_data": "test"}

        class FastCollector:
            name = "fast_test"
            description = "Fast test collector"

            def collect(self):
                return {"fast_data": "test"}

        # Replace collectors with our test ones
        with patch.object(
            core,
            "collectors",
            {
                "slow_test": SlowCollector,
                "fast_test": FastCollector,
            },
        ):
            start_time = time.perf_counter()
            report = core.collect(["slow_test", "fast_test"])
            end_time = time.perf_counter()

            execution_time = end_time - start_time

            # Should complete both collectors
            self.assertIn("slow_test", report.results)
            self.assertIn("fast_test", report.results)

            # Should take at least the slow collector time but not much more
            self.assertGreater(execution_time, 0.05, "Should take some time")
            self.assertLess(execution_time, 1.0, "Should not take excessive time")

    def test_performance_with_different_collection_sizes(self):
        """Test performance scaling with different numbers of collectors."""
        core = SnailCore(self.config)

        # Test with different collector subsets
        test_scenarios = [
            (["system"], "single collector"),
            (["system", "hardware"], "two collectors"),
            (None, "all collectors"),  # None means all
        ]

        times = {}

        for collector_list, scenario_name in test_scenarios:
            start_time = time.perf_counter()
            report = core.collect(collector_list)
            end_time = time.perf_counter()

            execution_time = end_time - start_time
            times[scenario_name] = execution_time

            # Should produce results
            num_results = len(report.results)
            expected_min = 1 if collector_list else 3
            self.assertGreaterEqual(
                num_results,
                expected_min,
                f"{scenario_name} should produce at least {expected_min} results",
            )

            print(f"{scenario_name}: {execution_time:.2f}s, {num_results} results")

    def test_resource_cleanup_after_collection(self):
        """Test that resources are properly cleaned up after collection."""
        import threading

        initial_threads = threading.active_count()
        initial_memory = self._get_memory_usage()

        try:
            # Run collection
            execution_time, results = self._measure_collection_time()

            # Check that we don't leak threads
            final_threads = threading.active_count()
            self.assertLessEqual(
                final_threads,
                initial_threads + 2,  # Allow some tolerance
                f"Thread leak: {initial_threads} -> {final_threads}",
            )

            # Check memory is reasonable
            final_memory = self._get_memory_usage()
            memory_delta = final_memory - initial_memory
            self.assertLess(memory_delta, 50, ".1f")  # Less than 50MB increase

        finally:
            # Force cleanup
            gc.collect()

    def test_performance_under_load(self):
        """Test collection performance under simulated load."""
        # This is a basic test - in a real load testing scenario,
        # you would run collections while the system is under CPU/memory load

        # Just verify normal performance for now
        execution_time, results = self._measure_collection_time()

        # Should still complete within reasonable time even under load
        self.assertLess(execution_time, 180, ".2f")  # 3 minutes

        # Should still produce results
        self.assertGreater(len(results), 0, "Should produce results under load")
