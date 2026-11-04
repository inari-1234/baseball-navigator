# Live Observation → State → Decision Contract (v1.0)

## Purpose and scope
Source-linked game observations are normalized to a deterministic event stream; the current state is a replay projection. This repairs the failure where screenshot analysis omitted match completion and let old June points drive July-or-later recommendations.

**Not an OCR system.** A human/assistant visually extracts visible values, marks unknowns, and attaches screenshot filename or exact user report. CI can validate extracted-data consistency, not pixel-reading correctness.

## Events
Required for each event: contiguous `seq`, unique `event_id`, `kind`, `source.kind` (RAW_SCREEN / USER_REPORT / USER_CORRECTION), `source.locator`, and `period` (year/month) except CORRECTION. Screenshot observation should include its visible clock when present.

- `SCREEN`: branch ACCEPTED, complete five-point resource counters (or do not emit a resource snapshot), money if visible.
- `MATCH_SCHEDULE`: unique match IDs with opponent and month, **not** played evidence.
- `MATCH_ATTEMPT`: match_id, period, opponent if first sighting, attempt number, score and branch ACCEPTED or REJECTED. First rejected 0–1 and second accepted 3–0 are two entries for one match.
- `MATCHES_COMPLETED`: direct user correction that period's matches are over, even if individual scores unknown. Changes remaining SCHEDULED to COMPLETED_SCORE_UNKNOWN.
- `TRAINING`, `ITEM_USE`, `ROLLBACK`: accepted branch can invalidate resource freshness.
- `CORRECTION`: target prior event_id and restricted patch. No implicit overwrite of unreferenced historical facts.

## Derivation and safety
`python3 live_state_engine.py` checks `CURRENT_LIVE_STATE.json` against replay of `LIVE_EVENTS.jsonl`. This projection is the gameplay runtime state; `CURRENT_RUN_LEDGER.yaml` preserves provenance and formal decision checkpoints. June resource screenshots may remain in history but cannot authorize paid actions after a July completion event.

A recommendation must pass `validate_recommendation` checks:
- `based_on_event_seq` equals latest accepted event revision
- nonempty `rule_ids`, all ACTIVE in Decision Contract
- `target_match_id` exists and is still SCHEDULED
- `spend` is within fresh visible resource counters

Example blocked request: `{"based_on_event_seq":7,"rule_ids":["DC-TRAIN-001"],"spend":{"sports":7}}` because post-July Sports is UNKNOWN.

## Confidence and precedence
A raw screenshot proves only visible UI; a user report may correct opponent, match completion, or reset provenance. No screenshot of June is automatically a snapshot of July. When only 'July matches finished' is known, scores and current month remain UNKNOWN. Do not claim a player gained a skill merely because an earlier discarded branch displayed it.

## Operating sequence
1. Extract factual visible fields into an event and quote its locator.
2. Distinguish schedule, result, initial/reloaded branch, current vs historical.
3. Apply explicit corrections to target IDs; replay and compare snapshot.
4. Before advice, run revision, resource, match-completion and ACTIVE-rule checks.
5. Issue one next action with Rule and Fallback, or state the precise unknown.
6. At meaningful checkpoints sync Ledger/Decision Log/Handoff. Append events rather than rewriting the past.

## Limitations
GitHub CI cannot validate the pixels, observe unsent future gameplay, or check every chat-only recommendation. A report of period completion is accepted as user evidence, not invented scores. The engine deliberately preserves these limits.
