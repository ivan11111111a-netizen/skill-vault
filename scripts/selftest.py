#!/usr/bin/env python3
"""Regression test for the funnel: audit.py must find every rule listed in
EXPECTED on the fixture. Run it after every change to RULES in audit.py.

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
    "outbound-post", "outbound-get", "hardcoded-host",
    # destructive or outside the project
    "destructive", "write-outside", "git-push", "chmod-sudo",
    # pressure on the reviewer
    "prompt-injection", "self-approval",
    # derived from parsing the skill rather than from the regexes
    "shell-injection", "file-reference", "hooks", "allowed-tools", "mcp-server",
    "thin",
    # unreadable
    "binary", "long-line",
]

# Not covered by the fixture: `large-file` needs a file over 2 MB, and keeping
# one in the repository costs more than the rule is worth.


def main() -> int:
    fixture = repo_root() / "lab" / "selftest" / "evil-skill"
    if not fixture.is_dir():
        print(f"no fixture: {fixture}", file=sys.stderr)
        return 2

    res = analyse(fixture)
    if "error" in res:
        print(f"audit failed: {res['error']}", file=sys.stderr)
        return 2

    found = {f["id"] for f in res["findings"]}
    missing = [r for r in EXPECTED if r not in found]
    if missing:
        print("selftest: NOT FOUND: " + " ".join(missing), file=sys.stderr)
        return 1

    print(f"selftest: ok, all {len(EXPECTED)} rules found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
