"""Unit tests for controller module."""

import unittest
import tempfile
import subprocess
from unittest.mock import Mock, patch, call, mock_open
from pathlib import Path

from src.controller import ConsoleController, InteractiveController
from src.models import ISOCreationConfig, CacheDirectoryManager


class TestConsoleController(unittest.TestCase):
    """Test cases for ConsoleController class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_view = Mock()
        self.controller = ConsoleController(self.mock_view)
        self.valid_config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host",
            hostname="test-host",
            username="testuser",
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
        error = subprocess.CalledProcessError(
            1, ["false"], "Error output", "Error stderr"
        )
        self.mock_view.execute_with_progress.side_effect = error

        with self.assertRaises(subprocess.CalledProcessError):
            self.controller.run_command(["false"], "Failing command")

        self.mock_view.show_error.assert_called_once()

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="template content {{SSH_KEY}} {{HOSTNAME}} {{USERNAME}}",
    )
    @patch("pathlib.Path.exists", return_value=True)
    @patch("tempfile.mkstemp")
    @patch("os.fdopen")
    def test_process_butane_template(
        self, mock_fdopen, mock_mkstemp, mock_exists, mock_file
    ):
        """Test Butane template processing with context manager."""
        mock_mkstemp.return_value = (123, "/tmp/server-abc123.bu")
        mock_write_file = Mock()
        mock_fdopen.return_value.__enter__.return_value = mock_write_file

        # Test the context manager
        with self.controller.process_butane_template() as temp_file:
            # Verify template file was read
            mock_file.assert_any_call(
                Path(__file__).parent.parent / "src" / "resources" / "server.bu", "r"
            )

            # Verify temporary file was created
            mock_mkstemp.assert_called_once()

            # Check that temp file path is returned
            self.assertEqual(temp_file, "/tmp/server-abc123.bu")

        # Verify template content processing
        expected_content = "template content ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host test-host testuser"
        mock_write_file.write.assert_called_once_with(expected_content)

    @patch("pathlib.Path.exists", return_value=False)
    def test_process_butane_template_missing_file(self, mock_exists):
        """Test template processing with missing template file."""
        with self.assertRaises(ValueError) as context:
            with self.controller.process_butane_template():
                pass

        self.assertIn("Template file not found", str(context.exception))

    @patch("tempfile.mkstemp")
    @patch("os.remove")
    @patch("os.path.exists", return_value=True)
    @patch("os.fdopen")
    @patch("os.close")
    def test_temp_file_context_manager(
        self, mock_close, mock_fdopen, mock_exists, mock_remove, mock_mkstemp
    ):
        """Test temporary file context manager."""
        mock_mkstemp.return_value = (123, "/tmp/test-abc123.temp")
        mock_write_file = Mock()
        mock_fdopen.return_value.__enter__.return_value = mock_write_file
        mock_fdopen.return_value.__exit__.return_value = None

        with self.controller._temp_file(
            suffix=".test", prefix="demo-", content="test content"
        ) as temp_file:
            self.assertEqual(temp_file, "/tmp/test-abc123.temp")
            mock_mkstemp.assert_called_once_with(
                suffix=".test", prefix="demo-", dir=str(self.controller.config.temp_dir)
            )

        # Verify content was written
        mock_fdopen.assert_called_once_with(123, "w")
        mock_write_file.write.assert_called_once_with("test content")

        # Verify cleanup happened
        mock_remove.assert_called_once_with("/tmp/test-abc123.temp")

    @patch("tempfile.mkstemp")
    @patch("os.close")
    @patch("os.remove")
    @patch("os.path.exists", return_value=True)
    def test_create_ignition_file_context_manager(
        self, mock_exists, mock_remove, mock_close, mock_mkstemp
    ):
        """Test ignition file context manager."""
        mock_mkstemp.return_value = (123, "/tmp/server-abc123.ign")
        original_ignition_file = self.controller.config.ignition_file

        with self.controller._create_ignition_file() as ignition_file:
            self.assertEqual(ignition_file, "/tmp/server-abc123.ign")
            self.assertEqual(
                self.controller.config.ignition_file, "/tmp/server-abc123.ign"
            )

        # Verify original config is restored
        self.assertEqual(self.controller.config.ignition_file, original_ignition_file)
        # Verify cleanup happened
        mock_remove.assert_called_once_with("/tmp/server-abc123.ign")

    @patch("tempfile.mkstemp")
    @patch("os.remove")
    @patch("os.close")
    @patch("os.path.exists", return_value=True)
    def test_temp_file_cleanup_on_exception(
        self, mock_exists, mock_close, mock_remove, mock_mkstemp
    ):
        """Test that temp files are cleaned up even when exceptions occur."""
        mock_mkstemp.return_value = (123, "/tmp/server-abc123.temp")

        # Simulate exception inside context manager
        with self.assertRaises(ValueError):
            with self.controller._temp_file(
                suffix=".test", prefix="demo-"
            ) as temp_file:
                raise ValueError("Test exception")

        # Verify cleanup still happened despite exception
        mock_remove.assert_called_once_with("/tmp/server-abc123.temp")

    @patch("tempfile.mkstemp")
    @patch("os.remove")
    @patch("os.fdopen")
    def test_temp_file_with_content_write_failure(
        self, mock_fdopen, mock_remove, mock_mkstemp
    ):
        """Test temp file cleanup when content write fails."""
        mock_mkstemp.return_value = (123, "/tmp/server-abc123.temp")
        mock_fdopen.side_effect = IOError("Write failed")

        # The IOError occurs during context manager setup, so no cleanup is expected in finally block
        # Instead, the exception handling in the controller should clean up
        with self.assertRaises(IOError):
            with self.controller._temp_file(
                suffix=".test", content="test"
            ) as temp_file:
                pass

        # No remove call expected since the exception happens during file creation
        mock_remove.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data="template {{SSH_KEY}}")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("tempfile.mkstemp")
    @patch("os.remove")
    @patch("os.fdopen")
    @patch("os.path.exists", return_value=True)
    def test_process_butane_template_auto_cleanup(
        self,
        mock_path_exists,
        mock_fdopen,
        mock_remove,
        mock_mkstemp,
        mock_exists,
        mock_file,
    ):
        """Test that Butane template files are auto-cleaned up."""
        mock_mkstemp.return_value = (123, "/tmp/server-abc123.bu")
        mock_write_file = Mock()
        mock_fdopen.return_value.__enter__.return_value = mock_write_file

        # Use context manager and verify cleanup
        with self.controller.process_butane_template() as temp_file:
            self.assertEqual(temp_file, "/tmp/server-abc123.bu")

        # Verify file was cleaned up after context exit
        mock_remove.assert_called_once_with("/tmp/server-abc123.bu")

    def test_download_base_iso_exists(self):
        """Test base ISO download when file already exists."""
        with patch("os.path.exists", return_value=True):
            self.controller.download_base_iso()

            # Should not attempt download
            self.mock_view.execute_with_progress.assert_not_called()

    @patch("os.rename")
    def test_download_base_iso_success(self, mock_rename):
        """Test successful base ISO download."""
        with patch("os.path.exists") as mock_exists:
            # First call (checking base_iso_exists) returns False, second call (checking downloaded file) returns True
            mock_exists.side_effect = [False, True]
            mock_result = Mock()
            mock_result.stdout = "downloaded-file.iso"
            self.mock_view.execute_with_progress.return_value = mock_result

            self.controller.download_base_iso()

            self.mock_view.show_step.assert_called_with(
                "Step 2", "Download base Fedora CoreOS ISO"
            )
            self.mock_view.execute_with_progress.assert_called_once_with(
                ["coreos-installer", "download", "-f", "iso", "--decompress"],
                "Downloading Fedora CoreOS ISO",
            )
            mock_rename.assert_called_once_with(
                "downloaded-file.iso", str(self.valid_config.base_iso)
            )

    @patch("os.remove")
    def test_customize_iso_remove_existing(self, mock_remove):
        """Test ISO customization removes existing output file."""
        with patch("os.path.exists", return_value=True):
            mock_result = Mock()
            self.mock_view.execute_with_progress.return_value = mock_result

            self.controller.customize_iso()

            mock_remove.assert_called_once_with("server.iso")

    def test_customize_iso_success(self):
        """Test successful ISO customization."""
        with patch("os.path.exists", return_value=False):
            mock_result = Mock()
            self.mock_view.execute_with_progress.return_value = mock_result

            self.controller.customize_iso()

            self.mock_view.show_step.assert_called_with("Step 3", "Create custom ISO")
            expected_cmd = [
                "coreos-installer",
                "iso",
                "customize",
                "--dest-ignition",
                self.valid_config.ignition_file,
                "--dest-device",
                "/dev/sda",
                "-o",
                "server.iso",
                str(self.valid_config.base_iso),
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

    @patch.object(ConsoleController, "download_base_iso")
    @patch.object(ConsoleController, "customize_iso")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="template {{SSH_KEY}} {{HOSTNAME}} {{USERNAME}}",
    )
    @patch("pathlib.Path.exists", return_value=True)
    @patch("tempfile.mkstemp")
    @patch("os.fdopen")
    @patch("os.close")
    @patch("os.remove")
    def test_create_iso_success(
        self,
        mock_remove,
        mock_close,
        mock_fdopen,
        mock_mkstemp,
        mock_path_exists,
        mock_open_file,
        mock_customize,
        mock_download,
    ):
        """Test successful full ISO creation process with context managers."""
        # Setup mocks
        mock_mkstemp.side_effect = [
            (123, "/tmp/server-abc.ign"),
            (124, "/tmp/server-def.bu"),
        ]
        mock_write_file = Mock()
        mock_fdopen.return_value.__enter__.return_value = mock_write_file

        self.mock_view.configure_settings.return_value = self.valid_config
        self.mock_view.confirm_proceed.return_value = True

        # Mock successful butane and validation commands
        mock_result = Mock()
        mock_result.returncode = 0
        self.mock_view.execute_with_progress.return_value = mock_result

        self.controller.create_iso()

        # Verify all steps were called in order
        self.mock_view.configure_settings.assert_called_once()
        self.mock_view.show_settings_summary.assert_called_once_with(self.valid_config)
        self.mock_view.confirm_proceed.assert_called_once()

        # Verify butane and validation commands were called
        expected_calls = [
            call(
                [
                    "butane",
                    "--pretty",
                    "--strict",
                    "/tmp/server-def.bu",
                    "--output",
                    "/tmp/server-abc.ign",
                ],
                "Converting Butane to Ignition",
            ),
            call(
                ["ignition-validate", "/tmp/server-abc.ign"], "Validating Ignition file"
            ),
        ]
        self.mock_view.execute_with_progress.assert_has_calls(
            expected_calls, any_order=False
        )

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

    @patch("tempfile.mkstemp")
    def test_create_iso_user_cancellation(self, mock_mkstemp):
        """Test ISO creation when user cancels."""
        self.mock_view.configure_settings.return_value = self.valid_config
        self.mock_view.confirm_proceed.return_value = False

        self.controller.create_iso()

        # Should not proceed with creation
        mock_mkstemp.assert_not_called()
        self.mock_view.execute_with_progress.assert_not_called()

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

    @patch.object(ConsoleController, "create_iso")
    def test_run(self, mock_create_iso):
        """Test interactive controller run method."""
        self.controller.run()

        self.mock_view.show_header.assert_called_once()
        mock_create_iso.assert_called_once()


if __name__ == "__main__":
    unittest.main()
