# P7-F: local evidence identity, freshness, content-hash and wording gate

## Independent review issues

P7-E allowed `readiness_evidence_refs` and `failure_evidence_refs` to pass if they were merely nonempty strings. Such a string is **not source existence or content validation**. It also called a source-certified exact three-session count "記録上4回目", even though "記録上" means only a lower bound elsewhere.

P7-F repairs these as a **local-only source-integrity gate** without changing game state, P4's public request allowlist or the meaning of a skill-reward experiment.

## Local source proof

`make_local_verified_draft_packet(..., context=..., evidence_sources=...)` requires both:
- The same verified current `failure_assessment` and `training_readiness` blocks that were passed to the navigator. P3 is recomputed from this local context, and its selected candidate and complete action draft must match.
- A private `evidence_sources` mapping for **every** referenced ID. Each record carries `source_event_seq`, current period, accepted branch, explicit reviewer attestation, source-kind, `sha256`, and claim-specific `reviewed_claim_sha256` binding the exact source-reviewed values.

Supported source kinds:
- `LOCAL_FILE`: `path` to an accessible **private local file** (image, user report or other reviewed observation), plus the expected SHA-256. The engine reads the real bytes and hashes them on every verification. A missing/changed file fails closed. Original bytes and private paths must never be sent to the public GitHub repo.
- `LIVE_EVENT`: `event_id` must exactly match a unique accepted event in `LIVE_EVENTS.jsonl` at the currently selected event revision and game period; the canonical JSON event hash must match the expected SHA-256. Older events or discarded branches are not treated as fresh readiness evidence.

The private packet retains `evidence_receipts` with individual content hashes and reviewed-claim hashes, plus `evidence_receipts_sha256` and `reviewed_context_sha256`. `render_guarded_reply` and `check_reply` require the original private context/source mapping and recompute all receipts; a changed file, replaced ID, altered readiness claim, old revision, edited packet or deleted source is rejected. In a local CLI call, use `--private-context` and `--private-evidence-index` with files stored locally; neither is sent to GitHub Actions.

Bare evidence references, guessed source hashes and unattached historical citations are NOT sufficient. Do not silently invent or retroactively fill these records for the currently unverified save. When proof is missing, `STOP_UNCERTIFIED` still applies: no participant/Cheer/cost plan.

## Exact-count wording

When `TRAINING_COUNT_BASELINE` proves exactly three sessions in the current accepted save and a skill-oriented fourth-session draft passes the other gates, the display is:
"現セーブで確定3回のため、次の特訓が4回目の候補（習得保証なし、根拠 …）".

For a partial log, the read-only count response still says "記録上少なくとも N 回（総回数は未確定）". The two certainty levels are intentionally not interchangeable. The game's hidden counter unit (player vs drill vs level) remains unknown.

## Limits

Source SHA-256 proves identity of bytes, **not that a reviewer correctly interpreted a screenshot or remembered a count**. `reviewed_for_current_state` and the reviewed claim hash are explicit local reviewer attestations, not independently generated game truth. A human reviewer must inspect actual visual HP, participant names, selected drill, current SAVE and branch; unverifiable information stays UNKNOWN. Source certainty must not be exaggerated.

PUBLIC P4 remains read-only and enum-only. It does not carry local evidence files or IDs, and normal ChatGPT replies cannot be universally intercepted. All source-integrity acceptance tests are synthetic; a real current TRUSTED save and current-source evidence have not yet been validated.

## Required regressions

Positive: an accessible local file with matching digest, full claim-attestation and current revision; exact event ID with matching current ledger hash. Negative: nonexistent ID, stale event seq, unsupported source kind, altered file digest, deleted source bytes, modified claim, edited packet receipt hash and post-capture rollback. Prior P7-A to P7-E regression tests must remain passing; main promotion remains candidate-CI→no-force fast-forward→main CI/readback.
