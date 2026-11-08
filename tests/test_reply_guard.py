"""P7-D guarded-reply regression with synthetic past failure cases."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import unittest
from chat_bridge import bridge_response
from check_reply import check_reply, render_guarded_reply, ReplyGateError

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
