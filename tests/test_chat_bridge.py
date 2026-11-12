"""P4 ChatGPT/connected GitHub GitHub Actions bridge regression tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from postload_fixture import POSTLOAD, copy_postload_runtime
import subprocess
import sys
import tempfile
import unittest

from chat_bridge import (
    BOOT_FILES, ChatBridgeError, INTENTS, bridge_response,
    git_head, validate_request, verify_boot, finalize_reply_delivery,
)

ROOT = Path(__file__).resolve().parents[1]
FAKE_SHA = "a" * 40


def request(intent="SKILL", **overrides):
    value = {
        "schema_version": "1.0",
        "request_id": "p4-safe-test-001",
        "intent": intent,
        "expected_main_sha": FAKE_SHA,
        "expected_event_seq": 10,
    }
    value.update(overrides)
    return value


class ChatBridgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.postload = Path(temp.name)
        copy_postload_runtime(self.postload)

    def test_ordered_boot_present(self):
        verify_boot(ROOT)
        self.assertTrue(all((ROOT / p).exists() for p in BOOT_FILES))

    def test_skill_end_to_end_source_pinned_and_safe(self):
        r = bridge_response(request(), root=self.postload, actual_main_sha=FAKE_SHA)
        self.assertEqual(r["intent"], "SKILL")
        self.assertEqual(r["source_commit_sha"], FAKE_SHA)
        self.assertEqual(r["state_event_seq"], 10)
        self.assertEqual(r["status"], "BLOCKED_UNVERIFIED_TIMELINE")
        self.assertIn("SKILL-4TH-PATTERN", r["knowledge_refs"])
        self.assertEqual(r["primary_next_step"], "VERIFY_CURRENT_SAVE_ANCHOR")
        self.assertIsNone(r["provisional_target"])
        self.assertFalse(r["action_authorized"])
        self.assertFalse(r["side_effects"])
        self.assertIsNone(r["candidate"])
        self.assertTrue(r["blocked_candidate_suppressed"])
        self.assertNotIn("岡治", json.dumps(r, ensure_ascii=False))
        self.assertNotIn("たき", json.dumps(r, ensure_ascii=False))
        self.assertNotIn("TRAIN_CONTACT_ON", json.dumps(r, ensure_ascii=False))
        # Blocked internal costs/cheer must never be exported as answer data.
        serialized=json.dumps(r, ensure_ascii=False)
        self.assertNotIn('"cost"', serialized)
        self.assertNotIn('"cheer"', serialized)
        self.assertNotIn("スポーツ6", serialized)
        self.assertNotIn("応援20", serialized)
        self.assertEqual(r["safe_reply_check"]["status"], "PASS")
        self.assertIn("未確定", r["safe_reply"])
        self.assertFalse(r["safe_reply_check"]["chat_runtime_hook_guaranteed"])
        self.assertEqual(r["context_source"], "NO_USER_CONTEXT_PUBLIC_REQUEST")
        self.assertTrue(r["source_is_current_only_at_this_commit"])

    def test_boot_intent_returns_full_verified_resume_capsule(self):
        response=bridge_response(request(intent="BOOT"),root=self.postload,
                                 actual_main_sha=FAKE_SHA)
        self.assertEqual(response["status"],"BOOT_VERIFIED_ACTIONS_BLOCKED")
        self.assertEqual(response["state_event_seq"],10)
        self.assertFalse(response["action_authorized"])
        self.assertFalse(response["side_effects"])
        self.assertIn("SKILL-4TH-PATTERN",response["knowledge_refs"])
        self.assertIn("DC-STATE-001",response["rule_ids"])
        self.assertEqual(response["boot_report"]["project_id"],
                         "kairosoft-baseball-story-sapporo-sprint")
        self.assertEqual(response["boot_report"]["state"]["period"],"Y1-06")
        self.assertEqual(response["boot_report"]["state"]["current_skills"],
                         "UNVERIFIED_AFTER_ROLLBACK")
        self.assertTrue(response["boot_report"]["live_replay_verified"])
        self.assertEqual(len(response["boot_report"]["boot_files_read"]),7)
        self.assertFalse(response["boot_report"]["automatic_new_chat_invocation_guaranteed"])

    def test_boot_intent_stale_event_seq_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"STALE_EVENT_REVISION"):
            bridge_response(request(intent="BOOT",expected_event_seq=9),
                            root=self.postload,actual_main_sha=FAKE_SHA)

    def test_all_intents_are_readonly(self):
        for intent in INTENTS:
            with self.subTest(intent=intent):
                r = bridge_response(request(intent=intent), root=self.postload,
                                    actual_main_sha=FAKE_SHA)
                self.assertEqual(r["intent"], intent)
                self.assertFalse(r["action_authorized"])
                self.assertFalse(r["side_effects"])
                if r["status"] != "VALIDATED_DRAFT_REVIEW" and intent != "BOOT":
                    self.assertIsNone(r.get("candidate"))
                    self.assertIsNone(r.get("provisional_target"))
                self.assertTrue(r["rule_ids"])

    def test_future_trusted_candidate_without_private_context_is_suppressed(self):
        state=json.loads((POSTLOAD/"CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        state["timeline_status"]="TRUSTED"
        contract=json.loads((ROOT/"DECISION_CONTRACT.json").read_text(encoding="utf-8"))
        from check_reply import canonical_state_sha256
        packet=bridge_response(request(intent="SKILL"),root=self.postload,
                               actual_main_sha=FAKE_SHA)
        packet["timeline_status"]="TRUSTED"
        packet["state_structured_sha256"]=canonical_state_sha256(state)
        packet["status"]="VALIDATED_DRAFT_REVIEW"
        packet["candidate"]={
            "id":"TRAIN_CONTACT_ON", "participants":["岡治","今井","たき"],
            "drill":"素振り","cheer":"ON",
            "cost":{"sports":6,"cheer":20}}
        packet["selected_candidate"]="TRAIN_CONTACT_ON"
        packet["primary_next_step"]="TRAIN_CONTACT_ON"
        packet["provisional_target"]="TRAIN_CONTACT_ON"
        packet["requires_manual_acceptance"]=True
        packet.pop("safe_reply",None)
        packet.pop("safe_reply_check",None)
        result={"status":"VALIDATED_DRAFT_REVIEW"}
        final=finalize_reply_delivery(
            packet,result=result,state=state,contract=contract,
            root=self.postload,main_sha=FAKE_SHA)
        self.assertEqual(final["status"],"REPLY_NOT_CERTIFIED")
        self.assertEqual(final["navigator_status"],"VALIDATED_DRAFT_REVIEW")
        self.assertEqual(final["reply_delivery_status"],"STOP_UNCERTIFIED")
        self.assertIsNone(final["safe_reply"])
        self.assertEqual(final["safe_reply_check"]["status"],"NOT_CERTIFIED")
        self.assertIsNone(final["candidate"])
        self.assertIsNone(final["selected_candidate"])
        self.assertIsNone(final["provisional_target"])
        self.assertFalse(final["requires_manual_acceptance"])
        self.assertEqual(final["primary_next_step"],
                         "VERIFY_REPLY_SUPPORT_BEFORE_ACTION")
        self.assertNotIn('"cost"',json.dumps(final,ensure_ascii=False))
        self.assertNotIn('"cheer"',json.dumps(final,ensure_ascii=False))

    def test_uncertified_public_action_intents_never_export_a_draft(self):
        for intent in ("GENERAL","MATCH","RECOVERY"):
            with self.subTest(intent=intent):
                reply=bridge_response(request(intent=intent),root=self.postload,
                                      actual_main_sha=FAKE_SHA)
                self.assertEqual(reply["status"],"REPLY_NOT_CERTIFIED")
                self.assertEqual(reply["reply_delivery_status"],"STOP_UNCERTIFIED")
                self.assertIsNone(reply["candidate"])
                self.assertIsNone(reply["selected_candidate"])
                self.assertIsNone(reply["provisional_target"])

    def test_training_counts_intent_never_claims_exact_current_sessions(self):
        r = bridge_response(request(intent="TRAINING_COUNTS"),
                            root=self.postload, actual_main_sha=FAKE_SHA)
        self.assertEqual(r["status"], "READ_ONLY_READY")
        self.assertIsNone(r["candidate"])
        obs = r["observation"]
        self.assertEqual(obs["topic"], "TRAINING_COUNTS")
        self.assertEqual(obs["exact_total_status"], "UNKNOWN")
        self.assertIsNone(obs["event_ledger_counts_lower_bound"])
        self.assertFalse(obs["ledger_complete_from_run_start"])
        self.assertFalse(obs["missing_player_drill_count_means_zero"])
        self.assertEqual(r["safe_reply_check"]["status"], "PASS")
        self.assertIn("未確定", r["safe_reply"])

    def test_status_response_is_readonly_projection(self):
        r=bridge_response(request(intent="STATUS"),root=self.postload,actual_main_sha=FAKE_SHA)
        self.assertEqual(r["status"], "READ_ONLY_READY")
        self.assertEqual(r["observation"]["source_event_seq"],10)
        self.assertEqual(r["observation"]["timeline_status"],
                         "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN")

    def test_changing_main_sha_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"STALE_MAIN_SHA"):
            bridge_response(request(),root=self.postload,actual_main_sha="b"*40)

    def test_changed_event_seq_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"STALE_EVENT_REVISION"):
            bridge_response(request(expected_event_seq=9),root=self.postload,
                            actual_main_sha=FAKE_SHA)

    def test_additional_free_text_not_sent_to_public_repo(self):
        for forbidden in ("message","images","private_library_file_id","hp","context","authorization"):
            with self.subTest(extra=forbidden):
                sample=request()
                sample[forbidden]="user data"
                with self.assertRaisesRegex(ChatBridgeError,"REQUEST_ALLOWLIST_ONLY"):
                    validate_request(sample)

    def test_unrecognized_intent_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"REQUEST_INTENT_NOT_ALLOWED"):
            validate_request(request(intent="WRITE_EVENTS"))

    def test_malformed_request_id_rejected(self):
        for bad in ("../private", "あいうえお", " ", "x"*65, "3"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ChatBridgeError,"REQUEST_ID_INVALID"):
                    validate_request(request(request_id=bad))

    def test_bool_revision_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"REQUEST_EVENT_REVISION_INVALID"):
            validate_request(request(expected_event_seq=True))

    def test_invalid_source_sha_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"REQUEST_MAIN_SHA_INVALID"):
            validate_request(request(expected_main_sha="abc"))

    def test_unrecognized_schema_rejected(self):
        with self.assertRaisesRegex(ChatBridgeError,"REQUEST_SCHEMA_VERSION_UNSUPPORTED"):
            validate_request(request(schema_version="2.0"))

    def test_output_does_not_embed_private_file_ids_or_raw_images(self):
        text=json.dumps(bridge_response(request(),root=self.postload,actual_main_sha=FAKE_SHA),
                        ensure_ascii=False)
        self.assertNotIn("libfile_",text)
        self.assertNotIn("data:image/",text)
        self.assertNotIn("evidence_originals",text)
        self.assertNotIn("IMG_8921",text)

    def test_source_files_unchanged_by_bridge(self):
        files=("CURRENT_LIVE_STATE.json", "LIVE_EVENTS.jsonl",
               "DECISION_CONTRACT.json", "KNOWLEDGE_CLAIMS.json",
               "CURRENT_HANDOFF.md")
        before={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
        bridge_response(request(),root=self.postload,actual_main_sha=FAKE_SHA)
        after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
        self.assertEqual(before,after)

    def test_cli_from_actual_checkout_writes_one_json_line(self):
        head=git_head(ROOT)
        state = json.loads((ROOT / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        req = request(expected_main_sha=head, expected_event_seq=state["last_event_seq"])
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"req.json"
            file.write_text(json.dumps(req),encoding="utf-8")
            p=subprocess.run(
                [sys.executable,str(ROOT/"chat_bridge.py"),
                 "--request",str(file),"--source-root",str(ROOT)],
                capture_output=True,text=True,check=True)
        self.assertEqual(len(p.stdout.strip().splitlines()),1)
        output=json.loads(p.stdout)
        self.assertEqual(output["source_commit_sha"],head)
        self.assertFalse(output["action_authorized"])

    def test_cli_bad_source_sha_exits_without_fake_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"req.json"
            file.write_text(json.dumps(request(expected_main_sha="b"*40)),
                            encoding="utf-8")
            p=subprocess.run(
                [sys.executable,str(ROOT/"chat_bridge.py"),
                 "--request",str(file),"--source-root",str(ROOT)],
                capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("NAV_CHAT_BRIDGE_FAIL:STALE_MAIN_SHA",p.stderr)
        self.assertFalse(p.stdout.strip())


if __name__=="__main__":
    unittest.main()
