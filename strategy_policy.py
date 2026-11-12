"""Executable checks for the existing Sapporo sprint special-training rules."""
from __future__ import annotations

import json
from pathlib import Path


OFFENSE_RULE = {"CONTACT": "DC-OFF-001", "CONVERSION": "DC-OFF-002"}
DRILL_PURPOSE = {"TRAIN_CONTACT": "CONTACT", "TRAIN_POWER": "CONVERSION"}
TRAINING_RULES = ("DC-ACTION-001", "DC-TRAIN-001", "DC-TRAIN-002", "DC-CHEER-001")
DEVELOPMENT_BASIS = "OCTOBER_CORE_DEVELOPMENT"
DEVELOPMENT_ROLES = {"CONTACT": "GET_ON_BASE", "CONVERSION": "ADVANCE_RUNNERS_WITH_POWER"}
DEVELOPMENT_CHEER = {
    "ON": {"COMMIT_HIGH_VALUE_GROWTH"},
    "OFF": {"PRESERVE_FOR_NAMED_SPRINT_USE", "PROGRESS_DRILL"},
}
PARTICIPANT_FACTORS = {
    "mandatory_core_need", "low_level_efficiency", "drill_fit_current_ability",
    "growth", "type_affinity_bonus", "Y1_October_lineup_contribution",
}
CHEER_PURPOSES = {
    "ON": {"HIGH_VALUE_COMMITTED_DEVELOPMENT"},
    "OFF": {"DRILL_PROGRESSION", "RESOURCE_PRESERVATION"},
}


def context_current(block, state):
    """Check the scope of a reviewed claim. The reply gate checks its sources."""
    return (isinstance(block, dict)
            and block.get("verified_for_current_state") is True
            and type(block.get("source_event_seq")) is int
            and block["source_event_seq"] == state["last_event_seq"]
            and block.get("period") == state.get("period_floor")
            and block.get("branch") == "ACCEPTED"
            and isinstance(block.get("evidence_refs"), list)
            and bool(block["evidence_refs"])
            and all(isinstance(ref, str) and ref.strip()
                    for ref in block["evidence_refs"])
            and len(set(block["evidence_refs"])) == len(block["evidence_refs"]))


def load_tactics(root):
    root = Path(root)
    try:
        catalog = json.loads((root / "NAV_TACTICS.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("NAV_TACTICS_UNAVAILABLE") from exc
    if (not isinstance(catalog, dict) or catalog.get("schema_version") != "1.0"
            or not isinstance(catalog.get("drills"), list)):
        raise ValueError("NAV_TACTICS_INVALID")
    by_id = {}
    for entry in catalog["drills"]:
        if (not isinstance(entry, dict)
                or not isinstance(entry.get("id"), str) or entry["id"] not in DRILL_PURPOSE
                or entry.get("purpose") != DRILL_PURPOSE[entry["id"]]
                or type(entry.get("sports_cost")) is not int or entry["sports_cost"] <= 0
                or not isinstance(entry.get("drill"), str) or not entry["drill"]
                or not isinstance(entry.get("historical_group"), list)
                or len(entry["historical_group"]) != 3
                or not all(isinstance(player, str) for player in entry["historical_group"])
                or len(set(entry["historical_group"])) != 3
                or not isinstance(entry.get("skill_chain_candidates"), list)
                or not entry["skill_chain_candidates"]
                or not all(isinstance(skill, str) and skill
                           for skill in entry["skill_chain_candidates"])
                or entry.get("cost_basis") != "HISTORICAL_EXPLICIT_MEASUREMENT"
                or not isinstance(entry.get("group_basis"), str)
                or entry.get("supports_skill_popup_with_cheer_on") not in (True, "UNKNOWN")):
            raise ValueError("NAV_TACTICS_INVALID_DRILL")
        cheer = entry.get("cheer_on_cost")
        if cheer is not None and (type(cheer) is not int or cheer <= 0):
            raise ValueError("NAV_TACTICS_INVALID_CHEER_COST")
        drill_id = entry["id"]
        if drill_id in by_id:
            raise ValueError("NAV_TACTICS_INVALID_DRILL")
        by_id[drill_id] = entry
    if set(by_id) != set(DRILL_PURPOSE):
        raise ValueError("NAV_TACTICS_REQUIRED_DRILLS_MISSING")
    try:
        manifest = json.loads((root / "KNOWLEDGE_MANIFEST.json").read_text(encoding="utf-8"))
        expected = manifest["required_navigation_tactics"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("NAV_TACTICS_MANIFEST_MISSING") from exc
    if not isinstance(expected, dict) or set(expected) != set(by_id):
        raise ValueError("NAV_TACTICS_MANIFEST_INVALID")
    for drill_id, entry in by_id.items():
        required = expected[drill_id]
        if (not isinstance(required, dict)
                or not {"drill", "sports_cost", "cheer_on_cost", "historical_group"}.issubset(required)
                or any(entry.get(field) != value for field, value in required.items())):
            raise ValueError("NAV_TACTICS_SOURCE_INTEGRITY_MISMATCH:" + drill_id)
    return catalog


def offense_pattern(assessment, state):
    """Apply the contract thresholds to reviewed, distinct first-attempt games."""
    if not context_current(assessment, state):
        return None
    mode = assessment.get("mode")
    samples = assessment.get("match_samples")
    if not isinstance(mode, str) or mode not in OFFENSE_RULE or not isinstance(samples, list):
        return None
    low_hits = heavy_strikeouts = low_conversion = 0
    seen = set()
    for sample in samples:
        if not isinstance(sample, dict):
            return None
        mid, hits, runs = (sample.get(key) for key in ("match_id", "hits", "runs"))
        if (not isinstance(mid, str) or not mid.strip() or mid in seen
                or sample.get("evidence_ref") not in assessment["evidence_refs"]
                or sample.get("first_attempt") is not True
                or sample.get("opponent_role") not in ("FARM", "BENCHMARK")
                or type(hits) is not int or hits < 0
                or type(runs) is not int or runs < 0):
            return None
        seen.add(mid)
        known = state.get("matches", {}).get(mid)
        if (not isinstance(known, dict) or known.get("status") != "PLAYED"
                or known.get("period") != state.get("period_floor")
                or not isinstance(known.get("first_attempt"), dict)
                or known["first_attempt"] != known.get("accepted_attempt")
                or known["first_attempt"].get("attempt") != 1
                or known["first_attempt"].get("our_runs") != runs
                or known.get("classification") == "RESET_ASSISTED_WIN"):
            return None
        low_hits += hits <= 3
        heavy_strikeouts += sample.get("heavy_strikeouts") is True
        low_conversion += 4 <= hits <= 7 and runs <= 1
    derived = ("CONTACT" if max(low_hits, heavy_strikeouts) >= 2 else
               "CONVERSION" if low_conversion >= 2 else None)
    return derived if derived == mode else None


def development_plan_errors(plan, spec, rec, state, context, root):
    """Review one October-core ability session at the current roster origin."""
    from current_observation import tracked_roster

    if not context_current(plan, state):
        return ["CURRENT_OCTOBER_DEVELOPMENT_PLAN_REQUIRED"]
    errors = []
    assessment = context.get("failure_assessment")
    if assessment is not None and (not isinstance(assessment, dict)
            or assessment.get("mode") != "UNKNOWN" or assessment.get("match_samples")):
        errors.append("DEVELOPMENT_REQUIRES_UNASSESSED_OFFENSE")
    origin = state.get("observed_tracking", {})
    roster = tracked_roster(state, root)
    players = rec.get("participants")
    target = plan.get("target_player")
    lineup = {row["player"] for row in roster or [] if not row["bench"]}
    names = {row["player"] for row in roster or []}
    if (not roster or plan.get("roster_origin_event_id") != origin.get("start_event_id")
            or plan.get("roster_archive_sha256") != origin.get("roster_archive_sha256")
            or not isinstance(target, str) or target not in lineup
            or not isinstance(players, list) or target not in players
            or any(not isinstance(player, str) or player not in names for player in players)):
        errors.append("CURRENT_OCTOBER_ROSTER_NOT_BOUND")
    if (plan.get("drill") != spec["drill"] or plan.get("cheer") != rec.get("cheer")
            or plan.get("october_role") != DEVELOPMENT_ROLES[spec["purpose"]]
            or plan.get("target_role") != "CORE_DEVELOP"):
        errors.append("OCTOBER_DEVELOPMENT_DRILL_FIT_UNVERIFIED")
    player_observation = plan.get("player_observation")
    image_refs = plan.get("roster_image_evidence_refs")
    if (not isinstance(image_refs, list) or not image_refs
            or any(not isinstance(ref, str) or ref not in plan["evidence_refs"] for ref in image_refs)
            or not isinstance(player_observation, dict)
            or player_observation.get("player") != target
            or player_observation.get("evidence_ref") not in image_refs
            or any(type(player_observation.get(stat)) is not int or player_observation[stat] < 0
                   for stat in ("contact", "slugging"))):
        errors.append("CURRENT_PLAYER_BATTING_OBSERVATION_REQUIRED")
    reasons = plan.get("priority_review")
    cheer = rec.get("cheer")
    if (not isinstance(cheer, str) or not isinstance(reasons, dict)
            or reasons.get("timing") != "LOW_LEVEL_CORE_BEFORE_MASS_MATCH_LEVELING"
            or reasons.get("other_drill") not in ("LOWER_PRIORITY_FOR_REVIEWED_OCTOBER_ROLE",
                                                   "DOES_NOT_SERVE_REVIEWED_OCTOBER_ROLE")
            or not isinstance(reasons.get("cheer_tradeoff"), str)
            or reasons["cheer_tradeoff"] not in DEVELOPMENT_CHEER.get(cheer, ())
            or any(not isinstance(reasons.get(key), str) or not reasons[key].strip()
                   for key in ("role_and_drill_fit", "why_before_alternatives", "cheer_reason"))):
        errors.append("OCTOBER_PRIORITY_NOT_JUSTIFIED")
    if (rec.get("skill_goal") is not None or rec.get("claimed_fourth_checkpoint") is not False
            or rec.get("checkpoint_player") is not None):
        errors.append("DEVELOPMENT_DOES_NOT_CERTIFY_SKILL_CHECKPOINT")
    readiness = context.get("training_readiness")
    menu_ref = readiness.get("menu_evidence_ref") if isinstance(readiness, dict) else None
    selection = readiness.get("menu_selection") if isinstance(readiness, dict) else None
    if (not context_current(readiness, state) or not isinstance(menu_ref, str)
            or menu_ref not in readiness["evidence_refs"]
            or not isinstance(selection, dict)
            or selection.get("drill") != spec["drill"] or selection.get("cheer") != cheer
            or selection.get("players") != players or selection.get("available_now") is not True):
        errors.append("CURRENT_SPECIAL_TRAINING_MENU_EVIDENCE_REQUIRED")
    else:
        if (selection.get("confirmed_immediately_before_execution") is not True
                or selection.get("same_save_no_material_change") is not True):
            errors.append("CURRENT_TRAINING_MENU_NOT_IMMEDIATE")
        if "displayed_spend" in selection:
            shown, spend = selection["displayed_spend"], rec.get("spend")
            if (not isinstance(shown, dict) or not shown or not isinstance(spend, dict)
                    or any(type(value) is not int or spend.get(key) != value
                           for key, value in shown.items())):
                errors.append("CURRENT_MENU_COST_MISMATCH")
    return errors


def training_cost(spec, cheer, readiness):
    cost = {"sports": spec["sports_cost"]}
    source = spec["cost_basis"]
    if cheer == "ON":
        amount = spec.get("cheer_on_cost")
        if amount is None:
            observed = readiness.get("cheer_on_costs")
            amount = observed.get(spec["drill"]) if isinstance(observed, dict) else None
            source = "CURRENT_SOURCE_ATTESTED_PLUS_HISTORICAL_SPORTS"
        if type(amount) is not int or amount <= 0:
            return cost, source, False
        cost["cheer"] = amount
    return cost, source, spec["cost_basis"] == "HISTORICAL_EXPLICIT_MEASUREMENT"


def training_strategy_errors(rec, state, context, root):
    context = context if isinstance(context, dict) else {}
    try:
        catalog = load_tactics(root)
    except ValueError:
        return ["TRAINING_TACTICS_UNAVAILABLE"]
    spec = next((item for item in catalog["drills"]
                 if item["drill"] == rec.get("drill")), None)
    if spec is None:
        return ["UNSUPPORTED_TRAINING_DRILL"]
    errors = []
    mode = spec["purpose"]
    rules = rec.get("rule_ids")
    development = rec.get("decision_basis") == DEVELOPMENT_BASIS
    if not development and rec.get("decision_basis") is not None:
        errors.append("TRAINING_DECISION_BASIS_UNSUPPORTED")
    required_rule = "DC-ROSTER-001" if development else OFFENSE_RULE[mode]
    if (not isinstance(rules, list)
            or not all(rule in rules for rule in (*TRAINING_RULES, required_rule))
            or any(rule.startswith("DC-OFF-") and rule != required_rule
                   for rule in rules if isinstance(rule, str))):
        errors.append("TRAINING_STRATEGY_RULE_MISMATCH")
    if development:
        errors.extend(development_plan_errors(
            context.get("development_plan"), spec, rec, state, context, root))
    elif offense_pattern(context.get("failure_assessment"), state) != mode:
        errors.append("TRAINING_FAILURE_MODE_NOT_SUPPORTED")
    readiness = context.get("training_readiness")
    if not context_current(readiness, state):
        return errors + ["CURRENT_TRAINING_READINESS_SOURCE_MISSING_OR_STALE"]
    drill, cheer = spec["drill"], rec.get("cheer")
    drills, ready_players = readiness.get("available_drills"), readiness.get("ready_players")
    players = rec.get("participants")
    if not isinstance(drills, list) or drill not in drills:
        errors.append("DRILL_AVAILABILITY_UNVERIFIED")
    if (not isinstance(players, list) or not isinstance(ready_players, list)
            or any(player not in ready_players for player in players)):
        errors.append("CURRENT_PLAYER_HP_OR_ELIGIBILITY_UNVERIFIED")
    if (not isinstance(players, list)
            or not all(isinstance(player, str) and player.isprintable() and player.strip()
                       for player in players)):
        errors.append("INVALID_TRAINING_PARTICIPANT_NAME")
    groups = readiness.get("preferred_participant_groups")
    group = groups.get(drill) if isinstance(groups, dict) else None
    factors = group.get("factors_reviewed") if isinstance(group, dict) else None
    refs = group.get("evidence_refs") if isinstance(group, dict) else None
    if (not isinstance(group, dict) or group.get("players") != players
            or not isinstance(group.get("basis"), str) or not group["basis"].strip()
            or not isinstance(factors, list)
            or not all(isinstance(factor, str) for factor in factors)
            or set(factors) != PARTICIPANT_FACTORS
            or not isinstance(refs, list) or not refs
            or any(ref not in readiness["evidence_refs"] for ref in refs)
            or group.get("opportunity_cost_favorable") is not True):
        errors.append("LIVE_PARTICIPANT_GROUP_OVERRIDE_NOT_VERIFIED")
    purposes = readiness.get("cheer_purposes")
    drill_purposes = purposes.get(drill) if isinstance(purposes, dict) else None
    purpose = drill_purposes.get(cheer) if isinstance(drill_purposes, dict) and isinstance(cheer, str) else None
    if (not isinstance(purpose, str) or not isinstance(cheer, str)
            or purpose not in CHEER_PURPOSES.get(cheer, ())):
        errors.append("CHEER_STRATEGY_NOT_VERIFIED")
    if development:
        plan = context.get("development_plan")
        review = plan.get("priority_review") if isinstance(plan, dict) else None
        tradeoff = review.get("cheer_tradeoff") if isinstance(review, dict) else None
        expected_purpose = {
            "COMMIT_HIGH_VALUE_GROWTH": "HIGH_VALUE_COMMITTED_DEVELOPMENT",
            "PRESERVE_FOR_NAMED_SPRINT_USE": "RESOURCE_PRESERVATION",
            "PROGRESS_DRILL": "DRILL_PROGRESSION",
        }
        if not isinstance(tradeoff, str) or expected_purpose.get(tradeoff) != purpose:
            errors.append("CHEER_PRIORITY_REVIEW_MISMATCH")
    cost, _, known = training_cost(spec, cheer, readiness)
    if not known:
        errors.append("EXACT_CHEER_ON_COST_UNVERIFIED")
    elif rec.get("spend") != cost:
        errors.append("CATALOG_TRAINING_COST_MISMATCH")
    if rec.get("skill_goal") is not None and cheer != "ON":
        errors.append("SKILL_TARGET_REQUIRES_CHEER_ON")
    if set(rec) - {
        "action_type", "based_on_event_seq", "rule_ids", "participants", "drill",
        "cheer", "spend", "knowledge_refs", "skill_goal", "claimed_fourth_checkpoint",
        "checkpoint_player", "hp_claims", "hp_min_by_player", "decision_basis",
    }:
        errors.append("UNSUPPORTED_TRAINING_FIELDS")
    return errors
