# Framework reference: where every rule comes from

Source: Hindi/English podcast interview with Manish Dhawan (founder, Mystic Wealth, Delhi; ~14 years of quantitative momentum investing). Timestamps refer to that interview. Rules he stated directly are marked **[stated]**. Numbers chosen to turn his words into a formula are marked **[calibration]**. Change the calibrations if you like, but say so in the report.

## 1. Philosophy (why price-only)

- "Everything is a story / narrative" (7:03–11:52). IPOs come in bull markets, TV calls get timed, sector themes rotate (AI → IT). A portfolio built on stories turns into a shopping cart full of whatever someone was selling. **Rule:** buy, hold and sell only on what the process says. News, promoter buying, forensic red flags and influencer tips are ignored. [stated]
- "I am a slave to my system" (29:41). Adani Total Gas (2017) was a 5-bagger that every value friend called overvalued. Laurus and Persistent kept rising after the system exited. Both cases are accepted as part of the deal. [stated]
- "60% of our stocks give us a loss; we're worse than a coin toss" (35:46). The edge comes from outliers paying for the losers ("one trend forgives five murders"). **Implication:** never judge the framework on one stock. Judge it on the portfolio and the rules. [stated]
- "All the bad things happen below the 200-DMA" (Anish Teli, quoted at 1:03:52). Used as part of the Stage-2 gate. [stated]

## 2. Stock selection: the scoring engine

| Step | Transcript | Formula in script | Type |
|---|---|---|---|
| Universe | Nifty 750 (top 750 by market cap); anything below is too illiquid (16:55) | G1, in order of preference: (1) member of the Nifty Total Market index (750 stocks, shown on Screener.in under "Part of"); (2) mcap_rank ≤ 750; (3) mcap ≥ ₹3,000 cr as a rough proxy | membership/rank [stated]; ₹ cutoff [calibration] |
| Stage-2 | Only stocks above their 30/50/100-DMA (13:13); plus the 200-DMA quote | G2: Close > SMA30, SMA50, SMA100, SMA200 | [stated] |
| Rate of change | "Rank which horse runs fastest" (17:08) | R12 = C_t/C_{t-252} − 1; R6 = C_t/C_{t-126} − 1; G3 needs both > 0 | ROC [stated]; 6m/12m windows [calibration, same as NSE momentum indices] |
| Volatility penalty | "Punish volatility… we want horses that run fastest but are least volatile" (14:08, 17:18) | σ = stdev(daily log returns, 252d) × √252; MomRA = 0.5·R6/σ + 0.5·R12/σ | [stated] concept; formula [calibration] |
| 45° consistency | "Consistently running at 45°, not suddenly up and down" (14:15) | R² of the regression of ln(Close) on time over 126 days (0 if the slope is negative) | [calibration] of a stated idea |
| Distance from 52WH | "Distance from 52-week high should not be too much" (13:27, 17:25) | P = Close/H52; G4 needs P ≥ 0.75 | concept [stated]; 0.75 [calibration] |
| Circuit filter | "Stocks constantly on circuits are punished and kept out" (14:23) | Locked-circuit proxy: day with \|ret\| ≥ 4.85% that closes at the day's high (up) or low (down). G5 allows ≤ 10 in a year; each one costs 2 pts | [stated] concept; thresholds [calibration] |
| Ranking | Rank everything and buy the top 20 (17:32) | Universe mode: weighted percentile score, sorted | [stated] |
| Hold/exit | Keep a holding while it is still in the top 50; replace it once it drops below 50 (17:57–18:15) | rank ≤ 20 → BUY; 21–50 → HOLD if owned, WATCH if not; > 50 or failed gate → EXIT/AVOID | [stated] |
| Rebalance | A fixed date each month (e.g. the 1st or 11th). Orders go in as after-market orders, never during market hours (16:37, 46:44) | `--asof` replays any rebalance date | [stated] |
| Fundamentals | "In my momentum process we don't judge the balance sheet; the safety card is diversification" (37:19) | Not scored | [stated] |

### Absolute score (single stock, 0–100) [calibration]

| Component | Max | Points |
|---|---|---|
| A. Risk-adjusted momentum | 40 | clip(MomRA / 2.0, 0, 1) × 40 |
| B. Proximity to 52WH | 20 | clip((P − 0.75) / 0.25, 0, 1) × 20 |
| C. Trend quality (45°) | 15 | R² × 15 if slope > 0, else 0 |
| D. Stage-2 alignment | 15 | 3 each for C>MA30, C>MA50, C>MA100, C>MA200, MA50>MA200 |
| E. Circuit cleanliness | 10 | 10 − 2 × circuit days (min 0); 5 if High/Low are unavailable |

Bands: ≥ 75 BUY-ZONE · 60–74.9 HOLD-ZONE · < 60 EXIT/AVOID · any gate fails → INELIGIBLE.
The bands approximate the "top 20 of 750" idea for a single stock. They are heuristics. The real rule is relative (universe mode).

### Relative score (universe mode, ≥ 150 stocks)

score_rel = 100 × [0.40·pct(MomRA) + 0.20·pct(P) + 0.15·pct(TQ) + 0.15·(stage pts/15) + 0.10·(circuit pts/10)]

pct() is the percentile rank among gate-passing stocks only. Ties are broken by MomRA.

## 3. Portfolio construction

- **Position size** [stated]: 20 stocks of equal weight. At 100% deployment that is 5% each. At 80% deployment it is 4% each. Never more than 5% in a single stock, "however good or however fraudulent the story looks" (1:06:51). Formula: w = min(5%, deployment / 20).
- **Product versions** [stated]:
  - v1: pure momentum. About 27% CAGR with a 28% max drawdown.
  - v2: 70% momentum + 30% gold. Same CAGR, about 14% drawdown.
  - v3 (current): 80% momentum + 20% gold/REIT "dry powder" that is redeployed into momentum at preset drawdown points.
- **Dry-powder ladder** [calibration]: the guest did not disclose the trigger levels. The default ladder deploys a third of the reserve at each index fall of −10%, −20% and −30% from the peak (`drypowder` sub-command). Change it to suit your own levels.
- **Combining strategies** (24:01–28:45) [stated]: momentum (32% CAGR / 28% DD) blended 50/50 with value (27% / 34%) gave about 29% CAGR / 20% DD, because the two had their drawdowns at different times. Uncorrelated sleeves (gold, debt, REITs) smooth the equity curve further.

## 4. Risk maths and checks

- **Drawdown recovery** [stated]: gain needed g = d/(1−d). A 50% fall needs +100% to recover, and a 70% fall needs +233%. Recovery also takes years, which is why preventing deep falls matters more than curing them (19:07).
- **Pain threshold** [stated]: "salt to taste, risk to capacity". Size equity so that the expected drawdown stays below the level at which you would panic. A 28% drawdown made two-thirds of clients leave in 2018-19.
- **Four pre-trade questions** [stated] (38:16). Answer all four before buying: What am I buying (system output)? When? How much (% of portfolio)? When will I exit (pre-coded)?
- **Risk/reward** [stated] (39:25): only take trades with ≥ 3:1 (`rr` sub-command). A stock that is already up 50–100% is fine. It has proven it has momentum. Minervini only buys stocks that have at least doubled.

## 5. Behaviour rules (not scored, but report them when relevant)

- Pick the strategy that suits your personality. If you want to know *why* a stock moves, you suit value investing. If you can surrender and say "the market is supreme", you suit trend following (49:43). Don't switch to whichever queue is moving faster. Value tends to beat momentum for 2–3 years after crashes, and retail investors usually switch at exactly the wrong time (51:42).
- Look at the portfolio only on rebalance days, with no trading app, and place after-market orders (46:22).
- When the urge to override the system comes up, observe it and notice where you feel it in your body. His own discretionary interventions were net negative (1:02:43).
- DIY or outsource: do it yourself only if you are curious about the subject. Otherwise index or outsource it and focus on your own profession (40:07).

## 6. Allocation guidance for savers (from the same interview)

- An SIP is a *necessity* (salary arrives monthly), not a strategy. Once the accumulated corpus is substantial, protect the lump sum with asset allocation and timing models, because a drawdown on ₹10 cr hurts far more than one on the monthly SIP (59:02).
- A 25-year-old with ₹50k/month to invest: 70% into **two** factor funds and 30% into a debt fund. Use the debt sleeve to buy equity after a fall ("you can't buy when there's blood on the street if you're fully deployed"). Avoid the large/mid/small/multi-cap "bouquet" that adds up to the Nifty 500 with no alpha (56:13).

## 7. What the framework does not do

- It makes no fundamental, forensic or governance check. Frauds are handled by the 4–5% cap and the exit rule, not by screening. A user who wants a fundamental view should pair it with a separate valuation framework and report the two separately.
- It does not predict returns. It shows where a stock sits in the momentum ranking today.
