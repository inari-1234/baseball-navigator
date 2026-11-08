# Evidence and Knowledge Continuity v1.0

## Why
A screenshot proving a skill appeared, an experimental SAVE/LOAD outcome, and a **skill retained in the latest active game state** are different facts. The previous handoff preserved the "fourth training" result as an unverified idea even though the player reported repeated negative and positive trials. This design prevents silent evidence loss, silent downgrades, and unjustified current-run bonuses.

## Storage layers
- `LIVE_EVENTS.jsonl` → `CURRENT_LIVE_STATE.json`: only sourced current game facts. In-game SAVE/LOAD discards rejected effects. This engine is unchanged.
- `EVIDENCE_EVENTS.jsonl`: immutable evidence **metadata**. Six reported screenshots are identified by filename, conversation attachment ID, computed SHA-256 and visible skill. The actual image **bytes are not saved in this repository**; do not claim guaranteed long-term image access. User report text is preserved.
- `EXPERIMENT_TRIALS.jsonl`: one negative *aggregate* for 1–3rd training, ~40 reroll attempts, and two fourth-training positive groups. Multiple screenshots may represent the same trial; no new independent sample count may be inferred.
- `KNOWLEDGE_CLAIMS.json`: evidence-backed observations, source/trial IDs, unresolved generalization questions, accepted-at-reporting skills and applicable navigation policy. The observed fourth-training pattern has status `OBSERVED_PATTERN`, **not** "always guaranteed".
- `KNOWLEDGE_MANIFEST.json`: mandatory IDs which cannot disappear from verification without failing the gate.
- `knowledge_engine.py`: executable validator, skill guidance and knowledge-aware training recommendation preflight.

## Original PNG archive and independently verified backup (2026-11-07)

The 6 referenced historical skill-acquisition screenshot originals were uploaded to the existing user's **Library** under the Baseball Authority workspace (in an `evidence_originals/skill_20261106` subfolder), rather than into the public GitHub repository. Each image was **listed and re-materialized through the Library connector** into a separate location; SHA-256 matched the original and its prior evidence record **6/6**. A private `private_backup_manifest.json` in the same Library folder stores Library IDs, source filenames, original sizes and readback digests. This manifest and the original images must remain outside public Git.

`EVIDENCE_BACKUP_CHECKPOINTS.jsonl` (public metadata) records six matching SHA-256 pairs, a checkpoint timestamp and the SHA-256 of the private manifest, with all private locators omitted. The public `KNOWLEDGE_MANIFEST.json` pins the six checkpoint IDs and requires the handoff marker `BACKUP:BK-SKILL-20261107-01`. `knowledge_engine.validate_knowledge()` confirms complete source/backup correspondence, rejects private locator fields, hash substitution, duplication and the false claim that GitHub stored original bytes.

**Two intentionally separate verification levels:**
1. **CI metadata gate**: `python3 knowledge_engine.py validate`. Confirms internal consistency of evidence ↔ public checkpoint. Cannot access private Library.
2. **Live original-byte gate**: from a local model container that actually re-fetched the Library originals, use `python3 backup_verifier.py --private-manifest /path/to/private_backup_manifest.json --restored-dir /path/to/retrieved --evidence EVIDENCE_EVENTS.jsonl --checkpoints EVIDENCE_BACKUP_CHECKPOINTS.jsonl`. Checks real restored bytes against the original source hashes and the public attestation, and validates the private manifest's own SHA-256.

A PASS in (1) does not prove (2); a successful (2) is a point-in-time observation, not a guarantee of indefinite availability. To reverify later, independently list and re-materialize the Library files again. For new critical evidence, retain both current-game branch attribution and experimental trial records. Never count a discarded screenshot as an acquired active skill. Do not block routine TEXT FAST game answers while doing archival work.

## The current experiment record
The user's May and June screenshots show ミート力アップ and コントロールアップ popup text. The user says all skill acquisitions occurred on the fourth training, while about 40 resets among the first three yielded none. **Only 石渡／コントロールアップ and 入江／ミート力アップ (one acceptance)** were retained *at the time*; other rerolls were discarded. The exact which-of-five Meet Up screenshot was accepted is unknown. The **later June PM5:20 unknown-anchor rollback** means even those two historical outcomes cannot be promoted automatically to the present player state.

For skill advice:
1. Read the validated evidence knowledge (`SKILL-4TH-PATTERN`).
2. Prefer training toward the fourth committed repetition over endless 1–3 reroll experiments.
3. Read `training_count_status` for the player/drill. A count in `training_counts_by_player_drill` is a recorded lower bound only. An exact total requires a direct, explicit `TRAINING_COUNT_BASELINE` user attestation tied to the current accepted save. A user's question about earlier trainings is not an attestation.
4. When the counter is absent, mark **UNKNOWN**, never 0; when the current branch is untrusted, stop paid actions.
5. Claim a specifically fourth committed session only when `training_count_status` reports `EXACT_CURRENT_SAVE` with exactly 3 sessions for that player and drill. Three logged sessions without a certified baseline are a lower bound and must fail closed. Run the standard action validator for resources/HP/inventory/timeline/rule IDs. Even a certified fourth session does not guarantee a skill reward.
6. Reevaluate scoring and roster opportunity cost; the 4th roll is not a guaranteed reward and is not automatically optimal.

## Validation entrypoints
From the repository root:

```bash
python3 knowledge_engine.py validate
python3 knowledge_engine.py guidance
python3 knowledge_engine.py guidance --player 入江 --drill 素振り
python3 text_fast.py "スキル獲得に向けて動いていい？" --boot-verified
python3 -m unittest discover -s tests -v
```

The text-only router calls the knowledge engine for skill advice and runs the knowledge-aware preflight before suggesting an actionable training draft. Merely mentioning the fourth skill theory is not a game mutation. An agent must still complete AGENTS.md BOOT and use the current status gate. No ChatGPT automatic Python hook is implied.

## Release/hand-off gates
- **Missing/duplicate evidence or trial/claim ID** → fail.
- Screenshot without SHA-256 and source attachment reference → fail; falsely declaring git-persisted image bytes → fail.
- Claim lacking links to all its supporting trial evidence → fail.
- Positive fourth-session findings downgraded to HYPOTHESIS or negatives silently removed → fail.
- All five Meet Up screenshots counted as accepted skills → fail.
- Historic accepted skills declared current despite unknown SAVE restoration → fail.
- Missing `KNOWLEDGE:SKILL-4TH-PATTERN` or `KNOWLEDGE:SKILL-ACCEPTED-HISTORICAL` in `CURRENT_HANDOFF.md` → fail.
- Skill navigation without the required knowledge ID → fail.
- Stale revision, missing per-person committed counts or rollback unknown → fail via existing action rules or knowledge gate.

Every change to experimental knowledge requires a new source-linked record, reevaluation of claim status and regression tests. **No file- or image-based conclusions are generated automatically by regex**; the user and assistant must inspect source content.

CI runs the continuity validator on every push as well as existing Run Guard, decision trace and live replay. These assertions protect known critical discoveries, not the completeness of every future insight; future confirmed skills must be added to both the manifest and test fixtures.
