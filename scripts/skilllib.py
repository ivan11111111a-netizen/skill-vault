"""Shared helpers for skill-lib: parsing SKILL.md, walking the vault, hashing a folder.

No dependencies. PyYAML is used when installed; otherwise a built-in minimal
frontmatter parser handles it (scalars, lists, >/| blocks).
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

try:  # optional dependency
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None

# Frontmatter fields accepted by uploads to claude.ai / the Skills API.
# Everything else is a Claude Code extension and fails such an upload hard.
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

# Claude Code extensions: valid locally, rejected on upload to an account.
CC_ONLY_FIELDS = {
    "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "disallowed-tools", "model", "effort", "context",
    "agent", "background", "hooks", "paths", "shell",
}

SKILL_FILE = "SKILL.md"


class SkillError(Exception):
    pass


def _mini_yaml(text: str) -> dict:
    """Minimal parser for the flat frontmatter skills use."""
    data: dict = {}
    key = None
    buf: list[str] = []
    mode = None  # None | 'list' | 'block'

    def flush():
        nonlocal key, buf, mode
        if key is None:
            return
        if mode == "list":
            data[key] = [x for x in buf if x]
        elif mode == "block":
            data[key] = " ".join(x.strip() for x in buf).strip()
        key, buf, mode = None, [], None

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            if mode == "block":
                buf.append("")
            continue
        if mode == "block" and (raw.startswith("  ") or raw.startswith("\t")):
            buf.append(raw.strip())
            continue
        stripped = raw.strip()
        if mode == "list" and stripped.startswith("- "):
            buf.append(stripped[2:].strip().strip("'\""))
            continue
        m = re.match(r"^([A-Za-z_][\w.-]*)\s*:\s*(.*)$", raw)
        if not m:
            continue
        flush()
        k, v = m.group(1), m.group(2).strip()
        if v in (">", "|", ">-", "|-", ">+", "|+"):
            key, mode, buf = k, "block", []
        elif v == "":
            key, mode, buf = k, "list", []
        else:
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            if v.lower() in ("true", "yes", "on"):
                data[k] = True
            elif v.lower() in ("false", "no", "off"):
                data[k] = False
            else:
                data[k] = v
    flush()
    # a key with no value and no list items is None
    return {k: (v if v != [] else None) for k, v in data.items()}


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Return (frontmatter, body). Frontmatter is read only when the opening ---
    is the very first line of the file, the same rule Claude Code applies."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, text
    raw = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    if _yaml is not None:
        try:
            fm = _yaml.safe_load(raw) or {}
            if not isinstance(fm, dict):
                fm = {}
            return fm, body
        except Exception:
            pass
    return _mini_yaml(raw), body


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [x for x in re.split(r"[,\s]+", value.strip()) if x]
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return [str(value)]


def find_skill_dirs(root: Path) -> list[Path]:
    """Folders that contain a SKILL.md (without descending into a found one)."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        if SKILL_FILE in filenames:
            found.append(Path(dirpath))
            dirnames[:] = []
    return sorted(found)


def dir_hash(path: Path) -> str:
    """Stable hash of a folder's content, so unchanged skills aren't rechecked."""
    h = hashlib.sha256()
    files = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in (".git", "__pycache__"))
        for name in sorted(filenames):
            # skill-lib's own files are not part of the skill and stay out of the hash:
            #   .skill-lib.yml     appears only once the skill is in the vault
            #   .skill-lib-usage   grows with every link
            #   .skill-lib-origin  written by quarantine
            #   .skill-lib-copy    marks a copy inside a project
            # Otherwise a candidate and the same skill in the vault would never
            # hash the same, and the duplicate check in intake.py would never fire.
            if name.endswith(".pyc") or name.startswith(".skill-lib"):
                continue
            files.append(Path(dirpath) / name)
    for f in files:
        data = f.read_bytes()
        # The hash must not depend on where the copy lives: git with eol=lf stores
        # text with LF, a Windows checkout hands out CRLF, and its separator is \.
        # Otherwise a fresh clone or WSL2 sees every skill as "edited after import".
        # Binaries are left alone: NUL in the first 8000 bytes, git's own heuristic.
        if b"\0" not in data[:8000]:
            data = data.replace(b"\r\n", b"\n")
        h.update(f.relative_to(path).as_posix().encode())
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
    return h.hexdigest()[:12]


def skill_meta(skill_dir: Path) -> dict:
    """Skill metadata: name (from the folder), description, size, hash."""
    sk = skill_dir / SKILL_FILE
    if not sk.exists():
        raise SkillError(f"no {SKILL_FILE} in {skill_dir}")
    fm, body = parse_frontmatter(sk)
    desc = (fm.get("description") or "").strip()
    if not desc:
        for line in body.splitlines():
            if line.strip():
                desc = line.strip().lstrip("# ").strip()
                break
    return {
        "dir": skill_dir,
        # the command comes from the folder name; the name field is only a label
        "name": skill_dir.name,
        "label": (fm.get("name") or skill_dir.name),
        "description": desc,
        "when_to_use": (fm.get("when_to_use") or "").strip(),
        "frontmatter": fm,
        "body": body,
        "lines": len(body.splitlines()),
        "bytes": sum(f.stat().st_size for f in skill_dir.rglob("*") if f.is_file()),
        "hash": dir_hash(skill_dir),
    }


COPY_MARKER = ".skill-lib-copy"


def linked_by_us(path: Path, vault: Path) -> bool:
    """Linked by us: a symlink into the vault, or a copy carrying the marker.

    Shared by link.py and unlink.py on purpose. When the two disagree on what
    is "ours", you get a folder link.py treats as foreign and unlink.py never
    removes."""
    if path.is_symlink():
        try:
            return vault.resolve() in path.resolve().parents
        except OSError:
            return False
    return (path / COPY_MARKER).is_file()


def repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    for cand in [p, *p.parents]:
        if (cand / "vault").is_dir() and (cand / "scripts").is_dir():
            return cand
    return Path(__file__).resolve().parent.parent
