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
