#!/usr/bin/env python3
"""Move an approved candidate into the vault: record status, source and review,
keep the cases it was checked with, and rebuild INDEX.md.

    python3 scripts/promote.py lab/candidates/pdf-tools \
        --status trial --admitted audited --tags docs,pdf
    python3 scripts/promote.py lab/candidates/pdf-tools \
        --status trial --delta "+0.50" --cases docs      # after an eval: measured

The final decision is always the human's; the script only records it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import find_skill_dirs, repo_root, skill_meta  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--status", default="trial", choices=["trial", "approved", "deprecated"])
    ap.add_argument("--source", default="", help="where it came from: repository URL")
    ap.add_argument("--commit", default="", help="commit or tag of the source")
    ap.add_argument("--tags", default="")
    ap.add_argument("--delta", default="", help="gain from an eval, e.g. +0.50")
    ap.add_argument("--admitted", choices=["trusted", "audited", "measured"],
                    help="grounds for admission: trusted = trust in the author, audit and "
                         "reading; audited = funnel up to step 3, no eval; measured = has a Δ. "
                         "Defaults to measured when --delta is given")
    ap.add_argument("--notes", default="")
    ap.add_argument("--cases", default="", help="case categories it was checked with")
    ap.add_argument("--name", default=None, help="rename on the way in")
    args = ap.parse_args()

    # The grounds for admission are never guessed: half a year later they show
    # what was never measured, so rechecks can be targeted instead of wholesale.
    admitted = args.admitted or ("measured" if args.delta else None)
    if not admitted:
        print("pass --admitted trusted|audited: without --delta there was no eval", file=sys.stderr)
        return 2
    if admitted == "measured" and not args.delta:
        print("--admitted measured without --delta: there is no measurement to record", file=sys.stderr)
        return 2

    root = repo_root()
    # expanduser: bash expands the tilde itself, PowerShell passes it through as is
    cand = Path(args.candidate).expanduser().resolve()
    skill_dirs = find_skill_dirs(cand)
    if not skill_dirs:
        print(f"SKILL.md not found in {cand}", file=sys.stderr)
        return 2
    if len(skill_dirs) > 1:
        # Otherwise the first one found would move silently: the funnel checks one
        # at a time, and "the first of 38" is almost certainly not the one checked.
        print(f"the candidate holds {len(skill_dirs)} skills, split one out:", file=sys.stderr)
        print(f"  python scripts/quarantine.py {args.candidate}/<path> --name <name>",
              file=sys.stderr)
        print("  " + ", ".join(d.name for d in skill_dirs[:8])
              + ("…" if len(skill_dirs) > 8 else ""), file=sys.stderr)
        return 1
    src = skill_dirs[0]
    meta = skill_meta(src)
    name = args.name or meta["name"]
    dest = root / "vault" / name

    # quarantine.py recorded the source and commit before deleting .git.
    # Explicit --source and --commit override it.
    origin: dict = {}
    for d in (src, cand):
        f = d / ".skill-lib-origin"
        if f.is_file():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    origin.setdefault(k.strip(), v.strip())
            break
    source = args.source or origin.get("source", "")
    commit = args.commit or origin.get("commit", "")

    if dest.exists():
        print(f"{name} is already in the vault. Remove it or rename with --name", file=sys.stderr)
        return 1

    shutil.copytree(src, dest)
    # its content moved into .skill-lib.yml, no need for a copy in the vault
    (dest / ".skill-lib-origin").unlink(missing_ok=True)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    lines = [
        "---",
        "# skill-lib bookkeeping, does not affect how the skill works",
        f"status: {args.status}",
        f"admitted: {admitted}",
        f"source: {source}",
        f"commit: {commit}",
        f"added: {dt.date.today().isoformat()}",
        f"reviewed: {dt.date.today().isoformat()}",
        f"delta: {args.delta}",
        f"origin_hash: {meta['hash']}",
        "tags:",
        *[f"  - {t}" for t in tags],
        f"cases: {args.cases}",
        f"notes: {args.notes}",
        "---",
        "",
    ]
    # newline="\n": on Windows text mode would write CRLF, and the sidecar
    # would fight eol=lf from .gitattributes every time
    with (dest / ".skill-lib.yml").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))

    print(f"moved into the vault: vault/{name} (status {args.status})")
    subprocess.run([sys.executable, str(root / "scripts" / "build_index.py")], check=False)
    print("\nnext:")
    print(f"  git add \"vault/{name}\" INDEX.md")
    print(f"  git commit -m \"vault: {name} ({args.status})\"")
    if args.status == "trial":
        print("  after a few real tasks, move it to approved "
              "(edit status in vault/%s/.skill-lib.yml) or remove it" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
