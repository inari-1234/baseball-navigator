# Navigator Step P3: source-grounded tactical comparison

## Integration
Use [the P7-H entry](NEXT_ACTION_P7H.md) for user-facing next-action replies. navigator_step.py supplies its internal comparison and a read-only diagnostic CLI. It combines TEXT FAST, the present live-state projection, evidence-backed skill knowledge, source-pinned historical drill facts, and the existing action validator. It does **not** operate iOS, run automatically inside ChatGPT, perform an in-game action, mutate event logs, or estimate unmeasured win percentages.

Ordered AGENTS.md BOOT must be complete. Source of truth:
1. text_fast.TextFastEngine.plan: intent, revision, BOOT and DELTA routing.
2. knowledge_engine.validate_knowledge + KNOWLEDGE_CLAIMS.json: valid fourth-session experimental evidence, never current unverified skill ownership.
3. NAV_TACTICS.json, pinned separately in KNOWLEDGE_MANIFEST.json: historical drill Sports costs and sample participant groups.
4. CURRENT_LIVE_STATE.json: active branch, current resource balance, match periods, inventory and only *committed* training sessions.
5. live_state_engine.validate_recommendation or knowledge_engine.validate_skill_recommendation: proposed action validation.

## Concrete options

| Candidate | Grounded historical cost and lineup | Required for live action draft |
| --- | --- | --- |
| Contact ON | 素振り Sports6 Cheer20; 岡治・今井・たき (45% affinity) | Current HP/readiness, drill menu, resources, verified SAVE anchor |
| Contact OFF | 素振り Sports6; same group | Same; skill drops with Cheer OFF remain UNKNOWN |
| Power ON | ダンベル Sports7; 芦田・今井・入江 | Same plus *exact current Cheer ON cost* (unverified for this drill) |
| Power OFF | ダンベル Sports7; same group | Same; ability improvement candidate, not proven skill-drop candidate |
| Match | A scheduled opponent | Current match period and explicit match-day, player and opponent readiness |
| Recovery | Explicit current item and player | Current HP, verified inventory, sourced need and branch |

Historical group affinity is research evidence. Training eligibility requires a current source-reviewed selection of three distinct participants, justified for the October objective, and a current Cheer purpose. See the [P7-H input contract](NEXT_ACTION_P7H.md).

Failure-mode preference is ordinal, not a claim of expected runs:
- CONTACT: repeated low-hit or heavy-strikeout results -> contact training.
- CONVERSION: repeated 4–7 hit, 0–1 run games -> power/high-impact skills.
- ADEQUATE: only if a current-period match is ready and reliably beatable.
- RECOVERY_REQUIRED: only with proven player need, stocked item, fresh player HP, verified recovery effect and an otherwise blocked high-value action.
- UNKNOWN: ask for the minimal current match failure signal; keep conditional comparisons instead of prescribing a paid action.

Skill training checks the experimental fourth-session pattern (about 40 negative rerolls at 1–3, positive popup on four). The exact game-internal counter unit and guaranteed reward are UNKNOWN. A specifically claimed next-fourth session requires *exactly three source-certified current-save sessions for that player and drill*, via the `TRAINING_COUNT_BASELINE` plus subsequently accepted trainings, on a TRUSTED active branch. Three logged events alone are only a lower bound. Retired screenshots never add current skills. For Cheer ON, return ACCEPT/RELOAD criteria; do not recommend exhaustive reloads at steps 1–3.

## Context trust boundary
Optional caller-reviewed context JSON is divided into failure_assessment, training_readiness, match_readiness, and recovery. Each active part requires:
- verified_for_current_state: true
- source_event_seq: equal to current last_event_seq
- period: equal to current period_floor
- branch: ACCEPTED
- evidence_refs: nonempty source references

The module checks those keys but cannot authenticate the truth of a caller's verified flag or item-effect claim. The source-ingestion layer or assistant MUST independently inspect and bind reports/screenshots before setting the flag. Do not infer HP, hidden skill or match playability from older pictures.

See [the current context and evidence format](NEXT_ACTION_P7H.md#source-reviewed-training-inputs).

## CLI
For internal diagnostics from repository root after actually verifying BOOT:

    python3 navigator_step.py "スキル獲得に向けて何をすべき？" --boot-verified --expected-event-seq 10
    python3 navigator_step.py "次は何をすべき？" --boot-verified --context /path/to/verified_context.json

Current game: rollback confirmed, SAVE anchor unknown -> result BLOCKED_UNVERIFIED_TIMELINE. No item or training is authorized. The P3 internal candidate comparison can contain historical costs/groups, but the ChatGPT-facing P4 bridge MUST suppress all blocked candidate fields (including historical participant names, Cheer and costs). Respond with only the blocking status and evidence needed for current-run reconciliation; never turn a conditional internal candidate into a recommended sequence.

With a trusted state and current-sourced readiness, result may be VALIDATED_DRAFT_REVIEW in the internal Python result, with exactly one selected draft, controlling ACTIVE rule IDs, evidence/knowledge IDs and fallback. The diagnostic CLI suppresses candidate details. action_authorized remains false in all cases, and no game state is modified.

## Acceptance tests
- BOOT, stale revision, unknown rollback and incomplete source must all block paid advice.
- Drill costs pinned to manifest, no invented power Cheer ON cost.
- Deficient contact vs poor conversion must change priority without invented numerical run estimates.
- A fourth-round claim must not arise from discarded skill popups or missing counts.
- No inventory inference from visible 0/N counters; recovery requires fresh ownership and target HP.
- No game action for matches scheduled in future periods.
- Read-only and delta messages cannot trigger action candidates.
- All existing GitHub Run Guard, contract, replay, backup and knowledge gates remain PASS.

GitHub Actions proves the deterministic Python behavior, not chat tool auto-invocation or iOS game execution.
