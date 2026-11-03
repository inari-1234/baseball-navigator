# SAPPORO_SPRINT_STRATEGY.md

## Mission
Primary goal: defeat さっぽこ高校 in Y1 October.
This is a short-horizon sprint route, not the standard multi-year safe route.

## Why the previous run was abandoned
The Y1 August Ogasawara match required two resets before a 2-1 win; prior branches were 0-0 and 0-2. That is not an acceptable combat curve for an October Sapporo target. The previous run is therefore `ABANDONED_FOR_REDESIGN`, not a successful base to continue unchanged.

## Core players
### Batting core: 入江ドゴンジ
入江 is never dropped from a dedicated batting/slugging core-development session merely to obtain a type-affinity bonus.

### Pitching core: 石渡翔人
石渡 is never dropped from a dedicated pitching-development session. The previous strategy deferred pitching too long because early results were strong.

## Special-training participant priority
For each special training, rank candidates in this order:
1. mandatory core player for that session,
2. match between drill and needed ability,
3. type-affinity bonus,
4. growth rank,
5. contribution to the Y1 October lineup,
6. future roster value.

Use separate session types:
- **Core batting session**: 入江 mandatory; optimize the other two slots.
- **Efficiency batting session**: use high-affinity combinations such as 今井 + たき + 岡治 when appropriate.
- **Core pitching session**: 石渡 mandatory; optimize the other two slots for pitching value / affinity / future value.

Do not select a player merely because they are a first-year student.

## Skill reroll policy — confirmed mechanic
A same-save SAVE/LOAD retry produced `ジャストミート` on the fifth attempt. Therefore at least one special-training skill acquisition is rerollable from the same pre-training state.

For targeted core training:
1. SAVE immediately before the special training.
2. Use the intended participants and Cheer setting.
3. Execute training.
4. If the target or an acceptable high-value skill is learned, accept and SAVE.
5. Otherwise LOAD and retry.

Only the accepted attempt counts as committed Sports/Cheer/HP use.
Do not use unlimited rerolls for low-value or non-core outcomes.

## Level-1 policy
Do **not** remain at Lv1 merely to preserve a skill pool.
Current evidence supports treating published skill levels as minimum required drill levels, not exclusive levels.
The advantage of Lv1 is:
- cheaper committed Sports cost,
- early access to useful skills,
- more efficient early ability growth.

Therefore: secure high-value minimum-level skills early when cost-effective, then allow drill progression.

## Batting plan
The largest historical failure mode is low run conversion even when pitching is adequate.

### 入江 target profile
Prioritize a compact October-winning skill set. Candidate order:
- ジャストミート
- スーパーパワー
- 選球眼○
- チャンスに強い

Opponent-handedness skills can replace a lower-value slot if the Sapporo matchup warrants it.
Do not fill the four skill slots with weak early skills simply because they appear first.

### Team offense
入江 alone is insufficient. Build at least two additional credible run producers.
- 今井 is a preferred long-horizon investment because of growth and useful affinity combinations.
- たき / 岡治 can be used for high-efficiency affinity sessions and current lineup contribution.
- Immediate-value low-growth players can remain in the lineup without receiving the same training priority as the core.

## Pitching plan
Treat run prevention as a combination of:
- control,
- breaking ability / strikeout generation,
- velocity,
- intelligence,
- stamina / current HP,
- pitching skills,
- defense behind the pitcher.

### 石渡 early targets
Use Shadow Pitching and other available pitching chains to seek useful early skills such as:
- strong control skill,
- ピンチ○,
- リズムのいい投球,
- handedness matchup skills when relevant.

When individual breaking-ball drills unlock, reassess strikeout-oriented skills.
Do not assume strikeout-machine skills come from Shadow Pitching unless verified.

## Cheer policy
Cheer-ON is reserved for high-value sessions:
- 入江 core development,
- 石渡 core development,
- proven high-efficiency affinity sessions.

For an important Cheer-ON session, pair it with the SAVE/LOAD skill-reroll loop so the committed 20 Cheer is attached to a good result.

## Item policy
Do not over-hoard items in a Y1 October sprint.
Use items when they increase training throughput, match readiness, or core ability before the deadline.
Known live samples from the abandoned run include:
- Taki + sakuramochi: long-hit +4,
- candy: used to restore Taki and Ishiwata from roughly 60% to roughly 80% with two items each,
- coffee x3 total sample: batting +1 / intelligence +9,
- megaphone sample: batting +1 / long-hit +2.

Treat exact effect sizes as samples, not universal constants, unless repeated.

## Match reset policy
### Practice matches
No reset when the match is serving as a combat gate.
A practice match must reveal the true current strength curve.

### Required official matches
One selective reload is allowed only for a close and clearly stochastic required loss.
A clear structural mismatch means return to development if the calendar permits.

### Sapporo
Record separately:
- WIN_STABLE = no-reset credible win,
- WIN_UNSTABLE = reset-assisted win,
- LOSS.

## Milestone gates
These are sprint-management gates, not immutable game rules.

### End of June
- F-grade opponents: stable no-reset wins.
- 入江: at least one high-value targeted skill preferred.

### End of July
- E-grade opponents: stable no-reset wins.
- Offense: repeated games with at least 2 runs.
- Failure state: `BEHIND_PLAN`.

### End of August
- Upper-E / D-grade opponents: credible no-reset wins.
- 石渡: generally in a 0-1 run-allowed band against appropriate tests.
- Offense: 2-3 runs reproducibly, not only on one lucky branch.
- Failure state: `HIGH_RISK` for the October goal.

### September
- Prefectural official route must advance.
- Avoid last-minute HP-consuming special training.
- Protect ace readiness.

### October
- Regional progression and Sapporo defeat.
- Failure state: `GOAL_FAIL` if Sapporo is not defeated by the target window.

## Failure logic
A win alone is not PASS.
Judge whether the team can reproduce the result without resets.
Two clear failures at the same grade under the same strategy require a development change before another meaningful retest.

## FAST live-play output
Once repository BOOT is complete, normal replies should be concise and operational:
- next action,
- exact three participants if training,
- target skill / stat,
- SAVE/LOAD continue or accept,
- one short reason.

Do not perform a full historical or web re-scan unless a conflict, mechanics question, strategic redesign, or explicit user request requires it.
