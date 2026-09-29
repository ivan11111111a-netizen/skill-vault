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


def split_files(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Return (text, binary, too large)."""
    text, binary, large = [], [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
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


def scan(cand: Path) -> dict:
    findings: list[dict] = []
    files, binaries_p, large = split_files(cand)

    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for n, line in enumerate(lines, 1):
            if len(line) > 4000:
                findings.append({
                    "id": "long-line", "severity": "medium",
                    "file": f.relative_to(cand).as_posix(), "line": n,
                    "why": "line longer than 4000 characters, a typical sign of obfuscation",
                    "text": line[:120],
                })
                continue
            for rid, sev, rx, why in COMPILED:
                if rx.search(line):
                    findings.append({
                        "id": rid, "severity": sev,
                        "file": f.relative_to(cand).as_posix(), "line": n,
                        "why": why, "text": line.strip()[:160],
                    })

    binaries = [p.relative_to(cand).as_posix() for p in binaries_p]
    groups: dict[tuple[str, str], list[str]] = {}
    for p in binaries_p:
        rel = p.relative_to(cand)
        groups.setdefault((rel.parent.as_posix(), rel.suffix.lower() or "no extension"), []).append(rel.name)
    for (folder, suffix), names in sorted(groups.items()):
        finding = {
            "id": "binary", "severity": "high",
            "file": (folder + "/" if folder != "." else "") + f"*{suffix}", "line": 0,
            "why": "binary files cannot be read by eye",
            "text": ", ".join(sorted(names)[:3]) + ("…" if len(names) > 3 else ""),
        }
        if len(names) > 1:
            finding["occurrences"] = len(names)
        findings.append(finding)
    for p in large:
        findings.append({
            "id": "large-file", "severity": "medium",
            "file": p.relative_to(cand).as_posix(), "line": 0,
            "why": f"{p.stat().st_size // 1024} KB, not read by the audit", "text": "",
        })

    return {"findings": collapse(findings), "files": len(files), "binaries": binaries}


def analyse(cand: Path) -> dict:
    skill_dirs = find_skill_dirs(cand)
    if not skill_dirs:
        return {"error": "SKILL.md not found"}
    meta = skill_meta(skill_dirs[0])
    fm = meta["frontmatter"]
    body = meta["body"]

    res = {"name": meta["name"], "hash": meta["hash"], "lines": meta["lines"]}
    res.update(scan(cand))

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
