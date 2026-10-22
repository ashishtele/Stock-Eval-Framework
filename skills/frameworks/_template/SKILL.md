---
name: framework-template
description: >
  Template for an extracted stock evaluation framework. Copy this directory to
  skills/frameworks/<creator>-<slug>/ and fill it in, or let the
  transcript-to-framework skill generate it. Do not use the template itself to
  evaluate anything.
---

# <Creator> — <Topic> framework

<One or two sentences: what this framework is for, what it deliberately excludes,
and whose reasoning it records.>

- Version: `<x.y.z>` (`draft` until evals pass)
- Status: `unvalidated`
- Source talks: see `framework.json` → `sources`

## Running it

1. Read `framework.json` (schema: `schema/framework.schema.json`).
2. Apply it with the `apply-framework` skill, passing this framework's id and a
   ticker.
3. Write the result up with `stock-memo` if a narrative is needed.

Do not paraphrase the criteria from this file. `framework.json` is the only
source of truth; numbers, thresholds, and evidence live there.

## Known limitations

- Extracted from <n> talk(s); see `CHANGELOG.md` for what each added.
- Unvalidated until `evals/` reproduces this creator's own stated views.
- Records what the creator said, including contradictions kept as `tensions`.
