# Context file schema

The context file is optional. It carries evidence that Screener cannot see.
Every field is a claim: leave it out if you cannot source it.

```json
{
  "theme": {
    "name": "EMS",
    "stage": "TRAIN_C",
    "expiry_risk": "low | medium | high",
    "evidence": "policy, order or industry source"
  },
  "relative_strength": {
    "benchmark": "NIFTY",
    "period_months": 6,
    "stock_return": 0.34,
    "benchmark_return": 0.12,
    "source": "price files or manual source"
  },
  "ownership": {
    "promoter_change_4q": 0.0,
    "institutional_change_4q": 3.0,
    "fii_change_4q": 2.0,
    "dii_change_4q": 1.0,
    "source": "Screener shareholding"
  },
  "base": {
    "start": "2026-06-01",
    "end": "2026-09-01",
    "breakout": true,
    "volume_multiple": 1.8,
    "support": 430.0,
    "resistance": 480.0,
    "source": "chart observation"
  },
  "concall": {
    "date": "2026-08-14",
    "congrats_count": 7,
    "guidance": "raised | maintained | cut | unknown",
    "source": "Q1 FY27 concall"
  },
  "entry": {
    "first_inflection": "2026-08-14",
    "return_since": 0.18,
    "extended": false,
    "plan": "buy on first base breakout",
    "source": "chart and result date"
  },
  "valuation": {
    "pe": 42.0,
    "note": "context only, not a gate"
  },
  "time_horizon_years": 3,
  "market_stage": "TRAIN_A | TRAIN_B | TRAIN_C | UNKNOWN",
  "notes": ["anything that does not fit above"]
}
```

## Status rules

The tool computes a separate status:

- `WARNING` — high theme expiry risk, negative relative strength, cut guidance,
  or an extended entry.
- `SUPPORTIVE` — at least two positives among: non-high theme, positive relative
  strength, base breakout, raised guidance, non-extended entry.
- `NEUTRAL` — context supplied but not enough evidence either way.
- `MISSING` — no context supplied.

The status never changes `stage`, `j_count` or `quality_status`.

## Auto-computed fields

If price files are supplied, the tool also reports:

- distance from the 52-week high
- distance from the loaded 5-year high
- TTM sales and PAT
- relative return when `--benchmark-json` is supplied
- promoter and institutional ownership change from Screener

Manual values override the auto-computed values for relative strength and
ownership.
