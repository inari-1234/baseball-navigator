"""Read present observations independently of the restored SAVE's history."""
from __future__ import annotations

import json
from pathlib import Path
import re

from strategy_policy import context_current

ROSTER_RECORD = "ROSTER_SCREEN_CANDIDATE_20261111.json"


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
    path = Path(root) / ROSTER_RECORD
    if path.is_file():
        record = json.loads(path.read_text(encoding="utf-8"))
        archive = record["source_archive_sha256"]
        if (record.get("evidence_status") != "PENDING_CURRENT_SAVE_CHRONOLOGY"
                or record.get("accepted_live_event") is not False
                or not re.fullmatch(r"[0-9a-f]{64}", archive)):
            raise ValueError("ROSTER_RECORD_INVALID")
        roster = {
            "archive_sha256": archive,
            "screens_recorded": record["image_count"],
            "status": "STALE_OR_UNLINKED",
        }
        observed["roster"] = roster
        if (resources["fresh"] and record.get("reference_live_event_seq") ==
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
    if state["timeline_status"] != "TRUSTED" and observed["next_evidence"] is None:
        observed["next_evidence"] = (
            "RECONCILE_RESTORED_SAVE_ANCHOR" if resources["fresh"]
            else "CURRENT_WORLD_COUNTERS")
    return observed


def render_observation_stop(observed, state, line):
    lines = ["現時点で表示できる攻略行動の候補はありません。"]
    if state["timeline_status"] != "TRUSTED":
        lines.append("復元元のSAVE、過去の特訓総回数、保持スキルは未確定です。")
    counters = observed["counters"]
    if counters:
        lines.append(
            f"現画面の記録は {observed['period']} {observed['clock']}、"
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
        None: "候補に不足している根拠を確認するまで操作を保留します。",
    }[observed["next_evidence"]]
    return "\n".join([*lines, line, "Fallback: " + next_evidence])
