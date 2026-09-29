# Report template

Goes into `lab/reports/<name>/<date>/report.md`. The report stays in the repository
even on rejection: it saves reviewing the same skill again.

```markdown
# <skill name>

- Source: <url> @ <commit>
- Reviewed: <date> · eval model: <model or "no eval"> · candidate hash: <hash>
- **Verdict: take / take with changes / reject**

## What it adds beyond the baseline

One paragraph: what exactly the skill does that the model does not do without it.
If there is nothing to say, the verdict is "reject" and the rest can stay empty.

## Audit

| Severity | Finding | Where | Decision |
|---|---|---|---|
| high | <id> | <file:line> | <reject / change / acceptable, because…> |

Read by eye: SKILL.md, scripts/<...>.

## Eval (only if there was one)

| Case | Δ | with skill | without | runs |
|---|---|---|---|---|
| <case> | +0.50 | 1.00 | 0.50 | 2×2 |

Cost: $X.XX · case category: `<category>`

Notes: <what broke, where the judge was wrong, what wobbled>

## Changes before the move

- [ ] <what to change in the skill>

## Line for the vault

    python3 scripts/promote.py lab/candidates/<name> --status trial \
        --admitted audited --tags <tags>
    # after an eval: instead of --admitted  →  --delta <Δ> --cases <category>
```
