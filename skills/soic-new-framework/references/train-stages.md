# Train A / B / C

The video's metaphor: a stock at rest stays at rest until a catalyst acts on it.
The stage describes how visible that catalyst is.

| Stage | Meaning | Evidence |
|---|---|---|
| `TRAIN_A` | Beautiful asset, no visible catalyst | No order, capex, product, management or policy event; no inflection |
| `TRAIN_B` | Catalyst visible, but not yet in the numbers | New capex/CWIP, order pipeline, approval, product launch, management change |
| `TRAIN_C` | Catalyst has arrived and the numbers are inflecting | J-curve conditions passing, revenue/PAT acceleration, margin expansion |

The video says to play within Train B and Train C for a three-year horizon, and
to avoid boarding Train C at 100 km/h when the incremental rate of change is
already gone. `[00:50:38]`–`[00:53:05]`

## Tool rules

These rules are derived by this repository:

```
TRAIN_C      J_count >= 4 and at least one catalyst tag
TRAIN_B      at least one catalyst tag and (capex signal or large_order/new_capex)
CANDIDATE    J_count >= 4 but no catalyst supplied
WATCH        J_count == 3, or a quality gate failed
TRAIN_A      J_count <= 2 and no catalyst
INSUFFICIENT coverage below 0.6 or a quality gate UNKNOWN
```

A catalyst tag is required for Train B/C. The Screener-only mode never guesses a
catalyst from financials.

## Entry discipline

The video also mentions:

- Wait for the first sign of inflection rather than predicting it.
- Giving up the first 15–20% of returns can improve the probability of success.
- Base formations can provide later entries.
- Do not lead with valuation; a high P/E can be cheap if the earnings band is
  changing, and a low P/E can be expensive if there is no growth.

Those are heuristics. They belong in the memo, not in the deterministic stage
classifier.
