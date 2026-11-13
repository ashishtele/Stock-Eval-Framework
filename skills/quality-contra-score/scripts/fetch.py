#!/usr/bin/env python3
"""Pre-fill quantitative Quality Contra Score inputs from Screener.in + Yahoo Finance (stdlib only).

Usage: python fetch.py SLUG [--as-of YYYY-MM-DD] [--standalone] [--yahoo SYM.NS] [-o out.json]
Only published numbers are filled; qualitative inputs stay for the analyst file.
Each `source` states the page, row and period so a reviewer can re-check it.
"""
import argparse
import datetime as dt
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from html import unescape
from urllib.parse import quote

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


def annual_idx(header, as_of, fy_month):
    # a fiscal year's numbers are published ~2 months after year end
    return [i for i, h in enumerate(header)
            if (d := col_date(h)) and d.month == fy_month and d + dt.timedelta(days=60) <= as_of]


def chart(cid, q, consolidated):
    url = f"{BASE}/api/company/{cid}/chart/?q={q}&days=10000" + ("&consolidated=true" if consolidated else "")
    ds = json.loads(get(url))["datasets"][0]["values"]
    return [(dt.date.fromisoformat(d), float(v)) for d, v in ds if v not in (None, "")]


def schedule(cid, parent, section, consolidated):
    url = (f"{BASE}/api/company/{cid}/schedules/?parent={parent.replace(' ', '+')}&section={section}"
           + ("&consolidated=" if consolidated else ""))
    return json.loads(get(url))


def cagr(a, b, years):
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return round(100 * ((b / a) ** (1 / years) - 1), 1)


def percentile_value(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(p / 100 * len(s)))]


def yahoo_daily(sym, as_of, years=6.3):
    p2 = int(dt.datetime.combine(as_of + dt.timedelta(days=1), dt.time()).timestamp())
    p1 = p2 - int(years * 365 * 86400)
    r = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym)}?period1={p1}&period2={p2}&interval=1d"))
    r = r["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date(), c)
            for t, c in zip(r["timestamp"], q["close"]) if c]


def close_on_or_before(bars, day):
    prior = [b for b in bars if b[0] <= day]
    return prior[-1] if prior else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--as-of", default=dt.date.today().isoformat())
    ap.add_argument("--standalone", action="store_true",
                    help="use standalone statements (e.g. when consolidation includes a lending subsidiary)")
    ap.add_argument("--yahoo", help="override Yahoo symbol, e.g. BAJAJ-AUTO.NS or 532977.BO")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()

    as_of = dt.date.fromisoformat(a.as_of)
    is_today = as_of >= dt.date.today() - dt.timedelta(days=7)
    consolidated = not a.standalone
    url = f"{BASE}/company/{a.slug}/" + ("consolidated/" if consolidated else "")
    html = get(url)
    if consolidated:
        sa_url = f"{BASE}/company/{a.slug}/"
        sa_html = get(sa_url)
        years = lambda h: len([c for c in section_table(h, "profit-loss")[0] if col_date(c)])  # noqa: E731
        if years(html) < max(4, years(sa_html)):
            print("note: consolidated history shorter than standalone; using standalone", file=sys.stderr)
            consolidated, url, html = False, sa_url, sa_html
        else:
            c_b = (section_table(html, "balance-sheet")[1].get("Borrowings") or [0])[-1] or 0
            s_b = (section_table(sa_html, "balance-sheet")[1].get("Borrowings") or [0])[-1] or 0
            if c_b > 3 * s_b + 500:
                print(f"WARNING: consolidated borrowings {c_b:g} cr vs standalone {s_b:g} cr. If this is a lending/captive-"
                      "finance subsidiary, rerun with --standalone; operating-subsidiary debt is real debt.", file=sys.stderr)
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

    pl_h, pl = section_table(html, "profit-loss")
    bs_h, bs = section_table(html, "balance-sheet")
    cf_h, cf = section_table(html, "cash-flow")
    rt_h, rt = section_table(html, "ratios")
    sh_h, sh = section_table(html, "shareholding")

    if "Sales" not in pl and "Revenue" in pl and "Financing Profit" in pl:
        sys.exit("Looks like a bank/NBFC (Revenue/Financing Profit rows). Lenders are out of scope for this score.")

    fy_month = col_date([h for h in pl_h if col_date(h)][-1]).month
    pli, bsi, cfi, rti = (annual_idx(h, as_of, fy_month) for h in (pl_h, bs_h, cf_h, rt_h))
    if len(pli) < 6:
        sys.exit("Need at least 6 fiscal years of P&L before --as-of")
    fy, fy5 = pli[-1], pli[-6]

    eps = pl.get("EPS in Rs")
    put("eps_cagr_5y_pct", cagr(eps[fy5], eps[fy], 5), src(f"P&L EPS in Rs CAGR {pl_h[fy5]} {eps[fy5]:g} -> {pl_h[fy]} {eps[fy]:g}"))

    # ---- Quality: ROCE ----
    roce_all = rt.get("ROCE %") or []
    roce = [(rt_h[i], roce_all[i]) for i in rti[-10:] if roce_all and roce_all[i] is not None]
    if len(roce) >= 5:
        vals = [v for _, v in roce]
        put("roce_10y_avg_pct", round(sum(vals) / len(vals), 1),
            src(f"Ratios ROCE % avg of {len(vals)}y {roce[0][0]}..{roce[-1][0]}: {', '.join(f'{v:g}' for v in vals)}"))
        put("roce_pct_years_ge_15", round(100 * sum(v >= 15 for v in vals) / len(vals)),
            src(f"Ratios ROCE %: {sum(v >= 15 for v in vals)} of {len(vals)} years >= 15%"))

    # ---- Quality: cash flow ----
    cfo_row, np_row = cf.get("Cash from Operating Activity"), pl.get("Net Profit")
    pl_by_label = {pl_h[i]: i for i in pli}
    pairs = [(cf_h[i], cfo_row[i], np_row[pl_by_label[cf_h[i]]]) for i in cfi[-10:]
             if cfo_row and cfo_row[i] is not None and cf_h[i] in pl_by_label and np_row[pl_by_label[cf_h[i]]] is not None]
    if len(pairs) >= 5:
        sum_cfo, sum_np = sum(p[1] for p in pairs), sum(p[2] for p in pairs)
        span = f"{pairs[0][0]}..{pairs[-1][0]} ({len(pairs)}y)"
        if sum_np > 0:
            put("cfo_to_pat_10y", round(sum_cfo / sum_np, 2),
                src(f"Cash Flow CFO sum {sum_cfo:,.0f} / P&L Net Profit sum {sum_np:,.0f}, {span}"))
        put("cfo_positive_years_pct", round(100 * sum(p[1] > 0 for p in pairs) / len(pairs)),
            src(f"Cash Flow CFO > 0 in {sum(p[1] > 0 for p in pairs)} of {len(pairs)} years, {span}"))
        last5 = pairs[-5:]
        put("cfo_5y_cumulative_cr", round(sum(p[1] for p in last5)),
            src(f"Cash Flow CFO sum {last5[0][0]}..{last5[-1][0]}"))

    # ---- Balance sheet: net debt / EBITDA, interest cover ----
    b = bsi[-1]
    borrow = (bs.get("Borrowings") or [0] * len(bs_h))[b] or 0
    lease = cash = 0
    try:
        lease = num(schedule(cid, "Borrowings", "balance-sheet", consolidated).get("Lease Liabilities", {}).get(bs_h[b])) or 0
    except Exception as e:
        print(f"warning: borrowings schedule unavailable ({e})", file=sys.stderr)
    try:
        cash = num(schedule(cid, "Other Assets", "balance-sheet", consolidated).get("Cash Equivalents", {}).get(bs_h[b])) or 0
    except Exception as e:
        print(f"warning: other-assets schedule unavailable ({e})", file=sys.stderr)
    ebitda = (pl.get("Operating Profit") or [None] * len(pl_h))[fy]
    net_debt = borrow - lease - cash
    if ebitda is not None:
        nde = round(net_debt / ebitda, 2) if ebitda > 0 else 99.0
        put("net_debt_to_ebitda", nde,
            src(f"(Borrowings {borrow:g} - leases {lease:g} - cash equivalents {cash:g}) {bs_h[b]} / "
                f"Operating Profit {ebitda:g} {pl_h[fy]}; investments not netted (conservative)"))
    interest, pbt = pl.get("Interest")[fy], pl.get("Profit before tax")[fy]
    if interest is not None and pbt is not None:
        cover = 100.0 if interest <= 0 else round(min((pbt + interest) / interest, 100), 1)
        put("interest_coverage", cover, src(f"(PBT {pbt:g} + Interest {interest:g}) / Interest, {pl_h[fy]}; capped at 100"))

    # ---- Capital allocation ----
    payout = pl.get("Dividend Payout %")
    if payout:
        last = [payout[i] or 0 for i in pli[-5:]]
        put("dividend_payout_5y_avg_pct", round(sum(last) / len(last), 1),
            src(f"P&L Dividend Payout % avg {pl_h[pli[-5]]}..{pl_h[fy]}: {', '.join(f'{v:g}' for v in last)}"))

    # ---- Price, market cap, yields ----
    mcap_now, price_now = top.get("Market Cap", [None])[0], top.get("Current Price", [None])[0]
    candidates = [a.yahoo] if a.yahoo else []
    if not candidates:
        plain = unescape(html)
        nse = re.search(r"NSE:\s*([A-Z0-9&_-]+)", plain)
        bse = re.search(r"bseindia\.com/stock-share-price/[^/]+/([^/]+)/\d{6}/", plain)
        candidates = [f"{m.group(1)}.{x}" for m, x in ((nse, "NS"), (bse, "BO")) if m]
    bars, sym = [], None
    for c in candidates:
        try:
            got = yahoo_daily(c, as_of)
            if len(got) > len(bars):
                sym, bars = c, got
        except Exception as e:
            print(f"warning: Yahoo {c} unavailable ({e})", file=sys.stderr)

    price = None
    if bars:
        last_d, price = bars[-1]
        ysrc = lambda what: f"Yahoo {sym} daily [{what}] fetched {fetched}"  # noqa: E731
        put("current_price", round(price, 2), ysrc(f"close on {last_d}"))
        three_y = [c for d, c in bars if d > last_d - dt.timedelta(days=3 * 365)]
        hi = max(three_y)
        put("drawdown_from_3y_high_pct", round(100 * (1 - price / hi), 1), ysrc(f"close {price:.2f} on {last_d} vs 3y closing high {hi:.2f}"))
        if len(bars) >= 200:
            dma = sum(c for _, c in bars[-200:]) / 200
            put("price_vs_200dma_pct", round(100 * (price / dma - 1), 1), ysrc(f"close vs 200-session average to {last_d}"))
        old = close_on_or_before(bars, last_d - dt.timedelta(days=5 * 365))
        if old and (last_d - old[0]).days < 5 * 365 + 10:
            put("price_cagr_5y_pct", cagr(old[1], price, 5), ysrc(f"close {old[1]:.2f} on {old[0]} -> {price:.2f} on {last_d}"))
        y1 = close_on_or_before(bars, last_d - dt.timedelta(days=365))
        try:
            nifty = yahoo_daily("^NSEI", as_of, years=1.2)
            n1, n0 = close_on_or_before(nifty, last_d - dt.timedelta(days=365)), close_on_or_before(nifty, last_d)
            if y1 and n1 and n0:
                rel = 100 * (price / y1[1] - 1) - 100 * (n0[1] / n1[1] - 1)
                put("rel_return_12m_vs_nifty_pp", round(rel, 1),
                    f"Yahoo {sym} 12m return {100 * (price / y1[1] - 1):.1f}% minus ^NSEI {100 * (n0[1] / n1[1] - 1):.1f}% "
                    f"({y1[0]} -> {last_d}), fetched {fetched}")
        except Exception as e:
            print(f"warning: Nifty series unavailable ({e})", file=sys.stderr)

    mcap = None
    if mcap_now and price_now:
        if is_today:
            mcap = mcap_now
            put("market_cap_cr", mcap, src("Top ratios Market Cap"))
        elif price:
            eq = [bs["Equity Capital"][i] for i, h in enumerate(bs_h) if col_date(h)]
            mcap = round(mcap_now * price / price_now * bs["Equity Capital"][b] / eq[-1])
            put("market_cap_cr", mcap, src(f"Yahoo close x shares implied by Equity Capital {bs_h[b]} (approx)"))

    if price and eps[fy] and payout and payout[fy] is not None:
        dps = eps[fy] * payout[fy] / 100
        put("dividend_yield_pct", round(100 * dps / price, 2),
            src(f"DPS ~ EPS {eps[fy]:g} x payout {payout[fy]:g}% ({pl_h[fy]}) / price {price:.2f}"))
    fcf = cf.get("Free Cash Flow")
    if fcf and mcap:
        last3 = [fcf[i] for i in cfi[-3:] if fcf[i] is not None]
        if len(last3) == 3:
            put("fcf_yield_pct", round(100 * sum(last3) / 3 / mcap, 2),
                src(f"Cash Flow Free Cash Flow avg {cf_h[cfi[-3]]}..{cf_h[cfi[-1]]} ({', '.join(f'{v:g}' for v in last3)}) / mcap {mcap:,.0f}"))

    # ---- Valuation history ----
    try:
        pe_series = chart(cid, "Price+to+Earning-Median+PE", consolidated)
        window = [v for d, v in pe_series if as_of - dt.timedelta(days=10 * 365) <= d <= as_of and v > 0]
        span = [d for d, v in pe_series if as_of - dt.timedelta(days=10 * 365) <= d <= as_of and v > 0]
        # Screener leaves loss-making periods blank, so a stale last point means no current P/E
        if span and (as_of - span[-1]).days > 30:
            print(f"note: no positive P/E since {span[-1]} (loss-making TTM); P/E inputs left empty", file=sys.stderr)
        elif len(window) >= 20:
            cur = window[-1]
            label = f"P/E chart {span[0]}..{span[-1]} ({len(window)} points, positive P/E only)"
            put("pe", cur, src(f"P/E chart value at {span[-1]}"))
            put("pe_percentile_10y", round(100 * sum(v <= cur for v in window) / len(window), 1), src(f"percentile of current P/E in {label}"))
            put("pe_median_10y", round(statistics.median(window), 1), src(f"median of {label}"))
            put("pe_p20_10y", round(percentile_value(window, 20), 1), src(f"20th percentile of {label}"))
            put("pe_p40_10y", round(percentile_value(window, 40), 1), src(f"40th percentile of {label}"))
    except Exception as e:
        print(f"warning: P/E history unavailable ({e})", file=sys.stderr)

    # ---- Shareholding (latest quarters only) ----
    if is_today and sh_h:
        prom = sh.get("Promoters")
        if not prom:
            put("promoter_holding_pct", "professionally_managed", src("Shareholding: no promoter category"))
        else:
            put("promoter_holding_pct", prom[-1], src(f"Shareholding Promoters {sh_h[-1]}"))
            put("promoter_holding_change_3y_pp", round(prom[-1] - prom[0], 2), src(f"Shareholding Promoters {sh_h[0]} -> {sh_h[-1]}"))
            i = html.find("CONS")
            m = re.search(r"pledged ([\d.]+)%", text(html[i:i + 3000])) if i >= 0 else None
            put("promoter_pledge_pct", float(m.group(1)) if m else 0.0,
                src("Pros/cons pledge flag" + ("" if m else " absent; verify in exchange shareholding pattern")))
        inst = [(sh.get("FIIs") or [0] * len(sh_h))[k] + (sh.get("DIIs") or [0] * len(sh_h))[k] for k in range(len(sh_h))]
        if len(inst) >= 5:
            put("institutional_change_4q_pp", round(inst[-1] - inst[-5], 2), src(f"Shareholding FIIs+DIIs {sh_h[-5]} {inst[-5]:.2f} -> {sh_h[-1]} {inst[-1]:.2f}"))

    result = {"company": name, "ticker": a.slug, "as_of": as_of.isoformat(), "inputs": out}
    js = json.dumps(result, indent=2, ensure_ascii=False)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(js + "\n")
    else:
        print(js)


if __name__ == "__main__":
    main()
