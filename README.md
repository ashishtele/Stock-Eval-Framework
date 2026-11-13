# Stock Eval Framework

Turn investor talks into explicit, testable stock-evaluation rubrics — then apply
them to any stock with every number and verdict traceable to a source.

Long-form interviews contain the reasoning that never makes it into books or
screeners: what an investor refuses to buy, which number they distrust, what
makes them sell. This repo converts those into checklists a human or an agent
can re-run consistently, and that show their work. The unit of value is the
**framework**, not "an AI that picks stocks."

## Layout

```
skills/
  fetch-transcript/        URL -> normalized, provenance-stamped transcript
  transcript-to-framework/ transcript -> framework.json + evidence (+ gate)
  apply-framework/         framework + financial data -> evaluation.json
  stock-memo/              evaluation.json -> written memo
  stock-cycle-scorer/      Pessimism RoC + Trajectory Pivot scorer
  soic-new-framework/      NEW / J-curve / Train B-C Screener screen
  microcap-mispricing-score/    mispricing score for Indian small/microcaps
  aveek-mitra-framework-score/  bottom-up quality-growth score (ValuePickr)
  momentum-process-score/       price-only momentum ranking ("Process over Prediction")
  equal-stock-framework/        E-QUAL quality/growth/price scorer (Emkay)
  frameworks/
    _template/             copy this to start a new framework
    <creator>-<slug>/      one skill per framework, self-contained
schema/                    framework.schema.json, evaluation.schema.json
transcripts/<creator>/     raw, immutable input (privacy: keep repo private)
evals/<framework-id>/      recorded applications used to validate a framework
metrics/registry.json      formula per criterion, anchors, and basis
data/screener/<TICKER>/    dated Screener snapshots (raw HTML + parsed JSON)
data/prices/<SYMBOL>/      dated Yahoo price snapshots
scripts/                   fetch_transcript.py, fetch_screener.py, fetch_prices.py, score.py
```

## Quickstart

1. Fetch a transcript (needs `pip install -r requirements.txt`):

   ```
   python scripts/fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

   Writes `transcripts/<channel>/<date>-<slug>.md` plus a `.segments.json`
   sidecar with per-cue timestamps. Fetch from your own machine: YouTube blocks
   datacenter IPs.

2. Extract a framework. Invoke the `transcript-to-framework` skill with the
   transcript path. It creates `skills/frameworks/<creator>-<slug>/`.

3. Validate before believing it. Apply the framework to stocks the creator
   actually discussed, record results under `evals/`, and iterate until the
   verdicts match what the creator said. A framework stays `status: draft`
   until this passes.

4. Evaluate a new stock: `apply-framework`, then `stock-memo`.

## Non-negotiable principles

1. **Evidence or it does not exist.** Every criterion carries a verbatim quote
   and a timestamp. No quote, no criterion.
2. **Testable or it is a heuristic.** Unmeasurable ideas go to `heuristics.md`,
   never into the checklist.
3. **UNKNOWN is a valid verdict.** A missing input is reported, never estimated.
4. **Screens are code; judgments are models.** Mechanical checks are
   deterministic. Qualitative ones return a typed verdict plus confidence.
5. **Do not invent what the creator did not say.** No composite score unless the
   framework defines weights. Contradictions are recorded as tensions, not
   smoothed over.

## Metric scoring

`metrics/registry.json` is the formula layer. Each metric carries `formula`,
`inputs`, `anchors`, `basis` and `available`:

- `basis: creator_stated` — the threshold is the creator's own
- `basis: derived` — an accounting identity or explicit convention
- `basis: proxy` — a measurable stand-in, always labelled low/medium confidence
- `available: false` — needs a data adapter that does not exist yet

`scripts/score.py` turns those metrics into a 0–100 equal-weight composite over
the measurable criteria. The composite is **derived, not creator-stated**; the
row table and gate state are the primary output:

```
state = DISQUALIFIED    if viability fails
      = NOT_APPLICABLE  if sector pain, multiple collapse, or drawdown fails
      = INSUFFICIENT    if a core gate is UNKNOWN
      = CANDIDATE       if all core gates pass and an inflection fires
      = WATCH           otherwise
```

A high composite does not override a failed gate. Coverage below 0.7 is
provisional, not a verdict.

```
python scripts/fetch_screener.py APOLLOPIPE --as-of 2026-10-13
python scripts/fetch_prices.py APOLLOPIPE.NS --as-of 2026-10-13
python scripts/score.py APOLLOPIPE --framework ameya-peak-pessimism \
  --as-of 2026-10-13 --peers ASTRAL,SUPREMEIND,FINPIPE
```

Snapshots land in `data/screener/<TICKER>/<date>/` and
`data/prices/<SYMBOL>/<date>/`, so every score can be re-run later.

## Standalone scorer skills

Self-contained scorers that do not use the `metrics/` registry. Each is a
`SKILL.md` + deterministic Python script + JSON config; run the bundled example
first. All are research checklists, not investment advice.

### stock-cycle-scorer

Two scores (Pessimism Rate of Change, Trajectory Pivot), a stage classifier,
vetoes and a point-in-time guard (`skills/stock-cycle-scorer/`).

```
python skills/stock-cycle-scorer/scripts/score.py INPUT.json --summary
```

Synthetic cases A–J pass; four video-mentioned names (Apollo Pipes, Coforge,
Clean Science, Laurus Labs) land in the expected bands. A mechanical 10-stock
smoke test (2026-10-22) ran without errors, but Score 1 coverage was only
56–74% and Score 2 coverage 9%; 7 of 10 landed in `MIXED`. Score 2 is not
usable without segment, pivot and qualitative inputs. Treat it as a deep-dive
aid, not an automated filter. Re-run the synthetic + backtest assets after any
scoring change.

### soic-new-framework

J-curve screen from Ishmohit Arora's SOIC conversation: sales/PAT growth,
margin expansion, return since the latest result, price above the 30-week EMA,
plus derived quality gates and a Train A/B/C stage (`skills/soic-new-framework/`).
J-curve thresholds are creator-stated; the rest is this repo's
operationalization. An optional context layer (theme expiry, RS, ownership,
base, concall sentiment, entry discipline) reports SUPPORTIVE / NEUTRAL /
WARNING and never changes the deterministic stage; catalysts are manual, never
guessed.

```
python skills/soic-new-framework/scripts/screen_screener.py \
  data/screener/APOLLOPIPE/2026-10-13/screener-consolidated.json \
  --price-json data/prices/APOLLOPIPE.NS/2026-10-13/prices.json --summary
```

### microcap-mispricing-score

Gaurav Agrawal's podcast framework for Indian small/microcaps: business-type
valuation (cyclical, stable, growth, capex-transition, new-age), six multiples
vs own history, one-off-stripped / cyclically-adjusted / forward earnings,
P/B-implied P/E, OCF quality, capital-cycle setup, upside/downside asymmetry and
governance kill switches; classifies cheap / value trap / not cheap
(`skills/microcap-mispricing-score/`).

```
python skills/microcap-mispricing-score/scripts/score_stock.py in.json \
  --json result.json --md report.md
```

### aveek-mitra-framework-score

Aveek Mitra's (ValuePickr) bottom-up score for Indian small/midcaps: growth
engine, reinvestment ROCE, niche moat, promoter behaviour and governance kill
switches, inflection/catalyst, P/E as perception of growth — with automatic
turnaround mode, a "quality in consolidation" re-entry detector, a sell/trim
module and position sizing. Qualitative points count only with cited evidence
(`skills/aveek-mitra-framework-score/`).

```
python skills/aveek-mitra-framework-score/scripts/score.py input.json
```

### momentum-process-score

Manish Dhawan / Mystic Wealth, "Process over Prediction": price-only momentum
for NSE/BSE — Stage-2 trend above 30/50/100/200-DMA, volatility-punished ROC,
52-week-high distance, 45-degree trend consistency, circuit filter, 4–5%
position sizing, 80/20 momentum-plus-gold ladder, rank-based buy/exit for a
universe (`skills/momentum-process-score/`; needs `pandas`, see requirements.txt).

```
python skills/momentum-process-score/scripts/momentum_score.py score   # see SKILL.md
python skills/momentum-process-score/scripts/momentum_score.py selftest
```

### equal-stock-framework

Manish Sonthalia (Emkay, ex-Motilal Oswal) three-step growth process from
"Conversation with Kushal": E-QUAL management quality (integrity / capability /
wealth distribution / investor communication / liquidity), earnings-growth
potential (ROCE vs 15% capital cost, profits doubling in 3–4y, structural vs
cyclical) and purchase-price discipline (PEG bands, 5-year cumulative-profit
test, expected vs required return from the market-cap/quality risk-reward
matrix, max buy price) — plus governance kill switches and a BUY / WATCHLIST /
AVOID / PASS / REJECT verdict (`skills/equal-stock-framework/`). Capital weights
and bands are in `scripts/config.json`; the rubric and data-source map are in
`references/rubric.md`.

```
python skills/equal-stock-framework/scripts/score.py company.json \
  --out report.md --json result.json
```

## Installing into another project

This repo follows the `skills/<name>/SKILL.md` layout, so any agent that supports
skill installation (including `skills-lock.json`-style tooling) can pull an
individual framework or procedure from it.

## Disclaimer

This is decision support and a record of how third parties reason. It is not
investment advice, it does not produce price targets, and it does not place
trades. Frameworks describe what a creator *said* and are unvalidated until the
evals in this repo say otherwise.

Transcripts are third-party copyrighted content. Keep this repository private
unless you replace raw transcripts with derived notes and short quotations.
