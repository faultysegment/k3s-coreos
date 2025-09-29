"""Unit tests for views module."""

import unittest
import subprocess
from unittest.mock import Mock, patch, call
from rich.console import Console
from rich.table import Table

from src.views import TUIView
from src.models import ISOCreationConfig, SSHKeyFinder


class TestTUIView(unittest.TestCase):
    """Test cases for TUIView class."""

    def setUp(self):
        """Set up test fixtures."""
        self.view = TUIView()

    def test_init_with_rich_available(self):
        """Test TUIView initialization when Rich is available."""
        self.assertIsInstance(self.view.console, Console)

    @patch('src.views.RICH_AVAILABLE', False)
    def test_init_without_rich(self):
        """Test TUIView initialization when Rich is not available."""
        with self.assertRaises(ImportError) as context:
            TUIView()

        self.assertIn("Rich library is required", str(context.exception))

    @patch.object(Console, 'print')
    def test_show_header(self, mock_print):
        """Test header display."""
        self.view.show_header()

        # Verify print was called (header content)
        self.assertTrue(mock_print.called)
        # Check that a Panel was printed (header should be in a panel)
        call_args = mock_print.call_args_list
        self.assertTrue(any(hasattr(call[0][0], 'renderable') or
                           'CoreOS ISO Creator' in str(call)
                           for call in call_args))

    @patch.object(TUIView, '_configure_ssh_key')
    @patch('rich.prompt.Prompt.ask')
    def test_configure_settings(self, mock_prompt, mock_ssh_config):
        """Test settings configuration."""
        mock_ssh_config.return_value = "ssh-rsa AAAAB... user@host"
        mock_prompt.side_effect = [
            "testuser",     # username
            "test-host",    # hostname
            "/dev/sda",     # install_disk (default)
            "server.iso"    # output_iso (default)
        ]

        config = self.view.configure_settings()

        self.assertEqual(config.ssh_key, "ssh-rsa AAAAB... user@host")
        self.assertEqual(config.username, "testuser")
        self.assertEqual(config.hostname, "test-host")
        self.assertEqual(config.install_disk, "/dev/sda")
        self.assertEqual(config.output_iso, "server.iso")

        # Verify that username prompt uses the config's default username
        username_prompt_call = mock_prompt.call_args_list[0]
        self.assertEqual(username_prompt_call[0][0], "Username for the system")
        # The default should be the system username (from config)
        import getpass
        self.assertEqual(username_prompt_call[1]['default'], getpass.getuser())

        # Verify that hostname prompt uses the config's default hostname
        hostname_prompt_call = mock_prompt.call_args_list[1]
        self.assertEqual(hostname_prompt_call[0][0], "Hostname for the system")
        self.assertEqual(hostname_prompt_call[1]['default'], "k3s")

    @patch.object(SSHKeyFinder, 'get_ssh_info')
    @patch('rich.prompt.Prompt.ask')
    def test_configure_ssh_key_no_keys_found(self, mock_prompt, mock_ssh_info):
        """Test SSH key configuration when no keys are found."""
        mock_ssh_info.return_value = {
            "key_count": 0,
            "ssh_dir": "/home/user/.ssh",
            "available_keys": {}
        }
        mock_prompt.return_value = "ssh-rsa AAAAB... manual@entry"

        result = self.view._configure_ssh_key()

        self.assertEqual(result, "ssh-rsa AAAAB... manual@entry")
        mock_prompt.assert_called_once_with("SSH public key (paste the entire key)")

    @patch.object(SSHKeyFinder, 'get_ssh_info')
    @patch('rich.prompt.Prompt.ask')
    @patch.object(Console, 'print')
    def test_configure_ssh_key_with_available_keys(self, mock_print, mock_prompt, mock_ssh_info):
        """Test SSH key configuration with available keys."""
        mock_ssh_info.return_value = {
            "key_count": 2,
            "ssh_dir": "/home/user/.ssh",
            "available_keys": {
                "rsa": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host",
                "ed25519": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user@host"
            }
        }
        mock_prompt.return_value = "1"  # Select first key

        result = self.view._configure_ssh_key()

        self.assertEqual(result, "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host")

        # Verify table was displayed
        table_printed = any(isinstance(call[0][0], Table) for call in mock_print.call_args_list)
        self.assertTrue(table_printed)

    @patch.object(SSHKeyFinder, 'get_ssh_info')
    @patch('rich.prompt.Prompt.ask')
    def test_configure_ssh_key_manual_entry(self, mock_prompt, mock_ssh_info):
        """Test SSH key configuration choosing manual entry."""
        mock_ssh_info.return_value = {
            "key_count": 1,
            "ssh_dir": "/home/user/.ssh",
            "available_keys": {
                "rsa": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host"
            }
        }
        mock_prompt.side_effect = ["2", "ssh-rsa AAAAB... manual@key"]  # Select manual entry

        result = self.view._configure_ssh_key()

        self.assertEqual(result, "ssh-rsa AAAAB... manual@key")

    @patch.object(Console, 'print')
    def test_show_settings_summary_minimal(self, mock_print):
        """Test settings summary with minimal configuration."""
        import getpass
        config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user@host"
        )

        self.view.show_settings_summary(config)

        # Verify print was called with a table
        table_printed = any(isinstance(call[0][0], Table) for call in mock_print.call_args_list)
        self.assertTrue(table_printed)

    @patch.object(Console, 'print')
    def test_show_settings_summary_custom(self, mock_print):
        """Test settings summary with custom configuration."""
        config = ISOCreationConfig(
            ssh_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user@host",
            hostname="custom-host",
            username="admin",
            install_disk="/dev/nvme0n1",
            output_iso="custom.iso"
        )

        self.view.show_settings_summary(config)

        # Verify print was called with a table
        table_printed = any(isinstance(call[0][0], Table) for call in mock_print.call_args_list)
        self.assertTrue(table_printed)

    @patch('rich.prompt.Confirm.ask')
    def test_confirm_proceed_yes(self, mock_confirm):
        """Test confirmation when user says yes."""
        mock_confirm.return_value = True

        result = self.view.confirm_proceed()

        self.assertTrue(result)
        mock_confirm.assert_called_once_with("Proceed with ISO creation?", default=True)

    @patch('rich.prompt.Confirm.ask')
    def test_confirm_proceed_no(self, mock_confirm):
        """Test confirmation when user says no."""
        mock_confirm.return_value = False

        result = self.view.confirm_proceed()

        self.assertFalse(result)

    @patch.object(Console, 'print')
    def test_show_step(self, mock_print):
        """Test step display."""
        self.view.show_step("Step 1", "Test description")

        mock_print.assert_called_once()
        # Check that the step was formatted correctly
        call_args = str(mock_print.call_args)
        self.assertIn("Step 1", call_args)

    @patch('subprocess.run')
    def test_execute_with_progress_success(self, mock_run):
        """Test command execution with progress - success case."""
        mock_result = Mock()
        mock_result.stdout = "Success output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = self.view.execute_with_progress(["echo", "test"], "Test command")

        self.assertEqual(result, mock_result)
        mock_run.assert_called_once_with(
            ["echo", "test"], capture_output=True, text=True, check=True
        )

    @patch('subprocess.run')
    def test_execute_with_progress_failure(self, mock_run):
        """Test command execution with progress - failure case."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["false"])

        with self.assertRaises(subprocess.CalledProcessError):
            self.view.execute_with_progress(["false"], "Failing command")

    @patch.object(Console, 'print')
    def test_show_completion_success(self, mock_print):
        """Test completion display for successful ISO creation."""
        config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB... user@host",
            hostname="test-host",
            username="testuser",
            output_iso="test.iso"
        )

        with patch('os.path.exists', return_value=True), \
             patch('src.models.ButaneFileFinder.get_file_info', return_value={"size_str": "100.0 MB"}):

            self.view.show_completion(config)

            # Verify completion panel was displayed
            panel_printed = any('Completed' in str(call) or hasattr(call[0][0], 'renderable')
                              for call in mock_print.call_args_list)
            self.assertTrue(panel_printed)

    @patch.object(Console, 'print')
    def test_show_completion_failure(self, mock_print):
        """Test completion display for failed ISO creation."""
        config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB... user@host",
            hostname="test-host",
            username="testuser"
        )

        with patch('os.path.exists', return_value=False):
            self.view.show_completion(config)

            # Should show error message
            error_printed = any('ISO file was not created' in str(call)
                              for call in mock_print.call_args_list)
            self.assertTrue(error_printed)

    @patch.object(Console, 'print')
    def test_show_error(self, mock_print):
        """Test error message display."""
        error_message = "Test error message"

        self.view.show_error(error_message)

        mock_print.assert_called_once()
        call_args = str(mock_print.call_args)
        self.assertIn(error_message, call_args)
        # Should be formatted as error (red)
        self.assertIn("red", call_args.lower())


if __name__ == '__main__':
    unittest.main()