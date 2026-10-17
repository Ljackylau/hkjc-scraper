# Meiji evidence research V2

Experimental independent research; no production tips-board hook.

The primary research arm imitates Meiji first-choice labels using 42 pre-off-compatible features. Two controls are frozen alongside it. These are ranking scores, not calibrated race probabilities. The 2026-10-19 Sha Tin snapshot contains exactly four active saddle numbers per race per arm, frozen at 2026-10-17T14:19:38.579533+08:00.

## Contents

- `sources.py`: date-checked result/report/trial parsers and text-mention normalization.
- `features.py`: strictly earlier-day features, explicit missingness and dated-addendum guards.
- `model.py`: fixed chronological replay, three frozen research arms and refusal to overwrite a forecast receipt.
- `collect_sources.py`, `build_inputs.py`: public-source caching, identity validation and normalized input construction.
- `data/inputs-20261017.json.gz`: 107 historical cards, 1320 race starts, 1330 normalized reports, 1994 trial appearances, 11 future cards and source receipts. No full report prose is redistributed.
- `outputs/evaluation.json`: September 56-race training / October 51-race exploratory replay.
- `outputs/2026-10-19-ST-initial.json`: frozen pre-off choices, names, evidence, model coefficients and hashes.

## Replay

```sh
pip install -r research/meiji/requirements.txt
python -m unittest discover -s research/meiji -p 'test_*.py'
python research/meiji/model.py --input research/meiji/data/inputs-20261017.json.gz --out /tmp/meiji-replay --evaluate-only
```

`--evaluate-only` reproduces evaluation after the meeting without creating another supposed pre-off receipt. A normal run refuses a post-off forecast and refuses to overwrite an existing initial snapshot.

To recollect, supply a separate checkout of tips-data/records:

```sh
python research/meiji/collect_sources.py --records /path/to/records --cache /tmp/meiji-cache
python research/meiji/build_inputs.py --raw /tmp/meiji-cache/raw --records /path/to/records --output /tmp/inputs.json.gz
```

These commands default to this frozen 2026-10-19 ST 11-race study; date/venue/race-count arguments are explicit when preparing a new meeting. Official past reports use `?Date=`, not the results page's `racedate=` parameter. Every source is checked before reuse.

## Historical results

| Method | Top pick placed / 51 | Total top-3 seats covered by four | Four-horse QP ROI |
|---|---:|---:|---:|
| meiji | 29 | 90 | +36.6% |
| baseline_M1 | 26 | 79 | -24.2% |
| evidence_M1 | 26 | 83 | -6.8% |
| evidence_place | 20 | 75 | +37.9% |

Evidence improves the basic imitation control but does not beat the author's placement or coverage. The direct-place arm's positive ROI is concentrated on 2026-10-07; it has lower placement and coverage. No superiority is claimed. QP stakes are HK$10 per combination; one Meiji card has only three active selections after a withdrawal, hence its cost is HK$3030 vs HK$3060 for the models.

The older research was corrected for 2026-10-11 R6's two dead-heat seconds. Regression tests retain both as starters/top-three finishers.

## Limits

98 of the original tips races were retrospective backfills. Trial text markers do not constitute video assessment; report mentions can refer to another horse or ordinary slowing. Running style/pace are sparse proxies from this 107-race sample, not lifetime form. Original report segments become available no earlier than the following day; dated addenda must precede the target date. Unknown evidence has explicit missing flags. This is exploratory historical replay, not an independent historical blind test.

The first genuinely prospective observation begins with the frozen 2026-10-19 initial receipt. Later scratches require a new version; preserve this original file and do not rewrite it to match results.
