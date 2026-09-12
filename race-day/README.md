# Race Day Runner — independent copy

Original `dragon/`, `dragon-webapp/`, workflows and local Horse103 file are untouched.

## Use

1. Open GitHub Actions → **Race Day Runner (Independent)**.
2. Today choose date `2026-09-13`, mode **Preflight**, Run workflow.
3. On race day start **Run** around 11:45 Hong Kong time (before first-race T−60). Starting the job does not imply that data collection is ready: check that early job is running before 12:00.
4. Open `race-day/index.html` on GitHub Pages. Select Dragon or Horse103. GitHub may take time to publish this initial page.
5. To stop both, cancel the entire workflow run, not one individual job. Closing a browser does not stop it. Avoid clicking Run twice; a second run queues rather than replacing the active run.

## Isolation and costs

Code additions only. Data goes to branch **race-day-data**, under date/early or date/late. No original results are written. Use standard Ubuntu runners. Public-repository runner minutes are free under GitHub's current policy; only the small schedule artifact is uploaded, retained for one day. Raw Dragon data remains on the separate branch, so repeated meetings accumulate repository storage. No LLM API or paid worker is used.

Three runtime jobs: early, a small waiting job releasing late, and late. Each collector job is capped at 330 minutes. Late starts 90 minutes before the first late-phase race, leaving 30 minutes before T−60 for setup. Queueing/network/source service can still fail. Check job status before its collection window. Only Run on the chosen HK race date. Running before race day is not scheduling.

## Timing and data fidelity

Dragon copy preserves the current source's **FCT-only first-available-baseline** chart and >30% threshold. In this copy pages open at T−60 to reduce CPU/network use. It preserves T−10 and T−3 samples and continues to post+15 minutes. If started late, its baseline is late; it is not a strict T−60 backtest. Data are saved every minute to a separate data branch; source timestamps and stale-data indicators remain visible.

Horse103 starts requesting at scheduled T−3, accepts the first ready locked/started response received no later than 90 seconds after that target, and preserves the response, receipt delay, valueIndex, and Q/QP records whose scraped_at <= lockTime. It uses 60% valueIndex /100 + 40% horse QP amount / maximum horse QP amount. No standby/withdrawn runners. Missing live data produces unavailable status, never fabricated tips. Requests/retries may occur more than once, but each race has one immutable successful output. Schedules are loaded at startup, so unexpected later post-time changes need operator review; mismatching lockTime is rejected. No claim of zero-second network latency or guaranteed first-minute publication.

Opening result pages does not fetch HKJC/Supabase directly. Pages read small summaries from the data branch; browser and raw-content cache can delay visibility. Updated-at is displayed. Restarting restores saved results and Dragon baselines; a missed Horse103 capture is labelled missed, not recreated after the race. Unpublished last-minute local data may be lost on a forced cancellation or runner failure.

## Validation

`python -m unittest discover -s race-day -p 'test_*.py' -v`

Preflight validates startup schedule access and pure logic. It does not prove HKJC market availability from hosted runners on race day, nor guarantee service uptime. Before relying on the copy, inspect one real snapshot and keep the original ready as backup.
