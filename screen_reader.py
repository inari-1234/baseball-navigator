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


def read_image(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        result = read_formation(im)
        if result["screen_type"] == "UNSUPPORTED":
            result["screen_type"] = _other_screen_type(im.convert("RGB"))
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
    # Fixed advance of 40 native pixels; never infer unseen tens as zero.
    ones=_read_blue_cell(image,(left,y,left+41,y+46))
    if ones is None: return None
    tens=_read_blue_cell(image,(left-40,y,left+1,y+46))
    return ones if tens is None else tens*10+ones


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
