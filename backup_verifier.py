#!/usr/bin/env python3
"""Verify source-original image bytes restored from a private Library archive.

This script has NO Library/GitHub network access. The caller must independently
fetch the actual Library objects into a fresh directory, then pass that
directory and the PRIVATE manifest here. Never commit the private manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HEX = set("0123456789abcdef")


class BackupError(ValueError):
    pass


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise BackupError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def _load_jsonl(path: Path, key: str) -> dict[str, dict]:
    try:
        entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    except (OSError, ValueError) as exc:
        raise BackupError("INVALID_JSONL:" + path.name) from exc
    result: dict[str, dict] = {}
    for item in entries:
        _need(isinstance(item, dict) and isinstance(item.get(key), str),
              "INVALID_BACKUP_ENTRY")
        _need(item[key] not in result, "DUPLICATE:" + item[key])
        result[item[key]] = item
    return result


def verify_private_backup(
    private_manifest: str | Path,
    restored_dir: str | Path,
    evidence_events: str | Path = "EVIDENCE_EVENTS.jsonl",
    backup_checkpoints: str | Path = "EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
) -> dict:
    private_manifest = Path(private_manifest)
    restored_dir = Path(restored_dir)
    try:
        manifest_bytes = private_manifest.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError) as exc:
        raise BackupError("PRIVATE_MANIFEST_UNREADABLE") from exc
    _need(isinstance(manifest, dict) and isinstance(manifest.get("records"), list),
          "INVALID_PRIVATE_MANIFEST")
    _need(manifest.get("storage_provider") == "CHATGPT_LIBRARY",
          "STORAGE_PROVIDER_MISMATCH")
    _need(manifest.get("verification_method") ==
          "FILE_LIBRARY_UPLOAD_LIST_MATERIALIZE_SHA256", "BACKUP_METHOD_MISMATCH")
    evidence = _load_jsonl(Path(evidence_events), "evidence_id")
    checkpoints = _load_jsonl(Path(backup_checkpoints), "checkpoint_id")
    checkpoint_by_evidence: dict[str, dict] = {}
    for entry in checkpoints.values():
        eid = entry.get("evidence_id")
        _need(isinstance(eid, str) and eid not in checkpoint_by_evidence,
              "DUPLICATE_PUBLIC_CHECKPOINT_EVIDENCE")
        checkpoint_by_evidence[eid] = entry
    evidence_ids = {eid for eid, entry in evidence.items()
                    if entry.get("kind") == "SCREENSHOT"}
    _need(len(manifest["records"]) == len(evidence_ids),
          "PRIVATE_BACKUP_INCOMPLETE")
    seen: set[str] = set()
    manifest_hash = _sha256(manifest_bytes)
    for record in manifest["records"]:
        _need(isinstance(record, dict), "MALFORMED_PRIVATE_RECORD")
        eid, filename = record.get("evidence_id"), record.get("filename")
        _need(eid in evidence_ids and eid not in seen, "UNEXPECTED_BACKUP_EVIDENCE")
        seen.add(eid)
        _need(isinstance(filename, str) and filename == Path(filename).name
              and filename not in {"", ".", ".."} and "/" not in filename
              and "\\" not in filename,
              "UNSAFE_PRIVATE_FILENAME")
        _need(evidence[eid]["source"].get("file_name") == filename,
              "SOURCE_FILENAME_CONFLICT")
        _need(isinstance(record.get("library_file_id"), str)
              and record["library_file_id"].startswith("libfile_"),
              "LIBRARY_ID_NOT_RECORDED_PRIVATELY")
        expected = evidence[eid]["source"].get("sha256")
        _need(_is_sha256(expected) and record.get("expected_sha256") == expected
              and record.get("readback_sha256") == expected,
              "PRIVATE_BACKUP_DIGEST_CONFLICT:" + eid)
        _need(record.get("verification_status") == "VERIFIED_AT_CHECKPOINT",
              "UNVERIFIED_BACKUP_RECORD:" + eid)
        actual_file = restored_dir / filename
        _need(actual_file.is_file() and not actual_file.is_symlink(),
              "RESTORED_FILE_MISSING_OR_SYMLINK:" + eid)
        try:
            actual_bytes = actual_file.read_bytes()
        except OSError as exc:
            raise BackupError("RESTORED_FILE_UNREADABLE:" + eid) from exc
        _need(_sha256(actual_bytes) == expected,
              "LIBRARY_READBACK_SHA_MISMATCH:" + eid)
        _need(record.get("original_size_bytes") == len(actual_bytes)
              and record.get("readback_size_bytes") == len(actual_bytes),
              "LIBRARY_READBACK_SIZE_MISMATCH:" + eid)
        checkpoint = checkpoint_by_evidence.get(eid)
        _need(isinstance(checkpoint, dict)
              and checkpoint.get("private_manifest_sha256") == manifest_hash
              and checkpoint.get("backup_batch_id") == manifest.get("backup_batch_id")
              and checkpoint.get("source_sha256") == expected
              and checkpoint.get("library_readback_sha256") == expected,
              "PUBLIC_BACKUP_ATTESTATION_MISMATCH:" + eid)
    _need(seen == evidence_ids, "PRIVATE_BACKUP_COVERAGE_MISSING")
    return {
        "result": "PASS",
        "verified_image_count": len(seen),
        "readback_sha256_match": True,
        "public_metadata_match": True,
        "verification_scope": "SUPPLIED_MATERIALIZED_LIBRARY_OBJECTS",
        "future_library_access_guaranteed": False,
        "private_manifest_sha256": manifest_hash,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Verify re-materialized private Library source images")
    p.add_argument("--private-manifest", type=Path, required=True)
    p.add_argument("--restored-dir", type=Path, required=True)
    p.add_argument("--evidence", type=Path, default=Path("EVIDENCE_EVENTS.jsonl"))
    p.add_argument("--checkpoints", type=Path,
                   default=Path("EVIDENCE_BACKUP_CHECKPOINTS.jsonl"))
    args = p.parse_args()
    try:
        result = verify_private_backup(args.private_manifest, args.restored_dir,
                                       args.evidence, args.checkpoints)
    except BackupError as exc:
        p.exit(1, "BACKUP_FAIL: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
