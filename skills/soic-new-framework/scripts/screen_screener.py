#!/usr/bin/env python3
"""Deterministic Screener.in screen for the SOIC NEW / J-curve / Train B-C idea.

The screen has two layers:

1. A creator-stated J-curve scan:
   sales growth >= 20%, PAT growth >= 30%, operating-margin expansion >= 10%,
   return since the latest result >= 5%, and price above the 30-week EMA.

2. Repository-derived quality gates and stage rules. These are not the
   creator's words. They exist to stop a high-growth, low-quality name from
   being presented as a candidate.

Catalysts are optional tags. Without them the tool can only return
CANDIDATE / WATCH / TRAIN_A; it never guesses TRAIN_B or TRAIN_C.

Examples:
  python screen_screener.py data/screener/APOLLOPIPE/2026-10-13/screener-consolidated.json \
      --price-json data/prices/APOLLOPIPE.NS/2026-10-13/prices.json --summary

  python screen_screener.py assets/example_screener.json \
      --price-json assets/example_prices.json \
      --result-date 2026-08-14 --catalyst new_capex --md example.md
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_ROOT / "assets" / "config.json"
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
DATE_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$", re.I)


def reconfigure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def clean_label(value) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("+", "").strip()


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    text = re.sub(r"[^\d.\-+]", "", text)
    if text in {"", "-", "--", "+", "."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def period_end(label: str) -> str | None:
    match = DATE_RE.match(str(label or "").strip())
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


def table_map(rows: list[dict]) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for row in rows or []:
        label = clean_label(row.get("label"))
        if not label:
            continue
        values: dict[str, float | None] = {}
        for key, value in (row.get("values") or {}).items():
            day = period_end(str(key))
            if day:
                values[day] = parse_number(value)
        if values:
            result[label] = values
    return result


def find_row(table: dict, *prefixes: str) -> dict[str, float | None] | None:
    for label, values in table.items():
        lowered = label.lower()
        if any(lowered.startswith(prefix.lower()) for prefix in prefixes):
            return values
    return None


def latest_value(values: dict[str, float | None] | None, as_of: str):
    if not values:
        return None, None
    days = [day for day, value in values.items() if day <= as_of and value is not None]
    if not days:
        return None, None
    day = max(days)
    return day, values[day]


def prior_year_value(values: dict[str, float | None] | None, day: str | None):
    if not values or not day:
        return None
    current = date.fromisoformat(day)
    try:
        target = current.replace(year=current.year - 1)
    except ValueError:
        target = current.replace(year=current.year - 1, day=28)
    key = target.isoformat()
    if key in values:
        return values[key]
    candidates = [
        item
        for item in values
        if date.fromisoformat(item).year == target.year
        and date.fromisoformat(item).month == target.month
        and values[item] is not None
    ]
    return values[sorted(candidates)[0]] if candidates else None


def growth(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return current / previous - 1.0


def safe_div(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def fmt_pct(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def fmt_num(value, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_config(path: str | Path | None) -> dict:
    config = load_json(path or DEFAULT_CONFIG)
    defaults = {
        "thresholds": {
            "sales_yoy": 0.20,
            "pat_yoy": 0.30,
            "opm_delta_rel": 0.10,
            "opm_delta_pp": 1.0,
            "return_since_result": 0.05,
            "ema_weeks": 30,
            "result_lag_days": 45,
            "interest_cover": 2.0,
            "debt_to_equity": 2.0,
            "cfo_conversion": 0.0,
            "cwip_to_sales": 0.05,
            "cwip_growth": 0.25,
            "coverage_gate": 0.6,
        },
        "catalyst_types": [
            "large_order",
            "new_capex",
            "new_product",
            "new_management",
            "approval_policy",
            "turnaround",
            "theme_tailwind",
            "acquisition_alliance",
            "year_zero",
            "switch",
        ],
    }
    config.setdefault("thresholds", {})
    for key, value in defaults["thresholds"].items():
        config["thresholds"].setdefault(key, value)
    config.setdefault("catalyst_types", defaults["catalyst_types"])
    return config


def ema(values: list[float], period: int):
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = value * alpha + current * (1.0 - alpha)
    return current


def load_prices(path: str | Path | None, as_of: str, ema_weeks: int) -> dict | None:
    if not path:
        return None
    payload = load_json(path)
    points: list[tuple[str, float]] = []
    for point in payload.get("points") or []:
        day = point.get("date")
        if not day or day > as_of:
            continue
        close = point.get("adjusted")
        if close is None:
            close = point.get("close")
        close = parse_number(close)
        if close is not None:
            points.append((str(day), close))
    points.sort()
    if not points:
        return None

    weekly: dict[tuple[int, int], tuple[str, float]] = {}
    for day, close in points:
        current = date.fromisoformat(day)
        iso = current.isocalendar()
        weekly[(iso.year, iso.week)] = (day, close)
    weekly_closes = [value[1] for _, value in sorted(weekly.items())]
    ema_value = ema(weekly_closes, ema_weeks)

    cutoff = date.fromisoformat(as_of) - timedelta(days=365)
    high_52w = max(
        (close for day, close in points if date.fromisoformat(day) >= cutoff),
        default=None,
    )
    current_day, current_price = points[-1]
    return {
        "symbol": payload.get("symbol"),
        "current_date": current_day,
        "current_price": current_price,
        "ema": ema_value,
        "ema_weeks": ema_weeks,
        "high_52w": high_52w,
        "points": points,
        "weekly_closes": weekly_closes,
    }


def return_since(points: list[tuple[str, float]], result_date: str | None):
    if not points or not result_date:
        return None, None
    candidates = [(day, close) for day, close in points if day >= result_date]
    if not candidates:
        return None, None
    first_day, first_close = candidates[0]
    current = points[-1][1]
    if first_close == 0:
        return None, first_day
    return current / first_close - 1.0, first_day


def condition(
    condition_id: str,
    label: str,
    value,
    threshold,
    passed: bool | None,
    basis: str,
    value_text: str | None = None,
    threshold_text: str | None = None,
) -> dict:
    status = "UNKNOWN" if passed is None else ("PASS" if passed else "FAIL")
    return {
        "id": condition_id,
        "label": label,
        "value": value,
        "value_text": value_text if value_text is not None else (fmt_pct(value) if isinstance(value, float) else "n/a"),
        "threshold": threshold,
        "threshold_text": threshold_text if threshold_text is not None else (fmt_pct(threshold) if isinstance(threshold, float) else "n/a"),
        "status": status,
        "basis": basis,
    }


def quality_item(item_id: str, label: str, value, passed: bool | None, detail: str = "") -> dict:
    status = "UNKNOWN" if passed is None else ("PASS" if passed else "FAIL")
    return {"id": item_id, "label": label, "value": value, "status": status, "detail": detail}


def extract_screener(path: str | Path, as_of: str, thresholds: dict | None = None) -> dict:
    thresholds = thresholds or {}
    payload = load_json(path)
    tables = payload.get("tables") or {}
    pnl = table_map(tables.get("profit-loss") or [])
    quarters = table_map(tables.get("quarters") or [])
    balance = table_map(tables.get("balance-sheet") or [])
    cash = table_map(tables.get("cash-flow") or [])
    holding = table_map(tables.get("shareholding") or [])

    annual_sales = find_row(pnl, "Sales")
    annual_np = find_row(pnl, "Net Profit")
    annual_op = find_row(pnl, "Operating Profit")
    annual_opm = find_row(pnl, "OPM")
    annual_interest = find_row(pnl, "Interest")
    annual_cfo = find_row(cash, "Cash from Operating Activity")
    annual_borrowings = find_row(balance, "Borrowings")
    annual_equity = find_row(balance, "Equity Capital")
    annual_reserves = find_row(balance, "Reserves")
    annual_cwip = find_row(balance, "CWIP")
    annual_fixed = find_row(balance, "Fixed Assets")
    q_sales = find_row(quarters, "Sales")
    q_np = find_row(quarters, "Net Profit")
    q_opm = find_row(quarters, "OPM")

    if not annual_sales:
        raise ValueError("could not find a Sales row in the profit-loss table")

    latest_annual_day, latest_sales = latest_value(annual_sales, as_of)
    prev_annual_day, prev_sales = None, None
    if latest_annual_day:
        annual_days = sorted(day for day, value in annual_sales.items() if value is not None and day <= as_of)
        if len(annual_days) >= 2:
            prev_annual_day = annual_days[-2]
            prev_sales = annual_sales.get(prev_annual_day)

    latest_q_day, latest_q_sales = latest_value(q_sales, as_of)
    prior_q_day = None
    prior_q_sales = None
    if latest_q_day:
        target = date.fromisoformat(latest_q_day).replace(year=date.fromisoformat(latest_q_day).year - 1)
        candidates = [
            day
            for day in q_sales
            if date.fromisoformat(day).year == target.year
            and date.fromisoformat(day).month == target.month
            and q_sales[day] is not None
            and day <= as_of
        ]
        if candidates:
            prior_q_day = sorted(candidates)[0]
            prior_q_sales = q_sales.get(prior_q_day)

    def q_prior(values):
        if not values or not prior_q_day:
            return None
        return values.get(prior_q_day)

    latest_q_pat = latest_value(q_np, as_of)[1] if q_np else None
    prior_q_pat = q_prior(q_np) if q_np else None
    latest_q_opm = latest_value(q_opm, as_of)[1] if q_opm else None
    prior_q_opm = q_prior(q_opm) if q_opm else None

    latest_annual_pat = latest_value(annual_np, as_of)[1] if annual_np else None
    latest_annual_op = latest_value(annual_op, as_of)[1] if annual_op else None
    latest_annual_opm = latest_value(annual_opm, as_of)[1] if annual_opm else None
    prev_annual_pat = annual_np.get(prev_annual_day) if annual_np and prev_annual_day else None
    prev_annual_opm = annual_opm.get(prev_annual_day) if annual_opm and prev_annual_day else None

    q_sales_growth = growth(latest_q_sales, prior_q_sales)
    q_pat_growth = growth(latest_q_pat, prior_q_pat)
    q_opm_rel = growth(latest_q_opm, prior_q_opm)
    annual_sales_growth = growth(latest_sales, prev_sales)
    annual_pat_growth = growth(latest_annual_pat, prev_annual_pat)
    annual_opm_rel = growth(latest_annual_opm, prev_annual_opm)

    sales_growth = q_sales_growth if q_sales_growth is not None else annual_sales_growth
    pat_growth = q_pat_growth if q_pat_growth is not None else annual_pat_growth
    opm_rel = q_opm_rel if q_opm_rel is not None else annual_opm_rel
    opm_delta_pp = (
        latest_q_opm - prior_q_opm
        if latest_q_opm is not None and prior_q_opm is not None
        else (latest_annual_opm - prev_annual_opm if latest_annual_opm is not None and prev_annual_opm is not None else None)
    )

    latest_cfo_day, latest_cfo = latest_value(annual_cfo, as_of) if annual_cfo else (None, None)
    latest_interest_day, latest_interest = latest_value(annual_interest, as_of) if annual_interest else (None, None)
    latest_borrow_day, latest_borrowings = latest_value(annual_borrowings, as_of) if annual_borrowings else (None, None)
    latest_equity_day, latest_equity = latest_value(annual_equity, as_of) if annual_equity else (None, None)
    latest_reserve_day, latest_reserves = latest_value(annual_reserves, as_of) if annual_reserves else (None, None)
    latest_cwip_day, latest_cwip = latest_value(annual_cwip, as_of) if annual_cwip else (None, None)
    latest_fixed_day, latest_fixed = latest_value(annual_fixed, as_of) if annual_fixed else (None, None)

    equity = None
    if latest_equity is not None or latest_reserves is not None:
        equity = (latest_equity or 0.0) + (latest_reserves or 0.0)
    cfo_conversion = safe_div(latest_cfo, latest_annual_op)
    debt_to_equity = safe_div(latest_borrowings, equity)
    interest_zero = latest_interest == 0
    interest_cover = None if interest_zero else safe_div(latest_annual_op, latest_interest)
    cwip_to_sales = safe_div(latest_cwip, latest_sales)
    prior_cwip = prior_year_value(annual_cwip, latest_cwip_day) if annual_cwip else None
    cwip_growth = growth(latest_cwip, prior_cwip)
    capex_signal = None
    if cwip_to_sales is not None or cwip_growth is not None:
        capex_signal = bool(
            (cwip_to_sales is not None and cwip_to_sales >= thresholds.get("cwip_to_sales", 0.05))
            or (cwip_growth is not None and cwip_growth >= thresholds.get("cwip_growth", 0.25))
        )

    promoter_delta = None
    institutional_delta = None
    promoters = find_row(holding, "Promoters")
    fiis = find_row(holding, "FII")
    diis = find_row(holding, "DII")
    if promoters:
        days = sorted(day for day, value in promoters.items() if value is not None and day <= as_of)
        if len(days) >= 5:
            promoter_delta = (promoters[days[-1]] or 0) - (promoters[days[-5]] or 0)
            if fiis and diis:
                latest_inst = (fiis.get(days[-1]) or 0) + (diis.get(days[-1]) or 0)
                prior_inst = (fiis.get(days[-5]) or 0) + (diis.get(days[-5]) or 0)
                institutional_delta = latest_inst - prior_inst

    ratios = payload.get("ratios") or {}
    return {
        "company": payload.get("company") or payload.get("slug") or Path(path).stem,
        "ticker": payload.get("slug") or Path(path).stem,
        "variant": payload.get("variant"),
        "screener_as_of": payload.get("as_of"),
        "ratios": {
            "market_cap": parse_number(ratios.get("Market Cap")),
            "current_price": parse_number(ratios.get("Current Price")),
            "stock_pe": parse_number(ratios.get("Stock P/E")),
            "book_value": parse_number(ratios.get("Book Value")),
            "roce": parse_number(ratios.get("ROCE")),
            "roe": parse_number(ratios.get("ROE")),
        },
        "metrics": {
            "latest_annual": latest_annual_day,
            "previous_annual": prev_annual_day,
            "latest_quarter": latest_q_day,
            "prior_year_quarter": prior_q_day,
            "sales": latest_sales,
            "sales_growth": sales_growth,
            "sales_growth_basis": "latest quarter YoY" if q_sales_growth is not None else "latest annual YoY",
            "pat": latest_annual_pat,
            "pat_growth": pat_growth,
            "pat_growth_basis": "latest quarter YoY" if q_pat_growth is not None else "latest annual YoY",
            "opm": latest_q_opm if latest_q_opm is not None else latest_annual_opm,
            "opm_delta_rel": opm_rel,
            "opm_delta_pp": opm_delta_pp,
            "opm_basis": "latest quarter YoY" if q_opm_rel is not None else "latest annual YoY",
            "operating_profit": latest_annual_op,
            "cfo": latest_cfo,
            "cfo_conversion": cfo_conversion,
            "borrowings": latest_borrowings,
            "equity": equity,
            "debt_to_equity": debt_to_equity,
            "interest": latest_interest,
            "interest_cover": interest_cover,
            "interest_zero": interest_zero,
            "cwip": latest_cwip,
            "fixed_assets": latest_fixed,
            "cwip_to_sales": cwip_to_sales,
            "cwip_growth": cwip_growth,
            "capex_signal": capex_signal,
            "promoter_delta": promoter_delta,
            "institutional_delta": institutional_delta,
        },
    }


def build_payload(args) -> dict:
    config = load_config(args.config)
    thresholds = config["thresholds"]
    screener = extract_screener(args.screener, args.as_of, thresholds)
    metrics = screener["metrics"]
    as_of = args.as_of
    price = load_prices(args.price_json, as_of, int(args.ema_weeks or thresholds["ema_weeks"]))

    result_date = args.result_date
    result_basis = "explicit"
    if not result_date and metrics.get("latest_quarter"):
        result_date = (
            date.fromisoformat(metrics["latest_quarter"]) + timedelta(days=int(thresholds["result_lag_days"]))
        ).isoformat()
        result_basis = f"inferred: quarter end + {thresholds['result_lag_days']} days"
    return_since_result, return_start = (None, None)
    if price:
        return_since_result, return_start = return_since(price["points"], result_date)

    j_conditions = []
    j_conditions.append(
        condition(
            "jc-sales-growth",
            "Sales growth >= 20%",
            metrics.get("sales_growth"),
            thresholds["sales_yoy"],
            None if metrics.get("sales_growth") is None else metrics["sales_growth"] >= thresholds["sales_yoy"],
            metrics.get("sales_growth_basis", ""),
        )
    )
    j_conditions.append(
        condition(
            "jc-pat-growth",
            "PAT growth >= 30%",
            metrics.get("pat_growth"),
            thresholds["pat_yoy"],
            None if metrics.get("pat_growth") is None else metrics["pat_growth"] >= thresholds["pat_yoy"],
            metrics.get("pat_growth_basis", ""),
        )
    )

    opm_rel = metrics.get("opm_delta_rel")
    opm_pp = metrics.get("opm_delta_pp")
    opm_pass = None
    if opm_rel is not None:
        opm_pass = opm_rel >= thresholds["opm_delta_rel"]
    elif opm_pp is not None:
        opm_pass = opm_pp >= thresholds["opm_delta_pp"]
    j_conditions.append(
        condition(
            "jc-opm-expansion",
            "Operating margin expansion >= 10%",
            opm_rel if opm_rel is not None else opm_pp,
            thresholds["opm_delta_rel"] if opm_rel is not None else thresholds["opm_delta_pp"],
            opm_pass,
            metrics.get("opm_basis", "") if opm_rel is not None else "percentage-point fallback",
            value_text=fmt_pct(opm_rel) if opm_rel is not None else (f"{opm_pp:.1f} pp" if opm_pp is not None else "n/a"),
            threshold_text="10.0%" if opm_rel is not None else "1.0 pp",
        )
    )
    j_conditions.append(
        condition(
            "jc-return-since-result",
            "Return since latest result >= 5%",
            return_since_result,
            thresholds["return_since_result"],
            None if return_since_result is None else return_since_result >= thresholds["return_since_result"],
            f"result date: {result_date or 'unknown'} ({result_basis})",
        )
    )
    price_vs_ema = None
    if price and price.get("ema") is not None and price.get("current_price") is not None:
        price_vs_ema = price["current_price"] / price["ema"] - 1.0
    j_conditions.append(
        condition(
            "jc-price-above-ema",
            f"Price above {int(thresholds['ema_weeks'])}-week EMA",
            price_vs_ema,
            None,
            None if price_vs_ema is None else price_vs_ema >= 0,
            f"{int(thresholds['ema_weeks'])}-week EMA from price history" if price else "price history not supplied",
            threshold_text=">= 0%",
        )
    )

    j_count = sum(1 for item in j_conditions if item["status"] == "PASS")
    j_known = sum(1 for item in j_conditions if item["status"] != "UNKNOWN")
    j_coverage = j_known / len(j_conditions)

    quality = [
        quality_item(
            "cfo-positive",
            "CFO positive",
            metrics.get("cfo"),
            None if metrics.get("cfo") is None else metrics["cfo"] > 0,
        ),
        quality_item(
            "interest-cover",
            "Interest cover >= 2x",
            "n/a (no interest)" if metrics.get("interest_zero") else metrics.get("interest_cover"),
            True if metrics.get("interest_zero") else (None if metrics.get("interest_cover") is None else metrics["interest_cover"] >= thresholds["interest_cover"]),
        ),
        quality_item(
            "debt-to-equity",
            "Debt / equity <= 2x",
            metrics.get("debt_to_equity"),
            None if metrics.get("debt_to_equity") is None else metrics["debt_to_equity"] <= thresholds["debt_to_equity"],
        ),
        quality_item(
            "sales-positive",
            "Sales positive",
            metrics.get("sales"),
            None if metrics.get("sales") is None else metrics["sales"] > 0,
        ),
    ]
    if any(item["status"] == "FAIL" for item in quality):
        quality_status = "FAIL"
    elif any(item["status"] == "UNKNOWN" for item in quality):
        quality_status = "UNKNOWN"
    else:
        quality_status = "PASS"
    quality_known = sum(1 for item in quality if item["status"] != "UNKNOWN")
    coverage = (j_known + quality_known) / (len(j_conditions) + len(quality))

    catalysts = sorted(set(args.catalyst or []))
    invalid = [item for item in catalysts if item not in config["catalyst_types"]]
    if invalid:
        raise ValueError(f"unknown catalyst tag(s): {', '.join(invalid)}")

    catalyst_count = len(catalysts)
    capex_signal = metrics.get("capex_signal")
    if coverage < thresholds["coverage_gate"] or quality_status == "UNKNOWN":
        stage = "INSUFFICIENT"
    elif quality_status == "FAIL":
        stage = "WATCH"
    elif catalyst_count and j_count >= 4:
        stage = "TRAIN_C"
    elif catalyst_count and (capex_signal or "large_order" in catalysts or "new_capex" in catalysts):
        stage = "TRAIN_B"
    elif j_count >= 4:
        stage = "CANDIDATE"
    elif j_count == 3:
        stage = "WATCH"
    else:
        stage = "TRAIN_A"

    unknowns = []
    for item in j_conditions:
        if item["status"] == "UNKNOWN":
            unknowns.append(item["label"])
    for item in quality:
        if item["status"] == "UNKNOWN":
            unknowns.append(item["label"])
    if not catalysts:
        unknowns.append("catalysts (orders, capex, products, management, theme, interviews)")

    notes = list(config.get("notes") or [])
    notes.append("Screener-only mode is a candidate filter, not a reproduction of the full framework.")
    notes.append("A J-curve PASS is not a buy signal; quality and catalyst evidence still gate the stage.")

    return {
        "framework": {
            "id": config.get("id"),
            "version": config.get("version"),
            "creator": config.get("creator"),
            "source": config.get("source"),
            "horizon_years": config.get("horizon_years"),
            "mode": "catalyst_assisted" if catalysts else "screener_only",
        },
        "ticker": screener["ticker"],
        "company": screener["company"],
        "variant": screener["variant"],
        "as_of": as_of,
        "screener_as_of": screener["screener_as_of"],
        "price": {
            "symbol": price.get("symbol") if price else None,
            "current_date": price.get("current_date") if price else None,
            "current_price": price.get("current_price") if price else None,
            "ema": price.get("ema") if price else None,
            "ema_weeks": price.get("ema_weeks") if price else None,
            "high_52w": price.get("high_52w") if price else None,
            "price_vs_ema": price_vs_ema,
        },
        "result": {
            "result_date": result_date,
            "result_date_basis": result_basis,
            "return_start": return_start,
            "return_since_result": return_since_result,
        },
        "metrics": metrics,
        "j_curve": j_conditions,
        "j_count": j_count,
        "j_known": j_known,
        "j_coverage": j_coverage,
        "quality": quality,
        "quality_status": quality_status,
        "coverage": coverage,
        "catalysts": catalysts,
        "catalyst_count": catalyst_count,
        "capex_signal": capex_signal,
        "stage": stage,
        "unknowns": unknowns,
        "notes": notes,
    }


def summary_line(payload: dict) -> str:
    return (
        f"{payload['ticker']:<14} {payload['stage']:<13} "
        f"J={payload['j_count']}/{len(payload['j_curve'])} known={payload['j_known']} "
        f"Q={payload['quality_status']:<7} cov={payload['coverage']:.0%} "
        f"sales={fmt_pct(payload['metrics'].get('sales_growth'))} "
        f"pat={fmt_pct(payload['metrics'].get('pat_growth'))} "
        f"opm={fmt_pct(payload['metrics'].get('opm_delta_rel'))} "
        f"catalysts={','.join(payload['catalysts']) or '-'}"
    )


def markdown(payload: dict) -> str:
    lines = [
        f"# {payload['company']} ({payload['ticker']}) — SOIC NEW screen",
        "",
        f"- As of: `{payload['as_of']}`",
        f"- Screener variant: `{payload.get('variant') or 'unknown'}`",
        f"- Stage: **{payload['stage']}**",
        f"- J-curve: **{payload['j_count']}/{len(payload['j_curve'])}** passed; **{payload['j_known']}/{len(payload['j_curve'])}** known",
        f"- Quality: **{payload['quality_status']}**",
        f"- Coverage: **{payload['coverage']:.0%}**",
        f"- Catalysts: {', '.join(payload['catalysts']) or 'none supplied'}",
        "",
        "## J-curve conditions",
        "",
        "| Condition | Value | Threshold | Status | Basis |",
        "|---|---:|---:|---|---|",
    ]
    for item in payload["j_curve"]:
        lines.append(
            f"| {item['label']} | {item['value_text']} | {item['threshold_text']} | {item['status']} | {item['basis']} |"
        )
    lines += [
        "",
        "## Quality gates",
        "",
        "| Gate | Value | Status |",
        "|---|---:|---|",
    ]
    for item in payload["quality"]:
        value = item["value"]
        value_text = value if isinstance(value, str) else (fmt_num(value) if isinstance(value, (int, float)) else "n/a")
        lines.append(f"| {item['label']} | {value_text} | {item['status']} |")
    lines += [
        "",
        "## Stage",
        "",
        f"`{payload['stage']}`",
        "",
        "## Unknowns",
        "",
    ]
    lines += [f"- {item}" for item in payload["unknowns"]] or ["- none"]
    lines += [
        "",
        "## Notes",
        "",
    ]
    lines += [f"- {item}" for item in payload["notes"]]
    lines += [
        "",
        "Screening aid only — not investment advice.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    reconfigure_streams()
    parser = argparse.ArgumentParser(description="Screen a stock with the SOIC NEW / J-curve framework.")
    parser.add_argument("screener", nargs="?", help="Screener JSON file produced by scripts/fetch_screener.py")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Point-in-time date (YYYY-MM-DD)")
    parser.add_argument("--price-json", dest="price_json", default=None, help="Price JSON from scripts/fetch_prices.py")
    parser.add_argument("--result-date", dest="result_date", default=None, help="Latest result date (YYYY-MM-DD)")
    parser.add_argument("--catalyst", action="append", default=[], help="Catalyst tag; repeatable")
    parser.add_argument("--config", default=None, help="Config JSON (default: assets/config.json)")
    parser.add_argument("--ema-weeks", type=int, default=None, help="EMA period in weeks")
    parser.add_argument("--summary", action="store_true", help="Print the one-line summary")
    parser.add_argument("--json", dest="json_out", default=None, help="Write full JSON result")
    parser.add_argument("--md", dest="md_out", default=None, help="Write markdown result")
    parser.add_argument("--print-config", action="store_true", help="Print the effective config and exit")
    parser.add_argument("--list-catalysts", action="store_true", help="List catalyst tags and exit")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.print_config:
        print(json.dumps(config, indent=2))
        return 0
    if args.list_catalysts:
        for item in config["catalyst_types"]:
            print(item)
        return 0
    if not args.screener:
        parser.error("a Screener JSON file is required")

    if not args.as_of:
        args.as_of = load_json(args.screener).get("as_of")
    if not args.as_of:
        parser.error("--as-of is required when the Screener JSON has no as_of")
    date.fromisoformat(args.as_of)
    if args.result_date:
        date.fromisoformat(args.result_date)

    catalysts = []
    for item in args.catalyst:
        catalysts.extend(part.strip() for part in item.split(",") if part.strip())
    args.catalyst = catalysts

    try:
        payload = build_payload(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"json: {args.json_out}")
    if args.md_out:
        Path(args.md_out).write_text(markdown(payload) + "\n", encoding="utf-8")
        print(f"md:   {args.md_out}")
    if args.summary or not (args.json_out or args.md_out):
        print(summary_line(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
