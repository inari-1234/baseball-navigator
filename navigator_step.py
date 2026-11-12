#!/usr/bin/env python3
"""P3 read-only Baseball Navigator decision orchestrator.

Combines TEXT FAST routing, current accepted-branch state, evidence-backed
knowledge, and the canonical action validator. It NEVER writes LIVE_EVENTS,
performs a game action, guarantees a skill, or treats historical measurements
as a current screen confirmation. The returned highest-priority action is
a *validated draft* only when all relevant gates actually pass.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from knowledge_engine import (
    ACCEPTED, FOURTH, KnowledgeError, validate_knowledge,
    validate_skill_recommendation,
)
from live_state_engine import validate_recommendation, training_count_status, has_current_lineage
from strategy_policy import (
    OFFENSE_RULE, TRAINING_RULES, context_current as _context_current,
    load_tactics as _load_catalog, offense_pattern, training_cost,
)
from text_fast import TextFastEngine

FAILURE_MODES = {"CONTACT", "CONVERSION", "ADEQUATE", "RECOVERY_REQUIRED", "UNKNOWN"}
RULE_BASE = ("DC-PROC-001", "DC-PROC-002", "DC-ACTION-001")
RULE_TRAIN = tuple(rule for rule in TRAINING_RULES if rule not in RULE_BASE)
RULE_MATCH = ("DC-MATCH-001",)
RULE_HP = ("DC-HP-001", "DC-ITEM-001")
FALLBACK_SAVE = "RECONCILE_ACTIVE_SAVE_ANCHOR_WITH_CURRENT_LIVE_EVIDENCE"
FALLBACK_REVIEW = "INGEST_FRESH_CURRENT_BRANCH_EVIDENCE"
FALLBACK_TRAIN = "STOP_IF_RESOURCES_HP_OR_SAVE_BRANCH_CHANGE"
FALLBACK_MATCH = "STOP_IF_MATCH_DATE_OR_ELIGIBILITY_CHANGES"
FALLBACK_RECOVERY = "STOP_IF_ITEM_INVENTORY_OR_TARGET_HP_CHANGES"


def _active_rules(contract: dict[str, Any]) -> set[str]:
    rules = contract.get("rules", [])
    if not isinstance(rules, list):
        return set()
    return {r.get("rule_id") for r in rules if isinstance(r, dict)
            and r.get("status") == "ACTIVE" and isinstance(r.get("rule_id"), str)}


def _mode_and_provenance(context: dict[str, Any], state: dict[str, Any]):
    block = context.get("failure_assessment")
    if not _context_current(block, state):
        return "UNKNOWN", [], False
    mode = block.get("mode")
    if (not isinstance(mode, str) or mode not in FAILURE_MODES
            or (mode in OFFENSE_RULE and offense_pattern(block, state) is None)):
        return "UNKNOWN", [], False
    return mode, list(block["evidence_refs"]), True


def _skills_for(player: str, drill: str, state: dict[str, Any]):
    # A partial logged count is a lower bound, not a verified fourth checkpoint.
    info = training_count_status(state, player, drill)
    exact = info["exact_committed_count"]
    return {"committed_count": exact,
            "recorded_lower_bound": info["recorded_lower_bound"],
            "count_certainty": info["count_certainty"],
            "certification_event_id": info["certification_event_id"],
            "next_ordinal": exact + 1 if exact is not None else None,
            "fourth_checkpoint": exact == 3 if exact is not None else False}


def _train_candidate(drill: dict, cheer: str, state: dict[str, Any],
                     context: dict[str, Any], contract: dict[str, Any]) -> dict:
    players = list(drill["historical_group"])
    readiness = context.get("training_readiness")
    ready_source = _context_current(readiness, state)
    groups = readiness.get("preferred_participant_groups") if ready_source else None
    override = groups.get(drill["drill"]) if isinstance(groups, dict) else None
    group_selected_from_live = (
        isinstance(override, dict)
        and isinstance(override.get("players"), list)
        and all(isinstance(player, str) for player in override["players"])
    )
    if group_selected_from_live:
        players = list(override["players"])
    cost, cost_source, cost_known = training_cost(
        drill, cheer, readiness if ready_source else {})
    rules = list(RULE_BASE + RULE_TRAIN) + [OFFENSE_RULE[drill["purpose"]]]
    skill_aim = cheer == "ON"
    info = {player: _skills_for(player, drill["drill"], state) for player in players}
    fourth_player = next((p for p in players if info[p]["fourth_checkpoint"]), None)
    recommendation = {
        "action_type": "TRAIN",
        "based_on_event_seq": state["last_event_seq"],
        "rule_ids": rules,
        "participants": players,
        "drill": drill["drill"],
        "cheer": cheer,
        "spend": cost,
        "knowledge_refs": [FOURTH] if skill_aim else [],
        "skill_goal": "ACQUIRE" if skill_aim else None,
        "claimed_fourth_checkpoint": bool(skill_aim and fourth_player),
        "checkpoint_player": fourth_player if skill_aim else None,
    }
    if skill_aim:
        errors = validate_skill_recommendation(
            recommendation, state, contract, root=context["_knowledge_root"],
            context=context)
    else:
        errors = validate_recommendation(
            recommendation, state, contract, root=context["_knowledge_root"],
            context=context)
    blocked = sorted(set(errors))
    targeted_reroll = (skill_aim and fourth_player
                       and drill["supports_skill_popup_with_cheer_on"] is True)
    return {
        "id": drill["id"] + "_" + cheer,
        "action_type": "TRAIN",
        "goal": drill["purpose"],
        "drill": drill["drill"],
        "cheer": cheer,
        "participants": players,
        "participants_are_historical_candidates": not group_selected_from_live,
        "participant_selection_basis": (
            override.get("basis") if group_selected_from_live
            else drill["group_basis"]),
        "participant_selection_evidence_refs": (
            override.get("evidence_refs", []) if group_selected_from_live else []),
        "training_readiness_evidence_refs": (
            list(readiness["evidence_refs"]) if ready_source else []),
        "historical_fit": drill["group_basis"],
        "cost": cost,
        "cost_source": cost_source,
        "cost_fully_known": cost_known,
        "target_skill_chain_candidates": list(drill["skill_chain_candidates"]),
        "target_skill": (drill["skill_chain_candidates"][0]
                         if skill_aim and drill["supports_skill_popup_with_cheer_on"] is True
                         else None),
        "target_skill_at_this_drill_not_guaranteed": True,
        "skill_popup_evidence": (drill["supports_skill_popup_with_cheer_on"]
                                 if cheer == "ON" else "UNKNOWN"),
        "accept_reload_plan": {
            "accept_if": ("TARGET_OR_HIGH_VALUE_SKILL_ACQUIRED"
                          if skill_aim and drill["supports_skill_popup_with_cheer_on"] is True
                          else "ABILITY_GAIN_MEETS_DEVELOPMENT_GOAL"),
            "reload_if": (
                "OPTIONAL_TARGETED_FOURTH_REROLL_WHEN_SAVE_AND_BUDGET_VERIFIED"
                if targeted_reroll else "NO_VERIFIED_SKILL_REROLL_TARGET"),
            "not_a_guaranteed_reward": True,
        },
        "training_observed_counts": info,
        "knowledge_refs": [FOURTH, ACCEPTED],
        "rule_ids": rules,
        "ready": not blocked,
        "blocking_reasons": blocked,
        "action_draft": recommendation if not blocked else None,
        "fallback": FALLBACK_TRAIN,
        "note": drill.get("historical_notes", ""),
    }


def _match_candidates(state: dict[str, Any], context: dict[str, Any],
                      contract: dict[str, Any]) -> list[dict]:
    candidates = []
    for mid, match in sorted(state.get("matches", {}).items()):
        if match.get("status") != "SCHEDULED":
            continue
        reasons = []
        if not has_current_lineage(state):
            reasons.append("CURRENT_SAVE_ANCHOR_UNVERIFIED")
        rules = list(RULE_BASE + RULE_MATCH) + ["DC-OFF-003"]
        rec = {"action_type": "MATCH", "based_on_event_seq": state["last_event_seq"],
               "rule_ids": rules, "target_match_id": mid,
               "target_period": match.get("period"), "spend": {}}
        reasons += validate_recommendation(rec, state, contract, context=context)
        reasons = sorted(set(reasons))
        candidates.append({
            "id": "MATCH:" + mid, "action_type": "MATCH",
            "target_match_id": mid, "opponent": match.get("opponent"),
            "period": match.get("period"), "rule_ids": rules, "knowledge_refs": [],
            "ready": not reasons, "blocking_reasons": reasons,
            "action_draft": rec if not reasons else None,
            "fallback": FALLBACK_MATCH,
            "note": "Scheduled does not mean playable now; match-day readiness is required.",
        })
    return candidates


def _recovery_candidate(state: dict[str, Any], context: dict[str, Any],
                        contract: dict[str, Any]) -> dict:
    recover = context.get("recovery")
    verified = _context_current(recover, state)
    player = recover.get("player") if verified else None
    item = recover.get("item") if verified else None
    reasons = []
    if not has_current_lineage(state):
        reasons.append("CURRENT_SAVE_ANCHOR_UNVERIFIED")
    if not verified or not isinstance(player, str) or not player or not isinstance(item, str) or not item:
        reasons.append("RECOVERY_TARGET_AND_ITEM_NOT_SOURCE_VERIFIED")
    if verified and recover.get("needed") is not True:
        reasons.append("RECOVERY_NEED_NOT_VERIFIED")
    if verified and recover.get("unlocks_high_value_action") is not True:
        reasons.append("RECOVERY_UNLOCK_NOT_VERIFIED")
    if verified and recover.get("verified_recovery_effect") is not True:
        reasons.append("ITEM_RECOVERY_EFFECT_NOT_SOURCE_VERIFIED")
    obs = state.get("hp_by_player", {}).get(player, {}) if isinstance(player, str) else {}
    if not obs or obs.get("fresh") is not True:
        reasons.append("CURRENT_TARGET_HP_UNVERIFIED")
    stock = state.get("inventory", {})
    if not stock.get("fresh") or not isinstance(stock.get("items"), dict):
        reasons.append("CURRENT_FULL_INVENTORY_UNVERIFIED")
    elif not isinstance(item, str) or stock["items"].get(item, 0) < 1:
        reasons.append("RECOVERY_ITEM_NOT_IN_STOCK")
    rules = list(RULE_BASE + RULE_HP)
    rec = {"action_type": "ITEM", "based_on_event_seq": state["last_event_seq"],
           "rule_ids": rules, "items": [{"item": item, "quantity": 1}],
           "spend": {}, "target_player": player}
    reasons += validate_recommendation(rec, state, contract)
    reasons = sorted(set(reasons))
    return {
        "id": "RECOVERY", "action_type": "ITEM", "target_player": player,
        "item": item, "rule_ids": rules, "knowledge_refs": [],
        "ready": not reasons, "blocking_reasons": reasons,
        "action_draft": rec if not reasons else None,
        "fallback": FALLBACK_RECOVERY,
        "note": "Only verified target HP, inventory and player-stated need; no item effect is inferred.",
    }


def navigator_step(message: str, *, state: dict, contract: dict,
                   boot_verified: bool, expected_event_seq: int | None = None,
                   context: dict | None = None,
                   root: str | Path = ".") -> dict[str, Any]:
    """Rank a source-grounded shortlist. A validated draft is NOT execution.

    Context is an independently *caller-reviewed* structured observation
    (not authenticated by this module). Every section must cite current
    event revision, period, accepted branch and evidence refs. No regex is
    allowed to fabricate a player's HP, a match time or an acquired skill.
    """
    root = Path(root)
    context = deepcopy(context) if isinstance(context, dict) else {}
    engine = TextFastEngine(root)
    routed = engine.plan(message, state=state, contract=contract,
                         boot_verified=boot_verified,
                         expected_event_seq=expected_event_seq)
    base = {
        "schema_version": "1.0",
        "component": "navigator_step",
        "mode": routed.get("mode"),
        "intent": routed.get("intent"),
        "source_event_seq": state.get("last_event_seq") if isinstance(state, dict) else None,
        "timeline_status": state.get("timeline_status") if isinstance(state, dict) else None,
        "action_authorized": False, "side_effects": False,
        "rule_ids": routed.get("rule_ids", []),
        "knowledge_refs": [], "candidates": [],
        "selected_candidate": None, "action_draft": None,
        "fallback": routed.get("fallback", FALLBACK_REVIEW),
        "errors": list(routed.get("errors", [])),
    }
    if routed["status"] in {"BOOT_REQUIRED", "CONTRACT_REQUIRED", "STALE_STATE_REVISION",
                             "FULL_REQUIRED", "INGEST_BEFORE_ADVICE",
                             "READ_ONLY_READY", "NEEDS_CONTEXT", "KNOWLEDGE_GATE_FAILED"}:
        return {**base, "status": routed["status"],
                "observation": routed.get("observation"),
                "requires_ingest": routed.get("requires_ingest", False)}
    if not isinstance(state, dict) or not isinstance(contract, dict):
        return {**base, "status": "BOOT_REQUIRED"}
    active = _active_rules(contract)
    if not set(RULE_BASE + RULE_TRAIN + RULE_MATCH + RULE_HP).issubset(active):
        return {**base, "status": "CONTRACT_REQUIRED",
                "errors": ["NAV_REQUIRED_RULE_INACTIVE"]}
    try:
        catalog = _load_catalog(root)
        validate_knowledge(root)
    except (KnowledgeError, ValueError) as exc:
        return {**base, "status": "KNOWLEDGE_GATE_FAILED",
                "errors": ["KNOWLEDGE_OR_CATALOG:" + str(exc)],
                "fallback": "RESTORE_REQUIRED_TACTICS_OR_EVIDENCE"}
    mode, mode_refs, mode_trusted = _mode_and_provenance(context, state)
    context["_knowledge_root"] = root  # local copy only; not written to user data
    drills = catalog["drills"]
    train = [_train_candidate(d, cheer, state, context, contract)
             for d in drills for cheer in ("ON", "OFF")]
    matches = _match_candidates(state, context, contract)
    recovery = _recovery_candidate(state, context, contract)
    candidate_list = train + matches + [recovery]
    all_by_id = {c["id"]: c for c in candidate_list}
    goal = ("SKILL" if "スキル" in message or "skill" in message.lower()
            else "OFFENSE" if any(x in message for x in ("得点", "打撃", "長打", "ミート"))
            else "GENERAL")
    preferred = {
        "CONTACT": ["TRAIN_CONTACT_ON", "TRAIN_CONTACT_OFF"],
        "CONVERSION": ["TRAIN_POWER_ON", "TRAIN_POWER_OFF"],
        "ADEQUATE": [c["id"] for c in matches],
        "RECOVERY_REQUIRED": ["RECOVERY"],
        "UNKNOWN": [],
    }[mode]
    if goal == "SKILL":
        # The only positive skill-pool example is with Cheer ON.
        preferred = [x for x in preferred if not x.endswith("_OFF")]
        if mode == "UNKNOWN":
            preferred = ["TRAIN_CONTACT_ON", "TRAIN_POWER_ON"]
    other = sorted([c["id"] for c in candidate_list if c["id"] not in preferred])
    ranked = [all_by_id[i] for i in preferred + other]
    for pos, c in enumerate(ranked):
        c["rank_group"] = "FAILURE_MODE_MATCH" if c["id"] in preferred else "ALTERNATIVE"
        c["ordinal_position_is_heuristic_not_expected_runs"] = pos + 1
    controlling = list(RULE_BASE)
    if mode in {"CONTACT", "CONVERSION"}:
        controlling += list(RULE_TRAIN)
        controlling.append("DC-OFF-001" if mode == "CONTACT" else "DC-OFF-002")
    elif mode == "ADEQUATE":
        controlling += ["DC-OFF-003", *RULE_MATCH]
    elif mode == "RECOVERY_REQUIRED":
        controlling += list(RULE_HP)
    else:
        controlling += ["DC-UNKNOWN-001"]
    if not has_current_lineage(state):
        controlling += ["DC-STATE-001", "DC-UNKNOWN-001"]
    result = {
        **base, "failure_mode": mode,
        "failure_assessment_current": mode_trusted,
        "failure_evidence_refs": mode_refs,
        "knowledge_refs": [FOURTH, ACCEPTED],
        "candidate_count": len(ranked), "candidates": ranked,
        "rule_ids": sorted(active.intersection(set(controlling))),
        "decision_goal": goal,
        "ranking_is_expected_value_estimate": False,
        "ranking_basis": "EVIDENCE_SCOPED_FAILURE_MODE_PRIORITY_NO_INVENTED_UTILITY",
    }
    if not has_current_lineage(state):
        return {**result, "status": "BLOCKED_UNVERIFIED_TIMELINE",
                "primary_next_step": "VERIFY_CURRENT_SAVE_ANCHOR",
                "fallback": FALLBACK_SAVE,
                "errors": ["ROLLBACK_SAVEPOINT_UNKNOWN_OR_UNTRUSTED_TIMELINE"],
                "provisional_target": preferred[0] if preferred else None}
    if mode == "UNKNOWN":
        return {**result, "status": "NEEDS_GROUNDED_FAILURE_ASSESSMENT",
                "primary_next_step": "CLASSIFY_CONTACT_VS_CONVERSION_FROM_ACTIVE_MATCH",
                "fallback": "IF_EVIDENCE_SHOWS_4_TO_7_HITS_AND_0_TO_1_RUN_SWITCH_TO_CONVERSION",
                "provisional_target": preferred[0] if preferred else None}
    if not preferred:
        return {**result, "status": "NEEDS_CANDIDATE",
                "primary_next_step": "CHECK_VERIFIED_AVAILABLE_ACTIONS",
                "fallback": FALLBACK_REVIEW}
    candidate = next((all_by_id[i] for i in preferred if all_by_id[i]["ready"]), None)
    if candidate is None:
        primary = all_by_id[preferred[0]]
        return {**result, "status": "BLOCKED_CANDIDATE",
                "primary_next_step": "VERIFY_CANDIDATE_CURRENT_SOURCE_GATES",
                "provisional_target": primary["id"],
                "blocking_reasons": primary["blocking_reasons"],
                "fallback": primary["fallback"]}
    # Every returned action draft was validated against the canonical validator
    # with current resources, accepted-branch skill knowledge and revision.
    return {**result, "status": "VALIDATED_DRAFT_REVIEW",
            "selected_candidate": candidate["id"],
            "action_draft": deepcopy(candidate["action_draft"]),
            "primary_next_step": candidate["id"], "rule_ids": candidate["rule_ids"],
            "fallback": candidate["fallback"],
            "requires_manual_acceptance": True,
            "action_authorized": False}


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only source-grounded next-step navigation")
    p.add_argument("message")
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--state", default="CURRENT_LIVE_STATE.json")
    p.add_argument("--contract", default="DECISION_CONTRACT.json")
    p.add_argument("--context", type=Path, help="Optional current-source verified context JSON")
    p.add_argument("--image", type=Path,
                   help="P5 local image path; inspect once without game mutation")
    p.add_argument("--image-review", type=Path,
                   help="Optional independently reviewed image-event draft JSON (never committed)")
    p.add_argument("--events", type=Path, default=Path("LIVE_EVENTS.jsonl"),
                   help="P5 canonical append-only events for review dry-run")
    p.add_argument("--expected-event-seq", type=int)
    p.add_argument("--boot-verified", action="store_true",
                   help="Set only after ordered AGENTS.md BOOT was actually checked")
    args = p.parse_args()
    try:
        state = json.loads((args.root / args.state).read_text(encoding="utf-8"))
        contract = json.loads((args.root / args.contract).read_text(encoding="utf-8"))
        context = json.loads(args.context.read_text(encoding="utf-8")) if args.context else {}
        if args.image_review is not None and args.image is None:
            raise ValueError("P5_REVIEW_REQUIRES_IMAGE")
        if args.image is not None:
            # P5 image-first path; no GitHub or network calls and no event writes.
            from quick_image_pipeline import QuickImageSession
            from live_state_engine import read_events
            session = QuickImageSession()
            picture = session.inspect(args.image)
            out = {
                "schema_version": "1.0",
                "component": "navigator_step+p5_image",
                "status": ("UNSUPPORTED_SCREEN_NEEDS_MANUAL_REVIEW"
                           if picture.get("screen_type") == "UNSUPPORTED"
                           else "IMAGE_OBSERVATION_READY"),
                "source_event_seq": state.get("last_event_seq"),
                "source_sha256": picture["source_sha256"],
                "screenshot_observation": picture,
                "action_authorized": False, "side_effects": False,
                "candidate_event_committed": False,
                "next_step": "REVIEW_ONLY_IF_NEW_STATE_FACTS_ARE_VISIBLE",
            }
            if args.image_review is not None:
                if not args.boot_verified:
                    raise ValueError("P5_BOOT_REQUIRED_FOR_EVENT_PREVIEW")
                if args.expected_event_seq != state.get("last_event_seq"):
                    raise ValueError("P5_EXACT_EXPECTED_EVENT_SEQ_REQUIRED")
                review=json.loads(args.image_review.read_text(encoding="utf-8"))
                preview=session.draft(args.image, review=review, state=state,
                                      events=read_events(args.events))
                out["status"]="UNCOMMITTED_IMAGE_EVENT_PREVIEW"
                out["event_preview"]=preview
                out["next_step"]="REVIEW_BEFORE_CANONICAL_TRANSACTION"
                out["action_authorized"]=False
                out["side_effects"]=False
        else:
            out = navigator_step(args.message, state=state, contract=contract,
                                 boot_verified=args.boot_verified,
                                 expected_event_seq=args.expected_event_seq,
                                 context=context, root=args.root)
            if out["candidates"]:
                out.update(candidates=[], selected_candidate=None, action_draft=None,
                           provisional_target=None, requires_manual_acceptance=False)
                if out["status"] == "VALIDATED_DRAFT_REVIEW":
                    out["primary_next_step"] = "RUN_NEXT_ACTION_FOR_CERTIFIED_REPLY"
    except (OSError, ValueError) as exc:
        p.exit(1, "NAVIGATOR_INPUT_ERROR: " + str(exc) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
