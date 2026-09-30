# HKJC Double archive

Enabled automatically in the existing Race Day Runner HKJC early/late jobs.
No separate workflow, login, LLM or paid API. No change to tips or Telegram.

For each first leg Rn (excluding the final race), archive the HKJC public `dbl`
page for Rn / Rn+1 from T-32 until the strict first-leg T-3 cutoff.
Poll every 60 seconds, then every 10 seconds from T-7. Actual cadence also
depends on page response time. Separate browser tasks isolate Double failures
from the WIN/PLA/QIN/QPL collectors.

Files in each existing `race-day-data/DATE/hkjc-early` or `hkjc-late` folder:
- `double_NN_MM.jsonl`: unique observations with receipt/source times.
- `double_NN_MM_t3.json`: last fresh observation received no later than T-3
  minus 10 seconds. Never substitute a later observation.
- `double_NN_MM_errors.jsonl`: failures, including stale quotes / wrong date.
- `double_status.json`: pair status; only `saved` means a snapshot was saved.

`qb_DBL_A_B` means first-leg horse A and second-leg horse B. Keys are ordered,
not sorted. Both race identities, date, venue and advertised off times are
checked. Source age and endpoint age must be at most 120 seconds. Schedule
changes up to 30 minutes are followed. Existing valid locks survive restarts.
Incomplete matrices and odds >=999 are explicitly marked; such values must
not be treated as uncensored exact odds when fitting a model.
Both races' contemporaneous WIN quotes are saved from the same page to support
future cross-pool comparisons. No reconstructed historical time series.

Research plan (not yet applied to predictions):
1. Compare each horse's normalized inverse-Double marginal share against its
   normalized inverse-WIN share, separately for first and second legs.
2. Compare marginal-share growth T-30/T-10/T-7/T-3 and last-minute acceleration.
3. Test pair concentration / excess support relative to the product of WIN
   shares, with missing/999 quotes excluded or handled by sensitivity bounds.
4. Add features to the independent model only after frozen out-of-sample races
   show improvement over its current main / legs ranking.

Second-leg Double data stops when the first leg closes. It is an earlier
signal for Rn+1, not that race's T-3 quote. Never relabel it. Final-race current
leg has no following Double; unavailable data must leave the model unchanged.

Public source: https://bet.hkjc.com/ch/racing/dbl
