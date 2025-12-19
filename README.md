# 🐌 Snail Core

![Snailcore Logo](snail-core.png)

A system information collection and upload framework for Linux, inspired by [Red Hat's insights-core](https://github.com/RedHatInsights/insights-core).

Snail Core provides an extensible framework for gathering system diagnostics and uploading them to a custom endpoint. It's designed to be modular, secure, and easy to integrate into your infrastructure.

## Features

- **Comprehensive System Collection**: Gathers OS info, hardware specs, network config, packages, services, filesystem, security settings, and logs
- **Multi-Distribution Support**: Compatible with Fedora, RHEL, CentOS, Debian, Ubuntu, SUSE, and other Linux distributions
- **Multi-Version Support**: Works across multiple versions of supported distributions
- **Modular Architecture**: Plugin-based collectors that can be enabled/disabled individually
- **Secure Upload**: HTTPS with API key auth, mutual TLS support, and automatic retries
- **Privacy Controls**: Configurable redaction and anonymization options
- **Rich CLI**: Beautiful terminal interface with progress indicators and colored output
- **Flexible Configuration**: YAML config files, environment variables, and CLI options

## Supported Distributions

Snail Core supports the following Linux distributions and their versions:

- **Fedora**: All recent versions (uses DNF)
- **RHEL**: 7.x (YUM), 8.x+ (DNF)
- **CentOS**: 7 (YUM), Stream 8+ (DNF)
- **Debian**: Recent versions (uses APT)
- **Ubuntu**: Recent versions (uses APT)
- **SUSE/openSUSE**: Leap, Tumbleweed, SLES (uses Zypper)
- **Other Linux**: Auto-detects available package managers

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/sluggisty/snail-core.git
cd snail-core

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate

# Install the package
pip install -e .
```

### System Dependencies

Some collectors require system tools to be installed:

```bash
# On Fedora/RHEL/CentOS
sudo dnf install lsof lshw pciutils usbutils

# On Debian/Ubuntu
sudo apt-get install lsof lshw pciutils usbutils

# On SUSE/openSUSE
sudo zypper install lsof lshw pciutils usbutils
```

## Quick Start

### 1. Generate a Configuration File

```bash
snail init-config ~/.config/snail-core/config.yaml
```

### 2. Edit the Configuration

Update the config file with your upload server URL:

```yaml
upload:
  url: https://your-server.example.com/api/v1/ingest
  enabled: true
```

### 3. Set Your API Key

```bash
export SNAIL_API_KEY="your-api-key-here"
```

### 4. Collect and Upload

```bash
# Collect only (no upload)
snail collect

# Collect and upload
snail collect --upload

# Or use the shorthand
snail run
```

## CLI Usage

```bash
# Show help
snail --help

# List available collectors
snail list

# Run specific collectors only
snail collect -C system -C network -C packages

# Output as JSON
snail collect --format json

# Save to file
snail collect -o /tmp/report.json

# Check configuration and connection
snail status

# Display version information
snail list-version

# View or reset persistent host ID
snail host-id
snail host-id --reset

# Verbose mode
snail -v collect
```

## Collectors

| Collector | Description | Multi-Distro Support |
|-----------|-------------|---------------------|
| `system` | OS version, kernel, hostname, uptime, virtualization | ✅ All distributions |
| `hardware` | CPU, memory, disks, PCI/USB devices, DMI info | ✅ All distributions |
| `network` | Interfaces, connections, routing, DNS, firewall | ✅ All distributions |
| `packages` | Installed packages, repositories, package manager config | ✅ DNF/YUM/APT/Zypper |
| `services` | Systemd units, running services, failed units, timers | ✅ Systemd-based distros |
| `filesystem` | Mounts, fstab, LVM, Btrfs, inode usage | ✅ All distributions |
| `security` | SELinux/AppArmor, firewall, crypto policies, SSH, audit | ✅ Multi-distro aware |
| `logs` | Recent journald entries, errors, auth failures | ✅ Systemd-based distros |

## Configuration

Snail Core looks for configuration in these locations (in order):

1. Path specified with `--config` flag
2. `/etc/snail-core/config.yaml`
3. `~/.config/snail-core/config.yaml`
4. `./snail-config.yaml`

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SNAIL_UPLOAD_URL` | Upload endpoint URL |
| `SNAIL_UPLOAD_ENABLED` | Enable/disable upload (true/false) |
| `SNAIL_API_KEY` | API key for authentication |
| `SNAIL_AUTH_CERT` | Path to client certificate |
| `SNAIL_AUTH_KEY` | Path to client key |
| `SNAIL_LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) |

### Example Configuration

```yaml
upload:
  url: https://insights.example.com/api/v1/upload
  enabled: true
  timeout: 30
  retries: 3

auth:
  api_key: null  # Use SNAIL_API_KEY env var

collection:
  enabled_collectors: []  # Empty = all
  disabled_collectors: []
  timeout: 300

output:
  dir: /var/lib/snail-core
  keep_local: false
  compress: true

privacy:
  anonymize_hostnames: false
  redact_passwords: true
```

## Multi-Distribution Support

Snail Core automatically detects your Linux distribution and uses the appropriate tools:

- **RPM-based (Fedora/RHEL/CentOS)**: Uses DNF (preferred) or YUM (fallback)
- **Debian-based (Debian/Ubuntu)**: Uses APT
- **SUSE-based (SUSE/openSUSE)**: Uses Zypper
- **Security**: Detects SELinux (RHEL/Fedora) or AppArmor (Ubuntu/Debian/SUSE)
- **Firewall**: Detects firewalld, ufw, or iptables
- **Services**: Uses systemd (most modern distributions)

## Server Integration

Snail Core uploads JSON data via HTTP POST. Your server should accept:

```
POST /api/v1/ingest
Content-Type: application/json
Content-Encoding: gzip  (if compression enabled)
Authorization: Bearer <api-key>

{
  "meta": {
    "hostname": "fedora-workstation",
    "host_id": "057a8430-c818-4a43-8683-0ab05be16ef6",
    "collection_id": "uuid",
    "timestamp": "2024-01-15T10:30:00Z",
    "snail_version": "0.2.0"
  },
  "data": {
    "system": { ... },
    "hardware": { ... },
    "network": { ... },
    ...
  },
  "errors": []
}
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Run pre-commit hooks
pre-commit run --all-files
```

## License

MIT License - See [LICENSE](LICENSE) for details.
