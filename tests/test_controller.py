"""Unit tests for controller module."""

import unittest
import tempfile
import subprocess
from unittest.mock import Mock, patch, call, mock_open
from pathlib import Path

from src.controller import ConsoleController, InteractiveController
from src.models import ISOCreationConfig


class TestConsoleController(unittest.TestCase):
    """Test cases for ConsoleController class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_view = Mock()
        self.controller = ConsoleController(self.mock_view)
        self.valid_config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host",
            hostname="test-host",
            username="testuser"
        )
        self.controller.config = self.valid_config

    def test_run_command_success(self):
        """Test successful command execution."""
        mock_result = Mock()
        mock_result.stdout = "Success output"
        mock_result.stderr = ""
        mock_result.returncode = 0

        self.mock_view.execute_with_progress.return_value = mock_result

        result = self.controller.run_command(["echo", "test"], "Test command")

        self.mock_view.execute_with_progress.assert_called_once_with(
            ["echo", "test"], "Test command"
        )
        self.assertEqual(result, mock_result)

    def test_run_command_failure(self):
        """Test command execution failure handling."""
        error = subprocess.CalledProcessError(1, ["false"], "Error output", "Error stderr")
        self.mock_view.execute_with_progress.side_effect = error

        with self.assertRaises(subprocess.CalledProcessError):
            self.controller.run_command(["false"], "Failing command")

        self.mock_view.show_error.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data="template content {{SSH_KEY}} {{HOSTNAME}} {{USERNAME}}")
    @patch('pathlib.Path.exists', return_value=True)
    def test_process_butane_template(self, mock_exists, mock_file):
        """Test Butane template processing."""
        temp_file = self.controller.process_butane_template()

        # Verify template file was read
        mock_file.assert_any_call(Path(__file__).parent.parent / "src" / "resources" / "server.bu", 'r')

        # Verify processed file was written
        expected_content = "template content ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host test-host testuser"
        mock_file.assert_any_call("server.processed.bu", 'w')

        # Get the write calls
        write_calls = [call for call in mock_file().write.call_args_list]
        self.assertTrue(any("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host" in str(call) for call in write_calls))
        self.assertTrue(any("test-host" in str(call) for call in write_calls))
        self.assertTrue(any("testuser" in str(call) for call in write_calls))

        self.assertEqual(temp_file, "server.processed.bu")

    @patch('pathlib.Path.exists', return_value=False)
    def test_process_butane_template_missing_file(self, mock_exists):
        """Test template processing with missing template file."""
        with self.assertRaises(ValueError) as context:
            self.controller.process_butane_template()

        self.assertIn("Template file not found", str(context.exception))

    @patch('os.remove')
    @patch('os.path.exists', return_value=True)
    def test_generate_ignition_success(self, mock_exists, mock_remove):
        """Test successful Ignition file generation."""
        # Mock successful command execution
        mock_result = Mock()
        mock_result.returncode = 0
        self.mock_view.execute_with_progress.return_value = mock_result

        self.controller.generate_ignition()

        # Verify steps were called
        self.mock_view.show_step.assert_called_with("Step 1", "Generate Ignition file")

        # Verify butane and validation commands were run
        expected_calls = [
            call(["butane", "--pretty", "--strict", "server.processed.bu", "--output", "server.ign"],
                 "Converting Butane to Ignition"),
            call(["ignition-validate", "server.ign"], "Validating Ignition file")
        ]
        self.mock_view.execute_with_progress.assert_has_calls(expected_calls)

        # Verify cleanup
        mock_remove.assert_called_once_with("server.processed.bu")

    @patch.object(ConsoleController, 'process_butane_template')
    @patch('os.remove')
    @patch('os.path.exists', return_value=True)
    def test_generate_ignition_cleanup_on_error(self, mock_exists, mock_remove, mock_process_template):
        """Test cleanup happens even when generation fails."""
        mock_process_template.return_value = "temp.processed.bu"
        self.mock_view.execute_with_progress.side_effect = subprocess.CalledProcessError(1, ["butane"])

        with self.assertRaises(subprocess.CalledProcessError):
            self.controller.generate_ignition()

        # Verify cleanup still happened
        mock_remove.assert_called_once_with("temp.processed.bu")

    def test_download_base_iso_exists(self):
        """Test base ISO download when file already exists."""
        with patch('os.path.exists', return_value=True):
            self.controller.download_base_iso()

            # Should not attempt download
            self.mock_view.execute_with_progress.assert_not_called()

    @patch('os.rename')
    def test_download_base_iso_success(self, mock_rename):
        """Test successful base ISO download."""
        with patch('os.path.exists') as mock_exists:
            # First call (checking base_iso_exists) returns False, second call (checking downloaded file) returns True
            mock_exists.side_effect = [False, True]
            mock_result = Mock()
            mock_result.stdout = "downloaded-file.iso"
            self.mock_view.execute_with_progress.return_value = mock_result

            self.controller.download_base_iso()

            self.mock_view.show_step.assert_called_with("Step 2", "Download base Fedora CoreOS ISO")
            self.mock_view.execute_with_progress.assert_called_once_with(
                ["coreos-installer", "download", "-f", "iso", "--decompress"],
                "Downloading Fedora CoreOS ISO"
            )
            mock_rename.assert_called_once_with("downloaded-file.iso", "fedora-coreos.iso")

    @patch('os.remove')
    def test_customize_iso_remove_existing(self, mock_remove):
        """Test ISO customization removes existing output file."""
        with patch('os.path.exists', return_value=True):
            mock_result = Mock()
            self.mock_view.execute_with_progress.return_value = mock_result

            self.controller.customize_iso()

            mock_remove.assert_called_once_with("server.iso")

    def test_customize_iso_success(self):
        """Test successful ISO customization."""
        with patch('os.path.exists', return_value=False):
            mock_result = Mock()
            self.mock_view.execute_with_progress.return_value = mock_result

            self.controller.customize_iso()

            self.mock_view.show_step.assert_called_with("Step 3", "Create custom ISO")
            expected_cmd = [
                "coreos-installer", "iso", "customize",
                "--dest-ignition", "server.ign",
                "--dest-device", "/dev/sda",
                "-o", "server.iso",
                "fedora-coreos.iso"
            ]
            self.mock_view.execute_with_progress.assert_called_once_with(
                expected_cmd, "Embedding Ignition into ISO"
            )

    def test_customize_iso_missing_config(self):
        """Test ISO customization with missing configuration."""
        self.controller.config.ignition_file = None

        with self.assertRaises(ValueError) as context:
            self.controller.customize_iso()

        self.assertIn("Missing required configuration", str(context.exception))

    @patch.object(ConsoleController, 'generate_ignition')
    @patch.object(ConsoleController, 'download_base_iso')
    @patch.object(ConsoleController, 'customize_iso')
    def test_create_iso_success(self, mock_customize, mock_download, mock_generate):
        """Test successful full ISO creation process."""
        self.mock_view.configure_settings.return_value = self.valid_config
        self.mock_view.confirm_proceed.return_value = True

        self.controller.create_iso()

        # Verify all steps were called in order
        self.mock_view.configure_settings.assert_called_once()
        self.mock_view.show_settings_summary.assert_called_once_with(self.valid_config)
        self.mock_view.confirm_proceed.assert_called_once()
        mock_generate.assert_called_once()
        mock_download.assert_called_once()
        mock_customize.assert_called_once()
        self.mock_view.show_completion.assert_called_once_with(self.valid_config)

    def test_create_iso_validation_failure(self):
        """Test ISO creation with validation errors."""
        invalid_config = ISOCreationConfig()  # Missing required fields
        self.mock_view.configure_settings.return_value = invalid_config

        self.controller.create_iso()

        # Should show errors and not proceed
        self.mock_view.show_error.assert_called()
        self.mock_view.confirm_proceed.assert_not_called()

    @patch.object(ConsoleController, 'generate_ignition')
    def test_create_iso_user_cancellation(self, mock_generate):
        """Test ISO creation when user cancels."""
        self.mock_view.configure_settings.return_value = self.valid_config
        self.mock_view.confirm_proceed.return_value = False

        self.controller.create_iso()

        # Should not proceed with creation
        mock_generate.assert_not_called()

    def test_create_iso_keyboard_interrupt(self):
        """Test ISO creation handles keyboard interrupt."""
        self.mock_view.configure_settings.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.controller.create_iso()

    def test_create_iso_exception_handling(self):
        """Test ISO creation handles general exceptions."""
        self.mock_view.configure_settings.side_effect = Exception("Test error")

        with self.assertRaises(Exception):
            self.controller.create_iso()

        self.mock_view.show_error.assert_called_with("Test error")


class TestInteractiveController(unittest.TestCase):
    """Test cases for InteractiveController class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_view = Mock()
        self.controller = InteractiveController(self.mock_view)

    @patch.object(ConsoleController, 'create_iso')
    def test_run(self, mock_create_iso):
        """Test interactive controller run method."""
        self.controller.run()

        self.mock_view.show_header.assert_called_once()
        mock_create_iso.assert_called_once()


if __name__ == '__main__':
    unittest.main()