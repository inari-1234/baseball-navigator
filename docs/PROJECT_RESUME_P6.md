# P6 — One-phrase project continuation and verified BOOT (2026-11-08)

## User experience and actual limitation

A new conversation can begin with **「野球部ものがたりの続き」**. No seven-file BOOT list or long handoff note is needed from the user. The connected assistant should identify the project `inari-1234/baseball-navigator`, read `AGENTS.md` first, then perform its ordered BOOT and knowledge-continuity checks. If the GitHub connector and a Python runner are available, `project_bootstrap.py` performs the ordered seven-source read and validation in one call. The P4 GitHub Actions bridge also supports a `BOOT` enum request and returns the verified capsule in its job logs.

**Limit:** a GitHub script or public repository cannot force ChatGPT to execute tools automatically every time a new chat begins. The code provides a deterministic mechanism **once invoked**. A new conversation still depends on the assistant recognizing the user's project phrase and calling the connected GitHub tool. If the connector is missing or the assistant cannot read the sources, it must say so rather than pretend a BOOT succeeded. This is not a globally installed ChatGPT hook or a custom Plugin.

## Project recognition

The public `PROJECT_ENTRYPOINT.json` is a stable, source-controlled **project discovery index**, not a cached game-state snapshot. It records the project ID, repository, authoritative BOOT location, entrypoint and narrowly scoped aliases. Recognition includes the full Japanese title, repository slug, Sapporo opponent and sufficiently distinctive compound references.

Generic phrases such as 「野球部」, 「野球」, 「高校野球の試合」 or 「続きをやりたい」 do **not** independently identify this project. In ambiguous conversations ask which project; do not silently substitute this game's state into unrelated topics.

## One-run BOOT execution

The P6 engine reads `AGENTS.md` first, checks the declared ordered BOOT section and reads the next authorities **in order**:

1. `RUN_GUARD_POLICY.yaml`
2. `DECISION_CONTRACT.json`
3. `CURRENT_LIVE_STATE.json`
4. `CURRENT_HANDOFF.md`
5. `CURRENT_RUN_LEDGER.yaml`
6. `DECISION_LOG.jsonl` (validates chronological sequence and latest decision)
7. `SAPPORO_SPRINT_STRATEGY.md`

Then it regenerates `CURRENT_LIVE_STATE.json` from **all** `LIVE_EVENTS.jsonl` events in memory and demands exact equality. It verifies the locked Y1 October Sapporo goal, required ACTIVE rules, latest decision/ledger version, current handoff anchors, and `knowledge_engine.validate_knowledge` including required experiment/backup attestations. The output has a single versioned BOOT capsule with source revision, file hashes, game-period/resourced state, scheduled matches, historical skill evidence and unknown SAVE ancestry.

If any authority is absent, stale, inconsistent, or the fourth-training pattern has been downgraded, it fails closed. The script does not edit the repository or operate iOS. A `BOOT_VERIFIED_ACTIONS_BLOCKED` result means **BOOT consistency is valid**, not that paid gameplay is safe.

Example from a checkout of `main`:

```bash
python3 project_bootstrap.py "野球部ものがたりの続き" --expected-main-sha "$(git rev-parse HEAD)"
```

The source SHA should be verified at the time the user requests a decision. In the P4 bridge, the SHA is independently checked against the actual checked-out canonical main. An old capsule must not be reused after updates.

## ChatGPT tool-mediated shortcut

The established P4 GitHub Actions route now allows `intent: "BOOT"` in the same strict five-field public request JSON. The user does **not** need to provide those fields; connected tools can derive them from the current repository.

```json
{
  "schema_version": "1.0",
  "request_id": "resume-safe-id-001",
  "intent": "BOOT",
  "expected_main_sha": "<verified 40-char main commit>",
  "expected_event_seq": 10
}
```

The values above are structural examples; the actual main SHA and event sequence must be read afresh. GitHub's public request must never contain images, full chat text, private Library IDs or unverified player details. `.github/workflows/chat_bridge.yml` returns a read-only `boot_report`, with `action_authorized=false`.

Each fresh-chat bootstrap still needs a connector action or equivalent source read. Running an external GitHub Actions job adds queue latency, so a fast normal play turn can directly fetch current BOOT authorities and use the same validation semantics, stating when code validation was not actually run.

## Critical test case from the real project

As of the P6 design snapshot, the canonical record is **Y1 June PM5:20, event seq 10, Sports28, Cheer100** and three future July matches. The timeline reads `ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN`. Do not promote historical accepted 石渡／コントロールアップ or 入江／ミート力アップ to the active branch without post-rollback evidence.

Preserve the *observed* fourth-training skill-popup pattern, about 40 negative rerolls at 1–3, and the six historical image backup attestations. These establish an evidence-backed **experiment**, not unconditional skill acquisition on every fourth training. The public CI cannot verify real-time private Library access.

The capsule's next step is `RECONCILE_RESTORED_SAVE_ANCHOR_BEFORE_PAID_ACTION`; its action authorization is always false. Actual game advice is a subsequent `navigator_step` decision with the current-source and cost/HP gates.

## QA and release

The tests in `tests/test_project_bootstrap.py` cover alias positives/false positives, missing BOOT sources, source-order tampering, replay mismatch, stale commit, missing image backup evidence, fourth-skill downgrade, ledger inconsistencies, inactive rules, and read-only CLI operation. `tests/test_chat_bridge.py` covers P4's `BOOT` roundtrip output and stale event revision.

Every change to the project entrypoint, BOOT engine, P4 bridge or P6 protocol must trigger Run Guard CI, plus an actual read-only BOOT request on a source-pinned GitHub request branch at release acceptance. Reread the main result after fast-forward. A passed CI does not itself create a ChatGPT automatic startup behavior.
