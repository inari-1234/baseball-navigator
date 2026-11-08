#!/usr/bin/env python3
"""P7-D: fail-closed verification of bounded user-facing gameplay replies.

Only a deterministic, source-pinned reply template can be certified here.
This does NOT inspect or intercept unrestricted ChatGPT answers, and does not
accept or upload private text through the public GitHub request bridge.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class ReplyGateError(ValueError):
    pass


def canonical_state_sha256(state: dict[str, Any]) -> str:
    """Hash structured state independent of source JSON formatting."""
    return sha256(json.dumps(state, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode("utf-8")).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReplyGateError(code)


def _no_action_fields(bridge: dict[str, Any]) -> None:
    _require(bridge.get("candidate") is None
             and bridge.get("provisional_target") is None
             and bridge.get("selected_candidate") is None,
             "BLOCKED_CANDIDATE_LEAK")


def _count_reply(bridge: dict[str, Any], state: dict[str, Any],
                 line: str) -> str:
    from text_fast import _read_only_projection
    observation = bridge.get("observation")
    _require(bridge.get("status") == "READ_ONLY_READY"
             and bridge.get("context_source") == "NO_USER_CONTEXT_PUBLIC_REQUEST"
             and isinstance(observation, dict)
             and observation == _read_only_projection(
                 "現在の本線の特訓回数の記録を確認して", state),
             "COUNT_OBSERVATION_MISMATCH")
    _no_action_fields(bridge)
    _require(observation.get("fourth_checkpoint_verified") is False
             and observation.get("missing_player_drill_count_means_zero") is False,
             "COUNT_CERTAINTY_BYPASS")
    if state["timeline_status"] == "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN":
        _require(observation.get("exact_total_status") == "UNKNOWN"
                 and observation.get("event_ledger_counts_lower_bound") is None
                 and observation.get("exact_current_counts_by_player_drill") == {},
                 "EXACT_TRAINING_COUNT_NOT_UNVERIFIED")
        return (
            "現在のセーブについて、選手別の特訓総回数は未確定です。"
            "記録に回数がないことは0回の証拠ではなく、3回済みとも次が4回目とも判断できません。\n"
            + line + "\n"
            + "Fallback: 現行セーブと選手・練習別の確定回数が確認されるまで、4回目とは認定しません。"
        )
    _require(state["timeline_status"] == "TRUSTED",
             "UNSUPPORTED_TIMELINE_FOR_TEMPLATE")
    exact = observation.get("exact_current_counts_by_player_drill", {})
    refs = observation.get("exact_count_source_event_ids", {})
    logged = observation.get("event_ledger_counts_lower_bound", {})
    _require(isinstance(exact, dict) and isinstance(refs, dict)
             and isinstance(logged, dict) and set(exact) == set(refs),
             "EXACT_COUNT_EVIDENCE_REQUIRED")
    lines = ["現在のセーブは確認済みです。特訓回数は以下の範囲だけ確認できます。"]
    for key in sorted(exact):
        player, drill = key.split("|")
        lines.append(f"{player}・{drill}：{exact[key]}回（現セーブで確定、根拠 {refs[key]}）")
    for key in sorted(set(logged) - set(exact)):
        player, drill = key.split("|")
        lines.append(f"{player}・{drill}：記録上少なくとも{logged[key]}回（総回数は未確定）")
    if not exact and not logged:
        lines.append("現在のセーブで確定できる選手別の特訓回数はありません。")
    lines.extend([
        "記載のない選手・練習は不明です。3回という数字だけで4回目のスキル習得を保証するものではありません。",
        line,
        "Fallback: 未確認の選手・練習を4回目と断定せず、現セーブの明示的な回数証拠を確認します。",
    ])
    return "\n".join(lines)


def _verified_draft_reply(bridge: dict[str, Any],
                          state: dict[str, Any], line: str,
                          *, contract: dict[str, Any] | None,
                          root: str | Path) -> str:
    from live_state_engine import validate_recommendation, training_count_status
    from knowledge_engine import validate_skill_recommendation
    from navigator_step import _load_catalog
    _require(bridge.get("context_source") == "VERIFIED_CURRENT_RUN_CONTEXT"
             and bridge.get("status") == "VALIDATED_DRAFT_REVIEW"
             and bridge.get("requires_manual_acceptance") is True
             and bridge.get("current_failure_assessed") is True
             and isinstance(bridge.get("failure_evidence_refs"), list)
             and bool(bridge["failure_evidence_refs"]),
             "CURRENT_RUN_CONTEXT_REQUIRED")
    _require(isinstance(contract, dict),
             "DECISION_CONTRACT_REQUIRED")
    candidate = bridge.get("candidate")
    draft = bridge.get("verified_action_draft")
    _require(isinstance(candidate, dict) and isinstance(draft, dict)
             and candidate.get("ready") is True
             and candidate.get("blocked_by") == []
             and isinstance(candidate.get("readiness_evidence_refs"), list)
             and bool(candidate["readiness_evidence_refs"])
             and candidate.get("id") == bridge.get("selected_candidate")
             and candidate.get("id") == bridge.get("primary_next_step"),
             "CURRENT_VERIFIED_CANDIDATE_REQUIRED")
    participants = candidate.get("participants")
    cost = candidate.get("cost")
    cheer = candidate.get("cheer")
    drill = candidate.get("drill")
    _require(isinstance(participants, list)
             and len(participants) == 3
             and len(set(participants)) == 3
             and all(isinstance(p, str) and p.strip() for p in participants)
             and isinstance(drill, str) and bool(drill)
             and cheer in {"ON", "OFF"}
             and isinstance(cost, dict) and set(cost).issubset({"sports", "cheer"})
             and type(cost.get("sports")) is int and cost["sports"] > 0
             and (cheer == "OFF" and "cheer" not in cost
                  or cheer == "ON" and type(cost.get("cheer")) is int
                  and cost["cheer"] > 0),
             "TRAINING_DRAFT_FIELDS_INVALID")
    _require(candidate.get("cost_fully_known") is True,
             "EXACT_TRAINING_COST_NOT_VERIFIED")
    catalog = _load_catalog(root)
    spec = next((d for d in catalog["drills"]
                 if d["id"] + "_" + cheer == candidate.get("id")
                 and d["drill"] == drill), None)
    _require(spec is not None and cost["sports"] == spec["sports_cost"],
             "CATALOG_TRAINING_COST_MISMATCH")
    if cheer == "ON":
        measured = spec.get("cheer_on_cost")
        _require((type(measured) is int and cost["cheer"] == measured)
                 or (measured is None
                     and candidate.get("cost_source") ==
                     "CURRENT_SOURCE_ATTESTED_PLUS_HISTORICAL_SPORTS"),
                 "CHEER_COST_SOURCE_MISMATCH")
    _require(draft.get("action_type") == "TRAIN"
             and draft.get("participants") == participants
             and draft.get("drill") == drill
             and draft.get("cheer") == cheer
             and draft.get("spend") == cost
             and draft.get("rule_ids") == bridge.get("rule_ids")
             and draft.get("based_on_event_seq") == state["last_event_seq"],
             "DRAFT_FIELDS_NOT_BOUND_TO_VALIDATOR")
    _require(validate_recommendation(draft, state, contract) == [],
             "TRAINING_RECOMMENDATION_NOT_VALIDATED")
    if draft.get("skill_goal") is not None:
        _require(validate_skill_recommendation(
            draft, state, contract, root=root) == [],
            "SKILL_RECOMMENDATION_NOT_VALIDATED")
    checkpoint = "4回目の根拠は未確認（習得保証なし）"
    if draft.get("claimed_fourth_checkpoint") is True:
        player = draft.get("checkpoint_player")
        _require(isinstance(player, str) and player in participants,
                 "FOURTH_CHECKPOINT_PLAYER_REQUIRED")
        info = training_count_status(state, player, drill)
        _require(info["count_certainty"] == "EXACT_CURRENT_SAVE"
                 and info["exact_committed_count"] == 3,
                 "EXACT_FOURTH_CHECKPOINT_NOT_VERIFIED")
        checkpoint = f"{player}の次回が記録上4回目の候補（習得保証なし、根拠 {info['certification_event_id']}）"
    plan = candidate.get("accept_reload_plan")
    accept = {
        "TARGET_OR_HIGH_VALUE_SKILL_ACQUIRED": "目標または高価値のスキルを確認した場合",
        "ABILITY_GAIN_MEETS_DEVELOPMENT_GOAL": "能力上昇が育成目標に合った場合",
    }
    reload = {
        "OPTIONAL_TARGETED_FOURTH_REROLL_WHEN_SAVE_AND_BUDGET_VERIFIED":
            "セーブと時間負担を確認した場合に限り任意で再試行を検討",
        "DO_NOT_FARM_FIRST_THREE_BASED_ON_HISTORICAL_NEGATIVES":
            "過去の陰性結果だけを根拠に1〜3回目の再試行を繰り返さない",
        "NO_SKILL_REROLL_TARGET": "スキル目的のやり直しは設定しない",
    }
    _require(isinstance(plan, dict)
             and plan.get("not_a_guaranteed_reward") is True
             and plan.get("accept_if") in accept
             and plan.get("reload_if") in reload
             and candidate.get("skills_not_guaranteed") is True,
             "ACCEPT_RELOAD_PROVENANCE_REQUIRED")
    expense = f"スポーツ{cost['sports']}" + (
        f"、応援{cost['cheer']}" if cheer == "ON" else "")
    return "\n".join([
        "現在のセーブで条件を確認した特訓の下書きです。ゲーム操作は実行していません。",
        "参加者：" + "・".join(participants),
        f"特訓：{drill}／応援{cheer}／消費予定：{expense}",
        "回数・スキル：" + checkpoint,
        "採用基準：" + accept[plan["accept_if"]],
        "再試行基準：" + reload[plan["reload_if"]],
        "手動承認前の候補です。実行直前に資源・参加可能状態・セーブの同一性を再確認してください。",
        line,
        "Fallback: 実行前の状態変化、費用の不一致、候補選手の準備不足があれば実行せず再検証します。",
    ])


def render_guarded_reply(bridge: dict[str, Any],
                         state: dict[str, Any],
                         *, contract: dict[str, Any] | None = None,
                         root: str | Path = ".") -> str:
    """Certify only source-backed, explicitly supported answer cases."""
    _require(isinstance(bridge, dict) and isinstance(state, dict),
             "SOURCE_MISSING")
    _require(bridge.get("source_is_current_only_at_this_commit") is True,
             "SOURCE_REVISION_NOT_ATTESTED")
    _require(isinstance(bridge.get("source_commit_sha"), str)
             and len(bridge["source_commit_sha"]) == 40
             and all(c in "0123456789abcdef" for c in bridge["source_commit_sha"]),
             "SOURCE_SHA_INVALID")
    _require(type(bridge.get("state_event_seq")) is int
             and bridge["state_event_seq"] == state.get("last_event_seq"),
             "STALE_EVENT_REVISION")
    _require(bridge.get("timeline_status") == state.get("timeline_status"),
             "TIMELINE_MISMATCH")
    _require(bridge.get("state_structured_sha256") ==
             canonical_state_sha256(state), "STATE_CONTENT_MISMATCH")
    _require(bridge.get("action_authorized") is False
             and bridge.get("side_effects") is False,
             "EXECUTION_BOUNDARY_VIOLATED")
    rules = bridge.get("rule_ids")
    _require(isinstance(rules, list) and len(rules) > 0
             and all(isinstance(x, str) and x.startswith("DC-") for x in rules),
             "RULE_IDS_REQUIRED")
    line = "Rule: " + "、".join(rules)
    intent = bridge.get("intent")
    if intent == "TRAINING_COUNTS":
        return _count_reply(bridge, state, line)
    if intent != "SKILL":
        raise ReplyGateError("UNSUPPORTED_INTENT_FOR_CERTIFIED_REPLY")
    _require("SKILL-4TH-PATTERN" in bridge.get("knowledge_refs", []),
             "SKILL_EVIDENCE_MISSING")
    if state["timeline_status"] == "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN":
        _no_action_fields(bridge)
        _require(bridge.get("context_source") == "NO_USER_CONTEXT_PUBLIC_REQUEST"
                 and bridge.get("status") == "BLOCKED_UNVERIFIED_TIMELINE"
                 and "ROLLBACK_SAVEPOINT_UNKNOWN_OR_UNTRUSTED_TIMELINE"
                 in bridge.get("blocking_reasons", []),
                 "SKILL_GATE_NOT_BLOCKED")
        return (
            "現行セーブの復元地点が未確定です。選手別の特訓総回数と、次が4回目かどうかは確認できません。"
            "スキル狙いの特訓は現時点では実行せず、現在のセーブの確認を優先してください。\n"
            + line + "\n"
            + "Fallback: 現行セーブと特訓履歴の証拠が揃わなければ、資源を消費する特訓を保留します。"
        )
    _require(state["timeline_status"] == "TRUSTED",
             "UNSUPPORTED_TIMELINE_FOR_TEMPLATE")
    if bridge.get("status") == "VALIDATED_DRAFT_REVIEW":
        return _verified_draft_reply(bridge, state, line,
                                     contract=contract, root=root)
    _no_action_fields(bridge)
    _require(bridge.get("context_source") == "NO_USER_CONTEXT_PUBLIC_REQUEST"
             and bridge.get("status") in {
                 "NEEDS_GROUNDED_FAILURE_ASSESSMENT", "BLOCKED_CANDIDATE",
                 "NEEDS_CANDIDATE"
             }, "UNSUPPORTED_TRUSTED_SKILL_STATE")
    return (
        "現在のセーブは確認済みですが、スキル狙いの特訓条件はまだ検証済みではありません。"
        "参加者・応援設定・費用を含む実行計画は提示しません。\n"
        + line + "\n"
        + "Fallback: 現在の選手準備状況、直近の試合内容、費用とスキル証拠を確認するまで実行を保留します。"
    )


def make_local_verified_draft_packet(
        navigator_result: dict[str, Any], state: dict[str, Any],
        *, source_commit_sha: str, contract: dict[str, Any],
        root: str | Path = ".") -> dict[str, Any]:
    """Local-only adapter; NEVER use this to bypass public P4 input allowlists.

    The input MUST be a sourced, already validated navigator_step result.
    Context and raw observations stay local, not on the public request branch.
    """
    _require(isinstance(navigator_result, dict)
             and navigator_result.get("status") == "VALIDATED_DRAFT_REVIEW"
             and navigator_result.get("action_authorized") is False
             and navigator_result.get("side_effects") is False
             and state.get("timeline_status") == "TRUSTED"
             and navigator_result.get("source_event_seq") ==
             state.get("last_event_seq"), "LOCAL_DRAFT_NOT_VALIDATED")
    cid = navigator_result.get("selected_candidate")
    matches = [item for item in navigator_result.get("candidates", [])
               if isinstance(item, dict) and item.get("id") == cid]
    _require(len(matches) == 1 and matches[0].get("ready") is True
             and matches[0].get("blocking_reasons") == [],
             "LOCAL_DRAFT_NOT_READY")
    source = matches[0]
    _require(source.get("action_draft") == navigator_result.get("action_draft"),
             "LOCAL_DRAFT_MISMATCH")
    draft = navigator_result["action_draft"]
    packet = {
        "intent": "SKILL",
        "status": "VALIDATED_DRAFT_REVIEW",
        "context_source": "VERIFIED_CURRENT_RUN_CONTEXT",
        "current_failure_assessed": navigator_result.get("failure_assessment_current"),
        "failure_evidence_refs": navigator_result.get("failure_evidence_refs"),
        "source_is_current_only_at_this_commit": True,
        "source_commit_sha": source_commit_sha,
        "state_event_seq": state["last_event_seq"],
        "timeline_status": state["timeline_status"],
        "state_structured_sha256": canonical_state_sha256(state),
        "action_authorized": False, "side_effects": False,
        "requires_manual_acceptance": True,
        "rule_ids": navigator_result.get("rule_ids"),
        "knowledge_refs": navigator_result.get("knowledge_refs"),
        "primary_next_step": cid,
        "selected_candidate": cid,
        "provisional_target": None,
        "verified_action_draft": draft,
        "candidate": {
            "id": source["id"],
            "ready": source["ready"],
            "blocked_by": source["blocking_reasons"],
            "drill": source["drill"], "cheer": source["cheer"],
            "participants": source["participants"], "cost": source["cost"],
            "accept_reload_plan": source["accept_reload_plan"],
            "skills_not_guaranteed": source["target_skill_at_this_drill_not_guaranteed"],
            "cost_fully_known": source["cost_fully_known"],
            "cost_source": source["cost_source"],
            "readiness_evidence_refs": source.get("training_readiness_evidence_refs", []),
        },
    }
    reply = render_guarded_reply(packet, state, contract=contract, root=root)
    verdict = check_reply(
        reply, bridge=packet, state=state,
        expected_main_sha=source_commit_sha,
        expected_event_seq=state["last_event_seq"],
        contract=contract, root=root)
    _require(verdict["status"] == "PASS", "LOCAL_DRAFT_REPLY_NOT_CERTIFIED")
    packet["safe_reply"] = reply
    packet["safe_reply_check"] = verdict
    return packet


def check_reply(text: str, *, bridge: dict[str, Any],
                state: dict[str, Any],
                expected_main_sha: str, expected_event_seq: int,
                contract: dict[str, Any] | None = None,
                root: str | Path = ".") -> dict[str, Any]:
    """Certify ONLY an exact rendered reply, never arbitrary prose via regex.

    Unrecognized text is REJECTED, not marked safe merely because it lacks a
    dangerous keyword. This avoids the illusion of comprehensive Japanese NLU.
    """
    error = None
    try:
        _require(type(expected_event_seq) is int
                 and type(bridge.get("state_event_seq")) is int
                 and bridge["state_event_seq"] == expected_event_seq,
                 "STALE_EVENT_REVISION")
        _require(bridge.get("source_commit_sha") == expected_main_sha,
                 "STALE_SOURCE_COMMIT")
        expected = render_guarded_reply(
            bridge, state, contract=contract, root=root)
        _require(isinstance(text, str), "REPLY_MUST_BE_TEXT")
        _require(text == expected, "REPLY_NOT_CANONICAL")
    except (ReplyGateError, TypeError, AttributeError, KeyError) as exc:
        error = (str(exc) if isinstance(exc, ReplyGateError)
                 else "MALFORMED_REPLY_INPUT")
    return {
        "status": "PASS" if error is None else "REJECTED",
        "error_codes": [] if error is None else [error],
        "enforcement_scope": "EXACT_RENDERED_REPLY_ONLY",
        "chat_runtime_hook_guaranteed": False,
        "source_commit_sha": expected_main_sha,
        "state_event_seq": expected_event_seq,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local-only check of a private reply draft against source-pinned bridge")
    parser.add_argument("--bridge-result", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=Path("DECISION_CONTRACT.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--reply", type=Path)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--expected-event-seq", type=int, required=True)
    parser.add_argument("--render", action="store_true",
                        help="Print the canonical guarded reply instead of checking one")
    args = parser.parse_args()
    if args.render == (args.reply is not None):
        parser.error("choose exactly one of --render or --reply")
    try:
        bridge = json.loads(args.bridge_result.read_text(encoding="utf-8"))
        state = json.loads(args.state.read_text(encoding="utf-8"))
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        if args.render:
            result = render_guarded_reply(bridge, state, contract=contract, root=args.root)
            gate = check_reply(result, bridge=bridge, state=state,
                               expected_main_sha=args.expected_main_sha,
                               expected_event_seq=args.expected_event_seq,
                               contract=contract, root=args.root)
            if gate["status"] != "PASS":
                parser.exit(2, "REPLY_GUARD_FAIL:" +
                            ",".join(gate["error_codes"]) + "\n")
            print(result)
            return
        draft = args.reply.read_text(encoding="utf-8")
        if draft.endswith("\n"):
            draft = draft[:-1]
        verdict = check_reply(
            draft, bridge=bridge, state=state,
            expected_main_sha=args.expected_main_sha,
            expected_event_seq=args.expected_event_seq,
            contract=contract, root=args.root)
        print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
        if verdict["status"] != "PASS":
            parser.exit(2)
    except (OSError, ValueError, ReplyGateError) as exc:
        parser.exit(2, "REPLY_GUARD_FAIL:" + str(exc) + "\n")


if __name__ == "__main__":
    main()
