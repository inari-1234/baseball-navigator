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
    best = None
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
            if best is None or displacement < best[0]:
                best = (displacement, xx, yy)
    if best is None:
        return None
    _, xx, yy = best

    # Refine actual bar x-position by its green horizontal run (not just a
    # nearby template coordinate). Zero-green bars retain the template centre.
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

    offsets = (-max(2, round(5*sx)), 0, max(2, round(5*sx)))
    green_rows = []
    for row in range(yy, yy+inner_h):
        green_rows.append(sum(_green(pix[xx+d, row]) for d in offsets) >= 2)
    count = sum(green_rows)
    if any(green_rows[:inner_h-count]) or (count and not all(green_rows[inner_h-count:])):
        return None

    edge = max(1, round(sy))
    return {
        "center_x": xx, "track_top": yy, "track_bottom_exclusive": yy+inner_h,
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


def read_image(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        result = read_formation(im)
        if result["screen_type"] == "UNSUPPORTED":
            result["screen_type"] = _other_screen_type(im.convert("RGB"))
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


def main():
    parser = argparse.ArgumentParser(
        description="Classify screenshot and measure formation graphical HP fill.")
    parser.add_argument("image")
    args = parser.parse_args()
    print(json.dumps(read_image(args.image), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
