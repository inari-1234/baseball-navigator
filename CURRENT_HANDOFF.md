# CURRENT_HANDOFF

Last updated: 2026-11-04
State: ACTIVE_POST_JULY_RECONCILIATION — BLOCKED_ON_CURRENT_COUNTERS

## Canonical runtime
Read `AGENTS.md`, `RUN_GUARD_POLICY.yaml`, `DECISION_CONTRACT.json`, `CURRENT_LIVE_STATE.json`, this handoff, ledger/log, then Sprint strategy. The event log `LIVE_EVENTS.jsonl` is the underlying evidence, not a separate conflicting current state.

## Confirmed
- Objective: Y1 October Sapporo.
- User explicitly confirmed **all July matches are already over**. July tournament registrations for まんるい・花さか・生南 are historical, never upcoming.
- Two grounded June reset pairs: 生南 initial 0-1, accepted 3-0; 花さか initial 0-0, accepted 6-1. Both count as RESET_ASSISTED, not STABLE.
- Latest older resource screenshot: Y1 June PM5:40, money 15,980; Study 4 / Sports 28 / Play 25 / Nature 18 / Cheer 100. These numbers are **STALE** after July.
- Current exact month/time, Sports, Cheer, HP and next match: **UNKNOWN**, do not reconstruct from June or assume current month is July.
- Initial batting core 入江, pitching core 石渡, secondary 今井; these are older roster anchors and not newly measured current stats.
- Skill-point accumulation / 4th committed drill threshold is an EXPERIMENTAL user hypothesis, not a verified hidden mechanic.

## Why prior gameplay advice failed
AI analyzed screenshots and match reports but never committed their temporal deltas to an executable current-state model. It subsequently advised preparing for July matches already finished and reused June points for unverified later actions.

## Audit v1.2 corrective boundary
- Cause-owner code: `live_state_engine.py`; tests: `tests/test_live_state_engine.py`.
- Correctly restored SAVEs prune superseded branch skill, item, match and training-count effects. Unknown rollback anchor blocks unsafe actions until a new screen is confirmed after that rollback.
- Screens in the same month do not refresh resource counters after a gameplay change unless `after_event_id` identifies that change.
- Committed per-player training counts are tracked **only from recorded TRAINING events**, not inferred from 40 SAVE/LOAD experiments. The hidden skill-point hypothesis stays OPEN.
- Old-month match registration is not an actionable upcoming match; Cheer ON costs must be checked.
- No current post-July screen has been supplied; the current exact time and resources remain UNKNOWN. No fresh playing advice is authorized yet.
- Image-to-data recognition remains manual; CI verifies data replay and fixed visual transcription fixtures, not OCR accuracy.

## First safe continuation
Do not recommend a training with cost or a July match. Ask only for a **current** resource/calendar snapshot when gameplay resumes, then append its sourced SCREEN event, re-run the event projection, update handoff and use the latest revision for the next action. No repeated request for historical July scores is required to establish July completion.

## Non-negotiable FAST checks
1. Treat screen reading as manually extracted observations, not automated OCR.
2. Keep planned/played and first/reloaded branch separate.
3. Respect explicit later user corrections.
4. Old resource counters expire after any later match or rollback.
5. Every recommendation must use latest event revision, ACTIVE rule IDs and fallback.
6. A validator PASS proves structured files obey these invariants; it does not independently prove the screen was read correctly.

## Boundary
Repo change is the ingestion/reconciliation owner; `Excel-Tests` is not mutated. Re-read remote main on restart.

## Live observation replay v2 audit boundary (2026-11-04)
- Reviewed the image-source → event → replay → action-guard chain against real July-completed / June-stale counter failures.
- Engine now preserves discarded branch IDs but removes reverted training, skills, item deltas and current match results. A first-attempt match result remains audit history when the later accepted branch is reset-assisted.
- Rollback source is explicit SAVE_CHECKPOINT or screenshot explicitly marked as savepoint. If unknown, timeline is UNKNOWN_AFTER_ROLLBACK; no actionable decision until an anchored recapture.
- Same-month old screens, past-period match recommendations, missing Cheer cost, unverified item inventory and omitted item selection are rejected by the action guard.
- All training counts are only confirmed in-log non-reverted executions; historical totals and hidden skill points remain UNKNOWN.
- Pixel extraction accuracy is not proven by CI. Manual image comparison/source verification is still required; do not claim it has been automated.
- Final v2 check: Run Guard, Decision Contract, event replay and 47-case regression on candidate branch; advance to main only after these PASS and re-read main.

## HP gauge grounded-reading boundary (2026-11-04)
- Inspected actual user's `IMG_8932.png` (2622×1206). Stone-pitcher 石渡's selected formation bar: inner track y543..594, green from y557..594 at x≈1300. Green graphical fraction 37/51 ≈72.5%, uncertainty 67..78% for ±1px; NOT an exact in-game HP value. Dark top and external frame are not fill.
- `HP_OBSERVATION` stores player-identity evidence, source, period, branch and bar geometry or direct user numeric report. Uncalibrated bars cannot satisfy exact numerical HP gates or FULL/NEAR_FULL claims. HP is invalidated on match/training/item/rollback.
- No current post-July HP image exists: actual present HP is UNKNOWN, historical June IMG_8932 must not be promoted as current.
- CI verifies source-structured numerical geometry, chronology and action guards, NOT pixel segmentation, character recognition or true gauge-to-HP calibration.

## HP correction and acceptance completion
- A later source-linked USER_CORRECTION can replace only an earlier `HP_OBSERVATION.entries` extraction, not unrelated match/score events. The original raw event persists in the append-only event log; derived state includes `hp_corrected_by_event_id`.
- Image-reading limitation remains: measured pixel segments are manually extracted. No automation is claimed to identify the player or derive exact game HP from a bar. Historical IMG_8932 is not current post-July HP.
- Final acceptance evidence: Guard + Decision Contract + replay + expanded HP regressions on candidate and final main.

## Screenshot pixel-reading v1 implementation boundary (2026-11-04)
- `screen_reader.py` is the code owner for deterministic iOS 1.42 full-screen formation gauges. It classifies relevant result/list/world screen kinds but **does not read text or scores**.
- Native screenshot `IMG_8932.png` (2622x1206, SHA256 d3966cd2762b991774e98e5b69feb48f069f7123447ef41fab7a2cf1aedca299) was read in the cloud working environment: 9/9 formation positions found. Graphical green fill: LF/CF/RF/P ~70.6%, SS/2B ~80.4%, 3B/1B/C ~90.2%. These are graphics, NOT game numeric HP and NOT fresh after July.
- The same actual image was independently probed at 1311×603 and 1808×832 (nearest-neighbor scaling); all nine tracks detected at each scale. A structural-candidate evaluation fixed an earlier half-size detection failure.
- 91 existing PNG screenshots were classified locally (no image bytes uploaded into the repo). Categories included 1 formation, 19 batter results, 11 pitcher results, 1 tournament, 39 world/overlay, 20 unsupported; **all category labels have not been independently human-reviewed**.
- 14 synthetic reader tests + 62 preexisting tests run in CI. `propose_hp_event()` requires explicit verified position→name mapping and timeline anchor and is only a draft; the parser never writes `LIVE_EVENTS` by itself.
- Remaining: automatic Japanese name recognition and numeric OCR; calibration of graphical bars to actual game HP; current post-July images. Do not claim automated general screenshot transcription.

## Batting/pitching result-number reader v1 (2026-11-05)
- Cause owner: `score_digits.py`, integrated with existing `screen_reader.py:read_image`. No external OCR service/driver; supported native 2622×1206 exact two blue palettes (29,73,153 and 40,72,147) plus white stat font. Unknown/unseen glyph is NULL, never a substituted number.
- Actual local historical-image probe: all 19 batter result pages and all 11 pitcher result pages returned COMPLETE for their supported numeric fields. One batter screenshot (IMG_8876) uses alternate dark blue palette; two others introduced 4/7 glyphs. Validation set contains previously uploaded images and may be correlated; it is not an independent generalization estimate.
- Manual gold examples: IMG_8922+IMG_8923 match (23 at-bats, 5 hits, 1 RBI); IMG_8926+IMG_8927 match (25 at-bats, 8 hits, 5 RBI). IMG_8924 pitching: displayed 6, 1 hit, 0 runs, ERA 0.75, W3 L0 K4 BB1. IMG_8928: displayed 6, 3 hits, 1 run, ERA 1.20, W4 L0 K5 BB2.
- CI uses synthetic pixel-font fixtures and invariant tests; actual user images are NOT checked into the repo. Source screenshot digests and restrictions in `docs/RESULT_NUMBER_READER.md`.
- Remaining limitations: player-name/Japanese text recognition, score or winner detection, redacted/unseen blue 9 glyph, resized result screens, differing game versions/layouts and automatic identity/accepted-branch linkage.
- This is a **historical extraction capability**; JULY matches remain reported COMPLETED, scores UNKNOWN, post-July resources/HP UNKNOWN. Do not populate current state from older images.
