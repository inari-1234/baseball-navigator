# SAPPORO_SPRINT_STRATEGY.md

## Mission
Primary goal: defeat さっぽこ高校 by Y1 October. This is a short-horizon sprint branch.
The executable rules live in `DECISION_CONTRACT.json`; this document explains the branch intent and targets.

## Success has two axes
- **ACHIEVEMENT**: defeat Sapporo by the deadline, including an official-match branch won after the first-attempt result is recorded.
- **STABILITY**: credible no-match-reset performance. A reset-assisted win is never STABLE.

## New-run initialization
Do not hard-lock the roster before reading the fresh-run state. Capture the initial roster, levels, growth/personality/fit and Creation Preview/Registered Initial for the protagonist.
入江 and 石渡 are preferred core candidates from prior live evidence, but final core lock follows `DC-ROSTER-001`.
If a reproducible pre-new-member save point exists, `DC-ROSTER-002` permits a small 2-3 reload experiment to test whether entrants vary; do not assume it works until live-confirmed.

## Low-level-first + skill reroll
Use low-level training/item opportunities before mass match leveling when their opportunity cost is favorable (`DC-TRAIN-001`).
One Just Meet case changed across SAVE/LOAD retries from the same pre-training save. Treat this as a scoped `sample_n=1` observation: targeted reroll use is allowed, but universal drill/skill probabilities are not assumed.

For an important special-training attempt:
1. SAVE immediately before training.
2. Fix participants and Cheer setting.
3. Execute.
4. ACCEPT a target/high-value outcome; otherwise RELOAD when the expected value justifies real-time effort.
5. Only the accepted branch commits Sports/Cheer/HP.

The four visible skill slots are treated as equipped slots, not a learning cap; do not reload merely because a weak skill was learned if the accepted training is otherwise good. Equip the best four for the matchup.

## Training participants
Score participants by October objective only:
- mandatory core need for the session,
- low-level efficiency,
- drill fit/current ability,
- growth,
- affinity bonus,
- Y1-October lineup contribution.

Post-October roster longevity is excluded from this Sprint score. Affinity bonuses are material, but they are not an unconditional override.

## Offense
Do not use a fixed batting:slugging ratio. Classify the failure mode.
- repeated <=3-hit / heavy-strikeout pattern -> batting/contact (`DC-OFF-001`)
- repeated 4-7 hits but only 0-1 run -> slugging/high-impact batting skills (`DC-OFF-002`)
- scoring adequate for the current gate -> stop marginal training and return to valuable matches (`DC-OFF-003`)

入江 is the leading batting-core candidate. High-impact targets include Just Meet, Super Power, plate-discipline/chance skills and matchup skills where available. Do not assume every skill mapping or minimum drill level beyond verified/public evidence.

## Pitching
石渡 is the leading ace candidate, but investment is symptom-driven.
- repeated control collapse -> control/shadow (`DC-PITCH-001`)
- control acceptable but hard contact/run allowance persists -> velocity/available run-prevention tools (`DC-PITCH-002`)
- pitching keeps the gate winnable while offense binds -> stop marginal pitching investment (`DC-PITCH-003`)

Do not design the October route around breaking-ball drills or recovery facilities that are not actually unlocked.

## Cheer
Cheer ON is for high-value committed development. Cheer OFF is allowed for drill progression/resource preservation. Do not assume ON changes skill-roll probability (`DC-CHEER-001`).

## Matches
Use **high match density × beatable opponents**, not fixed monthly quotas (`DC-MATCH-001`).
New benchmark failure -> farm/develop -> retest. Two equivalent failures under the same method require a method change before another meaningful retest (`DC-MATCH-002`).
Practice matches used as combat gates are not reset (`DC-RESET-001`).

## Official reset policy
For route-critical official matches, always preserve the first-attempt result as stability evidence. Later reloads may pursue ACHIEVEMENT without an arbitrary one-reload cap, but any such win is `RESET_ASSISTED`/UNSTABLE (`DC-RESET-002`).

## Items / recovery / facilities
Use ability items early on low-level October core when valuable; use recovery items when they unlock an otherwise blocked high-value action. Item deltas are samples, not constants (`DC-ITEM-001`).
School activities are resource conversion and random rewards must be re-read (`DC-ACTIVITY-001`).
Facility count is not fixed. Field demolition requires actual replacement/throughput value and is a material logged decision (`DC-FAC-001`).

## Sprint gates
These are operational heuristics, not game rules (`DC-GATE-001`). Reset-assisted results do not satisfy stability gates.

### End of June
- F-grade no-reset wins are routine enough to avoid repeated zero-run branches.
- At least one meaningful low-level core-development/skill attempt completed.

### End of July
- E-grade no-reset wins are credible/repeated.
- Offense can reproduce >=2 runs rather than relying on one branch.
- Verify the practical route toward the October regional/Sapporo encounter; exact bracket/order must not be assumed from legacy evidence.

### End of August
- Upper-E/D benchmark wins are credible without match-result reset.
- Repeated 0-run branches are a RED flag.
- Pitching should make the benchmark winnable; if 0-1 allowed but offense fails, offense owns the next investment.

### September
- Prefectural advancement/title is route-critical.
- Protect official-series HP and avoid unneeded HP-burning training immediately before key games.

### October
- Regional progression and Sapporo defeat are terminal. An October loss is not successful completion of this branch (`DC-GOAL-001`).

## FAST operation
Normal live-play replies run only the FAST core: live delta -> failure-mode classification -> hard constraints/deadlines -> one action + fallback.
Each recommendation should show its controlling `rule_id`(s).
FULL relation/opportunity-cost evaluation runs only at contract checkpoints.
