# Methodology and limits

## What is creator-stated

The five J-curve conditions come from the video's “Potential J-Curve” scan
`[01:28:49]`–`[01:29:24]`. The three-year horizon and the Train A/B/C metaphor
are also stated `[00:50:38]`–`[00:53:40]`.

## What is derived

The quality gates, the coverage formula, the stage thresholds, and the decision
to use latest-quarter YoY growth are this repository's choices. They are not
Ishmohit's words. They exist to make the screen deterministic and to prevent a
high-growth, low-quality name from being presented as a candidate.

## Why there is no single score

The video is a multi-dimensional process: theme, catalyst, stage, quality,
valuation, and tracking. It does not provide weights. A blended 0–100 score would
hide the evidence and imply precision that does not exist. The primary output is
the row table plus `J_count`, quality status, coverage, and stage.

## Point-in-time rules

- Use a dated Screener snapshot. The JSON's `as_of` is the snapshot date.
- Use price points with `date <= as_of`.
- Use quarterly/annual periods with period end `<= as_of`.
- Do not use a later concall, announcement or management interview.
- The result date must be the actual announcement date when known; otherwise the
  inferred quarter-end + 45 days is labelled.

## Coverage

`coverage = (known J conditions + known quality gates) / 9`.

A missing price history leaves J4 and J5 unknown, so coverage drops to 78%.
Below 60% the tool returns `INSUFFICIENT`. Coverage is not a quality score; it is
a statement about how much of the framework could be evaluated.

## What Screener cannot do

Screener does not contain:

- order book or order announcements
- product launches or customer wins
- management quality or board changes
- concall language or guidance
- theme classification
- segment margins
- peer relative strength

Those require exchange filings, concalls, interviews, and a separate peer/price
dataset. The skill must say so rather than infer them.

## Validation plan

Use the video's examples as eval cases only after verifying the numbers:

- TVS Motors — new product / EV inflection
- Welspun Corp — large order / Train B to C
- CG Power — new management
- Entero Healthcare — new business model, Train B
- Redington — margin target / AI-memory proxy
- Lumax — new product content, earnings surprise
- Deep Industries — order catalyst / concall sentiment

Add negative controls:

- a large-cap bank or insurer (quality gates do not fit)
- a mature paint company facing new competition
- PI Industries after Chinese competition entered

A framework version is not validated until these cases are replayed and the
expected stage/label is reproduced, including the negative cases.
