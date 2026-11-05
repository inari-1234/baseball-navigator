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

## Native roster-list page classification (v1.2, 2026-11-05)

`read_image()` now recognizes the **page header only** for native iOS 1.42 player-list screenshots as `ROSTER_LIST`. It returns `roster_page.page_index` (1–6) and `status=PAGE_ONLY`; Japanese names, abilities, roster ordering/scroll offset and player identity remain UNVERIFIED. Never map a visible row to a player using page number alone. No roster content is automatically ingested into the current live state.

Two fixed header ROIs are checked: the source-derived “選手一覧” mask and the page-number mask. The supported pixel masks were derived from original, user-provided `2622×1206` screenshots. Thresholds require a close title match, a close page-digit match and a distinct second-best distance. Unsupported scale, absent title, changed font/color and ambiguous page indicator return no roster detection. This is not generic OCR.

Actual-image local comparison (original PNG bytes stay in Library, **not GitHub**):
- Positive: `IMG_8894/8895` → 2/6, `IMG_8896/8897` → 1/6, `IMG_8898/8899` → 3/6, `IMG_8901` → 4/6, `IMG_8902` → 5/6, `IMG_8904` → 6/6: 9/9 page-only.
- Negative: `IMG_8926`, `IMG_8927`, `IMG_8928` batter/pitcher result screens: 3/3 rejected as roster.
- Sources include SHA256 `IMG_8894=216984a4e3ce56e65cb152eacaae168d3a3188dc455bca5a9c27bccc2b239a48`, `IMG_8902=e86445f53656491cc21dbc34b14850a6d5792ef04ef10795290e6a13cc371a9c`. New layouts remain unverified.

## Unrecognized tens-glyph correction (v1.2)

`_read_batter_number()` now distinguishes a genuinely empty tens position from a **present but unrecognized** blue pixel-font glyph. The latter returns `None`, causing `NEEDS_REVIEW` for that batting page; a team-total failure also prevents nine-row acceptance. The tens ROI excludes the ones ROI's first column. Verified historical samples show 0 source-blue tens pixels in each single-digit field on `IMG_8926` and 1150 in the `25` at-bats total's tens cell on `IMG_8927`. Unsupported blue 9 remains unsupported. No optimistic substitution or automatic player binding has been added.

GitHub Actions Run Guard for candidate code `e978187fa802ae96025dd21c798dc9e8f81eb1ff`: [run 41931474550](https://github.com/inari-1234/baseball-navigator/actions/runs/41931474550), guard/contract/replay PASS and 90 unittest cases PASS. Synthetic unit fixtures do not establish unseen-source recognition accuracy.

## Roster numeric ability reader (v1.3, 2026-11-05)

Source owner: `screen_reader.py`. It now extracts **numeric ability fields only** on native iOS Ver1.42 `2622×1206` pages `ROSTER_LIST` 2/6 and 3/6. The existing page-header classifier is required: no recognized page, changed scale, or unsupported layout yields no numeric records.

- Page 2: `roster_batting_values.rows[1..7]` each contains `visible_row`, `batting`, `slugging`, `running`.
- Page 3: `roster_pitching_values.rows[1..7]` each contains `visible_row`, `velocity_kmh`, `control`, `breaking`.
- Both types return `status=PASS` only if every numeric glyph in all seven visible rows is source-verified. On any unknown glyph (including unobserved `9`), missing value, or unexpected extra leading digit: the affected field is `null`, `status=NEEDS_REVIEW`, and its row is listed in `errors`. Do not silently truncate a two-/three-digit value.
- Exact source-derived navy-pixel font signatures 0–8 are used; no general OCR, font scaling, rank E/F OCR, player-name mapping, scroll-position alignment, roster merging, in-game timestamp inference or live-state mutation is claimed. `names_verified`, `player_identities_verified`, `ability_grades_verified`, and `live_state_current` are all `false`. The JSON includes the source image SHA256.
- The number reader is shared by the two page-specific APIs; the only differences are independently grounded column positions and field names.

Actual-source review (screens in the user's Library, not placed in the repository; each native 2622×1206):
| Image | Type | SHA256 | Manually cross-checked numeric cells |
| --- | --- | --- | ---: |
| IMG_8894.png | batting 2/6 | 216984a4e3ce56e65cb152eacaae168d3a3188dc455bca5a9c27bccc2b239a48 | 21/21 |
| IMG_8895.png | batting 2/6 | 808f0ca72d81934cc1b83983fbb2ed71bc8cc106dc104abb98e57707b06fce98 | 21/21 |
| IMG_8898.png | pitcher 3/6 | 2dbf3a0ea4d6c65f7ac950c75afc5c7df960c80c78548864eba6cecf1357083b | 21/21 |
| IMG_8899.png | pitcher 3/6 | 03368ca8c1d5f994a331c37a4dcf634c4e10f8f50a3a696ee26773d1052a6637 | 21/21 |

**84/84 is a same-source, source-family check, not an independent blind benchmark or unseen-game/font accuracy guarantee.** Screens 8894/8895 and 8898/8899 overlap in roster content, so this count is per visible numeric cell, not independent people. The generated code uses no private screenshots as test fixtures; CI uses synthesised silhouettes and state replay. For a new screenshot, review page and field consistency before accepting a roster observation.

The current gameplay state is not changed. July matches remain complete and the present calendar/resources/HP are UNKNOWN. Future work requires independently corroborated row→player identity/scroll offset and new screenshots for unseen glyphs/layouts, plus separately grounded matchup/scoreboard recognition.


## Source-linked roster identity joining (v1.4, 2026-11-05)

The function `screen_reader.link_verified_roster_pages(name_pages, ability_pages, *, run_id, snapshot_evidence, confirmed_same_snapshot)` links numeric draft observations to **manually verified names** using portrait pixels visible beside each roster row. It does **not** recognize Japanese text, infer a persistent identity from portraits alone, alter gameplay events, or refresh the current live state.

1. Supply native iOS v1.42 2622×1206 page 1/6 images with an independently checked `verified_names` mapping for all seven `visible_row` positions. The same player can occupy a different row after scrolling.
2. Supply page 2/6 or 3/6 ability images and explicit `run_id`, `snapshot_evidence` and `confirmed_same_snapshot=True`. The same-snapshot assertion must be grounded in source capture chronology, not inferred from avatar similarity. Page header and numeric glyph verification reuse `read_image()`.
3. Compare exact foreground RGB inside the native portrait ROI (x=822..885, y=row top−30..+39) while ignoring white/cyan row backgrounds. A name match must score ≥0.70 and lead the next-best candidate by ≥0.20. Duplicate faces assigned to distinct names, inconsistent repeated-name portraits, unknown avatars, invalid numeric pages, or contradictory overlapping stats fail closed.
4. Return `PASS_DRAFT` only for fully consistent records with both SHA256 sources, verified-name evidence, visible row, field values and portrait score. This still requires independent manual acceptance and is never automatically written into `LIVE_EVENTS.jsonl` or player state. `NEEDS_REVIEW` exposes no accepted records; missing snapshot attestation or verified names is rejected.

**Local real-image evidence boundary.** Manually labeled page 1/6 screenshots `IMG_8896.png` SHA256 `1352027472c9bab5dcfa2480501b2d1b183c1a5df7e2af0c83444da9a8923357` and `IMG_8897.png` SHA256 `0c7b3e667f702e554efe09579b2ccccf63388b0af91a631a8acf2108dc968bbc` were matched against ability pages `IMG_8894.png`, `IMG_8895.png`, `IMG_8898.png` and `IMG_8899.png` (their hashes are recorded in the v1.3 section). **28/28 visible row portraits** mapped unambiguously to nine manually labeled players. Lowest score: 0.791. Lowest best-vs-second margin: 0.491. These are checks on a known screenshot family, **not** proof of unseen-layout generalization or Japanese OCR. The PNG bytes are in the user's Library, never GitHub.

CI uses synthetic portraits and covers scrolling, source hashing, missing attestation, unmatched avatars, duplicate identities, inconsistent verified labels and repeated-stat conflicts. This does not alter the current post-July state, which still lacks a fresh calendar/resources/HP snapshot.


## Closed-set Japanese roster-name image templates (v1.5, 2026-11-05)

`match_verified_roster_names(reference_pages, target_page, *, run_id, snapshot_evidence, confirmed_same_snapshot)` is a **known-name image-template matcher**, not open-vocabulary Japanese OCR. The caller must provide complete, **independently manually confirmed** seven-row `verified_names` labels on supported native page 1/6 screenshots, along with an explicit same-snapshot/run attestation. The source labels are the only vocabulary. Unknown names remain `null`.

- Extract dark neutral ink from native page 1/6 name text ROI x=922..1351 and per-row y=(361,452,542,633,723,813,904)−26..+35. The ink mask is foreground-relative and works on the white and cyan backgrounds seen in the original sources.
- Compare per-row pixel-set Jaccard against the per-name image templates. Match only if similarity ≥0.70 and the next-best margin ≥0.20. Reject conflicting repeated templates, two different names with near-identical templates, duplicate matched names in one target screen, unsupported pages/scale, invalid label coverage and target==reference SHA256. Output is `PASS_DRAFT`, `PARTIAL_DRAFT` or `NEEDS_REVIEW`, never a live accepted name observation.
- Every row retains `source_image_sha256`; recognized rows also retain `name_reference_sha256`. A draft must still be manually reviewed, and must NOT be automatically provided to `link_verified_roster_pages` as a verified name map or appended to `LIVE_EVENTS.jsonl`.
- Source-bound local probe: the seven manually read names in `IMG_8896.png` (SHA256 `1352027472c9bab5dcfa2480501b2d1b183c1a5df7e2af0c83444da9a8923357`) were used as templates against `IMG_8897.png` (SHA256 `0c7b3e667f702e554efe09579b2ccccf63388b0af91a631a8acf2108dc968bbc`). **5/5 repeated players matched**, with similarities 1.000, 0.793, 1.000, 0.730, 0.823; **2/2 new names remained UNKNOWN**. These are not independent out-of-run accuracy metrics. Original PNGs are kept in the user's Library, not the repository.
- CI synthetic-name tests check reordered rows, partial and all-known draft results, missing snapshot attestation, self-reference, incomplete labels, duplicate target names, conflicting reference templates and unsupported targets. No Japanese font model or general OCR is introduced.

A separate local review of several saved batting/pitching panels and game/menu screenshots did not establish a safely identifiable **match final-score screen**. Existing batter totals and cumulative pitcher fields MUST NOT be promoted into game score, match winner, opponent name or accepted/reset branch. Next scoreboard extraction needs a directly labelled native final-score screen plus second independent example.


## Item use menu: observed selected item only (v1.7, 2026-11-05)

`screen_reader.read_item_use_page(image)` recognizes exactly one supported native iOS Ver1.42 `2622×1206` item-use layout. `read_image()` emits `screen_type="ITEM_USE_MENU"` and the draft `item_use_page` with image-source SHA256. This function **does not** read a complete item inventory, execute item use, determine effect category/amount, infer player identity, or refresh the current game's item stocks.

- Screen anchors: source-derived navy text fingerprint for the fixed `アイテムを使う` header and white text fingerprint for fixed `所持数` caption. If either differs, screen classification is unsupported. No screenshot bytes or entire text lines are stored in the repository.
- Item name: only a fixed white-text fingerprint for the visible **`チョコレート`**. Unseen item names return `selected_item_name=null`.
- Selected-item stock: only the source-confirmed numeral **`1`** from the bottom-right `所持数` field. Other digits/amounts return `selected_item_stock=null`. The per-slot `0/1`, `0/2` counters are distinct *assignment* quantities; do not treat them as inventory or evidence of a completed use.
- Output status: `PASS_DRAFT` only if both known name and known stock are recognized, otherwise `NEEDS_REVIEW` with explicit field errors. `stock_scope="SELECTED_ITEM_ONLY"`, `stock_glyph_scope="KNOWN_ONE_ONLY"`; `full_inventory_verified`, `selected_player_verified`, `event_time_verified` and `item_use_confirmed` are always `false`. No action may be authorized from this draft alone.
- Actual uploaded positive `IMG_8972.png` SHA256 `c5ae334bd764fbecdba68ba0aafc03a300b6e5ccfb58074f32e601793903cd67`: all 4 masks exact Hamming distance 0; selected `チョコレート`, bottom `所持数 1`. The visually read page is 1/12, player 芦田はじめ, 2年, but **the code does not recognize those fields automatically**. The Confirm button is visible; it is not a confirmed ITEM_USE event.
- Negative `IMG_8971.png` SHA256 `de88e4b7fe160910ee10b543bc547f45239635fc120136bcddab3844bf6fc197`: general game main-menu screen; correctly rejected by the item-use template (header Hamming distance 113; stock-caption distance 127).
- Both screens visibly show `1年6月 PM5:20`, which is **historical** relative to the recorded post-July state (July matches are complete, current time/resources/inventory stale). Nothing is appended to `LIVE_EVENTS.jsonl` or `CURRENT_LIVE_STATE.json`.

The source family contains only one positive example, so this does not establish broad accuracy over other items, amounts, resolutions, fonts or selected players. CI builds source-derived synthetic binary glyph silhouettes, tests the known item/stock draft, unknown item/count rejection, missing anchors and unrelated scale, native `read_image()` dispatch/source SHA, and fingerprint bit-width integrity. Future samples: item menus showing stock counts other than 1; item names other than チョコレート; a before/after Confirm sequence with verified branch and measured effects. Keep new glyphs and effects UNKNOWN until independently checked.
