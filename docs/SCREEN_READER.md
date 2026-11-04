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
