SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c

WA       := third_party/whatsapp-mcp
BRIDGE   := $(WA)/whatsapp-bridge
MCP      := $(WA)/whatsapp-mcp-server
SH_FILES := $(shell git ls-files '*.sh')

export GOTOOLCHAIN ?= auto
export CGO_ENABLED := 1

.PHONY: help bootstrap bridge bridge-build mcp lint fmt test check clean

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-14s %s\n", $$1, $$2}'

bootstrap: ## Install all deps (submodules, Go, Python)
	scripts/bootstrap.sh

bridge: ## Run the WhatsApp Go bridge (shows QR on first run)
	cd $(BRIDGE) && go run .

bridge-build: ## Build the bridge binary into bin/
	mkdir -p bin && cd $(BRIDGE) && go build -o $(CURDIR)/bin/whatsapp-bridge .

mcp: ## Run the WhatsApp MCP server (stdio)
	cd $(MCP) && uv run main.py

lint: ## Lint Python, shell, and Go
	uv run ruff check .
	uv run ruff format --check .
	@if [[ -z "$(SH_FILES)" ]]; then :; \
	elif command -v shellcheck >/dev/null && command -v shfmt >/dev/null; then \
	  shellcheck $(SH_FILES) && shfmt -d -i 2 -ci $(SH_FILES); \
	else echo "warning: shellcheck/shfmt not installed; skipping shell lint" >&2; fi
	cd $(BRIDGE) && go vet ./...

fmt: ## Auto-format Python and shell
	uv run ruff format .
	uv run ruff check --fix .
	@if [[ -n "$(SH_FILES)" ]]; then shfmt -w -i 2 -ci $(SH_FILES); fi

test: ## Run tests
	uv run pytest

check: lint test ## Lint + test

clean: ## Remove build artifacts
	rm -rf bin .pytest_cache .ruff_cache
