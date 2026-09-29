# Vault

Reviewed skills live here, one folder per skill. Next to each `SKILL.md` sits
`.skill-lib.yml`, skill-lib's bookkeeping file with the status, source and review
result. It does not affect how the skill works.

Nothing is placed here directly: skills reach the vault through the `/skill-review`
funnel and `scripts/promote.py`.

The easiest way to seed the vault is **from the inside**, not from the internet: take
your own rarely needed skills from `~/.claude/skills/`. They are already proven in
practice, need no funnel, and moving them frees the listing at once, which is the
whole point.

```bash
python3 scripts/promote.py ~/.claude/skills/<name> \
    --status approved --admitted trusted --source local --tags <tags>
# Remove the original right after the move: while it is there, the skill is
# available globally, calls bypass link.py, and the usage counter shows zero.
rm -rf ~/.claude/skills/<name>
```

A skill you call often is better left global: the extra step through `/pick-skills`
costs more than its line in the listing.

There is no point keeping skills that are available anyway: check what your plugins
and account already provide before pulling a same-named skill from GitHub.

Skills from outside go not here but into `lab/inbox/`, and on through `/skill-review`.
