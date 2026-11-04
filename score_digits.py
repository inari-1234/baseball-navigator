"""Exact pixel-font result numeric reader, limited to native 2622x1206 screenshots.

Monochrome digit masks are derived from explicitly reviewed user screenshots;
no screenshots or Japanese name glyphs are embedded. Unseen digits return UNKNOWN,
never nearest-character guessing. The output is not automatically a match event.
"""
from __future__ import annotations

import base64
import zlib
from functools import lru_cache

BLUE = {
    "7": (46, 41, "eJx1jrENAzEMA2l84dIjeJN4sUes0TSKRnDpwniGSpUmKlgcDqTIf+cAZijGUvStaEdRH8x1EWMXWj+gN5GoIsLWhV0i41ckDd/OSQYGudDJjUYeVMcblzCKsEHYcaMGXriyoeQUckriTHGk2PWRN5OoBomRop7NYg3p2cEHOYQcsg8yznKF"),
    "4": (46, 41, "eJxNj7ENBCEQA40INqQEOnkaOz1I1xjXCSUQboDO780+cTLWeBeN3Kiko5AHRr7IJNE2yqgOm+UgL3uRdibgArgE8BFAFUC5BezhvfPi42n3daL4jWJTcdRROcssXLaMO0vlyZMWD7QIhBqJQ8mp6EsRU4gpxBTsr0jKSDkVMuqLuNrDEM+gS40WatUQz40fHDVr4A=="),
    "0": (46, 41, "eJy1j7ENgDAQA40ovswIGSWj8RKLZZSMQEmBYo4+Lc0V97bkD9vXDu4NPAJTB4wpFVsKO0Wii8SQvjsNNRpZafSCGYFBZ0X3gh7xa/CRqlcbz8UzaiBfvQKDCw=="),
    "1": (46, 26, "eJydzrERgDAMQ1Gl8hheNHdmtGQTRnBJkeOHQAE1nd5JhQw6ZDAcjCsWhgI5zRY2xS4/ZKduvM0zs2Y9S1ZV/4/vg4UJAnpK+g=="),
    "2": (46, 41, "eJx1jjEOwzAMAxl00Ogn6Cl5mg30Y+5P/ISMGYww504F2mq4gRIphu3jAc4NTIFLFcYlFVsKu4mLLi6GtPY4tONoiaMXlBEoyC2Re0Ee8XFIRoJOIouvn8fmmSfRGOt6vftppV8/q7FdnajSQaUTrwEJ785/Zt5CfpPn"),
    "3": (46, 41, "eJxtjrENwzAMBD9IwVIjcJN4MQMR4MWUTTiCShWCmVOVFGq+OPKPtMzsT2I8iCni1pu0WyqZkmVWsdHERkhrTkMHjeo0WoGEQahVJxrFhPzUV8jz0zHGwNhPjOOFcbrWzf0POsDVwa2Aw/5OT2Hc/XhtReu1L7Vqj9c="),
    "5": (46, 41, "eJx1jrENwCAMBI1cUDKCN4HFkIiUxRiFESgpUMhRRgoUV7yPt9c6vSoipYHUgQ0QJvCPFMaSwGVbDKB5gKgN0fWMOCLIBiLGFITDV+KuxMMRI9ZAQiOrlYS4svorcorRJzRwE32i+2a3biqZ/2x8AWChiFM="),
    "6": (46, 41, "eJyFjrENwCAMBD9K4ZIRGIXRgpTFGIURKCkQztGlIErzxfn/ZHP3dhL9IIaIqYu0KQV3ydyzaBTRqNK6s1BikSOLEiDVIFuRki+DIgaMdRmbMHZhHPoz5gguAVztVRzLuPvx/vzhARk8hLI="),
    "8": (46, 41, "eJy9j7ENgDAQA40ovswIGSWj8RKLZZSMQEmBYo6Ogprminvb0oftYwXnAi6BqQ3GlIothZ0i0UViSM+dhhqNrDR6wYzAoLOie0GPeAUvqfqfxf3jGTWQNz4kgg8="),
}

WHITE = {
    "0": (36, 26, "eJxj//+D8f8/hvr/DfL/H7D//2HHwPi/gaH+AYP8Dwb2f9icGogyyvQAAOGROEE="),
    "1": (36, 11, "eJxjflDD3/jB/j8Y/AEy7dgP/JBnBotiZwIA0Moahg=="),
    "2": (36, 26, "eJxdyrENwCAMBdFDFC4ZgU1gsUgwWkbxCCld8ROhVFz3pDNF0mJoVrkpGkmT4dTAFumBCyrY/UNOD8oif+PGOZVJdghobOjoBau1Mhk="),
    "3": (36, 26, "eJxdjcEJgDAUxfLx8I+O0E3sYoV2NEfpCB7/qc9CBdFjICSuMA2qWlJ3xYGpUTsp8IFdUCCBnw+ok4N9sE1xwU/7BCaUlX4/N66BLus="),
    "4": (36, 26, "eJxjYPjBwGDHwMDfwMD8gAHI4f/HwPy/geH/AwZ7MKeGv0Ge+QH7gR+MH+yAnOYHzA9+MPywY7Djb8DJ+Y8K/kCNhtsDAGN6MrI="),
    "5": (36, 26, "eJz7/x8V/GNg4G9gYH7AwPCDgcEOC+f//wf///+w//+P////ZgiHgYHxAwNDDQODPAMD+wFMTj26HgApGDrZ"),
    "6": (36, 26, "eJxtzbENgDAMRNGLKFxmhGwSFkNKJBb1GK78QaRASJSv+HdGFFKD2XAjugpTw9VClg82l0LqUr0BDrGTFc6Fn+aDY02/Pxcetjn1"),
    "7": (36, 26, "eJz7/x8VHGBg/MDAUMPAIM/AwA7m8DcwMD9gYPjBwGDHgIPDf4CBGajrDwODPQMxHABf9idk"),
    "8": (36, 26, "eJxj//+D8f8/hvr/DfL/H7D//2HHwPi/gaH+AYP8Dwb2f5icGogyyvQAAOGROEE="),
    "9": (36, 26, "eJxtjbENwCAQxO6rH+M3yWRIMBrZhBEov4gwilKkSEoXtp00liotGE4eMprqUKR8faEEOJwwK9cDXTalIoXk/de50+9nAyA7OJQ="),
}

@lru_cache(maxsize=None)
def _atlas(style):
    src = BLUE if style == "BLUE" else WHITE
    result = {}
    for digit, (h, w, compressed) in src.items():
        raw = zlib.decompress(base64.b64decode(compressed))
        bits = tuple((raw[i // 8] >> (7-i % 8)) & 1 for i in range(h*w))
        result[digit] = (h, w, bits)
    return result


def _ink(color, style):
    if style == "BLUE":
        return color in {(29, 73, 153), (40, 72, 147)}
    if style == "WHITE":
        return color == (255, 255, 255)
    raise ValueError("unsupported numeric font")


def _components(im, box, style):
    """Vertical projection components; unsupported dimensions fail closed."""
    x1, y1, x2, y2 = box
    if im.size != (2622, 1206):
        return []
    px = im.load()
    xs = [x for x in range(x1, x2)
          if any(_ink(px[x, y], style) for y in range(y1, y2))]
    if not xs:
        return []
    spans = []
    first = last = xs[0]
    for x in xs[1:]:
        if x > last + 1:
            spans.append((first, last+1))
            first = x
        last = x
    spans.append((first, last+1))
    out = []
    for a, b in spans:
        yy = [y for y in range(y1,y2) if any(_ink(px[x,y],style) for x in range(a,b))]
        if not yy:
            continue
        top, bottom = min(yy), max(yy)+1
        bits = tuple(int(_ink(px[x,y],style)) for y in range(top,bottom) for x in range(a,b))
        out.append((bottom-top,b-a,bits,(a,top,b,bottom)))
    return out


def _recognize(comp, style):
    h, w, bits, _ = comp
    candidates = []
    for digit, (th,tw,reference) in _atlas(style).items():
        if (h,w) != (th,tw):
            continue
        error = sum(a!=b for a,b in zip(bits,reference))/(h*w)
        candidates.append((error,digit))
    if not candidates:
        return None
    candidates.sort()
    if candidates[0][0] > .01 or (len(candidates)>1 and candidates[1][0]-candidates[0][0] < .025):
        return None
    return candidates[0][1]


def _number(im, box, style, count=(1,), decimal=False):
    components = _components(im,box,style)
    # Team batting totals have two 41px characters sharing one stroke column.
    if style == "BLUE" and 2 in count and len(components) == 1 and components[0][:2] == (46,81):
        x,y,_,_ = components[0][3]
        px=im.load()
        components=[
            (46,41,tuple(int(_ink(px[col,row],style)) for row in range(y,y+46)
                           for col in range(left,left+41)),(left,y,left+41,y+46))
            for left in (x,x+40)
        ]
    chars = []
    for comp in components:
        if decimal and comp[0]<=6 and comp[1]<=8 and sum(comp[2])>=15:
            chars.append(".")
        else:
            digit = _recognize(comp,style)
            if digit is None:
                return {"value":None,"status":"UNKNOWN_GLYPH"}
            chars.append(digit)
    if len(chars) not in count:
        return {"value":None,"status":"UNEXPECTED_GLYPH_COUNT"}
    if decimal:
        if len(chars)!=4 or chars[1]!="." or any(not c.isdigit() for c in [chars[0],chars[2],chars[3]]):
            return {"value":None,"status":"INVALID_DECIMAL"}
        return {"value":"".join(chars),"status":"TEMPLATE_MATCH"}
    if not chars or not all(c.isdigit() for c in chars):
        return {"value":None,"status":"INVALID_NUMERIC"}
    return {"value":int("".join(chars)),"status":"TEMPLATE_MATCH"}


def _looks_like_result(im, kind):
    if im.size != (2622,1206):
        return False
    p=im.load()
    bg=p[100,80]
    if not (60<=bg[0]<=120 and 90<=bg[1]<=160 and 205<=bg[2]<=250):
        return False
    banner=p[1300,100]
    if kind=="BATTER":
        return banner[0]>170 and banner[1]<70 and banner[2]<80
    if kind=="PITCHER":
        return min(banner)>235
    return False


def read_batter_numbers(image):
    """Rows are lineup positions only, never auto-read player names."""
    im=image.convert("RGB")
    if not _looks_like_result(im,"BATTER"):
        return {"status":"UNSUPPORTED_SCREEN","page":"UNKNOWN","rows":[]}
    rows=[]
    for i in range(5):
        y=252+i*181
        box=lambda lo,hi: (lo,y,hi,y+57)
        ab=_number(im,box(1329,1419),"BLUE",count=(1,2))
        hits=_number(im,box(1563,1617),"BLUE")
        rbi=_number(im,box(1759,1813),"BLUE")
        rows.append({"row_position":i+1,"at_bats":ab["value"],"hits":hits["value"],
                     "rbi":rbi["value"],"field_status":{"at_bats":ab["status"],
                         "hits":hits["status"],"rbi":rbi["status"]}})
    total=rows[-1]
    is_total=(total["at_bats"] is not None and total["at_bats"]>=10)
    page="BOTTOM_6_TO_9_AND_TOTAL" if is_total else "TOP_1_TO_5"
    if is_total:
        for i,row in enumerate(rows[:4]):
            row["batting_order"]=i+6
        total["row_position"]="TOTAL"
        total["batting_order"]=None
    else:
        for i,row in enumerate(rows):
            row["batting_order"]=i+1
    contradictions=[]
    for row in rows:
        if row["hits"] is not None and row["at_bats"] is not None and row["hits"]>row["at_bats"]:
            contradictions.append("HITS_EXCEED_AT_BATS:"+str(row["row_position"]))
    if contradictions:
        return {"status":"INCONSISTENT_VALUES","page":page,"rows":rows,"errors":contradictions}
    count_unknown=sum(x is None for r in rows for x in (r["at_bats"],r["hits"],r["rbi"]))
    return {"status":"COMPLETE" if count_unknown==0 else "PARTIAL_UNVERIFIED",
            "page":page,"rows":rows,"unknown_field_count":count_unknown,
            "name_recognition":"NOT_AVAILABLE","match_id":"UNKNOWN",
            "accepted_branch":"UNKNOWN"}


def read_pitcher_numbers(image):
    """Top game pitching stats vs season W/L/ERA; never infer name or match ID."""
    im=image.convert("RGB")
    if not _looks_like_result(im,"PITCHER"):
        return {"status":"UNSUPPORTED_SCREEN","fields":{}}
    fields={
      "innings_displayed":((1177,304,1230,361),"BLUE",(1,),False),
      "hits_allowed":((1590,304,1644,361),"BLUE",(1,),False),
      "runs_allowed":((1825,304,1874,361),"BLUE",(1,),False),
      "era_displayed":((899,396,1021,442),"WHITE",(4,),True),
      "wins_record":((1480,396,1516,442),"WHITE",(1,),False),
      "losses_record":((1867,396,1903,442),"WHITE",(1,),False),
      "strikeouts":((1480,478,1516,522),"WHITE",(1,),False),
      "walks":((1867,478,1903,522),"WHITE",(1,),False)
    }
    values={};statuses={}
    for key,(box,font,amount,decimal) in fields.items():
        x=_number(im,box,font,count=amount,decimal=decimal)
        values[key]=x["value"]
        statuses[key]=x["status"]
    unread=sum(v is None for v in values.values())
    return {"status":"COMPLETE" if unread==0 else "PARTIAL_UNVERIFIED",
            "fields":values,"field_status":statuses,"unknown_field_count":unread,
            "name_recognition":"NOT_AVAILABLE","match_id":"UNKNOWN",
            "accepted_branch":"UNKNOWN"}


def reconcile_batter_pages(top,bottom):
    """Arithmetic reconciliation ONLY; screenshot-match identity remains unverified."""
    if top.get("page")!="TOP_1_TO_5" or bottom.get("page")!="BOTTOM_6_TO_9_AND_TOTAL":
        return {"status":"PAGE_MISMATCH"}
    if top.get("status")!="COMPLETE" or bottom.get("status")!="COMPLETE":
        return {"status":"INCOMPLETE_SOURCE"}
    players=top["rows"]+bottom["rows"][:4]
    total=bottom["rows"][-1]
    differences={}
    for col in ("at_bats","hits","rbi"):
        counted=sum(row[col] for row in players)
        if counted!=total[col]:
            differences[col]={"rows_sum":counted,"displayed_total":total[col]}
    return {"status":"ARITHMETIC_CONFLICT" if differences else "MATCH",
            "mismatches":differences,"match_identity_verified":False}
