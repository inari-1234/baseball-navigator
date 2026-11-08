# P7-E: TRUSTED state guarded replies and uncertified-stop behavior

## Critical separation

`TRUSTED` indicates that the active-save timeline is reconciled. It does **not** establish a complete player training count, an eligible three-player group, an exact Cheer cost, or the game's hidden skill-unlock counting unit.

The existing P7-D exact text comparison remains the verifier. P7-E expands its **supported source-bound templates**, not its authority over ordinary ChatGPT messages.

## Verified TRUSTED count answers

A read-only `TRAINING_COUNTS` result is checked against a fresh deterministic `text_fast._read_only_projection` of the same structured state. It lists only `exact_current_counts_by_player_drill` keys carrying a valid active-save source certificate, with the event ID. Recorded accepted sessions without an exact baseline are described only as **at least N**; missing entries are UNKNOWN, never zero. An observed ordinal is not proof that the game's skill-point mechanic counts by player/drill.

## TRUSTED action candidates

The separate **local-only** `make_local_verified_draft_packet(...)` adapter receives an actual P3 `VALIDATED_DRAFT_REVIEW` plus its source-grounded current context. The P3 candidate must be ready, have no blockers, contain current readiness and failure assessment evidence, and have a matching `action_draft`.

Before certification, the P7-E renderer:
- Rechecks `live_state_engine.validate_recommendation` and the knowledge-aware skill validator as relevant.
- Cross-checks drill and Sports cost against the pinned `NAV_TACTICS.json` catalogue; checks Cheer amount and source.
- Requires three distinct participants, a known Cheer ON/OFF state, explicit costs, positive evidence and an accept/reload policy.
- Shows the selected drill and people as a **manual review draft, not an executed action**.
- Mentions a specifically fourth-session candidate only with `EXACT_CURRENT_SAVE` count=3, includes its source certification ID, and states skill acquisition is not guaranteed.

This adapter is deliberately **not** exposed in the public GitHub Actions request. In the current `chat_bridge.py`, `context={}` is intentionally preserved because personal game screens, HP and readiness evidence are not part of the public allowlist.

## Public fail closed

The public bridge may return a `safe_reply` only when `safe_reply_check.status=PASS`. If there is no certified template, `reply_delivery_status=STOP_UNCERTIFIED`; the candidate, selected/provisional targets and manual-acceptance flag are cleared. For action intents, `status=REPLY_NOT_CERTIFIED` and `navigator_status` preserves the underlying result for audit. An uncertified internal `VALIDATED_DRAFT_REVIEW` is **not actionable**.

In ChatGPT replies, null/not-certified means: **no proposed game action, no three-person lineup, no Cheer setting and no spending plan.** Report only the verified status and the minimum missing evidence. Passing GitHub CI does not provide an automatic chat-output hook, and a paraphrase of a certified template is not itself certified.

## Regressions

Synthetic future-TRUSTED states cover: exact count and lower-bound coexistence, missing counts, tampered observations, TRUSTED but insufficient context, source-attested current readiness, full manual draft cost/participants/Cheer/accept-reload output, cost forgery, missing readiness proof and exact fourth checkpoint provenance. A future public bridge-validated candidate without private current context must be suppressed rather than exposed.

No accepted `LIVE_EVENTS.jsonl` record, present `CURRENT_LIVE_STATE.json` source, skills or current game resources are modified. Evidence quality of human count attestation and hidden 4th-session counting scope are still open scientific/operational questions.
