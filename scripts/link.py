#!/usr/bin/env python3
"""Link a skill from the vault into the current project's .claude/skills/.

    python scripts/link.py pdf xlsx             # into the current project
    python scripts/link.py --target /path pdf   # into the given one
    python scripts/link.py --copy pdf           # force a copy

A symlink by default: edits in the vault show up at once, and copies never drift.
If a symlink cannot be created, the script copies the folder and marks it with
.skill-lib-copy, so unlink.py knows the copy is its own.

Exit codes: 0 linked, 1 error, 2 no names given.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import COPY_MARKER as MARKER  # noqa: E402
from skilllib import SKILL_FILE, linked_by_us, repo_root  # noqa: E402

USAGE = ".skill-lib-usage"


def available(vault: Path) -> list[str]:
    if not vault.is_dir():
        return []
    return sorted(d.name for d in vault.iterdir() if (d / SKILL_FILE).is_file())


def remove(path: Path) -> None:
    """Remove a symlink or a folder. lexists: exists() says a broken link is absent."""
    if path.is_symlink():
        path.unlink()
    elif os.path.lexists(path):
        shutil.rmtree(path)


def try_symlink(src: Path, dst: Path) -> bool:
    """True only if what we got really is a symlink.

    Check the result, not the absence of an exception: `ln -s` in Git Bash, for
    one, silently copies the folder without the right permissions and reports
    success. os.symlink has no such trap, but the check costs one line."""
    try:
        os.symlink(src, dst, target_is_directory=True)
    except (OSError, NotImplementedError):
        return False
    if dst.is_symlink():
        return True
    remove(dst)
    return False


def link_one(root: Path, name: str, dest: Path, force_copy: bool) -> int:
    src = root / "vault" / name
    dst = dest / name

    if not (src / SKILL_FILE).is_file():
        print(f"no such skill in the vault: {name}", file=sys.stderr)
        return 1
    # A symlink that points somewhere other than our vault is foreign too;
    # otherwise any link would be taken as ours and silently overwritten.
    if os.path.lexists(dst) and not linked_by_us(dst, root / "vault"):
        print(f"the project already has its own: {dst}, leaving it alone", file=sys.stderr)
        return 1

    remove(dst)

    if not force_copy and try_symlink(src, dst):
        print(f"linked (symlink): {name} -> {src}")
    else:
        shutil.copytree(src, dst)
        (dst / MARKER).write_text(str(src) + "\n", encoding="utf-8")
        print(f"linked (copy): {name}. Edit it in the vault "
              "and link it again")

    # Real-usage counter: one date line per link. build_index.py reads it; it
    # decides trial -> approved and what to throw out. Best effort: bookkeeping
    # must never break the link itself.
    try:
        with (src / USAGE).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(dt.date.today().isoformat() + "\n")
    except OSError:
        pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="link a skill from the vault into a project")
    ap.add_argument("names", nargs="*", help="skill names in vault/")
    ap.add_argument("--target", default=None, help="project folder (the current one by default)")
    ap.add_argument("--copy", action="store_true", help="copy without trying a symlink")
    args = ap.parse_args()

    root = repo_root()
    if not args.names:
        print("name the skills. Available:", file=sys.stderr)
        names = available(root / "vault")
        for n in names:
            print(f"  {n}", file=sys.stderr)
        if not names:
            print("  (the vault is empty)", file=sys.stderr)
        return 2

    target = Path(args.target).expanduser().resolve() if args.target else Path.cwd()
    dest = target / ".claude" / "skills"
    dest.mkdir(parents=True, exist_ok=True)

    for name in args.names:
        rc = link_one(root, name, dest, args.copy)
        if rc:
            return rc

    print()
    print(f'to unlink: "{sys.executable}" "{root / "scripts" / "unlink.py"}" '
          + " ".join(args.names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
