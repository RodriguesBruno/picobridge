#!/bin/bash
set -e

BASE_DIR="$(pwd)"
MICROPYTHON_DIR="$BASE_DIR/micropython"
PICOBRIDGE_DIR="$BASE_DIR"

# Auto-clone MicroPython if not present
if [ ! -d "$MICROPYTHON_DIR" ]; then
  echo "📥 Cloning MicroPython..."
  git clone --depth=1 --recurse-submodules https://github.com/micropython/micropython.git "$MICROPYTHON_DIR"
  cd "$MICROPYTHON_DIR"
  git submodule update --init --recursive
else
  echo "✅ MicroPython already present."
fi

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
