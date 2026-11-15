# RS Leader Setup framework: rules, formulas and sources

Source: "Conversation with Kushal" podcast, guest Himanshu (CMT/CFTe/MSTA, full-time swing/positional
trader since 2022, holds stocks a few weeks to a few months). Timestamps refer to that transcript.
The speaker's own idea is to raise the *probability* of winning and make each bet *asymmetric*:
the coin stays 50/50 but the payoff changes (5:08-8:17).

## Contents
1. The four-stage funnel
2. Market health (regime)
3. Gates: the RS80 scan
4. Pillar rules and formulas
5. Caps, leg logic and classification
6. Trade plan and position sizing
7. Edge from your journal
8. Things deliberately left out, and known weaknesses

---

## 1. The four-stage funnel

| Stage | What happens | Output | Script |
|---|---|---|---|
| 0. Market | Breadth tells you how hard to press | Regime + risk per trade | `score_setup.py --market-only` |
| 1. Universe | ~2,500 NSE stocks -> RS80 scan -> 150-265 names | Shortlist + industry counts | `compute_rs.py` |
| 2. Chart | Keep names forming a base, about to emerge -> 20-40 | Technical inputs | `chart_metrics.py` |
| 3. Theme | Group them by industry, keep the strongest groups and the first 1-2 names in each -> 15-20 | Group count, leader rank | `compute_rs.py` + judgement |
| 4. Catalyst | Read presentation / con-call for the earnings trigger -> final 10-15 | Catalyst fields | research |
| Score | All of the above -> 0-100 + class + trade plan | Report | `score_setup.py` |

(Funnel described 37:36-40:27, 49:20-50:07 and 1:03:31-1:03:54.)

## 2. Market health

"Three out of four stocks follow the general market" (O'Neil, 9:39). In a poor market the win rate
falls to 20-30% and average gains shrink; in a healthy one it rises to 60-70% (10:35-10:54, 16:47-17:20).

| Field | Formula | Points | Source |
|---|---|---|---|
| `pct_above_50dma` | % of Nifty 500 above their 50 DMA | 15 | 13:02, 15:13 |
| `pct_above_50dma_change_4w` | today minus 4 weeks ago, in points | 5 | 15:13 "consistently declining" |
| `new_high_share` | NH / (NH + NL), 52-week | 20 | 12:26, 15:27 |
| `adv_decl_ratio_10d` | 10-day avg of advances / declines | 20 | 12:47 |
| `index_above_50dma`, `index_above_200dma` | bools | 10 + 10 | trend |
| `breakout_followthrough_rate` | watchlist breakouts that followed through / all breakouts, last 4 weeks | 10 | 14:18 watchlist feedback |
| `equity_curve_rising` | your own portfolio curve | 5 | 14:10 portfolio feedback |
| `positive_reaction_to_news` | market rises on good data (e.g. GDP beat) | 5 | 13:40 |
| Penalty: `index_near_high_breadth_falling` | index at highs while breadth falls | -10 | 13:24 (Jan-Feb 2020: Nifty highs on Reliance + HDFC Bank only) |
| Penalty: `false_breakdowns_rising` | breakouts reversing below the base low are rising | -10 | 1:09:58-1:10:41: first sign of a top |

Regimes (risk per trade / max position): HEALTHY >= 70 (1% / 30%), NEUTRAL 50-69 (0.5% / 20%),
WEAK 30-49 (0.25% / 10%), HOSTILE < 30 (0.25% / 10%, pilots only). The speaker's standard size is
10%, going to 25-30% with only 5-6 stocks in a healthy market (1:33:34).

Weak markets are *not* a reason to stop scanning. They are when the RS scan is shortest (100-120
names) and the true leaders are easiest to see: Laurus Labs made an all-time high on 23 Apr 2020, a
month after the Nifty low, then rose ~700% (51:20-51:46; 1:05:09-1:05:40).

## 3. Gates: the RS80 scan

All must pass, otherwise the stock is REJECTED (1:11:55 shows the live scan).

| Gate | Threshold | Why |
|---|---|---|
| `price_above_200dma` | true | "If it can't beat its own 200-day average, how will it become a multibagger?" (33:31) |
| `rs_rating` | >= 80 | top 20% of the market (28:53-29:29) |
| `avg_turnover_30d_cr` | >= 10 Cr (7 Cr soft floor) | liquidity (33:40) |
| `market_cap_cr` | >= 500 Cr | excludes illiquid microcaps (33:15) |
| `price` | >= Rs 10 | (33:59) |

**RS rating.** Rank every listed stock by 3-month return, convert to a percentile:
`rating = clip(100 - ceil(rank_from_top / N x 100), 1, 99)`. Top 1% = 99, top 2% = 98 (25:39-28:46).
Three months is the chosen window: 12 months is too late, 1 week catches news-driven junk
(26:28-27:42, citing Faber 2010 and Jegadeesh-Titman 1993). Weighted 3/6/9/12 is offered as an option.

Myth addressed (29:06): RS 80 does not mean "already missed it". A stock that merely holds flat while
the index falls also earns a high rating; STL was RS 91 at Rs 125 and still RS 99 at Rs 1,000.

## 4. Pillar rules and formulas (100 points)

### A. Relative strength - 15
| Rule | Bands | Source |
|---|---|---|
| `rs_rating` | 95+ = 12, 90+ = 10, 85+ = 8, 80+ = 6 | O'Neil: past US winners averaged RS 87 at the start (32:46) |
| `rs_resisted_decline` | 3 if true | Darvas "stocks that resisted the tide" (32:22); "the whole neighbourhood burned, our house stood" (1:17:32) |

`chart_metrics.py` tests the second rule: during the index's worst drawdown (>= 5%) in the last
126 sessions, did the stock lose less than half as much?

### B. Technical template of past winners - 30
"Study past winners, rewind their charts" (19:44-22:43). Common ingredients (34:44-36:33, 1:05:48):

| Rule | Formula | Bands | Source |
|---|---|---|---|
| `prior_uptrend` | close > EMA50 > SMA200, SMA200 rising, >= 20% off base low (or HH/HL by eye) | 5 | 47:55-48:14 (Dow theory) |
| `base_length_weeks` | sideways stretch (range <= 30%) before the advance | 26+ = 5, 8+ = 4, 4+ = 3 | "long base, minimum one month" (1:01:55, 1:05:56) |
| `stop_distance_pct` | (pivot - base low) / pivot x 100, i.e. depth of the tight right side | <=5 = 8, <=6 = 7, <=8 = 5, >8 = 0 | stop 5-8% max; ">8% is not a proper base" (1:08:54) |
| `volume_dryup_ratio` | avg vol last 10 / last 50 | <=0.6 = 4, <=0.8 = 3, <=1.0 = 1 | "volume dries up" in the right side (44:04, 1:06:29) |
| `volume_spike_ratio` | max vol last 60 / avg vol last 120 | 3x = 3, 2x = 2, 1.5x = 1 | "skyscrapers" = institutions (44:20); Darvas "sleeping stock wakes up" (1:20:35) |
| `ema50_breaches` | runs of >= 2 closes below EMA50 since the advance began | 0 = 3, 1 = 1 | "a strong stock doesn't breach the 50 EMA" (41:30, 1:21:15) |
| `fall_to_recover_ratio` | sessions spent falling / sessions to retrace it | 6+ = 2, 3+ = 1 | STL fell ~1 year, came back in ~1 month; SAN DLM 2 years vs 2 months (38:27, 47:45) |

### C. Stage / timing - 15
| Rule | Bands | Source |
|---|---|---|
| `leg_number` | 1 = 11, 2 = 9, 3 = 4, 4+ = 0 | "catch it in the first or second leg" (36:02, 43:24); 3rd-5th leg = trade only (1:19:55) |
| `rest_days` | <=20 = 2, <=40 = 1 | a leader with a strong catalyst rests 15-20 days, not 2-4 months (55:52-56:54) |
| `market_cap_cr` | 1,000-10,000 Cr = 2; 500-1,000 or 10,000-20,000 = 1 | "more room to grow" (36:33-37:28) |

### D. Theme & group leadership - 20
| Rule | Bands | Source |
|---|---|---|
| `group_count_in_scan` | names from the same industry in the RS80 scan: 6+ = 8, 4-5 = 6, 2-3 = 3 | "7-8 aerospace names = strong theme" (49:43-49:58); identify the theme and 80% of homework is done (55:19) |
| `leader_rank_in_group` | 1st = 6, 2nd = 5, 3rd = 2 | "only the first and second name" (53:01); STL before HFCL, Mazagon before Cochin (52:13-54:43) |
| `theme_revenue_share_pct` | % of revenue from the theme: 40+ = 4, 20+ = 3, 10+ = 1 | Paramount: OFC only 2% of revenue, didn't work (53:54) |
| `global_peer_confirmation` | global peer/customer already a multibagger | Corning/Lumentum for STL (30:44); Bloom Energy for MTAR (46:11); AXTI (39:42) |

Leader rank: `compute_rs.py` ranks by RS inside the industry as a proxy. The speaker's real test is
*who moved / made a new high first* after a market low; check the charts and override if they differ.

### E. Catalyst & earnings - 20
"Price is the slave of earnings" (22:10). A catalyst is the trigger that will lift earnings, and
management will advertise it loudly in presentations and con-calls (50:07, 1:28:30, 1:29:42).

| Rule | Formula | Bands | Source |
|---|---|---|---|
| `pat_growth_yoy_pct` | latest quarter PAT vs same quarter last year | 50+ = 5, 25+ = 4, 10+ = 2 | earnings back the move (1:03:46) |
| `sales_growth_yoy_pct` | TTM or quarterly YoY | 25+ = 3, 15+ = 2, 5+ = 1 | JG Chemicals 840 -> 973 Cr (1:23:07) |
| `catalyst_revenue_uplift_pct` | revenue the new capex/orders can add / current revenue x 100 | 50+ = 5, 25+ = 4, 10+ = 2 | JG: 50 Cr capex done adds 400-450 Cr on ~900 Cr (1:25:40) |
| `catalyst_months_to_impact` | months until commissioning / order execution | <=6 = 3, <=12 = 2, <=24 = 1 | "H1 FY27, active in 6 months" (1:25:30) |
| `quantified_guidance` | management gives numeric targets (EBITDA, revenue, mix) | 2 | "throw it far" - big projections make stocks move (50:17, 1:27:15) |
| `upcycle_quarters_elapsed` | consecutive strong-earnings quarters so far | <=4 = 2, <=6 = 1 | strong runs last ~6-8 quarters, then the top comes (1:00:27-1:00:48) |

Useful derived check for capex stories: **asset turnover of the capex** = potential revenue / capex
(JG: 900 / 100 = 9x). Note it in evidence; high turnover makes the uplift credible.

On verifying management claims (1:26:20-1:27:50): the speaker does not try to prove projections.
Rising price on heavy volume means better-informed institutions did their research; the stop-loss
is the protection if the story is wrong. Record the claim and the source anyway.

## 5. Caps, leg logic and classification

Caps (score can't exceed the cap):
- `loose_base`: stop_distance_pct > 8 -> max 59.
- `theme_tourist`: theme_revenue_share_pct < 10 -> max 59.
- `weak_vs_50ema`: ema50_breaches > 1 -> max 69.

Leg logic: if `leg_number` is missing it is derived from `gain_from_base_low_pct`
(<=60% = 1, <=100% = 2, <=150% = 3, else 4). If both exist, the later leg wins and a flag is raised.
Anchors: STL at Rs 125 after a 25-30% move "is not late" (31:08); Bliss GVS 200 -> 650 "already
took many legs" (1:16:27); MTAR 2400 -> 9000 is trade-only (1:21:30).

Missing data: rules with null inputs are excluded. Two scores are always computed, both after caps:
re-based (points earned / points available x 100) and conservative (missing = 0). At 70%+ coverage
the headline is the re-based score; below that it is the conservative score, because re-basing a
handful of strong facts can produce a misleading 90-100 (found when scoring Laurus 2020 from four
facts in the talk).

Word inputs: where a source only describes a feature ("volume bahut zyada", "tight base"), enter the
word. `framework_config.json -> qualitative` maps it to the floor of its band and the field is tagged
qualitative. Unknown words raise an error instead of guessing.

| Class | Condition |
|---|---|
| REJECT | any gate fails |
| BUY CANDIDATE - A | score >= 75, leg <= 2, pivot/stop defined |
| BUY CANDIDATE - B | score 60-74, leg <= 2, pivot/stop defined |
| BUY-GRADE - pending pivot/stop | would be BUY, but no base high/low given yet |
| TRADE ONLY - late stage | score >= 60, leg >= 3 |
| WATCHLIST | everything else (late-stage and no-pivot variants are labelled) |

Below 70% coverage any non-REJECT class is shown as "INSUFFICIENT DATA (n% coverage) - provisional:
<class>", so strong-but-unverified names stay distinguishable from weak ones. Below 20% coverage
the provisional grade is withheld ("too little data to grade").

In WEAK/HOSTILE markets BUY classes get "pilot size only".

Holding alerts (not scored, for existing positions): price below the 50 EMA (the trailing exit,
41:30), RS below 80, and a late leg combined with a loose base.

## 6. Trade plan and position sizing

- Entry = pivot (high of the tight consolidation). If price is already above the pivot, entry =
  price, which widens the stop and shrinks size (1:34:00).
- Stop = consolidation low (technical default; Minervini school). Aggressive alternative = breakout
  day low (Dan Zanger: "winning horses don't come back to the gates"), sized at 0.25% risk
  (1:07:45-1:08:16, 1:35:13).
- `stop_pct = (entry - stop) / entry x 100`
- **Position size % = risk% x 100 / stop%**. At 1% risk: 100 / stop% (1:31:01). 5% stop -> 20%
  position -> 1% portfolio loss if wrong. Beginners: 0.5% or 0.25% risk, or start with half and add
  once the stock proves itself (1:32:41).
- Target default = entry x (1 + 5 x stop%) (the 1:5 coin game). Flag if below 4R.
- Exit: trail on a daily close below the 50 EMA; don't exit on valuation, "there is no limit to how
  mad the market can get" (41:06-43:50, Tata Elxsi 900 -> 7000+ with "overvalued" threads all the way).

## 7. Edge from your journal

`Edge = (win% / loss%) x (avg gain% / avg loss%)` (16:32). This equals the profit factor.
< 1 losing, 1-2 thin, > 2 good; the speaker's is 3.8. Example: 50% win rate, 20% avg gain, 5% avg
loss -> edge 4. `edge_calc.py` computes it from a CSV of trade P&L %, plus expectancy per trade.

## 8. Deliberately left out, and known weaknesses

- Valuation (P/E) is not scored: the speaker explicitly exits on stops, not valuation.
- Leg counting and base quality are partly visual; the gain-from-base-low proxy is conservative but
  crude. Look at the chart.
- RS rating needs the full universe. A rating computed on a small universe is not comparable.
- The examples in `assets/examples/` are reconstructions from the talk with ASSUMED placeholders.
  They test the logic, not real-world performance. The framework has not been back-tested here.
