#!/bin/bash
set -e

# Use current directory as base
BASE_DIR="$(pwd)"
MICROPYTHON_DIR="$BASE_DIR/micropython"
PICOBRIDGE_DIR="$BASE_DIR"

# Extract version
VERSION=$(grep '__version__' "$PICOBRIDGE_DIR/frozen_modules/pb_version.py" | cut -d'"' -f2)

echo "📦 Building PicoBridge version $VERSION"

cd "$MICROPYTHON_DIR/ports/rp2"
rm -rf build-RPI_PICO2_W

export PICO_PLATFORM=rp2040

make BOARD=RPI_PICO2_W \
     FROZEN_MANIFEST=$PICOBRIDGE_DIR/my_manifest.py \
     -j$(nproc)

cp build-RPI_PICO2_W/firmware.uf2 "$PICOBRIDGE_DIR/picobridge_${VERSION}.uf2"

echo "✅ Done: $PICOBRIDGE_DIR/picobridge_${VERSION}.uf2"
