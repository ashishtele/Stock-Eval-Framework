# Collecting the inputs

The score is only as good as its inputs. This guide lists where each field comes from and the traps to
avoid.

## Fastest path (Indian listed company)
1. On Screener.in, open the company and click **Export to Excel**.
2. Run `python scripts/screener_to_json.py Company.xlsx --business-type <type> --out company.json`.
3. Read the printed report:
   - check that `rows_missing` is empty, and fill anything missing by hand;
   - compare two or three years of sales, PAT and borrowings against the website.
4. Fill the judgement blocks (below) from annual reports, concalls and your notes.
5. Score it: `python scripts/score_stock.py company.json --json result.json --md report.md`.

The importer covers the 10 years Screener exports. For a 15-year cyclical margin average, add older years
from annual reports (oldest first).

## Field sources and traps

| Field | Source | Trap |
|---|---|---|
| `ebitda` | P&L: PBT + interest + D&A - other income | Exclude other income. Companies classify costs differently. |
| `total_debt` / `lease_liabilities` | Balance sheet / notes | Screener's "Borrowings" includes lease liabilities. Enter the lease amount separately so it is stripped. |
| `cash` | Cash & bank (+ liquid investments if truly free) | Don't count strategic or group-company investments. |
| `ocf` | Cash-flow statement | One year can be distorted by inventory or receivables swings; the script also uses a 5-yr average. |
| `market_cap_year_end` | Year-end price x shares | Needed for own-history percentiles. Adjust for splits and bonuses (the importer uses Screener's adjusted shares). |
| `expense_items` | P&L notes in annual reports (advertising, packaging, warranty, etc.) | Put them on a like-for-like basis across years and peers. AI tools can tabulate 15 years of annual reports quickly; check a sample by hand. |
| `segments` | Segment reporting / MD&A | Use the same segment definitions each year. |
| `one_offs` | Notes, exceptional items, concall commentary | Only genuinely non-recurring items. If it recurs, it's a habit, not a one-off. |
| `forward` | Your model, management guidance, capacity x utilisation x realisation | Write the assumption in `forward.basis`. Use `long_term_growth_pct` for PEG when the near-term rebound is unusually high. |
| `normalised_roe_pct` | Management's long-term guided ROE, or your through-cycle view | Optional. Overrides the computed basis. |

## The judgement blocks
These are research conclusions, not data. Record a one-line reason for each in your notes.

- **`qualitative.change_identified`:** can you name a concrete change? Examples: capacity exits, policy
  (blending mandates, offtake guarantees), a new product's share rising, a capex now complete,
  pent-up replacement demand, a demerger with focused management.
- **`seller_concern`:** why is the seller selling?
  - `cyclical`: the trough of a known cycle;
  - `temporary`: a weather or inventory overhang;
  - `growth`: "it never grows";
  - `management`;
  - `structural`: the business model is being disrupted.
- **`sector_underperformed_10y`, `capital_exiting_sector`:** build a simple equal-weight index of the
  sector's long-listed names and compare it with a broad index. Note closures and exits.
- **`drawdown_from_3y_high_pct`:** from the price chart.
- **`optionality` + `base_business_protects_value`:** list the options. Answer "true" only if the base
  business alone justifies today's market cap.
- **`ai_disruption_risk`:** think it through even if the answer is uncertain.
- **`governance.*`:**
  - `guidance_track_record`: compare IPO and early-call promises with what was delivered;
  - `credible_board_or_investors`;
  - `related_party_clean`;
  - `auditor_clean`: check which other companies the auditor signs for;
  - `promoter_vanity_spend`: the amount, e.g. aircraft or showrooms unrelated to the business.
- **Kill switches:** set these to `true` only on evidence: an admission, a regulatory order, a contradiction
  seen on a plant visit, an auditor and merchant-banker overlap with fraud names, or operator activity.

## Plant visits and meetings (feeding governance flags)
- A half-hour meeting with a trained promoter tells you little. Two to three hours with them, or a plant
  visit, shows how they deal with others and what slips out.
- On a visit, check first whether the plant is actually running: machines on, workers present, trucks at
  the gate. Ask employees what is going on. Inventory comes later.
- Signals are shades of grey, not black and white. Record the observation, then make the judgement call.
