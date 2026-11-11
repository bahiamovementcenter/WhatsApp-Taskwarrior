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
go-sqlite3), ffmpeg, sqlite3, shellcheck, shfmt, just and Taskwarrior, then runs
`scripts/bootstrap.sh`.

**Nix:** `nix develop` gives you a shell with every tool above at pinned
versions (Python 3.12, uv, Go 1.26, Taskwarrior 3, just, and the rest). Clone
with `--recurse-submodules` first. With direnv, put `use flake` in `.envrc`.
You can also build and run the pieces directly:

```bash
nix run .#wtw -- --help          # the wtw CLI
nix run .#whatsapp-bridge        # the WhatsApp bridge (run it from the folder that should hold store/)
nix flake check                  # build both and run wtw's tests
```

The flake needs Nix 2.27 or newer (it includes the whatsapp-mcp submodule).
Update pinned versions with `nix flake update`.

**Local Linux:** install the tools above (including [just](https://github.com/casey/just), e.g. `apt install just` or `uv tool install rust-just`), then:

```bash
git clone --recurse-submodules https://github.com/bahiamovementcenter/WhatsApp-Taskwarrior
```

```bash
just bootstrap
```

## Common tasks

```bash
just bridge   # run the Go bridge; scan the QR code with WhatsApp on first run
just mcp      # run the MCP server (stdio)
just check    # lint (ruff, shellcheck, shfmt, go vet) + tests
just pull     # read new messages from allowlisted chats into work/batch.json
just check-plan  # dry run of work/plan.json
just apply    # write an approved plan (wtw-apply; you run this, not the agent)
just          # list all recipes
```

Updating the upstream whatsapp-mcp pin:

```bash
git submodule update --remote third_party/whatsapp-mcp
```

## Try it on sample data first

```bash
just demo
```

This runs the whole flow on a made-up group chat ("Studio Team", two days of
messages in `examples/demo/chat.json`) without WhatsApp or a phone. It builds a
fake bridge database, runs `wtw pull`, shows the dry run of the plans the agent
would write (`examples/demo/plan-day*.json`), applies them into a scratch task
list, and prints the result: new tasks on day 1, then notes, a new task and two
completions on day 2. It also shows that re-running a plan does nothing and that
a plan citing a made-up message is rejected. Everything goes in `.wtw-demo/`;
your real tasks and `~/.taskrc` are never touched.

## Using it

The safe path, one step at a time:

1. **Pair the bridge on your own computer:** `just bridge`, scan the QR code with
   WhatsApp (Linked devices). This can't be done in a cloud session.
2. **Pick the chats:** `cp wtw.example.toml wtw.toml`, then
   `uv run wtw chats --groups` and copy the JIDs of the groups you want into
   `[whatsapp.chats]`. Nothing else is ever read.
3. **Trial on a separate task list first:** set `data_location = ".wtw/taskdata"`
   in `wtw.toml` so trial runs can't touch your real tasks.
4. **Run the loop** (see the skill below): `wtw pull`, the agent writes a plan,
   `wtw apply plan.json batch.json` shows a dry run, and once you approve it,
   `wtw-apply plan.json batch.json` writes it.
5. When the trial looks right, remove `data_location` to use your real list.
   Every `wtw-apply` backs up the Taskwarrior data to `.wtw/backups/` first.

## Agents

The agent's instructions are one agent-neutral skill,
[`skills/whatsapp-taskwarrior/SKILL.md`](skills/whatsapp-taskwarrior/SKILL.md), and
[`AGENTS.md`](AGENTS.md) for working in this repo. Claude Code reads them through
`CLAUDE.md` and `.claude/skills/`; OpenClaw ([openclaw-fly](https://github.com/bahiamovementcenter/openclaw-fly))
loads it from this repo as a flake input. Any other agent can be
pointed at the same files.

`wtw` can only read chats and show dry runs. Writing to Taskwarrior is the separate
`wtw-apply` command, so in any runtime you can allow `wtw` and require your approval
for `wtw-apply`: Claude Code denies it in `.claude/settings.json`, and openclaw-fly
leaves it off the exec allowlist so OpenClaw asks you each time.

What `wtw` guarantees: it opens `messages.db` read-only and never calls the
bridge, so it can't send anything to WhatsApp; it only reads allowlisted chats;
every task must cite a real message; it never deletes tasks or edits tasks it
didn't create; re-running a plan doesn't duplicate tasks; message text is passed
to Taskwarrior as JSON data, never on the command line. For the agent,
`.claude/settings.json` denies the MCP server's send tools and `wtw-apply`.

## Security

The bridge's `store/` directory holds unencrypted linked-device credentials and
message history. By default the bridge stores every chat the account sees,
including personal ones. The flake's bridge carries a patch
(`nix/patches/bridge-chat-allowlist.patch`) that limits this: set
`WHATSAPP_ALLOWED_CHATS` to the chats to keep, as comma-separated `jid=label`
entries (label optional), and messages from any other chat are neither stored
nor printed. Put `chats_env = "WHATSAPP_ALLOWED_CHATS"` under `[whatsapp]` in
`wtw.toml` and `wtw` reads the same list, so chat IDs can live in a secret
instead of the config file. Every group the account is in keeps a
name-only row (recorded on connect), so `wtw chats --groups` can still list
them. `store/` is git-ignored; never commit it. `.env` is ignored too — copy
from `.env.example`.
