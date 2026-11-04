"""Synthetic pixel fixtures: no user screenshot bytes are committed."""
import hashlib
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from PIL import Image, ImageDraw
from screen_reader import BASE_H, BASE_W, SLOTS, read_formation, read_image, propose_hp_event


def fixture(size=(2622, 1206), fills=None, jitter=(0, 0)):
    im = Image.new("RGB", size, (188, 229, 255))
    draw = ImageDraw.Draw(im)
    fills = fills or {}
    sx, sy = size[0]/BASE_W, size[1]/BASE_H
    for position, (x, y) in SLOTS.items():
        cx, top = round((x+jitter[0])*sx), round((y+jitter[1])*sy)
        height = max(18, round(51*sy))
        half = max(9, round(15*sx))
        green_height = round(height*fills.get(position, 0.7))
        cap, rim = max(1, round(10*sy)), max(2, round(5*sy))
        draw.rectangle((cx-half, top-cap, cx+half, top-1), fill=(156, 156, 157))
        draw.rectangle((cx-half, top, cx+half, top+height-1), fill=(38, 42, 43))
        if green_height:
            draw.rectangle((cx-half, top+height-green_height,
                            cx+half, top+height-1), fill=(40, 255, 2))
        draw.rectangle((cx-half, top+height, cx+half, top+height+rim),
                       fill=(70, 78, 81))
    return im


class ScreenReaderRegression(unittest.TestCase):
    def test_nine_positions_and_no_numeric_hp(self):
        result = read_formation(fixture())
        self.assertEqual(result["screen_type"], "FORMATION")
        self.assertEqual(set(result["positions"]), set(SLOTS))
        p = result["positions"]["P"]
        self.assertEqual(p["graphical_fill_estimate_pct"], 70.6)
        self.assertIsNone(p["game_hp_percent"])

    def test_half_resolution_layout(self):
        self.assertEqual(len(read_formation(fixture(size=(1311, 603)))["positions"]), 9)

    def test_nearest_neighbor_half_scale_pixel_art(self):
        half = fixture().resize((1311, 603), Image.Resampling.NEAREST)
        result = read_formation(half)
        self.assertEqual(result["screen_type"], "FORMATION")
        self.assertEqual(len(result["positions"]), 9)

    def test_slight_shift_tracked(self):
        result = read_formation(fixture(jitter=(8, 4)))
        self.assertEqual(result["screen_type"], "FORMATION")
        self.assertEqual(result["positions"]["P"]["center_x"], 1309)

    def test_zero_green_does_not_imply_missing_slot(self):
        result = read_formation(fixture(fills={"C": 0}))
        self.assertEqual(result["positions"]["C"]["graphical_fill_estimate_pct"], 0)
        self.assertIsNone(result["positions"]["C"]["fill_top"])

    def test_full_green_does_not_imply_numeric_full(self):
        result = read_formation(fixture(fills={"P": 1}))
        self.assertEqual(result["positions"]["P"]["graphical_fill_estimate_pct"], 100)
        self.assertIsNone(result["positions"]["P"]["game_hp_percent"])

    def test_green_background_is_not_gauge(self):
        self.assertEqual(read_formation(Image.new("RGB", (2622, 1206),
                                                  (40, 255, 2)))["screen_type"],
                         "UNSUPPORTED")

    def test_blue_background_is_not_gauge(self):
        self.assertEqual(read_formation(Image.new("RGB", (2622, 1206),
                                                  (188, 229, 255)))["screen_type"],
                         "UNSUPPORTED")

    def test_cropped_aspect_is_rejected(self):
        self.assertEqual(read_formation(fixture(size=(1500, 1206)))["screen_type"],
                         "UNSUPPORTED")

    def test_source_digest_is_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"f.png"
            fixture().save(path)
            self.assertEqual(read_image(path)["source"]["sha256"],
                             hashlib.sha256(path.read_bytes()).hexdigest())

    def test_position_is_not_player_identity(self):
        result = read_formation(fixture())
        self.assertFalse(result["player_names_verified"])
        self.assertFalse(any("player" in data for data in result["positions"].values()))

    def test_event_proposal_requires_explicit_mapping_and_chronology(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"f.png"
            fixture().save(path)
            reading = read_image(path)
            def draft(mapping, after):
                return propose_hp_event(reading, mapping, event_id="E2", seq=2,
                                        year=1, month=6, after_event_id=after)
            with self.assertRaises(ValueError):
                draft({"P": "石渡"}, None)
            with self.assertRaises(ValueError):
                draft({"ZZ": "石渡"}, "E1")
            with self.assertRaises(ValueError):
                draft({}, "E1")

    def test_draft_event_replays_with_manual_name_mapping(self):
        from live_state_engine import replay
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"f.png"
            fixture().save(path)
            reading = read_image(path)
            event = propose_hp_event(reading, {"P": "石渡いなり"}, event_id="E2",
                                     seq=2, year=1, month=6, after_event_id="E1")
            previous = {"event_id": "E1", "seq": 1, "kind": "SCREEN",
                        "period": {"year": 1, "month": 6}, "branch": "ACCEPTED",
                        "source": {"kind": "USER_REPORT", "locator": "test fixture"},
                        "resources": {"study": 1, "sports": 2, "play": 3,
                                      "nature": 4, "cheer": 5}}
            result = replay([previous, event])
            self.assertEqual(list(result["hp_by_player"]), ["石渡いなり"])
            self.assertIsNone(result["hp_by_player"]["石渡いなり"]["hp_numeric_percent"])

    def test_nonformation_classification_only(self):
        im = Image.new("RGB", (2622, 1206), (85, 124, 233))
        draw = ImageDraw.Draw(im)
        draw.rectangle((1290, 90, 1310, 110), fill=(223, 0, 3))
        draw.rectangle((1290, 280, 1310, 290), fill=(255, 255, 255))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"b.png"
            im.save(path)
            out = read_image(path)
            self.assertEqual(out["screen_type"], "BATTER_RESULTS")
            self.assertEqual(out["positions"], {})




class RosterPageRegression(unittest.TestCase):
    """Synthesized masks; actual native images are verified outside GitHub."""
    def _sample(self,page,with_title=True):
        from screen_reader import _ROSTER_TITLE_MASK,_ROSTER_PAGE_MASKS
        im=Image.new("RGB",(BASE_W,BASE_H),"white")
        stamps=[]
        if with_title:
            stamps.append((_ROSTER_TITLE_MASK,(48,12),(1120,160,1375,220)))
        stamps.append((_ROSTER_PAGE_MASKS[page],(12,16),(1390,163,1435,218)))
        for bits,(w,h),(x1,y1,x2,y2) in stamps:
            mask=Image.new("L",(w,h))
            mask.putdata([255 if (bits>>i)&1 else 0 for i in range(w*h)])
            mask=mask.resize((x2-x1,y2-y1),Image.Resampling.NEAREST)
            im.paste((0,50,150),(x1,y1,x2,y2),mask)
        return im

    def test_native_roster_pages_1_to_6_are_classified_without_ocr(self):
        from screen_reader import read_roster_page
        for page in range(1,7):
            with self.subTest(page=page):
                read=read_roster_page(self._sample(page))
                self.assertIsNotNone(read)
                self.assertEqual(read["page_index"],page)
                self.assertEqual(read["status"],"PAGE_ONLY")
                self.assertFalse(read["names_verified"])
                self.assertFalse(read["player_stats_verified"])
                self.assertTrue(read["visible_rows_not_identified"])

    def test_missing_title_or_unsupported_scale_fails_closed(self):
        from screen_reader import read_roster_page
        self.assertIsNone(read_roster_page(self._sample(2,with_title=False)))
        self.assertIsNone(read_roster_page(
            self._sample(2).resize((1311,603),Image.Resampling.NEAREST)))
        self.assertIsNone(read_roster_page(Image.new("RGB",(BASE_W,BASE_H),"white")))

    def test_roster_screen_reader_output_keeps_source_and_unknown_names(self):
        from screen_reader import read_image
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"roster.png"
            self._sample(4).save(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            read=read_image(path)
        self.assertEqual(read["screen_type"],"ROSTER_LIST")
        self.assertEqual(read["roster_page"]["page_index"],4)
        self.assertFalse(read["roster_page"]["names_verified"])
        self.assertEqual(read["positions"],{})
        self.assertEqual(read["source"]["sha256"],digest)


class RosterBattingNumberRegression(unittest.TestCase):
    """Synthetic glyph test fixtures; actual user screenshot gold remains external."""
    def _image(self, values=None, *, page=2):
        from screen_reader import (
            _ROSTER_BATTING_FONT, _ROSTER_BATTING_ROW_Y,
            _ROSTER_BATTING_COLUMNS, _ROSTER_NUMERIC_INK,
        )
        img=RosterPageRegression()._sample(page)
        values=values or [
            (33,15,44),(10,11,4),(80,46,30),(5,4,4),
            (15,102,25),(15,12,30),(7,7,5),
        ]
        draw=ImageDraw.Draw(img)
        for top,triple in zip(_ROSTER_BATTING_ROW_Y,values):
            for (field,(right,limit)),value in zip(_ROSTER_BATTING_COLUMNS.items(),triple):
                for place,digit in enumerate(str(value)[::-1]):
                    bits=_ROSTER_BATTING_FONT[digit][0]
                    left=right-24-25*place
                    for y in range(7):
                        for x in range(5):
                            if bits>>(y*5+x)&1:
                                draw.rectangle((left+5*x,top+5*y,
                                                left+5*x+4,top+5*y+4),
                                               fill=_ROSTER_NUMERIC_INK)
        return img

    def test_roster_batting_three_numeric_fields_seven_visible_rows(self):
        from screen_reader import read_roster_batting_values
        rows=[(33,15,44),(10,11,4),(80,46,30),(5,4,4),
              (15,102,25),(15,12,30),(7,7,5)]
        result=read_roster_batting_values(self._image(rows))
        self.assertEqual(result["status"],"PASS",result)
        self.assertEqual(len(result["rows"]),7)
        values=[tuple(row[k] for k in ("batting","slugging","running"))
                for row in result["rows"]]
        self.assertEqual(values,rows)
        self.assertFalse(result["names_verified"])
        self.assertFalse(result["player_identities_verified"])
        self.assertFalse(result["ability_grades_verified"])
        self.assertFalse(result["live_state_current"])

    def test_roster_batting_integration_keeps_source_and_draft_only(self):
        from screen_reader import read_image
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"test_roster.png"
            self._image().save(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            result=read_image(path)
        self.assertEqual(result["screen_type"],"ROSTER_LIST")
        self.assertEqual(result["roster_batting_values"]["status"],"PASS")
        self.assertEqual(result["source"]["sha256"],digest)
        self.assertNotIn("player_names",result)
        self.assertFalse(result["roster_batting_values"]["player_identities_verified"])

    def test_unrecognized_digit_in_a_tens_slot_fails_closed(self):
        from screen_reader import read_roster_batting_values, _ROSTER_BATTING_ROW_Y
        img=self._image()
        # Replace the '3' in 33 with a previously unseen, all-ink glyph.
        top=_ROSTER_BATTING_ROW_Y[0]
        ImageDraw.Draw(img).rectangle((1442,top,1466,top+34),
                                      fill=(23,34,53))
        result=read_roster_batting_values(img)
        self.assertEqual(result["status"],"NEEDS_REVIEW")
        self.assertIsNone(result["rows"][0]["batting"])
        self.assertIn("UNKNOWN_BATTING_GLYPH_ROW:1",result["errors"])
        self.assertEqual(result["rows"][0]["slugging"],15)

    def test_extra_leading_digit_cannot_be_truncated(self):
        from screen_reader import (
            read_roster_batting_values, _ROSTER_BATTING_FONT, _ROSTER_BATTING_ROW_Y,
        )
        img=self._image()
        # Add a third digit before the 33 in the first bounded field.
        top=_ROSTER_BATTING_ROW_Y[0]
        left=1492-24-25*2
        mask=_ROSTER_BATTING_FONT["1"][0]
        draw=ImageDraw.Draw(img)
        for y in range(7):
            for x in range(5):
                if mask>>(y*5+x)&1:
                    draw.rectangle((left+x*5,top+y*5,
                                    left+x*5+4,top+y*5+4),fill=(23,34,53))
        result=read_roster_batting_values(img)
        self.assertEqual(result["status"],"NEEDS_REVIEW")
        self.assertIsNone(result["rows"][0]["batting"])

    def test_other_roster_page_and_scale_do_not_create_batting_stats(self):
        from screen_reader import read_roster_batting_values, read_image
        other=self._image(page=1)
        self.assertEqual(read_roster_batting_values(other)["status"],
                         "UNSUPPORTED_PAGE")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"wrong_page.png"
            other.save(path)
            result=read_image(path)
        self.assertNotIn("roster_batting_values",result)
        self.assertEqual(read_roster_batting_values(
            self._image().resize((1311,603),Image.Resampling.NEAREST)
        )["status"],"UNSUPPORTED_SCALE")


class ScorePixelReaderRegression(unittest.TestCase):
    """Deterministic digit silhouettes; real-game screenshot probes are external."""
    def test_blue_glyph_coverage_and_unknown(self):
        from screen_reader import _BLUE_DIGITS,_nearest_digit
        self.assertEqual(set(_BLUE_DIGITS),set("012345678"))
        for digit,variants in _BLUE_DIGITS.items():
            for variant in variants:
                self.assertEqual(_nearest_digit(variant,_BLUE_DIGITS),digit)
        self.assertIsNone(_nearest_digit((1<<192)-1,_BLUE_DIGITS))

    def test_white_digits_0_to_9_and_decimal(self):
        from screen_reader import _WHITE_DIGITS,_nearest_digit
        self.assertEqual(set(_WHITE_DIGITS),set("0123456789."))
        for digit,variants in _WHITE_DIGITS.items():
            for variant in variants:
                self.assertEqual(_nearest_digit(variant,_WHITE_DIGITS),digit)

    def test_pixel_fingerprint_round_trip(self):
        from screen_reader import _BLUE_DIGITS,_pixel_font_fingerprint
        for digit,items in _BLUE_DIGITS.items():
            bits=items[0]
            mask=[[bool(bits & (1<<(y*12+x))) for x in range(12)] for y in range(16)]
            self.assertEqual(_pixel_font_fingerprint(mask,12,16),bits,digit)

    def _put(self,im,digit,x,y,alphabet,ink):
        from PIL import ImageDraw
        if ink==(255,255,255) and str(digit) in {"1","4"}:
            # Native white pixel glyphs preserve contiguous column topology.
            rows=(
                ["......#####"]*5+["###########"]*5+["......#####"]*26
                if str(digit)=="1" else
                ["................#####....."]*5+
                ["..........###########....."]*5+
                [".....#####......#####....."]*5+
                ["#####...........#####....."]*11+
                ["##########################"]*5+
                ["................#####....."]*5
            )
            draw=ImageDraw.Draw(im)
            for yy,line in enumerate(rows):
                for xx,ch in enumerate(line):
                    if ch=="#":draw.point((x+xx,y+yy),fill=ink)
            return
        dim=(12,16) if ink==(29,73,153) else (10,14)
        bits=alphabet[str(digit)][0]
        draw=ImageDraw.Draw(im)
        for yy in range(dim[1]):
            for xx in range(dim[0]):
                if (bits>>(yy*dim[0]+xx))&1:
                    draw.point((x+xx,y+yy),fill=ink)

    def _batter_page(self, top):
        from screen_reader import _BLUE_DIGITS
        im=Image.new("RGB",(2622,1206),(255,255,255))
        im.putpixel((640,1004),(255,255,255) if top else (166,186,239))
        first=[(3,0,0),(3,1,0),(2,1,2),(3,1,0),(3,1,0)]
        last=[(3,1,0),(3,1,1),(3,1,0),(2,1,2),(25,8,5)]
        for y,values in zip((256,437,617,798,979),first if top else last):
            for x,value in zip((1376,1569,1768),values):
                if value>9:
                    self._put(im,str(value)[0],x-40,y+5,_BLUE_DIGITS,(29,73,153))
                self._put(im,str(value)[-1],x+14,y+5,_BLUE_DIGITS,(29,73,153))
        return im

    def test_batter_page_parse_and_merge(self):
        from screen_reader import read_batter_stats,validate_batter_pages
        first=read_batter_stats(self._batter_page(True))
        second=read_batter_stats(self._batter_page(False))
        self.assertEqual(first["status"],"PASS")
        self.assertEqual(second["status"],"PASS")
        self.assertEqual(len(first["rows"]),5)
        self.assertEqual(len(second["rows"]),4)
        self.assertEqual(second["team_total"],{"at_bats":25,"hits":8,"rbi":5})
        merged=validate_batter_pages(first,second,verified_match_id="Y1-JUN-HANASAKA")
        self.assertEqual(merged["status"],"PASS")
        self.assertFalse(merged["names_verified"])

    def test_unknown_present_tens_does_not_become_single_digit(self):
        from screen_reader import read_batter_stats
        from PIL import ImageDraw
        im=self._batter_page(True)
        # Native blue-colored ink exists in the tens slot but is not a
        # recognized 0-8 glyph. Previously this silently read "3".
        ImageDraw.Draw(im).rectangle((1342,263,1362,292),
                                     fill=(29,73,153))
        result=read_batter_stats(im)
        self.assertEqual(result["status"],"NEEDS_REVIEW")
        self.assertIsNone(result["rows"][0]["at_bats"])
        self.assertIn("UNRECOGNIZED_GLYPH_ROW:1",result["errors"])
        # An actually empty tens slot must still accept a single digit.
        normal=read_batter_stats(self._batter_page(True))
        self.assertEqual(normal["rows"][0]["at_bats"],3)
        self.assertEqual(normal["status"],"PASS")

    def test_unrecognized_team_total_tens_rejects_page_pair(self):
        from screen_reader import read_batter_stats,validate_batter_pages
        from PIL import ImageDraw
        top=read_batter_stats(self._batter_page(True))
        img=self._batter_page(False)
        # Team-total value 25 contains a tens glyph. Replace it with an
        # unknown silhouette rather than treating the number as 5.
        ImageDraw.Draw(img).rectangle((1342,986,1362,1015),
                                     fill=(29,73,153))
        bottom=read_batter_stats(img)
        self.assertEqual(bottom["status"],"NEEDS_REVIEW")
        self.assertIsNone(bottom["team_total"]["at_bats"])
        combined=validate_batter_pages(top,bottom,verified_match_id="M")
        self.assertEqual(combined["status"],"INVALID_PAGE_PAIR")
        self.assertEqual(combined["rows"],[])

    def test_batter_pair_rejects_implicit_match_pairing(self):
        from screen_reader import read_batter_stats,validate_batter_pages
        first=read_batter_stats(self._batter_page(True))
        second=read_batter_stats(self._batter_page(False))
        self.assertEqual(validate_batter_pages(first,second)["status"],"NEEDS_MATCH_ID")

    def test_batter_total_mismatch_fails_closed(self):
        from screen_reader import read_batter_stats,validate_batter_pages
        first=read_batter_stats(self._batter_page(True))
        second=read_batter_stats(self._batter_page(False))
        second["team_total"]["hits"]=7
        self.assertEqual(validate_batter_pages(first,second,verified_match_id="M")["status"],
                         "TOTAL_MISMATCH")

    def test_unknown_color_and_scale_do_not_create_stats(self):
        from screen_reader import read_batter_stats,read_pitcher_stats
        img=Image.new("RGB",(2622,1206),"white")
        self.assertEqual(read_batter_stats(img)["status"],"NEEDS_REVIEW")
        self.assertEqual(read_pitcher_stats(img)["status"],"NEEDS_REVIEW")
        self.assertEqual(read_batter_stats(Image.new("RGB",(1311,603)))["status"],
                         "UNSUPPORTED_SCALE")

    def test_pitcher_panel_numeric_fields(self):
        from screen_reader import _BLUE_DIGITS,_WHITE_DIGITS,read_pitcher_stats
        im=Image.new("RGB",(2622,1206),(69,71,72))
        for n,x in ((6,1185),(3,1597),(1,1833)):
            self._put(im,n,x,321,_BLUE_DIGITS,(29,73,153))
        for key,s,y,x in [
            ("era","1.20",406,904),("win","4",406,1487),
            ("loss","0",406,1874),("k","5",487,1487),
            ("bb","2",487,1874),
        ]:
            for ch in s:
                self._put(im,ch,x,y,_WHITE_DIGITS,(255,255,255))
                x+=16
        result=read_pitcher_stats(im)
        self.assertEqual(result["status"],"PASS", result)
        self.assertEqual(result["fields"]["innings_displayed"],6)
        self.assertEqual(result["fields"]["hits_allowed"],3)
        self.assertEqual(result["fields"]["runs_allowed"],1)
        self.assertEqual(result["fields"]["earned_run_average"],"1.20")
        self.assertEqual(result["fields"]["wins"],4)
        self.assertEqual(result["fields"]["losses"],0)
        self.assertEqual(result["fields"]["strikeouts"],5)
        self.assertEqual(result["fields"]["walks"],2)
        self.assertFalse(result["player_name_verified"])

    def test_pitcher_unsupported_era_format_rejected(self):
        from screen_reader import read_pitcher_stats
        with unittest.mock.patch("screen_reader._read_white_characters",return_value="12"):
            r=read_pitcher_stats(Image.new("RGB",(2622,1206),(69,71,72)))
        self.assertIn("INVALID_ERA_FORMAT",r["errors"])

if __name__ == "__main__":
    unittest.main()
