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
import threading

console = Console()
interaction_lock = threading.Lock()
print_lock = threading.Lock()

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
        TextColumn(" [bold blue]{task.fields[threads]}[/bold blue]"),
        console=console,
        transient=True
    )

def ask_for_name(original_title):
    """
    Interactively asks the user for a custom filename.
    Thread-safe and manages progress bar state.
    """
    from .adapters.ytdlp import stop_progress_bar, get_progress_bar
    
    with interaction_lock:
        # Hide progress bar if active
        stop_progress_bar()
        
        console.print(f"\n[bold yellow]Interactive Naming[/bold yellow]")
        console.print(f"Original Title: [cyan]{original_title}[/cyan]")
        
        try:
            custom = input("Enter custom name (Leave blank to keep original): ").strip()
        except EOFError:
            custom = ""
            
        # Resume progress bar (it will be recreated on next update)
        return custom if custom else None

def print_header(text):
    """Prints a styled header."""
    with print_lock:
        console.print(f"\n[bold blue]===[/bold blue] [bold white]{text}[/bold white] [bold blue]===[/bold blue]\n")

def print_success(text):
    """Prints a success message."""
    with print_lock:
        console.print(f"[bold green]✔[/bold green] {text}")

def print_error(text):
    """Prints an error message."""
    with print_lock:
        console.print(f"[bold red]✘[/bold red] {text}")

def print_info(text):
    """Prints an informational message."""
    with print_lock:
        console.print(f"[bold cyan]ℹ[/bold cyan] {text}")
