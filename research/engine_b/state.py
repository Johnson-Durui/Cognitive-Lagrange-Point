"""Engine B - Session State Persistence (文件方式，支持中断恢复)"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from research.engine_b.models import EngineBSession
from research.db import (
    db_save_engine_b_session, db_load_engine_b_session, 
    db_list_engine_b_sessions, db_delete_engine_b_session
)

# 状态文件目录 (仅保留 active_session.json 用于单机标记)
ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "research" / "output"
SESSION_DIR = OUTPUT_DIR / "engine_b_sessions"
ACTIVE_SESSION_PATH = SESSION_DIR / "active_session.json"


def _ensure_session_dir() -> None:
    """确保会话目录存在"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session(session: EngineBSession) -> None:
    """写入会话状态到数据库"""
    _ensure_session_dir()
    
    data = session.to_dict()
    db_save_engine_b_session(
        session_id=session.session_id,
        phase=session.phase.value,
        updated_at=session.updated_at,
        data=data
    )

    # 更新活跃会话索引 (向后兼容单例环境)
    with open(ACTIVE_SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "session_id": session.session_id,
            "phase": session.phase.value,
            "updated_at": session.updated_at,
        }, f, ensure_ascii=False)


def load_session(session_id: str) -> Optional[EngineBSession]:
    """根据 session_id 加载会话"""
    data = db_load_engine_b_session(session_id)
    if data:
        try:
            return EngineBSession.from_dict(data)
        except (KeyError, TypeError):
            pass
    return None


def load_active_session() -> Optional[EngineBSession]:
    """加载当前活跃会话（如果有）"""
    if not ACTIVE_SESSION_PATH.exists():
        return None
    try:
        active_data = json.loads(ACTIVE_SESSION_PATH.read_text(encoding="utf-8"))
        session_id = active_data.get("session_id")
        if session_id:
            return load_session(session_id)
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def get_active_session_id() -> Optional[str]:
    """获取当前活跃会话 ID"""
    if not ACTIVE_SESSION_PATH.exists():
        return None
    try:
        active_data = json.loads(ACTIVE_SESSION_PATH.read_text(encoding="utf-8"))
        return active_data.get("session_id")
    except (json.JSONDecodeError, KeyError):
        return None


def clear_active_session() -> None:
    """清除活跃会话标记"""
    if ACTIVE_SESSION_PATH.exists():
        ACTIVE_SESSION_PATH.unlink()


def delete_session(session_id: str) -> None:
    """删除指定会话"""
    db_delete_engine_b_session(session_id)

    # 如果删除的是活跃会话，也清除标记
    active_id = get_active_session_id()
    if active_id == session_id:
        clear_active_session()


def list_sessions() -> list[dict]:
    """列出所有会话（简要信息）"""
    return db_list_engine_b_sessions()
