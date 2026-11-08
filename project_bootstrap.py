#!/usr/bin/env python3
"""P6: Read-only one-phrase project identification and verified cross-chat BOOT.

Not an automatic ChatGPT startup hook. The caller must invoke it against the
actual GitHub checkout. It reads AGENTS.md first and every BOOT file in order.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from knowledge_engine import validate_knowledge, load_knowledge, KnowledgeError
from live_state_engine import read_events, replay, ObservationError

BOOT_ORDER = (
    "RUN_GUARD_POLICY.yaml", "DECISION_CONTRACT.json",
    "CURRENT_LIVE_STATE.json", "CURRENT_HANDOFF.md",
    "CURRENT_RUN_LEDGER.yaml", "DECISION_LOG.jsonl",
    "SAPPORO_SPRINT_STRATEGY.md",
)
REQUIRED_RULES = (
    "DC-INGEST-001", "DC-STATE-001", "DC-UNKNOWN-001",
    "DC-ACTION-001", "DC-TRAIN-001", "DC-TRACE-001",
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class ResumeError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise ResumeError(code)


def read(root, path):
    try:
        return (root / path).read_bytes()
    except OSError as exc:
        raise ResumeError("REQUIRED_SOURCE_UNREADABLE:" + path) from exc


def parse(raw, name):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ResumeError("INVALID_JSON:" + name) from exc
    require(isinstance(value, dict), "INVALID_OBJECT:" + name)
    return value


def normalize(text):
    return "".join(unicodedata.normalize("NFKC", text).lower().split())


def match_project(message, registry):
    if not isinstance(message, str) or not message.strip():
        return False
    cfg = registry.get("recognition", {})
    require(isinstance(cfg, dict), "INVALID_PROJECT_RECOGNITION")
    singles = cfg.get("normalized_substrings", [])
    groups = cfg.get("all_of_terms", [])
    require(isinstance(singles, list) and
            all(isinstance(x, str) and len(normalize(x)) >= 5 for x in singles),
            "INVALID_PROJECT_ALIASES")
    require(isinstance(groups, list) and all(
        isinstance(g, list) and len(g) >= 2 and all(
            isinstance(x, str) and len(normalize(x)) >= 2 for x in g)
        for g in groups), "INVALID_PROJECT_CONJUNCTIONS")
    text = normalize(message)
    return (any(normalize(s) in text for s in singles) or
            any(all(normalize(word) in text for word in g) for g in groups))


def check_agents(raw):
    try:
        agents = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ResumeError("AGENTS_INVALID_UTF8") from exc
    require(agents.startswith("# Baseball Navigator Agent Contract"),
            "WRONG_PROJECT_AGENTS")
    start = agents.find("## BOOT")
    end = agents.find("\n## ", start + 1)
    require(start >= 0 and end > start, "BOOT_SECTION_MISSING")
    section = agents[start:end]
    cursor = -1
    for name in BOOT_ORDER:
        next_at = section.find(chr(96) + name + chr(96), cursor + 1)
        require(next_at > cursor, "BOOT_ORDER_ALTERED:" + name)
        cursor = next_at


def git_sha(root):
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True, timeout=8,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ResumeError("GIT_SOURCE_REVISION_UNVERIFIED") from exc
    require(bool(SHA40.fullmatch(sha)), "INVALID_GIT_SOURCE_SHA")
    return sha


def bootstrap(message, *, root=".", expected_main_sha=None,
              checked_main_sha=None):
    root = Path(root)
    agents = read(root, "AGENTS.md")  # always first authority access
    check_agents(agents)
    registry = parse(read(root, "PROJECT_ENTRYPOINT.json"),
                     "PROJECT_ENTRYPOINT.json")
    require(registry.get("schema_version") == "1.0"
            and registry.get("repository") == "inari-1234/baseball-navigator"
            and registry.get("project_id") ==
                "kairosoft-baseball-story-sapporo-sprint",
            "PROJECT_ENTRYPOINT_INVALID")
    require(match_project(message, registry),
            "PROJECT_NOT_UNAMBIGUOUSLY_IDENTIFIED")
    if checked_main_sha is None:
        sha = git_sha(root)
    else:
        require(isinstance(checked_main_sha, str)
                and bool(SHA40.fullmatch(checked_main_sha)),
                "INVALID_CHECKED_MAIN_SHA")
        sha = checked_main_sha  # only a verified GitHub bridge may supply this
    if expected_main_sha is not None:
        require(isinstance(expected_main_sha, str)
                and bool(SHA40.fullmatch(expected_main_sha)),
                "EXPECTED_MAIN_SHA_INVALID")
        require(sha == expected_main_sha, "STALE_MAIN_SHA")

    data = [(name, read(root, name)) for name in BOOT_ORDER]
    files = dict(data)
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in data}
    policy = parse(files["RUN_GUARD_POLICY.yaml"], "RUN_GUARD_POLICY.yaml")
    contract = parse(files["DECISION_CONTRACT.json"], "DECISION_CONTRACT.json")
    state = parse(files["CURRENT_LIVE_STATE.json"], "CURRENT_LIVE_STATE.json")
    handoff = files["CURRENT_HANDOFF.md"].decode("utf-8")
    ledger = parse(files["CURRENT_RUN_LEDGER.yaml"], "CURRENT_RUN_LEDGER.yaml")
    strategy = files["SAPPORO_SPRINT_STRATEGY.md"].decode("utf-8")
    try:
        decisions = [json.loads(line) for line in
                     files["DECISION_LOG.jsonl"].decode("utf-8").splitlines()
                     if line.strip()]
    except (UnicodeError, ValueError) as exc:
        raise ResumeError("DECISION_LOG_UNREADABLE") from exc
    require(policy.get("schema_version") == "1.0" and
            isinstance(policy.get("policy_version"), str),
            "RUN_GUARD_POLICY_INVALID")
    rules = contract.get("rules", [])
    require(isinstance(rules, list), "CONTRACT_RULES_INVALID")
    active = {r.get("rule_id") for r in rules if
              isinstance(r, dict) and r.get("status") == "ACTIVE"}
    require(all(rule in active for rule in REQUIRED_RULES),
            "CRITICAL_ACTIVE_RULE_MISSING")
    try:
        events = read_events(root / "LIVE_EVENTS.jsonl")
        recreated = replay(events)
    except (OSError, ObservationError) as exc:
        raise ResumeError("LIVE_EVENT_REPLAY_FAILED:" + str(exc)) from exc
    require(state == recreated, "CURRENT_STATE_REPLAY_MISMATCH")
    require(type(state.get("last_event_seq")) is int
            and state["last_event_seq"] == len(events),
            "CURRENT_EVENT_SEQUENCE_MISMATCH")
    require(ledger.get("goal", {}).get("primary", {}).get("id") ==
            registry.get("primary_goal_id") and
            isinstance(ledger.get("ledger_version"), int),
            "GOAL_OR_LEDGER_MISMATCH")
    require("さっぽこ高校" in strategy and
            "CURRENT_HANDOFF" in handoff,
            "STRATEGY_OR_HANDOFF_MISSING")
    require(decisions and all(isinstance(x, dict) for x in decisions)
            and [x.get("seq") for x in decisions] ==
                list(range(1, len(decisions) + 1)),
            "DECISION_SEQUENCE_INCONSISTENT")
    latest = decisions[-1]
    require(latest.get("ledger_version") == ledger["ledger_version"],
            "DECISION_LEDGER_VERSION_CONFLICT")
    basis = latest.get("decision_basis", {})
    require(isinstance(basis, dict)
            and isinstance(basis.get("rule_ids"), list)
            and all(rule in active for rule in basis["rule_ids"]),
            "LAST_DECISION_RULES_NOT_ACTIVE")
    try:
        validated = validate_knowledge(root, check_handoff=True)
        knowledge = load_knowledge(root)
    except (KnowledgeError, ValueError, OSError) as exc:
        raise ResumeError("KNOWLEDGE_CONTINUITY_FAILED:" + str(exc)) from exc
    required = registry.get("required_knowledge_ids", [])
    require(isinstance(required, list) and
            all(k in knowledge["claims"] for k in required)
            and "SKILL-4TH-PATTERN" in required
            and "SKILL-ACCEPTED-HISTORICAL" in required,
            "PROJECT_REQUIRED_KNOWLEDGE_MISSING")
    require(validated["result"] == "PASS" and
            knowledge["claims"]["SKILL-4TH-PATTERN"]["status"] ==
                "OBSERVED_PATTERN" and
            "KNOWLEDGE:SKILL-4TH-PATTERN" in handoff and
            "NAVIGATOR:navigator_step.py" in handoff and
            "quick_image_pipeline.py" in handoff,
            "CRITICAL_HANDOFF_KNOWLEDGE_MISSING")
    matches = [
        {"id": mid, "opponent": info.get("opponent"),
         "period": info.get("period")}
        for mid, info in sorted(state.get("matches", {}).items())
        if info.get("status") == "SCHEDULED"
    ]
    trusted = state.get("timeline_status") == "TRUSTED"
    return {
        "schema_version": "1.0",
        "project_id": registry["project_id"],
        "project_match": "UNAMBIGUOUS_PROJECT_ALIAS",
        "source_repository": registry["repository"],
        "source_commit_sha": sha,
        "status": "BOOT_VERIFIED" if trusted else "BOOT_VERIFIED_ACTIONS_BLOCKED",
        "boot_order_verified": True,
        "boot_files_read": list(BOOT_ORDER),
        "boot_file_sha256": hashes,
        "live_replay_verified": True,
        "knowledge_integrity_verified": True,
        "goal": ledger["goal"]["primary"]["description"],
        "state": {
            "event_seq": state["last_event_seq"],
            "period": state.get("period_floor"),
            "clock": state.get("current_exact_time"),
            "timeline_status": state.get("timeline_status"),
            "resources": state.get("resources"),
            "current_skills": (state.get("skills") if trusted else
                               "UNVERIFIED_AFTER_ROLLBACK"),
            "current_training_counts": (
                (state.get("training_counts_exact_by_player_drill") or
                 "UNKNOWN_WITHOUT_EXACT_BASELINE") if trusted else
                "UNVERIFIED_AFTER_ROLLBACK"),
            "recorded_training_lower_bounds": (
                state.get("training_counts_by_player_drill", {}) if trusted else None),
            "scheduled_matches": matches,
        },
        "knowledge": {
            "required_claim_ids": required,
            "fourth_training_status": "OBSERVED_PATTERN",
            "fourth_training_not_guaranteed": True,
            "negative_rerolls_earlier_sessions_approx": 40,
            "historical_accepted_at_reporting":
                knowledge["claims"]["SKILL-ACCEPTED-HISTORICAL"]
                    ["accepted_at_reporting"],
            "historical_skills_are_not_current_confirmation": True,
            "evidence_records": validated["evidence"],
            "historical_private_backup_checkpoints":
                validated["private_backup_verified_at_checkpoint"],
            "original_image_bytes_in_public_git": False,
            "private_library_reachability_checked_now": False,
        },
        "latest_decision": {
            "seq": latest["seq"],
            "event": latest.get("event"),
            "rule_ids": basis["rule_ids"],
        },
        "next_safe_step": (
            "RECONCILE_RESTORED_SAVE_ANCHOR_BEFORE_PAID_ACTION" if not trusted
            else "INGEST_NEW_CURRENT_DELTA_BEFORE_NEXT_ACTION"
        ),
        "active_controlling_rules": list(REQUIRED_RULES),
        "action_authorized": False,
        "writes_performed": False,
        "automatic_new_chat_invocation_guaranteed": False,
        "requires_connector_invocation": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Source-verified baseball resume")
    parser.add_argument("message")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--expected-main-sha")
    args = parser.parse_args()
    try:
        response = bootstrap(args.message, root=args.root,
                             expected_main_sha=args.expected_main_sha)
    except (ResumeError, ValueError, OSError) as exc:
        parser.exit(2, "PROJECT_BOOT_FAIL:" + str(exc) + "\n")
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
