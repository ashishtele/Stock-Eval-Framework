# Rebuild specification: Stock Cycle Scorer skill

**For the agent building this.** This document describes a working, tested skill. Build the
files in section 2, follow the logic in sections 4–9 exactly, then pass the acceptance tests in
section 12. Section 13 explains *why* several rules exist. Each one was added after a real-data
test failed, so do not simplify them away. All numbers are defaults that live in one config
block (section 11).

---

## 1. What the skill does

It scores a listed stock (built for Indian equities) on two investing frameworks taken from a
podcast with an independent investor, Ameya of the "Value Equity" page on Twitter/X and Substack:

- **Score 1: Pessimism Rate of Change (0–100).** Finds stocks where sector pain is
  priced in *and* the business is starting to turn: promoters buying, management confident
  while analysts or the market stay skeptical, margins lifting off a trough, market-share gains.
  Cheapness alone scores modestly, because a cheap stock with no turn is a value trap.
- **Score 2: Trajectory Pivot (0–100).** Finds companies whose new, higher-margin business
  is large enough to change the earnings band if even half of it works, backed by proof of
  capability and a management team that delivers.
- **Stage label:** PEAK_OPTIMISM, CYCLE_CONFIRMED, EARLY_RECOVERY, PEAK_PESSIMISM, DECLINE or
  MIXED, plus a supply-vs-demand tag, value-trap vetoes, red flags, a price check, evidence lines
  and "what would change the score".

The two scores stay separate: they describe different setups. Every output ends with
"Screening aid only - not investment advice."

## 2. Files to build

```
stock-cycle-scorer/
├── SKILL.md                     # frontmatter (name, description) + workflow (section 3)
├── scripts/
│   ├── score.py                 # deterministic scoring engine (sections 4–9), stdlib only
│   └── import_screener.py       # Screener.in Excel export -> input JSON (section 10)
├── references/
│   ├── input_schema.md          # section 4
│   ├── pessimism_rubric.md      # section 8.1
│   ├── pivot_rubric.md          # section 8.2
│   ├── sector_checks.md         # section 8.3
│   └── methodology.md           # sections 5–7 in prose, for explaining scores
└── assets/
    ├── example_input.json       # one synthetic company with every field filled
    ├── synthetic_regression.json# section 12.1
    └── real_backtests.json      # section 12.2
```

`score.py` CLI: `score.py input.json [--json out.json] [--md out.md] [--summary] [--config override.json] [--print-config]`.
The input is an object (one company) or a list (batch). `--summary` prints a table with an
Expected/Check column driven by an optional `expected` block in each input. A `--config` file
deep-merges over the defaults.

**SKILL.md description (triggering):** say it scores stocks on the Pessimism Rate of Change
and Trajectory Pivot frameworks and labels the cycle stage. List triggers: score, screen or rank
stocks; "is this at peak pessimism / early recovery"; turnaround, cyclical-turn or pivot score;
uploads of Screener exports, concall transcripts or annual reports; backtesting or calibrating.
Add "even if they don't name the skill".

## 3. Workflow (the body of SKILL.md)

1. **Pin down the request:** which stock(s), the `as_of` date (today, or a past date for a
   backtest), what data the user has.
2. **Gather data point-in-time.** Use only what was public on `as_of`. Priority: price and
   valuation history, then the last 3 concall transcripts, then shareholding (5+ quarters) and
   promoter insider trades (6 months), then quarterly (8–12) and annual (up to 10y) results, then
   3–5 peer drawdowns. For Score 2, also segment history, management's pivot targets and
   pure-play peer multiples. **Never invent numbers**: leave fields out; the scorer re-weights
   and reports coverage. If a source is blocked, say so.
3. **Score the qualitative inputs** with the rubrics (section 8). Score only the words in
   transcripts dated before `as_of` (no hindsight). When borderline, re-score from scratch and
   average. Record 1–3 short evidence lines per call.
4. **Build the input JSON** (section 4) and run `score.py`.
5. **Present:** lead with three sentences (stage and its meaning, both scores with coverage,
   the single most important reason). Then show the signal tables, vetoes and red flags,
   evidence and what would change. If coverage is under 50%, say which inputs would help most.
   Explain in framework terms, never as buy/sell advice.

## 4. Input data model

Units: money in Rs crore; holdings, pledges, drawdowns and target margins in **percent**
(55.2 = 55.2%); ratios as plain numbers; dates YYYY-MM-DD.

| Block | Fields |
|---|---|
| top level | `company, ticker, sector, as_of` (required), `no_promoter` (bool, optional), `expected` (tests only) |
| `price` | `current, high_3y, low_52w`, or `history: [{date, close}]` (preferred; the scorer derives the three values as of `as_of`) |
| `valuation` | `pb_current, pb_history`; `ev_ebitda_current, ev_ebitda_history`; `pe_current, pe_history, pe_forward`. History items are numbers or `{date, value}` (dated is better) |
| `quarterly[]` | `period_end, revenue, ebitda`, optional `depreciation, interest, pat, gross_profit, volume, reported_on` |
| `annual[]` | `period_end, revenue, ebitda`, optional `cfo, debt, equity, cash, capex, reported_on` |
| `shareholding[]` | `period_end, promoter, fii, dii, pledge_pct` (pledge as % of promoter holding) |
| `insider_trades[]` | `date, person_category, type (buy/sell), value_cr, mode`. Only promoter / promoter-group trades with mode market/open_market count. Include the key with `[]` if checked and none were found |
| `corporate_actions[]` | `date, type, value_cr`. QIP/OFS types count as late-cycle fund-raising. Acquisitions use `type: "acquisition"` and the **closing/consolidation date** |
| `peers[]` | `company, drawdown_from_3y_high_pct` (same `as_of`) |
| `segments[]` | `period_end, name, revenue, ebit` (all segments of a period present) |
| `pivot` | `new_segments[], segment_period (quarter/year), target_revenue, target_margin_pct, target_source, pure_play_multiple, multiple_type (ev_ebitda/pe)` |
| `qualitative` | `concalls[]` (section 8.1), `shock_type, lost_share_in_downturn, governance_flags[], capability_proof, capability_built_vs_bought, management_track_record, external_tailwind`, and evidence lists `capability_evidence, management_evidence, tailwind_evidence` |

**Point-in-time guard.** An item is used only if it was available on `as_of`. Availability is
`reported_on` if given; otherwise `period_end` plus a lag (quarter 45 days, annual 60,
shareholding 21; events count from their `date`). Dated valuation-history points after `as_of`
are dropped. Report the counts of excluded items in the output.

## 5. Score 1: Pessimism Rate of Change

Notation: `lin(x, x0, x1)` maps x0→0 and x1→1, clamped to [0, 1] (works reversed). Signal
scores are 0–100. `combine` = weighted mean of available signals, renormalised. Coverage = share
of leaf weight that had data.

**Score 1 = 0.40 × Pain + 0.45 × Turning + 0.15 × Earnings delta**

### 5.1 Pain (how much is priced in)
| Signal | Weight | Computation |
|---|---|---|
| valuation | 0.30 | First metric in [P/B, EV/EBITDA, P/E] with 3+ history points. Percentile = (count below + 0.5 × count equal) / n × 100. Score = 100 − percentile |
| drawdown | 0.20 | dd = 1 − price / high_3y; `lin(dd, 0, 0.60)` |
| earnings stress | 0.20 | Cycle-average margin = mean annual EBITDA/revenue over the last 10 years (needs 3+), else mean quarterly margin (needs 8+ quarters). TTM margin = last 4 quarters. Part A (weight 0.6) = `lin((avg − ttm)/avg, 0, 0.40)`. Part B (0.4) = share of the last up-to-8 quarters with EBITDA below the same quarter a year earlier |
| neglect | 0.15 | Mean of the available parts: call length `lin(min, 90, 30)`; analyst questions `lin(n, 20, 5)`; institutional change (FII+DII latest − 4 quarters earlier) `lin(chg, +3, −3)`. Use the most recent of the last 3 calls that has length/question data, if ≤200 days old. **Ignore a falling FII+DII when the price is ≥50% above its 52-week low** (selling into strength) |
| sector breadth | 0.15 | Needs 3+ peers. Share of peers ≥40% below their 3y high; `lin(share, 0, 0.60)` |

### 5.2 Turning (is it changing). Each signal can "fire"
| Signal | Weight | Computation |
|---|---|---|
| promoter | 0.30 | **Not applicable** (dropped, re-weighted) if promoter holding is 0 for the last 3 quarters or `no_promoter` is set, and there are no promoter trades. Otherwise net = open-market promoter buys − sells (value) in the last 183 days; holding change = promoter % latest − 2 quarters earlier. net > 0 → 80 (+20 if holding rose), fires. net < 0 → 0, marks *promoter selling*. Else holding +0.25pp or more → 60, fires; −0.25pp or less → 0, *promoter selling*; else 20 |
| sentiment gap | 0.30 | Use calls that have both `mgmt_tone` and `analyst_skepticism`; take the last 3. t, sk = latest; Δ = t − tone of the oldest of those. **Market skepticism:** if the last 2 calls (any) record `prior_guidance_met` with no `false`, and dd ≥ 30%, and sk < 3, set sk = 3. Score = 0.5·lin(t,1,5) + 0.3·lin(sk,1,5) + 0.2·lin(Δ,0,2), then × credibility: misses (`prior_guidance_met == false`) in the last 2 calls → 0 misses ×1.0, 1 miss ×0.75, 2 misses ×0.5. Fires if t ≥ 4, sk ≥ 3 and misses < 2 |
| margin inflection | 0.25 | Last up-to-8 quarters of margin (gross margin if every quarter has `gross_profit`, else EBITDA margin); needs 4+. Trough = lowest. If the trough is the latest quarter → 0. If the trough was the previous quarter → 50 if the rise is ≥1pp, else 25. Otherwise → 100 if the last two quarter-on-quarter moves are both non-negative, else 40, and halved if the rise is <1pp. If EBITDA-based and the trough is above 0.9 × the cycle-average margin, cap at 30 (a steady uptrend is not a turn from pain). Fires if ≥50 |
| market share | 0.15 | Any of the last 2 calls has `market_share_gain_claimed: true` → 100, fires; if the field is present but false → 0 |

### 5.3 Earnings delta
If TTM EBITDA ≤ 0 and the cycle average is > 0 → 100. Else potential = max(0, (avg − ttm)/ttm);
score = `lin(potential, 0, 1.0)`. **Multiply by 0.5 if the margin-inflection signal has data but
has not fired.**

## 6. Tags, red flags, vetoes

**Supply vs demand** (TTM vs prior TTM): realisation growth = (1+revenue g)/(1+volume g) − 1.
Volume g ≥ 8% → DEMAND_LED; realisation > 3% with volume < 5% → SUPPLY_SHOCK; else MIXED. With
no volume data use `qualitative.shock_type`, else UNKNOWN.

**Red flags** (shown, not capping):
- interest coverage < 2x when it doesn't qualify as a veto
- margin up ≥4pp in one quarter ("check for inventory gains")
- an acquisition closed within 455 days *and* on or before the latest reported quarter end, with positive TTM EBITDA growth ("growth includes an acquisition")
- promoter holding down ≥5pp over two quarters ("insiders selling into the weakness")

**Score 1 vetoes** (cap Score 1 at 30):
- interest coverage (TTM EBITDA − depreciation)/interest < 2 with debt rising year on year **and** debt/equity ≥ 0.5 (or equity unknown)
- operating cash flow negative 3 straight years
- promoter pledge > 25% or up > 2pp over 2 quarters
- any governance flag
- `lost_share_in_downturn`

**Score 2 vetoes** (cap 30): pledge and governance only. A pivot's build phase legitimately
raises debt. **Management gate:** management rubric < 2 caps Score 2 at 40.

## 7. Stage classifier (checked in this order)

Definitions:
- vp = valuation percentile, dd = drawdown, off_low = price/52w low − 1
- n_fired = number of turning signals that fired
- optimism signals = promoter selling; QIP/OFS in the last 365 days; `aggressive_guidance` on the latest call; latest call ≥ 90 min
- **pivot lens** = (segment-shift score ≥ 60 **and** capability ≥ 3/5); fallback when segment data is missing: Score 2 ≥ 60 with coverage ≥ 0.5
- **promoter exit** = promoter holding down ≥5pp over two quarters

| Stage | Rule |
|---|---|
| PEAK_OPTIMISM | (vp ≥ 90 **and not** pivot lens) or (vp ≥ 80 and 2+ optimism signals) |
| CYCLE_CONFIRMED | TTM EBITDA growth ≥ 15%, DEMAND_LED, n_fired ≥ 1, 40 ≤ vp < 80 (or vp unknown) |
| EARLY_RECOVERY | n_fired ≥ 2, vp ≤ 50 (or unknown), (dd ≥ 25% or off_low ≥ 30%), **and no promoter exit** |
| PEAK_PESSIMISM | vp ≤ 25 (or unknown), dd ≥ 40%, n_fired ≤ 1 |
| DECLINE | TTM EBITDA growth < 0 and n_fired ≤ 1 |
| MIXED | anything else, and the output must say which rule blocked the nearest stage |

Low-confidence flag when vp or dd is missing or Score 1 coverage < 50%.

**Price check text:**
- vp ≥ 80 → "rich vs own history: a good business may not be a good investment at this price". With the pivot lens on, say instead that the history reflects the old business mix and to judge price on incremental earnings.
- vp ≤ 30 → "cheap vs own history".
- Otherwise → "middle of range".
- Append forward P/E if given.

**"What would change the score" hints:**
- Name the missing turning signals.
- For MIXED, state the blocking rule (e.g. "3 signals firing but valuation 80th percentile > 50 max; check the history covers a full cycle").
- Name the promoter-exit block, and the guidance-miss block for the sentiment signal.
- Warn when the pivot lens is just off.
- List missing data. Collapse to one line when a whole score has no inputs.

## 8. Score 2: Trajectory Pivot

| Signal | Weight | Computation |
|---|---|---|
| segment shift | 0.20 | Group segments by period; window = last 12 quarters or last 5 years. Mix = 0.7·lin(Δshare pp first→last, 0, 20) + 0.3·lin(latest share %, 0, 40). Margin diff (needs segment EBIT over the last 4 quarters / last year) = lin(new margin / base margin, 1.0, 1.8). Signal = 0.6·mix + 0.4·margin diff (renormalised if one is missing) |
| pivot size ("orbit") | 0.20 | Annualise current new/base revenue and EBIT (if EBIT is missing, apply the company TTM EBITDA margin to both and flag it). expected_new = new_ebit + 0.5 × (target_revenue × target_margin − new_ebit). orbit = (base_ebit + expected_new) / (base_ebit + new_ebit). lin(orbit, 1, 3) |
| capability | 0.20 | rubric/5, minus 0.10 if bought or 0.05 if mixed (on the 0–1 scale) |
| management | 0.20 | rubric/5 |
| mispricing | 0.10 | company multiple ÷ pure-play multiple; lin(ratio, 1.0, 0.4) |
| tailwind | 0.10 | rubric/5 |
| build phase | 0.10 | Needs 5+ years of annual capex and revenue. ratio = max capex/sales of the last 4 years ÷ mean of the 3 years before. lin(ratio, 1, 2), at full credit only if capability ≥ 3, otherwise ×0.5. Show a note when ratio ≥ 1.5 |

**Judgment share** = weight of capability + management + tailwind among available signals.
Above 60%, warn that Score 2 rests on judgment and that one rubric point moves it by
~(20 × 0.20 / available weight) points.

### 8.1 Concall rubric (fields per call)
- `date`; `duration_min` (estimate from word count at ~150 words/min if needed, and say so); `analyst_questions` (distinct participants).
- `mgmt_tone` 1–5: 1 defensive (guiding down, cutting capex); 2 cautious (wait-and-watch, flat or no guidance); 3 balanced; 4 constructive (bottom is in, positive guidance, share gains, restarting capex); 5 bullish with specifics (raised quantified guidance, order wins, promoters buying, capacity committed).
- `analyst_skepticism` 1–5: 1 enthusiastic; 2 mostly accepting (modelling questions); 3 probing (asks for evidence); 4 skeptical (repeatedly challenges guidance, anchored to the last downturn); 5 disbelieving or hostile.
- `market_share_gain_claimed`: management says it is gaining share or weaker players are exiting.
- `aggressive_guidance`: guidance stretched for the cycle stage (very high multi-year targets, big capacity announcements in a boom).
- `prior_guidance_met`: did this call's reported results deliver the previous call's quantified guidance? Within ~10% of the guided figure (or low end) = true, bigger shortfall = false, not checkable = omit.
- `evidence`: 1–3 short lines with speaker.

Other flags:
- `shock_type`: supply_shock if improvement is price- or supply-driven (input costs, weaker players exiting); demand_led if from end-demand volume.
- `lost_share_in_downturn`: only with evidence.
- `governance_flags`: auditor issues, related-party concerns, regulatory actions, delayed filings.

### 8.2 Pivot rubric
- `capability_proof` 0–5: 0 claims only; 1 capex announced or trial orders; 2 certifications or regulatory filings in place; 3 named customers, qualified supplier, recurring revenue; 4 scaled (material share, multiple customers, higher tier); 5 hard to replicate (top tier for years, sole or primary supplier).
- `management_track_record` 0–5: check guidance from 4–8 quarters back against what was delivered, ROCE through the last downturn, and past acquisitions or expansions. 0 repeated misses or governance issues; 3 generally delivers; 4 consistent delivery, invested ahead of the cycle and was right; 5 multi-cycle record, visible promoter passion.
- `external_tailwind` 0–5: 0 shrinking globally; 3 clear growth in global players' guidance; 4 multi-year growth with capacity shortages; 5 structural shortage with customers seeking new suppliers.
- `capability_built_vs_bought`: built / bought / mixed.
- Targets come from management guidance (record `target_source`). If none exists, a conservative estimate is allowed but must be labelled "Claude estimate".

### 8.3 Sector checklists (references/sector_checks.md)
- **Chemicals:** spreads, Chinese dumping, inventory gains in the first good quarter, specialty vs commodity labels.
- **Pipes/building materials:** easy-entry overcapacity, resin prices, government spending, unorganised players exiting when input costs spike (a supply shock, not yet a cycle).
- **Pharma/CDMO:** heavy capex phase, US FDA Drug Master File (DMF) filings as public proof, FDA inspections, innovator pipelines, peptides/ADCs.
- **Aerospace/defence:** supplier tiers, AS9100 and Nadcap certifications, OEM build rates; "aerospace" without certifications scores capability ≤ 1.
- **IT services:** outcome-based vs hours-based billing, domain specialisation, guidance vs sector, large caps re-rate late.
- **Auto ancillary:** non-auto mix and its margins.
- **Any sector:** name the 2–3 cycle variables and the public data that verifies management.

## 9. Output

**Markdown scorecard sections, in order:**
1. Title, as-of date, sector, price.
2. Stage with action and meaning (plus a pivot-lens note if on).
3. Supply/demand tag.
4. Table of both scores with coverage (Score 1 also shows pain and turning).
5. Price check.
6. Signal tables: pain; turning (mark "(fired)"); earnings delta line; pivot.
7. Build-phase note.
8. Vetoes and red flags, including late-cycle signals present.
9. Evidence (up to 8 lines).
10. What would change the score.
11. Point-in-time guard (excluded counts).
12. Disclaimer.

**JSON output** carries every computed value, including:
- `stage`, `score1_pessimism_roc`, `score1_level`, `score1_turn`, `score2_trajectory_pivot`, both coverages
- `turning_signals_fired`, `optimism_signals`, `supply_demand`, `valuation_percentile`, drawdown, off-low, EBITDA TTM YoY
- `pivot_lens`, `score2_judgment_share`, vetoes, `red_flags`, `build_phase`
- all signals, `evidence`, `what_would_change`, `excluded_future_data`

## 10. Screener importer

Read the "Data Sheet" tab. Match rows by the label in column A within sections (META, PROFIT &
LOSS, Quarters, BALANCE SHEET, CASH FLOW, PRICE, DERIVED), and read dates from "Report Date"
rows. Derive:
- EBITDA = PBT + interest + depreciation − other income (quarterly: use "Operating Profit" when present)
- capex = Δ(net block + CWIP) + depreciation
- equity = equity capital + reserves
- annual P/B and EV/EBITDA history from year-end prices × adjusted shares

Optional `--prices date,close` CSV for point-in-time prices. Output notes the approximations and
lists what is still needed (shareholding, trades, peers, concalls, segments). It has only been
tested on a mock file in Screener's layout, so verify it on a real export.

## 11. Default config

```json
{
  "score1_weights": {"level": 0.40, "turn": 0.45, "delta": 0.15},
  "level_weights": {"valuation": 0.30, "drawdown": 0.20, "earnings_stress": 0.20, "neglect": 0.15, "sector_breadth": 0.15},
  "turn_weights": {"promoter": 0.30, "sentiment_gap": 0.30, "margin_inflection": 0.25, "market_share": 0.15},
  "score2_weights": {"segment_shift": 0.20, "pivot_size": 0.20, "capability": 0.20, "management": 0.20,
                     "mispricing": 0.10, "tailwind": 0.10, "build_phase": 0.10},
  "segment_shift_split": {"mix": 0.6, "margin_diff": 0.4},
  "valuation_metric_preference": ["pb", "ev_ebitda", "pe"],
  "reporting_lag_days": {"quarter": 45, "annual": 60, "shareholding": 21, "event": 0},
  "thresholds": {
    "drawdown_full": 0.60, "earnings_stress_full": 0.40, "sector_breadth_dd": 0.40, "sector_breadth_full": 0.60,
    "min_peers": 3, "concall_short_min": 30, "concall_long_min": 90, "questions_few": 5, "questions_many": 20,
    "institutional_change_pp": 3.0, "promoter_window_days": 183, "promoter_holding_change_pp": 0.25,
    "inflection_min_rise": 0.01, "inflection_trough_below_avg": 0.10,
    "delta_full": 1.0, "delta_before_inflection": 0.5,
    "neglect_call_max_age_days": 200, "rally_off_low": 0.5,
    "credibility_one_miss": 0.75, "credibility_two_misses": 0.5, "market_skepticism_dd": 0.30,
    "acquisition_window_days": 455, "promoter_exit_flag_pp": 5.0,
    "mix_change_full_pp": 20, "mix_share_full_pct": 40, "margin_ratio_full": 1.8,
    "orbit_full": 3.0, "pivot_success_prob": 0.5, "mispricing_full_ratio": 0.4,
    "build_phase_capex_ratio": 1.5, "build_phase_full_ratio": 2.0, "judgment_heavy_share": 0.6,
    "veto_cap": 30, "veto_min_debt_to_equity": 0.5, "mgmt_gate_min": 2, "mgmt_gate_cap": 40, "low_coverage": 0.5,
    "peak_opt_val_pct": 80, "peak_opt_val_pct_alone": 90, "peak_opt_signals": 2,
    "confirmed_growth": 0.15, "confirmed_val_pct_min": 40,
    "early_val_pct_max": 50, "early_turn_signals": 2, "early_min_dd": 0.25, "early_min_off_low": 0.30,
    "peak_pess_val_pct": 25, "peak_pess_dd": 0.40,
    "pivot_lens_min": 60, "pivot_lens_shift_min": 60,
    "demand_led_volume_growth": 0.08, "supply_shock_max_volume_growth": 0.05,
    "supply_shock_min_realisation": 0.03, "inventory_gain_margin_jump": 0.04, "qip_window_days": 365
  }
}
```

## 12. Acceptance tests

### 12.1 Synthetic regression (invented numbers; all must PASS)
All cases use as_of 2026-05-20 and 12 quarters (Jun-2023 to Mar-2026) unless stated.

| Case | Setup | Expected |
|---|---|---|
| A peak pessimism | P/B 1.8 vs history 2.1–5.6; price 300, 3y high 620; margins falling 13%→6% with the latest quarter the trough; flat volume; no promoter trades; FII falling; calls 25–40 min with 4–9 questions, tone 2, skepticism 4–5; 4/5 peers ≥40% down | PEAK_PESSIMISM |
| B early recovery, supply shock | P/B 2.4 (≈20th percentile); price 420, high 620, low 280; margin trough 3 quarters back, up 2 quarters; volume flat while revenue rises (realisation +16%); promoter open-market buys ₹12 cr + ₹6 cr, holding rising; tone 3→4→5, skepticism 4, share-gain claims; plus one quarter and one call dated after as_of that must be excluded | EARLY_RECOVERY, Score 1 ≥ 60 |
| C peak optimism | P/B 11 above a history max of 10; near its high; margins rising; QIP 4 months ago; promoter sold ₹300 cr; 110–120 min calls, aggressive guidance | PEAK_OPTIMISM, Score 1 ≤ 50 |
| D value trap | P/B 0.8 (lowest); down 67%; CFO negative 3 years; debt rising; coverage < 2 (equity not given); pledge 40%; lost share | Score 1 ≤ 30 (vetoed); stage PEAK_PESSIMISM, DECLINE or MIXED |
| E pivot | New segment share 15%→36% over 12 quarters at 28% vs 12% EBIT margin; target ₹1,500 cr at 30%; capability 4, management 4, tailwind 4; EV/EBITDA 22 vs pure-play 45; capex spike | Score 2 ≥ 70 |
| F weak management | E with management 1 | Score 2 ≤ 40 |
| G thin data | Only price (100, high 220, low 95) and 4 P/B points | Runs without error, low coverage; PEAK_PESSIMISM or MIXED |
| H guidance misses | B with `prior_guidance_met: false` on the last two calls before as_of | Sentiment blocked, still EARLY_RECOVERY via the other 3 signals; Score 1 ≤ 80 |
| I no promoter | B with promoter holding 0 and no trades | Promoter signal N/A (not 20); EARLY_RECOVERY; Score 1 ≥ 75 |
| J promoter exit | B with promoter holding 60→50 over two quarters and no trades | Not EARLY_RECOVERY (PEAK_PESSIMISM or MIXED) |

### 12.2 Real backtests (inputs gathered from public sources; some fields derived)
| Case | Key inputs | Expected / observed |
|---|---|---|
| **Apollo Pipes, 5 Feb 2026** | Price ~₹267.5; 3y high ₹798.85 (9 Feb 2024); 52w low ₹252.8; P/B 1.45 vs history 1.37–5.48 (Feb 2024 onward); margins falling to 4.9%; Jan-2026 call tone 4, skepticism 4, share-gain claim, prior guidance missed; promoter buying came *after* (13 and 23 Feb) | EARLY_RECOVERY, Score 1 ≈ 54. Then ran to a high of ~₹670 |
| **Coforge, 5 May 2026** | No promoter group; price ₹1,168; 3y high ₹2,003.59; 52w low ₹1,008.1 (17 Mar 2026); P/E 25.2 vs history 10–82 (P/B unusable after the Encora share issue); May call tone 5, skepticism 2, guidance met, wallet-share claim | EARLY_RECOVERY via market skepticism, Score 1 ≈ 53. Then ran to ₹2,022 |
| **Clean Science, 18 Dec 2025** (value trap) | Price ₹891; 3y high ₹1,690; 52w low ₹873.55; P/B 6.68, the lowest ever; promoter holding 74.97%→50.97% in one quarter; Jul-2025 call tone 3, skepticism 3 (guidance cut); Nov-2025 call tone 2, guidance withdrawn | PEAK_PESSIMISM, Score 1 ≈ 38, promoter-exit red flag. Then fell to ₹652 |
| **Laurus Labs, 26 Apr 2024** (reference, no pass/fail) | Price ₹434.4; ATH ₹723.55; CDMO share 13% (FY20)→18% (FY24) after a COVID-contract spike to 36% in FY23; capex spike 1.6x; capability 3, management 3, tailwind 4; no point-in-time target or peer multiple | Score 2 ≈ 55, 62% judgment-driven (management 4 alone → 60). Then ~5x as CDMO reached 43% |

## 13. Why these rules exist (lessons from testing; keep them)
1. **Market skepticism.** Coforge's analysts were friendly, but the stock was down 42% while management beat guidance; the skepticism was in the price. Without this rule the signal missed a winner.
2. **Credibility discount.** Apollo's management missed its own guidance repeatedly. Skepticism is "anchoring" only if management delivers.
3. **Promoter-exit block.** Clean Science would have flipped to EARLY_RECOVERY on one upbeat call despite a 24-point promoter sale. Insider selling at the lows contradicts a turn.
4. **Promoter N/A.** Professionally managed companies (no promoter) were being scored as "no buying".
5. **Earnings delta halved before inflection.** Otherwise a deeper margin collapse raises the score while margins are still falling.
6. **Inflection needs a real trough** (10%+ below the cycle-average margin). A steady uptrend is not a turn from pain.
7. **Neglect fallback and rally rule.** Missing call data should not default to "max neglect", and institutions selling into a rally (or being diluted by a share issue) is not neglect.
8. **Coverage veto needs leverage.** Apollo's near-zero EBIT came from depreciation on a balance sheet with debt at 0.15x equity: an earnings problem, not solvency.
9. **Acquisition flag uses the closing date** and fires only once the deal is in reported quarters.
10. **Pivot lens keyed to proof of pivot, not total Score 2.** A re-rated pivot loses its mispricing and build-phase points; keying on total Score 2 switched its own lens off and called Laurus "peak optimism".
11. **MIXED must explain itself.** The user needs the blocking rule.

## 14. Known limitations (state them to users when relevant)
- Calibrated on 3 real cases chosen in hindsight, plus 1 reference; that is calibration, not validation. Add more value traps before trusting the weights.
- Own-history valuation misleads when the history is short or mostly one phase of the cycle (Apollo's history covered only the downturn).
- Score 2 is a credibility check more than a timing signal. With thin segment, target or peer data it rests mostly on rubric judgments. Pivot size understates big pivots when segment margins are undisclosed (the formula holds the base flat).
- The vetoes (debt, cash burn, pledge, governance) have only fired on synthetic data so far.
- Rubric scores drift by about a point between readings.
- Data is often partial: transcripts behind bot-blocking, Screener pages dropping columns, no point-in-time peer multiples.
