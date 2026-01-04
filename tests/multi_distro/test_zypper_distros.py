"""
Multi-distribution tests for Zypper-based package managers.

Tests PackagesCollector on SUSE, openSUSE, and other Zypper-based systems.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from snail_core.collectors.packages import PackagesCollector
import pytest


@pytest.mark.integration


class TestZypperDistros(unittest.TestCase):
    """Test PackagesCollector on Zypper-based distributions."""

    def setUp(self):
        """Set up test collector."""
        self.collector = PackagesCollector()

    def test_suse_detection_uses_zypper(self):
        """Test that SUSE detection results in Zypper package manager."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "sles"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "zypper")
            self.assertIn("repositories", result)
            self.assertIn("upgradeable", result)

    def test_opensuse_detection_uses_zypper(self):
        """Test that openSUSE detection results in Zypper package manager."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "opensuse-leap"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "zypper")

    def test_zypper_repository_listing(self):
        """Test Zypper repository listing functionality."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "opensuse"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            repos = result["repositories"]
            self.assertIsInstance(repos, list)
            self.assertGreater(len(repos), 0)

            # Check repository structure
            repo = repos[0]
            self.assertIn("id", repo)
            self.assertIn("name", repo)
            self.assertIn("enabled", repo)

    def test_zypper_package_listing(self):
        """Test Zypper package listing and summary."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "sles"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            summary = result["summary"]
            self.assertIn("total_count", summary)
            self.assertGreater(summary["total_count"], 0)

    def test_zypper_upgradeable_packages(self):
        """Test Zypper upgradeable packages detection."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "opensuse-leap"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            upgradeable = result["upgradeable"]
            self.assertIsInstance(upgradeable, dict)

    def test_zypper_config_parsing(self):
        """Test Zypper configuration parsing."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "sles"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            config = result["config"]
            self.assertIsInstance(config, dict)

    def test_zypper_transaction_history(self):
        """Test Zypper transaction history parsing."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "opensuse"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_zypper_commands()

            result = self.collector.collect()

            transactions = result["recent_transactions"]
            self.assertIsInstance(transactions, list)

    def _mock_zypper_commands(self):
        """Mock Zypper command outputs for testing."""
        call_count = 0

        def mock_command(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0] if args else []

            if not cmd:
                return ("", "", 1)

            if cmd[0] == "zypper":
                if "repos" in cmd or "lr" in cmd:
                    return ("# repo-oss\nURI: http://download.opensuse.org/distribution/leap/15.4/repo/oss/\nName: Main Repository\nEnabled: Yes\n# repo-update\nURI: http://download.opensuse.org/update/leap/15.4/oss/\nName: Main Update Repository\nEnabled: Yes\n", "", 0)
                elif "packages" in cmd or "pa" in cmd:
                    return ("S | Name           | Type    | Version     | Arch   | Repository\ni | kernel-default | package | 5.14.21-150400.24.11 | x86_64 | repo-update\ni | bash           | package | 5.1.16-6.1          | x86_64 | repo-oss\n", "", 0)
                elif "list-updates" in cmd or "lu" in cmd:
                    return ("Loading repository data...\nReading installed packages...\n\nNo updates found.\n", "", 0)
                elif "history" in cmd:
                    return ("ID | Date       | Action | Login | Name\n1  | 2024-01-01 | install | root  | vim\n", "", 0)
            elif cmd[0] == "rpm":
                if "-qa" in cmd:
                    return ("kernel-default-5.14.21-150400.24.11.x86_64\nbash-5.1.16-6.1.x86_64\n", "", 0)

            return ("", "", 1)  # Command not found

        return mock_command
