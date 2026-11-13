#!/usr/bin/env python3
"""Pre-fill quantitative ABCD Change-Catalyst Score inputs from Screener.in + Yahoo Finance (stdlib only).

Usage: python fetch.py SLUG [--as-of YYYY-MM-DD] [--standalone] [--yahoo SYM.NS] [-o out.json]
Only published numbers are filled; qualitative inputs stay for the analyst file.
Each `source` states the page, row and period so a reviewer can re-check it.
Point-in-time runs (--as-of) only use annual results >= 60 days and quarterly results >= 45 days old.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html import unescape

BASE = "https://www.screener.in"
HEADERS = {"User-Agent": "Mozilla/5.0"}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def get(url):
    for attempt in range(6):
        time.sleep(1.5)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 15 * (attempt + 1)))


def num(s):
    if s is None:
        return None
    try:
        return float(re.sub(r"[,%₹\s]", "", str(s)))
    except ValueError:
        return None


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ")).strip()


def section_table(html, sec):
    i = html.find(f'<section id="{sec}"')
    if i < 0:
        return [], {}
    j = html.find("<table", i)
    k = html.find("</table>", j)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html[j:k], re.S)
    header = [text(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", rows[0], re.S)][1:]
    data = {}
    for row in rows[1:]:
        cells = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if cells:
            data[cells[0].rstrip("+").strip()] = [num(c) for c in cells[1:]]
    return header, data


def col_date(h):
    m = re.match(r"([A-Z][a-z]{2}) (\d{4})$", h)
    return dt.date(int(m.group(2)), MONTHS[m.group(1)], 28) if m else None


def published_idx(header, as_of, lag_days, fy_month=None):
    return [i for i, h in enumerate(header)
            if (d := col_date(h)) and (fy_month is None or d.month == fy_month) and d + dt.timedelta(days=lag_days) <= as_of]


def chart(cid, q, consolidated):
    url = f"{BASE}/api/company/{cid}/chart/?q={q}&days=10000" + ("&consolidated=true" if consolidated else "")
    ds = json.loads(get(url))["datasets"][0]["values"]
    return [(dt.date.fromisoformat(d), float(v)) for d, v in ds if v not in (None, "")]


def chart_sets(cid, q, consolidated):
    url = f"{BASE}/api/company/{cid}/chart/?q={q}&days=10000" + ("&consolidated=true" if consolidated else "")
    return {s["metric"]: [(dt.date.fromisoformat(d), float(v)) for d, v in s["values"] if v not in (None, "")]
            for s in json.loads(get(url))["datasets"]}


def cagr(a, b, years):
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return round(100 * ((b / a) ** (1 / years) - 1), 1)


def yahoo_daily(sym, as_of):
    p2 = int(dt.datetime.combine(as_of + dt.timedelta(days=1), dt.time()).timestamp())
    p1 = p2 - 420 * 86400
    r = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"))
    r = r["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), c, h, v)
            for t, c, h, v in zip(r["timestamp"], q["close"], q["high"], q["volume"]) if c and h and v is not None]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--as-of", default=dt.date.today().isoformat())
    ap.add_argument("--standalone", action="store_true")
    ap.add_argument("--yahoo", help="override Yahoo symbol, e.g. TARIL.NS or 532977.BO")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()

    as_of = dt.date.fromisoformat(a.as_of)
    is_today = as_of >= dt.date.today() - dt.timedelta(days=7)
    consolidated = not a.standalone
    url = f"{BASE}/company/{a.slug}/" + ("consolidated/" if consolidated else "")
    html = get(url)
    if consolidated:
        years = lambda h: len([c for c in section_table(h, "profit-loss")[0] if col_date(c)])  # noqa: E731
        sa_url = f"{BASE}/company/{a.slug}/"
        sa_html = get(sa_url)
        # a recently formed subsidiary gives a short, distorted consolidated history (e.g. JYOTIRES)
        if years(html) < max(4, years(sa_html)):
            print("note: consolidated history shorter than standalone; using standalone", file=sys.stderr)
            consolidated, url, html = False, sa_url, sa_html
    cid = re.search(r'data-company-id="(\d+)"', html).group(1)
    name = unescape(text(re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S).group(1)))
    fetched = dt.date.today().isoformat()
    basis = "consolidated" if consolidated else "standalone"
    src = lambda what: f"Screener {url} ({basis}) [{what}] fetched {fetched}"  # noqa: E731
    out = {}

    def put(key, value, source):
        if value is not None:
            out[key] = {"value": value, "source": source}

    top = {}
    for li in re.findall(r'<li class="flex flex-space-between"[^>]*>(.*?)</li>', html[html.find('id="top-ratios"'):], re.S)[:12]:
        nm = text(re.search(r'class="name">(.*?)</span>', li, re.S).group(1))
        top[nm] = [num(x) for x in re.findall(r'class="number">([^<]*)<', li)]

    q_h, qt = section_table(html, "quarters")
    pl_h, pl = section_table(html, "profit-loss")
    bs_h, bs = section_table(html, "balance-sheet")
    cf_h, cf = section_table(html, "cash-flow")
    rt_h, rt = section_table(html, "ratios")
    sh_h, sh = section_table(html, "shareholding")

    fy_month = col_date([h for h in pl_h if col_date(h)][-1]).month
    pli, bsi, cfi, rti = (published_idx(h, as_of, 60, fy_month) for h in (pl_h, bs_h, cf_h, rt_h))
    pli_all = published_idx(pl_h, dt.date.today(), 0, fy_month)
    if len(pli) < 4:
        sys.exit("Need at least 4 fiscal years of P&L published before --as-of")
    fy, fy3 = pli[-1], pli[-4]
    lbl = f"{pl_h[fy3]}..{pl_h[fy]}"

    sales = pl.get("Sales") or pl.get("Revenue")
    eps, np_row = pl.get("EPS in Rs"), pl.get("Net Profit")
    put("sales_cagr_3y_pct", cagr(sales[fy3], sales[fy], 3), src(f"P&L Sales CAGR {lbl}: {sales[fy3]:g} -> {sales[fy]:g}"))
    put("eps_cagr_3y_pct", cagr(eps[fy3], eps[fy], 3), src(f"P&L EPS CAGR {lbl}: {eps[fy3]:g} -> {eps[fy]:g}"))
    put("pat_cagr_3y_pct", cagr(np_row[fy3], np_row[fy], 3), src(f"P&L Net Profit CAGR {lbl}: {np_row[fy3]:g} -> {np_row[fy]:g}"))
    span = min(10, len(pli) - 1)
    if span >= 7:
        first = pli[-1 - span]
        put("sales_cagr_10y_pct", cagr(sales[first], sales[fy], span),
            src(f"P&L Sales CAGR over {span}y {pl_h[first]} {sales[first]:g} -> {pl_h[fy]} {sales[fy]:g} (longest available up to 10y)"))
    opm = pl.get("OPM %") or pl.get("Financing Margin %")
    if opm and opm[fy] is not None and opm[fy3] is not None:
        put("opm_change_3y_pp", round(opm[fy] - opm[fy3], 1), src(f"P&L OPM % {pl_h[fy3]} {opm[fy3]:g} -> {pl_h[fy]} {opm[fy]:g}"))

    roce = [rt["ROCE %"][i] for i in rti[-3:] if rt.get("ROCE %") and rt["ROCE %"][i] is not None]
    if len(roce) == 3:
        put("roce_3y_avg_pct", round(sum(roce) / 3, 1), src(f"Ratios ROCE % avg of {', '.join(rt_h[i] for i in rti[-3:])}: {roce}"))

    cfo = cf.get("Cash from Operating Activity")
    pl_by_label = {pl_h[i]: i for i in pli}
    pairs = [(cf_h[i], cfo[i], np_row[pl_by_label[cf_h[i]]]) for i in cfi[-3:]
             if cfo and cfo[i] is not None and cf_h[i] in pl_by_label and np_row[pl_by_label[cf_h[i]]] is not None]
    if len(pairs) == 3 and sum(p[2] for p in pairs) > 0:
        s_cfo, s_np = sum(p[1] for p in pairs), sum(p[2] for p in pairs)
        put("cfo_to_pat_3y", round(s_cfo / s_np, 2), src(f"Cash Flow CFO sum {s_cfo:g} / Net Profit sum {s_np:g}, {pairs[0][0]}..{pairs[-1][0]}"))

    qi = published_idx(q_h, as_of, 45)
    q_sales, q_np = qt.get("Sales") or qt.get("Revenue"), qt.get("Net Profit")
    if len(qi) >= 8 and q_sales and q_np:
        last4, prev4 = qi[-4:], qi[-8:-4]
        qlbl = f"quarters {q_h[last4[0]]}..{q_h[last4[-1]]} vs {q_h[prev4[0]]}..{q_h[prev4[-1]]}"
        s1, s0 = sum(q_sales[i] or 0 for i in last4), sum(q_sales[i] or 0 for i in prev4)
        n1, n0 = sum(q_np[i] or 0 for i in last4), sum(q_np[i] or 0 for i in prev4)
        put("ttm_pat_cr", round(n1, 1), src(f"Quarterly Net Profit sum {q_h[last4[0]]}..{q_h[last4[-1]]}"))
        put("ttm_sales_cr", round(s1, 1), src(f"Quarterly Sales sum {q_h[last4[0]]}..{q_h[last4[-1]]}"))
        if s0 > 0:
            put("ttm_sales_growth_pct", round(100 * (s1 / s0 - 1), 1), src(f"TTM Sales {s1:g} vs {s0:g}, {qlbl}"))
        if n0 > 0:
            put("ttm_pat_growth_pct", round(100 * (n1 / n0 - 1), 1), src(f"TTM Net Profit {n1:g} vs {n0:g}, {qlbl}"))
        elif n1 > 0:
            # loss-to-profit swing has no meaningful % change; recorded as 100 so it counts as an inflection
            put("ttm_pat_growth_pct", 100.0, src(f"TTM Net Profit {n1:g} vs {n0:g} (loss -> profit, recorded as 100), {qlbl}"))
    else:
        # Screener keeps ~13 quarters, so older --as-of dates fall back to the last two fiscal years
        p0, s_0, n_0 = pli[-2], sales[pli[-2]], np_row[pli[-2]]
        albl = f"annual proxy {pl_h[fy]} vs {pl_h[p0]} (fewer than 8 published quarters)"
        put("ttm_pat_cr", np_row[fy], src(f"P&L Net Profit {pl_h[fy]}, {albl}"))
        put("ttm_sales_cr", sales[fy], src(f"P&L Sales {pl_h[fy]}, {albl}"))
        if s_0 and s_0 > 0 and sales[fy] is not None:
            put("ttm_sales_growth_pct", round(100 * (sales[fy] / s_0 - 1), 1), src(f"Sales {sales[fy]:g} vs {s_0:g}, {albl}"))
        if n_0 is not None and np_row[fy] is not None:
            if n_0 > 0:
                put("ttm_pat_growth_pct", round(100 * (np_row[fy] / n_0 - 1), 1), src(f"Net Profit {np_row[fy]:g} vs {n_0:g}, {albl}"))
            elif np_row[fy] > 0:
                put("ttm_pat_growth_pct", 100.0, src(f"Net Profit {np_row[fy]:g} vs {n_0:g} (loss -> profit, recorded as 100), {albl}"))

    b = bsi[-1]
    equity = (bs["Equity Capital"][b] or 0) + (bs["Reserves"][b] or 0)
    borrow = (bs.get("Borrowings") or [0] * len(bs_h))[b] or 0
    lease = 0
    try:
        sched = json.loads(get(f"{BASE}/api/company/{cid}/schedules/?parent=Borrowings&section=balance-sheet"
                               + ("&consolidated=" if consolidated else "")))
        lease = num(sched.get("Lease Liabilities", {}).get(bs_h[b])) or 0
    except Exception:
        pass
    if equity > 0:
        put("debt_to_equity", round(max(borrow - lease, 0) / equity, 2),
            src(f"Balance Sheet {bs_h[b]}: Borrowings {borrow:g} - leases {lease:g} / (Equity+Reserves) {equity:g}"))

    mcap_now = top.get("Market Cap", [None])[0]
    price = chart(cid, "Price", consolidated)
    hist = [(d, v) for d, v in price if d <= as_of]
    if hist:
        hi_d, hi_v = max(hist, key=lambda x: x[1])
        put("drawdown_from_high_pct", round(100 * (1 - hist[-1][1] / hi_v), 1),
            src(f"Price chart close {hist[-1][1]:g} on {hist[-1][0]} vs all-time high {hi_v:g} on {hi_d}"))
    if is_today and mcap_now:
        put("market_cap_cr", mcap_now, src("Top ratios Market Cap"))
    elif hist:
        d0, px = hist[-1]
        via_ms = None
        try:
            sets = chart_sets(cid, "Market+Cap+to+Sales-Median+Market+Cap+to+Sales-Sales", consolidated)
            ms = [v for d, v in sets.get("Market Cap to Sales", []) if d <= as_of]
            ttm = [v for d, v in sets.get("Sales", []) if d <= as_of]
            if ms and ttm:
                via_ms = ms[-1] * ttm[-1]
        except Exception as e:
            print(f"warning: market-cap/sales history unavailable ({e})", file=sys.stderr)
        n, e = np_row[fy], eps[fy]
        n1, e1, px1 = np_row[pli_all[-1]], eps[pli_all[-1]], price[-1][1] if price else None
        if mcap_now and px1 and all(x and x > 0 for x in (n, e, n1, e1)):
            # prices/EPS are bonus/split-restated; NP/EPS ratio adds new issuance and cancels minority interest
            share_ratio = (n / e) / (n1 / e1)
            mcap = mcap_now * px / px1 * share_ratio
            check = f"; cross-check MCap/Sales x TTM Sales = {via_ms:,.0f}" if via_ms else ""
            if via_ms and abs(mcap / via_ms - 1) > 0.1:
                print(f"warning: market cap {mcap:,.0f} vs MCap/Sales estimate {via_ms:,.0f} differ > 10%", file=sys.stderr)
            put("market_cap_cr", round(mcap), src(
                f"today's mcap {mcap_now:g} x adjusted price {px:g} ({d0}) / {px1:g} ({price[-1][0]}) x share ratio "
                f"{share_ratio:.3f} (NP/EPS {pl_h[fy]} vs {pl_h[pli_all[-1]]}){check}"))
        elif via_ms:
            put("market_cap_cr", round(via_ms), src(f"Market Cap to Sales chart x TTM Sales chart at {as_of} (ratio has 1 decimal)"))

    try:
        pe_series = chart(cid, "Price+to+Earning-Median+PE", consolidated)
        window = [v for d, v in pe_series if as_of - dt.timedelta(days=5 * 365) <= d <= as_of]
        if len(window) >= 10:
            put("pe", window[-1], src(f"P/E chart value at {as_of}"))
            pct = round(100 * sum(v <= window[-1] for v in window) / len(window), 1)
            put("pe_percentile_5y", pct, src(f"P/E chart percentile within 5y to {as_of} ({len(window)} points)"))
    except Exception as e:
        print(f"warning: P/E history unavailable ({e})", file=sys.stderr)

    if is_today and sh_h:
        prom = sh.get("Promoters")
        if not prom:
            put("promoter_holding_pct", "professionally_managed", src("Shareholding: no promoter category"))
        else:
            put("promoter_holding_pct", prom[-1], src(f"Shareholding Promoters {sh_h[-1]}"))
            put("promoter_holding_change_3y_pp", round(prom[-1] - prom[0], 2),
                src(f"Shareholding Promoters {sh_h[0]} {prom[0]:g} -> {sh_h[-1]} {prom[-1]:g}"))
            i = html.find("CONS")
            m = re.search(r"pledged ([\d.]+)%", text(html[i:i + 3000])) if i >= 0 else None
            put("promoter_pledge_pct", float(m.group(1)) if m else 0.0,
                src("Pros/cons pledge flag" + ("" if m else " absent; verify in exchange shareholding pattern")))
        inst = (sh.get("FIIs") or [0])[-1] + (sh.get("DIIs") or [0])[-1]
        put("institutional_holding_pct", round(inst, 2), src(f"Shareholding FIIs + DIIs {sh_h[-1]}"))

    candidates = [a.yahoo] if a.yahoo else []
    if not candidates:
        nse = re.search(r"NSE:\s*([A-Z0-9&_-]+)", html)
        bse = re.search(r"bseindia\.com/stock-share-price/[^/]+/([^/]+)/\d{6}/", html)
        candidates = [f"{m.group(1)}.{x}" for m, x in ((nse, "NS"), (bse, "BO")) if m]
    bars, sym = [], None
    for c in candidates:
        try:
            got = yahoo_daily(c, as_of)
            # new NSE listings have short history; use the exchange with more sessions
            if len(got) > len(bars):
                sym, bars = c, got
        except Exception as e:
            print(f"warning: Yahoo {c} unavailable ({e})", file=sys.stderr)
    if bars:
        ysrc = lambda what: f"Yahoo {sym} daily [{what}] fetched {fetched}"  # noqa: E731
        last = bars[-1]
        put("current_price", round(last[1], 2), ysrc(f"close on {last[0]}"))
        yr = [x for x in bars if x[0] > last[0] - dt.timedelta(days=365)]
        hi = max(x[2] for x in yr)
        put("pct_below_52w_high", round(100 * (1 - last[1] / hi), 1), ysrc(f"close {last[1]:.2f} on {last[0]} vs 52w high {hi:.2f}"))
        if len(bars) >= 60:
            v10 = sum(x[3] for x in bars[-10:]) / 10
            v50 = sum(x[3] for x in bars[-60:-10]) / 50
            if v50 > 0:
                put("volume_ratio_10d_vs_50d", round(v10 / v50, 2), ysrc(f"avg volume last 10 sessions / prior 50 to {last[0]}"))
        if len(bars) >= 200:
            dma = sum(x[1] for x in bars[-200:]) / 200
            put("price_vs_200dma_pct", round(100 * (last[1] / dma - 1), 1), ysrc(f"close vs 200-session average to {last[0]}"))

    result = {"company": name, "ticker": a.slug, "as_of": as_of.isoformat(), "inputs": out}
    js = json.dumps(result, indent=2, ensure_ascii=False)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(js + "\n")
    else:
        print(js)


if __name__ == "__main__":
    main()
