#!/bin/bash
set -e

cd /workspace/micropython

# Update submodules just in case
git submodule update --init --recursive

# Clean old build
rm -rf ports/rp2/build-RPI_PICO2_W

# Build
make -C ports/rp2 \
    BOARD=RPI_PICO2_W \
    FROZEN_MANIFEST=/workspace/picobridge/my_manifest.py \
    -j$(nproc)

# Resulting UF2 file:
echo "Built firmware:"
ls ports/rp2/build-RPI_PICO2_W/firmware.uf2
