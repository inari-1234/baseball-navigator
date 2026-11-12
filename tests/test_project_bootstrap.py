"""P6: one-phrase resume and source-verified bootstrap regression."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from postload_fixture import copy_postload_authorities
import subprocess
import sys
import tempfile
import unittest

from project_bootstrap import BOOT_ORDER, ResumeError, bootstrap, git_sha, match_project

ROOT=Path(__file__).resolve().parents[1]
FILES=list(BOOT_ORDER)+[
    "AGENTS.md","PROJECT_ENTRYPOINT.json","LIVE_EVENTS.jsonl",
    "EVIDENCE_EVENTS.jsonl","EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
    "EXPERIMENT_TRIALS.jsonl","KNOWLEDGE_CLAIMS.json","KNOWLEDGE_MANIFEST.json",
]
FAKE_SHA="a"*40


class Recognition(unittest.TestCase):
    def setUp(self):
        self.registry=json.loads(
            (ROOT/"PROJECT_ENTRYPOINT.json").read_text(encoding="utf-8"))

    def test_short_explicit_project_utterances(self):
        for phrase in (
            "野球部ものがたりの続き",
            "inari-1234/baseball-navigator の続きを再開",
            "さっぽこ高校を倒したい",
            "カイロソフトの野球の続き",
            "野球部 攻略 続き",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(match_project(phrase,self.registry))

    def test_generic_words_do_not_match_unrelated_project(self):
        for phrase in ("野球部","野球","部活","続きをやりたい","高校野球の試合","", "攻略について"):
            with self.subTest(phrase=phrase):
                self.assertFalse(match_project(phrase,self.registry))

    def test_unrelated_chat_fails_closed(self):
        with self.assertRaisesRegex(ResumeError,
                                    "PROJECT_NOT_UNAMBIGUOUSLY_IDENTIFIED"):
            bootstrap("学校の野球部の連絡",root=ROOT,checked_main_sha=FAKE_SHA)

    def test_unsafe_short_alias_in_registry_rejected(self):
        data=json.loads(json.dumps(self.registry))
        data["recognition"]["normalized_substrings"]=["野球"]
        with self.assertRaisesRegex(ResumeError,"INVALID_PROJECT_ALIASES"):
            match_project("野球の続き",data)


class Boot(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        copy_postload_authorities(self.root, FILES)

    def boot(self):
        return bootstrap("野球部ものがたりの続き",root=self.root,
                         checked_main_sha=FAKE_SHA,
                         expected_main_sha=FAKE_SHA)

    def test_seven_file_boot_replay_skill_and_rollback_continuity(self):
        result=self.boot()
        self.assertEqual(result["status"],"BOOT_VERIFIED_ACTIONS_BLOCKED")
        self.assertEqual(result["boot_files_read"],list(BOOT_ORDER))
        self.assertTrue(result["boot_order_verified"])
        self.assertTrue(result["live_replay_verified"])
        self.assertTrue(result["knowledge_integrity_verified"])
        self.assertEqual(len(result["boot_file_sha256"]),7)
        self.assertEqual(result["state"]["event_seq"],10)
        self.assertEqual(result["state"]["period"],"Y1-06")
        self.assertEqual(result["state"]["clock"],"PM 5:20")
        self.assertEqual(result["state"]["resources"]["values"]["sports"],28)
        self.assertEqual(result["state"]["resources"]["values"]["cheer"],100)
        self.assertEqual(result["state"]["current_skills"],"UNVERIFIED_AFTER_ROLLBACK")
        self.assertEqual(result["state"]["current_training_counts"],"UNVERIFIED_AFTER_ROLLBACK")
        self.assertEqual(len(result["state"]["scheduled_matches"]),3)
        self.assertEqual(result["knowledge"]["fourth_training_status"],"OBSERVED_PATTERN")
        self.assertTrue(result["knowledge"]["fourth_training_not_guaranteed"])
        self.assertEqual(result["knowledge"]["negative_rerolls_earlier_sessions_approx"],40)
        self.assertEqual(len(result["knowledge"]["historical_accepted_at_reporting"]),2)
        self.assertEqual(result["knowledge"]["historical_private_backup_checkpoints"],6)
        self.assertFalse(result["knowledge"]["private_library_reachability_checked_now"])
        ledger=json.loads((self.root/"CURRENT_RUN_LEDGER.yaml").read_text(encoding="utf-8"))
        recorded=[json.loads(x) for x in
                  (self.root/"DECISION_LOG.jsonl").read_text(encoding="utf-8").splitlines()
                  if x.strip()]
        self.assertEqual(result["latest_decision"]["seq"],len(recorded))
        self.assertEqual(result["latest_decision"]["seq"],ledger["ledger_version"])
        self.assertEqual(result["latest_decision"]["event"],recorded[-1]["event"])
        self.assertFalse(result["action_authorized"])
        self.assertFalse(result["writes_performed"])
        self.assertFalse(result["automatic_new_chat_invocation_guaranteed"])

    def test_postload_user_attestation_does_not_infer_restore_checkpoint(self):
        ledger=json.loads((self.root/"CURRENT_RUN_LEDGER.yaml").read_text(encoding="utf-8"))
        fact=next(f for f in ledger["facts"]
                  if f["fact_id"]=="FACT-Y1-JUNE-520-IMMEDIATE-POSTLOAD")
        self.assertTrue(fact["value"]["post_load_immediate"])
        self.assertFalse(fact["value"]["intervening_game_actions"])
        self.assertEqual(fact["value"]["restored_save_checkpoint"],"UNKNOWN")
        unknown=next(u for u in ledger["unknowns"]
                     if u["unknown_id"]=="UNK-ROLLBACK-SAVEPOINT-20261106")
        self.assertEqual(unknown["status"],"OPEN")
        self.assertEqual(ledger["current_gate"]["status"],"BLOCKED_UNKNOWN")
        boot=self.boot()
        self.assertEqual(boot["status"],"BOOT_VERIFIED_ACTIONS_BLOCKED")
        self.assertEqual(boot["state"]["event_seq"],10)
        self.assertEqual(boot["state"]["current_training_counts"],
                         "UNVERIFIED_AFTER_ROLLBACK")

    def test_cli_actual_git_revision_no_mutation(self):
        sha=git_sha(ROOT)
        paths=("LIVE_EVENTS.jsonl","CURRENT_LIVE_STATE.json","KNOWLEDGE_CLAIMS.json")
        before={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in paths}
        p=subprocess.run([sys.executable,str(ROOT/"project_bootstrap.py"),
                          "野球部ものがたりの続き","--expected-main-sha",sha],
                         cwd=ROOT,text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(p.stdout)["source_commit_sha"],sha)
        after={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in paths}
        self.assertEqual(before,after)

    def test_required_boot_document_missing(self):
        (self.root/"CURRENT_HANDOFF.md").unlink()
        with self.assertRaisesRegex(ResumeError,"REQUIRED_SOURCE_UNREADABLE:CURRENT_HANDOFF.md"):
            self.boot()

    def test_boot_document_order_change_rejected(self):
        f=self.root/"AGENTS.md"
        s=f.read_text(encoding="utf-8")
        s=s.replace("1. "+chr(96)+"RUN_GUARD_POLICY.yaml"+chr(96),
                    "1. "+chr(96)+"CURRENT_LIVE_STATE.json"+chr(96),1)
        f.write_text(s,encoding="utf-8")
        with self.assertRaisesRegex(ResumeError,"BOOT_ORDER_ALTERED"):
            self.boot()

    def test_state_projection_mismatch_rejected(self):
        f=self.root/"CURRENT_LIVE_STATE.json"
        j=json.loads(f.read_text(encoding="utf-8"))
        j["resources"]["values"]["sports"]=99
        f.write_text(json.dumps(j,ensure_ascii=False),encoding="utf-8")
        with self.assertRaisesRegex(ResumeError,"CURRENT_STATE_REPLAY_MISMATCH"):
            self.boot()

    def test_stale_sha_fails(self):
        with self.assertRaisesRegex(ResumeError,"STALE_MAIN_SHA"):
            bootstrap("野球部ものがたり",root=self.root,
                      checked_main_sha=FAKE_SHA,expected_main_sha="b"*40)

    def test_missing_entrypoint_rejected(self):
        (self.root/"PROJECT_ENTRYPOINT.json").unlink()
        with self.assertRaisesRegex(ResumeError,"REQUIRED_SOURCE_UNREADABLE"):
            self.boot()

    def test_fourth_claim_downgrade_rejected(self):
        f=self.root/"KNOWLEDGE_CLAIMS.json"
        j=json.loads(f.read_text(encoding="utf-8"))
        j["claims"][0]["status"]="UNVERIFIED_HYPOTHESIS"
        f.write_text(json.dumps(j,ensure_ascii=False),encoding="utf-8")
        with self.assertRaisesRegex(ResumeError,"KNOWLEDGE_CONTINUITY_FAILED"):
            self.boot()

    def test_missing_backup_evidence_rejected(self):
        f=self.root/"EVIDENCE_BACKUP_CHECKPOINTS.jsonl"
        rows=f.read_text(encoding="utf-8").splitlines()
        f.write_text("\n".join(rows[:-1])+"\n",encoding="utf-8")
        with self.assertRaisesRegex(ResumeError,"KNOWLEDGE_CONTINUITY_FAILED"):
            self.boot()

    def test_decision_ledger_mismatch_rejected(self):
        f=self.root/"CURRENT_RUN_LEDGER.yaml"
        j=json.loads(f.read_text(encoding="utf-8"))
        j["ledger_version"]+=1
        f.write_text(json.dumps(j,ensure_ascii=False),encoding="utf-8")
        with self.assertRaisesRegex(ResumeError,"DECISION_LEDGER_VERSION_CONFLICT"):
            self.boot()

    def test_inactive_critical_rule_blocks_boot(self):
        f=self.root/"DECISION_CONTRACT.json"
        j=json.loads(f.read_text(encoding="utf-8"))
        for r in j["rules"]:
            if r["rule_id"]=="DC-STATE-001":
                r["status"]="RETIRED"
        f.write_text(json.dumps(j,ensure_ascii=False),encoding="utf-8")
        with self.assertRaisesRegex(ResumeError,"CRITICAL_ACTIVE_RULE_MISSING"):
            self.boot()


if __name__=="__main__":
    unittest.main()
