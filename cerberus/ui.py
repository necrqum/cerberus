# cerberus/ui.py

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.logging import RichHandler
import logging

console = Console()

def setup_rich_logging(level=logging.INFO):
    """Sets up logging using RichHandler for beautiful console output."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)]
    )

def create_progress_bar():
    """Creates a standardized Rich progress bar for downloads."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True
    )

def print_header(text):
    """Prints a styled header."""
    console.print(f"\n[bold blue]===[/bold blue] [bold white]{text}[/bold white] [bold blue]===[/bold blue]\n")

def print_success(text):
    """Prints a success message."""
    console.print(f"[bold green]✔[/bold green] {text}")

def print_error(text):
    """Prints an error message."""
    console.print(f"[bold red]✘[/bold red] {text}")

def print_info(text):
    """Prints an informational message."""
    console.print(f"[bold cyan]ℹ[/bold cyan] {text}")
