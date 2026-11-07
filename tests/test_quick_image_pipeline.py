"""P5 fast-image and dry-run ingestion safety regressions; no user PNGs in Git."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from live_state_engine import read_events
from quick_image_pipeline import (
    QuickImageError, QuickImageSession, benchmark_local, _compact,
)

ROOT = Path(__file__).resolve().parents[1]


def state_events():
    state = json.loads((ROOT/"CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
    events = read_events(ROOT/"LIVE_EVENTS.jsonl")
    return state, events


class QuickImageSuite(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.path = self.root/"source.png"
        Image.new("RGB", (640, 360), (140, 162, 182)).save(self.path)
        self.state, self.events = state_events()
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.screen_id = "LIVE-Y1-JUN-CURRENT-IMG8971-8972-20261106"

    def _fake_reader(self, category="WORLD_UI_OR_OVERLAY"):
        return {
            "screen_type": category, "positions": {},
            "source": {"sha256": self.digest, "filename": self.path.name},
            "image_size": [640, 360],
        }

    def _review(self, kind="SCREEN", **overrides):
        result = {
            "schema_version": "1.0", "reviewed_image_sha256": self.digest,
            "expected_event_seq": self.state["last_event_seq"],
            "kind": kind, "event_id": "P5-PREVIEW-11",
            "period": {"year":1,"month":6}, "branch": "ACCEPTED",
            "after_event_id": self.screen_id, "source_reviewed_current": True,
        }
        if kind == "SCREEN":
            result.update({
                "clock": "PM 5:30",
                "resources": {"study":4, "sports":25, "play":25,
                              "nature":18, "cheer":80},
                "all_resource_values_verified_in_image": True,
            })
        else:
            result["verified_slot_players"] = {"P":"石渡"}
        result.update(overrides)
        return result

    def _screen_draft(self, review=None):
        with patch("quick_image_pipeline.read_image",
                   return_value=self._fake_reader()):
            return QuickImageSession().draft(
                self.path, review=self._review() if review is None else review,
                state=self.state, events=self.events)

    def test_quick_image_reader_returns_fact_without_state_mutation(self):
        before = self.path.read_bytes()
        res = QuickImageSession().inspect(self.path)
        self.assertEqual(res["source_sha256"], self.digest)
        self.assertFalse(res["proposed_game_mutation"])
        self.assertFalse(res["action_authorized"])
        self.assertTrue(res["human_review_required_for_ingestion"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_same_content_reuses_pixel_decode_and_preserves_provenance(self):
        original = QuickImageSession(max_cache=2)
        with patch("quick_image_pipeline.read_image", wraps=original_read_image) as spy:
            first = original.inspect(self.path)
            second = original.inspect(self.path)
            self.assertEqual(spy.call_count, 1)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(original.read_calls, 1)
        self.assertEqual(original.cache_hits, 1)
        self.assertEqual(first["source_sha256"], second["source_sha256"])

    def test_copied_identical_bytes_get_new_filename_without_second_decode(self):
        clone = self.root/"alternate.png"
        clone.write_bytes(self.path.read_bytes())
        session = QuickImageSession()
        with patch("quick_image_pipeline.read_image", wraps=original_read_image) as spy:
            session.inspect(self.path)
            b = session.inspect(clone)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(b["source"]["filename"],"alternate.png")
        self.assertEqual(b["source_sha256"],self.digest)

    def test_changed_bytes_force_new_decode_even_same_filename(self):
        session = QuickImageSession()
        with patch("quick_image_pipeline.read_image", wraps=original_read_image) as spy:
            session.inspect(self.path)
            Image.new("RGB", (640, 360), (35, 42, 51)).save(self.path)
            b = session.inspect(self.path)
        self.assertEqual(spy.call_count, 2)
        self.assertNotEqual(b["source_sha256"], self.digest)

    def test_benchmark_scope_and_cold_warm_measured_not_synthetic_time_claim(self):
        result = benchmark_local(self.path, 5)
        self.assertEqual(result["repeats"], 5)
        self.assertEqual(result["unique_pixel_decode_calls"], 1)
        self.assertFalse(result["chat_latency_measured"])
        self.assertFalse(result["real_ios_screen_accuracy_benchmarked"])
        self.assertGreaterEqual(result["cold_first_ms"], 0)
        self.assertGreaterEqual(result["warm_median_ms"], 0)

    def test_bad_benchmark_argument_rejected(self):
        with self.assertRaisesRegex(QuickImageError, "BENCHMARK_REPEATS_INVALID"):
            benchmark_local(self.path, 1)

    def test_invalid_image_bytes_fails_closed(self):
        self.path.write_bytes(b"not an image")
        with self.assertRaisesRegex(QuickImageError, "IMAGE_DECODE_FAILED"):
            QuickImageSession().inspect(self.path)

    def test_symlink_image_rejected(self):
        link=self.root/"link.png"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(QuickImageError, "IMAGE_MISSING_OR_SYMLINK"):
            QuickImageSession().inspect(link)

    def test_resource_candidate_replayed_without_game_state_or_file_changes(self):
        old_state=copy.deepcopy(self.state)
        old_events=copy.deepcopy(self.events)
        before=(ROOT/"LIVE_EVENTS.jsonl").read_bytes()
        draft=self._screen_draft()
        self.assertEqual(draft["event_draft"]["kind"],"SCREEN")
        self.assertEqual(draft["event_draft"]["source"]["kind"],"RAW_SCREEN")
        self.assertIn(self.digest,draft["event_draft"]["source"]["locator"])
        self.assertEqual(draft["preview_event_seq"],11)
        self.assertEqual(draft["preview_resource_values"]["sports"],25)
        self.assertEqual(draft["preview_timeline_status"],
                         "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN")
        self.assertEqual(draft["status"],"PROVISIONAL_ROLLBACK_OR_BRANCH_UNVERIFIED")
        self.assertFalse(draft["committed_to_live_events"])
        self.assertFalse(draft["repository_mutated"])
        self.assertFalse(draft["action_authorized"])
        self.assertEqual(old_state,self.state)
        self.assertEqual(old_events,self.events)
        self.assertEqual(before,(ROOT/"LIVE_EVENTS.jsonl").read_bytes())

    def test_source_digest_mismatch_never_generates_event(self):
        with self.assertRaisesRegex(QuickImageError,"SOURCE_IMAGE_HASH_MISMATCH"):
            self._screen_draft(self._review(reviewed_image_sha256="b"*64))

    def test_stale_event_revision_is_rejected(self):
        with self.assertRaisesRegex(QuickImageError,"STALE_STATE_REVISION"):
            self._screen_draft(self._review(expected_event_seq=9))

    def test_unknown_source_branch_rejected(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "CURRENT_ACCEPTED_SOURCE_ATTESTATION_REQUIRED"):
            self._screen_draft(self._review(branch="REJECTED"))

    def test_false_source_review_flag_rejected(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "CURRENT_ACCEPTED_SOURCE_ATTESTATION_REQUIRED"):
            self._screen_draft(self._review(source_reviewed_current=False))

    def test_missing_after_event_id_rejected(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "VERIFIED_CHRONOLOGY_ANCHOR_REQUIRED"):
            self._screen_draft(self._review(after_event_id="does-not-exist"))

    def test_past_screen_anchor_is_rejected_even_if_the_old_event_exists(self):
        prior = next(e["event_id"] for e in self.events
                     if e["kind"] == "SCREEN" and e["event_id"] != self.screen_id)
        with self.assertRaisesRegex(QuickImageError,
                                    "CHRONOLOGY_NOT_LATEST_ACCEPTED_CONTEXT"):
            self._screen_draft(self._review(after_event_id=prior))

    def test_same_image_cannot_be_reingested_under_new_event_id(self):
        events=copy.deepcopy(self.events)
        original=next(e for e in events if e["event_id"] == self.screen_id)
        original["source"]["locator"] += " #sha256="+self.digest
        with patch("quick_image_pipeline.read_image",
                   return_value=self._fake_reader()):
            with self.assertRaisesRegex(QuickImageError,
                                        "DUPLICATE_IMAGE_EVIDENCE"):
                QuickImageSession().draft(self.path, review=self._review(),
                                          state=self.state, events=events)

    def test_new_screen_with_older_game_clock_is_not_allowed(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "SCREENSHOT_DRAFT_DISCARDED_AS_STALE"):
            self._screen_draft(self._review(clock="PM 5:10"))

    def test_incomplete_resource_counter_rejected(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "INCOMPLETE_OR_INVALID_RESOURCE_COUNTERS"):
            self._screen_draft(self._review(
                resources={"study":4, "sports":25}))

    def test_bool_resource_rejected_as_integer(self):
        values=self._review()["resources"]
        values["cheer"]=True
        with self.assertRaisesRegex(QuickImageError,
                                    "INCOMPLETE_OR_INVALID_RESOURCE_COUNTERS"):
            self._screen_draft(self._review(resources=values))

    def test_unknown_money_or_other_extra_field_rejected(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "REVIEW_FIELDS_NOT_ALLOWLISTED"):
            self._screen_draft(self._review(skills=["ミート力アップ"]))

    def test_not_a_source_verified_resource_layout_rejected(self):
        with patch("quick_image_pipeline.read_image",
                   return_value=self._fake_reader("ITEM_USE_MENU")):
            with self.assertRaisesRegex(QuickImageError,
                                        "RESOURCE_SCREEN_LAYOUT_NOT_SUPPORTED_BY_P5"):
                QuickImageSession().draft(self.path, review=self._review(),
                                          state=self.state, events=self.events)

    def test_resource_values_still_require_explicit_human_visual_confirmation(self):
        with self.assertRaisesRegex(QuickImageError,
                                    "RESOURCE_VALUES_NOT_SOURCE_VERIFIED"):
            self._screen_draft(self._review(
                all_resource_values_verified_in_image=False))

    def test_duplicate_event_id_rejected(self):
        with self.assertRaisesRegex(QuickImageError, "FRESH_EVENT_ID_REQUIRED"):
            self._screen_draft(self._review(event_id=self.screen_id))

    def test_canonical_projection_conflict_rejected(self):
        state=copy.deepcopy(self.state)
        state["resources"]["values"]["sports"]=0
        with patch("quick_image_pipeline.read_image",
                   return_value=self._fake_reader()):
            with self.assertRaisesRegex(QuickImageError,
                                        "CANONICAL_STATE_PROJECTION_MISMATCH"):
                QuickImageSession().draft(self.path, review=self._review(),
                                          state=state, events=self.events)

    def test_stale_after_event_chronology_for_hp_blocks(self):
        from test_screen_reader import fixture
        fixture().save(self.path)
        sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        review=self._review(kind="HP_OBSERVATION",
                            reviewed_image_sha256=sha,
                            after_event_id="LIVE-Y1-JUL-COMPLETION-RETRACTED-20261106")
        # The wrong after-event anchor is an existing event but is NOT the
        # current accepted screenshot context for HP.
        with self.assertRaisesRegex(QuickImageError,
                                    "CHRONOLOGY_NOT_LATEST_ACCEPTED_CONTEXT"):
            QuickImageSession().draft(self.path, review=review,
                                      state=self.state, events=self.events)

    def test_live_formation_hp_draft_requires_verified_player_mapping(self):
        from test_screen_reader import fixture
        fixture().save(self.path)
        sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        r=self._review(kind="HP_OBSERVATION",reviewed_image_sha256=sha)
        response=QuickImageSession().draft(self.path,review=r,
                                           state=self.state,events=self.events)
        self.assertEqual(response["event_draft"]["kind"],"HP_OBSERVATION")
        self.assertEqual(response["event_draft"]["entries"][0]["player"],"石渡")
        self.assertEqual(response["preview_hp_players"],["石渡"])
        self.assertNotIn("hp_numeric_percent",response["event_draft"]["entries"][0])
        self.assertFalse(response["action_authorized"])
        self.assertFalse(response["committed_to_live_events"])

    def test_unverified_player_in_formation_is_never_inferred_from_position(self):
        from test_screen_reader import fixture
        fixture().save(self.path)
        sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        r=self._review(kind="HP_OBSERVATION",reviewed_image_sha256=sha,
                       verified_slot_players={})
        with self.assertRaisesRegex(QuickImageError,
                                    "VERIFIED_UNIQUE_SLOT_PLAYERS_REQUIRED"):
            QuickImageSession().draft(self.path,review=r,
                                      state=self.state,events=self.events)

    def test_navigator_cli_image_first_path_never_writes_game_events(self):
        import subprocess
        import sys
        old=(ROOT/"LIVE_EVENTS.jsonl").read_bytes()
        result=subprocess.run([
            sys.executable,str(ROOT/"navigator_step.py"),"画像を確認して",
            "--image",str(self.path),"--expected-event-seq","10"],
            cwd=ROOT,capture_output=True,text=True,check=True)
        out=json.loads(result.stdout)
        self.assertEqual(out["status"],"UNSUPPORTED_SCREEN_NEEDS_MANUAL_REVIEW")
        self.assertEqual(out["component"],"navigator_step+p5_image")
        self.assertEqual(out["source_sha256"],self.digest)
        self.assertFalse(out["candidate_event_committed"])
        self.assertFalse(out["side_effects"])
        self.assertEqual((ROOT/"LIVE_EVENTS.jsonl").read_bytes(),old)

    def test_navigator_cli_image_review_requires_explicit_boot_and_revision(self):
        import subprocess
        import sys
        review=self.root/"review.json"
        review.write_text(json.dumps(self._review()),encoding="utf-8")
        result=subprocess.run([
            sys.executable,str(ROOT/"navigator_step.py"),"画像を確認して",
            "--image",str(self.path),"--image-review",str(review)],
            cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("P5_BOOT_REQUIRED_FOR_EVENT_PREVIEW",result.stderr)
        result=subprocess.run([
            sys.executable,str(ROOT/"navigator_step.py"),"画像を確認して",
            "--image",str(self.path),"--image-review",str(review),
            "--boot-verified"],
            cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("P5_EXACT_EXPECTED_EVENT_SEQ_REQUIRED",result.stderr)

    def test_navigator_cli_proposed_screen_stays_uncommitted_after_human_review(self):
        import subprocess
        import sys
        from PIL import Image
        # Synthetic test layout: only a WORLD_UI class signature, not real
        # HUD OCR or proof that displayed numbers match the review.
        native=self.root/"world.png"
        frame=Image.new("RGB",(2622,1206),(10,20,30))
        frame.putpixel((100,80),(10,150,240))
        frame.save(native)
        digest=hashlib.sha256(native.read_bytes()).hexdigest()
        r=self._review(reviewed_image_sha256=digest)
        review=self.root/"review.json"
        review.write_text(json.dumps(r),encoding="utf-8")
        result=subprocess.run([
            sys.executable,str(ROOT/"navigator_step.py"),"画像を確認して",
            "--image",str(native),"--image-review",str(review),
            "--boot-verified","--expected-event-seq","10"],
            cwd=ROOT,capture_output=True,text=True,check=True)
        out=json.loads(result.stdout)
        self.assertEqual(out["status"],"UNCOMMITTED_IMAGE_EVENT_PREVIEW")
        self.assertEqual(out["event_preview"]["preview_event_seq"],11)
        self.assertEqual(out["event_preview"]["preview_timeline_status"],
                         "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN")
        self.assertFalse(out["action_authorized"])
        self.assertFalse(out["candidate_event_committed"])

    def test_p5_handoff_and_agent_gate_are_preserved(self):
        handoff=(ROOT/"CURRENT_HANDOFF.md").read_text(encoding="utf-8")
        agents=(ROOT/"AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("quick_image_pipeline.py",handoff)
        self.assertIn("quick_image_pipeline.py",agents)
        self.assertIn("docs/P5_QUICK_IMAGE_PROTOCOL.md",handoff)
        self.assertIn("docs/P5_QUICK_IMAGE_PROTOCOL.md",agents)
        self.assertTrue((ROOT/"docs/P5_QUICK_IMAGE_PROTOCOL.md").is_file())

    def test_screenshot_menu_does_not_claim_inventory_or_item_use(self):
        result=_compact({
            "screen_type":"ITEM_USE_MENU",
            "source":{"filename":"test.png","sha256":self.digest},
            "item_use_page":{"status":"PASS_DRAFT",
                             "selected_item_name":"チョコレート",
                             "selected_item_stock":1,
                             "full_inventory_verified":False}})
        self.assertFalse(result["item_use"]["full_inventory_verified"])
        self.assertFalse(result["item_use"]["item_use_confirmed"])

    def test_batter_page_not_promoted_as_match_result(self):
        result=_compact({
            "screen_type":"BATTER_RESULTS",
            "source":{"filename":"test.png","sha256":self.digest},
            "batter_stats":{"status":"PASS","page":"TOP_1_TO_5",
                            "rows":[{"hits":2}],"team_total":None}})
        self.assertFalse(result["result_panel"]["match_id_verified"])
        self.assertFalse(result["result_panel"]["player_names_verified"])
        self.assertFalse(result["proposed_game_mutation"])


original_read_image = __import__("screen_reader").read_image

if __name__=="__main__":
    unittest.main()
