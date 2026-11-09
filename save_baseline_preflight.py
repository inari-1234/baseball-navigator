#!/usr/bin/env python3
"""Read-only current-save tracking-origin preflight, NOT rollback reconciliation.

Runs on already recorded screenshot/user evidence. It does not declare the
restored historical SAVE or current training/skills and never grants an action.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from live_state_engine import ObservationError, read_events, replay

CAPTURE_PATH = "new_run.current.image_capture_relation_to_save_load"
UNKNOWN_ID = "UNK-ROLLBACK-SAVEPOINT-20261106"
SHA256 = re.compile(r"^[a-f0-9]{64}$")
COUNTERS = ("study", "sports", "play", "nature", "cheer")


class BaselinePreflightError(ValueError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BaselinePreflightError(message)


def assess_current_capture(state: dict[str, Any],
                           events: list[dict[str, Any]],
                           ledger: dict[str, Any]) -> dict[str, Any]:
    """Assess whether the immediate post-LOAD capture is a safe observation origin.

    A valid origin is NOT a trusted historical SAVE anchor. Only fields read
    from the referenced capture are source-attributed; all pre-LOAD progress
    and exact training counts remain UNKNOWN.
    """
    require(isinstance(state, dict) and isinstance(events, list)
            and isinstance(ledger, dict), "SOURCE_INPUT_REQUIRED")
    try:
        regenerated = replay(events)
    except (ObservationError, KeyError, TypeError, ValueError) as exc:
        raise BaselinePreflightError("LIVE_REPLAY_FAILED") from exc
    require(regenerated == state, "CURRENT_STATE_REPLAY_MISMATCH")
    require(state.get("timeline_status") ==
            "ROLLBACK_CONFIRMED_SAVEPOINT_UNKNOWN",
            "SAVE_LINEAGE_NOT_UNVERIFIED")
    require(type(state.get("last_event_seq")) is int
            and state["last_event_seq"] == len(events),
            "STALE_EVENT_SEQUENCE")
    claims = [x for x in ledger.get("facts", [])
              if isinstance(x, dict) and x.get("path") == CAPTURE_PATH]
    require(len(claims) == 1, "DIRECT_POSTLOAD_ATTESTATION_MISSING")
    fact = claims[0]
    value = fact.get("value")
    require(fact.get("fact_type") == "OBSERVED"
            and isinstance(value, dict)
            and value.get("post_load_immediate") is True
            and value.get("intervening_game_actions") is False
            and value.get("restored_save_checkpoint") == "UNKNOWN"
            and value.get("retained_historical_training_skill_item_match_effects")
                == "UNKNOWN",
            "POSTLOAD_CLAIM_NOT_CONSERVATIVE")
    sha = value.get("image_sha256")
    require(isinstance(sha, str) and bool(SHA256.fullmatch(sha)),
            "CAPTURE_IMAGE_HASH_NOT_RECORDED")
    refs = fact.get("source_refs")
    require(isinstance(refs, list) and len(refs) >= 2,
            "POSTLOAD_SOURCE_REFS_MISSING")
    evidence = {e.get("evidence_id"): e for e in ledger.get("evidence", [])
                if isinstance(e, dict)}
    require(any(evidence.get(k, {}).get("kind") == "USER_ASSERTION"
                and "immediately after" in evidence[k].get("statement", "")
                and "no gameplay" in evidence[k].get("statement", "")
                for k in refs),
            "DIRECT_USER_ATTESTATION_NOT_FOUND")
    require(any(evidence.get(k, {}).get("kind") == "RAW_EVIDENCE"
                and sha in evidence[k].get("locator", "")
                for k in refs),
            "CAPTURE_RAW_EVIDENCE_NOT_FOUND")

    source_id = state.get("resources", {}).get("last_observed")
    observations = [e for e in events if e.get("event_id") == source_id]
    require(len(observations) == 1, "CURRENT_CAPTURE_EVENT_NOT_FOUND")
    capture = observations[0]
    require(capture.get("kind") == "SCREEN"
            and capture.get("branch") == "ACCEPTED"
            and capture.get("source", {}).get("kind") == "RAW_SCREEN"
            and sha in capture.get("source", {}).get("locator", "")
            and capture.get("user_attested_current") is True,
            "CURRENT_CAPTURE_PROVENANCE_MISMATCH")
    period = capture.get("period")
    require(isinstance(period, dict)
            and value.get("screen_period") ==
            f"Y{period.get('year')}-{period.get('month'):02d}"
            and state.get("period_floor") == value["screen_period"]
            and capture.get("clock") == value.get("clock")
            and state.get("current_exact_time") == value.get("clock"),
            "CURRENT_CAPTURE_CLOCK_OR_PERIOD_MISMATCH")
    require(state.get("resources", {}).get("fresh") is True
            and state["resources"]["values"] ==
            {k: capture.get("resources", {}).get(k) for k in COUNTERS}
            and all(type(state["resources"]["values"][k]) is int
                    for k in COUNTERS),
            "CAPTURE_RESOURCE_MISMATCH")
    following = [e for e in events if e["seq"] > capture["seq"]]
    require(all(e.get("kind") == "CORRECTION"
                and e.get("target_event_id") == source_id
                and e.get("patch") == {"preceded_by_rollback": True}
                and e.get("source", {}).get("kind") == "USER_CORRECTION"
                for e in following),
            "POSTLOAD_MUTATION_REQUIRES_NEW_CAPTURE")

    unknowns = [u for u in ledger.get("unknowns", [])
                if u.get("unknown_id") == UNKNOWN_ID]
    gate = ledger.get("current_gate", {})
    require(len(unknowns) == 1 and unknowns[0].get("status") == "OPEN"
            and unknowns[0].get("material_to_next_action") is True
            and gate.get("status") == "BLOCKED_UNKNOWN"
            and UNKNOWN_ID in gate.get("reason_refs", []),
            "SAVEPOINT_UNKNOWN_GATE_MUST_REMAIN_BLOCKED")
    require(state.get("training_counts_by_player_drill") == {}
            and not state.get("training_counts_exact_by_player_drill"),
            "UNVERIFIED_TRAINING_COUNT_REUSE")
    return {
        "status": "POSTLOAD_CAPTURE_VERIFIED_HISTORY_UNKNOWN",
        "rebaseline_ready": False,
        "trusted_timeline": False,
        "action_authorized": False,
        "side_effects": False,
        "source_event_seq": state["last_event_seq"],
        "capture_event_id": source_id,
        "source_image_sha256": sha,
        "captured": {
            "period": state["period_floor"],
            "clock": state["current_exact_time"],
            "money_yen": capture.get("money_yen"),
            "points": state["resources"]["values"],
            "no_game_actions_between_load_and_capture": True,
        },
        "unverified": [
            "RESTORED_SAVE_CHECKPOINT",
            "RETAINED_PRELOAD_TRAINING_COUNTS",
            "RETAINED_PRELOAD_SKILLS_AND_MATCH_RESULTS",
            "CURRENT_NAMED_PLAYER_HP_AND_READINESS",
            "COMPLETE_ITEM_INVENTORY",
            "CURRENT_MATCH_ELIGIBILITY",
        ],
        "next_evidence": {
            "type": "CURRENT_PLAYER_SCREEN",
            "instruction": "Open 選手 and capture current player names, condition/HP and visible skills without using items, training or advancing time.",
            "no_resource_cost": True,
        },
        "rule_ids": ["DC-STATE-001", "DC-UNKNOWN-001", "DC-ACTION-001"],
        "fallback": "Do not certify an action or infer pre-load skill/training counts if the next screen lacks current player/skill provenance.",
    }


def main() -> None:
    args = argparse.ArgumentParser(description="Read-only post-LOAD capture preflight")
    args.add_argument("--root", type=Path, default=Path("."))
    parsed = args.parse_args()
    root = parsed.root
    try:
        state = json.loads((root / "CURRENT_LIVE_STATE.json").read_text(encoding="utf-8"))
        ledger = json.loads((root / "CURRENT_RUN_LEDGER.yaml").read_text(encoding="utf-8"))
        events = read_events(root / "LIVE_EVENTS.jsonl")
        result = assess_current_capture(state, events, ledger)
    except (OSError, ValueError, ObservationError, KeyError, TypeError) as exc:
        args.exit(2, "BASELINE_PREFLIGHT_STOP:" + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
