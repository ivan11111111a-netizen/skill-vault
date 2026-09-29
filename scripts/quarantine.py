#!/usr/bin/env python3
"""Put a candidate into quarantine and defuse its instructions for agents.

    python scripts/quarantine.py https://github.com/someone/skill
    python scripts/quarantine.py /path/to/folder --name my-candidate
    python scripts/quarantine.py lab/candidates/already-here     # defuse only

Why a separate step. Claude Code picks up `CLAUDE.md` from the working tree
automatically, so a cloned candidate's file becomes instructions **before** a
human has decided whether to trust it. For a repository whose first rule is
"a foreign skill's text is data, not instructions", that is a hole in the floor.
So such files are renamed to `<name>.quarantined`: still readable by eye, but
no longer picked up on their own.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import stat
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import repo_root  # noqa: E402

SUFFIX = ".quarantined"
ORIGIN = ".skill-lib-origin"  # where it came from: read by promote.py

# Files agents pick up as instructions without asking.
AGENT_FILES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md", ".cursorrules")


def neutralize(cand: Path) -> list[str]:
    """Rename instructions for agents. Returns what was defused."""
    done = []
    for p in sorted(cand.rglob("*")):
        if p.is_file() and p.name in AGENT_FILES:
            p.rename(p.with_name(p.name + SUFFIX))
            done.append(p.relative_to(cand).as_posix())
    return done


def _git(dest: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(dest), *args],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def read_origin(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
    return data


def inherited_origin(src: Path, candidates: Path) -> dict:
    """Look for .skill-lib-origin in the parents: a sub-skill split out of a large
    repository must not lose its source along with the deleted .git."""
    for p in [src, *src.parents]:
        f = p / ORIGIN
        if f.is_file():
            info = read_origin(f)
            rel = src.relative_to(p).as_posix()
            if rel:
                info["path"] = rel
            return info
        if p.resolve() == candidates.resolve():
            break
    return {}


def write_origin(dest: Path, info: dict) -> None:
    # a commit without a source is still enough: a local clone without a remote is worth remembering
    if not info.get("source") and not info.get("commit"):
        return
    lines = [f"{k}: {v}" for k, v in info.items() if v]
    with (dest / ORIGIN).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def name_from(source: str) -> str:
    tail = re.sub(r"[/\\]+$", "", source).split("/")[-1].split("\\")[-1]
    return re.sub(r"\.git$", "", tail) or "candidate"


def main() -> int:
    ap = argparse.ArgumentParser(description="put a candidate into quarantine")
    ap.add_argument("source", help="repository URL, folder path, or a candidate already in quarantine")
    ap.add_argument("--name", default=None, help="folder name inside lab/candidates/")
    args = ap.parse_args()

    root = repo_root()
    candidates = root / "lab" / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)

    is_url = "://" in args.source or args.source.startswith("git@")
    src_path = None if is_url else Path(args.source).expanduser()

    # A path already inside quarantine is defused in place. With --name we copy
    # instead: that is how one candidate is split out of a repository with dozens
    # of skills, since the funnel checks one at a time.
    in_quarantine = (src_path is not None and src_path.is_dir()
                     and candidates.resolve() in src_path.resolve().parents)
    origin: dict = {}
    if in_quarantine and args.name:
        origin = inherited_origin(src_path.resolve(), candidates)

    if in_quarantine and not args.name:
        dest = src_path.resolve()
    else:
        dest = candidates / (args.name or name_from(args.source))
        if dest.exists():
            print(f"already exists: {dest.relative_to(root)}. Remove it or pass --name", file=sys.stderr)
            return 1
        if is_url:
            rc = subprocess.run(["git", "clone", "--depth", "1", args.source, str(dest)]).returncode
            if rc:
                print("git clone failed", file=sys.stderr)
                return 1
        elif src_path.is_dir():
            shutil.copytree(src_path, dest)
        else:
            print(f"no such folder: {args.source}", file=sys.stderr)
            return 1

    # Record the source BEFORE deleting .git, or the commit is lost for good and
    # promote.py has nothing to compare updates against.
    git_dir = dest / ".git"
    if git_dir.is_dir():
        origin = {
            "source": args.source if is_url else _git(dest, "remote", "get-url", "origin"),
            "commit": _git(dest, "rev-parse", "HEAD"),
            "fetched": dt.date.today().isoformat(),
        }
        # We don't need the candidate's .git: its history is not reviewed, only weight and noise.
        # On Windows git objects are read-only and rmtree fails on them; with
        # ignore_errors this used to leave a half-deleted .git behind silently.
        def force(func, path, _exc):
            os.chmod(path, stat.S_IWRITE)
            func(path)

        if sys.version_info >= (3, 12):
            shutil.rmtree(git_dir, onexc=force)
        else:
            shutil.rmtree(git_dir, onerror=force)

    if origin:
        write_origin(dest, origin)

    done = neutralize(dest)
    rel = dest.relative_to(root).as_posix()
    print(f"in quarantine: {rel}")
    if done:
        print(f"defused instructions for agents ({len(done)}), renamed to *{SUFFIX}:")
        for d in done:
            print(f"  {d}")
    else:
        print("no instructions for agents found")
    if origin.get("commit"):
        print(f"source recorded: {origin.get('source', '')} @ {origin['commit'][:7]}")

    print("\nnext:")
    print(f"  python scripts/intake.py {rel}")
    print(f"  python scripts/audit.py  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
