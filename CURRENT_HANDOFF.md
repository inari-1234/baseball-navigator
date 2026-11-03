# CURRENT_HANDOFF

Last updated: 2026-11-03
State: ACTIVE_Y1_APRIL_INITIAL

## Scope
Fixed-name continuation authority for `inari-1234/baseball-navigator`.
This file carries current restart state only. Historical FC7F/FC7FR/Authority material is evidence in `archive/authority/` and is not executable unless reconciled into `DECISION_CONTRACT.json`.

## Current authorities
Read in this order after `AGENTS.md`:
1. `RUN_GUARD_POLICY.yaml`
2. `DECISION_CONTRACT.json` — active contract version 1.0.0
3. this `CURRENT_HANDOFF.md`
4. `CURRENT_RUN_LEDGER.yaml` — ledger version 5
5. latest `DECISION_LOG.jsonl` entry — seq 5 (`NEW_RUN_INITIAL_CAPTURE_AND_CORE_LOCK`)
6. `SAPPORO_SPRINT_STRATEGY.md`

## Current state
- Active objective: Y1 October Sapporo sprint.
- Fresh run is active at Y1 April AM 9:10.
- Initial live state: money 7,200 yen; Study 0 / Sports 1 / Play 6 / Nature 5; visible Cheer gauge 11.
- Initial roster/state screenshots were captured before scarce development spending.
- Batting core: 入江ドゴンジ — locked from live initial capture under `DC-ROSTER-001`.
- Pitching core: 石渡いなり — locked from live initial capture under `DC-ROSTER-001`.
- Secondary development: 今井. Bridge power: 長島. Bridge table-setter: 芦田.
- FAST operation is mandatory for ordinary live-play decisions; FULL evaluation runs only on contract triggers.
- Every actionable recommendation must expose controlling ACTIVE `rule_id`(s) and a fallback/stop trigger.

## Initial live anchors
- 入江: Y2 LF, batting 80 / slugging 46 / running 30, growth C, がんばり屋.
- 石渡: Y1 P, 87 km/h / control 18 / breaking 16, batting 9 / slugging 4 / running 4, growth C, がんばり屋.
- 長島: Y2 C, batting 15 / slugging 102 / running 25, growth F, おっとり.
- 今井: Y1 3B, batting 10 / slugging 11 / running 4, growth D, ほがらか.
- 芦田: Y2 CF, batting 33 / slugging 15 / running 44, growth E, でしゃばり.

## Exact restart action
Complete the initial formation correction, then build Sports/Cheer toward the first high-value low-level training opportunity without wasting scarce Sports.
Current batting-order defect: 石渡 is displayed 4th despite batting 9 / slugging 4; 長島 is the immediate cleanup candidate from live slugging 102. 入江 remains the central hitter.

## Prohibitions / defaults
- Do not reconstruct missing authority from conversation memory.
- Do not directly execute archived FC7F/FC7FR/Authority rules; only ACTIVE `DECISION_CONTRACT.json` rules are executable.
- Skill reroll evidence remains scoped to the observed Just Meet case (`sample_n=1`); do not claim universal probabilities.
- Practice matches used as combat gates are not match-result reloaded.
- For route-critical official matches, preserve the first-attempt result as stability evidence; later reloads may pursue achievement but never satisfy STABLE.
- Do not assume breaking-ball drills, recovery facilities, new-member reroll behavior, or exact Sapporo bracket order until resolved by live evidence/contract handling.

## Open UNKNOWNs that matter later
- exact Sapporo October bracket/order — check route/tournament screens by Y1 July and before Sep/Oct;
- new-member reroll reproducibility — small experiment only if a reproducible save point exists;
- skill-reroll probability/generalization — record scoped samples only.

## Validation identity
Initial capture was taken from live iOS Ver1.42 screenshots IMG_8894.png through IMG_8906.png on 2026-11-03.
The accepted restart point is the latest `main` commit containing ledger v5, decision-log seq 5, and this handoff. Re-read remote main at BOOT rather than relying on conversation history.
