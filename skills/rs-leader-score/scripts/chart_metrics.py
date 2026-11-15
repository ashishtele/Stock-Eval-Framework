#!/usr/bin/env python3
"""
chart_metrics.py - compute the framework's technical inputs from daily OHLCV.

Input CSV columns (case-insensitive): date, open, high, low, close, volume.
Optional --benchmark CSV (same format, index) to test "resisted the decline".

Outputs a JSON block you can paste into the stock file's "inputs" and "trade".
Every number is a plain formula on the price series (see references/framework.md §4),
so it can be re-checked in any charting tool.

  python chart_metrics.py STL.csv --benchmark NIFTY500.csv --base-days 15 --out stl_tech.json

What it does NOT compute (needs your eyes or research): leg_number (only a proxy via
gain_from_base_low_pct), group/theme fields, catalyst fields, rs_rating (needs the
whole universe: use compute_rs.py).
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd


def load_ohlcv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    need = {"date", "high", "low", "close", "volume"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"{path}: missing columns {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def pct_ret(close, n):
    if len(close) <= n:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - n] * 100 - 100)


def base_length_days(high, low, max_depth_pct):
    """Trading days back from today during which the high-low range stayed within max_depth_pct."""
    hi, lo, n = -np.inf, np.inf, 0
    for h, l in zip(high[::-1], low[::-1]):
        hi, lo = max(hi, h), min(lo, l)
        if (hi - lo) / hi * 100 > max_depth_pct:
            break
        n += 1
    return n


def count_ema_breaches(close, ema, start_idx, min_run=2):
    """Number of separate runs of >= min_run consecutive closes below the EMA after start_idx."""
    below = (close.iloc[start_idx:] < ema.iloc[start_idx:]).astype(int).tolist()
    runs, cur = 0, 0
    for b in below + [0]:
        if b:
            cur += 1
        else:
            if cur >= min_run:
                runs += 1
            cur = 0
    return runs


def resisted_decline(stock, bench, window=126, min_dd=5.0):
    """True if, during the index's worst drawdown in the window, the stock lost
    less than half as much (Darvas: 'stocks that resisted the tide')."""
    b = bench.set_index("date")["close"]
    s = stock.set_index("date")["close"]
    b = b.iloc[-window:]
    if len(b) < 20:
        return None, None
    peak_idx, best = None, (0.0, None, None)
    running_peak, running_peak_date = -np.inf, None
    for d, v in b.items():
        if v > running_peak:
            running_peak, running_peak_date = v, d
        dd = (running_peak - v) / running_peak * 100
        if dd > best[0]:
            best = (dd, running_peak_date, d)
    dd, p_date, t_date = best
    if dd < min_dd:
        return None, f"index max drawdown {dd:.1f}% < {min_dd}%: test not applicable"
    s_win = s.loc[(s.index >= p_date) & (s.index <= t_date)]
    if len(s_win) < 2:
        return None, "stock data does not cover the index drawdown window"
    s_chg = float(s_win.iloc[-1] / s_win.iloc[0] * 100 - 100)
    ok = s_chg > -0.5 * dd
    return bool(ok), (f"index fell {dd:.1f}% ({p_date.date()} to {t_date.date()}); "
                      f"stock {s_chg:+.1f}% over the same window")


def compute(df, bench=None, base_days=15, lookback=250, max_base_depth=30.0, retrace=1.0):
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema21 = c.ewm(span=21, adjust=False).mean()
    sma200 = c.rolling(200).mean()
    price = float(c.iloc[-1])
    out, why = {}, {}

    out["price"] = round(price, 2)
    out["ema50"] = round(float(ema50.iloc[-1]), 2)
    out["below_50ema_now"] = bool(price < ema50.iloc[-1])
    why["below_50ema_now"] = "close vs 50 EMA (holding/exit check, not scored)"
    if not np.isnan(sma200.iloc[-1]):
        out["price_above_200dma"] = bool(price > sma200.iloc[-1])
        why["price_above_200dma"] = f"close {price:.2f} vs 200 DMA {sma200.iloc[-1]:.2f}"
    out["avg_turnover_30d_cr"] = round(float((c * v).iloc[-30:].mean() / 1e7), 2)
    why["avg_turnover_30d_cr"] = "mean(close x volume) over 30 sessions / 1e7"

    rets = {k: pct_ret(c, n) for k, n in (("ret_3m", 63), ("ret_6m", 126), ("ret_9m", 189), ("ret_12m", 252))}

    # right side / pivot
    win = df.iloc[-base_days:]
    pivot, blow = float(win["high"].max()), float(win["low"].min())
    out["stop_distance_pct"] = round((pivot - blow) / pivot * 100, 2)
    why["stop_distance_pct"] = f"last {base_days} sessions: high {pivot:.2f}, low {blow:.2f}"

    out["volume_dryup_ratio"] = round(float(v.iloc[-10:].mean() / v.iloc[-50:].mean()), 2)
    why["volume_dryup_ratio"] = "avg volume last 10 / last 50 sessions"
    out["volume_spike_ratio"] = round(float(v.iloc[-60:].max() / v.iloc[-120:].mean()), 2)
    why["volume_spike_ratio"] = "max volume last 60 / avg volume last 120 sessions"

    lb = df.iloc[-lookback:]
    low_i = int(lb["low"].idxmin())
    long_low = float(df.loc[low_i, "low"])
    out["gain_from_base_low_pct"] = round(price / long_low * 100 - 100, 1)
    why["gain_from_base_low_pct"] = f"close vs lowest low {long_low:.2f} on {df.loc[low_i,'date'].date()} (last {lookback} sessions)"

    # prior uptrend proxy: close > EMA50 > SMA200, SMA200 rising, >= 20% off the low
    if not np.isnan(sma200.iloc[-1]) and len(sma200.dropna()) > 20:
        up = (price > ema50.iloc[-1] > sma200.iloc[-1]) and (sma200.iloc[-1] > sma200.iloc[-21]) \
             and out["gain_from_base_low_pct"] >= 20
        out["prior_uptrend"] = bool(up)
        why["prior_uptrend"] = "close > EMA50 > SMA200, SMA200 rising over 20 sessions, >= 20% off base low"

    # advance start: first close >= 1.2x long low after the low
    after = df.loc[low_i:]
    adv = after.index[after["close"] >= 1.2 * long_low]
    if len(adv):
        a0 = int(adv[0])
        out["ema50_breaches"] = count_ema_breaches(c, ema50, a0)
        why["ema50_breaches"] = f"runs of >=2 closes below EMA50 since {df.loc[a0,'date'].date()}"
        # long base = sideways stretch (range <= max_base_depth) that ended where the advance began
        bl = base_length_days(h.values[:a0], l.values[:a0], max_base_depth)
        out["base_length_weeks"] = round(bl / 5, 1)
        why["base_length_weeks"] = (f"{bl} sessions with high-low range <= {max_base_depth}% "
                                    f"before the advance began on {df.loc[a0,'date'].date()}")
    else:
        bl = base_length_days(h.values, l.values, max_base_depth)
        out["base_length_weeks"] = round(bl / 5, 1)
        why["base_length_weeks"] = f"no advance yet: {bl} sessions in the current range <= {max_base_depth}%"

    # fall vs recover time
    pre = df.loc[: low_i - 1].iloc[-500:] if low_i > 0 else df.iloc[0:0]
    if len(pre):
        hi_i = int(pre["high"].idxmax())
        prior_high = float(df.loc[hi_i, "high"])
        level = long_low + retrace * (prior_high - long_low)
        rec = df.loc[low_i:].index[df.loc[low_i:, "close"] >= level]
        fall_days = low_i - hi_i
        if len(rec) and fall_days > 0:
            rec_days = int(rec[0]) - low_i
            out["fall_to_recover_ratio"] = round(fall_days / max(rec_days, 1), 2)
            why["fall_to_recover_ratio"] = (f"fell {fall_days} sessions from {prior_high:.2f}, "
                                            f"recovered {int(retrace*100)}% in {rec_days} sessions")
        else:
            why["fall_to_recover_ratio"] = "decline not yet retraced: left null"

    hi120 = c.iloc[-120:]
    rest = len(hi120) - 1 - int(np.argmax(hi120.values))
    out["rest_days"] = rest
    why["rest_days"] = "sessions since the highest close of the last 120"

    if bench is not None:
        ok, msg = resisted_decline(df, bench)
        if ok is not None:
            out["rs_resisted_decline"] = ok
        why["rs_resisted_decline"] = msg

    trade = {"pivot_price": round(pivot, 2), "stop_price": round(blow, 2)}
    info = {"ema21": round(float(ema21.iloc[-1]), 2),
            "sma200": None if np.isnan(sma200.iloc[-1]) else round(float(sma200.iloc[-1]), 2),
            "returns_pct": {k: (None if x is None else round(x, 2)) for k, x in rets.items()},
            "as_of": str(df["date"].iloc[-1].date())}
    return {"inputs": out, "trade": trade, "info": info, "method": why}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--benchmark")
    ap.add_argument("--base-days", type=int, default=15)
    ap.add_argument("--lookback", type=int, default=250)
    ap.add_argument("--max-base-depth", type=float, default=30.0)
    ap.add_argument("--retrace", type=float, default=1.0)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    df = load_ohlcv(a.csv)
    if len(df) < 120:
        raise SystemExit("need at least 120 sessions (250+ recommended)")
    bench = load_ohlcv(a.benchmark) if a.benchmark else None
    res = compute(df, bench, a.base_days, a.lookback, a.max_base_depth, a.retrace)
    txt = json.dumps(res, indent=2)
    if a.out:
        with open(a.out, "w") as f:
            f.write(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
