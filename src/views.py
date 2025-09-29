"""Views for CoreOS ISO creation - TUI and CLI interfaces."""

import sys
import subprocess
from typing import Optional, List
from abc import ABC, abstractmethod

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from .models import ISOCreationConfig, ButaneFileFinder, SSHKeyFinder
except ImportError:
    from models import ISOCreationConfig, ButaneFileFinder, SSHKeyFinder


class BaseView(ABC):
    """Abstract base class for views."""

    @abstractmethod
    def show_header(self) -> None:
        """Display application header."""
        pass

    @abstractmethod
    def configure_settings(self) -> ISOCreationConfig:
        """Configure and return ISO creation settings."""
        pass

    @abstractmethod
    def show_settings_summary(self, config: ISOCreationConfig) -> None:
        """Display settings summary."""
        pass

    @abstractmethod
    def confirm_proceed(self) -> bool:
        """Ask user to confirm proceeding with operation."""
        pass

    @abstractmethod
    def show_step(self, step: str, description: str) -> None:
        """Show current step being executed."""
        pass

    @abstractmethod
    def show_completion(self, config: ISOCreationConfig) -> None:
        """Show completion information."""
        pass

    @abstractmethod
    def show_error(self, error: str) -> None:
        """Show error message."""
        pass

    @abstractmethod
    def execute_with_progress(
        self, cmd: List[str], description: str
    ) -> subprocess.CompletedProcess:
        """Execute command with progress display appropriate for this view."""
        pass


class TUIView(BaseView):
    """Rich TUI view for interactive mode."""

    def __init__(self):
        if not RICH_AVAILABLE:
            raise ImportError(
                "Rich library is required for TUI mode. Install with: pip install rich"
            )
        self.console = Console()

    def show_header(self) -> None:
        """Display application header with rich formatting."""
        header = Panel(
            Text("CoreOS ISO Creator", justify="center", style="bold blue"),
            subtitle="Create custom Fedora CoreOS ISO images",
            border_style="blue",
        )
        self.console.print(header)
        self.console.print()

    def configure_settings(self) -> ISOCreationConfig:
        """Configure settings through interactive TUI."""
        self.console.print("[bold blue]Configuration[/bold blue]")

        config = ISOCreationConfig()

        # Configure SSH key
        config.ssh_key = self._configure_ssh_key()

        # Configure username
        config.username = Prompt.ask("Username for the system", default="user")

        # Configure hostname
        config.hostname = Prompt.ask("Hostname for the system")

        # Configure target disk
        config.install_disk = Prompt.ask(
            "Target disk for installation", default=config.install_disk
        )

        # Configure output file name
        default_iso = config.output_iso or "server.iso"
        config.output_iso = Prompt.ask("Output ISO filename", default=default_iso)

        # Auto-generate derived fields
        config.__post_init__()

        self.console.print()
        return config

    def _configure_ssh_key(self) -> str:
        """Configure SSH key with options for default keys."""
        ssh_info = SSHKeyFinder.get_ssh_info()

        if ssh_info["key_count"] == 0:
            self.console.print("[yellow]No SSH keys found in default locations[/yellow]")
            self.console.print(f"[dim]Looked in: {ssh_info['ssh_dir']}[/dim]")
            return Prompt.ask("SSH public key (paste the entire key)")

        # Show available keys
        self.console.print(f"[green]Found {ssh_info['key_count']} SSH key(s) in {ssh_info['ssh_dir']}[/green]")

        table = Table(title="Available SSH Keys")
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Key Preview", style="yellow")

        keys = ssh_info["available_keys"]
        key_list = list(keys.items())

        for i, (key_type, key_content) in enumerate(key_list, 1):
            # Show first 50 chars of key for preview
            preview = f"{key_content[:50]}..." if len(key_content) > 50 else key_content
            table.add_row(str(i), key_type.upper(), preview)

        table.add_row(str(len(key_list) + 1), "MANUAL", "Enter key manually")

        self.console.print(table)
        self.console.print()

        choices = [str(i) for i in range(1, len(key_list) + 2)]
        choice = Prompt.ask(
            "Select SSH key",
            choices=choices,
            default="1"
        )

        choice_idx = int(choice) - 1
        if choice_idx < len(key_list):
            # User selected a default key
            selected_key_type, selected_key = key_list[choice_idx]
            self.console.print(f"[green]Selected {selected_key_type.upper()} key[/green]")
            return selected_key
        else:
            # User chose manual entry
            return Prompt.ask("SSH public key (paste the entire key)")

    def show_settings_summary(self, config: ISOCreationConfig) -> None:
        """Display settings summary in a table, showing only user-provided settings."""
        table = Table(title="User Configuration", show_header=False)
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="yellow")

        # Only show SSH key if provided
        if config.ssh_key:
            ssh_display = f"{config.ssh_key[:20]}..." if len(config.ssh_key) > 20 else config.ssh_key
            table.add_row("SSH key", ssh_display)

        # Only show username if it's not the default
        if config.username != "user":
            table.add_row("Username", config.username)

        # Only show hostname if provided
        if config.hostname:
            table.add_row("Hostname", config.hostname)

        # Only show target disk if it's not the default
        if config.install_disk != "/dev/sda":
            table.add_row("Target disk", config.install_disk)

        # Only show output ISO if it's not the default
        if config.output_iso and config.output_iso != "server.iso":
            table.add_row("Output ISO", config.output_iso)

        # Only show base ISO if it's not the default
        if config.base_iso != "fedora-coreos.iso":
            table.add_row("Base ISO", config.base_iso)

        self.console.print(table)
        self.console.print()

    def confirm_proceed(self) -> bool:
        """Ask user to confirm proceeding."""
        return Confirm.ask("Proceed with ISO creation?", default=True)

    def show_step(self, step: str, description: str) -> None:
        """Show current step with rich formatting."""
        self.console.print(f"[bold blue]{step}[/bold blue]")

    def execute_with_progress(
        self, cmd: List[str], description: str
    ) -> subprocess.CompletedProcess:
        """Execute command with rich progress display."""

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task(description, total=None)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                progress.update(task, description=f"✅ {description}")
                return result
            except subprocess.CalledProcessError:
                progress.update(task, description=f"❌ {description}")
                raise

    def show_completion(self, config: ISOCreationConfig) -> None:
        """Show completion information with rich panel."""
        if not config.output_iso or not config.output_iso_exists:
            self.console.print("[red]❌ ISO file was not created[/red]")
            return

        file_info = ButaneFileFinder.get_file_info(config.output_iso)

        completion_panel = Panel(
            f"[green]✅ ISO file created successfully![/green]\n\n"
            f"[cyan]File:[/cyan] {config.output_iso}\n"
            f"[cyan]Size:[/cyan] {file_info['size_str']}\n"
            f"[cyan]Target disk:[/cyan] {config.install_disk}\n\n"
            f"[yellow]You can now use this ISO to boot and install CoreOS.[/yellow]",
            title="🎉 Completed",
            border_style="green",
        )
        self.console.print(completion_panel)

    def show_error(self, error: str) -> None:
        """Show error message with rich formatting."""
        self.console.print(f"[red]Error: {error}[/red]")


