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

## A working folder prepared in advance

Every run starts in an empty folder. When the task needs a repository to work on,
`case.yaml` names a script that builds it; the prompt, run limits and graders stay in
`prompt.md` and `graders/`, and the three merge into one case:

```yaml
schema_version: "1.0"
name: <case>
context:
  scaffold_script: scaffold.sh   # a path inside the case folder
```

- The script runs with `bash`, from the run's empty folder, with a throwaway `HOME`,
  and **only when the eval gets `--scaffold`**. The command `wrap_plugin.py` prints does
  not add it; without it the case runs against an empty folder and the score means
  nothing. Commit the fixture inside the script (`git init`, a local `user.name` and
  `user.email`) if the task is about git.
- `prompt.md` frontmatter accepts only `schema_version`, `name`, `description`,
  `tags`, `plugins`, `runs`, `expected_outcome`, `model`, `max_turns`,
  `timeout_seconds`, `allowed_tools`, `artifact_publish`, `growthbook_overrides`,
  `append_system_prompt` and `env` (Claude Code 2.1.296); an unknown key fails the
  whole case. `context` lives only in `case.yaml`.
- Check the case for free before any paid run: run `scaffold.sh` in a scratch folder,
  then apply the file graders to the untouched tree (the ones that should fail, fail)
  and to a result you made by hand (all pass).

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
- **A bigger judge is not the cure either.** With one decision per grader and
  `--judge-model claude-sonnet-5`, the judge still voted FAIL three times out of three
  on traits plainly present in one arm's answers, and Δ came out −0.25 where reading
  gave +0.08. Run with `--keep-temp`, pull the final answers from `out/trace.jsonl`,
  read them, and report the by-eye score when it disagrees.
- **Don't punish a method for its order.** A grader asking "do the named causes have a
  check?" failed a method that deliberately defers causes until it can reproduce but
  says up front how it will test them. Word the trait so either shape passes.
- **Describe a disqualifier by its substance, not by an example wording.** "E.g.
  'reproduce or infer from logs'" was read as "look for the word 'or'", and the same
  fork expressed by the order of the steps went unnoticed.
- **A regex over hex values misses named colors.** An agent writing Tailwind names
  its palette in the config (`cream: '#F6EFE4'`, then `bg-cream` on `<body>`), so a
  list of hex codes passed a cream page as clean. Match the token name where it is used
  as well. Regex graders are deterministic: after fixing one, re-grade the saved
  outputs locally instead of re-running the agents.
- **The path grader matters more than it seems.** In one run the skill never fired,
  and Δ = 0 compared two identical arms. Without the `tool_used: Skill` indicator it
  would have read as an honest "the skill is useless". If the indicator is `false`,
  throw the result away rather than interpret it.
- **The task must be work, not a question.** A prompt like "briefly, where would you
  start?" is closed in one turn, tool choice never happens, and no skill fires. Ask
  for something to be done, not described.
- **A case that grants a shell does not run on native Windows.** With `Bash` in
  `allowed_tools` and in `--allow-tools`, the eval refuses every run before its first
  turn ("sandbox required but unavailable"): nothing is spent and nothing is measured.
  Such cases run in WSL2, macOS or Linux. Grant the shell narrowly even there
  (`"Bash(git:*)"`, `"Bash(python:*)"`), not `Bash` as a whole.
- `--runs 1` is only for debugging the graders themselves. For a verdict, at least 2.
- Pin the model (`--model`), or a model change will look like a regression.

The cases an accepted skill was checked with move with it: when a new model ships,
the vault can be re-run on them and whatever stopped paying off thrown out.
