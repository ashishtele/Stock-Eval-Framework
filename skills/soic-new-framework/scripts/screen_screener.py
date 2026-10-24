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


def ttm_sum(values: dict[str, float | None] | None, as_of: str, periods: int = 4):
    if not values:
        return None, None, None
    days = sorted(
        day
        for day, value in values.items()
        if day <= as_of and value is not None
    )
    if len(days) < periods:
        return None, None, None
    window = days[-periods:]
    return sum(values[day] for day in window), window[0], window[-1]


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


def period_return(points: list[tuple[str, float]], as_of: str, months: float):
    if not points or not months:
        return None
    end_day, end_price = points[-1]
    cutoff = date.fromisoformat(as_of) - timedelta(days=round(float(months) * 30.44))
    candidates = [
        (day, close)
        for day, close in points
        if date.fromisoformat(day) >= cutoff
    ]
    if not candidates:
        return None
    start_day, start_price = candidates[0]
    if start_price == 0:
        return None
    return {
        "start_date": start_day,
        "end_date": end_day,
        "return": end_price / start_price - 1.0,
    }


def load_context(path: str | Path | None) -> dict:
    if not path:
        return {}
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("context JSON must be an object")
    return payload


def build_context(
    context: dict,
    result: dict,
    price: dict | None,
    benchmark: dict | None,
    as_of: str,
) -> dict:
    context = context or {}
    theme = context.get("theme") or {}
    relative = context.get("relative_strength") or {}
    ownership = context.get("ownership") or {}
    base = context.get("base") or {}
    concall = context.get("concall") or {}
    entry = context.get("entry") or {}
    valuation = context.get("valuation") or {}
    metrics = result.get("metrics") or {}

    months = relative.get("period_months", 6)
    auto = {}
    if price:
        auto["high_52w"] = price.get("high_52w")
        auto["distance_from_52w_high"] = (
            price["current_price"] / price["high_52w"] - 1.0
            if price.get("current_price") is not None and price.get("high_52w")
            else None
        )
        high_5y = max((close for _, close in price.get("points") or []), default=None)
        auto["high_5y"] = high_5y
        auto["distance_from_5y_high"] = (
            price["current_price"] / high_5y - 1.0
            if price.get("current_price") is not None and high_5y
            else None
        )
        auto["price_vs_ema"] = result.get("price", {}).get("price_vs_ema")
    auto["ttm_sales"] = metrics.get("ttm_sales")
    auto["ttm_pat"] = metrics.get("ttm_pat")
    auto["ttm_period"] = metrics.get("ttm_period")

    stock_period = period_return(price.get("points") or [], as_of, months) if price else None
    benchmark_period = (
        period_return(benchmark.get("points") or [], as_of, months) if benchmark else None
    )
    stock_return = relative.get("stock_return")
    benchmark_return = relative.get("benchmark_return")
    if stock_return is None and stock_period:
        stock_return = stock_period["return"]
    if benchmark_return is None and benchmark_period:
        benchmark_return = benchmark_period["return"]
    relative_return = relative.get("relative_return")
    if relative_return is None and stock_return is not None and benchmark_return is not None:
        relative_return = stock_return - benchmark_return

    relative_out = {
        "benchmark": relative.get("benchmark") or (benchmark.get("symbol") if benchmark else None),
        "period_months": months,
        "stock_return": stock_return,
        "benchmark_return": benchmark_return,
        "relative_return": relative_return,
        "start_date": relative.get("start_date")
        or (stock_period["start_date"] if stock_period else None),
        "end_date": relative.get("end_date")
        or (stock_period["end_date"] if stock_period else None),
        "source": relative.get("source")
        or ("computed from price files" if stock_period and benchmark_period else None),
    }

    ownership_out = {
        "promoter_change_4q": ownership.get("promoter_change_4q", metrics.get("promoter_delta")),
        "institutional_change_4q": ownership.get(
            "institutional_change_4q", metrics.get("institutional_delta")
        ),
        "fii_change_4q": ownership.get("fii_change_4q"),
        "dii_change_4q": ownership.get("dii_change_4q"),
        "source": ownership.get("source") or "Screener shareholding",
    }

    base_out = {
        "start": base.get("start"),
        "end": base.get("end"),
        "breakout": base.get("breakout"),
        "volume_multiple": base.get("volume_multiple"),
        "support": base.get("support"),
        "resistance": base.get("resistance"),
        "source": base.get("source"),
    }
    concall_out = {
        "date": concall.get("date"),
        "congrats_count": concall.get("congrats_count"),
        "guidance": concall.get("guidance"),
        "source": concall.get("source"),
    }
    entry_out = {
        "first_inflection": entry.get("first_inflection"),
        "return_since": entry.get("return_since"),
        "extended": entry.get("extended"),
        "plan": entry.get("plan"),
        "source": entry.get("source"),
    }
    valuation_out = {
        "pe": valuation.get("pe"),
        "note": valuation.get("note"),
    }

    warnings = []
    if theme.get("expiry_risk") == "high":
        warnings.append("theme expiry risk is high")
    if relative_out["relative_return"] is not None and relative_out["relative_return"] < 0:
        warnings.append("relative strength is negative")
    if concall_out.get("guidance") == "cut":
        warnings.append("management cut guidance")
    if entry_out.get("extended") is True:
        warnings.append("entry is extended")

    positives = 0
    if theme.get("name") and theme.get("expiry_risk") in {"low", "medium"}:
        positives += 1
    if relative_out["relative_return"] is not None and relative_out["relative_return"] > 0:
        positives += 1
    if base_out.get("breakout") is True:
        positives += 1
    if concall_out.get("guidance") == "raised":
        positives += 1
    if entry_out.get("first_inflection") and not entry_out.get("extended"):
        positives += 1

    if not context and not benchmark:
        status = "MISSING"
    elif warnings:
        status = "WARNING"
    elif positives >= 2:
        status = "SUPPORTIVE"
    else:
        status = "NEUTRAL"

    return {
        "status": status,
        "theme": {
            "name": theme.get("name"),
            "stage": theme.get("stage"),
            "expiry_risk": theme.get("expiry_risk"),
            "evidence": theme.get("evidence"),
        },
        "relative_strength": relative_out,
        "ownership": ownership_out,
        "base": base_out,
        "concall": concall_out,
        "entry": entry_out,
        "valuation": valuation_out,
        "time_horizon_years": context.get(
            "time_horizon_years", result.get("framework", {}).get("horizon_years")
        ),
        "market_stage": context.get("market_stage"),
        "auto": auto,
        "warnings": warnings,
        "notes": context.get("notes") or [],
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
    ttm_sales, ttm_sales_start, ttm_sales_end = ttm_sum(q_sales, as_of)
    ttm_pat, ttm_pat_start, ttm_pat_end = ttm_sum(q_np, as_of)

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
            "ttm_sales": ttm_sales,
            "ttm_pat": ttm_pat,
            "ttm_period": (
                {"start": ttm_sales_start, "end": ttm_sales_end}
                if ttm_sales_start and ttm_sales_end
                else None
            ),
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
    ema_weeks = int(args.ema_weeks or thresholds["ema_weeks"])
    price = load_prices(args.price_json, as_of, ema_weeks)
    benchmark = load_prices(args.benchmark_json, as_of, ema_weeks) if args.benchmark_json else None

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

    result = {
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
        "ratios": screener.get("ratios") or {},
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
    if args.context or args.benchmark_json:
        result["context"] = build_context(
            load_context(args.context),
            result,
            price,
            benchmark,
            as_of,
        )
    return result


def summary_line(payload: dict) -> str:
    line = (
        f"{payload['ticker']:<14} {payload['stage']:<13} "
        f"J={payload['j_count']}/{len(payload['j_curve'])} known={payload['j_known']} "
        f"Q={payload['quality_status']:<7} cov={payload['coverage']:.0%} "
        f"sales={fmt_pct(payload['metrics'].get('sales_growth'))} "
        f"pat={fmt_pct(payload['metrics'].get('pat_growth'))} "
        f"opm={fmt_pct(payload['metrics'].get('opm_delta_rel'))} "
        f"catalysts={','.join(payload['catalysts']) or '-'}"
    )
    context = payload.get("context")
    if context:
        line += f" ctx={context.get('status')}"
    return line


def context_markdown(context: dict) -> list[str]:
    theme = context.get("theme") or {}
    relative = context.get("relative_strength") or {}
    ownership = context.get("ownership") or {}
    base = context.get("base") or {}
    concall = context.get("concall") or {}
    entry = context.get("entry") or {}
    valuation = context.get("valuation") or {}
    auto = context.get("auto") or {}

    lines = [
        "",
        "## Context layer",
        "",
        f"- Status: **{context.get('status')}**",
    ]
    if theme.get("name") or theme.get("stage") or theme.get("expiry_risk"):
        lines.append(
            "- Theme: "
            f"{theme.get('name') or 'unknown'}"
            f" — stage {theme.get('stage') or 'unknown'}"
            f", expiry risk {theme.get('expiry_risk') or 'unknown'}"
        )
    if relative.get("relative_return") is not None:
        lines.append(
            "- Relative strength: "
            f"{fmt_pct(relative.get('relative_return'))}"
            f" vs {relative.get('benchmark') or 'benchmark'}"
            f" over {relative.get('period_months')} months"
            f" (stock {fmt_pct(relative.get('stock_return'))},"
            f" benchmark {fmt_pct(relative.get('benchmark_return'))})"
        )
    elif relative.get("stock_return") is not None:
        lines.append(
            "- Stock return: "
            f"{fmt_pct(relative.get('stock_return'))}"
            f" over {relative.get('period_months')} months"
        )
    if auto.get("distance_from_52w_high") is not None:
        lines.append(
            f"- Distance from 52-week high: {fmt_pct(auto.get('distance_from_52w_high'))}"
        )
    if auto.get("ttm_sales") is not None or auto.get("ttm_pat") is not None:
        period = auto.get("ttm_period") or {}
        lines.append(
            "- TTM run-rate: "
            f"sales {fmt_num(auto.get('ttm_sales'))}"
            f", PAT {fmt_num(auto.get('ttm_pat'))}"
            f" ({period.get('start') or '?'} to {period.get('end') or '?'})"
        )
    if ownership.get("promoter_change_4q") is not None or ownership.get("institutional_change_4q") is not None:
        lines.append(
            "- Ownership change (4 quarters): "
            f"promoter {fmt_num(ownership.get('promoter_change_4q'))} pp,"
            f" institutional {fmt_num(ownership.get('institutional_change_4q'))} pp"
        )
    if base.get("start") or base.get("end") or base.get("breakout") is not None:
        breakout = base.get("breakout")
        breakout_text = "yes" if breakout is True else "no" if breakout is False else "unknown"
        lines.append(
            "- Base: "
            f"{base.get('start') or '?'} to {base.get('end') or '?'}"
            f", breakout {breakout_text}"
            f", volume {fmt_num(base.get('volume_multiple'))}x"
        )
    if concall.get("date") or concall.get("congrats_count") is not None or concall.get("guidance"):
        lines.append(
            "- Concall: "
            f"{concall.get('date') or 'date unknown'}"
            f", {concall.get('congrats_count') if concall.get('congrats_count') is not None else '?'} congrats"
            f", guidance {concall.get('guidance') or 'unknown'}"
        )
    if entry.get("first_inflection") or entry.get("return_since") is not None:
        extended = entry.get("extended")
        extended_text = "yes" if extended is True else "no" if extended is False else "unknown"
        lines.append(
            "- Entry: "
            f"first inflection {entry.get('first_inflection') or 'unknown'}"
            f", {fmt_pct(entry.get('return_since'))} since"
            f", extended {extended_text}"
        )
    if valuation.get("pe") is not None or valuation.get("note"):
        lines.append(
            f"- Valuation: P/E {fmt_num(valuation.get('pe'))}"
            f" — {valuation.get('note') or 'context only, not a gate'}"
        )
    if context.get("time_horizon_years") is not None:
        lines.append(f"- Time horizon: {context.get('time_horizon_years')} years")
    if context.get("market_stage"):
        lines.append(f"- Market stage: {context.get('market_stage')}")
    if context.get("warnings"):
        lines.append("- Warnings: " + "; ".join(context["warnings"]))
    if context.get("notes"):
        lines.extend(f"- {item}" for item in context["notes"])
    return lines


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
    if payload.get("context"):
        lines += context_markdown(payload["context"])
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
    parser.add_argument("--benchmark-json", dest="benchmark_json", default=None, help="Benchmark price JSON for relative strength")
    parser.add_argument("--context", default=None, help="Optional qualitative context JSON")
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
