# Screener variable map

Use the parsed Screener JSON produced by `scripts/fetch_screener.py`, not the
HTML page. Prefer `variant: consolidated`; record the variant in the output.

## Core variables

| Concept | Screener row | Formula |
|---|---|---|
| Sales growth | `Sales` in `quarters` | `latest_q_sales / same_q_last_year - 1` |
| PAT growth | `Net Profit` in `quarters` | `latest_q_pat / same_q_last_year - 1` |
| Operating margin | `OPM %` in `quarters` | `latest_q_opm / same_q_last_year - 1` |
| Operating margin, pp | `OPM %` in `quarters` | `latest_q_opm - same_q_last_year_opm` |
| Cash conversion | `Cash from Operating Activity` / `Operating Profit` | `cfo / operating_profit` |
| Leverage | `Borrowings` / (`Equity Capital` + `Reserves`) | `debt / equity` |
| Interest cover | `Operating Profit` / `Interest` | `op / interest` |
| Capex signal | `CWIP` | `cwip / sales`, and `cwip / prior_cwip - 1` |
| Ownership change | `Promoters`, `FIIs`, `DIIs` | latest minus four quarters ago |

If quarterly data is missing, the tool falls back to the latest annual period
and reports `*_basis` as annual. Never mix quarterly and annual values silently.

## Price variables

| Concept | Source | Formula |
|---|---|---|
| Current price | `scripts/fetch_prices.py` | last adjusted close `<= as_of` |
| 30-week EMA | weekly adjusted closes | EMA seeded with the first 30-week SMA |
| Return since result | price points | `current / first_close_on_or_after_result - 1` |
| 52-week high | price points | max adjusted close in the last 365 days |

The Screener `Current Price` ratio is not enough for J4 or J5. It has no history.

## What not to use

- `Stock P/E` as a gate. It is null for loss-makers and the creator explicitly
  says not to lead with valuation.
- `Promoter` change as proof of “new management”. It can be dilution, a
  reclassification, or a pledge.
- `CWIP` alone as proof of a catalyst. It is a capex signal, not an order or a
  product.
- `ROCE`/`ROE` as quality gates without checking the underlying capital base.
  They are useful context, not a substitute for the gates.

## Missing data

Screener often has gaps: early years, null OPM, missing shareholding. The tool
returns `UNKNOWN` and lowers coverage. It never fills a gap with an estimate.
