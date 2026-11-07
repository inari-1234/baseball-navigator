# P4: ChatGPT ↔ GitHub Actions ↔ Navigator Step (read-only)

## What the actual integration is

The **already-connected GitHub connector** is the available ChatGPT-to-code transport. It creates a minimal public request file on a `bridge/**` Git branch. The `.github/workflows/chat_bridge.yml` Actions runner independently checks out **current canonical main**, validates that source commit SHA and `last_event_seq` match the request, calls `chat_bridge.py` and `navigator_step.py`, and emits a delimited machine-readable result in the run's **job logs**. ChatGPT retrieves the logs using the same GitHub connector, checks request/commit/revision identity, and writes an answer incorporating the returned status, candidate, rules and fallback.

This is a **real tool-mediated ChatGPT ↔ GitHub ↔ Python round trip**, not an automatically installed ChatGPT-native Plugin, not a Vercel public API, not background gameplay execution, and not an iOS automation bridge. It has GitHub Actions queue latency; never hold a live gameplay instruction hostage to a slow bridge when a source-verified, safe quick answer is available.

## Security and authority boundaries

`NAV_CHAT_REQUEST.json` on the GitHub branch is **public** because the repository is public. It may contain ONLY:
- `schema_version` = `1.0`
- `request_id` = opaque non-personal lowercase ASCII ID (4–64 chars)
- `intent` = `BOOT`, `SKILL`, `GENERAL`, `MATCH`, `RECOVERY` or `STATUS`
- `expected_main_sha` = exact 40-character lowercase Git commit
- `expected_event_seq` = exact current live event revision

Do **not** write conversation text, screenshots, player identities/HP updates, Library IDs, private file paths, secrets, custom commands or source claims to this branch. The strict allowlist rejects extra keys and unrecognized intents. A new user screenshot/skill is ingested through the separate canonical provenance workflow before a bridge request.

The GitHub Actions job uses `permissions: contents: read` and cannot mutate the gameplay repository. The bridge verifies ordered BOOT presence, knowledge continuity and the canonical state revision before returning any result; it always reports `action_authorized=false` and `side_effects=false`. A queued result can go stale after main changes; ChatGPT must match source commit, request ID and event revision **at the moment of using the answer**.

The bridge has no trusted live HP/readiness/extra user context input. Therefore its current canonical answer (Y1 June PM5:20, rollback SAVE anchor unknown) is **conditional only** and will remain blocked for paid actions. Do not manufacture `verified_for_current_state` to get a successful draft.

## P6 new-chat project BOOT shortcut

For a new chat that clearly says 「野球部ものがたりの続き」, use `intent: BOOT`. This returns the source-verified `project_bootstrap.py` capsule with the seven ordered BOOT reads, live replay and fourth-training evidence, rather than the limited P4 next-action snapshot. Read `AGENTS.md` before starting. Inspect and honor the returned `status` and `action_authorized=false`. A blocked savepoint means gameplay paid actions remain blocked.

Only the strict five allowlisted request fields are published; no free-form text is transferred. This is a **connector-initiated** action, not a guaranteed automatic new-chat hook. Details: `docs/PROJECT_RESUME_P6.md`.

## Real ChatGPT GitHub tool sequence

1. At new-context BOOT, fetch `AGENTS.md` first, then the ordered BOOT files and the current `main` commit SHA and `CURRENT_LIVE_STATE.last_event_seq`.
2. Choose one allowlisted intent. Example:
   ```json
   {"schema_version":"1.0","request_id":"p4-smoke-20261107-01","intent":"SKILL","expected_main_sha":"<ACTUAL_MAIN_SHA>","expected_event_seq":10}
   ```
   Here `<ACTUAL_MAIN_SHA>` is a placeholder; the real 40-character SHA must be used.
3. Using the connected GitHub tools, create a request branch `bridge/<opaque-id>` from **that exact main commit**, and create `NAV_CHAT_REQUEST.json` on that branch with the compact, allowed JSON object. The push triggers `Navigator Chat Bridge P4 (read-only)`.
4. Query GitHub Actions for the **matching branch and head SHA**, read the job logs, and extract the single JSON line between:
   `NAV_CHAT_BRIDGE_RESULT_START` / `NAV_CHAT_BRIDGE_RESULT_END`.
5. Reject a failed, incomplete, unrelated or stale run. Check the returned `request_id`, `source_commit_sha`, `state_event_seq`, source status, `action_authorized=false`, `side_effects=false`, and required `SKILL-4TH-PATTERN` when relevant.
6. Summarize **actual tool-returned** `primary_next_step`, `candidate`, `blocking_reasons`, controlling `rule_ids`, `knowledge_refs`, and `fallback`. Never treat `VALIDATED_DRAFT_REVIEW` as a performed action.
7. If current main/state changed, discard the result and recheck; do not silently reply from a stale branch.

For a second intent, update the existing bridge branch's `NAV_CHAT_REQUEST.json` with a new request ID and fresh source SHA/seq. This avoids creating an unlimited number of branches. Do not force-push a branch, delete history, or use `main` as a scratchpad.

## Live gameplay speed

GitHub Actions job startup and logs retrieval require multiple remote calls. This path is suitable for **integration QA, reproducible audits, and source-confirmed decisions**, not as an unconditional preflight on every iPhone screen. For ordinary fast play, if a local code runtime is available invoke `navigator_step.py` directly; otherwise use the BOOT-loaded compact facts and state validation without claiming the remote runner was executed.

Every bridge result is pinned to an exact main SHA/event seq. It cannot update the present game state. Ingestion and evidence storage are separate. An unverified action remains unverified even if the bridge CI completed successfully.

## Development acceptance

- Candidate GitHub Actions: all existing Run Guard, knowledge, event replay and P3 tests plus `tests/test_chat_bridge.py` pass.
- Current canonical skill request returns `BLOCKED_UNVERIFIED_TIMELINE`, `SKILL-4TH-PATTERN`, and a conditional contact group/cost without a current skill grant.
- Malformed/extra/private fields, stale main SHA or event revision are rejected.
- Independently fetch GitHub Actions logs for a **real** request branch created from this conversation; verify request/result round trip and read-only output.
- Confirm no current game state or original image files were changed by that request.
