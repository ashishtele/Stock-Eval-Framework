#!/usr/bin/env python3
"""
E-QUAL Stock Framework scorer (Quality -> Growth -> Purchase-price discipline).

Deterministic, standard-library only. Every point awarded is traced to an
input value and a rule from config.json, so any score can be re-verified by hand.

Usage:
  python score.py input.json                       # markdown report to stdout
  python score.py input.json --out report.md --json result.json
  python score.py a.json b.json c.json --compare   # side-by-side ranking table
  python score.py input.json --config my_config.json
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ----------------------------------------------------------------- helpers
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get(d, path, default=None):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur or cur[k] is None:
            return default
        cur = cur[k]
    return cur


def step_points(value, rule):
    """Apply a step table. op '>=' : first threshold value meets wins (descending).
    op '<=' : first threshold value is within wins (ascending)."""
    op = rule["op"]
    for thr, pts in rule["steps"]:
        if (op == ">=" and value >= thr) or (op == "<=" and value <= thr):
            return pts, f"{op} {thr} -> {pts}"
    return rule["else"], f"outside all steps -> {rule['else']}"


def table_text(rule):
    unit = rule.get("unit", "")
    parts = [f"{rule['op']}{t}{'' if unit in ('x', 'count', 'pp') else ''}: {p}" for t, p in rule["steps"]]
    return f"[{', '.join(parts)}, else {rule['else']}] ({unit})"


def fmt(v, nd=2):
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        if math.isinf(v):
            return "inf"
        return f"{v:,.{nd}f}"
    return str(v)


def lerp(x, x0, y0, x1, y1):
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


# ----------------------------------------------------------------- scorer
class Scorer:
    def __init__(self, data, cfg):
        self.d = data
        self.c = cfg
        self.rows = []        # E-QUAL rule rows
        self.grows = []       # growth rule rows
        self.kills = []
        self.warnings = []
        self.missing = []
        self.inputs_checked = 0

    # --- row helpers
    def _row(self, bucket, rid, rule, value, pts, why, unverified=False):
        bucket.append({
            "id": rid,
            "pillar": rule.get("pillar", "growth"),
            "label": rule["label"],
            "value": value,
            "points": round(pts, 2),
            "max": rule["max"],
            "rule": why,
            "status": "UNVERIFIED" if unverified else "OK",
        })

    def _neutral(self, bucket, rid, rule, field):
        self.missing.append(field)
        credit = rule["max"] * self.c["missing_data_credit"]
        self._row(bucket, rid, rule, None, credit,
                  f"missing `{field}` -> neutral {int(self.c['missing_data_credit']*100)}% credit", True)

    def need(self, *fields):
        """Return values; None if any missing (and record missing)."""
        self.inputs_checked += 1
        vals = [get(self.d, f) for f in fields]
        return vals

    def simple(self, bucket, rid, field, value=None, extra=""):
        rule = self._rules(bucket)[rid]
        self.inputs_checked += 1
        v = get(self.d, field) if value is None else value
        if v is None:
            self._neutral(bucket, rid, rule, field)
            return None
        pts, why = step_points(v, rule)
        self._row(bucket, rid, rule, v, pts, f"{fmt(v)} {rule.get('unit','')} {why} {table_text(rule)}{extra}")
        return v

    def _rules(self, bucket):
        return self.c["equal_rules"] if bucket is self.rows else self.c["growth_rules"]

    # --- derived inputs
    def derived(self):
        d = self.d
        pat = get(d, "market.pat_ttm_cr")
        rev = get(d, "financials.revenue_cr")
        mcap = get(d, "market.market_cap_cr")
        pe = get(d, "market.pe_ttm")
        if pe is None and pat and mcap:
            pe = mcap / pat
        if pat is None and pe and mcap:
            pat = mcap / pe
        self.pat, self.rev, self.mcap, self.pe = pat, rev, mcap, pe
        self.is_fin = bool(get(d, "is_financial", False))
        self.sector_type = get(d, "sector_type", None)

    # --- E-QUAL pillars
    def score_equal(self):
        R = self.c["equal_rules"]
        rows = self.rows
        d = self.d

        # I1 promoter holding
        if get(d, "integrity.no_identifiable_promoter", False):
            r = R["I1_promoter_holding"]
            self._row(rows, "I1_promoter_holding", r, "no promoter", r["max"] * 0.5,
                      "professionally managed / no identifiable promoter -> 50% credit")
        else:
            self.simple(rows, "I1_promoter_holding", "integrity.promoter_holding_pct")

        self.simple(rows, "I2_promoter_change", "integrity.promoter_holding_change_3y_pp")

        # I3 equity history
        r = R["I3_equity_history"]
        cnt = get(d, "integrity.bonus_split_buyback_count_10y")
        pref = get(d, "integrity.preferential_to_promoters_5y")
        self.inputs_checked += 1
        if cnt is None:
            self._neutral(rows, "I3_equity_history", r, "integrity.bonus_split_buyback_count_10y")
        else:
            pts = r["base"] + r["per_event"] * cnt - (r["preferential_penalty"] if pref else 0)
            pts = max(0, min(r["max"], pts))
            self._row(rows, "I3_equity_history", r, f"{cnt} events; promoter preferential={fmt(bool(pref))}", pts,
                      f"{r['base']} + {r['per_event']} x {cnt} events"
                      f"{' - ' + str(r['preferential_penalty']) + ' (preferential/warrants to promoters)' if pref else ''}, capped 0..{r['max']}")

        self.simple(rows, "I4_proposed_dilution", "integrity.proposed_dilution_pct")

        pledge = self.simple(rows, "I5_pledge", "integrity.pledge_pct_of_promoter_holding")
        if pledge is not None:
            if pledge >= self.c["kill_switches"]["pledge_pct_ge"]:
                self.kills.append(f"Promoter pledge {fmt(pledge)}% >= {self.c['kill_switches']['pledge_pct_ge']}% of holding")
            elif pledge > 25:
                self.warnings.append(f"Promoter pledge {fmt(pledge)}% of holding - market rarely gives full valuation")

        # I6 promoter pay as % PAT
        r = R["I6_promoter_pay"]
        pay = get(d, "integrity.promoter_remuneration_cr")
        self.inputs_checked += 1
        if pay is None or not self.pat:
            self._neutral(rows, "I6_promoter_pay", r, "integrity.promoter_remuneration_cr / market.pat_ttm_cr")
        else:
            pct = 100.0 * pay / self.pat if self.pat > 0 else float("inf")
            pts, why = step_points(pct, r)
            ratio = get(d, "integrity.md_to_median_employee_ratio")
            extra = ""
            if ratio is not None and ratio > r["md_median_ratio_limit"]:
                pts = max(0, pts - r["md_median_ratio_penalty"])
                extra = f"; MD:median-employee pay {fmt(ratio,0)}x > {r['md_median_ratio_limit']}x -> -{r['md_median_ratio_penalty']}"
            self._row(rows, "I6_promoter_pay", r, round(pct, 2), pts,
                      f"{fmt(pay)} cr / PAT {fmt(self.pat)} cr = {fmt(pct)}% {why} {table_text(r)}{extra}")
            if pct > 8:
                self.warnings.append(f"Promoter remuneration {fmt(pct)}% of PAT - possible skimming; prefer dividends over salary")

        # I7 auditor
        r = R["I7_auditor"]
        tier = get(d, "integrity.auditor_tier")
        fee = get(d, "integrity.audit_fee_cr")
        peer = get(d, "integrity.peer_median_audit_fee_pct_revenue")
        redflag = get(d, "integrity.auditor_red_flag", False)
        self.inputs_checked += 1
        if tier is None and fee is None:
            self._neutral(rows, "I7_auditor", r, "integrity.auditor_tier / audit_fee_cr")
        elif redflag:
            self._row(rows, "I7_auditor", r, "red flag", 0,
                      "qualified opinion / mid-term resignation / going-concern emphasis -> 0")
            self.warnings.append("Auditor red flag (qualification, resignation or going-concern emphasis)")
        else:
            tp = r["tier_points"].get(tier, r["max"] * 0.0) if tier else (r["max"] - r["fee_points"]) * 0.5
            fee_pts, fee_why = r["fee_points"] * 0.5, "fee unknown -> half credit"
            if fee is not None and self.rev:
                fpct = 100.0 * fee / self.rev
                if peer:
                    ratio = fpct / peer
                    ok = r["peer_ratio_min"] <= ratio <= r["peer_ratio_max"]
                    fee_why = f"fee {fmt(fpct,4)}% of rev = {fmt(ratio)}x peer median (ok band {r['peer_ratio_min']}-{r['peer_ratio_max']}x)"
                else:
                    ok = r["fee_pct_rev_min"] <= fpct <= r["fee_pct_rev_max"]
                    fee_why = f"fee {fmt(fpct,4)}% of rev (ok band {r['fee_pct_rev_min']}-{r['fee_pct_rev_max']}%)"
                fee_pts = r["fee_points"] if ok else 0
                if not ok:
                    self.warnings.append(f"Audit fee outside sane band: {fee_why} - too low = rubber-stamp audit, too high = independence risk")
            self._row(rows, "I7_auditor", r, f"tier={tier}; fee={fmt(fee)} cr", tp + fee_pts,
                      f"tier {tier} -> {tp}; {fee_why} -> {fee_pts}")

        # I8 RPT
        r = R["I8_rpt"]
        rpt = get(d, "integrity.rpt_pct_revenue")
        sister = get(d, "integrity.sister_concern_same_business", False)
        self.inputs_checked += 1
        if rpt is None:
            self._neutral(rows, "I8_rpt", r, "integrity.rpt_pct_revenue")
        else:
            pts, why = step_points(rpt, r)
            extra = ""
            if sister:
                pts = max(0, pts - r["sister_concern_penalty"])
                extra = f"; sister concern in same line of business -> -{r['sister_concern_penalty']}"
                self.warnings.append("Promoter sister concern in the same line of business (supplier/distributor)")
            self._row(rows, "I8_rpt", r, rpt, pts, f"{fmt(rpt)}% {why} {table_text(r)}{extra}")

        # I9 royalty
        r = R["I9_royalty"]
        rp = get(d, "integrity.royalty_pct_revenue")
        rec = get(d, "integrity.royalty_recipient")
        self.inputs_checked += 1
        if rp is None and rec is None:
            self._neutral(rows, "I9_royalty", r, "integrity.royalty_pct_revenue / royalty_recipient")
        elif rec == "promoter_entity":
            pts = r["promoter_entity"]
            why = f"{fmt(rp) + '%' if rp is not None else 'amount unknown'} to promoter-owned entity -> 0"
            self.warnings.append(f"Royalty/brand fee ({fmt(rp) + '% of revenue' if rp is not None else 'amount unknown'}) paid to promoter entity - value leakage to minority")
            self._row(rows, "I9_royalty", r, f"{fmt(rp)}% -> {rec}", pts, why)
        elif rec == "foreign_tech_parent" and rp is None:
            self.missing.append("integrity.royalty_pct_revenue")
            self._row(rows, "I9_royalty", r, f"n/a -> {rec}", r["foreign_tech_parent_le3"],
                      "paid to genuine tech/brand parent, % unknown -> scored as <=3% band", True)
        else:
            rp = rp or 0
            if rec in (None, "none") or rp == 0:
                pts, why = r["none"], "no royalty/brand fee"
            elif rec == "foreign_tech_parent":
                pts = r["foreign_tech_parent_le3"] if rp <= 3 else r["foreign_tech_parent_gt3"]
                why = f"{fmt(rp)}% to genuine technology/brand parent ({'<=3%' if rp <= 3 else '>3%'})"
            else:
                pts, why = r["promoter_entity"], f"{fmt(rp)}% to promoter-owned entity without real technology"
                self.warnings.append(f"Royalty {fmt(rp)}% of revenue paid to promoter entity - value leakage to minority")
            self._row(rows, "I9_royalty", r, f"{fmt(rp)}% -> {rec}", pts, why)

        # ---- capability
        exp_ = get(d, "capability.exports_pct_revenue")
        imp_ = get(d, "capability.imports_pct_revenue")
        if exp_ is None or imp_ is None:
            self.inputs_checked += 1
            self._neutral(rows, "C1_net_export", R["C1_net_export"], "capability.exports_pct_revenue / imports_pct_revenue")
        else:
            self.simple(rows, "C1_net_export", "capability.exports_pct_revenue", value=exp_ - imp_,
                        extra=f" (exports {fmt(exp_)}% - imports {fmt(imp_)}%)")

        r = R["C2_net_debt_equity"]
        nde = get(d, "capability.net_debt_to_equity")
        if self.is_fin:
            self.inputs_checked += 1
            self._row(rows, "C2_net_debt_equity", r, nde, r["max"] * 0.5,
                      "financial company: leverage is the business model -> 50% credit (judge via asset quality separately)")
        else:
            v = self.simple(rows, "C2_net_debt_equity", "capability.net_debt_to_equity")
            if v is not None and v > self.c["kill_switches"]["net_debt_equity_gt"]:
                self.kills.append(f"Net debt/equity {fmt(v)}x > {self.c['kill_switches']['net_debt_equity_gt']}x")

        self.simple(rows, "C3_unhedged_fx_debt", "capability.unhedged_fx_debt_pct_of_debt")

        v = self.simple(rows, "C4_restructuring", "capability.debt_restructurings_count")
        if v is not None and v >= self.c["kill_switches"]["restructurings_ge"]:
            self.kills.append(f"Debt restructured {int(v)} times (market forgives once, not twice)")

        # C5 ROCE - WACC
        r = R["C5_roce_wacc_spread"]
        roce = get(d, "growth.roce_3y_avg_pct")
        kd = get(d, "capability.cost_of_debt_pct", 9.0)
        ke = get(d, "capability.cost_of_equity_pct", 13.0)
        tax = get(d, "capability.tax_rate_pct", 25.0)
        de = get(d, "capability.gross_debt_to_equity")
        if de is None:
            de = max(0.0, nde) if nde is not None else 0.0
        self.inputs_checked += 1
        if roce is None:
            self._neutral(rows, "C5_roce_wacc_spread", r, "growth.roce_3y_avg_pct")
            self.wacc = None
        else:
            wd = de / (1 + de)
            we = 1 - wd
            wacc = we * ke + wd * kd * (1 - tax / 100.0)
            self.wacc = wacc
            spread = roce - wacc
            pts, why = step_points(spread, r)
            self._row(rows, "C5_roce_wacc_spread", r, round(spread, 2), pts,
                      f"WACC = {fmt(we)}x{ke}% + {fmt(wd)}x{kd}%x(1-{tax}%) = {fmt(wacc)}%; "
                      f"ROCE {fmt(roce)}% - WACC = {fmt(spread)}pp {why} {table_text(r)}")

        self.simple(rows, "C6_execution", "capability.execution_hit_rate_pct")

        # ---- wealth distribution
        self.simple(rows, "W1_payout", "wealth.payout_ratio_3y_avg_pct")
        self.payout = get(d, "wealth.payout_ratio_3y_avg_pct")

        r = R["W2_dividend_consistency"]
        yrs = get(d, "wealth.dividend_years_paid_last5")
        self.inputs_checked += 1
        if yrs is None:
            self._neutral(rows, "W2_dividend_consistency", r, "wealth.dividend_years_paid_last5")
        else:
            yrs = max(0, min(5, yrs))
            self._row(rows, "W2_dividend_consistency", r, yrs, r["max"] * yrs / 5,
                      f"{r['max']} x {yrs}/5 (a defined, non-ad-hoc policy)")

        v = self.simple(rows, "W3_unrelated_investment", "wealth.unrelated_investments_pct_networth")
        if v is not None and v > self.c["kill_switches"]["unrelated_investment_pct_networth_gt"]:
            self.kills.append(f"Unrelated-business investments {fmt(v)}% of net worth (capital misallocation)")

        v = self.simple(rows, "W4_large_acquisition", "wealth.largest_acquisition_pct_networth_5y")
        if v is not None and v > self.c["kill_switches"]["acquisition_pct_networth_gt"]:
            self.kills.append(f"Acquisition of {fmt(v)}% of net worth (> {self.c['kill_switches']['acquisition_pct_networth_gt']}%)")

        # ---- investor communication
        r = R["K1_investor_comm"]
        calls = get(d, "communication.earnings_calls_per_year")
        pres = get(d, "communication.investor_presentation")
        iday = get(d, "communication.investor_day_or_plant_visit_2y")
        ir = get(d, "communication.dedicated_ir")
        self.inputs_checked += 1
        if all(x is None for x in (calls, pres, iday, ir)):
            self._neutral(rows, "K1_investor_comm", r, "communication.*")
        else:
            half = 0.5
            c_pts = min(calls, r["max_calls"]) * r["per_call"] if calls is not None else r["max_calls"] * r["per_call"] * half
            p_pts = (r["presentation"] if pres else 0) if pres is not None else r["presentation"] * half
            i_pts = (r["investor_day"] if iday else 0) if iday is not None else r["investor_day"] * half
            ir_pts = (r["dedicated_ir"] if ir else 0) if ir is not None else r["dedicated_ir"] * half
            tot = c_pts + p_pts + i_pts + ir_pts
            unknown = any(x is None for x in (calls, pres, iday, ir))
            self._row(rows, "K1_investor_comm", r, f"calls={fmt(calls,0)}, ppt={fmt(pres)}, day/visit={fmt(iday)}, IR={fmt(ir)}",
                      tot, f"calls {c_pts} + presentation {p_pts} + investor day/plant visit {i_pts} + IR {ir_pts}"
                           f"{' (unknown items at half credit)' if unknown else ''}", unknown)
            if (self.c["kill_switches"]["black_box_zero_communication"] and not unknown and tot == 0):
                self.kills.append("Black box: no earnings calls, presentations, investor meets or IR")

        # ---- liquidity
        r = R["L1_liquidity"]
        fno = get(d, "market.in_fno", False)
        adtv = get(d, "market.adtv_6m_cr")
        self.inputs_checked += 1
        if fno:
            self._row(rows, "L1_liquidity", r, "F&O stock", r["fno_points"], "in F&O segment -> fully liquid")
        elif adtv is None or not self.mcap:
            self._neutral(rows, "L1_liquidity", r, "market.adtv_6m_cr")
        else:
            pct = 100.0 * adtv / self.mcap
            pts, why = step_points(pct, r)
            extra = ""
            if adtv < r["min_adtv_cr"]:
                pts = min(pts, r["cap_if_below_min"])
                extra = f"; ADTV < Rs {r['min_adtv_cr']} cr -> capped at {r['cap_if_below_min']}"
            self._row(rows, "L1_liquidity", r, round(pct, 4), pts,
                      f"ADTV {fmt(adtv)} cr / mcap {fmt(self.mcap,0)} cr = {fmt(pct,4)}%/day {why} {table_text(r)}{extra}")

    # --- growth
    def score_growth(self):
        G = self.c["growth_rules"]
        self.simple(self.grows, "G1_roce", "growth.roce_3y_avg_pct")
        self.simple(self.grows, "G2_fwd_cagr", "growth.pat_cagr_fwd_pct")
        self.simple(self.grows, "G3_hist_cagr", "growth.pat_cagr_5y_hist_pct")
        r = G["G4_structural"]
        self.inputs_checked += 1
        if self.sector_type is None:
            self._neutral(self.grows, "G4_structural", r, "sector_type")
        else:
            pts = r["map"].get(self.sector_type, 0)
            self._row(self.grows, "G4_structural", r, self.sector_type, pts, f"map {r['map']}")

        fwd = get(self.d, "growth.pat_cagr_fwd_pct")
        hist = get(self.d, "growth.pat_cagr_5y_hist_pct")
        if fwd is not None and hist is not None and fwd > hist + 10:
            self.warnings.append(f"Forward growth {fmt(fwd)}% far above 5y history {fmt(hist)}% - check you are not capitalising a cyclical spurt")
        vis = get(self.d, "growth.growth_visibility_years")
        if vis is not None and vis < 3:
            self.warnings.append(f"Growth visibility only {vis} years (want 3-4+ to double profits)")
        if self.sector_type == "cyclical":
            self.warnings.append("Cyclical business: PEG and payout-based PE are not valid; framework is built for structural growers")

    # --- price discipline
    def score_price(self, equal_score):
        H = self.c["hurdles"]
        V = self.c["valuation"]
        P = self.c["price_score"]
        d = self.d
        out = {}
        g = get(d, "growth.pat_cagr_fwd_pct")
        pe = self.pe
        n = V["horizon_years"]
        dy = get(d, "market.dividend_yield_pct", 0.0) or 0.0
        exit_pe = get(d, "market.exit_pe")
        exit_basis = "10y median PE (input)"
        if exit_pe is None:
            exit_pe = pe
            exit_basis = "no exit_pe given -> assumes PE stays at current (no re-rating)"
        out.update(pe=pe, fwd_growth=g, exit_pe=exit_pe, exit_basis=exit_basis, dividend_yield=dy, horizon=n)

        # cap tier + required return
        tier = None
        if self.mcap is not None:
            for t in self.c["cap_tiers"]:
                if self.mcap >= t["min_mcap_cr"]:
                    tier = t
                    break
        grade = None
        for q in self.c["quality_grades"]:
            if equal_score >= q["min_score"]:
                grade = q
                break
        out["cap_tier"] = tier["name"] if tier else None
        out["base_return"] = tier["base_return_pct"] if tier else None
        out["grade"] = grade["grade"]
        out["risk_premium"] = grade["risk_premium_pct"]
        req = None
        if tier and grade["risk_premium_pct"] is not None:
            req = tier["base_return_pct"] + grade["risk_premium_pct"]
        out["required_return"] = req

        if pe is None or g is None:
            out.update(peg=None, expected_return=None, price_score=None)
            return out

        peg = pe / g if g > 0 else float("inf")
        out["peg"] = peg
        if peg <= H["peg_multibagger_max"]:
            zone = "< 1 : multibagger zone"
        elif peg <= H["peg_buy_max"]:
            zone = "1-2 : buy zone"
        elif peg <= H["peg_avoid_above"]:
            zone = "2-3 : caution, bordering risk over reward"
        else:
            zone = "> 3 : serious red flag (sell / avoid)"
        out["peg_zone"] = zone

        gr = g / 100.0
        exp = ((1 + gr) * (exit_pe / pe) ** (1.0 / n) - 1) * 100 + dy
        out["expected_return"] = exp
        out["expected_formula"] = (f"((1+{fmt(g)}%) x ({fmt(exit_pe)}/{fmt(pe)})^(1/{n}) - 1) + div yield {fmt(dy)}% = {fmt(exp)}%")
        out["margin_pp"] = exp - req if req is not None else None

        # growth sensitivity: the verdict usually hinges on the forward-growth input
        sens = []
        for dg in (-4, 0, 4):
            gg = g + dg
            if gg <= 0:
                continue
            e = ((1 + gg / 100.0) * (exit_pe / pe) ** (1.0 / n) - 1) * 100 + dy
            ok = (gg >= H["fwd_pat_cagr_min_pct"] and pe / gg <= H["peg_buy_max"]
                  and req is not None and e >= req)
            sens.append({"growth": gg, "peg": pe / gg, "expected": e, "price_ok": ok})
        out["sensitivity"] = sens

        # 5-yr cumulative profit test
        if self.pat and self.mcap:
            yrs = V["cumulative_profit_years"]
            cum = sum(self.pat * (1 + gr) ** t for t in range(1, yrs + 1))
            out["cum_profit_5y_cr"] = cum
            out["cum_profit_to_mcap"] = cum / self.mcap
        # payout-based theoretical PE (structural only)
        if self.payout is not None:
            tpe = self.payout / V["market_dividend_yield_pct"]
            out["theoretical_pe"] = tpe
            # The payout method only makes sense for mature, high-payout structural businesses (HUL, IT services)
            if (self.sector_type == "structural" and not self.is_fin
                    and self.payout >= V.get("theoretical_pe_min_payout_pct", 50) and pe > tpe):
                self.warnings.append(f"PE {fmt(pe)} above payout-implied theoretical PE {fmt(tpe)} (payout / market div. yield {V['market_dividend_yield_pct']}%)")

        # entry prices
        eps = None
        price = get(d, "market.price")
        if price and pe:
            eps = price / pe
        out["eps_ttm"] = eps
        if eps:
            out["price_at_peg2"] = H["peg_buy_max"] * g * eps if g > 0 else None
            if req is not None:
                k = (1 + (req - dy) / 100.0) / (1 + gr)
                pe_req = exit_pe / (k ** n) if k > 0 else None
                out["pe_for_required_return"] = pe_req
                out["price_for_required_return"] = pe_req * eps if pe_req else None
            cands = [x for x in (out.get("price_at_peg2"), out.get("price_for_required_return")) if x]
            out["max_buy_price"] = min(cands) if cands else None

        # price score
        pp = P["peg_points"]
        if peg <= pp[0][0]:
            peg_pts = pp[0][1]
        elif peg <= pp[1][0]:
            peg_pts = lerp(peg, pp[0][0], pp[0][1], pp[1][0], pp[1][1])
        elif peg <= pp[2][0]:
            peg_pts = lerp(peg, pp[1][0], pp[1][1], pp[2][0], pp[2][1])
        else:
            peg_pts = 0
        if out["margin_pp"] is None:
            m_pts = 0
        else:
            m = max(P["margin_zero_at_pp"], min(P["margin_full_at_pp"], out["margin_pp"]))
            m_pts = lerp(m, P["margin_zero_at_pp"], 0, P["margin_full_at_pp"], P["margin_component_max"])
        out["price_peg_pts"] = round(peg_pts, 2)
        out["price_margin_pts"] = round(m_pts, 2)
        out["price_score"] = round(peg_pts + m_pts, 1)
        return out

    # --- verdict
    def verdict(self, equal, growth_score, price):
        H = self.c["hurdles"]
        roce = get(self.d, "growth.roce_3y_avg_pct")
        g = get(self.d, "growth.pat_cagr_fwd_pct")
        peg = price.get("peg")
        if self.kills:
            return "REJECT", "Red-flag kill switch triggered"
        if equal < H["equal_min_score"]:
            return "REJECT", f"E-QUAL management score {fmt(equal,1)} < {H['equal_min_score']}"
        if roce is not None and roce < H["roce_min_pct"]:
            return "REJECT", f"ROCE {fmt(roce)}% < {H['roce_min_pct']}% cost of capital (value-trap risk)"
        if self.sector_type == "cyclical":
            return "OUT OF FRAMEWORK", "Cyclical earnings - growth extrapolation and PEG not valid"
        if g is not None and g < H["fwd_pat_cagr_min_pct"]:
            return "PASS", f"Forward PAT CAGR {fmt(g)}% < {H['fwd_pat_cagr_min_pct']}% (profits won't double in ~4 years)"
        if peg is None:
            return "INCOMPLETE", "Need PE and forward growth to apply purchase-price discipline"
        if peg > H["peg_avoid_above"]:
            return "AVOID", f"PEG {fmt(peg)} > {H['peg_avoid_above']} - overpriced"
        exp, req = price.get("expected_return"), price.get("required_return")
        if peg <= H["peg_buy_max"] and req is not None and exp >= req:
            mb = peg <= H["peg_multibagger_max"] and (price.get("cum_profit_to_mcap") or 0) >= 1
            return ("BUY - MULTIBAGGER SETUP" if mb else "BUY"), \
                f"PEG {fmt(peg)} and expected {fmt(exp)}% >= required {fmt(req)}%"
        return "WATCHLIST", "Quality and growth pass; price does not yet meet discipline - wait for max buy price"

    def run(self):
        self.derived()
        self.score_equal()
        self.score_growth()
        equal = round(sum(r["points"] for r in self.rows), 1)
        growth = round(sum(r["points"] for r in self.grows), 1)
        pillars = {}
        for r in self.rows:
            pillars.setdefault(r["pillar"], [0, 0])
            pillars[r["pillar"]][0] += r["points"]
            pillars[r["pillar"]][1] += r["max"]
        price = self.score_price(equal)
        kill_fields = {
            "integrity.pledge_pct_of_promoter_holding": "pledge",
            "capability.debt_restructurings_count": "restructuring history",
            "wealth.largest_acquisition_pct_networth_5y": "large acquisitions",
            "wealth.unrelated_investments_pct_networth": "unrelated investments",
        }
        if not self.is_fin:
            kill_fields["capability.net_debt_to_equity"] = "net debt/equity"
        unchecked = [v for k, v in kill_fields.items() if get(self.d, k) is None]
        if unchecked:
            self.warnings.insert(0, "Kill-switch inputs missing, red flags NOT checked for: " + ", ".join(unchecked)
                                 + ". Do not act on a BUY until these are verified.")
        W =self.c["composite_weights"]
        ps = price.get("price_score")
        composite = round(W["equal"] * equal + W["growth"] * growth + W["price"] * (ps or 0), 1)
        verdict, reason = self.verdict(equal, growth, price)
        unver = sum(1 for r in self.rows + self.grows if r["status"] == "UNVERIFIED")
        total = len(self.rows) + len(self.grows)
        completeness = round(100.0 * (total - unver) / total, 0)
        provisional = completeness < self.c["provisional_if_completeness_below_pct"]
        return {
            "company": get(self.d, "company", "Unknown"),
            "as_of": get(self.d, "as_of"),
            "equal_score": equal,
            "growth_score": growth,
            "price_score": ps,
            "composite_score": composite,
            "verdict": verdict + (" (PROVISIONAL)" if provisional else ""),
            "verdict_reason": reason,
            "data_completeness_pct": completeness,
            "pillars": {k: [round(v[0], 2), v[1]] for k, v in pillars.items()},
            "equal_rows": self.rows,
            "growth_rows": self.grows,
            "price": price,
            "kill_switches": self.kills,
            "warnings": self.warnings,
            "missing_inputs": self.missing,
            "sources": get(self.d, "sources", {}),
        }


# ----------------------------------------------------------------- report
def report_md(res):
    p = res["price"]
    L = []
    L.append(f"# E-QUAL Framework Scorecard - {res['company']}")
    if res.get("as_of"):
        L.append(f"_Data as of {res['as_of']}_")
    L.append("")
    L.append(f"## Verdict: **{res['verdict']}**")
    L.append(f"{res['verdict_reason']}")
    L.append("")
    L.append("| Score | Value |")
    L.append("|---|---|")
    L.append(f"| E-QUAL management quality (0-100) | **{fmt(res['equal_score'],1)}** - grade {p.get('grade')} |")
    L.append(f"| Earnings growth potential (0-100) | **{fmt(res['growth_score'],1)}** |")
    L.append(f"| Purchase-price discipline (0-100) | **{fmt(res['price_score'],1)}** |")
    L.append(f"| Composite (40/30/30) | **{fmt(res['composite_score'],1)}** |")
    L.append(f"| Data completeness | {fmt(res['data_completeness_pct'],0)}% |")
    L.append("")
    if res["kill_switches"]:
        L.append("## Kill switches triggered")
        for k in res["kill_switches"]:
            L.append(f"- {k}")
        L.append("")
    L.append("## Step 1 - E-QUAL management quality")
    L.append("| Pillar | Points | Max |")
    L.append("|---|---|---|")
    for k, (pts, mx) in res["pillars"].items():
        L.append(f"| {k} | {fmt(pts)} | {fmt(mx,1)} |")
    L.append("")
    L.append("| ID | Rule | Input | Points | Max | Calculation | Status |")
    L.append("|---|---|---|---|---|---|---|")
    for r in res["equal_rows"]:
        L.append(f"| {r['id']} | {r['label']} | {fmt(r['value'])} | {fmt(r['points'])} | {fmt(r['max'],1)} | {r['rule']} | {r['status']} |")
    L.append("")
    L.append("## Step 2 - Earnings growth potential")
    L.append("| ID | Rule | Input | Points | Max | Calculation | Status |")
    L.append("|---|---|---|---|---|---|---|")
    for r in res["growth_rows"]:
        L.append(f"| {r['id']} | {r['label']} | {fmt(r['value'])} | {fmt(r['points'])} | {fmt(r['max'],0)} | {r['rule']} | {r['status']} |")
    L.append("")
    L.append("## Step 3 - Purchase-price discipline")
    L.append("| Metric | Value |")
    L.append("|---|---|")
    L.append(f"| Market-cap tier | {p.get('cap_tier')} (base return {fmt(p.get('base_return'),0)}%) |")
    L.append(f"| Quality grade / risk premium | {p.get('grade')} / +{fmt(p.get('risk_premium'),0)}% |")
    L.append(f"| **Required return** | **{fmt(p.get('required_return'),1)}%** |")
    L.append(f"| PE (TTM) | {fmt(p.get('pe'))} |")
    L.append(f"| Forward PAT CAGR | {fmt(p.get('fwd_growth'))}% |")
    L.append(f"| **PEG** | **{fmt(p.get('peg'))}** ({p.get('peg_zone','n/a')}) |")
    L.append(f"| Exit PE | {fmt(p.get('exit_pe'))} - {p.get('exit_basis')} |")
    L.append(f"| **Expected return ({p.get('horizon')}y CAGR)** | **{fmt(p.get('expected_return'),1)}%** |")
    if p.get("expected_formula"):
        L.append(f"| Formula | {p['expected_formula']} |")
    L.append(f"| Expected - required | {fmt(p.get('margin_pp'),1)} pp |")
    if p.get("cum_profit_to_mcap") is not None:
        L.append(f"| Next-5y cumulative PAT / market cap | {fmt(p['cum_profit_to_mcap'])}x ({fmt(p['cum_profit_5y_cr'],0)} cr) - >=1x = multibagger signal |")
    if p.get("theoretical_pe") is not None:
        L.append(f"| Payout-implied theoretical PE (structural only) | {fmt(p['theoretical_pe'],1)} |")
    if p.get("price_at_peg2") is not None:
        L.append(f"| Price at PEG = 2 | Rs {fmt(p['price_at_peg2'])} |")
    if p.get("price_for_required_return") is not None:
        L.append(f"| Price that delivers required return | Rs {fmt(p['price_for_required_return'])} |")
    if p.get("max_buy_price") is not None:
        L.append(f"| **Max buy price (lower of the two)** | **Rs {fmt(p['max_buy_price'])}** |")
    L.append(f"| Price score | PEG component {fmt(p.get('price_peg_pts'))}/60 + return-margin component {fmt(p.get('price_margin_pts'))}/40 |")
    L.append("")
    if p.get("sensitivity"):
        L.append("**Forward-growth sensitivity** (growth >= hurdle, PEG <= 2 and expected >= required?)")
        L.append("")
        L.append("| Fwd PAT CAGR | PEG | Expected return | Growth + price tests pass? |")
        L.append("|---|---|---|---|")
        for s in p["sensitivity"]:
            L.append(f"| {fmt(s['growth'],1)}% | {fmt(s['peg'])} | {fmt(s['expected'],1)}% | {'yes' if s['price_ok'] else 'no'} |")
        L.append("")
    if res["warnings"]:
        L.append("## Warnings (not kill switches)")
        for w in res["warnings"]:
            L.append(f"- {w}")
        L.append("")
    if res["missing_inputs"]:
        L.append("## Data gaps (scored at neutral credit - verify to firm up)")
        for m in res["missing_inputs"]:
            L.append(f"- `{m}`")
        L.append("")
    L.append("## Exit triggers to monitor")
    L.append("- PAT growth falls below 18% on a sustained basis (growth thesis broken)")
    L.append("- Governance event: pledge rising, RPT/royalty leakage, auditor exit, etc. (re-score E-QUAL)")
    L.append("- PEG > 3 or euphoric valuation")
    L.append("")
    if res["sources"]:
        L.append("## Sources")
        for k, v in res["sources"].items():
            L.append(f"- {k}: {v}")
        L.append("")
    L.append("_Framework output, not investment advice. Every point above is traceable to an input and a rule in config.json._")
    return "\n".join(L)


def compare_md(results):
    L = ["# E-QUAL Framework - Comparison", "",
         "| Company | Verdict | E-QUAL | Growth | Price | Composite | PEG | Exp. ret % | Req. ret % | Max buy Rs | Kills | Data % |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = ["BUY - MULTIBAGGER SETUP", "BUY", "WATCHLIST", "AVOID", "PASS", "INCOMPLETE", "OUT OF FRAMEWORK", "REJECT"]

    def rank(x):
        v = x["verdict"].replace(" (PROVISIONAL)", "")
        return (order.index(v) if v in order else len(order), -x["composite_score"])

    for r in sorted(results, key=rank):
        p = r["price"]
        L.append(f"| {r['company']} | {r['verdict']} | {fmt(r['equal_score'],1)} | {fmt(r['growth_score'],1)} | "
                 f"{fmt(r['price_score'],1)} | **{fmt(r['composite_score'],1)}** | {fmt(p.get('peg'))} | "
                 f"{fmt(p.get('expected_return'),1)} | {fmt(p.get('required_return'),1)} | {fmt(p.get('max_buy_price'))} | "
                 f"{len(r['kill_switches'])} | {fmt(r['data_completeness_pct'],0)} |")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="E-QUAL stock framework scorer")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--out", help="write markdown report here")
    ap.add_argument("--json", help="write full JSON result here")
    ap.add_argument("--compare", action="store_true", help="print comparison table for multiple inputs")
    ap.add_argument("--set", action="append", default=[], metavar="path=value",
                    help="override an input for sensitivity, e.g. --set growth.pat_cagr_fwd_pct=20 --set sector_type=structural")
    a = ap.parse_args()
    cfg = load_json(a.config)

    def apply_overrides(d):
        for s in a.set:
            path, _, raw = s.partition("=")
            try:
                val = json.loads(raw)
            except ValueError:
                val = raw
            cur = d
            keys = path.split(".")
            for k in keys[:-1]:
                cur = cur.setdefault(k, {})
            cur[keys[-1]] = val
        if a.set:
            d["company"] = f"{d.get('company', 'Unknown')} [what-if: {', '.join(a.set)}]"
        return d

    results = [Scorer(apply_overrides(load_json(p)), cfg).run() for p in a.inputs]

    if a.compare or len(results) > 1:
        md = compare_md(results) + "\n\n" + "\n\n---\n\n".join(report_md(r) for r in results)
    else:
        md = report_md(results[0])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
        print(md)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(results if len(results) > 1 else results[0], f, indent=2, default=str)


if __name__ == "__main__":
    main()
