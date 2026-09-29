#!/usr/bin/env python3
"""Intake of a candidate: cheap formal checks before any model is involved.

    python3 scripts/intake.py lab/candidates/some-skill
    python3 scripts/intake.py lab/candidates/some-skill --json

Exit codes: 0 accepted, 1 blockers found, 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import (  # noqa: E402
    CC_ONLY_FIELDS, SPEC_FIELDS, as_list, find_skill_dirs, repo_root, skill_meta,
)

MAX_LINES = 500          # Anthropic's recommendation for SKILL.md
MAX_SKILL_BYTES = 5_000_000
BROAD_TOOLS = {"Bash", "Bash(*)", "Write", "Edit", "WebFetch", "WebSearch", "*"}


def check(cand: Path, root: Path) -> dict:
    res = {"path": str(cand), "blockers": [], "warnings": [], "notes": []}

    if not cand.is_dir():
        res["blockers"].append(f"no such folder: {cand}")
        return res

    skill_dirs = find_skill_dirs(cand)
    if not skill_dirs:
        res["blockers"].append("SKILL.md not found (the file name is case-sensitive)")
        return res
    if len(skill_dirs) > 1:
        res["notes"].append(
            f"the candidate holds {len(skill_dirs)} skills, review each one separately: "
            + ", ".join(d.name for d in skill_dirs)
        )

    meta = skill_meta(skill_dirs[0])
    res["name"] = meta["name"]
    res["label"] = meta["label"]
    res["description"] = meta["description"]
    res["lines"] = meta["lines"]
    res["bytes"] = meta["bytes"]
    res["hash"] = meta["hash"]
    fm = meta["frontmatter"]

    # --- frontmatter
    if not fm:
        res["warnings"].append(
            "frontmatter is empty or did not parse: the skill loads, but Claude cannot "
            "match it to a task (check that --- is the first line)"
        )
    if not meta["description"]:
        res["blockers"].append("no description: nothing to pick it by in the index")
    elif len(meta["description"]) < 30:
        res["warnings"].append("description under 30 characters, probably not enough to pick it by")

    combined = len(meta["description"]) + len(meta["when_to_use"])
    if combined > 1536:
        res["warnings"].append(
            f"description + when_to_use = {combined} chars, the listing cuts it at 1536"
        )

    unknown = set(fm) - SPEC_FIELDS - CC_ONLY_FIELDS
    if unknown:
        res["warnings"].append("unknown frontmatter fields: " + ", ".join(sorted(unknown)))
    non_spec = set(fm) & CC_ONLY_FIELDS
    if non_spec:
        res["notes"].append(
            "Claude Code-only fields (break uploads to claude.ai): "
            + ", ".join(sorted(non_spec))
        )

    # --- size
    if meta["lines"] > MAX_LINES:
        res["warnings"].append(
            f"SKILL.md is {meta['lines']} lines (> {MAX_LINES}): the body stays in context "
            "for every later turn, details belong in references/"
        )
    if meta["bytes"] > MAX_SKILL_BYTES:
        res["warnings"].append(f"the folder weighs {meta['bytes'] // 1024} KB")

    # --- permissions
    tools = set(as_list(fm.get("allowed-tools")))
    broad = {t for t in tools if t in BROAD_TOOLS or t.startswith("Bash(*")}
    if broad:
        res["warnings"].append(
            "broad allowed-tools: " + ", ".join(sorted(broad))
            + ", granted without the folder-trust dialog"
        )
    if "hooks" in fm:
        res["warnings"].append("the skill installs hooks: they live until the session ends and run outside the sandbox")

    # --- duplicates in the vault
    vault = root / "vault"
    if vault.is_dir():
        for d in find_skill_dirs(vault):
            # The candidate may itself live in the vault when it is rechecked after
            # an edit. Without this it finds itself as a duplicate and is rejected.
            if d.resolve() == skill_dirs[0].resolve():
                continue
            m = skill_meta(d)
            if m["hash"] == meta["hash"]:
                res["blockers"].append(f"same content already in the vault: {d.relative_to(root)}")
            elif m["name"] == meta["name"]:
                res["blockers"].append(
                    f"name {meta['name']} is taken ({d.relative_to(root)}): rename, or update that one"
                )

    res["ok"] = not res["blockers"]
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=None)
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else repo_root()
    res = check(Path(args.candidate).expanduser().resolve(), root)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"== intake: {res.get('name', res['path'])}")
        if "lines" in res:
            print(f"   {res['lines']} lines · {res['bytes'] // 1024} KB · hash {res['hash']}")
        for kind, items in (("BLOCKER", res["blockers"]),
                            ("warning", res["warnings"]),
                            ("note", res["notes"])):
            for i in items:
                print(f"   [{kind}] {i}")
        print("   -> " + ("accepted, go on to the audit" if res.get("ok") else "rejected"))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
