FROM ubuntu:22.04

# Install system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    cmake \
    python3 python3-pip python3-venv \
    git wget curl nano \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /workspace

# Clone MicroPython + submodules
RUN git clone --recursive https://github.com/micropython/micropython.git

# Optional: Install CMake 3.25+ if needed
# (Only needed if your build fails due to too-old CMake)
# RUN wget https://github.com/Kitware/CMake/releases/download/v3.25.2/cmake-3.25.2-linux-x86_64.sh && \
#     chmod +x cmake-3.25.2-linux-x86_64.sh && \
#     ./cmake-3.25.2-linux-x86_64.sh --skip-license --prefix=/usr/local && \
#     rm cmake-3.25.2-linux-x86_64.sh

# Copy your own project files (edit this to match your structure)
COPY picobridge /workspace/picobridge

# Set env var
ENV PICO_PLATFORM=rp2040

# Optional: Create Python venv
RUN python3 -m venv /workspace/mpy-env && \
    /workspace/mpy-env/bin/pip install --upgrade pip

# Entry script for GitHub Actions runner or CI
COPY build.sh /workspace/build.sh
RUN chmod +x /workspace/build.sh
