"""
Pytest fixtures and configuration for Snail Core tests.

Provides reusable test fixtures for command outputs, distribution detection,
and HTTP server mocking across the test suite.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest

from snail_core.config import Config


# Test Data Fixtures - Command Outputs
@pytest.fixture
def sample_uname_output():
    """Sample output from uname -a command."""
    return "Linux fedora 6.5.11-300.fc39.x86_64 #1 SMP PREEMPT_DYNAMIC Wed Nov 22 19:08:19 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux"


@pytest.fixture
def sample_hostnamectl_output():
    """Sample output from hostnamectl command."""
    return """Static hostname: fedora
       Icon name: computer-laptop
         Chassis: laptop
      Machine ID: 1234567890abcdef1234567890abcdef
         Boot ID: abcdef1234567890abcdef1234567890
Operating System: Fedora Linux 39 (Workstation Edition)
          Kernel: Linux 6.5.11-300.fc39.x86_64
    Architecture: x86-64
 Hardware Vendor: Dell Inc.
  Hardware Model: XPS 13 9380
Firmware Version: 1.22.0
   Firmware Date: Thu 2023-05-25
Firmware Age: 6month 1w 1d"""


@pytest.fixture
def sample_journalctl_json_output():
    """Sample JSON output from journalctl --output=json command."""
    return [
        {
            "__REALTIME_TIMESTAMP": "1704067200000000",
            "_SYSTEMD_UNIT": "sshd.service",
            "MESSAGE": "Server listening on 0.0.0.0 port 22.",
            "PRIORITY": "6"
        },
        {
            "__REALTIME_TIMESTAMP": "1704067260000000",
            "_SYSTEMD_UNIT": "sshd.service",
            "MESSAGE": "Accepted publickey for user from 192.168.1.100 port 12345 ssh2",
            "PRIORITY": "6"
        },
        {
            "__REALTIME_TIMESTAMP": "1704067320000000",
            "_SYSTEMD_UNIT": "systemd-logind.service",
            "MESSAGE": "New session 123 of user max.",
            "PRIORITY": "6"
        }
    ]


@pytest.fixture
def sample_dnf_repolist_output():
    """Sample output from dnf repolist command."""
    return """repo id                           repo name
fedora                            Fedora 39 - x86_64
updates                           Fedora 39 - x86_64 - Updates
rpmfusion-free                    RPM Fusion for Fedora 39 - Free
rpmfusion-free-updates            RPM Fusion for Fedora 39 - Free - Updates"""


@pytest.fixture
def sample_dnf_repolist_json_output():
    """Sample JSON output from dnf repolist --json command."""
    return [
        {
            "id": "fedora",
            "name": "Fedora 39 - x86_64",
            "is_enabled": True,
            "baseurl": ["https://download.fedoraproject.org/pub/fedora/linux/releases/39/Everything/x86_64/os/"],
            "gpgcheck": True
        },
        {
            "id": "updates",
            "name": "Fedora 39 - x86_64 - Updates",
            "is_enabled": True,
            "baseurl": ["https://download.fedoraproject.org/pub/fedora/linux/updates/39/Everything/x86_64/"],
            "gpgcheck": True
        }
    ]


@pytest.fixture
def sample_rpm_qa_output():
    """Sample output from rpm -qa command."""
    return """kernel-6.5.11-300.fc39.x86_64
bash-5.2.15-3.fc39.x86_64
glibc-2.38-14.fc39.x86_64
systemd-254.5-2.fc39.x86_64
dnf-4.18.0-1.fc39.noarch
python3-3.11.6-1.fc39.x86_64
openssl-libs-3.1.1-4.fc39.x86_64
zlib-1.2.13-4.fc39.x86_64
sqlite-libs-3.42.0-6.fc39.x86_64"""


@pytest.fixture
def sample_ip_route_output():
    """Sample output from ip route command."""
    return """default via 192.168.1.1 dev wlp2s0 proto dhcp metric 600
192.168.1.0/24 dev wlp2s0 proto kernel scope link src 192.168.1.100 metric 600
192.168.122.0/24 dev virbr0 proto kernel scope link src 192.168.122.1 linkdown"""


@pytest.fixture
def sample_resolvectl_output():
    """Sample output from resolvectl status command."""
    return """Global
         Protocols: +LLMNR +mDNS -DNSOverTLS DNSSEC=no/unsupported
  resolv.conf mode: stub

Link 2 (wlp2s0)
    Current Scopes: DNS LLMNR/IPv4 LLMNR/IPv6
         Protocols: +DefaultRoute +LLMNR -mDNS -DNSOverTLS DNSSEC=no/unsupported
  Current DNS Server: 192.168.1.1
       DNS Servers: 192.168.1.1 8.8.8.8 8.8.4.4
        DNS Domain: home.local"""


@pytest.fixture
def sample_df_output():
    """Sample output from df -h command."""
    return """Filesystem      Size  Used Avail Use% Mounted on
devtmpfs        4.0M     0  4.0M   0% /dev
tmpfs           3.8G  2.1M  3.8G   1% /dev/shm
/dev/nvme0n1p5   50G   25G   23G  52% /
/dev/nvme0n1p1  511M   50M  462M  10% /boot
tmpfs           1.9G   12M  1.9G   1% /run
tmpfs           1.9G     0  1.9G   0% /sys/fs/cgroup
/dev/nvme0n1p3  100G   10G   85G  11% /home
tmpfs           380M     0  380M   0% /run/user/1000"""


@pytest.fixture
def sample_mount_output():
    """Sample output from mount command."""
    return """/dev/nvme0n1p5 on / type ext4 (rw,relatime,seclabel)
/dev/nvme0n1p1 on /boot type ext4 (rw,relatime,seclabel)
/dev/nvme0n1p3 on /home type ext4 (rw,relatime,seclabel)
tmpfs on /tmp type tmpfs (rw,nosuid,nodev,seclabel)
proc on /proc type proc (rw,nosuid,nodev,noexec,relatime)
sysfs on /sys type sysfs (rw,nosuid,nodev,noexec,relatime,seclabel)
devtmpfs on /dev type devtmpfs (rw,nosuid,seclabel,size=4096k,nr_inodes=999424,mode=755)
tmpfs on /dev/shm type tmpfs (rw,nosuid,nodev,seclabel)"""


@pytest.fixture
def sample_lsblk_output():
    """Sample output from lsblk command."""
    return """NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
nvme0n1     259:0    0 476.9G  0 disk
├─nvme0n1p1 259:1    0   512M  0 part /boot
├─nvme0n1p2 259:2    0    49G  0 part [SWAP]
├─nvme0n1p3 259:3    0   100G  0 part /home
├─nvme0n1p4 259:4    0    50G  0 part
└─nvme0n1p5 259:5    0   277G  0 part /"""


@pytest.fixture
def sample_systemctl_list_units_output():
    """Sample output from systemctl list-units command."""
    return """UNIT                                 LOAD   ACTIVE SUB     DESCRIPTION
sshd.service                        loaded active running OpenSSH server daemon
systemd-logind.service               loaded active running User Login Management
NetworkManager.service               loaded active running Network Manager
firewalld.service                   loaded active running firewalld - dynamic firewall daemon
systemd-resolved.service             loaded active running Network Name Resolution
auditd.service                       loaded active running Security Auditing Service
rsyslog.service                      loaded active running System Logging Service
chronyd.service                      loaded active running NTP client/server
polkit.service                       loaded active running Authorization Manager
dbus.service                         loaded active running D-Bus System Message Bus

LOAD   = Reflects whether the unit definition was properly loaded.
ACTIVE = The high-level unit activation state, i.e. generalization of SUB.
SUB    = The low-level unit activation state, values depend on unit type.

10 loaded units listed. Pass --all to see loaded but inactive units, too.
To show all installed unit files use 'systemctl list-unit-files'."""


@pytest.fixture
def sample_ps_output():
    """Sample output from ps aux command."""
    return """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.0 235348  9724 ?        Ss   10:25   0:01 /usr/lib/systemd/systemd --switched-root --system --deserialize 31
root         2  0.0  0.0      0     0 ?        S    10:25   0:00 [kthreadd]
root         3  0.0  0.0      0     0 ?        I<   10:25   0:00 [rcu_gp]
root         4  0.0  0.0      0     0 ?        I<   10:25   0:00 [rcu_par_gp]
root         6  0.0  0.0      0     0 ?        I<   10:25   0:00 [kworker/0:0H-kblockd]
max       1234  2.1  1.2 1847296 98765 ?       Ssl  10:26   0:15 /usr/bin/gnome-shell
max       1567  0.1  0.3  456789 23456 ?       Sl   10:26   0:02 /usr/libexec/gsd-power
max       1789  0.0  0.2  345678 12345 ?       Sl   10:27   0:00 /usr/libexec/gsd-media-keys"""


@pytest.fixture
def sample_os_release_content():
    """Sample content for /etc/os-release file."""
    return """NAME="Fedora Linux"
VERSION="39 (Workstation Edition)"
ID=fedora
VERSION_ID=39
VERSION_CODENAME=""
PLATFORM_ID="platform:f39"
PRETTY_NAME="Fedora Linux 39 (Workstation Edition)"
ANSI_COLOR="0;38;2;60;110;180"
LOGO=fedora-logo-icon
CPE_NAME="cpe:/o:fedoraproject:fedora:39"
DEFAULT_HOSTNAME=fedora
HOME_URL="https://fedoraproject.org/"
DOCUMENTATION_URL="https://docs.fedoraproject.org/en-US/fedora/f39/system-administrators-guide/"
SUPPORT_URL="https://ask.fedoraproject.org/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"
REDHAT_SUPPORT_PRODUCT="Fedora"
REDHAT_SUPPORT_PRODUCT_VERSION=39
SUPPORT_END=2024-11-12"""


@pytest.fixture
def sample_proc_modules_content():
    """Sample content for /proc/modules file."""
    return """snd_hda_intel 53248 4 - Live 0x0000000000000000
snd_hda_codec 135168 3 snd_hda_intel,snd_hda_codec_generic,snd_hda_codec_hdmi, Live 0x0000000000000000
snd_hda_core 102400 4 snd_hda_intel,snd_hda_codec,snd_hda_codec_generic,snd_hda_codec_hdmi, Live 0x0000000000000000
snd_hwdep 20480 1 snd_hda_codec, Live 0x0000000000000000
snd_pcm 135168 4 snd_hda_intel,snd_hda_codec,snd_hda_core,snd_hda_codec_hdmi, Live 0x0000000000000000
snd_timer 53248 2 snd_pcm,snd_hda_core, Live 0x0000000000000000
snd 110592 18 snd_hda_intel,snd_hda_codec,snd_hwdep,snd_pcm,snd_timer,snd_hda_codec_generic,snd_hda_codec_hdmi, Live 0x0000000000000000
soundcore 16384 1 snd, Live 0x0000000000000000
i915 2875392 25 - Live 0x0000000000000000
drm_kms_helper 229376 1 i915, Live 0x0000000000000000
syscopyarea 16384 1 drm_kms_helper, Live 0x0000000000000000
sysfillrect 16384 1 drm_kms_helper, Live 0x0000000000000000
sysimgblt 16384 1 drm_kms_helper, Live 0x0000000000000000
fb_sys_fops 16384 1 drm_kms_helper, Live 0x0000000000000000
drm 577536 12 i915,drm_kms_helper, Live 0x0000000000000000
video 61440 1 i915, Live 0x0000000000000000"""


# Distribution Detection Fixtures
@pytest.fixture
def mock_fedora_detection():
    """Mock distribution detection for Fedora."""
    return {"id": "fedora", "version": "39", "version_id": "39", "like": "", "name": "Fedora Linux"}


@pytest.fixture
def mock_rhel_detection():
    """Mock distribution detection for RHEL."""
    return {"id": "rhel", "version": "9.2", "version_id": "9.2", "like": "", "name": "Red Hat Enterprise Linux"}


@pytest.fixture
def mock_ubuntu_detection():
    """Mock distribution detection for Ubuntu."""
    return {"id": "ubuntu", "version": "22.04.3 LTS (Jammy Jellyfish)", "version_id": "22.04", "like": "debian", "name": "Ubuntu"}


@pytest.fixture
def mock_debian_detection():
    """Mock distribution detection for Debian."""
    return {"id": "debian", "version": "12 (bookworm)", "version_id": "12", "like": "", "name": "Debian GNU/Linux"}


@pytest.fixture
def mock_suse_detection():
    """Mock distribution detection for SUSE/openSUSE."""
    return {"id": "opensuse-leap", "version": "15.5", "version_id": "15.5", "like": "", "name": "openSUSE Leap"}


# HTTP Server Fixtures
@pytest.fixture
def mock_upload_server_success():
    """Mock HTTP server that accepts uploads successfully."""
    def mock_post(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.text = '{"status": "success", "report_id": "test-12345"}'
        response.ok = True
        response.json.return_value = {"status": "success", "report_id": "test-12345"}
        return response

    return mock_post


@pytest.fixture
def mock_upload_server_auth_required():
    """Mock HTTP server that requires authentication."""
    def mock_post(*args, **kwargs):
        response = MagicMock()
        response.status_code = 401
        response.text = '{"error": "Authentication required"}'
        response.ok = False
        return response

    return mock_post


@pytest.fixture
def mock_upload_server_server_error():
    """Mock HTTP server that returns server errors."""
    def mock_post(*args, **kwargs):
        response = MagicMock()
        response.status_code = 500
        response.text = '{"error": "Internal server error"}'
        response.ok = False
        return response

    return mock_post


@pytest.fixture
def mock_upload_server_timeout():
    """Mock HTTP server that times out."""
    import requests

    def mock_post(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")

    return mock_post


@pytest.fixture
def mock_upload_server_connection_error():
    """Mock HTTP server that has connection errors."""
    import requests

    def mock_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Connection failed")

    return mock_post


# Utility Fixtures
@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file."""
    config_file = tmp_path / "test_config.yaml"
    config_content = """
upload:
  url: "https://test.example.com/api/upload"
  enabled: true
auth:
  api_key: "test-key-123"
collection:
  timeout: 60
"""

    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def temp_data_directory(tmp_path):
    """Create a temporary data directory."""
    data_dir = tmp_path / "snail_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_collection_report():
    """Sample collection report for testing."""
    from snail_core.core import CollectionReport

    return CollectionReport(
        hostname="test-host",
        host_id="test-host-id-12345",
        collection_id="test-collection-67890",
        timestamp="2024-01-01T12:00:00Z",
        snail_version="1.0.0",
        results={
            "system": {"os": "Linux", "kernel": "5.15.0"},
            "hardware": {"cpu": "Intel i7", "memory": "16GB"}
        },
        errors=[]
    )


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return Config(
        upload_url="https://test.example.com/api/upload",
        upload_enabled=True,
        api_key="test-api-key-12345",
        upload_timeout=30,
        upload_retries=3,
        collection_timeout=300,
        output_dir="/tmp/test_output"
    )


# Pytest Configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Clean up any temporary files created during tests."""
    # This runs before each test
    yield
    # This runs after each test
    # Cleanup logic can be added here if needed


@pytest.fixture(scope="session")
def test_session_setup():
    """Set up test session-wide fixtures."""
    # This runs once per test session
    # Can be used for expensive setup that should be shared across tests
    return {"session_id": "test-session-123"}
