#!/usr/bin/env python3
"""
Historical replay of the PoP momentum score on individual stocks.

At every monthly rebalance date (last trading day of each month) the score is
recomputed using ONLY data up to that date (no look-ahead). Single-stock proxy of
the "top-20 entry / exit below rank 50" rule:

    ENTER  when all gates pass and score >= 75   (BUY-ZONE)
    EXIT   when any gate fails or score < 60     (fell out of HOLD-ZONE)

Orders fill at the NEXT trading day's open (after-market order), or close if no Open.

Usage:
  python replay.py --csv ATGL.csv LAURUS.csv --start 2016-01-01 [--end 2025-12-31] --out replay
Writes replay.md (trade list + summary per stock) and replay.json.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from momentum_score import CFG, compute, load_prices  # noqa: E402


def max_dd(series):
    s = np.asarray(series, float)
    peak = np.maximum.accumulate(s)
    return float(np.min(s / peak - 1)) if len(s) else 0.0


def replay(sym, df, start, end, cfg):
    df = df.reset_index(drop=True)
    if end:
        df = df[df["date"] <= pd.Timestamp(end)].reset_index(drop=True)
    has_open = "open" in df.columns and df["open"].notna().all()
    me = df.groupby(df["date"].dt.to_period("M"))["date"].idxmax()
    rb_idx = [i for i in me.values if df["date"].iloc[i] >= pd.Timestamp(start) and i >= cfg["lb12"] and i + 1 < len(df)]
    pos, trades, log = None, [], []
    equity = np.ones(len(df))
    for i in rb_idx:
        r = compute(sym, df.iloc[: i + 1], {}, cfg)
        if not r.get("data_ok"):
            continue
        sc, el = r["score_abs"], r["eligible"]
        fill_i = i + 1
        fill_px = df["open"].iloc[fill_i] if has_open else df["close"].iloc[fill_i]
        action = ""
        failed = [g["gate"].split()[0] for g in r["gates"] if g["passed"] is False]
        if pos is None and el and sc >= cfg["band_buy"]:
            pos = dict(entry_date=str(df["date"].iloc[fill_i].date()), entry_px=float(fill_px), entry_i=fill_i, entry_score=sc)
            action = "BUY"
        elif pos is not None and (not el or sc < cfg["band_hold"]):
            ret = fill_px / pos["entry_px"] - 1
            trades.append(dict(**{k: v for k, v in pos.items() if k != "entry_i"}, exit_date=str(df["date"].iloc[fill_i].date()),
                               exit_px=float(fill_px), exit_score=sc, exit_reason=("gate " + ",".join(failed)) if failed else "score<60",
                               ret=ret, months=round((fill_i - pos["entry_i"]) / 21, 1)))
            pos = None
            action = "SELL"
        log.append(dict(date=str(df["date"].iloc[i].date()), close=float(df["close"].iloc[i]), score=sc, eligible=el,
                        failed=failed, action=action, R12=r["m"]["R12"], prox=r["m"]["prox"]))
    open_trade = None
    if pos is not None:
        last = df["close"].iloc[-1]
        open_trade = dict(**{k: v for k, v in pos.items() if k != "entry_i"}, mark_date=str(df["date"].iloc[-1].date()),
                          mark_px=float(last), ret=float(last / pos["entry_px"] - 1))
    # strategy equity curve (in stock when held, cash otherwise)
    c = df["close"].to_numpy(float)
    s0 = rb_idx[0] if rb_idx else 0
    held = np.zeros(len(df), bool)
    for t in trades + ([open_trade] if open_trade else []):
        a = df.index[df["date"] == pd.Timestamp(t["entry_date"])][0]
        b = df.index[df["date"] == pd.Timestamp(t.get("exit_date", t.get("mark_date")))][0]
        held[a + 1: b + 1] = True
    dr = np.r_[0, c[1:] / c[:-1] - 1]
    eq = np.cumprod(1 + np.where(held, dr, 0.0))[s0:]
    bh = c[s0:] / c[s0]
    rets = [t["ret"] for t in trades]
    summ = dict(symbol=sym, period=f"{df['date'].iloc[s0].date()} -> {df['date'].iloc[-1].date()}",
                rebalances=len(log), trades=len(trades), open_position=open_trade is not None,
                win_rate=(float(np.mean([x > 0 for x in rets])) if rets else None),
                strategy_mult=float(eq[-1]), buyhold_mult=float(bh[-1]),
                strategy_maxdd=max_dd(eq), buyhold_maxdd=max_dd(bh),
                time_in_market=float(held[s0:].mean()),
                best_trade=(max(rets) if rets else None), worst_trade=(min(rets) if rets else None))
    return dict(summary=summ, trades=trades, open_trade=open_trade, log=log)


def fmt(x, p=True):
    if x is None:
        return "-"
    return "%+.1f%%" % (x * 100) if p else "%.2fx" % x


def report(results):
    L = ["# PoP momentum score - historical replay", "",
         "Monthly rebalance, no look-ahead. Enter: gates pass & score >= 75. Exit: any gate fails or score < 60. Fill next day.", "",
         "| Stock | Period | Trades | Win rate | Strategy | Buy & hold | Strat max DD | B&H max DD | Time in mkt |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        s = r["summary"]
        L.append("| %s | %s | %d%s | %s | %s | %s | %.0f%% | %.0f%% | %.0f%% |" % (
            s["symbol"], s["period"], s["trades"], " +1 open" if s["open_position"] else "",
            "-" if s["win_rate"] is None else "%.0f%%" % (s["win_rate"] * 100),
            fmt(s["strategy_mult"], False), fmt(s["buyhold_mult"], False),
            s["strategy_maxdd"] * 100, s["buyhold_maxdd"] * 100, s["time_in_market"] * 100))
    for r in results:
        L += ["", "## " + r["summary"]["symbol"], "", "| Entry | Px | Score | Exit | Px | Score | Reason | Return | Months |", "|---|---|---|---|---|---|---|---|---|"]
        for t in r["trades"]:
            L.append("| %s | %.2f | %.0f | %s | %.2f | %.0f | %s | %s | %.1f |" % (
                t["entry_date"], t["entry_px"], t["entry_score"], t["exit_date"], t["exit_px"], t["exit_score"], t["exit_reason"], fmt(t["ret"]), t["months"]))
        if r["open_trade"]:
            t = r["open_trade"]
            L.append("| %s | %.2f | %.0f | (open, marked %s) | %.2f | | | %s | |" % (t["entry_date"], t["entry_px"], t["entry_score"], t["mark_date"], t["mark_px"], fmt(t["ret"])))
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", nargs="*")
    p.add_argument("--dir")
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end")
    p.add_argument("--out", default="replay")
    a = p.parse_args()
    data = load_prices(a.csv, a.dir)
    res = [replay(s, df, a.start, a.end, CFG) for s, df in data.items()]
    md = report(res)
    open(a.out + ".md", "w", encoding="utf-8").write(md)
    json.dump(res, open(a.out + ".json", "w"), indent=1, default=str)
    print(md)


if __name__ == "__main__":
    main()
