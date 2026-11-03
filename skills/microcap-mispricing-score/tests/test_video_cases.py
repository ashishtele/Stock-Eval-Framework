"""Regression tests on the real stocks discussed in the source video (point-in-time inputs).
If you retune framework_config.json, rerun these to see how each historical call would change.
Expected bands, not exact numbers, so small threshold tweaks don't break them needlessly."""
import json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import score_stock as S
CFG = S.load_json(S.DEFAULT_CONFIG)
D = ROOT / "assets/examples/video_cases"

def run(name):
    return S.run(json.load(open(D / f"{name}.json")), CFG)

class VideoCases(unittest.TestCase):
    def test_apar_2020_flagged_by_numbers_alone(self):
        m, s, _ = run("apar_jul2020__numbers_only")
        self.assertGreaterEqual(s["score"], 75)
        self.assertLess(m["cyclically_adjusted_pe"], 10)          # single-digit CAPE, as he described
        self.assertAlmostEqual(m["pb"], 0.82, places=2)            # ~1x book

    def test_apar_2020_with_thesis_is_cheap_and_undervalued(self):
        _, s, _ = run("apar_jul2020__with_thesis")
        self.assertIn("CHEAP AND UNDERVALUED", s["classification"])

    def test_force_2022_not_a_numbers_call(self):
        # Loss-making at FY22; the framework's earnings rules cannot see the turnaround.
        m, s, _ = run("force_motors_jun2022__numbers_only")
        self.assertIsNone(m["cyclically_adjusted_pe"])
        self.assertLess(s["score"], 60)

    def test_venus_2025_with_thesis(self):
        _, s, _ = run("venus_remedies_jul2025__with_thesis")
        self.assertGreaterEqual(s["score"], 75)
        self.assertIn("CHEAP AND UNDERVALUED", s["classification"])

    def test_kaveri_segment_mix_matches_video(self):
        m, _, _ = run("kaveri_seed_nov2026__with_thesis")
        cotton = [x for x in m["segments"]["segments"] if x["name"] == "cotton"][0]
        self.assertAlmostEqual(cotton["share_from_pct"], 55, delta=1)
        self.assertAlmostEqual(cotton["share_to_pct"], 11, delta=1)

if __name__ == "__main__":
    unittest.main()
