#!/usr/bin/env python3
"""Persistent experimental evidence, knowledge continuity and skill navigation.

Never merge experimental SAVE/LOAD outcomes into CURRENT_LIVE_STATE. This
module is read-only. Raw image bytes live in conversation attachments unless
separately persisted; Git only contains verifiable hashes and source locators.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from live_state_engine import validate_recommendation

FOURTH = "SKILL-4TH-PATTERN"
ACCEPTED = "SKILL-ACCEPTED-HISTORICAL"
REQUIRED_CLAIMS = (FOURTH, ACCEPTED)
REQUIRED_TRIALS = ("TR-SKILL-NO-RESULT-FIRST3",
                   "TR-SKILL-FOURTH-CONTROL", "TR-SKILL-FOURTH-MEET")
REQUIRED_EVIDENCE = tuple("EV-SKILL-IMG-" + str(i) for i in range(1, 7)) + (
    "EV-SKILL-USER-REPORT-20261106",)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class KnowledgeError(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise KnowledgeError(code)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KnowledgeError("CANNOT_READ:" + path.name) from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        result = [json.loads(line) for line in lines if line.strip()]
    except (OSError, ValueError) as exc:
        raise KnowledgeError("CANNOT_READ:" + path.name) from exc
    _require(all(isinstance(row, dict) for row in result), "NON_OBJECT_RECORD:" + path.name)
    return result


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        val = row.get(key)
        _require(isinstance(val, str) and bool(val), "BAD_RECORD_ID:" + key)
        _require(val not in result, "DUPLICATE_RECORD_ID:" + val)
        result[val] = row
    return result


def load_knowledge(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    return {
        "evidence": _index(_read_jsonl(root / "EVIDENCE_EVENTS.jsonl"), "evidence_id"),
        "trials": _index(_read_jsonl(root / "EXPERIMENT_TRIALS.jsonl"), "trial_id"),
        "claims": _index(_read_json(root / "KNOWLEDGE_CLAIMS.json")["claims"], "claim_id"),
        "manifest": _read_json(root / "KNOWLEDGE_MANIFEST.json"),
    }


def validate_knowledge(root: str | Path = ".", *, check_handoff: bool = True) -> dict[str, Any]:
    """Enforce evidence/claim links, accepted branch discipline and BOOT coverage.

    A passing check proves consistency of *recorded* facts, not that a
    fourth attempt always awards a skill or that uploaded bytes are in Git.
    """
    root = Path(root)
    data = load_knowledge(root)
    ev, trials, claims, manifest = (
        data["evidence"], data["trials"], data["claims"], data["manifest"])
    for typ, actual, mandatory in (
        ("EVIDENCE", ev, REQUIRED_EVIDENCE),
        ("TRIAL", trials, REQUIRED_TRIALS),
        ("KNOWLEDGE", claims, REQUIRED_CLAIMS)):
        _require(all(i in actual for i in mandatory), "MISSING_REQUIRED_" + typ)
    for key, mandatory in (
        ("required_evidence_ids", REQUIRED_EVIDENCE),
        ("required_experiment_trial_ids", REQUIRED_TRIALS),
        ("required_knowledge_ids", REQUIRED_CLAIMS)):
        refs = manifest.get(key)
        _require(isinstance(refs, list) and all(k in refs for k in mandatory),
                 "MANIFEST_MISSING:" + key)
    for key in ("schema_version", "knowledge_version"):
        _require(isinstance(_read_json(root / "KNOWLEDGE_CLAIMS.json").get(key), str),
                 "BAD_KNOWLEDGE_VERSION")
    for eid, record in ev.items():
        kind = record.get("kind")
        _require(kind in {"SCREENSHOT", "USER_REPORT"}, "BAD_EVIDENCE_KIND:" + eid)
        source = record.get("source")
        _require(isinstance(source, dict), "MISSING_SOURCE:" + eid)
        if kind == "SCREENSHOT":
            _require(bool(HEX64.fullmatch(str(source.get("sha256", "")))),
                     "MISSING_SCREENSHOT_HASH:" + eid)
            _require(bool(source.get("file_name")) and bool(source.get("conversation_file_id")),
                     "SCREENSHOT_SOURCE_MISSING:" + eid)
            _require(source.get("repository_bytes_persisted") is False and
                     source.get("storage") == "CONVERSATION_ATTACHMENT_ONLY",
                     "UNSUPPORTED_SCREENSHOT_PERSISTENCE_CLAIM:" + eid)
            _require(record.get("observation", {}).get("result") == "SKILL_ACQUISITION_POPUP",
                     "UNVERIFIED_SCREENSHOT_OBSERVATION:" + eid)
        else:
            _require(bool(source.get("quote")), "MISSING_VERBATIM_REPORT:" + eid)
    for tid, trial in trials.items():
        refs = trial.get("evidence_refs")
        _require(isinstance(refs, list) and refs and all(eid in ev for eid in refs),
                 "TRIAL_EVIDENCE_MISSING:" + tid)
        ordinals = trial.get("ordinal_range")
        _require(isinstance(ordinals, list) and len(ordinals) == 2 and
                 all(type(i) is int and i > 0 for i in ordinals) and
                 ordinals[0] <= ordinals[1],
                 "TRIAL_ORDINAL_INVALID:" + tid)
        _require(trial.get("current_run_effect") in {"NONE", "UNVERIFIED_AFTER_LATEST_ROLLBACK"},
                 "TRIAL_EFFECT_NOT_RECONCILED:" + tid)
    neg = trials[REQUIRED_TRIALS[0]]
    _require(neg.get("kind") == "REPORTED_AGGREGATE" and
             neg.get("observed_result") == "NO_SKILL_ACQUISITION_REPORTED" and
             neg.get("ordinal_range") == [1, 3] and
             type(neg.get("approx_resets")) is int and neg["approx_resets"] >= 40 and
             neg.get("distinct_independent_attempts") == "UNKNOWN",
             "NEGATIVE_RESET_EVIDENCE_DOWNGRADED")
    for tid in REQUIRED_TRIALS[1:]:
        t = trials[tid]
        _require(t.get("observed_result") == "SKILL_ACQUISITION_REPORTED" and
                 t.get("ordinal_range") == [4, 4] and
                 t.get("distinct_independent_attempts") == "UNKNOWN",
                 "FOURTH_POSITIVE_EVIDENCE_DOWNGRADED:" + tid)
    _require(trials["TR-SKILL-FOURTH-MEET"].get("branch") ==
             "MIXED_ACCEPTED_AND_DISCARDED_RESETS",
             "DISCARDED_OUTCOMES_PROMOTED")
    expected = {("石渡", "コントロールアップ", 1),
                ("入江", "ミート力アップ", 1)}
    observed = []
    for tid in REQUIRED_TRIALS[1:]:
        for item in trials[tid].get("accepted_at_reporting", []):
            _require(isinstance(item, dict), "INVALID_ACCEPTED_SKILL")
            observed.append((item.get("player"), item.get("skill"),
                             item.get("occurrences", 1)))
    _require(set(observed) == expected and len(observed) == 2,
             "HISTORICAL_ACCEPTED_SKILLS_MISMATCH")
    claim = claims[FOURTH]
    _require(claim.get("status") == "OBSERVED_PATTERN" and
             claim.get("positive_ordinal") == 4 and
             claim.get("negative_range") == [1, 3] and
             claim.get("navigation_policy") == "CHECK_FOURTH_BEFORE_EXPENSIVE_REROLL",
             "FOURTH_CLAIM_DOWNGRADED")
    _require(claim.get("current_run_relevance") == "HISTORICAL_MECHANIC_ONLY",
             "FOURTH_CLAIM_INVALID_SCOPE")
    for cid, item in claims.items():
        _require(isinstance(item.get("trial_refs"), list) and
                 item["trial_refs"] and all(t in trials for t in item["trial_refs"]),
                 "KNOWLEDGE_TRIAL_MISSING:" + cid)
        _require(isinstance(item.get("evidence_refs"), list) and
                 item["evidence_refs"] and all(e in ev for e in item["evidence_refs"]),
                 "KNOWLEDGE_EVIDENCE_MISSING:" + cid)
        _require(set(e for t in item["trial_refs"]
                     for e in trials[t]["evidence_refs"]).issubset(set(item["evidence_refs"])),
                 "KNOWLEDGE_NOT_LINKED_TO_ALL_TRIAL_EVIDENCE:" + cid)
    accepted = claims[ACCEPTED]
    accepted_set = {(row.get("player"), row.get("skill"), row.get("occurrences"))
                    for row in accepted.get("accepted_at_reporting", [])}
    _require(accepted.get("status") == "USER_REPORTED_HISTORICAL_ACCEPTANCE" and
             accepted_set == expected and
             accepted.get("current_run_effect") == "UNVERIFIED_AFTER_LATEST_ROLLBACK",
             "HISTORICAL_ACCEPTANCE_DOWNGRADED_OR_PROMOTED")
    for row in ev.values():
        if row["kind"] == "USER_REPORT":
            _require(row.get("observation", {}).get("positive_ordinal") == 4 and
                     row.get("observation", {}).get("approx_reset_attempts") == 40 and
                     row.get("observation", {}).get("negative_ordinal_range") == [1, 3],
                     "USER_SOURCE_NOT_CONSISTENT_WITH_CLAIM")
    if check_handoff:
        try:
            handoff = (root / "CURRENT_HANDOFF.md").read_text(encoding="utf-8")
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        except OSError as exc:
            raise KnowledgeError("HANDOFF_OR_AGENTS_MISSING") from exc
        for cid in manifest.get("required_handoff_knowledge_ids", []):
            _require(("KNOWLEDGE:" + cid) in handoff,
                     "HANDOFF_KNOWLEDGE_MISSING:" + cid)
        _require("KNOWLEDGE_MANIFEST.json" in agents and
                 "knowledge_engine.py" in agents,
                 "AGENT_KNOWLEDGE_GATE_NOT_WIRED")
        _require("EXPERIMENTAL user hypothesis, not a verified hidden mechanic" not in handoff,
                 "OUTDATED_HYPOTHESIS_PHRASE_REINTRODUCED")
    return {"result": "PASS", "claims": len(claims), "evidence": len(ev),
            "trial_groups": len(trials), "original_media_persisted": False,
            "required_claim_ids": list(REQUIRED_CLAIMS),
            "claim_status": claim["status"],
            "current_run_skill_survival": "UNVERIFIED"}


def skill_guidance(state: dict[str, Any], *, root: str | Path = ".",
                   player: str | None = None, drill: str | None = None) -> dict[str, Any]:
    """Return navigation evidence, never invent a current player skill or count."""
    valid = validate_knowledge(root)
    data = load_knowledge(root)
    claim = data["claims"][FOURTH]
    _require(type(state.get("last_event_seq")) is int, "STATE_REVISION_REQUIRED")
    result = {
        "knowledge_refs": [FOURTH, ACCEPTED],
        "knowledge_status": claim["status"],
        "evidence_basis": "FOURTH_POSITIVE_AND_FIRST_THREE_NEGATIVE_REPORT",
        "observed_fourth_checkpoint": 4,
        "negative_reset_attempts_approx": 40,
        "guaranteed_skill_at_fourth": False,
        "checkpoints_apply_to": "HISTORICAL_EVIDENCE_NOT_CURRENT_COUNTERS",
        "prior_accepted_skills": data["claims"][ACCEPTED]["accepted_at_reporting"],
        "prior_skills_survive_current_save": "UNKNOWN",
        "state_event_seq": state["last_event_seq"],
        "state_timeline_status": state.get("timeline_status", "UNKNOWN"),
        "next_step": "VERIFY_CURRENT_COMMITTED_COUNT_BEFORE_TARGETING_FOURTH",
        "source_media_repository_persisted": valid["original_media_persisted"],
    }
    if player is not None or drill is not None:
        _require(isinstance(player, str) and bool(player) and
                 isinstance(drill, str) and bool(drill),
                 "PLAYER_AND_DRILL_REQUIRED_TOGETHER")
        key = player + "|" + drill
        count = state.get("training_counts_by_player_drill", {}).get(key)
        trusted = state.get("timeline_status") == "TRUSTED"
        known = trusted and type(count) is int and count >= 0
        result["player"] = player
        result["drill"] = drill
        result["committed_count_known"] = bool(known)
        result["committed_count"] = count if known else None
        result["next_ordinal"] = count + 1 if known else None
        result["is_fourth_checkpoint"] = bool(known and count == 3)
        if known and count == 3:
            result["next_step"] = "FOURTH_SESSION_CANDIDATE_VALIDATE_ACTION"
        elif known:
            result["next_step"] = "PROGRESS_TOWARD_FOURTH_WITHOUT_GUARANTEE"
    return result


def validate_skill_recommendation(rec: dict[str, Any], state: dict[str, Any],
                                  contract: dict[str, Any],
                                  *, root: str | Path = ".") -> list[str]:
    """Combine existing action gate with proof that skill advice used knowledge.

    Only explicit `claimed_fourth_checkpoint` claims require a known count of
    three completed training sessions in the CURRENT accepted branch. This
    prevents treating screenshot count or rejected rerolls as sessions.
    """
    errors = validate_recommendation(rec, state, contract)
    try:
        validate_knowledge(root)
    except KnowledgeError as exc:
        return errors + ["KNOWLEDGE_GATE:" + str(exc)]
    if (not isinstance(rec.get("knowledge_refs"), list) or
            FOURTH not in rec["knowledge_refs"]):
        errors.append("FOURTH_KNOWLEDGE_REF_REQUIRED")
    if rec.get("action_type") != "TRAIN":
        errors.append("SKILL_ADVICE_REQUIRES_TRAINING_ACTION")
    if rec.get("skill_goal") not in {"ACQUIRE", "IMPROVE_ACQUISITION_OPPORTUNITY"}:
        errors.append("SKILL_GOAL_REQUIRED")
    if rec.get("claimed_fourth_checkpoint") is True:
        player = rec.get("checkpoint_player")
        drill = rec.get("drill")
        if (not isinstance(player, str) or
                player not in rec.get("participants", []) or
                not isinstance(drill, str) or not drill):
            errors.append("FOURTH_CHECKPOINT_PLAYER_DRILL_REQUIRED")
        else:
            info = skill_guidance(state, root=root, player=player, drill=drill)
            if not info.get("committed_count_known"):
                errors.append("CURRENT_COMMITTED_COUNT_UNKNOWN")
            elif not info["is_fourth_checkpoint"]:
                errors.append("NOT_FOURTH_COMMITTED_SESSION")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge continuity and skill checkpoint")
    parser.add_argument("command", choices=["validate", "guidance"])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--state", default="CURRENT_LIVE_STATE.json")
    parser.add_argument("--player")
    parser.add_argument("--drill")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = validate_knowledge(args.root)
        else:
            state = _read_json(args.root / args.state)
            result = skill_guidance(state, root=args.root, player=args.player, drill=args.drill)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except KnowledgeError as exc:
        parser.exit(1, "KNOWLEDGE_FAIL: " + str(exc) + "\\n")


if __name__ == "__main__":
    main()
