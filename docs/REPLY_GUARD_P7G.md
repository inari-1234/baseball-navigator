# P7-G: lineage-aware ledger evidence freshness

## Why this change

In P7-F the `LIVE_EVENT` source event's `seq` had to equal the **latest** `CURRENT_LIVE_STATE.last_event_seq`. Even a harmless `SAVE_CHECKPOINT` added after a genuine match/formation observation would make the older observation unusable. A failure-assessment match source and a later readiness screen also could not both remain valid at once.

P7-G separates two clocks:
- **Source event revision:** the original event's actual `seq` and `event_id`, frozen by its SHA-256.
- **Current review revision:** the latest `last_event_seq` in the reviewed claim and private `evidence_sources` record, refreshed after chronology review.

The source event can be older **only** if it survived the resolved accepted branch and no intervening event invalidated the **specific claim**. This does not make stale HP valid.

## Acceptable sources and intervening events

| Claim | Source event type | Permitted later events while retained in active branch |
|---|---|---|
| `failure_assessment` | ACCEPTED `MATCH_ATTEMPT`, `SCREEN`, `HP_OBSERVATION` | `SAVE_CHECKPOINT`, `MATCH_SCHEDULE`, `TRAINING_COUNT_BASELINE`, accepted `SCREEN` or `HP_OBSERVATION` |
| `training_readiness` | ACCEPTED `SCREEN`, `HP_OBSERVATION` | `SAVE_CHECKPOINT`, `MATCH_SCHEDULE`, `TRAINING_COUNT_BASELINE` |

A new match attempt, match completion, item use, training, known or unknown rollback, or a later correction expires either claim. A newer screen or HP observation expires prior training readiness (but does not automatically erase earlier match-failure analysis). An unexpected event type fails closed rather than being silently classified harmless.

The ledger must have a contiguous revision 1..current seq and unique event IDs. `apply_corrections` and `resolve_active_lineage` are used to check that the source is genuinely present in the active branch; an edited source, discarded branch, unknown rollback, wrong period or wrong branch must not pass. A source-event hash mismatch always stops. An event with source `REJECTED` never qualifies even if retained for research.

The stored private receipt includes both `source_record_seq` and `source_event_seq` (review revision), original event ID in its key, content SHA-256 and reviewed-claim SHA-256. Both contexts and private source records remain pinned to the current revision.

## Scope and limitations

This change does not permit any gameplay action on the present Y1 June restored-save-unknown snapshot. The actual future TRUSTED first-use acceptance remains open: the first time an actual reconciled save exists, test **both** `TRAINING_COUNTS` and `SKILL` and confirm an earlier match result plus a later SAVE do not trigger `LIVE_EVENT_EVIDENCE_EXPIRED_BY_MUTATION`, while genuinely stale readiness does.

A matching hash proves the source event bytes, not that a human interpretation of a screen or the game's underlying skill counter is correct. Current local source review remains required. The public enum-only P4 bridge cannot ingest private evidence and remains read-only.

## Regression acceptance

At least two earlier distinct LIVE_EVENT sources must simultaneously pass in the current branch after a SAVE; adding a harmless schedule must preserve them. Adding TRAINING, ROLLBACK (including rollback that keeps the earlier source), or a new readiness SCREEN must stop the affected claim. A discarded source cannot be resurrected; an edited source cannot be silently reused. Existing repository regression tests must remain green. Promote only after candidate CI and checked no-force main fast-forward, then verify main CI and final readback.
