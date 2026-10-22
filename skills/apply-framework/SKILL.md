---
name: apply-framework
description: >
  Apply an extracted stock evaluation framework to a specific ticker and produce
  a row-by-row PASS/FAIL/UNKNOWN evaluation with a source for every value. Use
  when the user asks to evaluate, screen, or score a stock against a named
  framework in skills/frameworks/, or asks how a stock would fare under an
  investor's criteria. Reports missing data as UNKNOWN instead of estimating it.
---

# Apply a framework

Input: a framework in `skills/frameworks/<id>/framework.json` and a ticker.
Output: `evaluation.json` conforming to `schema/evaluation.schema.json`, plus a
markdown table for the user.

## Procedure

1. **Load the framework.** Read `framework.json` and `CHANGELOG.md`. Note the
   version and `validation.status`. If `status` is `draft`, say so in the output.

2. **Build the data requirement list** from `criteria[].data_required` and
   `threshold.metric`. Resolve each to a concrete field (for example
   `income_statement.revenue`, `balance_sheet.total_debt`,
   `cash_flow.operating_cash_flow`) and the period the threshold names.

3. **Acquire data, with provenance.** Acceptable sources, in order:
   - the company's own filings (10-K/20-F/annual report) supplied by the user or
     retrieved from a filings source
   - a financial data API the user has configured
   - a user-provided screener export

   Every value carries `source` (URL, filing page, or dataset name) and `as_of`.
   Prefer the framework's stated window; if unavailable, use the closest period
   and set `note`.

4. **Evaluate screens deterministically.** Compute the metric from the acquired
   data and compare with the operator and value. Do the arithmetic in code or
   show it; never eyeball a threshold.

5. **Evaluate judgments deliberately.** Answer each judgment question using the
   filings and the framework's own rationale. Return `PASS`, `FAIL`, or
   `UNKNOWN`, plus a note citing the specific evidence (section, page, or quote).
   If the framework defines a `verdict_scale`, use it. Do not substitute a
   generic quality score.

6. **Handle missing data.** If a value is unavailable, the row is `UNKNOWN`.
   Never estimate, interpolate, annualize, or "assume roughly." UNKNOWN is
   information: it tells the reader what the framework cannot currently judge.

7. **Disqualification.** If any `disqualifying: true` criterion is `FAIL`, or any
   `severity: fatal` red flag triggers, set `disqualified: true` and list the
   reasons. A disqualified stock does not need the remaining rows finished, but
   record what was evaluated.

8. **Coverage.** Compute `coverage = (pass + fail) / (pass + fail + unknown)`.
   If coverage is below 0.7, state plainly that the evidence is insufficient to
   apply this framework and do not present a verdict.

## Scoring

Do not invent a composite score. Emit `score` only when the framework defines
`weight` on its criteria; otherwise `score` is null and the result is the row
table plus the disqualification status. When weights exist, show the formula.

## Output contract

Return, in this order:

1. a one-line status: disqualified / passes all screens / insufficient evidence,
   with coverage
2. the row table: `criterion | verdict | value | source`
3. the UNKNOWN list, with what data would resolve each
4. any triggered red flags and the sell rules that now apply
5. the path to the saved `evaluation.json`

When the run is part of validating a framework, save it to
`evals/<framework-id>/<ticker>-<YYYY-MM-DD>.json` and add that path to
`validation.evals`.

## Hard limits

- No buy/sell recommendation, no price target, no position size beyond what the
  framework states.
- No value without a source. If pressed, return UNKNOWN.
- No criteria added, removed, or reinterpreted. If the framework is wrong, fix
  the framework and version it.
- Never mix data periods silently; state the period for every row.
