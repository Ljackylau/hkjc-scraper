# Horse103 continuity

## Enabled

- First valid Live103 response is written to `race_NN_live.json` before ticket and entry requests. Its original receipt time is retained through in-process retries.
- Eligible source tickets are written separately before ranking. An incomplete calculation is `partial`, never a successful pick.
- Preflight checks schedule, Live103 response shape, entries and a bounded ticket sample. The report distinguishes connectivity/schema from readiness at T−3. Warnings do not invent a valid lock.
- Each phase uploads local evidence as an Actions artifact even when the runner fails. Hard runner termination may prevent this; the data branch remains the primary published store.
- A daily workflow at 00:30 Hong Kong time archives historical Horse103 JSON with SHA-256 hashes. Seven-day artifact retention limits accumulated duplicate archives. Download a ZIP for an independent local copy. Data branch history is not deleted.
- Archives and the repository are both on GitHub. This is **not** protection against loss of the GitHub account/provider. An off-provider automatic copy needs a user-owned destination and authentication; none is configured.
- The archive also contains independent HKJC market snapshots when they exist, including raw JSONL and T−30/T−3 evidence.

## Independent data source: validation stage

`horse103-source-probe.yml` tests HKJC directly, independently of 103.plus. It runs when the HKJC source code changes or by manual dispatch; eight-minute job limit, two odds pages, no betting actions. A completed workflow does not mean a validated fallback: inspect `hkjc-probe.json`.

The `Run` option starts two extra HKJC-only jobs alongside Horse103: early races R1–R4, late races R5–R9. The jobs use the separately supplied HKJC venue and official post times, then follow the official page's time if it moves by up to 30 minutes. They poll about once per minute from T−30 and every 10 seconds around T−3, reject stale timestamps and incomplete pools, and save raw Q, QP, win and place odds on the `race-day-data` branch. They do not request 103.plus. The experimental ranking uses positive drops in WIN 35%, PLA 25%, QIN 20%, QPL 20%; pair-pool measures average the three strongest positive drops touching a horse. Zero-signal races have no ranked pick. A ranking here is not Horse103 valueIndex or a validated Top-3 probability; the page displays it as observation only.

Before enabling a shadow ranking collector, verify all four pools, race identity, source update timestamps, announced schedule changes, and T−30/T−3 endpoint coverage. Record real capture times and reject stale/post-race reconstruction. Then accumulate several complete race days and compare against Horse103 using only contemporaneously captured data. No automatic fallback picks are enabled yet.

103.plus valueIndex cannot be reconstructed from HKJC odds. Any future fallback formula must be named and validated separately.
