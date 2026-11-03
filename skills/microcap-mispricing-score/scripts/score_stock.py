#!/usr/bin/env python3
"""
Microcap Mispricing Score
=========================
Deterministic scorer for the small/microcap "mispricing" framework:
  * choose valuation metrics by business type (cyclical / stable / growth /
    capex_transition / new_age)
  * six multiples (EV/EBITDA, EV/EBIT, P/E, EV/OCF, P/S, EV/Sales), each also
    ranked against the company's own history
  * three adjusted earnings (one-off stripped, cyclically adjusted, forward)
  * implied P/E from P/B and normalised ROE
  * earnings quality (OCF conversion, receivables vs sales, expense habits)
  * PEG and the "earnings gap"
  * capital-cycle setup, upside/downside asymmetry, optionality
  * governance kill switches
  * cheap vs undervalued classification

Usage:
  python score_stock.py input.json                 # markdown report to stdout
  python score_stock.py input.json --json out.json --md report.md
  python score_stock.py --template > my_stock.json # blank input template

All amounts must be in one consistent unit (e.g. INR crore). Percent inputs are
plain numbers (25 means 25%). No network access, no randomness: the same input
and config always give the same score.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "framework_config.json"
TEMPLATE = HERE.parent / "assets" / "input_template.json"
BUSINESS_TYPES = ("cyclical", "stable", "growth", "capex_transition", "new_age")


# ----------------------------------------------------------------- helpers
def num(x):
    """Return float or None (accepts int/float/numeric strings)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def div(a, b):
    a, b = num(a), num(b)
    if a is None or b is None or b == 0:
        return None
    return a / b


def pos_div(a, b):
    """Division only meaningful when the denominator is positive (multiples)."""
    b = num(b)
    if b is None or b <= 0:
        return None
    return div(a, b)


def cagr(start, end, years):
    start, end = num(start), num(end)
    if start is None or end is None or years <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1.0 / years) - 1.0


def pctile(value, history):
    """Share (0-100) of historical observations <= value."""
    hist = [h for h in history if h is not None]
    if value is None or not hist:
        return None
    return 100.0 * sum(1 for h in hist if h <= value) / len(hist)


def rnd(x, n=2):
    return None if x is None else round(x, n)


# ----------------------------------------------------------------- loading
def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate(data):
    errors = []
    if data.get("business_type") not in BUSINESS_TYPES:
        errors.append(f"business_type must be one of {BUSINESS_TYPES}")
    if num(data.get("market", {}).get("market_cap")) is None:
        errors.append("market.market_cap is required")
    annual = data.get("annual") or []
    if len(annual) < 1:
        errors.append("annual must contain at least one year")
    for i, row in enumerate(annual):
        if "year" not in row:
            errors.append(f"annual[{i}] missing 'year'")
        if num(row.get("sales")) is None:
            errors.append(f"annual[{i}] missing 'sales'")
    return errors


# ----------------------------------------------------------------- metrics
def compute_metrics(data, cfg):
    m, notes = {}, []
    t = cfg["tax_rate"]
    if num(data.get("tax_rate_pct")) is not None:   # company-specific effective tax (e.g. agri-income exempt)
        t = num(data["tax_rate_pct"]) / 100
        notes.append(f"Using company tax rate {t*100:g}% instead of default {cfg['tax_rate']*100:g}%.")
    m["tax_rate_used"] = t
    annual = sorted(data["annual"], key=lambda r: r["year"])
    latest = annual[-1]
    ttm = dict(latest)
    ttm.update({k: v for k, v in (data.get("ttm") or {}).items() if v is not None})
    mkt = data["market"]
    q = data.get("qualitative", {}) or {}
    g = data.get("governance", {}) or {}

    mcap = num(mkt["market_cap"])
    debt = num(mkt.get("total_debt", latest.get("total_debt"))) or 0.0
    lease = num(mkt.get("lease_liabilities", latest.get("lease_liabilities"))) or 0.0
    if cfg.get("exclude_lease_liabilities_from_debt", True) and lease:
        debt = max(debt - lease, 0.0)
        notes.append(f"Lease liabilities of {lease:g} removed from debt (not real borrowing).")
    cash = num(mkt.get("cash_and_investments", latest.get("cash"))) or 0.0
    ev = mcap + debt - cash
    m.update(market_cap=mcap, debt_ex_lease=debt, cash=cash, ev=ev)

    sales = num(ttm.get("sales"))
    ebitda = num(ttm.get("ebitda"))
    dep = num(ttm.get("depreciation")) or 0.0
    intr = num(ttm.get("interest")) or 0.0
    pat = num(ttm.get("pat"))
    ocf = num(ttm.get("ocf"))
    ebit = None if ebitda is None else ebitda - dep
    nw = num(latest.get("net_worth"))

    # --- six reported multiples (TTM)
    m["ev_ebitda"] = pos_div(ev, ebitda)
    m["ev_ebit"] = pos_div(ev, ebit)
    m["pe"] = pos_div(mcap, pat)
    m["ev_ocf"] = pos_div(ev, ocf)
    m["ps"] = pos_div(mcap, sales)
    m["ev_sales"] = pos_div(ev, sales)
    for k in ("ev_ebitda", "ev_ebit", "pe", "ev_ocf"):
        if m[k] is None:
            notes.append(f"{k} not meaningful (denominator missing or <= 0).")

    # --- adjusted earnings #1: strip one-offs
    adj = pat
    for item in data.get("one_offs", []) or []:
        amt = num(item.get("amount")) or 0.0
        post = amt if item.get("tax_effected") else amt * (1 - t)
        if adj is None:
            break
        if item.get("type") == "expense":
            adj += post
        elif item.get("type") == "gain":
            adj -= post
    m["trailing_adj_pat"] = adj
    m["trailing_adj_pe"] = pos_div(mcap, adj)

    # --- adjusted earnings #2: cyclically adjusted
    hist = [r for r in annual[-cfg["cyclical_history_years"]:]
            if num(r.get("sales")) and num(r.get("ebitda")) is not None]
    if len(hist) >= cfg["min_history_years_for_percentiles"] and sales:
        avg_margin = statistics.mean(num(r["ebitda"]) / num(r["sales"]) for r in hist)
        cyc_ebitda = avg_margin * sales
        cyc_pbt = cyc_ebitda - dep - intr
        cyc_pat = cyc_pbt * (1 - t) if cyc_pbt > 0 else cyc_pbt
        m.update(avg_ebitda_margin_pct=avg_margin * 100, margin_years_used=len(hist),
                 cyclically_adjusted_ebitda=cyc_ebitda, cyclically_adjusted_pat=cyc_pat,
                 cyclically_adjusted_pe=pos_div(mcap, cyc_pat))
    else:
        m.update(cyclically_adjusted_pat=None, cyclically_adjusted_pe=None)
        notes.append("Cyclically adjusted P/E needs >= "
                     f"{cfg['min_history_years_for_percentiles']} years of sales+EBITDA.")

    # --- adjusted earnings #3: forward
    fwd = data.get("forward") or {}
    fwd_years = num(fwd.get("years_out")) or 2
    fwd_pat = num(fwd.get("pat"))
    if fwd_pat is None and num(fwd.get("sales")) and num(fwd.get("ebitda_margin_pct")) is not None:
        f_pbt = (num(fwd["sales"]) * num(fwd["ebitda_margin_pct"]) / 100
                 - (num(fwd.get("depreciation")) or dep) - (num(fwd.get("interest")) or intr))
        fwd_pat = f_pbt * (1 - t)
        notes.append("Forward PAT derived from forward sales x margin - D&A - interest, taxed.")
    m["forward_pat"] = fwd_pat
    m["forward_years_out"] = fwd_years
    m["forward_pe"] = pos_div(mcap, fwd_pat)
    base = adj if (adj is not None and adj > 0) else None
    fg = cagr(base, fwd_pat, fwd_years)
    if fg is None and num(fwd.get("pat_cagr_pct")) is not None:
        fg = num(fwd["pat_cagr_pct"]) / 100
    m["forward_pat_cagr_pct"] = None if fg is None else fg * 100

    # PEG: current adjusted P/E / growth%; fall back to forward P/E when trailing is not meaningful
    pe_for_peg, src = (m["trailing_adj_pe"], "trailing adjusted P/E")
    if data["business_type"] in ("capex_transition", "new_age") or pe_for_peg is None:
        pe_for_peg, src = (m["forward_pe"], "forward P/E")
    lt = num(fwd.get("long_term_growth_pct"))
    growth_for_peg = lt if lt is not None else m["forward_pat_cagr_pct"]
    m["peg"] = pos_div(pe_for_peg, growth_for_peg)
    m["peg_basis"] = src + (" / long-term growth" if lt is not None else " / forward PAT CAGR")
    if lt is None and m["forward_pat_cagr_pct"] and m["forward_pat_cagr_pct"] > 50:
        notes.append("PEG uses >50% rebound growth off a depressed base and will look flattering; "
                     "set forward.long_term_growth_pct for a sustainable-growth PEG.")

    # earnings gap
    if len(annual) >= 4:
        past = cagr(annual[-4].get("pat"), annual[-1].get("pat"), 3)
        m["past3y_pat_cagr_pct"] = None if past is None else past * 100
        ps3 = cagr(annual[-4].get("sales"), annual[-1].get("sales"), 3)
        m["past3y_sales_cagr_pct"] = None if ps3 is None else ps3 * 100
    else:
        m["past3y_pat_cagr_pct"] = None
    if m["forward_pat_cagr_pct"] is not None:
        past = m.get("past3y_pat_cagr_pct")
        # if past PAT CAGR not computable (losses), treat as 0 growth baseline
        m["earnings_gap_pp"] = m["forward_pat_cagr_pct"] - (past if past is not None else 0.0)
    else:
        m["earnings_gap_pp"] = None

    # --- book value route
    norm_pat = m["cyclically_adjusted_pat"] if data["business_type"] == "cyclical" else adj
    m["pb"] = pos_div(mcap, nw)
    roe_n = pos_div(norm_pat, nw)
    roes = [num(r["pat"]) / num(r["net_worth"]) for r in annual[-10:]
            if num(r.get("pat")) is not None and (num(r.get("net_worth")) or 0) > 0]
    m["roe_10y_avg_pct"] = statistics.mean(roes) * 100 if roes else None
    guided = num(fwd.get("normalised_roe_pct"))
    if guided is not None:
        m["roe_normalised"], m["roe_basis"] = guided, "user/management guided long-term ROE"
    elif data["business_type"] == "cyclical":
        # through-cycle average, kept independent of the cyclically adjusted P/E to avoid double counting
        m["roe_normalised"], m["roe_basis"] = m["roe_10y_avg_pct"], "10-yr average ROE"
    elif data["business_type"] in ("capex_transition", "new_age") and pos_div(fwd_pat, nw):
        m["roe_normalised"], m["roe_basis"] = pos_div(fwd_pat, nw) * 100, "forward PAT / current net worth"
    else:
        m["roe_normalised"] = None if roe_n is None else roe_n * 100
        m["roe_basis"] = "trailing one-off-adjusted PAT / net worth"
    m["implied_pe_from_book"] = (m["pb"] / (m["roe_normalised"] / 100)
                                 if m["pb"] and m["roe_normalised"] and m["roe_normalised"] > 0 else None)

    # --- cash-flow quality
    n = cfg["ocf_normalisation_years"]
    recent = [r for r in annual[-n:] if num(r.get("ocf")) is not None and num(r.get("ebitda")) is not None]
    if len(recent) >= 3:
        s_ocf = sum(num(r["ocf"]) for r in recent)
        s_ebitda = sum(num(r["ebitda"]) for r in recent)
        m["ocf_ebitda_conversion_5y"] = div(s_ocf, s_ebitda) if s_ebitda > 0 else None
        avg_ocf = s_ocf / len(recent)
        m["avg_ocf_5y"] = avg_ocf
        m["ev_ocf_normalised"] = pos_div(ev, avg_ocf)
        m["ocf_at_peak"] = (ocf is not None and avg_ocf > 0 and ocf > cfg["ocf_peak_multiple"] * avg_ocf)
    else:
        m.update(ocf_ebitda_conversion_5y=None, ev_ocf_normalised=None, ocf_at_peak=None)

    if len(annual) >= 2:
        p, c = annual[-2], annual[-1]
        sg = cagr(p.get("sales"), c.get("sales"), 1)
        rp, rc = num(p.get("receivables")), num(c.get("receivables"))
        if sg is not None and rp is not None and rc is not None and rp > 0:
            rg = rc / rp - 1
            m["receivables_growth_pct"] = rg * 100
            m["sales_growth_pct"] = sg * 100
            m["receivables_minus_sales_growth_pp"] = (rg - sg) * 100
            m["receivables_fell_while_sales_grew"] = rc < rp and sg > 0
        else:
            m["receivables_minus_sales_growth_pp"] = None
    days = [div(num(r.get("receivables")) * 365 if num(r.get("receivables")) is not None else None,
                r.get("sales")) for r in annual]
    m["receivable_days_latest"] = days[-1] if days else None

    # --- balance sheet
    norm_ebitda = m.get("cyclically_adjusted_ebitda") if data["business_type"] == "cyclical" else ebitda
    net_debt = debt - cash
    m["net_debt"] = net_debt
    if net_debt <= 0:
        m["net_debt_to_ebitda"] = 0.0 if not norm_ebitda or norm_ebitda <= 0 else net_debt / norm_ebitda
    else:
        m["net_debt_to_ebitda"] = net_debt / norm_ebitda if norm_ebitda and norm_ebitda > 0 else 99.0
    if len(annual) >= 4:
        d0 = num(annual[-4].get("total_debt"))
        d1 = num(annual[-1].get("total_debt"))
        if d0 is not None and d1 is not None:
            m["debt_change_3y_pct"] = 0.0 if d0 == 0 and d1 == 0 else (
                ((d1 - d0) / d0 * 100) if d0 > 0 else 100.0)
        else:
            m["debt_change_3y_pct"] = None
    else:
        m["debt_change_3y_pct"] = None

    # --- valuation vs own history
    hv = {"ev_sales": [], "pe": [], "ev_ebitda": [], "pb": []}
    for r in annual:
        mc = num(r.get("market_cap_year_end"))
        if mc is None:
            continue
        ev_y = mc + (num(r.get("total_debt")) or 0) - (num(r.get("lease_liabilities")) or 0) - (num(r.get("cash")) or 0)
        hv["ev_sales"].append(pos_div(ev_y, r.get("sales")))
        hv["pe"].append(pos_div(mc, r.get("pat")))
        hv["ev_ebitda"].append(pos_div(ev_y, r.get("ebitda")))
        hv["pb"].append(pos_div(mc, r.get("net_worth")))
    current = {"ev_sales": m["ev_sales"], "pe": m["trailing_adj_pe"] or m["pe"],
               "ev_ebitda": m["ev_ebitda"], "pb": m["pb"]}
    m["history"] = {}
    for k, series in hv.items():
        s = [x for x in series if x is not None]
        if len(s) >= cfg["min_history_years_for_percentiles"]:
            m[f"pctile_{k}"] = pctile(current[k], s)
            m["history"][k] = {"min": min(s), "median": statistics.median(s), "max": max(s), "n": len(s)}
        else:
            m[f"pctile_{k}"] = None
    if hv["pe"] and not any(x is not None for x in hv["ev_sales"]):
        notes.append("No market_cap_year_end history: percentile rules skipped.")

    # --- expense habits (one-off vs habit) and peer comparison
    m["expense_flags"] = expense_flags(annual, data.get("peers") or [], cfg["expense_habit"])
    m["expense_flag_count"] = (sum(1 for f in m["expense_flags"]
                                   if f["kind"] in ("cut_boosting_margin", "peer_outlier_low"))
                               if any(r.get("expense_items") for r in annual) else None)

    # --- segment mix
    m["segments"] = segment_mix(annual)

    # --- asymmetry
    tgt = data.get("target") or {}
    exit_pe = num(tgt.get("exit_pe")) or cfg["default_exit_pe"]
    floor_pe = num(tgt.get("floor_pe"))
    if floor_pe is None:  # conservative: lower of history-min P/E and the config default
        hist_min = m["history"].get("pe", {}).get("min")
        floor_pe = min(hist_min, cfg["default_floor_pe"]) if hist_min else cfg["default_floor_pe"]
    floor_pb = num(tgt.get("floor_pb"))
    if floor_pb is None:
        floor_pb = cfg["default_floor_pb"]
    m["exit_pe_used"], m["floor_pe_used"], m["floor_pb_used"] = exit_pe, floor_pe, floor_pb
    m["upside_multiple"] = div(fwd_pat * exit_pe, mcap) if fwd_pat and fwd_pat > 0 else None
    floor_earn = [x for x in (m["cyclically_adjusted_pat"], adj) if x is not None and x > 0]
    earn_floor = floor_pe * min(floor_earn) if floor_earn else None  # lower of normalised earnings views
    book_floor = floor_pb * nw if nw and nw > 0 else None             # asset-backed floor
    floors = [f for f in (earn_floor, book_floor) if f is not None]
    m["earnings_floor"], m["book_floor"] = earn_floor, book_floor
    if floors:
        m["floor_value"] = max(floors)
        m["downside_pct"] = max(0.0, (1 - m["floor_value"] / mcap) * 100)
    else:
        m["floor_value"], m["downside_pct"] = None, None

    # --- qualitative and governance pass-through
    m["change_identified"] = q.get("change_identified")
    nps_now, nps_then = num(q.get("new_product_share_pct_now")), num(q.get("new_product_share_pct_3y_ago"))
    m["new_product_share_gain_pp"] = None if nps_now is None or nps_then is None else nps_now - nps_then
    for k in ("sector_underperformed_10y", "capital_exiting_sector", "drawdown_from_3y_high_pct",
              "seller_concern", "ai_disruption_risk"):
        m[k] = q.get(k)
    opt = q.get("optionality") or []
    if opt:
        m["optionality"] = "protected" if q.get("base_business_protects_value") else "unprotected"
    else:
        m["optionality"] = "none" if "optionality" in q else None
    m["optionality_items"] = opt

    m["years_listed"] = num(g.get("years_listed"))
    m["guidance_track_record"] = g.get("guidance_track_record")
    m["credible_board_or_investors"] = g.get("credible_board_or_investors")
    m["related_party_clean"] = g.get("related_party_clean")
    lavish = num(g.get("promoter_vanity_spend"))
    m["lavish_spend_pct_mcap"] = None if lavish is None else lavish / mcap * 100
    m["auditor_clean"] = g.get("auditor_clean")
    return m, notes


def expense_flags(annual, peers, h):
    flags = []
    items = sorted({k for r in annual for k in (r.get("expense_items") or {})})
    for item in items:
        series = [(r["year"], div(r["expense_items"].get(item), r.get("sales")))
                  for r in annual if (r.get("expense_items") or {}).get(item) is not None]
        series = [(y, p * 100) for y, p in series if p is not None]
        if len(series) < h["min_years"]:
            continue
        pcts = [p for _, p in series]
        base = statistics.median(pcts[:-1])
        if base <= 0:
            continue
        dev = [(p - base) / base for p in pcts]
        latest_dev = dev[-1]
        run_up = 0
        for d in reversed(dev):
            if d > h["relative_deviation"]:
                run_up += 1
            else:
                break
        run_dn = 0
        for d in reversed(dev):
            if d < -h["relative_deviation"]:
                run_dn += 1
            else:
                break
        rec = {"item": item, "latest_pct_sales": rnd(pcts[-1]), "historical_median_pct": rnd(base),
               "relative_deviation": rnd(latest_dev, 3)}
        if run_up >= h["persistent_years"]:
            flags.append({**rec, "kind": "persistent_increase",
                          "meaning": "Elevated for several years: treat as the new normal (habit), do not add back."})
        elif run_up >= 1:
            flags.append({**rec, "kind": "one_off_spike",
                          "meaning": "Spike vs history: candidate one-off; normalise back to median if the cause is temporary."})
        elif run_dn >= 1:
            flags.append({**rec, "kind": "cut_boosting_margin",
                          "meaning": "Cut well below history: margins may be flattered (e.g. ad spend cut); expect reversal."})
    # peers
    latest = annual[-1]
    for item, val in (latest.get("expense_items") or {}).items():
        peer_vals = [num((p.get("expense_pct") or {}).get(item)) for p in peers]
        peer_vals = [v for v in peer_vals if v is not None]
        own = div(val, latest.get("sales"))
        if len(peer_vals) >= 2 and own is not None:
            med = statistics.median(peer_vals)
            own *= 100
            if med > 0 and own < h["peer_low_ratio"] * med:
                flags.append({"item": item, "kind": "peer_outlier_low", "latest_pct_sales": rnd(own),
                              "peer_median_pct": rnd(med),
                              "meaning": "Far below peers: either a genuinely different model or numbers that don't add up. Ask why."})
            elif med > 0 and own > h["peer_high_ratio"] * med:
                flags.append({"item": item, "kind": "peer_outlier_high", "latest_pct_sales": rnd(own),
                              "peer_median_pct": rnd(med),
                              "meaning": "Far above peers: check classification (e.g. packaging in raw material vs other expenses)."})
    return flags


def segment_mix(annual):
    with_seg = [r for r in annual if r.get("segments")]
    if len(with_seg) < 2:
        return None
    first, last = with_seg[0], with_seg[-1]
    yrs = last["year"] - first["year"]
    out = {"from_year": first["year"], "to_year": last["year"], "segments": []}
    tf, tl = sum(first["segments"].values()), sum(last["segments"].values())
    for name in sorted(set(first["segments"]) | set(last["segments"])):
        a, b = first["segments"].get(name, 0), last["segments"].get(name, 0)
        out["segments"].append({"name": name, "share_from_pct": rnd(div(a, tf) * 100 if tf else None),
                                "share_to_pct": rnd(div(b, tl) * 100 if tl else None),
                                "cagr_pct": rnd(None if cagr(a, b, yrs) is None else cagr(a, b, yrs) * 100)})
    shrinking = [s for s in out["segments"] if s["share_to_pct"] is not None and s["share_from_pct"]
                 and s["share_to_pct"] < s["share_from_pct"]]
    if shrinking:
        big = max(shrinking, key=lambda s: s["share_from_pct"] - s["share_to_pct"])
        rest_a = tf - first["segments"].get(big["name"], 0)
        rest_b = tl - last["segments"].get(big["name"], 0)
        rg = cagr(rest_a, rest_b, yrs)
        out["drag_segment"] = big["name"]
        out["rest_of_business_cagr_pct"] = rnd(None if rg is None else rg * 100)
        out["note"] = (f"Headline growth hides mix shift: '{big['name']}' fell from {big['share_from_pct']}% to "
                       f"{big['share_to_pct']}% of sales; the rest grew at {out['rest_of_business_cagr_pct']}%/yr.")
    return out


# ----------------------------------------------------------------- scoring
def score_rule(rule, value):
    if value is None:
        return None
    rtype = rule.get("type", "band")
    if rtype == "bool":
        if not isinstance(value, bool):
            return None
        return rule["true_points"] if value else rule["false_points"]
    if rtype == "category":
        return rule["map"].get(str(value).lower()) if str(value).lower() in rule["map"] else None
    v = num(value)
    if v is None:
        return None
    for thr, pts in rule["bands"]:
        if (rule["direction"] == "lower_better" and v <= thr) or \
           (rule["direction"] == "higher_better" and v >= thr):
            return pts
    return 0


def score(data, m, cfg):
    pillars = {"valuation": cfg["valuation_rules"][data["business_type"]], **cfg["pillars"]}
    results, earned, possible = {}, 0.0, 0.0
    for pname, rules in pillars.items():
        rows, pe, pp = [], 0.0, 0.0
        for r in rules:
            val = m.get(r["metric"])
            pts = score_rule(r, val)
            rows.append({"metric": r["metric"], "label": r["label"], "value": rnd(val, 3) if isinstance(val, float) else val,
                         "points": pts, "max": r["max"],
                         "rule": r.get("bands") or r.get("map") or {"true": r.get("true_points"), "false": r.get("false_points")}})
            if pts is not None:
                pe += pts
                pp += r["max"]
        results[pname] = {"earned": pe, "possible": pp, "max": sum(r["max"] for r in rules),
                          "pct": rnd(pe / pp * 100, 1) if pp else None, "rules": rows}
        earned += pe
        possible += pp
    total_max = sum(p["max"] for p in results.values())
    raw = earned / possible * 100 if possible else 0.0
    coverage = possible / total_max if total_max else 0.0

    # kill switches
    g = data.get("governance", {}) or {}
    ks = cfg["kill_switches"]
    kills = [f for f in ks["flags"] if g.get(f) is True]
    yrs_ago = num(g.get("promoter_vanity_spend_years_ago"))
    recent = yrs_ago is None or yrs_ago < ks.get("vanity_spend_recent_years", 5)
    if m.get("lavish_spend_pct_mcap") is not None and m["lavish_spend_pct_mcap"] >= ks["lavish_spend_pct_of_mcap"]:
        if recent:
            kills.append(f"promoter_vanity_spend >= {ks['lavish_spend_pct_of_mcap']}% of market cap")
        else:
            s_note = (f"Vanity spend was {yrs_ago:g} yrs ago: scored as a penalty, not a kill switch "
                      f"(the investor in the source bought Force Motors years after its aircraft purchase).")
            results["governance_and_history"].setdefault("notes", []).append(s_note)
    final = min(raw, ks["score_cap"]) if kills else raw

    verdict = next(label for thr, label in cfg["verdict_bands"] if final >= thr)
    if results["valuation"]["possible"] == 0:
        verdict = "INSUFFICIENT DATA - no valuation rule could be evaluated; score is not meaningful"
    if kills:
        verdict = "AVOID - governance kill switch triggered"

    # cheap vs undervalued
    c = cfg["classification"]
    vpct = results["valuation"]["pct"]
    gpct = results["growth_and_earnings_gap"]["pct"]
    cheap = vpct is not None and vpct >= c["cheap_valuation_pct"]
    change = (gpct is not None and gpct >= c["change_growth_pct"]) or m.get("change_identified") is True
    structural = str(m.get("seller_concern", "")).lower() in ("structural", "management")
    if kills:
        cls = "UNINVESTABLE (governance)"
    elif cheap and change and not structural:
        cls = "CHEAP AND UNDERVALUED - cheap, with an identified change the market is missing"
    elif cheap:
        cls = "CHEAP BUT POSSIBLY A VALUE TRAP - no identified change, or sellers' concern looks structural"
    elif (change and data["business_type"] != "cyclical"   # PEG off a cyclical trough is not growth
          and m.get("peg") is not None and m["peg"] <= c["garp_peg_max"]):
        cls = "NOT CHEAP BUT UNDERVALUED - growth priced reasonably (PEG <= 1)"
    else:
        cls = "NOT CHEAP - fair or expensive on this framework"

    return {"score": rnd(final, 1), "raw_score_before_kill_cap": rnd(raw, 1), "coverage": rnd(coverage, 3),
            "verdict": verdict, "classification": cls, "kill_switches": kills, "pillars": results}


# ----------------------------------------------------------------- report
def fmt(v):
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def markdown(data, m, s, notes, cfg):
    L = []
    L.append(f"# Mispricing score: {data.get('company', 'Unnamed')}")
    L.append(f"As of {data.get('as_of', 'n/a')} | business type: **{data['business_type']}** | units: {data.get('units', 'as given')}\n")
    L.append(f"**Score: {s['score']} / 100**  ({s['verdict']})")
    L.append(f"**Classification:** {s['classification']}")
    L.append(f"Data coverage: {s['coverage']*100:.0f}% of rule points were evaluable; score is re-based to the evaluable points.")
    if s["coverage"] < cfg["min_coverage_warning"]:
        L.append(f"> WARNING: coverage below {cfg['min_coverage_warning']*100:.0f}%. Fill missing inputs before relying on the score.")
    if s["kill_switches"]:
        L.append(f"> KILL SWITCH: {', '.join(s['kill_switches'])}. Raw score was {s['raw_score_before_kill_cap']}, capped at {cfg['kill_switches']['score_cap']}.")
    L.append("\n## Pillars\n")
    L.append("| Pillar | Earned | Evaluable max | Full max | % |")
    L.append("|---|---|---|---|---|")
    for p, r in s["pillars"].items():
        L.append(f"| {p} | {r['earned']:g} | {r['possible']:g} | {r['max']:g} | {fmt(r['pct'])} |")
    L.append("\n## Rule-by-rule audit trail\n")
    L.append("| Pillar | Rule | Value | Points | Rule bands / map |")
    L.append("|---|---|---|---|---|")
    for p, r in s["pillars"].items():
        for row in r["rules"]:
            L.append(f"| {p} | {row['label']} | {fmt(row['value'])} | "
                     f"{'n/a' if row['points'] is None else row['points']}/{row['max']} | `{json.dumps(row['rule'])}` |")
    L.append("\n## The six multiples (TTM, reported) and adjusted views\n")
    L.append("| Metric | Value | Own-history percentile |")
    L.append("|---|---|---|")
    for k, lab, pk in [("ev_ebitda", "EV/EBITDA", "pctile_ev_ebitda"), ("ev_ebit", "EV/EBIT", None),
                       ("pe", "P/E (reported)", None), ("trailing_adj_pe", "P/E (one-offs stripped)", "pctile_pe"),
                       ("cyclically_adjusted_pe", "P/E (cyclically adjusted)", None),
                       ("forward_pe", f"P/E (forward, {fmt(m.get('forward_years_out'))} yr)", None),
                       ("ev_ocf", "EV/OCF", None), ("ev_ocf_normalised", "EV / 5-yr avg OCF", None),
                       ("ps", "Price/Sales", None), ("ev_sales", "EV/Sales", "pctile_ev_sales"),
                       ("pb", "P/B", "pctile_pb"), ("implied_pe_from_book", "Implied P/E (P/B / ROE)", None),
                       ("peg", f"PEG ({m.get('peg_basis')})", None)]:
        L.append(f"| {lab} | {fmt(m.get(k))} | {fmt(m.get(pk)) if pk else '-'} |")
    L.append("\n## Key computed facts\n")
    for k in ("ev", "net_debt", "trailing_adj_pat", "avg_ebitda_margin_pct", "cyclically_adjusted_pat",
              "forward_pat", "forward_pat_cagr_pct", "past3y_pat_cagr_pct", "earnings_gap_pp",
              "roe_normalised", "roe_basis", "roe_10y_avg_pct", "ocf_ebitda_conversion_5y", "receivables_minus_sales_growth_pp",
              "receivables_fell_while_sales_grew", "upside_multiple", "floor_value", "downside_pct",
              "exit_pe_used", "floor_pe_used", "floor_pb_used",
              "earnings_floor", "book_floor"):
        L.append(f"- {k}: {fmt(m.get(k))}")
    if m["expense_flags"]:
        L.append("\n## One-off vs habit: expense flags\n")
        for f in m["expense_flags"]:
            extra = (f"median {f['historical_median_pct']}%" if "historical_median_pct" in f
                     else f"peer median {f['peer_median_pct']}%")
            L.append(f"- **{f['item']}** ({f['kind']}): {f['latest_pct_sales']}% of sales vs {extra}. {f['meaning']}")
    if m.get("segments") and m["segments"].get("note"):
        L.append(f"\n## Segment mix\n\n{m['segments']['note']}")
    if notes:
        L.append("\n## Notes\n")
        L.extend(f"- {n}" for n in notes)
    L.append("\n---\nMechanical output of a published framework. Not investment advice; verify every input against filings.")
    return "\n".join(L)


# ----------------------------------------------------------------- main
def run(data, cfg):
    errs = validate(data)
    if errs:
        raise ValueError("Input errors:\n  - " + "\n  - ".join(errs))
    m, notes = compute_metrics(data, cfg)
    s = score(data, m, cfg)
    return m, s, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="stock input JSON")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--json", help="write full result JSON here")
    ap.add_argument("--md", help="write markdown report here (default: stdout)")
    ap.add_argument("--template", action="store_true", help="print blank input template")
    a = ap.parse_args(argv)
    if a.template:
        print(TEMPLATE.read_text(encoding="utf-8"))
        return 0
    if not a.input:
        ap.error("input JSON required (or --template)")
    cfg, data = load_json(a.config), load_json(a.input)
    try:
        m, s, notes = run(data, cfg)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    md = markdown(data, m, s, notes, cfg)
    if a.json:
        Path(a.json).write_text(json.dumps({"company": data.get("company"), "result": s,
                                            "metrics": m, "notes": notes,
                                            "config_version": cfg.get("version")},
                                           indent=2, default=str), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
