#!/usr/bin/env python3
"""Score a stock against a framework using the metric registry.

Equal-weight composite over available criteria. Derived, not creator-stated.
Every row keeps its raw value, formula basis, and source.
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTHS = {name: index for index, name in enumerate(calendar.month_abbr) if name}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm_label(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").replace("â‚¹", "").strip()
    match = re.search(r"[-+]?\d*\.?\d+", text)
    return float(match.group(0)) if match else None


def period_date(label: str) -> date | None:
    match = re.match(r"^([A-Z][a-z]{2}) (\d{4})$", norm_label(label))
    if not match:
        return None
    month = MONTHS.get(match.group(1))
    if not month:
        return None
    year = int(match.group(2))
    return date(year, month, calendar.monthrange(year, month)[1])


class Screener:
    def __init__(self, path: Path):
        self.path = path
        self.data = load_json(path)
        self.tables = self.data.get("tables") or {}
        self.ratios = self.data.get("ratios") or {}

    def row(self, section: str, prefix: str) -> dict:
        for item in self.tables.get(section) or []:
            if norm_label(item.get("label", "")).startswith(prefix):
                return item.get("values") or {}
        return {}

    def series(self, section: str, prefix: str, as_of: date, lag_days: int) -> list[tuple[date, float, str]]:
        out = []
        for label, raw in self.row(section, prefix).items():
            value = number(raw)
            day = period_date(label)
            if value is None or day is None:
                continue
            if day + timedelta(days=lag_days) <= as_of:
                out.append((day, value, label))
        out.sort(key=lambda item: item[0])
        return out

    def latest_annual(self, section: str, prefix: str, as_of: date) -> tuple[date, float, str] | None:
        values = self.series(section, prefix, as_of, lag_days=90)
        return values[-1] if values else None

    def ttm_valid(self, as_of: date) -> bool:
        quarters = self.row("quarters", "Sales")
        days = [period_date(label) for label in quarters if label != "TTM"]
        days = [day for day in days if day]
        if not days:
            return False
        return max(days) + timedelta(days=45) <= as_of

    def current_or_annual(self, section: str, prefix: str, as_of: date):
        if self.ttm_valid(as_of):
            ttm = number(self.row(section, prefix).get("TTM"))
            if ttm is not None:
                return ttm, "TTM"
        latest = self.latest_annual(section, prefix, as_of)
        return (latest[1], latest[2]) if latest else (None, None)

    def book_value_per_share(self, as_of: date, max_age_days: int = 550) -> dict | None:
        equity_series = {day: value for day, value, _ in self.series("balance-sheet", "Equity Capital", as_of, 90)}
        reserve_series = {day: value for day, value, _ in self.series("balance-sheet", "Reserves", as_of, 90)}
        common = sorted(set(equity_series) & set(reserve_series))
        if not common:
            return None
        day = common[-1]
        if (as_of - day).days > max_age_days:
            return None
        face_value = number(self.ratios.get("Face Value"))
        if not face_value:
            return None
        shares = equity_series[day] / face_value
        if shares <= 0:
            return None
        book_value = equity_series[day] + reserve_series[day]
        return {
            "bvps": book_value / shares,
            "book_value_cr": book_value,
            "shares_cr": shares,
            "period": day.isoformat(),
            "face_value": face_value,
        }

    def shareholding_changes(self, as_of: date) -> dict:
        def frame(prefix: str) -> dict[date, float]:
            return {day: value for day, value, _ in self.series("shareholding", prefix, as_of, 30)}

        promoter = frame("Promoters")
        dii = frame("DIIs")
        fii = frame("FIIs")
        result = {"promoter": None, "coverage": None, "periods": []}
        promoter_days = sorted(promoter)
        if len(promoter_days) >= 2:
            window = promoter_days[-5:]
            result["promoter"] = {
                "delta_pp": promoter[window[-1]] - promoter[window[0]],
                "from": window[0].isoformat(),
                "to": window[-1].isoformat(),
                "from_pct": promoter[window[0]],
                "to_pct": promoter[window[-1]],
            }
        common = sorted(set(dii) & set(fii))
        if len(common) >= 2:
            window = common[-5:]
            start = dii[window[0]] + fii[window[0]]
            end = dii[window[-1]] + fii[window[-1]]
            result["coverage"] = {
                "delta_pp": end - start,
                "from": window[0].isoformat(),
                "to": window[-1].isoformat(),
                "from_pct": start,
                "to_pct": end,
            }
            result["periods"] = [day.isoformat() for day in window]
        return result


def price_stats(path: Path) -> dict:
    return load_json(path)["stats"]


def interpolate(value: float, anchors: list[dict]) -> float:
    points = sorted(anchors, key=lambda item: item["value"])
    if value <= points[0]["value"]:
        return float(points[0]["score"])
    if value >= points[-1]["value"]:
        return float(points[-1]["score"])
    for left, right in zip(points, points[1:]):
        if left["value"] <= value <= right["value"]:
            ratio = (value - left["value"]) / (right["value"] - left["value"])
            return float(left["score"] + ratio * (right["score"] - left["score"]))
    return float(points[-1]["score"])


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Score a stock with a framework metric registry.")
    parser.add_argument("ticker")
    parser.add_argument("--framework", default="ameya-peak-pessimism")
    parser.add_argument("--as-of", dest="as_of", default=None)
    parser.add_argument("--screener-variant", default="consolidated", choices=["consolidated", "standalone"])
    parser.add_argument("--book-variant", default="auto", choices=["auto", "consolidated", "standalone"])
    parser.add_argument("--peers", default="", help="Comma-separated Screener slugs")
    parser.add_argument("--price-symbol", default=None)
    parser.add_argument("--screener-path", default=None, help="Override the Screener snapshot path")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    ticker = args.ticker.upper()
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    framework_dir = ROOT / "skills" / "frameworks" / args.framework
    framework = load_json(framework_dir / "framework.json")
    registry = load_json(ROOT / "metrics" / "registry.json")
    coverage_gate = float(registry.get("scoring", {}).get("coverage_gate", 0.7))
    metrics = {item["id"]: item for item in registry["metrics"]}
    by_criterion = {item["criterion_id"]: item for item in registry["metrics"]}

    screener_path = (
        Path(args.screener_path)
        if args.screener_path
        else ROOT / "data" / "screener" / ticker / as_of.isoformat() / f"screener-{args.screener_variant}.json"
    )
    if not screener_path.exists():
        print(f"missing screener snapshot: {screener_path}", file=sys.stderr)
        return 1
    screener = Screener(screener_path)

    symbol = (args.price_symbol or f"{ticker}.NS").upper()
    price_path = ROOT / "data" / "prices" / symbol / as_of.isoformat() / "prices.json"
    if not price_path.exists():
        print(f"missing price snapshot: {price_path}", file=sys.stderr)
        return 1
    prices = price_stats(price_path)

    peer_slugs = [slug.strip().upper() for slug in args.peers.split(",") if slug.strip()]
    peers = []
    for slug in peer_slugs:
        path = ROOT / "data" / "screener" / slug / as_of.isoformat() / f"screener-{args.screener_variant}.json"
        if not path.exists():
            fallback = screener_path.parent.name
            path = ROOT / "data" / "screener" / slug / fallback / f"screener-{args.screener_variant}.json"
        if path.exists():
            peers.append((slug, Screener(path)))

    computed: dict[str, dict] = {}

    def put(metric_id: str, value, unit: str, raw=None, detail: str = "", source: str = "", confidence=None):
        computed[metric_id] = {
            "value": value,
            "unit": unit,
            "raw": value if raw is None else raw,
            "detail": detail,
            "source": source,
            "confidence": (metrics[metric_id].get("confidence") if confidence is None else confidence),
        }

    # Price drawdown
    drawdown = float(prices["drawdown_from_peak"])
    put(
        "price_drawdown",
        round(drawdown * 100, 1),
        "percent",
        raw=drawdown,
        detail=f"peak {prices['peak_date']} {prices['peak_adjusted']}, now {prices['current_adjusted']}; "
        f"recovery {prices['recovery_from_trough']:.2f}x from trough {prices['trough_date']}",
        source=f"Yahoo {symbol} adjusted close ({price_path.relative_to(ROOT)})",
        confidence="high",
    )

    # Multiple compression
    variant = args.book_variant
    peak_day = date.fromisoformat(prices["peak_date"])
    if variant == "auto":
        candidate = args.screener_variant
        if screener.book_value_per_share(peak_day) is None:
            candidate = "standalone" if args.screener_variant == "consolidated" else "consolidated"
        variant = candidate

    def book_at(target: date):
        path = screener_path if variant == args.screener_variant else screener_path.with_name(f"screener-{variant}.json")
        if path.exists():
            return Screener(path).book_value_per_share(target)
        return None

    book_peak = book_at(peak_day)
    book_now = book_at(as_of)
    if book_peak and book_now and book_peak["bvps"] > 0:
        pb_peak = float(prices["peak_adjusted"]) / book_peak["bvps"]
        pb_now = float(prices["current_adjusted"]) / book_now["bvps"]
        ratio = pb_now / pb_peak
        put(
            "multiple_ratio",
            round(ratio, 3),
            "x peak P/B",
            raw=ratio,
            detail=f"P/B {pb_now:.2f} now vs {pb_peak:.2f} at peak; BVPS {book_now['bvps']:.1f} "
            f"({book_now['period']}) vs {book_peak['bvps']:.1f} ({book_peak['period']}); book basis {variant}",
            source=f"Screener {ticker} {variant} + Yahoo {symbol} ({peak_day.isoformat()} peak)",
        )

    # Sector breadth and relative margin gap
    def opm_profile(item: Screener):
        annual = [value for _, value, _ in item.series("profit-loss", "OPM %", as_of, 90)][-5:]
        current, when = item.current_or_annual("profit-loss", "OPM %", as_of)
        if current is None or len(annual) < 2:
            return None
        return {"current": current, "median": statistics.median(annual), "annual_n": len(annual), "when": when}

    sector_rows = []
    target_profile = opm_profile(screener)
    if target_profile:
        sector_rows.append((ticker, target_profile))
    for slug, peer in peers:
        profile = opm_profile(peer)
        if profile:
            sector_rows.append((slug, profile))

    if len(sector_rows) >= 3:
        below = [profile["current"] < profile["median"] for _, profile in sector_rows]
        breadth = sum(below) / len(below)
        put(
            "sector_breadth",
            round(breadth * 100, 1),
            "percent",
            raw=breadth,
            detail="; ".join(
                f"{slug} {profile['current']:.1f}% vs median {profile['median']:.1f}%"
                for slug, profile in sector_rows
            ),
            source="Screener consolidated OPM, peer basket: " + ", ".join(slug for slug, _ in sector_rows),
            confidence="medium",
        )
        peer_profiles = [profile for slug, profile in sector_rows if slug != ticker]
        if peer_profiles and target_profile:
            gap = statistics.median(profile["current"] for profile in peer_profiles) - target_profile["current"]
            put(
                "relative_margin_gap",
                round(gap, 1),
                "percentage_points",
                raw=gap,
                detail=f"peer median OPM {statistics.median(profile['current'] for profile in peer_profiles):.1f}% "
                f"minus {ticker} {target_profile['current']:.1f}%",
                source="Screener consolidated OPM, peer basket",
                confidence="low",
            )

    # Shareholding proxies
    changes = screener.shareholding_changes(as_of)
    if changes["promoter"]:
        item = changes["promoter"]
        put(
            "promoter_delta",
            round(item["delta_pp"], 2),
            "percentage_points",
            raw=item["delta_pp"],
            detail=f"{item['from_pct']:.2f}% ({item['from']}) -> {item['to_pct']:.2f}% ({item['to']}); "
            "open-market versus preferential allotment unverified",
            source=f"Screener {ticker} shareholding ({screener_path.relative_to(ROOT)})",
            confidence="low",
        )
    if changes["coverage"]:
        item = changes["coverage"]
        put(
            "coverage_delta",
            round(item["delta_pp"], 2),
            "percentage_points",
            raw=item["delta_pp"],
            detail=f"DII+FII {item['from_pct']:.2f}% ({item['from']}) -> {item['to_pct']:.2f}% ({item['to']}); "
            "proxy only, not analyst coverage",
            source=f"Screener {ticker} shareholding ({screener_path.relative_to(ROOT)})",
            confidence="low",
        )

    # Structural viability
    operating_profit, op_when = screener.current_or_annual("profit-loss", "Operating Profit", as_of)
    interest, _ = screener.current_or_annual("profit-loss", "Interest", as_of)
    borrowings = screener.latest_annual("balance-sheet", "Borrowings", as_of)
    equity = screener.latest_annual("balance-sheet", "Equity Capital", as_of)
    reserves = screener.latest_annual("balance-sheet", "Reserves", as_of)
    cfo = screener.latest_annual("cash-flow", "Cash from Operating Activity", as_of)
    if all(value is not None for value in [operating_profit, borrowings, equity, reserves, cfo]):
        coverage_ratio = (operating_profit / interest) if interest and interest > 0 else 99.0
        debt_to_equity = borrowings[1] / (equity[1] + reserves[1]) if (equity[1] + reserves[1]) > 0 else 99.0
        interest_score = clamp(coverage_ratio / 3.0)
        leverage_score = clamp((2.0 - debt_to_equity) / 2.0)
        viability = 100.0 * min(interest_score, leverage_score)
        if cfo[1] <= 0:
            viability *= 0.5
        put(
            "viability",
            round(viability, 1),
            "score_0_100",
            raw=viability,
            detail=f"interest cover {coverage_ratio:.2f}x, debt/equity {debt_to_equity:.2f}, CFO Rs {cfo[1]:.0f} Cr "
            f"({cfo[2]}), operating profit Rs {operating_profit:.0f} Cr ({op_when})",
            source=f"Screener {ticker} {args.screener_variant}",
        )

    # Map to criteria
    rows = []
    scores = []
    for criterion in framework["criteria"]:
        metric = by_criterion.get(criterion["id"])
        if not metric or not metric.get("available", True) or metric["id"] not in computed:
            reason = (metric or {}).get("reason", "no metric mapped")
            rows.append(
                {
                    "criterion_id": criterion["id"],
                    "verdict": "UNKNOWN",
                    "metric_id": (metric or {}).get("id"),
                    "source": "not collected",
                    "note": reason,
                }
            )
            continue

        item = computed[metric["id"]]
        raw = item["raw"]
        score = interpolate(float(raw), metric["anchors"])
        score = round(score, 1)
        scores.append(score)

        if metric["id"] == "multiple_ratio":
            verdict = "PASS" if raw <= 0.5 else "FAIL"
        elif metric["id"] == "price_drawdown":
            verdict = "PASS" if raw >= 0.5 else "FAIL"
        elif metric["id"] == "promoter_delta":
            verdict = "PASS" if raw > 0 else "FAIL"
        elif metric["id"] == "viability":
            verdict = "PASS" if raw >= 40 else "FAIL"
        else:
            verdict = "PASS" if score >= 50 else "FAIL"

        rows.append(
            {
                "criterion_id": criterion["id"],
                "verdict": verdict,
                "value": item["value"],
                "unit": item["unit"],
                "score_0_100": score,
                "metric_id": metric["id"],
                "basis": metric["basis"],
                "confidence": item["confidence"],
                "source": item["source"],
                "note": item["detail"],
            }
        )

    pass_count = sum(row["verdict"] == "PASS" for row in rows)
    fail_count = sum(row["verdict"] == "FAIL" for row in rows)
    unknown_count = sum(row["verdict"] == "UNKNOWN" for row in rows)
    total = len(rows)
    decided = pass_count + fail_count
    coverage = decided / total if total else 0.0
    composite = statistics.mean(scores) if scores else None
    viability_row = next((row for row in rows if row["criterion_id"] == "structural-viability"), None)
    viability_score = viability_row.get("score_0_100") if viability_row else None
    drawdown_row = next((row for row in rows if row["criterion_id"] == "price-drawdown"), None)
    multiple_row = next((row for row in rows if row["criterion_id"] == "multiple-collapse"), None)
    sector_row = next((row for row in rows if row["criterion_id"] == "sector-in-pain"), None)

    def gate(row, passed: bool | None):
        if row is None or row["verdict"] == "UNKNOWN":
            return "unknown"
        return "pass" if passed else "fail"

    gates = {
        "sector_pain": gate(sector_row, sector_row["verdict"] == "PASS" if sector_row else None),
        "multiple_collapse": gate(multiple_row, multiple_row["value"] <= 0.5 if multiple_row and multiple_row.get("value") is not None else None),
        "price_drawdown": gate(drawdown_row, drawdown_row["value"] >= 50 if drawdown_row and drawdown_row.get("value") is not None else None),
        "viability": gate(viability_row, viability_score is not None and viability_score >= 40),
    }
    inflection = any(
        row.get("score_0_100", 0) >= 50
        for row in rows
        if row["criterion_id"] in {"promoter-buying", "coverage-and-chatter-decline"}
    )
    gates["inflection"] = "pass" if inflection else "fail"

    if gates["viability"] == "fail":
        state = "DISQUALIFIED"
    elif "fail" in {gates["sector_pain"], gates["multiple_collapse"], gates["price_drawdown"]}:
        state = "NOT_APPLICABLE"
    elif "unknown" in {gates["sector_pain"], gates["multiple_collapse"], gates["price_drawdown"]}:
        state = "INSUFFICIENT"
    elif inflection:
        state = "CANDIDATE"
    else:
        state = "WATCH"

    summary = {
        "pass": pass_count,
        "fail": fail_count,
        "unknown": unknown_count,
        "na": 0,
        "coverage": round(coverage, 3),
        "score": None if composite is None else round(composite, 1),
        "score_method": "equal-weight mean of per-criterion 0-100 scores; derived, not creator-stated",
        "score_derived": True,
        "weights": "equal",
        "weight_basis": "derived_equal",
        "criteria_scored": len(scores),
        "criteria_total": total,
        "hit_rate": round(pass_count / decided, 3) if decided else None,
        "state": state,
        "gates": gates,
        "insufficient_evidence": coverage < coverage_gate,
    }

    out_path = Path(args.out) if args.out else (
        ROOT / "evals" / args.framework / f"{ticker}-{as_of.isoformat()}-scored.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticker": ticker,
        "as_of": as_of.isoformat(),
        "framework": {"id": framework["id"], "version": framework["version"]},
        "scoring_version": registry["version"],
        "rows": rows,
        "summary": summary,
        "disqualified": state == "DISQUALIFIED",
        "disqualifiers": ["structural-viability"] if state == "DISQUALIFIED" else [],
        "confidence": "low" if coverage < coverage_gate else "medium",
        "notes": (
            "Composite is a derived equal-weight index, not a recommendation. "
            f"State is {state}: the creator's entry logic is conjunctive, so a high composite does not"
            " override a failed gate. Coverage below the gate means the soft criteria are still missing."
        ),
        "inputs": {
            "screener": str(screener_path.relative_to(ROOT)),
            "screener_snapshot_as_of": screener.data.get("as_of"),
            "prices": str(price_path.relative_to(ROOT)),
            "book_variant": variant,
            "peers": peer_slugs,
        },
    }
    if screener.data.get("as_of") != as_of.isoformat():
        payload["notes"] += (
            " Replay: the Screener snapshot was captured later than as_of; only periods published"
            " by as_of are used, but this is not a true historical capture."
        )
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"ticker: {ticker}  as_of: {as_of}  state: {state}")
    print(
        f"composite: {'n/a' if composite is None else f'{composite:.1f}'}/100 (derived, equal weight)  "
        f"hit rate: {summary['hit_rate']}  coverage: {summary['criteria_scored']}/{total} ({coverage:.1%})"
    )
    if coverage < coverage_gate:
        print("coverage below the gate -> provisional, not a verdict")
    print()
    print(f"{'criterion':<38}{'verdict':<10}{'value':>12}  {'score':>6}  basis")
    print("-" * 84)
    for row in rows:
        value = "-" if row.get("value") is None else f"{row['value']} {row.get('unit', '')}"
        score = "-" if row.get("score_0_100") is None else f"{row['score_0_100']:.1f}"
        print(f"{row['criterion_id']:<38}{row['verdict']:<10}{value:>12}  {score:>6}  {row.get('basis', '')}")
    print()
    print(f"saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

