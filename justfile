# Run `just` to list recipes.

set shell := ["bash", "-euo", "pipefail", "-c"]

wa := "third_party/whatsapp-mcp"
bridge_dir := wa / "whatsapp-bridge"
mcp_dir := wa / "whatsapp-mcp-server"

# whatsapp-bridge needs Go 1.26+ (let go fetch it) and CGO for go-sqlite3.
export GOTOOLCHAIN := env("GOTOOLCHAIN", "auto")
export CGO_ENABLED := "1"

[private]
default:
    @just --list

# Install all deps (submodules, Go, Python)
bootstrap:
    scripts/bootstrap.sh

# Run the WhatsApp Go bridge (shows a QR code on first run)
bridge:
    cd {{ bridge_dir }} && go run .

# Build the bridge binary into bin/
bridge-build:
    mkdir -p bin && cd {{ bridge_dir }} && go build -o {{ justfile_directory() }}/bin/whatsapp-bridge .

# Run the WhatsApp MCP server (stdio)
mcp:
    cd {{ mcp_dir }} && uv run main.py

# List chats, to pick JIDs for the allowlist in wtw.toml
chats:
    uv run wtw chats --groups

# Read new messages from allowlisted chats into work/batch.json (changes nothing)
pull:
    uv run wtw pull -o work/batch.json

# Dry run: show what work/plan.json would change (nothing written)
check-plan plan="work/plan.json" batch="work/batch.json":
    uv run wtw apply {{ plan }} {{ batch }}

# Write an approved plan: back up Taskwarrior, write tasks, advance cursors (for you, not the agent)
apply plan="work/plan.json" batch="work/batch.json":
    uv run wtw-apply {{ plan }} {{ batch }}

# Walk through the whole flow on fake chat data, into a scratch task list (.wtw-demo/)
demo:
    scripts/demo.sh

# Lint Python, shell, and Go
lint: lint-sh
    uv run ruff check .
    uv run ruff format --check .
    cd {{ bridge_dir }} && go vet ./...

[private]
lint-sh:
    #!/usr/bin/env bash
    set -euo pipefail
    mapfile -t files < <(git ls-files '*.sh')
    (( ${#files[@]} )) || exit 0
    if command -v shellcheck >/dev/null && command -v shfmt >/dev/null; then
      shellcheck "${files[@]}"
      shfmt -d -i 2 -ci "${files[@]}"
    else
      echo "warning: shellcheck/shfmt not installed; skipping shell lint" >&2
    fi

# Auto-format Python and shell
fmt:
    uv run ruff format .
    uv run ruff check --fix .
    git ls-files -z '*.sh' | xargs -0 -r shfmt -w -i 2 -ci

# Run tests
test *args:
    uv run pytest {{ args }}

# Lint + test
check: lint test

# Remove build artifacts
clean:
    rm -rf bin .pytest_cache .ruff_cache
