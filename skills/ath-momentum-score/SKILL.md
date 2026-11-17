---
name: ath-momentum-score
description: >-
  Score Indian stocks (or a commodity ETF) on a rule-based momentum framework from Rohan Mehta's podcast. It has three binary criteria: price at all-time high, TTM profit (ex one-offs) at all-time high, and 52-week outperformance vs Nifty 500 and the sector index. Gates cover the top-750 universe, an 18-point governance check and an optional sin-business filter. It also sets a pre-decided 200-EMA exit, risk-budget sizing and portfolio diagnostics. A deterministic Python script gives each stock a 0-3 count, a class (super performer / performer / underperformer), a buy/hold/exit action and a 0-100 score, with every input echoed so the result can be checked. Use it whenever the user wants to screen, score or rank stocks for momentum, all-time-high breakouts, buy/hold/exit decisions, ATH-profit checks, position sizing from a stop, or a review of a portfolio's holdings, even if they just say "run my framework" or "is X a buy".
---

# ATH Momentum Score

This skill turns a podcast's stock-picking talk into a repeatable test. The point is
*verifiability*: every verdict reduces to three yes/no tests plus gates, computed by
`scripts/score.py` from numbers you can source and audit. Do not score by judgement.
Gather the data, run the script and show its rule table.

Read `references/framework.md` when you need the origin of a rule, a timestamp, or the
list of assumptions. It also documents the commodity-ETF variant.

## The model in one screen
- **Universe:** top 750 by market cap.
- **C1:** close within `ath_tolerance_pct` (default 5%) of the **lifetime** all-time high.
- **C2:** TTM PAT, minus exceptional/one-off items, at or above every earlier TTM value. For commodity ETFs, use demand > supply instead.
- **C3:** 52-week return > Nifty 500 52-week return **and** > the sector index's 52-week return.
- **Class:** 3/3 is a super performer (buy/add). 2/3 is a performer (hold, don't add; don't initiate). 0-1/3 is an underperformer (exit & replace).
- **Gates:** in universe; no "bad" governance item; not a sin business (animal killing, liquor, tobacco, leather, hotels, casinos), and this filter can be switched off.
- **Exit:** decided before entry. The default is a close below the 200-EMA.
- **Sizing:** `allocation% = (max_drawdown% / n_positions) / stop_distance%`. Example: 18/15 = 1.2% risk; a 20% stop gives 6%.
- **Portfolio:** 10-20 holdings; at least 80% of weight in the top 150 by 52-week return; trim underperformers with negative MTD alpha. Cash counts as alpha: cash weight × −benchmark return.
- **Ignored on purpose:** P/E, narratives, management promises, news.

## Workflow

### 1. Pin down the request
Work out which stocks, whether each is **held** (this changes the 2/3 action) and the as-of date.
If the user wants sizing, ask for the portfolio value. Ask whether the sin filter applies;
it is the speaker's personal ethics, so default it on but mention it. Don't block on
questions the defaults already answer.

### 2. Gather data, and record where each number came from
Per stock, collect the data below. Prefer primary or near-primary sources and note the URL and date in `sources`.

| Field | Where to get it |
|---|---|
| Close, 52w high, 1-year price return | `https://www.screener.in/company/<SYMBOL>/consolidated/` gives "Current Price", "High / Low" and the "Stock Price CAGR → 1 Year" row. If the quarterly table is empty, fall back to the standalone page (drop `/consolidated/`) |
| Lifetime ATH | Needed **only** if close ≥ 95% of the 52w high. The lifetime ATH can't be lower than the 52w high, so a stock >5% below its 52w high already fails C1 and you can pass the 52w high as `ath`. Otherwise web-search "<stock> record high" and cite the source |
| 200-day average | Broker technical pages (5paisa stock-update pages, Trendlyne technicals). Record whether it is an SMA or an EMA, because the two can land on opposite sides of the price |
| Quarterly PAT (13 quarters on Screener) plus `other_income` and `pbt` | Screener "Quarterly Results": the Net Profit, Other Income and Profit before tax rows |
| Longer profit history | Screener "Profit & Loss" → Net Profit, 10+ years. Pass it as `annual_pat`, but only the full years that end **before** the first quarter you supply. Skip TTM and odd-length (e.g. 15-month) periods |
| Nifty 500 and sector index 1-year returns | `https://www.screener.in/company/<CODE>/` uses codes CNX500, CNXIT, CNXAUTO, BANKNIFTY, CNXENERY, CNXMETAL, NFTCONSDUR, CNXCONSUMP, NFTCHEMIC, CNXPSUBANK. Cross-check against the niftyindices.com factsheets; use the same source and date as the stocks |
| Universe membership | The Screener "Part of" list shows whether the stock is in Nifty Total Market (pass `in_universe: true/false`). A market-cap rank, if you have it, overrides this |
| Governance items | Annual report, exchange filings, news search, credit-rating sites |

Yahoo Finance and Screener's chart API are blocked for fetching. Don't try to work around a
blocked source; use the substitutes above.

**One-off items.** Screener has no "exceptional items" row; it folds them into Other Income.
When you can't name the one-offs from filings, run the scorer twice: once as reported and once
with `--oneoff-proxy`. The proxy strips (Other Income − median) × 0.75 in quarters where
OI < 0 or OI > 2× its median, and caps PAT at PBT × 0.75 when a tax credit makes PAT > PBT.
Report a C2 that flips between the two runs as a judgement call, not a clean pass or fail.

Rules that keep the output trustworthy:
- **Never invent a number.** If a value can't be found, leave it out. The script marks that criterion `UNKNOWN`, counts it as not passed and adds a warning to the action. Tell the user what's missing.
- Strip **one-off** items from PAT (asset or land sales, stake sales, write-backs). Keep **recurring** other income (treasury income, regular dividends). If you aren't sure, record the choice in `notes`.
- The ATH must be the **lifetime** high, not the 52-week high. If your series is short, either supply `price.ath` from a long-history source or accept the script's warning.
- Use the **same as-of date** for the stock and the benchmark returns.
- For banks and NBFCs, judge "excess debt" by sector norms. Leverage is their business.

### 3. Build the input JSON
Copy `assets/input_template.json` and fill it in. Each stock accepts **either** summary
price fields (`close`, `ath`, `ema200`, `return_52w_pct`) **or** a `series`, given as an inline
`[[date, close], ...]` list or a `{"csv": path}`. When you supply a series, the script computes
the ATH, the 200-EMA and the 52-week return itself. For profit, supply `quarterly_pat` (oldest to newest,
with `exceptional`) or a precomputed `ttm_pat_history`. For holdings, add `held: true`,
`weight_pct` and `return_mtd_pct`, and put `benchmark_return_mtd_pct` and `cash_pct` under `portfolio`.

### 4. Run the scorer
```bash
python <skill-dir>/scripts/score.py input.json --json result.json
# options: --ath-tol 3   --margin 2   --no-sin-filter   --oneoff-proxy
```
C2 allows a 0.5% tolerance (`profit_tolerance_pct`) because quarterly sums and annual
figures are rounded separately.
The script uses only the Python standard library. It prints a markdown report: a summary table, a
per-stock rule table (gates G1-G3, criteria C1-C3, exit X), sizing arithmetic and
portfolio diagnostics.

### 5. Present the result
- Lead with the summary table: stock, n/3, class, score, action.
- For each stock, show the rule table **as the script printed it**, so the user can check each input.
  Add a short plain-language reason ("fails C3: 52-week return 6% vs Nifty 500 8.5%").
- List the sources and any UNKNOWN fields with what's needed to resolve them.
- Remind the user that the class and action come from the 0-3 count and the gates. The 0-100 score only
  ranks names with the same count.
- Close with one line saying this is a rule-based screen from a podcast framework, not
  investment advice. Keep it to one line; the table is the substance.

Save the input JSON and the report so the user can re-run them later with updated numbers.

## Edge cases
- **Just listed or short history:** C1 and C2 may be unreliable. Flag this and don't pass on partial data.
- **Loss-making company:** C2 fails, because TTM must be > 0 even if it's the "highest" loss.
- **Sector index unavailable:** C3 checks only the Nifty 500, and the inputs show `sector=n/a`. Say so.
- **Price below the exit level:** the script gives no position size, because there is no valid risk budget, even if 3/3 pass.
- **Commodity or ETF:** set `asset_type: "commodity_etf"` and `demand_exceeds_supply`, with `demand_source`.
- **User wants different thresholds:** change `config` or the CLI flags. Don't edit the script logic.
  Report the thresholds used.
