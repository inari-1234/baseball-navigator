import json
import re
import unittest
from pathlib import Path
from postload_fixture import POSTLOAD

ROOT=Path(__file__).resolve().parents[1]

class UploadedRosterCandidateGate(unittest.TestCase):
    def test_source_manifest_is_complete_but_not_promoted(self):
        report=json.loads((ROOT/"ROSTER_SCREEN_CANDIDATE_20261111.json").read_text(encoding="utf-8"))
        self.assertEqual(report["type"],"UNCOMMITTED_ROSTER_SCREEN_OBSERVATION")
        self.assertEqual(report["evidence_status"],"PENDING_CURRENT_SAVE_CHRONOLOGY")
        self.assertFalse(report["accepted_live_event"])
        self.assertFalse(report["action_authorized"])
        self.assertFalse(report["current_save_continuity_verified"])
        self.assertIsNone(report["game_clock_from_this_source"])
        self.assertIsNone(report["game_period_from_this_source"])
        self.assertEqual(report["image_count"],19)
        self.assertEqual(report["image_size_px"],[2622,1206])
        hashes=report["image_sha256_in_lexicographic_archive_order"]
        self.assertEqual(len(hashes),19)
        self.assertEqual(len(set(hashes)),19)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}",x) for x in hashes))
        self.assertEqual(len(report["roster"]),12)
        self.assertEqual([x["lineup"] for x in report["roster"][:9]],list(range(1,10)))
        self.assertTrue(all(x["bench"] for x in report["roster"][9:]))
        self.assertEqual(report["exact_training_counts_status"],"UNKNOWN")
        self.assertEqual(report["current_acquired_skill_names_status"],"UNVERIFIED_FROM_THIS_SOURCE")
        self.assertFalse(report["private_image_backup_verified"])
        self.assertFalse(report["original_image_bytes_in_public_repository"])
    def test_live_state_remains_untrusted_and_game_events_unchanged(self):
        report=json.loads((ROOT/"ROSTER_SCREEN_CANDIDATE_20261111.json").read_text(encoding="utf-8"))
        state=json.loads((POSTLOAD/"CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_event_seq"],report["reference_live_event_seq"])
        self.assertEqual(state["timeline_status"],"ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN")
        self.assertEqual(state.get("training_counts_by_player_drill"),{})
        self.assertEqual(state.get("skills"),[])
        ledger=json.loads((POSTLOAD/"CURRENT_RUN_LEDGER.yaml").read_text(encoding="utf-8"))
        self.assertEqual(ledger["current_gate"]["status"],"BLOCKED_UNKNOWN")

if __name__ == "__main__":
    unittest.main()
