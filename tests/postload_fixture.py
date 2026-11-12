"""Historical post-load data used by rollback-specific tests."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
POSTLOAD = ROOT / "tests" / "fixtures" / "postload_seq10"


def copy_postload_authorities(destination, names):
    for name in names:
        frozen = POSTLOAD / name
        shutil.copyfile(frozen if frozen.is_file() else ROOT / name, destination / name)


def copy_postload_runtime(destination):
    from project_bootstrap import BOOT_ORDER

    copy_postload_authorities(destination, (
        *BOOT_ORDER, "AGENTS.md", "PROJECT_ENTRYPOINT.json", "LIVE_EVENTS.jsonl",
        "EVIDENCE_EVENTS.jsonl", "EVIDENCE_BACKUP_CHECKPOINTS.jsonl",
        "EXPERIMENT_TRIALS.jsonl", "KNOWLEDGE_CLAIMS.json", "KNOWLEDGE_MANIFEST.json",
        "NAV_TACTICS.json",
    ))
