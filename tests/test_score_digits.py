"""Synthetic-font regression tests. Actual user screenshot bytes remain outside GitHub."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from score_digits import _atlas, read_batter_numbers, read_pitcher_numbers, reconcile_batter_pages
from screen_reader import read_image


BLUE_COLORS=((29,73,153),(40,72,147))
WHITE_COLOR=(255,255,255)


def paint_digit(image,digit,x,y,style="BLUE",palette=None):
    atlas=_atlas(style)
    h,w,bits=atlas[str(digit)]
    px=image.load()
    color=palette or (BLUE_COLORS[0] if style=="BLUE" else WHITE_COLOR)
    for row in range(h):
        for col in range(w):
            if bits[row*w+col]:
                px[x+col,y+row]=color


def batting_page(rows,second=False,palette=None):
    im=Image.new("RGB",(2622,1206),(85,124,233))
    px=im.load()
    px[1300,100]=(225,0,2)
    px[1300,285]=(255,255,255)
    for i,(ab,hits,rbi) in enumerate(rows):
        y=256+181*i
        if second and i==4:
            a,b=str(ab)
            paint_digit(im,a,1336,y,palette=palette)
            paint_digit(im,b,1376,y,palette=palette)
        else:
            w=_atlas("BLUE")[str(ab)][1]
            paint_digit(im,ab,1376+(41-w)//2,y,palette=palette)
        for val,x in [(hits,1572),(rbi,1768)]:
            w=_atlas("BLUE")[str(val)][1]
            paint_digit(im,val,x+(41-w)//2,y,palette=palette)
    return im


def pitcher_page():
    im=Image.new("RGB",(2622,1206),(85,124,233))
    px=im.load()
    px[1300,100]=(255,255,255)
    for val,x in [(6,1185),(3,1597),(1,1833)]:
        paint_digit(im,val,x,311)
    # Screen shows 1.20 as ERA; the decimal point has a different primitive.
    paint_digit(im,1,914,401,"WHITE")
    for y in range(432,437):
        for x in range(939,946):
            px[x,y]=(255,255,255) if x<945 else (85,85,85)
    paint_digit(im,2,954,401,"WHITE")
    paint_digit(im,0,989,401,"WHITE")
    for val,x,y in [(4,1487,401),(0,1874,401),(5,1487,482),(2,1874,482)]:
        paint_digit(im,val,x,y,"WHITE")
    return im


class ScoreDigitRegression(unittest.TestCase):
    def setUp(self):
        self.top=[(3,0,0),(3,1,0),(2,1,2),(3,1,0),(3,1,0)]
        self.bottom=[(3,1,0),(3,1,1),(3,1,0),(2,1,2),(25,8,5)]

    def test_top_page_digits(self):
        result=read_batter_numbers(batting_page(self.top))
        self.assertEqual(result["status"],"COMPLETE")
        self.assertEqual(result["page"],"TOP_1_TO_5")
        self.assertEqual([(r["at_bats"],r["hits"],r["rbi"]) for r in result["rows"]],self.top)

    def test_bottom_page_total_and_two_digit_overlap(self):
        result=read_batter_numbers(batting_page(self.bottom,second=True))
        self.assertEqual(result["page"],"BOTTOM_6_TO_9_AND_TOTAL")
        self.assertEqual(result["status"],"COMPLETE")
        self.assertEqual(result["rows"][-1]["row_position"],"TOTAL")
        self.assertEqual(result["rows"][-1]["at_bats"],25)

    def test_two_pages_arithmetic_cross_check(self):
        top=read_batter_numbers(batting_page(self.top))
        bottom=read_batter_numbers(batting_page(self.bottom,second=True))
        result=reconcile_batter_pages(top,bottom)
        self.assertEqual(result["status"],"MATCH")
        self.assertFalse(result["match_identity_verified"])

    def test_two_page_conflict_is_not_accepted(self):
        top=read_batter_numbers(batting_page(self.top))
        bad=self.bottom.copy()
        bad[-1]=(23,8,5)
        bottom=read_batter_numbers(batting_page(bad,second=True))
        outcome=reconcile_batter_pages(top,bottom)
        self.assertEqual(outcome["status"],"ARITHMETIC_CONFLICT")
        self.assertIn("at_bats",outcome["mismatches"])

    def test_wrong_page_rejected(self):
        top=read_batter_numbers(batting_page(self.top))
        self.assertEqual(reconcile_batter_pages(top,top)["status"],"PAGE_MISMATCH")

    def test_alternate_verified_palette(self):
        result=read_batter_numbers(batting_page(self.top,palette=BLUE_COLORS[1]))
        self.assertEqual(result["status"],"COMPLETE")

    def test_unknown_color_does_not_become_zero(self):
        result=read_batter_numbers(batting_page(self.top,palette=(1,40,122)))
        self.assertEqual(result["status"],"PARTIAL_UNVERIFIED")
        self.assertGreater(result["unknown_field_count"],0)
        self.assertIsNone(result["rows"][0]["hits"])

    def test_missing_digit_does_not_become_zero(self):
        im=batting_page(self.top)
        px=im.load()
        for y in range(256,302):
            for x in range(1572,1613):
                px[x,y]=(255,255,255)
        result=read_batter_numbers(im)
        self.assertIsNone(result["rows"][0]["hits"])
        self.assertNotEqual(result["status"],"COMPLETE")

    def test_hits_above_at_bats_caught(self):
        edited=[(2,3,0)]+self.top[1:]
        result=read_batter_numbers(batting_page(edited))
        self.assertEqual(result["status"],"INCONSISTENT_VALUES")

    def test_batter_only_numeric_not_names(self):
        result=read_batter_numbers(batting_page(self.top))
        self.assertEqual(result["name_recognition"],"NOT_AVAILABLE")
        self.assertEqual(result["match_id"],"UNKNOWN")
        self.assertEqual(result["accepted_branch"],"UNKNOWN")

    def test_pitcher_all_eight_fields(self):
        result=read_pitcher_numbers(pitcher_page())
        self.assertEqual(result["status"],"COMPLETE")
        self.assertEqual(result["fields"],{
            "innings_displayed":6,"hits_allowed":3,"runs_allowed":1,
            "era_displayed":"1.20","wins_record":4,"losses_record":0,
            "strikeouts":5,"walks":2})

    def test_pitcher_era_is_season_record_not_match_era(self):
        result=read_pitcher_numbers(pitcher_page())
        self.assertEqual(result["fields"]["era_displayed"],"1.20")
        self.assertEqual(result["name_recognition"],"NOT_AVAILABLE")

    def test_wrong_screen_rejected(self):
        self.assertEqual(read_batter_numbers(pitcher_page())["status"],"UNSUPPORTED_SCREEN")
        self.assertEqual(read_pitcher_numbers(batting_page(self.top))["status"],"UNSUPPORTED_SCREEN")

    def test_resized_number_screen_not_guessed(self):
        im=batting_page(self.top).resize((1311,603),Image.Resampling.NEAREST)
        self.assertEqual(read_batter_numbers(im)["status"],"UNSUPPORTED_SCREEN")

    def test_unknown_digit_font_remains_unknown(self):
        im=batting_page(self.top)
        px=im.load()
        for y in range(256,302):
            for x in range(1376,1417):
                px[x,y]=(255,255,255)
        # Make an artificial solid dark-blue rectangle rather than any glyph.
        for y in range(256,302):
            for x in range(1376,1417):
                px[x,y]=BLUE_COLORS[0]
        result=read_batter_numbers(im)
        self.assertIsNone(result["rows"][0]["at_bats"])
        self.assertEqual(result["rows"][0]["field_status"]["at_bats"],"UNKNOWN_GLYPH")

    def test_read_image_integrates_source_hash_and_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"synthetic_batter.png"
            im=batting_page(self.top)
            im.save(path)
            result=read_image(path)
            self.assertEqual(result["screen_type"],"BATTER_RESULTS")
            self.assertEqual(result["source"]["sha256"],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(result["numeric_results"]["status"],"COMPLETE")

    def test_pitcher_read_image_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"synthetic_pitcher.png"
            pitcher_page().save(path)
            result=read_image(path)
            self.assertEqual(result["screen_type"],"PITCHER_RESULTS")
            self.assertEqual(result["numeric_results"]["fields"]["strikeouts"],5)


if __name__=="__main__":
    unittest.main()
