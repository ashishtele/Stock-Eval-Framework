# Stock Eval Framework

Turn investor talks into an explicit, testable stock-evaluation rubric — then
apply that rubric to any stock with every number and verdict traceable to a source.

The unit of value is not "an AI that picks stocks." It is a **framework**:
a set of criteria with thresholds, verbatim evidence, and timestamps, extracted
from one investor's own words, plus the machinery to apply and audit it.

## Why this exists

Long-form interviews contain the reasoning that never makes it into books or
screeners: what an investor refuses to buy, which number they distrust, what
makes them sell. Those judgments are usually lost because they live in audio.
This repo converts them into checklists that a human or an agent can re-run
consistently, and that show their work.

## Layout

```
skills/
  fetch-transcript/        URL -> normalized, provenance-stamped transcript
  transcript-to-framework/ transcript -> framework.json + evidence (+ gate)
  apply-framework/         framework + financial data -> evaluation.json
  stock-memo/              evaluation.json -> written memo
  frameworks/
    _template/             copy this to start a new framework
    <creator>-<slug>/      one skill per framework, self-contained
schema/
  framework.schema.json    structure every framework must satisfy
  evaluation.schema.json   structure every evaluation must satisfy
transcripts/<creator>/     raw, immutable input (privacy: keep repo private)
evals/<framework-id>/      recorded applications used to validate a framework
scripts/fetch_transcript.py
```

## Quickstart

1. Fetch a transcript (needs `pip install -r requirements.txt`):

   ```
   python scripts/fetch_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

   It writes `transcripts/<channel>/<date>-<slug>.md` plus a `.segments.json`
   sidecar with per-cue timestamps. Fetch from your own machine: YouTube blocks
   datacenter IPs, so do not fetch at request time from a deployed server.

2. Extract a framework. Invoke the `transcript-to-framework` skill with the
   transcript path. It creates `skills/frameworks/<creator>-<slug>/`.

3. Validate before believing it. Apply the framework to stocks the creator
   actually discussed, record results under `evals/`, and iterate until the
   verdicts match what the creator said. A framework stays `status: draft`
   until this passes.

4. Evaluate a new stock: `apply-framework`, then `stock-memo`.

## Non-negotiable principles

1. **Evidence or it does not exist.** Every criterion carries a verbatim quote
   and a timestamp. No quote, no criterion.
2. **Testable or it is a heuristic.** Unmeasurable ideas go to `heuristics.md`,
   never into the checklist.
3. **UNKNOWN is a valid verdict.** A missing input is reported, never estimated.
4. **Screens are code; judgments are models.** Mechanical checks are
   deterministic. Qualitative ones return a typed verdict plus confidence.
5. **Do not invent what the creator did not say.** No composite score unless the
   framework defines weights. Contradictions are recorded as tensions, not
   smoothed over.

## Installing into another project

This repo follows the `skills/<name>/SKILL.md` layout, so any agent that supports
skill installation (including `skills-lock.json`-style tooling) can pull an
individual framework or procedure from it.

## Disclaimer

This is decision support and a record of how a third party reasons. It is not
investment advice, it does not produce price targets, and it does not place
trades. Frameworks describe what a creator *said* and are unvalidated until the
evals in this repo say otherwise.

Transcripts are third-party copyrighted content. Keep this repository private
unless you replace raw transcripts with derived notes and short quotations.
