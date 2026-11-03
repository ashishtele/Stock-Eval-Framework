# The framework, rule by rule

Source: a podcast conversation with a small/microcap investor (Gaurav Agrawal) about how he values and screens
companies. This file paraphrases each idea and names the script field that implements it, so anyone can
check that the code matches the framework.

## Contents
1. Philosophy that shapes the scoring
2. Choosing the right metric (business types)
3. The six valuation multiples
4. The three adjusted earnings
5. Book value and ROE
6. Earnings quality and cash flow
7. One-off or habit?
8. Growth, PEG and the earnings gap
9. Cheap vs undervalued
10. Capital cycle and sentiment
11. Asymmetry and optionality
12. Governance and kill switches
13. What the script deliberately does not do

---

## 1. Philosophy that shapes the scoring
- **Look for mispricing, not a style.** He doesn't call himself a value or growth investor. He'll pay 50x for a
  50% grower he can underwrite, or 0.5x book for a no-growth company where he can see growth coming.
  This is why valuation rules change by business type.
- **Microcaps reward staying invested, but the work is for down markets.** In bull runs most microcaps
  triple; few hold their gains through a full cycle. Research exists to decide what to do when prices fall:
  add, hold or exit. This is why the downside rules matter as much as the upside ones.
- **Two-to-four-year holding view.** AI and other disruption make ten-year views unreliable. Inside the
  holding period you should not lose money even if the thesis is late. This is why the floor value and the
  downside rules use conservative earnings.
- **Prefer companies with five or more listed years.** History lets you check what management promised at
  IPO against what it delivered, using cash flows, calls and annual reports. IPOs are fine only at
  dislocations. Field: `governance.years_listed`.
- **Fear at the buy button is information.** His best returns came when buying felt scary: bad recent
  years, uncertain cycle timing, new products. This is why the cycle and sentiment pillar rewards
  pessimism that has a cyclical or temporary cause.

## 2. Choosing the right metric (`business_type`)
"A man with a hammer sees every problem as a nail" (Munger). Apply metrics that fit the business:

| Type | Why | Valuation rules used |
|---|---|---|
| `cyclical` | Earnings can be zero at the trough, so P/E is meaningless. Sales can't go to zero. | cyclically adjusted P/E, EV/Sales percentile, implied P/E from book |
| `stable` | Margins sit in a narrow band (e.g. consumer, about 9-12% EBITDA). | adjusted P/E percentile, EV/EBITDA percentile, EV/normalised OCF |
| `growth` | Profitable compounder. | PEG, forward P/E, EV/normalised OCF |
| `capex_transition` | Just finished its largest capex, so new salaries, depreciation and interest crush trailing PAT. A 100x P/E can still be undervalued. | forward P/E, EV/Sales percentile, PEG. Trailing P/E is ignored. |
| `new_age` | No comparable history. | forward P/E on your 1-3 yr PAT assumption, PEG |

## 3. The six valuation multiples
EV/EBITDA, EV/EBIT, P/E, EV/OCF, P/S and EV/Sales. All six are computed and shown. Only the ones relevant to
the business type are scored.

**EV** = market cap + debt - cash: what you'd pay every claimant to own 100% of the business. Lease
liabilities are excluded from debt because they are not real borrowing (config
`exclude_lease_liabilities_from_debt`). Use EV rather than market cap whenever you compare companies with
different leverage.

**Relative valuation against the company's own 10-15 year history** is the core move. Ask where today's
multiple sits versus the range the market paid in good and bad times. Fields: `pctile_ev_sales`,
`pctile_pe`, `pctile_ev_ebitda`, `pctile_pb`. These need `annual[].market_cap_year_end`. The same P/E can
range from 10x to 40x across sentiment cycles (IT, railways and defence were his examples), so the absolute
level alone says little.

## 4. The three adjusted earnings
1. **Trailing adjusted:** start from the last 12 months of PAT. Add back genuine one-off expenses (e.g. a
   plant fire or a compensation payout) and remove one-off gains. Inputs: `one_offs[]`; tax at
   `tax_rate` unless `tax_effected`.
2. **Cyclically adjusted:** average the EBITDA margin over up to 15 years. Multiply by current sales, then
   subtract current depreciation and interest, then deduct 25% tax. Market cap / that PAT is the
   cyclically adjusted P/E. He wants single digits for cyclicals (`cyclically_adjusted_pe` <= 10 earns
   full points).
3. **Forward (1-3 years):** for growth, new-age and capex-done companies, estimate PAT once the
   new capacity is used. Inputs: `forward.pat`, or `forward.sales` + `ebitda_margin_pct`.

Screener and similar sites show unadjusted P/E. His point is that those numbers have no value until you
check the denominator.

## 5. Book value and ROE
A business at 1x book that can earn 15-20% ROE is effectively bought at about 5-7x earnings
(`implied_pe_from_book` = P/B / normalised ROE). The textile example: a well-run yarn maker traded below
book when margins were 8-9%. Management's long-term band was 14-18%. At a 16% mid-point the ROE came to
about 18-19%, giving a 5-7x adjusted P/E, and the stock tripled. In the Apar example, management guided
20% ROE while the stock sat at 1x book.

The ROE basis is chosen to avoid double-counting the cyclically adjusted P/E:
- the guided ROE, if `forward.normalised_roe_pct` is given;
- otherwise the 10-year average ROE for cyclicals;
- otherwise forward ROE for capex-transition and new-age companies.

## 6. Earnings quality and cash flow
- **EV/OCF** rewards companies that turn EBITDA into cash. Typical healthy range is about 5-15x; it is
  meaningless for loss-making new-age firms.
- **Aggressive vs conservative revenue recognition.** An EPC contractor that works for payers who settle
  after 200+ days books revenue and EBITDA, but OCF is weak or negative. Fields:
  `ocf_ebitda_conversion_5y` and `receivables_minus_sales_growth_pp` (debtors should grow slower than
  sales).
- **Normalise OCF over five years.** One year can be inflated or depressed by an inventory build for a
  new plant or a receivables swing (`ev_ocf_normalised`, `ocf_at_peak`).
- A company that grows revenue while receivables fall in absolute terms is rare and a strong quality
  signal (`receivables_fell_while_sales_grew`, reported).

## 7. One-off or habit?
Two lenses:
- **History:** compare each expense line as a % of sales with the company's own median.
  - One elevated year is a candidate one-off to normalise back: `one_off_spike`. Example: polymer
    packaging costs jump from 5% to 8% of sales when crude spikes.
  - Several elevated years mean it is the new normal; don't add it back: `persistent_increase`.
  - A sharp cut flatters margins temporarily: `cut_boosting_margin`. Example: an FMCG company that
    normally spends about 10% of sales on ads halves it to show profit growth, and the cost reappears
    later.
- **Peers:** compare like with like. Classification differs by company (e.g. packaging booked in raw
  material vs other expenses). A company spending 4% where peers spend 10-13% either has a different model
  or numbers that don't add up: `peer_outlier_low`.
- **Ind AS 116:** for retailers and QSRs, rent moved below EBITDA into depreciation and interest, so
  EBITDA margins before and after the change aren't comparable. Rebuild pre-Ind AS EBITDA before
  comparing ten years. Lease debt isn't real debt.

Only margin-boosting cuts and low peer outliers count against the score (`expense_flag_count`); spikes are
informational because they usually mean earnings are understated.

## 8. Growth, PEG and the earnings gap
- **PEG < 1 is attractive** (e.g. 30 P/E on 50% growth = 0.6). Rebound growth off a depressed base
  flatters PEG, so supply `forward.long_term_growth_pct` where that applies.
- **Earnings gap:** can the next three years' earnings growth accelerate versus the last three? A 10-15x
  P/E means the market is ignoring the company. When acceleration arrives, the market notices, reports get
  written and the re-rating follows (`earnings_gap_pp`).
- **Segment mix:** stagnant headline revenue can hide a shrinking drag segment. In the seed-company
  example, cotton fell from 55% to 11% of sales while the rest roughly doubled. Once the drag is small,
  headline growth shows through (`segments`).
- **New-product share** rising (e.g. 17% to 35% of sales from products launched in the last three years)
  signals R&D-led growth (`new_product_share_gain_pp`).

## 9. Cheap vs undervalued
A cheap stock is cheap for a reason: weak growth, management issues or a structural industry problem.
Buying only because it is cheap leads to value traps. First understand what the seller believes. It becomes
undervalued when you have a reasoned view that something is changing that the market isn't pricing.

The script's classification:
- **Cheap and undervalued:** valuation pillar >= 60%, a change identified, and the seller's concern is not
  structural or management-related.
- **Cheap but possibly a value trap:** cheap, but no change identified or the concern is structural.
- **Not cheap but undervalued:** a change identified and PEG <= 1, for non-cyclicals.
- **Not cheap:** none of the above.

Large caps are a weak hunting ground for an individual investor. Many smarter, better-resourced funds have
already looked, so cheapness there more likely has a reason. This is why the skill targets small and
microcaps.

## 10. Capital cycle and sentiment
From the book *Capital Returns*:
- When capital floods a sector, returns collapse.
- When capital leaves, marginal players shut down and survivors regain pricing power and earn
  super-normal profits.

Signals scored:
- the sector has underperformed the broad index for ~10 years;
- capital is exiting the sector;
- the stock is well off its 3-year high;
- the reason for selling is cyclical, temporary, or simple neglect (`neglected`: no concalls or presentations, nobody following the stock, as with Venus Remedies and Force Motors).

Pent-up replacement demand after several weak years (buses and ambulances after COVID) is a classic
trigger. Examples of setups he named: agri inputs after a poor monsoon, logistics after a decade of
underperformance, AC component makers after a rainy summer left channel inventory high.

## 11. Asymmetry and optionality
- **Upside** = forward PAT x a plausible exit P/E / market cap. If you think about downside, you must also
  think about upside; pure downside protection is a debt investor's job.
- **Downside floor** = the higher of:
  - an earnings floor: lower normalised earnings x the lower of history-minimum P/E and 8x;
  - a book floor: 0.7 x book.
- **Optionality:**
  - an out-licensable drug in phase 1, or a CBG business inside an ethanol company, scores best when the
    base business alone protects the current value: `optionality: protected`;
  - pure-play theme bets score less.
- **AI disruption check:** ask of every company whether AI can disrupt it. A seed company: unlikely.

## 12. Governance and kill switches
Hard **kill switches** cap the score at 20 and the verdict becomes AVOID:
- **revenue inflation** found or admitted (one promoter said half his reported growth was inflated);
- **auditor linked to fraud companies.** If an auditor signs one fraudulent balance sheet, what assurance
  is there for the others?
- **merchant banker regulatory action**, or heavy overlap between one banker's and one auditor's IPO
  clients (18 of 20 in his example);
- **plant claims contradicted on visit.** The promoter claimed 80-100% utilisation; a worker said they had
  been called in after a 15-day gap.
- **operator activity or fake volumes;**
- **promoter vanity spend of 15% or more of market cap** (a Rs 300 cr aircraft at a Rs 1,500 cr company). This only counts as a kill switch if the spend happened within the last 5 years (`promoter_vanity_spend_years_ago`). Older spend still scores 0 on the governance rule, because he bought Force Motors in 2022, years after its 2015-16 aircraft purchase.

Softer scored items:
- years listed;
- whether management delivered past guidance or its annual-report narrative;
- credible independent directors or investors (a respected investor joining the board gave him the
  conviction to buy);
- related-party and unrelated loss-making businesses (e.g. a car showroom inside a textile company);
- auditor quality.

No concalls or presentations is **not** penalised. Several of his biggest winners had none. Read ten years
of annual reports instead; even the cover themes tell the story of a company's arc.

## 13. What the script deliberately does not do
- **It doesn't fetch prices or financials.** Inputs come from you or the importer.
- **It doesn't judge the qualitative booleans.** `change_identified`, `seller_concern` and the governance
  flags are your research conclusions; the score is only as good as those calls.
- **It doesn't handle exits.** His selling lessons (don't sell too early in a structural re-rating; stop
  selling if supply is absorbed fast by credible buyers; penny-wise limit orders can cost a multibagger)
  are noted in SKILL.md, not scored.
- **It isn't investment advice.**
