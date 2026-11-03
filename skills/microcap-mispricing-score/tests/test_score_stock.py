"""
Verification suite. Every expected number below is worked out by hand in the
comment next to it, so a reviewer can check the framework maths without
trusting the code. Run:  python -m unittest discover -s tests -v
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import score_stock as S  # noqa: E402

CFG = S.load_json(S.DEFAULT_CONFIG)


def base(**over):
    """Minimal 5-year stable company; override pieces per test."""
    years = []
    for i, y in enumerate(range(2021, 2026)):
        years.append({"year": y, "sales": 100.0, "ebitda": 20.0, "depreciation": 4.0, "interest": 2.0,
                      "pat": 10.5, "ocf": 16.0, "net_worth": 100.0, "total_debt": 10.0, "cash": 5.0,
                      "receivables": 15.0})
    d = {"company": "T", "business_type": "stable",
         "market": {"market_cap": 150.0, "total_debt": 10.0, "cash_and_investments": 5.0},
         "annual": years}
    d.update(over)
    return d


class Formulas(unittest.TestCase):
    def test_enterprise_value_and_lease_exclusion(self):
        # EV = equity + debt - cash = 150 + 10 - 5 = 155
        m, _, _ = S.run(base(), CFG)
        self.assertAlmostEqual(m["ev"], 155.0)
        # lease 4 inside debt 10 is stripped: 150 + 6 - 5 = 151
        d = base(); d["market"]["lease_liabilities"] = 4.0
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["ev"], 151.0)

    def test_six_multiples(self):
        m, _, _ = S.run(base(), CFG)
        self.assertAlmostEqual(m["ev_ebitda"], 155 / 20)
        self.assertAlmostEqual(m["ev_ebit"], 155 / 16)          # EBIT = 20 - 4
        self.assertAlmostEqual(m["pe"], 150 / 10.5)
        self.assertAlmostEqual(m["ev_ocf"], 155 / 16)
        self.assertAlmostEqual(m["ps"], 1.5)
        self.assertAlmostEqual(m["ev_sales"], 1.55)

    def test_negative_denominator_gives_none(self):
        d = base(); d["annual"][-1]["pat"] = -3
        m, _, notes = S.run(d, CFG)
        self.assertIsNone(m["pe"])
        self.assertTrue(any("pe not meaningful" in n for n in notes))

    def test_one_off_strip(self):
        # PAT 10.5 + one-off expense 20 x (1-0.25) = 25.5 ; one-off gain 4 (already taxed) => 21.5
        d = base(one_offs=[{"amount": 20, "type": "expense"},
                           {"amount": 4, "type": "gain", "tax_effected": True}])
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["trailing_adj_pat"], 21.5)

    def test_cyclically_adjusted_pe(self):
        # margins 10,20,10,20,10 => avg 14%. TTM sales 200 => EBITDA 28.
        # PBT = 28 - D&A 4 - interest 4 = 20 ; PAT = 15 ; mcap 150 => CAPE 10.
        d = base(business_type="cyclical")
        for r, mg in zip(d["annual"], [10, 20, 10, 20, 10]):
            r["ebitda"] = mg
        d["ttm"] = {"sales": 200, "ebitda": 10, "depreciation": 4, "interest": 4, "pat": 1}
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["avg_ebitda_margin_pct"], 14.0)
        self.assertAlmostEqual(m["cyclically_adjusted_pat"], 15.0)
        self.assertAlmostEqual(m["cyclically_adjusted_pe"], 10.0)

    def test_tax_override(self):
        # same CAPE case at 5% tax: PAT = 20 x 0.95 = 19 => CAPE = 150/19
        d = base(business_type="cyclical", tax_rate_pct=5)
        for r, mg in zip(d["annual"], [10, 20, 10, 20, 10]):
            r["ebitda"] = mg
        d["ttm"] = {"sales": 200, "ebitda": 10, "depreciation": 4, "interest": 4, "pat": 1}
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["cyclically_adjusted_pe"], 150 / 19)

    def test_book_value_implied_pe_video_example(self):
        # Video: at 1x book a 20% ROE business costs 5x earnings; 15% ROE => ~6.7x.
        d = base(forward={"normalised_roe_pct": 20})
        d["market"]["market_cap"] = 100.0                      # = net worth 100 => P/B 1
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["implied_pe_from_book"], 5.0)
        d["forward"]["normalised_roe_pct"] = 15
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["implied_pe_from_book"], 100 / 15)

    def test_peg_video_example(self):
        # Video: 50% grower bought at 30 P/E => PEG 0.6
        d = base(forward={"years_out": 1, "pat": 15.0})       # adj PAT 10 -> 15 = 50% growth
        for r in d["annual"]:
            r["pat"] = 10.0
        d["market"]["market_cap"] = 300.0                      # 300/10 = 30x
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["forward_pat_cagr_pct"], 50.0)
        self.assertAlmostEqual(m["peg"], 0.6)

    def test_earnings_gap(self):
        # past 3y PAT 10 -> 13.31 = 10%/yr ; forward 13.31 -> 19.17 over 2y = 20%/yr ; gap = 10pp
        d = base(forward={"years_out": 2, "pat": 13.31 * 1.44})
        for r, p in zip(d["annual"], [9, 10, 11, 12.1, 13.31]):
            r["pat"] = p
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["past3y_pat_cagr_pct"], 10.0, places=4)
        self.assertAlmostEqual(m["earnings_gap_pp"], 10.0, places=4)

    def test_ocf_quality_and_receivables(self):
        # 5y OCF 16 / EBITDA 20 => 0.8 conversion; EV/avg OCF = 155/16
        d = base()
        d["annual"][-1]["sales"] = 110.0                     # +10% sales
        d["annual"][-1]["receivables"] = 14.0                # debtors fell in absolute terms
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["ocf_ebitda_conversion_5y"], 0.8)
        self.assertAlmostEqual(m["ev_ocf_normalised"], 155 / 16)
        self.assertTrue(m["receivables_fell_while_sales_grew"])
        self.assertLess(m["receivables_minus_sales_growth_pp"], 0)

    def test_percentile_vs_own_history(self):
        # history EV/Sales = 1,2,3,4,5 ; current 1.55 => 1 of 5 values <= 1.55 => 20th pctile
        d = base()
        for r, mc in zip(d["annual"], [95, 195, 295, 395, 495]):   # EV_y = mc + 10 - 5
            r["market_cap_year_end"] = mc
        m, _, _ = S.run(d, CFG)
        self.assertAlmostEqual(m["pctile_ev_sales"], 20.0)


class OneOffVsHabit(unittest.TestCase):
    def test_ad_cut_flattering_margin(self):
        d = base()
        d["annual"].append({**d["annual"][-1], "year": 2026})
        for r, a in zip(d["annual"], [10, 10, 10, 10, 10, 5]):
            r["expense_items"] = {"advertising": a}
        m, _, _ = S.run(d, CFG)
        kinds = {f["kind"] for f in m["expense_flags"]}
        self.assertIn("cut_boosting_margin", kinds)
        self.assertEqual(m["expense_flag_count"], 1)

    def test_spike_vs_persistent(self):
        d = base()
        for y in (2026, 2027, 2028):
            d["annual"].append({**d["annual"][-1], "year": y})
        spike = [5, 5, 5, 5, 5, 5, 5, 8]          # one year elevated => one-off candidate
        habit = [5, 5, 5, 5, 5, 8, 8, 8]          # three years elevated => habit
        for r, a, b in zip(d["annual"], spike, habit):
            r["expense_items"] = {"packaging": a, "warranty": b}
        m, _, _ = S.run(d, CFG)
        k = {f["item"]: f["kind"] for f in m["expense_flags"]}
        self.assertEqual(k["packaging"], "one_off_spike")
        self.assertEqual(k["warranty"], "persistent_increase")

    def test_peer_outlier(self):
        d = base(peers=[{"expense_pct": {"advertising": 10}}, {"expense_pct": {"advertising": 12}},
                        {"expense_pct": {"advertising": 13}}])
        for r in d["annual"]:
            r["expense_items"] = {"advertising": 4}
        m, _, _ = S.run(d, CFG)
        self.assertIn("peer_outlier_low", {f["kind"] for f in m["expense_flags"]})


class Scoring(unittest.TestCase):
    def test_weights_sum_to_100_for_every_business_type(self):
        other = sum(r["max"] for rules in CFG["pillars"].values() for r in rules)
        for bt, rules in CFG["valuation_rules"].items():
            self.assertEqual(sum(r["max"] for r in rules) + other, 100, bt)
            for r in rules:
                if "bands" in r:
                    self.assertEqual(max(p for _, p in r["bands"]), r["max"], r["metric"])

    def test_band_scorer(self):
        rule = {"direction": "lower_better", "bands": [[10, 10], [15, 6], [20, 3]], "max": 10}
        self.assertEqual(S.score_rule(rule, 9.9), 10)
        self.assertEqual(S.score_rule(rule, 10), 10)
        self.assertEqual(S.score_rule(rule, 14), 6)
        self.assertEqual(S.score_rule(rule, 25), 0)
        self.assertIsNone(S.score_rule(rule, None))

    def test_rebasing_on_missing_data(self):
        m, s, _ = S.run(base(), CFG)
        earned = sum(p["earned"] for p in s["pillars"].values())
        possible = sum(p["possible"] for p in s["pillars"].values())
        self.assertLess(s["coverage"], 1.0)
        self.assertAlmostEqual(s["score"], round(earned / possible * 100, 1))

    def test_kill_switch_caps_score(self):
        ex = S.load_json(ROOT / "assets/examples/cyclical_trough_example.json")
        _, clean, _ = S.run(ex, CFG)
        bad = copy.deepcopy(ex); bad["governance"]["revenue_inflation_found"] = True
        _, s, _ = S.run(bad, CFG)
        self.assertGreater(clean["score"], 60)
        self.assertLessEqual(s["score"], CFG["kill_switches"]["score_cap"])
        self.assertTrue(s["verdict"].startswith("AVOID"))
        self.assertIn("UNINVESTABLE", s["classification"])

    def test_lavish_spend_kill(self):
        # Video: 300 cr aircraft at a 1,500 cr market cap = 20% of market cap
        ex = S.load_json(ROOT / "assets/examples/cyclical_trough_example.json")
        ex["governance"]["promoter_vanity_spend"] = 0.20 * ex["market"]["market_cap"]
        _, s, _ = S.run(ex, CFG)
        self.assertTrue(s["kill_switches"])

    def test_old_vanity_spend_is_penalty_not_kill(self):
        ex = S.load_json(ROOT / "assets/examples/cyclical_trough_example.json")
        ex["governance"]["promoter_vanity_spend"] = 0.20 * ex["market"]["market_cap"]
        ex["governance"]["promoter_vanity_spend_years_ago"] = 7
        m, s, _ = S.run(ex, CFG)
        self.assertFalse(s["kill_switches"])
        lav = [r for r in s["pillars"]["governance_and_history"]["rules"] if r["metric"] == "lavish_spend_pct_mcap"][0]
        self.assertEqual(lav["points"], 0)

    def test_no_valuation_evidence_is_flagged(self):
        d = base(business_type="capex_transition")   # no forward PAT, no history => no valuation rule
        _, s, _ = S.run(d, CFG)
        self.assertTrue(s["verdict"].startswith("INSUFFICIENT DATA"))

    def test_deterministic(self):
        ex = S.load_json(ROOT / "assets/examples/capex_transition_example.json")
        a = S.run(copy.deepcopy(ex), CFG)[1]
        b = S.run(copy.deepcopy(ex), CFG)[1]
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_capex_transition_ignores_trailing_pe(self):
        # 100+ trailing P/E must not, by itself, sink a capex_transition valuation score
        ex = S.load_json(ROOT / "assets/examples/capex_transition_example.json")
        m, s, _ = S.run(ex, CFG)
        self.assertGreater(m["pe"], 100)
        self.assertNotIn("pe", [r["metric"] for r in s["pillars"]["valuation"]["rules"]])
        self.assertGreaterEqual(s["pillars"]["valuation"]["pct"], 60)

    def test_cheap_without_change_is_value_trap(self):
        ex = S.load_json(ROOT / "assets/examples/cyclical_trough_example.json")
        ex["qualitative"]["change_identified"] = False
        ex["qualitative"]["seller_concern"] = "structural"
        ex["forward"] = {"years_out": 2, "pat_cagr_pct": 0}
        _, s, _ = S.run(ex, CFG)
        self.assertIn("VALUE TRAP", s["classification"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            S.run({"business_type": "banana", "market": {}, "annual": []}, CFG)

    def test_cli_writes_outputs(self):
        with tempfile.TemporaryDirectory() as t:
            rc = S.main([str(ROOT / "assets/examples/cyclical_trough_example.json"),
                         "--json", f"{t}/r.json", "--md", f"{t}/r.md"])
            self.assertEqual(rc, 0)
            out = json.loads(Path(f"{t}/r.json").read_text())
            self.assertIn("score", out["result"])
            self.assertIn("Rule-by-rule audit trail", Path(f"{t}/r.md").read_text())


class ScreenerImport(unittest.TestCase):
    def test_synthetic_workbook(self):
        import datetime as dt
        import openpyxl
        import screener_to_json as I
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Data Sheet"
        yrs = [dt.datetime(y, 3, 31) for y in range(2020, 2026)]
        rows = [["COMPANY NAME", "Demo Ltd"], ["META"], ["Current Price", 100], ["Market Capitalization", 1000],
                ["PROFIT & LOSS"], ["Report Date", *yrs], ["Sales", *[500] * 6],
                ["Other Income", *[10] * 6], ["Depreciation", *[20] * 6], ["Interest", *[5] * 6],
                ["Profit before tax", *[75] * 6], ["Net profit", *[56] * 6],
                ["Quarters"], ["Report Date", *[dt.datetime(2025, m, 1) for m in (3, 6, 9, 12)]],
                ["Sales", 130, 130, 130, 130], ["Other Income", 2, 2, 2, 2], ["Depreciation", 5, 5, 5, 5],
                ["Interest", 1, 1, 1, 1], ["Profit before tax", 20, 20, 20, 20], ["Net profit", 15, 15, 15, 15],
                ["BALANCE SHEET"], ["Report Date", *yrs], ["Equity Share Capital", *[10] * 6],
                ["Reserves", *[390] * 6], ["Borrowings", *[50] * 6], ["Receivables", *[60] * 6],
                ["Inventory", *[80] * 6], ["Cash & Bank", *[30] * 6],
                ["CASH FLOW:"], ["Report Date", *yrs], ["Cash from Operating Activity", *[70] * 6],
                ["PRICE:", *[80] * 6], ["DERIVED:"], ["Adjusted Equity Shares in Cr", *[10] * 6]]
        for r in rows:
            ws.append(r)
        with tempfile.TemporaryDirectory() as t:
            p = f"{t}/demo.xlsx"; wb.save(p)
            out, rep = I.build(p, "stable")
        a = out["annual"][-1]
        self.assertEqual(len(out["annual"]), 6)
        self.assertAlmostEqual(a["ebitda"], 75 + 5 + 20 - 10)     # 90
        self.assertAlmostEqual(a["net_worth"], 400)
        self.assertAlmostEqual(a["market_cap_year_end"], 800)     # 80 x 10 cr shares
        self.assertAlmostEqual(out["ttm"]["ebitda"], 4 * (20 + 1 + 5 - 2))
        self.assertEqual(out["market"]["market_cap"], 1000)
        self.assertFalse(any(rep["rows_missing"].values()))
        out["governance"] = {}; S.run(out, CFG)                   # imported file scores cleanly


if __name__ == "__main__":
    unittest.main()
