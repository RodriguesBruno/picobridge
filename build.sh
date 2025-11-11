#!/bin/bash
set -ex

MICROPYTHON_DIR="$PWD/micropython"
PICOBRIDGE_DIR="$PWD"

if [ ! -d "$MICROPYTHON_DIR" ]; then
  git clone --recursive https://github.com/micropython/micropython.git "$MICROPYTHON_DIR"
fi

cd "$MICROPYTHON_DIR/mpy-cross"
make -j$(nproc)

VERSION=$(grep '__version__' "$PICOBRIDGE_DIR/src/pb_version.py" | cut -d'"' -f2)
echo "📦 Building PicoBridge $VERSION"

cd "$MICROPYTHON_DIR/ports/rp2"
rm -rf build-RPI_PICO2_W

make BOARD=RPI_PICO2_W \
     FROZEN_MANIFEST=$PICOBRIDGE_DIR/my_manifest.py \
     -j$(nproc)

cp build-RPI_PICO2_W/firmware.uf2 "$PICOBRIDGE_DIR/picobridge_${VERSION}.uf2"
