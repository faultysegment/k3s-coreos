"""Controller for CoreOS ISO creation - handles console operations."""

import os
import subprocess
import tempfile
from typing import List
from pathlib import Path
from contextlib import contextmanager

try:
    from .models import ISOCreationConfig, CacheDirectoryManager
    from .views import BaseView
except ImportError:
    from models import ISOCreationConfig, CacheDirectoryManager
    from views import BaseView


class ConsoleController:
    """Controller that handles console operations and coordinates between model and view."""  # noqa: E501

    def __init__(self, view: BaseView):
        self.view = view
        self.config: ISOCreationConfig = ISOCreationConfig()

    @contextmanager
    def _temp_file(self, suffix='', prefix='', content=''):
        """Context manager for temporary files that auto-cleanup."""
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=str(self.config.temp_dir)
        )
        try:
            if content:
                with os.fdopen(temp_fd, 'w') as f:
                    f.write(content)
            else:
                os.close(temp_fd)
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

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

    @contextmanager
    def process_butane_template(self):
        """Process Butane template file with configuration variables, yields temp file path."""
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

        # Use context manager for temp file
        with self._temp_file(suffix='.bu', prefix='server-', content=processed_content) as temp_path:
            yield temp_path

    @contextmanager
    def _create_ignition_file(self):
        """Create temporary ignition file that auto-cleans up."""
        with self._temp_file(suffix='.ign', prefix='server-') as ignition_path:
            # Temporarily store the path in config for other methods to use
            old_ignition_file = self.config.ignition_file
            self.config.ignition_file = ignition_path
            try:
                yield ignition_path
            finally:
                # Restore original path
                self.config.ignition_file = old_ignition_file


    def download_base_iso(self) -> None:
        """Download base Fedora CoreOS ISO if needed."""
        if self.config.base_iso_exists:
            print(f"Base ISO already exists: {self.config.base_iso}")
            return

        self.view.show_step("Step 2", "Download base Fedora CoreOS ISO")

        cmd = ["coreos-installer", "download", "-f", "iso", "--decompress"]
        result = self.run_command(cmd, "Downloading Fedora CoreOS ISO")

        # Find downloaded file and rename to cache directory
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

            # Execute creation steps with ignition file in context manager
            with self._create_ignition_file() as ignition_file:
                # Step 1: Generate ignition file
                self.view.show_step("Step 1", "Generate Ignition file")
                with self.process_butane_template() as temp_butane_file:
                    # Convert Butane to Ignition
                    cmd = [
                        "butane",
                        "--pretty",
                        "--strict",
                        temp_butane_file,
                        "--output",
                        ignition_file,
                    ]
                    self.run_command(cmd, "Converting Butane to Ignition")

                    # Validate Ignition file
                    cmd = ["ignition-validate", ignition_file]
                    self.run_command(cmd, "Validating Ignition file")

                    print(f"✅ Ignition file created: {ignition_file}")
                    print()

                # Step 2: Download base ISO
                self.download_base_iso()

                # Step 3: Customize ISO (temporarily update config to use context manager's ignition file)
                old_ignition_file = self.config.ignition_file
                self.config.ignition_file = ignition_file
                try:
                    self.customize_iso()
                finally:
                    self.config.ignition_file = old_ignition_file

                # Show completion
                self.view.show_completion(self.config)

            # All temp files automatically cleaned up by context managers

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


