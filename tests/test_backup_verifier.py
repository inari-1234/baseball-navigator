"""Offline verification of raw bytes actually recovered from private Library."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backup_verifier import BackupError, verify_private_backup


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PrivateLibraryBackupVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.files = root / "retrieved"
        self.files.mkdir()
        self.source = root / "EVIDENCE_EVENTS.jsonl"
        self.public = root / "EVIDENCE_BACKUP_CHECKPOINTS.jsonl"
        self.private = root / "private_manifest.json"
        self.filename = "demo.png"
        self.image = b"\\x89PNG\\r\\n\\x1a\\n" + b"sample-original-pixels"
        self.hash = digest(self.image)
        (self.files / self.filename).write_bytes(self.image)
        self.source.write_text(json.dumps({
            "evidence_id": "EV-1", "kind": "SCREENSHOT",
            "source": {"file_name": self.filename, "sha256": self.hash}
        }) + "\n", encoding="utf-8")
        self.manifest = {
            "schema_version": "1.0", "backup_batch_id": "BK-TEST",
            "storage_provider": "CHATGPT_LIBRARY",
            "verification_method": "FILE_LIBRARY_UPLOAD_LIST_MATERIALIZE_SHA256",
            "records": [{"evidence_id": "EV-1", "filename": self.filename,
                         "library_file_id": "libfile_REAL_FILE_REF",
                         "expected_sha256": self.hash,
                         "readback_sha256": self.hash,
                         "original_size_bytes": len(self.image),
                         "readback_size_bytes": len(self.image),
                         "verification_status": "VERIFIED_AT_CHECKPOINT"}],
        }
        self.persist()

    def persist(self):
        self.private.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        self.public.write_text(json.dumps({
            "checkpoint_id": "CHK-1", "evidence_id": "EV-1",
            "backup_batch_id": "BK-TEST", "source_sha256": self.hash,
            "library_readback_sha256": self.hash,
            "private_manifest_sha256": digest(self.private.read_bytes())}) + "\n",
            encoding="utf-8")

    def verify(self):
        return verify_private_backup(self.private, self.files, self.source, self.public)

    def test_verified_readback(self):
        result = self.verify()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["readback_sha256_match"])
        self.assertFalse(result["future_library_access_guaranteed"])

    def test_changed_restored_file_fails(self):
        (self.files / self.filename).write_bytes(b"modified")
        with self.assertRaisesRegex(BackupError, "LIBRARY_READBACK_SHA_MISMATCH"):
            self.verify()

    def test_file_unavailable_fails(self):
        (self.files / self.filename).unlink()
        with self.assertRaisesRegex(BackupError, "RESTORED_FILE_MISSING_OR_SYMLINK"):
            self.verify()

    def test_path_traversal_rejected(self):
        self.manifest["records"][0]["filename"] = "../secret.png"
        self.persist()
        with self.assertRaisesRegex(BackupError, "UNSAFE_PRIVATE_FILENAME"):
            self.verify()

    def test_duplicate_private_record_fails(self):
        self.manifest["records"].append(self.manifest["records"][0].copy())
        self.persist()
        with self.assertRaisesRegex(BackupError, "PRIVATE_BACKUP_INCOMPLETE"):
            self.verify()

    def test_manifest_tamper_detected_against_public_digest(self):
        self.manifest["records"][0]["library_file_id"] = "libfile_CHANGED"
        self.private.write_text(json.dumps(self.manifest) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(BackupError, "PUBLIC_BACKUP_ATTESTATION_MISMATCH"):
            self.verify()

    def test_missing_library_reference_rejected(self):
        self.manifest["records"][0]["library_file_id"] = ""
        self.persist()
        with self.assertRaisesRegex(BackupError, "LIBRARY_ID_NOT_RECORDED_PRIVATELY"):
            self.verify()

    def test_wrong_source_digest_rejected(self):
        record = json.loads(self.source.read_text(encoding="utf-8"))
        record["source"]["sha256"] = "b" * 64
        self.source.write_text(json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(BackupError, "PRIVATE_BACKUP_DIGEST_CONFLICT"):
            self.verify()

    def test_wrong_source_size_rejected(self):
        self.manifest["records"][0]["readback_size_bytes"] += 1
        self.persist()
        with self.assertRaisesRegex(BackupError, "LIBRARY_READBACK_SIZE_MISMATCH"):
            self.verify()

    def test_private_manifest_not_committed_by_this_engine(self):
        old_manifest = self.private.read_bytes()
        old_public = self.public.read_bytes()
        self.verify()
        self.assertEqual(self.private.read_bytes(), old_manifest)
        self.assertEqual(self.public.read_bytes(), old_public)


if __name__ == "__main__":
    unittest.main()
