"""P7-J: the loop continues after gameplay, and stale screenshots cannot pass."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

from capture_fixture import JST, exif_png, fresh_capture
from live_state_engine import read_events
from test_next_action import NextActionTests



class PlayLoopP7J(NextActionTests):
    def _rewrite_menu(self, sources, *, minutes_ago=1, stated=None, exif=True, suffix=".png"):
        menu = sources["MENU"]
        captured = fresh_capture(minutes_ago)
        self.case = getattr(self, "case", 0) + 1
        path = Path(menu["path"]).with_name(f"MENU-case{self.case}{suffix}")
        payload = b'{"synthetic": "menu without exif"}'
        path.write_bytes(exif_png(payload, captured) if exif else payload)
        menu["path"] = str(path)
        menu["sha256"] = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        menu["captured_at"] = stated if stated is not None else captured.isoformat()
        return sources

    def test_fresh_menu_capture_certifies(self):
        context, sources = self.development_fixture(contact=True)
        report = self.run_entry(context=context, evidence_sources=sources)
        self.assertEqual(report["status"], "CERTIFIED_TRAINING_DRAFT", report)

    def test_old_or_unbound_menu_capture_is_rejected(self):
        context, base_sources = self.development_fixture(contact=True)
        cases = (
            ("old", dict(minutes_ago=24 * 60 * 5), "CURRENT_CAPTURE_NOT_FRESH"),
            ("future", dict(minutes_ago=-30), "CURRENT_CAPTURE_NOT_FRESH"),
            ("mismatch", dict(stated=(fresh_capture() - timedelta(seconds=7)).isoformat()),
             "CAPTURE_TIME_MISMATCH"),
            ("no_offset", dict(stated=fresh_capture().replace(tzinfo=None).isoformat()),
             "CAPTURE_TIME_OFFSET_REQUIRED"),
            ("no_exif", dict(exif=False), "CAPTURE_TIME_UNSUPPORTED_FORMAT"),
            ("heic", dict(exif=False, suffix=".heic"), "CAPTURE_TIME_UNSUPPORTED_FORMAT"),
        )
        for name, kwargs, code in cases:
            with self.subTest(name):
                sources = self._rewrite_menu(deepcopy(base_sources), **kwargs)
                report = self.run_entry(context=context, evidence_sources=sources)
                self.assertEqual(report["status"], "CERTIFIED_NO_ACTION", report)
                self.assertIn(code, report["blocking_reasons"])
        sources = deepcopy(base_sources)
        sources["MENU"].pop("captured_at")
        report = self.run_entry(context=context, evidence_sources=sources)
        self.assertIn("CAPTURE_TIME_REQUIRED", report["blocking_reasons"])

    def _after_training(self, context):
        base = read_events(self.repo / "LIVE_EVENTS.jsonl")
        period, seq = base[-1]["period"], base[-1]["seq"]
        players = context["training_readiness"]["menu_selection"]["players"]
        training = {"seq": seq + 1, "event_id": "P7J-TRAIN-1", "kind": "TRAINING",
                    "branch": "ACCEPTED", "period": period, "drill": "素振り", "cheer": "ON",
                    "participants": players,
                    "source": {"kind": "USER_REPORT", "locator": "synthetic result"}}
        screen = {"seq": seq + 2, "event_id": "P7J-SCREEN-2", "kind": "SCREEN",
                  "branch": "ACCEPTED", "period": period, "after_event_id": "P7J-TRAIN-1",
                  "clock": "PM 5:30", "source": {"kind": "RAW_SCREEN", "locator": "synthetic"},
                  "resources": {"study": 4, "sports": 22, "play": 25, "nature": 18, "cheer": 80}}
        self.commit_fixture([*base, training, screen])
        updated = deepcopy(context)
        for claim in updated.values():
            claim["source_event_seq"] = self.state["last_event_seq"]
        updated["training_readiness"]["menu_selection"]["current_balances"] = {
            "sports": 22, "cheer": 80}
        return updated

    def test_second_cycle_keeps_roster_and_asks_only_for_changed_abilities(self):
        context, _ = self.development_fixture(contact=True)
        updated = self._after_training(context)
        self.assertNotIn("roster_invalidated_by_event_id", self.state["observed_tracking"])
        report = self.run_entry(context=updated, evidence_sources=self.sources(updated))
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION", report)
        self.assertIn("CURRENT_PLAYER_ABILITY_RECAPTURE_REQUIRED", report["blocking_reasons"])
        self.assertNotIn("CURRENT_OCTOBER_ROSTER_NOT_BOUND", report["blocking_reasons"])

        plan = updated["development_plan"]
        plan["evidence_refs"].append("ABILITY")
        plan["current_ability_evidence_refs"] = ["ABILITY"]
        plan["player_observation"]["ability_evidence_ref"] = "ABILITY"
        report = self.run_entry(context=updated, evidence_sources=self.sources(updated))
        self.assertEqual(report["status"], "CERTIFIED_TRAINING_DRAFT", report)
        self.assertEqual(report["safe_reply_check"]["status"], "PASS")

    def test_archive_image_cannot_stand_in_for_changed_abilities(self):
        context, _ = self.development_fixture(contact=True)
        updated = self._after_training(context)
        plan = updated["development_plan"]
        plan["current_ability_evidence_refs"] = ["ROSTER-IMAGE"]
        plan["player_observation"]["ability_evidence_ref"] = "ROSTER-IMAGE"
        report = self.run_entry(context=updated, evidence_sources=self.sources(updated))
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION", report)
        self.assertIn("CURRENT_PLAYER_ABILITY_RECAPTURE_REQUIRED", report["blocking_reasons"])


def load_tests(loader, tests, pattern):
    """Run only P7-J cases here; inherited fixtures stay in test_next_action."""
    import unittest
    names = [n for n in vars(PlayLoopP7J) if n.startswith("test_")]
    return unittest.TestSuite(PlayLoopP7J(n) for n in sorted(names))
