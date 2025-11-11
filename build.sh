#!/bin/bash
set -e

MICROPYTHON_DIR="$PWD/micropython"
PICOBRIDGE_DIR="$PWD"

# Clone MicroPython if not already present
if [ ! -d "$MICROPYTHON_DIR" ]; then
  echo "📥 Cloning MicroPython..."
  git clone --recursive https://github.com/micropython/micropython.git "$MICROPYTHON_DIR"
fi

# Get version
VERSION=$(grep '__version__' "$PICOBRIDGE_DIR/src/pb_version.py" | cut -d'"' -f2)
echo "📦 Building PicoBridge version $VERSION"

cd "$MICROPYTHON_DIR/ports/rp2"
rm -rf build-RPI_PICO2_W

make V=1 BOARD=RPI_PICO2_W \
     FROZEN_MANIFEST=$PICOBRIDGE_DIR/my_manifest.py \
     -j$(nproc)

cp build-RPI_PICO2_W/firmware.uf2 "$PICOBRIDGE_DIR/picobridge_${VERSION}.uf2"
echo "✅ Done: $PICOBRIDGE_DIR/picobridge_${VERSION}.uf2"
