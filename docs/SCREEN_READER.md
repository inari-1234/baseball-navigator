# Screenshot Pixel Reader v1 — Actual-image validation and limits

## Owner and output
The owner is `screen_reader.py` inside `baseball-navigator`; the downstream replay owner remains `live_state_engine.py`. No new external service, OCR model, iOS agent, or game-control component is introduced.

```bash
python3 -m pip install Pillow==11.3.0
python3 screen_reader.py IMG_8932.png
```

Output is JSON: source SHA256, image dimensions, safe screen category, and when recognized as `FORMATION` each position's horizontal center, inner track top/bottom, pixel-green fill top, graphical fill percentage and uncertainty band. Player name is deliberately **UNRESOLVED**. Numeric game HP is always `null`.

## Algorithm (actual supported view)
For iOS Ver 1.42 `2622×1206` or proportional full-frame screenshots, anchor nine expected formation slots, search around each for the common gray cap + dark inner track + gray rim signature, then:
1. Evaluate matching structural candidates against a continuous bottom-up bright-green fill; reject candidates with discontinuities. This prevents a half-size-downscaled false track.
2. Refine horizontal center using the green run edges rather than assuming the exact template coordinate.
3. Count green rows within the **inner track**. Report the ratio and a boundary-error interval; do not count outer frame/dark headroom as fill.
4. Require at least 8/9 trusted slot templates or return `UNSUPPORTED`; missing/ambiguous slots are not filled from last time.
5. Treat position as a **field position only**. A manually verified mapping is mandatory before emitting a draft `HP_OBSERVATION` with a named player. The user/assistant must also verify the actual current run, accepted branch and chronology.

Other recognized coarse categories: `BATTER_RESULTS`, `PITCHER_RESULTS`, `TOURNAMENT_LIST`, `WORLD_UI_OR_OVERLAY`. For them the script **does not extract numbers, names or outcomes**. Displayed category is not a completed match event.

## Actual screenshot probe — source bytes kept outside repo
Observed source: user-supplied `IMG_8932.png`, SHA256 `d3966cd2762b991774e98e5b69feb48f069f7123447ef41fab7a2cf1aedca299`, resolution 2622×1206.

| Position | Measured green bar/inner track | Graphics estimate |
|---|---:|---:|
| LF, CF, RF, P | 36 / 51 | 70.6% |
| SS, 2B | 41 / 51 | 80.4% |
| 3B, 1B, C | 46 / 51 | 90.2% |

The same image was probed with nearest-neighbor rescaling to `1311×603` and `1808×832`: 9/9 positions were found in both cases. Graphical ratios differ by a few percent after resampling; report an uncertainty interval rather than substituting a game HP number.

91 mounted screenshots were categorized in a local probe; one was the supported formation view, others included batter/pitcher result screens. These were not individually hand-annotated as a complete classification gold set. Repo CI uses **synthetic** shape fixtures and state-engine integration, not private screenshot bytes.

## Validation and fail-closed boundary
- A player name is never inferred from a position alone; a current roster or clearly selected-player panel must establish it.
- Existing replay demands explicit `period`, `branch`, `after_event_id`, and source locator. Script drafts are never automatically saved into the live timeline.
- A green bar is a graphical fraction only. No proof that it maps linearly to engine HP. Zero-fill draft is omitted because the existing HP observation event schema requires a fill top; graphic zero remains available in the reader's JSON.
- Unsupported aspect ratio, missing cap/rim structure, incomplete formation pattern and noncontiguous fill are rejected.
- Static color/layout template changes in a new game version require fresh pixel evidence, not speculative recognition.

## Remaining
Japanese OCR for actual player names/stat numbers, player identity recognition, HUD resource number extraction, and numeric HP bar calibration remain separate future changes. The current post-July resource and HP state is UNKNOWN.

## Native batting/pitcher numeric result reader (v1.1)

`python3 screen_reader.py IMG_8926.png` now attaches `batter_stats` to the existing category result, and `IMG_8928.png` attaches `pitcher_stats`. All derived stats remain screenshot evidence, not automatically accepted match events.

### Batting result sheets
- Fixed native pixels `2622×1206`; top result page rows 1–5, lower result page rows 6–9 with a final `team_total` row. Each row's `at_bats`, `hits`, `rbi` is extracted from source-observed fixed-font blue numerals and returned with `lineup_slot`. Player names are deliberately omitted.
- Source-observed blue glyph coverage: 0,1,2,3,4,5,6,7,8; **9 has no trusted native example yet**. Unknown glyphs return `None` and set `NEEDS_REVIEW` rather than invent a value. Other scales are `UNSUPPORTED_SCALE`.
- `validate_batter_pages(top,bottom,verified_match_id="...")` **only when the two screenshots are independently confirmed to be the same match**. The 9-row at-bat/hit/RBI sums must match the displayed total exactly; otherwise `TOTAL_MISMATCH` and accepted rows remain empty. The caller-supplied match ID is not proof by itself.
- Real mounted evidence: `IMG_8926.png` hash `29cd90d8876131377c9c4f05fb779a4f5f3c4d99a9e09dca05cfe82fd969571d` and `IMG_8927.png` hash `365d5d9bbbfd99224549941a7bcdcebefd420407670782ca7a14c53a3630c694`: 9 summed rows = shown `25 at-bats / 8 hits / 5 RBI`.

### Pitcher result
- Source-observed blue top row: appearances/innings display, hits allowed, runs allowed. White panel: cumulative ERA kept as a decimal string (e.g., `1.20`), wins, losses, strikeouts, walks. White pixel font covers digits 0–9 and the decimal point.
- Real mounted evidence: `IMG_8928.png` hash `79d789059eb563b2137168f51c1c11c474d0c4a15c9ea4f415ff6838eeeff302`: 6 innings displayed, H3 R1, ERA1.20, W4 L0 K5 BB2; `IMG_8924.png` hash `f06d6cefa38a0329fcaff2f9b9f409fbe894cc64d145619a987d2df82d84f2e9`: 6 innings, H1 R0, ERA0.75, W3 L0 K4 BB1. ERA is not interpreted as the single game's ERA without stronger evidence.
- The engine cannot read Japanese names, opponent, reset branch, current calendar or score solely from these numbers. That information requires independently sourced visible text/user report and chronological replay.

### Checks and known limits
- CI uses synthesized font silhouettes and 85 state/image regression tests. Actual screenshot comparisons were run separately from mounted source files; no user PNG is committed to GitHub. The templates were learned from the same observed font family, so this is not a blind accuracy benchmark on new sources.
- Font/layout resolution changes, color shifts, unknown blue 9 and substitute batting rows are not proved supported. Any unknown glyph or incompatible total is `NEEDS_REVIEW`, not PASS. Correct sum does not independently establish correct names or whether a branch was reloaded.
