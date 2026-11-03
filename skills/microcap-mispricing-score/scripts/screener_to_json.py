#!/usr/bin/env python3
"""
Convert a Screener.in "Export to Excel" workbook (sheet "Data Sheet") into the
scorer's input JSON. Best-effort: Screener's layout can change, so the script
prints exactly which rows it found and which it could not, and you should
sanity-check the output against the website before scoring.

Usage:
  python screener_to_json.py Company.xlsx --business-type cyclical --out company.json

Derivations (Screener's units are INR crore; price in INR):
  EBITDA     = Profit before tax + Interest + Depreciation - Other Income
  net_worth  = Equity Share Capital + Reserves
  total_debt = Borrowings   (Screener includes lease liabilities here: put the
                             lease amount in market.lease_liabilities to strip it)
  cash       = Cash & Bank  (investments are NOT treated as cash by default)
  market_cap_year_end = PRICE x Adjusted Equity Shares in Cr
  ttm        = sum of the last 4 quarters where available
The qualitative, governance, forward and one_offs blocks are left for you to
fill from annual reports, concalls and your own work.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install openpyxl")

SECTIONS = {"profit & loss": "pl", "quarters": "q", "balance sheet": "bs", "cash flow": "cf"}
WANT = {
    "pl": {"sales": "sales", "other income": "other_income", "depreciation": "depreciation",
           "interest": "interest", "profit before tax": "pbt", "net profit": "pat"},
    "q": {"sales": "sales", "other income": "other_income", "depreciation": "depreciation",
          "interest": "interest", "profit before tax": "pbt", "net profit": "pat"},
    "bs": {"equity share capital": "equity", "reserves": "reserves", "borrowings": "borrowings",
           "receivables": "receivables", "inventory": "inventory", "cash & bank": "cash"},
    "cf": {"cash from operating activity": "ocf"},
}


def norm(v):
    return str(v).strip().rstrip(":").lower() if v is not None else ""


def to_year(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.year
    try:
        return int(str(v)[:4]) if str(v)[:4].isdigit() else dt.datetime.fromisoformat(str(v)).year
    except ValueError:
        return None


def parse_sheet(ws):
    data = {k: {} for k in SECTIONS.values()}
    dates = {}
    price, shares, meta = [], [], {}
    section = None
    for row in ws.iter_rows(values_only=True):
        label = norm(row[0])
        if not label:
            continue
        if label in SECTIONS:
            section = SECTIONS[label]
            continue
        if label in ("meta",):
            section = "meta"
            continue
        if label.startswith("derived"):
            section = "derived"
            continue
        if label == "price":
            price = list(row[1:])
            continue
        if label == "report date" and section in WANT:
            dates[section] = [to_year(v) if section != "q" else v for v in row[1:]]
            continue
        if section == "meta" or label in ("current price", "market capitalization", "number of shares", "company name"):
            meta[label] = row[1]
            continue
        if label.startswith("adjusted equity shares"):
            shares = list(row[1:])
            continue
        if section in WANT and label in WANT[section]:
            data[section][WANT[section][label]] = list(row[1:])
    return data, dates, price, shares, meta


def val(series, i):
    if series is None or i >= len(series):
        return None
    v = series[i]
    return float(v) if isinstance(v, (int, float)) else None


def build(path, business_type):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Data Sheet"] if "Data Sheet" in wb.sheetnames else wb.active
    data, dates, price, shares, meta = parse_sheet(ws)
    found = {s: sorted(v) for s, v in data.items()}
    missing = {s: sorted(set(WANT[s].values()) - set(v)) for s, v in data.items()}

    pl_years = dates.get("pl", [])
    bs_idx = {y: i for i, y in enumerate(dates.get("bs", [])) if y}
    cf_idx = {y: i for i, y in enumerate(dates.get("cf", [])) if y}
    annual = []
    for i, y in enumerate(pl_years):
        if not y or val(data["pl"].get("sales"), i) is None:
            continue
        pbt, it, dp, oi = (val(data["pl"].get(k), i) for k in ("pbt", "interest", "depreciation", "other_income"))
        row = {"year": y, "sales": val(data["pl"]["sales"], i),
               "ebitda": None if pbt is None else pbt + (it or 0) + (dp or 0) - (oi or 0),
               "depreciation": dp, "interest": it, "pat": val(data["pl"].get("pat"), i)}
        j = bs_idx.get(y)
        if j is not None:
            eq, rs = val(data["bs"].get("equity"), j), val(data["bs"].get("reserves"), j)
            row.update(net_worth=None if eq is None else eq + (rs or 0),
                       total_debt=val(data["bs"].get("borrowings"), j),
                       receivables=val(data["bs"].get("receivables"), j),
                       inventory=val(data["bs"].get("inventory"), j),
                       cash=val(data["bs"].get("cash"), j))
        k = cf_idx.get(y)
        if k is not None:
            row["ocf"] = val(data["cf"].get("ocf"), k)
        p, sh = val(price, i), val(shares, i)
        row["market_cap_year_end"] = round(p * sh, 2) if p and sh else None
        annual.append({k2: v for k2, v in row.items() if v is not None})

    ttm = {}
    qs = data["q"]
    if qs.get("sales"):
        idx = [i for i, v in enumerate(qs["sales"]) if isinstance(v, (int, float))][-4:]
        if len(idx) == 4:
            s = lambda key: sum(val(qs.get(key), i) or 0 for i in idx)
            ttm = {"sales": s("sales"), "pat": s("pat"), "depreciation": s("depreciation"),
                   "interest": s("interest"),
                   "ebitda": s("pbt") + s("interest") + s("depreciation") - s("other_income")}

    latest = annual[-1] if annual else {}
    out = {
        "company": meta.get("company name") or Path(path).stem,
        "as_of": dt.date.today().isoformat(),
        "units": "INR crore",
        "business_type": business_type,
        "_source": f"Imported from Screener export {Path(path).name}; verify before use.",
        "market": {"market_cap": meta.get("market capitalization"),
                   "total_debt": latest.get("total_debt"), "lease_liabilities": None,
                   "cash_and_investments": latest.get("cash")},
        "annual": annual, "ttm": ttm, "one_offs": [], "forward": {"years_out": 2},
        "peers": [], "qualitative": {}, "governance": {}, "target": {},
    }
    report = {"rows_found": found, "rows_missing": missing, "years": [r["year"] for r in annual],
              "ttm_from_quarters": bool(ttm), "market_cap_found": out["market"]["market_cap"] is not None}
    return out, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx")
    ap.add_argument("--business-type", required=True,
                    choices=["cyclical", "stable", "growth", "capex_transition", "new_age"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out, report = build(a.xlsx, a.business_type)
    Path(a.out).write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if any(report["rows_missing"].values()) or not report["market_cap_found"]:
        print("WARNING: some rows were not found; fill them manually before scoring.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
