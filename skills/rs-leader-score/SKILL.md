---
name: rs-leader-score
description: Score any listed stock (built for NSE/BSE, works for any market) 0-100 on a relative-strength "leader" framework for swing and positional trades. It runs an RS80 universe scan (price above 200 DMA, RS percentile 80+, turnover, market cap), scores the past-winner chart template (prior uptrend, long base, tight right side, volume dry-up and spike, 50 EMA respect), the stage or leg of the move, theme and group leadership, and the earnings catalyst. It adds a market-breadth regime and builds a trade plan with stop %, position size (risk% x 100 / stop%) and reward multiple. Deterministic Python scripts make every point auditable. Use this whenever the user wants to pick, screen, rank, shortlist or check stocks for momentum, breakouts, RS rating, sector leaders, "first or second leg", base or VCP-style setups, CANSLIM or Minervini-style selection, position sizing, or market breadth, or asks whether a stock is a leader, late, or worth buying on a breakout, even if they don't say "score".
---

# RS Leader Setup Score

A formula version of a trader's stock-selection talk: find the strongest stocks in the strongest
themes early in their move, enter from a tight base where risk is small, and size so that a wrong
call costs about 1%. The maths is in `scripts/`; every weight and threshold is in
`scripts/framework_config.json`. Read `references/framework.md` for the reasoning and transcript
source of any rule, and `references/data_collection.md` when gathering inputs.

## Workflow

1. **Market regime first.** Fill a market file (`python scripts/score_setup.py --market-template`)
   from breadth data and run `python scripts/score_setup.py --market-only market.json`. The regime
   sets risk per trade and max position. Skip only if the user just wants a single stock checked,
   and say the overlay is missing.

2. **Universe and RS rating.** If the user has whole-market data, run
   `python scripts/compute_rs.py returns.csv --out scan.csv` (or `--prices-dir`). It prints the
   RS80 shortlist and which industries have the most names (theme strength). Otherwise accept a
   published RS rating and note its source. Never estimate an RS rating from one chart.

3. **Technical inputs.** For each candidate with an OHLCV CSV:
   `python scripts/chart_metrics.py SYMBOL.csv --benchmark INDEX.csv --out tech.json`.
   Copy `inputs` and `trade` into the stock file (`--template` gives a blank one). Look at the chart
   and override `leg_number`, `prior_uptrend` or `--base-days` if the proxies are wrong.

   **No data files?** Follow the web-search fallback in `references/data_collection.md`: it lists
   which sites show which fields (for example 50/200 DMA, 52-week range). Expect low coverage and
   say so.

4. **Theme and catalyst research.** From investor presentations, con-call transcripts and results
   (uploaded or found via search), fill the theme and catalyst fields and write the source of each
   in `evidence`. Leave unknowns null rather than guessing. These fields move the score most, so
   don't fill them from memory.

   Tag how solid each input is, because the report splits points by data quality:
   - start the evidence note with `inferred:` when you derived it (e.g. "price above 200 DMA,
     inferred from a +166% 6-month return");
   - write `ASSUMED` for placeholders;
   - when a source only describes something in words ("huge volume", "tight base", "RS above 80"),
     enter the word itself (`"high"`, `"tight"`, `"above_80"`), not a number you made up. The
     allowed words per field are under `qualitative` in the config, and each scores at the bottom
     of its band.

5. **Score.**
   `python scripts/score_setup.py stock.json --market market.json --md report.md --json result.json`
   For several names: `--batch a.json b.json ... --market market.json --md ranking.md`.

6. **Report back** in this order:
   - headline score, classification and market regime. Below 70% coverage the headline is the
     conservative score and the class reads "INSUFFICIENT DATA - provisional: ...". Lead with that,
     not with the re-based number, which only shows how the available evidence leans;
   - any holding alerts (below the 50 EMA, RS under 80), since they matter to someone who owns it;
   - data coverage and the points split by quality (measured / inferred / qualitative / assumed);
   - the caps or flags hit (loose base, theme tourist, late leg, chasing past the pivot);
   - the two or three rules that drove the score up and down;
   - the trade plan: entry, stop %, position size and the formula behind it, reward multiple;
   - the open questions that would change the result most.
   Offer the markdown report as a file for the full rule-by-rule audit. State plainly that this is
   the mechanical output of a framework, not a recommendation, and that inputs should be verified.

## Scoring at a glance

Gates (all required, else REJECT): price > 200 DMA, RS >= 80, 30-day turnover >= 10 Cr, mcap >= 500 Cr, price >= Rs 10.

| Pillar | Points | Core idea |
|---|---|---|
| Relative strength | 15 | RS percentile; held up while the index fell |
| Technical template | 30 | prior uptrend, long base, tight right side (stop <= 8%), volume dry-up, volume spike, no 50 EMA breaks, fast recovery |
| Stage / timing | 15 | leg 1-2 only for investment; short rests; 1,000-10,000 Cr sweet spot |
| Theme & leadership | 20 | many group names in the scan; first or second mover; theme is real revenue; global peer confirms |
| Catalyst & earnings | 20 | PAT and sales growth; capex/order uplift vs revenue; time to impact; quantified guidance; early in the earnings cycle |

Classes: BUY A (>= 75, leg <= 2), BUY B (60-74, leg <= 2), BUY-GRADE pending pivot/stop (buy score
but no base high/low yet), TRADE ONLY (>= 60, leg 3+), WATCHLIST, REJECT. Below 70% coverage the class
becomes "INSUFFICIENT DATA - provisional: <class>" (no provisional grade below 20%). Caps (applied to every score shown): stop > 8% ->
max 59; theme < 10% of revenue -> max 59; repeated 50 EMA breaks -> max 69.

Holding alerts (not scored): price below the 50 EMA (give `ema50` and `price`, or `below_50ema_now`),
RS below 80, late leg with a loose base.

Position size % = risk% x 100 / stop%. With 1% risk and a 5% stop that's 20%.

## Other tools
- **Journal edge:** `python scripts/edge_calc.py --trades journal.csv` (column `pnl_pct`) or
  `--win 45 --gain 22 --loss 5`. Edge = (win%/loss%) x (avg gain/avg loss); above 2 is good.
- **Tuning:** change bands or weights in `framework_config.json`, not in the code, then run
  `python -m unittest discover -s tests`. The tests check that weights still total 100 and that the
  transcript's own worked numbers (20% size at 5% stop, edge 4, top 1% = RS 99) still hold.

## Judgement notes worth passing on
- A high RS rating is not "too late". A stock flat in a falling market rates highly too. Lateness is
  measured by the leg and the gain from the base low, not by RS.
- In weak markets keep scanning: the short list of names holding up is where the next leaders come from.
- Buying the 3rd or 4th name in a theme because the leaders "ran away" is the classic mistake; when
  the second name moves, the leader is resting, not finished.
- Exits are stop-based (base low, then a close below the 50 EMA), not valuation-based.

## Examples
`assets/examples/` has four stock files and two market files reconstructed from the talk
(STL leg 1 leader, MTAR late stage, Paramount theme tourist, JG Chemicals capex catalyst). Fields
marked ASSUMED in `evidence` are placeholders, so use them to understand the logic, not as data.
