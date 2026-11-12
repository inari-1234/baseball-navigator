"""Source-grade postload origin is not historic SAVE reconciliation."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path
from postload_fixture import POSTLOAD

from live_state_engine import read_events
from save_baseline_preflight import assess_current_capture, BaselinePreflightError

ROOT = Path(__file__).resolve().parents[1]


class CurrentSavePreflight(unittest.TestCase):
    def setUp(self):
        self.state = json.loads((POSTLOAD / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        self.ledger = json.loads((POSTLOAD / "CURRENT_RUN_LEDGER.yaml").read_text(encoding="utf-8"))
        self.events = read_events(POSTLOAD / "LIVE_EVENTS.jsonl")

    def check(self, state=None, events=None, ledger=None):
        return assess_current_capture(
            self.state if state is None else state,
            self.events if events is None else events,
            self.ledger if ledger is None else ledger)

    def test_current_capture_is_read_only_origin_not_action_approval(self):
        result = self.check()
        self.assertEqual(result["status"], "POSTLOAD_CAPTURE_VERIFIED_HISTORY_UNKNOWN")
        self.assertEqual(result["captured"]["clock"], "PM 5:20")
        self.assertEqual(result["captured"]["period"], "Y1-06")
        self.assertEqual(result["captured"]["money_yen"], 15980)
        self.assertEqual(result["captured"]["points"]["sports"], 28)
        self.assertEqual(result["source_event_seq"], 10)
        self.assertFalse(result["trusted_timeline"])
        self.assertFalse(result["rebaseline_ready"])
        self.assertFalse(result["action_authorized"])
        self.assertFalse(result["side_effects"])
        self.assertIn("RETAINED_PRELOAD_TRAINING_COUNTS", result["unverified"])
        self.assertEqual(result["next_evidence"]["type"], "CURRENT_PLAYER_SCREEN")

    def test_unsupported_timeline_does_not_automatically_become_trusted(self):
        state = copy.deepcopy(self.state)
        state["timeline_status"] = "TRUSTED"
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "CURRENT_STATE_REPLAY_MISMATCH"):
            self.check(state=state)

    def test_missing_or_hedged_user_capture_attestation_fails(self):
        ledger = copy.deepcopy(self.ledger)
        fact = next(x for x in ledger["facts"]
                    if x.get("path") == "new_run.current.image_capture_relation_to_save_load")
        fact["value"]["post_load_immediate"] = False
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "POSTLOAD_CLAIM_NOT_CONSERVATIVE"):
            self.check(ledger=ledger)
        ledger = copy.deepcopy(self.ledger)
        fact = next(x for x in ledger["facts"]
                    if x.get("path") == "new_run.current.image_capture_relation_to_save_load")
        fact["value"]["restored_save_checkpoint"] = "KNOWN_FROM_IMAGE"
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "POSTLOAD_CLAIM_NOT_CONSERVATIVE"):
            self.check(ledger=ledger)

    def test_reused_historical_skill_or_exact_count_never_passes(self):
        state = copy.deepcopy(self.state)
        state["training_counts_exact_by_player_drill"] = {"たき|素振り": 3}
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "CURRENT_STATE_REPLAY_MISMATCH"):
            self.check(state=state)
        ledger = copy.deepcopy(self.ledger)
        ledger["current_gate"]["status"] = "READY"
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "SAVEPOINT_UNKNOWN_GATE_MUST_REMAIN_BLOCKED"):
            self.check(ledger=ledger)

    def test_fake_capture_hash_and_wrong_event_fail(self):
        ledger = copy.deepcopy(self.ledger)
        fact = next(x for x in ledger["facts"]
                    if x.get("path") == "new_run.current.image_capture_relation_to_save_load")
        fact["value"]["image_sha256"] = "0" * 64
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "CAPTURE_RAW_EVIDENCE_NOT_FOUND"):
            self.check(ledger=ledger)
        state = copy.deepcopy(self.state)
        state["resources"]["last_observed"] = "NONEXISTENT"
        with self.assertRaisesRegex(BaselinePreflightError,
                                     "CURRENT_STATE_REPLAY_MISMATCH"):
            self.check(state=state)

    def test_no_mutation_to_canonical_inputs(self):
        before = (copy.deepcopy(self.state), copy.deepcopy(self.events),
                  copy.deepcopy(self.ledger))
        self.check()
        self.assertEqual((self.state, self.events, self.ledger), before)


if __name__ == "__main__":
    unittest.main()
