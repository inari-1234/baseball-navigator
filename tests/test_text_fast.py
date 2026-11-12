"""TEXT FAST routing is tested without writing real live events or GitHub files."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from postload_fixture import POSTLOAD
from unittest.mock import patch

from text_fast import TextFastEngine, classify_text


def state(*, seq=10, trusted=True, inventory_fresh=True):
    return {
        "last_event_seq":seq,
        "timeline_status":"TRUSTED" if trusted else "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN",
        "completed_match_periods":[],
        "resources":{"fresh":True,"values":{"study":4,"sports":28,
                    "play":25,"nature":18,"cheer":100}},
        "inventory":{"fresh":inventory_fresh,"items":{"チョコレート":1}},
        "hp_by_player":{}, "matches":{},
    }


def contract():
    return {"rules":[{"rule_id":key,"status":"ACTIVE"}
            for key in ("DC-PROC-001","DC-PROC-002","DC-INGEST-001",
                        "DC-STATE-001","DC-ACTION-001","DC-ITEM-001",
                        "DC-TRAIN-001")]}


def item_draft(seq=10):
    return {"action_type":"ITEM","based_on_event_seq":seq,
            "rule_ids":["DC-ITEM-001"],"spend":{},
            "items":[{"item":"チョコレート","quantity":1}]}


class TextFastClassificationRegression(unittest.TestCase):
    def test_readonly_status_and_inventory_questions(self):
        for text in ["今の試合予定を教えて", "現在の所持アイテムは何個？",
                     "アイテムの判断ロジックは実装済み？"]:
            with self.subTest(text=text):
                plan=classify_text(text)
                self.assertEqual(plan.intent,"READ_ONLY")
                self.assertEqual(plan.mode,"QUICK")

    def test_decision_queries_use_fast_action_gate(self):
        for text in ["アイテムを使うべき？",
                     "スポーツ28なら特訓と試合どちらを優先？",
                     "次は何をすべき？"]:
            with self.subTest(text=text):
                plan=classify_text(text)
                self.assertEqual(plan.intent,"ACTION_EVALUATION")
                self.assertEqual(plan.mode,"QUICK")

    def test_training_questions_are_not_ingested_as_completed_sessions(self):
        for text in ["たきは3回特訓した？4回目スキル狙っていい？",
                     "たきはすでに3回特訓してたっけ？",
                     "何回特訓した？", "特訓した？"]:
            with self.subTest(text=text):
                result = classify_text(text)
                self.assertFalse(result.requires_ingest)
                self.assertNotEqual(result.intent, "STATE_REPORT")
        self.assertEqual(
            classify_text("たきは3回特訓した？4回目スキル狙っていい？").intent,
            "ACTION_EVALUATION")

    def test_cheer_on_off_questions_require_action_gate(self):
        for text in ["応援はすべてONでいい？", "全て応援使う？",
                     "応援OFFの方がいい？"]:
            with self.subTest(text=text):
                result = classify_text(text)
                self.assertEqual(result.intent, "ACTION_EVALUATION")
                self.assertFalse(result.requires_ingest)

    def test_statement_before_question_still_requires_ingest(self):
        result = classify_text("特訓した。次は何をすべき？")
        self.assertEqual(result.intent, "STATE_REPORT")
        self.assertTrue(result.requires_ingest)

    def test_development_is_explicit_full_not_silent_automatic(self):
        for text in ["コードとテストしてみよう", "ロジックを組んで",
                     "GitHubへ反映して", "設計して"]:
            with self.subTest(text=text):
                r=classify_text(text)
                self.assertEqual(r.intent,"DEVELOPMENT")
                self.assertTrue(r.requires_full)

    def test_plain_state_report_requires_ingestion(self):
        for text in ["7月は試合予定だよ", "スポーツが10減った",
                     "特訓した", "アイテムを使った"]:
            with self.subTest(text=text):
                r=classify_text(text)
                self.assertEqual(r.intent,"STATE_REPORT")
                self.assertTrue(r.requires_ingest)

    def test_match_result_rollback_and_correction_force_full_checkpoint(self):
        for text in ["6対1で勝った", "ロールバックした",
                     "試合が終了した", "訂正します"]:
            with self.subTest(text=text):
                r=classify_text(text)
                self.assertTrue(r.requires_ingest)
                self.assertTrue(r.requires_full)

    def test_questions_and_hypotheticals_do_not_mutate(self):
        for text in ["ロールバックした場合はどうなる？",
                     "7月は試合予定なの？", "勝ったらどうなる？"]:
            with self.subTest(text=text):
                self.assertFalse(classify_text(text).requires_ingest)

    def test_conditional_advice_is_not_a_completed_event(self):
        for text in ["特訓したら次は何をすべき？",
                     "ロールバックしたらどうなる？",
                     "もし試合に勝ったら何をする？"]:
            with self.subTest(text=text):
                r=classify_text(text)
                self.assertFalse(r.requires_ingest)

    def test_known_item_use_report_must_be_ingested_first(self):
        for item in ["チョコレート", "鉄アレイ", "コーヒー", "声だしメガホン"]:
            with self.subTest(item=item):
                result=classify_text(item+"を使った")
                self.assertEqual(result.intent,"STATE_REPORT")
                self.assertTrue(result.requires_ingest)

    def test_ambiguous_followup_is_not_an_unapproved_action(self):
        for text in ["進めて","続けて","お願い",""]:
            with self.subTest(text=text):
                self.assertEqual(classify_text(text).intent,"NEEDS_CONTEXT")


class TextFastSafetyRegression(unittest.TestCase):
    def setUp(self):
        self.engine=TextFastEngine()
        self.c=contract()

    def route(self,text,*,s=None,rec=None,boot=True,expected=None):
        if s is None:
            s=state()
        return self.engine.plan(text,state=s,contract=self.c,
                                boot_verified=boot,expected_event_seq=expected,
                                recommendation=rec)

    def test_boot_not_verified_blocks_even_readonly_source_claim(self):
        result=self.route("今の状態を教えて",boot=False)
        self.assertEqual(result["status"],"BOOT_REQUIRED")
        self.assertFalse(result["action_authorized"])

    def test_requires_real_state_and_active_rules(self):
        r=self.engine.plan("今の状態",state=None,contract=self.c,
                           boot_verified=True)
        self.assertEqual(r["status"],"BOOT_REQUIRED")
        incomplete={"rules":[{"rule_id":"DC-PROC-001","status":"ACTIVE"}]}
        r=self.engine.plan("今の状態",state=state(),contract=incomplete,
                           boot_verified=True)
        self.assertEqual(r["status"],"CONTRACT_REQUIRED")

    def test_source_certified_exact_count_is_not_conflated_with_partial_log(self):
        s=state(trusted=True)
        s["training_counts_by_player_drill"]={"たき|素振り":2,
                                               "今井|素振り":3}
        s["training_counts_exact_by_player_drill"]={"たき|素振り":3}
        s["training_count_certifications"]={"たき|素振り":{
            "event_id":"TEST-EXACT-TAKI","source_kind":"USER_REPORT",
            "scope":"EXACT_CURRENT_ACCEPTED_SAVE"}}
        r=self.route("たきの特訓回数は？",s=s)
        self.assertEqual(r["status"],"READ_ONLY_READY")
        obs=r["observation"]
        self.assertEqual(obs["exact_total_status"],"PARTIALLY_VERIFIED")
        self.assertEqual(obs["exact_current_counts_by_player_drill"],
                         {"たき|素振り":3})
        self.assertEqual(obs["exact_count_source_event_ids"],
                         {"たき|素振り":"TEST-EXACT-TAKI"})
        self.assertEqual(obs["event_ledger_counts_lower_bound"]["今井|素振り"],3)
        self.assertFalse(obs["missing_player_drill_count_means_zero"])
        self.assertFalse(obs["fourth_checkpoint_verified"])

    def test_training_count_query_does_not_claim_exact_total(self):
        s = state(trusted=True)
        s["training_counts_by_player_drill"] = {"たき|素振り": 3}
        out = self.route("たきはすでに3回特訓してたっけ？", s=s)
        self.assertEqual(out["status"], "READ_ONLY_READY")
        obs = out["observation"]
        self.assertEqual(obs["topic"], "TRAINING_COUNTS")
        self.assertEqual(obs["exact_total_status"], "UNKNOWN")
        self.assertEqual(obs["event_ledger_counts_lower_bound"], {"たき|素振り": 3})
        self.assertFalse(obs["ledger_complete_from_run_start"])
        self.assertFalse(obs["fourth_checkpoint_verified"])
        s["timeline_status"] = "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN"
        blocked = self.route("たきはすでに3回特訓してたっけ？", s=s)
        self.assertEqual(blocked["observation"]["count_scope"],
                         "UNVERIFIED_AFTER_ROLLBACK")
        self.assertIsNone(blocked["observation"]["event_ledger_counts_lower_bound"])

    def test_cheer_question_is_action_blocked_on_current_rollback(self):
        s = state(trusted=False)
        out = self.route("応援はすべてONでいい？", s=s)
        self.assertEqual(out["status"], "BLOCKED_UNVERIFIED_TIMELINE")
        self.assertFalse(out["action_authorized"])

    def test_no_implicit_event_write_and_readonly_skips_action_validation(self):
        s=state()
        copy_before=copy.deepcopy(s)
        with patch("text_fast.validate_recommendation",
                   side_effect=AssertionError("action validator not needed")):
            result=self.route("今の試合予定を教えて",s=s)
        self.assertEqual(result["status"],"READ_ONLY_READY")
        self.assertEqual(s,copy_before)
        self.assertFalse(result["side_effects"])
        self.assertFalse(result["action_authorized"])

    def test_quick_query_never_replays_the_full_event_history(self):
        with patch("live_state_engine.replay",
                   side_effect=AssertionError("full replay on QUICK")):
            result=self.route("今の試合予定を教えて")
        self.assertEqual(result["status"],"READ_ONLY_READY")
        self.assertFalse(result["requires_full"])

    def test_cached_route_cannot_bypass_newly_inactive_contract(self):
        s=state()
        self.route("今の試合予定を教えて",s=s)
        other=contract()
        other["rules"]=[r for r in other["rules"]
                         if r["rule_id"]!="DC-PROC-002"]
        result=self.engine.plan("今の試合予定を教えて",state=s,
                                contract=other,boot_verified=True)
        self.assertEqual(result["status"],"CONTRACT_REQUIRED")
        self.assertGreater(self.engine.route_hits,0)

    def test_live_report_does_not_automatically_apply_delta(self):
        s=state()
        old=copy.deepcopy(s)
        p=self.route("スポーツが10減った",s=s)
        self.assertEqual(p["status"],"INGEST_BEFORE_ADVICE")
        self.assertEqual(s,old)
        self.assertIn("DC-INGEST-001",p["rule_ids"])

    def test_report_and_advice_combination_first_ingests(self):
        p=self.route("特訓した。次は何をすべき？",rec=item_draft())
        self.assertEqual(p["status"],"INGEST_BEFORE_ADVICE")
        self.assertFalse(p["action_authorized"])

    def test_rollback_savepoint_unknown_blocks_action_draft(self):
        s=state(trusted=False)
        p=self.route("アイテムを使うべき？",s=s,rec=item_draft())
        self.assertEqual(p["status"],"BLOCKED_UNVERIFIED_TIMELINE")
        self.assertFalse(p["action_authorized"])
        self.assertEqual(self.engine.action_validator_calls,0)

    def test_current_repo_live_rollback_has_safe_action_gate(self):
        s=json.loads((POSTLOAD / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        c=json.loads(Path("DECISION_CONTRACT.json").read_text(encoding="utf-8"))
        p=self.engine.plan("アイテムを使うべき？",
                           state=s,contract=c,boot_verified=True,
                           recommendation=item_draft(seq=s["last_event_seq"]))
        self.assertEqual(p["status"],"BLOCKED_UNVERIFIED_TIMELINE")
        self.assertIn("ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN",
                      p["errors"][0])
        self.assertFalse(s["inventory"]["fresh"])

    def test_stale_revision_never_reuses_old_answer(self):
        s=state(seq=11)
        result=self.route("今の試合予定を教えて",s=s,expected=10)
        self.assertEqual(result["status"],"STALE_STATE_REVISION")

    def test_safe_action_still_requires_manual_acceptance(self):
        p=self.route("チョコレートを使うべき？",rec=item_draft())
        self.assertEqual(p["status"],"ACTION_DRAFT_REVIEW",p)
        self.assertFalse(p["action_authorized"])
        self.assertTrue(p["requires_manual_acceptance"])
        self.assertEqual(self.engine.action_validator_calls,1)

    def test_shortage_failed_rule_and_revision_detected_every_time(self):
        s=state()
        p=self.route("アイテムを使うべき？",s=s,rec=item_draft())
        self.assertEqual(p["status"],"ACTION_DRAFT_REVIEW")
        s["inventory"]["items"]["チョコレート"]=0
        p2=self.route("アイテムを使うべき？",s=s,rec=item_draft())
        self.assertEqual(p2["status"],"ACTION_BLOCKED")
        self.assertIn("INSUFFICIENT_ITEM_INVENTORY",p2["errors"])
        bad=item_draft(seq=9)
        p3=self.route("アイテムを使うべき？",s=s,rec=bad)
        self.assertIn("STALE_REVISION",p3["errors"])
        self.assertEqual(self.engine.action_validator_calls,3)

    def test_unverified_inventory_blocks_and_not_cached(self):
        s=state(inventory_fresh=False)
        p=self.route("アイテムを使うべき？",s=s,rec=item_draft())
        self.assertEqual(p["status"],"ACTION_BLOCKED")
        self.assertIn("ITEM_INVENTORY_NOT_VERIFIED",p["errors"])

    def test_route_cache_only_reuses_classification(self):
        text="今の試合予定を教えて"
        self.route(text)
        self.route(text,s=state(seq=11))
        self.assertEqual(self.engine.route_misses,1)
        self.assertEqual(self.engine.route_hits,1)
        self.assertEqual(self.engine.action_validator_calls,0)

    def test_real_current_match_schedule_is_read_only_and_not_completed(self):
        canonical=json.loads((POSTLOAD / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        p=self.route("今の試合予定を教えて",s=canonical)
        self.assertEqual(p["status"],"READ_ONLY_READY",p)
        obs=p["observation"]
        self.assertEqual(obs["topic"],"MATCHES")
        self.assertEqual(len(obs["scheduled_matches"]),3)
        self.assertEqual(
            {m["opponent"] for m in obs["scheduled_matches"]},
            {"花さか高校","まんるい高校","生南高校"})
        self.assertFalse(obs["prior_match_results_active_branch_verified"])
        self.assertTrue(obs["historical_results_are_not_current_guide"])

    def test_real_current_items_are_visible_slots_not_full_inventory(self):
        canonical=json.loads((POSTLOAD / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        p=self.route("現在のアイテム所持数は？",s=canonical)
        obs=p["observation"]
        self.assertEqual(obs["topic"],"ITEMS")
        self.assertFalse(obs["full_inventory_verified"])
        self.assertIsNone(obs["verified_inventory"])
        self.assertEqual(len(obs["visible_item_rows"]),4)
        self.assertEqual(obs["visible_item_rows"][0]["separately_verified_stock"],1)
        self.assertTrue(all(r["separately_verified_stock"] is None
                            for r in obs["visible_item_rows"][1:]))
        self.assertFalse(obs["counter_denominator_is_stock_verified"])
        self.assertFalse(obs["item_use_confirmed"])

    def test_resources_project_only_truly_present_canonical_fields(self):
        canonical=json.loads((POSTLOAD / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        p=self.route("スポーツと研究ポイントの現在値は？",s=canonical)
        obs=p["observation"]
        self.assertEqual(obs["topic"],"RESOURCES")
        self.assertTrue(obs["resource_fresh"])
        self.assertEqual(obs["resource_values"]["sports"],28)
        self.assertEqual(obs["resource_values"]["study"],4)
        self.assertEqual(obs["source_event_id"],canonical["resources"]["last_observed"])
        self.assertNotIn("money_yen",obs["resource_values"])

    def test_returned_readonly_view_cannot_mutate_canonical_input(self):
        s=state()
        s["visible_item_slots"]={
            "fresh":True, "source_event_id":"SRC","rows":[
                {"item":"チョコレート","assigned":0,
                 "display_denominator":1,"separately_verified_stock":1}]}
        original=copy.deepcopy(s)
        p=self.route("アイテムの所持数は？",s=s)
        p["observation"]["visible_item_rows"][0]["item"]="改変"
        self.assertEqual(s,original)

    def test_inactive_item_rule_fails_existing_validator(self):
        c=contract()
        c["rules"]=[r for r in c["rules"] if r["rule_id"]!="DC-ITEM-001"]
        p=self.engine.plan("アイテムを使うべき？",state=state(),
                           contract=c,boot_verified=True,
                           recommendation=item_draft())
        self.assertEqual(p["status"],"ACTION_BLOCKED")
        self.assertIn("INVALID_RULE_ID",p["errors"])

    def test_cli_uses_real_canonical_snapshot_and_writes_nothing(self):
        import hashlib
        import subprocess
        import sys
        paths=[Path("CURRENT_LIVE_STATE.json"),Path("DECISION_CONTRACT.json")]
        before=[hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        proc=subprocess.run(
            [sys.executable,"text_fast.py","アイテムを使うべき？",
             "--boot-verified","--expected-event-seq","10"],
            capture_output=True,text=True,check=True)
        result=json.loads(proc.stdout)
        self.assertEqual(result["status"],"BLOCKED_UNVERIFIED_TIMELINE",result)
        self.assertFalse(result["side_effects"])
        self.assertEqual(
            [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths],
            before)
        no_boot=subprocess.run(
            [sys.executable,"text_fast.py","今の試合予定は？"],
            capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(no_boot.stdout)["status"],"BOOT_REQUIRED")

    def test_full_development_route_does_not_trigger_match_action(self):
        with patch("text_fast.validate_recommendation",
                   side_effect=AssertionError("not an action")):
            p=self.route("コードとテストしてみよう",
                         rec=item_draft())
        self.assertEqual(p["status"],"FULL_REQUIRED")
        self.assertFalse(p["action_authorized"])


if __name__=="__main__":
    unittest.main()
