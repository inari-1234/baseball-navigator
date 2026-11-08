"""P7-D guarded-reply regression with synthetic past failure cases."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import unittest
from chat_bridge import bridge_response
from check_reply import (check_reply, render_guarded_reply, ReplyGateError,
                         make_local_verified_draft_packet, canonical_state_sha256)
from navigator_step import navigator_step
from live_state_engine import replay
from text_fast import _read_only_projection

ROOT=Path(__file__).resolve().parents[1]
SHA="a"*40

def request(intent):
    return {"schema_version":"1.0","request_id":"reply-guard-test-01",
            "intent":intent,"expected_main_sha":SHA,"expected_event_seq":10}

class GuardedReplyRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=json.loads((ROOT/"CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        cls.skill=bridge_response(request("SKILL"),root=ROOT,actual_main_sha=SHA)
        cls.counts=bridge_response(request("TRAINING_COUNTS"),root=ROOT,actual_main_sha=SHA)

    def verdict(self, text, bridge=None, sha=SHA, seq=10):
        return check_reply(text,bridge=self.skill if bridge is None else bridge,
                           state=self.state,expected_main_sha=sha,
                           expected_event_seq=seq)

    def test_canonical_skill_reply_is_source_pinned(self):
        text=render_guarded_reply(self.skill,self.state)
        self.assertEqual(self.verdict(text)["status"],"PASS")
        self.assertEqual(self.skill["safe_reply"],text)
        self.assertEqual(self.skill["safe_reply_check"]["status"],"PASS")
        self.assertNotIn("たき",text)
        self.assertNotIn("応援ON",text)

    def test_canonical_unknown_count_reply_passes(self):
        text=render_guarded_reply(self.counts,self.state)
        self.assertEqual(self.verdict(text,self.counts)["status"],"PASS")
        self.assertIn("未確定",text)

    def test_fabricated_counts_and_actionable_drills_rejected(self):
        drafts=[
            "たきはすでに3回特訓していました。次は4回目です。",
            "たきは3回済みなので4回目を狙いましょう。",
            "岡治・今井・たきで素振り。応援ON、スポーツ6、応援20です。",
            "1〜3回目は応援OFF、4回目だけ応援ONにしてください。",
            "4回連続でやっていいです。応援は全部ONにします。",
            "たきの特訓回数は0回です。",
            "4回目はスキル確定なのでリロードしましょう。",
            "条件付きでたき・岡治・今井の素振りを勧めます。"]
        for text in drafts:
            with self.subTest(text=text):
                out=self.verdict(text)
                self.assertEqual(out["status"],"REJECTED")
                self.assertIn("REPLY_NOT_CANONICAL",out["error_codes"])

    def test_even_one_appended_clause_is_uncertified(self):
        text=self.skill["safe_reply"]
        for draft in (text+" 応援20を使っても構いません。",
                      text.replace("未確定","3回済み",1),
                      text+"\n岡治・今井・たきで素振り。",
                      text+" ",
                      chr(96)*3+text+chr(96)*3):
            with self.subTest(draft=draft):
                self.assertEqual(self.verdict(draft)["status"],"REJECTED")

    def test_stale_source_revisions_rejected(self):
        text=self.skill["safe_reply"]
        self.assertIn("STALE_SOURCE_COMMIT",
                      self.verdict(text,sha="b"*40)["error_codes"])
        self.assertIn("STALE_EVENT_REVISION",
                      self.verdict(text,seq=9)["error_codes"])
        x=copy.deepcopy(self.skill);x["timeline_status"]="TRUSTED"
        self.assertEqual(self.verdict(text,x)["status"],"REJECTED")

    def test_state_content_mismatch_rejected_even_with_same_revision(self):
        changed=copy.deepcopy(self.state)
        changed["training_counts_by_player_drill"]={"たき|素振り":3}
        observed=check_reply(self.skill["safe_reply"],bridge=self.skill,
                             state=changed,expected_main_sha=SHA,
                             expected_event_seq=10)
        self.assertEqual(observed["status"],"REJECTED")
        self.assertIn("STATE_CONTENT_MISMATCH",observed["error_codes"])

    def test_blocked_candidate_data_cannot_be_certified(self):
        x=copy.deepcopy(self.skill)
        x["candidate"]={"cost":{"sports":6,"cheer":20},
                        "participants":["岡治","今井","たき"]}
        with self.assertRaisesRegex(ReplyGateError,"BLOCKED_CANDIDATE_LEAK"):
            render_guarded_reply(x,self.state)
        x=copy.deepcopy(self.skill);x["selected_candidate"]="TRAIN_CONTACT_ON"
        with self.assertRaisesRegex(ReplyGateError,"BLOCKED_CANDIDATE_LEAK"):
            render_guarded_reply(x,self.state)

    def test_count_and_certainty_tampering_rejected(self):
        x=copy.deepcopy(self.counts);x["observation"]["exact_total_status"]="PARTIALLY_VERIFIED"
        self.assertEqual(self.verdict(self.counts["safe_reply"],x)["status"],"REJECTED")
        x=copy.deepcopy(self.counts);x["observation"]["fourth_checkpoint_verified"]=True
        self.assertEqual(self.verdict(self.counts["safe_reply"],x)["status"],"REJECTED")

    def test_unsupported_intent_and_status_never_implicitly_certified(self):
        for intent in ("MATCH","RECOVERY","GENERAL","STATUS"):
            r=bridge_response(request(intent),root=ROOT,actual_main_sha=SHA)
            self.assertNotIn("safe_reply",r)
        x=copy.deepcopy(self.skill);x["status"]="VALIDATED_DRAFT_REVIEW"
        with self.assertRaises(ReplyGateError):
            render_guarded_reply(x,self.state)

    def test_trusted_readonly_count_reports_exact_and_lower_bounds(self):
        source={"kind":"USER_REPORT","locator":"synthetic-test-only"}
        def event(n,kind,**fields):
            return {"seq":n,"event_id":f"E{n}","kind":kind,"source":source,
                    "period":{"year":1,"month":6},**fields}
        state=replay([
            event(1,"SCREEN",branch="ACCEPTED",
                  resources={"study":4,"sports":28,"play":25,"nature":18,"cheer":100}),
            event(2,"TRAINING_COUNT_BASELINE",branch="ACCEPTED",
                  confirmed_current_save=True,
                  count_scope="EXACT_CURRENT_ACCEPTED_SAVE",
                  after_event_id="E1",counts={"たき|素振り":3}),
            event(3,"TRAINING",branch="ACCEPTED",cheer="OFF",
                  drill="ダンベル",drill_level=1,
                  participants=["今井","岡治","たき"]),
        ])
        self.assertEqual(state["timeline_status"],"TRUSTED")
        p=copy.deepcopy(self.counts)
        p["state_event_seq"]=3
        p["timeline_status"]="TRUSTED"
        p["state_structured_sha256"]=canonical_state_sha256(state)
        p["observation"]=_read_only_projection(
            "現在の本線の特訓回数の記録を確認して",state)
        content=render_guarded_reply(p,state)
        self.assertIn("たき・素振り：3回（現セーブで確定、根拠 E2）",content)
        self.assertIn("今井・ダンベル：記録上少なくとも1回",content)
        self.assertNotIn("必ずスキル",content)
        out=check_reply(content,bridge=p,state=state,
                        expected_main_sha=SHA,expected_event_seq=3)
        self.assertEqual(out["status"],"PASS")
        bad=copy.deepcopy(p)
        bad["observation"]["exact_current_counts_by_player_drill"]["たき|素振り"]=4
        self.assertIn("COUNT_OBSERVATION_MISMATCH",
                      check_reply(content,bridge=bad,state=state,
                          expected_main_sha=SHA,expected_event_seq=3)["error_codes"])

    def test_trusted_skill_without_current_context_uses_stop_template(self):
        state=copy.deepcopy(self.state)
        state["timeline_status"]="TRUSTED"
        p=copy.deepcopy(self.skill)
        p["timeline_status"]="TRUSTED"
        p["state_structured_sha256"]=canonical_state_sha256(state)
        p["status"]="NEEDS_GROUNDED_FAILURE_ASSESSMENT"
        p["blocking_reasons"]=[]
        text=render_guarded_reply(p,state)
        self.assertIn("特訓条件はまだ検証済みではありません",text)
        self.assertNotIn("応援ON",text)
        self.assertEqual(check_reply(text,bridge=p,state=state,
            expected_main_sha=SHA,expected_event_seq=10)["status"],"PASS")
        p["candidate"]={"participants":["たき","今井","岡治"],
                        "cost":{"sports":6,"cheer":20}}
        with self.assertRaisesRegex(ReplyGateError,"BLOCKED_CANDIDATE_LEAK"):
            render_guarded_reply(p,state)

    def test_local_current_verified_draft_has_costs_and_manual_acceptance(self):
        state=copy.deepcopy(self.state)
        state["timeline_status"]="TRUSTED"
        contract=json.loads((ROOT/"DECISION_CONTRACT.json").read_text(encoding="utf-8"))
        source=state["resources"]["last_observed"]
        def attested(**fields):
            return {"verified_for_current_state":True,
                    "source_event_seq":state["last_event_seq"],
                    "period":state["period_floor"],
                    "branch":"ACCEPTED",
                    "evidence_refs":[source],**fields}
        context={
            "failure_assessment":attested(mode="CONTACT"),
            "training_readiness":attested(
                available_drills=["素振り","ダンベル"],
                ready_players=["岡治","今井","たき","芦田","入江"]),
        }
        decision=navigator_step(
            "スキル獲得に向けて何をすべき？",state=state,
            contract=contract,boot_verified=True,
            expected_event_seq=10,context=context,root=ROOT)
        self.assertEqual(decision["status"],"VALIDATED_DRAFT_REVIEW")
        packet=make_local_verified_draft_packet(
            decision,state,source_commit_sha=SHA,contract=contract,root=ROOT)
        self.assertEqual(packet["safe_reply_check"]["status"],"PASS")
        self.assertIn("岡治・今井・たき",packet["safe_reply"])
        self.assertIn("素振り／応援ON／消費予定：スポーツ6、応援20",
                      packet["safe_reply"])
        self.assertIn("4回目の根拠は未確認",packet["safe_reply"])
        self.assertIn("採用基準：",packet["safe_reply"])
        self.assertIn("再試行基準：",packet["safe_reply"])
        self.assertIn("手動承認前",packet["safe_reply"])
        altered=copy.deepcopy(packet)
        altered["candidate"]["cost"]["sports"]=1
        altered["verified_action_draft"]["spend"]["sports"]=1
        self.assertIn("CATALOG_TRAINING_COST_MISMATCH",
                      check_reply(packet["safe_reply"],bridge=altered,state=state,
                          expected_main_sha=SHA,expected_event_seq=10,
                          contract=contract,root=ROOT)["error_codes"])
        altered=copy.deepcopy(packet)
        altered["candidate"]["readiness_evidence_refs"]=[]
        self.assertIn("CURRENT_VERIFIED_CANDIDATE_REQUIRED",
                      check_reply(packet["safe_reply"],bridge=altered,state=state,
                          expected_main_sha=SHA,expected_event_seq=10,
                          contract=contract,root=ROOT)["error_codes"])

    def test_local_fourth_session_label_requires_exact_source_certification(self):
        state=copy.deepcopy(self.state)
        state["timeline_status"]="TRUSTED"
        state["training_counts_by_player_drill"]={"今井|素振り":3}
        state["training_counts_exact_by_player_drill"]={"今井|素振り":3}
        state["training_count_certifications"]={"今井|素振り":{
            "event_id":"TEST-EXACT-IMAI","source_kind":"USER_REPORT",
            "scope":"EXACT_CURRENT_ACCEPTED_SAVE"}}
        contract=json.loads((ROOT/"DECISION_CONTRACT.json").read_text(encoding="utf-8"))
        source=state["resources"]["last_observed"]
        context={"failure_assessment":{
                     "verified_for_current_state":True,"source_event_seq":10,
                     "period":state["period_floor"],"branch":"ACCEPTED",
                     "evidence_refs":[source],"mode":"CONTACT"},
                 "training_readiness":{
                     "verified_for_current_state":True,"source_event_seq":10,
                     "period":state["period_floor"],"branch":"ACCEPTED",
                     "evidence_refs":[source],"available_drills":["素振り"],
                     "ready_players":["岡治","今井","たき"]}}
        result=navigator_step("スキル獲得に向けて何をすべき？",
                              state=state,contract=contract,boot_verified=True,
                              expected_event_seq=10,context=context,root=ROOT)
        self.assertEqual(result["status"],"VALIDATED_DRAFT_REVIEW")
        packet=make_local_verified_draft_packet(result,state,
            source_commit_sha=SHA,contract=contract,root=ROOT)
        self.assertIn("今井の次回が記録上4回目の候補",packet["safe_reply"])
        self.assertIn("習得保証なし",packet["safe_reply"])

    def test_read_only_no_chat_runtime_enforcement_claim(self):
        import hashlib
        names=("CURRENT_LIVE_STATE.json","LIVE_EVENTS.jsonl","DECISION_LOG.jsonl")
        before=[hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names]
        self.verdict(self.skill["safe_reply"])
        after=[hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names]
        self.assertEqual(before,after)
        self.assertFalse(self.skill["safe_reply_check"]["chat_runtime_hook_guaranteed"])

if __name__=="__main__":
    unittest.main()
