#!/usr/bin/env python3
"""
Capital-Efficiency-at-a-Price (CEP) scorer.

Deterministic, rule-by-rule 0-100 score built from the investing framework
Kenneth Andrade (Old Bridge Capital) describes: buy capital efficiency at a
price, compare earnings yield with the bond yield, own the debt-free,
cash-generating market leader that is gaining share in an industry whose
profitability is stagnant or falling, and sell when the industry gets hot.

Usage:
    python score.py input.json                 # markdown report to stdout
    python score.py input.json --out report.md --json result.json

input.json may hold one company (object) or several (list). With several, a
ranking table is printed first. See assets/input_template.json.

Every rule prints: formula, inputs used, computed value, threshold band, points.
Missing inputs score 0 and are flagged, never guessed.
"""
import json
import sys
import argparse
import statistics

WINDOW = 5  # years used for "through-cycle" averages


# ----------------------------------------------------------------- helpers
def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def last_n(xs, n=WINDOW):
    """Last n values of a series, or None if series missing/short/has gaps."""
    if not isinstance(xs, list) or len(xs) == 0:
        return None
    tail = xs[-n:] if len(xs) >= n else xs[:]
    if any(not num(v) for v in tail):
        return None
    return tail


def latest(xs):
    if isinstance(xs, list) and xs and num(xs[-1]):
        return xs[-1]
    if num(xs):
        return xs
    return None


def cagr(first, last, years):
    if not (num(first) and num(last)) or first <= 0 or last <= 0 or years <= 0:
        return None
    return ((last / first) ** (1.0 / years) - 1) * 100


def band(value, bands, default=0.0):
    """bands: list of (predicate, points, label). First match wins."""
    for pred, pts, label in bands:
        if pred(value):
            return pts, label
    return default, "below lowest band"


def r2(x):
    return None if x is None else round(x, 2)


class Rule:
    def __init__(self, rid, pillar, name, max_pts, formula):
        self.rid, self.pillar, self.name = rid, pillar, name
        self.max, self.formula = max_pts, formula
        self.inputs, self.value, self.points = {}, None, 0.0
        self.status, self.note, self.band = "OK", "", ""

    def missing(self, what):
        self.status, self.points = "MISSING", 0.0
        self.note = f"missing/invalid input: {what}"
        return self

    def to_dict(self):
        return dict(id=self.rid, pillar=self.pillar, name=self.name,
                    max=self.max, points=self.points, status=self.status,
                    formula=self.formula, inputs=self.inputs,
                    value=self.value, band=self.band, note=self.note)


# ----------------------------------------------------- shared calculations
def market_share_series(company_rev, ind):
    ms = ind.get("market_share_pct")
    if last_n(ms, 2):
        return last_n(ms, WINDOW) or last_n(ms, len(ms))
    ir = ind.get("industry_revenue")
    if isinstance(ir, list) and isinstance(company_rev, list):
        n = min(len(ir), len(company_rev), WINDOW)
        a, b = last_n(company_rev, n), last_n(ir, n)
        if a and b and all(v > 0 for v in b):
            return [x / y * 100 for x, y in zip(a, b)]
    return None


def industry_phase(ind):
    roe = ind.get("industry_roe_pct")
    s = roe if isinstance(roe, list) and roe and all(num(v) for v in roe) else None
    if not s or len(s) < 3:
        return None
    avg = statistics.mean(s)
    return dict(latest=s[-1], avg=avg, diff=s[-1] - avg, n=len(s))


# ----------------------------------------------------- non-financial model
def score_non_financial(c):
    h = c.get("hurdle_yield_pct")
    mcap = c.get("market_cap")
    f = c.get("financials", {}) or {}
    ind = c.get("industry_data", {}) or {}
    rules = []

    pat_l = latest(f.get("pat"))
    ey = (pat_l / mcap * 100) if num(pat_l) and num(mcap) and mcap > 0 else None
    pe = (mcap / pat_l) if num(pat_l) and pat_l > 0 and num(mcap) else None

    # ---- Pillar A: PRICE (25)
    r = Rule("A1", "A. Price", "Earnings yield vs hurdle (bond) yield", 10,
             "EY = latest PAT / market cap; ratio = EY / hurdle")
    if ey is None or not num(h) or h <= 0:
        r.missing("pat, market_cap, hurdle_yield_pct")
    else:
        ratio = ey / h
        r.inputs = dict(pat=pat_l, market_cap=mcap, hurdle_pct=h, pe=r2(pe))
        r.value = dict(ey_pct=r2(ey), ratio=r2(ratio))
        r.points, r.band = band(ratio, [
            (lambda x: x >= 1.0, 10, "EY >= hurdle"),
            (lambda x: x >= 0.75, 7.5, "EY >= 0.75x hurdle"),
            (lambda x: x >= 0.5, 5, "EY >= 0.5x hurdle"),
            (lambda x: x >= 0.33, 2.5, "EY >= 0.33x hurdle")])
    rules.append(r)

    r = Rule("A2", "A. Price", "Free-cash-flow yield vs hurdle", 8,
             "FCF yield = avg(OCF - capex, last 3y) / market cap; ratio = FCF yield / hurdle")
    ocf3, cap3 = last_n(f.get("ocf"), 3), last_n(f.get("capex"), 3)
    if not (ocf3 and cap3 and num(mcap) and mcap > 0 and num(h) and h > 0):
        r.missing("ocf, capex (3y), market_cap, hurdle")
    else:
        fcf = statistics.mean([o - abs(k) for o, k in zip(ocf3, cap3)])
        fy = fcf / mcap * 100
        r.inputs = dict(ocf_3y=ocf3, capex_3y=cap3, market_cap=mcap)
        r.value = dict(avg_fcf=r2(fcf), fcf_yield_pct=r2(fy), ratio=r2(fy / h),
                       payback_years=r2(mcap / fcf) if fcf > 0 else None)
        r.points, r.band = band(fy / h, [
            (lambda x: x >= 1.0, 8, "FCF yield >= hurdle"),
            (lambda x: x >= 0.75, 6, ">= 0.75x hurdle"),
            (lambda x: x >= 0.5, 4, ">= 0.5x hurdle"),
            (lambda x: x >= 0.25, 2, ">= 0.25x hurdle"),
            (lambda x: x > 0, 1, "positive")])
    rules.append(r)

    r = Rule("A3", "A. Price", "Earnings yield + growth vs hurdle", 7,
             "only if EY >= 0.5x hurdle; g = revenue CAGR (5y) clipped to [0,10]; compare EY + g with hurdle")
    rev = last_n(f.get("revenue"), WINDOW + 1)
    g = cagr(rev[0], rev[-1], len(rev) - 1) if rev and len(rev) >= 3 else None
    if ey is None or g is None or not num(h):
        r.missing("pat, market_cap, revenue (>=3y), hurdle")
    elif ey < 0.5 * h:
        r.inputs = dict(ey_pct=r2(ey), hurdle_pct=h)
        r.value = dict(ey_to_hurdle=r2(ey / h))
        r.band = "EY < 0.5x hurdle: growth cannot rescue the price"
    else:
        gc = max(0.0, min(10.0, g))
        tot = ey + gc
        r.inputs = dict(ey_pct=r2(ey), revenue_cagr_pct=r2(g), hurdle_pct=h)
        r.value = dict(g_used=r2(gc), ey_plus_g=r2(tot), excess_over_hurdle=r2(tot - h))
        r.points, r.band = band(tot - h, [
            (lambda x: x >= 6, 7, "EY+g >= hurdle + 6pp"),
            (lambda x: x >= 3, 5, "EY+g >= hurdle + 3pp"),
            (lambda x: x >= 0, 3, "EY+g >= hurdle")])
    rules.append(r)

    # ---- Pillar B: CAPITAL EFFICIENCY (15)
    r = Rule("B1", "B. Capital efficiency", "Through-cycle ROCE (5y avg)", 8,
             "ROCE_t = EBIT_t / (equity_t + borrowings_t); average of last 5y")
    eb, eq, bo = last_n(f.get("ebit")), last_n(f.get("equity")), last_n(f.get("borrowings"))
    if not (eb and eq and bo) or len({len(eb), len(eq), len(bo)}) != 1:
        r.missing("ebit, equity, borrowings (aligned)")
        roce = None
    else:
        roce = [e / (q + b) * 100 for e, q, b in zip(eb, eq, bo) if (q + b) > 0]
        avg = statistics.mean(roce)
        r.inputs = dict(ebit=eb, equity=eq, borrowings=bo)
        r.value = dict(roce_series=[r2(x) for x in roce], avg_roce_pct=r2(avg))
        r.points, r.band = band(avg, [
            (lambda x: x >= 25, 8, ">= 25%"), (lambda x: x >= 18, 6, ">= 18%"),
            (lambda x: x >= 14, 4, ">= 14%"), (lambda x: x >= 10, 2, ">= 10%")])
    rules.append(r)

    r = Rule("B2", "B. Capital efficiency", "Cash conversion (cum OCF / cum PAT, 5y)", 7,
             "sum(OCF) / sum(PAT) over last 5y")
    ocf5, pat5 = last_n(f.get("ocf")), last_n(f.get("pat"))
    if not (ocf5 and pat5):
        r.missing("ocf, pat (5y)")
    else:
        sp, so = sum(pat5), sum(ocf5)
        r.inputs = dict(sum_ocf=r2(so), sum_pat=r2(sp))
        if sp <= 0:
            r.value, r.note = None, "cumulative PAT <= 0"
        else:
            cc = so / sp
            r.value = dict(conversion=r2(cc))
            r.points, r.band = band(cc, [
                (lambda x: x >= 1.0, 7, ">= 1.0"), (lambda x: x >= 0.85, 5, ">= 0.85"),
                (lambda x: x >= 0.7, 3, ">= 0.7"), (lambda x: x >= 0.5, 1, ">= 0.5")])
    rules.append(r)

    # ---- Pillar C: BALANCE SHEET & SELF-FUNDING (20)
    bor_l, cash_l, eq_l = latest(f.get("borrowings")), latest(f.get("cash_and_investments")), latest(f.get("equity"))
    nd = (bor_l - cash_l) if num(bor_l) and num(cash_l) else None
    r = Rule("C1", "C. Balance sheet", "Net debt / equity (latest)", 8,
             "(borrowings - cash & investments) / equity")
    if nd is None or not num(eq_l) or eq_l <= 0:
        r.missing("borrowings, cash_and_investments, equity")
        nde = None
    else:
        nde = nd / eq_l
        r.inputs = dict(borrowings=bor_l, cash=cash_l, equity=eq_l)
        r.value = dict(net_debt=r2(nd), net_debt_to_equity=r2(nde))
        r.points, r.band = band(nde, [
            (lambda x: x <= 0, 8, "net cash"), (lambda x: x <= 0.25, 5, "<= 0.25"),
            (lambda x: x <= 0.5, 2, "<= 0.5")])
    rules.append(r)

    r = Rule("C2", "C. Balance sheet", "Capex funded internally (cum capex / cum OCF, 5y)", 5,
             "sum(|capex|) / sum(OCF) over last 5y")
    cap5 = last_n(f.get("capex"))
    if not (ocf5 and cap5):
        r.missing("ocf, capex (5y)")
    else:
        so, sc = sum(ocf5), sum(abs(x) for x in cap5)
        r.inputs = dict(sum_capex=r2(sc), sum_ocf=r2(so))
        if so <= 0:
            r.note = "cumulative OCF <= 0: capex externally funded"
        else:
            rt = sc / so
            r.value = dict(capex_to_ocf=r2(rt))
            r.points, r.band = band(rt, [
                (lambda x: x <= 0.6, 5, "<= 0.6"), (lambda x: x <= 0.8, 4, "<= 0.8"),
                (lambda x: x <= 1.0, 2, "<= 1.0")])
    rules.append(r)

    r = Rule("C3", "C. Balance sheet", "Years of positive FCF (last 5)", 4,
             "count(OCF_t - |capex_t| > 0) over last 5y")
    if not (ocf5 and cap5) or len(ocf5) != len(cap5):
        r.missing("ocf, capex (5y)")
    else:
        cnt = sum(1 for o, k in zip(ocf5, cap5) if o - abs(k) > 0)
        r.value = dict(positive_years=cnt, of=len(ocf5))
        r.points = {5: 4, 4: 3, 3: 2, 2: 1}.get(cnt, 0)
        r.band = f"{cnt}/{len(ocf5)} years"
    rules.append(r)

    r = Rule("C4", "C. Balance sheet", "No equity dilution", 3,
             "(shares_latest / shares_first - 1) over the series")
    sh = f.get("shares_outstanding")
    shs = last_n(sh, len(sh)) if isinstance(sh, list) and len(sh) >= 2 else None
    if not shs or shs[0] <= 0:
        r.missing("shares_outstanding (>=2 points)")
    else:
        d = (shs[-1] / shs[0] - 1) * 100
        r.value = dict(share_change_pct=r2(d))
        r.points, r.band = band(d, [(lambda x: x <= 2, 3, "<= 2%"), (lambda x: x <= 10, 1.5, "<= 10%")])
    rules.append(r)

    # ---- Pillar D: DOMINANCE & PRICING POWER (25)
    r = Rule("D1", "D. Dominance", "Industry rank (by revenue)", 8, "1 = largest player")
    rank = ind.get("rank_by_revenue")
    if not num(rank):
        r.missing("industry_data.rank_by_revenue")
    else:
        r.value = dict(rank=rank)
        r.points = {1: 8, 2: 5, 3: 3}.get(int(rank), 0)
        r.band = f"rank {int(rank)}"
    rules.append(r)

    share = market_share_series(f.get("revenue"), ind)
    r = Rule("D2", "D. Dominance", "Incremental market share", 8,
             "relative change = share_latest / share_first - 1 (window <= 5y); 0 if share fell in each of the last 2 years")
    share_gain, share_recent_decline = None, False
    if not share or len(share) < 2 or share[0] <= 0:
        r.missing("market_share_pct or industry_revenue")
    else:
        share_gain = (share[-1] / share[0] - 1) * 100
        share_recent_decline = len(share) >= 3 and share[-1] < share[-2] < share[-3]
        r.value = dict(share_series=[r2(x) for x in share], relative_gain_pct=r2(share_gain),
                       fell_last_2y=share_recent_decline)
        if share_recent_decline:
            r.band = "losing share in each of the last 2 years (not incremental)"
        else:
            r.points, r.band = band(share_gain, [
                (lambda x: x >= 15, 8, ">= +15% relative"), (lambda x: x >= 5, 6, ">= +5%"),
                (lambda x: x >= 0, 3, "held share")])
    rules.append(r)

    rv5, ebd5 = last_n(f.get("revenue")), last_n(f.get("ebitda"))
    margins = [e / v * 100 for e, v in zip(ebd5, rv5) if v > 0] if rv5 and ebd5 and len(rv5) == len(ebd5) else None
    r = Rule("D3", "D. Dominance", "Pricing power: EBITDA margin premium vs industry", 5,
             "avg company EBITDA margin - avg industry EBITDA margin (5y)")
    im = last_n(ind.get("industry_ebitda_margin_pct"))
    if not margins or not im:
        r.missing("revenue, ebitda, industry_ebitda_margin_pct")
    else:
        prem = statistics.mean(margins) - statistics.mean(im)
        r.value = dict(company_avg_margin=r2(statistics.mean(margins)),
                       industry_avg_margin=r2(statistics.mean(im)), premium_pp=r2(prem))
        r.points, r.band = band(prem, [
            (lambda x: x >= 5, 5, ">= +5pp"), (lambda x: x >= 2, 3.5, ">= +2pp"),
            (lambda x: x >= 0, 2, ">= 0pp")])
    rules.append(r)

    r = Rule("D4", "D. Dominance", "Pricing power: margin resilience", 4,
             "min EBITDA margin / avg EBITDA margin (5y)")
    if not margins:
        r.missing("revenue, ebitda (5y)")
    else:
        avgm = statistics.mean(margins)
        res = min(margins) / avgm if avgm > 0 else 0
        r.value = dict(margins=[r2(x) for x in margins], resilience=r2(res))
        r.points, r.band = band(res, [
            (lambda x: x >= 0.85, 4, ">= 0.85"), (lambda x: x >= 0.7, 2.5, ">= 0.7"),
            (lambda x: x >= 0.5, 1, ">= 0.5")])
    rules.append(r)

    # ---- Pillar E: CYCLE & CONTRARIAN (15)
    ph = industry_phase(ind)
    r = Rule("E1", "E. Cycle", "Industry profitability is stagnant/falling (not hot)", 5,
             "industry ROE latest vs its own average (>=3 points); hot if latest >= 25%")
    if not ph:
        r.missing("industry_data.industry_roe_pct (>=3 points)")
    else:
        r.value = dict(latest=r2(ph["latest"]), avg=r2(ph["avg"]), diff_pp=r2(ph["diff"]))
        if ph["latest"] >= 25:
            r.points, r.band = 0, "hot: industry ROE >= 25% attracts new capacity"
        else:
            r.points, r.band = band(ph["diff"], [
                (lambda x: x <= 0, 5, "at/below own average"),
                (lambda x: x <= 3, 2.5, "<= 3pp above average")])
    rules.append(r)

    r = Rule("E2", "E. Cycle", "Consolidator in a weak industry", 4,
             "4 if share rising AND industry ROE <= its avg; 2 if only share rising")
    if share_gain is None:
        r.missing("market share data")
    else:
        rising = share_gain > 0 and not share_recent_decline
        weak = ph is not None and ph["diff"] <= 0
        r.value = dict(share_rising=rising, industry_weak=weak if ph else None)
        if rising and weak:
            r.points, r.band = 4, "gaining share while industry profitability is weak"
        elif rising:
            r.points, r.band = 2, "gaining share (industry not weak or unknown)"
            if ph is None:
                r.note = "industry ROE missing: partial credit only"
        else:
            r.band = "not gaining share"
    rules.append(r)

    r = Rule("E3", "E. Cycle", "Not priced as consensus: P/E vs own 10y median", 3,
             "current P/E / 10y median P/E; only if EY >= 0.5x hurdle (absolute price first)")
    pem = c.get("pe_10y_median")
    abs_ok = ey is not None and num(h) and ey >= 0.5 * h
    if pe is None or not num(pem) or pem <= 0:
        r.missing("pe_10y_median (and positive PAT)")
    elif not abs_ok:
        r.inputs = dict(pe=r2(pe), pe_10y_median=pem)
        r.value = dict(ratio=r2(pe / pem))
        r.band = "EY < 0.5x hurdle: cheap vs own history is not cheap"
    else:
        rt = pe / pem
        r.inputs = dict(pe=r2(pe), pe_10y_median=pem)
        r.value = dict(ratio=r2(rt))
        r.points, r.band = band(rt, [
            (lambda x: x <= 0.8, 3, "<= 0.8x median"), (lambda x: x <= 1.0, 2, "<= median"),
            (lambda x: x <= 1.25, 1, "<= 1.25x median")])
    rules.append(r)

    r = Rule("E4", "E. Cycle", "Price has not outrun earnings", 3,
             "market-cap CAGR - PAT CAGR over lookback years; only if EY >= 0.5x hurdle")
    lb = int(c.get("price_lookback_years") or WINDOW)
    mc0 = c.get("market_cap_n_years_ago")
    pats = f.get("pat") if isinstance(f.get("pat"), list) else []
    p0 = pats[-1 - lb] if len(pats) > lb else None
    mc_g, pat_g = cagr(mc0, mcap, lb), cagr(p0, pat_l, lb)
    if mc_g is None or pat_g is None:
        r.missing("market_cap_n_years_ago, PAT lookback years ago (both > 0)")
    else:
        gap = mc_g - pat_g
        r.inputs = dict(lookback_years=lb, mcap_then=mc0, mcap_now=mcap, pat_then=p0, pat_now=pat_l)
        r.value = dict(mcap_cagr=r2(mc_g), pat_cagr=r2(pat_g), gap_pp=r2(gap))
        if not abs_ok:
            r.band = "EY < 0.5x hurdle: de-rating from a higher multiple is still not cheap"
        else:
            r.points, r.band = band(gap, [
            (lambda x: x <= 0, 3, "earnings grew faster than price"),
            (lambda x: x <= 5, 2, "<= 5pp"), (lambda x: x <= 10, 1, "<= 10pp")])
    rules.append(r)

    # ---- Gates
    gates = []
    ebitda_l = latest(f.get("ebitda"))
    if (num(pat_l) and pat_l <= 0) or (ocf5 and sum(ocf5) <= 0):
        gates.append(("G1", "No cash flows: latest PAT <= 0 or 5y cum OCF <= 0 -> wait for the second cycle", 30))
    if nd is not None and num(ebitda_l) and ebitda_l > 0 and nd / ebitda_l > 3:
        gates.append(("G2", f"Leverage: net debt/EBITDA = {nd / ebitda_l:.2f} > 3 (debt kills in a down-cycle)", 40))
    if nd is not None and num(ebitda_l) and ebitda_l <= 0 and nd > 0:
        gates.append(("G2", "Leverage: net debt with non-positive EBITDA", 40))
    if ey is not None and num(h) and ey < h / 3:
        gates.append(("G3", f"Overpaying: EY {ey:.2f}% < hurdle/3 ({h / 3:.2f}%, P/E > {3 / h * 100:.0f}x) - buying too much future", 40))
    elif ey is not None and num(h) and ey < h / 2:
        gates.append(("G3", f"Rich price: EY {ey:.2f}% < hurdle/2 ({h / 2:.2f}%, P/E > {2 / h * 100:.0f}x) - not a core buy at this price", 60))
    hot = []
    if ph and ph["latest"] >= 30:
        hot.append("industry ROE >= 30%")
    if ind.get("new_large_entrant") is True:
        hot.append("new large entrant")
    if ind.get("industry_capacity_addition_high") is True:
        hot.append("heavy industry capacity addition")
    if hot:
        gates.append(("G4", "Hot industry / oversupply risk: " + ", ".join(hot), 60))

    # ---- Sell triggers
    sells = []
    if ph and ph["latest"] >= 25 and ph["diff"] > 0:
        sells.append("S1 industry ROE >= 25% and above its average (capital will flood in)")
    if ind.get("new_large_entrant") is True:
        sells.append("S2 a large new entrant has announced entry")
    if margins and len(margins) >= 3 and margins[-1] < statistics.mean(margins) - 3:
        sells.append("S3 EBITDA margin > 3pp below 5y avg (pricing power slipping)")
    if share and len(share) >= 3 and share[-1] < share[-2] < share[-3]:
        sells.append("S4 market share fell two years running")
    if (pe is not None and num(pem) and pem > 0 and pe >= 2 * pem) or (ey is not None and num(h) and ey < h / 3):
        sells.append("S5 price ran ahead: P/E >= 2x own median or EY < hurdle/3")
    if nde is not None and nde > 0.5:
        sells.append("S6 net debt/equity > 0.5 (balance sheet drifting)")
    if ind.get("industry_capacity_addition_high") is True:
        sells.append("S7 heavy industry capacity addition (oversupply ahead)")
    return rules, gates, sells, dict(pe=r2(pe), ey_pct=r2(ey))


# ---------------------------------------------------------- lender model
def score_lender(c):
    h = c.get("hurdle_yield_pct")
    mcap = c.get("market_cap")
    L = c.get("lender", {}) or {}
    ind = c.get("industry_data", {}) or {}
    rules = []
    pat_l, nw_l = latest(L.get("pat")), latest(L.get("net_worth"))
    ey = (pat_l / mcap * 100) if num(pat_l) and num(mcap) and mcap > 0 else None
    pb = (mcap / nw_l) if num(mcap) and num(nw_l) and nw_l > 0 else None
    pat5, nw5 = last_n(L.get("pat")), last_n(L.get("net_worth"))
    roe = [p / n * 100 for p, n in zip(pat5, nw5) if n > 0] if pat5 and nw5 and len(pat5) == len(nw5) else None

    r = Rule("LA1", "A. Price", "Earnings yield vs hurdle", 12, "latest PAT / market cap vs hurdle")
    if ey is None or not num(h) or h <= 0:
        r.missing("pat, market_cap, hurdle")
    else:
        r.value = dict(ey_pct=r2(ey), ratio=r2(ey / h))
        r.points, r.band = band(ey / h, [
            (lambda x: x >= 1.0, 12, ">= hurdle"), (lambda x: x >= 0.75, 9, ">= 0.75x"),
            (lambda x: x >= 0.5, 6, ">= 0.5x"), (lambda x: x >= 0.33, 3, ">= 0.33x")])
    rules.append(r)

    r = Rule("LA2", "A. Price", "Absolute P/B (margin of safety on a no-FCF business)", 8, "market cap / net worth")
    if pb is None:
        r.missing("net_worth, market_cap")
    else:
        r.value = dict(pb=r2(pb))
        r.points, r.band = band(pb, [
            (lambda x: x <= 1.0, 8, "<= 1.0x"), (lambda x: x <= 1.3, 6, "<= 1.3x"),
            (lambda x: x <= 2.0, 3, "<= 2.0x"), (lambda x: x <= 3.0, 1, "<= 3.0x")])
    rules.append(r)

    r = Rule("LA3", "A. Price", "P/B vs justified P/B", 10,
             "justified P/B = (ROE5 - g) / (COE - g); ratio = P/B / justified")
    coe = c.get("cost_of_equity_pct") or (h + 5.5 if num(h) else None)
    g = c.get("long_term_growth_pct", 8)
    if pb is None or not roe or not num(coe) or not num(g) or coe <= g:
        r.missing("P/B, ROE series, cost_of_equity_pct > long_term_growth_pct")
    else:
        jpb = (statistics.mean(roe) - g) / (coe - g)
        r.inputs = dict(roe5=r2(statistics.mean(roe)), coe=coe, g=g)
        if jpb <= 0:
            r.value, r.note = dict(justified_pb=r2(jpb)), "ROE below growth: no justified premium"
        else:
            rt = pb / jpb
            r.value = dict(justified_pb=r2(jpb), ratio=r2(rt))
            r.points, r.band = band(rt, [
                (lambda x: x <= 0.8, 10, "<= 0.8x justified"), (lambda x: x <= 1.0, 7, "<= 1.0x"),
                (lambda x: x <= 1.3, 3, "<= 1.3x")])
    rules.append(r)

    r = Rule("LB1", "B. Capital efficiency", "ROE 5y avg", 8, "PAT / net worth (year-end), avg 5y")
    if not roe:
        r.missing("pat, net_worth (5y)")
    else:
        a = statistics.mean(roe)
        r.value = dict(roe_series=[r2(x) for x in roe], avg=r2(a))
        r.points, r.band = band(a, [(lambda x: x >= 18, 8, ">= 18%"), (lambda x: x >= 15, 6, ">= 15%"),
                                    (lambda x: x >= 12, 3, ">= 12%")])
    rules.append(r)

    r = Rule("LB2", "B. Capital efficiency", "ROA 5y avg", 7, "PAT / total assets (year-end), avg 5y")
    ta5 = last_n(L.get("total_assets"))
    if not (pat5 and ta5) or len(pat5) != len(ta5):
        r.missing("pat, total_assets (5y)")
    else:
        roa = statistics.mean([p / t * 100 for p, t in zip(pat5, ta5) if t > 0])
        r.value = dict(avg_roa=r2(roa))
        r.points, r.band = band(roa, [(lambda x: x >= 2.0, 7, ">= 2.0%"), (lambda x: x >= 1.5, 5, ">= 1.5%"),
                                      (lambda x: x >= 1.0, 2, ">= 1.0%")])
    rules.append(r)

    car = latest(L.get("car_pct"))
    r = Rule("LC1", "C. Balance sheet", "Capital adequacy (CRAR, latest)", 7, "regulatory CRAR %")
    if not num(car):
        r.missing("car_pct")
    else:
        r.value = dict(car=car)
        r.points, r.band = band(car, [(lambda x: x >= 18, 7, ">= 18%"), (lambda x: x >= 15, 5, ">= 15%"),
                                      (lambda x: x >= 12, 2, ">= 12%")])
    rules.append(r)

    nnpa = latest(L.get("nnpa_pct"))
    r = Rule("LC2", "C. Balance sheet", "Net NPA (latest)", 6, "net NPA %")
    if not num(nnpa):
        r.missing("nnpa_pct")
    else:
        r.value = dict(nnpa=nnpa)
        r.points, r.band = band(nnpa, [(lambda x: x <= 1, 6, "<= 1%"), (lambda x: x <= 2, 3, "<= 2%"),
                                       (lambda x: x <= 3, 1, "<= 3%")])
    rules.append(r)

    gn = last_n(L.get("gnpa_pct"))
    r = Rule("LC3", "C. Balance sheet", "Gross NPA trend", 4, "latest GNPA vs its 5y average")
    if not gn or len(gn) < 3:
        r.missing("gnpa_pct (>=3 points)")
    else:
        d = gn[-1] - statistics.mean(gn)
        r.value = dict(latest=gn[-1], avg=r2(statistics.mean(gn)), diff=r2(d))
        r.points, r.band = band(d, [(lambda x: x <= 0, 4, "at/below avg"), (lambda x: x <= 0.5, 2, "<= +0.5pp")])
    rules.append(r)

    sh = L.get("shares_outstanding")
    shs = last_n(sh, len(sh)) if isinstance(sh, list) and len(sh) >= 2 else None
    r = Rule("LC4", "C. Balance sheet", "Equity dilution", 3, "share count change over series")
    if not shs or shs[0] <= 0:
        r.missing("shares_outstanding")
    else:
        d = (shs[-1] / shs[0] - 1) * 100
        r.value = dict(change_pct=r2(d))
        r.points, r.band = band(d, [(lambda x: x <= 5, 3, "<= 5%"), (lambda x: x <= 15, 1.5, "<= 15%")])
    rules.append(r)

    rank = ind.get("rank_by_loan_book", ind.get("rank_by_revenue"))
    r = Rule("LD1", "D. Dominance", "Rank in segment (loan book)", 8, "1 = largest")
    if not num(rank):
        r.missing("industry_data.rank_by_loan_book")
    else:
        r.value = dict(rank=rank)
        r.points = {1: 8, 2: 5, 3: 3}.get(int(rank), 0)
        r.band = f"rank {int(rank)}"
    rules.append(r)

    share = market_share_series(L.get("loan_book"), {"market_share_pct": ind.get("market_share_pct"),
                                                     "industry_revenue": ind.get("industry_loan_book")})
    share_gain = None
    r = Rule("LD2", "D. Dominance", "Loan-book market share gain", 7, "share_latest / share_first - 1")
    if not share or len(share) < 2 or share[0] <= 0:
        r.missing("market_share_pct or industry_loan_book")
    else:
        share_gain = (share[-1] / share[0] - 1) * 100
        r.value = dict(share_series=[r2(x) for x in share], relative_gain_pct=r2(share_gain))
        r.points, r.band = band(share_gain, [(lambda x: x >= 15, 7, ">= +15%"), (lambda x: x >= 5, 5, ">= +5%"),
                                             (lambda x: x >= 0, 2.5, "held")])
    rules.append(r)

    r = Rule("LD3", "D. Dominance", "Down-cycle resilience (min ROE, 5y)", 5, "minimum annual ROE")
    if not roe:
        r.missing("pat, net_worth")
    else:
        m = min(roe)
        r.value = dict(min_roe=r2(m))
        r.points, r.band = band(m, [(lambda x: x >= 10, 5, ">= 10%"), (lambda x: x >= 5, 2.5, ">= 5%")])
    rules.append(r)

    ph = industry_phase(ind)
    r = Rule("LE1", "E. Cycle", "Segment profitability stagnant/falling", 5, "segment ROE latest vs own avg")
    if not ph:
        r.missing("industry_roe_pct")
    else:
        r.value = dict(latest=r2(ph["latest"]), avg=r2(ph["avg"]), diff=r2(ph["diff"]))
        if ph["latest"] >= 25:
            r.band = "hot"
        else:
            r.points, r.band = band(ph["diff"], [(lambda x: x <= 0, 5, "at/below avg"), (lambda x: x <= 3, 2.5, "<= 3pp above")])
    rules.append(r)

    r = Rule("LE2", "E. Cycle", "Consolidator in a stressed segment", 5, "share rising AND segment ROE <= avg")
    if share_gain is None:
        r.missing("share data")
    else:
        weak = ph is not None and ph["diff"] <= 0
        r.points = 5 if (share_gain > 0 and weak) else (2.5 if share_gain > 0 else 0)
        r.band = "consolidating a weak segment" if r.points == 5 else ("gaining share" if r.points else "not gaining")
    rules.append(r)

    pbm = c.get("pb_10y_median")
    r = Rule("LE3", "E. Cycle", "P/B vs own 10y median", 5, "P/B / 10y median P/B; only if P/B <= 2.0 (absolute first)")
    if pb is None or not num(pbm) or pbm <= 0:
        r.missing("pb_10y_median")
    elif pb > 2.0:
        r.value, r.band = dict(ratio=r2(pb / pbm)), "P/B > 2.0: cheap vs own history is not cheap"
    else:
        rt = pb / pbm
        r.value = dict(ratio=r2(rt))
        r.points, r.band = band(rt, [(lambda x: x <= 0.8, 5, "<= 0.8x"), (lambda x: x <= 1.0, 3, "<= 1.0x"),
                                     (lambda x: x <= 1.25, 1, "<= 1.25x")])
    rules.append(r)

    gates, sells = [], []
    if num(pat_l) and pat_l <= 0:
        gates.append(("G1", "Loss-making lender: wait", 30))
    if num(car) and car < 12:
        gates.append(("G2", f"Thin capital: CRAR {car}% < 12%", 40))
    if (pb is not None and pb > 3) or (ey is not None and num(h) and ey < h / 3):
        gates.append(("G3", "Overpaying for a no-FCF business: P/B > 3 or EY < hurdle/3", 40))
    elif (pb is not None and pb > 2) or (ey is not None and num(h) and ey < h / 2):
        gates.append(("G3", "Rich price for a no-FCF business: P/B > 2 or EY < hurdle/2", 60))
    if (ph and ph["latest"] >= 25) or ind.get("new_large_entrant") is True:
        gates.append(("G4", "Hot segment / new large entrant", 60))
    if ph and ph["latest"] >= 25 and ph["diff"] > 0:
        sells.append("S1 segment ROE >= 25% and rising")
    if ind.get("new_large_entrant") is True:
        sells.append("S2 large new entrant")
    if gn and len(gn) >= 2 and gn[-1] > gn[-2] + 0.5:
        sells.append("S3 GNPA rose > 0.5pp in the latest year")
    if share and len(share) >= 3 and share[-1] < share[-2] < share[-3]:
        sells.append("S4 share fell two years running")
    if pb is not None and num(pbm) and pbm > 0 and pb >= 2 * pbm:
        sells.append("S5 P/B >= 2x own median")
    return rules, gates, sells, dict(pb=r2(pb), ey_pct=r2(ey))


# ---------------------------------------------------------------- driver
def verdict(score):
    if score >= 75:
        return "CORE FIT - capital efficiency available at a price"
    if score >= 60:
        return "FIT - accumulate / strong watchlist"
    if score >= 45:
        return "PARTIAL FIT - monitor, wait for price or evidence"
    return "NOT A FIT"


def evaluate(c):
    kind = c.get("business_type", "non_financial")
    rules, gates, sells, extra = (score_lender if kind == "lender" else score_non_financial)(c)
    raw = round(sum(r.points for r in rules), 2)
    max_total = sum(r.max for r in rules)
    covered = sum(r.max for r in rules if r.status == "OK")
    cap = min([g[2] for g in gates], default=100)
    final = min(raw, cap)
    coverage = round(covered / max_total * 100, 1)
    pillars = {}
    for r in rules:
        p = pillars.setdefault(r.pillar, [0, 0])
        p[0] += r.points
        p[1] += r.max
    action = "HOLD" if not sells else ("REVIEW" if len(sells) == 1 else "EXIT / TRIM candidate")
    return dict(company=c.get("company", "?"), industry=c.get("industry", ""),
                business_type=kind, as_of=c.get("as_of", ""),
                hurdle_yield_pct=c.get("hurdle_yield_pct"),
                raw_score=raw, cap=cap, final_score=final, max_total=max_total,
                coverage_pct=coverage, low_confidence=coverage < 80,
                verdict=verdict(final), pillars={k: [round(v[0], 2), v[1]] for k, v in pillars.items()},
                gates=[dict(id=g[0], reason=g[1], cap=g[2]) for g in gates],
                sell_triggers=sells, holding_action=action, headline=extra,
                rules=[r.to_dict() for r in rules], sources=c.get("sources", {}))


def fmt(v):
    if isinstance(v, dict):
        return "; ".join(f"{k}={fmt(x)}" for k, x in v.items())
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    return "n/a" if v is None else str(v)


def report(res):
    o = []
    o.append(f"# {res['company']} - Capital-Efficiency-at-a-Price score")
    o.append(f"Industry: {res['industry']} | Model: {res['business_type']} | As of: {res['as_of']} | Hurdle yield: {res['hurdle_yield_pct']}%\n")
    o.append(f"**Final score: {res['final_score']} / 100** (raw {res['raw_score']}, cap {res['cap']}) -> **{res['verdict']}**")
    o.append(f"Data coverage: {res['coverage_pct']}%" + ("  **LOW CONFIDENCE (<80%)**" if res["low_confidence"] else ""))
    o.append(f"Headline: {fmt(res['headline'])}\n")
    o.append("## Pillars\n\n| Pillar | Points | Max |\n|---|---|---|")
    for k, (p, m) in res["pillars"].items():
        o.append(f"| {k} | {p} | {m} |")
    o.append("\n## Gates (score caps)\n")
    o.append("\n".join(f"- {g['id']}: {g['reason']} -> cap {g['cap']}" for g in res["gates"]) or "- none triggered")
    o.append(f"\n## Sell-discipline check (if already held): **{res['holding_action']}**\n")
    o.append("\n".join(f"- {s}" for s in res["sell_triggers"]) or "- no sell triggers")
    o.append("\n## Rule-by-rule audit\n\n| ID | Rule | Pts | Max | Value | Band | Formula | Status |\n|---|---|---|---|---|---|---|---|")
    for r in res["rules"]:
        st = r["status"] + (f" ({r['note']})" if r["note"] else "")
        o.append(f"| {r['id']} | {r['name']} | {r['points']} | {r['max']} | {fmt(r['value'])} | {r['band']} | {r['formula']} | {st} |")
    if res["sources"]:
        o.append("\n## Sources\n")
        o.extend(f"- {k}: {v}" for k, v in res["sources"].items())
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out")
    ap.add_argument("--json")
    a = ap.parse_args()
    with open(a.input, encoding="utf-8") as fh:
        data = json.load(fh)
    items = data if isinstance(data, list) else [data]
    results = [evaluate(c) for c in items]
    parts = []
    if len(results) > 1:
        rk = sorted(results, key=lambda x: -x["final_score"])
        parts.append("# Ranking\n\n| # | Company | Final | Raw | Cap | Coverage | Verdict | Holding action |\n|---|---|---|---|---|---|---|---|")
        for i, x in enumerate(rk, 1):
            parts.append(f"| {i} | {x['company']} | {x['final_score']} | {x['raw_score']} | {x['cap']} | {x['coverage_pct']}% | {x['verdict']} | {x['holding_action']} |")
        parts.append("")
    parts.extend(report(x) + "\n" for x in results)
    text = "\n".join(parts)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(results if len(results) > 1 else results[0], fh, indent=2)


if __name__ == "__main__":
    main()
