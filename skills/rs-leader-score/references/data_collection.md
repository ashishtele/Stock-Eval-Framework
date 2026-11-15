# Data collection: where each input comes from

Rule of thumb: numbers come from data files or cited sources, never from memory. Judgement fields
(catalyst, theme share, leader rank) need a source note in `evidence`. If something can't be found,
leave it null; the report shows the gap.

## Price data (feeds chart_metrics.py and compute_rs.py)
- Daily OHLCV CSV with columns `date, open, high, low, close, volume`, at least 250 sessions
  (500 is better for the fall-vs-recover check).
- Sources the user can export from: NSE bhavcopy archives, TradingView (Export chart data),
  Investing.com, broker terminals, Yahoo Finance (`.NS` tickers). This sandbox usually can't reach
  these sites, so ask the user to upload the CSVs.
- Benchmark: Nifty 500 (or Nifty 50 / Smallcap 250 to match the stock) for `rs_resisted_decline`.

## RS rating
- Best: `compute_rs.py` over the whole NSE universe (2,000+ names) from a returns CSV or a folder of
  price CSVs.
- Acceptable: a screener that already publishes a percentile RS rating (for example a Chartink /
  TradingView / MarketSmith India style 1-99 rating). Record which one in `evidence.rs_rating`, since
  definitions differ.
- Not acceptable: RS computed against a handful of stocks, or "RS line rising" used as a rating.

## Gates
| Field | Where |
|---|---|
| `price`, `price_above_200dma`, `avg_turnover_30d_cr` | chart_metrics.py |
| `market_cap_cr` | Screener.in, NSE, exchange filings |

## Technical fields
All from `chart_metrics.py`; check them against the chart:
- `stop_distance_pct`, `trade.pivot_price`, `trade.stop_price`: default window is the last 15
  sessions. If the visible consolidation is longer or shorter, rerun with `--base-days N`.
- `leg_number`: count by eye the distinct base-breakout-advance cycles since the stock left its long
  base. Also fill `gain_from_base_low_pct` (computed) so the scorer can cross-check.
- `prior_uptrend`: the script's proxy; override after looking for higher highs and higher lows.

## Theme & group
- `group_count_in_scan`, `leader_rank_in_group`: compute_rs.py output, when an `industry` column
  is supplied (Screener.in industry or NSE sector classification). Re-check leadership by date: which
  name in the group made the first new high after the last market low?
- `theme_revenue_share_pct`: segment revenue in the investor presentation or annual report.
- `global_peer_confirmation`: name the global peer/customer and its move in evidence (web search
  is fine, cite it).

## Catalyst & earnings
| Field | Where |
|---|---|
| `pat_growth_yoy_pct`, `sales_growth_yoy_pct` | quarterly results (Screener.in, BSE/NSE filings) |
| `catalyst_revenue_uplift_pct` | presentation / con-call: "capex of X Cr, peak revenue potential Y Cr" -> Y / current revenue x 100. Use the conservative phase if management splits it |
| `catalyst_months_to_impact` | commissioning date or order execution timeline |
| `quantified_guidance` | true only if management states numbers (revenue, EBITDA, margin, mix) |
| `upcycle_quarters_elapsed` | count consecutive quarters of strong YoY profit growth |

Reading a con-call, per the speaker (1:22:34-1:29:56): look for capex size and timeline, potential
revenue, new verticals or customers, order book, revenue mix shifts and named marquee clients.
Management highlights the good news itself; your job is to size it against current revenue.

## Market health
- `% above 50 DMA`, new highs/lows, advance/decline for Nifty 500: Chartink/TradingView breadth
  indicators, NSE market-statistics pages, or compute from a folder of price CSVs.
- Watchlist follow-through and false breakdowns: from the user's own watchlist over the last 4 weeks.
- Equity curve: the user's portfolio.

## Web-search fallback (no data files)

Use this when the environment can't download prices and the user hasn't uploaded CSVs. It gives
partial coverage (typically 15-45%), so the class will usually read INSUFFICIENT DATA; say so.

| Field | Where it showed up in search snippets | Tag |
|---|---|---|
| `price`, `ema50` (a site's 50 DMA is an acceptable stand-in), `price_above_200dma` | 5paisa stock pages list "50 & 200 DMA" | measured; note "50 DMA used for ema50" |
| 52-week high/low -> `gain_from_base_low_pct` = price / 52w low x 100 - 100 | ICICI Direct, IIFL, 5paisa | inferred (the 52-week low may not be the base low) |
| `market_cap_cr` | ICICI Direct FAQ, IIFL, 5paisa | measured |
| 3M/6M/1Y returns | IIFL, ICICI Direct | context only; never turn one stock's return into an RS rating |
| `price_above_200dma` without a DMA figure | a 6-month return above ~+50% makes it near-certain | inferred |
| `pat_growth_yoy_pct`, `sales_growth_yoy_pct` | results news, exchange filings | measured |

Rules:
- Use the most recent dated snippet and write the date in evidence. Search results mix dates from
  different years; discard undated numbers.
- RS rating, group count and leader rank need the whole universe. From the web, only use an RS
  figure that a screener or the source itself states, and cite it.
- Never fill `stop_distance_pct`, pivot or stop from the web: they come from the chart.
