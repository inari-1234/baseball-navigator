import unittest
from live_state_engine import replay, validate_recommendation, ObservationError

def e(n,kind,month=6,**fields):
    return {"seq":n,"event_id":f"E{n}","kind":kind,
            "source":{"kind":"USER_REPORT","locator":"test"}, "period":{"year":1,"month":month},**fields}

def screen(n,month=6):
    return e(n,"SCREEN",month,branch="ACCEPTED",resources={"study":4,"sports":28,"play":25,"nature":18,"cheer":100})

class LiveStateRegression(unittest.TestCase):
    def test_registration_is_not_result(self):
        s=replay([e(1,"MATCH_SCHEDULE",7,entries=[{"match_id":"J1","opponent":"まんるい"}])])
        self.assertEqual(s["matches"]["J1"]["status"],"SCHEDULED")
    def test_reset_result_retains_first_branch(self):
        s=replay([e(1,"MATCH_ATTEMPT",match_id="M",opponent="生南",attempt=1,our_runs=0,their_runs=1,branch="REJECTED"),
                  e(2,"MATCH_ATTEMPT",match_id="M",opponent="生南",attempt=2,our_runs=3,their_runs=0,branch="ACCEPTED")])
        self.assertEqual(s["matches"]["M"]["first_attempt"]["our_runs"],0)
        self.assertEqual(s["matches"]["M"]["classification"],"RESET_ASSISTED_WIN")
    def test_late_user_correction(self):
        s=replay([e(1,"MATCH_ATTEMPT",match_id="M",opponent="仮",attempt=1,our_runs=3,their_runs=0,branch="ACCEPTED"),
                  e(2,"CORRECTION",target_event_id="E1",patch={"opponent":"生南"})])
        self.assertEqual(s["matches"]["M"]["opponent"],"生南")
    def test_july_complete_blocks_july_future_advice(self):
        s=replay([e(1,"MATCH_SCHEDULE",7,entries=[{"match_id":"J1","opponent":"まんるい"}]),
                  e(2,"MATCHES_COMPLETED",7)])
        self.assertEqual(s["matches"]["J1"]["status"],"COMPLETED_SCORE_UNKNOWN")
        errors=validate_recommendation({"based_on_event_seq":2,"rule_ids":["DC-PROC-001"],
                                        "target_match_id":"J1"},s,{"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("ALREADY_COMPLETED_MATCH",errors)
    def test_screen_resources_expire_after_later_game(self):
        s=replay([screen(1),e(2,"MATCHES_COMPLETED",7)])
        self.assertIsNone(s["resources"]["values"])
        self.assertFalse(s["resources"]["fresh"])
        errors=validate_recommendation({"based_on_event_seq":2,"rule_ids":["DC-TRAIN-001"],
                                        "spend":{"sports":7}},s,{"rules":[{"rule_id":"DC-TRAIN-001","status":"ACTIVE"}]})
        self.assertIn("STALE_RESOURCES",errors)
    def test_old_june_screenshot_ignored_after_july_complete(self):
        s=replay([e(1,"MATCHES_COMPLETED",7),screen(2)])
        self.assertEqual(s["observations_ignored_as_stale"],["E2"])
        self.assertFalse(s["resources"]["fresh"])
    def test_no_invented_partial_resource_values(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"SCREEN",branch="ACCEPTED",resources={"sports":28})])
    def test_rollback_expires_snapshot(self):
        s=replay([screen(1),e(2,"ROLLBACK")])
        self.assertFalse(s["resources"]["fresh"])
    def test_two_accepted_branches_rejected(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"MATCH_ATTEMPT",match_id="M",opponent="花さか",attempt=1,our_runs=3,their_runs=1,branch="ACCEPTED"),
                    e(2,"MATCH_ATTEMPT",match_id="M",attempt=2,our_runs=6,their_runs=1,branch="ACCEPTED")])
    def test_missing_first_attempt_never_stable(self):
        s=replay([e(1,"MATCH_ATTEMPT",match_id="M",opponent="花さか",attempt=2,our_runs=6,their_runs=1,branch="ACCEPTED")])
        self.assertEqual(s["matches"]["M"]["classification"],"RESET_ASSISTED_WIN")
    def test_stale_state_revision_rejected(self):
        s=replay([e(1,"MATCHES_COMPLETED",7)])
        errors=validate_recommendation({"based_on_event_seq":0,"rule_ids":["DC-PROC-001"]},s,
                                       {"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("STALE_REVISION",errors)
    def test_late_historical_game_preserves_new_snapshot(self):
        s=replay([screen(1,8),
                 e(2,"MATCH_ATTEMPT",7,match_id="J",opponent="まんるい",attempt=1,our_runs=3,their_runs=1,branch="ACCEPTED")])
        self.assertTrue(s["resources"]["fresh"])
    def test_late_historical_completion_preserves_new_snapshot(self):
        s=replay([screen(1,8),e(2,"MATCHES_COMPLETED",7)])
        self.assertTrue(s["resources"]["fresh"])

if __name__=="__main__":unittest.main()
