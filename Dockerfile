# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS builder

# Install build dependencies for NextViper
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libvulkan-dev \
    libpq-dev \
    libcurl4-openssl-dev \
    python3 \
    curl \
    openssl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone and compile NextViper
WORKDIR /build
RUN git clone https://github.com/nuratix/nextviper.git . \
    && cmake -S . -B build-cmake -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build-cmake -j$(nproc)

# --- Runtime Stage ---
FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    libvulkan1 \
    libpq5 \
    libcurl4 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy NextViper compiled binary
COPY --from=builder /build/build-cmake/bin/nextviper /usr/local/bin/nextviper

# Copy NextViper music backend source code
WORKDIR /app
COPY src/ /app/src/

EXPOSE 8080

ENV PORT=8080
ENV HOST=0.0.0.0

CMD ["/usr/local/bin/nextviper", "run", "/app/src/server.nv"]
