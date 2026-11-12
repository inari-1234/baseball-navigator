"""P7-H end-to-end tests using committed, replayable synthetic authorities."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from postload_fixture import copy_postload_authorities
import subprocess
import sys
import tempfile
import unittest

from check_reply import (canonical_state_sha256, check_reply,
                         make_local_verified_draft_packet)
from current_observation import ROSTER_RECORD
from live_state_engine import (OBSERVED_TRACKING, ObservationError, read_events,
                               replay, training_count_status, validate_recommendation)
from save_baseline_preflight import BaselinePreflightError, prepare_observed_tracking
from navigator_step import navigator_step
from next_action import next_action
from project_bootstrap import BOOT_ORDER
from strategy_policy import offense_pattern
from test_navigator_step import attested, context_for, group_selection

ROOT = Path(__file__).resolve().parents[1]
ASK = "次は何をすべき？"
SKILL = "スキル獲得に向けて何をすべき？"
DENIED = "通常練習を打撃重視・練習量軽めに設定してください。"


def fixture_events(*, exact=False):
    def event(seq, kind, **fields):
        return {"seq": seq, "event_id": f"E{seq}", "kind": kind,
                "period": {"year": 1, "month": 6}, "branch": "ACCEPTED",
                "source": {"kind": "USER_REPORT", "locator": f"synthetic {seq}"},
                **fields}
    events = [
        event(i, "MATCH_ATTEMPT", match_id=f"SYNTHETIC-MATCH-{i}",
              opponent=f"テスト校{i}", attempt=1, our_runs=0, their_runs=1)
        for i in (1, 2)
    ]
    events.append(event(3, "SCREEN", after_event_id="E2", clock="PM 5:20",
                        resources={"study": 4, "sports": 28, "play": 25,
                                   "nature": 18, "cheer": 100}))
    if exact:
        events.append(event(4, "TRAINING_COUNT_BASELINE", after_event_id="E3",
                            confirmed_current_save=True,
                            count_scope="EXACT_CURRENT_ACCEPTED_SAVE", counts={"今井|素振り": 3}))
    return events


class NextActionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        copy_postload_authorities(self.repo, (
            *BOOT_ORDER, "AGENTS.md", "PROJECT_ENTRYPOINT.json", "LIVE_EVENTS.jsonl",
            "KNOWLEDGE_CLAIMS.json", "KNOWLEDGE_MANIFEST.json", "EVIDENCE_EVENTS.jsonl",
            "EVIDENCE_BACKUP_CHECKPOINTS.jsonl", "EXPERIMENT_TRIALS.jsonl",
            "NAV_TACTICS.json", ROSTER_RECORD))
        self.git("init", "-q")
        self.contract = json.loads((self.repo / "DECISION_CONTRACT.json").read_text(encoding="utf-8"))

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       stderr=subprocess.PIPE, text=True).strip()

    def commit_fixture(self, events=None):
        if events is not None:
            self.state = replay(events)
            (self.repo / "LIVE_EVENTS.jsonl").write_text(
                "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
                encoding="utf-8")
            (self.repo / "CURRENT_LIVE_STATE.json").write_text(
                json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        else:
            self.state = json.loads((self.repo / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        msg = self.root / "commit.txt"
        msg.write_text("test: commit synthetic navigator authorities\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-q", "-F", str(msg))
        self.sha = self.git("rev-parse", "HEAD")

    def sources(self, context):
        sources = {}
        for name, claim in context.items():
            for ref in claim["evidence_refs"]:
                path = self.root / (ref + ".json")
                path.write_text(json.dumps({"ref": ref, "context": context}, ensure_ascii=False),
                                encoding="utf-8")
                record = sources.setdefault(ref, {
                    "kind": "LOCAL_FILE", "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source_event_seq": self.state["last_event_seq"],
                    "period": self.state["period_floor"], "branch": "ACCEPTED",
                    "reviewed_for_current_state": True, "reviewed_claim_sha256": {},
                })
                record["reviewed_claim_sha256"][name] = canonical_state_sha256(claim)
        return sources

    def run_entry(self, message=ASK, **kwargs):
        return next_action(message, root=self.repo, expected_main_sha=self.sha,
                           expected_event_seq=self.state["last_event_seq"], **kwargs)

    def test_unsupported_settings_reply_rejected_on_current_and_trusted_states(self):
        for events in (None, fixture_events()):
            with self.subTest(trusted=events is not None):
                self.commit_fixture(events)
                context = context_for(self.state) if events else {}
                out = self.run_entry(context=context, evidence_sources=self.sources(context),
                                     proposed_reply=DENIED)
                self.assertTrue(out["live_replay_verified"])
                self.assertGreater(out["candidates_compared"], 0)
                self.assertIsNone(out["safe_reply"])
                self.assertEqual(out["safe_reply_check"]["error_codes"], ["REPLY_NOT_CANONICAL"])
                self.assertNotIn(DENIED, json.dumps(out, ensure_ascii=False))

    def test_supported_training_appears_with_current_evidence_even_without_exact_counts(self):
        self.commit_fixture(fixture_events())
        context = context_for(self.state)
        out = self.run_entry(SKILL, context=context, evidence_sources=self.sources(context))
        self.assertEqual(out["status"], "CERTIFIED_TRAINING_DRAFT", out)
        self.assertEqual(out["strategy_validation"], "PASS")
        self.assertEqual(out["safe_reply_check"]["status"], "PASS")
        self.assertIn("次の1手の候補は素振り", out["safe_reply"])
        self.assertIn("目標 ミート力アップ", out["safe_reply"])
        self.assertIn("4回目の根拠は未確認", out["safe_reply"])
        self.assertIn("スキル目的の再試行は保留", out["safe_reply"])
        self.assertFalse(out["action_authorized"])
        self.assertFalse(out["side_effects"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_verified_power_progression_can_display_cheer_off(self):
        self.commit_fixture(fixture_events())
        context = context_for(self.state, "CONVERSION")
        out = self.run_entry(context=context, evidence_sources=self.sources(context))
        self.assertEqual(out["status"], "CERTIFIED_TRAINING_DRAFT", out)
        self.assertIn("ダンベル／応援OFF／消費予定：スポーツ7", out["safe_reply"])
        self.assertIn("DC-OFF-002", out["safe_reply"])
        self.assertIn("能力上昇が育成目標に合った場合", out["safe_reply"])

    def test_retry_accept_and_fallback_must_match_recomputed_candidate(self):
        self.commit_fixture(fixture_events(exact=True))
        context = context_for(self.state)
        sources = self.sources(context)
        decision = navigator_step(SKILL, state=self.state, contract=self.contract, root=self.repo,
                                  boot_verified=True, context=context)
        packet = make_local_verified_draft_packet(
            decision, self.state, source_commit_sha=self.sha, contract=self.contract,
            context=context, evidence_sources=sources, root=self.repo)
        self.assertIn("目標・高価値スキルを得られず、直前のセーブと時間負担", packet["safe_reply"])
        for key, value in (
                ("accept_if", "ABILITY_GAIN_MEETS_DEVELOPMENT_GOAL"),
                ("reload_if", "NO_VERIFIED_SKILL_REROLL_TARGET"),
                ("fallback", "UNRELATED_FALLBACK")):
            with self.subTest(key=key):
                altered = deepcopy(packet)
                if key == "fallback":
                    altered[key] = value
                else:
                    altered["candidate"]["accept_reload_plan"][key] = value
                verdict = check_reply(packet["safe_reply"], bridge=altered, state=self.state,
                                      contract=self.contract, root=self.repo, context=context,
                                      evidence_sources=sources, expected_main_sha=self.sha,
                                      expected_event_seq=self.state["last_event_seq"])
                self.assertEqual(verdict["error_codes"], ["NAVIGATOR_REVALIDATION_MISMATCH"])

    def test_strategy_blocks_wrong_drill_one_result_and_unreviewed_group(self):
        self.commit_fixture(fixture_events())
        context = context_for(self.state)
        decision = navigator_step(ASK, state=self.state, contract=self.contract, root=self.repo,
                                  boot_verified=True, context=context)
        draft = decision["action_draft"]
        self.assertEqual(validate_recommendation(
            draft, self.state, self.contract, context=context, root=self.repo), [])
        wrong = deepcopy(draft)
        wrong["rule_ids"] = ["DC-OFF-002" if r == "DC-OFF-001" else r for r in wrong["rule_ids"]]
        self.assertIn("TRAINING_STRATEGY_RULE_MISMATCH", validate_recommendation(
            wrong, self.state, self.contract, context=context, root=self.repo))
        context["failure_assessment"]["match_samples"].pop()
        self.assertIn("TRAINING_FAILURE_MODE_NOT_SUPPORTED", validate_recommendation(
            draft, self.state, self.contract, context=context, root=self.repo))
        context = context_for(self.state)
        context["training_readiness"]["preferred_participant_groups"]["素振り"]["evidence_refs"] = ["MISSING"]
        self.assertIn("LIVE_PARTICIPANT_GROUP_OVERRIDE_NOT_VERIFIED", validate_recommendation(
            draft, self.state, self.contract, context=context, root=self.repo))
        context = context_for(self.state)
        context["training_readiness"]["cheer_purposes"]["素振り"]["ON"] = "BOOST_SKILL_ODDS"
        self.assertIn("CHEER_STRATEGY_NOT_VERIFIED", validate_recommendation(
            draft, self.state, self.contract, context=context, root=self.repo))
        settings = {"action_type": "OTHER", "based_on_event_seq": self.state["last_event_seq"],
                    "rule_ids": ["DC-OFF-001"], "practice_focus": "打撃重視", "practice_load": "軽め"}
        self.assertIn("ACTION_STRATEGY_UNSUPPORTED", validate_recommendation(
            settings, self.state, self.contract, root=self.repo))

    def test_match_candidate_is_compared_without_action_text(self):
        events = fixture_events()
        events.append({**events[2], "seq": 4, "event_id": "E4", "kind": "MATCH_SCHEDULE",
                       "entries": [{"match_id": "SCHEDULED", "opponent": "テスト校3"}]})
        self.commit_fixture(events)
        context = context_for(self.state, "ADEQUATE")
        context["match_readiness"] = {
            **context["failure_assessment"], "ready": True, "match_id": "SCHEDULED",
            "reliably_beatable": True,
        }
        out = self.run_entry(context=context)
        self.assertEqual(out["navigator_status"], "VALIDATED_DRAFT_REVIEW")
        self.assertEqual(out["strategy_validation"], "PASS")
        self.assertEqual(out["status"], "CERTIFIED_NO_ACTION")
        self.assertEqual(out["blocking_reasons"], ["UNSUPPORTED_ACTION_FOR_CERTIFIED_REPLY"])
        self.assertNotIn("テスト校3", out["safe_reply"])

    def test_recorded_roster_can_be_reused_without_certifying_history(self):
        self.commit_fixture()
        pending = self.run_entry()
        observed = pending["current_observation"]
        self.assertEqual(observed["counters"]["sports"], 28)
        self.assertEqual(observed["next_evidence"], "CONFIRM_UPLOADED_ROSTER_CONTINUITY")
        self.assertIn("画像の再提出は不要", pending["safe_reply"])
        context = {"roster_chronology": {
            "verified_for_current_state": True, "source_event_seq": self.state["last_event_seq"],
            "period": observed["period"], "branch": "ACCEPTED", "evidence_refs": ["ATTESTATION"],
            "archive_sha256": observed["roster"]["archive_sha256"],
            "after_world_event_id": observed["counter_source_event_id"],
            "same_save_no_intervening_gameplay": True,
        }}
        sources = self.sources(context)
        for _ in range(2):
            linked = self.run_entry(context=context, evidence_sources=sources)
            self.assertEqual(linked["status"], "CERTIFIED_NO_ACTION", linked)
            self.assertEqual(linked["current_observation"]["roster"]["status"],
                             "CURRENT_ROSTER_OBSERVATION")
            self.assertEqual(linked["current_observation"]["next_evidence"],
                             "RECONCILE_RESTORED_SAVE_ANCHOR")
            self.assertEqual(linked["save_history_status"], "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN")
            self.assertIn("過去の特訓総回数、保持スキルは未確定", linked["safe_reply"])
            self.assertNotIn("撮ったか確認", linked["safe_reply"])

    def tracking_preview(self):
        self.commit_fixture()
        events = read_events(self.repo / "LIVE_EVENTS.jsonl")
        ledger = json.loads((self.repo / "CURRENT_RUN_LEDGER.yaml").read_text(encoding="utf-8"))
        observed = self.run_entry()["current_observation"]
        context = {"roster_chronology": {
            "verified_for_current_state": True, "source_event_seq": self.state["last_event_seq"],
            "period": observed["period"], "branch": "ACCEPTED", "evidence_refs": ["ATTESTATION"],
            "archive_sha256": observed["roster"]["archive_sha256"],
            "after_world_event_id": observed["counter_source_event_id"],
            "same_save_no_intervening_gameplay": True,
        }}
        def preview():
            return prepare_observed_tracking(
                self.state, events, ledger, root=self.repo, context=context,
                evidence_sources=self.sources(context))
        with self.assertRaisesRegex(BaselinePreflightError, "CURRENT_SAVE_NO_CHANGE_REPORT_REQUIRED"):
            preview()
        context["roster_chronology"]["unchanged_through_current_report"] = True
        return events, preview()

    def test_tracking_uses_same_roster_and_world_without_reinstating_history(self):
        events, preview = self.tracking_preview()
        self.assertEqual(read_events(self.repo / "LIVE_EVENTS.jsonl"), events)
        event = preview["event_preview"]
        self.commit_fixture([*events, event])
        self.assertEqual(self.state, preview["state_preview"])
        self.assertEqual(self.state["timeline_status"], OBSERVED_TRACKING)
        self.assertEqual(self.state["observed_tracking"]["restored_save_checkpoint"], "UNKNOWN")
        self.assertEqual(self.state["matches"], {})
        self.assertEqual(self.state["skills"], [])
        self.assertIsNone(training_count_status(self.state, "今井", "素振り")["exact_committed_count"])
        report = self.run_entry("進めて")
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION", report)
        self.assertEqual(report["current_observation"]["counters"]["sports"], 28)
        self.assertEqual(report["current_observation"]["roster"]["status"], "CURRENT_ROSTER_OBSERVATION")
        self.assertEqual(report["current_observation"]["next_evidence"], "CURRENT_SPECIAL_TRAINING_SELECTION")
        self.assertEqual(report["action_comparison"]["TRAIN"]["reasons"],
                         ["CURRENT_OCTOBER_DEVELOPMENT_PLAN_REQUIRED"])
        self.assertNotIn("撮ったか確認", report["safe_reply"])

        context = context_for(self.state)
        report = self.run_entry(SKILL, context=context, evidence_sources=self.sources(context))
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION", report)
        self.assertEqual(report["navigator_status"], "NEEDS_GROUNDED_FAILURE_ASSESSMENT")

    def test_audit_matches_cannot_diagnose_offense_or_be_readded(self):
        events, preview = self.tracking_preview()
        base = [*events, preview["event_preview"]]
        self.commit_fixture(base)
        context = context_for(self.state)
        assessment = context["failure_assessment"]
        for sample, mid in zip(assessment["match_samples"], ("Y1-JUN-SEINAN", "Y1-JUN-HANASAKA")):
            sample["match_id"] = mid
        self.assertIsNone(offense_pattern(assessment, self.state))
        report = self.run_entry(context=context, evidence_sources=self.sources(context))
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION")
        self.assertEqual(report["action_comparison"]["TRAIN"]["status"], "EVIDENCE_INSUFFICIENT")
        for original in (base[1], base[3]):
            with self.subTest(mid=original["match_id"]):
                readded = dict(original, seq=12, event_id="READDED", branch="ACCEPTED")
                with self.assertRaisesRegex(ObservationError, "audit-only"):
                    replay([*base, readded])

    def development_fixture(self):
        events, preview = self.tracking_preview()
        base = [*events, preview["event_preview"]]
        self.state = replay(base)
        tracking = self.state["observed_tracking"]
        players = ["入江ドコンジ", "今井タッツ", "芦田はじめ"]
        context = {
            "development_plan": attested(
                self.state, evidence_refs=["ROSTER-IMAGE", "MENU"],
                roster_origin_event_id=tracking["start_event_id"],
                roster_archive_sha256=tracking["roster_archive_sha256"],
                roster_image_evidence_refs=["ROSTER-IMAGE"],
                target_player=players[0], target_role="CORE_DEVELOP",
                player_observation={"player": players[0], "contact": 27, "slugging": 34,
                                    "evidence_ref": "ROSTER-IMAGE"},
                october_role="ADVANCE_RUNNERS_WITH_POWER", drill="ダンベル", cheer="OFF",
                priority_review={
                    "timing": "LOW_LEVEL_CORE_BEFORE_MASS_MATCH_LEVELING",
                    "other_drill": "DOES_NOT_SERVE_REVIEWED_OCTOBER_ROLE",
                    "cheer_tradeoff": "PRESERVE_FOR_NAMED_SPRINT_USE",
                    "role_and_drill_fit": "Synthetic: support extra-base production in the middle of the order.",
                    "why_before_alternatives": "Synthetic: develop the current core before match leveling.",
                    "cheer_reason": "Synthetic: reserve Cheer for the next reviewed pitching-core drill.",
                }),
            "training_readiness": attested(
                self.state, evidence_refs=["MENU"], menu_evidence_ref="MENU",
                available_drills=["ダンベル"], ready_players=players,
                menu_selection={"drill": "ダンベル", "players": players, "cheer": "OFF",
                                "available_now": True, "displayed_spend": {"sports": 7}},
                preferred_participant_groups={"ダンベル": group_selection(players, ["MENU"])},
                cheer_purposes={"ダンベル": {"OFF": "RESOURCE_PRESERVATION"}}),
        }
        sources = self.sources(context)
        # The synthetic reviewed bytes stand in for an archive image only inside this fixture.
        manifest_path = self.repo / ROSTER_RECORD
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["image_sha256_in_lexicographic_archive_order"][0] = sources["ROSTER-IMAGE"]["sha256"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.commit_fixture(base)
        return context, sources

    def test_october_core_training_certifies_without_diagnosis_or_fourth_session(self):
        context, sources = self.development_fixture()
        report = self.run_entry(context=context, evidence_sources=sources)
        self.assertEqual(report["status"], "CERTIFIED_TRAINING_DRAFT", report)
        self.assertEqual(report["safe_reply_check"]["status"], "PASS")
        self.assertEqual(report["action_comparison"]["TRAIN"]["status"], "EVIDENCE_READY")
        for action in ("MATCH", "ACTIVITY", "RECOVERY"):
            self.assertEqual(report["action_comparison"][action]["status"], "EVIDENCE_INSUFFICIENT")
        self.assertIn("入江ドコンジの長打力", report["safe_reply"])
        self.assertIn("ダンベル／応援OFF／消費予定：スポーツ7", report["safe_reply"])
        self.assertNotIn("4回目", report["safe_reply"])
        self.assertNotIn("DC-OFF-", report["safe_reply"])
        appended = self.run_entry(context=context, evidence_sources=sources,
                                  proposed_reply=report["safe_reply"] + "\n" + DENIED)
        self.assertIsNone(appended["safe_reply"])
        self.assertEqual(appended["safe_reply_check"]["error_codes"], ["REPLY_NOT_CANONICAL"])

    def test_october_plan_rejects_unsourced_priority_readiness_and_changed_cost(self):
        context, _ = self.development_fixture()
        for key, value, expected in (
                ("priority_review", {"timing": "CHEAPEST"}, "OCTOBER_PRIORITY_NOT_JUSTIFIED"),
                ("ready_players", [], "CURRENT_PLAYER_HP_OR_ELIGIBILITY_UNVERIFIED"),
                ("menu_selection", None, "CURRENT_SPECIAL_TRAINING_MENU_EVIDENCE_REQUIRED")):
            with self.subTest(key=key):
                modified = deepcopy(context)
                claim = "development_plan" if key == "priority_review" else "training_readiness"
                modified[claim][key] = value
                report = self.run_entry(context=modified, evidence_sources=self.sources(modified))
                self.assertEqual(report["status"], "CERTIFIED_NO_ACTION")
                self.assertIn(expected, report["blocking_reasons"])
        modified = deepcopy(context)
        modified["training_readiness"]["menu_selection"]["displayed_spend"] = {"sports": 1}
        report = self.run_entry(context=modified, evidence_sources=self.sources(modified))
        self.assertIn("CURRENT_MENU_COST_MISMATCH", report["blocking_reasons"])
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION")
        decision = navigator_step(ASK, state=self.state, contract=self.contract, root=self.repo,
                                  boot_verified=True, context=context)
        draft = dict(decision["action_draft"], spend={"sports": 1})
        self.assertIn("CATALOG_TRAINING_COST_MISMATCH", validate_recommendation(
            draft, self.state, self.contract, context=context, root=self.repo))

    def test_reviewed_but_unsupported_activity_is_not_treated_as_missing_evidence(self):
        context, _ = self.development_fixture()
        context["activity"] = attested(
            self.state, evidence_refs=["ACTIVITY"], name="Synthetic", available_now=True,
            cost_verified=True, spend={"study": 2},
            october_use="RESOURCE_CONVERSION_FOR_NAMED_SPRINT_ACTION", unlocks="Synthetic drill")
        report = self.run_entry(context=context, evidence_sources=self.sources(context))
        self.assertEqual(report["action_comparison"]["ACTIVITY"]["status"], "RENDERING_UNSUPPORTED")
        self.assertEqual(report["status"], "CERTIFIED_NO_ACTION")
        self.assertIn("COMPETING_ACTION_PRIORITY_NOT_RESOLVED", report["blocking_reasons"])

    def test_tracking_counts_only_new_actions_and_expires_on_unknown_reload(self):
        events, preview = self.tracking_preview()
        marker = preview["event_preview"]
        base = [*events, marker]
        trial = {
            "seq": marker["seq"] + 1, "event_id": "TRACK-TRIAL", "kind": "TRAINING",
            "source": {"kind": "USER_REPORT", "locator": "test fixture"},
            "period": marker["period"], "branch": "ACCEPTED", "drill": "素振り",
            "participants": ["入江", "今井", "岡治"],
        }
        state = replay([*base, trial])
        info = training_count_status(state, "今井", "素振り")
        self.assertEqual(info["recorded_lower_bound"], 1)
        self.assertIsNone(info["exact_committed_count"])
        self.assertFalse(state["resources"]["fresh"])
        checkpoint = {k: trial[k] for k in ("seq", "event_id", "period", "source")}
        checkpoint.update(kind="SAVE_CHECKPOINT", event_id="TRACK-SAVE")
        rollback = {k: trial[k] for k in ("period", "source")}
        rollback.update(seq=trial["seq"] + 2, event_id="TRACK-LOAD", kind="ROLLBACK")
        post_save_trial = dict(trial, seq=trial["seq"] + 1)
        restored = replay([*base, checkpoint, post_save_trial,
                           dict(rollback, to_checkpoint_id="TRACK-SAVE")])
        self.assertEqual(restored["timeline_status"], OBSERVED_TRACKING)
        self.assertEqual(restored["training_counts_by_player_drill"], {})
        state = replay([*base, trial, dict(rollback, seq=trial["seq"] + 1)])
        self.assertEqual(state["timeline_status"], "UNKNOWN_AFTER_ROLLBACK")
        self.assertNotIn("observed_tracking", state)
        self.assertIsNone(training_count_status(state, "今井", "素振り")["recorded_lower_bound"])
        with self.assertRaisesRegex(ObservationError, "immediately follow"):
            replay([*events, dict(trial, seq=marker["seq"]), dict(marker, seq=trial["seq"])])
        with self.assertRaisesRegex(ObservationError, "predates"):
            replay([*base, dict(trial, period={"year": 1, "month": 5})])

    def test_replay_mismatch_stops_before_comparison(self):
        self.commit_fixture(fixture_events())
        altered = deepcopy(self.state)
        altered["resources"]["values"]["sports"] += 1
        (self.repo / "CURRENT_LIVE_STATE.json").write_text(json.dumps(altered), encoding="utf-8")
        out = self.run_entry()
        self.assertIsNone(out["safe_reply"])
        self.assertNotIn("candidates_compared", out)
        self.assertEqual(out["blocking_reasons"], ["CURRENT_STATE_REPLAY_MISMATCH"])

    def test_cli_exit_and_output_are_safe_for_arbitrary_prose(self):
        self.commit_fixture()
        path = self.root / "draft.txt"
        path.write_text(DENIED + "\n", encoding="utf-8")
        run = subprocess.run(
            [sys.executable, str(ROOT / "next_action.py"), ASK, "--root", str(self.repo),
             "--expected-main-sha", self.sha, "--expected-event-seq",
             str(self.state["last_event_seq"]), "--reply", str(path)],
            capture_output=True, encoding="utf-8", check=False)
        self.assertEqual(run.returncode, 2, run.stderr)
        out = json.loads(run.stdout)
        self.assertIsNone(out["safe_reply"])
        self.assertEqual(out["safe_reply_check"]["status"], "REJECTED")
