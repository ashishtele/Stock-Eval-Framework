#!/usr/bin/env python3
"""Re-run SDS on every listed stock named in the podcast: today + point-in-time near the guest's entry.

Usage: python verify.py [--refresh]   (fetches missing *.fetched.json; --refresh re-fetches all)
Writes <ticker>[-<date>].fetched.json, <ticker>.analyst.json and verification.json next to this file.
"""
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fetch  # noqa: E402
import score  # noqa: E402

# (ticker, guest stance, back-test as_of or None, guest's price claim)
CASES = [
    ("FRONTSP", "bought ~15-25, holds; ~300x", "2018-06-30", "15 -> 4,500 pre-bonus"),
    ("CAPLIPOINT", "bought ~2016, holds; ~90x", "2020-06-30", "~20 split-adj -> 1,800"),
    ("JYOTIRES", "bought ~40, partial exit at 4,000", "2020-06-30", "40 -> 4,000"),
    ("TARIL", "turnaround; 25 -> 1,300 in 2.5y", "2023-03-31", "25 -> 1,300"),
    ("SHILCTECH", "transformer theme, ~500 -> bonus", "2022-06-30", "~500 -> high"),
    ("INDOTECH", "transformer theme", "2023-03-31", "200 -> 2,200"),
    ("DYCL", "cable, SME find", "2023-03-31", "not stated"),
    ("RMC", "switchgear, Jaipur cluster", "2023-03-31", "not stated"),
    ("INA", "47x in 2y, 'over-hyped'", None, "100 -> 4,700"),
    ("JUBLPHARMA", "Covid buy; demerger chain", "2020-06-30", "150 -> 1,200-1,300"),
    ("JUBLINGREA", "demerged; 700", None, "-> 700"),
    ("JUBLCPL", "Jivanjor; demerged; 2,300", None, "-> 2,300"),
    ("SARDAEN", "2026 bullish pick (NCLT power asset)", "2022-03-31", "not stated"),
    ("CEINSYS", "agile GIS niche; ~2x in 2y", "2024-11-30", "~525 -> 1,150"),
    ("TERASOFT", "3,000 cr order vs 250 cr mcap; 10x", "2024-06-30", "10x in 1.5-2y"),
    ("MOSCHIP", "loss-making semis design; now ~200", "2023-03-31", "-> ~200"),
    ("SUZLON", "uncertain turnaround; pull capital first", "2023-03-31", "not stated"),
    ("INFY", "cautious: AI risk, elephant", None, "n/a"),
    ("INTELLECT", "cited as AI-automation example", None, "n/a"),
    ("PIDILITIND", "dominant incumbent (control)", None, "n/a"),
]


def ensure(ticker, as_of, refresh):
    name = ticker.lower() + (f"-{as_of[:7]}" if as_of else "")
    path = HERE / f"{name}.fetched.json"
    if refresh or not path.exists():
        cmd = [sys.executable, str(SCRIPTS / "fetch.py"), ticker, "-o", str(path)] + (["--as-of", as_of] if as_of else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "fetch failed"
    return path, None


def merged(*paths):
    data = {"inputs": {}}
    for p in paths:
        part = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        data["inputs"].update({k: v for k, v in part.pop("inputs", {}).items() if isinstance(v, dict) and v.get("value") is not None})
        data.update({k: v for k, v in part.items() if v not in (None, "") and not k.startswith("_")})
    return data


def price_path(ticker, as_of):
    html = fetch.get(f"{fetch.BASE}/company/{ticker}/")
    cid = re.search(r'data-company-id="(\d+)"', html).group(1)
    s = fetch.chart(cid, "Price", False)
    d0 = dt.date.fromisoformat(as_of)
    before = [v for d, v in s if d <= d0]
    after = [v for d, v in s if d > d0]
    if not before or not after:
        return None
    p0 = before[-1]
    return {"price_at_as_of": p0, "peak_after": max(after), "peak_multiple": round(max(after) / p0, 1),
            "today": s[-1][1], "today_multiple": round(s[-1][1] / p0, 1)}


def row(ticker, label, path, analyst):
    r = score.run(merged(path, analyst))
    return {"ticker": ticker, "when": label, "total": r["total"], "coverage": r["evidence_coverage"], "verdict": r["verdict"],
            "certainty": r["certainty"], "pillars": "/".join(f"{v['score']:g}" for v in r["pillars"].values()), "flags": r["flags"]}


def main():
    refresh = "--refresh" in sys.argv
    more = json.loads((HERE / "more-analyst.json").read_text(encoding="utf-8"))
    results = []
    for ticker, stance, as_of, claim in CASES:
        analyst = HERE / f"{ticker.lower()}.analyst.json"
        if ticker in more:
            analyst.write_text(json.dumps(more[ticker], indent=2) + "\n", encoding="utf-8")
        for when in [None, as_of] if as_of else [None]:
            path, err = ensure(ticker, when, refresh)
            label = when or "today"
            if err:
                results.append({"ticker": ticker, "when": label, "error": err})
                print(f"{ticker:<11} {label:<10} ERROR {err}")
                continue
            res = row(ticker, label, path, analyst)
            res.update({"stance": stance, "claim": claim})
            if when:
                try:
                    res["outcome"] = price_path(ticker, when)
                except Exception as e:  # price history is informative only
                    res["outcome"] = f"unavailable: {e}"
            results.append(res)
            o = res.get("outcome")
            out = f" peak {o['peak_multiple']}x / now {o['today_multiple']}x" if isinstance(o, dict) else ""
            print(f"{ticker:<11} {label:<10} {res['total']:>5} {res['coverage']:.0%} {res['verdict'][:28]:<28} {res['pillars']:<22}{out}"
                  + (f"  [{'; '.join(f.split(':')[0] for f in res['flags'])}]" if res["flags"] else ""))
    (HERE / "verification.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    bt = [r for r in results if isinstance(r.get("outcome"), dict)]
    if len(bt) >= 5:
        rank = lambda xs: [sorted(xs).index(x) + (xs.count(x) - 1) / 2 for x in xs]  # noqa: E731
        a, b = rank([r["total"] for r in bt]), rank([r["outcome"]["peak_multiple"] for r in bt])
        n = len(bt)
        rho = 1 - 6 * sum((x - y) ** 2 for x, y in zip(a, b)) / (n * (n * n - 1))
        print(f"\nSpearman(back-test score, later peak multiple) = {rho:.2f} over {n} back-tests")


if __name__ == "__main__":
    main()
