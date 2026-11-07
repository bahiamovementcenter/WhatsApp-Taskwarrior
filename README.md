# WhatsApp-Taskwarrior

Turn WhatsApp messages into [Taskwarrior](https://taskwarrior.org) tasks, built on
[verygoodplugins/whatsapp-mcp](https://github.com/verygoodplugins/whatsapp-mcp)
(vendored as a git submodule in `third_party/whatsapp-mcp`).

## Stack

| Part | Language | Location |
| --- | --- | --- |
| WhatsApp bridge (whatsmeow, REST on :8080) | Go 1.26+, CGO | `third_party/whatsapp-mcp/whatsapp-bridge` |
| WhatsApp MCP server | Python 3.11+ (uv) | `third_party/whatsapp-mcp/whatsapp-mcp-server` |
| This project | Python 3.11+ (uv) | `src/whatsapp_taskwarrior` |
| Tooling scripts | Bash | `scripts/` |

## Getting started

**Dev Container (recommended):** open the repo in VS Code / Codespaces and pick
"Reopen in Container". The container includes Python 3.12, uv, Go 1.26, gcc (for
go-sqlite3), ffmpeg, sqlite3, shellcheck, shfmt and Taskwarrior, then runs
`scripts/bootstrap.sh`.

**Local Linux:** install the tools above, then:

```bash
git clone --recurse-submodules https://github.com/bahiamovementcenter/WhatsApp-Taskwarrior
```

```bash
make bootstrap
```

## Common tasks

```bash
make bridge   # run the Go bridge; scan the QR code with WhatsApp on first run
make mcp      # run the MCP server (stdio)
make check    # lint (ruff, shellcheck, shfmt, go vet) + tests
make help     # list all targets
```

Updating the upstream whatsapp-mcp pin:

```bash
git submodule update --remote third_party/whatsapp-mcp
```

## Security

The bridge's `store/` directory holds unencrypted linked-device credentials and
message history. It is git-ignored; never commit it. `.env` is ignored too — copy
from `.env.example`.
