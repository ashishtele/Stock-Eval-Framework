---
name: aveek-mitra-framework-score
description: Score any listed stock (built for Indian small/midcaps) 0-100 on Aveek Mitra's ValuePickr-style bottom-up framework - growth engine, reinvestment ROCE, niche moat and structural tailwind, promoter behaviour and governance kill switches, inflection/catalyst, and P/E-as-perception-of-growth valuation - with an automatic turnaround mode, a "quality in consolidation" re-entry detector, a sell/trim module and a position-size guide. A deterministic Python script produces an auditable rule-by-rule report; qualitative points count only with cited evidence. Use whenever the user wants to run "the Aveek Mitra framework", a bottom-up quality-growth score, asks whether a company is a "good company but not a good investment", a compounder vs value trap vs turnaround, whether to hold/trim/sell or re-enter a stock, or wants to compare stocks on growth, moat, promoter and inflection - even if they don't say "score". For pure valuation mispricing use microcap-mispricing-score instead or alongside.
---

# Aveek Mitra bottom-up framework score (v2)

Turns the investing philosophy from Aveek Mitra's interview into a repeatable, verifiable 0-100 score.
Core beliefs encoded: a good company that isn't growing is not an investment; reinvesting at high ROCE
beats paying dividends; moats come from accumulated know-how in niche, critical products; buy the
inflection while it is still uncertain; sell after a run and re-buy in consolidation if the thesis and
insider buying are intact; P/E is a perception of growth x durability; sell when growth flattens or the
price assumes more growth than the industry can give.

`references/framework.md` maps every rule to the interview. `references/validation.md` shows how v2 scored
the 20 cases from the video against his actual decisions, and its known blind spots. Read them if the user asks
why a rule exists, how reliable the score is, or wants to change weights.

## Scoring structure (100 pts)

The script picks the mode automatically (override with `"mode": "normal" | "turnaround"`):

| Pillar | Normal | Turnaround* | What it rewards |
|---|---:|---:|---|
| A. Growth engine | 25 | 15 | Normal: avg of 3y & 5y sales and PAT CAGR, consistency, momentum. Turnaround: recent sales growth, 5y sales CAGR, consistency |
| B. Capital efficiency | 20 | 20 | ROCE, ROE (turnaround: through-cycle median), incremental ROCE, idle cash, CFO/PAT |
| C. Moat & tailwind | 20 | 20 | Margin stability, OPM vs peers, niche leadership, critical low-cost component, know-how barrier, tailwind, business type |
| D. Promoter & governance | 15 | 15 | Promoter buying, buy price vs CMP, no pledge, stable receivables, promoter hunger |
| E. Inflection / catalyst | 10 | 20 | Loss->profit (incl. latest-quarter profit), deleveraging, volume/utilisation, new-product adoption, unlock trigger |
| F. Valuation | 10 | 10 | Normal: PEG vs peers (absolute PEG fallback), P/E vs own 5y median, addressable-market headroom. Turnaround: price/sales, normalised P/E (mcap / avg PAT up to 10y), headroom |

*Turnaround mode = latest FY loss, or a loss in either of the two prior FYs (growth history is base-distorted).

**Caps:** growth gate (3y sales CAGR < 8% and recent growth < 10%, waived in consolidation) -> 55; local commodity
cyclical -> 55; structural headwind (evidenced) -> 60; asset play without unlock trigger -> 50; accounting concerns +
CFO/PAT < 0.5 or unexplained cash -> 40; auditor issue or pledge > 50% -> 30.

**Base-effect guard:** expected growth is clamped to min(35%, best sales CAGR + 10pp), and "growth shown" uses sales
CAGR + 10pp when PAT CAGR is inflated by a depressed base. Both clamps are printed.

## Workflow

1. **Identify the company and the question** - fresh score, comparison, or hold/sell/re-entry review of a position
   they own (set `holding.own = true` so the sell module produces an action).

2. **Gather data.** Use what the user provides first. Otherwise Screener.in (web_fetch of
   `https://www.screener.in/company/<CODE>/consolidated/` returns all tables as markdown - use standalone if the
   consolidated tables are empty), BSE/NSE shareholding and SAST disclosures, concall transcripts/investor PPTs,
   credit-rating rationales (CRISIL/ICRA/CARE pages often fetch when BSE PDFs don't). Lessons from validation:
   - Always capture the **last 8 quarters** - momentum, turnaround and consolidation logic depend on them. For a
     historical decision, quarterly results published before that date are fair game even if Screener no longer shows them.
   - Collect **market cap** (needed for turnaround valuation) and the **52-week high** (consolidation detector).
   - Find an **industry growth rate** for the end-market (rating rationale / industry report) - it powers sell signal S6,
     which caught the Kitex sale. Use the addressable market, not the headline TAM.
   - Revenue guidance is an acceptable proxy for expected growth; say so. Without guidance use 2/3 of the 3y PAT CAGR -
     the script clamps base-effect nonsense.
   - Record a source for every qualitative claim; empty `evidence` scores 0. Be as willing to evidence a negative
     (`structural_headwind`, flags) as a positive.

3. **Fill the input JSON.** Copy `assets/input_template.json` (fictional example of every field). Annual arrays oldest ->
   latest with `fy_labels` (6-11 years), money in Rs crore. Leave unknown fields out; never guess. `null` inside an array is fine.
   - `business_type`: `compounder`, `global_long_cycle`, `picks_and_shovels`, `turnaround`, `asset_play`, `global_commodity`
     (price-taker in a global commodity, e.g. cotton yarn), `local_commodity_cyclical` (price set by a regional market or
     government: sugar, cement, regional steel). A supplier to a growing commodity user (seamless pipes, refractories) is
     `picks_and_shovels`.
   - `qualitative.structural_headwind`: true only with evidence that the end-market is shrinking/structurally capped
     (e.g. falling birth rates for kidswear, customer technology shift away from the product).
   - `scuttlebutt`: independent checks (`plant_visit`, `agm_attended`, `customer_check`, `supplier_check`, `trade_data`,
     `ex_employee`, `management_meeting`). Desk research alone = Low confidence; that is honest.

4. **Run:** `python scripts/score.py input.json` (markdown) or `--json`. Let the script do the arithmetic.

5. **Present.** Lead with final score, mode, classification and sizing; then pillars, caps, sell signals, rule table.
   Add a 5-8 line narrative: the inflection to watch, what would trigger a sell, the biggest unverified assumption, and the
   cheapest way to close each missing/unverified rule. Show "score on available data" when completeness is below ~90% so
   the user sees how much missing data cost. For several stocks, add a comparison table. Save input JSON + report together.

6. **Caveat:** research framework, not investment advice; only as good as inputs and evidence.

## Reading the outputs

- **Classifications:** COMPOUNDER CANDIDATE; QUALITY IN CONSOLIDATION (accumulate zone); TURNAROUND / INFLECTION
  CANDIDATE (>=45 in turnaround mode, size small); TURNAROUND NOT YET EVIDENCED; WATCH / STARTER QUALITY;
  GOOD COMPANY, NOT A GOOD INVESTMENT; STRUCTURAL HEADWIND; VALUE TRAP RISK; LOCAL CYCLICAL; AVOID (kill switch); PASS.
- **Quality in consolidation** (normal mode): 5y sales CAGR >= 15%, ROCE >= 18%, evidenced moat points >= 6, recent growth
  below the 3y CAGR, AND a price signal - promoter bought at/above CMP, P/E below own 5y median, or price <= 75% of 52w high.
  This is the Shivalik re-entry pattern; it suppresses the growth-flattening sell signal.
- **Sizing:** >=80 ~4%; 70-79 ~3%; 60-69 ~2%; 50-59 watchlist; <50 avoid; consolidation starter ~2%; turnaround 1-2%.
  Low scuttlebutt confidence caps at 2%.
- **Growth priced in:** EPS CAGR the P/E needs for a 13% return over 10 years exiting at P/E 20 (tunable).
- **Sell signals:** S1 growth flattening (recent < half of 3y CAGR and < 10%); S2 P/E > 1.5x peers without superior growth;
  S3 price implies > growth shown + 5pp; S4 addressable market < 3x sales; S5 better alternative; S6 price implies > industry
  growth + 10pp for a decade. 0 -> HOLD, 1 -> REVIEW, 2 -> TRIM, 3+ -> SELL CANDIDATE.

## Adjusting the framework

Weights/thresholds are the `lin(...)` calls and mode weights in `scripts/score.py`. Keep each mode summing to 100, bump
`VERSION`, and re-run the validation cases in `references/validation.md` to see what changed before trusting new weights.
