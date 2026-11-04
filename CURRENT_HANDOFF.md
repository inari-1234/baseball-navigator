# CURRENT_HANDOFF

Last updated: 2026-11-04
State: ACTIVE_POST_JULY_RECONCILIATION — BLOCKED_ON_CURRENT_COUNTERS

## Canonical runtime
Read `AGENTS.md`, `RUN_GUARD_POLICY.yaml`, `DECISION_CONTRACT.json`, `CURRENT_LIVE_STATE.json`, this handoff, ledger/log, then Sprint strategy. The event log `LIVE_EVENTS.jsonl` is the underlying evidence, not a separate conflicting current state.

## Confirmed
- Objective: Y1 October Sapporo.
- User explicitly confirmed **all July matches are already over**. July tournament registrations for まんるい・花さか・生南 are historical, never upcoming.
- Two grounded June reset pairs: 生南 initial 0-1, accepted 3-0; 花さか initial 0-0, accepted 6-1. Both count as RESET_ASSISTED, not STABLE.
- Latest older resource screenshot: Y1 June PM5:40, money 15,980; Study 4 / Sports 28 / Play 25 / Nature 18 / Cheer 100. These numbers are **STALE** after July.
- Current exact month/time, Sports, Cheer, HP and next match: **UNKNOWN**, do not reconstruct from June or assume current month is July.
- Initial batting core 入江, pitching core 石渡, secondary 今井; these are older roster anchors and not newly measured current stats.
- Skill-point accumulation / 4th committed drill threshold is an EXPERIMENTAL user hypothesis, not a verified hidden mechanic.

## Why prior gameplay advice failed
AI analyzed screenshots and match reports but never committed their temporal deltas to an executable current-state model. It subsequently advised preparing for July matches already finished and reused June points for unverified later actions.

## First safe continuation
Do not recommend a training with cost or a July match. Ask only for a **current** resource/calendar snapshot when gameplay resumes, then append its sourced SCREEN event, re-run the event projection, update handoff and use the latest revision for the next action. No repeated request for historical July scores is required to establish July completion.

## Non-negotiable FAST checks
1. Treat screen reading as manually extracted observations, not automated OCR.
2. Keep planned/played and first/reloaded branch separate.
3. Respect explicit later user corrections.
4. Old resource counters expire after any later match or rollback.
5. Every recommendation must use latest event revision, ACTIVE rule IDs and fallback.
6. A validator PASS proves structured files obey these invariants; it does not independently prove the screen was read correctly.

## Boundary
Repo change is the ingestion/reconciliation owner; `Excel-Tests` is not mutated. Re-read remote main on restart.
