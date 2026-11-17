#!/usr/bin/env python3
"""
ATH Momentum Score - deterministic scorer for the "3-criteria all-time-high"
momentum framework (based on Rohan Mehta's talk on the Kushal Lodha podcast).

Usage:
    python score.py input.json                 # markdown report to stdout
    python score.py input.json --json out.json # also write machine-readable result
    python score.py input.json --ath-tol 3     # override ATH tolerance (%)

Input: a JSON file with {"config": {...}, "stocks": [...], "portfolio": {...}}
(see assets/input_template.json). Every number used is echoed in the report,
so any score can be re-checked by hand.

Only the Python standard library is used.
"""
import argparse
import csv
import json
import math
import sys
from datetime import date, datetime, timedelta

DEFAULT_CONFIG = {
    "ath_tolerance_pct": 5.0,          # price within X% of ATH counts as "at ATH"
    "outperformance_margin_pct": 0.0,  # stock 52w return must beat benchmark by > this
    "profit_tolerance_pct": 0.5,
    "oneoff_proxy": False,             # estimate one-offs from other_income/pbt when no 'exceptional' given       # absorbs rounding between quarterly sums and annual figures
    "ema_period": 200,                 # default pre-decided exit = 200-EMA
    "universe_max_mcap_rank": 750,     # Nifty Total Market style universe
    "top_rank_cutoff": 150,            # 52w-return rank that counts as "leader"
    "top_rank_target_share_pct": 80.0, # % of invested weight that should sit in top-150
    "portfolio_value": None,
    "max_portfolio_drawdown_pct": 18.0,
    "target_positions": 15,
    "min_positions": 10,
    "max_positions": 20,
    "max_position_pct": 25.0,
    "apply_sin_filter": True,
}

SIN_TAGS = {"animal_killing", "meat", "liquor", "alcohol", "tobacco",
            "leather", "hotels", "casino", "gambling"}

# 18-point governance checklist. Items marked [T] are named in the transcript;
# the rest are standard hygiene checks added to complete the 18 (documented
# in references/framework.md). Each item: "good" | "neutral" | "bad" | null.
GOVERNANCE_ITEMS = [
    ("litigation", "[T] Material litigation / legal cases against company"),
    ("regulatory_action", "[T] SEBI / regulator / enforcement action"),
    ("promoter_conduct", "[T] Promoter fraud, 'fishy' dealings, siphoning"),
    ("related_party_mergers", "[T] Value-destroying or related-party mergers"),
    ("excess_debt", "[T] Debt excessive for the sector (banks/NBFCs judged differently)"),
    ("duplicate_business", "[T] Duplicates a business already held (neutral, not bad)"),
    ("promoter_pledge", "Promoter share pledge high or rising"),
    ("auditor_issues", "Auditor resignation / qualified opinion / frequent change"),
    ("accounting_quality", "Aggressive accounting, frequent restatements"),
    ("cfo_vs_profit", "Operating cash flow persistently far below reported profit"),
    ("related_party_transactions", "Large related-party transactions"),
    ("contingent_liabilities", "Contingent liabilities large vs net worth"),
    ("dilution", "Frequent equity dilution / warrants to promoters"),
    ("minority_treatment", "Poor minority-shareholder treatment"),
    ("board_independence", "Weak board independence"),
    ("disclosure_quality", "Late / poor disclosures"),
    ("insider_selling", "Heavy promoter / insider selling"),
    ("credit_rating", "Credit rating downgrade / default history"),
]


# ----------------------------------------------------------------- helpers
def parse_date(s):
    if isinstance(s, date):
        return s
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised date: {s}")


def load_series(spec, base_dir):
    """spec: list of [date, close] OR {"csv": path, "date_col":.., "close_col":..}"""
    if spec is None:
        return None
    rows = []
    if isinstance(spec, dict) and "csv" in spec:
        import os
        path = spec["csv"]
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        dcol = spec.get("date_col", "Date")
        ccol = spec.get("close_col", "Close")
        with open(path, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                try:
                    v = float(str(r[ccol]).replace(",", ""))
                except (ValueError, KeyError):
                    continue
                rows.append((parse_date(r[dcol]), v))
    else:
        rows = [(parse_date(d), float(c)) for d, c in spec]
    rows.sort(key=lambda x: x[0])
    return rows


def ema(values, period):
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def return_over(series, as_of, days=365):
    """% return from last close on/before (as_of - days) to last close on/before as_of."""
    cur = [r for r in series if r[0] <= as_of]
    if not cur:
        return None
    end = cur[-1][1]
    target = as_of - timedelta(days=days)
    past = [r for r in cur if r[0] <= target]
    if not past:
        return None
    start = past[-1][1]
    return (end / start - 1) * 100.0


def fmt(x, nd=2, suffix=""):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return "n/a"
        return f"{x:,.{nd}f}{suffix}"
    return str(x)


def tri(v):
    return {True: "PASS", False: "FAIL", None: "UNKNOWN"}[v]


# ----------------------------------------------------------------- per stock
def price_block(stock, cfg, as_of, base_dir):
    p = stock.get("price", {}) or {}
    series = load_series(p.get("series"), base_dir)
    close = p.get("close")
    ath = p.get("ath")
    ema_v = p.get("ema200")
    r52 = p.get("return_52w_pct")
    notes = []
    if series:
        upto = [r for r in series if r[0] <= as_of]
        closes = [c for _, c in upto]
        if closes:
            close = close if close is not None else closes[-1]
            s_ath = max(closes)
            if ath is None:
                ath = s_ath
                notes.append(f"ATH computed from supplied series starting {upto[0][0]} "
                             "(true ATH only if series covers full listing history)")
            if ema_v is None:
                ema_v = ema(closes, cfg["ema_period"])
                if ema_v is None:
                    notes.append(f"<{cfg['ema_period']} closes: EMA not computable")
            if r52 is None:
                r52 = return_over(upto, as_of)
    return close, ath, ema_v, r52, notes


def oneoff_proxy(quarters, tax=0.25):
    """Mechanical one-off estimate when the data source has no 'exceptional' row
    (Screener folds exceptional items into Other Income). Per quarter:
      (a) other_income < 0 or > 2x median other_income -> (OI - median) x (1 - tax)
      (b) pat > pbt > 0 (tax credit)                     -> pat - pbt x (1 - tax)
    Returns a list of estimates aligned with `quarters`."""
    import statistics
    ois = [q.get("other_income") for q in quarters if q.get("other_income") is not None]
    med = statistics.median(ois) if ois else 0
    out = []
    for q in quarters:
        e = 0.0
        oi, pbt, pat = q.get("other_income"), q.get("pbt"), q.get("pat")
        if oi is not None and (oi < 0 or (med > 0 and oi > 2 * med)):
            e += (oi - med) * (1 - tax)
        if pbt is not None and pat is not None and pbt > 0 and pat > pbt:
            e += pat - pbt * (1 - tax)
        out.append(round(e, 1))
    return out


def ttm_series(quarters, use_proxy=False):
    """quarters oldest->newest: {"period","pat","exceptional"[, "other_income","pbt"]}.
    Returns list of (period, ttm_adj). If use_proxy, quarters without an explicit
    'exceptional' value get the oneoff_proxy() estimate."""
    proxy = oneoff_proxy(quarters) if use_proxy else [0.0] * len(quarters)
    adj = []
    for q, px in zip(quarters, proxy):
        pat = q.get("pat")
        if pat is None:
            adj.append((q.get("period"), None))
            continue
        exc = q["exceptional"] if q.get("exceptional") is not None else px
        adj.append((q.get("period"), float(pat) - float(exc)))
    out = []
    for i in range(3, len(adj)):
        window = adj[i - 3:i + 1]
        if any(v is None for _, v in window):
            out.append((adj[i][0], None))
        else:
            out.append((adj[i][0], sum(v for _, v in window)))
    return out


def score_stock(stock, cfg, ctx, base_dir):
    as_of = ctx["as_of"]
    name = stock.get("name", "?")
    held = bool(stock.get("held", False))
    asset_type = stock.get("asset_type", "equity")
    rules = []   # (id, rule, inputs, result)
    gates = []

    # ---- Gate 1: universe
    mrank = stock.get("mcap_rank")
    in_univ = stock.get("in_universe")  # e.g. listed in Nifty Total Market
    if mrank is not None:
        g_univ = mrank <= cfg["universe_max_mcap_rank"]
    elif in_univ is not None:
        g_univ = bool(in_univ)
    else:
        g_univ = None
    if asset_type != "equity":
        g_univ = True
    gates.append(("G1", f"In universe (market-cap rank <= {cfg['universe_max_mcap_rank']} / Nifty Total Market)",
                  f"mcap_rank={fmt(mrank,0)} in_universe={fmt(in_univ)} asset_type={asset_type}", g_univ))

    # ---- Gate 2: sin filter
    tags = {t.lower() for t in stock.get("business_tags", [])}
    hit = sorted(tags & SIN_TAGS)
    if cfg["apply_sin_filter"]:
        g_sin = not hit
        gates.append(("G2", "Not a 'sin' business (animal killing, liquor, tobacco, leather, hotels, casinos)",
                      f"tags={sorted(tags) or '[]'}", g_sin))
    else:
        g_sin = True
        gates.append(("G2", "Sin filter disabled by config", "-", True))

    # ---- Gate 3: governance
    gov = stock.get("governance", {}) or {}
    bad = [k for k, _ in GOVERNANCE_ITEMS if str(gov.get(k, "")).lower() == "bad"]
    neutral = [k for k, _ in GOVERNANCE_ITEMS if str(gov.get(k, "")).lower() == "neutral"]
    answered = [k for k, _ in GOVERNANCE_ITEMS if gov.get(k) not in (None, "")]
    if asset_type != "equity":
        g_gov, gov_rating = True, "n/a (non-equity)"
    elif bad:
        g_gov, gov_rating = False, "BAD"
    elif not answered:
        g_gov, gov_rating = None, "NOT CHECKED"
    elif neutral:
        g_gov, gov_rating = True, "NEUTRAL (discuss)"
    else:
        g_gov, gov_rating = True, "GOOD"
    gates.append(("G3", "Governance checklist has no 'bad' item",
                  f"answered={len(answered)}/18 bad={bad or '[]'} neutral={neutral or '[]'}", g_gov))

    # ---- C1: price at/near all-time high
    close, ath, ema_v, r52, pnotes = price_block(stock, cfg, as_of, base_dir)
    tol = cfg["ath_tolerance_pct"]
    if close is None or ath is None:
        c1, dist = None, None
    else:
        dist = (ath - close) / ath * 100.0 if ath else None
        c1 = dist is not None and dist <= tol + 1e-9
    rules.append(("C1", f"Price at/near ALL-TIME HIGH (<= {tol}% below ATH)",
                  f"close={fmt(close)} ATH={fmt(ath)} gap={fmt(dist,2,'%')}", c1))

    # ---- C2: TTM profit at all-time high (ex one-offs)  /  demand>supply for commodities
    ttm_now = ttm_prev_max = None
    if asset_type == "equity":
        if stock.get("ttm_pat_history"):
            hist = [(h.get("period"), h.get("ttm_pat")) for h in stock["ttm_pat_history"]]
        else:
            hist = ttm_series(stock.get("quarterly_pat", []), use_proxy=cfg.get("oneoff_proxy", False))
        vals = [v for _, v in hist]
        # Optional longer history: full-year PAT figures (e.g. 10+ years from Screener P&L).
        # Their max extends the "all-time" look-back beyond the quarterly window.
        annual = [a.get("pat") for a in stock.get("annual_pat", []) if a.get("pat") is not None]
        annual_max = max(annual) if annual else None
        if len(vals) >= 1 and vals[-1] is not None and (len(vals) >= 2 or annual):
            ttm_now = vals[-1]
            prev = [v for v in vals[:-1] if v is not None]
            if annual_max is not None:
                prev.append(annual_max)
            ttm_prev_max = max(prev) if prev else None
            ptol = cfg.get("profit_tolerance_pct", 0.0) / 100.0
            c2 = (ttm_prev_max is not None and ttm_now > 0
                  and ttm_now >= ttm_prev_max * (1 - ptol))
        elif len(vals) == 1 and vals[-1] is not None:
            ttm_now, c2 = vals[-1], None
        else:
            c2 = None
        n_q = len(stock.get("quarterly_pat", []))
        rules.append(("C2", "TTM PAT (ex exceptional/one-off items) at ALL-TIME HIGH",
                      f"TTM_now={fmt(ttm_now)} prior_TTM_peak={fmt(ttm_prev_max)} "
                      f"(quarters supplied={n_q}, TTM points={len(vals)}, "
                      f"max annual PAT={fmt(annual_max)} over {len(annual)} yrs)", c2))
    else:
        d = stock.get("demand_exceeds_supply")
        c2 = None if d is None else bool(d)
        rules.append(("C2", "Commodity substitute: demand > supply (latest industry data)",
                      f"demand_exceeds_supply={fmt(d)} source={stock.get('demand_source','?')}", c2))

    # ---- C3: 52-week outperformance vs benchmark AND sector index
    bench = stock.get("benchmark_return_52w_pct", ctx.get("benchmark_return_52w_pct"))
    sect = stock.get("sector_return_52w_pct")
    m = cfg["outperformance_margin_pct"]
    if r52 is None or bench is None:
        c3 = None
    else:
        beat_b = r52 > bench + m
        beat_s = True if sect is None else r52 > sect + m
        c3 = beat_b and beat_s
    rules.append(("C3", f"52-week return beats Nifty 500 AND own sector index (margin {m}%)",
                  f"stock={fmt(r52,2,'%')} N500={fmt(bench,2,'%')} "
                  f"sector[{stock.get('sector_index','n/a')}]={fmt(sect,2,'%')}", c3))

    passed = sum(1 for _, _, _, v in rules if v is True)
    unknown = sum(1 for _, _, _, v in rules if v is None)

    # ---- pre-decided exit (stop)
    pos = stock.get("position", {}) or {}
    exit_price = pos.get("exit_price", ema_v)
    if "exit_price" in pos:
        exit_basis = "user exit_price"
    elif (stock.get("price") or {}).get("ema200") is not None:
        exit_basis = f"{cfg['ema_period']}-day avg (supplied)"
    else:
        exit_basis = f"{cfg['ema_period']}-EMA (computed)"
    stop_hit = None
    if close is not None and exit_price is not None:
        stop_hit = close < exit_price

    # ---- 52w-return rank component
    em_rank = stock.get("em_rank")
    usize = stock.get("universe_size", ctx.get("universe_size", cfg["universe_max_mcap_rank"]))
    rank_pct = None
    if em_rank is not None and usize and usize > 1:
        rank_pct = max(0.0, min(1.0, 1 - (em_rank - 1) / (usize - 1)))

    # ---- composite 0-100
    pts = 25 * passed
    avail = 75
    if rank_pct is not None:
        pts += 25 * rank_pct
        avail += 25
    score = round(pts / avail * 100, 1)

    # ---- classification + action
    gate_fail = [g for g in gates if g[3] is False]
    gate_unknown = [g for g in gates if g[3] is None]
    if passed == 3:
        cls = "SUPER PERFORMER"
    elif passed == 2:
        cls = "PERFORMER"
    else:
        cls = "UNDERPERFORMER"

    if gate_fail:
        action = "REJECT / EXIT - failed gate: " + ", ".join(g[0] for g in gate_fail)
    elif held and stop_hit:
        action = f"EXIT - pre-decided exit hit (close {fmt(close)} < {exit_basis} {fmt(exit_price)})"
    elif cls == "SUPER PERFORMER":
        action = "BUY / ADD (average up allowed)" if not stop_hit else \
                 "WAIT - all 3 pass but price below exit level; no valid risk budget"
    elif cls == "PERFORMER":
        action = "HOLD - do not add" if held else "WATCHLIST - do not buy (needs 3/3)"
    else:
        action = "EXIT & REPLACE" if held else "AVOID"
    if unknown:
        action += f"  [!] {unknown} criterion/criteria UNKNOWN - fetch data before acting"
    if gate_unknown and not gate_fail:
        action += "  [!] gate(s) not verified: " + ", ".join(g[0] for g in gate_unknown)

    # ---- sizing (risk-budget method)
    sizing = None
    buyable = action.startswith("BUY")
    if buyable and close is not None and exit_price is not None and close > exit_price:
        n = cfg["target_positions"]
        risk_pct = cfg["max_portfolio_drawdown_pct"] / n
        stop_dist_pct = (close - exit_price) / close * 100.0
        raw = risk_pct / stop_dist_pct * 100.0
        alloc = min(raw, cfg["max_position_pct"])
        sizing = {
            "risk_per_position_pct": round(risk_pct, 3),
            "stop_distance_pct": round(stop_dist_pct, 2),
            "raw_allocation_pct": round(raw, 2),
            "allocation_pct": round(alloc, 2),
            "capped": raw > cfg["max_position_pct"],
        }
        if cfg.get("portfolio_value"):
            pv = cfg["portfolio_value"]
            sizing["amount"] = round(pv * alloc / 100.0, 0)
            sizing["max_loss_at_exit"] = round(pv * alloc / 100.0 * stop_dist_pct / 100.0, 0)

    return {
        "name": name, "ticker": stock.get("ticker"), "held": held, "asset_type": asset_type,
        "sector": stock.get("sector"),
        "gates": [{"id": a, "rule": b, "inputs": c, "result": tri(d)} for a, b, c, d in gates],
        "governance_rating": gov_rating,
        "criteria": [{"id": a, "rule": b, "inputs": c, "result": tri(d)} for a, b, c, d in rules],
        "criteria_passed": passed, "criteria_unknown": unknown,
        "classification": cls, "action": action,
        "score_0_100": score, "score_basis": f"{fmt(pts,1)} / {avail} pts",
        "em_rank": em_rank, "rank_pct": None if rank_pct is None else round(rank_pct, 4),
        "close": close, "ath": ath, "ema": ema_v, "return_52w_pct": r52,
        "exit_price": exit_price, "exit_basis": exit_basis, "stop_hit": stop_hit,
        "sizing": sizing, "buyable": buyable,
        "notes": pnotes
                 + ([f"Governance only partially checked ({len(answered)}/18 items answered)"]
                    if asset_type == "equity" and 0 < len(answered) < 18 else [])
                 + ([stock["notes"]] if stock.get("notes") else []),
        "sources": stock.get("sources", {}),
    }


# ----------------------------------------------------------------- portfolio
def portfolio_checks(results, stocks, cfg, ctx):
    pf = ctx.get("portfolio") or {}
    held = [(r, s) for r, s in zip(results, stocks) if s.get("held")]
    if not held and not pf:
        return None
    out = {"checks": [], "positions": []}
    n = len(held)
    out["checks"].append(("P1", f"Number of holdings within {cfg['min_positions']}-{cfg['max_positions']}",
                          f"holdings={n}", cfg["min_positions"] <= n <= cfg["max_positions"]))
    weights = {s.get("name"): s.get("weight_pct") for _, s in held}
    tot_w = sum(w for w in weights.values() if w is not None)
    top_w = sum(s.get("weight_pct") or 0 for r, s in held
                if r["em_rank"] is not None and r["em_rank"] <= cfg["top_rank_cutoff"])
    if tot_w > 0:
        share = top_w / tot_w * 100
        out["checks"].append(("P2", f">= {cfg['top_rank_target_share_pct']}% of invested weight in "
                              f"top-{cfg['top_rank_cutoff']} by 52w return",
                              f"share={fmt(share,1,'%')}", share >= cfg["top_rank_target_share_pct"]))
    bmtd = pf.get("benchmark_return_mtd_pct")
    total_alpha_contrib = 0.0
    have_mtd = bmtd is not None
    for r, s in held:
        w, rm = s.get("weight_pct"), s.get("return_mtd_pct")
        alpha = None if (rm is None or bmtd is None) else rm - bmtd
        contrib = None if (alpha is None or w is None) else w * alpha / 100.0
        if contrib is not None:
            total_alpha_contrib += contrib
        trim = r["classification"] == "UNDERPERFORMER" and alpha is not None and alpha < 0
        out["positions"].append({
            "name": r["name"], "class": r["classification"], "weight_pct": w,
            "return_mtd_pct": rm, "alpha_mtd_pct": alpha, "alpha_contrib_pct": contrib,
            "em_rank": r["em_rank"], "trim_flag": trim or r["action"].startswith(("EXIT", "REJECT")),
        })
    cash = pf.get("cash_pct")
    cash_drag = None
    if cash is not None and have_mtd:
        cash_drag = -cash * bmtd / 100.0
        total_alpha_contrib += cash_drag
    out["cash_pct"] = cash
    out["cash_alpha_contrib_pct"] = cash_drag
    out["portfolio_alpha_mtd_pct"] = total_alpha_contrib if have_mtd else None
    # class buckets
    buckets = {}
    for p in out["positions"]:
        b = buckets.setdefault(p["class"], {"weight": 0.0, "alpha_contrib": 0.0, "n": 0})
        b["n"] += 1
        b["weight"] += p["weight_pct"] or 0
        b["alpha_contrib"] += p["alpha_contrib_pct"] or 0
    out["buckets"] = buckets
    return out


# ----------------------------------------------------------------- report
def report(results, pfo, cfg, ctx):
    L = []
    L.append(f"# ATH Momentum Score - {ctx['as_of']}")
    L.append("")
    L.append(f"Config: ATH tolerance {cfg['ath_tolerance_pct']}%, outperformance margin "
             f"{cfg['outperformance_margin_pct']}%, exit = {cfg['ema_period']}-EMA unless given, "
             f"risk budget {cfg['max_portfolio_drawdown_pct']}% / {cfg['target_positions']} positions, "
             f"sin filter {'on' if cfg['apply_sin_filter'] else 'off'}, "
             f"profit tolerance {cfg['profit_tolerance_pct']}%, one-off proxy {'on' if cfg['oneoff_proxy'] else 'off'}.")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append("| Stock | Criteria | Class | Score | 52w rank | Action |")
    L.append("|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: (-x["criteria_passed"], -x["score_0_100"])):
        L.append(f"| {r['name']} | {r['criteria_passed']}/3 | {r['classification']} | "
                 f"{r['score_0_100']} | {fmt(r['em_rank'],0)} | {r['action']} |")
    L.append("")
    for r in results:
        L.append(f"## {r['name']}" + (f" ({r['ticker']})" if r.get("ticker") else ""))
        L.append("")
        L.append(f"**{r['classification']}** - {r['criteria_passed']}/3 criteria - "
                 f"score {r['score_0_100']}/100 ({r['score_basis']}) - governance {r['governance_rating']}")
        L.append("")
        L.append(f"**Action:** {r['action']}")
        L.append("")
        L.append("| # | Rule | Inputs | Result |")
        L.append("|---|---|---|---|")
        for g in r["gates"]:
            L.append(f"| {g['id']} | {g['rule']} | {g['inputs']} | {g['result']} |")
        for c in r["criteria"]:
            L.append(f"| {c['id']} | {c['rule']} | {c['inputs']} | **{c['result']}** |")
        L.append(f"| X | Pre-decided exit ({r['exit_basis']}) | close={fmt(r['close'])} "
                 f"exit={fmt(r['exit_price'])} | {'HIT' if r['stop_hit'] else ('not hit' if r['stop_hit'] is False else 'UNKNOWN')} |")
        L.append("")
        s = r["sizing"]
        if s:
            line = (f"Sizing: risk/position {s['risk_per_position_pct']}% / stop distance "
                    f"{s['stop_distance_pct']}% = {s['raw_allocation_pct']}%")
            if s["capped"]:
                line += f" -> capped at {s['allocation_pct']}%"
            else:
                line += f" -> allocate {s['allocation_pct']}%"
            if "amount" in s:
                line += f" (= {fmt(s['amount'],0)}; loss at exit ~ {fmt(s['max_loss_at_exit'],0)})"
            L.append(line)
            L.append("")
        elif r["buyable"] and r["close"] is not None and r["exit_price"] is not None:
            L.append("Sizing: price is at/below exit level - no position size (no valid risk budget).")
            L.append("")
        if r["rank_pct"] is not None:
            L.append(f"Rank points: 25 x (1 - ({r['em_rank']}-1)/(universe-1)) = {round(25*r['rank_pct'],2)}")
            L.append("")
        for n in r["notes"]:
            L.append(f"- Note: {n}")
        if r["sources"]:
            for k, v in r["sources"].items():
                L.append(f"- Source [{k}]: {v}")
        if r["notes"] or r["sources"]:
            L.append("")
    if pfo:
        L.append("## Portfolio diagnostics")
        L.append("")
        L.append("| # | Check | Value | Result |")
        L.append("|---|---|---|---|")
        for a, b, c, d in pfo["checks"]:
            L.append(f"| {a} | {b} | {c} | {tri(d)} |")
        L.append("")
        if pfo["positions"]:
            L.append("| Holding | Class | Weight | MTD ret | MTD alpha | Alpha contrib | 52w rank | Trim/Exit |")
            L.append("|---|---|---|---|---|---|---|---|")
            for p in pfo["positions"]:
                L.append(f"| {p['name']} | {p['class']} | {fmt(p['weight_pct'],1,'%')} | "
                         f"{fmt(p['return_mtd_pct'],2,'%')} | {fmt(p['alpha_mtd_pct'],2,'%')} | "
                         f"{fmt(p['alpha_contrib_pct'],3,'%')} | {fmt(p['em_rank'],0)} | "
                         f"{'YES' if p['trim_flag'] else '-'} |")
            if pfo.get("cash_pct") is not None:
                L.append(f"| CASH | - | {fmt(pfo['cash_pct'],1,'%')} | 0.00% | - | "
                         f"{fmt(pfo['cash_alpha_contrib_pct'],3,'%')} | - | - |")
            L.append("")
        for k, b in pfo["buckets"].items():
            L.append(f"- {k}: {b['n']} holdings, {fmt(b['weight'],1,'%')} weight, "
                     f"alpha contribution {fmt(b['alpha_contrib'],3,'%')}")
        if pfo.get("portfolio_alpha_mtd_pct") is not None:
            L.append(f"- Portfolio MTD alpha (incl. cash drag): {fmt(pfo['portfolio_alpha_mtd_pct'],3,'%')}")
        L.append("")
    L.append("---")
    L.append("Rule-based screen derived from a podcast discussion; not investment advice. "
             "Verify every input against its source before acting.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--json", help="write machine-readable results here")
    ap.add_argument("--ath-tol", type=float)
    ap.add_argument("--margin", type=float)
    ap.add_argument("--no-sin-filter", action="store_true")
    ap.add_argument("--oneoff-proxy", action="store_true",
                    help="estimate one-off items from other_income / pbt (see oneoff_proxy)")
    a = ap.parse_args()

    import os
    base_dir = os.path.dirname(os.path.abspath(a.input))
    with open(a.input, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        data = {"stocks": data}
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(data.get("config", {}) or {})
    if a.ath_tol is not None:
        cfg["ath_tolerance_pct"] = a.ath_tol
    if a.margin is not None:
        cfg["outperformance_margin_pct"] = a.margin
    if a.no_sin_filter:
        cfg["apply_sin_filter"] = False
    if a.oneoff_proxy:
        cfg["oneoff_proxy"] = True

    ctx = {
        "as_of": parse_date(data.get("as_of", date.today().isoformat())),
        "benchmark_return_52w_pct": data.get("benchmark_return_52w_pct"),
        "universe_size": data.get("universe_size"),
        "portfolio": data.get("portfolio"),
    }
    bser = data.get("benchmark_series")
    if ctx["benchmark_return_52w_pct"] is None and bser:
        ctx["benchmark_return_52w_pct"] = return_over(load_series(bser, base_dir), ctx["as_of"])

    stocks = data.get("stocks", [])
    results = [score_stock(s, cfg, ctx, base_dir) for s in stocks]
    pfo = portfolio_checks(results, stocks, cfg, ctx)
    print(report(results, pfo, cfg, ctx))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"as_of": str(ctx["as_of"]), "config": cfg, "results": results,
                       "portfolio": pfo}, fh, indent=2, default=str)


if __name__ == "__main__":
    main()
