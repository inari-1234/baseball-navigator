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


def render_guarded_reply(bridge: dict[str, Any],
                         state: dict[str, Any]) -> str:
    """Return only an evidence-constrained Japanese reply for supported cases.

    Unknown or future states deliberately have no certified template.
    Never use an unsupported state as permission to improvise a plan.
    """
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
    _require(bridge.get("context_source") == "NO_USER_CONTEXT_PUBLIC_REQUEST",
             "UNEXPECTED_USER_CONTEXT")
    _require(bridge.get("candidate") is None
             and bridge.get("provisional_target") is None
             and bridge.get("selected_candidate") is None,
             "BLOCKED_CANDIDATE_LEAK")
    _require(state.get("timeline_status") ==
             "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN",
             "UNSUPPORTED_TIMELINE_FOR_TEMPLATE")
    rules = bridge.get("rule_ids")
    _require(isinstance(rules, list) and len(rules) > 0
             and all(isinstance(x, str) and x.startswith("DC-") for x in rules),
             "RULE_IDS_REQUIRED")
    line = "Rule: " + "、".join(rules)
    intent = bridge.get("intent")
    if intent == "SKILL":
        _require(bridge.get("status") == "BLOCKED_UNVERIFIED_TIMELINE",
                 "SKILL_GATE_NOT_BLOCKED")
        _require("SKILL-4TH-PATTERN" in bridge.get("knowledge_refs", []),
                 "SKILL_EVIDENCE_MISSING")
        _require("ROLLBACK_SAVEPOINT_UNKNOWN_OR_UNTRUSTED_TIMELINE"
                 in bridge.get("blocking_reasons", []),
                 "SKILL_BLOCKER_MISSING")
        return (
            "現行セーブの復元地点が未確定です。選手別の特訓総回数と、次が4回目かどうかは確認できません。"
            "スキル狙いの特訓は現時点では実行せず、現在のセーブの確認を優先してください。\n"
            + line + "\n"
            + "Fallback: 現行セーブと特訓履歴の証拠が揃わなければ、資源を消費する特訓を保留します。"
        )
    if intent == "TRAINING_COUNTS":
        observation = bridge.get("observation")
        _require(bridge.get("status") == "READ_ONLY_READY"
                 and isinstance(observation, dict)
                 and observation.get("topic") == "TRAINING_COUNTS"
                 and observation.get("source_event_seq") == state["last_event_seq"]
                 and observation.get("exact_total_status") == "UNKNOWN"
                 and observation.get("fourth_checkpoint_verified") is False
                 and observation.get("event_ledger_counts_lower_bound") is None
                 and observation.get("exact_current_counts_by_player_drill") == {}
                 and observation.get("missing_player_drill_count_means_zero") is False,
                 "EXACT_TRAINING_COUNT_NOT_UNVERIFIED")
        return (
            "現在のセーブについて、選手別の特訓総回数は未確定です。"
            "記録に回数がないことは0回の証拠ではなく、3回済みとも次が4回目とも判断できません。\n"
            + line + "\n"
            + "Fallback: 現行セーブと選手・練習別の確定回数が確認されるまで、4回目とは認定しません。"
        )
    raise ReplyGateError("UNSUPPORTED_INTENT_FOR_CERTIFIED_REPLY")


def check_reply(text: str, *, bridge: dict[str, Any],
                state: dict[str, Any],
                expected_main_sha: str, expected_event_seq: int) -> dict[str, Any]:
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
        expected = render_guarded_reply(bridge, state)
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
        if args.render:
            result = render_guarded_reply(bridge, state)
            gate = check_reply(result, bridge=bridge, state=state,
                               expected_main_sha=args.expected_main_sha,
                               expected_event_seq=args.expected_event_seq)
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
            expected_event_seq=args.expected_event_seq)
        print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
        if verdict["status"] != "PASS":
            parser.exit(2)
    except (OSError, ValueError, ReplyGateError) as exc:
        parser.exit(2, "REPLY_GUARD_FAIL:" + str(exc) + "\n")


if __name__ == "__main__":
    main()
