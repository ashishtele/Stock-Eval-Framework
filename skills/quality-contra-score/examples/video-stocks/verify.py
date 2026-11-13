#!/usr/bin/env python3
"""Verify QCS on every listed non-financial stock named in the podcast: today + point-in-time near the guest's entry.

Usage: python verify.py [--refresh] [--fetch-only]
Fetches missing <case>.fetched.json, scores with <case>.analyst.json or more-analyst.json[case],
checks the guest's price claims and back-test forward returns vs Nifty, writes verification.json.
Screener's free pages hold ~12 fiscal years (FY2015+), so entries before mid-2020 cannot be back-tested.
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fetch  # noqa: E402
import score  # noqa: E402

SA = True  # consolidation includes a captive lender -> standalone
# (case, slug, standalone, as_of or None, guest stance with timestamp, claimed price for this date or None)
CASES = [
    ("itc", "ITC", False, None, "contra buy now at ~280, 5% yield (9:26)", 280),
    ("tcs", "TCS", False, None, "strong recent contra call, ~2,200 (11:02, 18:16)", 2200),
    ("infy", "INFY", False, None, "IT headwind; contra candidate (16:38, 27:21)", None),
    ("techm", "TECHM", False, None, "named as good stock facing AI headwind (16:38)", None),
    ("mphasis", "MPHASIS", False, None, "named as good stock facing AI headwind (16:38)", None),
    ("bajaj-auto", "BAJAJ-AUTO", SA, None, "recent contra call, already moved; ~11,000 (11:02, 45:13)", 11000),
    ("bajaj-auto-2022-06", "BAJAJ-AUTO", SA, "2022-06-30", "buyback 4,600 vs ~3,800 market (43:09)", 3800),
    ("mm", "M&M", SA, None, "buy if monsoon hurts (25:23)", None),
    ("tvsmotor", "TVSMOTOR", SA, None, "bought ~500 in contra fund (21:27)", None),
    ("tvsmotor-2020-09", "TVSMOTOR", SA, "2020-09-30", "bought ~500, 'a bit expensive' (21:27-21:51)", 500),
    ("maruti", "MARUTI", False, None, "demonetisation buy, sold early (24:44)", None),
    ("hindalco", "HINDALCO", False, None, "Birla backs it; ~950, can double (41:08-41:15)", 950),
    ("hindalco-2020-06", "HINDALCO", False, "2020-06-30", "metals crushed, tested patience (39:59-40:22)", None),
    ("jswsteel", "JSWSTEEL", False, None, "25x since iron-ore ban; lowest-cost converter (7:22-8:20)", None),
    ("tataconsum", "TATACONSUM", False, None, "bought 2019 at 200, now ~1,100 (23:07-23:16)", 1100),
    ("indhotel", "INDHOTEL", False, None, "bought post-vaccine at 75, now ~720 (28:30-28:43)", 720),
    ("indhotel-2020-11", "INDHOTEL", False, "2020-11-10", "bought on vaccine news (28:30)", 75),
    ("tatamotors-2020-11", "TMPV", False, "2020-11-10", "bought ~45 post-vaccine (30:15)", 45),
    ("motherson-2020-11", "MOTHERSON", False, "2020-11-10", "bought 45-65 post-vaccine (30:23)", 55),
    ("jswinfra", "JSWINFRA", False, None, "IPO at 119 was the no-brainer (48:28)", None),
    ("jswinfra-2023-10", "JSWINFRA", False, "2023-10-31", "IPO 119, 22,000 cr mcap, 6% CF yield (48:28-49:43)", 119),
    ("bhartiartl", "BHARTIARTL", False, None, "trial by fire 2016-19, 70k cr FCF ahead (13:52, 38:20)", None),
    ("sunpharma", "SUNPHARMA", False, None, "governance-issue contra buy (4:30-5:06)", None),
    ("ntpc", "NTPC", False, None, "8-9% weight, ESG overhang, re-rated 3x to ~350 (36:44-37:50)", 350),
    ("ntpc-2021-06", "NTPC", False, "2021-06-30", "stuck at 120-140, tested patience (36:59)", 130),
    ("powergrid", "POWERGRID", False, None, "annuity cash flow, tested patience (36:33)", None),
    ("trent", "TRENT", False, None, "bought ~1,200, sold early, went to 7,000 (23:43-24:05)", None),
    ("trent-2022-06", "TRENT", False, "2022-06-30", "bought ~1,200 (23:48)", 1200),
    ("pidilitind", "PIDILITIND", False, None, "crude-up contra example (5:30)", None),
    ("pidilitind-2022-06", "PIDILITIND", False, "2022-06-30", "crude-spike analogue of the 5:30 example", None),
    ("asianpaint", "ASIANPAINT", False, None, "crude-up contra example (5:30)", None),
    ("asianpaint-2022-06", "ASIANPAINT", False, "2022-06-30", "crude-spike analogue of the 5:30 example", None),
    ("hindunilvr", "HINDUNILVR", False, None, "best governance; 'cash flow after cash flow' (9:26, 52:22)", None),
    ("titan", "TITAN", False, None, "RJ's full ride (31:46-32:16)", None),
    ("mrf", "MRF", False, None, "full ride from ~500 (32:33-33:17)", None),
]
Q_MECH = ("roce_10y", "roce_consistency", "cfo_conversion", "cfo_consistency", "net_debt_to_ebitda", "interest_coverage", "dividend_payout")
S_MECH = ("drawdown", "derating_vs_earnings", "relative_underperformance", "pe_vs_own_10y", "yield_support", "expected_return")


def ensure(case, slug, standalone, as_of, refresh):
    path = HERE / f"{case}.fetched.json"
    if refresh or not path.exists():
        cmd = [sys.executable, str(SCRIPTS / "fetch.py"), slug, "-o", str(path)]
        cmd += (["--standalone"] if standalone else []) + (["--as-of", as_of] if as_of else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            lines = r.stderr.strip().splitlines()
            return None, lines[-1] if lines else "fetch failed"
    return path, None


def merged(*parts):
    data = {"inputs": {}}
    for part in parts:
        part = dict(part)
        data["inputs"].update({k: v for k, v in part.pop("inputs", {}).items() if isinstance(v, dict) and v.get("value") is not None})
        data.update({k: v for k, v in part.items() if v not in (None, "") and not k.startswith("_")})
    return data


def multiple_since(sym, as_of):
    days = (dt.date.today() - dt.date.fromisoformat(as_of)).days
    bars = fetch.yahoo_daily(sym, dt.date.today(), years=days / 365 + 0.05)
    start = fetch.close_on_or_before(bars, dt.date.fromisoformat(as_of))
    return bars[-1][1] / start[1] if start else None


def main():
    refresh, fetch_only = "--refresh" in sys.argv, "--fetch-only" in sys.argv
    more = json.loads((HERE / "more-analyst.json").read_text(encoding="utf-8")) if (HERE / "more-analyst.json").exists() else {}
    fetched, results = {}, []
    for case, slug, sa, as_of, stance, claim in CASES:
        path, err = ensure(case, slug, sa, as_of, refresh)
        print(f"{case:<20} {'ERROR ' + err if err else 'ok'}", file=sys.stderr)
        fetched[case] = (path, err)
    if fetch_only:
        return

    hdr = f"{'case':<20}{'QCS':>5}{'cov':>5}{'Q':>4}{'S':>4}{'Qm':>4}{'Sm':>4}  {'verdict':<34}{'price/claim':<16}{'fwd vs Nifty':<18}flags"
    print(hdr)
    for case, slug, sa, as_of, stance, claim in CASES:
        path, err = fetched[case]
        if err:
            results.append({"case": case, "stance": stance, "error": err})
            print(f"{case:<20} ERROR {err}")
            continue
        f = json.loads(path.read_text(encoding="utf-8"))
        analyst_file = HERE / f"{case}.analyst.json"
        analyst = json.loads(analyst_file.read_text(encoding="utf-8")) if analyst_file.exists() else more.get(case, {})
        r = score.run(merged(f, {"business_type": "non_financial"}, analyst))
        pts = {m["metric"]: m["points"] for m in r["metrics"]}
        qm, sm = sum(pts[k] for k in Q_MECH), sum(pts[k] for k in S_MECH)
        price_item = f["inputs"].get("current_price") or {}
        price = price_item.get("value")
        res = {"case": case, "as_of": f["as_of"], "stance": stance, "total": r["total"], "coverage": r["evidence_coverage"],
               "quality": r["quality_score"], "setup": r["setup_score"], "quality_mech_32": qm, "setup_mech_26": sm,
               "verdict": r["verdict"], "flags": [x.split(":")[0] for x in r["flags"]], "price": price, "claim": claim,
               "pillars": "/".join(f"{v['score']:g}" for v in r["pillars"].values())}
        if as_of and price:
            sym = price_item["source"].split()[1]
            mult, n = multiple_since(sym, as_of), multiple_since("^NSEI", as_of)
            yrs = (dt.date.today() - dt.date.fromisoformat(as_of)).days / 365
            if mult and n:
                res["forward"] = {"multiple": round(mult, 2), "cagr_pct": round(100 * (mult ** (1 / yrs) - 1), 1),
                                  "nifty_multiple": round(n, 2)}
        results.append(res)
        pc = f"{price:,.0f}" + (f"/{claim:,}" if claim else "") if price else "n/a"
        fw = res.get("forward")
        fws = f"{fw['multiple']}x vs {fw['nifty_multiple']}x" if fw else ""
        print(f"{case:<20}{r['total']:>5g}{r['evidence_coverage']:>5.0%}{r['quality_score']:>4g}{r['setup_score']:>4g}{qm:>4g}{sm:>4g}  "
              f"{r['verdict'].replace('PROVISIONAL ', '~')[:40]:<41}{pc:<16}{fws:<18}{','.join(res['flags'])}")
    (HERE / "verification.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
