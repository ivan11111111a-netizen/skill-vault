#!/usr/bin/env python3
"""Wrap a candidate into a minimal plugin so `claude plugin eval` accepts it.

    python3 scripts/wrap_plugin.py lab/candidates/some-skill --cases docs

Creates lab/reports/<skill>/<date>/plugin/ and prints a ready-made eval command.
It runs no evals itself: a human or the reviewer skill does that.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import find_skill_dirs, repo_root, skill_meta  # noqa: E402


def collect_cases(bench_root: Path, tags: list[str]) -> list[Path]:
    """A case is a folder with prompt.md. Its category is the folder above it.

    Without an explicit --cases the example category is skipped: it is a template
    full of placeholders ("<a specific trait>", "SKILL-NAME"). An eval over it
    costs money, means nothing, and looks like a real one."""
    cases = []
    for prompt in sorted(bench_root.rglob("prompt.md")):
        case = prompt.parent
        category = case.parent.name
        if tags:
            if category in tags or case.name in tags:
                cases.append(case)
        elif category != "example":
            cases.append(case)
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--cases", default="", help="categories or case names, comma-separated")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = repo_root()
    cand = Path(args.candidate).expanduser().resolve()
    skill_dirs = find_skill_dirs(cand)
    if not skill_dirs:
        print(f"SKILL.md not found in {cand}", file=sys.stderr)
        return 2
    meta = skill_meta(skill_dirs[0])
    name = meta["name"]

    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M")
    out = Path(args.out).resolve() if args.out else root / "lab" / "reports" / name / stamp
    plugin = out / "plugin"
    if plugin.exists():
        shutil.rmtree(plugin)
    (plugin / ".claude-plugin").mkdir(parents=True)

    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": f"trial-{name}",
            "description": f"Temporary wrapper for evaluating the {name} skill",
            "version": "0.0.1",
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    shutil.copytree(skill_dirs[0], plugin / "skills" / name)

    tags = [t.strip() for t in args.cases.split(",") if t.strip()]
    cases = collect_cases(root / "lab" / "benchmarks", tags)
    evals = plugin / "evals"
    evals.mkdir()
    for c in cases:
        shutil.copytree(c, evals / c.name)

    # --out may point outside the repository, where relative_to() raises
    shown = plugin.relative_to(root) if root in plugin.parents else plugin
    print(f"plugin built: {shown}")
    print(f"skill: {name} · cases: {len(cases)}"
          + (f" ({', '.join(c.name for c in cases)})" if cases else ", the bank is empty"))
    if not cases:
        print("add cases under lab/benchmarks/<category>/<case>/prompt.md")
        return 1

    # Quotes are mandatory and the command stays on one line: the vault path may
    # contain a space, and \ line continuation does not work in every shell.
    # The command is meant to be copied as is.
    result_json = out / "result.json"
    print("\neval (both arms, with the skill and without):")
    print(f'  claude plugin eval "{plugin}" --trust-plugin --runs 2 --max-cost-usd 1 --no-publish --json "{result_json}"')
    print("\ncheap, one arm, for debugging the cases:")
    print(f'  claude plugin eval "{plugin}" --trust-plugin --runs 1 --ablation none '
          '--max-cost-usd 1 --no-publish')
    print("\n--no-publish is required in both: without it the report goes to claude.ai by default.")
    print("A skill with scripts or hooks needs a container: its code runs outside the sandbox.")
    print("Pin the model with --model so a model change does not look like a regression.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
