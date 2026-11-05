#!/usr/bin/env python3
"""Conservative screenshot reader for Kairosoft baseball iOS formation screens.

Pixel geometry is NOT Japanese text OCR, player-name recognition, or numerical
game-HP calibration. Unsupported screens and uncertain pixels fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image

BASE_W, BASE_H = 2622, 1206
# Verified iOS v1.42 formation inner HP tracks in native screenshot pixels.
SLOTS: dict[str, tuple[int, int]] = {
    "LF": (869, 281), "CF": (1296, 266), "RF": (1743, 281),
    "SS": (1090, 381), "2B": (1517, 381),
    "3B": (969, 542), "P": (1301, 542), "1B": (1627, 542),
    "C": (1301, 713),
}
TRACK_HEIGHT = 51


def _cap(c: tuple[int, int, int]) -> bool:
    return 125 <= c[0] <= 181 and abs(c[0]-c[1]) <= 8 and abs(c[0]-c[2]) <= 9


def _green(c: tuple[int, int, int]) -> bool:
    r, g, b = c
    return g >= 210 and g >= r+115 and g >= b+115 and 15 <= r <= 105 and b <= 65


def _inside(c: tuple[int, int, int]) -> bool:
    r, g, b = c
    return _green(c) or (22 <= r <= 65 and 24 <= g <= 82 and 25 <= b <= 89)


def _rim(c: tuple[int, int, int]) -> bool:
    r, g, b = c
    return 52 <= r <= 89 and 55 <= g <= 100 and 55 <= b <= 108


def _find_track(image: Image.Image, center_x: int, top: int,
                sx: float, sy: float) -> dict[str, Any] | None:
    pix = image.load()
    width, height = image.size
    x_radius = max(2, round(16*sx))
    y_radius = max(1, round(8*sy))
    inner_h = max(18, round(TRACK_HEIGHT*sy))
    candidates = []
    for dy in range(-y_radius, y_radius+1):
        yy = top+dy
        if yy-round(9*sy) < 0 or yy+inner_h+round(4*sy) >= height:
            continue
        for dx in range(-x_radius, x_radius+1):
            xx = center_x+dx
            if xx < 5 or xx >= width-5:
                continue
            offsets = (-max(2, round(6*sx)), 0, max(2, round(6*sx)))
            checks = []
            for off in offsets:
                cx = xx+off
                checks.extend((
                    _cap(pix[cx, yy-round(8*sy)]),
                    _inside(pix[cx, yy+round(2*sy)]),
                    _rim(pix[cx, yy+inner_h+round(2*sy)]),
                ))
            if not all(checks):
                continue
            displacement = abs(dx)/max(1, x_radius)+abs(dy)/max(1, y_radius)
            candidates.append((displacement, xx, yy))

    # The nearest template match may have a wrong fill boundary in downscaled
    # pixel art. Test all structural candidates for one solid bottom green run.
    offsets = (-max(2, round(5*sx)), 0, max(2, round(5*sx)))
    for _, xx, yy in sorted(candidates):
        edge_y = yy+inner_h-max(2, round(4*sy))
        if _green(pix[xx, edge_y]):
            left = right = xx
            bound = max(10, round(27*sx))
            while left > xx-bound and _green(pix[left-1, edge_y]):
                left -= 1
            while right < xx+bound and _green(pix[right+1, edge_y]):
                right += 1
            span = right-left+1
            if round(23*sx) <= span <= round(38*sx):
                xx = (left+right)//2

        green_rows = []
        for row in range(yy, yy+inner_h):
            green_rows.append(sum(_green(pix[xx+d, row]) for d in offsets) >= 2)
        count = sum(green_rows)
        if any(green_rows[:inner_h-count]) or (
                count and not all(green_rows[inner_h-count:])):
            continue

        edge = max(1, round(sy))
        return {
            "center_x": xx, "track_top": yy,
            "track_bottom_exclusive": yy+inner_h,
            "fill_top": yy+inner_h-count if count else None,
            "graphical_fill_estimate_pct": round(100*count/inner_h, 1),
            "graphical_fill_range_pct": [
                max(0, round(100*max(0, count-edge)/(inner_h+2*edge), 1)),
                min(100, round(100*min(inner_h, count+edge)/(inner_h-2*edge), 1)),
            ],
            "green_height_px": count, "track_height_px": inner_h,
            "visual_confidence": "TEMPLATE_VALIDATED_UNCALIBRATED",
            "game_hp_percent": None,
        }
    return None


def read_formation(image: Image.Image) -> dict[str, Any]:
    image = image.convert("RGB")
    w, h = image.size
    if w < 900 or h < 400 or abs(w/h - BASE_W/BASE_H) > 0.04:
        return {"screen_type": "UNSUPPORTED",
                "reason": "geometry outside supported full-screen aspect/size", "positions": {}}
    sx, sy = w/BASE_W, h/BASE_H
    tracks = {}
    for slot, (x, y) in SLOTS.items():
        xx, yy = round(x*sx), round(y*sy)
        track = _find_track(image, xx, yy, sx, sy)
        if track is not None:
            tracks[slot] = track
    if len(tracks) < 8:
        return {"screen_type": "UNSUPPORTED",
                "reason": f"only {len(tracks)}/9 formation gauge templates matched",
                "positions": {}}
    return {"screen_type": "FORMATION", "position_detection_count": len(tracks),
            "positions": tracks, "player_names_verified": False,
            "game_hp_calibrated": False}


def _other_screen_type(image: Image.Image) -> str:
    """Coarse fixed-palette screen category only; no text/digit interpretation."""
    w, h = image.size
    if abs(w/h - BASE_W/BASE_H) > 0.04 or w < 900:
        return "UNSUPPORTED"
    pix = image.load()
    def at(x, y):
        return pix[round(x*w/BASE_W), round(y*h/BASE_H)]
    diamond = at(100, 80)
    if abs(diamond[0]-85) < 20 and abs(diamond[1]-124) < 20 and abs(diamond[2]-233) < 20:
        top, mid = at(1300, 100), at(1300, 285)
        if top[0] > 170 and top[1] < 60 and top[2] < 60 and min(mid) > 235:
            return "BATTER_RESULTS"
        if min(top) > 240 and abs(mid[0]-85) < 20 and abs(mid[1]-124) < 20:
            return "PITCHER_RESULTS"
    if at(100, 80)[2] > 225 and at(100, 80)[1] > 110 and at(100, 80)[0] < 30:
        if min(at(1300, 100)) > 240:
            return "TOURNAMENT_LIST"
        return "WORLD_UI_OR_OVERLAY"
    return "UNSUPPORTED"


# Source-derived title and page-digit masks from native iOS v1.42 roster
# screenshots (pages 1-6). These classify the VIEW only; they do not decode
# Japanese names, numbers, traits, scroll offset, or player identities.
_ROSTER_TITLE_MASK = 0x1000000000126000078ff41280000406680820000402080820007fe2480823ff0407e80003ff04024c01f0000407e003f000040128
_ROSTER_PAGE_MASKS = {
    1: 0xc00840840040040040040040040040040,
    2: 0xc008f88180100300600400c00c0080080,
    3: 0xc008f88c81801801800c00700c0080180,
    4: 0xc008c08c00c01fc0cc0c80d80d00d00e0,
    5: 0xc008788c81801801800800d8078018018,
    6: 0xc008f08d81881881881881980f8008018,
}


def _roster_blue_mask(image: Image.Image, box: tuple[int,int,int,int],
                      size: tuple[int,int]) -> int:
    crop=image.crop(box).convert("RGB")
    ink=Image.new("L",crop.size)
    ink.putdata([255 if r<45 and 25<=g<=75 and 120<=b<=185 else 0
                 for r,g,b in crop.getdata()])
    sampled=ink.resize(size,Image.Resampling.NEAREST)
    return sum(1<<i for i,val in enumerate(sampled.getdata()) if val>127)


def read_roster_page(image: Image.Image) -> dict[str, Any] | None:
    """Recognize a verified native roster-list page, not the roster contents.

    Unknown fonts, page indicators, or scales fail closed. In particular,
    a row position is NOT an identity when a list has been scrolled.
    """
    if image.size!=(BASE_W,BASE_H):
        return None
    title=_roster_blue_mask(image,(1120,160,1375,220),(48,12))
    if (title^_ROSTER_TITLE_MASK).bit_count()>5:
        return None
    number=_roster_blue_mask(image,(1390,163,1435,218),(12,16))
    distances=sorted(((number^bits).bit_count(),page)
                     for page,bits in _ROSTER_PAGE_MASKS.items())
    if distances[0][0]>4 or distances[1][0]-distances[0][0]<6:
        return None
    return {"page_index":distances[0][1], "page_count":6,
            "status":"PAGE_ONLY", "names_verified":False,
            "player_stats_verified":False, "visible_rows_not_identified":True}


# Source-verified native v1.42 player-list batting-value glyphs.
# Compact, exact five-by-seven silhouette masks from actual pixels. 9 has
# no trusted source and is deliberately absent; do not infer a font-wide OCR.
_ROSTER_BATTING_FONT = {
    "0": (0x7e35ad63f,),
    "1": (0x7294b4adc, 0x7296b4adc),
    "2": (0x7e3d8de3f,),
    "3": (0x7e378de3f,),
    "4": (0x72978d6bf, 0x72d78d6bf),
    "5": (0x7e378f63f,),
    "6": (0x7e358f63f,),
    "7": (0x7294bd63f,),
    "8": (0x7e358d63f,),
}
_ROSTER_BATTING_ROW_Y = (361, 452, 542, 633, 723, 813, 904)
_ROSTER_BATTING_COLUMNS = {
    "batting": (1492, 2),
    "slugging": (1668, 3),
    "running": (1843, 2),
}
_ROSTER_NUMERIC_INK = (23, 34, 53)


def _roster_numeric_glyph(image: Image.Image, right: int, top: int,
                          place: int) -> tuple[int, int]:
    """Return recognized silhouette plus raw-ink count for one fixed slot."""
    left = right - 24 - 25*place
    crop = image.crop((left, top, left+25, top+36)).convert("RGB")
    pix = list(crop.getdata())
    mask = [pixel == _ROSTER_NUMERIC_INK for pixel in pix]
    count = sum(mask)
    bits = 0
    for by in range(7):
        for bx in range(5):
            coverage = sum(mask[y*25+x]
                           for y in range(by*5, by*5+5)
                           for x in range(bx*5, bx*5+5))
            if coverage >= 12:
                bits |= 1 << (by*5+bx)
    return bits, count


def _read_roster_batting_number(image: Image.Image, right: int,
                                top: int, max_digits: int) -> int | None:
    """Exact known digits only; a present unknown glyph is never omitted."""
    numbers = []
    seen_blank = False
    for place in range(max_digits):
        bits, ink_count = _roster_numeric_glyph(image, right, top, place)
        # The source has <=52 stray outline pixels in an empty leading slot.
        if ink_count < 100:
            if not numbers:
                return None
            seen_blank = True
            continue
        if seen_blank:
            return None
        matches = [digit for digit, patterns in _ROSTER_BATTING_FONT.items()
                   if bits in patterns]
        if len(matches) != 1:
            return None
        numbers.append(matches[0])
    if not numbers:
        return None
    # A third or fourth glyph outside the supported digit width must not
    # silently truncate the actual value.
    if _roster_numeric_glyph(image, right, top, max_digits)[1] >= 100:
        return None
    return int("".join(reversed(numbers)))


_ROSTER_PITCHING_COLUMNS = {
    "velocity_kmh": (1446, 3),
    "control": (1668, 3),
    "breaking": (1843, 2),
}


def _read_roster_numeric_values(image: Image.Image, *, page_index: int,
                                columns: dict[str, tuple[int, int]],
                                label: str) -> dict[str, Any]:
    """Read only verified numeric columns on one fixed roster page."""
    if image.size != (BASE_W, BASE_H):
        return {"status": "UNSUPPORTED_SCALE", "rows": []}
    page = read_roster_page(image)
    if page is None or page.get("page_index") != page_index:
        return {"status": "UNSUPPORTED_PAGE", "rows": []}
    im = image.convert("RGB")
    rows, errors = [], []
    for row_index, top in enumerate(_ROSTER_BATTING_ROW_Y, 1):
        fields = {field: _read_roster_batting_number(im, right, top, digits)
                  for field, (right, digits) in columns.items()}
        if any(value is None for value in fields.values()):
            errors.append(f"UNKNOWN_{label}_GLYPH_ROW:{row_index}")
        rows.append({"visible_row": row_index, **fields})
    return {"status": "PASS" if not errors else "NEEDS_REVIEW",
            "page_index": page_index, "rows": rows, "errors": errors,
            "names_verified": False, "player_identities_verified": False,
            "ability_grades_verified": False, "live_state_current": False}


def read_roster_batting_values(image: Image.Image) -> dict[str, Any]:
    """Page 2: batting/slugging/running numbers, without player identities."""
    return _read_roster_numeric_values(
        image, page_index=2, columns=_ROSTER_BATTING_COLUMNS, label="BATTING")


def read_roster_pitching_values(image: Image.Image) -> dict[str, Any]:
    """Page 3: velocity/control/breaking numbers, without player identities."""
    return _read_roster_numeric_values(
        image, page_index=3, columns=_ROSTER_PITCHING_COLUMNS, label="PITCHING")



# Native iOS v1.42 roster portrait ROI, indexed by visible row, NOT by
# player or persistent roster order. Avatar matching is local to a verified
# same-snapshot set; globally identical portraits are not player identities.
_ROSTER_PORTRAIT_X = (822, 886)
_ROSTER_PORTRAIT_Y_REL = (-30, 40)


def _roster_portrait_pixels(image: Image.Image, visible_row: int) -> list[tuple[int,int,int]]:
    if not 1 <= visible_row <= len(_ROSTER_BATTING_ROW_Y):
        raise ValueError("invalid visible row")
    top = _ROSTER_BATTING_ROW_Y[visible_row - 1]
    x1, x2 = _ROSTER_PORTRAIT_X
    y1, y2 = _ROSTER_PORTRAIT_Y_REL
    return list(image.crop((x1, top+y1, x2, top+y2)).convert("RGB").getdata())


def _roster_portrait_similarity(a: list[tuple[int,int,int]],
                                b: list[tuple[int,int,int]]) -> float:
    """Exact overlapping foreground RGB pixels / foreground union.

    White and cyan row backgrounds are ignored; no learned classifier,
    facial identity recognition or Japanese OCR is involved.
    """
    if len(a) != len(b):
        return 0.0
    hit = union = 0
    for aa, bb in zip(a, b):
        fa = aa[0] < 230 and aa[1] < 216 and aa[2] < 220
        fb = bb[0] < 230 and bb[1] < 216 and bb[2] < 220
        if fa or fb:
            union += 1
            if fa and fb and aa == bb:
                hit += 1
    return hit / union if union >= 500 else 0.0



# Known-name text templates: source-verified labels only, not open-vocabulary
# Japanese OCR. The normalized ROI is in full native iOS v1.42 pixels.
_ROSTER_NAME_X1, _ROSTER_NAME_X2 = 922, 1352
_ROSTER_NAME_Y_TOP, _ROSTER_NAME_Y_BOTTOM = -26, 36


def _roster_name_ink(image: Image.Image, visible_row: int) -> frozenset[int]:
    """Extract dark neutral text pixels, independently of cyan/white row fill."""
    if not 1 <= visible_row <= len(_ROSTER_BATTING_ROW_Y):
        raise ValueError("invalid roster row")
    y = _ROSTER_BATTING_ROW_Y[visible_row-1]
    crop = image.crop((_ROSTER_NAME_X1, y+_ROSTER_NAME_Y_TOP,
                       _ROSTER_NAME_X2, y+_ROSTER_NAME_Y_BOTTOM)).convert("RGB")
    return frozenset(
        i for i, (r, g, b) in enumerate(crop.getdata())
        if r < 140 and g < 140 and b < 140 and abs(r-g) < 5
    )


def _roster_text_similarity(a: frozenset[int], b: frozenset[int]) -> float:
    if len(a) < 200 or len(b) < 200:
        return 0.0
    union = len(a | b)
    return len(a & b)/union if union else 0.0


def match_verified_roster_names(
        reference_pages: list[dict[str, Any]], target_page: str | Path,
        *, run_id: str, snapshot_evidence: str,
        confirmed_same_snapshot: bool) -> dict[str, Any]:
    """Closed-set replay of independently verified Japanese name *images*.

    The known text glyph silhouettes and their manually checked names are
    supplied at call time. Unknown names are NULL, never extrapolated from
    a lookalike. These drafts MUST NOT feed `verified_names` automatically.
    """
    base = {"status": "NEEDS_REVIEW", "rows": [], "errors": [],
            "japanese_ocr_performed": False, "live_state_current": False,
            "requires_manual_acceptance": True}
    if (not isinstance(run_id, str) or not run_id.strip()
            or not isinstance(snapshot_evidence, str)
            or not snapshot_evidence.strip() or not confirmed_same_snapshot):
        return {**base, "status": "NEEDS_SNAPSHOT_ATTESTATION"}
    if not reference_pages:
        return {**base, "status": "NEEDS_VERIFIED_NAME_REFERENCES"}

    target_path = Path(target_page)
    target = read_image(target_path)
    if (target.get("screen_type") != "ROSTER_LIST"
            or target.get("roster_page", {}).get("page_index") != 1):
        return {**base, "status": "UNSUPPORTED_TARGET_NAME_PAGE"}
    target_sha = target["source"]["sha256"]
    atlas: dict[str, list[tuple[frozenset[int], str]]] = {}
    source_shas = []
    for item in reference_pages:
        if not isinstance(item, dict) or not isinstance(item.get("verified_names"), dict):
            return {**base, "status": "NEEDS_VERIFIED_NAME_REFERENCES"}
        path = Path(item["path"])
        reading = read_image(path)
        if (reading.get("screen_type") != "ROSTER_LIST"
                or reading.get("roster_page", {}).get("page_index") != 1):
            return {**base, "status": "UNSUPPORTED_REFERENCE_NAME_PAGE"}
        sha = reading["source"]["sha256"]
        if sha == target_sha:
            return {**base, "status": "SELF_REFERENCE_NOT_VALIDATION"}
        labels = item["verified_names"]
        if set(labels) != set(range(1, 8)):
            return {**base, "status": "NEEDS_VERIFIED_NAME_REFERENCES"}
        if len(set(labels.values())) != 7 or any(
                not isinstance(n, str) or not n.strip() for n in labels.values()):
            return {**base, "status": "AMBIGUOUS_REFERENCE_NAMES"}
        source_shas.append(sha)
        with Image.open(path) as im:
            for row in range(1, 8):
                atlas.setdefault(labels[row], []).append(
                    (_roster_name_ink(im, row), sha))
    if len(atlas) < 2:
        return {**base, "status": "INSUFFICIENT_NAME_REFERENCES"}
    # A name's different reference images must agree, and distinct labels
    # must not share an indistinguishable text silhouette.
    names = list(atlas)
    for n, records in atlas.items():
        if any(_roster_text_similarity(records[0][0], rec[0]) < 0.70
               for rec in records[1:]):
            return {**base, "status": "CONFLICTING_NAME_TEMPLATES"}
    for i, first in enumerate(names):
        for second in names[i+1:]:
            if any(_roster_text_similarity(x[0], y[0]) >= 0.70
                   for x in atlas[first] for y in atlas[second]):
                return {**base, "status": "AMBIGUOUS_NAME_TEMPLATES"}
    candidates = []
    with Image.open(target_path) as im:
        for row in range(1, 8):
            ink = _roster_name_ink(im, row)
            ranked = sorted(
                ((max(_roster_text_similarity(ink, m) for m, _ in records), name)
                 for name, records in atlas.items()), reverse=True)
            first_score, first_name = ranked[0]
            second_score = ranked[1][0] if len(ranked) > 1 else 0.0
            accepted = first_score >= 0.70 and first_score-second_score >= 0.20
            candidates.append({
                "visible_row": row, "candidate_name": first_name if accepted else None,
                "similarity": round(first_score, 3),
                "runner_up_similarity": round(second_score, 3),
                "name_reference_sha256": sorted(
                    {sha for _, sha in atlas[first_name]}) if accepted else [],
                "source_image_sha256": target_sha,
                "source_type": "KNOWN_NAME_IMAGE_TEMPLATE" if accepted else "UNKNOWN",
            })
    assigned = [row["candidate_name"] for row in candidates
                if row["candidate_name"] is not None]
    if len(assigned) != len(set(assigned)):
        return {**base, "status": "DUPLICATE_NAME_MATCH",
                "errors": ["multiple rows matched the same named template"]}
    errors = [f"UNKNOWN_NAME_ROW:{row['visible_row']}" for row in candidates
              if row["candidate_name"] is None]
    return {**base, "status": ("PASS_DRAFT" if not errors else
                              "PARTIAL_DRAFT" if assigned else "NEEDS_REVIEW"),
            "run_id": run_id, "snapshot_evidence": snapshot_evidence,
            "reference_image_sha256": sorted(set(source_shas)),
            "target_image_sha256": target_sha, "rows": candidates,
            "errors": errors}


def link_verified_roster_pages(
        name_pages: list[dict[str, Any]],
        ability_pages: list[str | Path],
        *, run_id: str, snapshot_evidence: str,
        confirmed_same_snapshot: bool) -> dict[str, Any]:
    """Draft source-linked roster joins; manual row-name labels are required.

    name_pages: [{"path": image_path,
                  "verified_names": {1: "name", ..., 7: "name"}}].
    All screenshots MUST be independently confirmed to belong to one
    unchanged run/snapshot. Avatar similarity alone cannot establish that.
    Never mutate LIVE_EVENTS, CURRENT_LIVE_STATE or a player record here.
    """
    base = {"status": "NEEDS_REVIEW", "records": [], "errors": [],
            "name_ocr_performed": False, "live_state_current": False,
            "snapshot_evidence": snapshot_evidence}
    if (not confirmed_same_snapshot or not run_id.strip()
            or not snapshot_evidence.strip()):
        return {**base, "status": "NEEDS_SNAPSHOT_ATTESTATION"}
    if not name_pages or not ability_pages:
        return {**base, "status": "MISSING_SOURCE_PAGES"}
    atlas: dict[str, list[tuple[list[tuple[int,int,int]], str, int]]] = {}
    reference_hashes = []
    for item in name_pages:
        if not isinstance(item, dict) or not isinstance(item.get("verified_names"), dict):
            return {**base, "status": "NEEDS_VERIFIED_NAMES"}
        path = Path(item["path"])
        reading = read_image(path)
        if (reading.get("screen_type") != "ROSTER_LIST"
                or reading.get("roster_page", {}).get("page_index") != 1):
            return {**base, "status": "INVALID_NAME_PAGE"}
        labels = item["verified_names"]
        if set(labels) != set(range(1, 8)):
            return {**base, "status": "NEEDS_VERIFIED_NAMES"}
        sha = reading["source"]["sha256"]
        reference_hashes.append(sha)
        with Image.open(path) as im:
            for row in range(1, 8):
                name = labels[row]
                if not isinstance(name, str) or not name.strip():
                    return {**base, "status": "NEEDS_VERIFIED_NAMES"}
                avatar = _roster_portrait_pixels(im, row)
                atlas.setdefault(name, []).append((avatar, sha, row))
    # A name must have a repeatable portrait, and two different names may not
    # share a matching portrait in the declared snapshot. Reject collisions
    # instead of relying on nearby rows, uniform levels, or list order.
    names = list(atlas)
    for name, entries in atlas.items():
        anchor = entries[0][0]
        if any(_roster_portrait_similarity(anchor, entry[0]) < 0.70
               for entry in entries[1:]):
            return {**base, "status": "CONFLICTING_NAME_REFERENCE"}
    for i, name in enumerate(names):
        for other in names[i+1:]:
            if any(_roster_portrait_similarity(a[0], b[0]) >= 0.70
                   for a in atlas[name] for b in atlas[other]):
                return {**base, "status": "AMBIGUOUS_NAME_PORTRAITS"}

    records, errors = [], []
    observed: dict[str, dict[str, int]] = {}
    for source in ability_pages:
        path = Path(source)
        reading = read_image(path)
        page = reading.get("roster_page", {}).get("page_index")
        key = {2: "roster_batting_values", 3: "roster_pitching_values"}.get(page)
        values = reading.get(key) if key else None
        if reading.get("screen_type") != "ROSTER_LIST" or not values:
            errors.append(f"UNSUPPORTED_ABILITY_PAGE:{path.name}")
            continue
        if values.get("status") != "PASS":
            errors.append(f"UNVERIFIED_ABILITY_NUMBERS:{path.name}")
            continue
        with Image.open(path) as im:
            for row in values["rows"]:
                portrait = _roster_portrait_pixels(im, row["visible_row"])
                scores = sorted(
                    ((max(_roster_portrait_similarity(portrait, entry[0])
                          for entry in entries), name)
                     for name, entries in atlas.items()), reverse=True)
                best, name = scores[0]
                second = scores[1][0] if len(scores) > 1 else 0.0
                if best < 0.70 or best-second < 0.20:
                    errors.append(f"AMBIGUOUS_AVATAR:{path.name}:row{row['visible_row']}")
                    continue
                fields = {field: value for field, value in row.items()
                          if field != "visible_row"}
                prior = observed.setdefault(name, {})
                if any(field in prior and prior[field] != value
                       for field, value in fields.items()):
                    errors.append(f"CONFLICTING_ABILITY:{name}:{path.name}")
                    continue
                prior.update(fields)
                records.append({
                    "player_name": name, "visible_row": row["visible_row"],
                    "roster_page": page, "fields": fields,
                    "image_sha256": reading["source"]["sha256"],
                    "name_page_sha256": sorted(set(x[1] for x in atlas[name])),
                    "portrait_score": round(best, 3),
                    "manual_name_verification_required": True,
                })
    # A duplicate portrait cannot produce two different players on a single
    # page even if a reference set was mistakenly supplied.
    for source in ability_pages:
        matching = [r for r in records if r["image_sha256"] ==
                    __source_digest(Path(source))]
        seen = [r["player_name"] for r in matching]
        if len(seen) != len(set(seen)):
            errors.append(f"DUPLICATE_IDENTITY:{Path(source).name}")
    return {"status": "PASS_DRAFT" if not errors and records else "NEEDS_REVIEW",
            "run_id": run_id, "snapshot_evidence": snapshot_evidence,
            "reference_image_sha256": sorted(set(reference_hashes)),
            "records": records if not errors else [],
            "errors": errors, "name_ocr_performed": False,
            "live_state_current": False, "requires_manual_acceptance": True}


def __source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Native v1.42 item-use menu; exact, source-derived text silhouettes from
# IMG_8972.png. They are NOT Japanese OCR or a catalogue of all items/counts.
# The title and stock-label shapes serve as independent screen anchors.
_ITEM_USE_TITLE = ((1030,146,1460,208),(58,11),
    0x119460000000001819020f0608020803408c810200820510522080804081f46448202c103e510e003f0c14001f4081000608000103f04001020031f8101000800000000000000000)
_ITEM_USE_STOCK_LABEL = ((1470,1120,1615,1178),(48,11),
    0xc7b840418c6038f84c41984033f8405190406820c0c194404fd1fe43f44045f810f030000958fe41f7e0000000000000000000000000)
_ITEM_USE_CHOCOLATE = ((960,1120,1298,1178),(58,11),
    0x40003c7f1f80801000111004004004000844010010190fe21100400400c00004401000001000011007e00004000047f0003c01000010000020000000000000000)
_ITEM_USE_STOCK_ONE = ((1690,1128,1716,1170),(14,20),
    0xfc03f00fc03f00fc03f00fc03f00fc03f00ff03fc0ff03f00fc0000)


def _item_use_mask(image: Image.Image, spec, *, kind: str) -> int:
    box, size, _ = spec
    crop = image.crop(box).convert("RGB")
    if kind == "title":
        bits = [255 if r < 45 and g < 105 and 90 <= b <= 210 else 0
                for r,g,b in crop.getdata()]
    elif kind == "white":
        bits = [255 if r >= 235 and g >= 235 and b >= 235 else 0
                for r,g,b in crop.getdata()]
    elif kind == "stock_digit":
        bits = [255 if r >= 215 and g >= 215 and b >= 215 else 0
                for r,g,b in crop.getdata()]
    else:
        raise ValueError("unknown item pixel class")
    ink = Image.new("L",crop.size)
    ink.putdata(bits)
    small = ink.resize(size,Image.Resampling.NEAREST)
    return sum(1 << i for i,px in enumerate(small.getdata()) if px)


def read_item_use_page(image: Image.Image) -> dict[str, Any] | None:
    """Recognize one verified item-use layout and selected-item stock only.

    The screenshot does not prove the Confirm button was pressed or that the
    visible stock is current. Do not promote this to a complete inventory
    snapshot or an accepted ITEM_USE event. Unknown items/digits remain null.
    """
    if image.size != (BASE_W,BASE_H):
        return None
    if (_item_use_mask(image,_ITEM_USE_TITLE,kind="title") ^
            _ITEM_USE_TITLE[2]).bit_count() > 6:
        return None
    if (_item_use_mask(image,_ITEM_USE_STOCK_LABEL,kind="white") ^
            _ITEM_USE_STOCK_LABEL[2]).bit_count() > 5:
        return None
    item_name = "チョコレート" if (
        _item_use_mask(image,_ITEM_USE_CHOCOLATE,kind="white") ^
        _ITEM_USE_CHOCOLATE[2]).bit_count() <= 5 else None
    quantity = 1 if (
        _item_use_mask(image,_ITEM_USE_STOCK_ONE,kind="stock_digit") ^
        _ITEM_USE_STOCK_ONE[2]).bit_count() <= 5 else None
    errors=[]
    if item_name is None:
        errors.append("UNRECOGNIZED_SELECTED_ITEM_NAME")
    if quantity is None:
        errors.append("UNRECOGNIZED_SELECTED_ITEM_STOCK")
    return {
        "status": "PASS_DRAFT" if not errors else "NEEDS_REVIEW",
        "recognized_layout": "IOS_V1_42_ITEM_USE_FIXED",
        "selected_item_name": item_name,
        "selected_item_stock": quantity,
        "stock_scope": "SELECTED_ITEM_ONLY",
        "stock_glyph_scope": "KNOWN_ONE_ONLY",
        "errors": errors,
        "full_inventory_verified": False,
        "selected_player_verified": False,
        "event_time_verified": False,
        "item_use_confirmed": False,
        "requires_manual_acceptance": True,
    }


def read_image(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        # FAST: fixed native screen anchors are far cheaper than nine
        # graphical HP track searches. A recognized non-formation view must
        # never pay the formation cost or be mistaken for an HP observation.
        item_use = read_item_use_page(im)
        if item_use is not None:
            result={"screen_type":"ITEM_USE_MENU", "positions":{},
                    "item_use_page":item_use}
        else:
            roster=read_roster_page(im)
            if roster is not None:
                result={"screen_type":"ROSTER_LIST", "positions":{},
                        "roster_page":roster}
                if roster["page_index"]==2:
                    result["roster_batting_values"]=read_roster_batting_values(im)
                elif roster["page_index"]==3:
                    result["roster_pitching_values"]=read_roster_pitching_values(im)
            else:
                # The score panels have an existing coarse fixed-palette
                # signature. Other coarse UI hints are NOT strong enough
                # to rule out a formation gauge, so they retain fallback.
                coarse = _other_screen_type(im.convert("RGB"))
                if coarse in {"BATTER_RESULTS", "PITCHER_RESULTS"}:
                    result={"screen_type":coarse, "positions":{}}
                else:
                    result=read_formation(im)
                    if result["screen_type"] == "UNSUPPORTED":
                        result["screen_type"]=coarse
        if result["screen_type"]=="BATTER_RESULTS":
            result["batter_stats"]=read_batter_stats(im)
        elif result["screen_type"]=="PITCHER_RESULTS":
            result["pitcher_stats"]=read_pitcher_stats(im)
        result["image_size"] = [im.width, im.height]
    result["source"] = {
        "sha256": hashlib.sha256(raw).hexdigest(), "filename": path.name,
    }
    return result


def propose_hp_event(reading: dict[str, Any], verified_names: dict[str, str],
                     *, event_id: str, seq: int, year: int, month: int,
                     after_event_id: str | None) -> dict[str, Any]:
    """Return a draft event only; never infer names, acceptance, or current time.

    Caller must separately verify formation position -> player and that the
    screenshot belongs to the active game branch before appending it.
    """
    if reading.get("screen_type") != "FORMATION":
        raise ValueError("unsupported screen type")
    if not after_event_id:
        raise ValueError("fresh source chronology required")
    entries = []
    for position, player in verified_names.items():
        if (position not in reading["positions"] or not isinstance(player, str)
                or not player.strip()):
            raise ValueError("unknown slot or unverified player label")
        track = reading["positions"][position]
        if track["fill_top"] is None:
            # The existing HP event schema cannot encode an empty bar.
            continue
        entries.append({
            "player": player, "reading_kind": "VERTICAL_BAR",
            "identity_evidence": "VERIFIED_FORMATION_SLOT",
            "position": position, "geometry_px": {
                "center_x": track["center_x"],
                "track_top": track["track_top"],
                "track_bottom": track["track_bottom_exclusive"],
                "fill_top": track["fill_top"], "edge_uncertainty": 1,
            },
        })
    if not entries:
        raise ValueError("no verified player names with measurable fill")
    return {
        "seq": seq, "event_id": event_id, "kind": "HP_OBSERVATION",
        "source": {"kind": "RAW_SCREEN", "locator":
                   reading["source"]["filename"]+"#sha256="+reading["source"]["sha256"]},
        "period": {"year": year, "month": month},
        "branch": "ACCEPTED", "after_event_id": after_event_id, "entries": entries,
    }


# Native v1.42 pixel-font glyph fingerprints. They are 12x16 (blue font)
# and 10x14 (white pitcher panel) nearest-neighbor silhouettes. 9 is not
# observed in the blue batting font; unfamiliar symbols fail closed.
_BLUE_DIGITS: dict[str, tuple[int, ...]] = {
    "0": (0x7fe7fee078f18f18f18f18f18f18f18f18f18f1e077fe7fe,
          0x7fc7fcc078e38e38e38e38e38e38e38e38e38e3c077fc7fc),
    "1": (0xffcffcc1cc1cc1cc1cc1cc1cc1cc1fc1fc03c03c1fffcffc,),
    "2": (0xffffff801ff1ff17c77c7e3fe3f8f18f18f18f1e077fe7fe,
          0xffffff803fe3fe3787787c7fc7f8e38e38e38e3c077fc7fc),
    "3": (0x7fe7fee078f18f18ff8ffe09e098ff8ff8f18f1e077fe7fe,
          0x7fc7fcc078e38e38ff8ffc1bc1b8ff8ff8e38e3c077fc7fc),
    "4": (0x7f07f0e3f801801801801e31e3163763760760760e7f87f8,
          0x7e07e0c7f803803803803c63c6346746740740741c7f87f8),
    "5": (0x7fe7fee078f18f18f18f18ff8ff601601ff1ff1801ffffff,
          0x7fc7fcc078e38e38e38e38ff8ff403403fe3fe3803ffffff),
    "6": (0x7fc7fcc078e38e38e38e3c03c03fe3fe38e38e3c077fc7fc,
          0x7fe7fee078f18f18f18f1e01e01ff1ff18f18f1e077fe7fe),
    "7": (0x7e07e0460c60c6086086087f87f8e38e38e38e3803ffffff,),
    "8": (0x7fc7fcc078e38e38e38e3c07c078e38e38e38e3c077fc7fc,),
}
_WHITE_DIGITS: dict[str, tuple[int, ...]] = {
    ".": (0xfffffffffffffffffffffffffffffffffff,),
    "0": (0x3f0fcc0f03c0f03c0f03c0f03c0f033f0fc,),
    "1": (0xf83e0f83e0f83e0f83e0f83e0ffffff83e0,),
    "2": (0xfffff00c030300c3c0f0c0300c0f033f0fc,),
    "3": (0x3f0fcc0f03c03003c0f0c0300c0f033f0fc,),
    "4": (0x300c0fffff30cc330cc3330cc3c0f0300c0,),
    "5": (0x3fcffc0300c03003fcff00c0300c03fffff,),
    "6": (0x3f0fcc0f03c0f033fcff00c03c0f033f0fc,),
    "7": (0xc0300c0300c030300c0300c0c0300fffff,),
    "8": (0x3f0fcc0f03c0f033f0fcc0f03c0f033f0fc,),
    "9": (0x3f0fcc0f03c0300ff3fcc0f03c0f033f0fc,),
}
_BLUE_RGB=(29,73,153)
_BATTER_Y=(256,437,617,798,979)
_BATTER_NUM_X={"at_bats":1376,"hits":1569,"rbi":1768}


def _pixel_font_fingerprint(occupied: list[list[bool]],
                            width: int, height: int) -> int | None:
    yy=[y for y,row in enumerate(occupied) if any(row)]
    if not yy:
        return None
    xx=[x for x in range(len(occupied[0]))
        if any(occupied[y][x] for y in range(len(occupied)))]
    if not xx: return None
    left,right,top,bottom=min(xx),max(xx),min(yy),max(yy)
    cropped=Image.new("L",(right-left+1,bottom-top+1))
    cropped.putdata([255 if occupied[y][x] else 0
                     for y in range(top,bottom+1) for x in range(left,right+1)])
    normalized=cropped.resize((width,height),Image.Resampling.NEAREST)
    n=0
    for i,v in enumerate(normalized.getdata()):
        if v>127: n|=1<<i
    return n


def _nearest_digit(fp: int | None, alphabet: dict[str,tuple[int,...]],
                   *, max_errors: int=2, min_margin: int=5) -> str | None:
    if fp is None: return None
    distances=sorted(((min((fp^template).bit_count() for template in variants),
                        digit) for digit,variants in alphabet.items()))
    best,digit=distances[0]
    next_d=distances[1][0] if len(distances)>1 else 999
    if best>max_errors or next_d-best<min_margin: return None
    return digit


def _font_mask(image: Image.Image, box: tuple[int,int,int,int],
               color: tuple[int,int,int]) -> list[list[bool]]:
    crop=image.crop(box).convert("RGB")
    w,h=crop.size
    pix=list(crop.getdata())
    return [[pix[y*w+x]==color for x in range(w)] for y in range(h)]


def _read_blue_cell(image: Image.Image, box: tuple[int,int,int,int]) -> int | None:
    mask=_font_mask(image,box,_BLUE_RGB)
    if sum(sum(row) for row in mask)<80:return None
    digit=_nearest_digit(_pixel_font_fingerprint(mask,12,16),_BLUE_DIGITS)
    return int(digit) if digit is not None else None


def _read_batter_number(image: Image.Image, left: int, y: int) -> int | None:
    # A blank tens cell is different from a present but unreadable glyph
    # (including blue 9, for which no source-verified template exists).
    ones=_read_blue_cell(image,(left,y,left+41,y+46))
    if ones is None: return None
    tens_box=(left-40,y,left,y+46)  # do not borrow the ones' edge pixel
    tens_mask=_font_mask(image,tens_box,_BLUE_RGB)
    if not any(any(row) for row in tens_mask):
        return ones
    tens=_read_blue_cell(image,tens_box)
    return None if tens is None else tens*10+ones


def read_batter_stats(image: Image.Image) -> dict[str, Any]:
    """Source-agnostic counts only: no player names or inferred match state."""
    im=image.convert("RGB")
    if im.size!=(BASE_W,BASE_H):
        return {"status":"UNSUPPORTED_SCALE","rows":[],"team_total":None}
    # On the second page, row 5 is the team-total strip rather than player 5.
    anchor=im.getpixel((640,1004))
    if all(c>235 for c in anchor):
        page="TOP_1_TO_5"
    elif 140<=anchor[0]<=190 and 155<=anchor[1]<=220 and anchor[2]>210:
        page="BOTTOM_6_TO_9"
    else:
        return {"status":"UNSUPPORTED_PAGE","rows":[],"team_total":None}
    records=[];errors=[]
    for index,y in enumerate(_BATTER_Y):
        values={field:_read_batter_number(im,x,y) for field,x in _BATTER_NUM_X.items()}
        if any(v is None for v in values.values()):
            errors.append(f"UNRECOGNIZED_GLYPH_ROW:{index+1}")
        if values["at_bats"] is not None and values["hits"] is not None and values["hits"]>values["at_bats"]:
            errors.append(f"INVALID_HITS_GT_AT_BATS_ROW:{index+1}")
        records.append(values)
    if page=="TOP_1_TO_5":
        return {"status":"PASS" if not errors else "NEEDS_REVIEW",
                "page":page,"rows":[{"lineup_slot":i+1,**v} for i,v in enumerate(records)],
                "team_total":None,"errors":errors,"names_verified":False}
    return {"status":"PASS" if not errors else "NEEDS_REVIEW",
            "page":page,
            "rows":[{"lineup_slot":i+6,**v} for i,v in enumerate(records[:4])],
            "team_total":records[4],"errors":errors,"names_verified":False}


def validate_batter_pages(top: dict[str, Any], bottom: dict[str, Any],
                          *, verified_match_id: str | None=None) -> dict[str, Any]:
    """Only a caller-verified common match permits page merge; never auto-pair."""
    if not verified_match_id:
        return {"status":"NEEDS_MATCH_ID","rows":[]}
    if (top.get("page")!="TOP_1_TO_5" or bottom.get("page")!="BOTTOM_6_TO_9"
        or top.get("status")!="PASS" or bottom.get("status")!="PASS"):
        return {"status":"INVALID_PAGE_PAIR","rows":[]}
    rows=top["rows"]+bottom["rows"]; total=bottom.get("team_total")
    if not isinstance(total,dict):
        return {"status":"MISSING_TOTAL","rows":[]}
    sums={k:sum(row[k] for row in rows) for k in _BATTER_NUM_X}
    if sums!=total:
        return {"status":"TOTAL_MISMATCH","calculated":sums,"displayed":total,
                "rows":[],"match_id":verified_match_id}
    return {"status":"PASS","calculated":sums,"displayed":total,"rows":rows,
            "match_id":verified_match_id,"names_verified":False}


def _read_white_characters(image: Image.Image,
                           box: tuple[int,int,int,int]) -> str | None:
    mask=_font_mask(image,box,(255,255,255))
    if not mask: return None
    active=[x for x in range(len(mask[0])) if sum(row[x] for row in mask)>2]
    if not active:return None
    groups=[]
    for x in active:
        if not groups or x>groups[-1][-1]+1: groups.append([x])
        else:groups[-1].append(x)
    out=[]
    for group in groups:
        if len(group)<3:return None
        cropped=[[row[x] for x in range(group[0],group[-1]+1)] for row in mask]
        value=_nearest_digit(_pixel_font_fingerprint(cropped,10,14),
                             _WHITE_DIGITS)
        if value is None:return None
        out.append(value)
    return "".join(out)


def read_pitcher_stats(image: Image.Image) -> dict[str, Any]:
    """Native screenshot: pitching counts and cumulative panel fields."""
    im=image.convert("RGB")
    if im.size!=(BASE_W,BASE_H):
        return {"status":"UNSUPPORTED_SCALE","fields":{}}
    top_rects={
        "innings_displayed":(1180,311,1230,357),
        "hits_allowed":(1594,311,1641,357),
        "runs_allowed":(1824,311,1867,357),
    }
    other_rects={
        "earned_run_average":(900,396,1030,442),
        "wins":(1460,396,1535,442),
        "losses":(1850,396,1920,442),
        "strikeouts":(1460,475,1535,525),
        "walks":(1850,475,1920,525),
    }
    fields={key:_read_blue_cell(im,rect) for key,rect in top_rects.items()}
    fields.update({key:_read_white_characters(im,rect)
                   for key,rect in other_rects.items()})
    errors=[f"UNRECOGNIZED:{key}" for key,val in fields.items() if val is None]
    era=fields["earned_run_average"]
    if era is not None and (
            era.count(".")!=1 or not era.replace(".","").isdigit()
            or len(era.split(".")[-1])!=2):
        errors.append("INVALID_ERA_FORMAT")
    for field in ("wins","losses","strikeouts","walks"):
        value=fields[field]
        if value is not None and not value.isdigit():errors.append(f"INVALID_DIGITS:{field}")
        elif value is not None:fields[field]=int(value)
    return {"status":"PASS" if not errors else "NEEDS_REVIEW",
            "fields":fields,"errors":errors,"player_name_verified":False}


def main():
    parser = argparse.ArgumentParser(
        description="Classify screenshot and measure formation graphical HP fill.")
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(read_image(args.image), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
