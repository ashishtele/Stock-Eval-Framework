# Evidence Stock Screen — Scoring Framework (Model 1.0)

Model version: 1.0. Universe: Indian non-financial operating companies. All weights, cutoffs, freshness windows and decision bands are transparent heuristics, not empirically calibrated predictors. A score is not a probability of success or an estimate of future returns. Verification means reproducible arithmetic plus inspected evidence; predictive validity requires separate out-of-sample testing.

## 1. Inputs And Evidence

Use the bundled example (`assets/example.json`) as the JSON schema reference, never as a source of real-company values. Set `schemaVersion` to `1.0`, `synthetic` to `false` for actual research, `sectorClass` to `non-financial`, and `asOf` to the research date. An unsupported classification produces `OUT_OF_SCOPE` with no score.

`financials` contains exactly five comparable, consecutive 12-month annual periods, oldest first. All financial amounts use INR crore; diluted shares use crore shares, so profit divided by shares gives INR/share. Use consolidated statements consistently. Do not mix standalone profits with consolidated debt, CFO or revenue. Record accounting-policy changes and restatements in the ledger. A company with insufficient comparable history is outside the full model; do not invent older periods.

### Fields for each year

- **yearEnd**: real ISO date, no later than `asOf`.
- **revenue**: revenue from operations, excluding non-operating other income.
- **ebit**: operating earnings before interest and tax; exclude identified non-recurring/non-operating gains, with a reconciliation to reported accounts.
- **ebitda**: EBIT plus relevant depreciation/amortization, using a consistent lease-accounting basis.
- **pat**: consolidated profit after tax including non-controlling interests, consistent with consolidated CFO. Flag exceptional items and also inspect the unadjusted series; do not remove recurring "one-offs."
- **cfo**: net operating cash flow after cash tax, directly reconciled to statements. Treat interest classifications consistently across issuers and periods; document any analytical reclassification.
- **capex**: positive cash outflow for tangible/intangible operating assets, including capitalized development. Do not net asset disposals. Business acquisitions are separately reviewed under capital allocation and gates, not silently counted as organic capex.
- **capitalEmployed**: end-period total equity including non-controlling interests plus interest-bearing debt and lease liabilities, less unrestricted cash/cash equivalents and liquid non-operating investments. Exclude restricted cash from deductions. Use the same definition in every year.
- **netDebt**: interest-bearing debt plus lease liabilities less the same unrestricted liquid assets. It may be negative.
- **interest**: positive interest/borrowing finance expense including leases, excluding unrelated fair-value or FX movements. Zero is allowed, but never substitute zero for missing disclosure.
- **dilutedShares**: diluted weighted-average shares, retrospectively adjusted for splits/bonuses consistently. Capital raised through actual issuance is dilution; it is not a split adjustment.

Missing numeric data is `null`, not zero. Fields must be finite JSON numbers, not formatted strings. Percentages in `business` are 0-100; growth rates, returns, margins and discount rates are decimals, e.g. 0.15 for 15%.

Each source has `id`, `kind`, `url`, `publishedAt`, `accessedAt`, `locator`. IDs are unique. Supply public document links, not authenticated browser/session URLs. Cite every material input in a companion ledger with: field/metric; period; raw reported value; adjustment; final value; currency/unit; source ID; exact page/table/quoted passage; checked-by/date. One annual report may support several fields, but a vague report-level citation is insufficient for the ledger.

### Source factors

- `audited = 1.0`: inspected audited statements/notes for historical facts.
- `regulator = 1.0`: inspected official order or regulatory record for the assertion it actually establishes.
- `exchange = 1.0`: exchange price records or inspected filed historical disclosures. Filing a forecast does not make that forecast an established fact.
- `management = 0.8`: attributable management statement with date and context, not independently confirmed.
- `secondary = 0.5`: attributable third-party estimate/aggregation not reconciled to a primary source.
- `podcast = 0`: interview, tips, social claims or unsupported narrative used as company evidence. This includes any supplied interview or transcript.

Use `evidence[metricId]` to list the essential sources supporting that metric's factual inputs. The metric factor q is the minimum source factor in that list. When an authoritative source replaces a weak one, use the authoritative source in the calculation and retain the discarded lead in notes. If a necessary input still rests on weak evidence, do not omit that source to improve q. An unavailable metric or empty evidence list has q = 0. Conflicting disclosures must be reconciled or treated as missing, not averaged.

For live research, access and gate checks must be recent. For historical research, sources and financial periods must have been public by asOf; access can happen later. The program checks publication dates, but cannot detect a restated dataset passed off as original data. Preserve contemporaneous originals. It cannot verify whether a URL's content supports a claim, classify source honesty, or confirm that every relevant filing was found. These are mandatory researcher checks.

## 2. Five Gates

For each named gate supply `status` (`pass | fail | unknown`), `sourceIds`, `checkedAt`, and a specific note. Each pass needs source factor 1, a review date within 30 calendar days before asOf, and a nonempty note. Unsupported or stale passes become unknown. A declared fail remains a conservative screening veto even if its evidence is weak; describe such a concern as unverified, never as proven misconduct.

- **auditIntegrity**: inspect audit opinions and qualifications, internal-control reports, auditor changes/resignations, explanations and responses. Material unresolved adverse/disclaimer opinions, documented material accounting misstatement or unresolved serious audit findings fail the screen. A routine rotation is not a failure. An unexplained resignation with no adequate documents is unknown pending review, not proof of fraud.
- **reportingIntegrity**: reconcile material financial discrepancies and review regulator/exchange findings, material related-party transactions, promoter disclosures and capital diversion concerns. Confirmed material deception/diversion or unresolved material inconsistencies fail. An uncorroborated accusation alone is not a finding; unresolved evidence blocks a pass.
- **solvency**: inspect defaults, insolvency proceedings, refinancing needs, credit reports, contingent liabilities and going-concern disclosures. An uncured default, active insolvency or unaddressed material going-concern funding gap fails. Leverage ratios below are additional quantitative flags, not substitutes for this review.
- **filingCurrency**: inspect the most recent annual and legally due interim filings and material announcements through asOf. Missing mandatory filings, unexplained material reporting delays or irreconcilable current disclosures fail. Tool/data unavailability gives unknown. Compare the latest interim trend with annual data and downgrade the case if the annual series is no longer representative.
- **liquidity**: inspect suspension, surveillance restrictions, traded value and circuit history. This version fails suspended names, median daily traded value below INR 5 crore over the last 60 trading sessions, or five consecutive lower-circuit closes within those sessions. These screening thresholds are policy choices, not guarantees of exit. Surveillance alone triggers review, not an automatic fraud label. Missing trading evidence gives unknown.

No numerical score overrides these gates. A fail means `REJECT_NEW_POSITION`; an unknown blocks shortlisting. This does not instruct a holder to send a market sell order into an illiquid market.

## 3. Score Formula

For each metric, define a bad endpoint b, a good endpoint g, a raw value x, fixed weight w and evidence factor q:

    normalized = clip((x - b) / (g - b))   where clip(z) = min(1, max(0, z))
    points     = w * normalized * q
    Score      = sum(points)               [0 to 100]
    Coverage   = sum(w for metrics with q >= 0.8)   [0 to 100]
    EvidenceStrength = sum(w * q)          [0 to 100]

The same equation handles higher-is-better and lower-is-better metrics because g can be below b. Missing values earn zero; never redistribute their weight. Coverage measures documented input availability, not probability that the figures are true. A fully documented bad business can have 100% coverage and a low score.

Pillar maxima: **Governance 25; Business 20; Finances 20; Runway 15; Valuation 15; Downside 5.** There are **17 metrics**. All ratios use unrounded inputs; output rounding is display-only, and decision thresholds use full precision.

### G1 Management Commitment Delivery

Weight 10; b = 0.50, g = 0.90.

x = deliveredCommitments / dueCommitments, requiring at least five eligible due commitments.

Build the ledger from all material, specific commitments first made within the five years preceding asOf, with deadlines due in the last three years. Include revenue/margin targets, commercialization, commissioned capacity, debt reduction and promised capital-allocation milestones. Exclude vague aspirations and future deadlines. Freeze eligibility before observing outcomes; do not count repeated versions of one target multiple times. Record original statement/date/source, original metric/range, deadline, actual outcome/source, and met/missed.

A promise is delivered only when its original deadline and stated threshold/range were met; no credit for quietly lowered targets. Qualitative milestone promises require the promised milestone to be operational, not merely announced. If fewer than five are available, or outcomes cannot be established, use null. An understated management team can be unscorable here without being poor management; do not invent promises to fill the sample.

### G2 Cash Conversion

Weight 8; b = 0.50, g = 1.00.

x = sum(CFO over latest 3 years) / sum(PAT over latest 3 years).

Use the sum ratio, not the mean of annual ratios. A non-positive PAT sum receives zero and a high-risk flag. Missing CFO/PAT yields null. Investigate receivable build, factoring, customer advances and payment deferrals: a high ratio alone does not establish clean accounts.

### G3 Promoter Pledging

Weight 4; b = 20, g = 0 (percentage points).

x = 100 * pledged promoter shares / total promoter shares at the latest disclosed date. For a genuinely promoter-less company, zero is permitted only with a sourced ownership explanation. Non-disclosure is null. Above 20% triggers a high-risk flag; it is not a legal finding of wrongdoing.

### G4 Related-Party Sales Exposure

Weight 3; b = 20, g = 5 (percentage points).

x = 100 * latest annual sales to related parties outside the consolidated group / consolidated revenue.

Exclude eliminated intra-group sales and prevent double counting. Legitimate related-party business can be substantial, so this is a concentration/accounting scrutiny proxy, not a fraud test. Loans, guarantees, asset transfers and purchases also require gate review even though this narrow ratio does not capture them. Missing disclosure is null.

### B1 Return On Capital

Weight 10; b = 0.10, g = 0.20.

For each of the latest three years: ROCE_year = EBIT_year / mean(CE_previous_year_end, CE_current_year_end). x is the arithmetic mean of those three ROCE values.

Non-positive capital in the required four end-period balances receives zero and a high-risk/model-unsuitable flag. Missing inputs yield null. ROCE is pre-tax; do not compare this directly with a post-tax WACC. Exceptional accounting profits must be reconciled consistently.

### B2 Operating-Margin Retention

Weight 5; b = 0.70, g = 1.00.

x = min(latest 3 annual margins) / median(all 5 annual margins), where margin_year = EBIT_year / revenue_year.

Non-positive median margin receives zero. Missing/zero-revenue periods give null. This is a stability proxy, not proof of pricing power or a monopoly; a stable low-margin business still needs sound capital returns.

### B3 Customer Concentration

Weight 5; b = 40, g = 10 (percentage points).

x = 100 * sales to largest external customer / total sales using the most recent comparable disclosure. Do not confuse a distributor/customer with an end-market. Missing concentration data is null, not an assumption that retail brands are diversified.

### F1 Leverage

Weight 6; b = 3.0, g = 0.0.

x = latest netDebt / latest EBITDA.

Net cash receives full points after clipping. Non-positive EBITDA receives zero points (the calculator uses the bad endpoint as a scoring sentinel) and a high-risk flag. An actual ratio above 3 also triggers high risk. Investigate off-balance-sheet obligations separately.

### F2 Interest Coverage

Weight 6; b = 2, g = 8.

x = latest EBIT / latest interest.

Non-positive EBIT receives zero. Positive EBIT with verified zero interest receives full points; the calculator uses 8 as a finite capped sentinel, not a claim that the actual mathematical ratio is 8. Missing interest is null. Actual coverage below 2 triggers high risk.

### F3 Free-Cash-Flow Consistency

Weight 5; b = 1, g = 4.

FCF_year = CFO_year - capex_year; x = number of strictly positive FCF years among five.

Zero FCF does not count as positive. Any missing annual CFO or capex makes the metric null. This is a cash-generation consistency measure, not FCFE used in the valuation model. Expansion can legitimately depress FCF; inspect returns and funding rather than waiving the metric.

### F4 Share Dilution

Weight 3; b = 0.05, g = 0.00.

x = (dilutedShares_latest / dilutedShares_3_years_earlier)^(1/3) - 1.

Use split/bonus-adjusted shares. Buybacks receive full points here but can still destroy value; capital-allocation diligence remains required. Missing/non-positive share counts give null.

### R1 Demonstrated Demand Growth

Weight 5; b = 0.05, g = 0.15.

x = (revenue_latest / revenue_3_years_earlier)^(1/3) - 1.

Revenue endpoints must be positive; otherwise null. Reconcile acquisitions, disposals, currency and commodity-price effects. Report organic/volume growth separately where available. Revenue growth without cash and capital returns is not sufficient.

### R2 Incremental Capital Productivity

Weight 5; b = 0.10, g = 0.20.

x = (EBIT_latest - EBIT_3_years_earlier) / (CE_latest - CE_3_years_earlier).

Earlier CE and its increase must both be positive; otherwise null, not a flattering ratio from a negative denominator. This pre-tax proxy is not a project IRR or proof that recent capex caused the earnings increase. Acquisitions, working-capital release and cash accumulation can distort it; require a capital bridge. Asset-light or non-expanding businesses can lose these five points without being unattractive overall.

### R3 Evidenced Growth Runway

Weight 5; b = 0, g = 4. x is the count of true entries in `business.runwayChecks` in this fixed order:

1. **Demand**: independently evidenced customer demand, repeat orders, executed contracts or measured market/volume growth; a management market-size slide alone is insufficient.
2. **Delivery**: operating/qualified capacity, distribution or product capability that can serve the demand; announced capex alone is insufficient.
3. **Funding**: a sourced three-year cash/funding bridge that covers maintenance, expansion and working capital under stated stress assumptions; no unexplained financing gap.
4. **Economics**: evidence that the incremental activity can meet at least the 10% pre-tax incremental-return floor, with measured utilization/margins or comparable project results; unsubstantiated revenue targets are insufficient.

Each check is true, false or null with a source-backed explanation. False means assessed and not met; null means not established. Any null makes this metric unavailable. Management confidence and a supportive national policy cannot substitute for these checks.

### V1 Margin Of Safety

Weight 10; b = 0, g = 0.30.

x = 1 - currentPrice / baseFairValue, using the valuation method below. This is a discount to an assumption-dependent fair value, not a guaranteed protection against losses.

### V2 Modeled Return Hurdle

Weight 5; b = 0.10, g = 0.20.

x = (baseTerminalWealth / currentPrice)^(1/5) - 1.

This terminal-wealth CAGR treats interim dividends as cash held to year five with no reinvestment. It is not an annualized IRR of dated cash distributions. Values are nominal, pre-tax and pre-transaction-cost.

### D1 Modeled Bear Loss

Weight 5; b = 0.50, g = 0.15.

x = max(0, 1 - bearTerminalWealth / currentPrice).

This is the modeled loss at the five-year endpoint, not maximum drawdown, worst possible loss, VaR or expected shortfall. Intra-period drawdown and total loss can be much larger. A value above 50% triggers high risk. Show bear fair value as well: positive nominal terminal wealth can still fail the required-return hurdle.

## 4. Valuation Model

Inputs: current INR/share price and price date; positive `normalizedEps`; `discountRate`; `peerMedianPe`; `historyMedianPe`; and bear/base/bull objects containing `epsGrowth`, `terminalPe`, `payoutRatio`.

Normalize EPS with a bridge from reported diluted earnings attributable to ordinary shareholders, removing genuine non-recurring items and allowing for tax, non-controlling interests and expected dilution. For cyclical businesses use a documented mid-cycle earnings basis; if that basis cannot be defended, do not score valuation. For companies capitalizing excessive costs, adjust earnings before modeling. Do not feed enterprise-value multiples into this equity EPS model.

Freeze a comparable peer list before looking at the result: preferably at least five profitable companies with comparable products, geography, maturity and accounting. Use the median current normalized P/E for that set. `historyMedianPe` is the issuer's median from at least 36 comparable positive monthly trailing-P/E observations over the prior five years, with corporate actions and earnings methodology reconciled. Record excluded negative/meaningless observations. If suitable peers or history are unavailable, use null and block valuation; do not invent a favorable substitute.

Set a common nominal equity required return before comparison, ordinarily 15% for this research policy, with any change explicitly justified. The synthetic fixture uses 12% only to demonstrate arithmetic. The calculator permits positive rates up to 100% for explicit scenarios, so the researcher must reject economically implausible choices. It is not WACC. Do not lower it until the stock looks cheap.

```
H = 5 years
P = current price
EPS0 = normalized diluted EPS
r = required equity return
g = scenario EPS growth
payout = scenario dividend / earnings ratio

ceilingPE = min(P / EPS0, peerMedianPe, historyMedianPe)
exitPE = min(scenario terminalPe, ceilingPE)
EPS_t = EPS0 * (1 + g)^t
Dividend_t = EPS_t * payout
TerminalPrice = EPS_5 * exitPE
FairValue = sum(Dividend_t / (1 + r)^t, t=1..5) + TerminalPrice / (1 + r)^5
TerminalWealth = TerminalPrice + sum(Dividend_t, t=1..5)
MOS = 1 - P / FairValue
TerminalWealthCAGR = (TerminalWealth / P)^(1/5) - 1
TerminalWealthLoss = max(0, 1 - TerminalWealth / P)
```

Terminal P/E is capped to avoid relying on multiple expansion. Fair value is conditional on the observed price through that cap; it is a conservative screening value, not a price-independent intrinsic valuation. Re-running at a lower price can change the cap, so do not solve a mechanical buy target from one MOS calculation.

Base EPS growth cannot exceed min(20%, max(0, historical three-year revenue CAGR)). Bear/base growth cannot exceed 20%; bull cannot exceed 30%; all must exceed -100% (implementation lower bound -99%). Scenarios must be ordered bear <= base <= bull for growth, proposed exit P/E and terminal wealth. Payout is between 0 and 1. Non-positive normalized EPS blocks this valuation and produces a high-risk/model-unsuitable flag. Missing inputs produce null valuation metrics.

Forecast discipline remains a researcher responsibility. Reconcile growth and payout with reinvestment, returns on capital and funding; a high payout plus high growth cannot be assumed without a capital-light/high-return mechanism. Model customer loss, utilization slippage, pricing pressure or regulatory delays in the bear case, including a multiple contraction. If the scenario format cannot express the risk, add a separate stress analysis and do not imply that D1 captures it.

**Required sensitivities**: lower base growth by 5 percentage points; reduce effective exit multiples by 20%; increase the required return by 2 percentage points; and combine the three. Preserve scenario ordering and use the explicit lower effective multiple as the new requested multiple so the cap does not hide the stress. Report changes in fair value, MOS, score and status. Mark the case fragile if a modest sensitivity changes eligibility or reduces the score by at least 10 points. Sensitivity runs are required in research; they are not automatically generated by the single-input calculator.

## 5. Decision Rules

Applied in this exact order, with all reasons preserved:

1. Unsupported sector/model: `OUT_OF_SCOPE`, score null.
2. Any gate fail: `REJECT_NEW_POSITION`, even if the numerical score is 100.
3. Any quantitative high-risk flag: `HIGH_RISK`. Flags are non-positive three-year PAT, non-positive relevant CE, non-positive latest EBITDA, net debt/EBITDA > 3, interest coverage < 2, pledge > 20%, non-positive normalized EPS, or modeled bear terminal loss > 50%.
4. Any unknown gate; missing or >7-calendar-day-old price; latest annual year end >550 days old; coverage <85%; evidence strength <80%; or missing/weak critical metric evidence: `INSUFFICIENT_EVIDENCE`. Critical metrics are G1, G2, B1, F1, F2, V1, V2, D1, each requiring q >= 0.8. The filing-currency gate additionally checks current interim information; annual age alone is not enough.
5. Score >=75, base MOS >=20%, base terminal-wealth CAGR >=required return, and bear terminal loss <=35%: `RESEARCH_SHORTLIST`.
6. Otherwise score >=60: `WATCHLIST`. This includes high-quality businesses whose current valuation fails the shortlist hurdles.
7. Otherwise: `LOW_PRIORITY`.

The calculator preserves numerical diagnostics for blocked cases, but those numbers are provisional, not rankings against eligible names. HIGH_RISK can coexist with missing evidence; the reasons list must still disclose the gaps. A company with a passed model still needs sensitivity and portfolio checks. Do not convert a shortlist into a buy instruction.

## 6. Portfolio Safeguard

Separate the stock score from personal allocation. The calculator intentionally returns `portfolioStatus: NOT_ASSESSED`. Ask for investable portfolio value, current stock/sector exposure, liquidity needs and a user-approved loss budget before sizing. Do not request account credentials or private account numbers.

An optional conservative illustration, not a personalized allocation rule:

```
stressLoss         = max(0.50, modeledBearTerminalLoss, additionalAdverseStressLoss)
riskWeight         = 0.01 of investable portfolio / stressLoss
liquidityWeight    = 5 exit sessions * 0.05 participation * medianDailyTradedValue / portfolioValue
sectorHeadroom     = max(0, 0.25 - currentWeightOfOtherHoldingsInSameSector)
maximumTotalStockWeight    = min(0.05, riskWeight, liquidityWeight, sectorHeadroom)
maximumAdditionalWeight    = max(0, maximumTotalStockWeight - existingStockWeight)
```

All amounts must use consistent currency units. These 5% stock, 25% sector, 1% stress-budget and 5% daily-participation limits are illustrative policy assumptions that require user agreement. They do not guarantee loss containment: total loss of a 2% holding costs 2%, even if a 50% stress led to a 1% modeled loss budget. Correlated holdings can fail together; assess aggregate stress, leverage and emergency liquidity separately. Circuit locks can make assumed exit capacity zero.

## 7. Monitoring And Falsification

Register falsifiers before relying on a thesis, not after a price fall. Examples: a dated operating milestone missed by more than two reported quarters; rolling cash conversion below 0.5; debt/EBITDA above 3; a key customer/program cancellation; an adverse regulator/auditor development; or loss of the assumed volume/margin economics. Choose company-specific thresholds where necessary, disclose them separately from model defaults, and cite how they will be measured.

Review business economics year on year, check quarterly results for trajectory, and review material governance/regulatory/debt/liquidity announcements immediately. Re-score after annual results, material events and large valuation changes. A five-year horizon is not permission to ignore falsification. A high prior return is neither a reason to hold nor a reason to sell without prospective valuation and risk analysis.

Sector overlays do not change weights silently:

- **Pharma/CDMO**: distinguish discovery, qualification, clinical, commercial and contracted stages; inspect customer/program concentration, molecule attrition, regulatory findings, usable capacity, utilization, capitalized R&D and realized cash returns. A geopolitical theme or capex announcement is not an order.
- **Dairy/consumer**: inspect procurement costs, pass-through lags, cold-chain/distribution investment, inventory/receivables, segment margins and actual premium-brand profitability. Brands and unorganized-to-organized market forecasts are leads, not score inputs without evidence.
- **Cyclicals**: inspect mid-cycle earnings and stressed debt service. Peak earnings can make P/E look artificially cheap; this framework can be unsuitable until normalization is defensible.

## 8. Worked Example And Limits

The bundled fictional company (`assets/example.json`) is intentionally strong on every metric and has fabricated sources clearly marked `.invalid`. It exists to test arithmetic, not to represent an attainable investment or to imply that actual research should score 100.

Its price is 100, normalized EPS 10, required return 12%, base growth 20%, base payout 50%, and requested exit P/E 10. The five-year base results are:

- Terminal price: **248.8320**. Cash dividends over five years: **44.6496**. Terminal wealth: **293.4816**.
- Discounted fair value: **172.0894**. Margin of safety: **41.8907%**.
- Terminal-wealth CAGR: **24.0270%**. Evidence-adjusted score: **100**; coverage: **100%**; strength: **100%**, all synthetic.

The requested bull P/E of 12 is capped at today's P/E of 10. Its benign bear assumptions produce zero nominal endpoint loss, yet bear fair value is only **74.7666**; zero D1 loss therefore does not imply an attractive bear-case required return or absence of risk.

Set G1 evidence to an empty list: the score falls to **90** and status becomes `INSUFFICIENT_EVIDENCE`, because a critical measure lacks support. Set the audit gate to fail instead: even a score of 100 becomes `REJECT_NEW_POSITION`. These are tested behavior (`scripts/score.test.mjs`), not discretionary overrides.

Before claiming predictive skill, pre-register the universe, thresholds, holding/rebalancing policy and comparison benchmark; use point-in-time disclosures, contemporaneous prices, delisted/failed companies, actual disclosure lags, transaction costs, taxes and liquidity/circuit constraints. Use time-separated training and out-of-sample periods, compare against an appropriate total-return index and simple quality/value baselines, and report turnover, drawdown, loss frequency and stability across sectors. Do not tune on the interview's winners and call it validation. **No such return backtest has been performed for version 1.0.**
