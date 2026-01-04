"""
Snail Core - System information collection and upload framework for Linux.

A modular framework for collecting system diagnostics and uploading them
to a custom endpoint, inspired by Red Hat's insights-core.
"""

__version__ = "0.5.4"
__author__ = "Sluggisty"

# Import main modules to make them available as package attributes
from . import cli, collectors, config, core, uploader

__all__ = ["__version__", "cli", "collectors", "config", "core", "uploader"]
