# WhatsApp-Taskwarrior

An agent-managed Taskwarrior list compiled from WhatsApp group chats. The agent
reads allowlisted chats, decides what is a task, and proposes changes. The
`wtw` CLI (`src/whatsapp_taskwarrior`) is the only thing that writes to
Taskwarrior, and it enforces the safety rules in code.

This file is for any coding or operating agent (OpenClaw, Claude Code, Codex, …).
`CLAUDE.md` imports it and adds only Claude Code settings.

## Running the loop

The instructions for turning chats into tasks are one agent-neutral skill:
**`skills/whatsapp-taskwarrior/SKILL.md`**. Read it before running `wtw` and follow
its rules. It is the single copy: Claude Code finds it through
`.claude/skills/` (a symlink), and openclaw-fly loads it from this repo's flake.
Change the loop there, not in a runtime-specific copy.

In this checkout, run `uv run wtw ...`, keep the batch and plan in `work/`
(git-ignored), and never write in `.wtw/` (cursors and backups).

## Safety rules (do not work around these)

- **Never send anything to WhatsApp**, and don't reach the bridge's HTTP API (port 8080).
- **Only allowlisted chats.** Don't read other chats to make tasks.
- **Never delete tasks** and never change tasks that lack the `wa_key` UDA (they
  aren't ours). Don't run `task` directly to change data.
- **Don't write plans yourself.** `wtw apply` only shows the dry run. Writing is
  `wtw-apply`, a separate command so every runtime can require a person's approval
  for it. Never look for another way to write (running the Python module, editing
  Taskwarrior data, …).
- Never read or copy the bridge's `store/` folder (login keys and message history).

How each runtime enforces this:

| Runtime | Instructions | Enforcement |
| --- | --- | --- |
| Claude Code in this repo | `CLAUDE.md` → this file, skill via `.claude/skills/` | `.claude/settings.json` denies WhatsApp send tools, `wtw-apply`, port 8080, `store/` |
| OpenClaw (openclaw-fly) | skill from this repo's flake | exec allowlist has only `wtw`, so each `wtw-apply` needs your approval; file tools limited to the workspace; no group posting |
| Anything else | point it at this file | set it up so `wtw` may run but `wtw-apply` needs a person |

## Dev

`examples/demo/` has a sample chat and the plans an agent should write for it;
use it as the reference for what to turn into tasks. `just demo` runs it.

`just check` runs lint and tests. Tests use a throwaway Taskwarrior data dir and a
fixture SQLite DB; they never touch real data.
