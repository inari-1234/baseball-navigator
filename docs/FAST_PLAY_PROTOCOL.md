# FAST PLAY protocol v1.0 (2026-11-06)

## Purpose
Reduce time to first **source-grounded gameplay observation**. Do not run full GitHub research or change code while a player is waiting for a simple image reading. Separate the QUICK, DELTA and FULL paths.

## QUICK — default for screenshot interpretation
1. Load the exact image once, keep SHA256. If its hash was already observed in the uninterrupted chat, reuse the prior image interpretation unless reconsideration is requested.
2. Route with cheap native image anchors before costly image scanning. `screen_reader.read_image` checks item-use layout, roster page and result-panel signatures before the nine-position formation/HP search. Unknown formats still use formation fallback and fail closed.
3. Only run the selected screen-specific field decoder. Return known values first and label unsupported names/digits/branches UNKNOWN. Do not scan unrelated historical screenshots or GitHub code just to explain what is visible.
4. Distinguish visible item-slot counters `0/N` from separately verified stock. A visible confirmation button is not evidence an item was consumed.

## DELTA — only when gameplay state changed
1. Compare observation to last validated `CURRENT_LIVE_STATE.last_event_seq`, accepted branch and last mutation.
2. Ingest only grounded changed fields. Unchanged facts are reused; source SHA and chronology are retained. A new current screenshot does not retroactively verify prior branches.
3. When source evidence supports a state transition, append to `LIVE_EVENTS.jsonl` and replay into the projection. For a material correction, synchronize ledger, decision log, and handoff in one validated commit.
4. Action recommendations additionally require ACTIVE rules and `validate_recommendation` over fresh constraints. A reading alone is not authorization.

## FULL — explicitly triggered development/audit
Run only for user-requested implementation, unsupported layout/glyph, major uncertainty or correction, completed match, period boundary, material unlock, or explicit audit. Develop on fix/candidate, run regression and Run Guard, fast-forward main without force, reread main and CI. Avoid mixing FULL into routine image replies; give supported observable facts without delay.

## GitHub/interaction latency discipline
- Follow `AGENTS.md` ordered BOOT at the beginning of a new chat or after context loss. This protocol does not bypass its required checks.
- In the same uninterrupted chat, reuse already loaded unchanged authorities instead of rereading all BOOT files for each screenshot. Recheck the relevant revision when planning an action.
- Batch independent source reads and avoid repeated fetches of identical SHA and files.
- Present the concise useful image result before extended code research. Never claim background processing.
- Keep a compact top-of-file CURRENT_HANDOFF authority section; older superseded notes are audit history.

## Safe stop
Unknown screen/glyph: `NEEDS_REVIEW`. Unconfirmed player identity or SAVE point, stale resources, unverified inventory, or stale state revision: no paid/actionable instruction. Existing observations can still be reported.

## Acceptance and measurement
Deterministic CI checks that item/roster/score screens do **not** execute the HP gauge scan, while formation screenshots still do; no recognition of previously unseen characters is asserted. Measure wall-clock reader latency on identical native screenshots (median and high percentile) separately from time to first chat answer and GitHub CI time. Do not claim numerical speedup without before/after measurements.

## Current boundary
Y1 June PM5:20 current screenshot follows user-confirmed rollback; restored SAVE anchor unknown. Y1 July matches are SCHEDULED. Four item-slot icons are visible but not a fully verified inventory. Relevant rules: DC-PROC-001, DC-PROC-002, DC-INGEST-001, DC-STATE-001, DC-SCREEN-001, DC-ACTION-001.
