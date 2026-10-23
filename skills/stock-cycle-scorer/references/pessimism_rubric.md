# Pessimism Rate of Change (Score 1)

Score 1 asks: **how much bad news is already in the price, and is the business starting
to turn?**

```
Score 1 = 0.40 x Pain + 0.45 x Turning + 0.15 x Earnings delta
```

`combine` is a weighted mean of available signals, renormalised. Coverage is the share of
leaf weight that had data.

## Pain (0.40)

| Signal | Weight | Rule |
|---|---|---|
| valuation | 0.30 | First of P/B, EV/EBITDA, P/E with 3+ history points. Percentile = (below + 0.5 x equal) / n x 100. Score = 100 - percentile |
| drawdown | 0.20 | `dd = 1 - price / high_3y`; `lin(dd, 0, 0.60)` |
| earnings stress | 0.20 | Part A (0.6): `lin((cycle margin - TTM margin) / cycle margin, 0, 0.40)`. Part B (0.4): share of the last up-to-8 quarters with EBITDA below the same quarter a year earlier |
| neglect | 0.15 | Mean of available parts: call length `lin(min, 90, 30)`; analyst questions `lin(n, 20, 5)`; institutional change `lin(chg, +3, -3)` |
| sector breadth | 0.15 | Needs 3+ peers. Share at least 40% below their 3y high; `lin(share, 0, 0.60)` |

**Neglect fallback.** Use the most recent of the last 3 calls with length/question data if
it is at most 200 days old. Missing call data is not "maximum neglect". Ignore a falling
FII+DII when the price is at least 50% above its 52-week low: institutions selling into
strength (or being diluted by an issue) is not neglect.

**Earnings stress.** Cycle-average margin is the mean annual EBITDA/revenue over the last
10 years (3+ years required), else the mean quarterly margin (8+ quarters). TTM is the last
4 quarters.

## Turning (0.45)

| Signal | Weight | Fires when |
|---|---|---|
| promoter | 0.30 | Net open-market promoter buys minus sells over 183 days is positive (80, or 100 if holding also rose). Holding +0.25pp or more gives 60. Net selling gives 0 and marks *promoter selling* |
| sentiment gap | 0.30 | Last 3 calls with tone and skepticism. `0.5 lin(t,1,5) + 0.3 lin(sk,1,5) + 0.2 lin(delta,0,2)`, times credibility (1 miss 0.75, 2+ misses 0.5). Fires if tone >= 4, skepticism >= 3, misses < 2 |
| margin inflection | 0.25 | Last up-to-8 quarters. Latest quarter is the trough -> 0. Previous quarter -> 50 if rise >= 1pp else 25. Older trough -> 100 if the last two moves are non-negative else 40; halved if rise < 1pp. Fires at >= 50 |
| market share | 0.15 | Any of the last 2 calls claims share gains -> 100. Present but false -> 0 |

**Promoter N/A.** Drop and re-weight the signal when promoter holding is zero for the last
3 quarters or `no_promoter` is set, and there are no promoter trades. This prevents
professionally managed companies from being scored as "no buying".

**Market skepticism.** If the last 2 calls have `prior_guidance_met` with no `false`, the
drawdown is at least 30%, and skepticism is below 3, set skepticism to 3. The price can be
skeptical even when analysts are friendly.

**Credibility.** Skepticism is only an "anchoring" signal if management delivers. Two
guidance misses halve the sentiment score and block the fire.

**Margin inflection needs a real trough.** If EBITDA-based and the trough is above 0.9x
the cycle-average margin, cap at 30. A steady uptrend is not a turn from pain.

## Earnings delta (0.15)

If TTM EBITDA <= 0 and the cycle average is positive -> 100. Otherwise
`potential = max(0, (cycle average - TTM) / TTM)` and `lin(potential, 0, 1.0)`.
Multiply by 0.5 when margin-inflection has data but has not fired. Without this, a deeper
margin collapse raises the score while margins are still falling.

## Stage classifier (checked in order)

Definitions: `vp` = valuation percentile, `dd` = drawdown, `off_low = price / 52w low - 1`,
`n_fired` = number of turning signals that fired.

Optimism signals: promoter selling; QIP/OFS in the last 365 days; aggressive guidance on
the latest call; latest call at least 90 minutes.

Pivot lens: segment-shift score >= 60 and capability >= 3/5; fallback when segment data is
missing is Score 2 >= 60 with coverage >= 0.5.

Promoter exit: promoter holding down at least 5pp over two quarters.

| Stage | Rule |
|---|---|
| `PEAK_OPTIMISM` | (`vp` >= 90 and no pivot lens) or (`vp` >= 80 and 2+ optimism signals) |
| `CYCLE_CONFIRMED` | TTM EBITDA growth >= 15%, `DEMAND_LED`, `n_fired` >= 1, 40 <= `vp` < 80 (or vp unknown) |
| `EARLY_RECOVERY` | `n_fired` >= 2, `vp` <= 50 (or unknown), (`dd` >= 25% or `off_low` >= 30%), no promoter exit |
| `PEAK_PESSIMISM` | `vp` <= 25 (or unknown), `dd` >= 40%, `n_fired` <= 1 |
| `DECLINE` | TTM EBITDA growth < 0 and `n_fired` <= 1 |
| `MIXED` | Anything else; the output must name the blocking rule |

Low confidence when `vp` or `dd` is missing, or Score 1 coverage is below 50%.

## Vetoes and red flags

**Score 1 vetoes (cap at 30):**
- interest coverage `(TTM EBITDA - depreciation) / interest` < 2 with debt rising and
  debt/equity >= 0.5 (or equity unknown)
- operating cash flow negative 3 straight years
- promoter pledge > 25% or up > 2pp over two quarters
- any governance flag
- `lost_share_in_downturn`

**Red flags (shown, not capping):**
- interest coverage < 2 when it does not qualify as a veto
- margin up >= 4pp in one quarter (check inventory gains)
- acquisition closed within 455 days and on or before the latest reported quarter, with
  positive TTM EBITDA growth
- promoter holding down >= 5pp over two quarters

**Coverage veto needs leverage.** Apollo's near-zero EBIT came from depreciation on a
balance sheet with debt at 0.15x equity: an earnings problem, not solvency. The veto
requires rising debt and meaningful leverage (or unknown equity).
