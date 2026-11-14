---
name: surprise-dot-connect-score
description: >
  Score an Indian listed stock 0-100 with a deterministic, verifiable formula derived from a
  "Conversation with Kushal" podcast guest (Gandhinagar-based ex-Gujarat-government IT officer;
  multibaggers Haren Drugs/Matrix 200x, Caplin Point ~90x, Frontier Springs ~300x,
  Transformers & Rectifiers, Shilchar, Jyoti Resins, Jubilant demergers). Framework:
  spot a SURPRISE in an under-covered stock, CONNECT DOTS from news to the value chain (buy the
  ancillary before the end product), then test addressable market, promoter skill & integrity,
  and valuation. Outputs score, evidence coverage, gates, verdict, certainty bucket and an exit
  plan (hold compounders; recover capital and trim uncertain bets). Trigger on: "surprise score",
  "dot-connect score", "ancillary play", "score this stock with the Kushal podcast framework",
  "value-chain beneficiary", "is this a Caplin/Frontier-type stock", "when should I book profit".
metadata:
  version: "1.0"
  source: "Conversation with Kushal podcast transcript (Hindi, ~1h21m)"
---

# Surprise & Dot-Connect Score (SDS)

A repeatable stock-picking score. Inputs are gathered **with sources**; `scripts/score.py` turns
them into a number. The same inputs always give the same score. Not investment advice.

## 1. Principles extracted from the transcript

| # | Principle (timestamp) | Scored in |
|---|---|---|
| 1 | **Look for surprises, not consensus** – large caps are tracked by many funds, so news is priced instantly; small stocks hide unusual events (2:33–3:19) | P1 triggers, institutional neglect |
| 2 | **An acquirer paying above market is a signal** – Haren Drugs: market ₹13, new promoter paid ₹20, then successive open offers at 100, 300 → 3,000 (3:25–8:28) | trigger `acquirer_paid_premium_to_market`, `successive_open_offers_or_buybacks_higher` |
| 3 | **Read balance-sheet anomalies** – Caplin's current liabilities rose QoQ = customer advances for a blockbuster sildenafil product in LatAm (10:13–13:56) | trigger `customer_advances_surge`; P3 working capital |
| 4 | **A life high on volume means someone knows more – pay up, don't wait for a 20% dip** (10:37–14:31) | P1 price near high + volume |
| 5 | **Read broadly, connect dots** – daily Business Standard; any change in regulation, sector, product → where does the impact land? (8:53–10:13) | P1 `policy_change_beneficiary`; P2 theme |
| 6 | **Ancillary before end product** – tyres are paid before the car sells, carbon black before tyres; ancillary gains volume whichever OEM wins (23:44–25:15) | P2 `value_chain_position` |
| 7 | **Few approved vendors = duopoly/oligopoly** – Frontier Springs: 3 approved vendors, 1 listed; railways vendor approval → trial → field trial → commercial order (26:27, 31:17–32:14) | P2 oligopoly; trigger `first_order_after_vendor_approval` |
| 8 | **Replacement + new demand** – spring life ~5 years (26:14); younger buyers replace furniture faster (1:01:26) | P2 theme `replacement_or_repeat_demand` |
| 9 | **Import substitution** – imported air spring ~4x cost, Make in India priority (32:21) | P2 theme `local_preference_or_import_substitution` |
| 10 | **Lead-time compression pulls demand forward** – thermal plant 4 years vs solar 6 months → transformer demand surge (41:56–45:50) | P2 theme `lead_time_compression` |
| 11 | **Pricing-power inflection before the market notices** – T&R's COO: "we stopped undercutting BHEL" (46:34–47:23); ₹25 → ₹1,300 in 2.5 years | trigger `pricing_power_shift` |
| 12 | **Look at market cap, not share price** – Frontier at ₹6 cr mcap; Terasoft 250 cr mcap vs 3,000 cr order (26:43, 47:39, 1:13:47) | P2 opportunity/mcap; P5 size headroom |
| 13 | **Negative working capital, debt-free, spare capacity = operating leverage** – Caplin advances; Jyoti 50% spare capacity, no capex, no ad spend (15:03, 59:02) | P3 |
| 14 | **Walk the talk** – Caplin MD: "top line becomes bottom line every 6 years" (17:43) | P4 walk_the_talk |
| 15 | **Promoter integrity signals** – never sold, no market operations; high salary but disclosed; 15–20y worker tenure; unchanged company secretary; focused on business, not stock (28:04–33:00, 55:40) | P4 promoter alignment, stability |
| 16 | **Ground truth** – carpenter's 15-year guarantee (54:58), third-party railway inspector "no technical rejection" (29:06), AGM + factory visit, electricity-board officers (45:57), brand boards seen on the road (1:02:31) | P4 scuttlebutt; trigger `unknown_brand_preferred_by_users` |
| 17 | **Hidden value unlocks** – Jubilant demergers; NCLT asset bought cheap (Sarda Energy) (1:02:53–1:06:31) | triggers `demerger_or_hidden_asset_unlock`, `distressed_asset_bought_cheap` |
| 18 | **Framework = addressable market + promoter skill & integrity + (now more weight on) valuation** (1:15:38–1:15:54) | P2, P4, P5 weights |
| 19 | **AI threatens labour-arbitrage services; big elephants can't pivot; agile niche tech and physical goods benefit** (1:08:10–1:16:28) | P6 ai_exposure; ELEPHANT flag |
| 20 | **Avoid regulated-market patent risk** – Caplin chose registration markets (15:56–16:19) | P6 durability |
| 21 | **Exit discipline** – high-certainty compounders: hold through dips (tax + re-entry cost); uncertain/turnaround bets: pull capital out first; exceptional short-term gains melt like ice cream; don't catch falling knives (36:22–40:53) | certainty bucket, exit plan, FALLING KNIFE flag |

## 2. Gates (any FAIL ⇒ REJECT)

| Gate | Input | Fails when |
|---|---|---|
| Auditor | `auditor_red_flag_3y` (bool) | qualified opinion, or auditor resigned citing concerns, last 3y |
| Regulatory | `regulatory_action_against_promoters_or_kmp_3y` (bool) | SEBI/ED/fraud order against promoters or KMP |
| Related party | `related_party_red_flag_3y` (bool) | loans/advances to promoter entities, or RPTs > 10% of revenue |
| Pledge | `promoter_pledge_pct` | > 25% |

An unverified gate caps the verdict at `PROVISIONAL HIGH CONVICTION`.

## 3. Formula (100 points)

$$\text{SDS} = P1_{15} + P2_{20} + P3_{15} + P4_{25} + P5_{15} + P6_{10}$$

### P1 Surprise Trigger & Information Edge (15)
| Metric | Input | Points |
|---|---|---|
| surprise_triggers (7) | `trigger_events` ⊆ {`acquirer_paid_premium_to_market`, `successive_open_offers_or_buybacks_higher`, `customer_advances_surge` (advances/current liabilities up ≥ 50% YoY with revenue up), `blockbuster_product_or_approval`, `first_order_after_vendor_approval`, `pricing_power_shift` (management says pricing restored / OPM +300bp), `large_order_vs_mcap` (single order ≥ 1x mcap), `demerger_or_hidden_asset_unlock`, `distressed_asset_bought_cheap`, `policy_change_beneficiary`, `unknown_brand_preferred_by_users`} — each dated within 24 months | 0→0, 1→4, 2→6, ≥3→7 |
| institutional_neglect (4) | `institutional_holding_pct` (FII + DII) | ≤5→4, ≤10→3, ≤20→1 |
| price_near_high (2) | `pct_below_52w_high` | ≤5→2, ≤15→1 |
| volume_confirmation (2) | `volume_ratio_10d_vs_50d` | ≥2→2, ≥1.3→1 |

### P2 Opportunity & Value-Chain Position (20)
| Metric | Input | Points |
|---|---|---|
| theme_evidence (5) | `theme_evidence` ⊆ {`sector_capex_budget_up_ge_15pct`, `industry_capacity_target_documented`, `lead_time_compression`, `supply_shortage_or_backlog`, `local_preference_or_import_substitution`, `replacement_or_repeat_demand`} | 1 each, max 5 |
| value_chain_position (5) | `essential_component_multi_customer` / `niche_end_product_or_channel_edge` / `single_customer_dependent` / `commodity_price_taker` | 5 / 3 / 1 / 0 |
| oligopoly (5) | `players_in_niche` (credible or approved players incl. company) | ≤3→5, ≤6→3 |
| opportunity_vs_mcap (5) | `order_book_or_addressable_revenue_cr` ÷ `market_cap_cr` | ≥3→5, ≥1→3, ≥0.5→1 |

### P3 Business Model & Operating Leverage (15)
| Metric | Input | Points |
|---|---|---|
| working_capital (4) | `cash_conversion_cycle_days` | ≤0→4, ≤60→3, ≤120→1 |
| margin_expansion (3) | `opm_change_3y_pp` | ≥5→3, ≥2→2, ≥0→1 |
| spare_capacity (2) | `spare_capacity_pct` (from concall/AR) | ≥30→2, ≥15→1 |
| sales_growth (3) | `sales_cagr_3y_pct` | ≥25→3, ≥15→2, ≥10→1 |
| roce (3) | `roce_3y_avg_pct` | ≥25→3, ≥15→2, ≥10→1 |

### P4 Promoter Skill & Integrity (25)
| Metric | Input | Points |
|---|---|---|
| walk_the_talk (6) | `guidance_hit_pct` = % of explicit targets met (show the windows), or `"none_stated"` | ≥80→6, ≥50→3, none stated→2 |
| debt_prudence (4) | `debt_to_equity` (ex-leases) | ≤0.1→4, ≤0.5→2, ≤1→1 |
| promoter_alignment (5) | `promoter_holding_pct`, `promoter_holding_change_3y_pp`, `promoter_pledge_pct` | pledge > 0 or change < −2pp → 0; change ≥ −0.5pp: holding ≥50→5, ≥35→3, else 2; otherwise 1; professionally managed → 2 |
| stability (4) | `stability_checks` ⊆ {`cfo_or_cs_tenure_ge_5y`, `no_kmp_or_auditor_exit_3y`, `long_tenured_workforce_evidence`, `promoter_no_market_operations`} | 1 each |
| scuttlebutt (6) | `scuttlebutt_checks` ⊆ {`end_user_or_channel_feedback`, `quality_feedback_customer_or_inspector`, `factory_or_office_visit`, `agm_or_management_meeting`, `industry_expert_or_regulator_feedback`, `product_seen_in_market`} | 1 each |

### P5 Valuation & Headroom (15)
| Metric | Input | Points |
|---|---|---|
| size_headroom (4) | `market_cap_cr` | ≤500→4, ≤2,000→3, ≤10,000→1 |
| growth_adjusted_pe (6) | PEG = `pe` ÷ min(`eps_cagr_3y_pct`, 50) | ≤0.8→6, ≤1.2→4, ≤2→2 |
| pe_vs_own_history (5) | `multiple_percentile_vs_own_history` (P/E percentile in own 5y range) | ≤25→5, ≤50→3, ≤75→1 |

### P6 Disruption & Durability (10)
| Metric | Input | Points |
|---|---|---|
| ai_exposure (5) | `physical_goods_or_infra` / `agile_niche_tech_beneficiary` / `mixed` / `labour_arbitrage_services` | 5 / 4 / 2 / 0 |
| durability (5) | `durability_checks` ⊆ {`core_business_unchanged_5y`, `avoids_patent_litigation_markets`, `no_single_product_gt_70pct`, `net_worth_cagr_ge_15pct_3y`, `export_or_customer_diversified`} | 1 each |

## 4. Verdict, certainty, flags, exit plan

- **Evidence coverage** = metrics scored `ok` ÷ 23. Missing, unsourced or invalid inputs score 0. An empty list with a source means "checked, none found" (0 points, counted as covered).
- **Verdict:** gate FAIL → `REJECT`; coverage < 80% → `INCOMPLETE`; ≥75 → `HIGH CONVICTION` (100% coverage and all gates pass, else `PROVISIONAL`); 60–74 → `STARTER POSITION`; 45–59 → `WATCHLIST`; < 45 → `PASS`.
- **Certainty** (`thesis_type` ∈ compounder / turnaround / special_situation / cyclical): `HIGH CERTAINTY` only if compounder **and** P4 ≥ 18 **and** P3 ≥ 9 **and** durability ≥ 3 **and** debt_prudence ≥ 2. Everything else is `UNCERTAIN`.
- **Flags:** `FALLING KNIFE` (≥ 40% below 52-week high and below 200DMA; a "re-score before adding" warning, not a sell signal), `SURPRISE WITHOUT SUBSTANCE` (P1 ≥ 11, P4 < 12), `FANCY/HYPE RISK` (P5 ≤ 3 and within 5% of 52w high), `ELEPHANT` (mcap > 1 lakh cr), `AI SERVICES RISK`.
- **Exit plan** (thresholds are operationalised from the transcript, which gives no exact numbers):
  - HIGH CERTAINTY: hold through volatility; sell only on thesis break (model change, targets met < 50% two years running, gate fails, promoter holding down > 2pp).
  - UNCERTAIN: at ≥ 2x cost sell `1/multiple` of the position to recover capital; at ≥ 3x within 24 months trim another 25%; cut this bucket first when a pre-defined index support breaks.
  - FALLING KNIFE: never average down until re-scored with a diagnosis.
  - Optional inputs `position_cost_price`, `current_price`, `holding_months` make the plan numeric.

## 5. Workflow

1. **Find the surprise first.** Scan news, exchange filings (open offers, SAST disclosures, demergers, order wins, vendor approvals), quarterly balance-sheet line changes, and 52-week/life highs on volume. Write down the trigger and its date.
2. **Connect dots.** For a theme (railway capex, power/solar, import substitution), list the value chain end-to-end and find the essential component with few approved suppliers and a small market cap.
3. **Pre-fill numbers** (Screener.in + Yahoo daily; each value carries a re-checkable source):
   ```bash
   s=skills/surprise-dot-connect-score/scripts
   python "$s/fetch.py" FRONTSP -o frontsp.fetched.json
   python "$s/fetch.py" TARIL --as-of 2023-03-31 -o taril-2023.fetched.json   # point-in-time back-test
   ```
   Fills: market cap, sales/EPS CAGR, OPM change, ROCE, cash conversion cycle, debt/equity (ex-leases), P/E and its 5y percentile, promoter holding/change/pledge and FII+DII (today only), drawdown, % below 52w high, 10d/50d volume, vs 200DMA. Uses standalone when the consolidated history is shorter (new subsidiaries). Picks NSE or BSE on Yahoo by longer history.
4. **Write the analyst file** (copy `templates/input-template.json` outside the skill folder; null entries never overwrite fetched values). Every list item needs a specific evidence line: document + page/slide/timestamp or URL + date. Verify management claims against numbers (example: Caplin's "top line → bottom line in 6 years" checked against Screener P&L, see `examples/video-stocks/caplipoint.analyst.json`). Never invent a value; leave it null.
5. **Check gates** in the auditor's report/CARO, BSE/NSE announcements, SEBI orders, and the related-party note.
6. **Score** (later files override earlier):
   ```bash
   python "$s/score.py" frontsp.fetched.json frontsp.analyst.json [position.json] [--json]
   ```
7. **Report:** total, verdict, coverage, certainty, flags, gate table, per-pillar table with sources, evidence gaps ranked by points at stake, exit plan, a 3–5 line thesis (the surprise, the dots connected, why the market hasn't priced it, what would break it), and a not-investment-advice disclaimer.
8. **Compare** candidates only at ≥ 80% coverage. Re-score after each quarterly result and on any > 30% price move.

## 6. Verification against every listed stock in the video (run 2026-11-12)

Reproduce: `python examples/video-stocks/verify.py [--refresh]` → `verification.json`. Analyst evidence = transcript timestamps (`<ticker>.analyst.json`, generated from `more-analyst.json` for the newer ones); `AGENT ASSESSMENT` items are unverified; gates not checked. Back-tests use point-in-time Screener/Yahoo data (no shareholding), later outcome from Screener's adjusted price chart. Haren Drugs/Matrix Labs (delisted, acquired by Mylan) and Jubilant Agri & Consumer (< 4 listed years) cannot be scored.

**Point-in-time back-tests (score at date → what happened next)**

| Stock | As of | SDS | P1/P2/P3/P4/P5/P6 | Later peak | Now |
|---|---|---|---|---|---|
| Frontier Springs | 2018-06 | 50 | 6/12/7/8/11/6 | 42.0x | 37.5x |
| Jyoti Resins | 2020-06 | 46 | 4/4/10/7/15/6 | 36.0x | 19.2x |
| TARIL | 2023-03 | 46 | 6/13/6/3/13/5 | 21.8x | 11.1x |
| Indo Tech | 2023-03 | 41 | 4/8/7/4/13/5 | 22.7x | 16.0x |
| Caplin Point | 2020-06 | 40 | 8/4/6/3/12/7 | 9.0x | 7.6x |
| Shilchar | 2022-06 | 36 | 4/8/3/3/13/5 | 34.0x | 20.1x |
| RMC Switchgears | 2023-03 | 35 | 5/7/7/1/10/5 | 6.1x | 1.0x |
| Dynamic Cables | 2023-03 | 33 | 4/7/5/2/10/5 | 6.3x | 4.7x |
| Tera Software | 2024-06 | 30 | 6/5/2/2/11/4 | 6.9x | 4.0x |
| Jubilant Pharmova | 2020-06 | 28 | 6/0/4/1/12/5 | 2.2x | 1.7x |
| Sarda Energy | 2022-03 | 27 | 5/0/8/1/8/5 | 5.2x | 3.9x |
| Ceinsys Tech | 2024-11 | 24 | 1/0/10/4/5/4 | 1.3x | 0.5x |
| MosChip | 2023-03 | 23 | 5/0/6/2/6/4 | 4.8x | 2.7x |
| Suzlon | 2023-03 | 19 | 4/1/8/0/1/5 | 10.6x | 4.9x |

Spearman rank correlation (back-test score vs later peak multiple) = **0.76** over 14 cases: the four highest scores became 22–42x; the stocks the guest described only in passing (Ceinsys, MosChip, Suzlon, Sarda, Jubilant) scored lowest. Shilchar (34x from 36) is the main miss — at 2022-06 its ROCE/OPM had not yet inflected (P3 3/15). All back-tests are `INCOMPLETE` because shareholding and most qualitative evidence were not available point-in-time; treat this as rank evidence, not a hit rate.

**Scores today**

| Stock | Guest's stance | SDS | Verdict | Flags |
|---|---|---|---|---|
| Frontier Springs | holds, ~300x | 65 | STARTER POSITION | |
| Jyoti Resins | partial exit | 49 | WATCHLIST | |
| TARIL | turnaround winner | 49 | INCOMPLETE | |
| Shilchar | theme winner | 45 | INCOMPLETE | |
| Dynamic Cables / Tera / Indo Tech | finds | 44 / 42 / 42 | INCOMPLETE | Tera: FALLING KNIFE |
| Caplin Point | holds, ~90x | 40 | PASS | |
| RMC / Ceinsys | finds | 39 / 36 | INCOMPLETE | FALLING KNIFE |
| Sarda Energy | 2026 pick | 35 | INCOMPLETE | |
| Suzlon | "uncertain, pull capital" | 30 | INCOMPLETE | |
| Pidilite | dominant incumbent | 27 | INCOMPLETE | ELEPHANT |
| MosChip / Insolation | semis / "over-hyped" | 26 / 23 | INCOMPLETE | INA: FALLING KNIFE |
| Jubilant Ingrevia / Pharmova | demerger chain | 23 / 18 | INCOMPLETE | |
| Intellect Design | AI example | 21 | INCOMPLETE | FALLING KNIFE |
| Infosys | cautious (AI, elephant) | 17 | INCOMPLETE | ELEPHANT, AI SERVICES RISK |

The framework's ordering matches the guest's: his conviction holdings on top, the large incumbents and AI-exposed IT at the bottom.

**Guest's price claims vs Screener adjusted price history**

| Claim | Chart | Check |
|---|---|---|
| Frontier ₹15 → 4,500 (~300x) | 2013 low 3.33 → 1,556 today (467x); 1:2 bonus explains the scale | consistent |
| Jyoti ₹40 → 4,000 | 2017 low 19 → 2022 peak 1,745 (92x) | consistent |
| Insolation 47x in 2 years | 9.54 → 460.85 in 1.9y (48x) | confirmed |
| Tera Software 10x in 1.5–2y | 40.5 → 579 in 2.1y (14x) | confirmed |
| TARIL ₹25 → 1,300 in 2.5y | 2020 low 2.65 → 620 peak (234x, split-adjusted) | direction confirmed, scale depends on split base |
| Caplin ~90x from ~₹20 base, bought "9.5–10 years ago" | adjusted ₹17–20 traded in 2013–14; 2016 range 185–400 | multiple fits a 2013–14 entry, not 2016 — timing recollection off |
| Indo Tech ₹200 → 2,200 | 2021 low 86 → 3,902 peak | bigger than claimed |
| Jubilant Pharmova ₹150 → 1,200–1,300 | Covid low 232 → 1,263 peak (demerger-adjusted) | peak confirmed, base differs |
| Caplin "top line → bottom line every 6 years" | Sales FY17–20 vs PAT FY23–26: 94/85/83/75% | met once in 4 windows |

Known weaknesses:
- Scores **today** penalise past winners (size headroom, P/E percentile); the framework is meant to find the *next* Frontier, not re-rate the old one. Caplin scoring PASS today is consistent with that.
- Shareholding (promoter, FII+DII) is only available for the latest quarters; back-tests need it entered manually.
- `cash_conversion_cycle_days` misses Caplin's entry-time negative working capital (receivables have since grown); always read the trend, not just the latest year.
- Qualitative lists depend on how hard the analyst looks; an empty list with a source and a missing list score the same points but differ in coverage.
- P3 rewards margins/ROCE that have *already* inflected, so early-cycle theme plays (Shilchar 2022) score low; the P1 trigger + P2 theme are what should catch them.
- FALLING KNIFE also fired at Frontier 2018 and Jyoti 2020 (genuine 40%+ falls from the 52w high, later 36–42x). It means "diagnose before adding", not "avoid".

## 7. Limitations

- Bands are calibrated for Indian small/microcaps in ₹ crore.
- Triggers older than 24 months should not be counted; a surprise that everyone knows is no longer a surprise.
- The score ranks candidates; it does not predict returns. Not investment advice.
