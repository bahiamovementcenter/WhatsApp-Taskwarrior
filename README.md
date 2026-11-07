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

## Using it

The safe path, one step at a time:

1. **Pair the bridge on your own computer:** `make bridge`, scan the QR code with
   WhatsApp (Linked devices). This can't be done in a cloud session.
2. **Pick the chats:** `cp wtw.example.toml wtw.toml`, then
   `uv run wtw chats --groups` and copy the JIDs of the groups you want into
   `[whatsapp.chats]`. Nothing else is ever read.
3. **Trial on a separate task list first:** set `data_location = ".wtw/taskdata"`
   in `wtw.toml` so trial runs can't touch your real tasks.
4. **Run the loop** (see `CLAUDE.md`): `wtw pull`, the agent writes a plan,
   `wtw apply plan.json batch.json` shows a dry run, you add `--apply`.
5. When the trial looks right, remove `data_location` to use your real list.
   Every `--apply` backs up the Taskwarrior data to `.wtw/backups/` first.

What `wtw` guarantees: it opens `messages.db` read-only and never calls the
bridge, so it can't send anything to WhatsApp; it only reads allowlisted chats;
every task must cite a real message; it never deletes tasks or edits tasks it
didn't create; re-running a plan doesn't duplicate tasks; message text is passed
to Taskwarrior as JSON data, never on the command line. For the agent,
`.claude/settings.json` denies the MCP server's send tools and `--apply`.

## Security

The bridge's `store/` directory holds unencrypted linked-device credentials and
message history. It is git-ignored; never commit it. `.env` is ignored too — copy
from `.env.example`.
