# 🐌 Snail Core

A system information collection and upload framework for Linux, inspired by [Red Hat's insights-core](https://github.com/RedHatInsights/insights-core).

Snail Core provides an extensible framework for gathering system diagnostics and uploading them to a custom endpoint.

## Status

**Currently in Development** - This is a minimal implementation.

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

## Quick Start

### Check Version

```bash
# Display version information
snail list-version
```

This will show:
- Snail Core version
- Python version

## CLI Usage

```bash
# Show help
snail --help

# Display version information
snail list-version

# Show version (alternative)
snail --version
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Format code
black src/

# Lint
ruff src/
```
