# Concall reading and the “Congrats Index”

The video says to become a student of quarterly results and concalls
`[01:20:38]`. The “Congrats Index” is a tongue-in-cheek sentiment heuristic:
count how many times analysts say “congrats” on the call. The video claims it was
correlated with two- to three-month performance `[01:21:14]`.

Treat this as a **weak, noisy signal**, not a factor model.

## What to read

- management guidance: raised, maintained, cut
- order inflow and order-book commentary
- capacity commissioning dates
- margin drivers and one-offs
- working-capital and receivable commentary
- management tone on competition and pricing
- whether the numbers matched the previous guidance

## Context fields

```
concall.date
concall.congrats_count
concall.guidance: raised | maintained | cut | unknown
concall.source
```

A high “congrats” count with cut guidance is not supportive. A low count with
raised guidance can still be constructive. Read the transcript.

## Tool support

The tool only records the manual context. It does not transcribe or score
concalls. Do not infer sentiment from price action.
