FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# System deps:
#  - build-essential: CGO toolchain for github.com/mattn/go-sqlite3 (whatsapp-bridge)
#  - sqlite3: inspect the bridge's store/*.db files
#  - ffmpeg: voice-note conversion / media frames in whatsapp-mcp
#  - shellcheck, shfmt: shell linting/formatting
#  - taskwarrior: the task backend this project integrates with
#  - just: command runner (see justfile)
RUN apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        build-essential pkg-config sqlite3 ffmpeg \
        shellcheck shfmt taskwarrior jq just \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
