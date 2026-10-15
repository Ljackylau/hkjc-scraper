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

## Historical backfill (2026-09-01 through 2026-10-13)

`backfill.py` reads date-specific On.cc archives, Star `raceDay`, `raceEntry` and `expertTips` records, the index site's spotlight archive and explicit per-race `race_ai.index_top4` archive, and HKJC official results. Each source is matched to the date, venue, race and declared horses. Results use the selected date header, never a date present only in the navigation.

Historical meetings carry `record_type: historical_backfill`; their selections are `reconstructed`, not contemporaneous selections. Some per-race index archives report creation times at or after the published off time. These are displayed with a warning and must not be treated as verified T-2 captures or a leakage-free backtest. Current-day live records retain their original semantics.

A single unsupported Big5 glyph (`?` or replacement character) is repaired only when the horse number, name length and all remaining characters match the dated declaration; the original source name is retained. Other name mismatches stay errors.

Backfill operates in its own destination and never overwrites `latest.json`. The history index preserves later contemporaneous records when published.

## Buy-method settlement

Each W/P/Q/QP line is matched against HKJC's paid winning combinations. W/P shows the number of selected horses paid; Q/QP shows winning combinations out of all pairs in the compact horse list. Every winning combination displays its own official dividend divided by HK$10, including principal. This is a payout multiple, not net profit. Optional methods are evaluated separately. Missing dividends remain pending; races that did not offer a pool are labelled unavailable; withdrawn combinations are labelled refunded. No stake or aggregate profit is assumed.

`node tips-board/test_settlement.mjs` verifies pool matching, reversed pairs, multiple QP wins, dead heats, refunds and unavailable pools.

## Manual source collection

The latest page has a **要求抓取（GitHub）** button. It opens the authenticated workflow page; the repository owner selects `manual` and confirms **Run workflow**. This is a GitHub confirmation handoff, not a one-click backend endpoint. GitHub Pages cannot securely dispatch an authenticated workflow by itself. A real one-click button needs an authenticated backend; no repository token is embedded in the page.

Manual mode defaults to `latest` and does one bounded pass: refresh date-validated expert tips for unstarted races, attempt index only in its original pre-off window, and check eligible official results at least three minutes after off. A failed or stale manual fetch retains the last valid tips and records an error. It never changes tips or selections for a started/locked race, and does not consume the automatic T-2h check. Each pass records its times and errors. All collector modes share a concurrency group to prevent competing record writes; requests queue behind an active collector.

Both latest and history read records through an immutable tips-data commit SHA. Latest checks the branch head every 90 seconds; Refresh forces an immediate version check. A failed version check retains the last rendered table and displays the failure instead of silently falling back to old bundled data. Manual stale/error status is displayed when no previously valid tip exists.

## Browser manual tips

Latest meeting users can enter horse numbers per source in original order. Horse names come from the declared field; duplicate, unknown and incomplete numbers are rejected. Meiji/index require four picks; the three experts accept one to four, or an explicit absent choice. Automatic-source choice removes that override. H/pattern/bets recalculate from the combined manual and automatic tips. Manual rows are labelled.

Overrides live in browser localStorage per date/venue, not in the public GitHub archive, and are visible in that browser's history. Polling preserves them and refreshes their pre-off selection snapshot. After off or server lock the last observed pre-off snapshot is frozen; future automatic tips cannot rewrite it. Editing and resetting are only allowed before off. If the browser was closed before later sources arrived, its last observed selection is retained, including incomplete selections. JSON download backs up local records; clearing browser storage removes them. This feature does not synchronize devices.

## Formula reference columns

賽馬方程式key and 賽馬方程式real are free-text reference fields (up to 200 characters), entered directly in the latest table. Each keystroke saves to separate browser storage per meeting and race. They do not alter tips, H, selections or settlement, and can be edited after off because they are references only. Polling does not replace the input while typing. History displays the locally saved reference text, escaped as text. These fields share the existing local-only/device limitation.


## Sha Tin initial-card four (2026-10-15)

Independent `sha_tin_four` column, only ST. The banker site's initial H=0 is
**not** the expert-count score. Fetch `/race/DATE~ST~R?v=1`; require the published
`v1賽前排位` label and matching date/venue/race. That public label is the available
verification of initial/as-of-zero; the site HTML does not expose the database
`reason`/`as_of_race_no` columns themselves. Never parse the current/latest card
or the 同程檔位排序/table ordering. Preserve that captured five-pick initial list.

Take its first three active distinct runners. Fourth: the first published
source with any picks in ball → ma → computer → meiji order; take its first
active nonduplicate in published order. If that source has no eligible distinct
pick, use initial leg3 then leg4 (never a lower-priority tipster). Remove known
withdrawals and shift along the same list. Missing/failed higher sources are
unknown, not absent; emit pending with no partial list. Ready output always
contains exactly four saddle numbers. Does not create betting instructions.

Star expert identities use professional_list IDs (including AI rating ID
65e9600b960d550012a89716), and the expertTips system, not notes or HKJC ratings.
Collector captures only pre-off and preserves locked races. Declared-field
refresh handles pre-off withdrawals. Archived races can be reconstructed separately with `backfill-four`. This only adds initial-card/indicator fields, preserves original selections, locks and results, and marks the new indicator as historical reconstruction, not an independently sealed pre-off receipt. Future meetings use the live pre-off capture path.


The adjacent 馬會膽拖網推介 column shows all five initial-card numbers and
canonical horse names, labeled 膽/腳1/腳2/腳3/腳4, for both ST and HV. It uses
`banker_initial` only, never table order or 同程檔位排序. The separate four-number
indicator remains ST-only. Live pre-off capture now saves initial cards for
both venues; historical receipts remain explicitly marked as reconstruction.
