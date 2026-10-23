# Methodology and limitations

## What the two scores are for

- **Score 1 (Pessimism Rate of Change)** is a timing-oriented screen. It asks whether bad
  news is priced and whether at least two independent signals show a turn.
- **Score 2 (Trajectory Pivot)** is a credibility check on a business becoming something
  else. It is not a timing signal and often rests on judgment.

The **stage** is the primary output. The composite scores rank evidence, not expected
returns. In the Apollo test the later entry scored higher on Score 1 than the trough while
the stage flipped from `CANDIDATE`-like recovery to `PEAK_PESSIMISM`; the gate state, not
the composite, carried the timing information.

## Evidence standard

Every criterion should have a quote, a date and a resolvable source. Prefer primary
sources: company filings, transcripts, investor presentations, exchange disclosures.
Management claims are evidence of what management said, not proof that it is true. Mark
estimates as estimates and keep them out of hard verdicts.

## Why these rules exist

1. **Market skepticism.** Coforge's analysts were friendly, but the stock was down 42%
   while management beat guidance. Without the price-based skepticism rule the signal
   missed a winner.
2. **Credibility discount.** Apollo's management missed its own guidance repeatedly.
   Skepticism is "anchoring" only if management delivers.
3. **Promoter-exit block.** Clean Science would have flipped to `EARLY_RECOVERY` on one
   upbeat call despite a 24-point promoter sale. Insider selling at the lows contradicts a
   turn.
4. **Promoter N/A.** Professionally managed companies were being scored as "no buying".
5. **Earnings delta halved before inflection.** Otherwise a deeper margin collapse raises
   the score while margins are still falling.
6. **Inflection needs a real trough.** A steady uptrend is not a turn from pain.
7. **Neglect fallback and rally rule.** Missing call data should not default to maximum
   neglect; institutions selling into a rally (or being diluted by an issue) is not neglect.
8. **Coverage veto needs leverage.** Apollo's near-zero EBIT came from depreciation on a
   low-debt balance sheet: an earnings problem, not solvency.
9. **Acquisition flag uses the closing date** and fires only once the deal is in reported
   quarters.
10. **Pivot lens keyed to proof of pivot, not total Score 2.** A re-rated pivot loses its
    mispricing and build-phase points.
11. **MIXED must explain itself.** The output names the blocking rule.

## Known limitations

- Calibrated on 3 real cases chosen in hindsight plus 1 reference. That is calibration,
  not validation. Add more value traps before trusting the weights.
- Own-history valuation misleads when the history is short or covers only one phase of the
  cycle.
- Score 2 is a credibility check more than a timing signal. With thin segment, target or
  peer data it rests mostly on rubric judgments.
- Pivot size understates big pivots when segment margins are undisclosed.
- The vetoes (debt, cash burn, pledge, governance) have mostly fired on synthetic data so
  far.
- Rubric scores drift by about a point between readings.
- Data is often partial: transcripts behind bot-blocking, Screener pages dropping columns,
  no point-in-time peer multiples.
- The importer is a skeleton builder. It cannot invent insider trades, peers, concalls or
  segments.

## Workflow

1. Fix `as_of` first. Every later decision is point-in-time.
2. Gather the financial statements, shareholding and price/valuation history.
3. Add concalls with tone, skepticism, guidance delivery and share-gain claims.
4. Add peers for sector breadth, insider trades, and segments/pivot data if relevant.
5. Run `scripts/score.py`.
6. Read the stage and the blocking rule before reading the scores.
7. Write the three-sentence summary: stage and meaning, both scores with coverage, the
   single most important reason. Then show signals, vetoes, evidence and what would change.
8. State the limitations when the data is thin.

## Output contract

JSON carries every computed value: stage, both scores and coverages, pain/turning/delta,
fired signals, optimism signals, supply/demand, valuation percentile, drawdown, off-low,
EBITDA TTM YoY, pivot lens, judgment share, vetoes, red flags, build phase, all signals,
evidence, what would change, and excluded future data. Markdown follows section 9 of the
spec. The disclaimer is always present: **Screening aid only - not investment advice.**
