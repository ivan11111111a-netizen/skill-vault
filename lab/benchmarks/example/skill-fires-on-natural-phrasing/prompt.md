---
name: skill-fires-on-natural-phrasing
description: A sample case. Copy the folder to lab/benchmarks/<your-category>/ and rewrite it.
tags: [example]
runs: 2
max_turns: 12
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

Put the task here the way a person would phrase it. Don't name the skill: the case
also checks whether Claude finds it on its own.

Every run starts in an empty working folder, so put everything needed into the task
text or prepare it through `case.yaml` → `context.scaffold_script`.
