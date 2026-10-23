---
name: stock-cycle-scorer
description: >
  Score a listed stock (built for Indian equities) on Ameya's Pessimism Rate of
  Change and Trajectory Pivot frameworks, and label its cycle stage
  (PEAK_OPTIMISM, CYCLE_CONFIRMED, EARLY_RECOVERY, PEAK_PESSIMISM, DECLINE,
  MIXED). Use when asked to score, screen, or rank stocks; "is this at peak
  pessimism / early recovery"; turnaround, cyclical-turn or pivot score;
  backtesting or calibrating; or when the user uploads a Screener export,
  concall transcripts, or annual reports. Use it even if they do not name the
  skill.
---

# Stock Cycle Scorer

Two independent scores, one stage label. This is a screening aid, not investment
advice.

- **Score 1 — Pessimism Rate of Change (0–100).** Sector pain is priced in *and*
  the business is turning. Cheap alone scores modestly.
- **Score 2 — Trajectory Pivot (0–100).** A new, higher-margin business is large
  enough to change the earnings band, with proof of capability and a management
  team that delivers.
- **Stage:** `PEAK_OPTIMISM`, `CYCLE_CONFIRMED`, `EARLY_RECOVERY`,
  `PEAK_PESSIMISM`, `DECLINE`, or `MIXED`.

The two scores stay separate. They describe different setups.

## Workflow

1. **Pin down the request.** Which stock(s), the `as_of` date (today or a past
   date for a backtest), and what data the user has.
2. **Gather data point-in-time.** Use only what was public on `as_of`. Priority:
   price and valuation history; last 3 concall transcripts; shareholding (5+
   quarters) and promoter insider trades (6 months); quarterly (8–12) and annual
   (up to 10y) results; 3–5 peer drawdowns. For Score 2, also segment history,
   management's pivot targets, and pure-play peer multiples. **Never invent
   numbers**: leave fields out; the scorer re-weights and reports coverage. If a
   source is blocked, say so.
3. **Score the qualitative inputs** with the rubrics in `references/`. Score only
   words from transcripts dated before `as_of` (no hindsight). When borderline,
   re-score from scratch and average. Record 1–3 short evidence lines per call.
4. **Build the input JSON** (see `references/input_schema.md`) and run:
   `python scripts/score.py input.json --json out.json --md out.md`.
   `scripts/import_screener.py` can build a skeleton from a parsed Screener JSON
   or a saved Screener page; it lists what still has to be added by hand.
5. **Present** in this order:
   - three sentences: stage and meaning, both scores with coverage, the single
     most important reason
   - signal tables, vetoes, red flags, build-phase note, evidence
   - what would change the score
   - point-in-time excluded counts
   - "Screening aid only - not investment advice."

If Score 1 coverage is under 50%, say which inputs would help most. Explain in
framework terms, never as buy/sell advice.

## Hard rules

- Do not merge the scores or invent a combined rank.
- Do not estimate missing financials. UNKNOWN stays UNKNOWN.
- Do not use post-`as_of` data, including concall language.
- A veto caps a score at 30; it does not silently drop the stock.
- A management rubric below 2 caps Score 2 at 40.
- Every qualitative score carries evidence lines with a speaker.

## Files

```
scripts/score.py            deterministic scorer (stdlib only)
scripts/import_screener.py  Screener JSON/HTML -> input skeleton
references/input_schema.md  field-by-field input contract
references/pessimism_rubric.md
references/pivot_rubric.md
references/sector_checks.md
references/methodology.md
assets/example_input.json
assets/synthetic_regression.json
assets/real_backtests.json
```

## Acceptance checks

```bash
python scripts/score.py assets/synthetic_regression.json --summary
python scripts/score.py assets/real_backtests.json --summary
python scripts/score.py assets/example_input.json --md example.md
```

The synthetic cases A-J must all print `PASS`. The real backtests cover Apollo Pipes
(5 Feb 2026), Coforge (5 May 2026), Clean Science (18 Dec 2025) and Laurus Labs
(26 Apr 2024); Laurus is a reference case and is not a pass/fail. See
`references/methodology.md` for the limitations.
