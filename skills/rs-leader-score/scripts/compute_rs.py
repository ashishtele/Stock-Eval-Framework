#!/usr/bin/env python3
"""
compute_rs.py - RS percentile rating across a whole universe, then the RS80 scan.

RS rating (transcript 25:28-29:06): rank every stock by its 3-month return,
convert to a percentile. Top 1% = 99, top 2% = 98 ... bottom = 1.
  rating = clip(100 - ceil(rank_from_top / N * 100), 1, 99)

Input A, a returns CSV with at least: symbol, ret_3m
  optional: ret_6m, ret_9m, ret_12m, industry, price, market_cap_cr,
            avg_turnover_30d_cr, price_above_200dma
Input B, --prices-dir with one OHLCV CSV per symbol (file name = symbol); returns,
  turnover and 200-DMA are computed for you. Add --meta CSV (symbol, industry,
  market_cap_cr) to bring in the non-price fields.

  python compute_rs.py returns.csv --out rs_scan.csv
  python compute_rs.py --prices-dir data/ --meta meta.csv --mode weighted --out rs_scan.csv

--mode 3m (default; the podcast's choice, after Faber 2010) or weighted
(0.4 x 3m + 0.2 x 6m + 0.2 x 9m + 0.2 x 12m, IBD-style).

The scan keeps names that pass every gate column present, then adds
group_count_in_scan (passing names in the same industry) and
leader_rank_in_group (rank by RS inside the industry; verify against who broke
out first, which is the podcast's real test).
"""
import argparse
import glob
import math
import os
import sys

import pandas as pd


def rs_ratings(scores):
    """scores: pd.Series of performance numbers (NaN dropped). Returns int ratings."""
    s = scores.dropna()
    n = len(s)
    rank_from_top = s.rank(ascending=False, method="min")
    r = (100 - (rank_from_top / n * 100).apply(math.ceil)).clip(1, 99).astype(int)
    return r.reindex(scores.index)


def from_prices(d, meta=None):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*.csv"))):
        df = pd.read_csv(p)
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.sort_values("date")
        c, v = df["close"].reset_index(drop=True), df["volume"].reset_index(drop=True)
        def ret(n):
            return c.iloc[-1] / c.iloc[-1 - n] * 100 - 100 if len(c) > n else float("nan")
        sma200 = c.rolling(200).mean().iloc[-1]
        rows.append({
            "symbol": os.path.splitext(os.path.basename(p))[0],
            "price": c.iloc[-1],
            "ret_3m": ret(63), "ret_6m": ret(126), "ret_9m": ret(189), "ret_12m": ret(252),
            "avg_turnover_30d_cr": (c * v).iloc[-30:].mean() / 1e7,
            "price_above_200dma": (c.iloc[-1] > sma200) if not pd.isna(sma200) else None,
        })
    out = pd.DataFrame(rows)
    if meta is not None:
        out = out.merge(meta, on="symbol", how="left")
    return out


def scan(df, mode="3m", rs_min=80, turnover_min=10, mcap_min=500, price_min=10):
    df = df.copy()
    if mode == "weighted":
        perf = 0.4 * df["ret_3m"] + 0.2 * df["ret_6m"] + 0.2 * df["ret_9m"] + 0.2 * df["ret_12m"]
    else:
        perf = df["ret_3m"]
    df["rs_rating"] = rs_ratings(perf)
    mask = df["rs_rating"] >= rs_min
    if "price_above_200dma" in df:
        mask &= df["price_above_200dma"].fillna(False).astype(bool)
    if "avg_turnover_30d_cr" in df:
        mask &= df["avg_turnover_30d_cr"] >= turnover_min
    if "market_cap_cr" in df:
        mask &= df["market_cap_cr"] >= mcap_min
    if "price" in df:
        mask &= df["price"] >= price_min
    df["passes_rs80_scan"] = mask
    sc = df[mask].copy()
    if "industry" in sc and sc["industry"].notna().any():
        sc["group_count_in_scan"] = sc.groupby("industry")["symbol"].transform("count")
        sc["leader_rank_in_group"] = sc.groupby("industry")["rs_rating"].rank(
            ascending=False, method="min").astype(int)
    return df, sc.sort_values(["rs_rating"], ascending=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("returns_csv", nargs="?")
    ap.add_argument("--prices-dir")
    ap.add_argument("--meta")
    ap.add_argument("--mode", choices=["3m", "weighted"], default="3m")
    ap.add_argument("--rs-min", type=int, default=80)
    ap.add_argument("--turnover-min", type=float, default=10)
    ap.add_argument("--mcap-min", type=float, default=500)
    ap.add_argument("--out")
    ap.add_argument("--all-out", help="write every stock with its rating too")
    a = ap.parse_args(argv)

    if a.prices_dir:
        meta = pd.read_csv(a.meta) if a.meta else None
        df = from_prices(a.prices_dir, meta)
    elif a.returns_csv:
        df = pd.read_csv(a.returns_csv)
    else:
        ap.print_help(); return 1

    full, sc = scan(df, a.mode, a.rs_min, a.turnover_min, a.mcap_min)
    print(f"Universe {len(full)} stocks -> {len(sc)} pass the RS{a.rs_min} scan")
    if "group_count_in_scan" in sc:
        top = sc.groupby("industry")["symbol"].count().sort_values(ascending=False).head(10)
        print("\nIndustries with the most names in the scan (theme strength):")
        print(top.to_string())
    cols = [c for c in ["symbol", "industry", "rs_rating", "ret_3m", "group_count_in_scan",
                        "leader_rank_in_group", "market_cap_cr", "avg_turnover_30d_cr", "price"] if c in sc]
    print("\n" + sc[cols].head(40).to_string(index=False))
    if a.out:
        sc.to_csv(a.out, index=False)
    if a.all_out:
        full.to_csv(a.all_out, index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
