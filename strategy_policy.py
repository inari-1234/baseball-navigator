"""Executable checks for the existing Sapporo sprint special-training rules."""
from __future__ import annotations

import json
from pathlib import Path


OFFENSE_RULE = {"CONTACT": "DC-OFF-001", "CONVERSION": "DC-OFF-002"}
DRILL_PURPOSE = {"TRAIN_CONTACT": "CONTACT", "TRAIN_POWER": "CONVERSION"}
TRAINING_RULES = ("DC-ACTION-001", "DC-TRAIN-001", "DC-TRAIN-002", "DC-CHEER-001")
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
        if known is not None and (
                known.get("period") != state.get("period_floor")
                or not isinstance(known.get("first_attempt"), dict)
                or known["first_attempt"] != known.get("accepted_attempt")
                or known["first_attempt"].get("our_runs") != runs
                or known.get("classification") == "RESET_ASSISTED_WIN"):
            return None
        low_hits += hits <= 3
        heavy_strikeouts += sample.get("heavy_strikeouts") is True
        low_conversion += 4 <= hits <= 7 and runs <= 1
    derived = ("CONTACT" if max(low_hits, heavy_strikeouts) >= 2 else
               "CONVERSION" if low_conversion >= 2 else None)
    return derived if derived == mode else None


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
    if (not isinstance(rules, list)
            or not all(rule in rules for rule in (*TRAINING_RULES, OFFENSE_RULE[mode]))
            or any(rule.startswith("DC-OFF-") and rule != OFFENSE_RULE[mode]
                   for rule in rules if isinstance(rule, str))):
        errors.append("TRAINING_STRATEGY_RULE_MISMATCH")
    if offense_pattern(context.get("failure_assessment"), state) != mode:
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
        "checkpoint_player", "hp_claims", "hp_min_by_player",
    }:
        errors.append("UNSUPPORTED_TRAINING_FIELDS")
    return errors
