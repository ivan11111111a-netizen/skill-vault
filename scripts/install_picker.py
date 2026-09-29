#!/usr/bin/env python3
"""Install the /pick-skills picker into ~/.claude/skills/, filling the template
with the path to this vault and the interpreter the installer runs under.

    python scripts/install_picker.py                  # into ~/.claude/skills
    python scripts/install_picker.py --dest /path/.claude/skills

Running it again overwrites: that is how you update after editing the template.
Without it, edits to picker/pick-skills/SKILL.md have no effect.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import repo_root  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=None, help="where to install (~/.claude/skills by default)")
    args = ap.parse_args()

    root = repo_root()
    src = root / "picker" / "pick-skills" / "SKILL.md"
    if not src.is_file():
        print(f"no template: {src}", file=sys.stderr)
        return 1

    dest = Path(args.dest).expanduser() if args.dest else Path.home() / ".claude" / "skills"
    out = dest / "pick-skills"
    out.mkdir(parents=True, exist_ok=True)

    # __PYTHON__ is the interpreter running the installer: it settles "python or
    # python3" for whoever calls the picker later.
    # as_posix(): the template puts forward slashes after the placeholder, and
    # without this you get "C:\Users\me\skill-lib/scripts/link.py". Windows and
    # Python accept forward slashes; mixed ones are just noise.
    text = src.read_text(encoding="utf-8")
    text = (text.replace("__SKILL_LIB__", root.as_posix())
                .replace("__PYTHON__", Path(sys.executable).as_posix()))
    (out / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")

    print(f"installed: {out / 'SKILL.md'}")
    print(f"vault:     {root}")
    print(f"python:    {sys.executable}")
    print()
    print("Check it: start claude and type /pick-skills")
    print(f"If the command is missing, {dest} appeared after the session started: "
          "restart claude.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
