"""Run: python -m unittest discover -s tests -v   (from the skill folder)"""
import glob
import json
import os
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import score_setup as S  # noqa: E402
import compute_rs as R  # noqa: E402
import chart_metrics as C  # noqa: E402

CFG = S.load_config()
EX = os.path.join(ROOT, "assets", "examples")


def load(name):
    with open(os.path.join(EX, name)) as f:
        return json.load(f)


class TranscriptFormulas(unittest.TestCase):
    """Numbers the speaker works through on air."""

    def test_position_size_shortcut_5pct_stop(self):
        # 100 / 5% stop = 20% position; losing trade costs 1% of capital (1:31:01)
        size = S.position_size_pct(5, risk_pct=1.0)
        self.assertAlmostEqual(size, 20.0)
        self.assertAlmostEqual(size * 5 / 100, 1.0)

    def test_host_example_1000_portfolio(self):
        # 1000 portfolio, 200 position, 5% stop -> 10 lost = 1% (1:31:37)
        size = S.position_size_pct(5, 1.0)
        self.assertAlmostEqual(1000 * size / 100 * 0.05, 10.0)

    def test_day_low_stop_2pct(self):
        # 2% stop: 50% at 1% risk, 12.5% at 0.25% risk (1:35:13)
        self.assertAlmostEqual(S.position_size_pct(2, 1.0), 50.0)
        self.assertAlmostEqual(S.position_size_pct(2, 0.25), 12.5)

    def test_edge_example(self):
        # 50/50 win rate, 20% avg gain, 5% avg loss -> edge 4 (> 2) (18:27)
        self.assertAlmostEqual(S.edge_ratio(50, 20, 5), 4.0)
        self.assertLess(S.edge_ratio(50, 5, 5) - 1.0, 1e-9)  # coin toss game 1: no edge

    def test_coin_toss_games(self):
        # Game 1: +100/-100 -> 0 EV; Game 2: +200/-100 -> +50/toss; Game 3: +500/-100 -> +200/toss
        self.assertAlmostEqual(S.expectancy_pct(50, 100, 100), 0)
        self.assertAlmostEqual(S.expectancy_pct(50, 200, 100), 50)
        self.assertAlmostEqual(S.expectancy_pct(50, 500, 100), 200)
        # 1000 tosses in game 2 -> 50,000 (8:00)
        self.assertAlmostEqual(1000 * S.expectancy_pct(50, 200, 100), 50000)

    def test_rs_percentile_top1_is_99(self):
        # top 1% = 99, top 2% = 98 (25:56)
        perf = pd.Series(np.arange(2500, 0, -1), dtype=float)  # stock 0 best
        r = R.rs_ratings(perf)
        self.assertEqual(r.iloc[0], 99)
        self.assertEqual(r.iloc[24], 99)     # rank 25 of 2500 = top 1%
        self.assertEqual(r.iloc[25], 98)     # rank 26
        self.assertEqual(r.iloc[499], 80)    # rank 500 = top 20%
        self.assertEqual(r.iloc[-1], 1)
        self.assertEqual(int((r >= 80).sum()), 500)  # top 20% of 2500 = 500 names (33:15)


class Config(unittest.TestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(sum(p["weight"] for p in CFG["pillars"].values()), 100)
        for k, p in CFG["pillars"].items():
            self.assertEqual(sum(r["max"] for r in p["rules"].values()), p["weight"], k)
        self.assertEqual(sum(r["max"] for r in CFG["market_health"]["rules"].values()), 100)


class Scoring(unittest.TestCase):
    def test_deterministic(self):
        d = load("stl_jan2026_leg1.json")
        self.assertEqual(S.score_stock(d, CFG), S.score_stock(d, CFG))

    def test_stl_leader_is_buy_a(self):
        r = S.score_stock(load("stl_jan2026_leg1.json"), CFG)
        self.assertTrue(r["classification"].startswith("BUY CANDIDATE - A"))
        self.assertEqual(r["effective_leg"], 1)
        self.assertAlmostEqual(r["trade_plan"]["stop_pct"], 6.0)
        self.assertAlmostEqual(r["trade_plan"]["position_pct"], 16.67, places=2)

    def test_mtar_late_stage_never_buy(self):
        r = S.score_stock(load("mtar_nov2026_late.json"), CFG)
        self.assertEqual(r["effective_leg"], 4)  # derived from 275% gain
        self.assertFalse(r["classification"].startswith("BUY"))
        self.assertIn("late stage", r["classification"])
        self.assertTrue(any(c["cap"] == "loose_base" for c in r["caps"]))

    def test_paramount_theme_tourist_capped(self):
        r = S.score_stock(load("paramount_theme_tourist.json"), CFG)
        self.assertLessEqual(r["score"], 59)
        self.assertTrue(any(c["cap"] == "theme_tourist" for c in r["caps"]))

    def test_gate_fail_rejects(self):
        d = load("stl_jan2026_leg1.json")
        d["inputs"]["rs_rating"] = 70
        r = S.score_stock(d, CFG)
        self.assertTrue(r["classification"].startswith("REJECT"))

    def test_stated_leg_overridden_by_gain(self):
        d = load("stl_jan2026_leg1.json")
        d["inputs"]["gain_from_base_low_pct"] = 200
        r = S.score_stock(d, CFG)
        self.assertEqual(r["effective_leg"], 4)
        self.assertTrue(r["flags"])

    def test_missing_fields_rebased_and_reported(self):
        d = load("stl_jan2026_leg1.json")
        r = S.score_stock(d, CFG)
        self.assertLess(r["coverage_pct"], 100)
        self.assertLessEqual(r["conservative_score"], r["uncapped_score"])

    def test_no_pivot_blocks_buy(self):
        d = load("jgchem_capex_catalyst.json")
        d["inputs"]["stop_distance_pct"] = None
        d["trade"] = {}
        r = S.score_stock(d, CFG)
        self.assertEqual(r["classification"], "BUY-GRADE - pending pivot/stop")

    def test_chasing_widens_stop(self):
        d = load("stl_jan2026_leg1.json")
        d["inputs"]["price"] = 135  # 8% above pivot 125
        r = S.score_stock(d, CFG)
        tp = r["trade_plan"]
        self.assertGreater(tp["stop_pct"], 6.0)
        self.assertTrue(any("above pivot" in w for w in tp["warnings"]))

    def test_market_regimes(self):
        with open(os.path.join(EX, "market", "market_healthy.json")) as f:
            m = S.score_market(json.load(f), CFG)
        self.assertEqual(m["regime"]["name"], "HEALTHY")
        with open(os.path.join(EX, "market", "market_weak_divergence.json")) as f:
            m2 = S.score_market(json.load(f), CFG)
        self.assertIn(m2["regime"]["name"], ("WEAK", "HOSTILE"))
        r = S.score_stock(load("stl_jan2026_leg1.json"), CFG, m2)
        self.assertIn("pilot size", r["classification"])
        self.assertAlmostEqual(r["trade_plan"]["risk_pct_of_portfolio"], 0.25)

    def test_all_examples_run(self):
        for p in glob.glob(os.path.join(EX, "*.json")):
            with open(p) as f:
                S.score_stock(json.load(f), CFG)


class V11Fixes(unittest.TestCase):
    """Fixes found by running the skill on every stock in the video."""

    def sparse(self):
        # Laurus-2020 style: four strong facts, everything else unknown
        return {"symbol": "X", "inputs": {"rs_resisted_decline": True, "leader_rank_in_group": 1,
                                          "leg_number": 1, "market_cap_cr": 4500}}

    def test_low_coverage_headline_is_conservative(self):
        r = S.score_stock(self.sparse(), CFG)
        self.assertLess(r["coverage_pct"], 70)
        self.assertEqual(r["headline_score"], r["conservative_score"])
        self.assertTrue(r["classification"].startswith("INSUFFICIENT DATA"))
        self.assertGreater(r["score"], r["headline_score"])  # re-based still reported

    def test_low_coverage_keeps_strong_vs_weak_visible(self):
        strong = S.score_stock(self.sparse(), CFG)
        weak = S.score_stock({"symbol": "Y", "inputs": {"leader_rank_in_group": 5, "group_count_in_scan": 1,
                                                       "theme_revenue_share_pct": 2, "leg_number": 1}}, CFG)
        self.assertIn("pending pivot", strong["classification"])
        self.assertIn("not ready", weak["classification"])

    def test_tiny_coverage_gets_no_provisional_grade(self):
        r = S.score_stock({"symbol": "Z", "inputs": {"leader_rank_in_group": 1, "group_count_in_scan": 3}}, CFG)
        self.assertLess(r["coverage_pct"], 20)
        self.assertIn("too little data to grade", r["classification"])

    def test_full_coverage_headline_is_rebased(self):
        r = S.score_stock(load("jgchem_capex_catalyst.json"), CFG)
        self.assertGreaterEqual(r["coverage_pct"], 70)
        self.assertEqual(r["headline_score"], r["score"])

    def test_caps_apply_to_conservative(self):
        d = load("paramount_theme_tourist.json")
        r = S.score_stock(d, CFG)
        self.assertLessEqual(r["conservative_score"], 59)

    def test_exit_alert_below_50ema(self):
        d = load("mtar_nov2026_late.json")
        d["inputs"].update({"price": 6838, "ema50": 7110.5})
        r = S.score_stock(d, CFG)
        self.assertTrue(any(a.startswith("EXIT ALERT") for a in r["alerts"]))
        d["inputs"]["price"] = 7200
        self.assertFalse(any(a.startswith("EXIT ALERT") for a in S.score_stock(d, CFG)["alerts"]))

    def test_rs_drop_alert(self):
        d = load("stl_jan2026_leg1.json")
        d["inputs"]["rs_rating"] = 74
        r = S.score_stock(d, CFG)
        self.assertTrue(any("RS 74" in a for a in r["alerts"]))

    def test_word_inputs_scored_at_band_floor(self):
        d = load("stl_jan2026_leg1.json")
        d["inputs"]["volume_spike_ratio"] = "high"
        d["inputs"]["rs_resisted_decline"] = "yes"
        r = S.score_stock(d, CFG)
        rows = {row["rule"]: row for p in r["pillars"] for row in p["rows"]}
        self.assertEqual(rows["volume_spike_ratio"]["value"], 2)
        self.assertEqual(rows["volume_spike_ratio"]["points"], 2)
        self.assertEqual(rows["volume_spike_ratio"]["quality"], "qualitative")
        self.assertEqual(rows["rs_resisted_decline"]["points"], 3)

    def test_unknown_word_raises(self):
        d = load("stl_jan2026_leg1.json")
        d["inputs"]["volume_spike_ratio"] = "massive-ish"
        with self.assertRaises(ValueError):
            S.score_stock(d, CFG)

    def test_quality_tags_from_evidence(self):
        d = load("stl_jan2026_leg1.json")
        d["evidence"]["rs_rating"] = "inferred: from 6M return"
        r = S.score_stock(d, CFG)
        rows = {row["rule"]: row for p in r["pillars"] for row in p["rows"]}
        self.assertEqual(rows["rs_rating"]["quality"], "inferred")
        self.assertEqual(rows["stop_distance_pct"]["quality"], "assumed")
        self.assertAlmostEqual(sum(r["quality_points"].values()), r["conservative_score"], places=1)

    def test_batch_table_has_new_columns(self):
        rs = [S.score_stock(load(n), CFG) for n in ("stl_jan2026_leg1.json", "mtar_nov2026_late.json")]
        md = S.batch_md(rs)
        self.assertIn("Conservative", md)
        self.assertIn("Gates missing", md)
        self.assertIn("Alerts", md)


def synthetic_leader(seed=1):
    """250 sessions falling 40%, 60 flat, 25 sessions rallying 50% on volume,
    then 15 tight sessions on dry volume."""
    rng = np.random.default_rng(seed)
    fall = np.linspace(200, 120, 250)
    flat = np.full(60, 120.0)
    rally = np.linspace(120, 180, 25)
    tight = 178 + rng.uniform(-2, 2, 15)
    close = np.concatenate([fall, flat, rally, tight])
    vol = np.concatenate([np.full(250, 1e6), np.full(60, 8e5), np.full(25, 3e6), np.full(15, 4e5)])
    n = len(close)
    df = pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=n),
        "open": close, "high": close * 1.005, "low": close * 0.995,
        "close": close, "volume": vol})
    return df


class ChartMetrics(unittest.TestCase):
    def test_synthetic_leader(self):
        out = C.compute(synthetic_leader())
        i, t = out["inputs"], out["trade"]
        self.assertTrue(i["price_above_200dma"])
        self.assertLess(i["stop_distance_pct"], 8)       # tight right side
        self.assertLess(i["volume_dryup_ratio"], 0.6)    # volume dried up
        self.assertGreaterEqual(i["volume_spike_ratio"], 2)
        self.assertAlmostEqual(i["gain_from_base_low_pct"], 180 / (120 * 0.995) * 100 - 100, delta=3)
        self.assertEqual(i["ema50_breaches"], 0)
        self.assertLess(t["stop_price"], t["pivot_price"])
        self.assertIn("ema50", i)
        self.assertFalse(i["below_50ema_now"])


if __name__ == "__main__":
    unittest.main()
