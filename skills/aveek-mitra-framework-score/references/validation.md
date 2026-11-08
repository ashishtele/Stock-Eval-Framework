# Validation: framework vs Aveek Mitra's own decisions (Nov 2026)

Every stock discussed in the interview was scored, using Screener.in data plus filings, rating rationales and
news (desk research only, no scuttlebutt). There are two sets of tests:
- **Current:** data as of 8 Nov 2026, compared with his stated view.
- **Point-in-time (PIT):** data truncated to what existed at the time of his buy or sell, compared with what he did.

"Match" means the classification and action agree with what he said or did.

## Results

| # | Case | His view / action | v1 | v2 | v2 verdict |
|---|---|---|---|---|---|
| 1 | Shivalik Bimetal (now, PE 49.6) | Holds; "runway now… we may again sell" | 50.3 Good co, not investment ✗ | 58.9 PASS for new money + REVIEW (S2 rich vs peers) | Match |
| 2 | Force Motors (now, ~18,900) | Sold everything at 15-17k | 70.8 Compounder, HOLD | 72.1 Compounder, HOLD | **Miss**: his reason (Urbania segment TAM) needs `addressable_market_cr` |
| 3 | Unimech Aerospace | Good co; missed it at 750; not invested | 57.6 PASS | 57.6 PASS (watchlist) | Match |
| 4 | Vesuvius India | Good co, not growing, not for clients | 61.0 Watch + S1 | 65.9 Quality in consolidation | **Miss** on numbers (3y sales CAGR 16%). With an evidenced `structural_headwind` → 60, STRUCTURAL HEADWIND (match) |
| 5 | Ambika Cotton | Good co, conservative promoter, not growing | 33.8 Local cyclical | 33.8 Local cyclical, avoid | Partial: right action, label depends on business_type |
| 6 | KPR Mill | Excellent co, not invested | 51.2 Good co, not investment | 53.3 Good co, not investment | Match |
| 7 | Kitex (now) | Exited long ago | 24.3 PASS | 33.2 Turnaround not evidenced | Match (avoid) |
| 8 | Hemisphere Properties | Value trap, no trigger | 15.7 PASS | 11.3 avoid | Match |
| 9 | KCP | Local micro-market cyclical | 46.3 Local cyclical | 46.6 Local cyclical | Match |
| 10 | Orient Cement | Local cyclical | 37.8 Local cyclical | 37.8 Local cyclical | Match |
| 11 | ITC | High dividend yield, prefers reinvestors | 40.7 Good co, not investment | 42.0 Good co, not investment, TRIM | Match |
| 12 | Elecon (now) | Sold; guidance problem | 47.4 PASS + S1 | 52.9 PASS + S1 | Match |
| 13 | TRIL (now) | Sold early; didn't understand the hype | 58.8 PASS | 58.8 PASS | Partial (not a buy; no sell signal fired) |
| 14 | Maharashtra Seamless (now) | No current view | 35.8 | 40.9 | n/a |
| 15 | PIT TRIL, May-2016 (loss-making, Rs 285 cr mcap) | Bought | 24.6 PASS, insufficient data ✗ | 42.5 Turnaround not yet evidenced | Partial (just under the 45 threshold; FY12-14 balance sheets missing) |
| 16 | PIT Kitex, Apr-2015 at Rs 869 | Sold: growth assumed too high for kidswear | 43.9, no sell signal ✗ | 49.8 + **S6** (price implies 21.6% for 10y in a ~6% industry) | Match |
| 17 | PIT Shivalik, Feb-2026 at Rs 444 | Re-bought after promoter bought at Rs 610 | 59.0 PASS + S1 ✗ | 67.0 **Quality in consolidation** | Match |
| 18 | PIT Force Motors, Apr-2023 at Rs 1,340 | Bought | 34.8 PASS ✗ | 44.0 Turnaround not yet evidenced (48 with his Urbania scuttlebutt) | Partial |
| 19 | PIT Force Motors, Jan-2025 at Rs 6,100 | Re-bought | 51.5 Turnaround + S1 | 64.9 Turnaround candidate, HOLD | Match |
| 20 | PIT Elecon, Feb-2021 at ~Rs 50 | Bought | 27.8 PASS ✗ | 31.8 PASS | **Miss** |

| | Match | Partial | Miss | n/a |
|---|---:|---:|---:|---:|
| v1 | 9 | 4 | 6 | 1 |
| v2 | 12 | 4 | 3 | 1 |

## What changed in v2 and why

1. **Growth uses the average of 3y and 5y CAGR.** The growth gate needs a flat 3 years *and* recent growth under 10%, and it is waived in consolidation.
   - v1 capped Shivalik as "not growing" because its FY23-26 consolidation gave a 7% 3y CAGR. Meanwhile its trailing-12-month sales were up 28% and its 5y CAGR was 23%.
2. **Momentum has an absolute floor, and S1 needs growth under 10% in absolute terms.**
   - Force Motors in Jan-2025 was flagged "flattening" at 24% growth, only because its 3y base came out of COVID.
3. **Base-effect guards.**
   - Expected growth is clamped to at most best sales CAGR + 10pp. A 72% "expected growth" from a depressed FY23 profit base was flattering Force Motors.
   - "Growth shown" for S3 uses sales when profit CAGR is distorted.
   - An absolute PEG is used when peer growth is negative or missing.
4. **Turnaround mode.** It applies automatically when the latest FY was a loss, or either of the two prior FYs was.
   - Inflection is worth 20 points and history-based growth only 15.
   - Valuation uses price/sales and a normalised P/E.
   - E1 credits a profitable latest quarter after a loss year.
   - This reflects how he bought TRIL and Force Motors: through uncertainty, before the numbers showed it.
5. **"Quality in consolidation" detector.** This is his pattern of selling after a run and re-buying when growth pauses, as long as the thesis is intact and insiders are buying.
6. **S6 industry-growth sell signal.** This is the Kitex lesson: the price assumed growth the end-market (kidswear, with falling birth rates) couldn't provide.
7. **Evidence-gated `structural_headwind` cap at 60.** This is the Vesuvius lesson: growth tied to a structurally capped end-market.
8. **Plumbing fixes.**
   - `null` values inside arrays no longer crash the scorer.
   - Added the `global_commodity` business type.
   - The report shows the score computed only on rules that had data.

## Known blind spots (be honest with the user)

- **Overfitting risk.** The v2 changes were designed after looking at these 20 cases. Treat the 12/20 as in-sample.
  - The 45-point turnaround threshold was deliberately *not* lowered to rescue TRIL-2016 (42.5) or Force-2023 (44.0).
  - A fair out-of-sample test would score his other ValuePickr picks (Premco Global, Camlin Fine, KSE, SP Apparels) at the dates he wrote them up.
- **Deep-cyclical recoveries with no loss year (Elecon 2021) are not detected.**
  - That company had falling sales, ROCE of 7.7% and a 33% promoter pledge. His edge was a cycle judgement that the data didn't show.
  - Forcing turnaround mode doesn't help (27.1).
- **Scuttlebutt is where much of his edge came from.** This includes plant and AGM visits, shipment tracking and tour-operator checks. Desk-only inputs understate early buys.
- **TAM judgements drive his sell decisions** (Force Motors, Kitex). Without a sourced addressable market or industry growth figure, S4 and S6 can't fire.
- **Data quality.**
  - Peer sets were thin (2-3 names).
  - The 5-year median P/Es came from undated aggregator snippets.
  - Historical cases lack quarterly data that existed at the time.
