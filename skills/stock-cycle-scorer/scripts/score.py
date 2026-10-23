#!/usr/bin/env python3
"""Stock Cycle Scorer: Pessimism Rate of Change + Trajectory Pivot.

Stdlib only. Input is one company object or a list of them.
See ../references/input_schema.md for the input contract.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_CONFIG = {
    "score1_weights": {"level": 0.40, "turn": 0.45, "delta": 0.15},
    "level_weights": {
        "valuation": 0.30,
        "drawdown": 0.20,
        "earnings_stress": 0.20,
        "neglect": 0.15,
        "sector_breadth": 0.15,
    },
    "turn_weights": {
        "promoter": 0.30,
        "sentiment_gap": 0.30,
        "margin_inflection": 0.25,
        "market_share": 0.15,
    },
    "score2_weights": {
        "segment_shift": 0.20,
        "pivot_size": 0.20,
        "capability": 0.20,
        "management": 0.20,
        "mispricing": 0.10,
        "tailwind": 0.10,
        "build_phase": 0.10,
    },
    "segment_shift_split": {"mix": 0.6, "margin_diff": 0.4},
    "valuation_metric_preference": ["pb", "ev_ebitda", "pe"],
    "reporting_lag_days": {"quarter": 45, "annual": 60, "shareholding": 21, "event": 0},
    "thresholds": {
        "drawdown_full": 0.60,
        "earnings_stress_full": 0.40,
        "sector_breadth_dd": 0.40,
        "sector_breadth_full": 0.60,
        "min_peers": 3,
        "concall_short_min": 30,
        "concall_long_min": 90,
        "questions_few": 5,
        "questions_many": 20,
        "institutional_change_pp": 3.0,
        "promoter_window_days": 183,
        "promoter_holding_change_pp": 0.25,
        "inflection_min_rise": 0.01,
        "inflection_trough_below_avg": 0.10,
        "delta_full": 1.0,
        "delta_before_inflection": 0.5,
        "neglect_call_max_age_days": 200,
        "rally_off_low": 0.5,
        "credibility_one_miss": 0.75,
        "credibility_two_misses": 0.5,
        "market_skepticism_dd": 0.30,
        "acquisition_window_days": 455,
        "promoter_exit_flag_pp": 5.0,
        "mix_change_full_pp": 20,
        "mix_share_full_pct": 40,
        "margin_ratio_full": 1.8,
        "orbit_full": 3.0,
        "pivot_success_prob": 0.5,
        "mispricing_full_ratio": 0.4,
        "build_phase_capex_ratio": 1.5,
        "build_phase_full_ratio": 2.0,
        "judgment_heavy_share": 0.6,
        "veto_cap": 30,
        "veto_min_debt_to_equity": 0.5,
        "mgmt_gate_min": 2,
        "mgmt_gate_cap": 40,
        "low_coverage": 0.5,
        "peak_opt_val_pct": 80,
        "peak_opt_val_pct_alone": 90,
        "peak_opt_signals": 2,
        "confirmed_growth": 0.15,
        "confirmed_val_pct_min": 40,
        "early_val_pct_max": 50,
        "early_turn_signals": 2,
        "early_min_dd": 0.25,
        "early_min_off_low": 0.30,
        "peak_pess_val_pct": 25,
        "peak_pess_dd": 0.40,
        "pivot_lens_min": 60,
        "pivot_lens_shift_min": 60,
        "demand_led_volume_growth": 0.08,
        "supply_shock_max_volume_growth": 0.05,
        "supply_shock_min_realisation": 0.03,
        "inventory_gain_margin_jump": 0.04,
        "qip_window_days": 365,
    },
}


STAGE_META = {
    "PEAK_PESSIMISM": {
        "meaning": "The market is pricing a permanent decline; the business may be near a cyclical trough.",
        "action": "Start fundamental work and wait for a turning signal before acting.",
    },
    "EARLY_RECOVERY": {
        "meaning": "At least two independent turning signals have fired while the stock is still depressed.",
        "action": "Build conviction only as evidence accumulates; verify that the signals are not one-offs.",
    },
    "CYCLE_CONFIRMED": {
        "meaning": "Demand-led growth is visible and the multiple has begun to normalise.",
        "action": "Review the position against valuation and the durability of the demand signal.",
    },
    "PEAK_OPTIMISM": {
        "meaning": "The cycle is consensus and the price already embeds it; late-cycle signals are present.",
        "action": "Late-cycle risks dominate; the burden of proof is on the bull case.",
    },
    "DECLINE": {
        "meaning": "Earnings are still falling and no turn is visible.",
        "action": "Wait; do not confuse a low price with an early cycle.",
    },
    "MIXED": {
        "meaning": "The evidence is contradictory and no stage rule dominates.",
        "action": "Resolve the blocking rule before drawing a conclusion.",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def lin(value: float, x0: float, x1: float) -> float:
    if x1 == x0:
        return 0.0
    return clamp((value - x0) / (x1 - x0))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def wmean(pairs: list[tuple[float, float | None]]) -> float | None:
    usable = [(weight, value) for weight, value in pairs if value is not None and weight > 0]
    if not usable:
        return None
    total = sum(weight for weight, _ in usable)
    if total <= 0:
        return None
    return sum(weight * value for weight, value in usable) / total


def safe_div(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def pct_rank(history: list[float], current: float) -> float:
    below = sum(1 for value in history if value < current)
    equal = sum(1 for value in history if value == current)
    return (below + 0.5 * equal) / len(history) * 100



def available(item: dict, as_of: date, lag_days: int) -> bool:
    reported = parse_date(item.get("reported_on"))
    if reported:
        return reported <= as_of
    period = parse_date(item.get("period_end"))
    if not period:
        return False
    return period + timedelta(days=lag_days) <= as_of


def consecutive_periods(items: list[dict], max_days: int) -> bool:
    if len(items) < 2:
        return False
    for first, second in zip(items, items[1:]):
        first_day = parse_date(first.get("period_end"))
        second_day = parse_date(second.get("period_end"))
        if not first_day or not second_day or (second_day - first_day).days > max_days:
            return False
    return True


def point_in_time(items, as_of: date, lag_days: int) -> tuple[list[dict], list[str]]:
    kept, dropped = [], []
    for item in items or []:
        if available(item, as_of, lag_days):
            kept.append(item)
        else:
            dropped.append(str(item.get("period_end") or item.get("reported_on") or "?"))
    kept.sort(key=lambda item: parse_date(item.get("period_end")) or date.min)
    return kept, dropped


def available_calls(data: dict, as_of: date) -> tuple[list[dict], list[str]]:
    calls = []
    dropped = []
    for call in (data.get("qualitative") or {}).get("concalls") or []:
        day = parse_date(call.get("date"))
        if day and day <= as_of:
            calls.append(call)
        elif day:
            dropped.append(day.isoformat())
    calls.sort(key=lambda call: parse_date(call.get("date")) or date.min)
    return calls, dropped


class Company:
    def __init__(self, data: dict, config: dict):
        self.data = data
        self.config = config
        self.th = config["thresholds"]
        self.as_of = parse_date(data.get("as_of"))
        if not self.as_of:
            raise ValueError("as_of is required (YYYY-MM-DD)")
        self.excluded: dict[str, list[str]] = {"quarterly": [], "annual": [], "shareholding": [], "valuation": [], "price": [], "segments": [], "calls": []}
        self._valuation_done = False
        self._valuation_cache = None

        lag = config["reporting_lag_days"]
        self.quarters, self.excluded["quarterly"] = point_in_time(data.get("quarterly"), self.as_of, lag["quarter"])
        self.annuals, self.excluded["annual"] = point_in_time(data.get("annual"), self.as_of, lag["annual"])
        self.holdings, self.excluded["shareholding"] = point_in_time(
            data.get("shareholding"), self.as_of, lag["shareholding"]
        )
        self.segments_raw, self.excluded["segments"] = point_in_time(
            data.get("segments"), self.as_of, lag["quarter"]
        )

        self.price = self._price()
        self.ttm = self._ttm()
        self.cycle = self._cycle()
        self.risk = self._risk()
        self.calls, self.excluded["calls"] = available_calls(data, self.as_of)
        self.evidence: list[str] = []

    # ------------------------------------------------------------------ price
    def _price(self) -> dict:
        price = self.data.get("price") or {}
        history = []
        for point in price.get("history") or []:
            day = parse_date(point.get("date"))
            if day and point.get("close") is not None and day <= self.as_of:
                history.append((day, float(point["close"])))
            elif day and day > self.as_of:
                self.excluded["price"].append(day.isoformat())
        history.sort()
        if history:
            current = history[-1][1]
            three_year = [value for day, value in history if day >= self.as_of - timedelta(days=1095)]
            one_year = [value for day, value in history if day >= self.as_of - timedelta(days=365)]
            high_3y = max(three_year) if three_year else max(value for _, value in history)
            low_52w = min(one_year) if one_year else min(value for _, value in history)
        else:
            current = price.get("current")
            high_3y = price.get("high_3y")
            low_52w = price.get("low_52w")
        drawdown = None
        off_low = None
        if current is not None and high_3y:
            drawdown = max(0.0, 1 - float(current) / float(high_3y))
        if current is not None and low_52w:
            off_low = float(current) / float(low_52w) - 1
        return {
            "current": current,
            "high_3y": high_3y,
            "low_52w": low_52w,
            "drawdown": drawdown,
            "off_low": off_low,
        }

    # -------------------------------------------------------------------- ttm
    def _sum(self, rows: list[dict], key: str):
        values = [row.get(key) for row in rows]
        if any(value is None for value in values):
            return None
        return sum(float(value) for value in values)

    def _ttm(self) -> dict:
        last4 = self.quarters[-4:] if len(self.quarters) >= 4 else []
        prior4 = self.quarters[-8:-4] if len(self.quarters) >= 8 else []
        result = {"available": bool(last4)}
        if last4:
            result.update(
                revenue=self._sum(last4, "revenue"),
                ebitda=self._sum(last4, "ebitda"),
                depreciation=self._sum(last4, "depreciation"),
                interest=self._sum(last4, "interest"),
                pat=self._sum(last4, "pat"),
                volume=self._sum(last4, "volume"),
                gross_profit=self._sum(last4, "gross_profit"),
            )
            if result["revenue"] and result["ebitda"] is not None:
                result["margin"] = result["ebitda"] / result["revenue"]
        if prior4:
            result["prior_revenue"] = self._sum(prior4, "revenue")
            result["prior_ebitda"] = self._sum(prior4, "ebitda")
            result["prior_volume"] = self._sum(prior4, "volume")
        if result.get("revenue") and result.get("prior_revenue"):
            result["revenue_growth"] = result["revenue"] / result["prior_revenue"] - 1
        if result.get("ebitda") is not None and result.get("prior_ebitda"):
            result["ebitda_growth"] = result["ebitda"] / result["prior_ebitda"] - 1
        if result.get("volume") and result.get("prior_volume"):
            result["volume_growth"] = result["volume"] / result["prior_volume"] - 1
        if result.get("revenue_growth") is not None and result.get("volume_growth") is not None:
            result["realisation_growth"] = (1 + result["revenue_growth"]) / (1 + result["volume_growth"]) - 1
        return result

    def _cycle(self) -> dict:
        annuals = [row for row in self.annuals if row.get("revenue")][-10:]
        margins = [row["ebitda"] / row["revenue"] for row in annuals if row.get("ebitda") is not None]
        ebitdas = [row["ebitda"] for row in annuals if row.get("ebitda") is not None]
        if len(margins) >= 3:
            return {
                "basis": "annual",
                "n": len(margins),
                "margin": sum(margins) / len(margins),
                "ebitda": sum(ebitdas) / len(ebitdas),
            }
        quarters = [row for row in self.quarters if row.get("revenue")][-8:]
        margins = [row["ebitda"] / row["revenue"] for row in quarters if row.get("ebitda") is not None]
        ebitdas = [row["ebitda"] for row in quarters if row.get("ebitda") is not None]
        if len(margins) >= 8:
            return {
                "basis": "quarterly",
                "n": len(margins),
                "margin": sum(margins) / len(margins),
                "ebitda": (sum(ebitdas) / len(ebitdas) * 4),
            }
        return {"basis": None, "n": 0, "margin": None, "ebitda": None}

    def _risk(self) -> dict:
        coverage = None
        if self.ttm.get("ebitda") is not None and self.ttm.get("interest"):
            coverage = (self.ttm["ebitda"] - (self.ttm.get("depreciation") or 0)) / self.ttm["interest"]
        debt_now = self.annuals[-1].get("debt") if self.annuals else None
        debt_prev = self.annuals[-2].get("debt") if len(self.annuals) >= 2 else None
        equity = self.annuals[-1].get("equity") if self.annuals else None
        cfo = [row.get("cfo") for row in self.annuals[-3:]] if len(self.annuals) >= 3 else []
        last_three_annuals = self.annuals[-3:]
        last_three_holdings = self.holdings[-3:]
        pledge_now = self.holdings[-1].get("pledge_pct") if self.holdings else None
        pledge_prev = self.holdings[-3].get("pledge_pct") if len(self.holdings) >= 3 else None
        return {
            "coverage": coverage,
            "debt_now": debt_now,
            "debt_prev": debt_prev,
            "equity": equity,
            "debt_rising": (
                debt_now is not None
                and debt_prev is not None
                and debt_now > debt_prev
                and consecutive_periods(self.annuals[-2:], 400)
            ),
            "debt_to_equity": safe_div(debt_now, equity),
            "cfo": cfo,
            "cfo_negative_3y": (
                len(cfo) == 3
                and consecutive_periods(last_three_annuals, 400)
                and all(value is not None and value < 0 for value in cfo)
            ),
            "pledge": pledge_now,
            "pledge_change": (
                (pledge_now - pledge_prev)
                if pledge_now is not None
                and pledge_prev is not None
                and consecutive_periods(last_three_holdings, 220)
                else None
            ),
        }

    # ------------------------------------------------------------ score 1 base
    def valuation(self) -> dict | None:
        if self._valuation_done:
            return self._valuation_cache
        self._valuation_done = True
        valuation = self.data.get("valuation") or {}
        for metric in self.config["valuation_metric_preference"]:
            current = valuation.get(f"{metric}_current")
            raw_history = valuation.get(f"{metric}_history") or []
            history = []
            for point in raw_history:
                if isinstance(point, dict):
                    day = parse_date(point.get("date"))
                    if day and day > self.as_of:
                        self.excluded["valuation"].append(day.isoformat())
                        continue
                    value = point.get("value")
                else:
                    value = point
                if value is not None:
                    history.append(float(value))
            if current is None and history:
                current = history[-1]
            if current is None or len(history) < 3:
                continue
            percentile = pct_rank(history, float(current))
            result = {
                "metric": metric,
                "current": float(current),
                "percentile": percentile,
                "score": 100 - percentile,
                "n": len(history),
                "history_min": min(history),
                "history_max": max(history),
            }
            self._valuation_cache = result
            return result
        self._valuation_cache = None
        return None

    def earnings_stress(self) -> dict | None:
        avg_margin = self.cycle.get("margin")
        ttm_margin = self.ttm.get("margin")
        if avg_margin is None or ttm_margin is None or avg_margin <= 0:
            part_a = None
        else:
            part_a = lin((avg_margin - ttm_margin) / avg_margin, 0, self.th["earnings_stress_full"])
        pairs = 0
        below = 0
        by_month = {}
        for row in self.quarters:
            day = parse_date(row.get("period_end"))
            if day and row.get("ebitda") is not None:
                by_month[(day.year, day.month)] = row["ebitda"]
        for row in self.quarters[-8:]:
            day = parse_date(row.get("period_end"))
            if not day or row.get("ebitda") is None:
                continue
            prior = by_month.get((day.year - 1, day.month))
            if prior is None:
                continue
            pairs += 1
            below += 1 if row["ebitda"] < prior else 0
        part_b = (below / pairs) if pairs else None
        combined = wmean([(0.6, part_a), (0.4, part_b)])
        if combined is None:
            return None
        return {
            "score": combined * 100,
            "part_a": None if part_a is None else part_a * 100,
            "part_b": None if part_b is None else part_b * 100,
            "avg_margin": avg_margin,
            "ttm_margin": ttm_margin,
            "pairs": pairs,
        }

    def neglect(self) -> dict | None:
        parts = []
        detail = {}
        candidates = [
            call for call in self.calls[-3:] if call.get("duration_min") or call.get("analyst_questions")
        ]
        if candidates:
            latest = candidates[-1]
            day = parse_date(latest.get("date"))
            if day and (self.as_of - day).days <= self.th["neglect_call_max_age_days"]:
                if latest.get("duration_min") is not None:
                    value = lin(
                        float(latest["duration_min"]),
                        self.th["concall_long_min"],
                        self.th["concall_short_min"],
                    )
                    parts.append(value)
                    detail["call_length"] = value * 100
                if latest.get("analyst_questions") is not None:
                    value = lin(
                        float(latest["analyst_questions"]),
                        self.th["questions_many"],
                        self.th["questions_few"],
                    )
                    parts.append(value)
                    detail["questions"] = value * 100
        if len(self.holdings) >= 5 and consecutive_periods(self.holdings[-5:], 400):
            latest = self.holdings[-1]
            earlier = self.holdings[-5]
            change = (latest.get("fii") or 0) + (latest.get("dii") or 0) - (
                (earlier.get("fii") or 0) + (earlier.get("dii") or 0)
            )
            ignore = self.price.get("off_low") is not None and self.price["off_low"] >= self.th["rally_off_low"] and change < 0
            if not ignore:
                value = lin(change, self.th["institutional_change_pp"], -self.th["institutional_change_pp"])
                parts.append(value)
                detail["institutional_change_pp"] = change
                detail["institutional"] = value * 100
            else:
                detail["institutional_change_pp"] = change
                detail["institutional_ignored"] = "falling holdings into a rally or dilution"
        if not parts:
            return None
        return {"score": sum(parts) / len(parts) * 100, "parts": detail}

    def sector_breadth(self) -> dict | None:
        peers = self.data.get("peers") or []
        values = [float(peer["drawdown_from_3y_high_pct"]) for peer in peers if peer.get("drawdown_from_3y_high_pct") is not None]
        if len(values) < self.th["min_peers"]:
            return None
        share = sum(1 for value in values if value >= self.th["sector_breadth_dd"] * 100) / len(values)
        return {
            "score": lin(share, 0, self.th["sector_breadth_full"]) * 100,
            "share": share,
            "n": len(values),
            "values": values,
        }

    def pain(self) -> dict:
        signals = {
            "valuation": (self.config["level_weights"]["valuation"], self.valuation()),
            "drawdown": (self.config["level_weights"]["drawdown"], None),
            "earnings_stress": (self.config["level_weights"]["earnings_stress"], self.earnings_stress()),
            "neglect": (self.config["level_weights"]["neglect"], self.neglect()),
            "sector_breadth": (self.config["level_weights"]["sector_breadth"], self.sector_breadth()),
        }
        if self.price.get("drawdown") is not None:
            drawdown = {
                "score": lin(self.price["drawdown"], 0, self.th["drawdown_full"]) * 100,
                "drawdown": self.price["drawdown"],
            }
            signals["drawdown"] = (signals["drawdown"][0], drawdown)
        available = {key: value for key, (_, value) in signals.items() if value is not None}
        score = wmean([(weight, None if value is None else value["score"]) for weight, value in signals.values()])
        return {"score": None if score is None else round(score, 1), "signals": available, "weights": {k: v[0] for k, v in signals.items()}}

    # --------------------------------------------------------------- turning
    def promoter(self) -> dict | None:
        trades = self.data.get("insider_trades")
        promoter_trades = []
        if trades is not None:
            cutoff = self.as_of - timedelta(days=self.th["promoter_window_days"])
            for trade in trades:
                day = parse_date(trade.get("date"))
                if not day or day > self.as_of or day < cutoff:
                    continue
                category = str(trade.get("person_category", "")).lower()
                mode = str(trade.get("mode", "")).lower()
                if "promoter" in category and mode in {"market", "open_market", "open market"}:
                    promoter_trades.append(trade)
        holding_rows = [row for row in self.holdings if row.get("promoter") is not None]
        holdings = [row["promoter"] for row in holding_rows]
        last3 = holdings[-3:]
        no_promoter = bool(self.data.get("no_promoter")) or (len(last3) == 3 and all(value == 0 for value in last3))
        if no_promoter and not promoter_trades:
            return {"na": True, "reason": "no promoter group or promoter holding is zero"}
        net = 0.0
        if trades is not None:
            for trade in promoter_trades:
                value = float(trade.get("value_cr") or 0)
                net += value if str(trade.get("type", "")).lower() == "buy" else -value
        holding_change = None
        if len(holdings) >= 3 and consecutive_periods(holding_rows[-3:], 220):
            holding_change = holdings[-1] - holdings[-3]
        selling = False
        fired = False
        if trades is not None and net != 0:
            if net > 0:
                score = 80 + (20 if holding_change and holding_change > 0 else 0)
                fired = True
            else:
                score = 0
                selling = True
        elif holding_change is not None:
            if holding_change >= self.th["promoter_holding_change_pp"]:
                score = 60
                fired = True
            elif holding_change <= -self.th["promoter_holding_change_pp"]:
                score = 0
                selling = True
            else:
                score = 20
        elif trades is not None:
            score = 20
        else:
            return None
        return {
            "score": score,
            "net_cr": net,
            "holding_change_pp": holding_change,
            "fired": fired,
            "selling": selling,
            "na": False,
        }

    def sentiment(self) -> dict | None:
        calls = [call for call in self.calls if call.get("mgmt_tone") is not None and call.get("analyst_skepticism") is not None]
        if not calls:
            return None
        window = calls[-3:]
        latest = window[-1]
        tone = float(latest["mgmt_tone"])
        skepticism = float(latest["analyst_skepticism"])
        delta = tone - float(window[0]["mgmt_tone"])
        last_two = self.calls[-2:]
        misses = sum(1 for call in last_two if call.get("prior_guidance_met") is False)
        dd = self.price.get("drawdown")
        if (
            len(last_two) == 2
            and all(call.get("prior_guidance_met") is not None for call in last_two)
            and not any(call.get("prior_guidance_met") is False for call in last_two)
        ):
            if dd is not None and dd >= self.th["market_skepticism_dd"] and skepticism < 3:
                skepticism = 3
        score = (
            0.5 * lin(tone, 1, 5)
            + 0.3 * lin(skepticism, 1, 5)
            + 0.2 * lin(delta, 0, 2)
        )
        credibility = 1.0
        if misses == 1:
            credibility = self.th["credibility_one_miss"]
        elif misses >= 2:
            credibility = self.th["credibility_two_misses"]
        score *= credibility
        return {
            "score": score * 100,
            "tone": tone,
            "skepticism": skepticism,
            "delta": delta,
            "misses": misses,
            "credibility": credibility,
            "fired": tone >= 4 and skepticism >= 3 and misses < 2,
        }

    def margin_inflection(self) -> dict | None:
        rows = self.quarters[-8:]
        if len(rows) < 4:
            return None
        gross_ok = all(row.get("gross_profit") is not None and row.get("revenue") for row in rows)
        margins = []
        for row in rows:
            if not row.get("revenue"):
                margins.append(None)
                continue
            if gross_ok:
                margins.append(row["gross_profit"] / row["revenue"])
            elif row.get("ebitda") is not None:
                margins.append(row["ebitda"] / row["revenue"])
            else:
                margins.append(None)
        if any(value is None for value in margins):
            return None
        trough_index = min(range(len(margins)), key=lambda index: margins[index])
        latest_index = len(margins) - 1
        rise = margins[latest_index] - margins[trough_index]
        if trough_index == latest_index:
            score = 0
        elif trough_index == latest_index - 1:
            score = 50 if rise >= self.th["inflection_min_rise"] else 25
        else:
            last_two = margins[-1] - margins[-2] >= 0 and margins[-2] - margins[-3] >= 0
            score = 100 if last_two else 40
            if rise < self.th["inflection_min_rise"]:
                score /= 2
        capped = False
        if not gross_ok and self.cycle.get("margin") is not None:
            if margins[trough_index] > (1 - self.th["inflection_trough_below_avg"]) * self.cycle["margin"]:
                score = min(score, 30)
                capped = True
        return {
            "score": score,
            "basis": "gross" if gross_ok else "ebitda",
            "trough_index": trough_index,
            "trough_margin": margins[trough_index],
            "latest_margin": margins[latest_index],
            "rise": rise,
            "capped_steady_uptrend": capped,
            "fired": score >= 50,
        }

    def market_share(self) -> dict | None:
        recent = self.calls[-2:]
        if not recent:
            return None
        claimed = [call.get("market_share_gain_claimed") for call in recent if call.get("market_share_gain_claimed") is not None]
        if not claimed:
            return None
        if any(bool(value) for value in claimed):
            return {"score": 100, "fired": True, "claimed": True}
        return {"score": 0, "fired": False, "claimed": False}

    def turning(self) -> dict:
        promoter = self.promoter()
        signals = {
            "promoter": (self.config["turn_weights"]["promoter"], promoter),
            "sentiment_gap": (self.config["turn_weights"]["sentiment_gap"], self.sentiment()),
            "margin_inflection": (self.config["turn_weights"]["margin_inflection"], self.margin_inflection()),
            "market_share": (self.config["turn_weights"]["market_share"], self.market_share()),
        }
        applicable = {key: (weight, value) for key, (weight, value) in signals.items() if not (value and value.get("na"))}
        score = wmean([(weight, None if value is None else value["score"]) for weight, value in applicable.values()])
        fired = [key for key, (_, value) in applicable.items() if value and value.get("fired")]
        return {
            "score": None if score is None else round(score, 1),
            "signals": {key: value for key, (_, value) in applicable.items() if value is not None},
            "weights": {key: weight for key, (weight, _) in signals.items()},
            "applicable_weights": {key: weight for key, (weight, _) in applicable.items()},
            "fired": fired,
            "n_fired": len(fired),
        }

    def earnings_delta(self) -> dict | None:
        ttm = self.ttm.get("ebitda")
        avg = self.cycle.get("ebitda")
        if ttm is None or avg is None:
            return None
        if ttm <= 0 and avg > 0:
            potential = None
            score = 100.0
        elif ttm > 0:
            potential = max(0.0, (avg - ttm) / ttm)
            score = lin(potential, 0, self.th["delta_full"]) * 100
        else:
            return None
        inflection = self.margin_inflection()
        halved = False
        if inflection is not None and not inflection["fired"]:
            score *= self.th["delta_before_inflection"]
            halved = True
        return {"score": score, "potential": potential, "ttm_ebitda": ttm, "avg_ebitda": avg, "halved": halved}

    def score1(self) -> dict:
        pain = self.pain()
        turning = self.turning()
        delta = self.earnings_delta()
        weights = self.config["score1_weights"]
        score = wmean(
            [
                (weights["level"], pain["score"]),
                (weights["turn"], turning["score"]),
                (weights["delta"], None if delta is None else delta["score"]),
            ]
        )
        leaf_total = 0.0
        leaf_available = 0.0
        for key, weight in self.config["level_weights"].items():
            leaf_total += weights["level"] * weight
            if key in pain["signals"]:
                leaf_available += weights["level"] * weight
        for key, weight in self.config["turn_weights"].items():
            if key == "promoter" and "promoter" not in turning["applicable_weights"]:
                continue
            leaf_total += weights["turn"] * weight
            if key in turning["signals"]:
                leaf_available += weights["turn"] * weight
        leaf_total += weights["delta"]
        if delta is not None:
            leaf_available += weights["delta"]
        coverage = leaf_available / leaf_total if leaf_total else 0.0
        vetoes, red_flags = self.vetoes()
        capped = False
        if vetoes:
            score = self.th["veto_cap"]
            capped = True
        return {
            "score": None if score is None else round(score, 1),
            "pain": pain["score"],
            "turn": turning["score"],
            "delta": None if delta is None else round(delta["score"], 1),
            "coverage": round(coverage, 3),
            "pain_detail": pain,
            "turning_detail": turning,
            "delta_detail": delta,
            "vetoes": vetoes,
            "red_flags": red_flags,
            "veto_capped": capped,
        }

    # --------------------------------------------------------------- score 2
    def segment_series(self) -> dict | None:
        if not self.segments_raw:
            return None
        groups: dict[date, list[dict]] = {}
        for row in self.segments_raw:
            day = parse_date(row.get("period_end"))
            if day:
                groups.setdefault(day, []).append(row)
        if len(groups) < 2:
            return None
        periods = sorted(groups)
        gaps = [(periods[i + 1] - periods[i]).days for i in range(len(periods) - 1)]
        pivot = self.data.get("pivot") or {}
        period_hint = str(pivot.get("segment_period", "")).lower()
        if period_hint.startswith("q"):
            quarterly = True
        elif period_hint.startswith("y"):
            quarterly = False
        else:
            quarterly = bool(gaps) and (sum(gaps) / len(gaps)) <= 120
        window = [day for day in periods if day >= self.as_of - timedelta(days=365 * (5 if not quarterly else 3))][-12:]
        new_names = {str(name).lower() for name in pivot.get("new_segments") or []}
        if not new_names:
            return None
        points = []
        for day in window:
            rows = groups[day]
            total_revenue = sum(float(row.get("revenue") or 0) for row in rows)
            new_revenue = sum(
                float(row.get("revenue") or 0)
                for row in rows
                if str(row.get("name", "")).lower() in new_names
            )
            if total_revenue <= 0:
                continue
            points.append({"date": day, "total": total_revenue, "new": new_revenue, "rows": rows})
        if len(points) < 2:
            return None
        first, last = points[0], points[-1]
        first_share = first["new"] / first["total"]
        last_share = last["new"] / last["total"]
        return {
            "quarterly": quarterly,
            "points": points,
            "first": first,
            "last": last,
            "first_share": first_share,
            "last_share": last_share,
            "new_names": new_names,
        }

    def segment_shift(self) -> dict | None:
        series = self.segment_series()
        if not series:
            return None
        change_pp = (series["last_share"] - series["first_share"]) * 100
        mix = 0.7 * lin(change_pp, 0, self.th["mix_change_full_pp"]) + 0.3 * lin(
            series["last_share"] * 100, 0, self.th["mix_share_full_pct"]
        )
        recent = series["points"][-4:] if series["quarterly"] else series["points"][-1:]
        new_revenue = sum(point["new"] for point in recent)
        total_revenue = sum(point["total"] for point in recent)
        base_revenue = total_revenue - new_revenue
        new_ebit = 0.0
        base_ebit = 0.0
        ebit_ok = True
        for point in recent:
            for row in point["rows"]:
                ebit = row.get("ebit")
                if ebit is None:
                    ebit_ok = False
                    continue
                if str(row.get("name", "")).lower() in series["new_names"]:
                    new_ebit += float(ebit)
                else:
                    base_ebit += float(ebit)
        margin_diff = None
        new_margin = None
        base_margin = None
        if ebit_ok and new_revenue > 0 and base_revenue > 0:
            new_margin = new_ebit / new_revenue
            base_margin = base_ebit / base_revenue
            if base_margin > 0:
                margin_diff = lin(
                    new_margin / base_margin, 1.0, self.th["margin_ratio_full"]
                )
        score = wmean(
            [
                (self.config["segment_shift_split"]["mix"], mix),
                (self.config["segment_shift_split"]["margin_diff"], margin_diff),
            ]
        )
        return {
            "score": None if score is None else score * 100,
            "mix": mix * 100,
            "change_pp": change_pp,
            "last_share_pct": series["last_share"] * 100,
            "margin_diff": None if margin_diff is None else margin_diff * 100,
            "new_margin": new_margin,
            "base_margin": base_margin,
            "window": [series["first"]["date"].isoformat(), series["last"]["date"].isoformat()],
        }

    def pivot_size(self) -> dict | None:
        series = self.segment_series()
        if not series:
            return None
        pivot = self.data.get("pivot") or {}
        target_revenue = pivot.get("target_revenue")
        target_margin = pivot.get("target_margin_pct")
        if target_revenue is None or target_margin is None:
            return None
        last = series["last"]
        multiplier = 4 if series["quarterly"] else 1
        new_revenue = last["new"] * multiplier
        base_revenue = (last["total"] - last["new"]) * multiplier
        new_ebit = 0.0
        base_ebit = 0.0
        ebit_ok = True
        for row in last["rows"]:
            ebit = row.get("ebit")
            if ebit is None:
                ebit_ok = False
                continue
            if str(row.get("name", "")).lower() in series["new_names"]:
                new_ebit += float(ebit) * multiplier
            else:
                base_ebit += float(ebit) * multiplier
        estimate_margin_used = False
        if not ebit_ok:
            if self.ttm.get("margin") is None:
                return None
            new_ebit = new_revenue * self.ttm["margin"]
            base_ebit = base_revenue * self.ttm["margin"]
            estimate_margin_used = True
        if base_ebit <= 0 or new_ebit < 0:
            return None
        expected_new = new_ebit + self.th["pivot_success_prob"] * (
            float(target_revenue) * float(target_margin) / 100 - new_ebit
        )
        orbit = (base_ebit + expected_new) / (base_ebit + new_ebit)
        target_source = str(pivot.get("target_source") or "")
        return {
            "score": lin(orbit, 1, self.th["orbit_full"]) * 100,
            "orbit": orbit,
            "target_source": target_source or None,
            "estimate": "estimate" in target_source.lower() or "claude" in target_source.lower(),
            "new_revenue": new_revenue,
            "base_revenue": base_revenue,
            "new_ebit": new_ebit,
            "base_ebit": base_ebit,
            "target_revenue": target_revenue,
            "target_margin_pct": target_margin,
            "estimate_margin_used": estimate_margin_used,
        }

    def capability(self) -> dict | None:
        pivot = self.data.get("pivot") or {}
        proof = pivot.get("capability_proof")
        if proof is None:
            return None
        value = clamp(float(proof) / 5)
        built = str(pivot.get("capability_built_vs_bought", "")).lower()
        adjustment = 0.10 if built == "bought" else 0.05 if built == "mixed" else 0.0
        value = clamp(value - adjustment)
        return {"score": value * 100, "rubric": float(proof), "built_vs_bought": built, "adjustment": adjustment}

    def management(self) -> dict | None:
        pivot = self.data.get("pivot") or {}
        track = pivot.get("management_track_record")
        if track is None:
            return None
        return {"score": clamp(float(track) / 5) * 100, "rubric": float(track)}

    def mispricing(self) -> dict | None:
        pivot = self.data.get("pivot") or {}
        pure = pivot.get("pure_play_multiple")
        multiple_type = str(pivot.get("multiple_type", "")).lower()
        if pure is None or not multiple_type:
            return None
        company = (self.data.get("valuation") or {}).get(f"{multiple_type}_current")
        if company is None:
            return None
        ratio = float(company) / float(pure)
        return {
            "score": lin(ratio, 1.0, self.th["mispricing_full_ratio"]) * 100,
            "ratio": ratio,
            "company_multiple": company,
            "pure_play_multiple": pure,
        }

    def tailwind(self) -> dict | None:
        pivot = self.data.get("pivot") or {}
        value = pivot.get("external_tailwind")
        if value is None:
            return None
        return {"score": clamp(float(value) / 5) * 100, "rubric": float(value)}

    def build_phase(self) -> dict | None:
        rows = [row for row in self.annuals if row.get("capex") is not None and row.get("revenue")]
        if len(rows) < 5:
            return None
        if len(rows) >= 7:
            recent, prior = rows[-4:], rows[-7:-4]
        else:
            recent, prior = rows[-3:], rows[-5:-3]
        recent_ratios = [row["capex"] / row["revenue"] for row in recent]
        prior_ratios = [row["capex"] / row["revenue"] for row in prior]
        if not prior_ratios or sum(prior_ratios) == 0:
            return None
        ratio = max(recent_ratios) / (sum(prior_ratios) / len(prior_ratios))
        capability = self.capability()
        score = lin(ratio, 1, self.th["build_phase_full_ratio"]) * 100
        if not capability or capability["rubric"] < 3:
            score *= 0.5
        return {
            "score": score,
            "ratio": ratio,
            "note": "capex/sales step-up" if ratio >= self.th["build_phase_capex_ratio"] else None,
            "capability_below_3": not capability or capability["rubric"] < 3,
        }

    def score2(self) -> dict:
        weights = self.config["score2_weights"]
        signals = {
            "segment_shift": self.segment_shift(),
            "pivot_size": self.pivot_size(),
            "capability": self.capability(),
            "management": self.management(),
            "mispricing": self.mispricing(),
            "tailwind": self.tailwind(),
            "build_phase": self.build_phase(),
        }
        score = wmean([(weights[key], None if value is None else value["score"]) for key, value in signals.items()])
        available_weight = sum(weights[key] for key, value in signals.items() if value is not None)
        coverage = available_weight / sum(weights.values()) if weights else 0.0
        judgment_weight = sum(weights[key] for key in ("capability", "management", "tailwind") if signals[key] is not None)
        judgment_share = judgment_weight / available_weight if available_weight else 0.0
        management_gate = False
        if signals["management"] is not None and signals["management"]["rubric"] < self.th["mgmt_gate_min"]:
            score = self.th["mgmt_gate_cap"]
            management_gate = True
        vetoes = self.score2_vetoes()
        if vetoes:
            score = self.th["veto_cap"]
        return {
            "score": None if score is None else round(score, 1),
            "coverage": round(coverage, 3),
            "judgment_share": round(judgment_share, 3),
            "signals": {key: value for key, value in signals.items() if value is not None},
            "vetoes": vetoes,
            "management_gate": management_gate,
        }

    # --------------------------------------------------------------- flags
    def latest_call(self) -> dict | None:
        return self.calls[-1] if self.calls else None

    def vetoes(self) -> tuple[list[str], list[str]]:
        flags: list[str] = []
        red: list[str] = []
        risk = self.risk
        coverage = risk["coverage"]
        debt_veto = (
            coverage is not None
            and coverage < 2
            and risk["debt_rising"]
            and (risk["debt_to_equity"] is None or risk["debt_to_equity"] >= self.th["veto_min_debt_to_equity"])
        )
        if debt_veto:
            flags.append("interest coverage < 2x with rising debt and D/E >= 0.5")
        elif coverage is not None and coverage < 2:
            red.append("interest coverage < 2x")
        if risk["cfo_negative_3y"]:
            flags.append("operating cash flow negative for 3 straight years")
        pledge = risk.get("pledge")
        pledge_change = risk.get("pledge_change")
        if (pledge is not None and pledge > 25) or (pledge_change is not None and pledge_change > 2):
            flags.append("promoter pledge > 25% or up > 2pp over two quarters")
        governance = (self.data.get("qualitative") or {}).get("governance_flags") or []
        if governance:
            flags.append("governance flag: " + ", ".join(str(item) for item in governance))
        if (self.data.get("qualitative") or {}).get("lost_share_in_downturn"):
            flags.append("lost market share in the downturn")
        margins = self.quarter_margins()
        if len(margins) >= 2 and margins[-1] - margins[-2] >= self.th["inventory_gain_margin_jump"]:
            red.append("margin up >= 4pp in one quarter (check for inventory gains)")
        acquisitions = [
            action
            for action in self.data.get("corporate_actions") or []
            if str(action.get("type", "")).lower() == "acquisition"
            and parse_date(action.get("date"))
            and parse_date(action["date"]) <= self.as_of
            and (self.as_of - parse_date(action["date"])).days <= self.th["acquisition_window_days"]
            and self.quarters
            and parse_date(action["date"]) <= (parse_date(self.quarters[-1].get("period_end")) or date.min)
        ]
        if acquisitions and self.ttm.get("ebitda_growth") is not None and self.ttm["ebitda_growth"] > 0:
            red.append("growth includes an acquisition")
        promoter = self.promoter()
        if promoter and promoter.get("holding_change_pp") is not None and promoter["holding_change_pp"] <= -self.th["promoter_exit_flag_pp"]:
            red.append("promoter holding down >= 5pp over two quarters")
        return flags, red

    def score2_vetoes(self) -> list[str]:
        flags: list[str] = []
        pledge = self.risk.get("pledge")
        pledge_change = self.risk.get("pledge_change")
        if (pledge is not None and pledge > 25) or (pledge_change is not None and pledge_change > 2):
            flags.append("promoter pledge > 25% or up > 2pp over two quarters")
        governance = (self.data.get("qualitative") or {}).get("governance_flags") or []
        if governance:
            flags.append("governance flag: " + ", ".join(str(item) for item in governance))
        return flags

    def quarter_margins(self) -> list[float]:
        margins = []
        for row in self.quarters[-8:]:
            if row.get("revenue") and row.get("ebitda") is not None:
                margins.append(row["ebitda"] / row["revenue"])
        return margins

    def supply_demand(self) -> str:
        ttm = self.ttm
        if ttm.get("volume_growth") is not None and ttm.get("revenue_growth") is not None:
            if ttm["volume_growth"] >= self.th["demand_led_volume_growth"]:
                return "DEMAND_LED"
            realisation = ttm.get("realisation_growth")
            if (
                realisation is not None
                and realisation > self.th["supply_shock_min_realisation"]
                and ttm["volume_growth"] < self.th["supply_shock_max_volume_growth"]
            ):
                return "SUPPLY_SHOCK"
            return "MIXED"
        shock = str((self.data.get("qualitative") or {}).get("shock_type", "")).lower()
        if shock in {"supply_shock", "supply"}:
            return "SUPPLY_SHOCK"
        if shock in {"demand_led", "demand"}:
            return "DEMAND_LED"
        if shock == "mixed":
            return "MIXED"
        return "UNKNOWN"

    # ---------------------------------------------------------------- stage
    def stage(self, score1: dict, score2: dict) -> dict:
        valuation = self.valuation()
        vp = valuation["percentile"] if valuation else None
        dd = self.price.get("drawdown")
        off_low = self.price.get("off_low")
        turning = score1["turning_detail"]
        n_fired = turning["n_fired"]
        promoter = self.promoter()
        promoter_exit = bool(
            promoter
            and promoter.get("holding_change_pp") is not None
            and promoter["holding_change_pp"] <= -self.th["promoter_exit_flag_pp"]
        )
        latest = self.latest_call()
        optimism = []
        if promoter and promoter.get("selling"):
            optimism.append("promoter selling")
        if any(
            str(action.get("type", "")).lower() in {"qip", "ofs"}
            and parse_date(action.get("date"))
            and parse_date(action["date"]) <= self.as_of
            and (self.as_of - parse_date(action["date"])).days <= self.th["qip_window_days"]
            for action in self.data.get("corporate_actions") or []
        ):
            optimism.append("QIP/OFS in the last 365 days")
        if latest and latest.get("aggressive_guidance"):
            optimism.append("aggressive guidance")
        if latest and latest.get("duration_min") is not None and latest["duration_min"] >= self.th["concall_long_min"]:
            optimism.append("long call >= 90 min")
        shift = score2["signals"].get("segment_shift", {}).get("score")
        capability = score2["signals"].get("capability", {}).get("rubric")
        if shift is not None:
            pivot_lens = shift >= self.th["pivot_lens_shift_min"] and capability is not None and capability >= 3
        else:
            pivot_lens = (
                score2["score"] is not None
                and score2["score"] >= self.th["pivot_lens_min"]
                and score2["coverage"] >= 0.5
            )
        growth = self.ttm.get("ebitda_growth")
        tag = self.supply_demand()
        blocked = ""
        stage = "MIXED"
        if (vp is not None and vp >= self.th["peak_opt_val_pct_alone"] and not pivot_lens) or (
            vp is not None
            and vp >= self.th["peak_opt_val_pct"]
            and len(optimism) >= self.th["peak_opt_signals"]
        ):
            stage = "PEAK_OPTIMISM"
        elif (
            growth is not None
            and growth >= self.th["confirmed_growth"]
            and tag == "DEMAND_LED"
            and n_fired >= 1
            and (vp is None or self.th["confirmed_val_pct_min"] <= vp < self.th["peak_opt_val_pct"])
        ):
            stage = "CYCLE_CONFIRMED"
        elif (
            n_fired >= self.th["early_turn_signals"]
            and (vp is None or vp <= self.th["early_val_pct_max"])
            and ((dd is not None and dd >= self.th["early_min_dd"]) or (off_low is not None and off_low >= self.th["early_min_off_low"]))
            and not promoter_exit
        ):
            stage = "EARLY_RECOVERY"
        elif (
            (vp is None or vp <= self.th["peak_pess_val_pct"])
            and dd is not None
            and dd >= self.th["peak_pess_dd"]
            and n_fired <= 1
        ):
            stage = "PEAK_PESSIMISM"
        elif growth is not None and growth < 0 and n_fired <= 1:
            stage = "DECLINE"
        else:
            if n_fired >= self.th["early_turn_signals"] and vp is not None and vp > self.th["early_val_pct_max"]:
                blocked = f"{n_fired} signals firing but valuation {vp:.0f}th percentile > {self.th['early_val_pct_max']} max"
            elif n_fired >= self.th["early_turn_signals"] and promoter_exit:
                blocked = "promoter exit of >= 5pp blocks EARLY_RECOVERY"
            elif n_fired >= self.th["early_turn_signals"] and (dd is None or dd < self.th["early_min_dd"]) and (off_low is None or off_low < self.th["early_min_off_low"]):
                blocked = f"turn signals firing but drawdown {0 if dd is None else dd * 100:.0f}% < 25% and off-low {0 if off_low is None else off_low * 100:.0f}% < 30%"
            elif growth is not None and growth < 0:
                blocked = "TTM EBITDA growth is negative and few turn signals fired"
            else:
                blocked = "no stage rule matched the current combination"
        low_confidence = vp is None or dd is None or score1["coverage"] < self.th["low_coverage"]
        meta = STAGE_META[stage]
        return {
            "stage": stage,
            "meaning": meta["meaning"],
            "action": meta["action"],
            "blocked_rule": blocked,
            "pivot_lens": pivot_lens,
            "promoter_exit": promoter_exit,
            "optimism_signals": optimism,
            "n_fired": n_fired,
            "low_confidence": low_confidence,
            "supply_demand": tag,
        }

    # --------------------------------------------------------------- output
    def price_check(self, stage: dict) -> str:
        valuation = self.valuation()
        vp = valuation["percentile"] if valuation else None
        if vp is None:
            text = "valuation history unavailable"
        elif vp >= 80:
            text = "rich vs own history: a good business may not be a good investment at this price"
            if stage["pivot_lens"]:
                text = "history reflects the old business mix; judge price on incremental earnings"
        elif vp <= 30:
            text = "cheap vs own history"
        else:
            text = "middle of range"
        forward = (self.data.get("valuation") or {}).get("pe_forward")
        if forward is not None:
            text += f"; forward P/E {forward}"
        return text

    def what_would_change(self, score1: dict, score2: dict, stage: dict) -> list[str]:
        hints = []
        missing_turn = [
            key
            for key, weight in self.config["turn_weights"].items()
            if key not in score1["turning_detail"]["signals"] and key in score1["turning_detail"]["applicable_weights"]
        ]
        if missing_turn:
            hints.append("Missing turning signals: " + ", ".join(missing_turn) + ".")
        if stage["stage"] == "MIXED" and stage["blocked_rule"]:
            hints.append("Blocking rule: " + stage["blocked_rule"] + ".")
        if stage["promoter_exit"]:
            hints.append("Promoter exit of >= 5pp blocks EARLY_RECOVERY.")
        sentiment = score1["turning_detail"]["signals"].get("sentiment_gap")
        if sentiment and sentiment["misses"] >= 2:
            hints.append("Two guidance misses cut sentiment credibility to half.")
        shift = score2["signals"].get("segment_shift", {}).get("score")
        capability = score2["signals"].get("capability", {}).get("rubric")
        if shift is not None and shift >= 50 and (capability is None or capability < 3):
            hints.append("Pivot lens is close: segment shift is firing but capability is below 3/5.")
        if score1["coverage"] < self.th["low_coverage"]:
            hints.append(
                f"Score 1 coverage is {score1['coverage'] * 100:.0f}%; add the missing pain/turning inputs before relying on it."
            )
        if score2["coverage"] < 0.5:
            hints.append(
                f"Score 2 coverage is {score2['coverage'] * 100:.0f}%; segment, target or rubric data would help most."
            )
        missing_pain = [
            key
            for key in self.config["level_weights"]
            if key not in score1["pain_detail"]["signals"]
        ]
        missing_pivot = [
            key
            for key in self.config["score2_weights"]
            if key not in score2["signals"]
        ]
        if score1["score"] is not None and missing_pain:
            hints.append("Missing pain data: " + ", ".join(missing_pain) + ".")
        if score2["score"] is not None and missing_pivot:
            hints.append("Missing pivot data: " + ", ".join(missing_pivot) + ".")
        pivot_size = score2["signals"].get("pivot_size")
        if pivot_size and pivot_size.get("estimate"):
            hints.append("The pivot target is an estimate, not sourced guidance; keep it out of a hard verdict.")
        if score1["score"] is None:
            hints.append("Score 1 has no usable inputs.")
        if score2["score"] is None:
            hints.append("Score 2 has no usable inputs.")
        missing = []
        for key, values in self.excluded.items():
            if values:
                missing.append(f"{key}: {len(values)} future item(s) excluded")
        if missing:
            hints.append("; ".join(missing) + ".")
        return hints

    def build_evidence(self, score1: dict, score2: dict) -> list[str]:
        lines: list[str] = []
        qualitative = self.data.get("qualitative") or {}
        for key in ("capability_evidence", "management_evidence", "tailwind_evidence"):
            for item in qualitative.get(key) or []:
                lines.append(str(item))
        latest = self.latest_call()
        if latest:
            for item in latest.get("evidence") or []:
                lines.append(f"{latest.get('date')}: {item}")
        promoter = score1["turning_detail"]["signals"].get("promoter")
        if promoter and promoter.get("net_cr"):
            side = "buys" if promoter["net_cr"] > 0 else "sells"
            lines.append(
                f"Promoter net open-market {side} of Rs {abs(promoter['net_cr']):.1f} cr in the last 183 days."
            )
        valuation = self.valuation()
        if valuation:
            lines.append(
                f"{valuation['metric'].upper()} {valuation['current']:.2f} is at the "
                f"{valuation['percentile']:.0f}th percentile of {valuation['n']} observations."
            )
        shift = score2["signals"].get("segment_shift")
        if shift:
            lines.append(
                f"New-segment share moved {shift['change_pp']:.0f}pp to "
                f"{shift['last_share_pct']:.0f}% over {shift['window'][0]} to {shift['window'][1]}."
            )
        build = score2["signals"].get("build_phase")
        if build:
            lines.append(f"Capex/sales step-up {build['ratio']:.1f}x the prior three-year average.")
        breadth = score1["pain_detail"]["signals"].get("sector_breadth")
        if breadth:
            lines.append(
                f"{breadth['share'] * 100:.0f}% of {breadth['n']} peers are at least 40% below their 3y high."
            )
        seen = set()
        unique = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        return unique[:8]

    def run(self) -> dict:
        score1 = self.score1()
        score2 = self.score2()
        stage = self.stage(score1, score2)
        valuation = self.valuation()
        pivot_size = score2["signals"].get("pivot_size")
        result = {
            "company": self.data.get("company"),
            "ticker": self.data.get("ticker"),
            "sector": self.data.get("sector"),
            "as_of": self.as_of.isoformat(),
            "price": self.price,
            "stage": stage["stage"],
            "stage_meaning": stage["meaning"],
            "stage_action": stage["action"],
            "stage_detail": stage,
            "score1_pessimism_roc": score1["score"],
            "score1_level": score1["pain"],
            "score1_turn": score1["turn"],
            "score1_delta": score1["delta"],
            "score1_coverage": score1["coverage"],
            "score2_trajectory_pivot": score2["score"],
            "score2_coverage": score2["coverage"],
            "score2_judgment_share": score2["judgment_share"],
            "turning_signals_fired": score1["turning_detail"]["fired"],
            "optimism_signals": stage["optimism_signals"],
            "supply_demand": stage["supply_demand"],
            "valuation_percentile": None if valuation is None else valuation["percentile"],
            "valuation_metric": None if valuation is None else valuation["metric"],
            "drawdown": self.price.get("drawdown"),
            "off_low": self.price.get("off_low"),
            "ebitda_ttm_yoy": self.ttm.get("ebitda_growth"),
            "pivot_lens": stage["pivot_lens"],
            "pivot_estimate": bool(pivot_size and pivot_size.get("estimate")),
            "pivot_target_source": None if not pivot_size else pivot_size.get("target_source"),
            "build_phase": score2["signals"].get("build_phase"),
            "late_cycle_signals": stage["optimism_signals"],
            "vetoes": score1["vetoes"] + score2["vetoes"],
            "red_flags": score1["red_flags"],
            "score1_detail": score1,
            "score2_detail": score2,
            "price_check": self.price_check(stage),
            "what_would_change": self.what_would_change(score1, score2, stage),
            "evidence": self.build_evidence(score1, score2),
            "excluded_future_data": {key: values for key, values in self.excluded.items() if values},
            "disclaimer": "Screening aid only - not investment advice.",
        }
        return result


def run_one(data: dict, config: dict) -> dict:
    for key in ("company", "ticker", "sector", "as_of"):
        if not data.get(key):
            raise ValueError(f"missing required field: {key}")
    return Company(data, config).run()


def deep_merge_file(path: str | None, base: dict) -> dict:
    if not path:
        return base
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return deep_merge(base, payload)


def fmt(value, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def pct(value, digits: int = 0) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def markdown(result: dict) -> str:
    lines = []
    detail1 = result.get("score1_detail") or {}
    detail2 = result.get("score2_detail") or {}
    lines.append(f"# {result['company']} ({result['ticker']})")
    lines.append("")
    lines.append(f"**As of:** {result['as_of']}  |  **Sector:** {result['sector']}")
    current = (result.get("price") or {}).get("current")
    lines.append(f"**Price:** {fmt(current)}")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**Stage: {result['stage']}** - {result.get('stage_meaning', '')}")
    lines.append("")
    lines.append(f"**Research action:** {result.get('stage_action', '')}")
    lines.append("")
    lines.append(
        f"**Score 1 (Pessimism Rate of Change):** "
        f"{'n/a' if result['score1_pessimism_roc'] is None else fmt(result['score1_pessimism_roc']) + '/100'} "
        f"({pct(result['score1_coverage'], 0)} coverage) | pain {fmt(result['score1_level'])}, "
        f"turning {fmt(result['score1_turn'])}, delta {fmt(result['score1_delta'])}"
    )
    lines.append(
        f"**Score 2 (Trajectory Pivot):** "
        f"{'n/a' if result['score2_trajectory_pivot'] is None else fmt(result['score2_trajectory_pivot']) + '/100'} "
        f"({pct(result['score2_coverage'], 0)} coverage)"
    )
    fired = result.get("turning_signals_fired") or []
    if fired:
        lines.append(f"**Main support:** turning signals fired: {', '.join(fired)}.")
    else:
        lines.append("**Main support:** no turning signal fired yet.")
    if result.get("late_cycle_signals"):
        lines.append(f"**Late-cycle signals:** {', '.join(result['late_cycle_signals'])}.")
    lines.append("")
    if result["stage_detail"].get("pivot_lens"):
        lines.append("Pivot lens is on: judge the price against incremental pivot earnings, not the old mix.")
        lines.append("")
    if result["stage_detail"].get("blocked_rule"):
        lines.append(f"**Blocking rule:** {result['stage_detail']['blocked_rule']}")
        lines.append("")
    lines.append(f"**Supply/demand:** {result['supply_demand']}")
    lines.append("")
    lines.append("## Scores")
    lines.append("")
    lines.append("| Score | Value | Coverage | Pain | Turning | Delta |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        f"| Score 1 | {fmt(result['score1_pessimism_roc'])} | {pct(result['score1_coverage'], 0)} | "
        f"{fmt(result['score1_level'])} | {fmt(result['score1_turn'])} | {fmt(result['score1_delta'])} |"
    )
    lines.append(
        f"| Score 2 | {fmt(result['score2_trajectory_pivot'])} | {pct(result['score2_coverage'], 0)} | - | - | - |"
    )
    lines.append("")
    lines.append(f"**Price check:** {result['price_check']}")
    lines.append("")

    lines.append("## Signal detail")
    lines.append("")
    pain = detail1.get("pain_detail") or {}
    lines.append("### Pain")
    lines.append("")
    lines.append("| Signal | Weight | Score | Reading |")
    lines.append("|---|---|---|---|")
    for key, weight in (pain.get("weights") or {}).items():
        signal = (pain.get("signals") or {}).get(key)
        reading = "missing"
        if signal:
            if key == "valuation":
                reading = (
                    f"{signal['metric'].upper()} {signal['current']:.2f}; "
                    f"{signal['percentile']:.0f}th percentile of {signal['n']}"
                )
            elif key == "drawdown":
                reading = f"{pct(signal['drawdown'], 0)} below the 3y high"
            elif key == "earnings_stress":
                reading = (
                    f"TTM margin {pct(signal['ttm_margin'], 1)} vs cycle {pct(signal['avg_margin'], 1)}; "
                    f"{signal['pairs']} YoY pairs"
                )
            elif key == "neglect":
                reading = ", ".join(f"{name} {fmt(value)}" for name, value in (signal.get("parts") or {}).items())
            elif key == "sector_breadth":
                reading = f"{signal['share'] * 100:.0f}% of {signal['n']} peers down >=40%"
        lines.append(f"| {key} | {weight:.2f} | {fmt(None if not signal else signal['score'])} | {reading} |")
    lines.append("")

    turn = detail1.get("turning_detail") or {}
    lines.append("### Turning")
    lines.append("")
    lines.append("| Signal | Weight | Score | Fired | Reading |")
    lines.append("|---|---|---|---|---|")
    for key, weight in (turn.get("weights") or {}).items():
        signal = (turn.get("signals") or {}).get(key)
        if signal is None:
            reading = "N/A" if key not in (turn.get("applicable_weights") or {}) else "missing"
            lines.append(f"| {key} | {weight:.2f} | n/a | no | {reading} |")
            continue
        if key == "promoter":
            holding = signal.get("holding_change_pp")
            holding_text = f"{holding:+.2f}pp" if holding is not None else "n/a"
            if signal.get("net_cr"):
                reading = f"net Rs {signal['net_cr']:.1f} cr; holding {holding_text}"
            else:
                reading = f"holding {holding_text}"
        elif key == "sentiment_gap":
            reading = (
                f"tone {signal['tone']:.0f}, skepticism {signal['skepticism']:.0f}, "
                f"delta {signal['delta']:+.1f}, misses {signal['misses']}"
            )
        elif key == "margin_inflection":
            reading = (
                f"{signal['basis']} margin {pct(signal['trough_margin'], 1)} -> "
                f"{pct(signal['latest_margin'], 1)} ({signal['rise'] * 100:+.1f}pp)"
            )
        else:
            reading = "share gain claimed" if signal.get("claimed") else "no share-gain claim"
        fired_text = "yes" if signal.get("fired") else "no"
        name = f"{key} (fired)" if signal.get("fired") else key
        lines.append(f"| {name} | {weight:.2f} | {fmt(signal['score'])} | {fired_text} | {reading} |")
    lines.append("")

    delta = detail1.get("delta_detail")
    if delta:
        lines.append(
            f"**Earnings delta:** TTM EBITDA {fmt(delta['ttm_ebitda'])} vs cycle average "
            f"{fmt(delta['avg_ebitda'])}; potential {pct(delta['potential'], 0)}"
            + ("; halved because margins have not inflected." if delta.get("halved") else ".")
        )
    else:
        lines.append("**Earnings delta:** n/a.")
    lines.append("")

    lines.append("### Trajectory pivot")
    lines.append("")
    lines.append("| Signal | Weight | Score | Reading |")
    lines.append("|---|---|---|---|")
    pivot_weights = {
        "segment_shift": 0.20,
        "pivot_size": 0.20,
        "capability": 0.20,
        "management": 0.20,
        "mispricing": 0.10,
        "tailwind": 0.10,
        "build_phase": 0.10,
    }
    for key, weight in pivot_weights.items():
        signal = (detail2.get("signals") or {}).get(key)
        if signal is None:
            lines.append(f"| {key} | {weight:.2f} | n/a | missing |")
            continue
        if key == "segment_shift":
            reading = (
                f"share {signal['change_pp']:+.0f}pp to {signal['last_share_pct']:.0f}%; "
                f"margin ratio {fmt(signal['margin_diff'])}"
            )
        elif key == "pivot_size":
            reading = f"orbit {signal['orbit']:.2f}x; target {fmt(signal['target_revenue'])} at {fmt(signal['target_margin_pct'])}%"
        elif key in {"capability", "management", "tailwind"}:
            reading = f"rubric {signal['rubric']:.0f}/5"
        elif key == "mispricing":
            reading = f"{fmt(signal['company_multiple'])} vs pure-play {fmt(signal['pure_play_multiple'])}"
        else:
            reading = f"capex/sales {signal['ratio']:.2f}x" + (f" ({signal['note']})" if signal.get("note") else "")
        lines.append(f"| {key} | {weight:.2f} | {fmt(signal['score'])} | {reading} |")
    lines.append("")
    if detail2.get("management_gate"):
        lines.append("**Management gate:** management rubric below 2/5 caps Score 2 at 40.")
    if detail2.get("judgment_share", 0) > 0.6:
        lines.append("**Judgment-heavy:** over 60% of Score 2 rests on rubric judgments.")
    if detail2.get("management_gate") or detail2.get("judgment_share", 0) > 0.6:
        lines.append("")
    build = result.get("build_phase")
    if build:
        lines.append(
            f"**Build phase:** capex/sales {build['ratio']:.2f}x the prior average"
            + (f" - {build['note']}" if build.get("note") else "")
            + ("; capability below 3 so score halved." if build.get("capability_below_3") else ".")
        )
        lines.append("")
    if result.get("pivot_estimate"):
        lines.append(f"**Pivot target basis:** {result.get('pivot_target_source')} (estimate; not a hard input).")
        lines.append("")

    lines.append("## Vetoes and red flags")
    lines.append("")
    if result.get("vetoes"):
        for item in result["vetoes"]:
            lines.append(f"- Veto: {item}")
    if result.get("red_flags"):
        for item in result["red_flags"]:
            lines.append(f"- Red flag: {item}")
    if result.get("late_cycle_signals"):
        lines.append("- Late-cycle signals: " + "; ".join(result["late_cycle_signals"]) + ".")
    if not result.get("vetoes") and not result.get("red_flags") and not result.get("late_cycle_signals"):
        lines.append("- None.")
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    for item in result.get("evidence") or []:
        lines.append(f"- {item}")
    if not result.get("evidence"):
        lines.append("- No evidence lines supplied.")
    lines.append("")
    lines.append("## What would change the score")
    lines.append("")
    for hint in result.get("what_would_change") or []:
        lines.append(f"- {hint}")
    if not result.get("what_would_change"):
        lines.append("- Nothing material identified.")
    lines.append("")
    excluded = result.get("excluded_future_data") or {}
    lines.append("## Point-in-time guard")
    lines.append("")
    if excluded:
        for key, values in excluded.items():
            lines.append(f"- {key}: excluded {len(values)} future item(s) ({', '.join(values)})")
    else:
        lines.append("- No future-dated items found in the supplied data.")
    lines.append("")
    lines.append("---")
    lines.append(result["disclaimer"])
    return "\n".join(lines)


def check_expectation(result: dict, expected: dict) -> str:
    if not expected:
        return "n/a"
    checks = []
    if "stage" in expected:
        wanted = expected["stage"]
        allowed = wanted if isinstance(wanted, list) else [wanted]
        checks.append(result["stage"] in allowed)
    if "score1_min" in expected:
        checks.append(result["score1_pessimism_roc"] is not None and result["score1_pessimism_roc"] >= expected["score1_min"])
    if "score1_max" in expected:
        checks.append(result["score1_pessimism_roc"] is not None and result["score1_pessimism_roc"] <= expected["score1_max"])
    if "score2_min" in expected:
        checks.append(result["score2_trajectory_pivot"] is not None and result["score2_trajectory_pivot"] >= expected["score2_min"])
    if "score2_max" in expected:
        checks.append(result["score2_trajectory_pivot"] is not None and result["score2_trajectory_pivot"] <= expected["score2_max"])
    if "judgment_min" in expected:
        checks.append(result["score2_judgment_share"] >= expected["judgment_min"])
    if "judgment_max" in expected:
        checks.append(result["score2_judgment_share"] <= expected["judgment_max"])
    if "vetoed" in expected:
        checks.append(bool(result["vetoes"]) == bool(expected["vetoed"]))
    if "promoter_na" in expected:
        turn = (result.get("score1_detail") or {}).get("turning_detail") or {}
        checks.append("promoter" not in (turn.get("signals") or {}) and "promoter" not in (turn.get("applicable_weights") or {}))
    if "not_stage" in expected:
        blocked = expected["not_stage"]
        blocked = blocked if isinstance(blocked, list) else [blocked]
        checks.append(result["stage"] not in blocked)
    if "runs" in expected:
        checks.append("error" not in result)
    return "PASS" if all(checks) else "FAIL"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Score stocks with the Pessimism RoC and Trajectory Pivot frameworks.")
    parser.add_argument("input", nargs="?", help="Input JSON: one company or a list")
    parser.add_argument("--json", dest="json_out", default=None, help="Write results JSON")
    parser.add_argument("--md", dest="md_out", default=None, help="Write markdown scorecard")
    parser.add_argument("--summary", action="store_true", help="Print a one-line-per-company summary")
    parser.add_argument("--config", default=None, help="Override JSON, deep-merged over defaults")
    parser.add_argument("--print-config", action="store_true", help="Print the effective config and exit")
    args = parser.parse_args()

    config = deep_merge_file(args.config, DEFAULT_CONFIG)
    if args.print_config:
        print(json.dumps(config, indent=2))
        return 0
    if not args.input:
        parser.error("input is required unless --print-config is used")

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else [payload]
    results = []
    for item in items:
        try:
            results.append(run_one(item, config))
        except Exception as exc:  # keep batch runs going
            results.append({"company": item.get("company"), "ticker": item.get("ticker"), "error": str(exc)})

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results if isinstance(payload, list) else results[0], indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        text = "\n\n".join(markdown(result) if "error" not in result else f"# ERROR: {result['error']}" for result in results)
        Path(args.md_out).write_text(text + "\n", encoding="utf-8")

    if args.summary:
        print(f"{'company':<28}{'stage':<18}{'S1':>6}{'cov':>7}{'S2':>7}{'cov':>7}  expected  check")
        for item, result in zip(items, results):
            if "error" in result:
                print(f"{str(item.get('company')):<28}ERROR: {result['error']}")
                continue
            expected = item.get("expected") or {}
            check = check_expectation(result, expected)
            print(
                f"{str(result['company']):<28}{result['stage']:<18}"
                f"{fmt(result['score1_pessimism_roc']):>6}{fmt((result['score1_coverage'] or 0) * 100):>7}"
                f"{fmt(result['score2_trajectory_pivot']):>7}{fmt((result['score2_coverage'] or 0) * 100):>7}"
                f"  {str(expected.get('stage', '')):<10}{check}"
            )
    elif not args.json_out and not args.md_out:
        print(json.dumps(results if isinstance(payload, list) else results[0], indent=2))

    return 0 if all("error" not in result for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

