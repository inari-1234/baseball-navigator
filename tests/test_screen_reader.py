"""Synthetic pixel fixtures: no user screenshot bytes are committed."""
import hashlib
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
