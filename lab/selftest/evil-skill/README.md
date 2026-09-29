# Test target for audit.py

This is **not a skill** but a fixture: a folder deliberately stuffed with the signs
`scripts/audit.py` must find. Nothing inside works: every address points into the
`.invalid` zone, which never resolves, and the commands are never run.

The fixture never goes into `vault/` and is never linked into `.claude/skills/`.
Run the check with `python scripts/selftest.py`.
