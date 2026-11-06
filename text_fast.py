#!/usr/bin/env python3
"""Deterministic TEXT FAST routing for Baseball Navigator.

This module routes short *text* turns without rereading repo history or
mutating gameplay. A route is NOT natural-language truth validation.
Actions are only drafts after the canonical recommendation validator passes.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from live_state_engine import validate_recommendation


def _normalize(message: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", message).lower().split())


# These narrow patterns are deliberate: ambiguous statements go to REVIEW,
# never to the action engine or the event log.
_DEVELOP = re.compile(
    r"(?:コード.{0,6}(?:書|作|修正|テスト)|"
    r"テスト(?:して|しよう|を実施)|"
    r"実装(?:して|しよう|を進め|する)|"
    r"(?:設計|開発)(?:して|しよう|を進め)|"
    r"ロジック.{0,8}(?:組んで|組もう|実装して)|"
    r"(?:github|main).{0,14}(?:反映|コミット|更新して))"
)
_ACTION_QUERY = re.compile(
    r"(?:どちら.{0,10}(?:優先|いい)|どっち.{0,10}(?:優先|いい)|"
    r"優先(?:すべき|した方|順位)|使うべき|使った方|"
    r"特訓すべき|試合すべき|おすすめ|何をすべき|"
    r"次(?:は|に).{0,10}(?:すべき|何する|どうする)|"
    r"勝つために|攻略(?:して|方針)|提案して)"
)
_HYPOTHETICAL = re.compile(r"(?:もし|仮に|(?:した|する)場合|(?:したら|すると|するなら|したとき)|としたら|ならば)")
_QUESTION = re.compile(
    r"(?:[?？]|どう|何(?:が|を|は|個|月|回|から|です|なの)|"
    r"教えて|確認して|知りたい|できますか|できる|でしょう|ですか|って|"
    r"どこ|どれ|なぜ|いつ|可能|済み|実装済)"
)
_EVENT_REPORT = re.compile(
    r"(?:ロールバックした|ロードした|リセットした|"
    r"勝った|負けた|引き分けた|試合.{0,9}(?:終わった|終了した)|"
    r"特訓した|練習した|(?:アイテム|チョコレート|コーヒー|鉄アレイ|声だしメガホン).{0,10}(?:使った|使用した)|"
    r"(?:スポーツ|研究|応援|所持金|体力).{0,12}(?:増えた|減った)|"
    r"は試合予定|試合は予定|(?:現在|今)は.{0,20}(?:6月|7月|8月)|"
    r"訂正(?:します|する|です)|間違って(?:いる|た))"
)
_MATERIAL = re.compile(
    r"(?:ロールバックした|ロードした|リセットした|"
    r"試合.{0,9}(?:終わった|終了した)|勝った|負けた|引き分けた|"
    r"訂正(?:します|する|です))"
)
_READ_ONLY = re.compile(
    r"(?:状態|所持|何個|予定|記録|ルール|判断ロジック|"
    r"進行|履歴|能力|今月|現在|何月|試合|アイテム|特訓|"
    r"どこ|教えて|確認|説明|どうなってる)"
)
_SHORT_CONTEXT = {"進めて", "続けて", "それで", "お願い", "はい", "ok", "go"}


@dataclass(frozen=True)
class TextRoute:
    intent: str
    mode: str
    reason: str
    requires_ingest: bool = False
    requires_full: bool = False


def classify_text(message: str) -> TextRoute:
    """Classify *intent*, not the truth or source authority of a report."""
    if not isinstance(message, str) or not message.strip():
        return TextRoute("NEEDS_CONTEXT", "REVIEW", "EMPTY_MESSAGE")
    text = _normalize(message)
    if text in _SHORT_CONTEXT:
        return TextRoute("NEEDS_CONTEXT", "REVIEW", "NO_EXPLICIT_TASK")
    if _DEVELOP.search(text):
        return TextRoute("DEVELOPMENT", "FULL", "EXPLICIT_IMPLEMENTATION",
                         requires_full=True)
    # An actual report with an appended advice request must be ingested first.
    # Conditional and interrogative descriptions do not create new events.
    report = bool(_EVENT_REPORT.search(text)) and not bool(_HYPOTHETICAL.search(text))
    if report and (not _QUESTION.search(text) or _ACTION_QUERY.search(text)):
        material = bool(_MATERIAL.search(text))
        return TextRoute("STATE_REPORT", "FULL" if material else "DELTA",
                         "MATERIAL_STATE_CHANGE" if material else "LIVE_DELTA",
                         requires_ingest=True, requires_full=material)
    if _ACTION_QUERY.search(text):
        return TextRoute("ACTION_EVALUATION", "QUICK", "NEEDS_ACTION_VALIDATION")
    if _READ_ONLY.search(text) or _QUESTION.search(text):
        return TextRoute("READ_ONLY", "QUICK", "KNOWN_INFORMATION_QUERY")
    return TextRoute("NEEDS_CONTEXT", "REVIEW", "AMBIGUOUS_UNSUPPORTED_TEXT")


class TextFastEngine:
    """Cache only immutable text *routing*. Never cache a game action approval.

    The caller supplies BOOT-complete canonical state and contract; neither is
    fetched by this library. Every plan checks the current revision again.
    """

    def __init__(self) -> None:
        self._route_cache: dict[str, TextRoute] = {}
        self.route_hits = 0
        self.route_misses = 0
        self.action_validator_calls = 0

    def _route(self, message: str) -> TextRoute:
        key = _normalize(message) if isinstance(message, str) else ""
        if key in self._route_cache:
            self.route_hits += 1
            return self._route_cache[key]
        route = classify_text(message)
        self._route_cache[key] = route
        self.route_misses += 1
        return route

    def plan(self, message: str, *, state: dict[str, Any] | None,
             contract: dict[str, Any] | None, boot_verified: bool,
             expected_event_seq: int | None = None,
             recommendation: dict[str, Any] | None = None) -> dict[str, Any]:
        route = self._route(message)
        base = {
            "intent": route.intent, "mode": route.mode,
            "reason": route.reason, "requires_ingest": route.requires_ingest,
            "requires_full": route.requires_full,
            "rule_ids": [], "status": "NEEDS_REVIEW",
            "errors": [], "action_authorized": False,
            "side_effects": False, "fallback": "RECHECK_SOURCE_AND_STATE",
        }
        if (not boot_verified or not isinstance(state, dict)
                or not isinstance(contract, dict)
                or type(state.get("last_event_seq")) is not int
                or not isinstance(contract.get("rules"), list)):
            return {**base, "status": "BOOT_REQUIRED",
                    "errors": ["REQUIRED_AUTHORITY_UNVERIFIED"]}
        seq = state["last_event_seq"]
        active = {r.get("rule_id") for r in contract["rules"]
                  if isinstance(r, dict) and r.get("status") == "ACTIVE"}
        if not {"DC-PROC-001", "DC-PROC-002", "DC-ACTION-001"}.issubset(active):
            return {**base, "status": "CONTRACT_REQUIRED",
                    "errors": ["FAST_RULES_NOT_ACTIVE"]}
        base["state_revision"] = seq
        base["rule_ids"] = ["DC-PROC-001", "DC-PROC-002"]
        if (expected_event_seq is not None and
                (type(expected_event_seq) is not int or expected_event_seq != seq)):
            return {**base, "status": "STALE_STATE_REVISION",
                    "errors": ["STALE_REVISION"]}
        if route.intent == "DEVELOPMENT":
            return {**base, "status": "FULL_REQUIRED",
                    "fallback": "RUN_BRANCH_TESTS_AND_GUARD"}
        if route.requires_ingest:
            return {**base, "status": "INGEST_BEFORE_ADVICE",
                    "rule_ids": base["rule_ids"] + ["DC-INGEST-001", "DC-STATE-001"],
                    "fallback": "VERIFY_SOURCE_BRANCH_AND_REPLAY"}
        if route.intent == "READ_ONLY":
            # Source facts can be discussed; that does not authorize a game
            # action, and the model must still distinguish stale/UNKNOWN facts.
            return {**base, "status": "READ_ONLY_READY",
                    "fallback": "MARK_UNKNOWN_FIELDS"}
        if route.intent != "ACTION_EVALUATION":
            return {**base, "status": "NEEDS_CONTEXT"}
        base["rule_ids"] = base["rule_ids"] + ["DC-ACTION-001"]
        status = state.get("timeline_status")
        if status != "TRUSTED":
            return {**base, "status": "BLOCKED_UNVERIFIED_TIMELINE",
                    "errors": ["UNVERIFIED_TIMELINE:" + str(status)],
                    "fallback": "VERIFY_ACTIVE_SAVE_BRANCH"}
        if recommendation is None:
            return {**base, "status": "NEEDS_VALIDATED_CANDIDATE",
                    "fallback": "GATHER_ACTION_COST_AND_TARGET"}
        # Validate every request, including repeats. The classifier cache
        # cannot cache this result and cannot bypass inventory/HP/period checks.
        self.action_validator_calls += 1
        errors = validate_recommendation(recommendation, state, contract)
        if errors:
            return {**base, "status": "ACTION_BLOCKED",
                    "errors": errors,
                    "fallback": "CORRECT_INVALID_OR_STALE_ACTION"}
        return {**base, "status": "ACTION_DRAFT_REVIEW",
                "action_authorized": False,
                "requires_manual_acceptance": True,
                "rule_ids": sorted(set(base["rule_ids"] + recommendation["rule_ids"])),
                "fallback": "STOP_IF_STATE_CHANGES"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe text turn routing only")
    parser.add_argument("text")
    parser.add_argument("--state", default="CURRENT_LIVE_STATE.json")
    parser.add_argument("--contract", default="DECISION_CONTRACT.json")
    parser.add_argument("--boot-verified", action="store_true",
                        help="Set only after ordered AGENTS.md BOOT verification")
    parser.add_argument("--expected-event-seq", type=int)
    parser.add_argument("--recommendation", type=Path,
                        help="Optional JSON action draft; never executed")
    args = parser.parse_args()
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    rec = (json.loads(args.recommendation.read_text(encoding="utf-8"))
           if args.recommendation is not None else None)
    result = TextFastEngine().plan(
        args.text, state=state, contract=contract,
        boot_verified=args.boot_verified,
        expected_event_seq=args.expected_event_seq,
        recommendation=rec)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
