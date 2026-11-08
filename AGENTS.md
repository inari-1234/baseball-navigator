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

## P6 one-phrase project resume and BOOT
A user starting a new chat with a distinctive phrase such as **「野球部ものがたりの続き」** should not have to paste a long handoff text. When the connected GitHub source is available, first read this `AGENTS.md` file, identify this project using the narrow aliases in `PROJECT_ENTRYPOINT.json`, and execute the ordered BOOT immediately. If the Python checkout is available, use `project_bootstrap.py` to verify all seven BOOT files, full `LIVE_EVENTS.jsonl` replay, current goal, active rules, last decision/ledger integrity and mandatory fourth-training evidence. In the established connected P4 GitHub bridge, use the new enum `BOOT` and verify the returned source revision and read-only `boot_report`.

Do not auto-select this project from generic words like 「野球部」 or 「続き」. Do not treat historical skill evidence or an unconfirmed SAVE restore as active state. No repository file can **guarantee** that ChatGPT automatically calls tools on every new chat; the assistant must actually invoke the available connector and report a failure when the canonical source is unavailable. A successful BOOT is not an authorized game action. Use the brief protocol `docs/PROJECT_RESUME_P6.md`. This avoids putting project-restart text, screenshots or private Library references into PUBLIC GitHub request branches.

## Live observation state gate
Screenshots and user reports must be structured as source-linked observations before making recommendations. Use `LIVE_EVENTS.jsonl` as the append-only live event history and `CURRENT_LIVE_STATE.json` as the validated derived runtime state. This is not an automatic OCR tool: the assistant must read screenshots, mark uncertain fields UNKNOWN, and retain provenance.

A screenshot entered after a later state-changing event must explicitly cite the preceding mutation's event_id (`after_event_id`); otherwise it cannot restore resource freshness. A known SAVE rollback excludes all later discarded branch effects from the active timeline, including skills, matches, and player training counts. Unknown rollback anchors block action until a genuine post-rollback screen recaptures state.

An event saying a match is *scheduled* is not proof of a played result. A user report that the July matches have finished closes those schedule entries even when individual scores are unavailable. A discarded first-attempt loss/draw and an accepted reset-assisted win are separate observations; never promote the latter to STABLE.

Before actionable advice, check `CURRENT_LIVE_STATE.last_event_seq`, event ordering, completed periods, and resource freshness. Never reuse June resources after July match completion. On a match result, time change, reload, material resource spending, or correction, ingest the delta before recommending anything. If counters are stale, do not propose resource-paid training; request only the fresh counters actually needed.

When screenshot bytes are accessible and a supported v1.42 formation screen is supplied, use `screen_reader.py` to classify the screen and extract pixel-verified gauge geometry before using `HP_OBSERVATION`. The detector returns positions (LF/CF/...) **without names**; no automatic player identity or game HP is implied. Never append the proposed event until actual roster/selected-player identity, source, accepted branch and chronology are checked. Unsupported screens require manual extraction marked as such. Native v1.42 batter/pitcher **numeric pixel-font** reading is supported only for verified result-screen layouts. Blue batting font 0–8 and pitcher white font 0–9 plus decimal point are covered; unknown glyphs/other scales fail closed. Japanese player-name recognition is NOT supported. Treat extracted results as a draft observation until the match identity, source branch and chronological position are verified. For two batting pages, validate the 9-row sum against displayed team totals before accepting counts; do not silently merge separate matches.

HP gauges are vertical green fill bars. Measure only the green part inside the usable inner track, not the grey border, dark gap, player icon, or team Cheer bar. Bind each observation to a visually grounded player and a source screenshot/branch. A graphical fill ratio is NOT a verified numeric game HP percentage. About 80% is neither full nor almost full. Record HP with HP_OBSERVATION; matches, training, item use and reloads expire prior HP. Do not use an uncertain visual bar to claim a precise HP threshold.

Participant training counts are observations **only for recorded committed sessions**, not lifetime estimates. REJECTED retries and discarded rollback branches never increase the count. Never claim 4th-session skill-point thresholds from a partial record. `training_counts_by_player_drill` is a logged lower bound even on a TRUSTED branch. An exact current-save count requires a direct, explicit `TRAINING_COUNT_BASELINE` user attestation tied by `after_event_id` to the latest accepted context. Never synthesize this attestation from a question, prior run or historical image. An unknown SAVE anchor blocks baseline certification; rollback discards baselines outside the restored lineage. Only `training_count_status(...).exact_committed_count` with an active source certificate may support a fourth-session claim.

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

## Original image backup and public/private separation
For evidence-grade screenshots, keep original bytes and a locator/verification manifest in the user's nonpublic Library workspace; do NOT copy raw screenshots, Library IDs or private locators into this public GitHub repository. A public `EVIDENCE_BACKUP_CHECKPOINTS.jsonl` record may contain source and readback SHA-256 values and verification timestamp, but this proves **only a verification at that checkpoint**, not that the Library object still exists now. Run `backup_verifier.py` against freshly materialized Library downloads at archive acceptance or explicit availability audits; GitHub CI cannot independently access the private Library. During normal gameplay, respond via TEXT FAST without waiting for a full archival audit; any missing original needed for a new material research conclusion must be marked UNKNOWN. See `docs/KNOWLEDGE_PROTOCOL.md`.

## Navigator Step P3: next-action comparison
After the ordered BOOT and before issuing a gameplay action recommendation, use navigator_step.py when this repository Python runtime is available. It compares source-verified training (contact versus power), actually eligible matches and stocked/needed recovery against current state, active DECISION_CONTRACT rules, TEXT FAST routing and the evidence-backed fourth-training skill pattern. Full contract: docs/NAVIGATOR_STEP_PROTOCOL.md; historical drill costs and measured candidate groups: NAV_TACTICS.json, pinned in KNOWLEDGE_MANIFEST.json.

A returned VALIDATED_DRAFT_REVIEW is only a *read-only candidate*; it never operates the game or authorizes an item/training by itself. Unknown SAVE anchors, missing current player HP/readiness, absent training counts, stale revision, unknown exact Cheer cost, unverified inventory, and future scheduled matches block actionable drafts. When blocked, show the blocking state, already verified current-run facts and the smallest evidence needed to resolve it. Do NOT turn a historical drill/participant/Cheer/cost combination into a next-action or conditional execution plan. Historical examples remain research evidence, not executable advice; do not supply them as a substitute for current-run evidence. Do not ask the user to supply the documented fixed drill costs. Do not claim that ChatGPT automatically executes this Python module or that an assistant has run it when it has not.

## P5 image-first QUICK and source-reviewed draft gate
When a new iPhone screenshot is available as actual image bytes in the local model runtime, use `quick_image_pipeline.py` (or `navigator_step.py --image ...`) for a single screen-specific reading; prefer existing category-specific fast anchors over re-running broad HP scans. Repeated identical images may reuse the session's SHA-256-keyed decoded **observation** cache, after rehashing to detect byte changes. This does not permanently store an image or make image content authoritative across SAVE/LOAD.

For **state-changing information**, do not treat a screenshot classification as an accepted SCREEN, TRAINING or ITEM_USE event. `--image-review` requires an independently source-reviewed image SHA, current active branch, explicit period/time where applicable, exact current event revision, most recent accepted context event and all required resource fields or verified formation player mapping. It produces only an **uncommitted dry-run event preview**, using canonical `live_state_engine.replay`; a separate explicitly reviewed canonical transaction is required to persist. Unknown restored SAVE anchor continues to block action even if new resources are displayed. Duplicate image SHA, stale chronology, missing source values or unsupported screen types must fail closed. Full contract: `docs/P5_QUICK_IMAGE_PROTOCOL.md`.

Do not upload private image bytes or private source locators into the PUBLIC GitHub P4 bridge, and do not promise ChatGPT will automatically execute this local code on every user-uploaded image. Present the supported image result as soon as it is available, before expensive repository work.

## P4 ChatGPT GitHub bridge (tool-mediated, not automatic)
When the user asks for a verifiable ChatGPT-to-navigator invocation, use the **connected GitHub tools** and the strict `docs/CHAT_BRIDGE_P4.md` sequence. From a known `main` SHA and latest validated event seq, create/update a `bridge/**` request branch containing ONLY the allowlisted `NAV_CHAT_REQUEST.json` fields: schema version, opaque request ID, one intent enum, expected main SHA and event seq. Do not put chat text, screenshots, hidden HP/players, private Library references or credentials on this PUBLIC repository branch. `.github/workflows/chat_bridge.yml` runs `chat_bridge.py` against the independently checked-out canonical main and prints a bounded JSON response in Actions logs. Read that actual response via GitHub tools; verify request ID, source SHA, event seq, evidence refs, `action_authorized=false`, `side_effects=false`. The bridge NEVER performs in-game operations and NEVER ingests current screenshots.

GitHub Actions has queue latency. Do not require it for every ordinary QUICK chat turn; use the fast source-backed response where feasible. This is not a ChatGPT-native installed plugin or permanent automatic tool registration. If the GitHub integration is unavailable, state that rather than pretending the bridge ran.

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
Only for a current-state validated draft under explicit manual acceptance, specify all three participants, Cheer ON/OFF, target skill when relevant, and ACCEPT/RELOAD criteria. Under any BLOCKED status, never supply an actionable combination of participants, Cheer and cost or claim that a player's unknown count is 0 or 3; report UNKNOWN and the exact recovery gate. For source-pinned P4 SKILL and TRAINING_COUNTS replies, prefer the deterministic `safe_reply` only when `safe_reply_check.status=PASS`. The separate local `check_reply.py` can reject an arbitrary private draft unless it matches that certified rendering exactly; no repository rule can install a guaranteed pre-display hook into ordinary ChatGPT answers. Never claim a free-form reply was checked unless the exact text was actually passed through the guard.
When the same strategy reaches its contract-defined failure trigger, apply the alternative rule rather than brute-force repetition.

## Repository write discipline
Do not claim a checkpoint/strategy/decision was saved unless a real repository write completed.
Keep `CURRENT_HANDOFF.md`, `CURRENT_RUN_LEDGER.yaml`, `DECISION_LOG.jsonl`, `DECISION_CONTRACT.json`, and `RUN_GUARD_POLICY.yaml` mutually consistent.
At meaningful work boundaries, synchronize `CURRENT_HANDOFF.md` before beginning the next bounded action.

## Active objective
The active execution objective is the Y1 October Sapporo sprint. Legacy Y2/Y3 safe-route material is evidence only unless an ACTIVE contract rule explicitly imports it.
