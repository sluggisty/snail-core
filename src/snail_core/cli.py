"""
Command-line interface for Snail Core.

Provides commands for version information.
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from snail_core import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="snail-core")
def main() -> None:
    """
    Snail Core - System information collection for Linux.
    
    Collect system diagnostics and optionally upload to a remote server.
    """
    pass


@main.command("list-version")
def list_version() -> None:
    """Display version information for Snail Core."""
    console.print()
    console.print(Panel.fit(
        f"[bold blue]Snail Core[/]\n"
        f"Version: [cyan]{__version__}[/]",
        border_style="blue",
        title="Version Information",
    ))
    console.print()
    
    # Create a table with version details
    table = Table(show_header=False, box=None)
    table.add_column("Component", style="dim", width=20)
    table.add_column("Version", style="cyan")
    
    table.add_row("Snail Core", __version__)
    table.add_row("Python", f"{__import__('sys').version.split()[0]}")
    
    console.print(table)
    console.print()


if __name__ == "__main__":
    main()

