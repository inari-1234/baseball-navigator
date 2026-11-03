# RECOMMENDATION_ENGINE v1.3

## Objective
Link each live decision to the championship reverse roadmap, route unlocks, HP, resources, first-win recruits, current weakness, and uncertainty.

## Pipeline
1. ingest live delta (date/time, money, 4 research points, Cheer, HP, opponent menu, unlocks)
2. resolve relations (opponent→recruit→next school; drill→stats/affinity; facility→combo; date→deadline)
3. apply hard constraints (deadlines first; no HP-burning drill immediately before key games; live overrides public)
4. score opportunity cost and generation relevance (Y2/Y3 roster longevity matters)
5. choose one primary action + one fallback trigger
6. append the observed delta to Authority; do not invent missing values

## Current strategic state
- goal: no-carryover national championship; safe deadline Y3 Aug
- current: Y2 Feb, D-level ほこだて defeated 3-0; next C benchmark is 北の海
- unresolved high-value route: 手巻(E) → サ・ラール → 川田卓
- main development need remains batting, but E 8-0 and D 3-0 show improvement
- 石渡+早川 provide two-pitcher operational depth
- 青山浩三 is an immediate outfield batting candidate

## Guardrails
- school-activity Cheer gain is random: one activity → re-read Cheer
- strikeouts alone do not define pitcher decline; judge runs, walks/HBP, hits, and repeat trend together
- special drills are paused before important games if HP cost would lower win probability
- facility expansion is optimized by location+price+continuous footprint; price is not globally fixed
