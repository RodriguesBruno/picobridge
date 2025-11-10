#!/bin/bash
set -e

# Adjust this if your micropython folder is elsewhere
MICROPYTHON_DIR="$HOME/micropython"

echo "🔧 Building MicroPython firmware from $MICROPYTHON_DIR"

cd "$MICROPYTHON_DIR/ports/rp2"

# Clean previous build
rm -rf build-RPI_PICO2_W

# Set platform
export PICO_PLATFORM=rp2040

# Build
make BOARD=RPI_PICO2_W \
     FROZEN_MANIFEST=$HOME/picobridge/my_manifest.py \
     -j$(nproc)

# Copy output
cp build-RPI_PICO2_W/firmware.uf2 "$HOME/picobridge/picobridge_1.1.uf2"

echo "✅ Build complete. UF2 saved to picobridge_1.1.uf2"
