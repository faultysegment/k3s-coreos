"""Models for CoreOS ISO creation."""

import os
import glob
import tempfile
import platform
import getpass
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass


class CacheDirectoryManager:
    """Manages cache directories across different operating systems."""

    @staticmethod
    def get_system_cache_dir() -> Path:
        """Get system-appropriate cache directory."""
        system = platform.system().lower()

        if system == "linux":
            # Use XDG_CACHE_HOME or fallback to ~/.cache
            cache_home = os.environ.get("XDG_CACHE_HOME")
            if cache_home:
                return Path(cache_home)
            return Path.home() / ".cache"
        elif system == "darwin":  # macOS
            return Path.home() / "Library" / "Caches"
        elif system == "windows":
            # Use LOCALAPPDATA or fallback
            local_appdata = os.environ.get("LOCALAPPDATA")
            if local_appdata:
                return Path(local_appdata)
            return Path.home() / "AppData" / "Local"
        else:
            # Fallback for unknown systems
            return Path.home() / ".cache"

    @staticmethod
    def get_app_cache_dir(app_name: str = "k3s-coreos") -> Path:
        """Get application-specific cache directory."""
        cache_dir = CacheDirectoryManager.get_system_cache_dir() / app_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @staticmethod
    def get_temp_dir() -> Path:
        """Get system temporary directory."""
        return Path(tempfile.gettempdir())


@dataclass
class ISOCreationConfig:
    """Configuration model for ISO creation process."""

    install_disk: str = "/dev/sda"
    output_iso: Optional[str] = None
    ignition_file: Optional[str] = None
    base_iso: str = "fedora-coreos.iso"
    ssh_key: Optional[str] = None
    hostname: str = "k3s"
    username: Optional[str] = None
    cache_dir: Optional[Path] = None
    temp_dir: Optional[Path] = None

    def __post_init__(self):
        """Auto-generate derived fields after initialization."""
        # Set default username if not provided
        if not self.username:
            self.username = getpass.getuser()

        # Initialize cache and temp directories
        if not self.cache_dir:
            self.cache_dir = CacheDirectoryManager.get_app_cache_dir()

        if not self.temp_dir:
            self.temp_dir = CacheDirectoryManager.get_temp_dir()

        # Set file paths in cache directory if not specified
        if not self.ignition_file:
            # Use simple temp path - will be handled by controller's context manager
            self.ignition_file = str(self.temp_dir / "server.ign")

        if not self.output_iso:
            self.output_iso = "server.iso"

        # Move base ISO to cache directory
        if self.base_iso == "fedora-coreos.iso":
            self.base_iso = str(self.cache_dir / "fedora-coreos.iso")

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.install_disk:
            errors.append("Install disk must be specified")

        if not self.output_iso:
            errors.append("Output ISO filename must be specified")

        if not self.ssh_key:
            errors.append("SSH key must be specified")

        if not self.hostname:
            errors.append("Hostname must be specified")

        if not self.username:
            errors.append("Username must be specified")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

    @property
    def output_iso_exists(self) -> bool:
        """Check if output ISO file already exists."""
        return bool(self.output_iso and os.path.exists(self.output_iso))

    @property
    def base_iso_exists(self) -> bool:
        """Check if base ISO file already exists."""
        return os.path.exists(self.base_iso)

    @property
    def ignition_file_exists(self) -> bool:
        """Check if ignition file already exists."""
        return bool(self.ignition_file and os.path.exists(self.ignition_file))


class ButaneFileFinder:
    """Utility class for finding Butane files."""

    @staticmethod
    def find_butane_files(directory: str = ".") -> List[str]:
        """Find all .bu files in the specified directory."""
        pattern = os.path.join(directory, "*.bu")
        return glob.glob(pattern)

    @staticmethod
    def get_file_info(filepath: str) -> dict:
        """Get file information including size."""
        if not os.path.exists(filepath):
            return {"size": 0, "size_str": "0 bytes"}

        size = os.path.getsize(filepath)
        if size < 1024:
            size_str = f"{size:,} bytes"
        elif size < 1024 * 1024:
            size_str = f"{size/1024:.1f} KB"
        else:
            size_str = f"{size/(1024*1024):.1f} MB"

        return {"size": size, "size_str": size_str}


class SSHKeyFinder:
    """Utility class for finding SSH keys across different operating systems."""

    @staticmethod
    def get_ssh_directory() -> Path:
        """Get SSH directory path for different operating systems."""
        import platform

        system = platform.system().lower()

        if system == "windows":
            # Windows: Check multiple possible locations
            windows_paths = [
                Path.home() / ".ssh",
                Path(os.environ.get("USERPROFILE", "")) / ".ssh",
                Path("C:\\Users") / os.environ.get("USERNAME", "") / ".ssh"
            ]
            for path in windows_paths:
                if path.exists():
                    return path
            # Default to first option if none exist
            return windows_paths[0]
        else:
            # Linux and macOS use the same location
            return Path.home() / ".ssh"

    @staticmethod
    def get_default_ssh_keys() -> Dict[str, str]:
        """Find SSH public keys in default locations for Linux, Windows, and macOS."""
        ssh_dir = SSHKeyFinder.get_ssh_directory()
        keys = {}

        # Common SSH key file names (same across all platforms)
        key_files = ["id_rsa.pub", "id_ed25519.pub", "id_ecdsa.pub", "id_dsa.pub"]

        for key_file in key_files:
            key_path = ssh_dir / key_file
            if key_path.exists() and key_path.is_file():
                try:
                    with open(key_path, 'r', encoding='utf-8') as f:
                        key_content = f.read().strip()
                    if key_content:
                        # Extract key type from filename for display
                        key_type = key_file.replace('.pub', '').replace('id_', '')
                        keys[key_type] = key_content
                except Exception:
                    # Skip keys that can't be read
                    continue

        return keys

    @staticmethod
    def get_primary_ssh_key() -> Optional[str]:
        """Get the primary (first available) SSH key."""
        keys = SSHKeyFinder.get_default_ssh_keys()
        if not keys:
            return None

        # Prefer ed25519, then rsa, then others (security best practices)
        preferred_order = ["ed25519", "rsa", "ecdsa", "dsa"]

        for key_type in preferred_order:
            if key_type in keys:
                return keys[key_type]

        # Return first available if no preferred type found
        return next(iter(keys.values()))

    @staticmethod
    def get_ssh_info() -> Dict[str, any]:
        """Get comprehensive SSH key information."""
        ssh_dir = SSHKeyFinder.get_ssh_directory()
        keys = SSHKeyFinder.get_default_ssh_keys()
        primary_key = SSHKeyFinder.get_primary_ssh_key()

        return {
            "ssh_dir": str(ssh_dir),
            "ssh_dir_exists": ssh_dir.exists(),
            "available_keys": keys,
            "primary_key": primary_key,
            "key_count": len(keys)
        }
