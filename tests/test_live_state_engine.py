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
        s=replay([e(1,"SAVE_CHECKPOINT"),screen(2),e(3,"ROLLBACK",to_checkpoint_id="E1")])
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
        s=replay([{**screen(1),"is_savepoint":True},e(2,"TRAINING",participants=["入江","今井","芦田"],drill="素振り",drill_level=1,cheer="OFF",skill_awards=[{"player":"入江","skill":"ミート力アップ"}],branch="ACCEPTED"),
                  e(3,"ROLLBACK",restore_to_event_id="E1")])
        self.assertEqual(s["skills"],[])
        self.assertEqual(s["discarded_branch_event_ids"],["E2"])
        self.assertFalse(s["resources"]["fresh"])
        self.assertEqual(s["timeline_status"],"TRUSTED")
    def test_rollback_removes_discarded_match(self):
        s=replay([{**screen(1),"is_savepoint":True},e(2,"MATCH_ATTEMPT",match_id="M",opponent="生南",attempt=1,our_runs=3,their_runs=0,branch="ACCEPTED"),
                  e(3,"ROLLBACK",restore_to_event_id="E1")])
        self.assertEqual(s["matches"],{})
        self.assertIn("E2",s["discarded_branch_event_ids"])
    def test_rollback_removes_discarded_item_effect(self):
        s=replay([{**screen(1),"is_savepoint":True},e(2,"ITEM_USE",branch="ACCEPTED",items=[{"name":"バナナ","quantity":3}],observed_delta={"wisdom":11}),
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
        s=replay([{**screen(1),"is_savepoint":True},e(2,"TRAINING",participants=["石渡","たき","岡治"],drill="シャドー",drill_level=1,
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
    def test_rollback_drops_skill_and_training_count(self):
        s=replay([e(1,"SAVE_CHECKPOINT"),
                  e(2,"TRAINING",drill="シャドー",participants=["石渡","たき","岡治"],
                    skill_awards=[{"player":"石渡","skill":"コントロールアップ"}],branch="ACCEPTED"),
                  e(3,"ROLLBACK",to_checkpoint_id="E1"),
                  e(4,"TRAINING",drill="シャドー",participants=["石渡","たき","岡治"],
                    skill_awards=[],branch="ACCEPTED")])
        self.assertEqual(s["skills"],[])
        self.assertEqual(s["training_counts_by_player_drill"]["石渡|シャドー"],1)
        self.assertIn("E2",s["reverted_event_ids"])
        self.assertEqual(s["rollback_count"],1)
    def test_rollback_drops_item_effect(self):
        s=replay([e(1,"SAVE_CHECKPOINT"),
                  e(2,"ITEM_USE",branch="ACCEPTED",
                    item_bundle=[{"item":"バナナ","quantity":3}],
                    effect_deltas={"wisdom":5,"control":3}),
                  e(3,"ROLLBACK",to_checkpoint_id="E1"),
                  e(4,"ITEM_USE",branch="ACCEPTED",
                    item_bundle=[{"item":"バナナ","quantity":3}],
                    effect_deltas={"wisdom":11,"control":0})])
        self.assertEqual(len(s["item_effects"]),1)
        self.assertEqual(s["item_effects"][0]["effect_deltas"],{"wisdom":11,"control":0})
    def test_rollback_removes_match_but_preserves_first_attempt_audit(self):
        s=replay([e(1,"SAVE_CHECKPOINT"),
                  e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",attempt=1,
                    our_runs=0,their_runs=1,branch="ACCEPTED"),
                  e(3,"ROLLBACK",to_checkpoint_id="E1"),
                  e(4,"MATCH_ATTEMPT",match_id="M",opponent="花さか",attempt=2,
                    our_runs=3,their_runs=0,branch="ACCEPTED")])
        self.assertEqual(s["matches"]["M"]["first_attempt"]["our_runs"],0)
        self.assertEqual(s["matches"]["M"]["accepted_attempt"]["our_runs"],3)
        self.assertEqual(s["matches"]["M"]["classification"],"RESET_ASSISTED_WIN")
    def test_rollback_refuses_invalid_explicit_checkpoint(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"ROLLBACK",to_checkpoint_id="NOT_A_REAL_SAVE")])
    def test_same_month_post_match_old_screen_rejected(self):
        s=replay([screen(1),e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",
                    attempt=1,our_runs=2,their_runs=0,branch="ACCEPTED"),
                  screen(3)])
        self.assertIn("E3",s["observations_ignored_as_stale"])
        self.assertFalse(s["resources"]["fresh"])
    def test_same_month_post_match_screen_must_name_transition(self):
        s=replay([screen(1),e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",
                    attempt=1,our_runs=2,their_runs=0,branch="ACCEPTED"),
                  e(3,"SCREEN",branch="ACCEPTED",observed_after_event_id="E2",
                    resources={"study":1,"sports":2,"play":3,"nature":4,"cheer":5})])
        self.assertTrue(s["resources"]["fresh"])
        self.assertEqual(s["resources"]["values"]["sports"],2)
    def test_same_month_older_clock_rejected(self):
        s=replay([e(1,"SCREEN",clock="PM 5:40",branch="ACCEPTED",
                     resources={"study":1,"sports":2,"play":3,"nature":4,"cheer":5}),
                  e(2,"SCREEN",clock="PM 3:00",branch="ACCEPTED",
                    resources={"study":1,"sports":28,"play":3,"nature":4,"cheer":5})])
        self.assertEqual(s["resources"]["values"]["sports"],2)
        self.assertIn("E2",s["observations_ignored_as_stale"])
    def test_match_requires_target_period(self):
        s=replay([e(1,"MATCH_SCHEDULE",7,entries=[{"match_id":"J1","opponent":"まんるい"}])])
        err=validate_recommendation({"action_type":"MATCH","target_match_id":"J1",
              "based_on_event_seq":1,"rule_ids":["DC-PROC-001"]},s,
              {"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("MATCH_PERIOD_REQUIRED",err)
    def test_cheer_on_requires_cost(self):
        s=replay([screen(1)])
        err=validate_recommendation({"action_type":"TRAIN","spend":{"sports":6},
              "participants":["入江","今井","芦田"],"cheer":"ON","based_on_event_seq":1,
              "rule_ids":["DC-PROC-001"]},s,
              {"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("CHEER_COST_REQUIRED",err)
    def test_missing_item_cost_is_not_free(self):
        s=replay([screen(1)])
        err=validate_recommendation({"action_type":"ITEM","based_on_event_seq":1,
              "rule_ids":["DC-PROC-001"]},s,
              {"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]})
        self.assertIn("COST_DECLARATION_REQUIRED",err)
    def test_training_counts_only_accepted(self):
        s=replay([e(1,"TRAINING",drill="素振り",branch="REJECTED",
                     participants=["入江","今井","芦田"],skill_awards=[]),
                  e(2,"TRAINING",drill="素振り",branch="ACCEPTED",
                     participants=["入江","今井","芦田"],skill_awards=[])])
        self.assertEqual(s["training_counts_by_player_drill"]["入江|素振り"],1)
    def test_item_with_fresh_inventory_still_requires_selection(self):
        screen_obs=e(1,"SCREEN",branch="ACCEPTED",resources={"study":0,"sports":8,"play":4,"nature":2,"cheer":50},
                     inventory={"バナナ":3})
        s=replay([screen_obs])
        errs=validate_recommendation({"action_type":"ITEM","spend":{},"based_on_event_seq":1,
             "rule_ids":["DC-ITEM-001"]},s,
             {"rules":[{"rule_id":"DC-ITEM-001","status":"ACTIVE"}]})
        self.assertIn("ITEM_SELECTION_REQUIRED",errs)
    def test_visual_hp_geometry_fixture_ishiwata(self):
        # Manually reviewed IMG_8932.png: green fill is not a numeric game-HP reading.
        obs=e(1,"HP_OBSERVATION",source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},
              branch="ACCEPTED",entries=[{"player":"石渡いなり","reading_kind":"VERTICAL_BAR",
              "identity_evidence":"SELECTED_PLAYER_PANEL",
              "geometry_px":{"center_x":1300,"track_top":543,"track_bottom":594,
                             "fill_top":557,"edge_uncertainty":1}}])
        state=replay([obs])
        hp=state["hp_by_player"]["石渡いなり"]
        self.assertEqual(hp["graphical_fill_estimate_pct"],72.5)
        self.assertEqual(hp["graphical_fill_range_pct"],[67,78])
        self.assertIsNone(hp["hp_numeric_percent"])
        self.assertEqual(hp["full_state"],"NOT_NEAR_FULL")
        self.assertTrue(hp["fresh"])
    def test_visual_hp_never_supports_exact_or_near_full_claim(self):
        state=replay([e(1,"HP_OBSERVATION",source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},
              branch="ACCEPTED",entries=[{"player":"石渡","reading_kind":"VERTICAL_BAR",
              "identity_evidence":"SELECTED_PLAYER_PANEL","geometry_px":
              {"center_x":1300,"track_top":543,"track_bottom":594,"fill_top":557,"edge_uncertainty":1}}])])
        rules={"rules":[{"rule_id":"DC-HP-001","status":"ACTIVE"}]}
        full=validate_recommendation({"action_type":"OTHER","based_on_event_seq":1,
            "rule_ids":["DC-HP-001"],"hp_claims":{"石渡":"FULL"}},state,rules)
        self.assertIn("HP_FULL_NOT_PROVEN:石渡",full)
        near=validate_recommendation({"action_type":"OTHER","based_on_event_seq":1,
            "rule_ids":["DC-HP-001"],"hp_claims":{"石渡":"NEAR_FULL"}},state,rules)
        self.assertIn("HP_NEAR_FULL_CONTRADICTED:石渡",near)
        req=validate_recommendation({"action_type":"OTHER","based_on_event_seq":1,
            "rule_ids":["DC-HP-001"],"hp_min_by_player":{"石渡":80}},state,rules)
        self.assertIn("HP_THRESHOLD_UNVERIFIED:石渡",req)
    def test_visual_hp_rejects_player_without_identity_evidence(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",
               source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},
               entries=[{"player":"石渡","reading_kind":"VERTICAL_BAR",
                  "geometry_px":{"center_x":1300,"track_top":543,"track_bottom":594,
                                 "fill_top":557,"edge_uncertainty":1}}])])
    def test_visual_hp_invalid_geometry_fails_closed(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",
               source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},
               entries=[{"player":"石渡","reading_kind":"VERTICAL_BAR",
               "identity_evidence":"SELECTED_PLAYER_PANEL",
               "geometry_px":{"center_x":1300,"track_top":600,"track_bottom":594,
                               "fill_top":557,"edge_uncertainty":1}}])])
    def test_approx_user_eighty_is_not_full_or_exact(self):
        state=replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",
             entries=[{"player":"石渡","reading_kind":"USER_APPROX_PERCENT","reported_percent":80}])])
        hp=state["hp_by_player"]["石渡"]
        self.assertEqual(hp["confidence"],"USER_APPROX")
        self.assertEqual(hp["full_state"],"NOT_FULL")
        errors=validate_recommendation({"action_type":"OTHER","based_on_event_seq":1,
             "rule_ids":["DC-HP-001"],"hp_claims":{"石渡":"NEAR_FULL"},
             "hp_min_by_player":{"石渡":80}},state,
             {"rules":[{"rule_id":"DC-HP-001","status":"ACTIVE"}]})
        self.assertIn("HP_NEAR_FULL_CONTRADICTED:石渡",errors)
        self.assertIn("HP_THRESHOLD_UNVERIFIED:石渡",errors)
    def test_exact_user_hp_threshold_can_be_applied(self):
        state=replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",
             entries=[{"player":"石渡","reading_kind":"USER_EXACT_PERCENT","reported_percent":85}])])
        rules={"rules":[{"rule_id":"DC-HP-001","status":"ACTIVE"}]}
        ok=validate_recommendation({"action_type":"OTHER","based_on_event_seq":1,
             "rule_ids":["DC-HP-001"],"hp_min_by_player":{"石渡":80}},state,rules)
        self.assertEqual(ok,[])
        blocked=validate_recommendation({"action_type":"OTHER","based_on_event_seq":1,
             "rule_ids":["DC-HP-001"],"hp_min_by_player":{"石渡":90}},state,rules)
        self.assertIn("HP_BELOW_THRESHOLD:石渡",blocked)
    def test_hp_snapshot_expires_after_match(self):
        state=replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",
               entries=[{"player":"石渡","reading_kind":"USER_APPROX_PERCENT","reported_percent":80}]),
              e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",attempt=1,our_runs=4,their_runs=1,branch="ACCEPTED")])
        self.assertFalse(state["hp_by_player"]["石渡"]["fresh"])
        errors=validate_recommendation({"action_type":"OTHER","based_on_event_seq":2,
            "rule_ids":["DC-HP-001"],"hp_claims":{"石渡":"NOT_FULL"}},state,
            {"rules":[{"rule_id":"DC-HP-001","status":"ACTIVE"}]})
        self.assertIn("HP_NOT_VERIFIED:石渡",errors)
    def test_hp_from_older_screen_is_ignored_after_mutation(self):
        visual={"player":"石渡","reading_kind":"VERTICAL_BAR","identity_evidence":"SELECTED_PLAYER_PANEL",
              "geometry_px":{"center_x":1300,"track_top":543,"track_bottom":594,"fill_top":557,"edge_uncertainty":1}}
        state=replay([screen(1),
              e(2,"MATCH_ATTEMPT",match_id="M",opponent="花さか",attempt=1,our_runs=4,their_runs=1,branch="ACCEPTED"),
              e(3,"HP_OBSERVATION",branch="ACCEPTED",source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},
                after_event_id="E1",entries=[visual])])
        self.assertEqual(state["hp_by_player"],{})
        self.assertIn("E3",state["observations_ignored_as_stale"])
    def test_hp_after_current_screen_can_be_fresh(self):
        state=replay([screen(1),e(2,"HP_OBSERVATION",branch="ACCEPTED",after_event_id="E1",
              entries=[{"player":"石渡","reading_kind":"USER_APPROX_PERCENT","reported_percent":80}])])
        self.assertTrue(state["hp_by_player"]["石渡"]["fresh"])
    def test_hp_rollback_discards_unaccepted_fill(self):
        state=replay([e(1,"SAVE_CHECKPOINT"),
             e(2,"HP_OBSERVATION",branch="ACCEPTED",entries=[
               {"player":"石渡","reading_kind":"USER_EXACT_PERCENT","reported_percent":100}]),
             e(3,"ROLLBACK",to_checkpoint_id="E1")])
        self.assertEqual(state["hp_by_player"],{})
        self.assertIn("E2",state["reverted_event_ids"])
    def test_hp_from_old_month_is_not_current(self):
        state=replay([e(1,"MATCHES_COMPLETED",7),
             e(2,"HP_OBSERVATION",6,branch="ACCEPTED",entries=[
               {"player":"石渡","reading_kind":"USER_APPROX_PERCENT","reported_percent":80}])])
        self.assertEqual(state["hp_by_player"],{})
        self.assertIn("E2",state["observations_ignored_as_stale"])
    def test_hp_gauge_multiple_players_separately_bound(self):
        state=replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},entries=[
            {"player":"石渡","reading_kind":"VERTICAL_BAR","identity_evidence":"SELECTED_PLAYER_PANEL",
             "geometry_px":{"center_x":1300,"track_top":543,"track_bottom":594,"fill_top":557,"edge_uncertainty":1}},
            {"player":"入江","reading_kind":"VERTICAL_BAR","identity_evidence":"VERIFIED_FORMATION_SLOT",
             "geometry_px":{"center_x":850,"track_top":543,"track_bottom":594,"fill_top":549,"edge_uncertainty":1}}
        ])])
        self.assertEqual(len(state["hp_by_player"]),2)
        self.assertNotEqual(state["hp_by_player"]["石渡"]["graphical_fill_estimate_pct"],
                            state["hp_by_player"]["入江"]["graphical_fill_estimate_pct"])
    def test_bar_does_not_allow_numeric_hp_from_screenshot_source(self):
        with self.assertRaises(ObservationError):
            replay([e(1,"HP_OBSERVATION",branch="ACCEPTED",
               source={"kind":"RAW_SCREEN","locator":"IMG_8932.png"},
               entries=[{"player":"石渡","reading_kind":"USER_EXACT_PERCENT","reported_percent":80}])])
    def test_late_historical_completion_preserves_new_snapshot(self):
        s=replay([screen(1,8),e(2,"MATCHES_COMPLETED",7)])
        self.assertTrue(s["resources"]["fresh"])

if __name__=="__main__":unittest.main()
