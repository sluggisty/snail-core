"""
Multi-distribution tests for DNF-based package managers.

Tests PackagesCollector on Fedora, RHEL 8+, CentOS Stream, and other DNF-based systems.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from snail_core.collectors.packages import PackagesCollector
import pytest


@pytest.mark.integration
class TestDnfDistros(unittest.TestCase):
    """Test PackagesCollector on DNF-based distributions."""

    def setUp(self):
        """Set up test collector."""
        self.collector = PackagesCollector()

    def test_fedora_detection_uses_dnf(self):
        """Test that Fedora detection results in DNF package manager."""
        with (
            patch.object(
                self.collector, "detect_distro", return_value={"id": "fedora", "version": "39"}
            ),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            # Mock DNF availability
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "dnf")
            self.assertIn("repositories", result)
            self.assertIn("upgradeable", result)
            self.assertIn("summary", result)

    def test_rhel_8_detection_uses_dnf(self):
        """Test that RHEL 8+ detection results in DNF package manager."""
        with (
            patch.object(
                self.collector, "detect_distro", return_value={"id": "rhel", "version": "9.0"}
            ),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "dnf")

    def test_centos_stream_detection_uses_dnf(self):
        """Test that CentOS Stream detection results in DNF package manager."""
        with (
            patch.object(
                self.collector, "detect_distro", return_value={"id": "centos", "version": "9"}
            ),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "dnf")

    def test_dnf_repository_listing(self):
        """Test DNF repository listing functionality."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "fedora"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            repos = result["repositories"]
            self.assertIsInstance(repos, list)
            self.assertGreater(len(repos), 0)

            # Check repository structure
            repo = repos[0]
            self.assertIn("id", repo)
            self.assertIn("name", repo)
            self.assertIn("enabled", repo)

    def test_dnf_package_listing(self):
        """Test DNF package listing and summary."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "fedora"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            summary = result["summary"]
            self.assertIn("total_count", summary)
            self.assertGreater(summary["total_count"], 0)

    def test_dnf_upgradeable_packages(self):
        """Test DNF upgradeable packages detection."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "fedora"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            upgradeable = result["upgradeable"]
            self.assertIsInstance(upgradeable, dict)
            # May be empty if no upgrades available
            self.assertIsInstance(upgradeable.get("count", 0), int)

    def test_dnf_config_parsing(self):
        """Test DNF configuration parsing."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "fedora"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            config = result["config"]
            self.assertIsInstance(config, dict)
            # Should contain some DNF config options
            self.assertGreater(len(config), 0)

    def test_dnf_transaction_history(self):
        """Test DNF transaction history parsing."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "fedora"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            transactions = result["recent_transactions"]
            self.assertIsInstance(transactions, list)
            # May be empty if no recent transactions

    def test_fallback_to_yum_when_dnf_unavailable(self):
        """Test fallback to YUM when DNF is not available on RPM-based system."""
        with (
            patch.object(
                self.collector, "detect_distro", return_value={"id": "rhel", "version": "7"}
            ),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            # Mock YUM available but DNF not available
            call_count = 0

            def mock_commands(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if args[0][0] == "dnf":
                    return ("", "", 1)  # DNF not available
                elif args[0][0] == "yum":
                    return ("", "", 0)  # YUM available
                else:
                    return self._get_mock_command_output(args[0])

            mock_run.side_effect = mock_commands

            result = self.collector.collect()

            # Should still work with YUM
            self.assertIn("package_manager", result)
            self.assertIn("repositories", result)

    def _mock_dnf_commands(self):
        """Mock DNF command outputs for testing."""
        call_count = 0

        def mock_command(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0] if args else []

            if not cmd:
                return ("", "", 1)

            if cmd[0] == "dnf":
                if "--version" in cmd:
                    return ("dnf version 4.14.0", "", 0)
                elif "repolist" in cmd:
                    return (
                        "repo id                           repo name\nfedora                            Fedora 39 - x86_64\nupdates                           Fedora 39 - x86_64 - Updates\n",
                        "",
                        0,
                    )
                elif "list" in cmd and "installed" in cmd:
                    return (
                        "Installed Packages\nkernel.x86_64    6.5.6-300.fc39     @updates\nbash.x86_64      5.2.15-3.fc39      @fedora\n",
                        "",
                        0,
                    )
                elif "check-update" in cmd:
                    return ("", "", 0)  # No updates available
                elif "config-manager" in cmd:
                    return ("[main]\ngpgcheck=1\ninstallonly_limit=3\n", "", 0)
                elif "history" in cmd:
                    return (
                        "ID     | Command line             | Date and time    | Action(s)      | Altered\n1      | install bash            | 2024-01-01 10:00 | Install        | 1\n",
                        "",
                        0,
                    )
            elif cmd[0] == "rpm":
                if "-qa" in cmd:
                    return ("kernel-6.5.6-300.fc39.x86_64\nbash-5.2.15-3.fc39.x86_64\n", "", 0)
            elif cmd[0] == "yum":
                return ("", "", 1)  # YUM not available

            return ("", "", 1)  # Command not found

        return mock_command

    def _get_mock_command_output(self, cmd):
        """Get mock output for various commands."""
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)

        if "rpm -qa" in cmd_str:
            return ("kernel-6.5.6-300.fc39.x86_64\nbash-5.2.15-3.fc39.x86_64\n", "", 0)
        elif "dnf repolist" in cmd_str:
            return (
                "repo id                           repo name\nfedora                            Fedora 39 - x86_64\n",
                "",
                0,
            )

        return ("", "", 1)
