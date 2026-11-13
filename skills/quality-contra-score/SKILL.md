---
name: quality-contra-score
description: >
  Score an Indian listed non-financial stock 0-100 with a deterministic, verifiable "quality contra"
  formula derived from a Money Talks (Groww) podcast with Parag Thakkar (built ICICI Pru Contra Fund,
  now Fort Capital). Philosophy: buy GOOD companies in BAD times - never compromise on management or
  balance sheet (net debt/EBITDA <= 3.5, ~15% 10y ROCE, real operating cash flow), then buy only when a
  temporary market/sector/company problem makes the price attractive; contra is NOT just cheap.
  Outputs total score, Quality (60) vs Setup (35) quadrant, gates, evidence coverage, verdict,
  P/E-based buy zone, max portfolio weight (10-12% ceiling, 3% for cyclicals/disruption) and a
  hold-for-the-full-ride / thesis-break plan. Trigger on: "quality contra score", "contra score",
  "Parag Thakkar framework", "good company in bad times", "is this a contra buy", "is this a value trap",
  "3.5 debt rule", "should I buy this fallen blue chip", "falling knife on a quality stock",
  "buyback above market price signal", "should I sell after this gain".
metadata:
  version: "1.0"
  source: "Money Talks by Groww - Parag Thakkar interview transcript (~1h01m)"
---

# Quality Contra Score (QCS)

A repeatable score for "good company, bad time". Inputs are gathered **with sources**;
`scripts/score.py` turns them into a number. Same inputs always give the same score. Not investment advice.

## 1. Principles extracted from the transcript

| # | Principle (timestamp) | Scored in |
|---|---|---|
| 1 | **Never compromise on management or balance sheet** (2:37-2:55) | P1-P3 = Quality (60) |
| 2 | **Net debt/EBITDA > 3.5 → don't invest** ("earn 100, owe > 350"); this rule saved many mistakes (3:00-3:35) | Gate + P2 |
| 3 | **Operating cash flow must be real**, checkable on Screener (3:35-3:51) | Gate (5y CFO > 0) + P1 CFO/PAT |
| 4 | **10y average ROCE ~15%** (3:51, 20:57) | P1 roce_10y, consistency |
| 5 | **Moat via technology or brand** (20:57-21:09) | P1 moat |
| 6 | **Three kinds of temporary fall:** market-wide (rates, war), sector (IT, metals), company-specific (Sun Pharma governance) (4:01-5:06) | P4 fall_cause |
| 7 | **Contra ≠ cheap.** 5 P/E or < 1x book is not contra; a good company with no structural issue, down for a transient reason (crude up → Pidilite/Asian Paints) is ("quality contra") (5:12-6:38) | Quadrant: Quality ≥ 42 **and** Setup ≥ 20 |
| 8 | **Good management overcomes crises** - JSW Steel ran through the iron-ore ban (25x in 13y); Bharti survived Jio; trial by fire (7:01-8:42, 13:46-14:28) | P3 trial_by_fire |
| 9 | **Tried-and-tested groups/MNCs** (Tata, JSW, Birla, Bajaj, Mahindra, HUL) (8:47-9:26, 29:38) | P3 governance_pedigree, P2 deep_pockets |
| 10 | **Get paid to wait** - ITC ~5% dividend; TCS 6% dividend, 7.5% FCF yield (9:39, 16:59) | P5 yield_support |
| 11 | **Cash returned via dividends/buybacks**; Bajaj keeps ~15,000 cr cash (11:29-11:37, 44:58) | P3 payout, capital_allocation; P2 net cash |
| 12 | **A correction turns ~15% compounding into 20-25%**; Nifty earnings ~12% is the baseline (12:33-12:56, 19:04) | P5 expected_return (bands 12/15/20%) |
| 13 | **Management change can be the catalyst** - ICICI Bank under Bakshi, Tata Consumer under Chandra (14:44-16:01, 22:17-23:16) | P4 temporariness `positive_catalyst_emerging` |
| 14 | **Good news and good price never come together** - attractive price arrives with negative news (19:23-20:04) | P4 bad_news_flow, relative_underperformance |
| 15 | **Recency trap: 5 years of zero returns while profits grew = de-rating, not deterioration** (27:13-28:11) | P4 derating_vs_earnings (price CAGR − EPS CAGR) |
| 16 | **Buy the best company in the most-hit sector** - IHCL after the vaccine news, Maruti in demonetisation, M&M if the monsoon fails (24:44-30:15) | P4 fall_cause + temporariness |
| 17 | **Position sizing** - however bullish, ≤ 10-12%; cyclical/commodity 2-3%; add as confidence builds; stagger buying (17:50-18:29, 26:12, 1:00:31-1:00:52) | max_weight, tranche plan |
| 18 | **Don't fight technology disruption** - calibrated weight only (38:48-39:30) | P6 + weight cap + STRUCTURAL flag |
| 19 | **Promoter puts own money in** - Birla rights issues in the GFC; buyback above market with promoter not tendering (Bajaj 4,600 vs 3,800 → 11,000) (40:33-45:34) | P3 insider_signals, P2 deep_pockets, INSIDER CONTRA flag |
| 20 | **Avoid the crowd** - leveraged single-stock funds, silver euphoria, FOMO (41:57-42:36, 56:57-58:23) | CROWDED/FOMO flag |
| 21 | **Group-extension listings** - JSW Infra IPO: known group, 6% cash-flow yield, zero debt, 19-20% ROCE (47:52-50:34) | GROUP-EXTENSION flag |
| 22 | **Biggest mistake: selling too early - take the full ride** (Titan, MRF, IHCL 75 → 720) (23:25-24:44, 30:23-34:01, 50:55-51:23) | Plan: no sell on gains; sell on thesis break only |
| 23 | **If the thesis is not playing out, surrender** - cut on a bounce to a manageable weight (59:46-1:00:23) | Plan: 6-quarter review |
| 24 | **No leverage; only surplus money** (46:48-47:29) | Report disclaimer |

## 2. Gates (any FAIL ⇒ REJECT)

| Gate | Input | Fails when |
|---|---|---|
| Debt rule | `net_debt_to_ebitda` | > 3.5 (EBITDA ≤ 0 is recorded as 99) |
| Cash generation | `cfo_5y_cumulative_cr` | ≤ 0 |
| Fraud | `proven_fraud_or_fund_diversion` (bool) | proven fraud / fund diversion by promoters or KMP. An *allegation* that the business can survive (Sun Pharma) is a `company_specific_fixable` fall, not a gate fail |
| Auditor | `auditor_red_flag_3y` (bool) | qualified opinion, or resignation citing concerns, last 3y |

An unverified gate or < 100% coverage prefixes the verdict with `PROVISIONAL`.
`business_type` must be `non_financial`; banks/NBFCs/insurers are out of scope.

## 3. Formula (100 points)

$$\text{QCS} = \underbrace{P1_{25} + P2_{15} + P3_{20}}_{\text{Quality }(60)} + \underbrace{P4_{20} + P5_{15}}_{\text{Setup }(35)} + P6_{5}$$

### P1 Business Quality (25)
| Metric | Input | Points |
|---|---|---|
| roce_10y (8) | `roce_10y_avg_pct` | ≥20→8, ≥15→6, ≥12→3, ≥10→1 |
| roce_consistency (3) | `roce_pct_years_ge_15` | ≥80→3, ≥60→2, ≥40→1 |
| cfo_conversion (6) | `cfo_to_pat_10y` (Σ CFO ÷ Σ PAT) | ≥0.9→6, ≥0.75→4, ≥0.5→2 |
| cfo_consistency (2) | `cfo_positive_years_pct` | ≥90→2, ≥70→1 |
| moat (6) | `moat_evidence` ⊆ {`brand_leader_top3_share`, `lowest_cost_producer`, `technology_or_product_leadership`, `distribution_or_network_scale`, `pricing_power_passed_cost_inflation`, `regulatory_licence_or_scarce_asset`} | 1→2, 2→4, ≥3→6 |

### P2 Balance Sheet Strength (15)
| Metric | Input | Points |
|---|---|---|
| net_debt_to_ebitda (8) | (borrowings − leases − cash equivalents) ÷ operating profit | ≤0→8, ≤1→6, ≤2→4, ≤3.5→1 |
| interest_coverage (3) | (PBT + interest) ÷ interest | ≥10→3, ≥5→2, ≥3→1 |
| deep_pockets (4) | `funding_backstop` ⊆ {`net_cash_ge_5pct_of_mcap`, `promoter_or_parent_infused_capital_in_past_crisis`, `strong_group_parent`, `credit_rating_aa_or_better`} | 1 each |

### P3 Management DNA & Alignment (20)
| Metric | Input | Points |
|---|---|---|
| governance_pedigree (4) | `tried_tested_group_or_mnc` / `clean_promoter_record_10y` / `professional_board_clean_record` / `limited_record` | 4 / 3 / 2 / 0 |
| trial_by_fire (6) | `crisis_evidence` ⊆ {`operated_through_major_shock`, `market_share_held_or_gained_in_downturn`, `cost_reset_then_recovery`, `profit_regained_prior_peak_within_3y`, `no_distress_dilution_or_asset_sale`} | 1→2, 2→4, ≥3→6 |
| dividend_payout (2) | `dividend_payout_5y_avg_pct` | ≥40→2, ≥20→1 |
| capital_allocation (3) | `capital_allocation_evidence` ⊆ {`buyback_or_special_dividend_5y`, `capex_funded_internally`, `no_value_destroying_acquisition_5y`} | 1 each |
| insider_signals (3) | `insider_signals` ⊆ {`promoter_open_market_buy_24m`, `promoter_subscribed_rights_or_preferential_24m`, `buyback_promoter_not_tendering_24m`, `buyback_price_ge_15pct_above_market_24m`} | 1→2, ≥2→3 |
| promoter_alignment (2) | `promoter_holding_change_3y_pp`, `promoter_pledge_pct` | change ≥ −0.5pp and pledge 0 → 2; change ≥ −2pp and pledge ≤ 5 → 1; professionally managed → 1 |

### P4 Contra Setup - Temporary Pain (20)
| Metric | Input | Points |
|---|---|---|
| drawdown (5) | `drawdown_from_3y_high_pct` | ≥40→5, ≥25→4, ≥15→2 |
| derating_vs_earnings (4) | `price_cagr_5y_pct` − `eps_cagr_5y_pct` | ≤−10→4, ≤−5→3, ≤0→1 |
| fall_cause (4) | `market_wide_macro` / `input_cost_or_commodity` / `sector_temporary` → 4; `company_specific_fixable` / `prolonged_neglect` → 3; `no_fall` / `unknown` / `structural_disruption` → 0 | |
| temporariness (3) | `temporariness_evidence` ⊆ {`revenue_or_volume_base_intact`, `management_corrective_actions_announced`, `precedent_of_recovery`, `trigger_reversing_or_time_bound`, `positive_catalyst_emerging`} | 1 each, max 3 |
| relative_underperformance (2) | `rel_return_12m_vs_nifty_pp` | ≤−20→2, ≤−10→1 |
| bad_news_flow (2) | `sentiment_evidence` ⊆ {`institutions_cut_ge_1pp_4q`, `broker_downgrades_or_target_cuts_6m`, `negative_media_or_sector_out_of_favour`, `earnings_estimates_cut_6m`} | 1 each, max 2 |

### P5 Valuation & Yield Support (15)
| Metric | Input | Points |
|---|---|---|
| pe_vs_own_10y (5) | `pe_percentile_10y` | ≤20→5, ≤40→3, ≤60→1 |
| yield_support (5) | max(`dividend_yield_pct`, `fcf_yield_pct`) | ≥5→5, ≥3.5→4, ≥2.5→2, ≥1.5→1 |
| expected_return (5) | $r = \big((1+g)^3 \cdot \text{clip}(\tfrac{PE_{med,10y}}{PE}, 0.67, 1.5)\big)^{1/3} - 1 + \text{div yield}$, $g$ = 5y EPS CAGR clipped to 0-20% | ≥20→5, ≥15→3, ≥12→1 |

### P6 Disruption Risk (5)
| `disruption_risk` | low → 5, moderate → 3, high → 0 |
|---|---|

## 4. Quadrant, verdict, weight, flags, plan

- **Quadrant:** Quality (P1+P2+P3) ≥ 42/60 and Setup (P4+P5) ≥ 20/35 → `QUALITY CONTRA`; quality only → `QUALITY, NO CONTRA PRICE`; setup only → `CHEAP, NOT QUALITY`; else `NEITHER`. A missing metric is never read as a weak one: if an axis is below its bar but its unscored metrics could still lift it over, it is `UNPROVEN` and the verdict becomes `INCOMPLETE - research <metrics>` (unless Setup has already failed, which makes it a PASS regardless).
- **Evidence coverage** = metrics scored `ok` ÷ 24. Missing/unsourced/invalid inputs score 0. An empty list with a source means "checked, none found".
- **Verdict:** gate FAIL → `REJECT`; coverage < 80% → `INCOMPLETE`; QUALITY CONTRA with total ≥ 70 → `ACCUMULATE IN TRANCHES`, else `STARTER POSITION`; quality only → `WATCHLIST`; cheap only → `AVOID - value-trap risk`; neither → `PASS`.
- **Max weight:** accumulate 10%, starter 5%, others 0 (ceiling 12%). `cyclicality = cyclical_commodity` or `disruption_risk = high` → 3%; moderate disruption → 6%.
- **Buy zone:** price × (10y 40th-percentile P/E ÷ current P/E); strong zone uses the 20th percentile.
- **Flags:** `CROWDED/FOMO` (P/E ≥ 80th pct and ≥ 25% above 200DMA), `STRUCTURAL/DISRUPTION`, `NEAR DEBT LIMIT` (2.5-3.5), `VALUE TRAP RISK`, `PATIENCE TEST` (moderate disruption, prolonged neglect, or cyclical), `GROUP-EXTENSION LISTING`, `INSIDER CONTRA` (quality + buyback ≥ 15% above market + promoter not tendering).
- **Plan:** 3 tranches; hold for the full ride (no selling on a 20-40% gain); sell only on thesis break (net debt/EBITDA > 3.5, 5y CFO ≤ 0, ROCE < 12% two years running, governance gate fails, cause proves structural); quarterly thesis review, cut to 2-3% on a bounce if the cause has not started reversing after 6 quarters. Optional `position_cost_price`, `portfolio_weight_pct`, `holding_months` make it numeric.

Thresholds for weights, buy zone, the 6-quarter review and the 2.5 "near limit" are operationalised from the transcript, which gives no exact numbers for them.

## 5. Workflow

1. **Pre-fill numbers** (Screener.in + Yahoo; every value carries a re-checkable source):
   *(from repo root)*
   ```
   python skills/quality-contra-score/scripts/fetch.py ITC -o itc.fetched.json
   python skills/quality-contra-score/scripts/fetch.py BAJAJ-AUTO --standalone -o bajaj.fetched.json            # consolidation holds a captive NBFC
   python skills/quality-contra-score/scripts/fetch.py BAJAJ-AUTO --standalone --as-of 2022-06-30 -o b22.json    # point-in-time back-test
   ```
   Fills ROCE (10y), CFO/PAT, CFO-positive years, 5y CFO, net debt/EBITDA, interest cover, payout, EPS and price 5y CAGR, 3y drawdown, 12m vs Nifty, 200DMA, dividend/FCF yield, P/E with 10y percentile/median/p20/p40, promoter holding/pledge and institutional 4-quarter change (today only). It warns when consolidated borrowings dwarf standalone (rerun with `--standalone` only if the subsidiary is a lender) and leaves P/E empty for loss-making periods.
2. **Diagnose the fall** (the core of the method): what fell - market, sector or company? Why is it temporary? What bad news is in the price? Cite each item (filing, concall timestamp, article + date).
3. **Judge management** on record, not words: crisis episodes, rights issues/promoter buying, buybacks vs market price, payout history.
4. **Check gates** in the auditor's report/CARO, exchange filings and SEBI orders.
5. **Write the analyst file** (copy `templates/input-template.json` outside the skill folder; nulls never overwrite fetched values). Never invent a value; leave it null. Mark anything not directly evidenced `AGENT ASSESSMENT (unverified)`.
6. **Score:**
   ```
   python skills/quality-contra-score/scripts/score.py itc.fetched.json itc.analyst.json [position.json] [--json]
   ```
7. **Report:** total, quadrant (Quality/Setup), verdict, coverage, gates, per-pillar table with sources, flags, buy zone, max weight, plan, evidence gaps ranked by points at stake, a 3-5 line thesis (why it's good, why it fell, why the fall is temporary, what would prove it structural), and a not-investment-advice note (no leverage; surplus money only).
8. **Re-score** every quarter and after any > 20% move.

## 6. Verification on every non-financial stock in the video (run 2026-11-12)

`python examples/video-stocks/verify.py` (add `--refresh` to re-fetch) scores 35 cases, checks the guest's price claims and measures back-test forward returns vs Nifty; output in `verification.json`. Qualitative inputs: `<case>.analyst.json` or `more-analyst.json` (transcript timestamps; `AGENT ASSESSMENT` = unverified; null = not researched). Fraud/auditor gates not checked (hence `~`/PROVISIONAL). `Qm/32` and `Sm/26` are the purely fetched (fully reproducible) parts of Quality and Setup.

**Price claims** match fetched closes: ITC 285 vs "280", Bajaj 11,040 vs "11,000", Bajaj Jun-22 3,625 vs "3,800", TVS 480 vs "500", Hindalco 962 vs "950", Tata Consumer 1,093 vs "1,100", NTPC 327 vs "350", NTPC Jun-21 117 vs "120-140", Trent Jun-22 1,074 vs "1,200". Mismatches: IHCL Nov-20 105 vs "75" (75 was the earlier COVID low); Tata Motors Nov-20 151 vs "45" (unexplained; post-2025 demerger symbol TMPV).

**Live calls (today):**

| Case | QCS | Q | S | Verdict | Reading |
|---|---|---|---|---|---|
| TCS | 78 | 44 | 31 | QUALITY CONTRA (cap 6%) | P/E 4th pct, FCF yield 5.1%, −46% |
| ITC | 77 | 43 | 29 | QUALITY CONTRA | 5.1% yield, −43%, tax shock |
| HUL | 72 | 43 | 24 | QUALITY CONTRA | price CAGR −3.4% vs EPS +13.5%, P/E 5th pct - the guest's "recency trap" (27:13) |
| Infosys | 76 | 41 | 32 | INCOMPLETE - quality unproven | 1 point short; crisis/insider/backstop not researched |
| Bajaj Auto | 60 | 50 | 7 | WATCHLIST | already moved |
| Asian Paints / Pidilite / Maruti / M&M / Sun / TVS / Titan / MRF / JSW Steel / TechM / IHCL / Tata Consumer / Hindalco / JSW Infra | 32-61 | | ≤ 17 | PASS | no contra price today |
| NTPC, Power Grid | 33 | | | REJECT | net debt/EBITDA 4.7 / 4.2 |

**Back-tests near the guest's entry (forward return to 2026-11-12):**

| Case | QCS | Verdict | Stock vs Nifty | Framework right? |
|---|---|---|---|---|
| Asian Paints Jun-22 | 50 | not contra (P/E 86th pct, Setup 6) | 0.95x vs 1.60x | **Yes** - avoided |
| Pidilite Jun-22 | 49 | not contra (P/E 91st pct, Setup 6) | 1.51x vs 1.60x | **Yes** - avoided |
| Tata Motors Nov-20 | 27 | REJECT (ND/EBITDA 4.7) | 2.05x vs 2.00x | Neutral (demerger understates) |
| Bajaj Auto Jun-22 | 62 | WATCHLIST + INSIDER CONTRA flag | 2.98x vs 1.60x | Partial - only the flag caught it |
| NTPC Jun-21 | 47 | REJECT (ND/EBITDA 6.0) | 2.81x vs 1.61x | **No** - the guest's own 3.5 rule rejects his NTPC call |
| Trent Jun-22 | 29 | PASS (P/E 346) | 3.00x vs 1.60x | No - but it was a growth buy, not a contra |
| TVS Motor Sep-20 | 48 | PASS (P/E 99th pct) | 9.74x vs 2.25x | No - guest: "a bit expensive... not my style" (21:51) |
| Hindalco Jun-20 | 53 | AVOID - value trap (10y ROCE 8%) | 6.58x vs 2.45x | **No** |
| IHCL Nov-20 | 37 | INCOMPLETE (loss-making, ROCE 5.8%) | 7.92x vs 2.00x | **No** |
| Motherson Nov-20 | 45 | INCOMPLETE (67%) | 4.88x vs 2.00x | Not scorable |
| JSW Infra Oct-23 | 26 | INCOMPLETE (no P/E history at listing) | 2.04x vs 1.32x | Not scorable; GROUP-EXTENSION flag fired |

**What verification shows:** the formula faithfully encodes the guest's *stated* rules and correctly avoids expensive "quality" names (paints/adhesives 2022). His biggest COVID-era winners (IHCL, Hindalco, TVS, Motherson) were cyclical/catalyst recoveries in lower-ROCE or expensive businesses bought at crisis lows - they break his own quality filter, so a rule-based score cannot reproduce them. Treat such bets outside QCS, small-sized.

Known weaknesses:
- **Trailing P/E on trough earnings** (Bajaj 2022) makes a cheap stock look expensive. When `INSIDER CONTRA` fires, re-check P/E on normalised (3y average) EPS manually.
- **Regulated utilities** (NTPC, Power Grid) carry > 3.5x net debt/EBITDA by design and always fail the debt gate.
- **Crisis-recovery/catalyst buys** (IHCL, Hindalco 2020, Tata Consumer 2019, ICICI under Bakshi) fail the quality filter; the guest bought them on group + brand + catalyst.
- Screener's free pages hold ~12 fiscal years, so entries before mid-2020 (Tata Consumer 2019, JSW Steel 2012, Sun Pharma) cannot be back-tested; loss-making years leave P/E empty.
- Net debt excludes investments (conservative); evidence `net_cash_ge_5pct_of_mcap` separately.
- Shareholding is only available for recent quarters; back-tests miss `promoter_alignment`.
- Lenders (ICICI Bank, HDFC Bank, Bajaj Finance, Chola - all in the transcript) are out of scope.

## 7. Limitations

- Bands are calibrated for Indian large/mid caps in ₹ crore.
- The score ranks candidates; it does not time the bottom or predict returns. Not investment advice.
