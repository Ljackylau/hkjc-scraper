# 賽日貼士表

GitHub Pages: https://ljackylau.github.io/hkjc-scraper/tips-board/

Latest and history are static pages. A separate `tips-data` branch holds `records/latest.json`, `records/YYYY-MM-DD.json` and `records/history.json`. The pages poll raw GitHub JSON every 20 seconds with a cache-busting URL; no repeated Pages deployment is needed. GitHub/CDN propagation adds delivery latency, so the polling interval is not a guaranteed end-to-end latency.

## Automatic operation (Asia/Hong_Kong)

- Official HKJC cards identify the current upcoming meeting, fields and advertised times.
- Scheduler runs every 15 minutes, dispatching collectors ahead of their deadlines. GitHub may delay scheduled starts. The tips collector waits until the first race minus two hours, checks each source once, and persists the cutoff. Failed/stale sources stay unavailable.
- Live collector starts before race 1, polls index state every 20 seconds inside each race's minus-three-minute window, validates exactly four horses, then retains the first valid pre-off capture. Declared off time locks selections. HKJC published schedule revisions are checked before off; unannounced delays cannot be inferred safely.
- Official results are first checked at published off plus three minutes and retried once a minute. Results are required to match the meeting date and declared field. The full day archives after all results or last off plus 45 minutes. Missing results remain explicit.
- Nightly recovery checks the last three days, fills missing official results, and never reconstructs missing pre-race index tips.
- No credentials in public frontend or records. Index encryption is decoded by the source site's own public page configuration and algorithm. The data endpoint is queried with a timestamp to avoid reusing a browser cache; upstream publication delays remain outside this system's control.

## Rules

Score is the number of nonempty selections from 波仔, 馬觀微 and 電腦評分, even if they choose the same horse. Unknown/error sources do not imply score zero.

0: index first two, W/P. 1: sole expert first plus Meiji first (Meiji second on overlap), W/P and optional QP. 2/3: Meiji first three, QP and optional W/Q. Pools display a compact horse list without expanded pair combinations. Stake amounts are not specified.

## Verify

`pip install -r tips-board/requirements.txt`

`python -m unittest discover -s tips-board -p 'test_*.py'`

`python tips-board/collector.py bootstrap`

Workflow status: `.github/workflows/expert-tips-{schedule,run,reconcile}.yml`.
