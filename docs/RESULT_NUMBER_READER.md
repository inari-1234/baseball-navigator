# Result-screen numeric pixel reader — iOS v1.42

## Source and processing boundaries

`screen_reader.py` exposes a single screenshot-reading entrypoint and delegates numeric result fields to `score_digits.py`. A `BATTER_RESULTS` screen returns five visible rows of `at_bats`, `hits` and `rbi`. The top page has batting-order rows 1–5; the bottom page has rows 6–9 plus a team total. A `PITCHER_RESULTS` screen returns displayed appearances/innings count, hits allowed, runs allowed, ERA as a display string, W/L and K/BB.

All results include per-field status and are **not** a match result, a named player observation, a confirmed date, or an accepted reset branch. The parser never mutates `LIVE_EVENTS.jsonl`.

## Algorithm

- Supports exact, native **2622 × 1206** iOS v1.42 screenshots only. Rescaled result images return UNSUPPORTED rather than guessing.
- Uses exact source-verified monochrome pixel glyph masks (blue palette 29,73,153 or 40,72,147; white stats glyphs 255,255,255), extracted from tiny single-character regions of historical supplied screenshots.
- Recognized blue digit alphabet: 0–8. **Blue 9 remains unsupported** until a trusted example exists. White digit alphabet: 0–9. No English/Japanese general OCR is involved.
- Unknown pixel glyphs, missing ink, out-of-bounds/incorrect screen categories yield null and PARTIAL_UNVERIFIED. No zero by default.
- Batter team totals use a two-digit 41px + 41px glyph pair with a shared center column, not generic connected components.
- `reconcile_batter_pages(top,bottom)` sums all 9 rows for three numeric columns and checks against displayed team total; this checks arithmetic only and explicitly reports `match_identity_verified:false`. It cannot prove that two pages belong to the same attempt.

## Actual historical screenshot probes (local, no source PNGs committed)

| Screenshot | SHA-256 | Grounded numeric outcome |
|---|---|---|
| IMG_8922.png | b776a76dc1402a909f2ab56581b2dc0c754ce97d923d98cf1d37bd7195d01c82 | Top five batter rows |
| IMG_8923.png | 86ebd1236fa02b64fb6af905ac272ad93a1da2fe3cd4c09f313a2b085f1f6aff | Bottom four; team 23 AB, 5 H, 1 RBI |
| IMG_8924.png | f06d6cefa38a0329fcaff2f9b9f409fbe894cc64d145619a987d2df82d84f2e9 | Pitcher: displayed 6, 1 hit, 0 runs, ERA .75, W3 L0 K4 BB1 |
| IMG_8926.png | 29cd90d8876131377c9c4f05fb779a4f5f3c4d99a9e09dca05cfe82fd969571d | Top five batter rows |
| IMG_8927.png | 365d5d9bbbfd99224549941a7bcdcebefd420407670782ca7a14c53a3630c694 | Bottom four; team 25 AB, 8 H, 5 RBI |
| IMG_8928.png | 79d789059eb563b2137168f51c1c11c474d0c4a15c9ea4f415ff6838eeeff302 | Pitcher: displayed 6, 3 hits, 1 run, ERA 1.20, W4 L0 K5 BB2 |
| IMG_8876.png | be4223f30b725d3f8337215b445cb90a458793507f7f37c3184532babe1636ad | Alternate verified dark-blue palette; five batter rows |

Local probe over available screenshots: 19/19 **batting-result pages** and 11/11 **pitching-result pages** returned COMPLETE for the fields in scope, including a palette variant and additional 4/7 glyph samples. This is a small non-independent corpus; CI does **not** contain the private screenshot bytes. CI exercises synthetic glyph and invariant tests, not automated Japanese image understanding.

## Safety / usage

To read a native screenshot in an environment with Python and Pillow 11.3.0:

```bash
python3 screen_reader.py IMG_8928.png
```

The JSON result includes source SHA-256, screen_type and numeric_results. If a digit is unsupported, do not fill it from previous screenshots, neighboring players, inferred scoreboard or team totals. Do not attach player names or assume current match/date/branch without separate verified evidence. ERA and W-L may reflect cumulative season stats, not necessarily the most recent game only.

## Next scope

Japanese player-name/label recognition requires separately validated templates or model-level recognition with source-level correction support; screen result numeric extraction is not a substitute. True game HP remains visually uncalibrated. The current post-July live run remains UNKNOWN until a fresh accepted screen is received.
