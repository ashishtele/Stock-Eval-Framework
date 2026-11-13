---
name: abcd-change-catalyst-score
description: >
  Score an Indian listed small/microcap 0-100 with a deterministic, verifiable formula derived from
  Atul Raval's "Market Ki Baat" interview (Hindi, ~1h03m, Apr 2023; Gandhinagar retail microcap
  investor since 1993). Framework: top-down (economy -> government-focus sector -> microcap), the
  ABCD company categories (A tracked large caps = avoid, B stable grown-ups, C old under-achievers
  now changing = main hunting ground, D fallen/turnaround <= 10% of portfolio), CHANGE as the price
  driver (policy, management/next-gen, technology, order wins), earnings x P/E re-rating, promoter
  integrity and capital allocation (fund diversion via ICDs = zero), transparency, and ground
  research/networking. Outputs score, ABCD category, evidence coverage, gates, verdict, flags and an
  action plan (capital-out at 2x, exit on broken assumption). Trigger on: "ABCD score", "ABCD
  category", "change catalyst score", "Atul Raval framework", "Market Ki Baat framework", "is this a
  C-category stock", "score this microcap with the ABCD framework".
metadata:
  version: "1.0"
  source: "Market Ki Baat podcast - Atul Raval interview transcript (Hindi auto-captions, ~1h03m, ~Apr 2023)"
---

# ABCD Change-Catalyst Score (ACS)

A repeatable stock-picking score. Inputs are gathered **with sources**; `scripts/score.py` turns them
into a number. The same inputs always give the same score. Not investment advice.

> Same guest as `surprise-dot-connect-score` (Kushal podcast). That skill scores the *surprise /
> value-chain* lens; this one scores the *ABCD category + change catalyst + integrity* lens from a
> different interview. Running both on one stock is a useful cross-check.

## 1. Principles extracted from the transcript

| # | Principle (timestamp) | Scored in |
|---|---|---|
| 1 | **Top-down first**: understand the global and Indian economy, find where the government is focused, then research companies in those sectors (19:45-20:52, 22:43-22:52) | P1 tailwind |
| 2 | **Sectors with visible spend**: railways (budget Rs 2.4 lakh cr, 200 Vande Bharat), defence (indigenisation + exports to weak-currency countries), engineering exports, power T&D, automation, well-run NBFCs (23:01-27:23, 36:27-40:27) | P1 `tailwind_evidence` |
| 3 | **Government client = no NPA risk; approvals = entry barrier**: Frontier Springs, 3 approved players, 2 private, 1 listed (21:24-21:51) | P1 `customer_credit_quality`, `entry_barrier` |
| 4 | **Microcaps: single product, limited reach** - success and failure are both easy to understand; big players don't touch them (focus strategy) (8:17-10:37) | P4 `business_focus`; P5 neglect, size |
| 5 | **Price moves need CHANGE**: product, environment, government policy, management, regulation - whatever turns an ordinary company into an extraordinary one (9:17-9:44, 28:56-29:28) | P2 `change_catalysts` |
| 6 | **ABCD categories**: A = large, tracked, no surprise (avoid); B = small grown stable over 10-30 years (less surprise); C = 25-30-year-old companies that did little, now next generation / new technology / new markets enter (most capital); D = fallen glory, ahead-of-time concept or turnaround, high risk, usually <= 10% (13:59-19:30) | ABCD classifier, verdict, action plan |
| 7 | **C migrates to B**: Balaji Amines Rs 50 -> 350, part booked (19:21-19:30) | action plan (C -> B) |
| 8 | **Return = earnings x P/E**: microcaps usually trade at low P/E (safety); if P/E expands with earnings you get the multiplier (27:56-28:56) | P5 `pe_level`, `growth_adjusted_pe`, `pe_vs_history`; P2 `earnings_inflection` |
| 9 | **Order size vs company size**: Rs 66 cr order to be executed in 3 months vs Rs 6 cr quarterly turnover (12:45-12:55); T&R order book Rs 1,500 cr (40:52) | P2 `growth_visibility` |
| 10 | **Technical confirmation**: a defined level (Rs 56) - buy when price crosses it, because insiders know first (12:28-12:45) | P2 `technical_trigger` |
| 11 | **Management candour**: the promoter described the situation plainly, no stories (13:04-13:27); companies reply to shareholder e-mails about order-book execution (35:05-36:20) | P3 `transparency` |
| 12 | **Exchange disclosures + annual reports are enough information** today (32:58-34:55) | P6 `annual_reports_read_ge_3y`, `exchange_filings_reviewed` |
| 13 | **Questions to promoters**: history, growth projections, succession, competition, plans - and above all integrity (36:41-36:48, 40:59-41:31) | P3 `walk_the_talk`, `reputation` (`succession_plan_clear`) |
| 14 | **Verify the theme down the value chain**: visited transformer and cable makers; debt offset by monetisable assets (39:50-40:44) | P6 `value_chain_peer_confirms_thesis`; P4 `balance_sheet` |
| 15 | **Third-party integrity check**: State Electricity Board friends vouched for T&R's technocrat promoter (59:40-59:56) | P3 `reputation` |
| 16 | **End-user scuttlebutt**: a carpenter's 15-year preference revealed Jyoti Resins; no ads, channel incentives; Rs 40 -> 4,000 + bonus (47:57-51:42) | P6 `end_user_or_tradesman_feedback`; P1 `dealer_or_channel_lock_in` |
| 17 | **Read unusual signals of strength**: an NBFC declining the COVID moratorium = strong liquidity; verify written claims with management by phone (52:40-54:56) | P2 `balance_sheet_repair`; P3 `transparency` |
| 18 | **Networking** spreads research load; don't rely on fund reports (Manpasand had buy ratings) (41:39-43:17) | P6 ground checks |
| 19 | **Exit when an assumption breaks, regardless of P&L** - the market doesn't care what you paid (43:50-44:32) | `thesis_assumption_broken` -> EXIT |
| 20 | **Integrity failures go to zero**: pharma-packaging company moved money via ICDs to a private sister concern -> NCLT; Panyam Cement transferred funds to a private group firm. Every metric was fine; the intent wasn't (56:43-58:59) | gate `fund_diversion`; P3 `capital_allocation` |
| 21 | **Take capital out after a big move; no "buy and sleep"** (Yes Bank, Manpasand, DHFL); cash out of D-category positions at a high-uncertainty level; average up as the story confirms (13:37-13:44, 52:34-52:40, 58:59-59:31) | action plan |
| 22 | **Accept external failure, never promoter failure** (1:00:04-1:00:20) | action plan, gates |

## 2. Gates (any FAIL => REJECT)

| Gate | Input | Fails when |
|---|---|---|
| Auditor | `auditor_red_flag_3y` | qualified opinion, or auditor resigned citing concerns, last 3y |
| Regulatory | `regulatory_action_against_promoters_or_kmp_3y` | SEBI/ED/fraud order against promoters or KMP |
| Fund diversion | `fund_diversion_red_flag_3y` | ICDs, loans, advances or guarantees to promoter-group private entities |
| Pledge | `promoter_pledge_pct` | > 25% |

An unverified gate caps the verdict at `PROVISIONAL HIGH CONVICTION`. `thesis_assumption_broken = true` overrides everything with `EXIT / AVOID`.

## 3. Formula (100 points)

$$\text{ACS} = P1_{15} + P2_{20} + P3_{25} + P4_{15} + P5_{15} + P6_{10}$$

### P1 Macro & Sector Tailwind (15)
| Metric | Input | Points |
|---|---|---|
| tailwind_evidence (6) | `tailwind_evidence` ⊆ {`govt_capex_or_budget_up_ge_15pct`, `policy_or_regulatory_mandate`, `indigenisation_or_import_substitution`, `export_opportunity_documented`, `demand_pulled_forward_or_supply_shortage`, `structural_cost_shift` (e.g. labour scarcity -> automation), `sector_order_inflow_rising`} | 1 each, max 6 |
| entry_barrier (6) | `entry_barrier_checks` ⊆ {`approval_or_vendor_registration_required`, `long_qualification_or_trial_cycle`, `players_in_niche_le_3`, `only_or_one_of_two_listed_players`, `proprietary_process_or_know_how`, `dealer_or_channel_lock_in`} | 1 each |
| customer_credit_quality (3) | `govt_or_psu_payer` / `large_rated_corporates` / `diversified_retail_or_dealers` / `weak_or_concentrated_private` | 3 / 2 / 2 / 0 |

### P2 Change Catalyst & Earnings Inflection (20)
| Metric | Input | Points |
|---|---|---|
| change_catalysts (8) | `change_catalysts` ⊆ {`policy_or_regulation_change`, `next_generation_or_new_management`, `new_technology_or_product`, `new_market_or_export_entry`, `strategic_acquirer_or_open_offer`, `asset_monetisation_or_demerger`, `large_order_win`, `capacity_or_approval_unlock`, `balance_sheet_repair`}, each dated within 24 months | 0→0, 1→4, 2→6, ≥3→8 |
| growth_visibility (5) | `order_book_to_ttm_sales` if order-based: ≥3→5, ≥2→4, ≥1→2, ≥0.5→1; else `ttm_sales_growth_pct`: ≥40→5, ≥25→4, ≥15→2, ≥10→1 | |
| earnings_inflection (4) | `ttm_pat_growth_pct` vs `pat_cagr_3y_pct` | ≥25 and above 3y CAGR (or CAGR n/a)→4, ≥25→3, ≥10→2, >0→1 |
| technical_trigger (3) | `pct_below_52w_high` (≤5→2, ≤15→1) + `volume_ratio_10d_vs_50d` ≥1.5→+1 | |

### P3 Promoter Integrity & Capital Allocation (25)
| Metric | Input | Points |
|---|---|---|
| capital_allocation (5) | `capital_allocation_checks` ⊆ {`no_loans_icd_or_guarantees_to_promoter_entities_3y`, `rpt_lt_5pct_of_revenue`, `group_investments_lt_5pct_networth`, `no_unrelated_diversification_5y`, `equity_dilution_lt_10pct_3y`} | 1 each |
| cash_conversion (3) | `cfo_to_pat_3y` | ≥0.9→3, ≥0.7→2, ≥0.5→1 |
| promoter_alignment (5) | `promoter_holding_pct`, `promoter_holding_change_3y_pp`, `promoter_pledge_pct` | pledge > 0 or change < −2pp → 0; change ≥ −0.5pp: holding ≥50→5, ≥35→3, else 2; otherwise 1; professionally managed → 2 |
| transparency (4) | `transparency_checks` ⊆ {`responds_to_shareholder_queries`, `discloses_order_book_or_execution_status`, `concalls_or_investor_meets`, `candid_no_hype`} | 1 each |
| walk_the_talk (4) | `guidance_hit_pct` (% of explicit targets met; list them) or `"none_stated"` | ≥80→4, ≥50→2, none stated→1 |
| reputation (4) | `reputation_checks` ⊆ {`industry_or_customer_vouches_integrity`, `technocrat_or_domain_expert_promoter`, `no_adverse_media_or_litigation`, `succession_plan_clear`} | 1 each |

### P4 Business Quality & Balance Sheet (15)
| Metric | Input | Points |
|---|---|---|
| business_focus (2) | `single_product_or_niche` / `focused_few_segments` / `diversified_conglomerate` | 2 / 1 / 0 |
| sales_growth (3) | `sales_cagr_3y_pct` | ≥20→3, ≥12→2, ≥8→1 |
| roce (3) | `roce_3y_avg_pct` | ≥20→3, ≥15→2, ≥10→1 |
| margin_trend (3) | `opm_change_3y_pp` | ≥3→3, ≥0→2, ≥−3→1 |
| balance_sheet (4) | `debt_to_equity` (ex-leases); optional `monetisable_assets_cover_debt` | ≤0.3→4; asset-covered→3; ≤1→2; ≤1.5→1 |

### P5 Valuation & Re-rating Room (15)
| Metric | Input | Points |
|---|---|---|
| pe_level (4) | `pe` | ≤10→4, ≤15→3, ≤20→2, ≤30→1, loss→0 |
| growth_adjusted_pe (4) | PEG = `pe` ÷ min(`eps_cagr_3y_pct`, 50) | ≤0.8→4, ≤1.2→3, ≤2→1 |
| pe_vs_history (3) | `pe_percentile_5y` | ≤25→3, ≤50→2, ≤75→1 |
| institutional_neglect (2) | `institutional_holding_pct` (FII+DII) | ≤5→2, ≤10→1 |
| size_headroom (2) | `market_cap_cr` | ≤1,000→2, ≤5,000→1 |

### P6 Ground Research & Network (10)
`ground_checks` (weighted): `annual_reports_read_ge_3y` 1, `exchange_filings_reviewed` 1, `end_user_or_tradesman_feedback` 2, `dealer_or_channel_feedback` 1, `customer_or_inspector_feedback` 1, `value_chain_peer_confirms_thesis` 2, `factory_or_office_visit` 1, `management_meeting_or_agm` 1.

## 4. ABCD classifier (deterministic, first match wins)

| Category | Rule | Meaning / sizing |
|---|---|---|
| **D** | `ttm_pat_cr` ≤ 0 **or** `drawdown_from_high_pct` ≥ 70 | Fallen / turnaround. Whole D bucket ≤ 10% of portfolio (transcript 19:05) |
| **A** | `market_cap_cr` ≥ 20,000 | Tracked, no surprise. Verdict forced to `AVOID - Category A` |
| **C** | age (`as_of` year − `incorporation_year`) ≥ 15 **and** `sales_cagr_10y_pct` < 12 **and** ≥ 1 change catalyst | Old under-achiever now changing. Primary bucket |
| **C-DORMANT** | same, but no catalyst | Verdict capped at `WATCHLIST` - wait for the change |
| **B** | otherwise (including any company < 15 years old) | Grown and stable; less surprise |
| UNCLASSIFIED | a required input is missing (`sales_cagr_10y_pct` needs ≥ 7 years of P&L) | |

The 20,000 cr, 15-year, 12% and 70% cut-offs operationalise the transcript's qualitative descriptions; they are not the guest's numbers.

## 5. Verdict, flags, action plan

- **Evidence coverage** = metrics scored `ok` ÷ 24. Missing, unsourced or invalid inputs score 0. An empty list with a source means "checked, none found" (0 points, counted as covered).
- **Verdict:** broken assumption → `EXIT / AVOID`; gate FAIL → `REJECT`; category A → `AVOID`; coverage < 80% → `INCOMPLETE`; ≥ 75 → `HIGH CONVICTION` (100% coverage, all gates pass; else `PROVISIONAL`); 60–74 → `STARTER POSITION`; 45–59 → `WATCHLIST`; < 45 → `PASS`. C-DORMANT caps at `WATCHLIST`.
- **Flags:** `NO CHANGE YET` (0 catalysts), `INTEGRITY UNPROVEN` (transparency + reputation < 3), `CAPITAL ALLOCATION RISK` (capital_allocation ≤ 2), `CROWDED` (FII+DII > 25%), `PRICED FOR PERFECTION` (P/E > 30 and above 75th percentile of own range).
- **Action plan:** exit on broken assumption regardless of P&L; exit fully on integrity breach; D bucket ≤ 10%, cash out at a high-uncertainty level; C re-rated above the 75th P/E percentile → book part (C → B); add only as the catalyst is confirmed (average up, not down); with `position_cost_price` and `current_price`, at ≥ 2x sell `1/multiple` to take the original capital out (the 2x trigger is operationalised).

## 6. Workflow

1. **Top-down.** Write the macro/sector view first: which sector has documented government spend, policy or a demand shift? Collect dated proofs for `tailwind_evidence`.
2. **Find microcaps in that sector** whose story is small and understandable (one product, one niche). Note approvals, number of players, who pays.
3. **Pre-fill numbers** (Screener.in + Yahoo; each value carries a re-checkable source):
   *(from repo root)*
   ```
   python skills/abcd-change-catalyst-score/scripts/fetch.py FRONTSP -o frontsp.fetched.json
   python skills/abcd-change-catalyst-score/scripts/fetch.py TARIL --as-of 2023-04-15 -o taril-2023-04.fetched.json   # point-in-time
   python skills/abcd-change-catalyst-score/scripts/fetch.py 526073 -o galaxy.fetched.json                            # BSE-only: use the code
   ```
   Fills: market cap, sales/EPS/PAT CAGR (3y), sales CAGR (up to 10y), OPM change, ROCE, CFO/PAT (3y), TTM sales/PAT and their YoY growth (annual proxy when < 8 published quarters), debt/equity ex-leases, P/E and 5y percentile, drawdown from all-time high, % below 52w high, 10d/50d volume, vs 200DMA, current price, and (today only) promoter holding/change/pledge and FII+DII. Point-in-time runs respect publication lags (annual 60 days, quarterly 45 days).
4. **Write the analyst file** (copy `templates/input-template.json` outside the skill folder; null entries never overwrite fetched values). Every list item needs evidence: document + page/timestamp or URL + date. Mark your own judgements `AGENT ASSESSMENT`. Never invent a value; leave it null.
5. **Integrity work before buying:** read the related-party note, ICD/loan schedules and group investments (gate + `capital_allocation_checks`); e-mail the company a specific question (order-book execution, disclosure gap) and record whether they reply (`transparency_checks`); ask an industry/customer contact about the promoter (`reputation_checks`).
6. **Ground checks:** end users/tradesmen, dealers, a value-chain peer, factory visit, AGM.
7. **Score** (later files override earlier):
   ```
   python skills/abcd-change-catalyst-score/scripts/score.py frontsp.fetched.json frontsp.analyst.json [position.json] [--json]
   ```
8. **Report:** total, ABCD category + reason, verdict, coverage, flags, gate table, per-pillar table with sources, evidence gaps ranked by points at stake, action plan, a 3–5 line thesis (the macro tailwind, the change, why the market hasn't priced it, the written assumptions that would break it), and a not-investment-advice disclaimer.
9. **Re-score** after each quarterly result, on any > 30% price move, and whenever a written assumption is tested. Share updates with your network if others follow your idea.

## 7. Verification on the stocks named in the episode (run 2026-11-12)

Reproduce: `python examples/video-stocks/calibrate.py` (exit code 1 if any label check fails).

### 7a. Episode date and the guest's price claims (Yahoo weekly, un-adjusted for bonus/split)

| Claim (timestamp) | Data | Holds? |
|---|---|---|
| Frontier Springs "from 15-20 levels, touched 500 this time", ~7 years (22:21-22:28) | 2016 low 21; first week ≥ 500: 2022-10-23 (high 540) | Yes |
| T&R "started at Rs 20, went up to 65" (59:56) | 2020 high 23.7; 2022 high 67.4; Apr-2023 closes 57-66 | Yes |
| Jyoti Resins "40 -> 4,000", then bonus (50:43-51:33) | 2015-16 lows 10-58; first week ≥ 4,000: 2022-08-28; bonus Sep-2022 | Yes |
| Galaxy Bearings "Rs 8-10 -> 1,200" (47:15-47:24) | 2016 high 8.3; 2022 high 1,338 | Yes |
| Yes Bank "available at Rs 10" (17:12-17:29) | 2020 low 5.65; 2021 low 10.5; Apr-2023 close 15.4 | Yes (2020-22) |
| Renuka "Rs 8" (18:37) | 2019-20 range 3.25-14.7; Apr-2023 close 45.8 | Yes (2019-20, not at the episode) |
| Panyam Cement went to zero (58:35-58:59) | 2018 high 69 -> 2019 low 6.3; 2021 capital reduction 20:1 | Yes |

Frontier's "touched 500" (Oct 2022-Jan 2023), the Rs 2.4 lakh cr railway budget (Feb 2023) and "after 31 March" pin the episode to ~Apr 2023, so point-in-time runs use **2023-04-15** (FY23 annuals not yet published -> FY22 numbers).

### 7b. Scores (point-in-time vs today)

Qualitative inputs are only what the transcript says, with timestamps. Shareholding history is unavailable for back-tests, so promoter alignment and institutional neglect are missing and coverage stays < 80%. Gates are unverified except where noted. `fwd x` = Yahoo close 2026-11-11 ÷ close at the point-in-time date.

| Stock | Date | Score | Category | P1/P2/P3/P4/P5/P6 | Score today | Category today | fwd x |
|---|---|---|---|---|---|---|---|
| Transformers & Rectifiers | 2023-04 | 40 | C | 6/10/5/6/9/4 | 45 | B | 9.91 |
| Jyoti Resins | 2023-04 | 35 | B | 3/8/1/15/4/4 | 37 | B | 0.66 |
| Galaxy Bearings | 2023-04 | 31 | B | 0/10/2/13/6/0 | 17 | C-DORMANT | 1.20 |
| Balaji Amines | 2023-04 | 31 | B | 0/10/1/13/7/0 | 24 | C-DORMANT | 0.73 |
| Frontier Springs | 2023-04 | 30 | B | 8/5/3/10/3/1 | 48 | B | 11.36 |
| Shree Renuka Sugars | 2023-04 | 15 | D | 1/5/0/5/4/0 | 12 | D | 0.41 |
| L&T | 2023-04 | 10 | A | 0/4/3/3/0/0 | 16 (AVOID) | A | 1.86 |
| Yes Bank | 2023-04 | 9 | D | 0/4/0/5/0/0 | 27 | D | 1.12 |
| Manpasand Beverages | 2018-06 | 31 | UNCLASSIFIED | 0/7/3/12/9/0 | REJECT (2019 auditor exit + promoter arrests) | - | delisted |
| Panyam Cements | - | - | - | - | 22, REJECT (fund diversion) | D | - |

### 7c. Checks against the guest's own labels: 7/7 pass

L&T = A; Yes Bank = D; Renuka = D; Balaji Amines = B (had moved from C); T&R = C at the episode; Manpasand = REJECT once 2019 facts are added; Panyam = REJECT on the fund-diversion gate.

Reading:
- T&R ranked first and became ~10x. Frontier Springs (~11x) scored low in Apr 2023: FY22 numbers were flat and P/E sat at the 90th percentile of its range; the edge was the railway/approval thesis, which the transcript evidences only partly. Known weakness: the numeric pillars lag a catalyst that hasn't reached the P&L.
- D names scored lowest; Renuka lost 59%, consistent with keeping D ≤ 10%.
- Manpasand already showed a 68% drawdown and ROCE 10.7% by Jun 2018; it stays UNCLASSIFIED because Screener has < 7 years of its P&L. The gates, not the score, catch it - as in the transcript.
- The guest's pharma-packaging failure (56:51-58:28, auto-captioned "Gujarat ...") could not be identified with confidence, so it is not scored.
- Ten stocks is not a statistical test. Thresholds were set from the transcript before these runs and were not tuned to outcomes.

### 7d. Data cross-checks

- Today's P/E (chart) equals Screener's headline Stock P/E for TARIL, FRONTSP, JYOTIRES, BALAMINES; Yahoo close is within 1-5% of Screener's live price (previous close vs intraday).
- Point-in-time market cap = today's market cap × adjusted-price ratio × share ratio (Net Profit/EPS then vs latest), cross-checked against Screener's Market-Cap-to-Sales × TTM Sales; differences > 10% print a warning (Balaji Amines: 9,071 vs 7,993 - minority interest shifts; treat back-test market caps as ±15%).

## 8. Limitations

- Bands are calibrated for Indian small/microcaps in Rs crore. Banks/NBFCs: ROCE, OPM and CFO/PAT are not meaningful; score them with care or skip P4/P3 cash conversion.
- Catalysts older than 24 months should not be counted.
- `incorporation_year` in the examples is agent recall - verify before relying on the category.
- Point-in-time market cap is reconstructed (±15%); shareholding is only available for recent quarters.
- Qualitative lists depend on how hard the analyst looks; an empty list with a source and a missing list score the same points but differ in coverage.
- The score ranks candidates; it does not predict returns. Not investment advice.
