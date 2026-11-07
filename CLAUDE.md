# WhatsApp-Taskwarrior

An agent-managed Taskwarrior list compiled from WhatsApp group chats. The agent
reads allowlisted chats, decides what is a task, and proposes changes. The
`wtw` CLI (`src/whatsapp_taskwarrior`) is the only thing that writes to
Taskwarrior, and it enforces the safety rules below.

## Safety rules (do not work around these)

- **Never send anything to WhatsApp.** No messages, reactions, files, voice notes
  or read receipts. The send tools of the `whatsapp` MCP server are denied in
  `.claude/settings.json`; don't reach the bridge's HTTP API (port 8080) either.
- **Only allowlisted chats.** `wtw` reads only the JIDs in `wtw.toml`. Don't read
  other chats through the MCP server to make tasks.
- **Never delete tasks** and never change tasks that lack the `wa_key` UDA (they
  aren't ours). Don't run `task` directly to change data.
- **Don't apply plans yourself.** `wtw apply ... --apply` is denied for the agent
  for now; write the plan, show the dry run, and let Ash apply it.
- Never read or copy the bridge's `store/` folder (login keys and message history).

## The loop

1. `uv run wtw pull -o .wtw/batch.json` reads new messages from allowlisted chats.
   It changes nothing.
2. Read the batch. For each actionable message (a request, a commitment, a
   deadline, "can someone…"), write an operation into `.wtw/plan.json`.
   Use the whatsapp MCP server's read tools (e.g. `get_message_context`) only for
   context on messages already in the batch.
3. `uv run wtw apply .wtw/plan.json .wtw/batch.json` shows the dry run. Fix any
   rejected operations, then hand the dry run to Ash.
4. Ash runs the same command with `--apply`: Taskwarrior data is backed up to
   `.wtw/backups/`, tasks are written, and the read cursors move forward.

Even a batch with no tasks needs an empty plan applied, so the cursors advance.

## Plan format

```json
{
  "version": 1,
  "operations": [
    {"op": "add", "source": {"chat_jid": "…@g.us", "message_id": "…"},
     "description": "Book the venue for Saturday", "due": "2026-11-14", "priority": "M", "tags": ["venue"]},
    {"op": "annotate", "task": "<wa_key>", "source": {…}, "text": "Venue said they need a deposit"},
    {"op": "complete", "task": "<wa_key>", "source": {…}}
  ]
}
```

- `source` must be a message in the batch; the message it cites is checked
  against `messages.db` too.
- A task's `wa_key` is `<chat_jid>/<message_id>` of the message that created it.
  List them with `uv run wtw tasks` (read only).
- Adding a task for a message that already has one is skipped, so re-running is safe.

## Dev

`examples/demo/` has a sample chat and the plans an agent should write for it;
use it as the reference for what to turn into tasks. `just demo` runs it.

`just check` runs lint and tests. Tests use a throwaway Taskwarrior data dir and a
fixture SQLite DB; they never touch real data.
