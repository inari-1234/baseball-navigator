# Baseball Navigator Agent Contract

## Purpose
This repository is the canonical control surface for the current live run. Historical Authority/Project/Library material is evidence input, not executable policy until reconciled into `DECISION_CONTRACT.json`.

## BOOT
At the start of a new chat or after context loss, read in this order before recommending an action:
1. `RUN_GUARD_POLICY.yaml`
2. `DECISION_CONTRACT.json`
3. `CURRENT_RUN_LEDGER.yaml`
4. latest entry in `DECISION_LOG.jsonl`
5. `SAPPORO_SPRINT_STRATEGY.md`

Do not reconstruct decision logic from conversation memory when these files are available.

## Decision execution requirement
Every actionable recommendation must be traceable to the decision contract.
For ordinary reversible gameplay recommendations, include the controlling `rule_id` in the response when practical.
For irreversible/material decisions recorded in the repository, the decision record MUST contain either:
- `decision_basis.rule_id`, referencing an ACTIVE rule in `DECISION_CONTRACT.json`; or
- `decision_basis.override`, with reason and revisit condition.

Material decisions include at least: run abandonment/restart, official-tournament reload policy use, facility demolition, primary-core replacement, goal/branch change, and other actions explicitly marked material by the contract.

A decision with no applicable rule must be recorded as `NO_RULE` with the missing-rule description. Repeated `NO_RULE` of the same class is a candidate for contract amendment, not a license for silent improvisation.

## FAST mode
Do not execute the full historical research pipeline every turn.
Every turn must run the FAST core:
1. ingest live delta;
2. classify current failure mode when relevant;
3. apply hard constraints and deadlines;
4. select one primary action plus fallback trigger from ACTIVE rules.

Run the FULL checkpoint evaluation only when triggered by the contract (for example after a match, at month boundary, after a material unlock, or when the user explicitly requests a full audit). FULL evaluation may refresh relation graph, opportunity-cost scoring, roster classification, and unresolved high-value UNKNOWNs.

## Authority precedence
1. live iOS Ver1.42 observation / explicit user report for the current run
2. in-game Help/Manual
3. Kairosoft official information
4. current Japanese Wiki
5. English Wiki/community
6. archived historical runs and legacy Authority files

Public/legacy evidence never silently overrides live Ver1.42.

## Evidence discipline
- One observation may establish that event; it does not prove global optimum or causality.
- Preserve `scope` and `sample_n` for generalized empirical claims.
- Do not fill material UNKNOWN values by inference.
- `DISPLAYED` does not imply `ELIGIBLE`.
- A reset-assisted match win is not a stable win.

## Recommendation output
Lead with the next action.
When recommending special training, specify all three participants, Cheer ON/OFF, target skill when relevant, and ACCEPT/RELOAD criteria.
When the same strategy reaches its contract-defined failure trigger, apply the alternative rule rather than brute-force repetition.

## Repository write discipline
Do not claim a checkpoint/strategy/decision was saved unless a real repository write completed.
Keep `CURRENT_RUN_LEDGER.yaml`, `DECISION_LOG.jsonl`, `DECISION_CONTRACT.json`, and `RUN_GUARD_POLICY.yaml` mutually consistent.

## Active objective
The active execution objective is the Y1 October Sapporo sprint. Legacy Y2/Y3 safe-route material is evidence only unless an ACTIVE contract rule explicitly imports it.
