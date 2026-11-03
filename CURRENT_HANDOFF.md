# CURRENT_HANDOFF

Last updated: 2026-11-04
State: ACTIVE_Y1_MAY_SKILL_BASELINE

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
- Fresh run is active at Y1 May.
- Latest live screen after accepted 入江 skill branch shows Study 0 / Sports 2 / Play 9 / Nature 8 and visible Cheer 13.
- No additional special training is currently affordable from Sports 2.
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

## Y1 May skill-selection live evidence
- Drill: 素振り Lv1.
- Participant set used for reroll sampling: 入江 / 今井 / 芦田.
- User performed approximately 40 SAVE/LOAD retries from the same pre-training state.
- Accepted final branch: 入江 acquired `ミート力アップ` on approximately the 40th attempt; this branch is SAVED and is the current run state.
- 芦田 acquired no skill in the observed approximately-40-attempt sample.
- 今井 produced skill-acquisition events during earlier retries, but those branches were not saved; do not use an exact count as canonical because the conversational counts were not recorded under a controlled attempt ledger.
- No `ジャストミート` was observed in this approximately-40-attempt Lv1 sample.
- Interpretation: this does NOT prove `ジャストミート` is unavailable at Lv1. It shows that targeted `specific player × specific high-tier skill` rerolling at Lv1 had poor observed efficiency in this live sample.
- Operational consequence: do not continue brute-force Lv1 rerolling for a specific high-tier batting skill under the same conditions. Advance development while recording future skill events by drill level and player.

## Exact next action
1. Do NOT attempt another special training while Sports is 2.
2. Continue normal time progression/resource acquisition toward the next scheduled match while preserving Sports.
3. Do not spend scarce Sports on low-value school activity/measurement.
4. Re-evaluate the next special training only after the live screen shows sufficient Sports for the intended drill; use the current displayed cost rather than archive cost assumptions.
5. If a school-activity choice, new-member event, or match decision appears before Sports is rebuilt, apply FAST rules to that live choice instead of forcing a training plan.

## Prohibitions / defaults
- Do not reconstruct missing authority from conversation memory.
- Do not directly execute archived FC7F/FC7FR/Authority rules; only ACTIVE `DECISION_CONTRACT.json` rules are executable.
- Latest live resource counters override stale pre-training values and archived drill-cost assumptions.
- Skill-reroll evidence remains scoped; do not infer universal probabilities from this sample.
- Do not infer player-specific skill-rate causality from 芦田=0 occurrences in ~40 attempts; treat it as an observed sample only.
- Practice matches used as combat gates are not match-result reloaded.
- For route-critical official matches, preserve the first-attempt result as stability evidence; later reloads may pursue achievement but never satisfy STABLE.
- Do not assume breaking-ball drills, recovery facilities, new-member reroll behavior, or exact Sapporo bracket order until resolved by live evidence/contract handling.

## Open UNKNOWNs that matter later
- exact Sapporo October bracket/order — check route/tournament screens by Y1 July and before Sep/Oct;
- new-member reroll reproducibility — small experiment only if a reproducible save point exists;
- skill-reroll probability/generalization — continue scoped sampling by drill level/player; current Lv1 batting sample shows low targeted efficiency but does not establish a universal rate.

## Validation identity
Initial capture was taken from live iOS Ver1.42 screenshots IMG_8894.png through IMG_8906.png on 2026-11-03.
Y1 May accepted batting-skill branch is supported by live screenshot IMG_8912.png and the user's approximately-40-attempt report on 2026-11-04.
Latest resource correction is supported by IMG_8912.png: Study 0 / Sports 2 / Play 9 / Nature 8 / Cheer 13.
The accepted continuation point is the latest `main` commit containing this handoff; re-read remote main at BOOT rather than relying on conversation history.
