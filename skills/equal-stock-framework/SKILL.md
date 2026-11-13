---
name: equal-stock-framework
description: Score an Indian listed stock with Manish Sonthalia's (Emkay) three-step growth-investing framework - E-QUAL management-quality score (integrity, capability, wealth distribution, investor communication, liquidity), earnings-growth potential (ROCE vs 15% cost of capital, profits doubling in 3-4 years, structural vs cyclical) and purchase-price discipline (PEG bands, 5-year cumulative-profit test, expected vs required return from the market-cap/quality risk-reward matrix, max buy price) - plus governance kill switches. A Python script gives auditable 0-100 scores and a BUY/WATCHLIST/AVOID/REJECT verdict. Use whenever the user wants to evaluate, screen, rank or compare stocks on management quality, corporate governance red flags (pledge, related-party deals, royalty, promoter salary, auditor fees), quality-growth-at-reasonable-price, PEG, or asks "should I buy X", "is X a multibagger", "score this company", "E-QUAL", or shares a Screener.in export or annual-report data - even if they don't name the framework.
---

# E-QUAL Stock Framework

A formula-based, verifiable way to pick stocks the way a quality-growth fund manager does:

1. **E-QUAL** – is management worth partnering with? (0–100; <50 = never invest)
2. **Earnings growth** – does the business earn above cost of capital and can profits double in 3–4 years? (0–100)
3. **Purchase-price discipline** – is the price low enough that growth turns into the required return? (0–100, PEG, max buy price)

Every point is produced by `scripts/score.py` from explicit inputs and the rules in `scripts/config.json`, so anyone can re-check a score line by line. The full rubric, the reasoning behind each rule, which numbers came straight from the source interview vs. were calibrated, and where to find each input are in `references/rubric.md` – read it when you need to explain a rule, defend a score, or locate data.

## Workflow

### 1. Gather inputs
Copy `assets/input_template.json` to a working file (one per company). Fill it from, in order of preference:
- files the user gave you (Screener.in export, annual report PDF, shareholding pattern, con-call transcript);
- web research (Screener.in, BSE/NSE filings, company IR page, credit-rating rationales). See the "Where to find each input" table in `references/rubric.md`.

Rules that keep the score honest:
- **Leave unknowns as `null`.** The script gives missing fields 50% neutral credit, marks them UNVERIFIED and lists them under "Data gaps". Guessing a number defeats the point of a verifiable score.
- Use percentages as plain numbers (18.5 means 18.5%), money in ₹ crore.
- `pat_cagr_fwd_pct` drives PEG and expected return, so it matters most. Prefer management guidance or consensus; if you estimate it yourself, say so in `growth.fwd_basis` and keep it conservative relative to history.
- `exit_pe` = 10-year median PE (Screener chart). If unavailable, leave null – the script then assumes no re-rating.
- `sector_type`: classify by what drives *this company's* earnings, not the sector label. `structural` = demand and pricing set by the company's franchise and Indian consumption (consumer brands, IT services, private banks, specialty franchises, and premium consumer franchises inside "cyclical" sectors – the fund manager treats Royal Enfield/Eicher this way). `cyclical` = profits set by global commodity prices or the capex cycle (steel, metals, sugar, shipping). `semi_cyclical` = genuinely in between (weather-driven ACs, lumpy projects, CV trucks, auto-components tied to OEM volumes). Cyclicals get "OUT OF FRAMEWORK".
- Historical PAT CAGR: normalise before entering. A 5-year window starting at the FY21 COVID trough, or a PAT figure with a one-off gain (demerger, stake sale), will flatter growth. Strip one-offs from `pat_ttm_cr` too (PE should be on clean earnings).
- Audit fee and revenue must be on the same basis (both standalone or both consolidated), or the fee-band check misfires.
- Banks/NBFCs: set `is_financial: true`; put **3-year average ROE** in `roce_3y_avg_pct` and leave `gross_debt_to_equity` null (the spread check then becomes ROE vs cost of equity). D/E isn't penalised, and the framework doesn't judge asset quality – say so.
- Record where each number came from in `sources`.

### 2. Run the scorer
```bash
python scripts/score.py company.json --out company_report.md --json company_result.json
python scripts/score.py a.json b.json c.json --compare --out comparison.md   # rank several
```
What-if runs without editing the file: `--set growth.pat_cagr_fwd_pct=20 --set sector_type=structural`. The report always includes a forward-growth sensitivity table (g − 4, g, g + 4) because the verdict usually hinges on that one input; when the user or a fund manager has a different growth view from consensus, show both runs.
Config overrides (e.g., new AMFI cut-offs, different hurdles): `--config my_config.json`. When AMFI publishes a new semi-annual list, update `cap_tiers` in config.json.

### 3. Report to the user
Lead with the verdict and the four numbers, then what drove them. A good summary includes:
- Verdict + one-line reason (e.g., "WATCHLIST – PEG 1.9 but expected 20.6% < required 22%").
- E-QUAL / Growth / Price / Composite scores and quality grade.
- Required vs expected return, PEG, and **max buy price**.
- Kill switches, warnings, and data gaps – data gaps first if the verdict is PROVISIONAL or kill-switch inputs are missing.
- Offer the full rule-by-rule report file so they can audit each point.

Kill switches are mechanical. If one fires for a reason that looks benign (e.g., a large acquisition from the parent group at a fair price, paid in cash), keep the REJECT but explain the context so the user can judge.

Composite (40% E-QUAL / 30% growth / 30% price) is for ranking among stocks that pass the gates; never present a high composite as a reason to override a REJECT.

End with a short note that this is a framework output, not investment advice, and that the user should verify inputs before acting.

## How the verdict is decided
1. Any kill switch (pledge ≥70%, ≥2 debt restructurings, net D/E >2.5, acquisition >50% of net worth, unrelated investments >25% of net worth, zero investor communication) → **REJECT**
2. E-QUAL < 50 → **REJECT**; ROCE < 15% → **REJECT** (value trap)
3. Cyclical → **OUT OF FRAMEWORK**
4. Forward PAT CAGR < 18% → **PASS** (profits won't double in ~4 years)
5. PEG > 3 → **AVOID**
6. PEG ≤ 2 and expected return ≥ required return → **BUY** (PEG ≤ 1 and next-5y cumulative profit ≥ market cap → **BUY – MULTIBAGGER SETUP**)
7. Otherwise → **WATCHLIST** with a max buy price

Required return = market-cap base (Mega 13%, LC2 16%, Mid 19%, SC1 22%, SC2 25%) + quality premium (E-QUAL ≥85: +0, 70–85: +2, 60–70: +5, 50–60: +10).
Expected return = `(1+g) × (exit PE / PE)^(1/5) − 1 + dividend yield`.

## Exit rules (for holdings)
Re-run the score each quarter/annual report. Sell only if growth sustainably drops below 18%, governance breaks (re-scored E-QUAL falls or a kill switch fires), or PEG > 3 / euphoria. Don't sell a structural compounder just because it has risen a lot, and don't mistake a temporary raw-material squeeze for lost pricing power.

## Files
- `scripts/score.py` – scorer (stdlib Python 3, no installs)
- `scripts/config.json` – every weight, band, hurdle and kill switch
- `assets/input_template.json` – blank input; `assets/example_input.json` – fictional worked example
- `references/rubric.md` – full rubric, provenance [T]/[C], verdict logic, data-source map
