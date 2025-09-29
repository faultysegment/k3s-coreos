"""Controller for CoreOS ISO creation - handles console operations."""

import os
import subprocess
from typing import List
from pathlib import Path

try:
    from .models import ISOCreationConfig
    from .views import BaseView
except ImportError:
    from models import ISOCreationConfig
    from views import BaseView


class ConsoleController:
    """Controller that handles console operations and coordinates between model and view."""  # noqa: E501

    def __init__(self, view: BaseView):
        self.view = view
        self.config: ISOCreationConfig = ISOCreationConfig()

    def run_command(
        self, cmd: List[str], description: str
    ) -> subprocess.CompletedProcess:
        """Execute a console command with error handling."""
        try:
            # Delegate progress display to view
            return self.view.execute_with_progress(cmd, description)

        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed: {' '.join(cmd)}\nReturn code: {e.returncode}"
            if e.stdout:
                error_msg += f"\nSTDOUT: {e.stdout}"
            if e.stderr:
                error_msg += f"\nSTDERR: {e.stderr}"

            self.view.show_error(error_msg)
            raise

    def process_butane_template(self) -> str:
        """Process Butane template file with configuration variables."""
        # Get template from resources
        try:
            # Try to get from package resources first
            from . import resources
            template_path = Path(__file__).parent / "resources" / "server.bu"
        except ImportError:
            # Fallback for direct script execution
            template_path = Path(__file__).parent / "resources" / "server.bu"

        if not template_path.exists():
            raise ValueError(f"Template file not found: {template_path}")

        # Read template file
        with open(template_path, 'r') as f:
            template_content = f.read()

        # Replace template variables
        processed_content = template_content.replace('{{SSH_KEY}}', self.config.ssh_key)
        processed_content = processed_content.replace('{{HOSTNAME}}', self.config.hostname)
        processed_content = processed_content.replace('{{USERNAME}}', self.config.username)

        # Create temporary butane file
        temp_butane_file = "server.processed.bu"
        with open(temp_butane_file, 'w') as f:
            f.write(processed_content)

        return temp_butane_file

    def generate_ignition(self) -> None:
        """Generate Ignition file from Butane configuration."""
        self.view.show_step("Step 1", "Generate Ignition file")

        if not self.config.ignition_file:
            raise ValueError("Ignition file not configured")

        # Process template to create temporary butane file
        temp_butane_file = self.process_butane_template()

        try:
            # Convert Butane to Ignition
            cmd = [
                "butane",
                "--pretty",
                "--strict",
                temp_butane_file,
                "--output",
                self.config.ignition_file,
            ]
            self.run_command(cmd, "Converting Butane to Ignition")

            # Validate Ignition file
            cmd = ["ignition-validate", self.config.ignition_file]
            self.run_command(cmd, "Validating Ignition file")

            print(f"✅ Ignition file created: {self.config.ignition_file}")
            print()
        finally:
            # Clean up temporary file
            if os.path.exists(temp_butane_file):
                os.remove(temp_butane_file)

    def download_base_iso(self) -> None:
        """Download base Fedora CoreOS ISO if needed."""
        if self.config.base_iso_exists:
            print(f"Base ISO already exists: {self.config.base_iso}")
            return

        self.view.show_step("Step 2", "Download base Fedora CoreOS ISO")

        cmd = ["coreos-installer", "download", "-f", "iso", "--decompress"]
        result = self.run_command(cmd, "Downloading Fedora CoreOS ISO")

        # Find downloaded file and rename
        downloaded_iso = result.stdout.strip()
        if downloaded_iso and os.path.exists(downloaded_iso):
            os.rename(downloaded_iso, self.config.base_iso)

        print(f"✅ Base ISO ready: {self.config.base_iso}")
        print()

    def customize_iso(self) -> None:
        """Embed Ignition configuration into ISO."""
        self.view.show_step("Step 3", "Create custom ISO")

        if not all(
            [
                self.config.ignition_file,
                self.config.output_iso,
                self.config.install_disk,
                self.config.base_iso,
            ]
        ):
            raise ValueError("Missing required configuration for ISO customization")

        # Remove existing output file
        if self.config.output_iso_exists and self.config.output_iso:
            os.remove(self.config.output_iso)
            print(f"Removed existing file: {self.config.output_iso}")

        if not all([self.config.ignition_file, self.config.output_iso]):
            raise ValueError("Required file paths are not configured")

        cmd = [
            "coreos-installer",
            "iso",
            "customize",
            "--dest-ignition",
            self.config.ignition_file,
            "--dest-device",
            self.config.install_disk,
            "-o",
            self.config.output_iso,
            self.config.base_iso,
        ]
        self.run_command(cmd, "Embedding Ignition into ISO")

        print(f"🎉 Custom ISO created: {self.config.output_iso}")
        print()

    def create_iso(self) -> None:
        """Main method to create ISO with full process."""
        try:
            # Configure settings through view
            self.config = self.view.configure_settings()

            # Validate configuration
            errors = self.config.validate()
            if errors:
                for error in errors:
                    self.view.show_error(error)
                return

            # Show settings summary
            self.view.show_settings_summary(self.config)

            # Confirm proceed
            if not self.view.confirm_proceed():
                print("Operation cancelled by user")
                return

            print()

            # Execute creation steps
            self.generate_ignition()
            self.download_base_iso()
            self.customize_iso()

            # Show completion
            self.view.show_completion(self.config)

        except KeyboardInterrupt:
            print("\nOperation interrupted by user")
            raise
        except Exception as e:
            self.view.show_error(str(e))
            raise


class InteractiveController(ConsoleController):
    """Controller for interactive mode with full TUI experience."""

    def run(self) -> None:
        """Run interactive mode."""
        self.view.show_header()
        self.create_iso()


