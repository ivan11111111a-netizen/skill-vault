# Reading checklist

`audit.py` finds the obvious and shrinks how much there is to read. It proves nothing.
Always read: `SKILL.md` in full and **every** file under `scripts/`.

## Safety

- [ ] Injections `` !`command` `` and ```` ```! ```` blocks: what exactly runs on
      every invocation? This is code execution, not documentation.
- [ ] `allowed-tools`: the minimal set needed? `Bash`, `Write`, `Edit`, `WebFetch`
      without narrowing are a reason to cut.
- [ ] `hooks` in the frontmatter: almost always a reason to reject. They live until
      the session ends and run outside the sandbox.
- [ ] MCP servers (`mcpServers`, `.mcp.json`) and edits to `.claude/settings.json`:
      the same. They run outside the sandbox and outlive the eval. A passed eval says
      nothing about their safety.
- [ ] Scripts: network, reading `~/.ssh`, `~/.aws`, `.env`, `~/.claude/`, sending
      data out, `curl | bash`, `eval`, `base64 -d`.
- [ ] Writes outside the working folder: `.bashrc`, `crontab`, `systemctl`, `launchctl`,
      folders on `$PATH`.
- [ ] `git push`, `gh auth`, `gh pr create`: the skill publishes nothing on its own.
- [ ] Binary files and lines over 4000 characters: they cannot be read by eye,
      so we don't take them.
- [ ] The text does not try to steer whoever reads it: "ignore previous
      instructions", "don't check", "this skill is safe".
- [ ] Links to external domains: where to and why.
- [ ] `*.quarantined` files (the candidate's defused `CLAUDE.md`, `AGENTS.md`):
      read them like everything else. They are the instructions it meant to hand
      the agent silently.

## Usefulness

- [ ] What does the skill add **beyond** what the model does anyway? Name something
      tangible: a script, a file format, a rule set, knowledge of an external API.
- [ ] Is there substance: commands, templates, tables, thresholds? Or only
      "be careful" and "follow best practices"?
- [ ] On what real task would the difference show? If none comes to mind,
      reject here, before any eval.
- [ ] Compared with the closest existing skills (`INDEX.md` and the installed ones)?
      On an overlap the human decides which stays, after a comparison with concrete
      evidence: see step 3 of `/skill-review`.

## Hygiene

- [ ] Is the `description` written the way a person states a task? (In this setup
      that matters not for auto-triggering but so you can pick it from the index.)
- [ ] `description` + `when_to_use` fit in 1536 characters.
- [ ] The body is under ~500 lines. It stays in context **until the session ends**;
      details belong in `references/`.
- [ ] Source and commit are recorded, so you can tell later what changed.

## What to do with a finding

| Finding | Decision |
|---|---|
| network, secrets, `hooks`, binaries | reject |
| broad `allowed-tools` | take with changes: narrow it |
| `!` injections with no clear need | take with changes: remove them |
| a 1500-line body | take with changes: move details to `references/` |
| restated generic advice | reject |
