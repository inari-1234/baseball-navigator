"""Regression suite for durable experimental evidence and skill decision gates."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from knowledge_engine import (
    KnowledgeError, load_knowledge, skill_guidance, validate_knowledge,
    validate_skill_recommendation, FOURTH, ACCEPTED,
)
from text_fast import TextFastEngine, classify_text
from test_navigator_step import context_for


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    "EVIDENCE_EVENTS.jsonl", "EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
    "EXPERIMENT_TRIALS.jsonl",
    "KNOWLEDGE_CLAIMS.json", "KNOWLEDGE_MANIFEST.json",
    "AGENTS.md", "CURRENT_HANDOFF.md",
)


def load_canonical():
    state = json.loads((ROOT / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "DECISION_CONTRACT.json").read_text(encoding="utf-8"))
    return state, contract


def draft(*, count_player="入江", claimed_fourth=True):
    return {"action_type":"TRAIN","based_on_event_seq":10,
            "rule_ids":["DC-TRAIN-001","DC-TRAIN-002","DC-CHEER-001",
                        "DC-ACTION-001","DC-OFF-001"],"participants":["入江","今井","芦田"],
            "cheer":"ON","spend":{"sports":6,"cheer":20},
            "skill_goal":"ACQUIRE","drill":"素振り",
            "knowledge_refs":[FOURTH],"claimed_fourth_checkpoint":claimed_fourth,
            "checkpoint_player":count_player}


def certify_synthetic_count(state, player, drill, count):
    # Positive validator fixtures model fields emitted by sourced baseline replay.
    # tests/test_live_state_engine.py separately proves the replay requirements.
    key = player + "|" + drill
    state["training_counts_exact_by_player_drill"] = {key: count}
    state["training_count_certifications"] = {
        key: {"event_id": "TEST-SOURCE-EXACT", "source_kind": "USER_REPORT",
              "scope": "EXACT_CURRENT_ACCEPTED_SAVE"}}
    return state


class KnowledgeFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for f in FIXTURES:
            shutil.copyfile(ROOT / f, self.root / f)

    def tearDown(self):
        self.tmp.cleanup()

    def mutate_json(self, file, fn):
        p = self.root / file
        doc = json.loads(p.read_text(encoding="utf-8"))
        fn(doc)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+"\n",
                     encoding="utf-8")

    def mutate_jsonl(self, file, fn):
        p = self.root / file
        rows = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines()]
        fn(rows)
        p.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows)+"\n",
                     encoding="utf-8")

    def expect_error(self, code):
        with self.assertRaises(KnowledgeError) as ctx:
            validate_knowledge(self.root)
        self.assertIn(code, str(ctx.exception))

    def test_real_experiment_has_preserved_negative_and_positive_evidence(self):
        result = validate_knowledge(self.root)
        self.assertEqual(result["result"],"PASS")
        self.assertEqual(result["claims"],2)
        self.assertEqual(result["trial_groups"],3)
        self.assertEqual(result["evidence"],7)
        self.assertEqual(result["claim_status"],"OBSERVED_PATTERN")
        self.assertFalse(result["original_media_persisted"])

    def test_source_image_hashes_and_nonpersistent_image_bytes(self):
        doc = load_knowledge(self.root)
        imgs = [e for e in doc["evidence"].values() if e["kind"] == "SCREENSHOT"]
        self.assertEqual(len(imgs),6)
        self.assertEqual(len({e["source"]["sha256"] for e in imgs}),6)
        self.assertTrue(all(e["source"]["repository_bytes_persisted"] is False
                            for e in imgs))

    def test_checkpoint_metadata_coverage_and_timepoint_semantics(self):
        outcome = validate_knowledge(self.root)
        self.assertEqual(outcome["private_backup_verified_at_checkpoint"], 6)
        self.assertFalse(outcome["private_backup_current_access_verified_by_ci"])
        backups=load_knowledge(self.root)["backups"]
        self.assertEqual(len(backups), 6)
        self.assertTrue(all(not row["original_bytes_in_repository"]
                            and not row["private_locator_in_repository"]
                            and row["availability_now_not_guaranteed"]
                            for row in backups.values()))

    def test_missing_backup_checkpoint_fails(self):
        self.mutate_jsonl("EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
                          lambda rows: rows.pop())
        self.expect_error("SCREENSHOT_BACKUP_COVERAGE_MISSING")

    def test_public_attestation_sha_mismatch_fails(self):
        self.mutate_jsonl("EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
                          lambda rows: rows[0].update(
                              library_readback_sha256="a"*64))
        self.expect_error("BACKUP_IMAGE_HASH_MISMATCH")

    def test_duplicate_public_attestation_fails(self):
        self.mutate_jsonl("EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
                          lambda rows: rows.append(copy.deepcopy(rows[0])))
        self.expect_error("DUPLICATE_RECORD_ID")

    def test_leaked_private_locator_rejected(self):
        self.mutate_jsonl("EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
                          lambda rows: rows[0].update(
                              library_file_id="libfile_SECRET"))
        self.expect_error("PUBLIC_BACKUP_PRIVATE_FIELD_LEAK")

    def test_misleading_permanent_availability_status_fails(self):
        self.mutate_jsonl("EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
                          lambda rows: rows[0].update(
                              availability_now_not_guaranteed=False))
        self.expect_error("INVALID_BACKUP_ATTESTATION")

    def test_missing_image_evidence_fails(self):
        self.mutate_jsonl("EVIDENCE_EVENTS.jsonl", lambda r: r.pop(0))
        self.expect_error("MISSING_REQUIRED_EVIDENCE")

    def test_duplicate_evidence_fails(self):
        self.mutate_jsonl("EVIDENCE_EVENTS.jsonl", lambda r: r.append(copy.deepcopy(r[0])))
        self.expect_error("DUPLICATE_RECORD_ID")

    def test_missing_trial_fails(self):
        self.mutate_jsonl("EXPERIMENT_TRIALS.jsonl", lambda r: r.pop(0))
        self.expect_error("MISSING_REQUIRED_TRIAL")

    def test_unverified_fourth_downgrade_fails(self):
        self.mutate_json("KNOWLEDGE_CLAIMS.json", lambda c:
                         c["claims"][0].update(status="HYPOTHESIS"))
        self.expect_error("FOURTH_CLAIM_DOWNGRADED")

    def test_altered_negative_trial_fails(self):
        self.mutate_jsonl("EXPERIMENT_TRIALS.jsonl", lambda r:
                          r[0].update(approx_resets=0))
        self.expect_error("NEGATIVE_RESET_EVIDENCE_DOWNGRADED")

    def test_fourth_must_retain_ordinal_four(self):
        self.mutate_jsonl("EXPERIMENT_TRIALS.jsonl", lambda r:
                          r[1].update(ordinal_range=[3, 3]))
        self.expect_error("FOURTH_POSITIVE_EVIDENCE_DOWNGRADED")

    def test_five_may_screens_cannot_create_five_accepted_skills(self):
        def bad(rows):
            rows[2]["accepted_at_reporting"].append(
                {"player":"今井","skill":"ミート力アップ","occurrences":4})
        self.mutate_jsonl("EXPERIMENT_TRIALS.jsonl", bad)
        self.expect_error("HISTORICAL_ACCEPTED_SKILLS_MISMATCH")

    def test_cannot_promote_historical_skill_to_current(self):
        self.mutate_json("KNOWLEDGE_CLAIMS.json", lambda c: c["claims"][1].update(
            current_run_effect="CONFIRMED_CURRENT"))
        self.expect_error("HISTORICAL_ACCEPTANCE_DOWNGRADED_OR_PROMOTED")

    def test_trial_evidence_link_missing_fails(self):
        self.mutate_jsonl("EXPERIMENT_TRIALS.jsonl", lambda r:
                          r[1].update(evidence_refs=["EV-NONEXISTENT"]))
        self.expect_error("TRIAL_EVIDENCE_MISSING")

    def test_claim_trail_cannot_omit_negative_report(self):
        self.mutate_json("KNOWLEDGE_CLAIMS.json",lambda c:
                         c["claims"][0].update(
                             evidence_refs=["EV-SKILL-IMG-"+str(i) for i in range(1,7)]))
        self.expect_error("KNOWLEDGE_NOT_LINKED_TO_ALL_TRIAL_EVIDENCE")

    def test_handoff_must_contain_both_required_claim_ids(self):
        p = self.root / "CURRENT_HANDOFF.md"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "KNOWLEDGE:SKILL-4TH-PATTERN","missing-reference"),encoding="utf-8")
        self.expect_error("HANDOFF_KNOWLEDGE_MISSING")

    def test_agents_must_require_knowledge_gate(self):
        p = self.root / "AGENTS.md"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "KNOWLEDGE_MANIFEST.json","disconnected-manifest"),encoding="utf-8")
        self.expect_error("AGENT_KNOWLEDGE_GATE_NOT_WIRED")

    def test_claim_has_no_false_source_media_persistence(self):
        self.mutate_jsonl("EVIDENCE_EVENTS.jsonl", lambda r:
                          r[0]["source"].update(repository_bytes_persisted=True))
        self.expect_error("UNSUPPORTED_SCREENSHOT_PERSISTENCE_CLAIM")

    def test_hash_mismatch_or_garble_rejected(self):
        self.mutate_jsonl("EVIDENCE_EVENTS.jsonl", lambda r:
                          r[0]["source"].update(sha256="incomplete"))
        self.expect_error("MISSING_SCREENSHOT_HASH")

    def test_substituted_but_well_formed_image_hash_is_rejected(self):
        self.mutate_jsonl("EVIDENCE_EVENTS.jsonl", lambda r:
                          r[0]["source"].update(sha256="a"*64))
        self.expect_error("IMAGE_DIGEST_CHANGED")

    def test_future_manifest_required_claim_must_exist(self):
        self.mutate_json("KNOWLEDGE_MANIFEST.json", lambda m:
                         m["required_knowledge_ids"].append("NEW-IMPORTANT-DISCOVERY"))
        self.expect_error("MANIFEST_REFERENCED_RECORD_MISSING")

    def test_future_manifest_claim_status_must_match(self):
        self.mutate_json("KNOWLEDGE_MANIFEST.json", lambda m:
                         m["required_claim_statuses"].update(
                             {"SKILL-4TH-PATTERN":"UNVERIFIED_HYPOTHESIS"}))
        self.expect_error("MANIFEST_CLAIM_DOWNGRADED")

    def test_manifest_cannot_drop_required_claim(self):
        self.mutate_json("KNOWLEDGE_MANIFEST.json",lambda m:
                         m.update(required_knowledge_ids=[ACCEPTED]))
        self.expect_error("MANIFEST_MISSING")

    def test_legacy_hypothesis_wording_fails(self):
        p = self.root / "CURRENT_HANDOFF.md"
        p.write_text(p.read_text(encoding="utf-8")+
                     "Skill-point accumulation / 4th committed drill threshold is an "
                     "EXPERIMENTAL user hypothesis, not a verified hidden mechanic.",
                     encoding="utf-8")
        self.expect_error("OUTDATED_HYPOTHESIS_PHRASE_REINTRODUCED")


class NavigationGate(unittest.TestCase):
    def setUp(self):
        self.state,self.contract = load_canonical()

    def test_real_canonical_rollback_blocks_skill_action_but_returns_knowledge(self):
        out = skill_guidance(self.state, root=ROOT, player="入江", drill="素振り")
        self.assertEqual(out["knowledge_status"],"OBSERVED_PATTERN")
        self.assertFalse(out["guaranteed_skill_at_fourth"])
        self.assertEqual(out["negative_reset_attempts_approx"],40)
        self.assertFalse(out["committed_count_known"])
        self.assertEqual(out["prior_skills_survive_current_save"],"UNKNOWN")
        self.assertEqual(len(out["prior_accepted_skills"]),2)
        errors = validate_skill_recommendation(
            draft(),self.state,self.contract,root=ROOT)
        self.assertIn("ROLLBACK_SAVEPOINT_UNKNOWN",errors)
        self.assertIn("CURRENT_COMMITTED_COUNT_UNKNOWN",errors)

    def test_observed_skill_counts_are_never_synthesized_as_zero(self):
        s = copy.deepcopy(self.state)
        s["timeline_status"]="TRUSTED"
        s["training_counts_by_player_drill"]={}
        out = skill_guidance(s,root=ROOT,player="入江",drill="素振り")
        self.assertIsNone(out["committed_count"])
        self.assertIsNone(out["next_ordinal"])
        self.assertFalse(out["is_fourth_checkpoint"])

    def test_trusted_three_recorded_without_baseline_does_not_certify_fourth(self):
        s=copy.deepcopy(self.state)
        s["timeline_status"]="TRUSTED"
        s["training_counts_by_player_drill"]={"入江|素振り":3}
        out=skill_guidance(s,root=ROOT,player="入江",drill="素振り")
        self.assertEqual(out["count_certainty"],"RECORDED_LOWER_BOUND")
        self.assertEqual(out["recorded_lower_bound"],3)
        self.assertIsNone(out["committed_count"])
        self.assertFalse(out["is_fourth_checkpoint"])
        errors=validate_skill_recommendation(draft(),s,self.contract,root=ROOT)
        self.assertIn("CURRENT_COMMITTED_COUNT_UNKNOWN",errors)

    def test_observed_three_accepted_trainings_qualifies_fourth_draft(self):
        s = copy.deepcopy(self.state)
        s["timeline_status"]="TRUSTED"
        s["training_counts_by_player_drill"]={"入江|素振り":3}
        certify_synthetic_count(s,"入江","素振り",3)
        out = skill_guidance(s,root=ROOT,player="入江",drill="素振り")
        self.assertEqual(out["count_certainty"],"EXACT_CURRENT_SAVE")
        self.assertEqual(out["certification_event_id"],"TEST-SOURCE-EXACT")
        self.assertTrue(out["is_fourth_checkpoint"])
        self.assertEqual(out["next_ordinal"],4)
        rec = draft()
        context = context_for(s)
        context["training_readiness"]["preferred_participant_groups"]["素振り"]["players"] = rec["participants"]
        self.assertEqual(validate_skill_recommendation(
            rec,s,self.contract,root=ROOT,context=context),[])

    def test_two_or_four_committed_trainings_are_not_fourth(self):
        for count in (2, 4):
            with self.subTest(count=count):
                s=copy.deepcopy(self.state)
                s["timeline_status"]="TRUSTED"
                s["training_counts_by_player_drill"]={"入江|素振り":count}
                certify_synthetic_count(s,"入江","素振り",count)
                errors=validate_skill_recommendation(draft(),s,self.contract,root=ROOT)
                self.assertIn("NOT_FOURTH_COMMITTED_SESSION",errors)

    def test_missing_knowledge_reference_blocks_even_valid_training(self):
        s = copy.deepcopy(self.state)
        s["timeline_status"]="TRUSTED"
        s["training_counts_by_player_drill"]={"入江|素振り":3}
        certify_synthetic_count(s,"入江","素振り",3)
        rec=draft()
        rec["knowledge_refs"]=[]
        errors=validate_skill_recommendation(rec,s,self.contract,root=ROOT)
        self.assertIn("FOURTH_KNOWLEDGE_REF_REQUIRED",errors)

    def test_resource_gate_remains_effective_with_valid_knowledge(self):
        s=copy.deepcopy(self.state)
        s["timeline_status"]="TRUSTED"
        s["training_counts_by_player_drill"]={"入江|素振り":3}
        certify_synthetic_count(s,"入江","素振り",3)
        s["resources"]["values"]["sports"]=1
        errors=validate_skill_recommendation(draft(),s,self.contract,root=ROOT)
        self.assertIn("INSUFFICIENT_OR_UNKNOWN_RESOURCE:sports",errors)

    def test_text_router_reads_required_knowledge_for_skill_question(self):
        self.assertEqual(
            classify_text("練習4回でスキル獲得を狙っていい？").intent,
            "ACTION_EVALUATION")
        engine=TextFastEngine(ROOT)
        out=engine.plan("スキル獲得に向けて動いていい？",
                        state=self.state,contract=self.contract,
                        boot_verified=True)
        self.assertEqual(out["status"],"BLOCKED_UNVERIFIED_TIMELINE")
        self.assertEqual(out["knowledge"]["knowledge_status"],"OBSERVED_PATTERN")
        self.assertIn(FOURTH,out["knowledge_refs"])
        self.assertFalse(out["action_authorized"])

    def test_skill_draft_cannot_bypass_gate_with_generic_question(self):
        state=copy.deepcopy(self.state)
        state["timeline_status"]="TRUSTED"
        state["training_counts_by_player_drill"]={"入江|素振り":3}
        rec=draft()
        rec["knowledge_refs"]=[]
        result=TextFastEngine(ROOT).plan(
            "次は何をすべき？",state=state,contract=self.contract,
            boot_verified=True,recommendation=rec)
        self.assertEqual(result["status"],"ACTION_BLOCKED")
        self.assertIn("FOURTH_KNOWLEDGE_REF_REQUIRED",result["errors"])

    def test_text_router_missing_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as empty:
            out=TextFastEngine(empty).plan(
                "スキル獲得に向けて動いていい？",state=self.state,
                contract=self.contract,boot_verified=True)
            self.assertEqual(out["status"],"KNOWLEDGE_GATE_FAILED")
            self.assertFalse(out["action_authorized"])

    def test_cli_knowledge_validation_and_readonly_guidance(self):
        proc=subprocess.run([sys.executable,"knowledge_engine.py","validate"],
                            cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(proc.stdout)["result"],"PASS")
        p=subprocess.run([sys.executable,"knowledge_engine.py","guidance",
                          "--player","入江","--drill","素振り"],
                         cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(p.stdout)["knowledge_status"],"OBSERVED_PATTERN")


if __name__=="__main__":
    unittest.main()
