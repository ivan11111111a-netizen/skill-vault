---
type: llm
weight: 2
---

PASS if the answer contains <one specific trait of a correct result>.
FAIL if <a trait of an empty, incomplete or wrong answer>.

The judge is a model call: it costs money and wobbles. Keep the rubric short, one
decision per grader, and describe substance, not formatting. Check long text with
a regex over a file instead.
