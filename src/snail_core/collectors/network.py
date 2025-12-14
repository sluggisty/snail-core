"""
Network information collector.

Collects network interfaces, connections, routing, and DNS information.
"""

from __future__ import annotations

import socket
from typing import Any

import psutil

from snail_core.collectors.base import BaseCollector


class NetworkCollector(BaseCollector):
    """Collects network information."""

    name = "network"
    description = "Network interfaces, connections, and routing information"

    def collect(self) -> dict[str, Any]:
        """Collect network information."""
        return {
            "interfaces": self._get_interfaces(),
            "connections": self._get_connections_summary(),
            "routing": self._get_routing_table(),
            "dns": self._get_dns_config(),
            "stats": self._get_network_stats(),
            "hostname_resolution": self._get_hostname_resolution(),
            "firewall": self._get_firewall_status(),
        }

    def _get_interfaces(self) -> list[dict[str, Any]]:
        """Get network interface information."""
        interfaces = []

        # Get addresses
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)

        for iface_name, addr_list in addrs.items():
            iface = {
                "name": iface_name,
                "addresses": [],
                "mac": "",
            }

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    iface["addresses"].append(
                        {
                            "type": "ipv4",
                            "address": addr.address,
                            "netmask": addr.netmask,
                            "broadcast": addr.broadcast,
                        }
                    )
                elif addr.family == socket.AF_INET6:
                    iface["addresses"].append(
                        {
                            "type": "ipv6",
                            "address": addr.address,
                            "netmask": addr.netmask,
                        }
                    )
                elif addr.family == psutil.AF_LINK:
                    iface["mac"] = addr.address

            # Add interface stats
            if iface_name in stats:
                s = stats[iface_name]
                iface["is_up"] = s.isup
                iface["duplex"] = str(s.duplex) if hasattr(s, "duplex") else ""
                iface["speed"] = s.speed
                iface["mtu"] = s.mtu

            # Add I/O counters
            if iface_name in io_counters:
                c = io_counters[iface_name]
                iface["io"] = {
                    "bytes_sent": c.bytes_sent,
                    "bytes_recv": c.bytes_recv,
                    "packets_sent": c.packets_sent,
                    "packets_recv": c.packets_recv,
                    "errin": c.errin,
                    "errout": c.errout,
                    "dropin": c.dropin,
                    "dropout": c.dropout,
                }

            interfaces.append(iface)

        return interfaces

    def _get_connections_summary(self) -> dict[str, Any]:
        """Get summary of network connections."""
        try:
            connections = psutil.net_connections(kind="all")
        except (psutil.AccessDenied, PermissionError):
            return {"error": "Permission denied - run as root for connection info"}

        # Summarize by status
        status_count: dict[str, int] = {}
        type_count: dict[str, int] = {}

        for conn in connections:
            status = conn.status if hasattr(conn, "status") else "UNKNOWN"
            status_count[status] = status_count.get(status, 0) + 1

            conn_type = "tcp" if conn.type == socket.SOCK_STREAM else "udp"
            type_count[conn_type] = type_count.get(conn_type, 0) + 1

        # Get listening ports
        listening = []
        for conn in connections:
            if hasattr(conn, "status") and conn.status == "LISTEN":
                if conn.laddr:
                    listening.append(
                        {
                            "address": conn.laddr.ip,
                            "port": conn.laddr.port,
                            "pid": conn.pid,
                        }
                    )

        return {
            "total": len(connections),
            "by_status": status_count,
            "by_type": type_count,
            "listening_ports": listening[:50],  # Limit to 50
        }

    def _get_routing_table(self) -> list[dict[str, str]]:
        """Get routing table."""
        routes = []
        stdout, _, rc = self.run_command(["ip", "route", "show"])

        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    route: dict[str, str] = {"raw": line}

                    if parts:
                        if parts[0] == "default":
                            route["destination"] = "0.0.0.0/0"
                            route["type"] = "default"
                        else:
                            route["destination"] = parts[0]
                            route["type"] = "network"

                    # Parse gateway
                    if "via" in parts:
                        idx = parts.index("via")
                        if idx + 1 < len(parts):
                            route["gateway"] = parts[idx + 1]

                    # Parse device
                    if "dev" in parts:
                        idx = parts.index("dev")
                        if idx + 1 < len(parts):
                            route["device"] = parts[idx + 1]

                    routes.append(route)

        return routes

    def _get_dns_config(self) -> dict[str, Any]:
        """Get DNS configuration."""
        dns: dict[str, Any] = {
            "nameservers": [],
            "search_domains": [],
            "options": [],
        }

        # Parse /etc/resolv.conf
        for line in self.read_file_lines("/etc/resolv.conf"):
            line = line.strip()
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) > 1:
                    dns["nameservers"].append(parts[1])
            elif line.startswith("search") or line.startswith("domain"):
                parts = line.split()
                dns["search_domains"].extend(parts[1:])
            elif line.startswith("options"):
                parts = line.split()
                dns["options"].extend(parts[1:])

        # Check systemd-resolved status
        stdout, _, rc = self.run_command(["resolvectl", "status", "--no-pager"])
        if rc == 0:
            dns["systemd_resolved"] = True
            # Extract current DNS from resolvectl
            for line in stdout.split("\n"):
                if "DNS Servers:" in line or "Current DNS Server:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        servers = parts[1].strip().split()
                        for server in servers:
                            if server and server not in dns["nameservers"]:
                                dns["nameservers"].append(server)
        else:
            dns["systemd_resolved"] = False

        return dns

    def _get_network_stats(self) -> dict[str, Any]:
        """Get overall network statistics."""
        counters = psutil.net_io_counters()

        return {
            "total_bytes_sent": counters.bytes_sent,
            "total_bytes_recv": counters.bytes_recv,
            "total_packets_sent": counters.packets_sent,
            "total_packets_recv": counters.packets_recv,
            "total_errors_in": counters.errin,
            "total_errors_out": counters.errout,
            "total_drops_in": counters.dropin,
            "total_drops_out": counters.dropout,
        }

    def _get_hostname_resolution(self) -> dict[str, Any]:
        """Test hostname resolution."""
        hostname = socket.gethostname()
        result: dict[str, Any] = {
            "hostname": hostname,
            "fqdn": socket.getfqdn(),
        }

        # Try to resolve hostname
        try:
            result["hostname_ip"] = socket.gethostbyname(hostname)
        except socket.gaierror:
            result["hostname_ip"] = None

        # Check NSSwitch config
        nsswitch = self.parse_key_value_file("/etc/nsswitch.conf", separator=":")
        result["nsswitch_hosts"] = nsswitch.get("hosts", "").strip()

        return result

    def _get_firewall_status(self) -> dict[str, Any]:
        """Get firewall status."""
        firewall: dict[str, Any] = {
            "firewalld": {"installed": False, "running": False},
            "iptables": {"installed": False, "rules_count": 0},
            "nftables": {"installed": False, "tables_count": 0},
        }

        # Check firewalld
        stdout, _, rc = self.run_command(["firewall-cmd", "--state"])
        if rc != -1:  # Command exists
            firewall["firewalld"]["installed"] = True
            firewall["firewalld"]["running"] = "running" in stdout.lower()

            if firewall["firewalld"]["running"]:
                stdout, _, _ = self.run_command(["firewall-cmd", "--get-default-zone"])
                firewall["firewalld"]["default_zone"] = stdout.strip()

                stdout, _, _ = self.run_command(["firewall-cmd", "--get-active-zones"])
                firewall["firewalld"]["active_zones"] = stdout.strip()

        # Check iptables
        stdout, _, rc = self.run_command(["iptables", "-L", "-n"])
        if rc == 0:
            firewall["iptables"]["installed"] = True
            # Count non-empty, non-chain lines
            rules = [
                line
                for line in stdout.split("\n")
                if line.strip() and not line.startswith("Chain") and not line.startswith("target")
            ]
            firewall["iptables"]["rules_count"] = len(rules)

        # Check nftables
        stdout, _, rc = self.run_command(["nft", "list", "tables"])
        if rc == 0:
            firewall["nftables"]["installed"] = True
            tables = [line for line in stdout.split("\n") if line.strip()]
            firewall["nftables"]["tables_count"] = len(tables)

        return firewall
