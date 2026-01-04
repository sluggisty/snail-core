"""
Unit tests for PackagesCollector.

Tests package manager detection and package/repository collection.
"""

from __future__ import annotations

from unittest.mock import patch

from snail_core.collectors.packages import PackagesCollector


class TestPackagesCollector:
    """Test PackagesCollector class."""

    def test_collect_returns_structure(self):
        """Test that collect() returns expected structure."""
        collector = PackagesCollector()

        with patch.object(
            collector, "detect_distro", return_value={"id": "fedora", "like": "rhel"}
        ):
            with patch.object(
                collector, "_collect_rpm_based", return_value={"package_manager": "dnf"}
            ):
                result = collector.collect()
                assert "package_manager" in result

    def test_collect_rpm_based_distro_detection(self):
        """Test RPM-based distribution detection."""
        collector = PackagesCollector()

        # Test Fedora detection
        with patch.object(collector, "detect_distro", return_value={"id": "fedora", "like": ""}):
            with patch.object(collector, "_collect_rpm_based") as mock_collect:
                collector.collect()
                mock_collect.assert_called_once()

    def test_get_dnf_repositories_json(self):
        """Test DNF repository parsing from JSON output."""
        collector = PackagesCollector()
        mock_json = '[{"id": "fedora", "name": "Fedora", "is_enabled": true}]'

        with patch.object(collector, "run_command", return_value=(mock_json, "", 0)):
            result = collector._get_dnf_repositories()
            assert isinstance(result, list)

    def test_get_apt_repositories(self):
        """Test APT repository parsing."""
        collector = PackagesCollector()
        mock_sources = [
            "deb http://archive.ubuntu.com/ubuntu/ focal main restricted",
            "# deb http://archive.ubuntu.com/ubuntu/ focal universe",
        ]

        with patch.object(collector, "read_file_lines", return_value=mock_sources):
            result = collector._get_apt_repositories()
            assert isinstance(result, list)
            assert len(result) > 0
            assert result[0]["type"] == "deb"

    def test_get_rpm_summary(self):
        """Test RPM package summary."""
        collector = PackagesCollector()
        mock_output = "x86_64\nx86_64\naarch64\n"

        with patch.object(
            collector,
            "run_command",
            side_effect=[
                (mock_output, "", 0),  # rpm -qa --qf
                ("", "", 0),  # gpg-pubkey
            ],
        ):
            result = collector._get_rpm_summary()
            assert "total_count" in result
            assert "by_arch" in result
