#!/usr/bin/env python3
"""
edge_calc.py - your system's edge from a trade journal (transcript 16:26-19:36).

  Edge = (win% / loss%) x (avg gain% / avg loss%)

  < 1  : the system is losing money
  1-2  : thin edge
  > 2  : working system (the speaker reports 3.8)

Mathematically this is the profit factor. Expectancy per trade is also shown.

  python edge_calc.py --trades journal.csv        # needs a pnl_pct column
  python edge_calc.py --win 50 --gain 20 --loss 5  # summary numbers
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_setup import edge_ratio, expectancy_pct, load_config  # noqa: E402


def from_trades(path):
    with open(path) as f:
        pnl = [float(r["pnl_pct"]) for r in csv.DictReader(f) if r.get("pnl_pct") not in (None, "")]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p <= 0]
    if not pnl:
        raise SystemExit("no pnl_pct values")
    win_pct = len(wins) / len(pnl) * 100
    avg_gain = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    return len(pnl), win_pct, avg_gain, avg_loss


def verdict(e, cfg):
    if e < cfg["edge"]["no_edge_below"]:
        return "NO EDGE - the system is losing money"
    if e <= cfg["edge"]["good_above"]:
        return "THIN EDGE - profitable but fragile"
    return "GOOD EDGE"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trades")
    ap.add_argument("--win", type=float)
    ap.add_argument("--gain", type=float)
    ap.add_argument("--loss", type=float)
    a = ap.parse_args(argv)
    cfg = load_config()
    if a.trades:
        n, w, g, l = from_trades(a.trades)
    elif None not in (a.win, a.gain, a.loss):
        n, w, g, l = None, a.win, a.gain, abs(a.loss)
    else:
        ap.print_help(); return 1
    e = edge_ratio(w, g, l)
    out = {"trades": n, "win_pct": round(w, 2), "avg_gain_pct": round(g, 2), "avg_loss_pct": round(l, 2),
           "edge": round(e, 2) if e != float("inf") else "inf",
           "expectancy_pct_per_trade": round(expectancy_pct(w, g, l), 2),
           "verdict": verdict(e, cfg)}
    if n is not None and n < 20:
        out["warning"] = f"only {n} trades: the edge estimate is noisy (aim for 20+)"
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
