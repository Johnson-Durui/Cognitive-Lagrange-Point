"""Database persistence layer for Engine B sessions and Engine A jobs."""

import json
from pathlib import Path
from typing import Optional, List

from sqlalchemy import create_engine, String, Text, select
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, Session, sessionmaker

Base = declarative_base()

class DBEngineBSession(Base):
    __tablename__ = "engine_b_sessions"
    
    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    phase: Mapped[str] = mapped_column(String(50))
    updated_at: Mapped[str] = mapped_column(String(50))
    data_json: Mapped[str] = mapped_column(Text)


class DBDetectionJob(Base):
    __tablename__ = "detection_jobs"
    
    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(50))
    updated_at: Mapped[str] = mapped_column(String(50))
    data_json: Mapped[str] = mapped_column(Text)


class DBDecisionSession(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tier: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    phase: Mapped[str] = mapped_column(String(50))
    updated_at: Mapped[str] = mapped_column(String(50))
    data_json: Mapped[str] = mapped_column(Text)


# Setup SQLite Database
DB_DIR = Path(__file__).resolve().parent / "output"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "app_state.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)


# --- Engine B Session Persistence Hooks ---

def db_save_engine_b_session(session_id: str, phase: str, updated_at: str, data: dict) -> None:
    with SessionLocal() as db_session:
        db_obj = DBEngineBSession(
            session_id=session_id,
            phase=phase,
            updated_at=updated_at,
            data_json=json.dumps(data, ensure_ascii=False)
        )
        db_session.merge(db_obj)
        db_session.commit()

def db_load_engine_b_session(session_id: str) -> Optional[dict]:
    with SessionLocal() as db_session:
        obj = db_session.get(DBEngineBSession, session_id)
        if obj:
            return json.loads(obj.data_json)
        return None

def db_list_engine_b_sessions() -> List[dict]:
    with SessionLocal() as db_session:
        result = db_session.execute(select(DBEngineBSession))
        sessions = []
        for row in result.scalars():
            try:
                data = json.loads(row.data_json)
                sessions.append({
                    "session_id": data.get("session_id", ""),
                    "original_question": data.get("original_question", ""),
                    "phase": data.get("phase", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                pass
        return sorted(sessions, key=lambda x: x.get("created_at", ""), reverse=True)

def db_delete_engine_b_session(session_id: str) -> None:
    with SessionLocal() as db_session:
        obj = db_session.get(DBEngineBSession, session_id)
        if obj:
            db_session.delete(obj)
            db_session.commit()

# --- Engine A/Detection Job Persistence Hooks ---

def db_save_detection_job(job_id: str, status: str, updated_at: str, data: dict) -> None:
    with SessionLocal() as db_session:
        db_obj = DBDetectionJob(
            job_id=job_id,
            status=status,
            updated_at=updated_at,
            data_json=json.dumps(data, ensure_ascii=False)
        )
        db_session.merge(db_obj)
        db_session.commit()

def db_load_detection_job(job_id: str) -> Optional[dict]:
    with SessionLocal() as db_session:
        obj = db_session.get(DBDetectionJob, job_id)
        if obj:
            return json.loads(obj.data_json)
        return None


def db_save_decision_session(
    decision_id: str,
    tier: str,
    status: str,
    phase: str,
    updated_at: str,
    data: dict,
) -> None:
    with SessionLocal() as db_session:
        db_obj = DBDecisionSession(
            decision_id=decision_id,
            tier=tier,
            status=status,
            phase=phase,
            updated_at=updated_at,
            data_json=json.dumps(data, ensure_ascii=False),
        )
        db_session.merge(db_obj)
        db_session.commit()


def db_load_decision_session(decision_id: str) -> Optional[dict]:
    with SessionLocal() as db_session:
        obj = db_session.get(DBDecisionSession, decision_id)
        if obj:
            return json.loads(obj.data_json)
        return None


def db_list_decision_sessions() -> List[dict]:
    with SessionLocal() as db_session:
        result = db_session.execute(select(DBDecisionSession))
        sessions = []
        for row in result.scalars():
            try:
                data = json.loads(row.data_json)
            except Exception:
                continue
            sessions.append({
                "decision_id": data.get("decision_id", ""),
                "question": data.get("question", ""),
                "tier": data.get("tier", ""),
                "status": data.get("status", ""),
                "phase": data.get("phase", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "linked_detection_job_id": data.get("linked_detection_job_id", ""),
                "linked_engineb_session_id": data.get("linked_engineb_session_id", ""),
            })
        return sorted(sessions, key=lambda x: x.get("created_at", ""), reverse=True)

def db_get_all_confirmed_clps() -> List[dict]:
    """从所有检测任务中提取已确认的认知拉格朗日点。"""
    all_points = []
    with SessionLocal() as db_session:
        # 1. 优先获取主循环 checkpoint
        main_job = db_session.get(DBDetectionJob, "main_detection_loop")
        if main_job:
            try:
                data = json.loads(main_job.data_json)
                all_points.extend(data.get("confirmed", []))
            except Exception:
                pass
        
        # 2. 获取其他所有任务中的点（避免主循环没跑完的情况）
        result = db_session.execute(select(DBDetectionJob))
        for row in result.scalars():
            if row.job_id == "main_detection_loop":
                continue
            try:
                data = json.loads(row.data_json)
                # 有些任务可能直接存的就是点数据
                if "confirmed" in data:
                    all_points.extend(data["confirmed"])
                elif "id" in data and "question_text" in data:
                    all_points.append(data)
            except Exception:
                pass
                
    # 去重
    seen_ids = set()
    unique_points = []
    for p in all_points:
        pid = p.get("id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_points.append(p)
            
    return unique_points

def db_register_engine_b_as_clp(session_data: dict) -> str:
    """将 Engine B 的高质量评估结果反哺注册为一颗新星。"""
    session_id = session_data.get("session_id", "unknown")
    question = session_data.get("original_question", "")
    
    # 构建符合 ConfirmedLagrangePoint 结构的字典
    clp_id = f"CLP-B-{session_id[:6].upper()}"
    new_star = {
        "id": clp_id,
        "question_text": question,
        "source_candidate": f"EngineB-Session-{session_id}",
        "pro_forces": [],
        "con_forces": [],
        "pro_total": session_data.get("updated_pro_total", 50),
        "con_total": session_data.get("updated_con_total", 50),
        "balance_precision": 100 - abs(int(session_data.get("updated_pro_total", 50)) - int(session_data.get("updated_con_total", 50))),
        "balance_analysis": session_data.get("reasoning", ""),
        "stability_type": "稳定-扰动后回归",
        "fault_lines": ["用户实测反馈线"],
        "tunnel_connections": [],
        "presentation_mode": "experiment", # 标记为实测点
    }
    
    # 存入数据库作为一个独立的检测任务存档
    db_save_detection_job(
        job_id=clp_id,
        status="completed",
        updated_at=session_data.get("updated_at", ""),
        data=new_star
    )
    return clp_id
