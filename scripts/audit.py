#!/usr/bin/env python3
"""Static audit of a skill: risks and signs of usefulness. No model is called.

    python3 scripts/audit.py lab/candidates/some-skill
    python3 scripts/audit.py lab/candidates/some-skill --json

Exit codes: 0 clean, 1 high-severity findings, 2 could not run.

The audit runs nothing and proves nothing about safety. It is a filter that
strips out the obvious, so a human reads only what got through.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skilllib import as_list, find_skill_dirs, parse_frontmatter, repo_root, skill_meta  # noqa: E402

MAX_SCAN_BYTES = 2_000_000   # larger files are not read line by line
SNIFF_BYTES = 8192           # how much we look at to decide text vs binary

# (id, severity, regex, explanation)
# Some patterns are bilingual on purpose: candidates come in more than one language.
RULES: list[tuple[str, str, str, str]] = [
    # --- running someone else's code
    ("pipe-to-shell", "high",
     r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z|d)?sh\b",
     "downloads a script and runs it immediately"),
    ("remote-install", "medium",
     r"\b(sudo\s+)?(apt-get|apt|brew|npm\s+i(nstall)?\s+-g|pip\s+install)\b[^\n]*",
     "installs packages system-wide"),
    ("run-remote-pkg", "medium",
     r"\b(npx|bunx|uvx|pnpm\s+dlx|yarn\s+dlx)\s+|\bpipx\s+run\b",
     "runs a package straight from the network: the code is never on disk, nothing to read"),
    ("eval-exec", "high",
     r"\b(eval|exec)\s*\(|\bexec\s+\"|\$\(\s*(curl|wget)",
     "executes a string as code"),
    ("base64-exec", "high",
     r"base64\s+(-d|--decode)[^\n]*\|\s*(ba)?sh|b64decode[^\n]*exec",
     "executes an encoded payload"),
    ("shell-true", "medium",
     r"subprocess\.(run|call|Popen|check_output)\([^)]*shell\s*=\s*True",
     "runs a command through the shell"),

    # --- secrets
    ("read-secrets", "high",
     r"(~|\$HOME)/\.(ssh|aws|gnupg|docker|kube)\b|id_rsa|\.netrc|credentials\.json",
     "touches keys and credentials"),
    ("claude-config", "high",
     r"(~|\$HOME)/\.claude(\.json|/\.credentials|/settings)|\.claude/settings(\.local)?\.json",
     "reaches into Claude Code configuration and credentials"),
    ("mcp-server", "high",
     r'"mcpServers"\s*:|\bmcp\.json\b',
     "declares an MCP server: it runs outside the eval sandbox"),
    ("dotenv", "medium",
     r"\.env\b(?!\w)|dotenv|process\.env\s*\)|printenv\b|\benv\s*\|",
     "reads environment variables or .env"),
    ("token-grep", "medium",
     r"(GITHUB_TOKEN|NPM_TOKEN|ANTHROPIC_API_KEY|AWS_SECRET|OPENAI_API_KEY)",
     "names specific secrets"),

    # --- network
    ("outbound-post", "high",
     r"(curl[^\n]*(-X\s*POST|--data|-d\s)|requests\.post|fetch\([^)]*method\s*:\s*['\"]POST)",
     "sends data out"),
    ("outbound-get", "low",
     r"\b(curl|wget|requests\.get|urllib\.request|axios\.|fetch\()",
     "goes to the network"),
    ("hardcoded-host", "low",
     r"https?://(?!([a-z0-9-]+\.)*(github\.com|githubusercontent\.com|claude\.com|anthropic\.com|"
     r"agentskills\.io|pypi\.org|npmjs\.com|python\.org|w3\.org|localhost|"
     r"openxmlformats\.org|microsoft\.com|purl\.org|xml\.org|oasis-open\.org|json-schema\.org)(/|\b))"
     r"[a-z0-9.-]+\.[a-z]{2,}",
     "mentions a third-party domain"),
    ("remote-instructions", "high",
     r"(?i)raw\.githubusercontent\.com/[^\s/]+/[^\s/]+/(main|master|HEAD)/|"
     r"\b(webfetch|fetch|download|retrieve|curl|wget|скача\w*|загрузи\w*)\b[^\n]{0,80}"
     r"\b(rules|instructions|guidelines|prompt|правил\w*|инструкци\w*)\b",
     "takes its instructions from the network at run time: what runs is not what was reviewed"),

    # --- destructive or outside the project
    ("destructive", "high",
     r"rm\s+-[a-zA-Z]*[rf][a-zA-Z]*\s+(/|~|\$HOME|\*)|shutil\.rmtree|git\s+reset\s+--hard|"
     r"git\s+push\s+--force",
     "deletes or overwrites irreversibly"),
    ("write-outside", "medium",
     r">\s*(~|\$HOME|/etc|/usr|/bin)/|\.bashrc|\.zshrc|\.profile|crontab|systemctl|launchctl",
     "writes outside the working folder or persists itself in the system"),
    ("git-push", "medium",
     r"\bgit\s+(push|remote\s+add)\b|\bgh\s+(auth|repo\s+create|pr\s+create)\b",
     "publishes changes on its own"),
    ("chmod-sudo", "medium",
     r"\bsudo\b|chmod\s+[0-7]*7[0-7]*|chmod\s+\+x",
     "changes permissions or needs sudo"),

    # --- the plugin around the skill
    # Survives a split out of a marketplace: the text still names the plugin root,
    # while the scripts and hooks it means stayed behind in the clone.
    ("plugin-root-ref", "medium",
     r"\$\{?CLAUDE_PLUGIN_ROOT\b",
     "uses files from its plugin's root: they are not in this folder, and outside a plugin "
     "the variable is empty"),

    # --- pressure on the reviewer
    ("prompt-injection", "high",
     r"(?i)(ignore (all |any )?(previous|prior|above) instructions|disregard (the )?(previous|system)|"
     r"you are now|не следуй (предыдущим|системным)|игнорируй (все )?(предыдущие|прошлые) инструкции|"
     r"do not (review|audit|question)|mark (this|it) as safe|без проверки)",
     "the text tries to take over whoever reads it"),
    ("self-approval", "medium",
     r"(?i)(this skill is (safe|trusted|verified)|полностью безопас|не требует проверки|"
     r"доверенн\w+ источник)",
     "the skill vouches for its own safety"),
    # zero-width, bidi overrides and isolates, tag characters (ASCII smuggling);
    # a BOM at the start of a line is just an encoding marker, so it is let through
    ("hidden-unicode", "high",
     r"[​-‏‪-‮⁠-⁤⁦-⁩\U000e0000-\U000e007f]|(?!^)﻿",
     "invisible characters: text the reviewer does not see, but the model reads"),
]

COMPILED = [(i, s, re.compile(p), d) for i, s, p, d in RULES]

# signs that a skill carries more than generic advice
VALUE_HINTS = [
    ("scripts", r"(?m)^\s*(python3?|node|bash|sh)\s+\S+\.(py|js|sh)"),
    ("commands", r"(?m)^\s*```(bash|sh|shell|console)"),
    ("templates", r"\{\{[^}]+\}\}|\$ARGUMENTS|\$\{CLAUDE_"),
    ("tables", r"(?m)^\s*\|.+\|\s*$"),
    ("checklists", r"(?m)^\s*[-*]\s+\[[ x]\]"),
]
VAGUE = re.compile(
    r"(?i)(be (helpful|careful|thorough)|follow best practices|use good judgment|"
    r"будь (внимателен|аккуратен)|следуй лучшим практикам|используй здравый смысл)"
)


def looks_binary(p: Path) -> bool:
    """Binary is decided by NUL bytes, not by extension: otherwise .xsd, .xml
    and other text formats end up as "unreadable"."""
    try:
        with p.open("rb") as fh:
            chunk = fh.read(SNIFF_BYTES)
    except OSError:
        return True
    return b"\0" in chunk


def split_files(root: Path, exclude: tuple[Path, ...] = ()) -> tuple[list[Path], list[Path], list[Path]]:
    """Return (text, binary, too large), skipping everything under `exclude`."""
    text, binary, large = [], [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        if any(ex in p.parents for ex in exclude):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if looks_binary(p):
            binary.append(p)
        elif size > MAX_SCAN_BYTES:
            large.append(p)
        else:
            text.append(p)
    return text, binary, large


MAX_PER_RULE_PER_FILE = 3  # the rest is counted, not printed


def collapse(findings: list[dict]) -> list[dict]:
    """Keep three examples per rule per file, fold the rest into a count."""
    seen: dict[tuple, int] = {}
    out: list[dict] = []
    for f in findings:
        key = (f["id"], f["file"])
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= MAX_PER_RULE_PER_FILE:
            out.append(f)
    for f in out:
        total = seen[(f["id"], f["file"])]
        if total > MAX_PER_RULE_PER_FILE:
            f["occurrences"] = total
    return out


def scan(cand: Path, prefix: str = "", exclude: tuple[Path, ...] = (),
         skip: frozenset[str] = frozenset()) -> dict:
    """Line rules, binaries and large files under `cand`. `prefix` marks paths that
    lie outside the skill itself (the plugin root), so the report says where;
    `skip` names rules that make no sense there."""
    findings: list[dict] = []
    files, binaries_p, large = split_files(cand, exclude)

    def rel(p: Path) -> str:
        return prefix + p.relative_to(cand).as_posix()

    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for n, line in enumerate(lines, 1):
            if len(line) > 4000:
                findings.append({
                    "id": "long-line", "severity": "medium",
                    "file": rel(f), "line": n,
                    "why": "line longer than 4000 characters, a typical sign of obfuscation",
                    "text": line[:120],
                })
                continue
            for rid, sev, rx, why in COMPILED:
                if rid not in skip and rx.search(line):
                    findings.append({
                        "id": rid, "severity": sev,
                        "file": rel(f), "line": n,
                        "why": why, "text": line.strip()[:160],
                    })

    binaries = [rel(p) for p in binaries_p]
    groups: dict[tuple[str, str], list[str]] = {}
    for p in binaries_p:
        r = p.relative_to(cand)
        groups.setdefault((r.parent.as_posix(), r.suffix.lower() or "no extension"), []).append(r.name)
    for (folder, suffix), names in sorted(groups.items()):
        finding = {
            "id": "binary", "severity": "high",
            "file": prefix + (folder + "/" if folder != "." else "") + f"*{suffix}", "line": 0,
            "why": "binary files cannot be read by eye",
            "text": ", ".join(sorted(names)[:3]) + ("…" if len(names) > 3 else ""),
        }
        if len(names) > 1:
            finding["occurrences"] = len(names)
        findings.append(finding)
    for p in large:
        findings.append({
            "id": "large-file", "severity": "medium",
            "file": rel(p), "line": 0,
            "why": f"{p.stat().st_size // 1024} KB, not read by the audit", "text": "",
        })

    return {"findings": collapse(findings), "files": len(files), "binaries": binaries}


# <plugin>/skills/<skill>/SKILL.md puts the plugin root two levels up; one spare
# level for nested layouts, and no further, or a stray plugin.json far above
# would claim every skill below it.
PLUGIN_UP = 3


def plugin_root(cand: Path) -> Path | None:
    """The nearest folder at or above the candidate that is a Claude Code plugin."""
    stop = repo_root()
    for d in [cand, *cand.parents][:PLUGIN_UP + 1]:
        if d == stop:
            break
        if (d / ".claude-plugin" / "plugin.json").is_file():
            return d
    return None


def plugin_hooks(root: Path) -> list[dict]:
    """A plugin's hooks run in every session once it is enabled, whether or not
    any of its skills is invoked, so the skill's own frontmatter never shows them."""
    manifest = root / ".claude-plugin" / "plugin.json"
    try:
        declared = "hooks" in json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, TypeError):
        declared = False
    out = []
    for path, present in ((root / "hooks" / "hooks.json", (root / "hooks" / "hooks.json").is_file()),
                          (manifest, declared)):
        if present:
            out.append({
                "id": "plugin-hooks", "severity": "high",
                "file": "plugin:" + path.relative_to(root).as_posix(), "line": 0,
                "why": "the plugin registers hooks: once enabled they run in every session, "
                       "outside the sandbox, even if this skill is never invoked",
                "text": "",
            })
    return out


def analyse(cand: Path) -> dict:
    skill_dirs = find_skill_dirs(cand)
    if not skill_dirs:
        return {"error": "SKILL.md not found"}
    meta = skill_meta(skill_dirs[0])
    fm = meta["frontmatter"]
    body = meta["body"]

    res = {"name": meta["name"], "hash": meta["hash"], "lines": meta["lines"]}
    res.update(scan(cand))

    # A skill audited inside a marketplace clone: the plugin around it ships
    # manifests, hooks, servers and scripts that sit above the skill folder.
    # Its other skills are left out, they are candidates of their own.
    root = plugin_root(cand)
    res["plugin_root"] = root.as_posix() if root else None
    res["plugin_files"] = 0
    if root is not None:
        if root != cand:
            # the plugin's own files name its root by design
            outer = scan(root, prefix="plugin:", exclude=(root / "skills", cand),
                         skip=frozenset({"plugin-root-ref"}))
            res["findings"].extend(outer["findings"])
            res["binaries"].extend(outer["binaries"])
            res["plugin_files"] = outer["files"]
        res["findings"].extend(plugin_hooks(root))

    # Dynamic injections run BEFORE Claude sees the text.
    # Known limitation: a skill that WRITES ABOUT this technique trips it itself,
    # since the documented syntax and the real injection look the same. Our own
    # skill-review and review-checklist trip it this way. Deliberately not
    # relaxed: a false alarm on `!` is cheaper than a missed one.
    inline = re.findall(r"(?:^|\s)!`([^`]+)`", body)
    blocks = re.findall(r"(?m)^```!\s*$", body)
    if inline or blocks:
        res["findings"].append({
            "id": "shell-injection", "severity": "high",
            "file": "SKILL.md", "line": 0,
            "why": (f"{len(inline)} inline injections and {len(blocks)} `!` blocks: the commands "
                    "run when the skill is invoked, before the model sees them"),
            "text": "; ".join(inline[:3])[:160],
        })
    res["inline_commands"] = inline

    # @-references pull files into context
    ats = re.findall(r"(?:^|\s)@([\w./~-]+)", body)
    if ats:
        res["findings"].append({
            "id": "file-reference", "severity": "low", "file": "SKILL.md", "line": 0,
            "why": "@-references pull files into context on invocation",
            "text": ", ".join(sorted(set(ats))[:5]),
        })

    if "hooks" in fm:
        res["findings"].append({
            "id": "hooks", "severity": "high", "file": "SKILL.md", "line": 0,
            "why": "the skill registers hooks: they live until the session ends and run outside the sandbox",
            "text": str(fm.get("hooks"))[:160],
        })

    tools = as_list(fm.get("allowed-tools"))
    if tools:
        res["findings"].append({
            "id": "allowed-tools",
            "severity": "medium" if any(
                t.startswith(("Bash", "Write", "Edit", "WebFetch", "*")) for t in tools
            ) else "low",
            "file": "SKILL.md", "line": 0,
            "why": "permissions are granted without the folder-trust dialog",
            "text": " ".join(tools)[:160],
        })

    # usefulness
    value = [name for name, rx in VALUE_HINTS if re.search(rx, body)]
    res["value_signals"] = value
    res["vague"] = len(VAGUE.findall(body))
    if not value and meta["lines"] < 40:
        res["findings"].append({
            "id": "thin", "severity": "low", "file": "SKILL.md", "line": 0,
            "why": "short text with no commands, templates or tables: probably restates "
                   "what the model already does",
            "text": "",
        })

    sev = {"high": 0, "medium": 0, "low": 0}
    for f in res["findings"]:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
    res["counts"] = sev
    res["verdict"] = (
        "read it by eye" if sev["high"]
        else "look at the flagged spots" if sev["medium"]
        else "clean"
    )
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cand = Path(args.candidate).expanduser().resolve()
    if not cand.is_dir():
        print(f"no such folder: {cand}", file=sys.stderr)
        return 2
    res = analyse(cand)
    if "error" in res:
        print(res["error"], file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 1 if res["counts"]["high"] else 0

    print(f"== audit: {res['name']} ({res['files']} files, {res['lines']} lines, hash {res['hash']})")
    if res["plugin_root"]:
        print(f"   inside a plugin: {res['plugin_root']} "
              f"({res['plugin_files']} more files read, paths marked plugin:)")
    order = {"high": 0, "medium": 1, "low": 2}
    for f in sorted(res["findings"], key=lambda x: (order[x["severity"]], x["file"], x["line"])):
        loc = f["file"] + (f":{f['line']}" if f["line"] else "")
        rep = f"  (×{f['occurrences']})" if f.get("occurrences") else ""
        print(f"   [{f['severity']:<6}] {f['id']:<17} {loc}{rep}")
        print(f"              {f['why']}")
        if f["text"]:
            print(f"              > {f['text']}")
    print(f"   value: {', '.join(res['value_signals']) or 'no clear signs'}"
          f" · generic phrases: {res['vague']}")
    print(f"   -> {res['verdict']} "
          f"(high {res['counts']['high']}, medium {res['counts']['medium']}, low {res['counts']['low']})")
    return 1 if res["counts"]["high"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
