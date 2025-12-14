"""
Security information collector with multi-distro support.

Supports SELinux (RHEL/Fedora/CentOS), AppArmor (Ubuntu/Debian/SUSE),
and various firewall tools.
"""

from __future__ import annotations

from typing import Any

from snail_core.collectors.base import BaseCollector


class SecurityCollector(BaseCollector):
    """Collects security-related system information with multi-distro support."""

    name = "security"
    description = "SELinux, AppArmor, crypto policies, and security configuration"

    def collect(self) -> dict[str, Any]:
        """Collect security information based on detected distribution."""
        result: dict[str, Any] = {
            "selinux": self._get_selinux_info(),
            "apparmor": self._get_apparmor_info(),
            "firewall": self._get_firewall_status(),
            "crypto_policy": self._get_crypto_policy(),
            "fips": self._get_fips_status(),
            "sshd": self._get_sshd_config(),
            "sudo": self._get_sudo_info(),
            "pam": self._get_pam_info(),
            "audit": self._get_audit_status(),
        }

        return result

    def _get_selinux_info(self) -> dict[str, Any]:
        """Get SELinux status and configuration (RHEL/Fedora/CentOS)."""
        selinux: dict[str, Any] = {
            "enabled": False,
            "mode": "disabled",
            "policy": "",
            "available": False,
        }

        # Check if SELinux is available
        if not self.read_file("/sys/fs/selinux/enforce"):
            return selinux

        selinux["available"] = True
        selinux["enabled"] = True

        # Get current mode
        stdout, _, rc = self.run_command(["getenforce"])
        if rc == 0:
            selinux["mode"] = stdout.strip().lower()

        # Parse SELinux config file
        config = self.parse_key_value_file("/etc/selinux/config")
        selinux["configured_mode"] = config.get("SELINUX", "").lower()
        selinux["policy"] = config.get("SELINUXTYPE", "")

        return selinux

    def _get_apparmor_info(self) -> dict[str, Any]:
        """Get AppArmor status (Ubuntu/Debian/SUSE)."""
        apparmor: dict[str, Any] = {
            "enabled": False,
            "available": False,
            "profiles": {},
        }

        # Check if AppArmor is available
        stdout, _, rc = self.run_command(["aa-status"])
        if rc == 0:
            apparmor["available"] = True
            apparmor["enabled"] = True

            # Parse profile counts
            for line in stdout.strip().split("\n"):
                if "profiles are loaded" in line:
                    try:
                        apparmor["profiles"]["loaded"] = int(line.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "profiles are in enforce mode" in line:
                    try:
                        apparmor["profiles"]["enforce"] = int(line.split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "profiles are in complain mode" in line:
                    try:
                        apparmor["profiles"]["complain"] = int(line.split()[0])
                    except (ValueError, IndexError):
                        pass
        else:
            # Check if module is loaded
            modules = self.read_file("/proc/modules")
            if modules and "apparmor" in modules:
                apparmor["available"] = True
                apparmor["enabled"] = True

        return apparmor

    def _get_firewall_status(self) -> dict[str, Any]:
        """Get firewall status (supports firewalld, ufw, iptables)."""
        firewall: dict[str, Any] = {
            "type": "none",
            "enabled": False,
            "running": False,
        }

        # Try firewalld (RHEL/Fedora/CentOS)
        stdout, _, rc = self.run_command(["systemctl", "is-active", "firewalld"])
        if rc == 0 and "active" in stdout:
            firewall["type"] = "firewalld"
            firewall["running"] = True
            firewall["enabled"] = True

            # Get zones
            stdout, _, rc = self.run_command(["firewall-cmd", "--get-zones"])
            if rc == 0:
                firewall["zones"] = stdout.strip().split()

            # Get default zone
            stdout, _, rc = self.run_command(["firewall-cmd", "--get-default-zone"])
            if rc == 0:
                firewall["default_zone"] = stdout.strip()

            return firewall

        # Try ufw (Ubuntu/Debian)
        stdout, _, rc = self.run_command(["ufw", "status"])
        if rc == 0:
            firewall["type"] = "ufw"
            firewall["running"] = "active" in stdout.lower()
            firewall["enabled"] = firewall["running"]
            return firewall

        # Check iptables (fallback)
        stdout, _, rc = self.run_command(["iptables", "-L", "-n"])
        if rc == 0:
            firewall["type"] = "iptables"
            firewall["running"] = True
            # Count rules
            rules = [
                line for line in stdout.strip().split("\n") if line and not line.startswith("Chain")
            ]
            firewall["rules_count"] = len(rules)

        return firewall

    def _get_crypto_policy(self) -> dict[str, Any]:
        """Get system-wide cryptographic policy (RHEL/Fedora)."""
        policy: dict[str, Any] = {}

        # Get current policy
        stdout, _, rc = self.run_command(["update-crypto-policies", "--show"])
        if rc == 0:
            policy["current"] = stdout.strip()
        else:
            # Fallback to reading the file directly
            current = self.read_file("/etc/crypto-policies/state/current").strip()
            if current:
                policy["current"] = current

        return policy

    def _get_fips_status(self) -> dict[str, Any]:
        """Get FIPS 140 mode status."""
        fips: dict[str, Any] = {
            "enabled": False,
        }

        # Check kernel FIPS mode
        fips_enabled = self.read_file("/proc/sys/crypto/fips_enabled").strip()
        fips["enabled"] = fips_enabled == "1"

        return fips

    def _get_sshd_config(self) -> dict[str, Any]:
        """Get SSH daemon configuration (sanitized)."""
        sshd: dict[str, Any] = {
            "running": False,
            "port": "22",
            "permit_root_login": "unknown",
            "password_auth": "unknown",
            "pubkey_auth": "unknown",
        }

        # Check if sshd is running (try different service names)
        for service_name in ["sshd", "ssh"]:
            stdout, _, rc = self.run_command(["systemctl", "is-active", service_name])
            if rc == 0 and "active" in stdout:
                sshd["running"] = True
                break

        # Parse sshd_config for key settings
        for line in self.read_file_lines("/etc/ssh/sshd_config"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(None, 1)
            if len(parts) < 2:
                continue

            key, value = parts[0].lower(), parts[1].lower()

            if key == "port":
                sshd["port"] = value
            elif key == "permitrootlogin":
                sshd["permit_root_login"] = value
            elif key == "passwordauthentication":
                sshd["password_auth"] = value
            elif key == "pubkeyauthentication":
                sshd["pubkey_auth"] = value

        return sshd

    def _get_sudo_info(self) -> dict[str, Any]:
        """Get sudo configuration information."""
        sudo: dict[str, Any] = {
            "version": "",
        }

        # Get sudo version
        stdout, _, rc = self.run_command(["sudo", "--version"])
        if rc == 0 and stdout:
            sudo["version"] = stdout.strip().split("\n")[0]

        return sudo

    def _get_pam_info(self) -> dict[str, Any]:
        """Get PAM configuration highlights."""
        pam: dict[str, Any] = {
            "faillock_enabled": False,
            "pwquality_enabled": False,
        }

        # Check system-auth or common-auth
        for auth_file in ["/etc/pam.d/system-auth", "/etc/pam.d/common-auth"]:
            content = self.read_file(auth_file)
            if content:
                pam["faillock_enabled"] = pam["faillock_enabled"] or "pam_faillock" in content
                pam["pwquality_enabled"] = pam["pwquality_enabled"] or "pam_pwquality" in content

        return pam

    def _get_audit_status(self) -> dict[str, Any]:
        """Get audit daemon status."""
        audit: dict[str, Any] = {
            "installed": False,
            "running": False,
        }

        # Check if auditd is installed
        _, _, rc = self.run_command(["which", "auditctl"])
        audit["installed"] = rc == 0

        if not audit["installed"]:
            return audit

        # Check if auditd is running
        stdout, _, rc = self.run_command(["systemctl", "is-active", "auditd"])
        audit["running"] = rc == 0 and "active" in stdout

        return audit
