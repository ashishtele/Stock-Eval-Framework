# Trajectory Pivot (Score 2)

Score 2 asks: **is this company becoming a different business, and is the market still
pricing the old one?** It is a credibility check more than a timing signal.

| Signal | Weight | Rule |
|---|---|---|
| segment shift | 0.20 | Group segments by period; window = last 12 quarters or last 5 years. Mix = `0.7 lin(change in share pp, 0, 20) + 0.3 lin(latest share %, 0, 40)`. Margin diff = `lin(new margin / base margin, 1.0, 1.8)`. Signal = `0.6 mix + 0.4 margin diff`, renormalised if one is missing |
| pivot size ("orbit") | 0.20 | Annualise current new/base revenue and EBIT. `expected_new = new_ebit + 0.5 x (target revenue x target margin - new_ebit)`. `orbit = (base_ebit + expected_new) / (base_ebit + new_ebit)`. `lin(orbit, 1, 3)` |
| capability | 0.20 | `rubric/5`, minus 0.10 if bought or 0.05 if mixed |
| management | 0.20 | `rubric/5` |
| mispricing | 0.10 | Company multiple / pure-play multiple; `lin(ratio, 1.0, 0.4)` |
| tailwind | 0.10 | `rubric/5` |
| build phase | 0.10 | Needs 5+ years of annual capex and revenue. `ratio = max capex/sales of the last 4 years / mean of the 3 years before`. `lin(ratio, 1, 2)`; full credit only if capability >= 3, otherwise x0.5 |

The weights above sum to 1.10 because the spec assigns them that way. The engine
renormalises the weighted mean, and coverage is measured against the full 1.10, so a
complete input set reports 100% coverage.

If segment EBIT is missing, the company TTM EBITDA margin is applied to both new and base
revenue and the result is flagged. This understates big pivots when segment margins are
undisclosed.

**Management gate.** A management rubric below 2/5 caps Score 2 at 40.

**Score 2 vetoes (cap at 30):** pledge and governance only. A pivot's build phase
legitimately raises debt, so debt is not a Score 2 veto.

**Judgment share** = weight of capability + management + tailwind among available signals.
Above 60%, warn that Score 2 rests on judgment; one rubric point moves it by roughly
`20 x 0.20 / available weight` points.

## Concall rubric

| Field | Scale |
|---|---|
| `mgmt_tone` | 1 defensive (guiding down, cutting capex); 2 cautious (wait-and-watch, flat/no guidance); 3 balanced; 4 constructive (bottom is in, positive guidance, share gains, restarting capex); 5 bullish with specifics (raised quantified guidance, order wins, promoters buying, capacity committed) |
| `analyst_skepticism` | 1 enthusiastic; 2 mostly accepting (modelling questions); 3 probing (asks for evidence); 4 skeptical (repeatedly challenges guidance, anchored to the last downturn); 5 disbelieving or hostile |
| `prior_guidance_met` | Did reported results deliver the previous call's quantified guidance? Within ~10% of the guided figure (or low end) = true; bigger shortfall = false; not checkable = omit |
| `market_share_gain_claimed` | Management says it is gaining share or weaker players are exiting |
| `aggressive_guidance` | Guidance stretched for the cycle stage (very high multi-year targets, big capacity announcements in a boom) |

Estimate `duration_min` from word count at ~150 words/minute if needed, and say so.
`analyst_questions` counts distinct participants, not questions.

## Pivot rubric

| Field | Scale |
|---|---|
| `capability_proof` | 0 claims only; 1 capex announced or trial orders; 2 certifications or regulatory filings; 3 named customers, qualified supplier, recurring revenue; 4 scaled (material share, multiple customers, higher tier); 5 hard to replicate (top tier for years, sole/primary supplier) |
| `management_track_record` | Check guidance from 4-8 quarters back against delivery, ROCE through the last downturn, and past acquisitions/expansions. 0 repeated misses or governance issues; 3 generally delivers; 4 consistent delivery and invested ahead of the cycle; 5 multi-cycle record, visible promoter passion |
| `external_tailwind` | 0 shrinking globally; 3 clear growth in global players' guidance; 4 multi-year growth with capacity shortages; 5 structural shortage with customers seeking new suppliers |
| `capability_built_vs_bought` | `built` / `bought` / `mixed` |

Targets come from management guidance and must record `target_source`. If none exists, a
conservative estimate is allowed but must be labelled `Claude estimate`. The scorer flags
an estimate and it should not be used as a hard verdict input.

**Pivot lens.** Keyed to proof of pivot, not total Score 2: segment-shift >= 60 and
capability >= 3. A re-rated pivot loses its mispricing and build-phase points; keying the
lens on total Score 2 switched it off and called Laurus "peak optimism".
