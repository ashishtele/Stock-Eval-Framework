#!/usr/bin/env python3
"""Fetch daily adjusted prices from Yahoo Finance and store a dated snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "prices"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Snapshot Yahoo Finance daily prices.")
    parser.add_argument("symbol", help="Yahoo symbol, e.g. APOLLOPIPE.NS")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Snapshot date (YYYY-MM-DD)")
    parser.add_argument("--lookback-years", type=float, default=5.0)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    as_of = parse_date(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    start = as_of - timedelta(days=int(args.lookback_years * 365.25) + 10)
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(as_of.year, as_of.month, as_of.day, 23, 59, tzinfo=timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{args.symbol}"
        f"?period1={period1}&period2={period2}&interval=1d&events=div%2Csplit"
    )
    response = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    quotes = result["indicators"]["quote"][0]
    adjusted = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose") or quotes["close"]

    points = []
    for stamp, close, adj in zip(timestamps, quotes["close"], adjusted):
        if close is None or adj is None:
            continue
        day = datetime.fromtimestamp(stamp, tz=timezone.utc).date()
        if day > as_of:
            continue
        points.append({"date": day.isoformat(), "close": round(float(close), 4), "adjusted": round(float(adj), 4)})

    if not points:
        print("no price points returned", file=sys.stderr)
        return 1

    closes = [point["adjusted"] for point in points]
    peak_index = max(range(len(points)), key=lambda i: closes[i])
    trough_index = min(range(len(points)), key=lambda i: closes[i])
    current = points[-1]

    payload = {
        "symbol": args.symbol.upper(),
        "as_of": as_of.isoformat(),
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "currency": result.get("meta", {}).get("currency"),
        "source_url": url,
        "lookback_years": args.lookback_years,
        "points": points,
        "stats": {
            "current_date": current["date"],
            "current_adjusted": current["adjusted"],
            "peak_date": points[peak_index]["date"],
            "peak_adjusted": points[peak_index]["adjusted"],
            "trough_date": points[trough_index]["date"],
            "trough_adjusted": points[trough_index]["adjusted"],
            "drawdown_from_peak": round(1 - current["adjusted"] / points[peak_index]["adjusted"], 6),
            "recovery_from_trough": round(current["adjusted"] / points[trough_index]["adjusted"], 6),
        },
    }

    out_dir = Path(args.out).resolve() / payload["symbol"] / as_of.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "prices.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"saved: {json_path}")
    print(f"points: {len(points)}  {points[0]['date']} .. {current['date']}")
    print(
        "peak {peak_date} {peak_adjusted}  trough {trough_date} {trough_adjusted}  now {current_adjusted}".format(
            **payload["stats"]
        )
    )
    print(
        f"drawdown {payload['stats']['drawdown_from_peak']:.2%}  "
        f"recovery {payload['stats']['recovery_from_trough']:.2f}x"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
