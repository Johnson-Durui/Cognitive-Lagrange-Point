#!/usr/bin/env python3
"""认知拉格朗日点 · FastAPI 本地网页控制台后端"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Any

from sse_starlette.sse import EventSourceResponse

from decision import DecisionManager, THINKING_TIERS, get_tier_config, normalize_tier
from decision.reporting import (
    build_decision_report_pdf,
    build_decision_summary_report_pdf,
    session_has_insight_result,
    session_has_simulator_result,
)
from research.engine_b import state as engine_b_state
from research.engine_b.runtime import hydrate_recheck_from_detection
from research.checkpoint_utils import (
    generate_discovered_payload_from_checkpoint,
    summarize_checkpoint,
)

# Import core handlers from the original codebase
from server_core import (
    RUNTIME, DETECTION,
    start_engine_b_session, submit_engine_b_answer, reset_engine_b,
    start_simulator, submit_sim_answer, 
    get_engine_b_status_for_session,
)
from research.db import init_db, db_list_engine_b_sessions

ROOT = Path(__file__).resolve().parent
DECISIONS = DecisionManager(DETECTION)
DIST_DIR = ROOT / "dist"

# --- Startup / Shutdown logic ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    init_db()
    yield
    # Shutdown logic
    pass

app = FastAPI(title="Cognitive Lagrange Point API", lifespan=lifespan)

# Mount static frontend
# We mount this at the end so it doesn't override /api endpoints
FRONTEND_DIR = DIST_DIR if DIST_DIR.exists() else ROOT
if not (FRONTEND_DIR / "index.html").exists():
    logging.warning("Frontend index.html not found!")

@app.middleware("http")
async def disable_frontend_cache(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (
        path == "/"
        or path.endswith(".html")
        or path.endswith(".js")
        or path.endswith(".css")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# --- Helper models ---
class StartRunReq(BaseModel):
    preset: Optional[str] = "resume-full"

class DetectStartReq(BaseModel):
    question: str


class DecisionStartReq(BaseModel):
    question: str
    tier: Optional[str] = "deep"


class DecisionAnswerReq(BaseModel):
    decision_id: str
    question_id: str
    answer: str


class DecisionUpgradeReq(BaseModel):
    decision_id: str
    tier: str


class DecisionSimStartReq(BaseModel):
    decision_id: str


class DecisionFeedbackReq(BaseModel):
    decision_id: str
    user_choice: Optional[str] = ""
    satisfaction: Optional[int] = None
    note: Optional[str] = ""
    follow_up_note: Optional[str] = ""


class EngineBStartReq(BaseModel):
    question: str
    source_job_id: Optional[str] = ""
    source_detection: Optional[dict] = None
    tier: Optional[str] = "deep"

class EngineBAnswerReq(BaseModel):
    session_id: str
    question_id: str
    answer: str

class SimStartReq(BaseModel):
    session_id: str

@app.get("/api/status")
def get_status():
    return {"ok": True, **RUNTIME.get_status()}

@app.get("/api/log")
def get_log(lines: int = 160):
    lines = max(20, min(500, lines))
    return {"ok": True, **RUNTIME.get_log_payload(line_count=lines)}

@app.get("/api/config")
def get_config():
    return {"ok": True, "config": RUNTIME.get_config_summary()}

@app.post("/api/config")
async def post_config(request: Request):
    payload = await request.json()
    config = RUNTIME.save_config(payload)
    return {"ok": True, "config": config}

@app.get("/api/discovered")
def get_discovered():
    checkpoint = summarize_checkpoint()
    payload = generate_discovered_payload_from_checkpoint(checkpoint)
    return {"ok": True, **payload}

@app.get("/api/runs")
def get_runs():
    return {"ok": True, "runs": RUNTIME.list_runs()}

@app.get("/api/runs/{run_id}")
def get_run_detail(run_id: str):
    detail = RUNTIME.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"ok": True, "run": detail}

@app.post("/api/start")
def start_run(req: StartRunReq):
    try:
        status = RUNTIME.start_run(req.preset)
        return {"ok": True, **status}
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.post("/api/stop")
def stop_run():
    status = RUNTIME.stop_run()
    return {"ok": True, **status}

@app.post("/api/detect/start")
def detect_start(req: DetectStartReq):
    status = DETECTION.start(req.question.strip())
    return {"ok": True, **status}

@app.get("/api/detect/status")
def detect_status(job_id: str = ""):
    status = DETECTION.get_status(job_id)
    return {"ok": True, **status}

# --- SSE Streaming Logic ---
async def detection_event_generator(job_id: str):
    status = DETECTION.get_status(job_id)
    while True:
        status = DETECTION.get_status(job_id)
        yield json.dumps({"ok": True, **status}, ensure_ascii=False)
        if not status.get("running") or status.get("status") in ["completed", "failed"]:
            break
        await asyncio.sleep(0.5)

@app.get("/api/detect/events")
async def detect_events(job_id: str = ""):
    return EventSourceResponse(detection_event_generator(job_id))

async def engineb_event_generator(session_id: str, mode: str):
    status = get_engine_b_status_for_session(session_id)
    yield json.dumps({"ok": True, **status}, ensure_ascii=False)
    
    while True:
        status = get_engine_b_status_for_session(session_id)
        session = status.get("session") or {}
        yield json.dumps({"ok": True, **status}, ensure_ascii=False)
        
        if not status.get("active") or not session:
            break
            
        phase = session.get("phase", "")
        if mode == "sim":
            if phase in ["abandoned", "simulator_complete"] or session_has_simulator_result(session):
                break
        else:
            if phase == "abandoned" or session_has_insight_result(session):
                break
                
        await asyncio.sleep(0.5)

@app.get("/api/engineb/events")
async def engineb_events(session_id: str = "", mode: str = "b1"):
    return EventSourceResponse(engineb_event_generator(session_id, mode))

@app.get("/api/engineb/status")
def engineb_status(session_id: str = ""):
    status = get_engine_b_status_for_session(session_id)
    return {"ok": True, **status}

@app.get("/api/engineb/sessions")
def engineb_list_sessions():
    sessions = db_list_engine_b_sessions()
    return {"ok": True, "sessions": sessions}


@app.get("/api/decision/tiers")
def decision_tiers():
    return {
        "ok": True,
        "tiers": {
            key: {
                "key": key,
                **get_tier_config(key),
            }
            for key in THINKING_TIERS
        },
        "default_tier": normalize_tier("deep"),
    }


@app.post("/api/decision/start")
def decision_start(req: DecisionStartReq):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    status = DECISIONS.start(question, req.tier)
    return {"ok": True, **status}


@app.get("/api/decision/status")
def decision_status(id: str = "", decision_id: str = ""):
    status = DECISIONS.get_status(id or decision_id)
    return {"ok": True, **status}


async def decision_event_generator(decision_id: str):
    last_signature = ""
    while True:
        status = DECISIONS.get_status(decision_id)
        decision = status.get("decision") or {}
        session = decision.get("engineb_session") if isinstance(decision.get("engineb_session"), dict) else {}
        phase = str(session.get("phase") or decision.get("phase") or "")
        signature = "|".join([
            str(decision.get("status", "") or ""),
            phase,
            str(decision.get("status_text", "") or ""),
        ])
        if signature and signature != last_signature:
            info_type = "info"
            anchor = "center"
            if phase in {"b7_sim_timelines"}:
                info_type = "pro"
                anchor = "left"
            elif phase in {"b8_sim_coping", "b9_sim_comparison"}:
                info_type = "con"
                anchor = "right"
            elif phase in {"simulator_complete"}:
                info_type = "regret"
                anchor = "center"
            elif decision.get("status") == "failed":
                info_type = "regret"
                anchor = "center"
            yield {
                "event": "star_event",
                "data": json.dumps({
                    "infoType": info_type,
                    "anchor": anchor,
                    "phase": phase,
                    "count": 30 if phase in {"b7_sim_timelines", "b8_sim_coping", "b9_sim_comparison"} else 20,
                }, ensure_ascii=False),
            }
            last_signature = signature
        yield {"data": json.dumps({"ok": True, **status}, ensure_ascii=False)}
        if not status.get("active") or decision.get("status") in {"completed", "failed"}:
            break
        await asyncio.sleep(0.5)


@app.get("/api/decision/events")
async def decision_events(id: str = "", decision_id: str = ""):
    resolved = id or decision_id
    return EventSourceResponse(decision_event_generator(resolved))


@app.get("/api/decision/history")
def decision_history():
    return {"ok": True, "decisions": DECISIONS.list_history()}


@app.post("/api/decision/answer")
def decision_answer(req: DecisionAnswerReq):
    try:
        status = DECISIONS.submit_answer(req.decision_id, req.question_id, req.answer)
        return {"ok": True, **status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/decision/simulate/start")
def decision_simulate_start(req: DecisionSimStartReq):
    try:
        status = DECISIONS.start_simulator(req.decision_id)
        return {"ok": True, **status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/decision/upgrade")
def decision_upgrade(req: DecisionUpgradeReq):
    try:
        upgraded = DECISIONS.upgrade(req.decision_id, req.tier)
        return {"ok": True, **upgraded}
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "找不到" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)


@app.post("/api/decision/feedback")
def decision_feedback(req: DecisionFeedbackReq):
    try:
        status = DECISIONS.submit_feedback(
            req.decision_id,
            user_choice=req.user_choice or "",
            satisfaction=req.satisfaction,
            note=req.follow_up_note or req.note or "",
        )
        return {"ok": True, **status}
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "找不到" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)

@app.post("/api/engineb/start")
def engineb_start(req: EngineBStartReq):
    source_detection = req.source_detection
    if source_detection is None and req.source_job_id:
        source_detection = DETECTION.get_status(req.source_job_id).get("job")
    try:
        session = start_engine_b_session(req.question, source_detection=source_detection, tier=req.tier or "deep")
        return {"ok": True, "session": session.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/engineb/answer")
def engineb_answer(req: EngineBAnswerReq):
    try:
        session = submit_engine_b_answer(req.session_id, req.question_id, req.answer)
        return {"ok": True, "session": session.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/engineb/reset")
def engineb_reset():
    reset_engine_b()
    return {"ok": True}

@app.post("/api/engineb/simulate/start")
def engineb_simulate_start(req: SimStartReq):
    try:
        session = start_simulator(req.session_id)
        return {"ok": True, "session": session.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/engineb/simulate/answer")
def engineb_simulate_answer(req: EngineBAnswerReq):
    try:
        session = submit_sim_answer(req.session_id, req.question_id, req.answer)
        return {"ok": True, "session": session.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/report/pdf")
def get_report_pdf():
    pdf_path = ROOT / "research" / "output" / "report.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF报告尚未生成，请先运行实验。")
    return FileResponse(path=pdf_path, filename="认知拉格朗日点_研究报告.pdf", media_type="application/pdf")

@app.get("/api/report/txt")
def get_report_txt():
    txt_path = ROOT / "research" / "output" / "report.txt"
    if not txt_path.exists():
        raise HTTPException(status_code=404, detail="文本报告尚未生成，请先运行实验。")
    return FileResponse(path=txt_path, filename="认知拉格朗日点_研究报告.txt", media_type="text/plain")

@app.get("/api/final-report/pdf")
def get_final_report_pdf(job_id: str = "", session_id: str = ""):
    try:
        report_path = build_decision_report_pdf(
            output_dir=ROOT / "research" / "output",
            job_id=job_id,
            session_id=session_id,
            detection_manager=DETECTION,
            load_session=engine_b_state.load_session,
            load_active_session=engine_b_state.load_active_session,
            hydrate_recheck=hydrate_recheck_from_detection,
        )
        if report_path.suffix == ".txt":
            return FileResponse(path=report_path, filename=report_path.name, media_type="text/plain")
        return FileResponse(path=report_path, filename=report_path.name, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/final-report/summary-pdf")
def get_final_report_summary_pdf(job_id: str = "", session_id: str = ""):
    try:
        report_path = build_decision_summary_report_pdf(
            output_dir=ROOT / "research" / "output",
            job_id=job_id,
            session_id=session_id,
            detection_manager=DETECTION,
            load_session=engine_b_state.load_session,
            load_active_session=engine_b_state.load_active_session,
            hydrate_recheck=hydrate_recheck_from_detection,
        )
        return FileResponse(path=report_path, filename=report_path.name, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/decision/report")
def decision_report(id: str = "", decision_id: str = ""):
    resolved_id = id or decision_id
    status = DECISIONS.get_status(resolved_id)
    decision = status.get("decision") or {}
    if not decision:
        raise HTTPException(status_code=404, detail="找不到该决策会话")

    linked_job_id = str(decision.get("linked_detection_job_id", "") or "")
    linked_session_id = str(decision.get("linked_engineb_session_id", "") or "")
    if linked_job_id or linked_session_id:
        try:
            report_path = build_decision_report_pdf(
                output_dir=ROOT / "research" / "output",
                job_id=linked_job_id,
                session_id=linked_session_id,
                decision_data=decision,
                detection_manager=DETECTION,
                load_session=engine_b_state.load_session,
                load_active_session=engine_b_state.load_active_session,
                hydrate_recheck=hydrate_recheck_from_detection,
            )
            media_type = "application/pdf" if report_path.suffix == ".pdf" else "text/plain"
            return FileResponse(path=report_path, filename=report_path.name, media_type=media_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    reports_dir = ROOT / "research" / "output" / "decision_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"decision_{resolved_id}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    report_path = reports_dir / filename
    analysis = decision.get("analysis") or {}
    result = decision.get("result") or {}
    lines = [
        "认知拉格朗日点 · 决策快照",
        "=" * 36,
        f"问题：{decision.get('question', '')}",
        f"思考深度：{decision.get('tier', '')}",
        f"状态：{decision.get('status', '')}",
        "",
        "结构分析：",
        str(analysis.get("analysis_summary", "") or "暂无"),
        "",
        "建议：",
        str(result.get("recommendation_title", "") or ""),
        str(result.get("recommendation", "") or ""),
        "",
        f"下一步：{result.get('next_step', '')}",
        f"原因：{result.get('why', '')}",
    ]
    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return FileResponse(path=report_path, filename=report_path.name, media_type="text/plain")


@app.get("/api/decision/summary-report")
def decision_summary_report(id: str = "", decision_id: str = ""):
    resolved_id = id or decision_id
    status = DECISIONS.get_status(resolved_id)
    decision = status.get("decision") or {}
    if not decision:
        raise HTTPException(status_code=404, detail="找不到该决策会话")

    linked_job_id = str(decision.get("linked_detection_job_id", "") or "")
    linked_session_id = str(decision.get("linked_engineb_session_id", "") or "")
    try:
        report_path = build_decision_summary_report_pdf(
            output_dir=ROOT / "research" / "output",
            job_id=linked_job_id,
            session_id=linked_session_id,
            decision_data=decision,
            detection_manager=DETECTION,
            load_session=engine_b_state.load_session,
            load_active_session=engine_b_state.load_active_session,
            hydrate_recheck=hydrate_recheck_from_detection,
        )
        return FileResponse(path=report_path, filename=report_path.name, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")

# Static files mapping
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    print(f"FastAPI starting on http://{args.host}:{args.port}")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=True)
