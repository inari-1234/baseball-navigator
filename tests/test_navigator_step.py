"""P3 navigator safety, ranking and knowledge-use regression tests."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from navigator_step import navigator_step, _load_catalog

ROOT = Path(__file__).resolve().parents[1]


def canonical():
    state = json.loads((ROOT / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "DECISION_CONTRACT.json").read_text(encoding="utf-8"))
    return state, contract


def attested(state, **kwargs):
    return {
        "verified_for_current_state": True,
        "source_event_seq": state["last_event_seq"],
        "period": state["period_floor"],
        "branch": "ACCEPTED",
        "evidence_refs": [state["resources"]["last_observed"]],
        **kwargs,
    }


def context_for(state, failure="CONTACT", *, ready=True):
    ctx = {"failure_assessment": attested(state, mode=failure)}
    if ready:
        ctx["training_readiness"] = attested(
            state, available_drills=["素振り", "ダンベル"],
            ready_players=["岡治", "今井", "たき", "芦田", "入江"])
    return ctx


class NavigatorStepRegression(unittest.TestCase):
    def setUp(self):
        self.state, self.contract = canonical()

    def navigate(self, message="次は何をすべき？", *, state=None, context=None,
                 boot=True, revision=None, root=ROOT):
        return navigator_step(
            message, state=self.state if state is None else state,
            contract=self.contract, boot_verified=boot,
            expected_event_seq=revision, context=context, root=root)

    def trusted(self):
        s = copy.deepcopy(self.state)
        s["timeline_status"] = "TRUSTED"
        return s

    def test_canonical_rollback_emits_conditional_target_not_paid_action(self):
        out = self.navigate("スキル獲得に向けて何をすべき？")
        self.assertEqual(out["status"], "BLOCKED_UNVERIFIED_TIMELINE")
        self.assertEqual(out["primary_next_step"], "VERIFY_CURRENT_SAVE_ANCHOR")
        self.assertFalse(out["action_authorized"])
        self.assertIsNone(out["action_draft"])
        self.assertEqual(out["source_event_seq"], 10)
        self.assertIn("SKILL-4TH-PATTERN", out["knowledge_refs"])
        self.assertEqual(len(out["candidates"]), 4 + 3 + 1)
        contact = next(x for x in out["candidates"] if x["id"] == "TRAIN_CONTACT_ON")
        self.assertEqual(contact["participants"], ["岡治", "今井", "たき"])
        self.assertEqual(contact["cost"], {"sports": 6, "cheer": 20})
        self.assertIsNone(contact["training_observed_counts"]["今井"]["committed_count"])
        self.assertTrue(contact["participants_are_historical_candidates"])

    def test_report_then_action_is_ingest_first(self):
        state = copy.deepcopy(self.state)
        out = self.navigate("特訓した。次は何をすべき？", state=state)
        self.assertEqual(out["status"], "INGEST_BEFORE_ADVICE")
        self.assertFalse(out["action_authorized"])
        self.assertEqual(out["candidates"], [])
        self.assertEqual(self.state, state)

    def test_read_only_is_never_game_action(self):
        out = self.navigate("今の試合予定を教えて")
        self.assertEqual(out["status"], "READ_ONLY_READY")
        self.assertIn("scheduled_matches", out["observation"])
        self.assertEqual(out["candidates"], [])
        self.assertFalse(out["side_effects"])

    def test_boot_missing_fails_closed(self):
        out = self.navigate(boot=False)
        self.assertEqual(out["status"], "BOOT_REQUIRED")
        self.assertEqual(out["candidates"], [])

    def test_stale_expected_revision_blocks_before_candidate_scoring(self):
        out = self.navigate(revision=self.state["last_event_seq"] - 1)
        self.assertEqual(out["status"], "STALE_STATE_REVISION")
        self.assertEqual(out["candidates"], [])

    def test_current_trusted_but_no_scoring_evidence_stops(self):
        state = self.trusted()
        out = self.navigate(state=state, context={"training_readiness":
                            attested(state, available_drills=["素振り"],
                                     ready_players=["岡治", "今井", "たき"])})
        self.assertEqual(out["status"], "NEEDS_GROUNDED_FAILURE_ASSESSMENT")
        self.assertIsNone(out["selected_candidate"])
        self.assertFalse(out["action_authorized"])

    def test_contact_mode_prioritizes_real_contact_draft(self):
        state = self.trusted()
        out = self.navigate(state=state, context=context_for(state))
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["selected_candidate"], "TRAIN_CONTACT_ON")
        self.assertEqual(out["action_draft"]["participants"], ["岡治", "今井", "たき"])
        self.assertEqual(out["action_draft"]["spend"], {"sports": 6, "cheer": 20})
        self.assertIn("DC-OFF-001", out["rule_ids"])
        self.assertIn("SKILL-4TH-PATTERN", out["action_draft"]["knowledge_refs"])
        self.assertFalse(out["action_draft"]["claimed_fourth_checkpoint"])
        self.assertFalse(out["action_authorized"])
        self.assertTrue(out["requires_manual_acceptance"])

    def test_conversion_skill_goal_does_not_invent_power_cheer_cost(self):
        state = self.trusted()
        out = self.navigate("スキル獲得なら次は何をすべき？",
                            state=state, context=context_for(state, "CONVERSION"))
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertEqual(out["provisional_target"], "TRAIN_POWER_ON")
        self.assertIn("EXACT_CHEER_ON_COST_UNVERIFIED", out["blocking_reasons"])
        self.assertIn("DC-OFF-002", out["rule_ids"])
        self.assertFalse(out["action_authorized"])

    def test_conversion_ability_goal_can_use_verified_power_off(self):
        state = self.trusted()
        out = self.navigate(state=state, context=context_for(state, "CONVERSION"))
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["selected_candidate"], "TRAIN_POWER_OFF")
        self.assertEqual(out["action_draft"]["spend"], {"sports": 7})
        target = next(x for x in out["candidates"] if x["id"] == "TRAIN_POWER_OFF")
        self.assertEqual(target["skill_popup_evidence"], "UNKNOWN")
        self.assertFalse(out["action_authorized"])

    def test_source_attested_power_cheer_cost_unlocks_draft(self):
        state = self.trusted()
        ctx = context_for(state, "CONVERSION")
        ctx["training_readiness"]["cheer_on_costs"] = {"ダンベル": 20}
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["selected_candidate"], "TRAIN_POWER_ON")
        self.assertEqual(out["action_draft"]["spend"], {"sports": 7, "cheer": 20})
        self.assertFalse(out["action_authorized"])

    def test_no_current_readiness_does_not_promote_old_affinity(self):
        state = self.trusted()
        out = self.navigate(state=state, context=context_for(state, ready=False))
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("CURRENT_TRAINING_READINESS_SOURCE_MISSING_OR_STALE",
                      out["blocking_reasons"])

    def test_stale_player_readiness_source_rejected(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["training_readiness"]["source_event_seq"] -= 1
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("CURRENT_TRAINING_READINESS_SOURCE_MISSING_OR_STALE",
                      out["blocking_reasons"])

    def test_stale_failure_assessment_does_not_set_mode(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["failure_assessment"]["period"] = "Y1-05"
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "NEEDS_GROUNDED_FAILURE_ASSESSMENT")
        self.assertEqual(out["failure_mode"], "UNKNOWN")

    def test_missing_evidence_refs_disables_mode(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["failure_assessment"]["evidence_refs"] = []
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["failure_mode"], "UNKNOWN")

    def test_insufficient_current_sports_blocks_even_verified_group(self):
        state = self.trusted()
        state["resources"]["values"]["sports"] = 4
        out = self.navigate(state=state, context=context_for(state))
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("INSUFFICIENT_OR_UNKNOWN_RESOURCE:sports",
                      out["blocking_reasons"])

    def test_unverified_current_cheer_blocks(self):
        state = self.trusted()
        state["resources"]["fresh"] = False
        out = self.navigate(state=state, context=context_for(state))
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("STALE_RESOURCES", out["blocking_reasons"])

    def test_unavailable_current_drill_blocks(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["training_readiness"]["available_drills"] = ["ダンベル"]
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("DRILL_AVAILABILITY_UNVERIFIED", out["blocking_reasons"])

    def test_current_verified_group_overrides_historical_fixed_three(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["training_readiness"]["preferred_participant_groups"] = {
            "素振り": {
                "players": ["入江", "今井", "たき"],
                "basis": "CURRENT_OCTOBER_LINEUP_SCORING_NEED",
                "evidence_refs": ["EV-ACTIVE-LINEUP-DECISION"],
            }
        }
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["selected_candidate"], "TRAIN_CONTACT_ON")
        self.assertEqual(out["action_draft"]["participants"], ["入江", "今井", "たき"])
        candidate = next(x for x in out["candidates"] if x["id"] == "TRAIN_CONTACT_ON")
        self.assertFalse(candidate["participants_are_historical_candidates"])
        self.assertEqual(candidate["participant_selection_basis"],
                         "CURRENT_OCTOBER_LINEUP_SCORING_NEED")
        self.assertEqual(candidate["participant_selection_evidence_refs"],
                         ["EV-ACTIVE-LINEUP-DECISION"])

    def test_unsubstantiated_current_group_override_blocks_not_silently_falls_back(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["training_readiness"]["preferred_participant_groups"] = {
            "素振り": {
                "players": ["入江", "今井", "たき"],
                "basis": "CURRENT_OCTOBER_LINEUP_SCORING_NEED",
                "evidence_refs": [],
            }
        }
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("LIVE_PARTICIPANT_GROUP_OVERRIDE_NOT_VERIFIED",
                      out["blocking_reasons"])

    def test_catalog_valid_looking_mutation_is_rejected_by_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("NAV_TACTICS.json", "KNOWLEDGE_MANIFEST.json"):
                shutil.copyfile(ROOT / name, base / name)
            path = base / "NAV_TACTICS.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["drills"][0]["sports_cost"] = 8
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NAV_TACTICS_SOURCE_INTEGRITY_MISMATCH"):
                _load_catalog(base)

    def test_handoff_retains_navigation_entrypoint(self):
        handoff=(ROOT / "CURRENT_HANDOFF.md").read_text(encoding="utf-8")
        agents=(ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("NAVIGATOR:navigator_step.py", handoff)
        self.assertIn("navigator_step.py", agents)
        self.assertTrue((ROOT / "docs/NAVIGATOR_STEP_PROTOCOL.md").is_file())

    def test_current_player_not_ready_blocks(self):
        state = self.trusted()
        ctx = context_for(state)
        ctx["training_readiness"]["ready_players"] = ["岡治", "今井"]
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("CURRENT_PLAYER_HP_OR_ELIGIBILITY_UNVERIFIED",
                      out["blocking_reasons"])

    def test_three_logged_sessions_without_exact_baseline_are_not_fourth(self):
        state = self.trusted()
        state["training_counts_by_player_drill"] = {"今井|素振り": 3}
        out = self.navigate(state=state, context=context_for(state))
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertFalse(out["action_draft"]["claimed_fourth_checkpoint"])
        candidate = next(x for x in out["candidates"] if x["id"] == "TRAIN_CONTACT_ON")
        info = candidate["training_observed_counts"]["今井"]
        self.assertEqual(info["recorded_lower_bound"], 3)
        self.assertEqual(info["count_certainty"], "RECORDED_LOWER_BOUND")
        self.assertIsNone(info["committed_count"])
        self.assertFalse(info["fourth_checkpoint"])

    def test_exact_three_committed_sessions_marks_fourth_but_no_guarantee(self):
        state = self.trusted()
        state["training_counts_by_player_drill"] = {"今井|素振り": 3}
        state["training_counts_exact_by_player_drill"] = {"今井|素振り": 3}
        state["training_count_certifications"] = {
            "今井|素振り": {"event_id":"TEST-EXACT-IMAI",
                           "source_kind":"USER_REPORT",
                           "scope":"EXACT_CURRENT_ACCEPTED_SAVE"}}
        out = self.navigate(state=state, context=context_for(state))
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        rec = out["action_draft"]
        self.assertTrue(rec["claimed_fourth_checkpoint"])
        self.assertEqual(rec["checkpoint_player"], "今井")
        self.assertFalse(out["action_authorized"])
        c = next(x for x in out["candidates"] if x["id"] == "TRAIN_CONTACT_ON")
        self.assertEqual(c["training_observed_counts"]["今井"]["next_ordinal"], 4)
        self.assertTrue(c["target_skill_at_this_drill_not_guaranteed"])

    def test_discarded_screens_do_not_create_skill_or_count(self):
        state = self.trusted()
        baseline = copy.deepcopy(state)
        out = self.navigate(state=state, context=context_for(state))
        self.assertEqual(state, baseline)
        self.assertEqual(state["skills"], baseline["skills"])
        self.assertEqual(state["training_counts_by_player_drill"], {})
        self.assertEqual(out["action_draft"]["claimed_fourth_checkpoint"], False)

    def test_recovery_requires_verified_inventory_and_target_hp(self):
        state = self.trusted()
        ctx = context_for(state, "RECOVERY_REQUIRED")
        ctx["recovery"] = attested(state, player="石渡", item="チョコレート",
                                   needed=True, verified_recovery_effect=True)
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertEqual(out["provisional_target"], "RECOVERY")
        self.assertIn("CURRENT_FULL_INVENTORY_UNVERIFIED", out["blocking_reasons"])
        self.assertIn("CURRENT_TARGET_HP_UNVERIFIED", out["blocking_reasons"])

    def test_recovery_item_requires_effect_evidence_not_just_ownership(self):
        state = self.trusted()
        state["inventory"] = {"fresh": True, "items": {"チョコレート": 1}}
        state.setdefault("hp_by_player", {})["石渡"] = {"fresh": True}
        ctx = context_for(state, "RECOVERY_REQUIRED")
        ctx["recovery"] = attested(state, player="石渡", item="チョコレート",
                                   needed=True)
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("ITEM_RECOVERY_EFFECT_NOT_SOURCE_VERIFIED",
                      out["blocking_reasons"])

    def test_verified_recovery_item_yields_only_draft(self):
        state = self.trusted()
        state["inventory"] = {"fresh": True, "items": {"チョコレート": 1}}
        state.setdefault("hp_by_player", {})["石渡"] = {"fresh": True}
        ctx = context_for(state, "RECOVERY_REQUIRED")
        ctx["recovery"] = attested(state, player="石渡", item="チョコレート",
                                   needed=True, verified_recovery_effect=True)
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["selected_candidate"], "RECOVERY")
        self.assertEqual(out["action_draft"]["items"], [
            {"item": "チョコレート", "quantity": 1}])
        self.assertFalse(out["action_authorized"])

    def test_no_auto_match_while_current_month_before_july(self):
        state = self.trusted()
        ctx = context_for(state, "ADEQUATE")
        match_id = "Y1-JUL-MANRUI"
        ctx["match_readiness"] = attested(state, match_id=match_id, ready=True)
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "BLOCKED_CANDIDATE")
        self.assertIn("MATCH_NOT_IN_CURRENT_GAME_PERIOD", out["blocking_reasons"])

    def test_current_month_scheduled_match_can_be_draft_after_attestation(self):
        state = self.trusted()
        state["period_floor"] = "Y1-07"
        ctx = context_for(state, "ADEQUATE")
        ctx["match_readiness"] = attested(
            state, match_id="Y1-JUL-MANRUI", ready=True)
        out = self.navigate(state=state, context=ctx)
        self.assertEqual(out["status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["selected_candidate"], "MATCH:Y1-JUL-MANRUI")
        self.assertEqual(out["action_draft"]["target_period"], "Y1-07")
        self.assertFalse(out["action_authorized"])

    def test_ended_match_is_never_proposed(self):
        state = self.trusted()
        state["period_floor"] = "Y1-07"
        state["matches"]["Y1-JUL-MANRUI"]["status"] = "PLAYED"
        ctx = context_for(state, "ADEQUATE")
        ctx["match_readiness"] = attested(
            state, match_id="Y1-JUL-MANRUI", ready=True)
        out = self.navigate(state=state, context=ctx)
        self.assertNotEqual(out["selected_candidate"], "MATCH:Y1-JUL-MANRUI")
        self.assertTrue(all(c["id"] != "MATCH:Y1-JUL-MANRUI"
                            for c in out["candidates"]))

    def test_knowledge_gate_downgrade_blocks_all_action_comparison(self):
        state = self.trusted()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("EVIDENCE_EVENTS.jsonl", "EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
                         "EXPERIMENT_TRIALS.jsonl", "KNOWLEDGE_CLAIMS.json",
                         "KNOWLEDGE_MANIFEST.json", "AGENTS.md", "CURRENT_HANDOFF.md",
                         "NAV_TACTICS.json"):
                shutil.copyfile(ROOT / name, base / name)
            path = base / "KNOWLEDGE_CLAIMS.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["claims"][0]["status"] = "HYPOTHESIS"
            path.write_text(json.dumps(data), encoding="utf-8")
            out = self.navigate(state=state, context=context_for(state), root=base)
            self.assertEqual(out["status"], "KNOWLEDGE_GATE_FAILED")
            self.assertFalse(out["action_authorized"])

    def test_invalid_catalog_cost_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copyfile(ROOT / "NAV_TACTICS.json", base / "NAV_TACTICS.json")
            path = base / "NAV_TACTICS.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["drills"][0]["sports_cost"] = -6
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NAV_TACTICS_INVALID_DRILL"):
                _load_catalog(base)

    def test_cli_real_snapshot_safe_and_deterministic(self):
        args = [sys.executable, "navigator_step.py",
                "スキル獲得に向けて何をすべき？", "--boot-verified",
                "--expected-event-seq", "10"]
        a = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
        b = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(a.stdout, b.stdout)
        data = json.loads(a.stdout)
        self.assertEqual(data["status"], "BLOCKED_UNVERIFIED_TIMELINE")
        self.assertFalse(data["action_authorized"])


if __name__ == "__main__":
    unittest.main()
