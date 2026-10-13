#!/usr/bin/env python3
"""Regression test for the funnel: audit.py must find every rule listed in
EXPECTED on the fixtures. Run it after every change to RULES in audit.py.

    python scripts/selftest.py

Added a rule to RULES? Add a trigger to lab/selftest/evil-skill/ and the rule
name here, or nothing checks the rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit import analyse  # noqa: E402
from skilllib import repo_root  # noqa: E402

EXPECTED = [
    # running someone else's code
    "pipe-to-shell", "remote-install", "run-remote-pkg", "eval-exec", "base64-exec",
    "shell-true",
    # secrets and configuration
    "read-secrets", "claude-config", "dotenv", "token-grep",
    # network
    "outbound-post", "outbound-get", "hardcoded-host", "remote-instructions",
    # destructive or outside the project
    "destructive", "write-outside", "git-push", "chmod-sudo",
    # the plugin around the skill
    "plugin-root-ref",
    # pressure on the reviewer
    "prompt-injection", "self-approval", "hidden-unicode",
    # derived from parsing the skill rather than from the regexes
    "shell-injection", "file-reference", "hooks", "allowed-tools", "mcp-server",
    "thin",
    # unreadable
    "binary", "long-line",
]

# Not covered by the fixture: `large-file` needs a file over 2 MB, and keeping
# one in the repository costs more than the rule is worth.

# The second fixture is a plugin with a clean skill inside. Only findings marked
# plugin: count, otherwise a pass would not prove the plugin root was read at all.
EXPECTED_PLUGIN = ["plugin-hooks", "mcp-server"]

CHECKS = [
    ("evil-skill", EXPECTED, ""),
    ("evil-plugin/skills/inner", EXPECTED_PLUGIN, "plugin:"),
]


def main() -> int:
    base = repo_root() / "lab" / "selftest"
    for rel, expected, prefix in CHECKS:
        fixture = base / rel
        if not fixture.is_dir():
            print(f"no fixture: {fixture}", file=sys.stderr)
            return 2

        res = analyse(fixture)
        if "error" in res:
            print(f"audit failed on {rel}: {res['error']}", file=sys.stderr)
            return 2

        found = {f["id"] for f in res["findings"] if f["file"].startswith(prefix)}
        missing = [r for r in expected if r not in found]
        if missing:
            print(f"selftest: {rel}: NOT FOUND: " + " ".join(missing), file=sys.stderr)
            return 1

    print(f"selftest: ok, {len(EXPECTED)} rules on evil-skill, "
          f"{len(EXPECTED_PLUGIN)} on evil-plugin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
