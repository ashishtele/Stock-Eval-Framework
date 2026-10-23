---
name: ameya-peak-pessimism
description: >
  Apply Ameya Deosthali's Pessimism Rate of Change Tracker to a stock: sector
  pain, multiple collapse, analyst neglect, capacity exit, promoter buying, and
  the management-bullish/analysts-skeptical inflection. Use when the user asks
  whether a beaten-down cyclical or regulated-sector stock is at peak pessimism
  or early recovery, or asks how Ameya would view a stock. Cyclical and
  sector-level; not a general quality-compounder checklist.
---

# Ameya Deosthali — Pessimism Rate of Change Tracker

Records one investor's cycle-timing framework. `framework.json` is the only
source of truth for criteria, thresholds, and evidence.

- Version: `0.1.0` (draft)
- Status: `unvalidated`
- Source: Kushal Lodha #393, 2026-10-13 (auto-captions)

## How it is meant to be used

1. Apply it with the `apply-framework` skill, passing `ameya-peak-pessimism`
   and a ticker.
2. Judge sector pain and the shock type first. If there is no sector-wide pain
   or no identified recovery mechanism, the framework does not apply.
3. Peak pessimism alone is wait-and-watch. Entry requires an inflection:
   capacity exit, promoter buying, or bullish management against skeptical
   analysts.
4. Report `UNKNOWN` for anything Screener or filings cannot answer. Coverage
   below 70% means the framework cannot judge the stock.

## What this framework is not

- Not a quality-compounder screen; it deliberately prefers the higher-delta
  name over the best operator.
- Not a valuation floor. A low multiple without a recovery mechanism is a value
  trap, and `structural-viability` is disqualifying.
- Not validated. No evals have reproduced the creator's own calls yet.

See `references/evidence.md` for every quote in context and `CHANGELOG.md` for
what this version adds and omits.
