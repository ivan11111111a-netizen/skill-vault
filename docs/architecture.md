# How it works

Three layers that know no more about each other than they must.

```
   something found online
           │
     lab/inbox/          ←  you drop a link or a folder
           │
     lab/candidates/     ←  quarantine: the skill sits as a plain folder,
           │                 Claude Code knows nothing about it
   ┌───────┴────────┐
   │  funnel        │    intake → audit → reading by eye (an eval only by exception)
   │  /skill-review │
   └───────┬────────┘
           │  a human decides
       vault/<name>/     ←  the vault: skill + .skill-lib.yml + cases
           │
     build_index.py
           │
       INDEX.md          ←  the only thing the picker reads
           │
    /pick-skills         ←  invoked by hand for a specific task
           │
  .claude/skills/<name>  ←  a symlink for the duration of the task
```

## Why this and not "install everything"

An installed skill is not free. The descriptions of **all** installed skills sit in
context on every turn, and the listing gets about 1% of the context window
(`skillListingBudgetFraction`, or `SLASH_COMMAND_TOOL_CHAR_BUDGET` in characters).
When the listing overflows, Claude Code starts **truncating descriptions**, beginning
with the skills you call least, and picking by them gets worse.

The vault lives outside `.claude/skills/`, so its footprint in any session is zero.
The index is read only when `/pick-skills` is invoked, and it is one file.

The built-in alternative if you don't want a system of your own: install everything
into `~/.claude/skills/` and switch rare skills in `skillOverrides` to `name-only`
(only the name stays in the listing) or `user-invocable-only` (hidden from the model,
available to you as `/name`). Simpler to set up, but the model picks worse by a bare
name than by your index with its explanations.

## Why a symlink and not a copy

Edits in the vault show up at once, and copies never drift. Claude Code reads
`SKILL.md` through the link and loads the skill once even when several places point
at the same target.

Two caveats:

- Claude Code watches skill folders that **already existed** when the session started.
  If `.claude/skills/` is created mid-session, a restart is needed.
- If a symlink cannot be created (no permission in the system), `link.py` copies the
  folder and marks it with `.skill-lib-copy`, so `unlink.py` removes it later.
  Force a copy with `--copy`. The downside of a copy: vault edits don't show up,
  the skill has to be linked again.

## Why quarantine and not straight into the vault

A skill is an executable thing, not a note:

- `` !`command` `` injections in the body run on every invocation, **before** the text
  reaches the model;
- `allowed-tools` applies without the folder-trust dialog, so a project skill from a
  cloned repository can grant itself broad permissions;
- `hooks` live until the session ends and run outside the sandbox;
- `CLAUDE.md` and `AGENTS.md` are picked up by the agent automatically, just because
  they sit in the working tree. A cloned candidate with such a file becomes a source
  of instructions **before** anyone has reviewed it. That is why `quarantine.py`
  renames them to `*.quarantined`: readable by eye, never picked up on their own.

So a candidate never sits in `.claude/skills/` and its scripts never run before it is
read. The isolation of `claude plugin eval` guards against the agent's actions but
**not** against the skill's own code: its hooks and MCP servers run outside the
sandbox, and a passed eval says nothing about safety.

## Statuses

| Status | Meaning | Set by |
|---|---|---|
| `trial` | passed the funnel, not yet proven in real work | `promote.py` by default |
| `approved` | several real tasks confirmed its use | a human, by editing `.skill-lib.yml` |
| `deprecated` | no longer suggested, history kept | a human |

`.skill-lib.yml` sits next to `SKILL.md`, does not affect how the skill works, and
holds the status, the grounds for admission, the source and commit, dates, the Δ
from an eval, tags and the case category.

The grounds for admission, `admitted`: `trusted` means taken on trust in the author,
audit passed, read; `audited` means the funnel up to step 3, no eval; `measured`
means there is a Δ. It shows what was never measured, so rechecks can be targeted.

## How usefulness is measured

The main signal is **real use**, not an eval score: `link.py` appends a date line to
`vault/<name>/.skill-lib-usage` on every link, and `build_index.py` shows
`linked: N · last <date>` in the index. It is free and more honest than any
benchmark: if a skill was not needed once in half a year, it is not needed, whatever
its Δ.

Transition rules:

- `trial` → `approved` after 3 links in real work;
- `approved` → `deprecated` if unused for half a year;
- the Δ from `claude plugin eval` is kept for one case: two similar skills for the
  same job, pick one.

The counter is deliberately excluded from `skilllib.dir_hash`, otherwise the hash
would drift with use and `build_index.py --check` would fail for no reason.

## For changing the scripts

Everything below is what isn't obvious from the code at first glance, and what has
already broken once.

**General.** `scripts/skilllib.py` is the only shared module; the other scripts put
`scripts/` on `sys.path` and import it. No dependencies: Python 3.9+ and the standard
library, PyYAML only as an optional speed-up. When changing frontmatter parsing, test
both branches: PyYAML and the built-in `_mini_yaml`. `repo_root()` finds the root by
the presence of `vault/` and `scripts/`, so the scripts work from any folder. The skill
and command name come from the **folder name**; the `name` field in the frontmatter is
only a label.

**`.skill-lib.yml`** is the single source of `status`/`admitted`/`tags`/`delta`/`cases`.
`promote.py` writes it, `build_index.py` reads it. `promote.py` refuses without
`--admitted` or `--delta`, before copying anything. `admitted` is not shown in the
index: the picker doesn't need it, and the index is read whole on every call.

**`skilllib.dir_hash`** hashes **content**; the duplicate check in `intake.py` and the
comparison with `origin_hash` ("was it edited after import") both rest on it. Hence:
- everything starting with `.skill-lib` is excluded, otherwise a candidate and the same
  skill in the vault would never hash the same;
- CRLF in text is normalized to LF and paths use `/`, otherwise a Windows checkout,
  a fresh clone and WSL2 would hash the same skill differently. Binary files (NUL in
  the first 8000 bytes) are not normalized.

**When you change the hashing rules, every recorded `origin_hash` becomes
incomparable at once**: recompute them.

**`.skill-lib-origin`** in a candidate holds the source, commit and date. `quarantine.py`
writes it **before** deleting `.git`, or the commit is lost. A sub-skill split out of a
large repository with `--name` inherits the file from its parent and adds `path`.
`promote.py` reads it, fills in `--source`/`--commit`, and does not copy it into the vault.

**`.skill-lib-usage`** is written by `link.py` on every link. Consequence: **every link
makes `INDEX.md` stale**; pre-commit catches that, so rebuild the index before committing.

**The repository's own skills** are both invoked by hand. `.claude/skills/skill-review/`
works here. `picker/pick-skills/SKILL.md` is a template with the placeholders
`__SKILL_LIB__` and `__PYTHON__`; `install_picker.py` fills them when copying into
`~/.claude/skills/` (the second from `sys.executable`). Editing the template changes
nothing until you rerun `install_picker.py`. Paths are substituted there as text and
end up in `allowed-tools` and in commands: quotes are required, test on a path with
a space in it.

**Evals.** A case is a folder with `prompt.md`, its category the folder above;
`wrap_plugin.py --cases` filters by category or case name. `wrap_plugin.py` itself
only builds the plugin under `lab/reports/<name>/<date>/plugin/` and prints the
command. How to write cases, and what past evals taught: `lab/benchmarks/README.md`.

**Audit.** A rule in `RULES` (`scripts/audit.py`) without a trigger in
`lab/selftest/evil-skill/` and without its name in `EXPECTED` (`scripts/selftest.py`)
is checked by nothing. To check one: `python scripts/audit.py lab/selftest/evil-skill
--json` and look for its `id`. One rule is uncovered on purpose: `large-file` (it needs
a file over 2 MB).

**Windows.**
- `.gitattributes` keeps `eol=lf`: the git hook is the only shell file, and CRLF in its
  shebang breaks it. Lost exec bits are handled by `git config core.fileMode false`.
- `os.symlink` creates a real NTFS symlink without developer mode. `ln -s` in Git Bash
  only emulates a symlink by copying, so don't rely on it. If it fails, `link.py`
  copies and sets `.skill-lib-copy`.
- Files inside `.git` are read-only: `shutil.rmtree` fails on them, so delete with a
  handler that clears the attribute (as `quarantine.py` does).
- There is no Bash sandbox, but only `claude plugin eval` with `--allow-tools Bash`
  runs into that.
