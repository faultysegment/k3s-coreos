# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Fedora CoreOS configuration project for setting up a K3s Kubernetes cluster. The repository contains Butane configuration files and scripts to create bootable CoreOS ISO images with K3s pre-installed.

## Architecture

The project uses a declarative approach to provision CoreOS systems:

1. **Butane Configuration** (`server.bu`): Defines the complete system configuration including:
   - User accounts and SSH keys
   - Systemd services for K3s installation and operation
   - Disk partitioning and filesystem layout
   - Package repositories for Kubernetes and K3s
   - K3s binary installation and kubelet configuration
   - Automatic system updates via Zincati

2. **ISO Creation Script** (`create-iso.sh`): Automates the process of:
   - Converting Butane config to Ignition format using `butane`
   - Validating Ignition files with `ignition-validate`
   - Downloading Fedora CoreOS ISO if needed
   - Embedding Ignition config into ISO using `coreos-installer`

## Key Components

- **K3s Installation**: Automated via systemd service that installs dependencies (kubectl, k3s-selinux) using rpm-ostree
- **Storage Configuration**: Separate /var partition for container data persistence
- **Pod Cleanup**: Automatic cleanup of shutdown pods on system startup
- **Update Strategy**: Automatic updates scheduled for weekends (Saturday/Sunday 12:00 UTC)

## Setup

### Dependencies
Install Poetry for dependency management:
```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Activate virtual environment
poetry shell
```

### External Tools Required
- `butane` - Butane configuration transpiler
- `ignition-validate` - Ignition configuration validator
- `coreos-installer` - CoreOS installer tool

## Common Commands

### Creating a Custom CoreOS ISO

#### Python Script (TUI)
```bash
# Using Poetry (recommended)
poetry run python src/create_iso.py
poetry run python src/create_iso.py server.bu
poetry run python src/create_iso.py server.bu /dev/sdb custom-output.iso

# Using wrapper script
./create-iso

# Direct Python execution (requires rich: pip install rich)
python3 src/create_iso.py
python3 src/create_iso.py server.bu --no-tui
```

#### Original Shell Script
```bash
# Use defaults (server.bu -> server.iso, /dev/sda target)
./create-iso.sh

# Specify custom parameters
./create-iso.sh server.bu /dev/sda custom-output.iso
```

### Working with Butane/Ignition
```bash
# Convert Butane to Ignition manually
butane --pretty --strict server.bu --output server.ign

# Validate Ignition file
ignition-validate server.ign
```

### CoreOS Installer Operations
```bash
# Download latest CoreOS ISO
coreos-installer download -f iso --decompress

# Customize ISO with ignition config
coreos-installer iso customize \
  --dest-ignition server.ign \
  --dest-device /dev/sda \
  -o custom.iso \
  fedora-coreos.iso
```

### Development Commands
```bash
# Run tests
poetry run pytest                    # Run all tests with pytest
poetry run python run_tests.py      # Run all tests with custom runner

# Run specific test files
poetry run pytest tests/test_models.py
poetry run pytest tests/test_controller.py
poetry run pytest tests/test_views.py

# Run specific test cases
poetry run pytest tests/test_models.py::TestISOCreationConfig
poetry run pytest tests/test_models.py::TestISOCreationConfig::test_default_values

# Run linting
poetry run black src/
poetry run flake8 src/
poetry run mypy src/

# Build package
poetry build
```

## File Structure

- `server.bu` - Main Butane configuration file
- `server.ign` - Generated Ignition file (auto-generated)
- `create-iso.sh` - Original shell ISO creation script
- `src/` - Python package directory
  - `create_iso.py` - Main application entry point
  - `models.py` - Data models and configuration
  - `views.py` - TUI and CLI view interfaces
  - `controller.py` - Business logic and console operations
- `create-iso` - Wrapper script for Python version
- `pyproject.toml` - Poetry project configuration
- `*.iso` files - CoreOS installation media
- `*.qcow2` files - VM disk images

## Architecture

The Python ISO creator follows MVC (Model-View-Controller) pattern:

- **Model** (`models.py`):
  - `ISOCreationConfig` - Configuration data and validation
  - `ButaneFileFinder` - File discovery utilities
- **View** (`views.py`):
  - `TUIView` - Rich interactive interface
  - `CLIView` - Simple command-line interface
- **Controller** (`controller.py`):
  - `InteractiveController` - Handles TUI mode
  - `CLIController` - Handles CLI mode
  - `ConsoleController` - Base console operations

## Development Notes

- The system is designed for immutable infrastructure - changes should be made to Butane config, not running systems
- K3s version is pinned in the Butane config (`v1.26.3+k3s1`) - update the hash when changing versions
- The configuration assumes x86_64 architecture
- SSH access is configured for the `faultysegment` user with sudo privileges
- Python code follows MVC pattern for better maintainability and testability