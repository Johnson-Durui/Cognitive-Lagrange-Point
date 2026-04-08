"""认知拉格朗日点 · 运行断点保存与恢复"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.models import CandidateQuestion, ConfirmedLagrangePoint, FaultLine
from research.db import db_load_detection_job, db_save_detection_job, init_db

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "checkpoint.json")
# backward compatibility Job ID
CHECKPOINT_JOB_ID_COMPAT = "main_detection_loop"
_DB_INITIALIZED = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _archive_dir() -> str | None:
    value = os.environ.get("CLP_ARCHIVE_DIR", "").strip()
    return value or None


def _write_json_atomic(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _ensure_db_initialized() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    init_db()
    _DB_INITIALIZED = True


def load_checkpoint(path: str = CHECKPOINT_PATH) -> dict | None:
    """读取断点记录（从数据库读取，兼容文件 fallback）。"""
    _ensure_db_initialized()
    data = db_load_detection_job(CHECKPOINT_JOB_ID_COMPAT)
    if data is None:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

    return {
        "version": data.get("version", "MVP-0.4"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "completed_miners": data.get("completed_miners", []),
        "metadata": data.get("metadata", {}),
        "candidates": [
            CandidateQuestion.from_dict(item)
            for item in data.get("candidates", [])
        ],
        "confirmed": [
            ConfirmedLagrangePoint.from_dict(item)
            for item in data.get("confirmed", [])
        ],
        "fault_lines": [
            FaultLine.from_dict(item)
            for item in data.get("fault_lines", [])
        ],
        "tunnel_effects": data.get("tunnel_effects", []),
        "social_conflict_predictions": data.get("social_conflict_predictions", []),
        "key_discoveries": data.get("key_discoveries", []),
    }


def save_checkpoint(
    candidates: list[CandidateQuestion],
    confirmed: list[ConfirmedLagrangePoint],
    *,
    fault_lines: list[FaultLine] | None = None,
    tunnel_effects: list[dict] | None = None,
    social_conflict_predictions: list[dict] | None = None,
    key_discoveries: list[str] | None = None,
    completed_miners: list[str] | None = None,
    metadata: dict | None = None,
    path: str = CHECKPOINT_PATH,
    created_at: str | None = None,
) -> str:
    """写入断点到数据库，同时向下兼容保留一份 JSON 文件。"""
    _ensure_db_initialized()
    stable_created_at = created_at
    
    if stable_created_at is None:
        existing = db_load_detection_job(CHECKPOINT_JOB_ID_COMPAT)
        if existing:
            stable_created_at = existing.get("created_at")
        elif os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stable_created_at = json.load(f).get("created_at")
            except (json.JSONDecodeError, OSError):
                stable_created_at = None

    payload = {
        "version": "MVP-0.4",
        "created_at": stable_created_at or _now_iso(),
        "updated_at": _now_iso(),
        "completed_miners": completed_miners or [],
        "metadata": metadata or {},
        "candidates": [candidate.to_dict() for candidate in candidates],
        "confirmed": [point.to_dict() for point in confirmed],
        "fault_lines": [line.to_dict() for line in (fault_lines or [])],
        "tunnel_effects": tunnel_effects or [],
        "social_conflict_predictions": social_conflict_predictions or [],
        "key_discoveries": key_discoveries or [],
    }

    _write_json_atomic(path, payload)
    
    db_save_detection_job(
        job_id=CHECKPOINT_JOB_ID_COMPAT,
        status="running",
        updated_at=payload.get("updated_at", ""),
        data=payload
    )

    archive_root = _archive_dir()
    if archive_root:
        archive_path = os.path.join(archive_root, os.path.basename(path))
        if os.path.abspath(archive_path) != os.path.abspath(path):
            _write_json_atomic(archive_path, payload)

    return path
