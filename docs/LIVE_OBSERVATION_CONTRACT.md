# Live Observation → State → Decision Contract (v1.2)

## Purpose and scope
Source-linked game observations are normalized to a deterministic event stream; the current state is a replay projection. This repairs the failure where screenshot analysis omitted match completion and let old June points drive July-or-later recommendations.

**Not an OCR system.** A human/assistant visually extracts visible values, marks unknowns, and attaches screenshot filename or exact user report. CI can validate extracted-data consistency, not pixel-reading correctness.

## Events
Required for each event: contiguous `seq`, unique `event_id`, `kind`, `source.kind` (RAW_SCREEN / USER_REPORT / USER_CORRECTION), `source.locator`, and `period` (year/month) except CORRECTION. Screenshot observation should include its visible clock when present.

- `SCREEN`: branch ACCEPTED, complete five-point resource counters (or do not emit a resource snapshot), money if visible.
- `MATCH_SCHEDULE`: unique match IDs with opponent and month, **not** played evidence.
- `MATCH_ATTEMPT`: match_id, period, opponent if first sighting, attempt number, score and branch ACCEPTED or REJECTED. First rejected 0–1 and second accepted 3–0 are two entries for one match.
- `MATCHES_COMPLETED`: direct user correction that period's matches are over, even if individual scores unknown. Changes remaining SCHEDULED to COMPLETED_SCORE_UNKNOWN.
- `TRAINING`: exact three distinct participants, drill and drill level, Cheer ON/OFF, branch ACCEPTED/REJECTED and optional `skill_awards`. Only accepted training contributes to `training_counts_observed`. Counts cover **recorded** committed sessions only; pre-log training is UNKNOWN.
- `ITEM_USE`: accepted/rejected branch and optional combined observed item effects. Distinguish an observed combined delta from an unmeasured per-item effect. Item inventory tracking is not yet implemented; ITEM action proposals fail closed.
- `ROLLBACK`: use `restore_to_event_id` if the exact restored checkpoint is known. Subsequent discarded branch actions are excluded from the current state but retained in raw event history. Without a known anchor, invalidate earlier active timeline, block unsafe actions, and require an explicitly sourced post-rollback screen.
- `CORRECTION`: target prior event_id and restricted patch; `target_match_id` with opponent correction updates the schedule and all attempts consistently. No implicit overwrite of unreferenced historical facts.

## Derivation and safety
`python3 live_state_engine.py` checks `CURRENT_LIVE_STATE.json` against replay of `LIVE_EVENTS.jsonl`. This projection is the gameplay runtime state; `CURRENT_RUN_LEDGER.yaml` preserves provenance and formal decision checkpoints. June resource screenshots may remain in history but cannot authorize paid actions after a July completion event.

Source time matters: any accepted SCREEN after a match, training, item use, period-completion report or rollback must set `after_event_id` to the immediately preceding resource-invalidating event. Without the anchor the screen remains historical/stale. This also protects same-month screens. The source locator must still identify the actual attachment or user statement.

A recommendation must pass `validate_recommendation` checks:
- `based_on_event_seq` equals latest accepted event revision
- nonempty `rule_ids`, all ACTIVE in Decision Contract
- `action_type` is explicit; MATCH requires `target_match_id`, and `target_period` cannot be a completed period
- TRAIN requires three distinct participants, Cheer ON/OFF and explicit Sports cost, not an omitted cost
- `target_match_id` exists, is still SCHEDULED, and is not older than the last confirmed live period
- `spend` is within fresh visible resource counters; Cheer ON training requires its own positive verified Cheer cost
- `timeline_status` must not be UNKNOWN_AFTER_ROLLBACK
- ITEM advice is blocked because no current source-verified item inventory is modeled

Example blocked request: `{"based_on_event_seq":7,"action_type":"TRAIN","rule_ids":["DC-TRAIN-001"],"participants":["入江","長島","今井"],"cheer":"ON","spend":{"sports":7,"cheer":20}}` because post-July Sports and Cheer are UNKNOWN.

## Confidence and precedence
A screenshot after a later resource mutation is treated as stale unless `after_event_id` identifies that mutation. A bare boolean `confirmed_after_period_completion` is not sufficient. This permits a genuinely fresh same-month screen while refusing an older reposted screen. A raw screenshot proves only visible UI; a user report may correct opponent, match completion, or reset provenance. No screenshot of June is automatically a snapshot of July. When only 'July matches finished' is known, scores and current month remain UNKNOWN. Do not claim a player gained a skill merely because an earlier discarded branch displayed it.

## Operating sequence
1. Extract factual visible fields into an event and quote its locator.
2. Distinguish schedule, result, initial/reloaded branch, current vs historical.
3. Apply explicit corrections to target IDs; replay and compare snapshot.
4. Before advice, run revision, resource, match-completion and ACTIVE-rule checks.
5. Issue one next action with Rule and Fallback, or state the precise unknown.
6. At meaningful checkpoints sync Ledger/Decision Log/Handoff. Append events rather than rewriting the past.

## Limitations
GitHub CI cannot validate the pixels, observe unsent future gameplay, or check every chat-only recommendation. A report of period completion is accepted as user evidence, not invented scores. The engine deliberately preserves these limits.


## Corrected lineage, same-month freshness and skill experiments
- A committed SAVE is a \`SAVE_CHECKPOINT\` event with its event_id. A \`ROLLBACK\` MUST name \`to_checkpoint_id\`. Without a verified checkpoint, the engine fails closed; it does not guess which skills/results survived.
- Replaying events drops all post-checkpoint events from the active state, retains their IDs in \`reverted_event_ids\`, and preserves the earliest match branch as **audit**. A later win cannot be marked STABLE after a discarded prior attempt.
- Accepted TRAINING records exactly three participants and optional \`skill_awards\`. \`training_counts_by_player_drill\` counts only accepted, non-reverted training visible in the current event log. It does NOT claim total lifetime participation or prove a hidden skill-point mechanic.
- Accepted ITEM_USE uses item bundles and optional \`effect_deltas\` as observed aggregate deltas; a discarded alternate branch does not affect current stats. Do not split aggregate effects into per-item claims.
- A SCREEN after a state-changing event must cite \`observed_after_event_id\` pointing to that specific event. If not, it is marked stale. An earlier in-month clock is stale unless the source explicitly documents a clock reset. For a user-confirmed completed month, same-month SCREEN also requires \`confirmed_after_period_completion=true\`.
- A MATCH recommendation must specify both match_id and period, TRAIN requires all three players, actual Sports cost, and Cheer ON cost when applicable. ITEM/ACTIVITY actions must explicitly declare costs, even if zero.
- Scope limitation: screenshot extraction is still a manual read, not independent pixel verification; evidence of source identity cannot prove a number was transcribed correctly.
- ITEM action must declare a nonempty item/quantity selection even when inventory was observed; blank selection cannot bypass availability checks.
