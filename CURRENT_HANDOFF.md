# CURRENT_HANDOFF

Last updated: 2026-11-05
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

## Native batting/pitching score pixel-reader v1.1 (2026-11-05)
- Scope owner: `screen_reader.py`, pixel matching of **numeric** batting/pitching score fields in native 2622×1206 v1.42 result screens; no Japanese name OCR or other-scale claim. Recognized categories remain `BATTER_RESULTS` / `PITCHER_RESULTS`.
- Two consecutive batting pages can be paired only by an independently confirmed match ID. Top page rows 1–5, lower page rows 6–9 plus team total. `validate_batter_pages()` checks exactly nine row sums against displayed team at-bats, hits and RBI. Mismatch -> TOTAL_MISMATCH and no accepted rows.
- Grounded actual-image probe from supplied accepted June 花さか screenshots: `IMG_8926.png` SHA256 `29cd90d8876131377c9c4f05fb779a4f5f3c4d99a9e09dca05cfe82fd969571d`; `IMG_8927.png` SHA256 `365d5d9bbbfd99224549941a7bcdcebefd420407670782ca7a14c53a3630c694`. Both halves yield 25打数, 8安打, 5打点 and nine-row sum matches.
- Pitcher `IMG_8928.png` SHA256 `79d789059eb563b2137168f51c1c11c474d0c4a15c9ea4f415ff6838eeeff302`: 出場6回 / 被安打3 / 失点1 / 防御率1.20 / 4勝0敗 / K5 / BB2. Earlier `IMG_8924.png` SHA256 `f06d6cefa38a0329fcaff2f9b9f409fbe894cc64d145619a987d2df82d84f2e9`: 6回 / 1安打 / 0失点 / 防御率0.75 / 3勝0敗 / K4 / BB1.
- Blue font observed digit coverage is 0–8, **9 unsupported** and unknown characters fail closed. White pitcher panel font 0–9 plus dot observed. Fixed native layouts only; no generic OCR, no automatic player name, no game-score reconstruction, no proof of beyond-sample accuracy. Font shapes are derived signatures; original screenshots are NOT in GitHub.
- Current post-July time/resources and HP are still UNKNOWN; historical match screenshot extraction does not promote them to current. No new live EVENT was appended by a detector.
- Acceptance requires GitHub Actions Guard + Contract + existing replay + 85-case test suite, read back after main FF. No user screenshots were committed as fixtures.

## Screenshot reader v1.2 continuation boundary (2026-11-05)
- Owner: `screen_reader.py`; existing result-screen numeric parser remains limited to native `2622×1206` iOS 1.42. `_read_batter_number` now distinguishes a genuinely blank tens cell from present unrecognized blue ink, so unsupported glyphs (including blue 9) fail closed rather than losing a tens digit. Two focused regression tests added.
- Implemented **page-only** `ROSTER_LIST` detection from source-derived title plus 1/6–6/6 page-number pixel masks, without Japanese name/ability/stat OCR, player identity, or scroll-offset inference. Three additional regressions test six known pages, missing-header/scale negatives, and provenance output. No new live event or game action.
- Verified original Library images locally: 9 roster screenshots correctly classified by page (`IMG_8894/8895`:2, `8896/8897`:1, `8898/8899`:3, `8901`:4, `8902`:5, `8904`:6); three historical result screens (`IMG_8926`, `8927`, `8928`) rejected as roster. Real-image check is separate from CI, and source PNG bytes are not committed.
- Actual-image hashes: `IMG_8894` SHA256 `216984a4e3ce56e65cb152eacaae168d3a3188dc455bca5a9c27bccc2b239a48`; `IMG_8902` SHA256 `e86445f53656491cc21dbc34b14850a6d5792ef04ef10795290e6a13cc371a9c`. Their canonical storage is the user's Library.
- Verified candidate code SHA `e978187fa802ae96025dd21c798dc9e8f81eb1ff` with GitHub Actions Run Guard [41931474550](https://github.com/inari-1234/baseball-navigator/actions/runs/41931474550): Guard PASS, Decision Contract PASS, all 90 unittest cases PASS, live event replay PASS. Final handoff/doc commits require their own final main PASS/readback.
- Next owner-boundary: extract grounded numerical player abilities and source-linked names using the saved 1/6–6/6 screenshot family with independent gold labels and explicit scroll/roster identity, **not** by filling missing values from earlier pages. Match outcome/score extraction also requires independently verified actual scoreboard sources. No change to Y1-July-complete and stale current-resource gate.


## Source-grounded roster ability numbers v1.3 (2026-11-05)
- Development owner: `screen_reader.py`; only `ROSTER_LIST` page 2/6 (`batting/slugging/running`) and 3/6 (`velocity_kmh/control/breaking`) on exact iOS 1.42 native 2622x1206. Returns seven `visible_row` records per page; values are not associated with any player identity or current runtime.
- Source-derived 5×7 masks of navy ability digits `0..8` are re-used for the two pages; `9` is unobserved. Unrecognized/missing glyph and unexpected extra leading digit fail closed to `null` / `NEEDS_REVIEW`. Scrolled rows, E/F grades, player names, other page numbers, screenshots with other resolutions, and absent resource freshness are NOT inferred.
- Previous original Library screenshots were re-opened and manually checked, with local extraction showing 84/84 matching **visible cell** values across four images (not 84 independent subjects): batting `IMG_8894.png` SHA256 `216984a4e3ce56e65cb152eacaae168d3a3188dc455bca5a9c27bccc2b239a48`, `IMG_8895.png` SHA256 `808f0ca72d81934cc1b83983fbb2ed71bc8cc106dc104abb98e57707b06fce98`; pitching `IMG_8898.png` SHA256 `2dbf3a0ea4d6c65f7ac950c75afc5c7df960c80c78548864eba6cecf1357083b`, `IMG_8899.png` SHA256 `03368ca8c1d5f994a331c37a4dcf634c4e10f8f50a3a696ee26773d1052a6637`. Raw screenshots remain in user Library, not repository. Not a blind new-image accuracy benchmark.
- Candidate code+synthetic tests SHA `84b4c090051bc980a509d5c842c397804db7f6e6`, GitHub Run Guard [41933897933](https://github.com/inari-1234/baseball-navigator/actions/runs/41933897933): 98 tests PASS, Run Guard/Decision Contract/replay PASS. Final documentation+handoff commit still requires final GitHub main CI success and readback.
- Live replay unchanged (`last_event_seq=7`, July matches completed). Current exact month/resources/HP remain UNKNOWN. No gameplay action authorized from historical screenshot numbers.
- Next distinct investigations: obtaining source-grounded player identities (names + scroll/row binding), and match result scoreboard/branch detection. Neither should be guessed from page order. Collect genuinely new `9` and changed-layout samples before expanding glyph support.


## Roster portrait-to-ability source joining v1.4 (2026-11-05)
- Owner: `screen_reader.py`, function `link_verified_roster_pages`. It accepts independently manually verified names for each visible row of roster page 1/6 plus explicit same-run/same-snapshot evidence. It matches portraits to numeric-only page 2/6 and 3/6 observations across differing scroll positions, rather than using row index as permanent player ID. This is NOT Japanese name OCR or general face recognition.
- Strict boundary: exact native iOS 1.42 `2622×1206`, supported header/pages, manual 7-row name labels with source-hash links, explicit `run_id` and `snapshot_evidence`, full numeric-page PASS. Portrait foreground overlap score ≥0.70, best-vs-next margin ≥0.20, no duplicate name portrait, conflicting repeated-name portrait, unknown face or contradictory overlapping stats. Errors produce no accepted combined observations. A clean result is `PASS_DRAFT` and still needs manual acceptance; `LIVE_EVENTS.jsonl` and `CURRENT_LIVE_STATE.json` were not mutated.
- Actual original Library evidence: page 1 name sources `IMG_8896.png` SHA256 `1352027472c9bab5dcfa2480501b2d1b183c1a5df7e2af0c83444da9a8923357` and `IMG_8897.png` SHA256 `0c7b3e667f702e554efe09579b2ccccf63388b0af91a631a8acf2108dc968bbc`. Ability pages `IMG_8894/8895/8898/8899` carry the exact hashes documented in v1.3. A local pixel comparison matched **28/28 visible row portraits** to **9 distinct manually read names**, minimum similarity 0.791, minimum margin 0.491. This is within the prior same-run family only; source bytes were not checked in.
- CI boundary: candidate SHA `a6bdb6ed4d5255d040adc36f39b20e70bcabc80d`, GitHub Run Guard [41983372959](https://github.com/inari-1234/baseball-navigator/actions/runs/41983372959), Guard/Contract/replay PASS, **103 unittest cases PASS** (five new synthetic regressions). Final documentation/handoff and main head need independent final Actions PASS/readback.
- Next bounded investigation: source-verified Japanese name transcription (currently manually labeled), capture-session authority validation, and candidate scoreboard/score recognition. Do not infer current July+ resources or actionable lineup changes from historical initial pages. If a new source has reused portrait sprites, changed scale/layout or unseen glyphs, treat identity as UNKNOWN and request an independent identifier/label.


## Known roster-name template continuation v1.5 (2026-11-05)
- Change owner: `screen_reader.py` / `tests/test_screen_reader.py`. Implemented `match_verified_roster_names` for native 2622×1206 iOS 1.42 page 1/6. Closed-set dark text-template classification uses **independently manually verified** `verified_names` references; no open-vocabulary Japanese OCR. Requires run ID, same-snapshot evidence, correct page, complete reference row labels and distinct target/reference source SHA. Two-stage pixel Jaccard threshold ≥0.70, best/next margin ≥0.20. Reject reference identity collision, ambiguous or duplicate target label and unsupported layouts. `PASS_DRAFT`/`PARTIAL_DRAFT` only; never writes live state nor supplies accepted names to v1.4 automatically.
- Local Library real-image probe: `IMG_8896.png` sha256 `1352027472c9bab5dcfa2480501b2d1b183c1a5df7e2af0c83444da9a8923357` (7 manually read names) was tested against `IMG_8897.png` sha256 `0c7b3e667f702e554efe09579b2ccccf63388b0af91a631a8acf2108dc968bbc` (5 overlapping and 2 new names). **5/5 repeated exact names matched, 2/2 new names stayed UNKNOWN**. Min accepted similarity ~0.730, no new-name inference. This is an in-family check, not general accuracy or live provenance. Original PNGs not in repo.
- Candidate implementation+synthetic tests SHA `bd5b97a6db00f08915adf6ebefad87cbfc3936bb`; [GitHub Actions 41985523999](https://github.com/inari-1234/baseball-navigator/actions/runs/41985523999): 109 tests PASS, Guard PASS, Decision Contract PASS, replay PASS. Final docs/handoff and main commit still require exact-head CI/readback.
- Separate bounded scoreboard source check inspected historical `IMG_8881/8882/8883` (batter/pitcher results), `IMG_8906/8915/8879/8907` (game/menu) and `IMG_8913/8928` (pitcher stats). These sampled images do not supply two independently corroborated **match final-score** views. Do not infer a match winner from the 25/8/5 batting total or cumulative pitcher ERA/W-L. Resolve score blocker by a native final-score/game-end screen with independently verified scores/opponent and first/reload chronology. No scoreboard number parser was added.
- Live state unchanged: `last_event_seq=7`; July reported complete; current exact time/resources/HP UNKNOWN. Next bounded owner: native post-match final scoreboard source, or otherwise direct user-provided target screenshot. Do not use prior screenshots to update current match outcome/branch.
