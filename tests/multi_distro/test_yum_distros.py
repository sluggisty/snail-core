"""
Multi-distribution tests for YUM-based package managers.

Tests PackagesCollector on RHEL 7, CentOS 7, and other YUM-based systems.
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from snail_core.collectors.packages import PackagesCollector


class TestYumDistros(unittest.TestCase):
    """Test PackagesCollector on YUM-based distributions."""

    def setUp(self):
        """Set up test collector."""
        self.collector = PackagesCollector()

    def test_rhel_7_detection_uses_yum(self):
        """Test that RHEL 7 detection results in YUM package manager."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "rhel", "version": "7.9"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "yum")
            self.assertIn("repositories", result)
            self.assertIn("upgradeable", result)

    def test_centos_7_detection_uses_yum(self):
        """Test that CentOS 7 detection results in YUM package manager."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "centos", "version": "7.9"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "yum")

    def test_yum_repository_listing(self):
        """Test YUM repository listing functionality."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "rhel", "version": "7"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            repos = result["repositories"]
            self.assertIsInstance(repos, list)
            self.assertGreater(len(repos), 0)

            # Check repository structure
            repo = repos[0]
            self.assertIn("id", repo)
            self.assertIn("name", repo)
            self.assertIn("enabled", repo)

    def test_yum_package_listing(self):
        """Test YUM package listing and summary."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "centos", "version": "7"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            summary = result["summary"]
            self.assertIn("total_count", summary)
            self.assertGreater(summary["total_count"], 0)

    def test_yum_upgradeable_packages(self):
        """Test YUM upgradeable packages detection."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "rhel", "version": "7"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            upgradeable = result["upgradeable"]
            self.assertIsInstance(upgradeable, dict)

    def test_yum_config_parsing(self):
        """Test YUM configuration parsing."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "centos", "version": "7"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            config = result["config"]
            self.assertIsInstance(config, dict)

    def test_yum_transaction_history(self):
        """Test YUM transaction history parsing."""
        with patch.object(self.collector, "detect_distro", return_value={"id": "rhel", "version": "7"}), \
             patch.object(self.collector, "run_command") as mock_run:

            mock_run.side_effect = self._mock_yum_commands()

            result = self.collector.collect()

            transactions = result["recent_transactions"]
            self.assertIsInstance(transactions, list)

    def _mock_yum_commands(self):
        """Mock YUM command outputs for testing."""
        call_count = 0

        def mock_command(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0] if args else []

            if not cmd:
                return ("", "", 1)

            if cmd[0] == "yum":
                if "--version" in cmd:
                    return ("3.4.3", "", 0)
                elif "repolist" in cmd:
                    return ("repo id                             repo name                            status\nrhel-7-server-rpms                  Red Hat Enterprise Linux 7 Server     enabled\nrhel-7-server-optional-rpms          Red Hat Enterprise Linux 7 Server     enabled\n", "", 0)
                elif "list" in cmd and "installed" in cmd:
                    return ("Installed Packages\nkernel.x86_64    3.10.0-1160.el7     @rhel-7-server-rpms\nbash.x86_64      4.2.46-34.el7       @rhel-7-server-rpms\n", "", 0)
                elif "check-update" in cmd:
                    return ("", "", 0)  # No updates available
                elif "history" in cmd:
                    return ("ID     | Login user               | Date and time    | Action(s)      | Altered\n1      | root <root>              | 2024-01-01 10:00 | Install        | 1\n", "", 0)
            elif cmd[0] == "dnf":
                return ("", "", 1)  # DNF not available
            elif cmd[0] == "rpm":
                if "-qa" in cmd:
                    return ("kernel-3.10.0-1160.el7.x86_64\nbash-4.2.46-34.el7.x86_64\n", "", 0)

            return ("", "", 1)  # Command not found

        return mock_command
