---
name: transcript-to-framework
description: >
  Convert an investor video transcript into an explicit, auditable stock
  evaluation framework: criteria with thresholds, red flags, sell rules, and
  verbatim timestamped evidence, written as a self-contained skill under
  skills/frameworks/. Use when the user provides a new transcript or video URL
  and wants it turned into a reusable checklist, or wants an existing framework
  updated with another talk by the same person. Refuses to emit criteria it
  cannot quote.
---

# Transcript to framework

The output is a **checklist a stranger could re-run**, not a summary of the talk.
If a claim cannot be tested against data, it is a heuristic, not a criterion.

## Preconditions

- The transcript exists under `transcripts/` with a `.segments.json` sidecar.
  If not, run `fetch-transcript` first.
- Determine the **creator**: whose framework this is. In an interview the host
  and guest are different people; only the creator's reasoning belongs here.

## Extraction passes

Read the whole transcript before writing anything. Then extract in this order —
it moves from most to least precise.

1. **Exclusions and refusals.** What does the creator refuse to buy, and why?
   ("I don't touch banks", "No company where the founder owns less than 10%").
   These are often the highest-value, easiest-to-test criteria.
2. **Quantitative thresholds.** Any number tied to a decision: growth, margins,
   debt, valuation, holding period, position size. Capture the metric, the
   operator, the value, the unit, and the window if stated.
3. **Qualitative judgments.** Moat, management, capital allocation, industry
   structure. These become `kind: "judgment"` with an explicit verdict scale.
4. **Sell and position rules.** When to add, trim, exit; what would change their
   mind. Put these in `sell_rules` / `position_rules`.
5. **Contradictions.** Where the creator says one thing and does another, or
   contradicts an earlier talk. Record in `tensions`; do not reconcile.

## Turning a statement into a criterion

For each candidate, write down:

- the **question** in neutral, testable form ("Does revenue growth exceed 10% per
  year over five years?")
- the **kind**: `screen` (mechanical, from data) or `judgment` (needs reading)
- the **threshold**: `{metric, operator, value, unit, window}` — required for
  `screen`, optional for `judgment`
- the **evidence**: verbatim quote, timestamp from the sidecar, source id
- the **rationale**: the creator's own reason, not yours
- **disqualifying**: true if one FAIL is enough to reject the stock
- `unvalidated: true` until evals reproduce the creator's views

Attribution rules:

- A criterion requires the creator to have said it, or to have clearly affirmed
  it. A host's framing is not the creator's framework.
- If speaker labels are absent and the attribution is ambiguous, leave the
  criterion out and note the omission in `CHANGELOG.md`.
- Auto-generated captions mangle names and numbers. Quote what the transcript
  says, add `note` when the transcript is clearly wrong, and never "correct" a
  number by guessing. A garbled number is not extractable.
- Do not add criteria from your own knowledge of investing. Mark every item you
  inferred with `note: "inferred"` and keep it out of `criteria`.

## Gate (blocking)

Do not report success until all of these hold:

- [ ] Every criterion/red flag/heuristic/rule has at least one evidence item.
- [ ] Every evidence quote appears in the transcript near its timestamp.
- [ ] Every `screen` criterion has `threshold.metric`, `operator`, `value`, and
      `unit`.
- [ ] Every `judgment` criterion has a `verdict_scale`.
- [ ] No criterion contains a company's financial figure; frameworks hold rules,
      never data.
- [ ] Ids are unique kebab-case; `source_id` values resolve to `sources`.
- [ ] `framework.json` validates against `schema/framework.schema.json`.

Run `python scripts/validate_framework.py <path>` to check the mechanical parts.

## Merging a new transcript into an existing framework

One skill per creator-framework, not per video.

1. Find the existing framework under `skills/frameworks/` and read its
   `framework.json` and `CHANGELOG.md`.
2. Deduplicate by **meaning** (same question + same metric), not wording. Keep
   the single strongest quote; add the new source to `sources`.
3. New criterion, or a threshold change, is a minor version bump. A reversal or
   a rewritten core is a major bump. Quote/typo fixes are a patch.
4. Append a CHANGELOG entry: source added, criteria added/changed/removed, and
   any new tensions.
5. Re-run evals. A version bump resets `validation.status` to `unvalidated`
   until the recorded evals pass again.

## Output

```
skills/frameworks/<creator>-<slug>/
  SKILL.md                thin skill: when to use, how to run, points to JSON
  framework.json          single source of truth, schema-valid
  references/evidence.md  every quote with +-30s of context, grouped by criterion
  CHANGELOG.md            versions, sources, changes, tensions, omissions
```

`references/evidence.md` exists so a human can audit without reading JSON.
It is generated from `framework.json`, never hand-edited.

## Anti-patterns

- Summarizing the talk instead of extracting rules.
- Turning every opinion into a criterion, producing a 60-row checklist nobody
  can run.
- Assigning weights so a composite score looks rigorous. Only use weights the
  creator stated.
- Writing "the creator seems to like quality" — that is a heuristic, and it
  needs a quote too.
