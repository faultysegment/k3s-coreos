"""Unit tests for models module."""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open

from src.models import ISOCreationConfig, ButaneFileFinder, SSHKeyFinder


class TestISOCreationConfig(unittest.TestCase):
    """Test cases for ISOCreationConfig class."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = ISOCreationConfig()
        self.assertEqual(config.install_disk, "/dev/sda")
        self.assertEqual(config.base_iso, "fedora-coreos.iso")
        self.assertEqual(config.username, "user")
        self.assertIsNone(config.ssh_key)
        self.assertIsNone(config.hostname)

    def test_post_init_auto_generation(self):
        """Test that __post_init__ generates derived fields."""
        config = ISOCreationConfig()
        self.assertEqual(config.ignition_file, "server.ign")
        self.assertEqual(config.output_iso, "server.iso")

    def test_validation_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        config = ISOCreationConfig()
        errors = config.validate()

        self.assertIn("SSH key must be specified", errors)
        self.assertIn("Hostname must be specified", errors)
        self.assertFalse(config.is_valid())

    def test_validation_with_all_fields(self):
        """Test validation passes with all required fields."""
        config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB... test@example.com",
            hostname="test-host",
            username="testuser"
        )
        errors = config.validate()

        self.assertEqual(len(errors), 0)
        self.assertTrue(config.is_valid())

    def test_validation_empty_username(self):
        """Test validation fails with empty username."""
        config = ISOCreationConfig(
            ssh_key="ssh-rsa AAAAB... test@example.com",
            hostname="test-host",
            username=""
        )
        errors = config.validate()

        self.assertIn("Username must be specified", errors)

    def test_file_existence_properties(self):
        """Test file existence properties."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            config = ISOCreationConfig(
                ssh_key="ssh-rsa AAAAB... test@example.com",
                hostname="test-host",
                output_iso=tmp_path,
                base_iso=tmp_path
            )

            self.assertTrue(config.output_iso_exists)
            self.assertTrue(config.base_iso_exists)
        finally:
            os.unlink(tmp_path)

    def test_custom_values(self):
        """Test custom values are preserved."""
        config = ISOCreationConfig(
            install_disk="/dev/nvme0n1",
            output_iso="custom.iso",
            ignition_file="custom.ign",
            base_iso="custom-base.iso",
            ssh_key="ssh-ed25519 AAAAC... user@host",
            hostname="custom-host",
            username="admin"
        )

        self.assertEqual(config.install_disk, "/dev/nvme0n1")
        self.assertEqual(config.output_iso, "custom.iso")
        self.assertEqual(config.ignition_file, "custom.ign")
        self.assertEqual(config.base_iso, "custom-base.iso")
        self.assertEqual(config.ssh_key, "ssh-ed25519 AAAAC... user@host")
        self.assertEqual(config.hostname, "custom-host")
        self.assertEqual(config.username, "admin")


class TestButaneFileFinder(unittest.TestCase):
    """Test cases for ButaneFileFinder class."""

    def test_find_butane_files_empty_directory(self):
        """Test finding butane files in empty directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            files = ButaneFileFinder.find_butane_files(tmp_dir)
            self.assertEqual(files, [])

    def test_find_butane_files_with_files(self):
        """Test finding butane files with .bu files present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create test .bu files
            bu_file1 = os.path.join(tmp_dir, "server.bu")
            bu_file2 = os.path.join(tmp_dir, "client.bu")
            other_file = os.path.join(tmp_dir, "readme.txt")

            for file_path in [bu_file1, bu_file2, other_file]:
                Path(file_path).touch()

            files = ButaneFileFinder.find_butane_files(tmp_dir)

            self.assertEqual(len(files), 2)
            self.assertIn(bu_file1, files)
            self.assertIn(bu_file2, files)
            self.assertNotIn(other_file, files)

    def test_get_file_info_existing_file(self):
        """Test getting file info for existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            info = ButaneFileFinder.get_file_info(tmp_path)
            self.assertGreater(info["size"], 0)
            self.assertIn("bytes", info["size_str"])
        finally:
            os.unlink(tmp_path)

    def test_get_file_info_nonexistent_file(self):
        """Test getting file info for non-existent file."""
        info = ButaneFileFinder.get_file_info("nonexistent.bu")
        self.assertEqual(info["size"], 0)
        self.assertEqual(info["size_str"], "0 bytes")

    def test_get_file_info_size_formatting(self):
        """Test file size formatting for different sizes."""
        # Test with mock file sizes
        with patch('os.path.getsize') as mock_getsize, \
             patch('os.path.exists', return_value=True):

            # Test bytes
            mock_getsize.return_value = 500
            info = ButaneFileFinder.get_file_info("test.bu")
            self.assertEqual(info["size_str"], "500 bytes")

            # Test KB
            mock_getsize.return_value = 2048
            info = ButaneFileFinder.get_file_info("test.bu")
            self.assertEqual(info["size_str"], "2.0 KB")

            # Test MB
            mock_getsize.return_value = 2097152  # 2 MB
            info = ButaneFileFinder.get_file_info("test.bu")
            self.assertEqual(info["size_str"], "2.0 MB")


class TestSSHKeyFinder(unittest.TestCase):
    """Test cases for SSHKeyFinder class."""

    @patch('platform.system')
    def test_get_ssh_directory_linux(self, mock_system):
        """Test SSH directory detection on Linux."""
        mock_system.return_value = 'Linux'
        ssh_dir = SSHKeyFinder.get_ssh_directory()
        expected = Path.home() / ".ssh"
        self.assertEqual(ssh_dir, expected)

    @patch('platform.system')
    def test_get_ssh_directory_macos(self, mock_system):
        """Test SSH directory detection on macOS."""
        mock_system.return_value = 'Darwin'
        ssh_dir = SSHKeyFinder.get_ssh_directory()
        expected = Path.home() / ".ssh"
        self.assertEqual(ssh_dir, expected)

    @patch('platform.system')
    @patch('os.environ', {'USERPROFILE': 'C:\\Users\\TestUser', 'USERNAME': 'TestUser'})
    def test_get_ssh_directory_windows_existing(self, mock_system):
        """Test SSH directory detection on Windows with existing directory."""
        mock_system.return_value = 'Windows'

        with patch.object(Path, 'exists') as mock_exists:
            mock_exists.side_effect = lambda: str(self) == str(Path.home() / ".ssh")

            ssh_dir = SSHKeyFinder.get_ssh_directory()
            expected = Path.home() / ".ssh"
            self.assertEqual(ssh_dir, expected)

    @patch('platform.system')
    @patch('os.environ', {'USERPROFILE': 'C:\\Users\\TestUser', 'USERNAME': 'TestUser'})
    def test_get_ssh_directory_windows_fallback(self, mock_system):
        """Test SSH directory detection on Windows with fallback."""
        mock_system.return_value = 'Windows'

        with patch.object(Path, 'exists', return_value=False):
            ssh_dir = SSHKeyFinder.get_ssh_directory()
            expected = Path.home() / ".ssh"
            self.assertEqual(ssh_dir, expected)

    def test_get_default_ssh_keys_empty_directory(self):
        """Test getting SSH keys from empty directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(SSHKeyFinder, 'get_ssh_directory', return_value=Path(tmp_dir)):
                keys = SSHKeyFinder.get_default_ssh_keys()
                self.assertEqual(keys, {})

    def test_get_default_ssh_keys_with_keys(self):
        """Test getting SSH keys with keys present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create test key files
            rsa_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ... user@host"
            ed25519_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user@host"

            rsa_path = Path(tmp_dir) / "id_rsa.pub"
            ed25519_path = Path(tmp_dir) / "id_ed25519.pub"

            rsa_path.write_text(rsa_key, encoding='utf-8')
            ed25519_path.write_text(ed25519_key, encoding='utf-8')

            with patch.object(SSHKeyFinder, 'get_ssh_directory', return_value=Path(tmp_dir)):
                keys = SSHKeyFinder.get_default_ssh_keys()

                self.assertEqual(len(keys), 2)
                self.assertEqual(keys["rsa"], rsa_key)
                self.assertEqual(keys["ed25519"], ed25519_key)

    def test_get_primary_ssh_key_empty(self):
        """Test getting primary SSH key when no keys exist."""
        with patch.object(SSHKeyFinder, 'get_default_ssh_keys', return_value={}):
            primary_key = SSHKeyFinder.get_primary_ssh_key()
            self.assertIsNone(primary_key)

    def test_get_primary_ssh_key_preference_order(self):
        """Test SSH key preference order (ed25519 > rsa > ecdsa > dsa)."""
        keys = {
            "rsa": "ssh-rsa AAAAB... rsa@host",
            "dsa": "ssh-dss AAAAB... dsa@host",
            "ecdsa": "ssh-ecdsa AAAAB... ecdsa@host",
            "ed25519": "ssh-ed25519 AAAAC... ed25519@host"
        }

        with patch.object(SSHKeyFinder, 'get_default_ssh_keys', return_value=keys):
            primary_key = SSHKeyFinder.get_primary_ssh_key()
            self.assertEqual(primary_key, keys["ed25519"])

    def test_get_ssh_info(self):
        """Test getting comprehensive SSH information."""
        keys = {"rsa": "ssh-rsa AAAAB... user@host"}
        primary_key = "ssh-rsa AAAAB... user@host"
        ssh_dir = Path.home() / ".ssh"

        with patch.object(SSHKeyFinder, 'get_ssh_directory', return_value=ssh_dir), \
             patch.object(SSHKeyFinder, 'get_default_ssh_keys', return_value=keys), \
             patch.object(SSHKeyFinder, 'get_primary_ssh_key', return_value=primary_key), \
             patch.object(Path, 'exists', return_value=True):

            info = SSHKeyFinder.get_ssh_info()

            self.assertEqual(info["ssh_dir"], str(ssh_dir))
            self.assertTrue(info["ssh_dir_exists"])
            self.assertEqual(info["available_keys"], keys)
            self.assertEqual(info["primary_key"], primary_key)
            self.assertEqual(info["key_count"], 1)

    def test_ssh_key_file_error_handling(self):
        """Test handling of unreadable SSH key files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a file that will cause read errors
            bad_key_path = Path(tmp_dir) / "id_rsa.pub"
            bad_key_path.write_text("valid content", encoding='utf-8')

            with patch.object(SSHKeyFinder, 'get_ssh_directory', return_value=Path(tmp_dir)), \
                 patch('builtins.open', side_effect=PermissionError("Access denied")):

                keys = SSHKeyFinder.get_default_ssh_keys()
                self.assertEqual(keys, {})


if __name__ == '__main__':
    unittest.main()