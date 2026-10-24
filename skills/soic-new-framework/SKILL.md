---
name: soic-new-framework
description: >
  Screen a listed stock against the SOIC "NEW" framework from Ishmohit Arora:
  new earnings power, a J-curve inflection, a visible catalyst, and the
  Train A/B/C stage. Use when asked to screen or rank stocks for new products,
  new orders, new management, new capacity, turnarounds, or J-curve setups, or
  to apply the video's "Potential J-Curve" scan to Screener data. Reports
  UNKNOWN and coverage instead of guessing.
---

# SOIC NEW framework screen

This is a **derived screen** built from Ishmohit Arora's talk, not a
reproduction of his private process. The J-curve thresholds come from the
video's scan. The quality gates and Train A/B/C rules are this repository's
operationalization and are labelled as such.

Source: <https://www.youtube.com/watch?v=O_TndKzToCI>

## What it checks

**Creator-stated J-curve conditions**

1. Sales growth `>= 20%`
2. PAT growth `>= 30%`
3. Operating-margin expansion `>= 10%`
4. Return since the latest result `>= 5%`
5. Price above the 30-week EMA

**Derived quality gates**

- CFO positive
- Interest cover `>= 2x`
- Debt/equity `<= 2x`
- Sales positive

**Derived stage**

- `TRAIN_C` — J-curve confirmed and a catalyst is tagged
- `TRAIN_B` — catalyst/capex visible, but the J-curve is not yet confirmed
- `TRAIN_A` — no visible catalyst and no inflection
- `CANDIDATE` — J-curve confirmed, but no catalyst was supplied
- `WATCH` — partial evidence or a failed quality gate
- `INSUFFICIENT` — coverage below the gate

A catalyst is required for `TRAIN_B` and `TRAIN_C`. Without a catalyst tag the
tool never guesses a train stage.

## Procedure

1. **Get a dated Screener snapshot.** Use the repository fetcher:

   ```
   python scripts/fetch_screener.py APOLLOPIPE --as-of 2026-10-13
   ```

   Prefer the consolidated statement. Record the `as_of` date.

2. **Get price history** for J4 and J5:

   ```
   python scripts/fetch_prices.py APOLLOPIPE.NS --as-of 2026-10-13
   ```

   J4 needs the latest result date. Pass `--result-date` when known. If omitted,
   the tool infers it as quarter-end + 45 days and labels that in the output.

3. **Run the screen:**

   ```
   python skills/soic-new-framework/scripts/screen_screener.py \
     data/screener/APOLLOPIPE/2026-10-13/screener-consolidated.json \
     --price-json data/prices/APOLLOPIPE.NS/2026-10-13/prices.json \
     --summary
   ```

   Add catalysts only when you have an announcement, concall or interview:

   ```
   --catalyst large_order --catalyst new_capex
   ```

   Use `--list-catalysts` for the allowed tags.

4. **Read the row table, not just the stage.** The stage is a summary. The
   J-curve rows, quality gates, coverage and unknowns are the evidence.

5. **Add the qualitative layer manually.** Orders, new products, management
   changes, themes and interviews are not in Screener. Do not infer them from a
   shareholding change or a price move.

6. **Optionally encode the qualitative layer in a context file.** Use
   `--context context.json` for theme, base formation, concall sentiment, entry
   discipline and valuation notes. Use `--benchmark-json` to compute relative
   strength from two price files. The context layer never changes the stage; it
   adds a separate `SUPPORTIVE / NEUTRAL / WARNING / MISSING` status.

## Commands

```
python skills/soic-new-framework/scripts/screen_screener.py SCREENER.json --summary
python skills/soic-new-framework/scripts/screen_screener.py SCREENER.json \
  --price-json PRICES.json --result-date YYYY-MM-DD \
  --catalyst large_order --json out.json --md out.md
python skills/soic-new-framework/scripts/screen_screener.py SCREENER.json \
  --price-json PRICES.json --benchmark-json BENCHMARK.json \
  --context CONTEXT.json --result-date YYYY-MM-DD --summary
python skills/soic-new-framework/scripts/screen_screener.py --list-catalysts
python skills/soic-new-framework/scripts/screen_screener.py --print-config
```

The context file is optional. Its schema is illustrated by
`assets/example_context.json`; the benchmark fixture is
`assets/example_benchmark_prices.json`.

## Output contract

The JSON contains:

- `j_curve[]` — each condition with value, threshold, status, basis
- `j_count`, `j_known`, `j_coverage`
- `quality[]`, `quality_status`
- `coverage`
- `catalysts`, `catalyst_count`, `capex_signal`
- `stage`
- `unknowns[]`
- `context` (optional): status, theme, relative strength, ownership, base,
  concall, entry, valuation, market stage, warnings, notes
- `notes[]`

Report, in order:

1. stage and one-sentence meaning
2. J-curve table
3. quality gates
4. coverage and unknowns
5. catalysts and their evidence, if supplied
6. context layer, if supplied, with its separate status
7. “Screening aid only — not investment advice.”

## Hard rules

- Do not call this Ishmohit's exact score. The J-curve thresholds are his; the
  quality gates and stage rules are ours.
- Do not invent a catalyst to upgrade `CANDIDATE` to `TRAIN_C`.
- Do not let the context layer change the stage. It is a separate risk/quality
  note, not a hidden score.
- Do not invent context fields. If a theme, base, concall or entry observation is
  not sourced, leave it out or mark it unknown.
- Do not use post-`as_of` data. Screener snapshots and price files must be dated.
- Do not estimate missing values. `UNKNOWN` is a valid result.
- Do not use P/E as a gate. The video explicitly says not to lead with
  valuation.
- Do not treat a high J-count as a buy signal. Quality gates still apply.
- Do not screen banks, insurers or other companies where operating profit,
  debt/equity and CFO mean something different without adapting the gates.
- If the latest quarter is not the latest annual period, state which basis was
  used for sales, PAT and OPM.

## Files

```
scripts/screen_screener.py       deterministic Screener-only screen
assets/config.json               thresholds, catalyst tags, notes
assets/example_screener.json     synthetic J-curve example
assets/example_prices.json       synthetic price history
assets/example_context.json      synthetic qualitative context
assets/example_benchmark_prices.json synthetic benchmark history
references/context-schema.md     optional context JSON schema
references/screener-variables.md variable mapping and formulas
references/j-curve-rules.md      creator-stated thresholds and timestamps
references/catalyst-taxonomy.md  the video's catalyst types
references/train-stages.md       Train A/B/C definitions
references/convexity-and-new.md  convexity and the NEW taxonomy
references/theme-expiry.md       theme expiry and capital-cycle risk
references/relative-strength.md  benchmark-relative returns
references/funnel-and-watchlist.md theme-to-watchlist process
references/entry-and-base-formation.md entry discipline and bases
references/concall-sentiment.md  concall reading and “Congrats Index”
references/time-horizon-and-valuation.md three-year view and valuation caution
references/market-stage.md       market/index Train stage and theme win-rate
references/methodology.md        limitations and reproducibility notes
```

## Acceptance checks

```
python skills/soic-new-framework/scripts/screen_screener.py \
  skills/soic-new-framework/assets/example_screener.json \
  --price-json skills/soic-new-framework/assets/example_prices.json \
  --result-date 2026-08-14 --catalyst new_capex --summary
```

Expected: `TRAIN_C`, `J=5/5`, `Q=PASS`, `cov=100%`.

```
python skills/soic-new-framework/scripts/screen_screener.py \
  skills/soic-new-framework/assets/example_screener.json --summary
```

Expected: `WATCH`, J-curve passes 3 of 5 known conditions, coverage below 100%,
because price-dependent conditions are UNKNOWN.

Context-layer smoke test:

```
python skills/soic-new-framework/scripts/screen_screener.py \
  skills/soic-new-framework/assets/example_screener.json \
  --price-json skills/soic-new-framework/assets/example_prices.json \
  --benchmark-json skills/soic-new-framework/assets/example_benchmark_prices.json \
  --context skills/soic-new-framework/assets/example_context.json \
  --result-date 2026-08-14 --catalyst new_capex --summary
```

Expected: the same `TRAIN_C`, `J=5/5`, `Q=PASS`, `cov=100%`, plus
`ctx=SUPPORTIVE`. The context layer must not change the stage.

Real-data smoke test:

```
python skills/soic-new-framework/scripts/screen_screener.py \
  data/screener/APOLLOPIPE/2026-10-13/screener-consolidated.json \
  --price-json data/prices/APOLLOPIPE.NS/2026-10-13/prices.json --summary
```

## Limitations

- Screener has no order book, product pipeline, management quality, theme tags or
  concall language. Those must be supplied with evidence.
- The 30-week EMA and return-since-result need price history; a Screener-only run
  cannot evaluate them.
- The result date is inferred when not supplied. That is a convenience, not a
  fact.
- The quality gates are generic and will misclassify financials and some
  asset-light businesses.
- The context layer is manually sourced. It does not detect themes, bases,
  concall sentiment or entry points by itself. `--benchmark-json` only computes
  relative return; it does not choose the benchmark or the window for you.
- This is a candidate filter. It does not reproduce the full discretionary
  framework and is not investment advice.
