#!/usr/bin/env python3
"""
RS Leader Setup Score - deterministic scorer.

Scores a stock 0-100 on the "RS80 leader" framework (relative strength, past-winner
chart template, stage/timing, theme leadership, catalyst & earnings), applies hard
gates and caps, overlays a market-health regime, and builds a trade plan
(stop %, position size, reward multiple).

Same input + same config = same output. Every point is traceable to a rule in
framework_config.json.

Usage:
  python score_setup.py --template                      # blank stock input
  python score_setup.py --market-template               # blank market input
  python score_setup.py stock.json [--market m.json] [--json out.json] [--md out.md]
  python score_setup.py --market-only m.json [--md out.md]
  python score_setup.py --batch a.json b.json ... [--market m.json] [--md rank.md]
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "framework_config.json")


# --------------------------------------------------------------------------- utils
def load_config(path=None):
    with open(path or DEFAULT_CONFIG) as f:
        return json.load(f)


def is_missing(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def band_points(rule, v):
    """Points for one value under one rule. Assumes v is not missing."""
    t = rule["type"]
    if t == "bool":
        return rule["max"] if bool(v) else 0
    if t == "high":
        for thr, pts in rule["bands"]:
            if v >= thr:
                return pts
        return 0
    if t == "low":
        for thr, pts in rule["bands"]:
            if v <= thr:
                return pts
        return 0
    if t == "range":
        for lo, hi, pts in rule["bands"]:
            if lo <= v <= hi:
                return pts
        return 0
    raise ValueError(f"unknown rule type {t}")


def r2(x):
    return None if x is None else round(x, 2)


# --------------------------------------------------------------------------- formulas
def stop_distance_pct(entry, stop):
    """% distance from entry (pivot) down to stop."""
    if is_missing(entry) or is_missing(stop) or entry <= 0 or stop >= entry:
        return None
    return (entry - stop) / entry * 100.0


def position_size_pct(stop_pct, risk_pct=1.0, max_position_pct=None):
    """Position size as % of portfolio = risk% x 100 / stop%.
    With 1% risk this is the transcript's shortcut 100 / stop%."""
    if stop_pct is None or stop_pct <= 0:
        return None
    size = risk_pct * 100.0 / stop_pct
    if max_position_pct is not None:
        size = min(size, max_position_pct)
    return size


def edge_ratio(win_pct, avg_gain_pct, avg_loss_pct):
    """Edge = (win% / loss%) x (avg gain / avg loss). Equals profit factor."""
    loss_pct = 100.0 - win_pct
    if loss_pct <= 0 or avg_loss_pct <= 0:
        return float("inf")
    return (win_pct / loss_pct) * (avg_gain_pct / abs(avg_loss_pct))


def expectancy_pct(win_pct, avg_gain_pct, avg_loss_pct):
    """Expected % return per trade (per unit of position)."""
    w = win_pct / 100.0
    return w * avg_gain_pct - (1 - w) * abs(avg_loss_pct)


def leg_from_gain(gain_pct, cfg):
    if is_missing(gain_pct):
        return None
    for thr, leg in cfg["leg_from_gain"]["bands"]:
        if gain_pct <= thr:
            return leg
    return cfg["leg_from_gain"]["bands"][-1][1]


# --------------------------------------------------------------------------- market
def score_market(m, cfg):
    mh = cfg["market_health"]
    rows, earned, avail = [], 0.0, 0.0
    for field, rule in mh["rules"].items():
        v = m.get(field)
        if is_missing(v):
            rows.append({"rule": field, "value": None, "points": None, "max": rule["max"]})
            continue
        p = band_points(rule, v)
        earned += p
        avail += rule["max"]
        rows.append({"rule": field, "value": v, "points": p, "max": rule["max"]})
    penalties = []
    if m.get("index_near_high_breadth_falling"):
        penalties.append(("index-vs-breadth divergence", mh["divergence_penalty"]))
    if m.get("false_breakdowns_rising"):
        penalties.append(("false breakouts / breakdowns rising (distribution)", mh["false_breakdown_penalty"]))
    if avail == 0:
        return {"score": None, "coverage_pct": 0, "regime": None, "rows": rows, "penalties": penalties}
    score = earned / avail * 100.0 - sum(p for _, p in penalties)
    score = max(0.0, min(100.0, score))
    regime = next(r for r in mh["regimes"] if score >= r["min"])
    return {
        "score": r2(score),
        "coverage_pct": r2(avail),
        "regime": regime,
        "rows": rows,
        "penalties": penalties,
    }


# --------------------------------------------------------------------------- stock
def evaluate_gates(inp, cfg):
    out = []
    for field, g in cfg["gates"].items():
        if field.startswith("_"):
            continue
        v = inp.get(field)
        if is_missing(v):
            out.append({"gate": field, "value": None, "status": "MISSING"})
            continue
        if g["type"] == "bool":
            status = "PASS" if bool(v) else "FAIL"
        else:
            if v >= g["value"]:
                status = "PASS"
            elif "soft_min" in g and v >= g["soft_min"]:
                status = "SOFT"
            else:
                status = "FAIL"
        out.append({"gate": field, "value": v, "status": status,
                    "need": g.get("value", True)})
    return out


QUALITY_ORDER = ("measured", "inferred", "qualitative", "assumed")


def normalise_inputs(inp, cfg):
    """Turn word inputs ('high', 'yes') into numbers via config, and record which fields were words."""
    q = cfg.get("qualitative", {})
    bw = {k.lower(): v for k, v in q.get("bool_words", {}).items()}
    maps = q.get("maps", {})
    words = {}
    for k, v in list(inp.items()):
        if not isinstance(v, str):
            continue
        key = v.strip().lower().replace(" ", "_").replace("-", "_")
        if k in maps and key in maps[k]:
            inp[k] = maps[k][key]
            words[k] = v
        elif key in bw:
            inp[k] = bw[key]
            words[k] = v
        else:
            allowed = sorted(maps.get(k, {}).keys()) or sorted(bw.keys())
            raise ValueError(f"{k} = '{v}' is not a recognised word. Use a number or one of: {allowed}")
    return words


def field_quality(field, words, evidence):
    if field in words:
        return "qualitative"
    ev = str(evidence.get(field, "")).lower()
    if "assumed" in ev:
        return "assumed"
    if "inferred" in ev:
        return "inferred"
    if "qualitative" in ev or "coded at band floor" in ev:
        return "qualitative"
    return "measured"


def grade(score, late, cl):
    if score >= cl["buy_a"] and not late:
        return "BUY CANDIDATE - A"
    if score >= cl["buy_b"] and not late:
        return "BUY CANDIDATE - B"
    if score >= cl["buy_b"] and late:
        return "TRADE ONLY - late stage (expect a 20-50% swing, not a multibagger)"
    if late:
        return "WATCHLIST - late stage; trade only, and only from a tight base"
    return "WATCHLIST - not ready"


def score_stock(doc, cfg, market=None):
    if "inputs" not in doc:
        raise ValueError(f"{doc.get('symbol', 'file')}: no 'inputs' block (is this a market file?)")
    inp = dict(doc["inputs"])
    trade = doc.get("trade", {}) or {}
    evidence = doc.get("evidence", {}) or {}
    notes, flags, alerts = [], [], []
    words = normalise_inputs(inp, cfg)
    if words:
        notes.append("Word inputs converted at band floor: " +
                     ", ".join(f"{k}='{v}' -> {inp[k]}" for k, v in words.items()))

    # derive stop distance from the trade block when not given directly
    if is_missing(inp.get("stop_distance_pct")):
        sd = stop_distance_pct(trade.get("pivot_price"), trade.get("stop_price"))
        if sd is not None:
            inp["stop_distance_pct"] = sd
            notes.append(f"stop_distance_pct derived from pivot/stop = {sd:.2f}%")

    # leg: worse of stated leg and gain-implied leg
    stated = inp.get("leg_number")
    implied = leg_from_gain(inp.get("gain_from_base_low_pct"), cfg)
    if is_missing(stated) and implied is not None:
        inp["leg_number"] = implied
        notes.append(f"leg_number derived from gain_from_base_low_pct "
                     f"({inp['gain_from_base_low_pct']}%) = leg {implied}")
    elif not is_missing(stated) and implied is not None and implied > stated:
        flags.append(f"Stated leg {stated} but stock is already {inp['gain_from_base_low_pct']}% "
                     f"off its base low, which implies leg {implied}. Using leg {implied}.")
        inp["leg_number"] = implied

    gates = evaluate_gates(inp, cfg)
    gate_fail = any(g["status"] == "FAIL" for g in gates)
    gate_missing = [g["gate"] for g in gates if g["status"] == "MISSING"]
    for g in gates:
        if g["status"] == "SOFT":
            flags.append(f"{g['gate']} = {g['value']} is between the soft floor and the target; liquidity is thin.")

    quality_pts = {k: 0.0 for k in QUALITY_ORDER}
    pillars, total_earned, total_avail = [], 0.0, 0.0
    for pkey, p in cfg["pillars"].items():
        rows, e, a = [], 0.0, 0.0
        for field, rule in p["rules"].items():
            v = inp.get(field)
            if is_missing(v):
                rows.append({"rule": field, "value": None, "points": None, "max": rule["max"], "quality": None})
                continue
            pts = band_points(rule, v)
            qual = field_quality(field, words, evidence)
            quality_pts[qual] += pts
            e += pts
            a += rule["max"]
            rows.append({"rule": field, "value": v, "points": pts, "max": rule["max"], "quality": qual})
        pillars.append({"key": pkey, "label": p["label"], "weight": p["weight"],
                        "earned": e, "available": a,
                        "pct": r2(e / a * 100) if a else None, "rows": rows})
        total_earned += e
        total_avail += a

    coverage = total_avail  # pillar maxima sum to 100
    rebased = total_earned / total_avail * 100 if total_avail else 0.0
    conservative = total_earned

    caps_hit, cap_limit = [], 100.0
    for cname, c in cfg["caps"].items():
        v = inp.get(c["field"])
        if is_missing(v):
            continue
        hit = ("above" in c and v > c["above"]) or ("below" in c and v < c["below"])
        if hit:
            caps_hit.append({"cap": cname, "limit": c["cap"], "msg": c["msg"]})
            cap_limit = min(cap_limit, c["cap"])
    score = min(rebased, cap_limit)
    conservative_capped = min(conservative, cap_limit)

    # ----- classification
    cl = cfg["classification"]
    leg = inp.get("leg_number")
    late = (not is_missing(leg)) and leg > cl["max_leg_for_investment"]
    enough = coverage >= cl["min_coverage_pct"]
    provisional = grade(score, late, cl)
    if provisional.startswith("BUY") and is_missing(inp.get("stop_distance_pct")):
        provisional = "BUY-GRADE - pending pivot/stop"
        flags.append("Scores like a buy, but there is no pivot and stop yet, so it can't be confirmed "
                     "as a low-risk entry. Define the base high and low.")

    if gate_fail:
        cls = "REJECT - outside RS80 universe"
        headline = conservative_capped if not enough else score
    elif enough:
        cls = provisional
        headline = score
    else:
        if coverage < cl.get("min_coverage_for_provisional", 0):
            provisional = "too little data to grade"
        cls = f"INSUFFICIENT DATA ({coverage:.0f}% coverage) - provisional: {provisional}"
        headline = conservative_capped
        flags.append(f"Coverage {coverage:.0f}% is below {cl['min_coverage_pct']}%, so the headline is the "
                     f"conservative score {conservative_capped:.0f} (missing = 0). The re-based {score:.0f} "
                     f"only shows how the available evidence leans.")
    if gate_missing and not gate_fail:
        flags.append("Gates not verified: " + ", ".join(gate_missing))

    # ----- exit / holding alerts (for people already in the stock)
    price, ema50 = inp.get("price"), inp.get("ema50")
    below = inp.get("below_50ema_now")
    if is_missing(below) and not is_missing(price) and not is_missing(ema50):
        below = price < ema50
    if below:
        detail = f" (price {price} vs 50 EMA {ema50})" if not is_missing(ema50) else ""
        alerts.append("EXIT ALERT: below the 50 EMA" + detail + ". The framework's trailing exit for holders "
                      "is a daily close below it.")
    rs = inp.get("rs_rating")
    if not is_missing(rs) and rs < cfg["gates"]["rs_rating"]["value"]:
        alerts.append(f"REVIEW: RS {rs} has dropped below 80; leaders that lose RS are usually done.")
    if any(c["cap"] == "loose_base" for c in caps_hit) and late:
        alerts.append("REVIEW: late leg plus a deep, loose base - typical of a topping or tiring leader.")

    regime = market["regime"] if market and market.get("regime") else None
    if regime and cls.startswith("BUY") and regime["name"] in ("WEAK", "HOSTILE"):
        cls += f" - pilot size only (market {regime['name']})"
        if inp.get("rs_resisted_decline"):
            notes.append("A high-scoring leader holding up in a weak market is the framework's "
                         "highest-value signal: these are the names that lead the next up-move.")

    plan = build_trade_plan(inp, trade, cfg, regime)

    return {
        "symbol": doc.get("symbol"), "name": doc.get("name"), "as_of": doc.get("as_of"),
        "industry": doc.get("industry"), "theme": doc.get("theme"),
        "headline_score": r2(headline), "score": r2(score), "uncapped_score": r2(rebased),
        "conservative_score": r2(conservative_capped), "coverage_pct": r2(coverage),
        "classification": cls, "provisional_class": provisional,
        "gates": gates, "gates_missing": gate_missing, "pillars": pillars,
        "quality_points": {k: r2(v) for k, v in quality_pts.items()},
        "caps": caps_hit, "flags": flags, "notes": notes, "alerts": alerts,
        "effective_leg": leg, "trade_plan": plan,
        "market": market, "evidence": evidence,
    }


def build_trade_plan(inp, trade, cfg, regime):
    tp = cfg["trade_plan"]
    pivot, stop = trade.get("pivot_price"), trade.get("stop_price")
    if is_missing(pivot) or is_missing(stop):
        return None
    price = inp.get("price")
    entry = trade.get("entry_price")
    chasing = False
    if is_missing(entry):
        entry = pivot
        if not is_missing(price) and price > pivot:
            entry = price
            chasing = True
    sp = stop_distance_pct(entry, stop)
    if sp is None:
        return {"error": "stop must be below entry"}
    risk = trade.get("risk_pct")
    if is_missing(risk):
        risk = regime["risk_pct"] if regime else 1.0
    max_pos = trade.get("max_position_pct")
    if is_missing(max_pos):
        max_pos = regime["max_position_pct"] if regime else 30
    size_uncapped = position_size_pct(sp, risk)
    size = min(size_uncapped, max_pos)
    actual_risk = size * sp / 100.0
    tgt = trade.get("target_price")
    if is_missing(tgt):
        R = tp["default_reward_multiple"]
        tgt = entry * (1 + R * sp / 100.0)
        tgt_source = f"default {R}R"
    else:
        R = (tgt - entry) / (entry - stop)
        tgt_source = "user target"
    warnings = []
    if sp > tp["max_stop_pct"]:
        warnings.append(f"Stop {sp:.1f}% exceeds {tp['max_stop_pct']}%: base too loose, size shrinks.")
    if R < tp["min_reward_multiple"]:
        warnings.append(f"Reward multiple {R:.1f}R is below {tp['min_reward_multiple']}R: asymmetry is weak.")
    if chasing:
        warnings.append(f"Price {price} is above pivot {pivot}: entering now widens the stop to {sp:.1f}% "
                        f"and cuts position size (confirmation vs size trade-off).")
    out = {
        "entry": r2(entry), "stop": r2(stop), "stop_pct": r2(sp),
        "risk_pct_of_portfolio": r2(risk),
        "position_pct": r2(size), "position_pct_uncapped": r2(size_uncapped),
        "actual_risk_pct": r2(actual_risk), "target": r2(tgt),
        "target_source": tgt_source, "reward_multiple": r2(R),
        "reward_pct": r2((tgt - entry) / entry * 100),
        "warnings": warnings,
        "exit_rules": [
            "Initial stop: consolidation (base) low. Aggressive variant: breakout-day low, sized at 0.25% risk.",
            "Trail: exit on a daily close below the 50 EMA (strong leaders rarely close below it).",
            "Review: RS rating falling below 80, or the market showing rising false breakouts.",
        ],
    }
    pv = trade.get("portfolio_value")
    if not is_missing(pv):
        amt = pv * size / 100.0
        out["position_amount"] = r2(amt)
        out["amount_at_risk"] = r2(amt * sp / 100.0)
        out["shares"] = int(amt // entry) if entry > 0 else None
    return out


# --------------------------------------------------------------------------- reports
def market_md(m):
    if not m or m.get("score") is None:
        return "_Market health not scored._\n"
    r = m["regime"]
    s = [f"**Market health: {m['score']:.0f}/100 -> {r['name']}** (coverage {m['coverage_pct']:.0f}%)  ",
         f"Risk per trade {r['risk_pct']}%, max position {r['max_position_pct']}%, "
         f"max {r['max_stocks']} stocks. {r['stance']}\n",
         "| Rule | Value | Points |", "|---|---|---|"]
    for row in m["rows"]:
        pts = "n/a" if row["points"] is None else f"{row['points']}/{row['max']}"
        s.append(f"| {row['rule']} | {row['value']} | {pts} |")
    for name, p in m["penalties"]:
        s.append(f"| PENALTY: {name} | yes | -{p} |")
    return "\n".join(s) + "\n"


def stock_md(res):
    qp = res.get("quality_points", {})
    L = [f"# {res.get('symbol') or ''} {res.get('name') or ''} - RS Leader Setup Score",
         f"As of {res.get('as_of')}. Industry: {res.get('industry')}. Theme: {res.get('theme')}.\n",
         f"## Score: {res['headline_score']:.0f}/100 -> {res['classification']}",
         f"Re-based {res['score']:.0f} (uncapped {res['uncapped_score']:.0f}), conservative "
         f"{res['conservative_score']:.0f}, data coverage {res['coverage_pct']:.0f}%. "
         f"Effective leg: {res['effective_leg']}.  ",
         "Points by data quality: " + ", ".join(f"{k} {v:.0f}" for k, v in qp.items()) + "\n"]
    if res.get("alerts"):
        L.append("**Holding alerts:**")
        L += [f"- {a}" for a in res["alerts"]]
        L.append("")
    if res["caps"]:
        L.append("**Caps applied:**")
        L += [f"- {c['cap']} (max {c['limit']}): {c['msg']}" for c in res["caps"]]
        L.append("")
    if res["flags"]:
        L.append("**Flags:**")
        L += [f"- {f}" for f in res["flags"]]
        L.append("")
    if res["notes"]:
        L.append("**Notes:**")
        L += [f"- {n}" for n in res["notes"]]
        L.append("")
    L += ["## Gates (RS80 scan)", "| Gate | Value | Status |", "|---|---|---|"]
    L += [f"| {g['gate']} | {g['value']} | {g['status']} |" for g in res["gates"]]
    L += ["", "## Pillars", "| Pillar | Earned | Available | Weight | % |", "|---|---|---|---|---|"]
    for p in res["pillars"]:
        pct = "n/a" if p["pct"] is None else "{:.0f}%".format(p["pct"])
        L.append(f"| {p['label']} | {p['earned']:.0f} | {p['available']:.0f} | {p['weight']} | {pct} |")
    L += ["", "## Rule-by-rule audit", "| Pillar | Rule | Value | Points | Quality | Evidence |", "|---|---|---|---|---|---|"]
    ev = res.get("evidence") or {}
    for p in res["pillars"]:
        for row in p["rows"]:
            pts = "missing" if row["points"] is None else f"{row['points']}/{row['max']}"
            v = row["value"]
            if isinstance(v, float):
                v = round(v, 2)
            L.append(f"| {p['label']} | {row['rule']} | {v} | {pts} | {row.get('quality') or ''} | {ev.get(row['rule'], '')} |")
    tp = res.get("trade_plan")
    L += ["", "## Trade plan"]
    if not tp:
        L.append("_No pivot/stop given._")
    elif "error" in tp:
        L.append(tp["error"])
    else:
        L += [f"- Entry {tp['entry']}, stop {tp['stop']} ({tp['stop_pct']}% risk on the position)",
              f"- Risk budget {tp['risk_pct_of_portfolio']}% of portfolio -> position size "
              f"{tp['position_pct']}% (formula {tp['risk_pct_of_portfolio']} x 100 / {tp['stop_pct']} = "
              f"{tp['position_pct_uncapped']}%, capped by regime) -> actual risk {tp['actual_risk_pct']}%",
              f"- Target {tp['target']} ({tp['target_source']}): +{tp['reward_pct']}%, "
              f"{tp['reward_multiple']}R"]
        if "position_amount" in tp:
            L.append(f"- Amount {tp['position_amount']}, at risk {tp['amount_at_risk']}, ~{tp['shares']} shares")
        L += [f"- WARNING: {w}" for w in tp["warnings"]]
        L += [f"- {e}" for e in tp["exit_rules"]]
    if res.get("market"):
        L += ["", "## Market overlay", market_md(res["market"])]
    L += ["", "_Mechanical output of a framework derived from one podcast, not investment advice. "
          "Verify every input against filings and charts before acting._"]
    return "\n".join(L) + "\n"


def batch_md(results):
    L = ["# RS Leader Setup Score - ranking", "",
         "Headline = re-based score when coverage >= 70%, otherwise the conservative score (missing = 0).", "",
         "| # | Symbol | Headline | Re-based | Conservative | Coverage | Class | Leg | RS | Stop % | Size % | Gates missing | Alerts |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        def val(field):
            for p in r["pillars"]:
                for row in p["rows"]:
                    if row["rule"] == field:
                        return row["value"]
            for g in r["gates"]:
                if g["gate"] == field:
                    return g["value"]
            return None
        tp = r.get("trade_plan") or {}
        alerts = "; ".join(a.split(":")[0] for a in r.get("alerts", [])) or "-"
        gm = ", ".join(r.get("gates_missing", [])) or "-"
        L.append(f"| {i} | {r['symbol']} | {r['headline_score']:.0f} | {r['score']:.0f} | "
                 f"{r['conservative_score']:.0f} | {r['coverage_pct']:.0f}% | {r['classification']} | "
                 f"{r['effective_leg']} | {val('rs_rating')} | {tp.get('stop_pct', '-')} | "
                 f"{tp.get('position_pct', '-')} | {gm} | {alerts} |")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- templates
STOCK_TEMPLATE = {
    "symbol": "TICKER", "name": "Company name", "as_of": "YYYY-MM-DD",
    "industry": "e.g. Telecom - optical fibre", "theme": "e.g. AI data-centre optical fibre",
    "inputs": {
        "price": None, "ema50": None, "below_50ema_now": None,
        "price_above_200dma": None, "rs_rating": None,
        "avg_turnover_30d_cr": None, "market_cap_cr": None,
        "rs_resisted_decline": None,
        "prior_uptrend": None, "base_length_weeks": None, "stop_distance_pct": None,
        "volume_dryup_ratio": None, "volume_spike_ratio": None, "ema50_breaches": None,
        "fall_to_recover_ratio": None,
        "leg_number": None, "gain_from_base_low_pct": None, "rest_days": None,
        "group_count_in_scan": None, "leader_rank_in_group": None,
        "theme_revenue_share_pct": None, "global_peer_confirmation": None,
        "pat_growth_yoy_pct": None, "sales_growth_yoy_pct": None,
        "catalyst_revenue_uplift_pct": None, "catalyst_months_to_impact": None,
        "quantified_guidance": None, "upcycle_quarters_elapsed": None
    },
    "trade": {"pivot_price": None, "stop_price": None, "entry_price": None,
              "target_price": None, "risk_pct": None, "max_position_pct": None,
              "portfolio_value": None},
    "evidence": {"catalyst_revenue_uplift_pct": "source + page/quote for each judgement field"},
    "_help": "Leave unknown fields null: they are excluded and reported as missing coverage. "
             "Numbers are preferred; descriptive words ('high', 'tight', 'yes') are accepted for the "
             "fields listed under 'qualitative' in framework_config.json and are scored at the band floor. "
             "Start evidence notes with 'inferred:' or 'ASSUMED' when that applies. "
             "See references/data_collection.md for how to source each field."
}

MARKET_TEMPLATE = {
    "as_of": "YYYY-MM-DD", "universe": "Nifty 500",
    "pct_above_50dma": None, "pct_above_50dma_change_4w": None,
    "new_high_share": None, "adv_decl_ratio_10d": None,
    "index_above_50dma": None, "index_above_200dma": None,
    "breakout_followthrough_rate": None, "equity_curve_rising": None,
    "positive_reaction_to_news": None,
    "index_near_high_breadth_falling": None, "false_breakdowns_rising": None,
    "_help": "new_high_share = NH / (NH + NL) of 52-week highs/lows. adv_decl_ratio_10d = "
             "10-day average of advances / declines."
}


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stock", nargs="?")
    ap.add_argument("--market")
    ap.add_argument("--market-only")
    ap.add_argument("--batch", nargs="+")
    ap.add_argument("--config")
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--market-template", action="store_true")
    a = ap.parse_args(argv)

    if a.template:
        print(json.dumps(STOCK_TEMPLATE, indent=2)); return 0
    if a.market_template:
        print(json.dumps(MARKET_TEMPLATE, indent=2)); return 0

    cfg = load_config(a.config)
    market = None
    mpath = a.market or a.market_only
    if mpath:
        with open(mpath) as f:
            market = score_market(json.load(f), cfg)

    if a.market_only:
        md = market_md(market)
        out = market
    elif a.batch:
        results = []
        for p in a.batch:
            with open(p) as f:
                results.append(score_stock(json.load(f), cfg, market))
        results.sort(key=lambda r: (r["classification"].startswith("REJECT"), -r["headline_score"], r["symbol"] or ""))
        md = batch_md(results)
        if market:
            md += "\n" + market_md(market)
        out = results
    elif a.stock:
        with open(a.stock) as f:
            out = score_stock(json.load(f), cfg, market)
        md = stock_md(out)
    else:
        ap.print_help(); return 1

    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=2, default=str)
    if a.md:
        with open(a.md, "w") as f:
            f.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
