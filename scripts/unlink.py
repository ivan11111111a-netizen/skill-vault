#!/usr/bin/env python3
"""Remove linked skills from .claude/skills/: both symlinks and the copies made
by link.py. With no arguments removes all of ours. Never touches foreign folders.

    python scripts/unlink.py               # everything linked from the vault
    python scripts/unlink.py pdf xlsx      # only the named ones
    python scripts/unlink.py --target /path
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import COPY_MARKER as MARKER  # noqa: E402
from skilllib import linked_by_us, repo_root  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="unlink vault skills from a project")
    ap.add_argument("names", nargs="*")
    ap.add_argument("--target", default=None)
    args = ap.parse_args()

    root = repo_root()
    vault = (root / "vault").resolve()
    target = Path(args.target).expanduser().resolve() if args.target else Path.cwd()
    dest = target / ".claude" / "skills"

    if not dest.is_dir():
        print("nothing to unlink")
        return 0

    names = args.names or [p.name for p in sorted(dest.iterdir()) if linked_by_us(p, vault)]
    if not names:
        print("no skills from the vault are linked")
        return 0

    for name in names:
        p = dest / name
        if not os.path.lexists(p):
            continue
        if p.is_symlink():
            p.unlink()
            print(f"unlinked: {name}")
        elif (p / MARKER).is_file():
            shutil.rmtree(p)
            print(f"unlinked (copy removed): {name}")
        else:
            print(f"skipped (not linked by us): {name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
