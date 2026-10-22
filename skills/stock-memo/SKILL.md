---
name: stock-memo
description: >
  Turn an evaluation.json produced by apply-framework into a short, sourced
  investment memo: what the framework says, the strongest bull and bear points,
  what would change the conclusion, and the unanswered questions. Use when the
  user wants a written view on a stock, a one-page research note, or an
  explanation of why an evaluation came out the way it did. Produces decision
  support, never a recommendation or price target.
---

# Stock memo

The memo explains an evaluation. It does not redo the analysis and it does not
have opinions the evaluation cannot support.

## Inputs

- `evaluation.json` (required)
- `framework.json` for the criteria wording and rationale (required)
- the source filings used in the evaluation, when the memo cites them

If `evaluation.json` is missing, run `apply-framework` first.

## Structure

```
# <Company> (<TICKER>) — <framework name> v<version>
<as_of> | coverage <n>% | <disqualified / not disqualified / insufficient evidence>

## What the framework measured
One paragraph: what this framework is for and which criteria are disqualifying.

## Where the company stands
Rows grouped as: screens failed, screens passed, judgments, unknown. Reference
criterion ids so the reader can trace each statement.

## Strongest bull case
Two or three points, each tied to a passing criterion or a judgment with cited
evidence. No new arguments.

## Strongest bear case
Two or three points, each tied to a failing or unknown criterion, or a tension
recorded in the framework. If the bear case is thin, say so.

## What would change this view
The specific data points or events that would flip FAIL to PASS, or resolve an
UNKNOWN. This is the most useful section; keep it concrete.

## Open questions
The UNKNOWN list, ordered by how much it would move the conclusion, with the
filing or dataset that would answer each.

## Sources
Every filing, dataset, and transcript used, with dates.

## Caveats
Framework status and version, validation state, and stale-data warnings.
```

## Rules

- Every factual sentence traces to an evaluation row or a listed source. If it
  cannot, delete it.
- Distinguish what the data shows from what the framework infers. Use separate
  paragraphs, not hedging adverbs.
- If `disqualified: true`, lead with that. Do not bury it under a bull case.
- If coverage is below 0.7, the memo's conclusion is "insufficient evidence,"
  full stop.
- Do not introduce valuation multiples, target prices, or expected returns that
  the framework does not define.
- State the framework's own limitations: it is one investor's heuristics, it is
  `draft` or `unvalidated` if it says so, and it is not advice.
- Keep it under 900 words. A memo nobody finishes is not decision support.
