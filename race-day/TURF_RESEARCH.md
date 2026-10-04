# Turf optimization and cold-runner validation — 2026-10-04

This change collects prospective research observations. Live banker, legs,
cold selection, website and Telegram selections are not replaced by these
exploratory outputs. `hkjc_shadow.py` writes `race_XX_turf_research.json` at
the existing freeze, using only in-memory quotes and previously archived
results. There are no additional network requests at the deadline.

## Turf draw candidate

The pre-race racecard context now preserves declared distance and rail.
Only same-day, same-venue, same-rail turf races of 1200–1800m are pooled.
Straight 1000m, dirt and other distances are inapplicable. Unknown rail or
distance cannot produce a substitution. These pooled distances are an
exploratory hypothesis, not a validated exchangeability assumption.

Use at least three earlier races with results actually received by the
current freeze. Compute observed top-three inner-third draws minus a
Plackett–Luce expectation proxy using each previous frozen WIN quote.
The proxy is descriptive, not calibrated probability. If excess >=2 and
the current four legs contain fewer than two inner-third draws, retain
the banker and substitute the lowest-F outside leg with the highest-F
unselected inside horse. Archive the proposed legs and each evidence
race with its result receipt. The frozen actual legs remain unchanged.

The thresholds were explored after seeing Oct4. The earlier replay pooling
1200–1800m without a rail gate would change R8, adding horse10 for horse4;
Oct4 turf banker-QP-hit races would rise from2/6 to3/6 and placed legs from
9/24 to10/24. Oct1 total QP hits remain6/10. Neither day is an untouched
validation of this new draw rule. The implementation adds a stricter
declared-rail requirement; old contexts missing that field are unavailable,
not silently filled with post-race metadata.

## Cold divergence observation

The independent signal follows the previous Oct1 hypothesis: endpoint
WIN>10, both single WIN and PLA drifting, while QIN and QPL with the
endpoint favorite both shorten >=15%. No WIN<=30 ceiling and no forced
single horse. All candidates are archived; none automatically replaces
the fourth leg. Capped pair prices >=999 are excluded.

Require complete matching fields/pools and advertised post-time, valid
source timestamps, endpoint received by T−3:10 and source age <=120sec.
The baseline is closest to T−30 in T−32..T−25, with source age <=180sec.
This conservative observer rejects an old advertised-clock baseline after
a delay. It does not change the existing live cold selector's separate
post-time revision handling. A missing observer baseline does not mean
the main system failed.

## New-day cold checks

Oct4 live cold v2 selected six turf runners. Top-two and top-three hits
are both1/6: R4 horse12 (21x pre-freeze WIN), confirmed-prior-form branch.
Market-second branch0/4; late-entry branch0/1. These are tiny samples,
so disabling a branch based solely on this day would be overfitting.

All six turf races have49 runners with pre-freeze WIN>10; five placed
and only one won. R2/R6/R7 had no qualifying cold runner in the top three;
R4/R8/R10 did. The selector found one of those three races. Keep both
denominators visible:1/6 operationally,1/3 retrospectively where a >10
placed horse existed. The latter condition cannot be known before racing.

The divergence observer has four strict-clock eligible turf races: R2,
R4,R7,R8. Its only candidate R2 horse8 (71x) did not place:0/1 candidates.
R6/R10 are unavailable for its strict baseline clock, not no-signal races.
As a clearly separate sensitivity check, retaining same-race old-clock
baselines also identifies R10 horses5 (19x) and11 (30x); neither placed,
giving0/3 turf candidates. This is not evidence that the Oct1 30% win
rate generalizes. No threshold was tuned to rescue this day.

R8 placed cold horses10 and11 were missed; R10 placed cold horse7 was
missed. Record their component scores prospectively and compare absolute
support and same-course form in future development folds. Relative rank
always has a winner, even in a weak field: research an abstention gate
using separate development and validation days before adopting it.

## Acceptance and validation

Use original published picks as the control. Report banker placement,
leg placement, distinct Q/QP-hit races, candidate count, missing-data rate,
and returns only with actual official dividends and explicit stakes.
Separate ST straight/turning and HV, distance and rail; avoid fitting on
actual current-race running positions. Fit gate/weights only on development
days, freeze them, then test forward on separate days. The Oct4 draw rule
cannot call Oct4 its holdout. A shadow observation must never overwrite
an already published tip after its deadline.

Tests cover late/stale/future source quotes, incomplete pools, capped
prices, changed advertised clocks, context parsing, mud/straight exclusion,
future result receipts, duplicate evidence, rail differences and unchanged
bankers/live inputs. Existing cold and freeze integration replays remain
unchanged.

Sources: [Oct4 archived inputs and actual tips](https://github.com/Ljackylau/hkjc-scraper/tree/race-day-data/race-day-data/2026-10-04),
[Oct4 official results](https://racing.hkjc.com/en-us/local/information/localresults?racedate=2026/10/04&Racecourse=ST&RaceNo=4).
