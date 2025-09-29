#!/usr/bin/env sh

set -e

[ $# -ge 4 ] && {
  echo "Usage: $0 BUTANE INSTALL_DISK OUTPUT_ISO"
  exit 1
}

INPUT_BUTANE=${1:-"server.bu"}
INSTALL_DISK=${2:-"/dev/sda"}
OUTPUT_IGNITION="${INPUT_BUTANE%.bu}.ign"
OUTPUT_ISO=${3:-"${INPUT_BUTANE%.bu}.iso"}

echo "Generating ignition"
butane --pretty --strict "$INPUT_BUTANE" --output "$OUTPUT_IGNITION"
ignition-validate server.ign

if [ ! -f fedora-coreos.iso ]; then
  echo "Downloading Fedora coreos"
  FCOS_ISO=$(coreos-installer download -f iso --decompress)
  mv "$FCOS_ISO" fedora-coreos.iso
fi

if [ -f "$OUTPUT_ISO" ]; then
  rm "$OUTPUT_ISO"
fi

echo "Embedding ignition"
coreos-installer iso customize \
  --dest-ignition "$OUTPUT_IGNITION" \
  --dest-device "$INSTALL_DISK" \
  -o "$OUTPUT_ISO" \
  fedora-coreos.iso

echo "Created $OUTPUT_ISO"
