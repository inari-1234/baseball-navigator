# TEXT FAST v1.0 — executable routing for text-only game turns

Date: 2026-11-06. Source owner: `text_fast.py`, tests: `tests/test_text_fast.py`.

## Purpose and authority
This is a **deterministic routing and safety-preflight helper**, not Japanese natural-language understanding, a strategic optimizer, an automatically installed ChatGPT plugin, or an event writer. It cannot compel the ChatGPT runtime to execute Python. When the repository is available to an agent or CLI, run it before text-only game decision advice; otherwise follow these documented stages and be explicit that the program was not executed.

The `AGENTS.md` ordered BOOT remains required at first turn or after context loss. Do not supply `--boot-verified` until BOOT authorities are actually read. The engine does not itself authenticate the flag. The supplied `CURRENT_LIVE_STATE.json` is a projection of the append-only live events, not a substitute for their audit trail. For game actions, `live_state_engine.validate_recommendation` remains the authority.

## Classifications, not actions

| Example input | Intent | Mode | Output |
| --- | --- | --- | --- |
| `今の試合予定は？` | READ_ONLY | QUICK | READ_ONLY_READY; report source-backed facts and UNKNOWNs |
| `7月は試合予定だよ` | STATE_REPORT | DELTA | INGEST_BEFORE_ADVICE; append only after source/branch validation |
| `試合で勝った` | STATE_REPORT | FULL | INGEST_BEFORE_ADVICE; outcome/branch may trigger full checkpoint |
| `ロールバックした` | STATE_REPORT | FULL | INGEST_BEFORE_ADVICE; savepoint not invented |
| `アイテムを使うべき？` | ACTION_EVALUATION | QUICK | gate state, revision, inventory and candidate |
| `コードとテストしてみよう` | DEVELOPMENT | FULL | FULL_REQUIRED; candidate→tests→main CI |
| `進めて` (without task context) | NEEDS_CONTEXT | REVIEW | No guessed action |

If a message reports a mutation and asks for advice, the source update wins: `INGEST_BEFORE_ADVICE`. Hypothetical and interrogative forms cannot automatically create events. Unsupported or ambiguous phrasing returns REVIEW, not a guessed route. This is a finite, conservative vocabulary; **not** a complete Japanese parser. In mixed messages, inspect the exact claim; a regex route cannot prove whether gameplay happened.

## CLI
From the repository root after ordered BOOT:

```bash
python3 text_fast.py "今の試合予定は？" --boot-verified --expected-event-seq 10
python3 text_fast.py "アイテムを使うべき？" --boot-verified --expected-event-seq 10
python3 text_fast.py "コードとテストしてみよう" --boot-verified
```

`text_fast.py` reads the existing state/contract and emits JSON. It does **not** change live events or snapshot files. A supported action draft can be supplied with `--recommendation candidate.json` but still returns `ACTION_DRAFT_REVIEW` with `action_authorized=false`; user/agent acceptance remains a separate decision. Never present that state as an item actually used or a recommendation actually executed.

The current source state at implementation is Y1 June PM5:20 with a user-confirmed rollback and an unknown SAVE restore anchor, `last_event_seq=10`. Therefore an item-use request must return `BLOCKED_UNVERIFIED_TIMELINE` even when the text classifier recognizes it. The four visible item-slot counters are **not** a fully verified inventory.

## Cache boundaries and latency
The in-process cache stores **only the normalized message's route**. It does not cache:
- gameplay facts or event snapshots;
- account/character/item identity;
- action approval or a validated recommendation;
- freshness, health, resource availability or inventory;
- the contract or latest event revision.

For every turn, the engine checks `last_event_seq`, the supplied expected revision, and the required ACTIVE contract identifiers. For an action draft it invokes the actual `validate_recommendation` every time. An identical question with changed item stock is revalidated; a cached route cannot authorize a stale recommendation.

This avoids unnecessary full historical replay for plain questions, but no numerical ChatGPT response-time improvement has been established. Parser elapsed time, GitHub API latency, model generation time and CI duration are **different measurements** and must not be conflated.

## Test/acceptance scope
`python3 -m unittest discover -s tests -v` and repo Actions should cover at least:
- read-only/decision/state-report/development/ambiguous text classification;
- hypothetical/question vs actual event report;
- mixed report + request requiring ingestion first;
- BOOT/contract missing, stale state, unknown rollback anchor, unknown inventory;
- immutable read-only query never calling action validation;
- repeated matching queries reuse route but re-run action validation against updated inventory;
- successful existing validator yields draft, not automatically authorized action;
- CLI integration using the actual committed state and contract; no source writes.

No automatic game decisions, native ChatGPT response hooks, or external cache persistence are claimed. Only add them after separately verified end-to-end integration and tests.
