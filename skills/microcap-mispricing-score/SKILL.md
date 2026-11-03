---
name: microcap-mispricing-score
description: Score any listed stock (built for Indian small and microcaps) on a 0-100 "mispricing" framework. Covers business-type-specific valuation (cyclical, stable, growth, capex-transition, new-age), six multiples vs own history, one-off-stripped / cyclically adjusted / forward earnings, P/B-implied P/E, OCF quality, one-off-vs-habit expense checks, PEG and earnings gap, capital-cycle setup, upside/downside asymmetry, and governance kill switches. It also classifies the stock as cheap-and-undervalued, value trap, or not cheap. A deterministic Python script does the maths and produces an auditable rule-by-rule report. Use this whenever the user wants to evaluate, screen, score, value or compare a stock or company. Also use it when they share a Screener.in export or annual-report numbers, or ask whether something is cheap, undervalued, a value trap, or what its cyclically adjusted P/E, EV/OCF or PEG is, even if they don't say "score".
---

# Microcap Mispricing Score

Apply a microcap investor's mispricing framework to any company and get a reproducible score. The maths
lives in `scripts/score_stock.py`. All weights and thresholds are in `scripts/framework_config.json`, so
results are verifiable and tunable. Read `references/framework.md` when you need the reasoning behind a
rule, or when the user asks "why". Read `references/data_collection.md` when gathering inputs.

## Workflow

1. **Get the numbers.** In order of preference:
   - a Screener.in Excel export: run `python scripts/screener_to_json.py file.xlsx --business-type <type> --out in.json`
     and read its found/missing report;
   - figures the user pasted or uploaded (annual reports, spreadsheets);
   - web search of filings or financial sites, citing sources.

   Never invent or recall financials from memory. A wrong number produces a confident wrong score. Missing
   fields are fine: the script skips them and reports coverage. Get the blank template with
   `python scripts/score_stock.py --template`. Keep every amount in one unit (e.g. INR crore).

2. **Pick `business_type` deliberately.** This choice drives which valuation rules apply. See the table in
   `references/framework.md` §2. State the choice and the reason to the user, because the wrong type
   gives misleading output:
   - a textile spinner scored as `stable` would look terrible at a trough;
   - a company just past its biggest capex, scored as `growth`, gets punished for upfront costs.

3. **Fill the judgement blocks honestly.** `qualitative`, `governance`, `one_offs` and `forward` are
   research conclusions. Fill them from evidence in the material, or ask the user. Otherwise leave them
   null so they're excluded rather than guessed. Set kill-switch flags to `true` only on evidence. Write
   the forward assumption in `forward.basis`.

4. **Run the scorer.**
   ```bash
   python scripts/score_stock.py in.json --json result.json --md report.md
   ```
   It is deterministic: same input + config = same score.

5. **Report back** in this order:
   - score, verdict and classification;
   - data coverage, flagging it if below 70%;
   - the two or three rules that drove the score up and down;
   - any expense, segment or PEG notes;
   - the open questions that would move the score most: usually the judgement flags and the forward
     assumption.

   Offer the markdown report as a file if they want the full audit trail. Say plainly that this is the
   mechanical output of a framework, not a recommendation, and that the user should verify inputs and make
   their own decision.

## Comparing several stocks
Score each company separately with the same config, then compare `score`, pillar percentages and
classification side by side. Pillar percentages are comparable across business types, but individual
valuation rules aren't.

## Tuning the framework
If the user disagrees with a threshold (say, a cyclical P/E of 12 should still earn full points), edit the
band in `framework_config.json` rather than the script. Then re-run `python -m unittest discover -s tests`:
the weights-sum test guards that every business type still totals 100.

## Things the score does not cover (mention when relevant)
- **Exits.** Selling discipline from the framework:
  - don't sell a structural re-rating just because it has doubled;
  - if your sell orders are absorbed quickly by credible buyers, pause selling;
  - don't miss a buy over a tiny limit-price difference.
- **Position sizing and portfolio construction.**
- **Large caps.** The framework argues individual investors rarely have an edge there.

## Verification
`tests/test_score_stock.py` checks every formula against hand-worked numbers, including the video's own
examples:
- 1x book at 20% ROE = 5x P/E;
- 30 P/E on 50% growth = PEG 0.6;
- a vanity spend of 20% of market cap triggers the kill switch.

It also covers kill-switch capping, re-basing on missing data, determinism and the Screener importer. Run
the tests after any change. Two hypothetical worked examples are in `assets/examples/`.
