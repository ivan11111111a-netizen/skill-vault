# Task bank

Cases are written **per category**, not per skill: one set of tasks compares every
candidate that claims the same job, and shows which of three similar ones is best.

```
lab/benchmarks/
└── <category>/            docs, tables, code, research …
    └── <case>/
        ├── prompt.md       the task + run limits
        ├── graders/*.md    graders, one per file
        └── case.yaml       (optional) setup of the working folder
```

`example/` is a template full of placeholders. `wrap_plugin.py` skips it unless
asked for it by name: an eval over placeholders costs money and means nothing.

## Rules that save money and nerves

- **Two graders per case at least**: one on the result (`regex` over a file or `llm`
  over the answer), one on the path to it (`tool_used`, `tool_order`). Together they
  answer both "is it right" and "did the skill do it".
- `regex`, `tool_used`, `tool_order`, `file_exists` cost nothing and don't wobble.
  `llm` and `baseline` call a judge model. Check long output with a regex over a file,
  keep the judge for short answers.
- A `tool_used: Skill` grader does not count toward the score in a two-arm run (it can
  never pass without the skill) and is shown as an indicator. The others make the score.
- Look at `Δ`, not at the absolute score. But 1.0 in both arms does not mean "the skill
  doesn't matter", it means **"this case cannot tell them apart"**, and those differ.
  Seen in practice on a debugging skill: it clearly changed the answer, yet the rubric
  passed both arms because it asked about intent ("does it aim for a reproducible
  signal?"), and the baseline formally aims for one too.
- **A rubric must target what the baseline does not do.** Check for concrete traits,
  not good intentions. List 4–6 tangible traits of quality, **one grader per trait**.
  Word them so any good method fits, not one skill's signature checklist, or the case
  stops being usable for comparing competitors, which is what it is for.
- **One grader, one decision.** A single judge asked "at least three of five traits,
  plus a disqualifier" over answers of 3–4 thousand characters inverted three verdicts
  out of four, and Δ came out −0.5 where it should have been +1.0. The same judge
  model, asked through `claude -p` to go trait by trait before the verdict, got all
  four right. The compound question was the problem, not the model; a stronger judge
  treats the wrong thing.
- **Check the judge's verdicts by eye before trusting Δ.** `result.json` keeps the
  answer the judge saw (`evidence`) but not its reasoning. In doubt, re-judge the saved
  answers: that costs cents, not a rerun of the agents.
- **Describe a disqualifier by its substance, not by an example wording.** "E.g.
  'reproduce or infer from logs'" was read as "look for the word 'or'", and the same
  fork expressed by the order of the steps went unnoticed.
- **The path grader matters more than it seems.** In one run the skill never fired,
  and Δ = 0 compared two identical arms. Without the `tool_used: Skill` indicator it
  would have read as an honest "the skill is useless". If the indicator is `false`,
  throw the result away rather than interpret it.
- **The task must be work, not a question.** A prompt like "briefly, where would you
  start?" is closed in one turn, tool choice never happens, and no skill fires. Ask
  for something to be done, not described.
- `--runs 1` is only for debugging the graders themselves. For a verdict, at least 2.
- Pin the model (`--model`), or a model change will look like a regression.

The cases an accepted skill was checked with move with it: when a new model ships,
the vault can be re-run on them and whatever stopped paying off thrown out.
