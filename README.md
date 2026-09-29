# skill-vault

A personal skill vault for [Claude Code](https://code.claude.com), with quarantine
at the door.

Skills from the internet are handy, but every installed skill costs context: the
descriptions of all installed skills sit in the context window on every turn, and when
that listing overflows, Claude Code starts truncating them. Installing each one by hand
for each task gets old fast. And skills come from unreviewed sources: a skill can run
commands, grant itself permissions and install hooks.

skill-vault keeps skills **outside** `.claude/skills/`, where they cost nothing. For a
given task, `/pick-skills` reads one index file, picks what fits and links it into the
project with a symlink. A new skill reaches the vault only through the `/skill-review`
funnel: intake → static audit → reading by eye. A paid eval measuring the gain (with
the skill versus without) is the exception, for choosing between two similar skills.

How it is built and why: [docs/architecture.md](docs/architecture.md).

## Install

```bash
git clone https://github.com/ivan11111111a-netizen/skill-vault ~/skill-vault
cd ~/skill-vault
python3 scripts/install_picker.py   # installs /pick-skills into ~/.claude/skills/
python3 scripts/build_index.py      # builds INDEX.md from vault/
git config core.hooksPath scripts/hooks   # pre-commit: keep the index in sync
```

No dependencies: Python 3.9+ and git. All scripts are Python and behave the same on
Windows, macOS and Linux, no shell needed. PyYAML is used if present. On Windows the
interpreter is usually called `python`, not `python3`.

If `/pick-skills` doesn't show up after installing, `~/.claude/skills/` appeared after
the session started: restart `claude`.

## Use

**For a task**, in your working project:

```
/pick-skills turn a stack of PDF bank statements into one spreadsheet
```

Claude reads `INDEX.md`, suggests what fits and why, and links the chosen skills into
the project's `.claude/skills/`. Afterwards: `python3 ~/skill-vault/scripts/unlink.py`.

**A new skill**, in the vault folder:

```
/skill-review https://github.com/someone/great-skill
```

The funnel takes the candidate through its steps and writes a report with a verdict.
Nothing moves into the vault without your decision.

**Seeding the vault**: start with your own rarely used skills from `~/.claude/skills/`,
see [vault/README.md](vault/README.md).

## Layout

| Path | What it is |
|---|---|
| `vault/` | the vault: reviewed skills, each with `.skill-lib.yml` and a link counter `.skill-lib-usage` |
| `INDEX.md` | the vault index, generated, never edited by hand |
| `picker/pick-skills/` | the picker template, installed by `install_picker.py` |
| `.claude/skills/skill-review/` | the reviewer, works inside this repository |
| `lab/inbox/` | inbox: links and folders you found |
| `lab/candidates/` | quarantine: candidates under review |
| `lab/benchmarks/` | the task bank for evals, by category |
| `lab/selftest/` | the fixture for the audit's regression test |
| `lab/reports/` | review reports, rejections included |
| `scripts/` | intake, audit, index, eval wrapper, linking |
| `docs/` | architecture, reading checklist, report template |

## Scripts

```bash
python3 scripts/quarantine.py <url|path>         # into quarantine, defusing CLAUDE.md
python3 scripts/intake.py   lab/candidates/X     # formal intake
python3 scripts/audit.py    lab/candidates/X     # static risk audit
python3 scripts/wrap_plugin.py lab/candidates/X --cases docs
python3 scripts/promote.py  lab/candidates/X --status trial --admitted audited
python3 scripts/build_index.py [--check]         # rebuild the index
python3 scripts/selftest.py                      # check the audit still catches what it should
python3 scripts/link.py <name>...                # link into the current project
python3 scripts/unlink.py [<name>...]            # unlink (no names: all of ours)
```

## Caveats

- Review guarantees nothing. The isolation of `claude plugin eval` guards against the
  agent's actions, but the skill's own code, its hooks and MCP servers, runs outside
  the sandbox. Evaluate skills with scripts in a container.
- **Windows.** No separate shell is needed. A regular Python install on Windows doesn't
  create `python3`: run `python scripts/…`. If the system won't create a symlink,
  `link.py` copies the folder and marks it, and `unlink.py` removes such a copy;
  force a copy with `--copy`.
- **WSL2 is not always needed.** The vault, picking, intake and audit work on any OS.
  WSL2 (or macOS/Linux) is only required for `claude plugin eval` runs that need
  `--allow-tools Bash`: there is no Bash sandbox on native Windows.
- `claude plugin eval` needs Claude Code 2.1.269+. Without it the funnel works up to
  the eval step, and the gain has to be judged by hand.

## License

[MIT](LICENSE).
