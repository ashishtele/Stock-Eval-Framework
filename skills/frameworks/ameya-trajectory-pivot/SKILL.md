---
name: ameya-trajectory-pivot
description: >
  Apply Ameya Deosthali's Value Equity Trajectory Pivot framework to a company:
  a different product line, a prize large enough to change the earnings
  trajectory, management depth, capex ahead of revenue, verifiable capability
  filings, mix shift, and margin delta. Use when a company claims to be pivoting
  into a new business (aerospace, CDMO, specialty chemicals, defense, semis) or
  when the user asks whether a capex-heavy story is real. Capability-led, not
  cyclical.
---

# Ameya Deosthali — Value Equity Trajectory Pivot

Records one investor's framework for companies changing what they do, not just
how much they do. `framework.json` is the only source of truth.

- Version: `0.1.0` (draft)
- Status: `unvalidated`
- Source: Kushal Lodha #393, 2026-10-13 (auto-captions)

## How it is meant to be used

1. Apply it with `apply-framework`, passing `ameya-trajectory-pivot` and a
   ticker.
2. Management depth is disqualifying. If the track record is absent, stop; the
   size of the capex does not compensate.
3. Verify the capability outside the investor presentation: US FDA DMF filings
   for pharma, AS 9100 / NADCAP for aerospace, segment disclosure and customer
   qualifications elsewhere.
4. A pivot with no capex, no mix shift, or no verifiable certification across
   two to four quarters is an announcement, not a pivot.
5. Report `UNKNOWN` where segment-level data is unavailable; most Indian
   companies disclose too little for every row.

## Case studies the creator used

- Laurus Labs: ARV to CDMO, capex ahead of revenue, stock halved, then 5x.
- Sansera Engineering: auto ancillary to aerospace/defense/semiconductor
  (transcript auto-captions render the name as "Sasera"/"Sesea").
- Dynamatic Technologies: aerospace capability built since 2006, Tier 1 Airbus
  supplier.

## What this framework is not

- Not a momentum or capex-announcement screen; the anti-hype check is
  `built-over-years`.
- No explicit sell rule was stated, so none is recorded.
- Not validated. No evals yet.
