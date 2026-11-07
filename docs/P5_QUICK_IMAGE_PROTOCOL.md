# P5 — Image-first QUICK and source-reviewed event drafts (2026-11-07)

## Goal

Reduce repeated pixel decoding and user re-entry **without sacrificing SAVE/LOAD, source chronology, or knowledge continuity**. The module `quick_image_pipeline.py` reuses the already-validated v1.42 screen reader and game-event replay. `navigator_step.py` now accepts optional `--image` and `--image-review` inputs. It is a LOCAL tool; it is not a new ChatGPT-native image connector and does not launch automatically on iOS.

P5 has two paths:

1. **Image-first QUICK**: compute SHA-256, classify one image using existing targeted anchors, and return only supported observations. A within-process hash cache avoids decoding the same bytes twice; the source is hashed on every access to detect changed images. `local_elapsed_ms` is measured, not estimated. No live events are appended.
2. **Verified event preview**: an independently reviewed confirmation record explicitly identifies image hash, accepted branch, current period, time, latest contextual event and expected sequence; only then a candidate SCREEN or HP_OBSERVATION event is constructed. In-memory `live_state_engine.replay` validates it against the *exact* current event history and state snapshot. The result is a dry-run. Formal persistence to GitHub still requires an explicit canonical transaction and the same Run Guard checks.

The current canonical branch is `ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN` at event 10, June PM5:20. A later screenshot alone does **not** identify the restored SAVE anchor. Even if a preview updates visible resources, the action gate remains blocked until SAVE ancestry is source-confirmed.

## CLI

Image only (read-only):

```bash
python3 quick_image_pipeline.py /path/to/ios_screen.png
python3 navigator_step.py "画像を確認して" --image /path/to/ios_screen.png
```

Reviewed candidate (still read-only):

```bash
python3 navigator_step.py "画像を確認して" \
  --image /path/to/ios_screen.png \
  --image-review /path/to/current_source_review.json \
  --expected-event-seq 10 --boot-verified
```

The review file must come from actual inspection of that particular image and accepted-branch chronology. An example **structure only** (never mark as true without inspecting an actual current screenshot):

```json
{
  "schema_version": "1.0",
  "kind": "SCREEN",
  "reviewed_image_sha256": "<SHA-256 OF ACTUAL IMAGE>",
  "expected_event_seq": 10,
  "period": {"year": 1, "month": 6},
  "branch": "ACCEPTED",
  "after_event_id": "<LATEST VERIFIED ACCEPTED GAME CONTEXT EVENT ID>",
  "source_reviewed_current": true,
  "event_id": "P5-REVIEWED-UNIQUE-ID",
  "clock": "PM 5:30",
  "resources": {
    "study": 4, "sports": 25, "play": 25, "nature": 18, "cheer": 80
  },
  "all_resource_values_verified_in_image": true
}
```

**Numbers above are illustrative only, NOT actual current game state.** Human-reviewed screenshot values do not become machine OCR just because a flag is true. For resource-screen drafts, all five values and clock must actually be visible and verified; read-only screenshot recognition does not extract these HUD numbers. Unsupported screen types and incomplete fields are rejected. A different screenshot category cannot be used to inject arbitrary resource values.

For `HP_OBSERVATION`, replace the resource-specific fields with `verified_slot_players`, e.g. `{"P":"石渡"}`, after independently confirming the actual position-to-player mapping on that exact screen. Image geometry is measured, but it is **not numeric game HP**. The latest contextual event ID must be correct; a previously observed screenshot is not a new game-state mutation.

## Image-specific observed scope

| Detected screen | Extracted safely | Not established |
| --- | --- | --- |
| Formation | 9 position bar geometry and graphical fill | Player name, numeric HP %, whether current HP remained unchanged |
| Item-use | Selected-item name and verified '1' stock on recognized fixed layout | Complete inventory, other counters `0/N`, item use or recovery effect |
| Batter/pitcher results | Recognized fixed-font numeric cells if PASS | Match identity, result acceptance, player name, whether the game continued |
| Roster | Recognized page/selected numeric stats where supported | General Japanese OCR, all player names, unverified matching across pages |
| Other screens | Source hash, image size, coarse category | Automatic extraction of unsupported resource values, SAVE lineage |

All outputs carry `action_authorized=false`, `side_effects=false`. Existing knowledge on skill acquisition at fourth session remains unchanged: do not infer that an uploaded skill popup is current committed progress or grant additional skills from discarded rerolls.

## Cache and performance claims

`QuickImageSession` is capped at eight source digests by default (configurable 1–64). It caches **decoded observation JSON** only within one Python process, not user image bytes in GitHub or a private persistent cache. It hashes bytes again before each reuse; files modified in place trigger re-decoding. Same bytes with a different filename reuse the decode while correctly updating the returned source filename. Evicted entries re-decode.

For a local **measured** benchmark:

```bash
python3 quick_image_pipeline.py /path/to/local_screenshot.png --benchmark 9
```

It reports cold first inspection, median and nearest-rank p95 of repeated warm inspections. These figures are LOCAL Python image-read measurements, **not** ChatGPT response time, iOS capture time, network latency or real-world player workflow. CI synthetic image benchmarks do not establish real screenshot accuracy or speedup for brand-new screenshots.

## Review safety and stop conditions

- Any source SHA mismatch, stale event sequence, missing/untrusted branch, invalid time/period, prior contextual event ID, duplicate screenshot SHA or reused event ID blocks the draft.
- The canonical state must exactly equal `replay(LIVE_EVENTS.jsonl)`; otherwise no preview.
- When adding a proposed event, the entire source replay is checked and rejects ignored/stale observations. The event is NOT appended to the real log.
- A returned `PROVISIONAL_ROLLBACK_OR_BRANCH_UNVERIFIED` never authorizes game actions. Do not "repair" the unknown SAVE point by assuming the image proves a particular save.
- If a user reports SAVE/LOAD, game training or a match, route to DELTA/FULL before any next-action recommendation. A screenshot does not itself prove a training occurred.
- P5 does not automate all screenshot ingestion, persist new events to GitHub, or let ChatGPT run image code automatically. A fully connected native low-latency screenshot ingestion loop remains a separate integration task.

## QA

Run Guard + all Python tests including `tests/test_quick_image_pipeline.py`, then explicit source-history comparison, candidate main fast-forward, reread and final main CI. Tests use synthetic image fixtures; **no private user screenshot bytes are put into the public GitHub repository**.
