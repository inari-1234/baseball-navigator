# Baseball Navigator Agent Contract

## Authority and precedence
1. Live user-reported game state in the current chat is the highest authority for the current run.
2. `CURRENT_RUN_LEDGER.yaml` is the canonical repository state for the latest committed checkpoint.
3. `DECISION_LOG.jsonl` records irreversible or strategically material decisions and their provenance.
4. `SAPPORO_SPRINT_STRATEGY.md` defines the current Y1 October Sapporo sprint strategy.
5. Historical Authority/Handoff/Archive material may provide evidence and prior measurements, but must not silently override current live state or current strategy.

## Boot contract
At the start of a new chat or after context loss, read in this order before recommending actions:
1. `RUN_GUARD_POLICY.yaml`
2. `CURRENT_RUN_LEDGER.yaml`
3. the latest entry in `DECISION_LOG.jsonl`
4. `SAPPORO_SPRINT_STRATEGY.md`

Do not reconstruct the run from conversational memory if these repository files are available.

After BOOT, use FAST operation: keep the loaded state and strategy in working context. Do not reread the whole repository or rerun broad web research for ordinary gameplay turns. Reread/research only when a contradiction, UNKNOWN, strategic redesign, or explicit user request requires it.

## Live delta rule
For ordinary gameplay, ingest only the new delta supplied by the user (screen/report/result), combine it with the loaded canonical state, and recommend the next action.

If a new user report conflicts with the committed ledger, the new live report controls the current answer, and the conflict must be treated as a pending ledger update rather than silently rewriting history.

## Evidence discipline
Do not convert one observation into a global rule.
Do not convert DISPLAYED into ELIGIBLE.
Do not treat reset-assisted outcomes as STABLE.
Do not fill UNKNOWN values by inference when the value is material to the next action.

Evidence priority:
1. iOS Ver1.42 live observation / explicit user report
2. in-game Help/Manual
3. Kairosoft official information
4. current Japanese Wiki
5. English Wiki/community
6. archive/historical run as contextual evidence only

## Recommendation output
For ordinary gameplay recommendations, output the actionable decision first. If special training is recommended, always identify all three participants, Cheer ON/OFF, target skill when relevant, and whether to ACCEPT or RELOAD the result.

Use the current sprint strategy's decision rules instead of improvising an unrelated route.

When the same strategy clearly fails twice, require an alternative rather than a third brute-force repetition.

## Run-state semantics
`STABLE` means the result is supported without match-result reset assistance under the strategy's current Gate definition.
`RESET_ASSISTED` means a desired result was obtained only after match-result reset/retry.
`DISPLAYED` means visible/selectable and does not imply participation eligibility.

## Repository write rule
Do not claim that gameplay state or strategy was saved to GitHub unless a real repository write was completed.
When committing run state, keep `CURRENT_RUN_LEDGER.yaml` and `DECISION_LOG.jsonl` consistent with `RUN_GUARD_POLICY.yaml`.

## Current objective
The active branch objective is Y1 October Sapporo sprint, not the prior safe Y2/Y3 national-title route. Historical safe-route material is evidence, not the execution target.
