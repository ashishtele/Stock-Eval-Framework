# Input schema

The scorer takes one company object, or a JSON list of them. Money is in **Rs crore**.
Holdings, pledges, drawdowns and target margins are **percent** (`55.2` means 55.2%).
Ratios are plain numbers. Dates are `YYYY-MM-DD`.

## Top level

| Field | Required | Notes |
|---|---|---|
| `company` | yes | Display name |
| `ticker` | yes | Exchange ticker |
| `sector` | yes | Used for the sector checklist |
| `as_of` | yes | The only date the scorer is allowed to know |
| `no_promoter` | no | Set `true` for professionally managed companies |
| `expected` | no | Acceptance-test assertions only |

## Blocks

| Block | Fields |
|---|---|
| `price` | `current, high_3y, low_52w`, or preferred `history: [{date, close}]` |
| `valuation` | `pb_current, pb_history`; `ev_ebitda_current, ev_ebitda_history`; `pe_current, pe_history, pe_forward` |
| `quarterly[]` | `period_end, revenue, ebitda`; optional `depreciation, interest, pat, gross_profit, volume, reported_on` |
| `annual[]` | `period_end, revenue, ebitda`; optional `cfo, debt, equity, cash, capex, reported_on` |
| `shareholding[]` | `period_end, promoter, fii, dii, pledge_pct` |
| `insider_trades[]` | `date, person_category, type (buy/sell), value_cr, mode` |
| `corporate_actions[]` | `date, type, value_cr`; QIP/OFS and `acquisition` are recognised |
| `peers[]` | `company, drawdown_from_3y_high_pct` |
| `segments[]` | `period_end, name, revenue, ebit`; include every segment in a period |
| `pivot` | `new_segments[], segment_period, target_revenue, target_margin_pct, target_source, pure_play_multiple, multiple_type` |
| `qualitative` | `concalls[]`, `shock_type`, `lost_share_in_downturn`, `governance_flags[]`, rubric fields and evidence lists |

`valuation` history items are numbers or `{date, value}`. Dated items are better because
points after `as_of` are dropped.

## Concall fields

Each call carries `date`, `duration_min`, `analyst_questions`, `mgmt_tone` (1-5),
`analyst_skepticism` (1-5), `market_share_gain_claimed`, `aggressive_guidance`,
`prior_guidance_met`, and `evidence` (1-3 short lines with the speaker).

## Pivot fields

`capability_proof` 0-5, `capability_built_vs_bought` (`built` / `bought` / `mixed`),
`management_track_record` 0-5, `external_tailwind` 0-5. Targets come from management
guidance; if a target is only an estimate, set `target_source` to a string containing
`estimate` or `Claude estimate`. The scorer flags it and it should not be treated as a
hard input.

## Point-in-time guard

An item is used only if it was available on `as_of`. Availability is `reported_on` if
given, otherwise `period_end` plus a lag:

| Block | Lag |
|---|---|
| quarterly | 45 days |
| annual | 60 days |
| shareholding | 21 days |
| events | from `date` |
| calls | from `date` |

Dated valuation points after `as_of` are dropped. The output reports the excluded counts.

## Minimal example

```json
{
  "company": "Example Co",
  "ticker": "EXAMPLE",
  "sector": "Industrials",
  "as_of": "2026-05-20",
  "price": {"current": 420, "high_3y": 620, "low_52w": 280},
  "valuation": {"pb_current": 2.4, "pb_history": [5.6, 4.4, 3.6, 3.0, 2.8, 2.4]},
  "quarterly": [
    {"period_end": "2025-09-30", "revenue": 100, "ebitda": 7},
    {"period_end": "2025-12-31", "revenue": 100, "ebitda": 9},
    {"period_end": "2026-03-31", "revenue": 116, "ebitda": 11}
  ],
  "annual": [
    {"period_end": "2024-03-31", "revenue": 400, "ebitda": 40, "cfo": 40, "debt": 70, "equity": 360, "capex": 30},
    {"period_end": "2025-03-31", "revenue": 440, "ebitda": 30, "cfo": 25, "debt": 80, "equity": 380, "capex": 35}
  ],
  "shareholding": [
    {"period_end": "2025-09-30", "promoter": 44, "fii": 16, "dii": 8},
    {"period_end": "2025-12-31", "promoter": 45, "fii": 16, "dii": 8},
    {"period_end": "2026-03-31", "promoter": 45, "fii": 16, "dii": 8}
  ],
  "insider_trades": [],
  "peers": [
    {"company": "P1", "drawdown_from_3y_high_pct": 55},
    {"company": "P2", "drawdown_from_3y_high_pct": 48},
    {"company": "P3", "drawdown_from_3y_high_pct": 42}
  ],
  "qualitative": {"concalls": []}
}
```

## Importer

`scripts/import_screener.py` builds a skeleton from this repo's parsed Screener JSON or a
saved Screener page. It fills the statements, shareholding, price history and (with a
`date,close` CSV) P/B, P/E and EV/EBITDA history. It cannot invent insider trades, peers,
concalls or segments, so those are listed under `needs`. The HTML parser is heuristic:
verify the tables it picks before trusting the output.
