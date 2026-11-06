# Baseball Navigator Agent Contract

## Purpose
This repository is the canonical control surface for the current live run. Historical Authority/Project/Library material is evidence input, not executable policy until reconciled into `DECISION_CONTRACT.json`.

## BOOT
At the start of a new chat or after context loss, read in this order before recommending an action:
1. `RUN_GUARD_POLICY.yaml`
2. `DECISION_CONTRACT.json`
3. `CURRENT_LIVE_STATE.json` — validated projection of `LIVE_EVENTS.jsonl`; check its `last_event_seq`
4. `CURRENT_HANDOFF.md`
5. `CURRENT_RUN_LEDGER.yaml` — provenance, strategy, and historical baseline; do not assume its last initial screenshot is current
6. latest entry in `DECISION_LOG.jsonl`
7. `SAPPORO_SPRINT_STRATEGY.md`

If any required BOOT authority cannot be read, do not reconstruct it from conversation memory and do not recommend gameplay actions. State the missing authority.

## Live observation state gate
Screenshots and user reports must be structured as source-linked observations before making recommendations. Use `LIVE_EVENTS.jsonl` as the append-only live event history and `CURRENT_LIVE_STATE.json` as the validated derived runtime state. This is not an automatic OCR tool: the assistant must read screenshots, mark uncertain fields UNKNOWN, and retain provenance.

A screenshot entered after a later state-changing event must explicitly cite the preceding mutation's event_id (`after_event_id`); otherwise it cannot restore resource freshness. A known SAVE rollback excludes all later discarded branch effects from the active timeline, including skills, matches, and player training counts. Unknown rollback anchors block action until a genuine post-rollback screen recaptures state.

An event saying a match is *scheduled* is not proof of a played result. A user report that the July matches have finished closes those schedule entries even when individual scores are unavailable. A discarded first-attempt loss/draw and an accepted reset-assisted win are separate observations; never promote the latter to STABLE.

Before actionable advice, check `CURRENT_LIVE_STATE.last_event_seq`, event ordering, completed periods, and resource freshness. Never reuse June resources after July match completion. On a match result, time change, reload, material resource spending, or correction, ingest the delta before recommending anything. If counters are stale, do not propose resource-paid training; request only the fresh counters actually needed.

When screenshot bytes are accessible and a supported v1.42 formation screen is supplied, use `screen_reader.py` to classify the screen and extract pixel-verified gauge geometry before using `HP_OBSERVATION`. The detector returns positions (LF/CF/...) **without names**; no automatic player identity or game HP is implied. Never append the proposed event until actual roster/selected-player identity, source, accepted branch and chronology are checked. Unsupported screens require manual extraction marked as such. Native v1.42 batter/pitcher **numeric pixel-font** reading is supported only for verified result-screen layouts. Blue batting font 0–8 and pitcher white font 0–9 plus decimal point are covered; unknown glyphs/other scales fail closed. Japanese player-name recognition is NOT supported. Treat extracted results as a draft observation until the match identity, source branch and chronological position are verified. For two batting pages, validate the 9-row sum against displayed team totals before accepting counts; do not silently merge separate matches.

HP gauges are vertical green fill bars. Measure only the green part inside the usable inner track, not the grey border, dark gap, player icon, or team Cheer bar. Bind each observation to a visually grounded player and a source screenshot/branch. A graphical fill ratio is NOT a verified numeric game HP percentage. About 80% is neither full nor almost full. Record HP with HP_OBSERVATION; matches, training, item use and reloads expire prior HP. Do not use an uncertain visual bar to claim a precise HP threshold.

Participant training counts are observations **only for recorded committed sessions**, not lifetime estimates. REJECTED retries and discarded rollback branches never increase the count. Never claim 4th-session skill-point thresholds from a partial record.

Every actionable recommendation must be checked against `live_state_engine.validate_recommendation` semantics: ACTIVE rules, current state revision, not-yet-completed target, and available fresh resources. If the check fails, no action should be issued. The check is operationally required in chat; repository CI validates the event replay and regression tests, not the pixels of a screenshot or all ordinary chat replies.

## Decision execution requirement
Every actionable recommendation MUST be traceable to the decision contract and MUST expose the controlling ACTIVE `rule_id`(s) in the response.
Every actionable recommendation must also include one fallback/stop trigger from the same decision path.
If no ACTIVE rule applies, label the recommendation path `NO_RULE`; do not silently improvise. For a material decision, record the `NO_RULE` basis before acting. For a reversible ordinary action, run the configured FULL checkpoint before deciding whether a contract amendment is needed.

For irreversible/material decisions recorded in the repository, the decision record MUST contain one of the contract-defined basis modes:
- `RULE_APPLIED`, with non-empty `rule_ids` referencing ACTIVE rules;
- `RULE_OVERRIDDEN`, with `rule_ids`, reason, and revisit condition; or
- `NO_RULE`, with the missing-rule description.

Material decisions include at least: run abandonment/restart, official-tournament reload policy use, facility demolition, primary-core replacement, goal/branch change, and other actions explicitly marked material by the contract.

Repeated `NO_RULE` of the same class is a candidate for contract amendment, not a license for silent improvisation.

## Evidence and knowledge continuity gate
For experiments, screenshots and SAVE/LOAD results, keep immutable observations in `EVIDENCE_EVENTS.jsonl`, test-group histories in `EXPERIMENT_TRIALS.jsonl`, and promoted evidence-backed knowledge in `KNOWLEDGE_CLAIMS.json`. `KNOWLEDGE_MANIFEST.json` contains non-droppable key discoveries. Before claiming a skill mechanic is unverified, before skill-focused navigation and at every handoff/release, execute `knowledge_engine.py validate` or equivalent `validate_knowledge()`. If required evidence, accepted/discarded branch distinctions or a promoted discovery are missing, stop with `KNOWLEDGE_GATE` rather than silently demoting or inventing a conclusion.

Use `knowledge_engine.skill_guidance` and `validate_skill_recommendation` for skill acquisition advice. A 4th-session screenshot confirms an observed result in an experiment but does not itself authorize current-run progress. Only committed training recorded on the active branch counts, and an unknown SAVE restore anchor must block paid actions. Screenshot hashes with `repository_bytes_persisted=false` are *metadata only*: do not claim the original screenshot image bytes are safely in GitHub. Full rules: `docs/KNOWLEDGE_PROTOCOL.md`.

## TEXT FAST (text-only gameplay turns)
After the ordered BOOT, when a text-only game turn needs routing and this repository's Python runtime is available, use `text_fast.py` to distinguish QUICK read-only queries, DELTA reports, actionable requests requiring the canonical validator, and FULL changes/development. Follow `docs/TEXT_FAST_PROTOCOL.md`. Its cached classification is never an action approval. Do not claim the program executed when it did not; without an executable runtime use the same safety boundaries and state that validation was not programmatic. Never skip live state, rules, rollback, or inventory checks.

## FAST mode
Do not execute the full historical research pipeline every turn.
Every turn must run the FAST core:
1. ingest live delta;
2. classify current failure mode when relevant;
3. apply hard constraints and deadlines;
4. select one primary action plus fallback trigger from ACTIVE rules;
5. emit the controlling `rule_id`(s).

Run the FULL checkpoint evaluation only when triggered by the contract (for example after a match, at month boundary, after a material unlock, on `NO_RULE`, or when the user explicitly requests a full audit). FULL evaluation may refresh relation graph, opportunity-cost scoring, roster classification, and unresolved high-value UNKNOWNs.

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
Always include a `Rule:` line naming the controlling ACTIVE `rule_id`(s), and a `Fallback:` line naming the trigger that changes/stops the action.
When recommending special training, specify all three participants, Cheer ON/OFF, target skill when relevant, and ACCEPT/RELOAD criteria.
When the same strategy reaches its contract-defined failure trigger, apply the alternative rule rather than brute-force repetition.

## Repository write discipline
Do not claim a checkpoint/strategy/decision was saved unless a real repository write completed.
Keep `CURRENT_HANDOFF.md`, `CURRENT_RUN_LEDGER.yaml`, `DECISION_LOG.jsonl`, `DECISION_CONTRACT.json`, and `RUN_GUARD_POLICY.yaml` mutually consistent.
At meaningful work boundaries, synchronize `CURRENT_HANDOFF.md` before beginning the next bounded action.

## Active objective
The active execution objective is the Y1 October Sapporo sprint. Legacy Y2/Y3 safe-route material is evidence only unless an ACTIVE contract rule explicitly imports it.
