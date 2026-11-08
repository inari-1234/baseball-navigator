#!/usr/bin/env python3
"""P4: ChatGPT -> connected GitHub -> Actions -> navigator_step -> ChatGPT.

Read-only, source-pinned tool bridge. Public GitHub request branches carry ONLY
a constrained enum, an opaque non-identifying request ID and source revisions.
Free-text chats, screenshots, HP/player measurements and private Library IDs are
rejected at this boundary, not uploaded to a public repository.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from knowledge_engine import validate_knowledge
from navigator_step import navigator_step
from project_bootstrap import ResumeError, bootstrap
from check_reply import (ReplyGateError, render_guarded_reply,
                         check_reply, canonical_state_sha256)

INTENTS = {
    "SKILL": "スキル獲得に向けて何をすべき？",
    "GENERAL": "次は何をすべき？",
    "MATCH": "試合すべき？",
    "RECOVERY": "アイテムを使うべき？",
    "STATUS": "現在の状態を教えて",
    "TRAINING_COUNTS": "現在の本線の特訓回数の記録を確認して",
    "BOOT": "野球部ものがたりの続き",
}
REQUIRED_FIELDS = {
    "schema_version", "request_id", "intent",
    "expected_main_sha", "expected_event_seq",
}
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{3,63}$")
BOOT_FILES = (
    "AGENTS.md",
    "RUN_GUARD_POLICY.yaml",
    "DECISION_CONTRACT.json",
    "CURRENT_LIVE_STATE.json",
    "CURRENT_HANDOFF.md",
    "CURRENT_RUN_LEDGER.yaml",
    "DECISION_LOG.jsonl",
    "SAPPORO_SPRINT_STRATEGY.md",
)
ORDERED_BOOT = BOOT_FILES[1:]


class ChatBridgeError(ValueError):
    pass


def validate_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != REQUIRED_FIELDS:
        raise ChatBridgeError("REQUEST_ALLOWLIST_ONLY")
    if request["schema_version"] != "1.0":
        raise ChatBridgeError("REQUEST_SCHEMA_VERSION_UNSUPPORTED")
    if not isinstance(request["request_id"], str) or not ID_RE.fullmatch(request["request_id"]):
        raise ChatBridgeError("REQUEST_ID_INVALID")
    if request["intent"] not in INTENTS:
        raise ChatBridgeError("REQUEST_INTENT_NOT_ALLOWED")
    if not isinstance(request["expected_main_sha"], str) or not SHA_RE.fullmatch(request["expected_main_sha"]):
        raise ChatBridgeError("REQUEST_MAIN_SHA_INVALID")
    if type(request["expected_event_seq"]) is not int or request["expected_event_seq"] < 0:
        raise ChatBridgeError("REQUEST_EVENT_REVISION_INVALID")
    return request


def verify_boot(root: Path) -> None:
    if not all((root / name).is_file() for name in BOOT_FILES):
        raise ChatBridgeError("BOOT_AUTHORITY_MISSING")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    start = agents.find("## BOOT")
    end = agents.find("## ", start + 1)
    if start < 0 or end < 0:
        raise ChatBridgeError("BOOT_ORDER_UNCONFIRMED")
    boot = agents[start:end]
    cursor = -1
    for name in ORDERED_BOOT:
        found = boot.find(name, cursor + 1)
        if found < 0 or found <= cursor:
            raise ChatBridgeError("BOOT_ORDER_UNCONFIRMED")
        cursor = found
    if ("navigator_step.py" not in agents or
            "KNOWLEDGE_MANIFEST.json" not in agents):
        raise ChatBridgeError("BOOT_NAVIGATOR_NOT_WIRED")


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def bridge_response(request: Any, *, root: str | Path,
                    actual_main_sha: str) -> dict[str, Any]:
    """Create machine-readable, source-pinned and non-authorizing advice."""
    request = validate_request(request)
    root = Path(root)
    if actual_main_sha != request["expected_main_sha"]:
        raise ChatBridgeError("STALE_MAIN_SHA")
    verify_boot(root)
    if request["intent"] == "BOOT":
        # A single connected GitHub action now returns all seven verified
        # BOOT authorities and mandatory skill evidence in one safe capsule.
        # This remains a tool-initiated operation, not an automatic ChatGPT hook.
        try:
            report = bootstrap(INTENTS["BOOT"], root=root,
                               expected_main_sha=actual_main_sha,
                               checked_main_sha=actual_main_sha)
        except ResumeError as exc:
            raise ChatBridgeError("PROJECT_BOOT_FAILED:" + str(exc)) from exc
        if report["state"]["event_seq"] != request["expected_event_seq"]:
            raise ChatBridgeError("STALE_EVENT_REVISION")
        return {
            "schema_version": "1.0",
            "request_id": request["request_id"],
            "intent": "BOOT",
            "source_commit_sha": actual_main_sha,
            "state_event_seq": report["state"]["event_seq"],
            "status": report["status"],
            "rule_ids": report["active_controlling_rules"],
            "knowledge_refs": report["knowledge"]["required_claim_ids"],
            "primary_next_step": report["next_safe_step"],
            "boot_report": report,
            "action_authorized": False,
            "side_effects": False,
            "source_is_current_only_at_this_commit": True,
        }
    try:
        state = json.loads((root / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        contract = json.loads((root / "DECISION_CONTRACT.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ChatBridgeError("CANONICAL_SOURCE_UNREADABLE") from exc
    if state.get("last_event_seq") != request["expected_event_seq"]:
        raise ChatBridgeError("STALE_EVENT_REVISION")
    try:
        knowledge = validate_knowledge(root)
    except (OSError, ValueError) as exc:
        raise ChatBridgeError("KNOWLEDGE_CONTINUITY_FAILED:" + str(exc)) from exc
    if knowledge.get("result") != "PASS":
        raise ChatBridgeError("KNOWLEDGE_CONTINUITY_NOT_PASS")

    result = navigator_step(
        INTENTS[request["intent"]],
        state=state, contract=contract, boot_verified=True,
        expected_event_seq=request["expected_event_seq"],
        context={}, root=root,
    )
    if result.get("action_authorized") is not False or result.get("side_effects") is not False:
        raise ChatBridgeError("EXECUTION_BOUNDARY_VIOLATED")
    # No user input or source file paths are reflected in this public response.
    # Include enough evidence and stop reasons for the assistant to answer directly.
    blocked_for_user = result.get("status") != "VALIDATED_DRAFT_REVIEW"
    result_candidate = None
    # A blocked internal comparison is NOT a ChatGPT-facing action plan.
    # Do not export its historical participants, Cheer setting or costs.
    cid = result.get("selected_candidate") if not blocked_for_user else None
    if isinstance(cid, str):
        for item in result.get("candidates", []):
            if item.get("id") == cid:
                result_candidate = {
                    "id": cid,
                    "drill": item.get("drill"),
                    "cheer": item.get("cheer"),
                    "participants": item.get("participants"),
                    "cost": item.get("cost"),
                    "blocked_by": item.get("blocking_reasons", []),
                    "candidate_rules": item.get("rule_ids", []),
                    "accept_reload_plan": item.get("accept_reload_plan"),
                    "skills_not_guaranteed": item.get("target_skill_at_this_drill_not_guaranteed", False),
                }
                break
    summary = {
        "schema_version": "1.0",
        "request_id": request["request_id"],
        "intent": request["intent"],
        "source_commit_sha": actual_main_sha,
        "state_event_seq": state["last_event_seq"],
        "state_sha256": _sha256_file(root / "CURRENT_LIVE_STATE.json"),
        "state_structured_sha256": canonical_state_sha256(state),
        "knowledge_claims_sha256": _sha256_file(root / "KNOWLEDGE_CLAIMS.json"),
        "timeline_status": state.get("timeline_status"),
        "status": result["status"],
        "primary_next_step": result.get("primary_next_step"),
        "provisional_target": None if blocked_for_user else result.get("provisional_target"),
        "selected_candidate": None if blocked_for_user else result.get("selected_candidate"),
        "candidate": result_candidate,
        "blocked_candidate_suppressed": blocked_for_user,
        "failure_mode": result.get("failure_mode"),
        "rule_ids": result.get("rule_ids", []),
        "knowledge_refs": result.get("knowledge_refs", []),
        "fallback": result.get("fallback"),
        "blocking_reasons": result.get("blocking_reasons", result.get("errors", [])),
        "observation": result.get("observation"),
        "action_authorized": False,
        "side_effects": False,
        "requires_manual_acceptance": bool(result.get("requires_manual_acceptance", False)),
        "context_source": "NO_USER_CONTEXT_PUBLIC_REQUEST",
        "source_is_current_only_at_this_commit": True,
    }
    if request["intent"] == "SKILL" and "SKILL-4TH-PATTERN" not in summary["knowledge_refs"]:
        raise ChatBridgeError("REQUIRED_SKILL_KNOWLEDGE_NOT_APPLIED")
    if not summary["rule_ids"]:
        raise ChatBridgeError("MISSING_ACTIVE_RULE_IDS")
    # P7-D: a bounded deterministic response is certified at this exact
    # source revision. This does not constrain free-form ChatGPT messages.
    if request["intent"] in {"SKILL", "TRAINING_COUNTS"}:
        try:
            rendered = render_guarded_reply(summary, state)
        except ReplyGateError as exc:
            summary["safe_reply"] = None
            summary["safe_reply_check"] = {
                "status": "NOT_CERTIFIED",
                "reason": str(exc),
                "chat_runtime_hook_guaranteed": False,
            }
        else:
            verdict = check_reply(
                rendered, bridge=summary, state=state,
                expected_main_sha=actual_main_sha,
                expected_event_seq=state["last_event_seq"])
            if verdict["status"] != "PASS":
                raise ChatBridgeError("REPLY_GUARD_FAILED")
            summary["safe_reply"] = rendered
            summary["safe_reply_check"] = verdict
    return summary


def git_head(root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=8, text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ChatBridgeError("CANONICAL_COMMIT_UNVERIFIED") from exc
    if not SHA_RE.fullmatch(out):
        raise ChatBridgeError("CANONICAL_COMMIT_INVALID")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only GitHub Actions ChatGPT bridge")
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--source-root", type=Path, default=Path("."))
    args = p.parse_args()
    try:
        data = json.loads(args.request.read_text(encoding="utf-8"))
        reply = bridge_response(data, root=args.source_root,
                                actual_main_sha=git_head(args.source_root))
    except (ChatBridgeError, ValueError, OSError) as exc:
        p.exit(2, "NAV_CHAT_BRIDGE_FAIL:" + str(exc) + "\n")
    print(json.dumps(reply, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
