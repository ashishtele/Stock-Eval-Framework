#!/usr/bin/env python3
"""Deterministic scorer for the ABCD Change-Catalyst Score (ACS), stdlib only.

Usage: python score.py input.json [more.json ...] [--json]
Every input is {"value": ..., "source": "..."}; points are awarded only when both are present.
Later files override earlier ones (e.g. fetched.json analyst.json position.json).
"""
import argparse
import json
import sys

TAILWIND = {
    "govt_capex_or_budget_up_ge_15pct",
    "policy_or_regulatory_mandate",
    "indigenisation_or_import_substitution",
    "export_opportunity_documented",
    "demand_pulled_forward_or_supply_shortage",
    "structural_cost_shift",
    "sector_order_inflow_rising",
}
ENTRY_BARRIER = {
    "approval_or_vendor_registration_required",
    "long_qualification_or_trial_cycle",
    "players_in_niche_le_3",
    "only_or_one_of_two_listed_players",
    "proprietary_process_or_know_how",
    "dealer_or_channel_lock_in",
}
CUSTOMER = {
    "govt_or_psu_payer": 3,
    "large_rated_corporates": 2,
    "diversified_retail_or_dealers": 2,
    "weak_or_concentrated_private": 0,
}
CATALYSTS = {
    "policy_or_regulation_change",
    "next_generation_or_new_management",
    "new_technology_or_product",
    "new_market_or_export_entry",
    "strategic_acquirer_or_open_offer",
    "asset_monetisation_or_demerger",
    "large_order_win",
    "capacity_or_approval_unlock",
    "balance_sheet_repair",
}
CAPITAL_ALLOCATION = {
    "no_loans_icd_or_guarantees_to_promoter_entities_3y",
    "rpt_lt_5pct_of_revenue",
    "group_investments_lt_5pct_networth",
    "no_unrelated_diversification_5y",
    "equity_dilution_lt_10pct_3y",
}
TRANSPARENCY = {
    "responds_to_shareholder_queries",
    "discloses_order_book_or_execution_status",
    "concalls_or_investor_meets",
    "candid_no_hype",
}
REPUTATION = {
    "industry_or_customer_vouches_integrity",
    "technocrat_or_domain_expert_promoter",
    "no_adverse_media_or_litigation",
    "succession_plan_clear",
}
FOCUS = {"single_product_or_niche": 2, "focused_few_segments": 1, "diversified_conglomerate": 0}
GROUND = {
    "annual_reports_read_ge_3y": 1,
    "exchange_filings_reviewed": 1,
    "end_user_or_tradesman_feedback": 2,
    "dealer_or_channel_feedback": 1,
    "customer_or_inspector_feedback": 1,
    "value_chain_peer_confirms_thesis": 2,
    "factory_or_office_visit": 1,
    "management_meeting_or_agm": 1,
}
PILLARS = {
    "P1": ("Macro & Sector Tailwind", 15),
    "P2": ("Change Catalyst & Earnings Inflection", 20),
    "P3": ("Promoter Integrity & Capital Allocation", 25),
    "P4": ("Business Quality & Balance Sheet", 15),
    "P5": ("Valuation & Re-rating Room", 15),
    "P6": ("Ground Research & Network", 10),
}
CATEGORY_NOTE = {
    "A": "Large, well-tracked; no surprise element left. Outside this framework - avoid for fresh money.",
    "B": "Was small, now stable after 10-30y of promoter effort; moderate surprise. Hold/accumulate on value.",
    "C": "Old company that under-achieved, now changing (next gen, new tech/market, policy). Primary hunting ground.",
    "C-DORMANT": "Old under-achiever with no evidenced change yet. Watch only; wait for the catalyst.",
    "D": "Fallen glory / ahead-of-its-time / turnaround. High risk: whole D bucket <= 10% of portfolio.",
    "UNCLASSIFIED": "Missing inputs for ABCD classification (market cap, TTM PAT, drawdown, incorporation year, 10y sales CAGR).",
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

    def opt(self, fn, *args):
        try:
            return fn(*args)
        except (Missing, Unsourced, Invalid):
            return None


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


# ---- P1 Macro & sector tailwind ---------------------------------------------
def m_tailwind(i):
    n = len(i.items("tailwind_evidence", TAILWIND))
    return min(n, 6), f"{n} documented sector tailwinds"


def m_barrier(i):
    n = len(i.items("entry_barrier_checks", ENTRY_BARRIER))
    return n, f"{n}/6 entry-barrier checks"


def m_customer(i):
    v = i.choice("customer_credit_quality", CUSTOMER)
    return CUSTOMER[v], v


# ---- P2 Change catalyst & inflection ----------------------------------------
def m_catalysts(i):
    n = len(i.items("change_catalysts", CATALYSTS))
    return [0, 4, 6, 8][min(n, 3)], f"{n} dated change catalyst(s) in last 24 months"


def m_visibility(i):
    ob = i.opt(i.num, "order_book_to_ttm_sales")
    if ob is not None:
        return ge(ob, [(3, 5), (2, 4), (1, 2), (0.5, 1)]), f"order book {ob:.2f}x TTM sales"
    g = i.num("ttm_sales_growth_pct")
    return ge(g, [(40, 5), (25, 4), (15, 2), (10, 1)]), f"TTM sales growth {g:g}% (no order book input)"


def m_inflection(i):
    t = i.num("ttm_pat_growth_pct")
    c = i.opt(i.num, "pat_cagr_3y_pct")
    if t >= 25 and (c is None or t > c):
        pts = 4
    elif t >= 25:
        pts = 3
    elif t >= 10:
        pts = 2
    else:
        pts = 1 if t > 0 else 0
    return pts, f"TTM PAT growth {t:g}% vs 3y PAT CAGR {'n/a' if c is None else f'{c:g}%'}"


def m_technical(i):
    below, vol = i.num("pct_below_52w_high"), i.num("volume_ratio_10d_vs_50d")
    pts = le(below, [(5, 2), (15, 1)]) + (1 if vol >= 1.5 else 0)
    return pts, f"{below:g}% below 52w high, 10d/50d volume {vol:.2f}x"


# ---- P3 Promoter integrity & capital allocation -----------------------------
def m_capital_allocation(i):
    n = len(i.items("capital_allocation_checks", CAPITAL_ALLOCATION))
    return n, f"{n}/5 capital-allocation checks"


def m_cash_conversion(i):
    x = i.num("cfo_to_pat_3y")
    return ge(x, [(0.9, 3), (0.7, 2), (0.5, 1)]), f"CFO/PAT 3y {x:.2f}"


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


def m_transparency(i):
    n = len(i.items("transparency_checks", TRANSPARENCY))
    return n, f"{n}/4 transparency checks"


def m_walk_the_talk(i):
    if i.get("guidance_hit_pct") == "none_stated":
        return 1, "no explicit targets stated"
    x = i.num("guidance_hit_pct")
    return ge(x, [(80, 4), (50, 2)]), f"{x:g}% of stated targets met"


def m_reputation(i):
    n = len(i.items("reputation_checks", REPUTATION))
    return n, f"{n}/4 third-party reputation checks"


# ---- P4 Business quality & balance sheet ------------------------------------
def m_focus(i):
    v = i.choice("business_focus", FOCUS)
    return FOCUS[v], v


def m_sales(i):
    x = i.num("sales_cagr_3y_pct")
    return ge(x, [(20, 3), (12, 2), (8, 1)]), f"sales CAGR 3y {x:g}%"


def m_roce(i):
    x = i.num("roce_3y_avg_pct")
    return ge(x, [(20, 3), (15, 2), (10, 1)]), f"ROCE 3y avg {x:g}%"


def m_margin(i):
    x = i.num("opm_change_3y_pp")
    return ge(x, [(3, 3), (0, 2), (-3, 1)]), f"OPM change {x:+g}pp (3y)"


def m_balance_sheet(i):
    de = i.num("debt_to_equity")
    if de <= 0.3:
        return 4, f"debt/equity {de:.2f}"
    if i.opt(i.flag, "monetisable_assets_cover_debt"):
        return 3, f"debt/equity {de:.2f}, covered by monetisable non-core assets"
    return le(de, [(1, 2), (1.5, 1)]), f"debt/equity {de:.2f}"


# ---- P5 Valuation & re-rating room ------------------------------------------
def m_pe_level(i):
    pe = i.num("pe")
    if pe <= 0:
        return 0, f"P/E {pe:g} (loss-making)"
    return le(pe, [(10, 4), (15, 3), (20, 2), (30, 1)]), f"P/E {pe:g}"


def m_peg(i):
    pe, g = i.num("pe"), i.num("eps_cagr_3y_pct")
    if pe <= 0 or g <= 0:
        return 0, "PEG n/a (non-positive P/E or EPS growth)"
    # tiny-base turnarounds produce meaningless 100%+ CAGRs
    peg = pe / min(g, 50)
    return le(peg, [(0.8, 4), (1.2, 3), (2, 1)]), f"PEG {peg:.2f} (EPS CAGR {g:g}%, capped at 50)"


def m_pe_history(i):
    x = i.num("pe_percentile_5y")
    return le(x, [(25, 3), (50, 2), (75, 1)]), f"P/E at {x:g}th percentile of own 5y range"


def m_neglect(i):
    x = i.num("institutional_holding_pct")
    return le(x, [(5, 2), (10, 1)]), f"FII+DII {x:g}%"


def m_size(i):
    x = i.num("market_cap_cr")
    return le(x, [(1000, 2), (5000, 1)]), f"market cap {x:,.0f} cr"


# ---- P6 Ground research -----------------------------------------------------
def m_ground(i):
    got = i.items("ground_checks", GROUND)
    return sum(GROUND[g] for g in got), f"{len(got)}/8 ground checks ({', '.join(sorted(got)) or 'none'})"


METRICS = [
    ("P1", "tailwind_evidence", 6, m_tailwind),
    ("P1", "entry_barrier", 6, m_barrier),
    ("P1", "customer_credit_quality", 3, m_customer),
    ("P2", "change_catalysts", 8, m_catalysts),
    ("P2", "growth_visibility", 5, m_visibility),
    ("P2", "earnings_inflection", 4, m_inflection),
    ("P2", "technical_trigger", 3, m_technical),
    ("P3", "capital_allocation", 5, m_capital_allocation),
    ("P3", "cash_conversion", 3, m_cash_conversion),
    ("P3", "promoter_alignment", 5, m_promoter),
    ("P3", "transparency", 4, m_transparency),
    ("P3", "walk_the_talk", 4, m_walk_the_talk),
    ("P3", "reputation", 4, m_reputation),
    ("P4", "business_focus", 2, m_focus),
    ("P4", "sales_growth", 3, m_sales),
    ("P4", "roce", 3, m_roce),
    ("P4", "margin_trend", 3, m_margin),
    ("P4", "balance_sheet", 4, m_balance_sheet),
    ("P5", "pe_level", 4, m_pe_level),
    ("P5", "growth_adjusted_pe", 4, m_peg),
    ("P5", "pe_vs_history", 3, m_pe_history),
    ("P5", "institutional_neglect", 2, m_neglect),
    ("P5", "size_headroom", 2, m_size),
    ("P6", "ground_checks", 10, m_ground),
]


# ---- Gates -------------------------------------------------------------------
def g_auditor(i):
    return not i.flag("auditor_red_flag_3y"), "auditor qualification/resignation with concerns (3y)"


def g_regulatory(i):
    return not i.flag("regulatory_action_against_promoters_or_kmp_3y"), "SEBI/ED/fraud action on promoters/KMP (3y)"


def g_fund_diversion(i):
    return not i.flag("fund_diversion_red_flag_3y"), "ICDs/loans/advances/guarantees to promoter-group private entities (3y)"


def g_pledge(i):
    if i.get("promoter_holding_pct") == "professionally_managed":
        return True, "promoter pledge (n/a, professionally managed)"
    x = i.num("promoter_pledge_pct")
    return x <= 25, f"promoter pledge {x:g}% (fail if > 25%)"


GATES = [g_auditor, g_regulatory, g_fund_diversion, g_pledge]


def classify(i, as_of):
    mcap, pat, dd = i.opt(i.num, "market_cap_cr"), i.opt(i.num, "ttm_pat_cr"), i.opt(i.num, "drawdown_from_high_pct")
    year, s10 = i.opt(i.num, "incorporation_year"), i.opt(i.num, "sales_cagr_10y_pct")
    cats = i.opt(i.items, "change_catalysts", CATALYSTS) or set()
    if (pat is not None and pat <= 0) or (dd is not None and dd >= 70):
        why = f"TTM PAT {pat:g} cr" if pat is not None and pat <= 0 else f"{dd:g}% below all-time high"
        return "D", why
    if mcap is None:
        return "UNCLASSIFIED", "market_cap_cr missing"
    if mcap >= 20000:
        return "A", f"market cap {mcap:,.0f} cr >= 20,000"
    if year is None or not as_of:
        return "UNCLASSIFIED", "incorporation_year missing"
    age = int(str(as_of)[:4]) - int(year)
    if age < 15:
        return "B", f"{age}y old (too young for C)"
    if s10 is None:
        return "UNCLASSIFIED", f"{age}y old but sales_cagr_10y_pct missing (needs >= 7 years of P&L)"
    if s10 < 12:
        if cats:
            return "C", f"{age}y old, 10y sales CAGR {s10:g}% < 12%, change: {', '.join(sorted(cats))}"
        return "C-DORMANT", f"{age}y old, 10y sales CAGR {s10:g}% < 12%, no change catalyst evidenced"
    return "B", f"{age}y old, 10y sales CAGR {s10:g}%"


def val(data, key):
    item = (data.get("inputs", {}).get(key) or {})
    return item.get("value") if str(item.get("source") or "").strip() else None


def isnum(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def action_plan(data, category, pts, broken):
    plan = []
    if broken:
        plan.append("EXIT: a written thesis assumption is broken. Exit regardless of profit or loss - "
                    "the market does not care about your buy price.")
    plan.append("Exit fully on any integrity breach (fund diversion, misleading disclosure); "
                "accept failures caused by the external environment, never those caused by the promoter.")
    if category == "D":
        plan.append("D bucket: keep total D exposure <= 10% of portfolio; once the turnaround re-rates "
                    "to a level where uncertainty is still high, convert gains to cash.")
    if category == "C" and isnum(val(data, "pe_percentile_5y")) and val(data, "pe_percentile_5y") > 75:
        plan.append("C -> B migration: re-rated to the top quartile of its own P/E range; book part profits.")
    if category == "A":
        plan.append("Category A: no fresh money under this framework.")
    plan.append("Add only as the catalyst is confirmed (order executed, results delivered) - average up, not down.")

    cost, price = val(data, "position_cost_price"), val(data, "current_price")
    if isnum(cost) and isnum(price) and cost > 0:
        mult = price / cost
        plan.append(f"Position: {mult:.2f}x cost.")
        if mult >= 2:
            plan.append(f"ACTION: sell {100 / mult:.0f}% to take the original capital out; let the rest run.")
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
            p, note = fn(i)
            status = "ok"
        except Missing as e:
            p, status, note = 0, "missing", f"needs '{e}'"
        except Unsourced as e:
            p, status, note = 0, "unsourced", f"'{e}' has no source"
        except Invalid as e:
            p, status, note = 0, "invalid", str(e)
        rows.append({"pillar": pillar, "metric": name, "points": min(p, mx), "max": mx, "status": status, "note": note})

    pts = {r["metric"]: r["points"] for r in rows}
    pillars = {p: sum(r["points"] for r in rows if r["pillar"] == p) for p in PILLARS}
    total = sum(pillars.values())
    coverage = sum(r["status"] == "ok" for r in rows) / len(rows)
    category, why = classify(i, data.get("as_of"))
    broken = i.opt(i.flag, "thesis_assumption_broken") is True

    flags = []
    if pts["change_catalysts"] == 0:
        flags.append("NO CHANGE YET: price needs change (policy, management, technology, market) - wait for it")
    if pts["transparency"] + pts["reputation"] < 3:
        flags.append("INTEGRITY UNPROVEN: fewer than 3 transparency/reputation checks - meet or call management first")
    if pts["capital_allocation"] <= 2:
        flags.append("CAPITAL ALLOCATION RISK: read related-party note, ICDs and group investments before buying")
    inst = val(data, "institutional_holding_pct")
    if isnum(inst) and inst > 25:
        flags.append(f"CROWDED: FII+DII {inst:g}% - big players already present, little surprise left")
    if pts["pe_level"] == 0 and pts["pe_vs_history"] == 0:
        flags.append("PRICED FOR PERFECTION: high P/E and top of own range - earnings must carry all the return")

    statuses = {g["status"] for g in gates}
    if broken:
        verdict = "EXIT / AVOID (thesis assumption broken)"
    elif "FAIL" in statuses:
        verdict = "REJECT (gate failed)"
    elif category == "A":
        verdict = "AVOID - Category A (no surprise element left)"
    elif coverage < 0.8:
        verdict = "INCOMPLETE - gather sourced evidence before deciding"
    elif total >= 75:
        verdict = ("HIGH CONVICTION" if coverage == 1 and "unverified" not in statuses
                   else "PROVISIONAL HIGH CONVICTION - close evidence gaps")
    elif total >= 60:
        verdict = "STARTER POSITION"
    elif total >= 45:
        verdict = "WATCHLIST"
    else:
        verdict = "PASS"
    if category == "C-DORMANT" and verdict.startswith(("HIGH", "PROVISIONAL", "STARTER")):
        verdict = "WATCHLIST (C-dormant: score qualifies but no change catalyst yet)"

    return {
        "company": data.get("company"),
        "ticker": data.get("ticker"),
        "as_of": data.get("as_of"),
        "category": category,
        "category_reason": why,
        "category_note": CATEGORY_NOTE[category],
        "gates": gates,
        "metrics": rows,
        "pillars": {p: {"name": PILLARS[p][0], "score": pillars[p], "max": PILLARS[p][1]} for p in PILLARS},
        "total": total,
        "evidence_coverage": round(coverage, 3),
        "verdict": verdict,
        "flags": flags,
        "action_plan": action_plan(data, category, pts, broken),
    }


def render(r):
    out = [f"{r['company']} ({r['ticker']})  as of {r['as_of']}", "",
           f"ABCD CATEGORY      {r['category']}  ({r['category_reason']})", f"                   {r['category_note']}",
           "", "GATES"]
    out += [f"  [{g['status']:<10}] {g['note']}" for g in r["gates"]]
    for p, meta in r["pillars"].items():
        out += ["", f"{p} {meta['name']}: {meta['score']:g}/{meta['max']}"]
        out += [f"  {m['metric']:<24} {m['points']:>3g}/{m['max']:<2} {m['status']:<9} {m['note']}"
                for m in r["metrics"] if m["pillar"] == p]
    out += ["",
            f"TOTAL SCORE        {r['total']:g}/100",
            f"EVIDENCE COVERAGE  {r['evidence_coverage']:.0%}",
            f"VERDICT            {r['verdict']}"]
    out += [f"FLAG               {f}" for f in r["flags"]]
    out += ["", "ACTION PLAN"] + [f"  - {p}" for p in r["action_plan"]]
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
        data.update({k: v for k, v in part.items() if v not in (None, "") and not k.startswith("_")})
    result = run(data)
    print(json.dumps(result, indent=2) if args.json else render(result))


if __name__ == "__main__":
    sys.exit(main())
