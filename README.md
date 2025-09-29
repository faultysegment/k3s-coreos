# K3s on Fedora CoreOS

This repository contains Butane configuration files and scripts to create bootable CoreOS ISO images with K3s pre-installed.

> **Note**: This project was generated with AI assistance using [Claude Code](https://claude.ai/code) by Anthropic.

## Overview

This project uses a declarative approach to provision CoreOS systems with K3s Kubernetes cluster. The configuration is based on the guide from [K3s on Fedora CoreOS Bare Metal](https://devnonsense.com/posts/k3s-on-fedora-coreos-bare-metal/).

## Quick Start

### Prerequisites

- `butane` - Butane configuration transpiler
- `ignition-validate` - Ignition configuration validator
- `coreos-installer` - CoreOS installer tool
- Python 3.x with Poetry (for the Python version)

### Creating a Custom ISO

#### Using Python Script (TUI)
```bash
# Install dependencies
poetry install

# Run interactive ISO creator
poetry run python src/create_iso.py

# Or use wrapper script
./create-iso
```

#### Using Shell Script
```bash
# Use defaults (server.bu -> server.iso, /dev/sda target)
./create-iso.sh

# Specify custom parameters
./create-iso.sh server.bu /dev/sda custom-output.iso
```

## Architecture

- **Butane Configuration** (`server.bu`): Complete system configuration
- **ISO Creation Scripts**: Automated ISO building with embedded Ignition config
- **K3s Integration**: Pre-configured K3s installation with dependencies
- **Storage Management**: Separate /var partition for container data
- **Auto Updates**: Scheduled system updates via Zincati

## Key Features

- Automated K3s installation with kubectl and SELinux support
- Persistent storage configuration for containers
- Automatic cleanup of shutdown pods
- Weekend-scheduled system updates
- SSH key-based authentication
- Avahi service discovery

## Based On

This repository was created using the guide: [K3s on Fedora CoreOS Bare Metal](https://devnonsense.com/posts/k3s-on-fedora-coreos-bare-metal/) as a foundation.