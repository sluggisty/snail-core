"""
Unit tests for NetworkCollector.

Tests network interfaces, connections, routing, DNS, and firewall collection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import psutil

from snail_core.collectors.network import NetworkCollector


class TestNetworkCollector:
    """Test NetworkCollector class."""

    def test_collect_returns_expected_structure(self):
        """Test that collect() returns expected structure."""
        collector = NetworkCollector()
        result = collector.collect()

        assert isinstance(result, dict)
        assert "interfaces" in result
        assert "connections" in result
        assert "routing" in result
        assert "dns" in result

    @patch("snail_core.collectors.network.psutil")
    def test_get_interfaces(self, mock_psutil):
        """Test network interface collection."""
        collector = NetworkCollector()

        # Mock network interface data
        mock_addr = MagicMock()
        mock_addr.family = 2  # AF_INET
        mock_addr.address = "192.168.1.100"
        mock_addr.netmask = "255.255.255.0"

        mock_psutil.net_if_addrs.return_value = {"eth0": [mock_addr]}
        mock_psutil.net_if_stats.return_value = {"eth0": MagicMock(isup=True, speed=1000, mtu=1500)}
        mock_psutil.net_io_counters.return_value = {"eth0": MagicMock(
            bytes_sent=1000, bytes_recv=2000, packets_sent=10, packets_recv=20
        )}

        result = collector._get_interfaces()
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["name"] == "eth0"

    @patch("snail_core.collectors.network.psutil")
    def test_get_connections_summary(self, mock_psutil):
        """Test connection summary collection."""
        collector = NetworkCollector()

        mock_conn = MagicMock()
        mock_conn.status = "ESTABLISHED"
        mock_conn.type = 1  # SOCK_STREAM
        mock_conn.laddr = None
        mock_psutil.net_connections.return_value = [mock_conn]

        result = collector._get_connections_summary()
        assert "total" in result
        assert "by_status" in result
        assert "by_type" in result

    def test_get_routing_table(self):
        """Test routing table parsing."""
        collector = NetworkCollector()
        mock_output = "default via 192.168.1.1 dev eth0\n192.168.1.0/24 dev eth0"

        with patch.object(collector, "run_command", return_value=(mock_output, "", 0)):
            result = collector._get_routing_table()
            assert isinstance(result, list)

    def test_get_dns_config(self):
        """Test DNS configuration parsing."""
        collector = NetworkCollector()
        mock_resolv = ["nameserver 8.8.8.8", "nameserver 8.8.4.4", "search example.com"]

        with patch.object(collector, "read_file_lines", return_value=mock_resolv):
            result = collector._get_dns_config()
            assert "nameservers" in result
            assert "search_domains" in result

    def test_get_firewall_status(self):
        """Test firewall status detection."""
        collector = NetworkCollector()

        # Test firewalld detection - use side_effect list to handle all calls
        mock_calls = [
            ("running", "", 0),   # firewall-cmd --state
            ("public", "", 0),    # firewall-cmd --get-default-zone
            ("public", "", 0),    # firewall-cmd --get-active-zones
            ("", "", 1),          # iptables -L -n (not accessible)
            ("", "", 1),          # nft list tables (not accessible)
        ]

        with patch.object(collector, "run_command", side_effect=mock_calls):
            result = collector._get_firewall_status()
            assert "firewalld" in result
            assert result["firewalld"]["installed"] is True
            assert result["firewalld"]["running"] is True

