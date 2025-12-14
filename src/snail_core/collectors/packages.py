"""
Package information collector with multi-distro support.

Supports DNF (Fedora, RHEL 8+, CentOS Stream), YUM (RHEL 7, CentOS 7),
APT (Debian, Ubuntu), and Zypper (SUSE, openSUSE).
"""

from __future__ import annotations

import json
from typing import Any

from snail_core.collectors.base import BaseCollector


class PackagesCollector(BaseCollector):
    """Collects package and repository information with multi-distro support."""

    name = "packages"
    description = "Installed packages, repositories, and package manager info"

    def collect(self) -> dict[str, Any]:
        """Collect package information based on detected distribution."""
        distro_info = self.detect_distro()
        distro_id = distro_info.get("id", "").lower()
        distro_like = distro_info.get("like", "").lower()

        # Determine package manager
        if (
            distro_id in ("fedora", "rhel", "centos", "rocky", "almalinux")
            or "fedora" in distro_like
            or "rhel" in distro_like
        ):
            return self._collect_rpm_based(distro_id)
        elif distro_id in ("debian", "ubuntu") or "debian" in distro_like:
            return self._collect_apt_based()
        elif distro_id in (
            "suse",
            "opensuse",
            "sles",
            "opensuse-leap",
            "opensuse-tumbleweed",
        ):
            return self._collect_zypper_based()
        else:
            # Try to auto-detect
            return self._collect_auto_detect()

    def _collect_rpm_based(self, distro_id: str) -> dict[str, Any]:
        """Collect package info for RPM-based distributions."""
        result: dict[str, Any] = {
            "package_manager": "rpm",
            "summary": self._get_rpm_summary(),
            "repositories": [],
            "config": {},
            "recent_transactions": [],
            "upgradeable": {},
            "kernel_packages": self._get_kernel_packages(),
        }

        # Try DNF first (Fedora, RHEL 8+, CentOS Stream)
        dnf_available = self.run_command(["dnf", "--version"])[2] == 0
        yum_available = self.run_command(["yum", "--version"])[2] == 0

        if dnf_available:
            result["package_manager"] = "dnf"
            result["repositories"] = self._get_dnf_repositories()
            result["config"] = self._get_dnf_config()
            result["recent_transactions"] = self._get_dnf_transactions()
            result["upgradeable"] = self._get_dnf_upgradeable()
        elif yum_available:
            result["package_manager"] = "yum"
            result["repositories"] = self._get_yum_repositories()
            result["config"] = self._get_yum_config()
            result["recent_transactions"] = self._get_yum_transactions()
            result["upgradeable"] = self._get_yum_upgradeable()

        return result

    def _collect_apt_based(self) -> dict[str, Any]:
        """Collect package info for APT-based distributions (Debian, Ubuntu)."""
        return {
            "package_manager": "apt",
            "summary": self._get_apt_summary(),
            "repositories": self._get_apt_repositories(),
            "config": self._get_apt_config(),
            "recent_transactions": self._get_apt_transactions(),
            "upgradeable": self._get_apt_upgradeable(),
            "kernel_packages": self._get_deb_kernel_packages(),
        }

    def _collect_zypper_based(self) -> dict[str, Any]:
        """Collect package info for Zypper-based distributions (SUSE)."""
        return {
            "package_manager": "zypper",
            "summary": self._get_zypper_summary(),
            "repositories": self._get_zypper_repositories(),
            "config": self._get_zypper_config(),
            "recent_transactions": self._get_zypper_transactions(),
            "upgradeable": self._get_zypper_upgradeable(),
            "kernel_packages": self._get_rpm_kernel_packages(),
        }

    def _collect_auto_detect(self) -> dict[str, Any]:
        """Auto-detect package manager and collect info."""
        # Try each package manager
        if self.run_command(["dnf", "--version"])[2] == 0:
            return self._collect_rpm_based("fedora")
        elif self.run_command(["yum", "--version"])[2] == 0:
            return self._collect_rpm_based("rhel")
        elif self.run_command(["apt", "--version"])[2] == 0:
            return self._collect_apt_based()
        elif self.run_command(["zypper", "--version"])[2] == 0:
            return self._collect_zypper_based()
        else:
            return {
                "package_manager": "unknown",
                "error": "No supported package manager found",
            }

    # RPM-based methods
    def _get_rpm_summary(self) -> dict[str, Any]:
        """Get summary of installed RPM packages."""
        summary: dict[str, Any] = {
            "total_count": 0,
            "by_arch": {},
        }

        stdout, _, rc = self.run_command(["rpm", "-qa", "--qf", "%{ARCH}\n"])
        if rc == 0 and stdout:
            arches = stdout.strip().split("\n")
            summary["total_count"] = len(arches)
            for arch in arches:
                arch = arch.strip()
                if arch:
                    summary["by_arch"][arch] = summary["by_arch"].get(arch, 0) + 1

        stdout, _, rc = self.run_command(["rpm", "-qa", "gpg-pubkey*"])
        summary["gpg_keys_count"] = len(stdout.strip().split("\n")) if rc == 0 and stdout else 0

        return summary

    def _get_dnf_repositories(self) -> list[dict[str, Any]]:
        """Get DNF repositories."""
        repos = []
        stdout, _, rc = self.run_command(["dnf", "repolist", "--all", "-v", "--json"], timeout=60)
        if rc == 0 and stdout:
            try:
                data = json.loads(stdout)
                for repo in data:
                    repos.append(
                        {
                            "id": repo.get("id", ""),
                            "name": repo.get("name", ""),
                            "enabled": repo.get("is_enabled", False),
                            "baseurl": repo.get("baseurl", []),
                            "gpgcheck": repo.get("gpgcheck", True),
                        }
                    )
                return repos
            except json.JSONDecodeError:
                pass

        # Fallback
        stdout, _, rc = self.run_command(["dnf", "repolist", "--all"])
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    repo_id = parts[0].rstrip("*")
                    repos.append(
                        {
                            "id": repo_id,
                            "name": " ".join(parts[1:]),
                            "enabled": not repo_id.endswith("disabled"),
                        }
                    )
        return repos

    def _get_dnf_config(self) -> dict[str, Any]:
        """Get DNF configuration."""
        config: dict[str, Any] = {}
        main_config = self.parse_key_value_file("/etc/dnf/dnf.conf")
        config["gpgcheck"] = main_config.get("gpgcheck", "1") == "1"
        config["installonly_limit"] = int(main_config.get("installonly_limit", "3"))

        stdout, _, rc = self.run_command(["dnf", "--version"])
        if rc == 0 and stdout:
            config["version"] = stdout.strip().split("\n")[0]
        return config

    def _get_dnf_transactions(self) -> list[dict[str, Any]]:
        """Get recent DNF transactions."""
        transactions = []
        stdout, _, rc = self.run_command(["dnf", "history", "list", "--json"], timeout=30)
        if rc == 0 and stdout:
            try:
                data = json.loads(stdout)
                for tx in data[:20]:
                    transactions.append(
                        {
                            "id": tx.get("id"),
                            "command": tx.get("command_line", ""),
                            "date": tx.get("dt_begin", ""),
                        }
                    )
                return transactions
            except json.JSONDecodeError:
                pass
        return transactions

    def _get_dnf_upgradeable(self) -> dict[str, Any]:
        """Get upgradeable packages from DNF."""
        result: dict[str, Any] = {"count": 0, "packages": []}
        stdout, _, rc = self.run_command(["dnf", "check-update", "--json"], timeout=120)
        if stdout and rc in (0, 100):
            try:
                data = json.loads(stdout)
                packages = data if isinstance(data, list) else []
                result["count"] = len(packages)
                result["packages"] = [
                    {"name": p.get("name", ""), "version": p.get("version", "")}
                    for p in packages[:50]
                ]
            except json.JSONDecodeError:
                pass
        return result

    def _get_yum_repositories(self) -> list[dict[str, Any]]:
        """Get YUM repositories."""
        repos = []
        stdout, _, rc = self.run_command(["yum", "repolist", "all"])
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    repo_id = parts[0].rstrip("*")
                    repos.append(
                        {
                            "id": repo_id,
                            "name": " ".join(parts[1:]),
                            "enabled": not repo_id.endswith("disabled"),
                        }
                    )
        return repos

    def _get_yum_config(self) -> dict[str, Any]:
        """Get YUM configuration."""
        config: dict[str, Any] = {}
        main_config = self.parse_key_value_file("/etc/yum.conf")
        config["gpgcheck"] = main_config.get("gpgcheck", "1") == "1"
        stdout, _, rc = self.run_command(["yum", "--version"])
        if rc == 0 and stdout:
            config["version"] = stdout.strip().split("\n")[0]
        return config

    def _get_yum_transactions(self) -> list[dict[str, Any]]:
        """Get recent YUM transactions."""
        transactions = []
        stdout, _, rc = self.run_command(["yum", "history", "list"])
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n")[2:22]:
                parts = line.split("|")
                if len(parts) >= 3:
                    transactions.append(
                        {
                            "id": parts[0].strip(),
                            "command": parts[1].strip(),
                            "date": parts[2].strip(),
                        }
                    )
        return transactions

    def _get_yum_upgradeable(self) -> dict[str, Any]:
        """Get upgradeable packages from YUM."""
        result: dict[str, Any] = {"count": 0, "packages": []}
        stdout, _, rc = self.run_command(["yum", "check-update"], timeout=120)
        if rc in (0, 100) and stdout:
            for line in stdout.strip().split("\n"):
                if line and not line.startswith("Loaded") and not line.startswith("Updated"):
                    parts = line.split()
                    if len(parts) >= 2:
                        result["packages"].append({"name": parts[0], "version": parts[1]})
            result["count"] = len(result["packages"])
        return result

    # APT-based methods
    def _get_apt_summary(self) -> dict[str, Any]:
        """Get summary of installed APT packages."""
        summary: dict[str, Any] = {"total_count": 0, "by_arch": {}}
        stdout, _, rc = self.run_command(["dpkg-query", "-W", "-f=${Architecture}\n"])
        if rc == 0 and stdout:
            arches = stdout.strip().split("\n")
            summary["total_count"] = len(arches)
            for arch in arches:
                arch = arch.strip()
                if arch:
                    summary["by_arch"][arch] = summary["by_arch"].get(arch, 0) + 1
        return summary

    def _get_apt_repositories(self) -> list[dict[str, Any]]:
        """Get APT repositories."""
        repos = []
        # Parse sources.list and sources.list.d
        sources = self.read_file_lines("/etc/apt/sources.list")
        for line in sources:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 3:
                    repos.append(
                        {
                            "type": parts[0],
                            "url": parts[1],
                            "suite": parts[2],
                            "components": parts[3:] if len(parts) > 3 else [],
                        }
                    )
        return repos

    def _get_apt_config(self) -> dict[str, Any]:
        """Get APT configuration."""
        config: dict[str, Any] = {}
        # APT always checks GPG
        config["gpgcheck"] = True
        stdout, _, rc = self.run_command(["apt", "--version"])
        if rc == 0 and stdout:
            config["version"] = stdout.strip().split()[1] if " " in stdout else stdout.strip()
        return config

    def _get_apt_transactions(self) -> list[dict[str, Any]]:
        """Get recent APT transactions from history."""
        transactions = []
        history_file = "/var/log/apt/history.log"
        lines = self.read_file_lines(history_file)
        for line in lines[-100:]:  # Last 100 lines
            if line.startswith("Start-Date:") or line.startswith("Commandline:"):
                transactions.append({"info": line.strip()})
                if len(transactions) >= 20:
                    break
        return transactions

    def _get_apt_upgradeable(self) -> dict[str, Any]:
        """Get upgradeable packages from APT."""
        result: dict[str, Any] = {"count": 0, "packages": []}
        stdout, _, rc = self.run_command(["apt", "list", "--upgradable"], timeout=60)
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n")[1:]:  # Skip header
                if "/" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        result["packages"].append(
                            {
                                "name": parts[0].split("/")[0],
                                "version": parts[1],
                            }
                        )
            result["count"] = len(result["packages"])
        return result

    def _get_deb_kernel_packages(self) -> list[dict[str, str]]:
        """Get installed kernel packages (Debian/Ubuntu)."""
        kernels = []
        stdout, _, rc = self.run_command(
            ["dpkg-query", "-W", "-f=${Package}|${Version}\n", "linux-image*"]
        )
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if "|" in line:
                    name, version = line.split("|", 1)
                    kernels.append({"name": name, "version": version})
        return kernels

    # Zypper-based methods
    def _get_zypper_summary(self) -> dict[str, Any]:
        """Get summary of installed Zypper packages."""
        summary: dict[str, Any] = {"total_count": 0}
        stdout, _, rc = self.run_command(["rpm", "-qa", "--qf", "%{ARCH}\n"])
        if rc == 0 and stdout:
            summary["total_count"] = len(
                [line for line in stdout.strip().split("\n") if line.strip()]
            )
        return summary

    def _get_zypper_repositories(self) -> list[dict[str, Any]]:
        """Get Zypper repositories."""
        repos = []
        stdout, _, rc = self.run_command(["zypper", "repos", "-d"])
        if rc == 0 and stdout:
            current_repo: dict[str, Any] = {}
            for line in stdout.strip().split("\n"):
                if line.startswith("#"):
                    if current_repo:
                        repos.append(current_repo)
                    current_repo = {"id": line.strip("# ").strip()}
                elif ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    current_repo[key] = value.strip()
            if current_repo:
                repos.append(current_repo)
        return repos

    def _get_zypper_config(self) -> dict[str, Any]:
        """Get Zypper configuration."""
        config: dict[str, Any] = {}
        stdout, _, rc = self.run_command(["zypper", "--version"])
        if rc == 0 and stdout:
            config["version"] = stdout.strip()
        return config

    def _get_zypper_transactions(self) -> list[dict[str, Any]]:
        """Get recent Zypper transactions."""
        transactions = []
        stdout, _, rc = self.run_command(["zypper", "history"])
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n")[2:22]:  # Skip header
                parts = line.split("|")
                if len(parts) >= 3:
                    transactions.append(
                        {
                            "id": parts[0].strip(),
                            "command": parts[1].strip(),
                            "date": parts[2].strip(),
                        }
                    )
        return transactions

    def _get_zypper_upgradeable(self) -> dict[str, Any]:
        """Get upgradeable packages from Zypper."""
        result: dict[str, Any] = {"count": 0, "packages": []}
        stdout, _, rc = self.run_command(["zypper", "list-updates"], timeout=120)
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n")[2:]:  # Skip header
                parts = line.split("|")
                if len(parts) >= 3:
                    result["packages"].append(
                        {
                            "name": parts[2].strip(),
                            "version": parts[4].strip() if len(parts) > 4 else "",
                        }
                    )
            result["count"] = len(result["packages"])
        return result

    def _get_rpm_kernel_packages(self) -> list[dict[str, str]]:
        """Get installed kernel packages (RPM-based)."""
        kernels = []
        stdout, _, rc = self.run_command(
            ["rpm", "-qa", "kernel*", "--qf", "%{NAME}|%{VERSION}-%{RELEASE}\n"]
        )
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                if "|" in line:
                    name, version = line.split("|", 1)
                    kernels.append({"name": name, "version": version})
        return kernels

    def _get_kernel_packages(self) -> list[dict[str, str]]:
        """Get kernel packages (generic, calls appropriate method)."""
        return self._get_rpm_kernel_packages()
