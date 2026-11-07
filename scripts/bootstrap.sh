#!/usr/bin/env bash
# Set up the local dev environment: submodules, Go modules, Python venvs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

need() { command -v "$1" >/dev/null 2>&1 || {
  echo "missing required tool: $1" >&2
  exit 1
}; }
need git
need go
need uv

echo "==> Syncing submodules"
git submodule update --init --recursive

# whatsapp-bridge requires Go 1.26+; let the go command fetch it if older.
export GOTOOLCHAIN="${GOTOOLCHAIN:-auto}"
export CGO_ENABLED=1

echo "==> Downloading Go modules (whatsapp-bridge)"
(cd third_party/whatsapp-mcp/whatsapp-bridge && go mod download)

echo "==> Syncing Python deps (whatsapp-mcp-server)"
(cd third_party/whatsapp-mcp/whatsapp-mcp-server && uv sync --extra dev)

echo "==> Syncing Python deps (this project)"
uv sync

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created .env from .env.example"
fi

echo "Done. Next: 'make bridge' to pair WhatsApp (QR code), then 'make mcp'."
