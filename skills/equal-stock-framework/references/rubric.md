# E-QUAL Framework – full rubric, provenance and data-sourcing guide

Source: interview with Manish Sonthalia (Director & CIO, Emkay Investment Managers; ex-Motilal Oswal) on "Conversation with Kushal". The framework is his three-step process: **(1) E-QUAL management quality → (2) earnings growth potential → (3) purchase-price discipline**, with a risk-reward matrix and red-flag kill switches.

Legend: **[T]** = stated in the transcript. **[C]** = calibrated interpretation (the interview gave the principle but not the exact number). All [C] values live in `scripts/config.json` and can be changed.

## Contents
1. Core philosophy
2. Step 1 – E-QUAL (100 pts)
3. Step 2 – Earnings growth potential (100 pts)
4. Step 3 – Purchase-price discipline
5. Risk-reward matrix (required return)
6. Kill switches and warnings
7. Verdict logic
8. Exit rules
9. Where to find each input (India)

---

## 1. Core philosophy [T]
- Stock price = present value of future cash flows. Value − price = opportunity.
- Value = Quality (business + management) × Growth × Longevity of growth, bought at the right Price.
- Quality of business: ROCE must exceed cost of capital. Thumb-rule cost of capital = 15%.
- "In India growth is value; value is a value trap" – ~2/3 of listed Indian companies don't earn their cost of capital.
- Growth investor only: want profits to **double every 3–4 years** (≈18–24%+ PAT CAGR), and only in **structural** (not cyclical) businesses.
- Low churn (10–20%/yr); ~30% of portfolio held 10+ years. Wealth transfers from active to patient investors.

## 2. Step 1 – E-QUAL management quality (100)

Pillar weights: Integrity **40 [T]**, Wealth distribution **15 [T]**, Capability 25 [C], Investor communication 10 [C], Liquidity 10 [C]. (The interview named the five pillars and gave 40% and 15%; the split of the remaining 45% is calibrated.)

### Integrity (40)
| ID | Metric | Max | Scoring | Why (from interview) |
|---|---|---|---|---|
| I1 | Promoter holding % | 7.5 [T] | ≥70:7.5, ≥60:6, ≥50:4.5, ≥40:3, ≥26:1.5, else 0 [C] | Skin in the game; 75% is the legal max |
| I2 | Change in promoter holding (3y, pp) | 2.5 [T] | ≥+1:2.5, ≥−1:2, ≥−5:1, else 0 [C] | Raising stake = confidence; OFS/selling signals valuation view |
| I3 | Equity history | 5 [C] | 2 + 1.5×(bonus/split/buyback events, 10y), −2 if preferential/warrants to promoters (5y); cap 0–5 | Bonus = confidence to service larger equity; investor friendliness |
| I4 | FCCB / proposed dilution (% equity) | 2.5 [C] | 0:2.5, ≤5:1.5, ≤10:0.5, else 0 | Named in interview |
| I5 | Pledge (% of promoter holding) | 7.5 [C] | 0:7.5, ≤5:6, ≤10:4.5, ≤25:2, ≤50:0.5, else 0 | "Big red flag"; 5–10% OK, 70% = both companies sink |
| I6 | Promoter-group pay (% of PAT) | 5 [C] | ≤2:5, ≤5:3.5, ≤8:1.5, else 0; −1 if MD:median-employee ratio >300x | ₹200 cr salary example; "take dividends, not salary" |
| I7 | Auditor | 2.5 [C] | Tier (Big4 1.5 / top-tier 1.25 / mid 0.75 / small 0) + fee sanity 1.0. Fee band: 0.003–0.3% of revenue, or 0.33–3x peer median if given. Qualified opinion/resignation → 0 | ₹5 lakh audit fee on ₹500 cr revenue (defunct jewellers) = red flag; too high also bad |
| I8 | Related-party transactions (% revenue, excl. wholly-owned subs) | 5 [C] | ≤2:5, ≤5:3.5, ≤10:2, ≤25:0.5, else 0; −2 if promoter sister concern in same line | Profit shifting to RP entities |
| I9 | Royalty / brand / tech fee | 2.5 [C] | None 2.5; genuine foreign tech parent ≤3% 1.5, >3% 0.5; promoter entity 0 | OK for Honda→Hero, Suzuki→Maruti; not for own holding co |

### Capability (25)
| ID | Metric | Max | Scoring | Why |
|---|---|---|---|---|
| C1 | Net exports (exports − imports, % revenue) | 3 | ≥20:3, ≥0:2, ≥−10:1, else 0 | Rupee cost → dollar revenue = capability (IT, pharma, gems, auto-comp) |
| C2 | Net debt/equity | 5 | ≤0:5, ≤0.5:4, ≤1:2.5, ≤2.5:1, else 0. Financials: 50% credit | Ideal zero debt; ≤0.5 structural; >2.5 red flag [T] |
| C3 | Unhedged FX debt (% of debt) | 3 | 0:3, ≤10:2, ≤25:1, else 0 | "Playing with fire" |
| C4 | Debt restructurings / OTS count | 4 | 0:4, 1:1.5, ≥2:0 + kill | Market forgives once, not twice [T] |
| C5 | ROCE − WACC (pp) | 5 | ≥10:5, ≥5:4, ≥0:2, else 0 | WACC = E/(D+E)·Ke + D/(D+E)·Kd·(1−t). Defaults Ke 13%, Kd 9%, t 25% (interview example: Kd 7, Ke 13, ROCE 15) |
| C6 | Execution hit rate (% of guidance/capex delivered on time) | 5 | ≥90:5, ≥75:3.5, ≥50:2, else 0 | Under-promise, over-deliver |

### Wealth distribution (15) [T]
| ID | Metric | Max | Scoring | Why |
|---|---|---|---|---|
| W1 | Payout ratio, 3y avg | 6 | ≥30:6, ≥25:5, ≥15:3.5, ≥10:2, else 0 | Min 10%; ideal 25–30% policy [T] |
| W2 | Years dividend paid, last 5 | 2 | 2 × years/5 | Defined policy, not ad-hoc [T] |
| W3 | Investments/loans to unrelated businesses (% NW) | 4 | ≤2:4, ≤10:2.5, ≤25:1, else 0; >25 kill | Power of focus; capital misallocation |
| W4 | Largest acquisition, 5y (% NW) | 3 | ≤10:3, ≤25:2, ≤50:1, else 0; >50 kill | >50% of net worth = red flag [T] |

### Investor communication (10)
1 pt per earnings call/yr (max 4) + investor presentation 2 + investor day/plant visit (2y) 2 + dedicated IR 2. All zero → "black box" kill switch [T].

### Liquidity (10)
F&O stock → 10. Else ADTV(6m)/mcap per day: ≥0.05%:10, ≥0.02%:8, ≥0.01%:5, ≥0.005%:2, else 0; capped at 3 if ADTV < ₹1 cr. Calibrated to the interview's "₹1 lakh cr mcap → ₹20–25 cr daily turnover; must be able to exit in ~5 days".

### Grade bands
AAA ≥85 · AA 70–85 · A 60–70 · BBB 50–60 · <50 reject [T for 50/70/85 cut-offs; letter names C].

## 3. Step 2 – Earnings growth potential (100)
| ID | Metric | Max | Scoring |
|---|---|---|---|
| G1 | ROCE 3y avg | 40 | ≥25:40, ≥20:34, ≥15:26, ≥12:12, else 0. Gate: <15% → REJECT [T] |
| G2 | Forward PAT CAGR (3–5y) | 30 | ≥26:30, ≥22:26, ≥18:22, ≥15:12, ≥10:5, else 0. Hurdle 18% [T] |
| G3 | Demonstrated 5y PAT CAGR | 15 | ≥20:15, ≥15:10, ≥10:5, else 0 ("must have demonstrated track record") |
| G4 | Structural vs cyclical | 15 | structural 15 / semi-cyclical 7 / cyclical 0 |

Warning if forward growth > history + 10pp ("capitalising a cyclical spurt" – the fast-fashion retailer example: PE 200 on 100% growth, growth fell to 15%, stock ₹8,000 → ₹3,000).

## 4. Step 3 – Purchase-price discipline [T]
- **PEG = PE(TTM) / forward PAT CAGR(%)**. <1 multibagger zone · 1–2 buy · 2–3 caution · >3 serious red flag. Exceptions exist (Bajaj Finance, HDFC Bank in their prime) but are rare.
- **Cumulative-profit test**: Σ next-5y PAT (at forward growth) ≥ today's market cap → sitting on a multibagger.
- **Expected return** (straight maths from the interview: return = earnings growth × change in multiple):
  `E[R] = (1+g) × (exit PE / entry PE)^(1/n) − 1 + dividend yield`, n = 5, exit PE = 10-year median PE (if not given, assumes no re-rating).
- **Payout-implied theoretical PE** (structural businesses only): payout ratio ÷ market dividend yield (~1.5–2%). HUL example: 70% / 2% = 35x. Shown as a cross-check, not scored; warns only for structural, non-financial companies with payout ≥ 50% (for low-payout growers the method gives meaningless numbers).
- **Max buy price** = lower of (price at PEG 2) and (price at which E[R] = required return).

Price score (0–100) = PEG component (≤1 → 60, 2 → 40, 3 → 10, >3 → 0, linear between) + return-margin component (E[R] − required: +10pp → 40, 0 → 20, −10pp → 0).

## 5. Risk-reward matrix – required return
Required return = cap-tier base + quality risk premium.

| Tier [C cut-offs, ₹ cr] | Base [T] |
|---|---|
| Large Cap 1 / Mega (≥2,00,000) | 13% |
| Large Cap 2 (≥1,05,000 – AMFI Jan-2026 large-cap cut-off) | 16% |
| Mid Cap (≥34,700 – AMFI Jan-2026 mid-cap cut-off) | 19% |
| Small Cap 1 (≥5,000) | 22% |
| Small Cap 2 (<5,000) | 25% |

| E-QUAL | Premium |
|---|---|
| ≥85 | +0 [T: "13% for mega cap with no issues"] |
| 70–85 | +2 [T: "14–15%"] |
| 60–70 | +5 [T: "one level down, 13 → 18"] |
| 50–60 | +10 [C; interview's extreme small-cap corner was ~43%] |
| <50 | do not invest [T] |

Update the AMFI cut-offs every January/July (AMFI publishes the list semi-annually; large-cap = top 100, mid = 101–250).

## 6. Kill switches (any one → REJECT) [T]
- Promoter pledge ≥ 70% of holding
- Debt restructured ≥ 2 times
- Net debt/equity > 2.5x (non-financials)
- Single acquisition > 50% of net worth
- Investments in unrelated businesses > 25% of net worth [C threshold]
- Zero investor communication (black box)
- E-QUAL < 50, or ROCE < 15% (gates)

Warnings (no auto-reject): pledge > 25%, promoter pay > 8% of PAT, audit fee outside band, auditor red flag, sister concern, royalty to promoter entity, PE above payout-implied PE, forward growth ≫ history, growth visibility < 3 years.

## 7. Verdict logic (in order)
1. Kill switch → **REJECT**
2. E-QUAL < 50 → **REJECT**
3. ROCE < 15% → **REJECT** (value trap)
4. Cyclical → **OUT OF FRAMEWORK**
5. Forward PAT CAGR < 18% → **PASS**
6. PEG > 3 → **AVOID**
7. PEG ≤ 2 and E[R] ≥ required → **BUY** (PEG ≤ 1 and cumulative 5y PAT ≥ mcap → **BUY – MULTIBAGGER SETUP**)
8. Otherwise → **WATCHLIST** (wait for max buy price)

"(PROVISIONAL)" is appended when < 80% of rules had real data.

## 8. Exit rules [T]
Sell only if: (a) growth sustainably falls below 18–24%, (b) management/governance thesis breaks, or (c) PEG > 3 / euphoria. Don't sell a structural compounder just because it's up 20x (Eicher ₹40 → ₹8,000; Page Industries ~150-bagger). Beware mis-reading a temporary margin squeeze as a broken moat (his Pidilite mistake: VAM price spike looked like lost pricing power, but pricing power held).

## 9. Where to find each input (Indian listed companies)
| Input | Source |
|---|---|
| Price, mcap, PE, PAT, ROCE, 5y PAT CAGR, payout, 10y median PE, D/E | Screener.in company page / export; NSE/BSE quote |
| Promoter holding, pledge, 3y change | BSE/NSE quarterly shareholding pattern (Screener "Shareholding") |
| Bonus/split/buyback/preferential history | BSE corporate actions; Screener "Documents"; annual reports |
| FCCB / warrants / convertibles | Annual report notes on borrowings & share capital; exchange filings |
| Promoter remuneration, MD:median-employee ratio | Annual report – Board's report, "Particulars of employees" (Sec 197(12), Rule 5(1)); Corporate Governance report |
| Auditor name, audit fee, qualifications | Independent auditor's report; notes – "Payment to auditors" |
| Related-party transactions, royalty | Ind AS 24 related-party note; half-yearly RPT filings on exchanges |
| Exports / imports | Board's report – "Foreign exchange earnings and outgo"; geographic segment note |
| Unhedged FX debt | Financial-risk-management note (foreign currency exposure, hedged vs unhedged) |
| Restructuring history | Credit-rating rationales (CRISIL/ICRA/CARE/India Ratings), news, CDR/OTS disclosures |
| Execution hit rate | Compare past con-call/AR guidance (revenue, capex commissioning dates) with actuals |
| Unrelated investments, acquisitions | Notes on investments & loans (Sec 186), exchange filings on acquisitions |
| Investor communication | Company IR page; con-call transcripts filed on BSE/NSE |
| ADTV, F&O status | NSE historical data; NSE F&O securities list |
| Forward PAT CAGR | Management guidance, consensus estimates, or own model – always state the basis |
