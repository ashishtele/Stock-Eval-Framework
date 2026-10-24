# Entry discipline and base formation

The video separates **what to buy** from **when to buy** `[00:54:18]`–`[00:59:30]`.

## Base formation

A moving stock often pauses and builds a base. During that base, old shareholders
sell, management may monetise a small stake, and the price gives multiple entry
points. A breakout from a base can be a later entry if the train is still moving.

Do not treat every pause as a base. Record:

- base start and end dates
- support and resistance
- breakout level
- volume on breakout versus the base
- whether the longer-term trend is still up

The tool does not automatically detect bases. Base formation is subjective and
needs a chart. The context file can record the manual observation.

## Entry rules from the talk

- Do not try to predict the exact bottom.
- Wait for the first sign of inflection in the numbers.
- It is acceptable to give up the first 15–20% of returns if the probability of
  success improves.
- Do not board Train C at 100 km/h.
- A later base breakout can be a better entry than chasing the first move.
- Define the time horizon before entering.

## Context fields

```
base.start, base.end, base.breakout, base.volume_multiple
entry.first_inflection, entry.return_since, entry.extended, entry.plan
```

`entry.extended = true` is a warning, not an automatic rejection. The J-curve and
quality gates still decide the stage.
