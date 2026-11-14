#!/usr/bin/env python3
"""Deterministic scorer for the Surprise & Dot-Connect Score (SDS), stdlib only.

Usage: python score.py input.json [more.json ...] [--json]
Every input is {"value": ..., "source": "..."}; points are awarded only when both are present.
Later files override earlier ones (e.g. fetched.json analyst.json).
"""
import argparse
import json
import sys

TRIGGERS = {
    "acquirer_paid_premium_to_market",
    "successive_open_offers_or_buybacks_higher",
    "customer_advances_surge",
    "blockbuster_product_or_approval",
    "first_order_after_vendor_approval",
    "pricing_power_shift",
    "large_order_vs_mcap",
    "demerger_or_hidden_asset_unlock",
    "distressed_asset_bought_cheap",
    "policy_change_beneficiary",
    "unknown_brand_preferred_by_users",
}
THEME = {
    "sector_capex_budget_up_ge_15pct",
    "industry_capacity_target_documented",
    "lead_time_compression",
    "supply_shortage_or_backlog",
    "local_preference_or_import_substitution",
    "replacement_or_repeat_demand",
}
CHAIN = {
    "essential_component_multi_customer": 5,
    "niche_end_product_or_channel_edge": 3,
    "single_customer_dependent": 1,
    "commodity_price_taker": 0,
}
STABILITY = {
    "cfo_or_cs_tenure_ge_5y",
    "no_kmp_or_auditor_exit_3y",
    "long_tenured_workforce_evidence",
    "promoter_no_market_operations",
}
SCUTTLEBUTT = {
    "end_user_or_channel_feedback",
    "quality_feedback_customer_or_inspector",
    "factory_or_office_visit",
    "agm_or_management_meeting",
    "industry_expert_or_regulator_feedback",
    "product_seen_in_market",
}
AI_EXPOSURE = {
    "physical_goods_or_infra": 5,
    "agile_niche_tech_beneficiary": 4,
    "mixed": 2,
    "labour_arbitrage_services": 0,
}
DURABILITY = {
    "core_business_unchanged_5y",
    "avoids_patent_litigation_markets",
    "no_single_product_gt_70pct",
    "net_worth_cagr_ge_15pct_3y",
    "export_or_customer_diversified",
}
THESIS_TYPES = ("compounder", "turnaround", "special_situation", "cyclical")
PILLARS = {
    "P1": ("Surprise Trigger & Information Edge", 15),
    "P2": ("Opportunity & Value-Chain Position", 20),
    "P3": ("Business Model & Operating Leverage", 15),
    "P4": ("Promoter Skill & Integrity", 25),
    "P5": ("Valuation & Headroom", 15),
    "P6": ("Disruption & Durability", 10),
}


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


# ---- P1 Surprise -------------------------------------------------------------
def m_triggers(i):
    n = len(i.items("trigger_events", TRIGGERS))
    return [0, 4, 6, 7][min(n, 3)], f"{n} evidenced surprise trigger(s)"


def m_neglect(i):
    x = i.num("institutional_holding_pct")
    return le(x, [(5, 4), (10, 3), (20, 1)]), f"FII+DII {x:g}%"


def m_price_strength(i):
    x = i.num("pct_below_52w_high")
    return le(x, [(5, 2), (15, 1)]), f"{x:g}% below 52w high"


def m_volume(i):
    x = i.num("volume_ratio_10d_vs_50d")
    return ge(x, [(2, 2), (1.3, 1)]), f"10d/50d volume {x:.2f}x"


# ---- P2 Opportunity ----------------------------------------------------------
def m_theme(i):
    n = len(i.items("theme_evidence", THEME))
    return min(n, 5), f"{n} theme proofs"


def m_chain(i):
    v = i.choice("value_chain_position", CHAIN)
    return CHAIN[v], v


def m_players(i):
    x = i.num("players_in_niche")
    if x < 1:
        raise Invalid("players_in_niche counts the company itself, must be >= 1")
    return le(x, [(3, 5), (6, 3)]), f"{x:g} credible players incl. company"


def m_opportunity(i):
    opp, mcap = i.num("order_book_or_addressable_revenue_cr"), i.num("market_cap_cr")
    if mcap <= 0:
        raise Invalid("market_cap_cr must be > 0")
    r = opp / mcap
    return ge(r, [(3, 5), (1, 3), (0.5, 1)]), f"opportunity/mcap={r:.2f}x"


# ---- P3 Business model -------------------------------------------------------
def m_ccc(i):
    x = i.num("cash_conversion_cycle_days")
    return le(x, [(0, 4), (60, 3), (120, 1)]), f"cash conversion cycle {x:g} days"


def m_opm(i):
    x = i.num("opm_change_3y_pp")
    return ge(x, [(5, 3), (2, 2), (0, 1)]), f"OPM change {x:+g}pp (3y)"


def m_spare(i):
    x = i.num("spare_capacity_pct")
    return ge(x, [(30, 2), (15, 1)]), f"spare capacity {x:g}%"


def m_sales(i):
    x = i.num("sales_cagr_3y_pct")
    return ge(x, [(25, 3), (15, 2), (10, 1)]), f"sales CAGR {x:g}%"


def m_roce(i):
    x = i.num("roce_3y_avg_pct")
    return ge(x, [(25, 3), (15, 2), (10, 1)]), f"ROCE {x:g}%"


# ---- P4 Promoter -------------------------------------------------------------
def m_walk_the_talk(i):
    if i.get("guidance_hit_pct") == "none_stated":
        return 2, "no explicit targets stated"
    x = i.num("guidance_hit_pct")
    return ge(x, [(80, 6), (50, 3)]), f"{x:g}% of stated targets met"


def m_debt(i):
    x = i.num("debt_to_equity")
    return le(x, [(0.1, 4), (0.5, 2), (1, 1)]), f"debt/equity {x:.2f}"


def m_promoter(i):
    if i.get("promoter_holding_pct") == "professionally_managed":
        return 2, "professionally managed"
    ph, chg, pledge = i.num("promoter_holding_pct"), i.num("promoter_holding_change_3y_pp"), i.num("promoter_pledge_pct")
    note = f"holding {ph:g}%, 3y change {chg:+g}pp, pledge {pledge:g}%"
    if pledge > 0 or chg < -2:
        return 0, note
    if chg >= -0.5:
        return (5 if ph >= 50 else 3 if ph >= 35 else 2), note
    return 1, note


def m_stability(i):
    n = len(i.items("stability_checks", STABILITY))
    return n, f"{n}/4 stability checks"


def m_scuttlebutt(i):
    n = len(i.items("scuttlebutt_checks", SCUTTLEBUTT))
    return n, f"{n}/6 ground checks"


# ---- P5 Valuation ------------------------------------------------------------
def m_headroom(i):
    x = i.num("market_cap_cr")
    return le(x, [(500, 4), (2000, 3), (10000, 1)]), f"market cap {x:,.0f} cr"


def m_peg(i):
    pe, g = i.num("pe"), i.num("eps_cagr_3y_pct")
    if pe <= 0 or g <= 0:
        return 0, "PEG n/a (non-positive P/E or EPS growth)"
    # turnarounds from a tiny EPS base produce meaningless 100%+ CAGRs
    peg = pe / min(g, 50)
    return le(peg, [(0.8, 6), (1.2, 4), (2, 2)]), f"PEG={peg:.2f} (P/E {pe:g}, EPS CAGR {g:g}%, capped at 50)"


def m_history(i):
    x = i.num("multiple_percentile_vs_own_history")
    return le(x, [(25, 5), (50, 3), (75, 1)]), f"P/E at {x:g}th percentile of own 5y range"


# ---- P6 Durability -----------------------------------------------------------
def m_ai(i):
    v = i.choice("ai_exposure", AI_EXPOSURE)
    return AI_EXPOSURE[v], v


def m_durability(i):
    n = len(i.items("durability_checks", DURABILITY))
    return n, f"{n}/5 durability checks"


METRICS = [
    ("P1", "surprise_triggers", 7, m_triggers),
    ("P1", "institutional_neglect", 4, m_neglect),
    ("P1", "price_near_high", 2, m_price_strength),
    ("P1", "volume_confirmation", 2, m_volume),
    ("P2", "theme_evidence", 5, m_theme),
    ("P2", "value_chain_position", 5, m_chain),
    ("P2", "oligopoly", 5, m_players),
    ("P2", "opportunity_vs_mcap", 5, m_opportunity),
    ("P3", "working_capital", 4, m_ccc),
    ("P3", "margin_expansion", 3, m_opm),
    ("P3", "spare_capacity", 2, m_spare),
    ("P3", "sales_growth", 3, m_sales),
    ("P3", "roce", 3, m_roce),
    ("P4", "walk_the_talk", 6, m_walk_the_talk),
    ("P4", "debt_prudence", 4, m_debt),
    ("P4", "promoter_alignment", 5, m_promoter),
    ("P4", "stability", 4, m_stability),
    ("P4", "scuttlebutt", 6, m_scuttlebutt),
    ("P5", "size_headroom", 4, m_headroom),
    ("P5", "growth_adjusted_pe", 6, m_peg),
    ("P5", "pe_vs_own_history", 5, m_history),
    ("P6", "ai_exposure", 5, m_ai),
    ("P6", "durability", 5, m_durability),
]


# ---- Gates -------------------------------------------------------------------
def g_auditor(i):
    return not i.flag("auditor_red_flag_3y"), "auditor qualification/resignation with concerns (3y)"


def g_regulatory(i):
    return not i.flag("regulatory_action_against_promoters_or_kmp_3y"), "SEBI/ED/fraud action on promoters/KMP (3y)"


def g_related_party(i):
    return not i.flag("related_party_red_flag_3y"), "loans/advances to promoter entities or RPT > 10% of revenue (3y)"


def g_pledge(i):
    if i.get("promoter_holding_pct") == "professionally_managed":
        return True, "promoter pledge (n/a, professionally managed)"
    x = i.num("promoter_pledge_pct")
    return x <= 25, f"promoter pledge {x:g}% (fail if >25%)"


GATES = [g_auditor, g_regulatory, g_related_party, g_pledge]


def val(data, key):
    item = (data.get("inputs", {}).get(key) or {})
    return item.get("value") if str(item.get("source") or "").strip() else None


def exit_plan(data, certainty, flags):
    plan = []
    if certainty == "HIGH CERTAINTY":
        plan.append("Hold through volatility; do not sell on price alone (tax + re-entry cost exceed a typical dip).")
        plan.append("Sell only on thesis break: core model changes, targets met < 50% two years running, a gate fails, "
                    "or promoter holding falls > 2pp.")
    else:
        plan.append("Uncertain bucket: recover invested capital first, let the rest run.")
        plan.append("Trim into exceptional short-term gains ('ice cream melts').")
        plan.append("Raise cash from this bucket first when a pre-defined market-wide support level breaks.")
    if any(f.startswith("FALLING KNIFE") for f in flags):
        plan.append("Do NOT average down until re-scored with a diagnosis of the fall.")

    cost, price, months = val(data, "position_cost_price"), val(data, "current_price"), val(data, "holding_months")
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (cost, price)) and cost > 0:
        mult = price / cost
        plan.append(f"Position: {mult:.2f}x cost.")
        if certainty != "HIGH CERTAINTY":
            if mult >= 2:
                plan.append(f"ACTION: sell {100 / mult:.0f}% of the position to take out the original capital.")
            if mult >= 3 and isinstance(months, (int, float)) and months <= 24:
                plan.append("ACTION: >= 3x within 24 months - trim a further 25% of the remainder.")
    return plan


def run(data):
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

    pts = {r["metric"]: r["points"] for r in rows}
    pillars = {p: round(sum(r["points"] for r in rows if r["pillar"] == p), 1) for p in PILLARS}
    total = round(sum(pillars.values()), 1)
    coverage = sum(r["status"] == "ok" for r in rows) / len(rows)

    thesis = data.get("thesis_type")
    if thesis not in THESIS_TYPES:
        raise SystemExit(f"thesis_type must be one of {THESIS_TYPES}")
    high = (thesis == "compounder" and pillars["P4"] >= 18 and pillars["P3"] >= 9
            and pts["durability"] >= 3 and pts["debt_prudence"] >= 2)
    certainty = "HIGH CERTAINTY" if high else "UNCERTAIN"

    flags = []
    # a decade-old all-time high flagged Frontier 2018 / Suzlon 2023 before 10-40x runs; use the 52w high
    fall, dma = val(data, "pct_below_52w_high"), val(data, "price_vs_200dma_pct")
    if isinstance(fall, (int, float)) and isinstance(dma, (int, float)) and fall >= 40 and dma < 0:
        flags.append(f"FALLING KNIFE: {fall:g}% below 52w high and {dma:+g}% vs 200DMA")
    if pillars["P1"] >= 11 and pillars["P4"] < 12:
        flags.append("SURPRISE WITHOUT SUBSTANCE: strong trigger, weak promoter evidence")
    if pillars["P5"] <= 3 and pts["price_near_high"] == 2:
        flags.append("FANCY/HYPE RISK: at highs with little valuation support - size small, trim on spikes")
    mcap = val(data, "market_cap_cr")
    if isinstance(mcap, (int, float)) and mcap > 100000:
        flags.append("ELEPHANT: > 1 lakh cr market cap, slow to adapt to disruption, little surprise left")
    if val(data, "ai_exposure") == "labour_arbitrage_services":
        flags.append("AI SERVICES RISK: labour-arbitrage service model exposed to AI automation")

    statuses = {g["status"] for g in gates}
    if "FAIL" in statuses:
        verdict = "REJECT (gate failed)"
    elif coverage < 0.8:
        verdict = "INCOMPLETE - gather sourced evidence before deciding"
    elif total >= 75:
        verdict = "HIGH CONVICTION" if coverage == 1 and "unverified" not in statuses else "PROVISIONAL HIGH CONVICTION - close evidence gaps"
    elif total >= 60:
        verdict = "STARTER POSITION"
    elif total >= 45:
        verdict = "WATCHLIST"
    else:
        verdict = "PASS"

    return {
        "company": data.get("company"),
        "ticker": data.get("ticker"),
        "as_of": data.get("as_of"),
        "thesis_type": thesis,
        "gates": gates,
        "metrics": rows,
        "pillars": {p: {"name": PILLARS[p][0], "score": pillars[p], "max": PILLARS[p][1]} for p in PILLARS},
        "total": total,
        "evidence_coverage": round(coverage, 3),
        "verdict": verdict,
        "certainty": certainty,
        "flags": flags,
        "exit_plan": exit_plan(data, certainty, flags),
    }


def render(r):
    out = [f"{r['company']} ({r['ticker']})  as of {r['as_of']}  thesis={r['thesis_type']}", "", "GATES"]
    out += [f"  [{g['status']:<10}] {g['note']}" for g in r["gates"]]
    for p, meta in r["pillars"].items():
        out += ["", f"{p} {meta['name']}: {meta['score']:g}/{meta['max']}"]
        out += [
            f"  {m['metric']:<22} {m['points']:>4g}/{m['max']:<2} {m['status']:<9} {m['note']}"
            for m in r["metrics"]
            if m["pillar"] == p
        ]
    out += [
        "",
        f"TOTAL SCORE        {r['total']:g}/100",
        f"EVIDENCE COVERAGE  {r['evidence_coverage']:.0%}",
        f"VERDICT            {r['verdict']}",
        f"CERTAINTY          {r['certainty']}",
    ]
    out += [f"FLAG               {f}" for f in r["flags"]]
    out += ["", "EXIT PLAN"] + [f"  - {p}" for p in r["exit_plan"]]
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
