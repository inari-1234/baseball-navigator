# P7-H local next action

Use a clean checkout at the independently verified canonical commit and event sequence. On Windows, use `py`:

```powershell
py next_action.py "次は何をすべき？" --expected-main-sha $canonicalSha --expected-event-seq $canonicalEventSeq
```

For source-backed action requests, add `--private-context <file>` and `--private-evidence-index <file>`. Keep those files and their sources local. To check proposed wording, add `--reply <utf8-text-file>`. Exit 0 means the exact `safe_reply` passed, either a manual-review training draft or an observation-only stop. Exit 2 means no reply passed. Use `blocking_reasons` to identify the gate that failed. The output never authorizes or executes a game operation.

The command reads `AGENTS.md` and the seven BOOT authorities, replays `LIVE_EVENTS.jsonl` and compares the projection, checks the requested SHA and revision, compares navigator candidates, validates the selected action against the ACTIVE sprint rules, and rechecks the exact reply. A failed prerequisite stops downstream use. Local action rendering recomputes the selected candidate, including its participants, cost, rules, skill target, acceptance, retry and fallback. The public bridge remains enum-only. Ordinary ChatGPT replies require an actual invocation of the local entry for this guarantee.

## Source-reviewed training inputs

Use the [P7-F receipt format](REPLY_GUARD_P7F.md) and [P7-G lineage rules](REPLY_GUARD_P7G.md). Each claim carries `verified_for_current_state`, `source_event_seq`, `period`, `branch` and `evidence_refs`. Review the evidence independently and index its actual hash and the claim hash. A source hash establishes the reviewed bytes. The review establishes what those bytes show.

- `failure_assessment` has `mode` and `match_samples`. Each sample has a distinct `match_id`, `hits`, `runs`, `first_attempt: true`, `opponent_role` (`FARM` or `BENCHMARK`) and `evidence_ref` from this claim. Use at least two games with ≤3 hits or two with source-reviewed `heavy_strikeouts: true` for CONTACT. Use at least two 4–7 hit, 0–1 run games for CONVERSION. A structural contact failure takes precedence. Known game results must agree with replay. A reviewed local report can bind multiple games when their separate ledger events cannot all satisfy P7-G freshness.
- `training_readiness` has `available_drills`, `ready_players`, and `preferred_participant_groups` keyed by drill. A group supplies `players` (three distinct names), `basis`, `evidence_refs` from this claim, `opportunity_cost_favorable: true` and `factors_reviewed` covering mandatory core need, low-level efficiency, drill fit/current ability, growth, type affinity bonus and Y1 October lineup contribution. Use the field names in `strategy_policy.PARTICIPANT_FACTORS`. Use the actual available roster and current condition in the review.
- `training_readiness.cheer_purposes[drill][setting]` is `HIGH_VALUE_COMMITTED_DEVELOPMENT` for ON, or `DRILL_PROGRESSION` or `RESOURCE_PRESERVATION` for OFF. Provide `cheer_on_costs[drill]` only when the catalog lacks an exact ON cost and the current source shows it. Catalog Sports costs are reused.
- A normal ability or skill-target draft can pass with unknown prior counts. Targeted fourth-session retry requires a certified exact three on the current SAVE and a sourced drill/skill pattern. Its display also requires an unmet outcome and verification of the immediate pre-training SAVE and time cost before a retry.

Certified action text covers special training for contact and conversion. Ordinary-practice settings, matches, recovery and other items, school activities, facilities, roster operations and other material decisions lack certified action text. Match and recovery candidates can still be compared internally.

## Current observations and unresolved SAVE history

At seq 10 the world clock and fresh counters are already in the replayed projection. The 19 previously submitted roster screens have indexed metadata. A directly reviewed `roster_chronology` claim can link them to the current world screen without resubmitting the ZIP. It uses the same current-claim fields and a private `LOCAL_FILE` receipt for the user's confirmation. Include the existing `archive_sha256`, `after_world_event_id` and `same_save_no_intervening_gameplay: true`. Supply that same sourced confirmation on subsequent calls at the same revision.

Linking the roster establishes its observed fields for that revision. SAVE identity and pre-load counts or skill acquisitions remain independently unresolved. A real paid-action acceptance run requires established active chronology and fresh sources for the action. If the restored checkpoint is unavailable, use the separately reviewed [current-observation tracking start](SAVE_BASELINE_PREFLIGHT.md#start-tracking-from-the-current-observation). A game change requires a reviewed delta and fresh checks for the fields it invalidated.
