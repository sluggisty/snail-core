"""
Multi-distribution tests for APT-based package managers.

Tests PackagesCollector on Debian, Ubuntu, and other APT-based systems.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

from snail_core.collectors.packages import PackagesCollector


@pytest.mark.integration
class TestAptDistros(unittest.TestCase):
    """Test PackagesCollector on APT-based distributions."""

    def setUp(self):
        """Set up test collector."""
        self.collector = PackagesCollector()

    def test_debian_detection_uses_apt(self):
        """Test that Debian detection results in APT package manager."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "debian"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "apt")
            self.assertIn("repositories", result)
            self.assertIn("upgradeable", result)

    def test_ubuntu_detection_uses_apt(self):
        """Test that Ubuntu detection results in APT package manager."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "ubuntu"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            self.assertEqual(result["package_manager"], "apt")

    def test_apt_repository_listing(self):
        """Test APT repository listing functionality."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "ubuntu"}),
            patch.object(self.collector, "run_command") as mock_run,
            patch.object(
                self.collector,
                "read_file_lines",
                return_value=[
                    "deb http://archive.ubuntu.com/ubuntu focal main restricted",
                    "# deb http://archive.ubuntu.com/ubuntu focal universe",
                    "deb-src http://archive.ubuntu.com/ubuntu focal main",
                ],
            ),
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            repos = result["repositories"]
            self.assertIsInstance(repos, list)
            self.assertGreater(len(repos), 0)

            # Check repository structure
            repo = repos[0]
            self.assertIn("url", repo)
            self.assertIn("suite", repo)
            self.assertIn("components", repo)
            self.assertEqual(repo["url"], "http://archive.ubuntu.com/ubuntu")
            self.assertEqual(repo["suite"], "focal")

    def test_apt_package_listing(self):
        """Test APT package listing and summary."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "debian"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            summary = result["summary"]
            self.assertIn("total_count", summary)
            self.assertGreaterEqual(summary["total_count"], 0)

    def test_apt_upgradeable_packages(self):
        """Test APT upgradeable packages detection."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "ubuntu"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            upgradeable = result["upgradeable"]
            self.assertIsInstance(upgradeable, dict)

    def test_apt_config_parsing(self):
        """Test APT configuration parsing."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "debian"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            config = result["config"]
            self.assertIsInstance(config, dict)

    def test_apt_transaction_history(self):
        """Test APT transaction history parsing."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "ubuntu"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            transactions = result["recent_transactions"]
            self.assertIsInstance(transactions, list)

    def _mock_apt_commands(self):
        """Mock APT command outputs for testing."""
        call_count = 0

        def mock_command(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0] if args else []

            if not cmd:
                return ("", "", 1)

            if cmd[0] == "apt":
                if "list" in cmd and "--installed" in cmd:
                    return (
                        "Listing...\nlinux-image-5.15.0-25-generic/focal,focal,now 5.15.0-25.25 amd64 [installed]\nbash/focal,focal,now 5.0.17-1ubuntu1 amd64 [installed]\n",
                        "",
                        0,
                    )
                elif "list" in cmd and "--upgradable" in cmd:
                    return (
                        "Listing...\nlinux-image-5.15.0-26-generic/focal 5.15.0-26.26 amd64 [upgradable from: 5.15.0-25.25]\n",
                        "",
                        0,
                    )
                elif "show" in cmd:
                    return ("Package: bash\nVersion: 5.0.17-1ubuntu1\n", "", 0)
            elif cmd[0] == "dpkg":
                if "--list" in cmd:
                    return (
                        "ii  linux-image-5.15.0-25-generic  5.15.0-25.25  amd64  Signed kernel image generic\nii  bash                           5.0.17-1ubuntu1 amd64  GNU Bourne Again SHell\n",
                        "",
                        0,
                    )
                elif "--get-selections" in cmd:
                    return ("bash\t\t\tinstall\nlinux-image-generic\t\tinstall\n", "", 0)
            elif cmd[0] == "grep" and "sources.list" in " ".join(cmd):
                return (
                    "deb http://archive.ubuntu.com/ubuntu focal main restricted\n# deb http://archive.ubuntu.com/ubuntu focal universe\n",
                    "",
                    0,
                )
            elif cmd[0] == "apt-config":
                if "dump" in cmd:
                    return ('APT::Architecture "amd64";\nAPT::Install-Recommends "1";\n', "", 0)
            elif cmd[0] == "cat" and "/var/log/apt/history.log" in " ".join(cmd):
                return (
                    "Start-Date: 2024-01-01 10:00:00\nCommandline: apt install vim\nInstall: vim:amd64 (2:8.1.2269-1ubuntu5)\nEnd-Date: 2024-01-01 10:00:15\n",
                    "",
                    0,
                )

            return ("", "", 1)  # Command not found

        return mock_command
