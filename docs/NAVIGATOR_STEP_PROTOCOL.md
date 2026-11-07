# Navigator Step P3: source-grounded tactical comparison

## Integration
navigator_step.py is a single read-only Python/CLI entrypoint for comparing next-step *drafts*. It combines TEXT FAST, the present live-state projection, evidence-backed skill knowledge, source-pinned historical drill facts, and the existing action validator. It does **not** operate iOS, run automatically inside ChatGPT, perform an in-game action, mutate event logs, or estimate unmeasured win percentages.

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

Historical group affinity is evidence for testing, not proof of present roster optimality. Failure-mode preference is ordinal, not a claim of expected runs:
- CONTACT: poor contact -> contact training.
- CONVERSION: hits but 0–1 run -> power/high-impact skills.
- ADEQUATE: only if a current-period match is genuinely ready.
- RECOVERY_REQUIRED: only with proven player need, stocked item and fresh player HP.
- UNKNOWN: ask for the minimal current match failure signal; keep conditional comparisons instead of prescribing a paid action.

Skill training checks the experimental fourth-session pattern (about 40 negative rerolls at 1–3, positive popup on four). The exact game-internal counter unit and guaranteed reward are UNKNOWN. A specifically claimed next-fourth session requires *three accepted sessions for that player and drill on a TRUSTED active branch*. Retired screenshots never add current skills. For Cheer ON, return ACCEPT/RELOAD criteria; do not recommend exhaustive reloads at steps 1–3.

## Context trust boundary
Optional caller-reviewed context JSON is divided into failure_assessment, training_readiness, match_readiness, and recovery. Each active part requires:
- verified_for_current_state: true
- source_event_seq: equal to current last_event_seq
- period: equal to current period_floor
- branch: ACCEPTED
- evidence_refs: nonempty source references

The module checks those keys but cannot authenticate the truth of a caller's verified flag. The source-ingestion layer or assistant MUST independently inspect and bind reports/screenshots before setting the flag. Do not infer HP, hidden skill or match playability from older pictures.

Example source-attested context structure (replace placeholders with actually validated current evidence, not fabricated):

    {
      "failure_assessment": {
        "verified_for_current_state": true,
        "source_event_seq": 10,
        "period": "Y1-06",
        "branch": "ACCEPTED",
        "evidence_refs": ["SOURCE_ID_FROM_VERIFIED_CURRENT_REPORT"],
        "mode": "CONTACT"
      },
      "training_readiness": {
        "verified_for_current_state": true,
        "source_event_seq": 10,
        "period": "Y1-06",
        "branch": "ACCEPTED",
        "evidence_refs": ["SOURCE_ID_FROM_VERIFIED_CURRENT_MENU_AND_HP"],
        "available_drills": ["素振り"],
        "ready_players": ["岡治", "今井", "たき"]
      }
    }

Do not submit this sample as though evidence has been inspected.

## CLI
From repository root after actually verifying BOOT:

    python3 navigator_step.py "スキル獲得に向けて何をすべき？" --boot-verified --expected-event-seq 10
    python3 navigator_step.py "次は何をすべき？" --boot-verified --context /path/to/verified_context.json

Current game: rollback confirmed, SAVE anchor unknown -> result BLOCKED_UNVERIFIED_TIMELINE. No item or training is authorized. The output nevertheless includes source-measured costs and historical candidate groups with conditional reasons.

With a trusted state and current-sourced readiness, result may be VALIDATED_DRAFT_REVIEW including exactly one selected validated draft, controlling ACTIVE rule IDs, evidence/knowledge IDs and fallback. action_authorized remains false in all cases, and no game state is modified.

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
