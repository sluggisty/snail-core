"""
Command-line interface for Snail Core.

Provides commands for collecting system information and uploading to a server.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from snail_core import __version__
from snail_core.config import Config
from snail_core.core import SnailCore

console = Console()


def setup_logging(level: str) -> None:
    """Configure logging with rich handler."""
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.version_option(version=__version__, prog_name="snail-core")
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "-V",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.pass_context
def main(ctx: click.Context, config: Path | None, verbose: bool) -> None:
    """
    Snail Core - System information collection for Linux.

    Collect system diagnostics and optionally upload to a remote server.
    """
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        ctx.obj["config"] = Config.load(config)
    else:
        ctx.obj["config"] = Config.load()

    # Set log level
    log_level = "DEBUG" if verbose else ctx.obj["config"].log_level
    setup_logging(log_level)
    ctx.obj["verbose"] = verbose


@main.command()
@click.option(
    "--collectors",
    "-C",
    multiple=True,
    help="Specific collectors to run (can be repeated)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write output to file instead of stdout",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "pretty"]),
    default="pretty",
    help="Output format",
)
@click.option(
    "--upload/--no-upload",
    default=False,
    help="Upload results to configured server",
)
@click.pass_context
def collect(
    ctx: click.Context,
    collectors: tuple[str, ...],
    output: Path | None,
    format: str,
    upload: bool,
) -> None:
    """
    Collect system information.

    By default, runs all collectors and displays results. Use --collectors
    to run specific collectors only.
    """
    config: Config = ctx.obj["config"]
    core = SnailCore(config)

    collector_list = list(collectors) if collectors else None

    # Show what we're doing
    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]Snail Core v{__version__}[/]\nCollecting system information...",
            border_style="blue",
        )
    )
    console.print()

    # Run collection with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running collectors...", total=None)
        report = core.collect(collector_list)
        progress.update(task, completed=True)

    # Show summary
    _display_summary(report)

    # Handle upload
    if upload:
        if not config.upload_url:
            console.print("[yellow]Warning: No upload URL configured. Skipping upload.[/]")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Uploading to {config.upload_url}...", total=None)
                try:
                    response = core.upload(report)
                    progress.update(task, completed=True)
                    console.print("[green]✓ Upload successful[/]")
                    if ctx.obj["verbose"]:
                        console.print(f"  Response: {response}")
                except Exception as e:
                    progress.update(task, completed=True)
                    console.print(f"[red]✗ Upload failed: {e}[/]")

    # Handle output
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.to_json())
        console.print(f"\n[dim]Report saved to: {output}[/]")
    elif format == "json":
        console.print()
        console.print_json(report.to_json())


def _display_summary(report) -> None:
    """Display a summary table of collection results."""
    table = Table(title="Collection Results", show_header=True)
    table.add_column("Collector", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Items", justify="right")

    for name, data in report.results.items():
        status = "[green]✓[/]"

        # Count items in the data
        if isinstance(data, dict):
            item_count = str(len(data))
        elif isinstance(data, list):
            item_count = str(len(data))
        else:
            item_count = "1"

        table.add_row(name, status, item_count)

    # Show errors
    for error in report.errors:
        # Extract collector name from error message
        if "Collector '" in error:
            name = error.split("'")[1]
        else:
            name = "unknown"
        table.add_row(name, "[red]✗[/]", "-")

    console.print(table)

    if report.errors:
        console.print()
        console.print("[yellow]Errors:[/]")
        for error in report.errors:
            console.print(f"  • {error}")


@main.command("list")
def list_available() -> None:
    """List all available collectors."""
    table = Table(title="Available Collectors", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    from snail_core.collectors import COLLECTORS

    for name, cls in COLLECTORS.items():
        table.add_row(name, cls.description)

    console.print()
    console.print(table)


@main.command("version", short_help="Display version information")
def version() -> None:
    """Display version information for Snail Core."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]Snail Core[/]\nVersion: [cyan]{__version__}[/]",
            border_style="blue",
            title="Version Information",
        )
    )
    console.print()

    # Create a table with version details
    table = Table(show_header=False, box=None)
    table.add_column("Component", style="dim", width=20)
    table.add_column("Version", style="cyan")

    table.add_row("Snail Core", __version__)
    table.add_row("Python", f"{__import__('sys').version.split()[0]}")

    console.print(table)
    console.print()


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current configuration and connection status."""
    config: Config = ctx.obj["config"]

    console.print()
    console.print(
        Panel.fit(
            "[bold]Snail Core Status[/]",
            border_style="blue",
        )
    )

    # Configuration
    table = Table(show_header=False, box=None)
    table.add_column("Setting", style="dim")
    table.add_column("Value")

    table.add_row("Upload URL", config.upload_url or "[dim]Not configured[/]")
    table.add_row("Upload Enabled", "Yes" if config.upload_enabled else "No")
    table.add_row("API Key", "Configured" if config.api_key else "[dim]Not set[/]")
    table.add_row("Client Cert", config.auth_cert_path or "[dim]Not set[/]")
    table.add_row("Output Dir", config.output_dir)
    table.add_row("Log Level", config.log_level)

    console.print(table)

    # Test connection
    if config.upload_url:
        console.print()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Testing connection...", total=None)
            from snail_core.uploader import Uploader

            uploader = Uploader(config)
            connected = uploader.test_connection()
            progress.update(task, completed=True)

        if connected:
            console.print("[green]✓ Server is reachable[/]")
        else:
            console.print("[red]✗ Server is not reachable[/]")


@main.command()
@click.argument("output_path", type=click.Path(path_type=Path))
@click.pass_context
def init_config(ctx: click.Context, output_path: Path) -> None:
    """
    Generate a sample configuration file.

    Creates a YAML configuration file with all available options
    and helpful comments.
    """
    sample_config = """# Snail Core Configuration
# See documentation for full options

# Upload settings
upload:
  # URL to upload collected data to
  url: https://your-server.example.com/api/v1/ingest

  # Enable/disable automatic upload
  enabled: true

  # Request timeout in seconds
  timeout: 30

  # Number of retry attempts
  retries: 3

# Authentication (choose one method)
auth:
  # API key authentication
  api_key: null  # Set via SNAIL_API_KEY env var for security

  # Mutual TLS (client certificate)
  cert_path: null  # /path/to/client.crt
  key_path: null   # /path/to/client.key

# Collection settings
collection:
  # Specific collectors to enable (empty = all)
  enabled_collectors: []

  # Collectors to disable
  disabled_collectors: []

  # Collection timeout in seconds
  timeout: 300

# Output settings
output:
  # Directory for local report copies
  dir: /var/lib/snail-core

  # Keep local copy after upload
  keep_local: false

  # Compress output data
  compress: true

# Logging
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR
  level: INFO

  # Log file path (null = stderr only)
  file: null

# Privacy settings
privacy:
  # Anonymize hostnames in reports
  anonymize_hostnames: false

  # Redact password-like values
  redact_passwords: true

  # Paths to exclude from collection
  exclude_paths: []
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sample_config)
    console.print(f"[green]✓ Configuration file created: {output_path}[/]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Edit the configuration file with your server URL")
    console.print("  2. Set your API key: [cyan]export SNAIL_API_KEY=your-key[/]")
    console.print("  3. Run collection: [cyan]snail collect --upload[/]")


@main.command("host-id")
@click.option(
    "--reset",
    is_flag=True,
    help="Reset the host ID (generates a new UUID)",
)
@click.pass_context
def host_id(ctx: click.Context, reset: bool) -> None:
    """
    Display or reset the persistent host ID.

    The host ID is a UUID that uniquely identifies this system across all
    collections. It is stored persistently and reused for all uploads.
    """
    from snail_core.host_id import get_host_id, reset_host_id

    config: Config = ctx.obj["config"]

    if reset:
        if not click.confirm(
            "⚠️  Resetting the host ID will make this system appear as a new host "
            "to the server. Continue?"
        ):
            console.print("[yellow]Cancelled[/]")
            return

        new_id = reset_host_id(config.output_dir)
        console.print(f"[green]✓[/] Host ID reset to: [cyan]{new_id}[/]")
        console.print("[dim]This system will now appear as a new host to the server.[/]")
    else:
        host_id_value = get_host_id(config.output_dir)
        console.print(f"[bold]Host ID:[/] [cyan]{host_id_value}[/]")
        console.print("[dim]This UUID uniquely identifies this system across all collections.[/]")


@main.command("run")
@click.option(
    "--collectors",
    "-C",
    multiple=True,
    help="Specific collectors to run",
)
@click.pass_context
def run_and_upload(ctx: click.Context, collectors: tuple[str, ...]) -> None:
    """
    Collect and upload in one command.

    Convenience command that runs collection and uploads to the
    configured server.
    """
    config: Config = ctx.obj["config"]

    if not config.upload_url:
        console.print("[red]Error: No upload URL configured.[/]")
        console.print("Set SNAIL_UPLOAD_URL or configure in config file.")
        sys.exit(1)

    # Invoke collect with upload flag
    ctx.invoke(
        collect,
        collectors=collectors,
        output=None,
        format="pretty",
        upload=True,
    )


if __name__ == "__main__":
    main()
