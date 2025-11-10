#!/bin/bash
set -e

MICROPYTHON_DIR="$HOME/micropython"
PICOBRIDGE_DIR="$HOME/picobridge"

# Extract version from frozen_modules/pb_version.py
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
