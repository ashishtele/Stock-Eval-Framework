# Framework reference: where each rule comes from

Source: Rohan Mehta (momentum / quant PMS manager, ~20 years in markets) on the
"Conversations with Kushal" podcast. Timestamps are from that transcript (Hindi/English).
Rules tagged **[T]** are stated in the talk. Rules tagged **[A]** are assumptions added to
make the framework computable. Change them in `config` if you disagree.

## Contents
1. Philosophy
2. Universe
3. The three core criteria
4. Classification and actions
5. Pre-decided exit
6. Position sizing
7. Governance gate (18 checks)
8. Exclusions
9. Portfolio rules and diagnostics
10. Things deliberately ignored
11. Composite score (0-100)
12. Known limitations

## 1. Philosophy [T]
- "Datafication, not storification." Decisions come from data, not stories about the company (30:34, 37:18).
- The Indian market is mostly driven by momentum. Over about 17 years, Nifty 500 Momentum 50 beat the Quality, Low-Vol and Value indices (19:20-21:33).
- Sector leadership rotates every year. A top sector rarely stays on top, so buy-and-forget loses alpha (14:23-19:11).
- Momentum here means medium-term momentum. It usually lasts about 6 quarters, so the view is 1-2 years, not 3 days (23:02-23:40).
- "Conviction is the evil of wealth destruction." Be convinced of the process, not of any stock (47:11).

## 2. Universe [T]
- Use the top 750 companies by market cap (the Nifty Total Market style universe). Pick from the whole list, with no fixed tilt to large, mid, small or micro caps (27:40-28:15).
- Config: `universe_max_mcap_rank = 750`.

## 3. The three core criteria [T] (31:30-44:21)
| # | Criterion | Exact test used by the script |
|---|---|---|
| C1 | Price at an **all-time high** (lifetime, not the 52-week high, 36:55) | `(ATH - close)/ATH <= ath_tolerance_pct` |
| C2 | **Profit at an all-time high**: TTM PAT (last 4 quarters) minus one-off or exceptional items. Recurring other income stays in (40:14-41:14, 42:28) | `TTM_now >= max(all earlier TTM values)` and `TTM_now > 0` |
| C3 | **Outperformance over 52 weeks** vs the Nifty 500 **and** the stock's own sector index (41:30-43:59) | `r52(stock) > r52(N500) + margin` and `r52(stock) > r52(sector) + margin` |

- Hit rates quoted for 2010-2024 on Nifty 750: ATH price alone gave about 66% positive 1-year returns. Adding ATH profit raised it to about 75%. Adding outperformance raised it to **about 82%** (38:38-42:13).
- In the example "Nifty 500 gave 10%, the stock must give at least 12%" (41:39). This reads as an illustration, so the default margin is 0. [A]
- ATH tolerance: the speaker says "near or above ATH" counts as a super performer (1:22:34). The default `ath_tolerance_pct = 5` is an assumption. [A]
- Commodities and ETFs (the silver example, 1:16:35): profit can't be measured, so C2 becomes **"demand > supply"** from industry data, such as weekly or annual silver reports.

## 4. Classification and actions [T] (56:08-58:10, 1:22:34)
| Criteria passed | Class | If held | If not held |
|---|---|---|---|
| 3/3 | Super performer | Buy / add (averaging **up** is allowed) | Buy |
| 2/3 | Performer | Hold, do not reallocate | Don't buy (watchlist) [A: entry needs 3/3] |
| 0-1/3 | Underperformer | Exit and replace with a 3/3 stock | Avoid |

- Checks run **daily or weekly**. Quoted churn is about 22% (58:25).
- An underperformer that still shows positive alpha may be kept **only if** no new super performer is waiting. Otherwise it is replaced (1:23:33-1:24:00).

## 5. Pre-decided exit [T] (51:06-56:06)
- The exit price is decided **before buying**, on the downside.
- The simple long-term exit is a close below the **200-day EMA** (55:50). The speaker's own levels come from his website, "Exit Mantra".
- Example: silver was bought at 80 with the exit at 69. It was sold after it broke the 200-EMA and started underperforming the Nifty 500 (1:18:28, 1:18:57).
- The script exits if a held position closes below `exit_price` (default: the 200-EMA). [A: treated as a hard stop]

## 6. Position sizing [T] (1:00:45-1:02:28)
```
risk_per_position % = max_portfolio_drawdown % / number_of_positions   e.g. 18 / 15 = 1.2%
stop_distance %     = (entry - exit) / entry                          e.g. (100-80)/100 = 20%
allocation %        = risk_per_position % / stop_distance %           e.g. 1.2 / 0.20 = 6%
```
- When the stop is wider, the allocation is smaller. For example, an exit at 70 gives 4% (1:01:35).
- Sizing is dynamic, not a model portfolio. A stock that has run far above its exit gets a smaller allocation for **new** money. In the Acutaas example, the fund held about 10% but new clients got about 3% (1:01:50-1:02:28).
- `max_position_pct = 25` is a safety cap. [A] Silver once drifted to 20-23% (1:20:15).

## 7. Governance gate [T: concept, A: full list] (1:10:52-1:12:45)
- There are 18 basic checks. Each company gets a rating of **Good** (proceed), **Neutral** (discuss, for example a near-duplicate of a business already held) or **Bad** (do not buy).
- Items named in the talk: litigation or cases, very large debt (judged by sector; banks naturally carry debt), "fishy" promoter conduct, and bad mergers. Example: Patanjali / Ruchi Soya litigation meant no buy.
- The talk does not list all 18. The script adds 12 standard hygiene items to make up the set, shown without [T] in `GOVERNANCE_ITEMS`.
- The speaker says fewer than about 15 of the 750 companies have clear governance problems. Research happens **after** the 3 criteria pass, and runs on roughly 40 names, not all 750 (1:12:54).

## 8. Exclusions [T, personal / ethical, optional] (1:05:16-1:08:45)
- No investment in animal killing, liquor, tobacco, leather, hotels (F&B revenue depends on liquor and non-veg) or casinos.
- This is close to the BSE "Satvik" index idea. `apply_sin_filter` is on by default and can be turned off with `--no-sin-filter`.

## 9. Portfolio rules and diagnostics [T]
- Hold **10-20 stocks**, typically 15-18 (59:56, 1:04:08-1:04:38).
- **80% of the portfolio should be in the top 150** of the universe, ranked by 52-week return (the "EM rank") (1:13:18-1:13:39).
- Only 30-40% of holdings need to produce big alpha (1:15:45).
- The weekly breakdown covers: weight, MTD return, MTD alpha vs the benchmark, and EM rank. It is grouped into Super performer, Performer and Underperformer buckets (1:22:00-1:27:47).
- An **underperformer with negative alpha this month gets trimmed** (1:23:17).
- **Cash has alpha too.** `cash_alpha = -cash_weight x benchmark_return`. Example: 14% cash in a +11% month cost 1.4% of alpha (1:24:09-1:24:39).
- Behaviour rules: no minimum holding period, no sector or market-cap bias, no averaging down, no early profit-booking, no falling in love with stocks, no entry without a decided exit (1:08:45-1:09:35).

## 10. Deliberately ignored [T]
- **P/E and valuation** have zero weight. Examples: Hitachi Energy (Power India) bought at about 250x trailing earnings, and Acutaas at 70-90x (44:43-46:55).
- Narratives, management quality as a buy reason, promoter assurances, news and macro ("left-hand problems") are ignored (31:57-35:23, 47:49-50:43, 1:34:37).

## 11. Composite score (0-100) [A]
The talk gives a 0-3 count, not a 0-100 score. The script adds a composite for ranking candidates:
```
points = 25*C1 + 25*C2 + 25*C3 + 25*rank_pct      (rank_pct = 1 - (EM_rank-1)/(universe-1))
score  = points / available_points * 100          (available = 100, or 75 if EM rank missing)
```
The **class and action always come from the 0-3 count and the gates**. The composite only breaks ties between candidates with the same count.

## 12. Known limitations
- A true lifetime ATH needs a price history back to listing. Without it, the script warns that ATH is measured only within the supplied series.
- C2 needs enough quarters to cover the earlier TTM peak. For cyclicals, supply at least 5 years of data.
- Index membership changes over time (the speaker admits this survivorship issue at 37:49).
- Hit-rate figures are the speaker's own backtest. They were not independently checked.
