"""
Multi-distribution tests for package manager fallback and edge cases.

Tests auto-detection and fallback behavior when standard detection fails.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from snail_core.collectors.packages import PackagesCollector
import pytest


@pytest.mark.integration
class TestPackageManagerFallback(unittest.TestCase):
    """Test package manager fallback and auto-detection."""

    def setUp(self):
        """Set up test collector."""
        self.collector = PackagesCollector()

    def test_unknown_distribution_fallback(self):
        """Test fallback behavior for unknown distributions."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "unknown-distro"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            # Mock some basic commands that might be available
            mock_run.side_effect = lambda *args, **kwargs: ("", "", 1)  # All commands fail

            result = self.collector.collect()

            # Should still return a result, even if minimal
            self.assertIsInstance(result, dict)
            self.assertIn("package_manager", result)

    def test_auto_detection_with_multiple_package_managers(self):
        """Test auto-detection when multiple package managers are available."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "unknown"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            call_log = []

            def mock_command(*args, **kwargs):
                call_log.append(args[0] if args else [])
                cmd = args[0] if args else []

                if not cmd:
                    return ("", "", 1)

                # Simulate all package managers being available
                if cmd[0] in ["dnf", "yum", "apt", "zypper"]:
                    if "--version" in cmd:
                        return (f"{cmd[0]} version 1.0", "", 0)
                    elif cmd[0] == "dnf" and "repolist" in cmd:
                        return ("repo id    repo name\nfedora     Fedora\n", "", 0)
                elif cmd[0] == "rpm" and "-qa" in cmd:
                    return ("package1\npackage2\n", "", 0)

                return ("", "", 1)

            mock_run.side_effect = mock_command

            result = self.collector.collect()

            # Should detect and use a package manager
            self.assertIn("package_manager", result)
            self.assertIn(result["package_manager"], ["dnf", "yum", "apt", "zypper"])

    def test_rpm_fallback_when_no_specific_manager(self):
        """Test fallback to basic RPM when no specific package manager is available."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "fedora"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):

            def mock_command(*args, **kwargs):
                cmd = args[0] if args else []

                if not cmd:
                    return ("", "", 1)

                # DNF and YUM not available, but RPM is
                if cmd[0] in ["dnf", "yum"]:
                    if "--version" in cmd:
                        return ("", "", 1)  # Not available
                elif cmd[0] == "rpm":
                    if "-qa" in cmd:
                        return ("kernel-1.0\nbash-2.0\n", "", 0)

                return ("", "", 1)

            mock_run.side_effect = mock_command

            result = self.collector.collect()

            # Should still work with basic RPM
            self.assertEqual(result["package_manager"], "rpm")
            self.assertIn("summary", result)
            self.assertIn("kernel_packages", result)

    def test_distribution_like_detection(self):
        """Test distribution detection using 'like' field."""
        with (
            patch.object(
                self.collector, "detect_distro", return_value={"id": "custom", "like": "fedora"}
            ),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_dnf_commands()

            result = self.collector.collect()

            # Should detect as RPM-based due to "like": "fedora"
            self.assertEqual(result["package_manager"], "dnf")

    def test_distribution_like_debian_detection(self):
        """Test Debian-like distribution detection."""
        with (
            patch.object(
                self.collector, "detect_distro", return_value={"id": "custom", "like": "debian"}
            ),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            mock_run.side_effect = self._mock_apt_commands()

            result = self.collector.collect()

            # Should detect as APT-based due to "like": "debian"
            self.assertEqual(result["package_manager"], "apt")

    def test_all_package_managers_unavailable(self):
        """Test behavior when no package managers are available."""
        with (
            patch.object(self.collector, "detect_distro", return_value={"id": "minimal"}),
            patch.object(self.collector, "run_command") as mock_run,
        ):
            # All commands fail
            mock_run.return_value = ("", "", 1)

            result = self.collector.collect()

            # Should still return a result structure
            self.assertIsInstance(result, dict)
            self.assertIn("package_manager", result)

    def test_mixed_case_distribution_ids(self):
        """Test that distribution ID matching is case-insensitive."""
        test_cases = [
            ({"id": "FEDORA"}, "dnf"),
            ({"id": "RHEL", "version": "9"}, "dnf"),
            ({"id": "Debian"}, "apt"),
            ({"id": "UBUNTU"}, "apt"),
            ({"id": "SLES"}, "zypper"),
            ({"id": "openSUSE"}, "zypper"),
        ]

        for distro_info, expected_manager in test_cases:
            with self.subTest(distro=distro_info["id"]):
                with (
                    patch.object(self.collector, "detect_distro", return_value=distro_info),
                    patch.object(self.collector, "run_command") as mock_run,
                ):
                    if expected_manager == "dnf":
                        mock_run.side_effect = self._mock_dnf_commands()
                    elif expected_manager == "apt":
                        mock_run.side_effect = self._mock_apt_commands()
                    elif expected_manager == "zypper":
                        mock_run.side_effect = self._mock_zypper_commands()

                    result = self.collector.collect()

                    self.assertEqual(result["package_manager"], expected_manager)

    def _mock_dnf_commands(self):
        """Mock DNF commands for fallback testing."""

        def mock_command(*args, **kwargs):
            cmd = args[0] if args else []
            if not cmd:
                return ("", "", 1)

            if cmd[0] == "dnf" and "--version" in cmd:
                return ("dnf version 4.0", "", 0)
            elif cmd[0] == "dnf" and "repolist" in cmd:
                return ("repo id    repo name\nfedora    Fedora\n", "", 0)
            elif cmd[0] == "rpm" and "-qa" in cmd:
                return ("kernel-1.0\nbash-2.0\n", "", 0)

            return ("", "", 1)

        return mock_command

    def _mock_apt_commands(self):
        """Mock APT commands for fallback testing."""

        def mock_command(*args, **kwargs):
            cmd = args[0] if args else []
            if not cmd:
                return ("", "", 1)

            if cmd[0] == "dpkg" and "--list" in cmd:
                return ("ii  bash    5.0    amd64    GNU Bourne Again SHell\n", "", 0)

            return ("", "", 1)

        return mock_command

    def _mock_zypper_commands(self):
        """Mock Zypper commands for fallback testing."""

        def mock_command(*args, **kwargs):
            cmd = args[0] if args else []
            if not cmd:
                return ("", "", 1)

            if cmd[0] == "zypper" and "repos" in cmd:
                return ("1 | repo-oss | Main Repository | Yes | Yes | Yes\n", "", 0)
            elif cmd[0] == "rpm" and "-qa" in cmd:
                return ("kernel-1.0\nbash-2.0\n", "", 0)

            return ("", "", 1)

        return mock_command
