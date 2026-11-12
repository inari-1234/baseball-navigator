"""Read present observations independently of the restored SAVE's history."""
from __future__ import annotations

import json
from pathlib import Path
import re

from live_state_engine import OBSERVED_TRACKING, has_current_lineage
from strategy_policy import context_current

ROSTER_RECORD = "ROSTER_SCREEN_CANDIDATE_20261111.json"
HISTORICAL_TRAINING_MENU_IMAGES = {
    "IMG_9036": "810b80cd1c2373b642e17124f5df747156dba10f818c17b75b11723e853243c8",
    "IMG_9037": "f9cdc0a4939f1a737346fad2420c5c2bc30cd2c8a237e7260b3954fda5f30eea",
}


def _roster_record(root):
    path = Path(root) / ROSTER_RECORD
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if (record.get("evidence_status") != "PENDING_CURRENT_SAVE_CHRONOLOGY"
            or record.get("accepted_live_event") is not False
            or not re.fullmatch(r"[0-9a-f]{64}", record["source_archive_sha256"])):
        raise ValueError("ROSTER_RECORD_INVALID")
    return record


def tracked_roster_record(state, root):
    tracking = state.get("observed_tracking")
    if (state["timeline_status"] != OBSERVED_TRACKING
            or not isinstance(tracking, dict)
            or "roster_invalidated_by_event_id" in tracking):
        return None
    record = _roster_record(root)
    if record and tracking["roster_archive_sha256"] == record["source_archive_sha256"]:
        return record
    return None


def tracked_roster(state, root):
    record = tracked_roster_record(state, root)
    return record["roster"] if record else None


def current_observations(state, root, context, evidence_sources):
    """Reuse recorded world counters and, with continuity, the uploaded roster."""
    from check_reply import ReplyGateError, _verified_evidence_receipts

    resources = state["resources"]
    observed = {
        "period": state["period_floor"],
        "clock": state["current_exact_time"],
        "counters": resources["values"] if resources["fresh"] else None,
        "counter_source_event_id": resources["last_observed"] if resources["fresh"] else None,
        "roster": None,
        "next_evidence": None,
    }
    record = _roster_record(root)
    if record:
        archive = record["source_archive_sha256"]
        roster = {
            "archive_sha256": archive,
            "screens_recorded": record["image_count"],
            "status": "STALE_OR_UNLINKED",
        }
        observed["roster"] = roster
        if tracked_roster_record(state, root):
            roster["status"] = "CURRENT_ROSTER_OBSERVATION"
            roster["players"] = record["roster"]
        elif (resources["fresh"] and record.get("reference_live_event_seq") ==
                state["last_event_seq"]):
            roster["status"] = "PENDING_SAME_SAVE_CONTINUITY"
            observed["next_evidence"] = "CONFIRM_UPLOADED_ROSTER_CONTINUITY"
            claim = context.get("roster_chronology") if isinstance(context, dict) else None
            if (context_current(claim, state)
                    and claim.get("archive_sha256") == archive
                    and claim.get("after_world_event_id") == resources["last_observed"]
                    and claim.get("same_save_no_intervening_gameplay") is True):
                try:
                    _verified_evidence_receipts(
                        context, evidence_sources, state, root,
                        claims=("roster_chronology",))
                except ReplyGateError as exc:
                    roster["continuity_error"] = str(exc)
                else:
                    roster["status"] = "CURRENT_ROSTER_OBSERVATION"
                    roster["players"] = record["roster"]
                    observed["next_evidence"] = None
    if not has_current_lineage(state) and observed["next_evidence"] is None:
        observed["next_evidence"] = (
            "RECONCILE_RESTORED_SAVE_ANCHOR" if resources["fresh"]
            else "CURRENT_WORLD_COUNTERS")
    elif state["timeline_status"] == OBSERVED_TRACKING:
        readiness = context.get("training_readiness") if isinstance(context, dict) else None
        selection = readiness.get("menu_selection") if context_current(readiness, state) else None
        if state.get("observed_tracking", {}).get("roster_invalidated_by_event_id"):
            observed["next_evidence"] = "REVIEW_CHANGED_ROSTER_CONTEXT"
        elif not resources["fresh"]:
            observed["next_evidence"] = "CURRENT_WORLD_COUNTERS"
        elif (not isinstance(selection, dict) or selection.get("available_now") is not True
              or selection.get("confirmed_immediately_before_execution") is not True
              or selection.get("same_save_no_material_change") is not True
              or not selection.get("current_balances")):
            observed["next_evidence"] = "CURRENT_SPECIAL_TRAINING_SELECTION"
    return observed


def render_observation_stop(observed, state, line):
    lines = ["現時点で表示できる攻略行動の候補はありません。"]
    if state["timeline_status"] == OBSERVED_TRACKING:
        lines.append("現在の観測から追跡中です。復元元と観測起点以前の履歴は未確定です。")
    elif not has_current_lineage(state):
        lines.append("復元元のSAVE、過去の特訓総回数、保持スキルは未確定です。")
    counters = observed["counters"]
    if counters:
        lines.append(
            f"台帳の観測記録は {observed['period']} {observed['clock']}、"
            f"勉強{counters['study']}・スポーツ{counters['sports']}・遊び{counters['play']}・"
            f"自然{counters['nature']}・応援{counters['cheer']} です。")
    if observed["roster"]:
        roster = observed["roster"]
        if roster["status"] == "CURRENT_ROSTER_OBSERVATION":
            lines.append("提出済みの選手画面を同一SAVEの現行観測として確認しました。")
        elif roster["status"] == "PENDING_SAME_SAVE_CONTINUITY":
            lines.append("提出済みの選手画面は、同一SAVEでの撮影かどうかが確認待ちです。")
    next_evidence = {
        "CONFIRM_UPLOADED_ROSTER_CONTINUITY":
            "提出済みの選手画面を、記録済みの現画面と同じSAVEで、間にゲームを進めず撮ったか確認します。画像の再提出は不要です。",
        "RECONCILE_RESTORED_SAVE_ANCHOR":
            "復元元を特定できる既存のSAVE記録を確認します。確認済みの画面や数値の再提出は不要です。",
        "CURRENT_WORLD_COUNTERS": "現在の時刻と資源カウンターを確認します。",
        "REVIEW_CHANGED_ROSTER_CONTEXT":
            "記録された状態変更以降の選手情報を確認します。",
        "CURRENT_SPECIAL_TRAINING_SELECTION":
            "実行を押さず、現行SAVEの素振り候補の選択画面で、入江ドコンジを含む3人の参加可否、応援設定、消費する資源の残高を確認します。",
        None: "候補に不足している根拠を確認するまで操作を保留します。",
    }[observed["next_evidence"]]
    return "\n".join([*lines, line, "Fallback: " + next_evidence])
