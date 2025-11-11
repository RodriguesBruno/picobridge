FROM ubuntu:22.04

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    cmake \
    python3 python3-pip python3-venv \
    git wget curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Optional Python venv
RUN python3 -m venv /workspace/mpy-env && \
    /workspace/mpy-env/bin/pip install --upgrade pip

# Set environment for MicroPython build
ENV PICO_PLATFORM=rp2040

# Set up working directory
WORKDIR /workspace

# You don’t need to COPY anything here — GitHub Actions will checkout your repo
