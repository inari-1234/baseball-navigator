# CURRENT_HANDOFF

Last updated: 2026-11-03
State: READY_FOR_NEW_RUN

## Scope
Fixed-name continuation authority for `inari-1234/baseball-navigator`.
This file carries current restart state only. Historical FC7F/FC7FR/Authority material is evidence in `archive/authority/` and is not executable unless reconciled into `DECISION_CONTRACT.json`.

## Current authorities
Read in this order after `AGENTS.md`:
1. `RUN_GUARD_POLICY.yaml`
2. `DECISION_CONTRACT.json` — active contract version 1.0.0
3. this `CURRENT_HANDOFF.md`
4. `CURRENT_RUN_LEDGER.yaml` — ledger version 4
5. latest `DECISION_LOG.jsonl` entry — seq 4 (`DECISION_CONTRACT_ADOPTION`)
6. `SAPPORO_SPRINT_STRATEGY.md`

## Current state
- Active objective: Y1 October Sapporo sprint.
- Previous run: abandoned for redesign after Ogasawara required reset-assisted recovery; it is historical evidence, not the active save.
- New run: `RESET_PLANNED_NOT_YET_STARTED`.
- Decision contract: ACTIVE, version 1.0.0.
- FAST operation is mandatory for ordinary live-play decisions; FULL evaluation runs only on contract triggers.
- Every actionable recommendation must expose controlling ACTIVE `rule_id`(s) and a fallback/stop trigger.

## Exact restart action
Start a fresh run and capture the initial state before hard-locking cores or committing scarce development resources.
Capture at minimum:
- protagonist Creation Preview and Registered Initial values separately;
- initial roster, levels, growth/personality/fit visible in-game;
- date/time, money, four research-point pools, Cheer;
- currently available special training and opponent/menu state relevant to the first action.

After capture, run the FAST core and apply `DC-ROSTER-001` before naming final batting/pitching cores.

## Prohibitions / defaults
- Do not reconstruct missing authority from conversation memory.
- Do not directly execute archived FC7F/FC7FR/Authority rules; only ACTIVE `DECISION_CONTRACT.json` rules are executable.
- Do not hard-lock 入江/石渡 before the new-run initial capture; they are preferred candidates only.
- Skill reroll evidence remains scoped to the observed Just Meet case (`sample_n=1`); do not claim universal probabilities.
- Practice matches used as combat gates are not match-result reloaded.
- For route-critical official matches, preserve the first-attempt result as stability evidence; later reloads may pursue achievement but never satisfy STABLE.
- Do not assume breaking-ball drills, recovery facilities, new-member reroll behavior, or exact Sapporo bracket order until resolved by live evidence/contract handling.

## Open UNKNOWNs that matter later
- exact new-run initial state — resolve immediately by fresh-run capture;
- exact Sapporo October bracket/order — check route/tournament screens by Y1 July and before Sep/Oct;
- new-member reroll reproducibility — small experiment only if a reproducible save point exists;
- skill-reroll probability/generalization — record scoped samples only.

## Validation identity
Reviewed baseline main before this handoff hardening:
`60b75e643cf3c042416fdc4a10055912edae6e6f`

The accepted restart point is the latest `main` commit containing this handoff and the corresponding `AGENTS.md`; re-read remote main at BOOT rather than relying on the baseline SHA above.
