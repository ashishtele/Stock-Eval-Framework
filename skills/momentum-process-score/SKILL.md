---
name: momentum-process-score
description: Score and rank stocks (built for Indian NSE/BSE equities) on a deterministic, price-only momentum framework, "Process over Prediction", distilled from Manish Dhawan / Mystic Wealth. Gives an auditable 0-100 score and, for a universe, a top-20 buy / exit-below-rank-50 decision. It covers Stage-2 trend (price above 30/50/100/200-DMA), 6m/12m rate of change punished by volatility, distance from the 52-week high, 45-degree trend consistency, the circuit-stock filter, 4-5% position sizing, the 80/20 momentum-plus-gold dry-powder ladder, drawdown recovery maths and the 3:1 risk/reward check. Use it whenever the user asks whether a stock is in momentum or trending, wants to screen, rank or rebalance a momentum portfolio, says "should I hold or exit X", shares price CSVs or NSE/Yahoo/TradingView exports for scoring, or mentions momentum investing, trend following, relative strength, 52-week-high stocks, Nifty 750 / Nifty 200 momentum, or Mystic Wealth, even if they don't say "score".
---

# Process-over-Prediction Momentum Score

This framework turns one practitioner's systematic momentum process into formulas that anyone can check. Its core idea: **ignore stories and follow a coded process**. Buy what ranks in the top 20, hold while it stays in the top 50, exit when it falls out, and size every position at 4-5% so no single mistake hurts much. The guest says openly that about 60% of picks lose money and a few outliers pay for everything. Present results in that spirit: a score describes where a stock sits in the momentum ranking today. It does not predict its future and it is not a quality verdict.

The provenance of every rule (with interview timestamps), and which numbers are the guest's own versus calibration choices, is in `references/framework.md`. Read it when the user asks "why this rule?", wants to change a threshold, or asks about allocation, SIPs or behaviour.

## Workflow

### 1. Get price data

The script needs daily **split/bonus-adjusted** OHLC(V) data with at least 253 trading rows. About 300 or more (15 months) is better. Accepted inputs:
- one CSV per stock (the file name becomes the symbol), or
- one long CSV with a `Symbol` column.

Column names are matched case-insensitively (`Date, Open, High, Low, Close, Volume`, NSE bhavcopy style `CLOSE_PRICE`, `Adj Close`, and so on). Dates like `2025-03-21` or `21-Mar-2025` both work.

If the user has no file, ask them to export one from NSE "Historical data", Yahoo Finance (`TICKER.NS`), TradingView, or their broker. Don't invent prices. Every point of the score has to trace back to real data, otherwise "verifiable" means nothing.

Optional `meta.csv` with columns `symbol, in_nifty_tm, mcap_cr, mcap_rank, held`. It feeds the universe gate and the hold/exit logic. For a single stock you can pass `--mcap-cr` or `--mcap-rank` instead.

- **Universe gate (G1):** prefer `in_nifty_tm` (yes/no). It means membership of the Nifty Total Market index, which is the guest's "Nifty 750". Screener.in lists it under "Part of … Nifty Total Market" on each company page. Use `mcap_rank` if that's what you have. The ₹3,000 cr `mcap_cr` cutoff is only a rough fallback: the real cutoff moves at every index rebalance, and Wonderla, at ₹3,026 cr, is not a member.
- **Key every file and meta row by NSE ticker, not company name.** Companies get renamed (Shriram Pistons is now SPR Auto Technologies, still ticker SHRIPISTON). The scorer warns when price files and meta rows don't match. It also warns about any held symbol that has no price data, because a holding that can't be scored needs an exit review.

### 2. Run the scorer

```bash
python ${CLAUDE_SKILL_DIR}/scripts/momentum_score.py score \
    --csv RELIANCE.csv TCS.csv            # or --dir prices/   or --csv long.csv
    [--meta meta.csv] [--mcap-cr 8000]    # universe gate
    [--held TCS INFY]                      # current holdings -> HOLD/EXIT logic
    [--deployment 0.8] [--asof 2026-10-31] # equity fraction; replay a rebalance date
    --out /path/to/outputs/momentum_report
```

This writes `momentum_report.md` (human report) and `.json` (full audit trail: config, weights, every metric). Run `python …/momentum_score.py selftest` once if you change the code. It checks the formulas against hand calculations.

The two modes are chosen automatically:
- **Absolute mode** (fewer than 150 stocks): each stock gets a 0-100 score and a band. ≥ 75 BUY-ZONE, 60-75 HOLD-ZONE, < 60 EXIT/AVOID, any gate failed means INELIGIBLE. Use it for "is X in momentum?" or comparing a handful of names.
- **Rank mode** (150 or more stocks, ideally the whole Nifty 750): percentile-weighted relative score, then rank 1…N. Top 20 → BUY, 21-50 → HOLD if owned / WATCH if not, > 50 or a failed gate → EXIT/AVOID. It also prints the post-rebalance target portfolio (held names still ≤ 50 kept first, then filled from the top). This is the guest's actual process. Absolute bands are only an approximation of it, so say which mode was used.

### 3. The score (what to explain to the user)

Five hard gates. If any one fails, the stock is ineligible whatever its score:
G1 universe (Nifty 750 / mcap proxy) · G2 Stage-2 (Close > SMA30, 50, 100, 200) · G3 R12 > 0 and R6 > 0 · G4 Close/52WH ≥ 0.75 · G5 ≤ 10 locked-circuit days in a year.

Composite out of 100:

| Component | Pts | Formula |
|---|---|---|
| A. Risk-adjusted momentum | 40 | MomRA = 0.5·R6/σ + 0.5·R12/σ (σ = annualised stdev of daily log returns, 252d); pts = clip(MomRA/2, 0, 1)·40 |
| B. Proximity to 52-week high | 20 | clip((Close/H52 − 0.75)/0.25, 0, 1)·20 |
| C. 45° trend quality | 15 | R² of ln(Close) vs time over 126d, ·15 (0 if the slope is negative) |
| D. Stage-2 alignment | 15 | 3 each: C>MA30, C>MA50, C>MA100, C>MA200, MA50>MA200 |
| E. Circuit cleanliness | 10 | 10 − 2 × locked-circuit days (1y) |

The report prints every input value next to its formula, so the user can rebuild any number in Excel. When you present results, lead with the score, the decision and the gate table. Then show the component table. Point out any warnings (missing High/Low, a suspected unadjusted split, short history).

### 4. Portfolio and risk helpers

Use these when the conversation moves from "which stock" to "how much / when":

```bash
python …/momentum_score.py size --deployment 0.8 --n 20 --capital 2500000   # 4% each, max 5%
python …/momentum_score.py recovery --drawdown 0.4 --cagr 0.12             # +66.7% needed, years to break even
python …/momentum_score.py rr --entry 520 --stop 470 --target 690          # >= 3:1 required
python …/momentum_score.py drypowder --peak 26200 --current 21800 --reserve 0.2 --ladder 0.1,0.2,0.3
```

The dry-powder ladder levels are a calibration. The guest only said "preset drawdown points", so tell the user they can set their own.

### 4a. Pre-screen when only snapshot data is available (e.g. Screener.in)

When you can't get a daily price series, but a company page such as Screener.in gives the price, 52W high/low, market cap, index membership and 1-year return, build a CSV with the columns `symbol,price,high52,mcap_cr,in_nifty_tm,ret1y[,ret6m]` (returns as decimals) and run:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/momentum_score.py snapshot --file snap.csv --out snapshot
```

This checks G1, G3 (R6 too, if you supply it) and G4, computes the proximity points, and prints the range of scores still possible. Passing stocks get a tier:
- **PASS-STRONG:** 1Y ≥ 20% and Close/H52 ≥ 0.85.
- **PASS-MARGINAL:** everything else that passes. These are the borderline names, like Persistent at +4%, that would rank low in the real process.

Both tier thresholds are calibration choices. A failed gate here is definitive. A pass is only a pre-screen, so say clearly that a full score needs daily prices.

### 4b. Historical replay (backtest one stock)

To see how the rules would have traded a stock in the past ("would it have caught X's run and got out before the crash?"), run:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/replay.py --csv ATGL.csv --start 2016-01-01 --out replay
```

It rescores the stock at every month-end using only the data available on that date, then reports the trades it would have made, its win rate, how its gain and maximum drawdown compare with buy & hold, and how much of the time it was invested. Entry and exit use the absolute bands, so this is a single-stock stand-in for the full universe ranking.

### 5. Report format

Keep it short and lead with the numbers:
1. One line per stock: **Symbol, score/100 (or rank), decision**.
2. A gate table and a component table for each stock (copy them from the script output; don't recompute by hand).
3. Position size if relevant (4% at 80% deployment).
4. Caveats, briefly: price-only framework with no fundamental or governance check; around 60% of individual picks are expected to lose; the edge comes from following the rules across ~20 positions with fixed exits. This is not investment advice, and the user makes the call.

If the user also wants a fundamental or valuation view, run that as a separate analysis and keep the two scores apart. Mixing a story into the momentum score breaks the point of the framework.

## Things to avoid

- Don't override the output with news or an opinion ("but the promoter is buying…"). Report the system's answer. Context can go in a separate note.
- Don't use unadjusted prices. A bonus or split looks like a crash and wrongly fails G2 and G4. The script warns about daily moves over 35%.
- Don't apply rank rules (top 20 / exit at 50) to a 5-stock list. That is what absolute mode is for.
