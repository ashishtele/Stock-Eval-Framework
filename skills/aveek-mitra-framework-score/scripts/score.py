#!/usr/bin/env python3
"""
Aveek Mitra-style bottom-up stock score (0-100).  Version 2.

Deterministic and auditable: every rule prints its inputs, formula and points.
Qualitative rules score ONLY when an evidence string (source / URL / document /
scuttlebutt note) is supplied - unevidenced claims score 0 and are listed as
"unverified". Missing numeric data scores 0 and is listed as "missing".

Two scoring modes (chosen automatically, override with "mode"):
  normal      - growth/quality compounders           A25 B20 C20 D15 E10 F10
  turnaround  - latest FY loss, or a loss in either   A15 B20 C20 D15 E20 F10
                of the 2 prior FYs (growth history is
                base-distorted; inflection + P/S valuation matter more)

Usage:
    python score.py input.json            # markdown report to stdout
    python score.py input.json --json     # machine-readable result
"""
import json
import statistics
import sys

VERSION = "2.0"

# ----------------------------------------------------------------- helpers

def lin(x, lo, hi, pts):
    """Linear interpolation: x<=lo -> 0, x>=hi -> pts. Works for lo>hi (inverse)."""
    if x is None:
        return 0.0
    if lo == hi:
        return pts if x >= hi else 0.0
    frac = (x - lo) / (hi - lo)
    return round(max(0.0, min(1.0, frac)) * pts, 2)


def vals(series):
    return [v for v in (series or []) if v is not None]


def cagr(series, years):
    """CAGR over the last `years` intervals of an oldest->latest series."""
    if not series or len(series) < years + 1:
        return None
    start, end = series[-(years + 1)], series[-1]
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1.0 / years) - 1) * 100


def blend(*xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def avg_last(series, n):
    v = vals((series or [])[-n:])
    return sum(v) / len(v) if v else None


def get(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def fmt(x, nd=1, suffix=""):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, (int, float)):
        return f"{x:,.{nd}f}{suffix}"
    return str(x)


class Scorer:
    def __init__(self, data):
        self.d = data
        self.f = data.get("financials", {}) or {}
        self.v = data.get("valuation", {}) or {}
        self.rules, self.caps, self.labels, self.sell_signals = [], [], [], []
        self.diag = {}
        self.mode = self._mode()

    def _mode(self):
        m = self.d.get("mode", "auto")
        if m in ("normal", "turnaround"):
            return m
        pat = self.f.get("pat") or []
        if pat and pat[-1] is not None and pat[-1] <= 0:
            return "turnaround"
        if len(pat) >= 3 and any(p is not None and p <= 0 for p in pat[-3:-1]):
            return "turnaround"
        return "normal"

    def T(self):
        return self.mode == "turnaround"

    # --- rule recording
    def add(self, rid, pillar, name, inputs, formula, pts, mx, status="ok"):
        self.rules.append(dict(id=rid, pillar=pillar, name=name, inputs=inputs,
                               formula=formula, pts=round(pts, 2), max=mx, status=status))
        return pts

    def qual(self, rid, pillar, name, key, mx, levels=None):
        """Evidence-gated qualitative rule. Item: {"value": true|false|"<level>", "evidence": "source"}"""
        item = get(self.d, "qualitative", key)
        if item is None:
            return self.add(rid, pillar, name, "not assessed", "evidence-gated", 0, mx, "missing")
        val = item.get("value")
        ev = (item.get("evidence") or "").strip()
        if levels:
            base = max(levels.values())
            pts = levels.get(str(val), 0) * mx / base
            formula = "levels: " + ", ".join(f"{k}={round(v * mx / base, 2)}" for k, v in levels.items())
        else:
            pts = mx if val is True else 0
            formula = f"true={mx}, false=0"
        if pts > 0 and not ev:
            return self.add(rid, pillar, name, f"value={val}; NO EVIDENCE", formula + " (evidence required)", 0, mx, "unverified")
        return self.add(rid, pillar, name, f"value={val}; evidence: {ev or '-'}", formula, pts, mx)

    # --- shared derived numbers
    def derive(self):
        f = self.f
        sales, pat = f.get("sales"), f.get("pat")
        self.s3, self.s5 = cagr(sales, 3), cagr(sales, 5)
        self.p3, self.p5 = cagr(pat, 3), cagr(pat, 5)
        self.s_bl, self.p_bl = blend(self.s3, self.s5), blend(self.p3, self.p5)
        q = f.get("quarterly_sales")
        self.ttm_sales = self.ttm_g = None
        self.ttm_basis = None
        if q and len(q) >= 8 and None not in q[-8:]:
            ttm, prev = sum(q[-4:]), sum(q[-8:-4])
            self.ttm_sales = ttm
            self.ttm_g = (ttm / prev - 1) * 100 if prev > 0 else None
            self.ttm_basis = "TTM vs prior 4Q"
        elif sales and len(sales) >= 2 and sales[-2]:
            self.ttm_g = (sales[-1] / sales[-2] - 1) * 100
            self.ttm_basis = "latest FY vs prior FY"
        qp = f.get("quarterly_pat")
        self.ttm_pat = sum(qp[-4:]) if qp and len(qp) >= 4 and None not in qp[-4:] else None
        # growth the business has actually shown (base-effect guarded)
        if self.p_bl is not None and self.s_bl is not None and self.p_bl > self.s_bl + 10:
            self.hist_g, self.hist_basis = self.s_bl + 10, "sales CAGR + 10pp (PAT CAGR base/margin-distorted)"
        elif self.p_bl is not None:
            self.hist_g, self.hist_basis = self.p_bl, "blended 3y/5y PAT CAGR"
        else:
            self.hist_g, self.hist_basis = self.s_bl, "blended 3y/5y sales CAGR (PAT base <= 0)"
        # effective expected growth (clamped)
        g = self.v.get("expected_growth_pct")
        self.g_eff, self.g_note = g, "as input"
        if g is not None:
            ceil = 35.0
            if self.s_bl is not None or self.s3 is not None:
                ceil = min(ceil, max(x for x in (self.s3, self.s5, self.s_bl) if x is not None) + 10)
            if g > ceil:
                self.g_eff, self.g_note = round(ceil, 1), f"clamped from {g} to min(35, best sales CAGR + 10pp)"
        # market cap
        mc = self.d.get("market_cap_cr") or self.v.get("market_cap_cr")
        if not mc and self.v.get("pe"):
            e = self.ttm_pat if self.ttm_pat and self.ttm_pat > 0 else (pat[-1] if pat else None)
            mc = self.v["pe"] * e if e and e > 0 else None
        self.mcap = mc
        self.diag.update(sales_cagr_3y=self.s3, sales_cagr_5y=self.s5, pat_cagr_3y=self.p3, pat_cagr_5y=self.p5,
                         ttm_sales_growth=self.ttm_g, ttm_basis=self.ttm_basis, historical_growth=self.hist_g,
                         historical_growth_basis=self.hist_basis, expected_growth_effective=self.g_eff,
                         expected_growth_note=self.g_note, market_cap_cr=self.mcap)

    # ------------------------------------------------------------- pillars
    def growth(self):
        P = "A. Growth engine"
        sales = self.f.get("sales")
        if self.T():
            self.add("A1", P, "Recent sales growth (" + (self.ttm_basis or "n/a") + ")", f"{fmt(self.ttm_g)}%",
                     "lin(g, 0%->0, 20%->8)", lin(self.ttm_g, 0, 20, 8), 8, "ok" if self.ttm_g is not None else "missing")
            s = self.s5 if self.s5 is not None else self.s3
            self.add("A2", P, "Sales CAGR 5y (3y if 5y n/a)", f"{fmt(s)}%", "lin(CAGR, 0%->0, 15%->4)",
                     lin(s, 0, 15, 4), 4, "ok" if s is not None else "missing")
            mx3 = 3
        else:
            self.add("A1", P, "Sales CAGR (avg of 3y & 5y)", f"3y {fmt(self.s3)}% / 5y {fmt(self.s5)}% -> {fmt(self.s_bl)}%",
                     "lin(CAGR, 5%->0, 20%->8)", lin(self.s_bl, 5, 20, 8), 8, "ok" if self.s_bl is not None else "missing")
            self.add("A2", P, "PAT CAGR (avg of 3y & 5y)", f"3y {fmt(self.p3)}% / 5y {fmt(self.p5)}% -> {fmt(self.p_bl)}%",
                     "lin(CAGR, 5%->0, 25%->7)", lin(self.p_bl, 5, 25, 7), 7, "ok" if self.p_bl is not None else "missing")
            mx3 = 5
        if sales and len(sales) >= 6 and None not in sales[-6:]:
            ups = sum(1 for a, b in zip(sales[-6:-1], sales[-5:]) if b > a)
            self.add("A3", P, "Growth consistency (sales up-years of last 5)", f"{ups}/5", f"up_years/5 x {mx3}", ups / 5 * mx3, mx3)
        else:
            self.add("A3", P, "Growth consistency", "need 6 annual sales points", f"up_years/5 x {mx3}", 0, mx3, "missing")

        if not self.T():
            if self.ttm_g is None:
                self.add("A4", P, "Momentum", "need 8 quarters or 2 FYs", "-", 0, 5, "missing")
            else:
                abs_pts = lin(self.ttm_g, 0, 20, 5)
                rel_pts = lin(self.ttm_g / self.s3, 0.5, 1.0, 5) if self.s3 and self.s3 > 0 else 0
                self.add("A4", P, f"Momentum ({self.ttm_basis})", f"g {fmt(self.ttm_g)}% vs 3y CAGR {fmt(self.s3)}%",
                         "max(lin(g/CAGR3y, 0.5->0, 1.0->5), lin(g, 0%->0, 20%->5))", max(abs_pts, rel_pts), 5)
            # Growth gate is applied in run() after the consolidation detector (which can waive it).

    def capital(self):
        P = "B. Capital efficiency & allocation"
        f = self.f
        if self.T():
            r, e = vals(f.get("roce_pct")), vals(f.get("roe_pct"))
            roce = statistics.median(r) if len(r) >= 3 else None
            roe = statistics.median(e) if len(e) >= 3 else None
            lbl = "through-cycle median (all years)"
        else:
            roce, roe = avg_last(f.get("roce_pct"), 3), avg_last(f.get("roe_pct"), 3)
            lbl = "avg 3y"
        self.roce = roce
        self.diag["roce_used"] = roce
        self.add("B1", P, f"ROCE {lbl}", f"{fmt(roce)}%", "lin(ROCE, 10%->0, 25%->6)", lin(roce, 10, 25, 6), 6,
                 "ok" if roce is not None else "missing")
        self.add("B2", P, f"ROE {lbl}", f"{fmt(roe)}%", "lin(ROE, 10%->0, 22%->4)", lin(roe, 10, 22, 4), 4,
                 "ok" if roe is not None else "missing")

        ebit, ce = f.get("ebit"), f.get("capital_employed")
        if ebit and ce and len(ebit) >= 4 and len(ce) >= 4 and None not in (ebit[-1], ebit[-4], ce[-1], ce[-4]) and roce:
            d_ebit, d_ce = ebit[-1] - ebit[-4], ce[-1] - ce[-4]
            if d_ce > 0:
                incr = d_ebit / d_ce * 100
                pts = lin(incr / roce, 0.6, 1.0, 5) if roce > 0 else 0
                inp = f"dEBIT {fmt(d_ebit)} / dCE {fmt(d_ce)} = {fmt(incr)}% vs ROCE {fmt(roce)}%"
            else:
                incr, pts, inp = None, 1, "capital employed not growing (no reinvestment)"
            self.diag["incremental_roce_3y"] = incr
            self.add("B3", P, "Reinvestment: incremental ROCE vs ROCE", inp,
                     "lin(incrROCE/ROCE, 0.6->0, 1.0->5); no reinvestment=1", pts, 5)
        else:
            self.add("B3", P, "Reinvestment: incremental ROCE", "need 4y EBIT & capital employed", "-", 0, 5, "missing")

        cash, ta = f.get("cash_and_investments"), f.get("total_assets")
        if cash is not None and ta:
            share = cash / ta * 100
            self.add("B4", P, "Idle-cash drag (cash+investments / total assets)", f"{fmt(share)}%",
                     "lin(share, 40%->0, 15%->3)", lin(share, 40, 15, 3), 3)
        else:
            self.add("B4", P, "Idle-cash drag", "missing", "-", 0, 3, "missing")

        cfo, pat = vals((f.get("cfo") or [])[-5:]), vals((f.get("pat") or [])[-5:])
        if len(cfo) >= 5 and len(pat) >= 5:
            if sum(pat) > 0:
                conv = sum(cfo) / sum(pat)
                self.diag["cfo_pat_5y"] = conv
                self.add("B5", P, "Cash conversion (sum CFO 5y / sum PAT 5y)", fmt(conv, 2), "lin(x, 0.5->0, 0.9->2)",
                         lin(conv, 0.5, 0.9, 2), 2)
            else:
                self.add("B5", P, "Cash generation while loss-making", f"sum CFO 5y {fmt(sum(cfo))}",
                         "sum CFO > 0 -> 1, else 0", 1 if sum(cfo) > 0 else 0, 2)
        else:
            self.add("B5", P, "Cash conversion", "need 5y CFO & PAT", "-", 0, 2, "missing")

    def moat(self):
        P = "C. Moat & tailwind"
        opm = vals(self.f.get("opm_pct"))
        if len(opm) >= 5:
            sd = statistics.pstdev(opm[-5:])
            self.add("C1", P, "Margin stability (stdev OPM 5y)", f"{fmt(sd)} pp", "lin(sd, 8pp->0, 2pp->4)", lin(sd, 8, 2, 4), 4)
        else:
            self.add("C1", P, "Margin stability", "need 5y OPM", "-", 0, 4, "missing")
        peer_opm = self.v.get("peer_median_opm_pct")
        if opm and peer_opm is not None:
            diff = opm[-1] - peer_opm
            self.add("C2", P, "OPM vs peer median", f"{fmt(opm[-1])}% vs {fmt(peer_opm)}% ({fmt(diff)} pp)",
                     "lin(diff, -2pp->0, +5pp->2)", lin(diff, -2, 5, 2), 2)
        else:
            self.add("C2", P, "OPM vs peer median", "missing", "-", 0, 2, "missing")
        m = 0
        m += self.qual("C3", P, "Niche leadership", "niche_leadership", 4,
                       levels={"global_leader": 4, "national_leader": 3, "significant_player": 1, "none": 0})
        m += self.qual("C4", P, "Critical component, small share of customer cost", "critical_low_cost_share", 2)
        m += self.qual("C5", P, "Hard-to-replicate know-how / approvals / process IP", "process_knowhow_barrier", 3)
        m += self.qual("C6", P, "Structural long-cycle tailwind (evidenced)", "structural_tailwind", 3)
        self.moat_pts = m
        bt = self.d.get("business_type", "")
        bt_pts = {"compounder": 2, "global_long_cycle": 2, "picks_and_shovels": 2, "turnaround": 1,
                  "asset_play": 0, "global_commodity": 0, "local_commodity_cyclical": 0}
        self.add("C7", P, "Business type", bt or "missing",
                 "compounder/global_long_cycle/picks_and_shovels=2, turnaround=1, asset_play/global_commodity/local_commodity_cyclical=0",
                 bt_pts.get(bt, 0), 2, "ok" if bt in bt_pts else "missing")
        if bt == "local_commodity_cyclical":
            self.labels.append("LOCAL_CYCLICAL")
            self.caps.append((55, "Local commodity cyclical (price set by micro-market/govt) - hard to predict"))

    def governance(self):
        P = "D. Promoter & governance"
        o = self.d.get("ownership", {}) or {}
        now, ago = o.get("promoter_holding_pct_now"), o.get("promoter_holding_pct_1y_ago")
        if now is not None and ago is not None:
            dlt = now - ago
            self.add("D1", P, "Promoter holding change 12m", f"{fmt(ago)}% -> {fmt(now)}% ({fmt(dlt, 2)} pp)",
                     "lin(delta, -2pp->0, +1pp->4)", lin(dlt, -2, 1, 4), 4)
        else:
            self.add("D1", P, "Promoter holding change", "missing", "-", 0, 4, "missing")
        bp, cmp_ = o.get("promoter_buy_price_24m"), self.d.get("cmp")
        self.promoter_bought_above = bool(bp and cmp_ and bp >= cmp_)
        if bp and cmp_:
            r = bp / cmp_
            self.add("D2", P, "Promoter/insider buying price vs CMP (24m)", f"buy {fmt(bp)} / CMP {fmt(cmp_)} = {fmt(r, 2)}",
                     ">=0.8x CMP ->3, lower ->1.5, none ->0", 3 if r >= 0.8 else 1.5, 3)
        else:
            self.add("D2", P, "Promoter/insider buying (24m)", "none reported", ">=0.8x CMP ->3, lower ->1.5, none ->0", 0, 3)
        pl = o.get("pledge_pct")
        if pl is not None:
            self.add("D3", P, "Promoter pledge", f"{fmt(pl)}%", "lin(pledge, 20%->0, 0%->3)", lin(pl, 20, 0, 3), 3)
            if pl > 50:
                self.caps.append((30, f"Kill switch: pledge {pl}% > 50%"))
        else:
            self.add("D3", P, "Promoter pledge", "missing", "-", 0, 3, "missing")
        dd = self.f.get("debtor_days")
        if dd and len(dd) >= 4 and dd[-4] and dd[-1] is not None:
            chg = (dd[-1] / dd[-4] - 1) * 100
            self.add("D4", P, "Receivable days trend (3y)", f"{fmt(dd[-4], 0)} -> {fmt(dd[-1], 0)} ({fmt(chg)}%)",
                     "lin(change, +50%->0, +10%->3)", lin(chg, 50, 10, 3), 3)
        else:
            self.add("D4", P, "Receivable days trend", "need 4y debtor days", "-", 0, 3, "missing")
        self.qual("D5", P, "Promoter hunger to grow (evidenced capex/expansion/new markets)", "promoter_hunger", 2)
        fl = self.d.get("flags", {}) or {}
        if fl.get("auditor_qualification_or_resignation"):
            self.caps.append((30, "Kill switch: auditor qualification / resignation"))
        if fl.get("unexplained_cash_or_related_party"):
            self.caps.append((40, "Kill switch: unexplained cash (e.g. parked abroad) / related-party concerns"))
        conv = self.diag.get("cfo_pat_5y")
        if fl.get("accounting_concerns") and conv is not None and conv < 0.5:
            self.caps.append((40, f"Kill switch: accounting concerns + CFO/PAT {conv:.2f} < 0.5"))
        elif fl.get("accounting_concerns"):
            self.labels.append("ACCOUNTING_WATCH")

    def inflection(self):
        P = "E. Inflection / catalyst"
        w = dict(E1=5, E2=4, E3=5, E4=4, E5=2) if self.T() else dict(E1=3, E2=2, E3=2, E4=2, E5=1)
        pat, qp = self.f.get("pat"), self.f.get("quarterly_pat")
        if pat and len(pat) >= 3:
            prior_loss = any(p is not None and p < 0 for p in pat[-3:])
            ttm = self.ttm_pat if self.ttm_pat is not None else None
            if prior_loss and ttm is not None and ttm > 0:
                pts, why = w["E1"], f"loss in last 3 FYs and TTM PAT {fmt(ttm)} > 0"
            elif pat[-1] is not None and pat[-1] <= 0 and qp and qp[-1] is not None and qp[-1] > 0:
                pts, why = 0.6 * w["E1"], f"loss FY but latest quarter PAT {fmt(qp[-1])} > 0"
            else:
                pts, why = 0, f"PAT last 3 FY {pat[-3:]}; TTM {fmt(ttm)}"
            self.add("E1", P, "Loss-to-profit turnaround", why,
                     f"loss in last 3 FY & TTM profit -> {w['E1']}; loss FY & latest qtr profit -> {0.6 * w['E1']}", pts, w["E1"])
            if pts > 0:
                self.labels.append("TURNAROUND")
        else:
            self.add("E1", P, "Loss-to-profit turnaround", "missing", "-", 0, w["E1"], "missing")
        b = self.f.get("borrowings")
        if b and len(b) >= 3 and b[-3] is not None and b[-1] is not None:
            if b[-3] <= 0 and b[-1] <= 0:
                self.add("E2", P, "Deleveraging (2y)", "debt-free", f"debt-free -> {w['E2']}", w["E2"], w["E2"])
            elif b[-3] > 0:
                red = (1 - b[-1] / b[-3]) * 100
                self.add("E2", P, "Deleveraging (2y)", f"{fmt(b[-3])} -> {fmt(b[-1])} ({fmt(red)}% cut)",
                         f"lin(cut, 0%->0, 50%->{w['E2']})", lin(red, 0, 50, w["E2"]), w["E2"])
            else:
                self.add("E2", P, "Deleveraging (2y)", "debt newly added", "-", 0, w["E2"])
        else:
            self.add("E2", P, "Deleveraging", "need 3y borrowings", "-", 0, w["E2"], "missing")
        self.qual("E3", P, "Capacity utilisation / order book / volume data rising", "volume_inflection", w["E3"])
        self.qual("E4", P, "New product/design/customer with visible adoption", "new_product_adoption", w["E4"])
        trig = self.qual("E5", P, "Dated value-unlock trigger (demerger, sale, buyback, listing)", "unlock_trigger", w["E5"])
        if self.d.get("business_type") == "asset_play" and not trig:
            self.labels.append("VALUE_TRAP_RISK")
            self.caps.append((50, "Asset play with no evidenced unlock trigger - value-trap risk"))

    def valuation(self):
        P = "F. Valuation (P/E = perception of growth x durability)"
        v = self.v
        pe = v.get("pe")
        if self.T():
            sales_now = self.ttm_sales or (vals(self.f.get("sales")) or [None])[-1]
            if self.mcap and sales_now:
                ps = self.mcap / sales_now
                self.add("F1", P, "Price / sales (turnaround mode)", f"{fmt(self.mcap, 0)} / {fmt(sales_now, 0)} = {fmt(ps, 2)}",
                         "lin(P/S, 2.0->0, 0.5->4)", lin(ps, 2.0, 0.5, 4), 4)
            else:
                self.add("F1", P, "Price / sales", "need market_cap_cr (or P/E) and sales", "-", 0, 4, "missing")
            hist = vals((self.f.get("pat") or [])[-10:])
            if self.mcap and len(hist) >= 5:
                norm = sum(hist) / len(hist)
                if norm > 0:
                    npe = self.mcap / norm
                    self.add("F2", P, "Normalised P/E (mcap / avg PAT up to 10y)", f"{fmt(self.mcap, 0)} / {fmt(norm)} = {fmt(npe)}",
                             "lin(nPE, 25->0, 10->3)", lin(npe, 25, 10, 3), 3)
                else:
                    self.add("F2", P, "Normalised P/E", f"avg PAT {fmt(norm)} <= 0", "-> 0", 0, 3)
            else:
                self.add("F2", P, "Normalised P/E", "need market cap and >=5y PAT", "-", 0, 3, "missing")
        else:
            g, ppe, pg = self.g_eff, v.get("peer_median_pe"), v.get("peer_median_growth_pct")
            if pe and g is not None:
                if g <= 0:
                    self.add("F1", P, "PEG", f"expected growth {g}% <= 0", "no growth -> 0", 0, 4)
                elif ppe and pg and pg > 0:
                    rel = (pe / g) / (ppe / pg)
                    self.diag["relative_peg"] = rel
                    self.add("F1", P, "Relative PEG vs peers", f"({fmt(pe)}/{fmt(g)}) / ({fmt(ppe)}/{fmt(pg)}) = {fmt(rel, 2)}",
                             "lin(relPEG, 1.5->0, 0.8->4)", lin(rel, 1.5, 0.8, 4), 4)
                else:
                    peg = pe / g
                    self.diag["peg"] = peg
                    self.add("F1", P, "Absolute PEG (peer growth n/a or <= 0)", f"{fmt(pe)}/{fmt(g)} = {fmt(peg, 2)}",
                             "lin(PEG, 2.0->0, 1.0->4)", lin(peg, 2.0, 1.0, 4), 4)
            else:
                self.add("F1", P, "PEG", "need P/E and expected growth", "-", 0, 4, "missing")
            med = v.get("pe_5y_median")
            if pe and med:
                r = pe / med
                self.add("F2", P, "P/E vs own 5y median", f"{fmt(pe)} / {fmt(med)} = {fmt(r, 2)}",
                         "lin(ratio, 1.5->0, 0.8->3)", lin(r, 1.5, 0.8, 3), 3)
            else:
                self.add("F2", P, "P/E vs own 5y median", "missing", "-", 0, 3, "missing")
        tam = v.get("addressable_market_cr")
        sales_ttm = self.ttm_sales or (vals(self.f.get("sales")) or [None])[-1]
        if tam and sales_ttm:
            h = tam / sales_ttm
            self.diag["tam_headroom_x"] = h
            self.add("F3", P, "Addressable-market headroom (SAM / TTM sales)", f"{fmt(tam, 0)} / {fmt(sales_ttm, 0)} = {fmt(h)}x",
                     "lin(x, 2->0, 10->3)  [ADDRESSABLE, not total, market]", lin(h, 2, 10, 3), 3)
        else:
            self.add("F3", P, "Addressable-market headroom", "missing", "-", 0, 3, "missing")
        ke, exit_pe, n = v.get("hurdle_rate_pct", 13) / 100, v.get("exit_pe", 20), v.get("horizon_years", 10)
        if pe and pe > 0:
            self.diag["implied_eps_cagr_pct"] = (((pe / exit_pe) * (1 + ke) ** n) ** (1 / n) - 1) * 100
            self.diag["implied_basis"] = f"hurdle {ke * 100:.0f}%, exit P/E {exit_pe}, {n}y"

    # ------------------------------------------------- consolidation detector
    def consolidation(self):
        """Sell after a run, re-buy in consolidation when the long-term thesis is intact (Shivalik pattern)."""
        if self.T():
            return
        pe, med, cmp_ = self.v.get("pe"), self.v.get("pe_5y_median"), self.d.get("cmp")
        hi = self.v.get("high_52w")
        cheap = self.promoter_bought_above or (pe and med and pe < med) or (hi and cmp_ and cmp_ <= 0.75 * hi)
        ok = (self.s5 is not None and self.s5 >= 15 and self.roce is not None and self.roce >= 18
              and self.moat_pts >= 6 and self.ttm_g is not None and self.s3 is not None and self.ttm_g < self.s3 and cheap)
        if ok:
            self.labels.append("CONSOLIDATION")
            why = ("promoter bought above CMP" if self.promoter_bought_above else
                   "P/E below own 5y median" if (pe and med and pe < med) else ">=25% below 52w high")
            self.diag["consolidation_reason"] = f"5y sales CAGR {self.s5:.1f}%, ROCE {self.roce:.1f}%, moat pts {self.moat_pts}, growth paused ({self.ttm_g:.1f}% < {self.s3:.1f}%), {why}"

    # ----------------------------------------------------------- sell module
    def sell_check(self):
        v = self.v
        if (self.s3 and self.s3 > 0 and self.ttm_g is not None and self.ttm_g < 0.5 * self.s3 and self.ttm_g < 10
                and "CONSOLIDATION" not in self.labels):
            self.sell_signals.append(f"S1 Growth flattening: {self.ttm_basis} {self.ttm_g:.1f}% < half of 3y CAGR {self.s3:.1f}% and < 10%")
        pe, ppe, pg = v.get("pe"), v.get("peer_median_pe"), v.get("peer_median_growth_pct")
        if pe and ppe and self.g_eff is not None and pg is not None and pe > 1.5 * ppe and self.g_eff <= pg:
            self.sell_signals.append(f"S2 P/E {pe} > 1.5x peers ({ppe}) without superior growth ({self.g_eff}% vs {pg}%)")
        imp = self.diag.get("implied_eps_cagr_pct")
        if imp is not None and self.hist_g is not None and imp > self.hist_g + 5:
            self.sell_signals.append(f"S3 Price implies {imp:.1f}% EPS CAGR vs shown {self.hist_g:.1f}% ({self.hist_basis})")
        th = self.diag.get("tam_headroom_x")
        if th is not None and th < 3:
            self.sell_signals.append(f"S4 Addressable market nearly saturated ({th:.1f}x sales)")
        if (self.d.get("holding") or {}).get("better_alternative_available"):
            self.sell_signals.append("S5 Better risk-adjusted alternative identified (opportunity cost)")
        ind = v.get("industry_growth_pct")
        if imp is not None and ind is not None and imp > ind + 10:
            self.sell_signals.append(f"S6 Price implies {imp:.1f}% EPS CAGR for a decade in an industry growing {ind}% - needs a decade of share gains")

    # ---------------------------------------------------------------- run
    def run(self):
        self.derive()
        self.growth(); self.capital(); self.moat(); self.governance(); self.inflection(); self.valuation()
        self.consolidation()
        # Gate: "a good company that is not growing is not an investment" (waived for quality-in-consolidation)
        if (not self.T() and "CONSOLIDATION" not in self.labels and self.s3 is not None and self.s3 < 8
                and (self.ttm_g is None or self.ttm_g < 10)):
            self.labels.append("NOT_GROWING")
            self.caps.append((55, "Growth gate: 3y sales CAGR < 8% and recent growth < 10% - 'good company, not a good investment'"))
        # Structural headwind (evidence-gated judgement, e.g. end-market shrinking): caps and blocks bullish labels
        hw = get(self.d, "qualitative", "structural_headwind") or {}
        if hw.get("value") is True and (hw.get("evidence") or "").strip():
            self.labels.append("HEADWIND")
            if "CONSOLIDATION" in self.labels:
                self.labels.remove("CONSOLIDATION")
            self.caps.append((60, f"Structural headwind: {hw['evidence'][:120]}"))
        self.sell_check()
        raw = round(sum(r["pts"] for r in self.rules), 1)
        cap = min([c for c, _ in self.caps], default=100)
        final = round(min(raw, cap), 1)
        pillars = {}
        for r in self.rules:
            p = pillars.setdefault(r["pillar"], [0, 0]); p[0] += r["pts"]; p[1] += r["max"]
        avail_max = sum(r["max"] for r in self.rules if r["status"] != "missing")
        on_avail = round(raw / avail_max * 100, 1) if avail_max else 0
        completeness = round(sum(1 for r in self.rules if r["status"] != "missing") / len(self.rules) * 100)
        scut_ok = [s for s in (self.d.get("scuttlebutt") or []) if (s.get("evidence") or "").strip()]
        n_types = len({s.get("type") for s in scut_ok})
        conf = "High" if n_types >= 3 else "Medium" if n_types >= 1 else "Low"

        A = pillars.get("A. Growth engine", [0, 25])
        q_pts = pillars.get("B. Capital efficiency & allocation", [0, 20])[0] + pillars.get("D. Promoter & governance", [0, 15])[0]
        size = None
        if any(c <= 40 for c, _ in self.caps):
            cls = "AVOID - governance / accounting kill switch"
        elif "NOT_GROWING" in self.labels and q_pts >= 0.6 * 35:
            cls = "GOOD COMPANY, NOT A GOOD INVESTMENT (quality without growth)"
        elif "VALUE_TRAP_RISK" in self.labels:
            cls = "VALUE TRAP RISK (cheap asset, no unlock trigger)"
        elif "LOCAL_CYCLICAL" in self.labels:
            cls = "LOCAL CYCLICAL - only with picks-and-shovels angle or deleveraging inflection"
        elif "HEADWIND" in self.labels:
            cls = "STRUCTURAL HEADWIND - growth tied to a shrinking/stagnant end-market; not a compounder"
        elif "CONSOLIDATION" in self.labels and final >= 50:
            cls = "QUALITY IN CONSOLIDATION - accumulate zone (growth paused, thesis & insider buying intact)"
            size = "Starter ~2%, add as growth re-accelerates"
        elif self.T():
            if final >= 45:
                cls = "TURNAROUND / INFLECTION CANDIDATE (speculative - invest through uncertainty, size small)"
                size = "Starter ~1-2%; add only as the inflection shows in reported numbers"
            else:
                cls = "TURNAROUND NOT YET EVIDENCED - watch for the inflection"
                size = "Watchlist only"
        elif final >= 70 and A[0] >= 0.68 * A[1]:
            cls = "COMPOUNDER CANDIDATE"
        elif final >= 60:
            cls = "WATCH / STARTER QUALITY"
        else:
            cls = "PASS"
        if size is None:
            size = ("High conviction - start ~4%, add on evidence" if final >= 80 else "Start ~3%" if final >= 70 else
                    "Starter/tracking position ~2%" if final >= 60 else "Watchlist only" if final >= 50 else "Avoid")
        if conf == "Low" and final >= 60:
            size += " (cap at 2% until scuttlebutt verifies the thesis)"
        if completeness < 70:
            cls += " - INSUFFICIENT DATA (<70% of rules scored; fill gaps before acting)"
        ns = len(self.sell_signals)
        action = None
        if (self.d.get("holding") or {}).get("own"):
            action = "HOLD" if ns == 0 else "REVIEW" if ns == 1 else "TRIM" if ns == 2 else "SELL CANDIDATE"
        return dict(version=VERSION, company=self.d.get("company"), ticker=self.d.get("ticker"), as_of=self.d.get("as_of"),
                    mode=self.mode, raw_score=raw, cap=cap if cap < 100 else None, final_score=final,
                    score_on_available_data=on_avail,
                    pillars={k: [round(a, 1), b] for k, (a, b) in pillars.items()},
                    caps=self.caps, labels=self.labels, classification=cls, sizing=size,
                    data_completeness_pct=completeness, evidence_confidence=conf,
                    scuttlebutt_types=sorted({s.get("type") for s in scut_ok}),
                    sell_signals=self.sell_signals, holding_action=action,
                    diagnostics={k: (round(x, 2) if isinstance(x, float) else x) for k, x in self.diag.items()},
                    rules=self.rules)


def report(r):
    L = [f"# {r['company']} ({r['ticker']}) - Bottom-up Framework Score (v{r['version']})", f"As of: {r['as_of']}  |  Mode: **{r['mode']}**\n",
         f"## Final score: **{r['final_score']} / 100**  (raw {r['raw_score']}" + (f", capped at {r['cap']})" if r['cap'] else ")"),
         f"- Score on available data only: {r['score_on_available_data']} (for context; final score treats missing as 0)",
         f"- Classification: **{r['classification']}**", f"- Position-size guide: {r['sizing']}",
         f"- Data completeness: {r['data_completeness_pct']}% of rules had data",
         f"- Evidence confidence (scuttlebutt): {r['evidence_confidence']} {r['scuttlebutt_types'] or ''}"]
    if r["holding_action"]:
        L.append(f"- Existing holding action: **{r['holding_action']}**")
    L += ["\n## Pillars", "| Pillar | Points | Max |", "|---|---:|---:|"]
    L += [f"| {k} | {a} | {b} |" for k, (a, b) in r["pillars"].items()]
    if r["caps"]:
        L.append("\n## Caps / kill switches applied")
        L += [f"- Cap {c}: {why}" for c, why in r["caps"]]
    L += ["\n## Rule-by-rule audit", "| ID | Rule | Inputs | Formula | Pts | Max | Status |", "|---|---|---|---|---:|---:|---|"]
    for x in r["rules"]:
        L.append(f"| {x['id']} | {x['name']} | {str(x['inputs']).replace('|', '/')} | {x['formula']} | {x['pts']} | {x['max']} | {x['status']} |")
    d = r["diagnostics"]
    L.append("\n## Diagnostics")
    if "implied_eps_cagr_pct" in d:
        L.append(f"- Growth priced in: {d['implied_eps_cagr_pct']}% EPS CAGR ({d['implied_basis']})")
    for k, x in d.items():
        if k not in ("implied_eps_cagr_pct", "implied_basis") and x is not None:
            L.append(f"- {k}: {x}")
    L.append("\n## Sell / review signals")
    L.extend([f"- {s}" for s in r["sell_signals"]] or ["- None triggered"])
    miss = [x["id"] for x in r["rules"] if x["status"] == "missing"]
    unv = [x["id"] for x in r["rules"] if x["status"] == "unverified"]
    if miss: L.append(f"\nMissing data (scored 0): {', '.join(miss)}")
    if unv: L.append(f"Unverified claims (scored 0 - add evidence): {', '.join(unv)}")
    return "\n".join(L)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    res = Scorer(data).run()
    print(json.dumps(res, indent=2, default=str) if "--json" in sys.argv else report(res))
