#!/usr/bin/env python3
"""Single local entry point for a replayed, strategy-checked and certified reply."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from check_reply import (ReplyGateError, canonical_state_sha256, check_reply,
                         make_local_verified_draft_packet, render_guarded_reply)
from current_observation import ROSTER_RECORD, current_observations
from knowledge_engine import validate_skill_recommendation
from live_state_engine import validate_recommendation
from navigator_step import navigator_step
from project_bootstrap import ResumeError, bootstrap_sources, git_sha


def verify_checkout(root, expected_sha):
    if git_sha(root) != expected_sha:
        raise ResumeError("STALE_MAIN_SHA")
    checked = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"],
        capture_output=True, check=False)
    if checked.returncode:
        raise ResumeError("CHECKOUT_DIFF_UNVERIFIED" if checked.returncode != 1
                          else "TRACKED_CHECKOUT_CHANGES")
    if (root / ROSTER_RECORD).is_file():
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", ROSTER_RECORD],
            capture_output=True, check=False)
        if tracked.returncode:
            raise ResumeError("ROSTER_OBSERVATION_NOT_TRACKED")


def next_action(message, *, root=".", expected_main_sha, expected_event_seq,
                context=None, evidence_sources=None, proposed_reply=None):
    """Read-only. The only user-facing gameplay prose is safe_reply on PASS."""
    root = Path(root).resolve()
    result = {
        "status": "STOP_UNCERTIFIED", "safe_reply": None,
        "safe_reply_check": None, "action_authorized": False, "side_effects": False,
        "source_commit_sha": expected_main_sha, "state_event_seq": expected_event_seq,
        "blocking_reasons": [],
    }
    try:
        boot, state, contract, _, _ = bootstrap_sources(
            "野球部ものがたりの続き", root=root, expected_main_sha=expected_main_sha)
        verify_checkout(root, expected_main_sha)
        result["boot_status"] = boot["status"]
        result["live_replay_verified"] = boot["live_replay_verified"]
        if type(expected_event_seq) is not int or expected_event_seq != state["last_event_seq"]:
            raise ResumeError("STALE_EVENT_REVISION")

        # This explicit entry resolves the continuation request to next-action intent.
        if isinstance(message, str) and message.strip() in {"進めて", "続けて"}:
            message = "次は何をすべき？"
        compared = navigator_step(
            message, state=state, contract=contract, boot_verified=True,
            expected_event_seq=expected_event_seq, context=context, root=root)
        result["navigator_status"] = compared["status"]
        result["candidates_compared"] = len(compared["candidates"])
        result["blocking_reasons"] = compared.get("blocking_reasons", compared["errors"])
        result["current_observation"] = current_observations(
            state, root, context, evidence_sources)
        result["save_history_status"] = state["timeline_status"]
        if "observed_tracking" in state:
            result["observed_tracking"] = state["observed_tracking"]
        draft = compared["action_draft"]
        packet = None
        result["strategy_validation"] = "NO_VALIDATED_CANDIDATE"
        if draft is not None:
            validator = (validate_skill_recommendation if draft.get("skill_goal") is not None
                         else validate_recommendation)
            errors = validator(draft, state, contract, context=context, root=root)
            if errors:
                raise ReplyGateError("STRATEGY_VALIDATION_FAILED:" + ",".join(errors))
            result["strategy_validation"] = "PASS"
            if draft["action_type"] == "TRAIN":
                try:
                    packet = make_local_verified_draft_packet(
                        compared, state, source_commit_sha=expected_main_sha, contract=contract,
                        root=root, context=context, evidence_sources=evidence_sources,
                        decision_message=message)
                except ReplyGateError as exc:
                    result["blocking_reasons"] = [str(exc)]
            else:
                result["blocking_reasons"] = ["UNSUPPORTED_ACTION_FOR_CERTIFIED_REPLY"]

        training_reply = packet is not None
        if packet is None:
            packet = {
                "intent": "LOCAL_OBSERVATION_STOP",
                "source_is_current_only_at_this_commit": True,
                "source_commit_sha": expected_main_sha,
                "state_event_seq": expected_event_seq,
                "timeline_status": state["timeline_status"],
                "state_structured_sha256": canonical_state_sha256(state),
                "action_authorized": False, "side_effects": False,
                "rule_ids": compared["rule_ids"] or boot["active_controlling_rules"],
                "current_observation": result["current_observation"],
            }
        reply = (proposed_reply if proposed_reply is not None else
                 render_guarded_reply(packet, state, contract=contract, root=root,
                                      context=context, evidence_sources=evidence_sources))
        verdict = check_reply(
            reply, bridge=packet, state=state, expected_main_sha=expected_main_sha,
            expected_event_seq=expected_event_seq, contract=contract, root=root,
            context=context, evidence_sources=evidence_sources)
        verify_checkout(root, expected_main_sha)
        result["safe_reply_check"] = verdict
        if verdict["status"] == "PASS":
            result["status"] = ("CERTIFIED_TRAINING_DRAFT" if training_reply
                                else "CERTIFIED_NO_ACTION")
            result["safe_reply"] = reply
        else:
            result["blocking_reasons"] = result["blocking_reasons"] + verdict["error_codes"]
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        result["blocking_reasons"] = result["blocking_reasons"] + [str(exc)]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--expected-event-seq", required=True, type=int)
    parser.add_argument("--private-context", type=Path)
    parser.add_argument("--private-evidence-index", type=Path)
    parser.add_argument("--reply", type=Path, help="Exact private draft to check")
    args = parser.parse_args()
    try:
        context = (json.loads(args.private_context.read_text(encoding="utf-8"))
                   if args.private_context else None)
        sources = (json.loads(args.private_evidence_index.read_text(encoding="utf-8"))
                   if args.private_evidence_index else None)
        reply = args.reply.read_text(encoding="utf-8").removesuffix("\n") if args.reply else None
        result = next_action(
            args.message, root=args.root, expected_main_sha=args.expected_main_sha,
            expected_event_seq=args.expected_event_seq, context=context,
            evidence_sources=sources, proposed_reply=reply)
    except (OSError, ValueError) as exc:
        parser.exit(2, "NEXT_ACTION_INPUT_ERROR:" + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    if result["safe_reply"] is None:
        parser.exit(2)


if __name__ == "__main__":
    main()
