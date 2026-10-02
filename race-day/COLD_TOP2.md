# 留意冷馬：頭二優先方法（2026-10-02）

Each eligible race selects at most one horse whose WIN quote at T−3:10 is
greater than 10. The target is finish 1 or 2. The frozen exploratory study
selected 14/30 on Sep23, Sep27 and Oct1, retaining the original ten hits.
This is a repeatedly explored retrospective result, not a calibrated live
probability or an untouched validation set.

The selector is `cold_policy_v2.py` plus `market_math.py`, copied unchanged
from the study. The live journal adapter is `cold_top2_live.py`. Priority:

1. New qualifying market entry between T−5 and T−3:10. Conservative QIN
   residual growth exceeds 10%, conservative growth and FCT direction ranks
   are at least 75%, at least two QIN/QPL pairs shorten by 15%, and at least
   five uncapped FCT direction pairs are comparable. Choose the largest
   original-B score among eligible entries.
2. Jockey strength at least .30; latest valid earlier trial in the preceding
   30 calendar days finishes in the first three, with no failed/required
   result; today's venue and surface equal the latest earlier race. Choose
   the highest mean of the best three Q growth, previous finish, jockey
   strength and trial-score ranks. The jockey prior stays the frozen
   24-profile 2025/26 sample: (top-three finishes + 50 × sample rate) /
   (rides + 50). Late rider changes use the pre-cutoff live roster.
3. Keep original B's candidate if its last-finish score is at least .60,
   Q residual growth is positive, and either its previous finish is first/
   second or its QIN quote with the favorite shortens. B = (Q-growth rank +
   FCT-first growth rank + 2 × last-finish rank) / 4.
4. Otherwise maximize the mean rank of favorite QIN quote shortening,
   conservative FCT second-position support, and FCT second-position growth
   with the five most favored partners.

Ranks are among cold runners; missing optional terms keep the neutral rank
.5, and equal scores prefer the lowest horse number. Capped quotes use the
original conservative interval arithmetic. A cold horse is retained when
it also happens to be the main banker.

## Race-day operation

Run `Race Day Runner (Independent)` once on the race day using **main**,
**Run**, the correct date/venue and the official complete post-time list.
Start at least 45 minutes before race 1. The second-half worker starts
about 90 minutes before its first race. HKJC post-time revisions observed
before freezing update the deadline. The banker/leg method stays separate
from the cold-horse selector.

History and trials load in the background before the deadline. Fresh WP,
QIN/QPL and directed FCT are collected locally in the same worker. The FCT
task does not wait for another worker's commit. Last-six-minute sampling
targets two seconds. Both quote publication and actual receipt must precede
the cut. The long baseline is the closest valid receipt to T−30 within
T−32..T−25. A prior-clock baseline is allowed for an observed post-time
revision; the endpoint must match the revised advertised clock.

At T−3:10, preserve the candidate, reason, WIN quote and source clocks, and
request publication immediately without waiting for Telegram's T−3 send.
`hkjc-*/status.json` embeds frozen tips, so the page can show cold tips even
when Horse103 or the banker is unavailable. Today's page reads cache-busted
small summaries directly from the data branch and does not wait for the
former 55-second SHA cache. Polling targets two seconds near T−3 and pauses
while the tab is hidden.

Missing required pools, incomplete coverage, unfinished history or late
preparation give an unavailable reason. Missing optional T−5 or long FCT
comparisons are marked partial; missing T−5 cannot qualify the late-entry
branch. No after-cut quote replaces a missing endpoint. GitHub, HKJC,
network, browser scheduling and runner availability still affect actual
display time. T−3 is a target, not a guaranteed delivery time or a promise
of one candidate in every race.

`race_XX_cold_history.json` stores prepared history and `race_XX_cold_v2.json`
stores the frozen calculation and input receipts. Past archives retain
the genuine method recorded on each date.

## Verification

Python tests check all 30 frozen candidates and replay all 30 through the
live journal adapter, including observed post-time revisions, missing/late
sources and publication before notification waiting. The compressed fixture
contains public numerical odds/history facts and expected candidates, with
no current-race outcome input. Node tests check receipt validation, direct
collector display, retention of a cold banker, and protection from legacy
trainer reconstruction. CI checks page syntax and legacy receipt/group
behavior. These are simulations; live availability and actual screen
visibility must still be observed on a new race day.
