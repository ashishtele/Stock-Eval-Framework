#!/usr/bin/env python3
"""Deterministic scorer for the Quality Contra Score (QCS), stdlib only.

Usage: python score.py input.json [more.json ...] [--json]
Every input is {"value": ..., "source": "..."}; points are awarded only when both are present.
Later files override earlier ones (e.g. fetched.json analyst.json position.json).
"""
import argparse
import json
import sys

MOAT = {
    "brand_leader_top3_share",
    "lowest_cost_producer",
    "technology_or_product_leadership",
    "distribution_or_network_scale",
    "pricing_power_passed_cost_inflation",
    "regulatory_licence_or_scarce_asset",
}
BACKSTOP = {
    "net_cash_ge_5pct_of_mcap",
    "promoter_or_parent_infused_capital_in_past_crisis",
    "strong_group_parent",
    "credit_rating_aa_or_better",
}
PEDIGREE = {
    "tried_tested_group_or_mnc": 4,
    "clean_promoter_record_10y": 3,
    "professional_board_clean_record": 2,
    "limited_record": 0,
}
CRISIS = {
    "operated_through_major_shock",
    "market_share_held_or_gained_in_downturn",
    "cost_reset_then_recovery",
    "profit_regained_prior_peak_within_3y",
    "no_distress_dilution_or_asset_sale",
}
CAPITAL = {
    "buyback_or_special_dividend_5y",
    "capex_funded_internally",
    "no_value_destroying_acquisition_5y",
}
INSIDER = {
    "promoter_open_market_buy_24m",
    "promoter_subscribed_rights_or_preferential_24m",
    "buyback_promoter_not_tendering_24m",
    "buyback_price_ge_15pct_above_market_24m",
}
FALL_CAUSE = {
    "market_wide_macro": 4,
    "input_cost_or_commodity": 4,
    "sector_temporary": 4,
    "company_specific_fixable": 3,
    "prolonged_neglect": 3,
    "no_fall": 0,
    "unknown": 0,
    "structural_disruption": 0,
}
TEMPORARY = {
    "revenue_or_volume_base_intact",
    "management_corrective_actions_announced",
    "precedent_of_recovery",
    "trigger_reversing_or_time_bound",
    "positive_catalyst_emerging",
}
SENTIMENT = {
    "institutions_cut_ge_1pp_4q",
    "broker_downgrades_or_target_cuts_6m",
    "negative_media_or_sector_out_of_favour",
    "earnings_estimates_cut_6m",
}
DISRUPTION = {"low": 5, "moderate": 3, "high": 0}
CYCLICALITY = ("secular", "cyclical_commodity")
PILLARS = {
    "P1": ("Business Quality", 25),
    "P2": ("Balance Sheet Strength", 15),
    "P3": ("Management DNA & Alignment", 20),
    "P4": ("Contra Setup (Temporary Pain)", 20),
    "P5": ("Valuation & Yield Support", 15),
    "P6": ("Disruption Risk", 5),
}
QUALITY_BAR, SETUP_BAR = 42, 20


class Missing(Exception):
    pass


class Unsourced(Exception):
    pass


class Invalid(Exception):
    pass


class Inputs:
    def __init__(self, raw):
        self.raw = raw

    def get(self, key):
        item = self.raw.get(key)
        if not isinstance(item, dict) or item.get("value") is None:
            raise Missing(key)
        if not str(item.get("source") or "").strip():
            raise Unsourced(key)
        return item["value"]

    def num(self, key):
        v = self.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise Invalid(f"{key} must be a number")
        return float(v)

    def flag(self, key):
        v = self.get(key)
        if not isinstance(v, bool):
            raise Invalid(f"{key} must be true/false")
        return v

    def items(self, key, allowed):
        v = self.get(key)
        if not isinstance(v, list):
            raise Invalid(f"{key} must be a list")
        bad = [x for x in v if x not in allowed]
        if bad:
            raise Invalid(f"{key} has unknown items {bad}")
        return set(v)

    def choice(self, key, allowed):
        v = self.get(key)
        if v not in allowed:
            raise Invalid(f"{key} must be one of {sorted(allowed)}")
        return v


def ge(x, table):
    for threshold, points in table:
        if x >= threshold:
            return points
    return 0


def le(x, table):
    for threshold, points in table:
        if x <= threshold:
            return points
    return 0


# ---- P1 Business quality -----------------------------------------------------
def m_roce(i):
    x = i.num("roce_10y_avg_pct")
    return ge(x, [(20, 8), (15, 6), (12, 3), (10, 1)]), f"10y avg ROCE {x:g}% (bar: ~15%)"


def m_roce_consistency(i):
    x = i.num("roce_pct_years_ge_15")
    return ge(x, [(80, 3), (60, 2), (40, 1)]), f"{x:g}% of years with ROCE >= 15%"


def m_cfo_conversion(i):
    x = i.num("cfo_to_pat_10y")
    return ge(x, [(0.9, 6), (0.75, 4), (0.5, 2)]), f"10y CFO/PAT {x:.2f}"


def m_cfo_consistency(i):
    x = i.num("cfo_positive_years_pct")
    return ge(x, [(90, 2), (70, 1)]), f"CFO positive in {x:g}% of years"


def m_moat(i):
    n = len(i.items("moat_evidence", MOAT))
    return [0, 2, 4, 6][min(n, 3)], f"{n} moat proof(s)"


# ---- P2 Balance sheet --------------------------------------------------------
def m_net_debt(i):
    x = i.num("net_debt_to_ebitda")
    return le(x, [(0, 8), (1, 6), (2, 4), (3.5, 1)]), f"net debt/EBITDA {x:.2f} (rule: <= 3.5)"


def m_interest(i):
    x = i.num("interest_coverage")
    return ge(x, [(10, 3), (5, 2), (3, 1)]), f"interest coverage {x:g}x"


def m_backstop(i):
    n = len(i.items("funding_backstop", BACKSTOP))
    return n, f"{n}/4 deep-pocket proofs"


# ---- P3 Management DNA -------------------------------------------------------
def m_pedigree(i):
    v = i.choice("governance_pedigree", PEDIGREE)
    return PEDIGREE[v], v


def m_crisis(i):
    n = len(i.items("crisis_evidence", CRISIS))
    return [0, 2, 4, 6][min(n, 3)], f"{n} trial-by-fire proof(s)"


def m_payout(i):
    x = i.num("dividend_payout_5y_avg_pct")
    return ge(x, [(40, 2), (20, 1)]), f"5y avg dividend payout {x:g}%"


def m_capital(i):
    n = len(i.items("capital_allocation_evidence", CAPITAL))
    return n, f"{n}/3 capital-allocation proofs"


def m_insider(i):
    n = len(i.items("insider_signals", INSIDER))
    return [0, 2, 3][min(n, 2)], f"{n} promoter/buyback signal(s) in 24m"


def m_alignment(i):
    if i.get("promoter_holding_pct") == "professionally_managed":
        return 1, "professionally managed (no promoter)"
    chg, pledge = i.num("promoter_holding_change_3y_pp"), i.num("promoter_pledge_pct")
    note = f"promoter 3y change {chg:+g}pp, pledge {pledge:g}%"
    if chg >= -0.5 and pledge == 0:
        return 2, note
    if chg >= -2 and pledge <= 5:
        return 1, note
    return 0, note


# ---- P4 Contra setup ---------------------------------------------------------
def m_drawdown(i):
    x = i.num("drawdown_from_3y_high_pct")
    return ge(x, [(40, 5), (25, 4), (15, 2)]), f"{x:g}% below 3y closing high"


def m_derating(i):
    p, e = i.num("price_cagr_5y_pct"), i.num("eps_cagr_5y_pct")
    gap = p - e
    return le(gap, [(-10, 4), (-5, 3), (0, 1)]), f"price CAGR {p:g}% vs EPS CAGR {e:g}% (gap {gap:+.1f}pp)"


def m_cause(i):
    v = i.choice("fall_cause", FALL_CAUSE)
    return FALL_CAUSE[v], v


def m_temporary(i):
    n = len(i.items("temporariness_evidence", TEMPORARY))
    return min(n, 3), f"{n} proof(s) the pain is temporary"


def m_relative(i):
    x = i.num("rel_return_12m_vs_nifty_pp")
    return le(x, [(-20, 2), (-10, 1)]), f"12m return vs Nifty {x:+g}pp"


def m_sentiment(i):
    n = len(i.items("sentiment_evidence", SENTIMENT))
    return min(n, 2), f"{n} bad-news proof(s)"


# ---- P5 Valuation ------------------------------------------------------------
def m_pe_pct(i):
    x = i.num("pe_percentile_10y")
    return le(x, [(20, 5), (40, 3), (60, 1)]), f"P/E at {x:g}th percentile of own 10y"


def m_yield(i):
    dy, fy = i.num("dividend_yield_pct"), i.num("fcf_yield_pct")
    y = max(dy, fy)
    return ge(y, [(5, 5), (3.5, 4), (2.5, 2), (1.5, 1)]), f"dividend yield {dy:g}%, FCF yield {fy:g}% (best {y:g}%)"


def expected_return(i):
    g = min(max(i.num("eps_cagr_5y_pct"), 0), 20) / 100
    pe, med, dy = i.num("pe"), i.num("pe_median_10y"), i.num("dividend_yield_pct")
    if pe <= 0 or med <= 0:
        raise Invalid("pe and pe_median_10y must be > 0")
    rerate = min(max(med / pe, 0.67), 1.5)
    return 100 * (((1 + g) ** 3 * rerate) ** (1 / 3) - 1) + dy, g, rerate


def m_expected(i):
    r, g, rerate = expected_return(i)
    note = f"3y expected {r:.1f}%/yr = EPS growth {100 * g:.1f}% (0-20) + re-rating x{rerate:.2f} to 10y median P/E (0.67-1.5) + dividend"
    return ge(r, [(20, 5), (15, 3), (12, 1)]), note


# ---- P6 Disruption -----------------------------------------------------------
def m_disruption(i):
    v = i.choice("disruption_risk", DISRUPTION)
    return DISRUPTION[v], f"technology disruption risk: {v}"


METRICS = [
    ("P1", "roce_10y", 8, m_roce),
    ("P1", "roce_consistency", 3, m_roce_consistency),
    ("P1", "cfo_conversion", 6, m_cfo_conversion),
    ("P1", "cfo_consistency", 2, m_cfo_consistency),
    ("P1", "moat", 6, m_moat),
    ("P2", "net_debt_to_ebitda", 8, m_net_debt),
    ("P2", "interest_coverage", 3, m_interest),
    ("P2", "deep_pockets", 4, m_backstop),
    ("P3", "governance_pedigree", 4, m_pedigree),
    ("P3", "trial_by_fire", 6, m_crisis),
    ("P3", "dividend_payout", 2, m_payout),
    ("P3", "capital_allocation", 3, m_capital),
    ("P3", "insider_signals", 3, m_insider),
    ("P3", "promoter_alignment", 2, m_alignment),
    ("P4", "drawdown", 5, m_drawdown),
    ("P4", "derating_vs_earnings", 4, m_derating),
    ("P4", "fall_cause", 4, m_cause),
    ("P4", "temporariness", 3, m_temporary),
    ("P4", "relative_underperformance", 2, m_relative),
    ("P4", "bad_news_flow", 2, m_sentiment),
    ("P5", "pe_vs_own_10y", 5, m_pe_pct),
    ("P5", "yield_support", 5, m_yield),
    ("P5", "expected_return", 5, m_expected),
    ("P6", "disruption", 5, m_disruption),
]


# ---- Gates -------------------------------------------------------------------
def g_debt_rule(i):
    x = i.num("net_debt_to_ebitda")
    return x <= 3.5, f"net debt/EBITDA {x:.2f} (fail if > 3.5)"


def g_cash_generation(i):
    x = i.num("cfo_5y_cumulative_cr")
    return x > 0, f"5y cumulative CFO {x:,.0f} cr (fail if <= 0)"


def g_fraud(i):
    return not i.flag("proven_fraud_or_fund_diversion"), "proven fraud / fund diversion by promoters or KMP"


def g_auditor(i):
    return not i.flag("auditor_red_flag_3y"), "auditor qualification or resignation citing concerns (3y)"


GATES = [g_debt_rule, g_cash_generation, g_fraud, g_auditor]


def val(data, key):
    item = data.get("inputs", {}).get(key) or {}
    return item.get("value") if str(item.get("source") or "").strip() else None


def position_cap(verdict, data):
    if verdict.startswith("QUALITY CONTRA - ACCUMULATE"):
        cap = 10.0
    elif verdict.startswith("QUALITY CONTRA - STARTER"):
        cap = 5.0
    else:
        cap = 0.0
    why = [f"base {cap:g}% from verdict (absolute ceiling 12% however bullish)"]
    if val(data, "cyclicality") == "cyclical_commodity" and cap > 3:
        cap, why = 3.0, why + ["cyclical/commodity: price unpredictable -> 3%"]
    risk = val(data, "disruption_risk")
    if risk == "high" and cap > 3:
        cap, why = 3.0, why + ["high technology-disruption risk -> 3%"]
    elif risk == "moderate" and cap > 6:
        cap, why = 6.0, why + ["moderate disruption risk -> 6%, raise only as thesis confirms"]
    return cap, why


def plan(data, verdict, cap, flags):
    out = []
    price, pe, p40, p20 = (val(data, k) for k in ("current_price", "pe", "pe_p40_10y", "pe_p20_10y"))
    if all(isinstance(x, (int, float)) for x in (price, pe, p40, p20)) and pe > 0:
        b40, b20 = price * p40 / pe, price * p20 / pe
        where = "inside the strong zone" if price <= b20 else "inside the buy zone" if price <= b40 else "above the buy zone"
        out.append(f"Buy zone (P/E-based): below {b40:,.0f} (10y 40th pct P/E {p40:g}); strong below {b20:,.0f} "
                   f"(20th pct P/E {p20:g}). Price {price:,.0f} is {where}.")
    if cap > 0:
        out.append(f"Max weight {cap:g}% of portfolio; buy in 3 tranches (1/3 now, 1/3 on a further 10% fall or the next "
                   "quarter that confirms the temporary cause, 1/3 as the recovery shows in numbers).")
    elif verdict.startswith("WATCHLIST"):
        out.append("No position yet: quality without a contra price. Wait for bad news to bring the price into the buy zone.")
    out.append("Hold for the full ride: do not sell because the stock is up 20-40%; sell only on a thesis break.")
    out.append("Thesis break = net debt/EBITDA > 3.5, 5y CFO <= 0, ROCE < 12% two years running, a governance gate fails, "
               "or the cause of the fall proves structural.")
    out.append("Review the thesis every quarter; if after 6 quarters the temporary cause has not started reversing, "
               "cut to 2-3% on a bounce.")
    if any(f.startswith("CROWDED") for f in flags):
        out.append("Crowded/euphoric: do not add; if P/E is also > 2x its 10y median, trim back to the cap.")

    cost, months, weight = (val(data, k) for k in ("position_cost_price", "holding_months", "portfolio_weight_pct"))
    if isinstance(cost, (int, float)) and isinstance(price, (int, float)) and cost > 0:
        mult = price / cost
        out.append(f"Position: {mult:.2f}x cost.")
        if isinstance(weight, (int, float)) and weight > max(cap, 3):
            out.append(f"ACTION: weight {weight:g}% exceeds cap {max(cap, 3):g}% - trim to cap.")
        elif mult >= 1.2:
            out.append("ACTION: HOLD - a gain alone is not a sell reason (the guest's self-declared #1 mistake).")
        if mult < 1 and isinstance(months, (int, float)) and months >= 18 and not verdict.startswith("QUALITY CONTRA"):
            out.append("ACTION: underwater 18+ months and no longer a quality contra - reduce to 2-3% on the next bounce.")
    return out


def run(data):
    if data.get("business_type") != "non_financial":
        raise SystemExit("business_type must be 'non_financial'; banks/NBFCs/insurers are out of scope (no EBITDA/CFO).")
    i = Inputs(data.get("inputs", {}))

    gates = []
    for g in GATES:
        try:
            ok, note = g(i)
            gates.append({"gate": g.__name__[2:], "status": "pass" if ok else "FAIL", "note": note})
        except (Missing, Unsourced, Invalid) as e:
            gates.append({"gate": g.__name__[2:], "status": "unverified", "note": f"{type(e).__name__}: {e}"})

    rows = []
    for pillar, name, mx, fn in METRICS:
        try:
            pts, note = fn(i)
            status = "ok"
        except Missing as e:
            pts, status, note = 0, "missing", f"needs '{e}'"
        except Unsourced as e:
            pts, status, note = 0, "unsourced", f"'{e}' has no source"
        except Invalid as e:
            pts, status, note = 0, "invalid", str(e)
        rows.append({"pillar": pillar, "metric": name, "points": min(pts, mx), "max": mx, "status": status, "note": note})

    pillars = {p: round(sum(r["points"] for r in rows if r["pillar"] == p), 1) for p in PILLARS}
    total = round(sum(pillars.values()), 1)
    coverage = sum(r["status"] == "ok" for r in rows) / len(rows)
    quality = pillars["P1"] + pillars["P2"] + pillars["P3"]
    setup = pillars["P4"] + pillars["P5"]

    def axis(score_, pillar_set, bar):
        open_rows = [r for r in rows if r["pillar"] in pillar_set and r["status"] != "ok"]
        if score_ >= bar:
            return "pass", []
        # a missing metric must not be read as a weak one
        if score_ + sum(r["max"] for r in open_rows) >= bar:
            return "unproven", [r["metric"] for r in open_rows]
        return "fail", []

    q_state, q_open = axis(quality, ("P1", "P2", "P3"), QUALITY_BAR)
    s_state, s_open = axis(setup, ("P4", "P5"), SETUP_BAR)
    if s_state == "fail":
        quadrant = "QUALITY, NO CONTRA PRICE" if q_state == "pass" else "NO CONTRA PRICE"
    elif q_state == "unproven":
        quadrant = "QUALITY UNPROVEN"
    elif q_state == "pass":
        quadrant = "QUALITY CONTRA" if s_state == "pass" else "SETUP UNPROVEN"
    elif s_state == "pass":
        quadrant = "CHEAP, NOT QUALITY"
    else:
        quadrant = "NEITHER"

    statuses = {g["status"] for g in gates}
    provisional = coverage < 1 or "unverified" in statuses
    if "FAIL" in statuses:
        verdict = "REJECT (gate failed)"
    elif coverage < 0.8:
        verdict = "INCOMPLETE - gather sourced evidence before deciding"
    elif quadrant in ("QUALITY UNPROVEN", "SETUP UNPROVEN"):
        verdict = f"INCOMPLETE - {quadrant.split()[0].lower()} unproven; research {', '.join(q_open or s_open)}"
    elif quadrant == "QUALITY CONTRA":
        verdict = "QUALITY CONTRA - ACCUMULATE IN TRANCHES" if total >= 70 else "QUALITY CONTRA - STARTER POSITION"
    elif quadrant == "QUALITY, NO CONTRA PRICE":
        verdict = "WATCHLIST - quality without a contra price"
    elif quadrant == "CHEAP, NOT QUALITY":
        verdict = "AVOID - cheap is not contra (value-trap risk)"
    else:
        verdict = "PASS"
    if provisional and not verdict.startswith(("REJECT", "INCOMPLETE")):
        verdict = "PROVISIONAL " + verdict

    flags = []
    pe_pct, dma = val(data, "pe_percentile_10y"), val(data, "price_vs_200dma_pct")
    if isinstance(pe_pct, (int, float)) and isinstance(dma, (int, float)) and pe_pct >= 80 and dma >= 25:
        flags.append(f"CROWDED/FOMO: P/E at {pe_pct:g}th pct and {dma:+g}% vs 200DMA - good news is in the price")
    if val(data, "fall_cause") == "structural_disruption" or val(data, "disruption_risk") == "high":
        flags.append("STRUCTURAL/DISRUPTION: don't fight technology disruption - calibrated weight only")
    nde = val(data, "net_debt_to_ebitda")
    if isinstance(nde, (int, float)) and 2.5 < nde <= 3.5:
        flags.append(f"NEAR DEBT LIMIT: net debt/EBITDA {nde:.2f} close to the 3.5 rule")
    if quadrant == "CHEAP, NOT QUALITY":
        flags.append("VALUE TRAP RISK: low P/E without quality is not contra")
    if val(data, "disruption_risk") == "moderate" or val(data, "fall_cause") == "prolonged_neglect" \
            or val(data, "cyclicality") == "cyclical_commodity":
        flags.append("PATIENCE TEST: recovery timing uncertain - expect 1.5-3 years; collect dividends while waiting")
    if val(data, "group_extension_listing") is True:
        flags.append("GROUP-EXTENSION LISTING: new listing of a proven group's business - low-risk opportunity if cheap")
    insider = val(data, "insider_signals") or []
    if quality >= QUALITY_BAR and isinstance(insider, list) and "buyback_price_ge_15pct_above_market_24m" in insider \
            and "buyback_promoter_not_tendering_24m" in insider:
        flags.append("INSIDER CONTRA: company buying back >= 15% above market and promoter not tendering - "
                     "trailing P/E may overstate valuation on trough earnings (Bajaj Auto 2022 pattern); review manually")

    cap, cap_why = position_cap(verdict.replace("PROVISIONAL ", ""), data)
    try:
        exp = round(expected_return(i)[0], 1)
    except (Missing, Unsourced, Invalid):
        exp = None

    return {
        "company": data.get("company"),
        "ticker": data.get("ticker"),
        "as_of": data.get("as_of"),
        "gates": gates,
        "metrics": rows,
        "pillars": {p: {"name": PILLARS[p][0], "score": pillars[p], "max": PILLARS[p][1]} for p in PILLARS},
        "total": total,
        "quality_score": quality,
        "setup_score": setup,
        "quadrant": quadrant,
        "evidence_coverage": round(coverage, 3),
        "verdict": verdict,
        "expected_3y_return_pct": exp,
        "max_weight_pct": cap,
        "max_weight_reasons": cap_why,
        "flags": flags,
        "plan": plan(data, verdict.replace("PROVISIONAL ", ""), cap, flags),
    }


def render(r):
    out = [f"{r['company']} ({r['ticker']})  as of {r['as_of']}", "", "GATES"]
    out += [f"  [{g['status']:<10}] {g['note']}" for g in r["gates"]]
    for p, meta in r["pillars"].items():
        out += ["", f"{p} {meta['name']}: {meta['score']:g}/{meta['max']}"]
        out += [f"  {m['metric']:<26} {m['points']:>4g}/{m['max']:<2} {m['status']:<9} {m['note']}"
                for m in r["metrics"] if m["pillar"] == p]
    out += [
        "",
        f"TOTAL SCORE        {r['total']:g}/100",
        f"QUALITY (P1-P3)    {r['quality_score']:g}/60  (bar {QUALITY_BAR})",
        f"SETUP (P4-P5)      {r['setup_score']:g}/35  (bar {SETUP_BAR})",
        f"QUADRANT           {r['quadrant']}",
        f"EVIDENCE COVERAGE  {r['evidence_coverage']:.0%}",
        f"VERDICT            {r['verdict']}",
        f"EXPECTED 3Y RETURN {r['expected_3y_return_pct']}%/yr" if r["expected_3y_return_pct"] is not None else "EXPECTED 3Y RETURN n/a",
        f"MAX WEIGHT         {r['max_weight_pct']:g}%  ({'; '.join(r['max_weight_reasons'])})",
    ]
    out += [f"FLAG               {f}" for f in r["flags"]]
    out += ["", "PLAN"] + [f"  - {p}" for p in r["plan"]]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()
    data = {"inputs": {}}
    for path in args.inputs:
        with open(path, encoding="utf-8") as f:
            part = json.load(f)
        # null template entries must not erase values from earlier files
        data["inputs"].update({k: v for k, v in part.pop("inputs", {}).items()
                               if isinstance(v, dict) and v.get("value") is not None})
        data.update({k: v for k, v in part.items() if v not in (None, "")})
    result = run(data)
    print(json.dumps(result, indent=2) if args.json else render(result))


if __name__ == "__main__":
    sys.exit(main())
