#!/usr/bin/env python3
"""P5 fast screenshot review -> source-linked, *uncommitted* event preview.

No GitHub, iOS or network calls. No automatic Japanese OCR. No updates to
LIVE_EVENTS.jsonl or CURRENT_LIVE_STATE.json. The review side is explicitly
human-attested; Python validates linkage and event replay, NOT visual truth
of unrecognized resource numbers or SAVE-point provenance.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import Any

from live_state_engine import ObservationError, replay, read_events, clock_minutes
from screen_reader import read_image, propose_hp_event

COUNTERS = ("study", "sports", "play", "nature", "cheer")
SCREENS_FOR_MANUAL_RESOURCE_ENTRY = {"WORLD_UI_OR_OVERLAY", "TOURNAMENT_LIST"}
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SOURCE_BYTES = 40 * 1024 * 1024
MAX_CACHE = 8


class QuickImageError(ValueError):
    pass


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise QuickImageError(code)


def _source(path: str | Path) -> tuple[Path, str]:
    path = Path(path)
    _need(path.is_file() and not path.is_symlink(), "IMAGE_MISSING_OR_SYMLINK")
    _need(path.suffix.lower() in SUPPORTED_FORMATS, "UNSUPPORTED_IMAGE_FORMAT")
    try:
        stat = path.stat()
        _need(0 < stat.st_size <= MAX_SOURCE_BYTES, "INVALID_IMAGE_SIZE_BYTES")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QuickImageError("IMAGE_UNREADABLE") from exc
    return path, digest


def _compact(reading: dict[str, Any]) -> dict[str, Any]:
    category = reading.get("screen_type", "UNSUPPORTED")
    summary = {
        "screen_type": category,
        "image_size": reading.get("image_size"),
        "source": deepcopy(reading.get("source", {})),
        "proposed_game_mutation": False,
        "action_authorized": False,
        "unverified_game_time": True,
        "unverified_active_save_branch": True,
        "human_review_required_for_ingestion": True,
    }
    if category == "FORMATION":
        summary["hp_graphics"] = {
            name: {
                "graphical_fill_percent": entry.get("fill_percent"),
                "numeric_game_hp_percent": None,
                "player_name": None,
                "reading_kind": "VERTICAL_BAR",
            }
            for name, entry in reading.get("positions", {}).items()
        }
        summary["next_review"] = "VERIFY_VISIBLE_PLAYER_NAMES_AND_CHRONOLOGY"
    elif category == "ITEM_USE_MENU":
        panel = deepcopy(reading.get("item_use_page", {}))
        summary["item_use"] = {
            "status": panel.get("status"),
            "selected_item_name": panel.get("selected_item_name"),
            "selected_item_stock": panel.get("selected_item_stock"),
            "full_inventory_verified": False,
            "item_use_confirmed": False,
            "stock_scope": panel.get("stock_scope"),
        }
        summary["next_review"] = "DO_NOT_INTERPRET_SLOT_DENOMINATORS_AS_INVENTORY"
    elif category in {"BATTER_RESULTS", "PITCHER_RESULTS"}:
        key = "batter_stats" if category == "BATTER_RESULTS" else "pitcher_stats"
        stats = deepcopy(reading.get(key, {}))
        summary["result_panel"] = {
            "status": stats.get("status"),
            "page": stats.get("page"),
            "rows": stats.get("rows"),
            "team_total": stats.get("team_total"),
            "fields": stats.get("fields"),
            "errors": stats.get("errors", []),
            "match_id_verified": False,
            "player_names_verified": False,
        }
        summary["next_review"] = "VERIFY_MATCH_AND_PAGE_ASSOCIATION"
    elif category == "ROSTER_LIST":
        summary["roster_page"] = deepcopy(reading.get("roster_page", {}))
        summary["next_review"] = "VERIFY_PLAYER_IDENTITY_BEFORE_RECOMMENDING_TRAINING"
    else:
        summary["next_review"] = "INSPECT_VISIBLE_FIELDS_MANUALLY"
    return summary


class QuickImageSession:
    """Read each unique image only once; hash again on every reuse.

    A per-process content-hash cache cannot permanently persist user images.
    New or modified bytes always cause a new decode, and a reused digest with
    a different filename has its provenance filename corrected.
    """

    def __init__(self, max_cache: int = MAX_CACHE):
        if type(max_cache) is not int or max_cache < 1 or max_cache > 64:
            raise QuickImageError("INVALID_CACHE_LIMIT")
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.max_cache = max_cache
        self.read_calls = 0
        self.cache_hits = 0

    def inspect(self, image_path: str | Path) -> dict[str, Any]:
        start = time.perf_counter_ns()
        path, digest = _source(image_path)
        if digest in self._cache:
            self.cache_hits += 1
            reading = deepcopy(self._cache[digest])
            reading["source"]["filename"] = path.name
            self._cache.move_to_end(digest)
            from_cache = True
        else:
            try:
                reading = read_image(path)
            except (OSError, ValueError, SyntaxError) as exc:
                raise QuickImageError("IMAGE_DECODE_FAILED") from exc
            _need(reading.get("source", {}).get("sha256") == digest,
                  "IMAGE_CHANGED_DURING_DECODE")
            self.read_calls += 1
            self._cache[digest] = deepcopy(reading)
            self._cache.move_to_end(digest)
            while len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
            from_cache = False
        summary = _compact(reading)
        summary["cache_hit"] = from_cache
        summary["source_sha256"] = digest
        summary["local_elapsed_ms"] = round(
            (time.perf_counter_ns() - start) / 1_000_000, 3)
        summary["local_measurement_only"] = True
        return summary

    def draft(self, image_path: str | Path, *, review: dict[str, Any],
              state: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        """Simulate a grounded event with replay. Never write to the ledger."""
        observed = self.inspect(image_path)
        reading = deepcopy(self._cache[observed["source_sha256"]])
        reading["source"]["filename"] = Path(image_path).name
        _need(isinstance(review, dict), "REVIEW_OBJECT_REQUIRED")
        kind = review.get("kind")
        _need(kind in {"SCREEN", "HP_OBSERVATION"}, "UNSUPPORTED_DRAFT_EVENT_KIND")
        allowed = {
            "kind", "schema_version", "reviewed_image_sha256", "expected_event_seq",
            "period", "branch", "after_event_id", "source_reviewed_current",
            "event_id", "clock",
        }
        if kind == "SCREEN":
            allowed |= {"resources", "money_yen", "all_resource_values_verified_in_image"}
        else:
            allowed |= {"verified_slot_players"}
        _need(set(review) == allowed - (
            {"money_yen"} if kind == "SCREEN" and "money_yen" not in review else set()
        ) - ({"clock"} if kind == "HP_OBSERVATION" and "clock" not in review else set()),
              "REVIEW_FIELDS_NOT_ALLOWLISTED")
        _need(review.get("schema_version") == "1.0", "REVIEW_SCHEMA_INVALID")
        _need(review.get("reviewed_image_sha256") == observed["source_sha256"],
              "SOURCE_IMAGE_HASH_MISMATCH")
        _need(type(review.get("expected_event_seq")) is int and
              review["expected_event_seq"] == state.get("last_event_seq"),
              "STALE_STATE_REVISION")
        _need(isinstance(events, list) and len(events) == state["last_event_seq"]
              and all(type(e.get("seq")) is int and e["seq"] == i + 1
                      for i, e in enumerate(events)),
              "BASELINE_EVENTS_OUT_OF_SYNC")
        base = replay(events)
        _need(base == state, "CANONICAL_STATE_PROJECTION_MISMATCH")
        _need(review.get("branch") == "ACCEPTED" and
              review.get("source_reviewed_current") is True,
              "CURRENT_ACCEPTED_SOURCE_ATTESTATION_REQUIRED")
        p = review.get("period")
        _need(isinstance(p, dict) and set(p) == {"year", "month"} and
              type(p["year"]) is int and p["year"] >= 1 and
              type(p["month"]) is int and 1 <= p["month"] <= 12,
              "INVALID_CURRENT_PERIOD")
        after = review.get("after_event_id")
        _need(isinstance(after, str) and after in {e["event_id"] for e in events},
              "VERIFIED_CHRONOLOGY_ANCHOR_REQUIRED")
        event_id = review.get("event_id")
        _need(isinstance(event_id, str) and
              event_id.startswith("P5-") and len(event_id) <= 100 and
              event_id not in {e["event_id"] for e in events},
              "FRESH_EVENT_ID_REQUIRED")
        source = {
            "kind": "RAW_SCREEN",
            "locator": reading["source"]["filename"] + "#sha256=" +
                       reading["source"]["sha256"],
        }
        if kind == "SCREEN":
            _need(reading.get("screen_type") in SCREENS_FOR_MANUAL_RESOURCE_ENTRY,
                  "RESOURCE_SCREEN_LAYOUT_NOT_SUPPORTED_BY_P5")
            _need(review.get("all_resource_values_verified_in_image") is True,
                  "RESOURCE_VALUES_NOT_SOURCE_VERIFIED")
            values = review.get("resources")
            _need(isinstance(values, dict) and set(values) == set(COUNTERS)
                  and all(type(values[key]) is int and values[key] >= 0
                          for key in COUNTERS), "INCOMPLETE_OR_INVALID_RESOURCE_COUNTERS")
            clock = review.get("clock")
            _need(isinstance(clock, str) and clock_minutes(clock) is not None,
                  "CURRENT_CLOCK_NOT_VERIFIED")
            event = {
                "seq": len(events) + 1, "event_id": event_id, "kind": "SCREEN",
                "period": deepcopy(p), "clock": clock, "source": source,
                "branch": "ACCEPTED", "resources": deepcopy(values),
                "after_event_id": after,
            }
            if "money_yen" in review:
                money = review["money_yen"]
                _need(type(money) is int and money >= 0, "INVALID_MONEY")
                event["money_yen"] = money
        else:
            _need(reading.get("screen_type") == "FORMATION",
                  "HP_SOURCE_NOT_FORMATION")
            verified_names = review.get("verified_slot_players")
            _need(isinstance(verified_names, dict) and bool(verified_names) and
                  len(set(verified_names.values())) == len(verified_names),
                  "VERIFIED_UNIQUE_SLOT_PLAYERS_REQUIRED")
            try:
                event = propose_hp_event(
                    reading, verified_names, event_id=event_id,
                    seq=len(events)+1, year=p["year"], month=p["month"],
                    after_event_id=after,
                )
            except ValueError as exc:
                raise QuickImageError("HP_EVENT_PROPOSAL_INVALID") from exc
            if "clock" in review:
                clock = review["clock"]
                _need(isinstance(clock, str) and clock_minutes(clock) is not None,
                      "CURRENT_CLOCK_NOT_VERIFIED")
                event["clock"] = clock
        try:
            proposed = replay(events + [event])
        except ObservationError as exc:
            raise QuickImageError("LIVE_EVENT_REPLAY_FAILED:" + str(exc)) from exc
        _need(event_id not in proposed.get("observations_ignored_as_stale", []),
              "SCREENSHOT_DRAFT_DISCARDED_AS_STALE")
        status = ("REVIEWABLE_NOT_COMMITTED" if proposed.get("timeline_status") == "TRUSTED"
                  else "PROVISIONAL_ROLLBACK_OR_BRANCH_UNVERIFIED")
        return {
            "schema_version": "1.0",
            "status": status,
            "event_draft": event,
            "accepted_into_preview_only": True,
            "committed_to_live_events": False,
            "repository_mutated": False,
            "action_authorized": False,
            "source_sha256": observed["source_sha256"],
            "base_event_seq": state["last_event_seq"],
            "preview_event_seq": proposed["last_event_seq"],
            "preview_timeline_status": proposed["timeline_status"],
            "preview_resource_values": deepcopy(proposed["resources"]["values"])
                if proposed["resources"].get("fresh") is True else None,
            "preview_hp_players": sorted(
                player for player, hp in proposed.get("hp_by_player", {}).items()
                if hp.get("fresh") is True),
            "next_step": "REVIEW_DRAFT_AND_COMMIT_WITH_CANONICAL_TRANSACTION",
            "image_reader_reused": observed["cache_hit"],
            "source_truth_is_externally_attested_not_machine_verified": True,
        }


def benchmark_local(image_path: str | Path, repeats: int = 7) -> dict[str, Any]:
    """Measured local read/decode latency; no claims about GitHub or iPhone UI."""
    _need(type(repeats) is int and 2 <= repeats <= 100, "BENCHMARK_REPEATS_INVALID")
    cold, warm = [], []
    session = QuickImageSession()
    for i in range(repeats):
        outcome = session.inspect(image_path)
        (cold if i == 0 else warm).append(outcome["local_elapsed_ms"])
    def pct95(sample: list[float]) -> float:
        return sorted(sample)[max(0, min(len(sample)-1,
                               (95 * len(sample) + 99)//100 - 1))]
    return {
        "measurement_scope": "LOCAL_IMAGE_INSPECTION_ONLY",
        "repeats": repeats,
        "cold_first_ms": cold[0],
        "warm_median_ms": round(statistics.median(warm), 3),
        "warm_p95_nearest_rank_ms": round(pct95(warm), 3),
        "unique_pixel_decode_calls": session.read_calls,
        "digest_check_on_every_call": True,
        "chat_latency_measured": False,
        "real_ios_screen_accuracy_benchmarked": False,
        "source_sha256": outcome["source_sha256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast local screenshot -> review draft")
    parser.add_argument("image")
    parser.add_argument("--review", type=Path, help="Independent human-reviewed event fields")
    parser.add_argument("--state", type=Path, default=Path("CURRENT_LIVE_STATE.json"))
    parser.add_argument("--events", type=Path, default=Path("LIVE_EVENTS.jsonl"))
    parser.add_argument("--benchmark", type=int, help="Local repeated-inspection samples")
    args = parser.parse_args()
    try:
        if args.benchmark is not None:
            result = benchmark_local(args.image, args.benchmark)
        else:
            session = QuickImageSession()
            result = session.inspect(args.image)
            if args.review:
                review = json.loads(args.review.read_text(encoding="utf-8"))
                state = json.loads(args.state.read_text(encoding="utf-8"))
                events = read_events(args.events)
                result["candidate"] = session.draft(args.image, review=review,
                                                     state=state, events=events)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (QuickImageError, OSError, ValueError, ObservationError) as exc:
        parser.exit(2, "P5_IMAGE_REVIEW_BLOCKED:" + str(exc) + "\n")


if __name__ == "__main__":
    main()
