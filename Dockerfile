FROM ubuntu:22.04

# Install build and runner dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    cmake \
    python3 python3-pip python3-venv \
    git wget curl unzip \
    libcurl4-openssl-dev \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /workspace

# Clone MicroPython + submodules
RUN git clone --recursive https://github.com/micropython/micropython.git

# Copy your own project files
COPY picobridge /workspace/picobridge
COPY build.sh /workspace/build.sh
RUN chmod +x /workspace/build.sh

# Optional: Set environment
ENV PICO_PLATFORM=rp2040

# Optional: Create Python venv
RUN python3 -m venv /workspace/mpy-env && \
    /workspace/mpy-env/bin/pip install --upgrade pip

# Install GitHub Actions runner
WORKDIR /actions-runner
RUN curl -o actions-runner-linux-x64.tar.gz -L https://github.com/actions/runner/releases/download/v2.329.0/actions-runner-linux-x64-2.329.0.tar.gz && \
    tar xzf actions-runner-linux-x64.tar.gz && \
    rm actions-runner-linux-x64.tar.gz

# Add entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
