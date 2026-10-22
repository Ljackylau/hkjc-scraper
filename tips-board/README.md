# 賽日貼士表

## Adopted ST turf confidence Win add-on — October 20

Both pages add **沙草信心場補Win** and append its confirmed plan to the existing
bet cells. This independent add-on does not change original selections, H,
confidence eligibility, monthly Q/QP statistics, or HV/AWT methods.

Exclude Meiji four and the initial banker five, plus known withdrawals. Use
only dated HKJC numeric-finish records since 2025-09-01, strictly before the
meeting date; at least two valid first-position readings in the last three
numeric-finish races, median >=4. Rest >=60 days needs one of 西門獨/諸葛數/
陳志懷/兆文; shorter rest needs last finish <=3 and at least two authors.
Filter **Win odds >8** before ranking by supporter count descending, best
author rank ascending, saddle ascending; take at most two, $10 Win each.

`st_coldwin.py` captures the four authors from the dated On.cc matrix and
minimal official prior-race form. Identity/date/name checks fail closed. Form
requests are batched at 12 per pass, with three workers, and stop within ten
minutes of the advertised off; missing data never becomes a partial plan.
Preparation/manual/live passes fill pending support without reading the index,
race-day results, post-race notes, or private prediction-model data. Upcoming
cards now retain official horse IDs. Started/locked races are never enriched.

The board has **no automatic live Win-price feed**. Latest-page users enter
prices for all qualified candidates and confirm them. Blank/invalid prices do
not count as <=8; no final plan appears until all candidate prices are known.
Prices and the resulting receipt live in this browser only, survive polling,
and freeze at off. They do not synchronize to public archive or other devices.
Displayed prices are saved observations, not a claim of continuously live odds.

`st-coldwin-history.mjs` holds explicitly reconstructed public-source inputs
for the 31 ST turf confidence races through October 19. Historical display uses
final odds, is labelled retrospective, and is never represented as an original
pre-off receipt. The frozen fixture reproduces **28 bets, four winners, $280
cost, $542 gross return, +$262**. Post-adoption races without a pre-off receipt
are labelled missing, not reconstructed from future prices. The historical
study is exploratory, not an independent validation or a profit guarantee.

Checks: `node tips-board/test_st_coldwin.mjs`,
`node --experimental-vm-modules tips-board/test_st_coldwin_ui.cjs`,
and Python unittest discovery including `test_st_coldwin.py`.

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


## 2026 exact-condition jockey top 5

The column immediately after the initial banker list ranks only riders declared
in the target race by top-three finishes / actual starts since 2026-01-01.
Venue, surface, distance and rail must all match. AWT is its own track/rail.
No minimum sample exclusion and no fallback to other rails; zero starts are
unranked, and samples below 15 are labeled. Ties use starts descending then
saddle number ascending. Withdrawals/TNP do not count; DNF counts as a start;
dead-heat positions count at their published numeric placing.

`records/jockey-2026.json` holds the official full-field results cache (including
stable HKJC jockey IDs). Only dates before the target date, or earlier races
at the same meeting, can contribute. The target result and later races cannot
contribute. Current official card refresh handles rider changes/withdrawals,
and the rank locks at the off. Archived rankings are explicitly reconstructed
from final official starters, not represented as sealed pre-race receipts.

`python tips-board/collector.py refresh-jockeys --data data/records` rebuilds the
historical column and prepares the latest meeting without changing betting
selections, expert tips or results. The collector updates the durable results
cache on subsequent meetings; no calendar-2025 history is used.


## October 16 collection and draw-statistics update

The tips board no longer requests the index feed or per-race official results in live, tips or manual collection. `reconcile` is a disabled legacy entry point; the former recovery workflow refreshes draw history from completed prior days only. Existing stored results and settlement displays are retained.

The table hides the index column. The ranking uses each declared jockey’s own performances at the current barrier draw, exact rail/draw only, pooling venues and distances, top-three finishes divided by actual starts, from 2026-09-01 through the day before the selected meeting. Same-day and future results are excluded. Jockeys are ranked by rate, sample size, then current saddle number; only the first five with history are displayed. No condition fallback or inferred draw numbers.

`python tips-board/collector.py refresh-draws --data data/records --publish` fills the durable `draw-history.json` cache and recomputes archive/latest `draw_top5` without replacing original selections or board results. Future cards supply the actual draws; historical cards are explicitly reconstructions of the final field.


## Jockey/draw correction

`draw_top5` now ranks only jockeys riding in the selected race. Each rate uses that jockey's own rides at the current barrier draw, with exact rail/draw only, pooling venues and distances and dates from 2026-09-01 strictly before the meeting. Different jockeys at the same barrier are excluded. Output uses `method_version: jockey_rail_draw_v2` and `riders`, retaining each jockey's current saddle number for identification. The renderer waits for the corrected version instead of showing the former all-jockey draw rates.

## October 17: same rail and draw only

The jockey ranking matches only rider ID, rail configuration and current draw. It pools Sha Tin and Happy Valley rides at identically named rails and all distances; AWT remains its own rail key. Dates, withdrawals, ranking tie-breaks and current-field-only eligibility are unchanged. The version guard is `jockey_rail_draw_v2`.

## October 17: draw only (supersedes same-rail filter)

`jockey_draw_only_v3` matches only each declared rider and the current barrier draw. Pool both venues, turf and AWT, all rails and distances. The September 1 cutoff, prior-day-only rule, current-field eligibility, top-five limit and ranking tie-breaks remain. The UI waits for this version and labels the column 同檔表現頭5騎師.

## Confidence-only and monthly tables (October 17)

Both pages show a compact confidence-only table above the full race table, with race/H, the displayed bets and official results. Happy Valley H=1/2/3 are confidence races regardless of selection readiness; H=0/pending are excluded. Sha Tin keeps the existing M1-outside-initial-first-three rule, including turf for H=0.

The last section aggregates every archived meeting plus the current meeting, deduplicated by meeting identity. It groups by month, venue, H, pool and main/optional role. A race hits when its displayed bet has at least one official paid combination; several winning horses or pairs still count as one hit race. Only settled hit/miss races enter the denominator. Pending results/plans, fully refunded bets and unavailable pools are displayed separately. Local saved snapshots and explicitly labelled ST historical strategy recalculations match the main table. These are retrospective confidence-rule statistics, not an independently sealed historical track record.

Archive requests use a single pinned data revision. Any failed/mismatched archive response suppresses monthly rates until a complete reload succeeds. New/live races with results collection disabled remain pending, never losses. This UI change does not fetch race-day results or change selections.

GitHub版本API限流時，頁面使用本機上次成功核對的固定版本；首次瀏覽則使用2026-10-17的備用固定版本，並顯示可能未含最新貼士的提示。所有歷史紀錄仍來自同一固定版本，避免混合版本計算月率。

Monthly confidence tables display pair pools only (QP, then Q), ordered by venue (Sha Tin, Happy Valley), H, then month descending. Main/optional roles remain separate; race and settlement definitions are unchanged.

### Mobile refresh and stale-data recovery

Both pages recheck the data revision when shown again, when the tab becomes
visible, and after reconnecting. History polling retains the selected date and
refreshes its date index and monthly summaries when the source changes.
`data-source.mjs` tries the GitHub branch ref, then current raw data if the API
is blocked or rate-limited; a saved immutable revision is an explicitly labelled
last resort when both routes fail. Requests time out instead of leaving refresh
permanently busy. Browser-local manual selections and odds receipts are preserved.

Checks: `node tips-board/test_data_source.mjs` and the three
`node --experimental-vm-modules tips-board/test_*_ui.cjs` suites.


## Happy Valley H=0/1 trial (2026-10-21)

Both pages and the collector use the same trial rule: H=0 buys one $10 Place on J2 only when Meiji's original first pick is outside the initial banker/leg1/leg2; otherwise skip. H=1 buys one $10 Win on the sole available expert's original first pick. No odds threshold, extra legs or optional pools. Missing/stale inputs wait; a withdrawn selected runner is skipped without promotion. J2 must match the current declared draw and jockey.

The browser labels historical replays as recalculated and leaves source records unchanged. Existing pre-off snapshots using this trial method remain frozen after off. H=2/3 and Sha Tin retain their rules. Monthly confidence reporting remains Q/QP-only, so H=1's former optional QP is excluded after replay under the new W-only method. These exploratory rules are marked as a trial, not a promised future return.


## Sha Tin turf confidence-only QP (2026-10-21)

H=0/1 now require TURF and Meiji's original first pick outside the initial banker/leg1/leg2. Keep the existing new-D (H0) and M3+T2+T3/fallback (H1) three-runner selection order, but buy only three Quinella Place combinations at $10 each. Skip AWT and failed gates; incomplete sources remain pending. H=2/3 and Happy Valley rules are unchanged. The display labels historical recalculation without overwriting original archive tickets. New-method pre-off snapshots stay frozen after off.


## 2026-10-22：主買法＋每日首三注補Win

入口只保留 `index.html`（最新賽日）與 `history.html`（歷史紀錄）；兩者共用 `board.mjs`、`combined-model.mjs` 的選馬及結算。舊 `strategies.html` 和 `strategy-history.html` 已移除。

主買法沿用原信心場主要彩池。補Win按原四選第4匹、跑法前五未重複候選最高W賠率>10、每日首三注，每注$10。歷史回算使用 `combined-archives.json` 的最終賠率代理；不代表賽前封存或實際下注。歷史統計以去重後的下注場數作命中率分母。

即場跑法由 `front_forms.py` 收集目標賽日前最近三仗。賠率目前需要有效 `win_odds` 資料物件或頁面本機輸入；沒有完整候選價格，不產生補Win。`combined-live-snapshot.mjs` 不讀歷史賠率；開跑前3分鐘內分別封存主買法與補Win。伺服器封存跨裝置可讀；本機輸入及本機封存只在同一瀏覽器保留。未接入下注收據，實際下注帳保持未有資料。

檢查：`node test_combined_model.mjs`、`node --experimental-vm-modules test_combined_ui.cjs`、`python -m unittest test_front_forms test_collector`。


### H=0交集補Win（2026-10-22新增）

保留原每日首三注補Win。其餘場次只限H=0：按膽拖初版五選次序，取出現在明治四選中的第2匹；僅當W>7.5時買$10W。先取原第2交集，該馬退出不補位。原首三注歸屬未明時仍顯示候選及價格條件，但不能確認下注。這個附加方法沒有額外每日三注限制。

`intersectionCandidate()` 不需要賠率或跑法往績即可顯示候選；確認下注仍須原首三注排除及有效賽前價格。封存新增獨立 `secondary_version` / `secondary_finalized` / `secondary_captured_at` / `secondary_input`，不覆寫原主買法或原首三注封存。主買法、原補Win、新交集補Win可分別篩選統計，總覽按場去重。原統計用 `role:original`，現行合計用 `role:combined`。

9月6日至10月21日歷史代理回算：新交集補Win15注、5勝、投入$150、淨利$392；現行合計投入$1,840、淨利$3,544.5。這是調整門檻後的探索回算，非獨立前瞻驗證或實單成績。
