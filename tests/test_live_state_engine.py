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
        errors=validate_recommendation({"based_on_event_seq":2,"action_type":"MATCH","rule_ids":["DC-PROC-001"],
                                        "target_match_id":"J1"},s,{"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("ALREADY_COMPLETED_MATCH",errors)
    def test_screen_resources_expire_after_later_game(self):
        s=replay([screen(1),e(2,"MATCHES_COMPLETED",7)])
        self.assertIsNone(s["resources"]["values"])
        self.assertFalse(s["resources"]["fresh"])
        errors=validate_recommendation({"based_on_event_seq":2,"action_type":"TRAIN","cheer":"ON","participants":["入江","今井","芦田"],"rule_ids":["DC-TRAIN-001"],
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
        errors=validate_recommendation({"based_on_event_seq":0,"action_type":"OTHER","rule_ids":["DC-PROC-001"]},s,
                                       {"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("STALE_REVISION",errors)
    def test_late_historical_game_preserves_new_snapshot(self):
        s=replay([screen(1,8),
                 e(2,"MATCH_ATTEMPT",7,match_id="J",opponent="まんるい",attempt=1,our_runs=3,their_runs=1,branch="ACCEPTED")])
        self.assertTrue(s["resources"]["fresh"])
    def test_match_without_id_cannot_bypass_completion(self):
        state=replay([e(1,"MATCHES_COMPLETED",7)])
        errors=validate_recommendation({"based_on_event_seq":1,"action_type":"MATCH",
                "target_period":"Y1-07","rule_ids":["DC-PROC-001"]},state,
                {"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("MATCH_ID_REQUIRED",errors)
        self.assertIn("COMPLETED_PERIOD_MATCH",errors)
    def test_training_without_cost_cannot_bypass_stale_resource(self):
        state=replay([e(1,"MATCHES_COMPLETED",7)])
        errors=validate_recommendation({"based_on_event_seq":1,"action_type":"TRAIN",
                "participants":["石渡","たき","芦田"],"cheer":"ON","rule_ids":["DC-TRAIN-001"]},state,
                {"rules":[{"rule_id":"DC-TRAIN-001","status":"ACTIVE"}]})
        self.assertIn("TRAINING_COST_REQUIRED",errors)
        self.assertIn("STALE_RESOURCES",errors)
    def test_same_month_older_screen_does_not_reopen_state(self):
        state=replay([e(1,"MATCHES_COMPLETED",7),
                      e(2,"SCREEN",7,branch="ACCEPTED",
                        resources={"study":4,"sports":28,"play":25,"nature":18,"cheer":100})])
        self.assertEqual(state["observations_ignored_as_stale"],["E2"])
        self.assertFalse(state["resources"]["fresh"])
    def test_explicit_confirmed_current_screen_reopens_state(self):
        state=replay([e(1,"MATCHES_COMPLETED",7),
                      e(2,"SCREEN",7,branch="ACCEPTED",after_event_id="E1",
                        resources={"study":4,"sports":28,"play":25,"nature":18,"cheer":100})])
        self.assertTrue(state["resources"]["fresh"])
    def test_rollback_removes_discarded_skill(self):
        s=replay([screen(1),e(2,"TRAINING",participants=["入江","今井","芦田"],drill="素振り",drill_level=1,cheer="OFF",skill_awards=[{"player":"入江","skill":"ミート力アップ"}],branch="ACCEPTED"),
                  e(3,"ROLLBACK",restore_to_event_id="E1")])
        self.assertEqual(s["skills"],[])
        self.assertEqual(s["discarded_branch_event_ids"],["E2"])
        self.assertFalse(s["resources"]["fresh"])
        self.assertEqual(s["timeline_status"],"TRUSTED")
    def test_rollback_removes_discarded_match(self):
        s=replay([screen(1),e(2,"MATCH_ATTEMPT",match_id="M",opponent="生南",attempt=1,our_runs=3,their_runs=0,branch="ACCEPTED"),
                  e(3,"ROLLBACK",restore_to_event_id="E1")])
        self.assertEqual(s["matches"],{})
        self.assertIn("E2",s["discarded_branch_event_ids"])
    def test_rollback_removes_discarded_item_effect(self):
        s=replay([screen(1),e(2,"ITEM_USE",branch="ACCEPTED",items=[{"name":"バナナ","quantity":3}],observed_delta={"wisdom":11}),
                  e(3,"ROLLBACK",restore_to_event_id="E1")])
        self.assertEqual(s["item_uses"],[])
    def test_unanchored_rollback_blocks_unsafe_advice(self):
        s=replay([screen(1),e(2,"ROLLBACK")])
        self.assertEqual(s["timeline_status"],"UNKNOWN_AFTER_ROLLBACK")
        errors=validate_recommendation({"based_on_event_seq":2,"action_type":"TRAIN","rule_ids":["DC-TRAIN-001"],
                 "participants":["入江","今井","長島"],"cheer":"ON","spend":{"sports":7,"cheer":20}},
                 s,{"rules":[{"rule_id":"DC-TRAIN-001","status":"ACTIVE"}]})
        self.assertIn("UNRESOLVED_ROLLBACK",errors)
    def test_explicit_recap_after_unanchored_rollback(self):
        s=replay([screen(1),e(2,"ROLLBACK"),e(3,"SCREEN",after_event_id="E2",branch="ACCEPTED",
            resources={"study":4,"sports":28,"play":25,"nature":18,"cheer":100})])
        self.assertEqual(s["timeline_status"],"RECAPTURED_AFTER_UNANCHORED_ROLLBACK")
        self.assertTrue(s["resources"]["fresh"])
    def test_bad_rollback_anchor_is_rejected(self):
        with self.assertRaises(ObservationError):
            replay([screen(1),e(2,"ROLLBACK",restore_to_event_id="NEVER_EXISTED")])
    def test_old_same_month_screen_after_match_is_stale(self):
        s=replay([screen(1),e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",
           attempt=1,our_runs=4,their_runs=1,branch="ACCEPTED"),screen(3)])
        self.assertIn("E3",s["observations_ignored_as_stale"])
        self.assertFalse(s["resources"]["fresh"])
    def test_evidenced_same_month_screen_after_match_is_fresh(self):
        s=replay([screen(1),e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",
           attempt=1,our_runs=4,their_runs=1,branch="ACCEPTED"),
           e(3,"SCREEN",after_event_id="E2",branch="ACCEPTED",
              resources={"study":4,"sports":28,"play":25,"nature":18,"cheer":100})])
        self.assertTrue(s["resources"]["fresh"])
    def test_old_month_scheduled_match_is_not_actionable(self):
        s=replay([e(1,"MATCH_SCHEDULE",entries=[{"match_id":"OLD","opponent":"生南"}]),screen(2,7)])
        errs=validate_recommendation({"based_on_event_seq":2,"action_type":"MATCH",
          "target_match_id":"OLD","rule_ids":["DC-MATCH-001"]},s,
          {"rules":[{"rule_id":"DC-MATCH-001","status":"ACTIVE"}]})
        self.assertIn("PAST_PERIOD_MATCH",errs)
    def test_cheer_on_requires_actual_cheer_cost(self):
        s=replay([screen(1)])
        errs=validate_recommendation({"based_on_event_seq":1,"action_type":"TRAIN","rule_ids":["DC-TRAIN-001"],
          "participants":["入江","今井","長島"],"cheer":"ON","spend":{"sports":7}},s,
          {"rules":[{"rule_id":"DC-TRAIN-001","status":"ACTIVE"}]})
        self.assertIn("CHEER_COST_REQUIRED",errs)
    def test_item_recommendations_fail_closed_without_inventory(self):
        s=replay([screen(1)])
        errs=validate_recommendation({"based_on_event_seq":1,"action_type":"ITEM","rule_ids":["DC-ITEM-001"]},
          s,{"rules":[{"rule_id":"DC-ITEM-001","status":"ACTIVE"}]})
        self.assertIn("ITEM_INVENTORY_NOT_VERIFIED",errs)
    def test_match_period_mismatch_is_rejected(self):
        s=replay([e(1,"MATCH_SCHEDULE",7,entries=[{"match_id":"J1","opponent":"まんるい"}])])
        errs=validate_recommendation({"based_on_event_seq":1,"action_type":"MATCH","rule_ids":["DC-MATCH-001"],
          "target_match_id":"J1","target_period":"Y1-08"},s,
          {"rules":[{"rule_id":"DC-MATCH-001","status":"ACTIVE"}]})
        self.assertIn("MATCH_PERIOD_CONFLICT",errs)
    def test_existing_screenshot_fact_fixture(self):
        from live_state_engine import read_events
        events=read_events("LIVE_EVENTS.jsonl")
        snapshot=next(x for x in events if x["event_id"]=="LIVE-Y1-JUN-POST-HANASAKA-SCREEN")
        self.assertEqual(snapshot["resources"],{"study":4,"sports":28,"play":25,"nature":18,"cheer":100})
        self.assertEqual(snapshot["money_yen"],15980)
        self.assertEqual(snapshot["after_event_id"],"LIVE-Y1-JUN-HANASAKA-ACCEPTED")
    def test_training_counts_only_committed_participants(self):
        s=replay([e(1,"TRAINING",participants=["石渡","たき","岡治"],drill="シャドー",drill_level=1,
                  cheer="ON",branch="ACCEPTED",skill_awards=[{"player":"石渡","skill":"コントロールアップ"}]),
                  e(2,"TRAINING",participants=["石渡","たき","岡治"],drill="シャドー",drill_level=1,
                  cheer="ON",branch="REJECTED",skill_awards=[])])
        self.assertEqual(s["training_counts_observed"]["石渡"]["シャドー"],1)
        self.assertEqual(s["training_counts_observed"]["岡治"]["シャドー"],1)
        self.assertEqual(len(s["skills"]),1)
        self.assertEqual(len(s["training_history"]),1)
    def test_rollback_resets_training_counts(self):
        s=replay([screen(1),e(2,"TRAINING",participants=["石渡","たき","岡治"],drill="シャドー",drill_level=1,
                  cheer="ON",branch="ACCEPTED",skill_awards=[]),e(3,"ROLLBACK",restore_to_event_id="E1")])
        self.assertEqual(s["training_counts_observed"],{})
    def test_training_skill_must_be_awarded_to_participant(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"TRAINING",participants=["石渡","たき","岡治"],drill="シャドー",drill_level=1,
                      cheer="ON",branch="ACCEPTED",skill_awards=[{"player":"入江","skill":"ジャストミート"}])])
    def test_match_wide_correction_updates_all_attempts(self):
        events=[e(1,"MATCH_SCHEDULE",entries=[{"match_id":"M","opponent":"仮"}]),
                e(2,"MATCH_ATTEMPT",match_id="M",opponent="仮",attempt=1,our_runs=0,their_runs=1,branch="REJECTED"),
                e(3,"MATCH_ATTEMPT",match_id="M",opponent="仮",attempt=2,our_runs=3,their_runs=0,branch="ACCEPTED"),
                e(4,"CORRECTION",target_match_id="M",patch={"opponent":"生南"})]
        s=replay(events)
        self.assertEqual(s["matches"]["M"]["opponent"],"生南")
        self.assertEqual(events[0]["entries"][0]["opponent"],"仮")
    def test_match_wide_correction_unknown_id_fails(self):
        with self.assertRaises(ObservationError):
            replay([screen(1),e(2,"CORRECTION",target_match_id="NOT_FOUND",patch={"opponent":"生南"})])
    def test_late_historical_completion_preserves_new_snapshot(self):
        s=replay([screen(1,8),e(2,"MATCHES_COMPLETED",7)])
        self.assertTrue(s["resources"]["fresh"])

if __name__=="__main__":unittest.main()
