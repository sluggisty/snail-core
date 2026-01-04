"""
Unit tests for SystemCollector.

Tests OS info, kernel, hostname, uptime, and virtualization collection.
"""

from __future__ import annotations

from unittest.mock import patch


from snail_core.collectors.system import SystemCollector


class TestSystemCollector:
    """Test SystemCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = SystemCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "os" in result
        assert "kernel" in result
        assert "hostname" in result
        assert "uptime" in result
        assert "boot" in result
        assert "users" in result
        assert "virtualization" in result

    def test_parse_version_rhel_format(self):
        """Test version parsing for RHEL format (major.minor)."""
        collector = SystemCollector()
        result = collector._parse_version("rhel", "9.2", "Red Hat Enterprise Linux 9.2")

        assert result["major"] == "9"
        assert result["minor"] == "2"
        assert result["patch"] is None

    def test_parse_version_fedora_format(self):
        """Test version parsing for Fedora format (single number)."""
        collector = SystemCollector()
        result = collector._parse_version("fedora", "39", "Fedora Linux 39")

        assert result["major"] == "39"
        assert result["minor"] is None
        assert result["patch"] is None

    def test_parse_version_ubuntu_format(self):
        """Test version parsing for Ubuntu format (year.month)."""
        collector = SystemCollector()
        result = collector._parse_version("ubuntu", "22.04", "Ubuntu 22.04 LTS")

        assert result["major"] == "22"
        assert result["minor"] == "04"

    @patch("snail_core.collectors.system.distro")
    @patch("snail_core.collectors.system.platform")
    def test_get_os_info(self, mock_platform, mock_distro):
        """Test OS info collection with mocked distro."""
        collector = SystemCollector()
        mock_distro.id.return_value = "fedora"
        mock_distro.version.return_value = "39"
        mock_distro.version.return_value = "39"  # pretty=True case
        mock_distro.name.return_value = "Fedora Linux"
        mock_distro.codename.return_value = ""
        mock_distro.like.return_value = "rhel fedora"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.platform.return_value = "Linux-5.x-x86_64"

        with patch.object(collector, "parse_key_value_file", return_value={}):
            result = collector._get_os_info()

            assert result["id"] == "fedora"
            assert result["name"] == "Fedora Linux"
            assert "architecture" in result
