---
name: capital-efficiency-at-a-price
description: Score any listed company 0-100 on Kenneth Andrade's (Old Bridge Capital) "buy capital efficiency at a price" framework. It compares earnings and FCF yield with the bond yield, checks for debt-free self-funded cash flow, looks for the industry leader gaining market share with pricing power, asks whether industry profitability is stagnant (the contrarian consolidation set-up), and runs capital-cycle sell triggers. A deterministic Python script produces an auditable rule-by-rule report, with a separate model for banks and NBFCs. Use whenever the user wants to screen, score, rank or compare stocks with this framework, mentions Kenneth Andrade, Old Bridge, earnings yield vs bond yield, capital cycle, "largest company in a weak industry", or asks whether a stock still fits / should be sold under this lens, even if they don't say "score".
---

# Capital-Efficiency-at-a-Price (CEP) score

This skill turns Kenneth Andrade's investing framework into a repeatable 0-100 score. The maths lives in `scripts/score.py` and runs the same way every time. Your job is to gather correct inputs, run the script, and explain the result. You never adjust the points by hand: that keeps the number reproducible, and anyone with the same inputs gets the same score.

`references/framework.md` maps every rule back to the principle in the interview it comes from. Read it if the user asks "why this rule?" or wants to change thresholds.

## The model at a glance

Non-financial companies (100 points):

| Pillar | Max | What it tests |
|---|---|---|
| A. Price | 25 | A1 earnings yield vs bond hurdle (10) · A2 3y-avg FCF yield vs hurdle (8) · A3 EY + revenue growth (capped at 10%) vs hurdle, scored only if EY ≥ 0.5× hurdle (7) |
| B. Capital efficiency | 15 | B1 5y avg ROCE (8) · B2 cum OCF / cum PAT (7) |
| C. Balance sheet | 20 | C1 net debt/equity (8) · C2 capex funded from OCF (5) · C3 FCF-positive years (4) · C4 no dilution (3) |
| D. Dominance | 25 | D1 industry rank (8) · D2 market-share gain, which scores 0 if share fell in each of the last 2 years (8) · D3 margin premium vs industry (5) · D4 margin resilience (4) |
| E. Cycle | 15 | E1 industry ROE at/below its own average (5) · E2 share gain while industry weak (4) · E3 P/E vs own 10y median (3) · E4 market-cap CAGR not ahead of PAT CAGR (3). E3 and E4 score only if EY ≥ 0.5× hurdle |

**Absolute price comes first.** The relative tests (A3, E3, E4) only count once the absolute earnings yield is acceptable. Andrade explicitly rejects calling a stock cheap because it trades below its own or its sector's history. A great business de-rating from 100x to 54x is still not cheap.

Lenders (`business_type: "lender"`) use a parallel model: P/B, justified P/B, ROE, ROA, CRAR, NPAs, loan-book share, and segment cycle. The reason is that he says lenders have no FCF and must be bought only at a clearly attractive valuation.

Gates cap the final score when a kill condition holds:

| Gate | Condition | Cap |
|---|---|---|
| G1 | No cash flows (PAT ≤ 0 or 5y cum OCF ≤ 0) | 30 ("wait for the second cycle") |
| G2 | Net debt/EBITDA > 3 (lenders: CRAR < 12) | 40 |
| G3 | Overpaying: EY < hurdle/3, i.e. P/E above ~42x at a 7% hurdle (lenders: or P/B > 3) | 40 |
| G3 | Rich price: EY < hurdle/2, i.e. P/E above ~28x (lenders: or P/B > 2) | 60 |
| G4 | Hot industry: industry ROE ≥ 30%, a large new entrant, or a capacity flood | 60 |

Verdict bands:

| Score | Verdict |
|---|---|
| ≥ 75 | CORE FIT |
| 60–74 | FIT |
| 45–59 | PARTIAL FIT |
| < 45 | NOT A FIT |

If data coverage is below 80%, the result is flagged **LOW CONFIDENCE**.

The sell-discipline check runs separately and returns HOLD (0 triggers), REVIEW (1) or EXIT/TRIM candidate (2+). It is meant for stocks the user already owns.

## Workflow

1. **Pin down the company and model.** Use `lender` for banks, NBFCs, HFCs and MFIs. Use `non_financial` for everything else, including insurers' parents and holding companies, but say that the fit is imperfect there.

2. **Gather inputs** into the JSON shape in `assets/input_template.json`. Money goes in ₹ crore (or any single consistent unit). Series run oldest → newest, with 6 years so CAGRs cover a true 5-year span. Typical sources:
   - Financials (revenue, EBITDA = operating profit, EBIT = PBT + interest, PAT, OCF, capex = "fixed assets purchased", borrowings, cash + investments, equity = share capital + reserves, shares): Screener.in consolidated pages (`https://www.screener.in/company/<TICKER>/consolidated/`), annual reports, or a file the user uploads. Use consolidated figures unless the standalone business is the economic entity.
   - Market cap, and market cap 5 years ago: Screener / exchange data.
   - `pe_10y_median` / `pb_10y_median`: Screener's PE chart "median" or the user's data source.
   - `hurdle_yield_pct`: the current India 10-year G-sec yield. Search for it on the day, because it changes. Use a AAA corporate index if the user wants the stricter test he used in his example.
   - Industry data: rank by revenue, market share series (industry body, company presentations, or company revenue ÷ industry revenue), industry EBITDA margin and industry ROE series. The usual proxy is the median of the top 4–6 listed peers, which you compute from their Screener pages. Record which peers you used.
   - `new_large_entrant` / `industry_capacity_addition_high`: set to `true` only with a cited news source, for example a large conglomerate announcing entry or capacity being added well ahead of demand.

   Put a source for every block in `sources`. Use `null` for anything you can't find. Never estimate a value just to fill a gap: a MISSING rule scoring 0 is honest, while a guessed value makes the score unverifiable.

3. **Run the scorer:**
   ```bash
   python scripts/score.py input.json --out report.md --json result.json
   ```
   A list of companies in one file produces a ranking table first. Use that for "rank these 10 stocks" requests and to build a concentrated ~20–25 name list.

4. **Present the result:**
   - Give the final score, the verdict and any gates up front, then the pillar table.
   - Give 3–5 bullets on what drove the score. Name the specific rules (e.g. "A1: EY 5.1% vs 7% hurdle, 0.73x → 5/10"), so the user can check each one against the audit table.
   - Give the sell-discipline result if relevant.
   - Explain any MISSING rules and how to fill them.
   - Include the full rule-by-rule audit table (or attach `report.md`) and the sources.
   - Close with a one-line caveat that this is a screening framework, not investment advice.

5. **What-ifs.** If the user asks "what price makes this a CORE FIT?", re-run the script with a different `market_cap`. Don't reason about it by hand, so the answer stays verifiable.

## Interpreting edge cases

- **Cyclicals at the trough** (metals, cement, tyres in a bad year) score low on A1 because the yield uses latest PAT. They can score well on E1/E2. That tension is the contrarian set-up he describes, so point it out rather than "fixing" it.
- **High-quality compounders at 40–100x** (Page Industries today) will hit the G3 cap even with near-perfect quality pillars. He called the re-rating to 100x luck, not method. The framework is supposed to say "great business, not at this price". Report the quality pillars (B, C, D) separately so the user can see that.
- **Market share from a listed-peer universe** (company revenue ÷ sum of the listed peers' revenue) is a proxy. Say so, and prefer industry-body data when it is available.
- **Holding companies, conglomerates, and companies with large one-offs:** note them. Strip a clearly one-off item from PAT only if the user agrees, and record it in `sources` as an adjustment.
- **IPOs or companies with fewer than 3 years of data:** most rules go MISSING and the result is LOW CONFIDENCE. That is the correct outcome ("wait for cash flows to emerge").

## Changing the framework

Thresholds sit inline in `scripts/score.py`, inside each rule's `band(...)` call. If the user wants different weights or bands, edit them there, keep each pillar's maxima adding up to 100, and re-run the template to confirm `max_total == 100`. Tell the user that scores from before the change are no longer comparable.
