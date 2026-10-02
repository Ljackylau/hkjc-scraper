# Four-leg cold fusion — active from 2026-10-02

Keep the existing F2 + banker QP2 selection. Once the cold v2 tip is prepared,
replace the fourth leg only if the one selected cold runner has predeadline
WIN >10 and <=30, is not the banker, and is not already in the original four.
The original first three legs and their ordering remain fixed. No fifth leg.

`leg_fusion.apply()` runs inside the existing T−3:10 freeze after cold
preparation and before saving, publication and notification. It makes no
network requests. The collector, website, copied tip and existing notification
path all use the same frozen final selection. Browser legacy QP sorting must
never overwrite this method. Old saved race-day selections are not upgraded
to this fusion method after the deadline.

Method: `f2_qp1_cold_10_30_exploratory_2026_10_02`.
Cold version: `cold_top2_priority_v2_exploratory_2026-10-02`.

Audit fields: `legs_original`, `legs_original_method`, `legs_original_qp`,
`legs_fusion_changed`, `legs_added`, `legs_removed`, `legs_fusion_win`,
`legs_cold`, `legs_fusion_reason_code`, `legs_fusion_reason`.
If cold is unavailable, outside the WIN gate, already selected, the banker,
or its source receipts/history preparation arrive after the shared freeze,
keep the original four with a reason. If original F legs lack valid T−10
inputs, retain the explicit unavailable state; cold cannot invent four legs.

This is an exploratory retrospective rule. On the same 29 complete races
across Sep23, Sep27 and Oct1, placed legs were 41/116 before and 47/116 after;
banker QP-hit races 18/29 to19/29; QIN9/29 to11/29; both placed partners5/19 to8/19.
Thirty-one races were scheduled: Sep27 R11 lacked a fresh endpoint; Oct1 R11
lacked valid T−10 for F. No untouched external validation or profit claim.
The cold selector and WIN cap were explored using these same dates.

The regression fixture stores predeadline F scores, banker pair prices,
original/fused choices and source receipts. History-preparation receipts are
simulated for fixture execution, as in the existing cold replay; they do not
claim historical live execution. No current finish/final odds feed selection.
The website shows the reason and retains the original four for review.
Future live data availability and display timing still depend on the source,
runner and publication; no exact T−3 delivery guarantee is implied.
