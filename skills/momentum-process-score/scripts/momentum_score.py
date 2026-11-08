#!/usr/bin/env python3
"""
Process-over-Prediction Momentum Score (PoP-MS)  v1.0

A deterministic, auditable momentum scoring framework distilled from Manish Dhawan's
(Mystic Wealth) interview on systematic momentum investing. Every number in the output
can be recomputed by hand / in Excel from the price CSV using the formulas printed in
the report.

Sub-commands
  score       Score one stock (absolute 0-100) or rank a universe (top-20 entry / exit below 50)
  recovery    Gain needed to recover from a drawdown:  g = d / (1 - d)
  rr          Risk/reward check for a trade (framework wants >= 3:1)
  size        Position size per stock  = deployed equity fraction / N (capped at 5%)
  drypowder   How much of the gold/REIT/debt reserve to redeploy at the current drawdown
  selftest    Synthetic-data test of all formulas

Input price data: one CSV per stock (file name = symbol) or one long CSV with a
Symbol column. Columns (case-insensitive): Date, High, Low, Close, [Open], [Volume].
Prices must be split/bonus adjusted. >= 253 trading rows required (use ~300+).
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np
import pandas as pd

VERSION = "1.1"

CFG = dict(
    lb12=252, lb6=126, lb3=63, lb1=21, tq_window=126,
    ma_windows=(30, 50, 100, 200),
    prox_floor=0.75,          # must be within 25% of 52-week high
    momra_full=2.0,           # risk-adjusted momentum that earns full 40 pts
    circuit_move=0.0485,      # |daily move| that counts as a possible circuit if closed at the extreme
    circuit_max_days=10,      # gate: more locked-circuit days than this in 1y -> ineligible
    circuit_penalty=2.0,      # points lost per circuit day (out of 10)
    min_mcap_cr=3000.0,       # proxy for "Nifty 750" when rank unknown (approximate, configurable)
    max_mcap_rank=750,
    top_n=20, exit_rank=50, min_universe_for_rank=150,
    deployment=0.80, max_position=0.05,
    band_buy=75.0, band_hold=60.0,
)
W = dict(momentum=40.0, proximity=20.0, trend_quality=15.0, stage2=15.0, circuit=10.0)


# ----------------------------------------------------------------------------- loading
ALIASES = {
    "date": ["date", "timestamp", "datetime", "trade_date"],
    "open": ["open", "open_price"],
    "high": ["high", "high_price"],
    "low": ["low", "low_price"],
    "close": ["close", "close_price", "adj_close", "adjclose", "adjusted_close", "last", "ltp", "price"],
    "volume": ["volume", "total_traded_quantity", "tottrdqty", "qty", "vol", "shares"],
    "symbol": ["symbol", "ticker", "scrip", "stock"],
}


def _normalise(df):
    df = df.rename(columns={c: str(c).strip().lower().replace(" ", "_").replace(".", "") for c in df.columns})
    ren = {}
    for key, opts in ALIASES.items():
        for o in opts:
            if o in df.columns and o not in ren:
                ren[o] = key
                break
    df = df.rename(columns=ren)
    df = df.loc[:, ~df.columns.duplicated()]
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError("CSV needs at least Date and Close columns; found %s" % list(df.columns))
    for c in ("open", "high", "low", "close", "volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    d = pd.to_datetime(df["date"], errors="coerce")
    if d.isna().mean() > 0.2:
        d = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["date"] = d
    keys = ["symbol", "date"] if "symbol" in df.columns else ["date"]
    df = df.dropna(subset=["date", "close"]).sort_values(keys).drop_duplicates(keys, keep="last")
    return df.reset_index(drop=True)


def load_prices(csvs, folder):
    data = {}
    paths = list(csvs or [])
    if folder:
        paths += sorted(glob.glob(os.path.join(folder, "*.csv")))
    for p in paths:
        raw = pd.read_csv(p)
        df = _normalise(raw)
        if "symbol" in df.columns and df["symbol"].nunique() > 1:
            for s, g in df.groupby("symbol"):
                data[str(s).strip()] = g.drop(columns=["symbol"]).reset_index(drop=True)
        else:
            sym = str(df["symbol"].iloc[0]).strip() if "symbol" in df.columns else os.path.splitext(os.path.basename(p))[0]
            data[sym] = df.drop(columns=["symbol"], errors="ignore")
    return data


def load_meta(path):
    if not path:
        return {}
    m = pd.read_csv(path)
    m.columns = [str(c).strip().lower() for c in m.columns]
    out = {}
    for _, r in m.iterrows():
        sym = str(r.get("symbol", r.get("ticker", ""))).strip()
        if not sym:
            continue
        out[sym] = {k: r[k] for k in m.columns if k not in ("symbol", "ticker") and pd.notna(r[k])}
    return out


# ----------------------------------------------------------------------------- metrics
def _lin(x, x0, x1, pts):
    """Linear map x0->0 pts, x1->pts, clipped."""
    if x is None or not np.isfinite(x):
        return 0.0
    return float(np.clip((x - x0) / (x1 - x0), 0, 1) * pts)


TRUE = ("1", "true", "yes", "y", "t")
FALSE = ("0", "false", "no", "n", "f")


def _flag(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v).strip().lower()
    return True if s in TRUE else False if s in FALSE else None


def universe_gate(meta, cfg):
    """G1, in order of preference:
    1. in_nifty_tm  - membership of the Nifty Total Market index (= the guest's 'Nifty 750').
                      Screener.in lists it under 'Part of ... Nifty Total Market'.
    2. mcap_rank    - <= 750
    3. mcap_cr      - >= min_mcap_cr (rough proxy; the real cutoff moves every rebalance)."""
    tm = _flag(meta.get("in_nifty_tm"))
    mr, mc = meta.get("mcap_rank"), meta.get("mcap_cr")
    if tm is not None:
        return ("G1 Universe (Nifty Total Market member)", "index member = yes", "yes" if tm else "no", tm)
    if mr is not None and not (isinstance(mr, float) and math.isnan(mr)):
        return ("G1 Universe (Nifty 750)", "mcap_rank <= %d" % cfg["max_mcap_rank"], mr, float(mr) <= cfg["max_mcap_rank"])
    if mc is not None and not (isinstance(mc, float) and math.isnan(mc)):
        return ("G1 Universe (mcap proxy - verify index membership)", "mcap >= Rs %.0f cr" % cfg["min_mcap_cr"], mc, float(mc) >= cfg["min_mcap_cr"])
    return ("G1 Universe (Nifty 750)", "membership / mcap not supplied", "n/a", None)


def compute(sym, df, meta, cfg):
    r = {"symbol": sym, "rows": int(len(df)), "warnings": []}
    if len(df) == 0:
        r.update(data_ok=False)
        r["warnings"].append("No rows")
        return r
    r["asof"] = str(df["date"].iloc[-1].date())
    need = cfg["lb12"] + 1
    if len(df) < need:
        r["data_ok"] = False
        r["warnings"].append("Need >= %d trading rows, have %d" % (need, len(df)))
        return r
    r["data_ok"] = True
    c = df["close"].to_numpy(float)
    has_hl = {"high", "low"} <= set(df.columns) and df[["high", "low"]].iloc[-cfg["lb12"]:].notna().all().all()
    h = df["high"].to_numpy(float) if has_hl else c
    l = df["low"].to_numpy(float) if has_hl else c
    if not has_hl:
        r["warnings"].append("High/Low missing: 52WH uses closes; circuit filter cannot be verified")
    ret = c[1:] / c[:-1] - 1
    lr = np.log(c[1:] / c[:-1])

    if np.any(np.abs(ret[-cfg["lb12"]:]) > 0.35):
        r["warnings"].append("A daily move >35% in last year - check split/bonus adjustment")

    m = {}
    m["close"] = c[-1]
    m["R12"] = c[-1] / c[-1 - cfg["lb12"]] - 1
    m["R6"] = c[-1] / c[-1 - cfg["lb6"]] - 1
    m["R3"] = c[-1] / c[-1 - cfg["lb3"]] - 1
    m["R1"] = c[-1] / c[-1 - cfg["lb1"]] - 1
    m["sigma"] = float(np.std(lr[-cfg["lb12"]:], ddof=1) * math.sqrt(252))
    s = m["sigma"] if m["sigma"] > 1e-9 else float("nan")
    m["RAM6"] = m["R6"] / s
    m["RAM12"] = m["R12"] / s
    m["MomRA"] = 0.5 * m["RAM6"] + 0.5 * m["RAM12"]
    for w in cfg["ma_windows"]:
        m["MA%d" % w] = float(c[-w:].mean())
    m["H52"] = float(np.max(h[-cfg["lb12"]:]))
    m["L52"] = float(np.min(l[-cfg["lb12"]:]))
    m["prox"] = c[-1] / m["H52"]

    y = np.log(c[-cfg["tq_window"]:])
    x = np.arange(len(y), dtype=float)
    b, a = np.polyfit(x, y, 1)
    yhat = a + b * x
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    m["R2"] = 1 - float(np.sum((y - yhat) ** 2)) / ss_tot if ss_tot > 0 else 0.0
    m["slope_ann"] = math.exp(b * 252) - 1
    m["TQ"] = m["R2"] if b > 0 else 0.0

    cw, hw, lw, rw = c[-cfg["lb12"]:], h[-cfg["lb12"]:], l[-cfg["lb12"]:], ret[-cfg["lb12"]:]
    cm = cfg["circuit_move"]
    up = (rw >= cm) & (cw >= hw * (1 - 1e-4))
    dn = (rw <= -cm) & (cw <= lw * (1 + 1e-4))
    m["circuit_days"] = int(up.sum() + dn.sum()) if has_hl else 0
    if "volume" in df.columns and df["volume"].iloc[-63:].notna().all():
        m["med_traded_value_cr"] = float(np.median((df["close"] * df["volume"]).iloc[-63:]) / 1e7)
    m["doubled_12m"] = bool(m["R12"] >= 1.0)
    r["m"] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in m.items()}

    # ---------------- gates
    g = [universe_gate(meta, cfg)]
    stage = all(c[-1] > m["MA%d" % w] for w in cfg["ma_windows"])
    g.append(("G2 Stage-2 trend", "Close > MA30, MA50, MA100, MA200", "%.2f vs %s" % (c[-1], "/".join("%.1f" % m["MA%d" % w] for w in cfg["ma_windows"])), stage))
    g.append(("G3 Absolute momentum", "R12 > 0 and R6 > 0", "R12 %.1f%%, R6 %.1f%%" % (m["R12"] * 100, m["R6"] * 100), m["R12"] > 0 and m["R6"] > 0))
    g.append(("G4 Near 52-week high", "Close/H52 >= %.2f" % cfg["prox_floor"], round(m["prox"], 4), m["prox"] >= cfg["prox_floor"]))
    g.append(("G5 Circuit filter", "locked-circuit days (1y) <= %d" % cfg["circuit_max_days"], m["circuit_days"] if has_hl else "unverified", (m["circuit_days"] <= cfg["circuit_max_days"]) if has_hl else None))
    g = [(a, b_, v, None if p is None else bool(p)) for a, b_, v, p in g]  # numpy bool -> python bool
    r["gates"] = [dict(gate=a, rule=b_, value=v, passed=p) for a, b_, v, p in g]
    r["eligible"] = all(p is not False for *_, p in g)

    # ---------------- absolute points (single-stock score)
    pts = {}
    pts["momentum"] = _lin(m["MomRA"], 0.0, cfg["momra_full"], W["momentum"])
    pts["proximity"] = _lin(m["prox"], cfg["prox_floor"], 1.0, W["proximity"])
    pts["trend_quality"] = round(m["TQ"] * W["trend_quality"], 4)
    conds = [c[-1] > m["MA%d" % w] for w in cfg["ma_windows"]] + [m["MA50"] > m["MA200"]]
    pts["stage2"] = 3.0 * sum(conds)
    pts["circuit"] = max(0.0, W["circuit"] - cfg["circuit_penalty"] * m["circuit_days"]) if has_hl else W["circuit"] / 2
    r["stage2_conditions"] = dict(zip(["C>MA30", "C>MA50", "C>MA100", "C>MA200", "MA50>MA200"], [bool(x) for x in conds]))
    r["points"] = {k: round(v, 2) for k, v in pts.items()}
    r["score_abs"] = round(sum(pts.values()), 2)
    return r


def band(score, eligible, cfg):
    if not eligible:
        return "INELIGIBLE - avoid / exit if held"
    if score >= cfg["band_buy"]:
        return "BUY-ZONE (strong momentum)"
    if score >= cfg["band_hold"]:
        return "HOLD-ZONE (keep if owned, do not initiate)"
    return "EXIT/AVOID (weak momentum)"


# ----------------------------------------------------------------------------- universe ranking
def rank_universe(results, held, cfg):
    ok = [r for r in results if r.get("data_ok")]
    elig = [r for r in ok if r["eligible"]]
    U = len(ok)
    use_rank = U >= cfg["min_universe_for_rank"]
    if elig and use_rank:
        df = pd.DataFrame({
            "sym": [r["symbol"] for r in elig],
            "mom": [r["m"]["MomRA"] for r in elig],
            "prox": [r["m"]["prox"] for r in elig],
            "tq": [r["m"]["TQ"] for r in elig],
            "st": [r["points"]["stage2"] / W["stage2"] for r in elig],
            "ci": [r["points"]["circuit"] / W["circuit"] for r in elig],
        })
        for col in ("mom", "prox", "tq"):
            df[col + "_pct"] = df[col].rank(pct=True, method="average")
        df["score_rel"] = 100 * (
            W["momentum"] / 100 * df["mom_pct"] + W["proximity"] / 100 * df["prox_pct"]
            + W["trend_quality"] / 100 * df["tq_pct"] + W["stage2"] / 100 * df["st"] + W["circuit"] / 100 * df["ci"])
        df = df.sort_values(["score_rel", "mom"], ascending=False).reset_index(drop=True)
        df["rank"] = np.arange(1, len(df) + 1)
        lookup = df.set_index("sym")
        for r in elig:
            row = lookup.loc[r["symbol"]]
            r["score_rel"] = round(float(row["score_rel"]), 2)
            r["rank"] = int(row["rank"])
            r["pctiles"] = {k: round(float(row[k + "_pct"]), 4) for k in ("mom", "prox", "tq")}
    for r in results:
        is_held = r["symbol"] in held
        r["held"] = is_held
        if not r.get("data_ok"):
            r["decision"] = "NO DATA"
            continue
        if use_rank:
            rk = r.get("rank")
            if rk is None:
                r["decision"] = "EXIT (failed gate)" if is_held else "AVOID (failed gate)"
            elif rk <= cfg["top_n"]:
                r["decision"] = "HOLD (top %d)" % cfg["top_n"] if is_held else "BUY (top %d)" % cfg["top_n"]
            elif rk <= cfg["exit_rank"]:
                r["decision"] = "HOLD (rank <= %d)" % cfg["exit_rank"] if is_held else "WATCH (rank %d-%d, not top %d)" % (cfg["top_n"] + 1, cfg["exit_rank"], cfg["top_n"])
            else:
                r["decision"] = "EXIT (rank > %d)" % cfg["exit_rank"] if is_held else "AVOID (rank > %d)" % cfg["exit_rank"]
        else:
            r["decision"] = band(r["score_abs"], r["eligible"], cfg)
    # target portfolio (only meaningful in rank mode)
    target = []
    if use_rank and elig:
        keep = sorted([r for r in elig if r["held"] and r["rank"] <= cfg["exit_rank"]], key=lambda r: r["rank"])
        target = [r["symbol"] for r in keep][: cfg["top_n"]]
        for r in sorted(elig, key=lambda r: r["rank"]):
            if len(target) >= cfg["top_n"]:
                break
            if r["symbol"] not in target:
                target.append(r["symbol"])
    return dict(universe_size=U, eligible=len(elig), rank_mode=use_rank, target=target)


# ----------------------------------------------------------------------------- reporting
def pct(x):
    return "%.1f%%" % (x * 100)


def stock_md(r, cfg):
    if not r.get("data_ok"):
        return "### %s\nInsufficient data: %s\n" % (r["symbol"], "; ".join(r["warnings"]))
    m, p = r["m"], r["points"]
    L = ["### %s  (as of %s, %d rows)" % (r["symbol"], r["asof"], r["rows"]), ""]
    L.append("**Absolute score: %.1f / 100** -> %s" % (r["score_abs"], band(r["score_abs"], r["eligible"], cfg)))
    if "rank" in r:
        L.append("**Universe rank: %d** (relative score %.1f) -> **%s**" % (r["rank"], r["score_rel"], r["decision"]))
    elif "decision" in r:
        L.append("**Decision:** %s" % r["decision"])
    L += ["", "**Hard gates** (any FAIL = not eligible)", "", "| Gate | Rule | Value | Result |", "|---|---|---|---|"]
    for g in r["gates"]:
        res = "PASS" if g["passed"] else ("FAIL" if g["passed"] is False else "NOT VERIFIED")
        L.append("| %s | %s | %s | %s |" % (g["gate"], g["rule"], g["value"], res))
    L += ["", "**Score components** (recompute from CSV with these formulas)", "",
          "| Component | Formula | Input value | Points |", "|---|---|---|---|"]
    L.append("| A. Risk-adj momentum (max %d) | MomRA = 0.5*R6/sigma + 0.5*R12/sigma ; pts = clip(MomRA/%.1f,0,1)*40 | R6 %s, R12 %s, sigma %s -> MomRA %.3f | %.2f |"
             % (W["momentum"], cfg["momra_full"], pct(m["R6"]), pct(m["R12"]), pct(m["sigma"]), m["MomRA"], p["momentum"]))
    L.append("| B. Proximity to 52WH (max %d) | P = Close/H52 ; pts = clip((P-0.75)/0.25,0,1)*20 | %.2f / %.2f = %.4f | %.2f |"
             % (W["proximity"], m["close"], m["H52"], m["prox"], p["proximity"]))
    L.append("| C. Trend quality / '45-degree' (max %d) | R-squared of ln(Close) vs time, last %d days, x15 (0 if slope<0) | R2 %.3f, ann. slope %s | %.2f |"
             % (W["trend_quality"], cfg["tq_window"], m["R2"], pct(m["slope_ann"]), p["trend_quality"]))
    sc = r["stage2_conditions"]
    L.append("| D. Stage-2 alignment (max %d) | 3 pts each: %s | %s | %.2f |"
             % (W["stage2"], ", ".join(sc.keys()), ", ".join("Y" if v else "N" for v in sc.values()), p["stage2"]))
    L.append("| E. Circuit cleanliness (max %d) | 10 - 2 x locked-circuit days in 1y | %s days | %.2f |"
             % (W["circuit"], m["circuit_days"], p["circuit"]))
    L.append("| **Total** | | | **%.2f** |" % r["score_abs"])
    extra = "R3 %s, R1 %s, 52W low %.2f" % (pct(m["R3"]), pct(m["R1"]), m["L52"])
    if "med_traded_value_cr" in m:
        extra += ", median daily traded value Rs %.2f cr" % m["med_traded_value_cr"]
    if m.get("doubled_12m"):
        extra += ", doubled in 12m (Minervini-style leader)"
    L += ["", "Info: " + extra]
    if r["warnings"]:
        L.append("Warnings: " + "; ".join(r["warnings"]))
    return "\n".join(L) + "\n"


def build_report(results, summary, cfg):
    L = ["# Process-over-Prediction Momentum Score (v%s)" % VERSION, ""]
    L.append("Universe scored: %d stocks with data, %d pass all gates. Mode: %s." % (
        summary["universe_size"], summary["eligible"],
        "RANK (top %d buy, exit below rank %d)" % (cfg["top_n"], cfg["exit_rank"]) if summary["rank_mode"]
        else "ABSOLUTE bands (universe < %d, so top-20/50 rank rules are not meaningful)" % cfg["min_universe_for_rank"]))
    L.append("")
    ok = [r for r in results if r.get("data_ok")]
    key = (lambda r: (r.get("rank") or 10**9, -r["score_abs"])) if summary["rank_mode"] else (lambda r: -r["score_abs"])
    ok.sort(key=key)
    L += ["| # | Symbol | Abs score | Rel score | Rank | Gates | R12 | R6 | sigma | MomRA | Close/H52 | Decision |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(ok, 1):
        m = r["m"]
        L.append("| %d | %s | %.1f | %s | %s | %s | %s | %s | %s | %.2f | %.3f | %s |" % (
            i, r["symbol"], r["score_abs"], "%.1f" % r["score_rel"] if "score_rel" in r else "-",
            r.get("rank", "-"), "PASS" if r["eligible"] else "FAIL", pct(m["R12"]), pct(m["R6"]),
            pct(m["sigma"]), m["MomRA"], m["prox"], r["decision"]))
    bad = [r for r in results if not r.get("data_ok")]
    if bad:
        L.append("\nNo/insufficient data: " + ", ".join(r["symbol"] for r in bad))
    if summary["target"]:
        w = min(cfg["max_position"], cfg["deployment"] / cfg["top_n"])
        L += ["", "## Target portfolio after rebalance", "",
              "Equal weight %.2f%% each (deployment %.0f%% / %d stocks, cap %.0f%%). Remaining %.0f%% stays in the gold/REIT/debt dry-powder sleeve."
              % (w * 100, cfg["deployment"] * 100, cfg["top_n"], cfg["max_position"] * 100, (1 - w * len(summary["target"])) * 100), "",
              ", ".join(summary["target"])]
    L += ["", "## Stock detail", ""]
    detail = ok if len(ok) <= 25 else [r for r in ok if r.get("held") or (r.get("rank") or 999) <= cfg["top_n"]]
    for r in detail:
        L.append(stock_md(r, cfg))
    L += ["", "---", "Scores are mechanical outputs of a price-only momentum framework, not investment advice. "
          "The framework expects ~60% of individual picks to lose; edge comes from diversification (max 4-5% per stock), "
          "cutting losers at the exit rule and letting outliers run."]
    return "\n".join(L)


# ----------------------------------------------------------------------------- utilities
def recovery(d):
    return d / (1 - d)


def cmd_score(a):
    cfg = dict(CFG)
    for k in ("deployment", "top_n", "exit_rank", "min_mcap_cr", "min_universe_for_rank"):
        v = getattr(a, k, None)
        if v is not None:
            cfg[k] = v
    data = load_prices(a.csv, a.dir)
    if not data:
        sys.exit("No price files found.")
    meta = load_meta(a.meta)
    if a.mcap_cr is not None or a.mcap_rank is not None:
        for s in data:
            meta.setdefault(s, {})
            if a.mcap_cr is not None:
                meta[s]["mcap_cr"] = a.mcap_cr
            if a.mcap_rank is not None:
                meta[s]["mcap_rank"] = a.mcap_rank
    if a.meta:
        orphan_px = sorted(set(data) - set(meta))
        orphan_meta = sorted(set(meta) - set(data))
        if orphan_px or orphan_meta:
            print("WARNING ticker mismatch (key everything by NSE ticker; companies get renamed, e.g. "
                  "Shriram Pistons -> SPR Auto Technologies, ticker SHRIPISTON unchanged):\n"
                  "  price files without meta row: %s\n  meta rows without price file: %s"
                  % (", ".join(orphan_px) or "-", ", ".join(orphan_meta) or "-"), file=sys.stderr)
    held = set(a.held or [])
    unknown_held = sorted(held - set(data))
    if unknown_held:
        print("WARNING held symbols with no price file (cannot be scored -> treat as EXIT review): %s"
              % ", ".join(unknown_held), file=sys.stderr)
    for s, v in meta.items():
        if str(v.get("held", "")).strip().lower() in ("1", "true", "yes", "y"):
            held.add(s)
    results = []
    for s, df in data.items():
        if a.asof:
            df = df[df["date"] <= pd.Timestamp(a.asof)].reset_index(drop=True)
        results.append(compute(s, df, meta.get(s, {}), cfg))
    summary = rank_universe(results, held, cfg)
    md = build_report(results, summary, cfg)
    out = a.out or "momentum_report"
    with open(out + ".md", "w", encoding="utf-8") as f:
        f.write(md)
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(dict(version=VERSION, config=cfg, weights=W, summary=summary, results=results), f, indent=2, default=str)
    print(md)
    print("\nWrote %s.md and %s.json" % (out, out))


def cmd_recovery(a):
    g = recovery(a.drawdown)
    print("Drawdown %.1f%% -> need +%.1f%% to get back to the old peak.  (g = d / (1 - d))" % (a.drawdown * 100, g * 100))
    if a.cagr:
        yrs = math.log(1 + g) / math.log(1 + a.cagr)
        print("At %.1f%% CAGR that takes %.1f years just to break even." % (a.cagr * 100, yrs))


def cmd_rr(a):
    risk, reward = a.entry - a.stop, a.target - a.entry
    if risk <= 0:
        sys.exit("Stop must be below entry.")
    ratio = reward / risk
    print("Risk %.2f, reward %.2f -> R:R = %.2f : 1  -> %s (framework wants >= 3:1)" % (risk, reward, ratio, "PASS" if ratio >= 3 else "FAIL"))


def cmd_size(a):
    w = min(CFG["max_position"], a.deployment / a.n)
    print("Per-stock weight = min(%.0f%%, %.0f%% / %d) = %.2f%%" % (CFG["max_position"] * 100, a.deployment * 100, a.n, w * 100))
    if a.capital:
        print("On capital Rs %s -> Rs %s per stock; reserve sleeve Rs %s"
              % (f"{a.capital:,.0f}", f"{a.capital * w:,.0f}", f"{a.capital * (1 - w * a.n):,.0f}"))


def cmd_drypowder(a):
    dd = 1 - a.current / a.peak
    ladder = [float(x) for x in a.ladder.split(",")]
    tranche = a.reserve / len(ladder)
    hit = [t for t in ladder if dd >= t]
    print("Index drawdown from peak: %.1f%%  (1 - %.2f / %.2f)" % (dd * 100, a.current, a.peak))
    print("Ladder %s, each tranche = %.1f%% of portfolio" % (", ".join("-%.0f%%" % (t * 100) for t in ladder), tranche * 100))
    print("Triggered levels: %s -> cumulative redeployment into momentum = %.1f%% of portfolio"
          % (", ".join("-%.0f%%" % (t * 100) for t in hit) or "none", tranche * len(hit) * 100))


SNAP_STRONG_R12 = 0.20   # [calibration] 1y return needed for a STRONG pre-screen pass
SNAP_STRONG_PROX = 0.85  # [calibration] Close/H52 needed for a STRONG pre-screen pass


def snapshot_eval(r, cfg=CFG):
    """Evaluate one snapshot row (dict-like): price, high52, ret1y, optional ret6m, mcap_cr,
    mcap_rank, in_nifty_tm. Returns gates, proximity points, possible score range and verdict."""
    get = lambda k: (r[k] if k in r and not (isinstance(r[k], float) and math.isnan(r[k])) else None)
    P = float(get("price")) / float(get("high52"))
    g1 = universe_gate({k: get(k) for k in ("in_nifty_tm", "mcap_rank", "mcap_cr")}, cfg)
    r12, r6 = float(get("ret1y")), get("ret6m")
    g3 = r12 > 0 and (r6 is None or float(r6) > 0)
    g3_rule = "R12 > 0" + (" and R6 > 0" if r6 is not None else " (R6 unknown)")
    g4 = P >= cfg["prox_floor"]
    b = _lin(P, cfg["prox_floor"], 1.0, W["proximity"])
    gates = [("G1", g1[0], g1[3]), ("G3", g3_rule, g3), ("G4", "Close/H52 >= %.2f" % cfg["prox_floor"], g4)]
    fails = [n for n, _, ok in gates if ok is False]
    unknown_max = W["momentum"] + W["trend_quality"] + W["stage2"] + W["circuit"]
    if fails:
        verdict, tier = "INELIGIBLE (fails %s)" % ",".join(fails), "FAIL"
    else:
        strong = r12 >= SNAP_STRONG_R12 and P >= SNAP_STRONG_PROX
        tier = "STRONG" if strong else "MARGINAL"
        why = [] if strong else (["1Y < %.0f%%" % (SNAP_STRONG_R12 * 100)] if r12 < SNAP_STRONG_R12 else []) + \
            (["Close/H52 < %.2f" % SNAP_STRONG_PROX] if P < SNAP_STRONG_PROX else [])
        verdict = ("PASS-%s%s - needs daily prices for G2/G5 and A/C/D/E" % (tier, " (%s)" % ", ".join(why) if why else ""))
        if g1[3] is None:
            verdict += "; G1 unverified"
    return dict(symbol=r["symbol"], P=round(P, 4), gates=[dict(gate=n, rule=ru, passed=ok) for n, ru, ok in gates],
                g1_basis="%s: %s" % ({"G1 Universe (Nifty Total Market member)": "Nifty TM member", "G1 Universe (Nifty 750)": "mcap rank"}.get(g1[0], "mcap Rs cr (proxy)"), g1[2]), B=round(b, 2), lo=round(b, 2), hi=round(b + unknown_max, 2) if not fails else None,
                tier=tier, verdict=verdict)


def cmd_snapshot(a):
    """Pre-screen from snapshot data only (e.g. a Screener.in company page). A failed gate is definitive;
    a pass still needs daily data for the full score."""
    df = pd.read_csv(a.file)
    df.columns = [c.strip().lower() for c in df.columns]
    rows = ["| Symbol | Close/H52 | 1Y ret | G1 basis | G1 | G3 | G4 | B pts | Possible score | Verdict |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    out = []
    mark = lambda ok: "PASS" if ok else ("FAIL" if ok is False else "n/v")
    order = {"STRONG": 0, "MARGINAL": 1, "FAIL": 2}
    res = [snapshot_eval(r) for r in df.to_dict("records")]
    res.sort(key=lambda x: (order[x["tier"]], -x["B"]))
    for x, r in ((x, df[df["symbol"] == x["symbol"]].iloc[0]) for x in res):
        g = {d["gate"]: d["passed"] for d in x["gates"]}
        rows.append("| %s | %.3f | %+.0f%% | %s | %s | %s | %s | %.1f | %s | %s |" % (
            x["symbol"], x["P"], r["ret1y"] * 100, x["g1_basis"], mark(g["G1"]), mark(g["G3"]), mark(g["G4"]),
            x["B"], "%.1f - %.1f" % (x["lo"], x["hi"]) if x["hi"] is not None else "-", x["verdict"]))
        out.append(x)
    md = "\n".join(rows)
    print(md)
    if a.out:
        open(a.out + ".md", "w", encoding="utf-8").write(md)
        json.dump(out, open(a.out + ".json", "w"), indent=1, default=str)


# ----------------------------------------------------------------------------- self test
def _synth(n, mu, vol, seed, circuits=0):
    rng = np.random.default_rng(seed)
    r = rng.normal(mu / 252, vol / math.sqrt(252), n)
    idx = rng.choice(np.arange(n - 252, n), circuits, replace=False) if circuits else []
    for i in idx:
        r[i] = 0.05 if rng.random() > 0.3 else -0.05
    c = 100 * np.exp(np.cumsum(r))
    hi = c * (1 + np.abs(rng.normal(0, 0.006, n)))
    lo = c * (1 - np.abs(rng.normal(0, 0.006, n)))
    for i in idx:
        if r[i] > 0:
            hi[i] = c[i]
        else:
            lo[i] = c[i]
    d = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame(dict(date=d, high=hi, low=lo, close=c, volume=rng.integers(1e5, 1e6, n)))


def cmd_selftest(_):
    ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name)

    check("recovery 50% -> 100%", abs(recovery(0.5) - 1.0) < 1e-12)
    check("recovery 70% -> 233.3%", abs(recovery(0.7) - 7 / 3) < 1e-12)
    df = _synth(320, 0.6, 0.25, 1)
    r = compute("T", df, {"mcap_rank": 100}, CFG)
    c = df["close"].to_numpy()
    check("R12 matches hand calc", abs(r["m"]["R12"] - (c[-1] / c[-253] - 1)) < 1e-5)
    lr = np.diff(np.log(c))[-252:]
    check("sigma matches hand calc", abs(r["m"]["sigma"] - lr.std(ddof=1) * math.sqrt(252)) < 1e-5)
    check("MA200 matches", abs(r["m"]["MA200"] - c[-200:].mean()) < 1e-4)
    check("score in [0,100]", 0 <= r["score_abs"] <= 100)
    check("points sum to score", abs(sum(r["points"].values()) - r["score_abs"]) < 0.05)
    down = compute("D", _synth(320, -0.5, 0.3, 2), {}, CFG)
    check("downtrend fails stage-2 / momentum gate", not down["eligible"])
    circ = compute("C", _synth(320, 0.6, 0.25, 3, circuits=15), {}, CFG)
    check("circuit-heavy stock detected (>=12 days)", circ["m"]["circuit_days"] >= 12 and not circ["eligible"])
    short = compute("S", _synth(200, 0.3, 0.2, 4), {}, CFG)
    check("short history flagged", short["data_ok"] is False)
    # G1 precedence: index membership beats mcap proxy
    check("G1: in_nifty_tm=no overrides mcap 3026 >= 3000", universe_gate({"in_nifty_tm": "no", "mcap_cr": 3026}, CFG)[3] is False)
    check("G1: in_nifty_tm=yes passes even if mcap small", universe_gate({"in_nifty_tm": "yes", "mcap_cr": 900}, CFG)[3] is True)
    check("G1: falls back to mcap proxy", universe_gate({"mcap_cr": 3026}, CFG)[3] is True)
    check("G1: nothing supplied -> unverified", universe_gate({}, CFG)[3] is None)
    # snapshot tiers
    s = snapshot_eval(dict(symbol="L", price=2370, high52=2442, ret1y=1.41, in_nifty_tm="yes"))
    check("snapshot: strong leader -> PASS-STRONG, B=17.64", s["tier"] == "STRONG" and abs(s["B"] - 17.64) < 0.01)
    s = snapshot_eval(dict(symbol="P", price=6022, high52=6599, ret1y=0.04, in_nifty_tm="yes"))
    check("snapshot: +4% 1Y -> PASS-MARGINAL", s["tier"] == "MARGINAL")
    s = snapshot_eval(dict(symbol="W", price=477, high52=585, ret1y=0.10, mcap_cr=3026, in_nifty_tm="no"))
    check("snapshot: non-member fails G1", s["tier"] == "FAIL" and "G1" in s["verdict"])
    s = snapshot_eval(dict(symbol="X", price=95, high52=100, ret1y=0.5, ret6m=-0.05, in_nifty_tm="yes"))
    check("snapshot: negative R6 fails G3 when supplied", s["tier"] == "FAIL" and "G3" in s["verdict"])
    # universe of 200 to exercise rank mode
    res = [compute("S%03d" % i, _synth(320, np.random.default_rng(i).uniform(-0.4, 1.0), np.random.default_rng(i + 999).uniform(0.15, 0.6), i + 10), {}, CFG) for i in range(200)]
    summ = rank_universe(res, {"S000", "S001"}, CFG)
    check("rank mode active for 200 stocks", summ["rank_mode"])
    check("target portfolio has <= 20 names", 0 < len(summ["target"]) <= 20)
    ranks = sorted(r["rank"] for r in res if "rank" in r)
    check("ranks are 1..N contiguous", ranks == list(range(1, len(ranks) + 1)))
    top = [r for r in res if r.get("rank") == 1][0]
    check("rank-1 decision is BUY/HOLD", top["decision"].startswith(("BUY", "HOLD")))
    print("\nSELFTEST %s" % ("PASSED" if ok else "FAILED"))
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("score")
    s.add_argument("--csv", nargs="*", help="price CSV(s)")
    s.add_argument("--dir", help="folder of price CSVs (one per stock)")
    s.add_argument("--meta", help="CSV with symbol, mcap_cr, mcap_rank, held")
    s.add_argument("--mcap-cr", dest="mcap_cr", type=float, help="market cap in Rs crore (single-stock use)")
    s.add_argument("--mcap-rank", dest="mcap_rank", type=int, help="market-cap rank in India (single-stock use)")
    s.add_argument("--held", nargs="*", help="symbols currently held (for hold/exit logic)")
    s.add_argument("--deployment", type=float, help="fraction of portfolio in momentum (default 0.80)")
    s.add_argument("--top-n", dest="top_n", type=int)
    s.add_argument("--exit-rank", dest="exit_rank", type=int)
    s.add_argument("--min-mcap-cr", dest="min_mcap_cr", type=float)
    s.add_argument("--min-universe", dest="min_universe_for_rank", type=int)
    s.add_argument("--asof", help="YYYY-MM-DD: ignore data after this date (rebalance-date replay)")
    s.add_argument("--out", help="output path prefix (writes .md and .json)")
    s.set_defaults(f=cmd_score)
    r = sp.add_parser("recovery"); r.add_argument("--drawdown", type=float, required=True); r.add_argument("--cagr", type=float); r.set_defaults(f=cmd_recovery)
    q = sp.add_parser("rr"); [q.add_argument("--" + k, type=float, required=True) for k in ("entry", "stop", "target")]; q.set_defaults(f=cmd_rr)
    z = sp.add_parser("size"); z.add_argument("--deployment", type=float, default=0.8); z.add_argument("--n", type=int, default=20); z.add_argument("--capital", type=float); z.set_defaults(f=cmd_size)
    d = sp.add_parser("drypowder"); d.add_argument("--peak", type=float, required=True); d.add_argument("--current", type=float, required=True)
    d.add_argument("--reserve", type=float, default=0.20); d.add_argument("--ladder", default="0.10,0.20,0.30"); d.set_defaults(f=cmd_drypowder)
    n = sp.add_parser("snapshot", help="pre-screen from symbol,price,high52,low52,mcap_cr,ret1y CSV (e.g. Screener.in)")
    n.add_argument("--file", required=True); n.add_argument("--out"); n.set_defaults(f=cmd_snapshot)
    t = sp.add_parser("selftest"); t.set_defaults(f=cmd_selftest)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
