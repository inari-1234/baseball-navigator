# Legacy Decision Logic Crosswalk

Legacy files are archived evidence only. This table decides what is executable in the Y1 October Sapporo branch.

| Legacy source | Disposition | Current rule(s) | Reason |
|---|---|---|---|
| `FC7F:D00` | **ARCHIVE_ONLY** | — | Calibration-branch identity rule; not a live Sapporo gameplay rule. |
| `FC7F:D01` | **KEEP** | DC-EV-002 | Single observation remains scoped; now explicit scope/sample_n. |
| `FC7F:D02` | **AMEND** | DC-EV-002 | Pair-comparability principle retained; generalized empirical claims now carry scope/sample_n. |
| `FC7F:D03` | **KEEP** | DC-MATCH-001 | State-dependent match value retained; fixed monthly optimum rejected. |
| `FC7F:D04` | **AMEND** | DC-ROSTER-001 | Role classification retained; post-October longevity removed from Sprint score. |
| `FC7F:D05` | **AMEND** | DC-OFF-001, DC-OFF-002, DC-OFF-003 | Failure-mode logic retained and operationalized with repeated/comparable definitions. |
| `FC7F:D06` | **AMEND** | DC-PITCH-001, DC-PITCH-002, DC-PITCH-003 | Failure-mode logic retained; pre-October breaking unlock is conditional, not assumed. |
| `FC7F:D07` | **KEEP** | DC-ACTIVITY-001 | No Sports spending solely for measurement retained. |
| `FC7F:D08` | **AMEND** | DC-ITEM-001 | Recovery-action ROI retained; low-level October-core item use added. |
| `FC7F:D09` | **KEEP** | DC-FAC-001 | No fixed facility count; material demolition must be traceable. |
| `FC7F:D10` | **AMEND** | DC-MATCH-002 | Two equivalent failures still force method change; comparable/repeated now defined. |
| `FC7F:D11` | **KEEP** | DC-EV-001 | Historical run may inform mechanics but not silently dictate current allocation. |
| `FC7F:D12` | **SUPERSEDED** | — | FC7F release-stage scoping is historical; DECISION_CONTRACT is now the execution authority. |
| `FC7FR:R00` | **KEEP** | DC-REGION-001 | Hokkaido remains practical baseline, not global-fastest proof. |
| `FC7FR:R01` | **AMEND** | DC-START-001 | Pitcher/がんばり屋/velocity30 retained only as experimental baseline, not optimum. |
| `FC7FR:R02` | **SUPERSEDED** | DC-CHEER-001 | Later live operation withdrew Cheer-OFF prohibition. |
| `FC7FR:R03` | **AMEND** | DC-TRAIN-001, DC-ITEM-001 | Low-level-first retained; Y2-Aug horizon replaced by Y1-Oct core and skill-reroll evidence. |
| `FC7FR:R04` | **AMEND** | DC-OFF-001, DC-OFF-002, DC-OFF-003 | Fixed long-ball bias is subordinate to live failure-mode classification. |
| `FC7FR:R05` | **AMEND** | DC-TRAIN-002 | Affinity remains material; remaining tenure/future value removed from Sprint scoring. |
| `FC7FR:R06` | **KEEP** | DC-MATCH-001 | High density × beatable opponent retained. |
| `FC7FR:R07` | **SUPERSEDED** | DC-MATCH-001 | 3-4/4-5 monthly targets are not active quotas. |
| `FC7FR:R08` | **AMEND** | DC-MATCH-003 | Retained only as experimental tie-breaker pending live verification. |
| `FC7FR:R09` | **AMEND** | DC-MATCH-002 | Farm/retrain/retest retained; equivalence and failure count made explicit. |
| `FC7FR:R10` | **AMEND** | DC-PITCH-001, DC-PITCH-002, DC-PITCH-003 | Velocity-first is no longer unconditional; live failure mode controls. |
| `FC7FR:R11` | **AMEND** | DC-FAC-001 | Field removal is no longer automatic GO; requires observed replacement/throughput value and trace. |
| `FC7FR:R12` | **SUPERSEDED** | DC-GOAL-001 | Old October-loss-acceptable objective conflicts with Sapporo terminal goal. |
| `FC7FR:R13` | **SUPERSEDED** | DC-STUDY-LEGACY | December Study30 reserve is outside Y1-Oct Sprint horizon. |
| `FC7FR:R14` | **AMEND** | DC-RESET-002 | One-reload cap removed; first result remains stability evidence and later retries are achievement-only. |
| `FC7FR:R15` | **KEEP** | DC-EV-001 | Live Ver1.42 override retained. |
| `FC7FR:failure_mode.offense_contact` | **KEEP** | DC-OFF-001 | Threshold preserved with comparable/repeated definition. |
| `FC7FR:failure_mode.offense_conversion` | **KEEP** | DC-OFF-002 | 4-7 hits with 0-1 runs repeated remains conversion-failure trigger. |
| `FC7FR:failure_mode.pitch_control` | **KEEP** | DC-PITCH-001 | >=3 BB/HBP-equivalent across two comparable games retained. |
| `FC7FR:failure_mode.pitch_power` | **AMEND** | DC-PITCH-002 | Hard-contact/run allowance retained; available pre-Oct tools constrain response. |
| `FC7FR:failure_mode.recovery` | **AMEND** | DC-ITEM-001, DC-FAC-001 | Blocked high-value actions still trigger recovery response; facilities are not assumed available. |
| `EngineCSV:R01 Deadline first` | **KEEP** | DC-GOAL-001 | Deadline precedence retained. |
| `EngineCSV:R02 First-win value` | **KEEP** | DC-PROC-002 | Retained in FULL opportunity-cost evaluation, not a fixed automatic action. |
| `EngineCSV:R03 Use actual loss history` | **KEEP** | DC-MATCH-001 | Live loss history remains stronger than public grade for practical risk. |
| `EngineCSV:R04 Cheer threshold` | **AMEND** | DC-CHEER-001 | Cheer<20 no longer forces activity; compare current action opportunity cost. |
| `EngineCSV:R05 Resource opportunity cost` | **KEEP** | DC-PROC-002 | Retained at FULL checkpoints; hardcoded reserves are not imported. |
| `EngineCSV:R06 Random outcome recheck` | **KEEP** | DC-ACTIVITY-001 | Random school-activity rewards are re-read. |
| `EngineCSV:R07 No pre-game HP burn` | **KEEP** | DC-GOAL-001 | Retained as deadline/readiness hard consideration. |
| `EngineCSV:R08 Weakness alignment` | **KEEP** | DC-OFF-001, DC-OFF-002, DC-PITCH-001, DC-PITCH-002 | Retained through failure-mode rules. |
| `EngineCSV:R09 Live placement` | **KEEP** | DC-FAC-001 | Live preview/throughput overrides public facility base value. |
| `EngineCSV:R10 Affinity experimental gate` | **AMEND** | DC-TRAIN-002 | Affinity is now an explicit material factor; A/B remains useful when uncertain. |
| `EngineCSV:R11 Reverse-roadmap gate` | **AMEND** | DC-GOAL-001, DC-PROC-002 | Roadmap target replaced by Y1-Oct Sprint. |
| `EngineCSV:R12 Generation longevity` | **SUPERSEDED** | DC-ROSTER-001 | Y2/Y3 longevity is outside Sprint objective. |
| `recommendation_engine.py hardcoded reserves` | **ARCHIVE_ONLY** | — | Study30/Sports60/Fun15/Nature17 are historical implementation constants, not current contract. |
| `recommendation_engine.py school-specific score bonuses` | **ARCHIVE_ONLY** | — | Hardcoded Teikyo/Choshi bonuses are old-state implementation details. |
| `Authority v1.3 pipeline` | **AMEND** | DC-PROC-001, DC-PROC-002 | State→relation→action retained but split FAST vs FULL for latency and auditability. |

## Disposition semantics
- **KEEP**: meaning preserved in an ACTIVE current rule.
- **AMEND**: core idea preserved but scope/conditions/objective changed.
- **SUPERSEDED**: must not drive live play.
- **ARCHIVE_ONLY**: retained only as historical evidence/implementation context.

## New evidence requiring amendments
- SAVE/LOAD skill result changed in one observed Just Meet case; generalization is PLAUSIBLE with `sample_n=1`, not universal fact.
- Current Sprint deadline is Y1 October, so Y2/Y3 longevity and December Study reserve are outside the objective.
- Practice-match resets corrupt combat-gate measurement; official first-attempt result and achievement retry are separated.
- Four skill slots are treated as equipped slots rather than a learning cap; skill acquisition itself is not rejected merely because a weak skill appeared.
- Pre-October breaking-ball training/recovery facilities are not assumed unlocked; live availability controls.
- New-run roster/core selection is captured before hard lock; entrant reroll remains EXPERIMENTAL until reproduced on Ver1.42.
