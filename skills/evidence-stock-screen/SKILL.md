---
name: evidence-stock-screen
description: Evidence-based screen for Indian non-financial listed companies, built from the Piyush Mutha interview ("Evidence Stock Screen", Model 1.0). Scores a company 0-100 across six pillars (Governance 25, Business 20, Finances 20, Runway 15, Valuation 15, Downside 5) over 17 metrics, with five governance gates (auditIntegrity, reportingIntegrity, solvency, filingCurrency, liquidity) that veto before any score counts, an evidence ledger with source-quality discounts (audited/regulator/exchange=1.0, management=0.8, secondary=0.5, podcast=0), a five-year no-multiple-expansion valuation model (bear/base/bull, capped terminal P/E), a dated management commitment-vs-outcome ledger (G1), and a deterministic dependency-free Node calculator (scripts/score.mjs) that outputs an auditable JSON verdict. Use this whenever the user wants to evaluate, screen, rank or research an Indian listed non-financial company for a 3-5 year horizon, asks "should I research this stock", "is this a good long-term hold", "does the management deliver on promises", "what's the margin of safety on X", shares Indian annual-report numbers, Screener exports or filing links for a governance/quality/valuation check, wants a commitment-versus-outcome ledger, or asks to compare candidates on an evidence-based basis. Also use for point-in-time historical screening. Not for banks, NBFCs, insurers, brokers, asset managers, REITs, InvITs, pre-revenue companies, names without five comparable annual periods, or silver/gold/mutual funds. A score prioritizes research; it is never a buy signal, a return probability or personalized investment advice.
---

# Evidence Stock Screen

Turn an investment narrative into a falsifiable, source-backed research decision. The interview (see `references/transcript-analysis.md`) supplies research questions, not evidence that a stock is attractive. The numerical weights and thresholds are deliberately conservative design choices, not formulas from the speaker or an empirically validated alpha model.

Read `references/framework.md` (FOLLOW IT EXACTLY) before scoring: it carries every definition, threshold, missing-data rule, gate and output requirement. Read `references/transcript-analysis.md` for provenance and what the interview does/does not support. The deterministic calculator lives in `scripts/score.mjs` (Node 20+, no packages, no network). A synthetic fixture is `assets/example.json`; a smoke test is `scripts/score.test.mjs`.

**Model version 1.0 (12 Nov 2026). A score of 80 is not an 80% chance of success. Never describe it as one.**

## Scope

Default: Indian listed non-financial operating companies with five comparable annual financial periods. Compare similar business models, not unrelated sectors solely by score. The holding-period lens is 3-5 years; valuation uses five years.

Do **not** force banks, NBFCs, insurers, brokers, asset managers, REITs, InvITs, pre-revenue businesses or companies without comparable history into these formulas. Return `OUT_OF_SCOPE` and identify the required sector-specific model. Structurally negative capital, deep turnarounds and strongly cyclical peak earnings require special analysis; a low or blocked score can mean model unsuitability rather than a bad business. Do not assess silver, gold, mutual funds or portfolio diversification using this company score.

## Workflow

1. **Establish identity.** Company, NSE/BSE ticker, sector, analysis date, and whether the task is a current screen or a point-in-time historical exercise. Ask only for missing essentials. If screening an unspecified universe, ask for a candidate list or sector; do not pretend to exhaustively screen the exchange.
2. **Explain the tool.** It is a research prioritization aid, not a return probability. Do not copy the interviewee's concentration or claimed returns.
3. **Collect primary evidence** with available browsing/file tools: exchange filings, consolidated audited statements and notes, annual reports, company results, regulator orders and credit disclosures. Verify identity before using similarly named companies. If browsing or required documents are unavailable, request them and mark the work incomplete; never fabricate financial inputs or citations.
4. **Fix the as-of date and source set.** Record URL, publication date, access date, page/section, scope, units and any restatement. Historical research must use information public by that date, not later restated figures. Inspect document contents: merely providing a URL does not verify a number.
5. **Apply the five gates first** (`auditIntegrity`, `reportingIntegrity`, `solvency`, `filingCurrency`, `liquidity` — see framework §2). A failed gate vetoes new-position shortlisting. Unresolved gate evidence means `INSUFFICIENT_EVIDENCE`, not a clean bill of health. Describe allegations as allegations; distinguish confirmed orders from speculation; never call a company fraudulent because of a ratio or auditor change alone.
6. **Prepare five-year financial inputs** (INR crore, consolidated, consecutive periods), a management-commitment ledger, four runway checks, an evidence ledger and a normalized-EPS bridge — exactly as defined in `references/framework.md`. Enter unavailable numerical fields as `null`, never zero or optimistic estimates. Use all qualifying commitments, not selected successes.
7. **Set explicit bear/base/bull assumptions.** Cite the factual starting point and separately label forecasts. Freeze the peer set, discount rate, thresholds and normalization policy before comparing candidates. Test lower growth, lower multiples and a higher required return; do not manufacture a target price that clears a desired hurdle.
8. **Create a separate company JSON** using `assets/example.json` as the schema reference (never as real values). Set `synthetic: false`, replace every fictional source and number, and leave the bundled fixture unchanged. Store inputs and research notes in a user-approved research folder (e.g. `data/`), not in this skill directory.
9. **Run the calculator and retain its full output.** Do not replace computed numbers with intuition, round before classification, or manually upgrade a blocked status:
   ```bash
   node scripts/score.mjs /path/to/company-input.json
   ```
   Resolve the skill directory from this file's actual installation location; do not assume the cwd is the skill directory. Requires Node 20+. If execution is unavailable, show hand calculations and explicitly say calculator validation was not run. Smoke-test the fixture with `node --test scripts/score.test.mjs`.
10. **Review the score together with** its gates, coverage, assumptions, sensitivity, peer context and falsifiers. A shortlist is permission for deeper diligence only. Portfolio fit is a separate calculation; without portfolio inputs retain `portfolioStatus: NOT_ASSESSED`.
11. **Deliver the report** in the contract below. For a comparison, use the same as-of date, model version, hurdle rate and accounting treatment; rank only eligible companies and put blocked/incomplete cases separately.

## Report contract

Every material factual assertion linked to its source and locator. Sections:

1. **Decision:** company, ticker, as-of date, model version, status and evidence-adjusted score out of 100. State whether provisional or synthetic. Do not describe a score of 80 as an 80% chance of success.
2. **Evidence:** weighted coverage and strength, unverified inputs, stale items, five gate outcomes, and the reason for any veto.
3. **Score Breakdown:** six pillar totals and all 17 metric calculations, including raw values, thresholds, weights, evidence factors, source IDs and points. An appendix or saved JSON can hold the detailed calculations.
4. **Valuation:** current price and date, EPS normalization, discount rate, frozen peers, bear/base/bull assumptions, fair values, margin of safety, terminal-wealth CAGR and modeled terminal loss. Show the growth/multiple/rate sensitivities and identify fragile conclusions.
5. **Investment Case:** at most three independently evidenced drivers; three concrete falsifiers with deadlines or thresholds; what would change the score or thesis. A theme or a large capex number is not itself a driver of shareholder returns.
6. **Portfolio Check:** concentration, liquidity and stress sizing only if portfolio inputs are supplied. Otherwise state not assessed. Never infer risk tolerance or disposable capital from the target score.
7. **Sources And Next Review:** evidence ledger, uncertainties, upcoming filings/milestones and next review date. Revisit immediately for material governance, debt, regulatory or liquidity events.

## Boundaries

- Never place trades, access a broker, or make automatic sell decisions. This skill produces research, not execution.
- Never present invented thresholds as academically proven or as the interview's own system. Version any calibration changes and re-score the whole comparison set.
- Never award points for the interviewee's wealth, brand recognition alone, a past multibagger, tips, confidence, a bullish policy headline or a claimed guaranteed return. Do not infer safety from a long holding period. Stocks can lose all their value; circuit limits can prevent exit. A stop-loss assumption is not a liquidity guarantee.
- Explain material limitations briefly. For personal investment suitability, a SEBI-registered investment adviser can help; the screen does not replace that assessment.

## Provenance and validation

Distilled from "Evidence Stock Screen — Email Edition | Model 1.0 | 12 November 2026", a portable export of the skill. The bundled `assets/example.json` is fictional and exists to test arithmetic; its `.invalid` URLs cannot serve as evidence about a real company. Calculator arithmetic, the fixture's documented outputs (terminal price 248.83, fair value 172.09, MOS 41.89%, score 100, coverage 100%), and the two documented veto behaviours (empty G1 evidence → 90 / INSUFFICIENT_EVIDENCE; audit-gate fail → REJECT_NEW_POSITION) are verified by `scripts/score.test.mjs`. No out-of-sample return backtest has been performed for Model 1.0; the framework is a research policy, not a validated predictor.
