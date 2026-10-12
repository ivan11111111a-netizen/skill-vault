# Test target for audit.py: a plugin

A fixture, like `evil-skill/`, but shaped as a Claude Code plugin. Its skill
`skills/inner/` is clean; the risk is in the plugin around it: a `SessionStart` hook in
`hooks/hooks.json` and an MCP server in `.claude-plugin/plugin.json`. A skill split out
of a marketplace looks exactly like `inner`, so the audit has to read the plugin root.

Nothing here is ever installed: the hook only echoes, the server file does not exist.
Run the check with `python scripts/selftest.py`.
