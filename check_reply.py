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

from live_state_engine import OBSERVED_TRACKING, has_current_lineage


class ReplyGateError(ValueError):
    pass


def canonical_state_sha256(state: dict[str, Any]) -> str:
    """Hash structured state independent of source JSON formatting."""
    return sha256(json.dumps(state, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode("utf-8")).hexdigest()


def _accepted_lineage_evidence(events, ref, claim, latest_seq, period):
    """Confirm an earlier source survives in this branch without invalidation.

    SAVE_CHECKPOINT and scheduling are metadata-only for this purpose.
    Failed/rewound chronology or material mutations expire source eligibility;
    failure-assessment context tolerates newer SCREEN/HP observations whereas
    player-readiness evidence does not.
    """
    from live_state_engine import (apply_corrections, resolve_active_lineage,
                                   ObservationError)
    _require(len(events) == latest_seq
             and [e.get("seq") for e in events] ==
             list(range(1, latest_seq + 1))
             and len({e.get("event_id") for e in events}) == len(events),
             "LIVE_EVENT_LEDGER_REVISION_MISMATCH")
    try:
        corrected = apply_corrections(events)
        active, _, _, _, unknown = resolve_active_lineage(corrected)
    except (ObservationError, KeyError, TypeError, ValueError) as exc:
        raise ReplyGateError("LIVE_EVENT_LEDGER_LINEAGE_INVALID") from exc
    _require(not unknown, "LIVE_EVENT_UNKNOWN_ROLLBACK_LINEAGE")
    raw_matches = [e for e in events if e.get("event_id") == ref]
    active_matches = [e for e in active if e.get("event_id") == ref]
    _require(len(raw_matches) == 1 and len(active_matches) == 1,
             "LIVE_EVENT_NOT_IN_ACTIVE_LINEAGE")
    source, active_source = raw_matches[0], active_matches[0]
    _require(source == active_source, "LIVE_EVENT_CORRECTED_SOURCE_NEEDS_REVIEW")
    allowed = {"failure_assessment": {"MATCH_ATTEMPT", "SCREEN", "HP_OBSERVATION"},
               "training_readiness": {"SCREEN", "HP_OBSERVATION"}}
    _require(source.get("kind") in allowed[claim]
             and source.get("branch") == "ACCEPTED"
             and type(source.get("seq")) is int
             and 1 <= source["seq"] <= latest_seq
             and source.get("period") == {
                 "year": int(period.split("-")[0][1:]),
                 "month": int(period.split("-")[1])},
             "LIVE_EVENT_NOT_CURRENT_ACCEPTED_SOURCE")
    # A correction after the source requires a fresh source review, even if
    # it targets another event. It is not silently treated as harmless.
    _require(not any(e["kind"] == "CORRECTION" and
                     e["seq"] > source["seq"] for e in events),
             "LIVE_EVENT_LATER_CORRECTION_REQUIRES_REVIEW")
    innocuous = {
        "failure_assessment": {"SAVE_CHECKPOINT", "MATCH_SCHEDULE",
                               "SCREEN", "HP_OBSERVATION",
                               "TRAINING_COUNT_BASELINE"},
        "training_readiness": {"SAVE_CHECKPOINT", "MATCH_SCHEDULE",
                               "TRAINING_COUNT_BASELINE"},
    }[claim]
    _require(all(
        e.get("kind") in innocuous
        and (e.get("kind") not in {"SCREEN","HP_OBSERVATION",
                                   "TRAINING_COUNT_BASELINE"}
             or e.get("branch") == "ACCEPTED")
        for e in active if e.get("seq", 0) > source["seq"]),
        "LIVE_EVENT_EVIDENCE_EXPIRED_BY_MUTATION")
    return source


def _verified_evidence_receipts(context, evidence_sources, state, root, *,
                                claims=("failure_assessment", "training_readiness")):
    """Private local evidence: resolve every ID to bytes or a current ledger event.

    Hashes certify the reviewed bytes and context version; not the semantic
    accuracy of an image/user recollection. Human review is still necessary.
    """
    _require(isinstance(context, dict) and isinstance(evidence_sources, dict),
             "LOCAL_EVIDENCE_INDEX_REQUIRED")
    observation_only = claims == ("roster_chronology",)
    _require(observation_only or has_current_lineage(state),
             "EVIDENCE_BRANCH_UNTRUSTED")
    seq, period = state.get("last_event_seq"), state.get("period_floor")
    receipts, events = {}, None
    for claim in claims:
        block = context.get(claim)
        _require(isinstance(block, dict)
                 and block.get("verified_for_current_state") is True
                 and type(block.get("source_event_seq")) is int
                 and block["source_event_seq"] == seq
                 and block.get("period") == period
                 and block.get("branch") == "ACCEPTED",
                 "CURRENT_CONTEXT_ATTESTATION_REQUIRED")
        refs = block.get("evidence_refs")
        _require(isinstance(refs, list) and bool(refs)
                 and all(isinstance(v, str) and v.strip() for v in refs)
                 and len(set(refs)) == len(refs),
                 "CURRENT_CONTEXT_EVIDENCE_REQUIRED")
        claim_sha = canonical_state_sha256(block)
        for ref in refs:
            record = evidence_sources.get(ref)
            _require(isinstance(record, dict)
                     and record.get("reviewed_for_current_state") is True
                     and record.get("source_event_seq") == seq
                     and record.get("period") == period
                     and record.get("branch") == "ACCEPTED"
                     and isinstance(record.get("reviewed_claim_sha256"), dict)
                     and record["reviewed_claim_sha256"].get(claim) == claim_sha,
                     "EVIDENCE_REF_UNRESOLVED_OR_STALE")
            kind = record.get("kind")
            _require(not observation_only or kind == "LOCAL_FILE",
                     "DIRECT_ROSTER_ATTESTATION_SOURCE_REQUIRED")
            if kind == "LOCAL_FILE":
                local = record.get("path")
                _require(isinstance(local, str) and bool(local.strip()),
                         "LOCAL_EVIDENCE_FILE_REQUIRED")
                try:
                    with Path(local).open("rb") as f:
                        digest = sha256()
                        for chunk in iter(lambda: f.read(1048576), b""):
                            digest.update(chunk)
                    actual = digest.hexdigest()
                except OSError as exc:
                    raise ReplyGateError("LOCAL_EVIDENCE_FILE_NOT_ACCESSIBLE") from exc
            elif kind == "LIVE_EVENT":
                _require(record.get("event_id") == ref,
                         "LEDGER_EVIDENCE_ID_MISMATCH")
                if events is None:
                    try:
                        raw = (Path(root) / "LIVE_EVENTS.jsonl").read_text(encoding="utf-8")
                        events = [json.loads(v) for v in raw.splitlines() if v.strip()]
                    except (OSError, ValueError) as exc:
                        raise ReplyGateError("LIVE_EVENT_LEDGER_UNAVAILABLE") from exc
                source = _accepted_lineage_evidence(
                    events, ref, claim, seq, period)
                if (claim == "failure_assessment" and source["kind"] == "MATCH_ATTEMPT"
                        and "match_samples" in block):
                    samples = [sample for sample in block["match_samples"]
                               if sample.get("evidence_ref") == ref]
                    _require(len(samples) == 1
                             and source.get("attempt") == 1
                             and samples[0].get("match_id") == source.get("match_id")
                             and samples[0].get("runs") == source.get("our_runs"),
                             "MATCH_SAMPLE_NOT_BOUND_TO_LIVE_EVENT")
                actual = canonical_state_sha256(source)
            else:
                raise ReplyGateError("EVIDENCE_SOURCE_TYPE_UNSUPPORTED")
            expected = record.get("sha256")
            _require(isinstance(expected, str) and len(expected) == 64
                     and all(v in "0123456789abcdef" for v in expected)
                     and actual == expected,
                     "EVIDENCE_CONTENT_HASH_MISMATCH")
            receipts[claim + ":" + ref] = {
                "source_kind": kind, "content_sha256": actual,
                "reviewed_claim_sha256": claim_sha,
                "source_event_seq": seq,
                "source_record_seq": (source["seq"] if kind == "LIVE_EVENT" else None),
                "period": period}
    return receipts


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
    _require(has_current_lineage(state),
             "UNSUPPORTED_TIMELINE_FOR_TEMPLATE")
    exact = observation.get("exact_current_counts_by_player_drill", {})
    refs = observation.get("exact_count_source_event_ids", {})
    logged = observation.get("event_ledger_counts_lower_bound", {})
    _require(isinstance(exact, dict) and isinstance(refs, dict)
             and isinstance(logged, dict) and set(exact) == set(refs),
             "EXACT_COUNT_EVIDENCE_REQUIRED")
    lines = [
        "観測起点以前の履歴は不明です。特訓回数は以下の範囲だけ確認できます。"
        if state["timeline_status"] == OBSERVED_TRACKING else
        "現在のセーブは確認済みです。特訓回数は以下の範囲だけ確認できます。"
    ]
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


# These messages reproduce the navigator's three actionable goal routes without
# storing the caller's private text in the reply packet.
DECISION_MESSAGES = {
    "SKILL": "スキル獲得に向けて何をすべき？",
    "OFFENSE": "得点のために何をすべき？",
    "GENERAL": "次は何をすべき？",
}


def _training_projection(result):
    _require(result.get("status") == "VALIDATED_DRAFT_REVIEW"
             and result.get("action_authorized") is False
             and result.get("side_effects") is False
             and result.get("requires_manual_acceptance") is True
             and result.get("failure_assessment_current") is True,
             "LOCAL_DRAFT_NOT_VALIDATED")
    draft = result.get("action_draft")
    _require(isinstance(draft, dict) and draft.get("action_type") == "TRAIN",
             "UNSUPPORTED_ACTION_FOR_CERTIFIED_REPLY")
    cid = result.get("selected_candidate")
    matches = [c for c in result["candidates"] if c.get("id") == cid]
    _require(len(matches) == 1 and matches[0].get("action_draft") == draft
             and matches[0].get("ready") is True
             and matches[0].get("blocking_reasons") == [],
             "LOCAL_DRAFT_NOT_READY")
    source = matches[0]
    return {
        "intent": "SKILL" if result["decision_goal"] == "SKILL" else "GENERAL",
        "decision_goal": result["decision_goal"],
        "status": result["status"],
        "current_failure_assessed": result["failure_assessment_current"],
        "failure_evidence_refs": result["failure_evidence_refs"],
        "requires_manual_acceptance": result["requires_manual_acceptance"],
        "rule_ids": result["rule_ids"],
        "knowledge_refs": result["knowledge_refs"],
        "primary_next_step": result["primary_next_step"],
        "selected_candidate": cid,
        "provisional_target": None,
        "fallback": result["fallback"],
        "verified_action_draft": draft,
        "candidate": {
            key: source[key] for key in (
                "id", "ready", "blocking_reasons", "drill", "cheer", "participants",
                "cost", "cost_fully_known", "cost_source", "accept_reload_plan",
                "target_skill", "target_skill_at_this_drill_not_guaranteed",
                "training_readiness_evidence_refs", "participant_selection_evidence_refs",
            )
        },
    }


def _verified_draft_reply(bridge: dict[str, Any], state: dict[str, Any], line: str,
                          *, contract: dict[str, Any] | None, root: str | Path,
                          context: dict[str, Any] | None,
                          evidence_sources: dict[str, Any] | None) -> str:
    from live_state_engine import training_count_status
    from navigator_step import navigator_step
    _require(isinstance(contract, dict), "DECISION_CONTRACT_REQUIRED")
    receipts = _verified_evidence_receipts(context, evidence_sources, state, root)
    _require(bridge.get("evidence_receipts") == receipts
             and bridge.get("evidence_receipts_sha256") == canonical_state_sha256(receipts)
             and bridge.get("reviewed_context_sha256") == canonical_state_sha256(context),
             "EVIDENCE_RECEIPT_MISMATCH")
    goal = bridge.get("decision_goal")
    _require(isinstance(goal, str) and goal in DECISION_MESSAGES,
             "LOCAL_DRAFT_GOAL_UNSUPPORTED")
    fresh = navigator_step(
        DECISION_MESSAGES[goal], state=state, contract=contract,
        boot_verified=True, expected_event_seq=state["last_event_seq"],
        context=context, root=root)
    expected = _training_projection(fresh)
    _require(all(bridge.get(key) == value for key, value in expected.items()),
             "NAVIGATOR_REVALIDATION_MISMATCH")

    candidate, draft = expected["candidate"], expected["verified_action_draft"]
    drill, cheer, cost = candidate["drill"], candidate["cheer"], candidate["cost"]
    checkpoint = "4回目の根拠は未確認（習得保証なし）"
    if draft["claimed_fourth_checkpoint"]:
        player = draft["checkpoint_player"]
        info = training_count_status(state, player, drill)
        checkpoint = (f"{player}は現セーブで確定3回のため、次の特訓が4回目の候補"
                      f"（習得保証なし、根拠 {info['certification_event_id']}）")
    target = candidate["target_skill"]
    if target:
        checkpoint = f"目標 {target}／" + checkpoint
    plan = candidate["accept_reload_plan"]
    accept = {
        "TARGET_OR_HIGH_VALUE_SKILL_ACQUIRED": "目標または高価値のスキルを確認した場合",
        "ABILITY_GAIN_MEETS_DEVELOPMENT_GOAL": "能力上昇が育成目標に合った場合",
    }
    reload = {
        "OPTIONAL_TARGETED_FOURTH_REROLL_WHEN_SAVE_AND_BUDGET_VERIFIED":
            "目標・高価値スキルを得られず、直前のセーブと時間負担を確認できた場合に限り、再試行を検討",
        "NO_VERIFIED_SKILL_REROLL_TARGET": "スキル目的の再試行は保留",
    }
    fallback = {
        "STOP_IF_RESOURCES_HP_OR_SAVE_BRANCH_CHANGE":
            "実行前の状態変化、費用の不一致、候補選手の準備不足があれば実行せず再検証します。",
    }[expected["fallback"]]
    expense = f"スポーツ{cost['sports']}" + (
        f"、応援{cost['cheer']}" if cheer == "ON" else "")
    return "\n".join([
        f"次の1手の候補は{drill}の特訓です。手動承認前の下書きです。",
        "参加者：" + "・".join(candidate["participants"]),
        f"特訓：{drill}／応援{cheer}／消費予定：{expense}",
        "回数・スキル：" + checkpoint,
        "採用基準：" + accept[plan["accept_if"]],
        "再試行基準：" + reload[plan["reload_if"]],
        line,
        "Fallback: " + fallback,
    ])


def render_guarded_reply(bridge: dict[str, Any],
                         state: dict[str, Any],
                         *, contract: dict[str, Any] | None = None,
                         root: str | Path = ".",
                         context: dict[str, Any] | None = None,
                         evidence_sources: dict[str, Any] | None = None) -> str:
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
    if intent == "LOCAL_OBSERVATION_STOP":
        from current_observation import current_observations, render_observation_stop
        _no_action_fields(bridge)
        _require(isinstance(contract, dict) and
                 all(rule in {r["rule_id"] for r in contract["rules"]
                              if r["status"] == "ACTIVE"} for rule in rules),
                 "INVALID_RULE_ID")
        observed = current_observations(state, root, context, evidence_sources)
        _require(bridge.get("current_observation") == observed,
                 "CURRENT_OBSERVATION_MISMATCH")
        return render_observation_stop(observed, state, line)
    if bridge.get("context_source") == "VERIFIED_CURRENT_RUN_CONTEXT":
        return _verified_draft_reply(
            bridge, state, line, contract=contract, root=root,
            context=context, evidence_sources=evidence_sources)
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
    _require(has_current_lineage(state),
             "UNSUPPORTED_TIMELINE_FOR_TEMPLATE")
    _no_action_fields(bridge)
    _require(bridge.get("context_source") == "NO_USER_CONTEXT_PUBLIC_REQUEST"
             and bridge.get("status") in {
                 "NEEDS_GROUNDED_FAILURE_ASSESSMENT", "BLOCKED_CANDIDATE",
                 "NEEDS_CANDIDATE"
             }, "UNSUPPORTED_TRUSTED_SKILL_STATE")
    return (
        ("現在の観測から追跡中です。復元元と観測起点以前の履歴は未確定です。"
         if state["timeline_status"] == OBSERVED_TRACKING else "現在のセーブは確認済みですが、")
        + "スキル狙いの特訓条件はまだ検証済みではありません。"
        "参加者・応援設定・費用を含む実行計画は提示しません。\n"
        + line + "\n"
        + "Fallback: 現在の選手準備状況、直近の試合内容、費用とスキル証拠を確認するまで実行を保留します。"
    )


def make_local_verified_draft_packet(
        navigator_result: dict[str, Any], state: dict[str, Any],
        *, source_commit_sha: str, contract: dict[str, Any],
        root: str | Path = ".",
        context: dict[str, Any] | None = None,
        evidence_sources: dict[str, Any] | None = None,
        decision_message: str = "スキル獲得に向けて何をすべき？") -> dict[str, Any]:
    """Local-only adapter; NEVER use this to bypass public P4 input allowlists.

    The input MUST be a sourced, already validated navigator_step result.
    Context and raw observations stay local, not on the public request branch.
    """
    from navigator_step import navigator_step

    requested = _training_projection(navigator_result)
    _require(navigator_result.get("source_event_seq") == state.get("last_event_seq"),
             "LOCAL_DRAFT_NOT_VALIDATED")
    fresh = navigator_step(
        decision_message, state=state, contract=contract,
        boot_verified=True, expected_event_seq=state["last_event_seq"],
        context=context, root=root)
    _require(_training_projection(fresh) == requested, "NAVIGATOR_REVALIDATION_MISMATCH")
    receipts = _verified_evidence_receipts(context, evidence_sources, state, root)
    packet = {
        **requested,
        "context_source": "VERIFIED_CURRENT_RUN_CONTEXT",
        "source_is_current_only_at_this_commit": True,
        "source_commit_sha": source_commit_sha,
        "state_event_seq": state["last_event_seq"],
        "timeline_status": state["timeline_status"],
        "state_structured_sha256": canonical_state_sha256(state),
        "reviewed_context_sha256": canonical_state_sha256(context),
        "evidence_receipts": receipts,
        "evidence_receipts_sha256": canonical_state_sha256(receipts),
        "action_authorized": False,
        "side_effects": False,
    }
    reply = render_guarded_reply(
        packet, state, contract=contract, root=root,
        context=context, evidence_sources=evidence_sources)
    verdict = check_reply(
        reply, bridge=packet, state=state,
        expected_main_sha=source_commit_sha,
        expected_event_seq=state["last_event_seq"],
        contract=contract, root=root,
        context=context, evidence_sources=evidence_sources)
    _require(verdict["status"] == "PASS", "LOCAL_DRAFT_REPLY_NOT_CERTIFIED")
    packet["safe_reply"] = reply
    packet["safe_reply_check"] = verdict
    return packet


def check_reply(text: str, *, bridge: dict[str, Any],
                state: dict[str, Any],
                expected_main_sha: str, expected_event_seq: int,
                contract: dict[str, Any] | None = None,
                root: str | Path = ".",
                context: dict[str, Any] | None = None,
                evidence_sources: dict[str, Any] | None = None) -> dict[str, Any]:
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
            bridge, state, contract=contract, root=root,
            context=context, evidence_sources=evidence_sources)
        _require(isinstance(text, str), "REPLY_MUST_BE_TEXT")
        _require(text == expected, "REPLY_NOT_CANONICAL")
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
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
    parser.add_argument("--private-context", type=Path)
    parser.add_argument("--private-evidence-index", type=Path)
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
        context = (json.loads(args.private_context.read_text(encoding="utf-8"))
                   if args.private_context else None)
        sources = (json.loads(args.private_evidence_index.read_text(encoding="utf-8"))
                   if args.private_evidence_index else None)
        if args.render:
            result = render_guarded_reply(
                bridge, state, contract=contract, root=args.root,
                context=context, evidence_sources=sources)
            gate = check_reply(result, bridge=bridge, state=state,
                               expected_main_sha=args.expected_main_sha,
                               expected_event_seq=args.expected_event_seq,
                               contract=contract, root=args.root,
                               context=context, evidence_sources=sources)
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
            contract=contract, root=args.root,
            context=context, evidence_sources=sources)
        print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
        if verdict["status"] != "PASS":
            parser.exit(2)
    except (OSError, ValueError, ReplyGateError) as exc:
        parser.exit(2, "REPLY_GUARD_FAIL:" + str(exc) + "\n")


if __name__ == "__main__":
    main()
