# Stock Eval Framework

Turn investor talks into an explicit, testable stock-evaluation rubric — then
apply that rubric to any stock with every number and verdict traceable to a source.

The unit of value is not "an AI that picks stocks." It is a **framework**:
a set of criteria with thresholds, verbatim evidence, and timestamps, extracted
from one investor's own words, plus the machinery to apply and audit it.

## Why this exists

Long-form interviews contain the reasoning that never makes it into books or
screeners: what an investor refuses to buy, which number they distrust, what
makes them sell. Those judgments are usually lost because they live in audio.
This repo converts them into checklists that a human or an agent can re-run
consistently, and that show their work.

## Layout

```
skills/
  fetch-transcript/        URL -> normalized, provenance-stamped transcript
  transcript-to-framework/ transcript -> framework.json + evidence (+ gate)
  apply-framework/         framework + financial data -> evaluation.json
  stock-memo/              evaluation.json -> written memo
  stock-cycle-scorer/      standalone Pessimism RoC + Trajectory Pivot scorer
  soic-new-framework/      NEW / J-curve / Train B-C Screener screen
  frameworks/
    _template/             copy this to start a new framework
    <creator>-<slug>/      one skill per framework, self-contained
schema/
  framework.schema.json    structure every framework must satisfy
  evaluation.schema.json   structure every evaluation must satisfy
transcripts/<creator>/     raw, immutable input (privacy: keep repo private)
evals/<framework-id>/      recorded applications used to validate a framework
metrics/registry.json      formula per criterion, anchors, and basis
data/screener/<TICKER>/    dated Screener snapshots (raw HTML + parsed JSON)
data/prices/<SYMBOL>/      dated Yahoo price snapshots
scripts/fetch_transcript.py
scripts/fetch_screener.py
scripts/fetch_prices.py
scripts/score.py
```

## Quickstart

1. Fetch a transcript (needs `pip install -r requirements.txt`):

   ```
   python scripts/fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

   It writes `transcripts/<channel>/<date>-<slug>.md` plus a `.segments.json`
   sidecar with per-cue timestamps. Fetch from your own machine: YouTube blocks
   datacenter IPs, so do not fetch at request time from a deployed server.

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

`metrics/registry.json` is the formula layer: one numeric metric per criterion,
with its formula, inputs, anchors, basis, and data adapter.

- `basis: creator_stated` — the threshold is the creator's own
- `basis: derived` — an accounting identity or explicit convention
- `basis: proxy` — a measurable stand-in, always labelled low/medium confidence
- `available: false` — the metric needs a data adapter that does not exist yet

`scripts/score.py` turns those metrics into a 0–100 equal-weight composite over
the criteria that are measurable. The composite is **derived, not
creator-stated**. The row table and the gate state are the primary output:

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

## Standalone cycle scorer

`skills/stock-cycle-scorer/` is a self-contained implementation of the uploaded
spec: two separate scores (Pessimism Rate of Change and Trajectory Pivot), a
stage classifier, vetoes and a point-in-time guard. It does not use the
`metrics/` registry.

```
python skills/stock-cycle-scorer/scripts/score.py INPUT.json --summary
python skills/stock-cycle-scorer/scripts/score.py INPUT.json --json out.json --md out.md
python skills/stock-cycle-scorer/scripts/import_screener.py \
  --json data/screener/APOLLOPIPE/2026-10-13/screener-standalone.json \
  --prices prices.csv --as-of 2026-02-05 --company "Apollo Pipes" \
  --ticker APOLLOPIPE --sector Pipes --out apollo.json
```

The synthetic cases A-J and the four real backtests are in
`skills/stock-cycle-scorer/assets/`; both must be run after any scoring change.

### Validation status

- Synthetic cases A-J pass.
- Four video-mentioned names match the expected labels/score bands: Apollo Pipes,
  Coforge, Clean Science and Laurus Labs.
- A mechanical 10-stock smoke test on 2026-10-22 completed without errors, but
  Score 1 coverage was only 56-74% and Score 2 coverage was 9% for every name;
  7 of 10 stocks landed in `MIXED`.
- This is calibration and mechanical validation, not proof of predictive edge.
  Score 2 is not usable without segment, pivot and qualitative inputs. Treat the
  skill as a research checklist and deep-dive aid, not an automated stock filter.

## SOIC NEW screen

`skills/soic-new-framework/` implements the J-curve scan from Ishmohit Arora's
SOIC conversation: sales growth, PAT growth, operating-margin expansion, return
since the latest result, and price above the 30-week EMA. It adds derived quality
gates and a Train A/B/C stage. Catalysts are supplied manually from announcements,
concalls or interviews; the Screener-only mode never guesses them.

```
python skills/soic-new-framework/scripts/screen_screener.py \
  data/screener/APOLLOPIPE/2026-10-13/screener-consolidated.json \
  --price-json data/prices/APOLLOPIPE.NS/2026-10-13/prices.json --summary
```

The J-curve thresholds are creator-stated; the quality gates and stage rules are
this repository's operationalization. It is a candidate filter, not investment
advice.

## Installing into another project

This repo follows the `skills/<name>/SKILL.md` layout, so any agent that supports
skill installation (including `skills-lock.json`-style tooling) can pull an
individual framework or procedure from it.

## Disclaimer

This is decision support and a record of how a third party reasons. It is not
investment advice, it does not produce price targets, and it does not place
trades. Frameworks describe what a creator *said* and are unvalidated until the
evals in this repo say otherwise.

Transcripts are third-party copyrighted content. Keep this repository private
unless you replace raw transcripts with derived notes and short quotations.
