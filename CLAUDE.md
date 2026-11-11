@AGENTS.md

## Claude Code specifics

- The loop is the `whatsapp-taskwarrior` skill (`.claude/skills/`, a link to
  `skills/whatsapp-taskwarrior/`).
- `.claude/settings.json` denies the `whatsapp` MCP server's send tools, `wtw-apply`
  and `--apply`, `curl` to port 8080, `task delete`/`purge`, reading `store/`, and
  writing in `.wtw/`. When a plan's dry run is ready, give Ash the
  `uv run wtw-apply work/plan.json work/batch.json` command to run.
- Use the `whatsapp` MCP server's read tools (e.g. `get_message_context`) only for
  context on messages already in the batch.
