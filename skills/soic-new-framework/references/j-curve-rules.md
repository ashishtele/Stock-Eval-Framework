# J-curve rules

These are the five conditions the video associates with a “Potential J-Curve”
scan. They are **creator-stated thresholds**, but the video is an auto-generated
transcript; verify any number against the video before treating it as exact.

| # | Condition | Threshold | Video reference |
|---|---|---|---|
| J1 | Sales growth | `>= 20%` | `[01:28:49]` |
| J2 | PAT growth | `>= 30%` | `[01:28:49]` |
| J3 | Operating margin expansion | `>= 10%` year on year | `[01:29:24]` |
| J4 | Return since latest result | `>= 5%` (some use 3%) | `[01:29:24]` |
| J5 | Price above 30-week EMA | close `>` EMA | `[01:29:24]` |

## J1 and J2

Use the latest quarter versus the same quarter last year. This avoids seasonality.
If quarterly data is unavailable, fall back to the latest annual period and label
the basis. Do not annualise a single quarter.

## J3

The video says operating margins are “10% higher than last year's operating
margins.” That is a **relative** change: `opm_t / opm_t-1 - 1 >= 10%`.

Relative expansion is unstable when the prior OPM is near zero or negative. The
tool therefore also computes percentage-point change and uses a `>= 1.0 pp`
fallback when relative expansion is undefined. The output says which basis was
used.

## J4

Needs a result date and price history. If `--result-date` is not supplied, the
tool infers quarter-end + 45 days and marks the result as inferred. That is a
convenience; a real evaluation should use the actual announcement date.

## J5

Needs at least 30 weekly closes. The tool groups daily adjusted closes by ISO
week, takes the last close in each week, seeds the EMA with the first 30-week
SMA, and then applies the standard EMA smoothing.

## What a J-count means

`J_count` is the number of PASS conditions. `UNKNOWN` is not a PASS and not a
FAIL. A stock with `J=3/5` and two unknowns is not the same as a stock with
`J=3/5` and two fails. Always report `j_known` and coverage.

## Not part of the J-curve

The video's wider framework also uses themes, catalysts, management, relative
strength, and the Train A/B/C stage. Do not fold those into the J-count. They are
separate gates in `train-stages.md` and `catalyst-taxonomy.md`.
