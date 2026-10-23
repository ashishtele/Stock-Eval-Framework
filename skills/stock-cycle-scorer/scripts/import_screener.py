#!/usr/bin/env python3
"""Build a scorer input skeleton from Screener.in data.

Two input modes:
  --json  a Screener JSON file already parsed into {"tables": {...}} (this repo's
          scripts/fetch_screener.py output)
  --html  a saved Screener company page or Data Sheet tab (heuristic table parser)

The importer deliberately stops at a skeleton. It fills the financial statements,
shareholding and (when prices are supplied) valuation history, then lists what a
human still has to add: insider trades, peers, concalls and segments.

Examples:
  python import_screener.py --json data/screener/APOLLOPIPE/2026-10-13/screener-consolidated.json \
      --as-of 2026-02-05 --company "Apollo Pipes" --ticker APOLLOPIPE --sector "Pipes" \
      --prices prices.csv --out apollo.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
DATE_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$", re.I)


def clean_label(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = text.replace("+", "").strip()
    return text


def period_end(label: str) -> str | None:
    match = DATE_RE.match(label.strip())
    if not match:
        return None
    month = MONTHS[match.group(1).lower()[:3]]
    year = int(match.group(2))
    if month == 2:
        day = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    elif month in {4, 6, 9, 11}:
        day = 30
    else:
        day = 31
    return date(year, month, day).isoformat()


def number(value):
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "-", "--", "null", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def table_map(rows: list[dict]) -> dict[str, dict[str, float | None]]:
    result = {}
    for row in rows:
        label = clean_label(row.get("label"))
        if not label:
            continue
        values = {}
        for key, value in (row.get("values") or {}).items():
            day = period_end(str(key))
            if day:
                values[day] = number(value)
        if values:
            result[label] = values
    return result


def lookup(table: dict, *prefixes: str) -> dict[str, float | None] | None:
    for label, values in table.items():
        lowered = label.lower()
        if any(lowered.startswith(prefix.lower()) for prefix in prefixes):
            return values
    return None


def value_at(values: dict | None, day: str):
    return None if not values else values.get(day)


def build_from_tables(tables: dict, args) -> tuple[dict, list[str]]:
    pnl = table_map(tables.get("profit-loss") or [])
    quarters = table_map(tables.get("quarters") or [])
    balance = table_map(tables.get("balance-sheet") or [])
    cash = table_map(tables.get("cash-flow") or [])
    holding = table_map(tables.get("shareholding") or [])

    sales = lookup(pnl, "Sales")
    operating = lookup(pnl, "Operating Profit")
    pbt = lookup(pnl, "Profit before tax")
    other = lookup(pnl, "Other Income")
    interest = lookup(pnl, "Interest")
    depreciation = lookup(pnl, "Depreciation")
    net_profit = lookup(pnl, "Net Profit")
    eps = lookup(pnl, "EPS")
    equity_capital = lookup(balance, "Equity Capital")
    reserves = lookup(balance, "Reserves")
    borrowings = lookup(balance, "Borrowings")
    fixed = lookup(balance, "Fixed Assets")
    cwip = lookup(balance, "CWIP")
    cash_balance = lookup(balance, "Cash & Bank", "Cash Equivalents", "Cash")
    cfo = lookup(cash, "Cash from Operating Activity")

    if not sales:
        raise ValueError("could not find a 'Sales' row in the profit-loss table")

    annual_days = sorted(sales)
    annual = []
    for day in annual_days:
        revenue = value_at(sales, day)
        ebitda = value_at(operating, day)
        if ebitda is None and value_at(pbt, day) is not None:
            ebitda = (
                (value_at(pbt, day) or 0)
                + (value_at(interest, day) or 0)
                + (value_at(depreciation, day) or 0)
                - (value_at(other, day) or 0)
            )
        equity = None
        if value_at(equity_capital, day) is not None or value_at(reserves, day) is not None:
            equity = (value_at(equity_capital, day) or 0) + (value_at(reserves, day) or 0)
        row = {
            "period_end": day,
            "revenue": revenue,
            "ebitda": ebitda,
            "cfo": value_at(cfo, day),
            "debt": value_at(borrowings, day),
            "equity": equity,
            "capex": None,
        }
        annual.append(row)

    for idx, row in enumerate(annual):
        if idx == 0:
            continue
        prev = annual[idx - 1]
        if None in (row.get("debt"),) or fixed is None:
            continue
        if (date.fromisoformat(row["period_end"]) - date.fromisoformat(prev["period_end"])).days > 400:
            continue
        current_block = (value_at(fixed, row["period_end"]) or 0) + (value_at(cwip, row["period_end"]) or 0)
        prior_block = (value_at(fixed, prev["period_end"]) or 0) + (value_at(cwip, prev["period_end"]) or 0)
        dep = value_at(depreciation, row["period_end"]) or 0
        row["capex"] = current_block - prior_block + dep

    q_sales = lookup(quarters, "Sales")
    q_operating = lookup(quarters, "Operating Profit")
    q_interest = lookup(quarters, "Interest")
    q_dep = lookup(quarters, "Depreciation")
    quarterly = []
    if q_sales:
        for day in sorted(q_sales):
            quarterly.append(
                {
                    "period_end": day,
                    "revenue": value_at(q_sales, day),
                    "ebitda": value_at(q_operating, day),
                    "interest": value_at(q_interest, day),
                    "depreciation": value_at(q_dep, day),
                }
            )

    promoters = lookup(holding, "Promoters")
    fiis = lookup(holding, "FII")
    diis = lookup(holding, "DII")
    shareholding = []
    if promoters:
        for day in sorted(promoters):
            shareholding.append(
                {
                    "period_end": day,
                    "promoter": value_at(promoters, day),
                    "fii": value_at(fiis, day),
                    "dii": value_at(diis, day),
                }
            )

    as_of_date = date.fromisoformat(args.as_of)
    annual = [row for row in annual if date.fromisoformat(row["period_end"]) <= as_of_date]
    quarterly = [row for row in quarterly if date.fromisoformat(row["period_end"]) <= as_of_date]
    shareholding = [row for row in shareholding if date.fromisoformat(row["period_end"]) <= as_of_date]

    data = {
        "company": args.company,
        "ticker": args.ticker,
        "sector": args.sector,
        "as_of": args.as_of,
        "quarterly": quarterly,
        "annual": annual,
        "shareholding": shareholding,
        "insider_trades": [],
        "corporate_actions": [],
        "peers": [],
        "qualitative": {"concalls": []},
        "notes": [],
    }
    needs = ["insider trades (promoter buys/sells)", "peer drawdowns", "concalls", "segments/pivot"]
    if not shareholding:
        needs.append("shareholding")
    if not quarterly:
        needs.append("quarterly results")

    prices = [(day, close) for day, close in read_prices(args.prices) if day <= as_of_date]
    if prices:
        data["price"] = {
            "history": [{"date": day.isoformat(), "close": close} for day, close in prices],
        }
        valuation = build_valuation(annual, prices, eps, net_profit, cash_balance)
        if valuation:
            data["valuation"] = valuation
        else:
            needs.append("valuation history (share count / EPS missing)")
    else:
        needs.append("price history CSV (date,close)")

    data["notes"] = [
        "EBITDA uses Screener Operating Profit where present; otherwise PBT + interest + depreciation - other income.",
        "Capex = change in (fixed assets + CWIP) + depreciation; it is left blank when the prior annual is more than 400 days earlier (a missing year).",
        "Equity = equity capital + reserves. Annual P/B uses year-end price x shares (net profit / EPS).",
        "Shareholding and prices are used as supplied; the point-in-time guard still applies at scoring time.",
    ]
    data["needs"] = needs
    return data, needs


def read_prices(path: str | None):
    if not path:
        return []
    points = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_date = row.get("date") or row.get("Date")
            raw_close = row.get("close") or row.get("Close")
            if not raw_date or raw_close in (None, ""):
                continue
            try:
                points.append((date.fromisoformat(str(raw_date)[:10]), float(raw_close)))
            except ValueError:
                continue
    points.sort()
    return points


def price_near(day: date, prices, window_days: int = 15):
    best = None
    for price_day, close in prices:
        distance = abs((price_day - day).days)
        if distance > window_days:
            continue
        key = (distance, 1 if price_day > day else 0)
        if best is None or key < best[0]:
            best = (key, close)
    return best[1] if best else None


def build_valuation(annual, prices, eps, net_profit, cash=None):
    if not prices or not annual:
        return None
    pb_history = []
    pe_history = []
    ev_history = []
    for row in annual:
        day = date.fromisoformat(row["period_end"])
        price = price_near(day, prices)
        if price is None:
            continue
        row_eps = (eps or {}).get(row["period_end"])
        profit = (net_profit or {}).get(row["period_end"])
        shares = profit / row_eps if row_eps and row_eps > 0 and profit and profit > 0 else None
        if not shares:
            continue
        if row.get("equity") not in (None, 0):
            pb_history.append(
                {"date": day.isoformat(), "value": round(price * shares / row["equity"], 3)}
            )
        if row_eps and row_eps > 0:
            pe_history.append({"date": day.isoformat(), "value": round(price / row_eps, 3)})
        if row.get("ebitda") and row["ebitda"] > 0:
            debt = row.get("debt") or 0
            row_cash = (cash or {}).get(row["period_end"]) or 0
            ev = price * shares + debt - row_cash
            if ev > 0:
                ev_history.append(
                    {"date": day.isoformat(), "value": round(ev / row["ebitda"], 3)}
                )
    result = {}
    last_row = annual[-1]
    last_eps = (eps or {}).get(last_row["period_end"])
    last_profit = (net_profit or {}).get(last_row["period_end"])
    last_price = prices[-1][1]
    last_shares = (
        last_profit / last_eps
        if last_eps and last_eps > 0 and last_profit and last_profit > 0
        else None
    )
    if len(pb_history) >= 3:
        result["pb_history"] = pb_history
        result["pb_current"] = pb_history[-1]["value"]
        if last_shares and last_row.get("equity"):
            result["pb_current"] = round(last_price * last_shares / last_row["equity"], 3)
    if len(pe_history) >= 3:
        result["pe_history"] = pe_history
        result["pe_current"] = pe_history[-1]["value"]
        if last_eps and last_eps > 0:
            result["pe_current"] = round(last_price / last_eps, 3)
    if len(ev_history) >= 3:
        result["ev_ebitda_history"] = ev_history
        result["ev_ebitda_current"] = ev_history[-1]["value"]
        if last_shares and last_row.get("ebitda") and last_row["ebitda"] > 0:
            debt = last_row.get("debt") or 0
            last_cash = (cash or {}).get(last_row["period_end"]) or 0
            ev = last_price * last_shares + debt - last_cash
            result["ev_ebitda_current"] = round(ev / last_row["ebitda"], 3)
    return result or None


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[tuple[str | None, list[list[str]]]] = []
        self._section = None
        self._table = None
        self._row = None
        self._cell = None
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "section":
            self._section = attributes.get("id")
        elif tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
            self._buffer = []

    def handle_data(self, data):
        if self._cell is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._cell is not None:
            self._row.append(" ".join(self._buffer).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append((self._section, self._table))
            self._table = None
        elif tag == "section":
            self._section = None


def rows_from_table(table: list[list[str]]) -> list[dict]:
    header = None
    for row in table:
        if sum(1 for cell in row if period_end(cell)) >= 2:
            header = row
            break
    if not header:
        return []
    rows = []
    for row in table:
        if not row or clean_label(row[0]).lower() in {"", "data sheet"}:
            continue
        values = {}
        for idx, cell in enumerate(row[1:], start=1):
            if idx >= len(header):
                continue
            label = header[idx]
            if period_end(label):
                values[label] = cell
        if values:
            rows.append({"label": row[0], "values": values})
    return rows


def tables_from_html(path: str) -> dict:
    parser = TableParser()
    parser.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    known = {"profit-loss", "quarters", "balance-sheet", "cash-flow", "shareholding", "ratios"}
    result: dict[str, list[dict]] = {}
    fallback: list[dict] = []
    for section, table in parser.tables:
        if len(table) < 3:
            continue
        rows = rows_from_table(table)
        if not rows:
            continue
        if section in known:
            result.setdefault(section, []).extend(rows)
        else:
            fallback.extend(rows)
    if result:
        if "profit-loss" not in result and fallback:
            result["profit-loss"] = fallback
        return result
    if fallback:
        return {"profit-loss": fallback}
    raise ValueError("no Screener-style table with a 'Sales' row and dated columns found")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Build a stock-cycle-scorer input skeleton from Screener data.")
    parser.add_argument("--json", dest="json_path", help="Parsed Screener JSON with a tables object")
    parser.add_argument("--html", dest="html_path", help="Saved Screener page / Data Sheet HTML")
    parser.add_argument("--prices", help="CSV with date,close rows")
    parser.add_argument("--out", required=True, help="Output input JSON")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    parser.add_argument("--company", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--sector", default="Unknown")
    args = parser.parse_args()
    if bool(args.json_path) == bool(args.html_path):
        parser.error("supply exactly one of --json or --html")

    if args.json_path:
        payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
        tables = payload.get("tables") or payload
        if not isinstance(tables, dict):
            parser.error("--json must contain a tables object")
    else:
        tables = tables_from_html(args.html_path)

    data, needs = build_from_tables(tables, args)
    Path(args.out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print("still needed: " + "; ".join(needs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
