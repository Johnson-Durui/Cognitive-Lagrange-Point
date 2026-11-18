#!/usr/bin/env python3
"""FastAPI application, REST/SSE endpoints, and CLI runner for Cognitive Lagrange Point."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from decision import THINKING_TIERS, DecisionManager, get_tier_config, normalize_tier
from decision.reporting import (
    build_decision_report_pdf,
    build_decision_summary_report_pdf,
    session_has_insight_result,
    session_has_simulator_result,
)
from research.checkpoint_utils import (
    generate_discovered_payload_from_checkpoint,
    summarize_checkpoint,
)
from research.db import SessionLocal, db_list_engine_b_sessions, init_db
from research.engine_b import state as engine_b_state
from research.engine_b.runtime import hydrate_recheck_from_detection
from research.output_formatter import _decision_report_font_path

from .core import (
    DETECTION,
    RUNTIME,
    get_engine_b_status_for_session,
    reset_engine_b,
    start_engine_b_session,
    start_simulator,
    submit_engine_b_answer,
    submit_sim_answer,
)
from .shared import (
    ROOT,
    get_demo_status,
    get_effective_env,
    mask_secret,
    now_iso,
)

SERVICE_VERSION = "2.0.0"

DECISIONS = DecisionManager(DETECTION)
DIST_DIR = ROOT / "dist"
FRONTEND_DIR = DIST_DIR if DIST_DIR.exists() else ROOT

if not (FRONTEND_DIR / "index.html").exists():
    logging.getLogger(__name__).warning("Frontend index.html not found!")


class DisableFrontendCacheMiddleware:
    """Pure ASGI middleware disabling browser caching for static HTML/JS/CSS assets."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        should_disable_cache = (
            path == "/"
            or path.endswith(".html")
            or path.endswith(".js")
            or path.endswith(".css")
        )
        if not should_disable_cache:
            await self.app(scope, receive, send)
            return

        async def send_with_no_cache(message) -> None:
            if message.get("type") == "http.response.start":
                raw_headers = list(message.get("headers") or [])
                filtered = [
                    (k, v)
                    for k, v in raw_headers
                    if k.lower() not in {b"cache-control", b"pragma", b"expires"}
                ]
                filtered.extend([
                    (b"cache-control", b"no-store, no-cache, must-revalidate, max-age=0"),
                    (b"pragma", b"no-cache"),
                    (b"expires", b"0"),
                ])
                message = {**message, "headers": filtered}
            await send(message)

        await self.app(scope, receive, send_with_no_cache)


def _check_database_ready() -> bool:
    try:
        init_db()
        with SessionLocal() as db_session:
            db_session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_pdf_reporter_ready() -> bool:
    try:
        import fpdf  # noqa: F401

        return bool(_decision_report_font_path())
    except Exception:
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cognitive Lagrange Point API",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)
app.add_middleware(DisableFrontendCacheMiddleware)


# --- Request Schemas ---
class StartRunReq(BaseModel):
    preset: Optional[str] = "resume-full"


class DetectStartReq(BaseModel):
    question: str


class DecisionStartReq(BaseModel):
    question: str
    tier: Optional[str] = "deep"
    demo: Optional[bool] = None


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


# --- Health & System Metadata ---
@app.get("/api/health")
def get_health():
    env = get_effective_env()
    demo = get_demo_status(env)
    db_ready = _check_database_ready()
    pdf_ready = _check_pdf_reporter_ready()
    return {
        "ok": True,
        "status": "healthy" if db_ready else "degraded",
        "service": "cognitive-lagrange-point",
        "version": SERVICE_VERSION,
        "timestamp": now_iso(),
        "engines": {
            "engine_a": "ready",
            "engine_b": "ready",
            "decision_protocol": "ready",
            "pdf_reporter": "ready" if pdf_ready else "degraded",
        },
        "database": {
            "ready": db_ready,
            "driver": "sqlite",
        },
        "supported_tiers": list(THINKING_TIERS.keys()),
        "llm_configured": demo["llm_configured"],
        "demo_fallback_available": demo["fallback_available"],
        "demo_mode_active": demo["active"],
    }


@app.get("/api/system/info")
def get_system_info():
    env = get_effective_env()
    demo = get_demo_status(env)
    pdf_ready = _check_pdf_reporter_ready()
    tier_summaries = {}
    for key in THINKING_TIERS:
        cfg = get_tier_config(key)
        tier_summaries[key] = {
            "key": key,
            "label": cfg.get("label", key),
            "tagline": cfg.get("tagline", ""),
            "estimated_tokens": cfg.get("estimated_tokens", 0),
            "estimated_seconds": cfg.get("estimated_seconds", 0),
            "enable_simulation": bool(cfg.get("enable_simulation")),
            "allow_manual_simulation": bool(cfg.get("allow_manual_simulation")),
            "enable_ultra_monte_carlo": bool(cfg.get("enable_ultra_monte_carlo")),
        }

    fallbacks = [
        item.strip()
        for item in str(env.get("CLP_MODEL_FALLBACKS", "") or "").split(",")
        if item.strip()
    ]
    return {
        "ok": True,
        "service": "Cognitive Lagrange Point",
        "version": SERVICE_VERSION,
        "supported_tiers": list(THINKING_TIERS.keys()),
        "default_tier": normalize_tier("deep"),
        "tiers": tier_summaries,
        "engines": {
            "engine_a": {
                "status": "ready",
                "description": "Three-stage structural symmetry & stability filter",
            },
            "engine_b": {
                "status": "ready",
                "description": "Multi-agent B1-B9 cognitive breakthrough & future simulator",
            },
            "ultra_monte_carlo": {
                "status": "ready",
                "description": "Multi-persona branch collision & probability smoothing",
            },
            "pdf_reporter": {
                "status": "ready" if pdf_ready else "degraded",
                "renderer": str(env.get("CLP_PDF_RENDERER", "fpdf") or "fpdf"),
            },
        },
        "llm": {
            "configured": demo["llm_configured"],
            "provider_format": "openai-compatible",
            "base_url": str(env.get("CLP_BASE_URL", "") or ""),
            "model": str(env.get("CLP_MODEL", "deepseek-v3") or "deepseek-v3"),
            "fallbacks": fallbacks,
            "api_key_present": demo["llm_configured"],
            "api_key_masked": mask_secret(env.get("CLP_API_KEY", "")),
        },
        "demo": demo,
        "frontend": {
            "served_from": "dist" if DIST_DIR.exists() else "root",
            "index_present": (FRONTEND_DIR / "index.html").exists(),
        },
    }


# --- Batch Research Runtime Endpoints ---
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


_CONFIG_BODY_DEFAULT = Body(default_factory=dict)


@app.post("/api/config")
def post_config(payload: dict = _CONFIG_BODY_DEFAULT):
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
        status = RUNTIME.start_run(req.preset or "resume-full")
        return {"ok": True, **status}
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.post("/api/stop")
def stop_run():
    status = RUNTIME.stop_run()
    return {"ok": True, **status}


# --- Engine A Single-Question Detection ---
@app.post("/api/detect/start")
def detect_start(req: DetectStartReq):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    status = DETECTION.start(question)
    return {"ok": True, **status}


@app.get("/api/detect/status")
def detect_status(job_id: str = ""):
    status = DETECTION.get_status(job_id)
    return {"ok": True, **status}


async def detection_event_generator(job_id: str):
    while True:
        status = DETECTION.get_status(job_id)
        yield json.dumps({"ok": True, **status}, ensure_ascii=False)
        job = status.get("job") or {}
        if not status.get("active") or job.get("status") in {"completed", "failed"}:
            break
        await asyncio.sleep(0.5)


@app.get("/api/detect/events")
async def detect_events(job_id: str = ""):
    return EventSourceResponse(detection_event_generator(job_id))


# --- Engine B Direct Endpoints ---
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
            if phase in {"abandoned", "simulator_complete"} or session_has_simulator_result(session):
                break
        elif phase == "abandoned" or session_has_insight_result(session):
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


# --- Unified Decision Protocol Endpoints ---
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
    if req.demo is None:
        status = DECISIONS.start(question, req.tier)
    else:
        status = DECISIONS.start(question, req.tier, demo=req.demo)
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
            elif phase in {"simulator_complete"} or decision.get("status") == "failed":
                info_type = "regret"
                anchor = "center"
            yield {
                "event": "star_event",
                "data": json.dumps(
                    {
                        "infoType": info_type,
                        "anchor": anchor,
                        "phase": phase,
                        "count": 30 if phase in {"b7_sim_timelines", "b8_sim_coping", "b9_sim_comparison"} else 20,
                    },
                    ensure_ascii=False,
                ),
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
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/decision/simulate/start")
def decision_simulate_start(req: DecisionSimStartReq):
    try:
        status = DECISIONS.start_simulator(req.decision_id)
        return {"ok": True, **status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/decision/upgrade")
def decision_upgrade(req: DecisionUpgradeReq):
    try:
        upgraded = DECISIONS.upgrade(req.decision_id, req.tier)
        return {"ok": True, **upgraded}
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "找不到" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from e


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
        raise HTTPException(status_code=status_code, detail=detail) from e


@app.post("/api/engineb/start")
def engineb_start(req: EngineBStartReq):
    source_detection = req.source_detection
    if source_detection is None and req.source_job_id:
        source_detection = DETECTION.get_status(req.source_job_id).get("job")
    try:
        session = start_engine_b_session(
            req.question,
            source_detection=source_detection,
            tier=req.tier or "deep",
        )
        return {"ok": True, "session": session.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/engineb/answer")
def engineb_answer(req: EngineBAnswerReq):
    try:
        session = submit_engine_b_answer(req.session_id, req.question_id, req.answer)
        return {"ok": True, "session": session.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/engineb/simulate/answer")
def engineb_simulate_answer(req: EngineBAnswerReq):
    try:
        session = submit_sim_answer(req.session_id, req.question_id, req.answer)
        return {"ok": True, "session": session.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Report Generation & Export ---
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
        media_type = "text/plain" if report_path.suffix == ".txt" else "application/pdf"
        return FileResponse(path=report_path, filename=report_path.name, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/decision/report")
def decision_report(id: str = "", decision_id: str = ""):
    resolved_id = id or decision_id
    status = DECISIONS.get_status(resolved_id)
    decision = status.get("decision") or {}
    if not decision:
        raise HTTPException(status_code=404, detail="找不到该决策会话")

    linked_job_id = str(decision.get("linked_detection_job_id", "") or "")
    linked_session_id = str(decision.get("linked_engineb_session_id", "") or "")
    has_structured_payload = bool(
        linked_job_id
        or linked_session_id
        or decision.get("detection_job")
        or decision.get("engineb_session")
        or decision.get("tier") == "quick"
    )
    if has_structured_payload:
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
            raise HTTPException(status_code=500, detail=str(e)) from e

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
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cognitive Lagrange Point (认知拉格朗日点) Web Console & API Server"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=4173, help="Bind port (default: 4173)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Force deterministic Offline Demo Mode (no API key required)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable Uvicorn auto-reload for local development",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.demo:
        os.environ["CLP_DEMO_MODE"] = "1"
    demo = get_demo_status()
    mode_banner = (
        f"DEMO MODE ({demo['reason']})"
        if demo["active"]
        else f"LIVE LLM MODE ({get_effective_env().get('CLP_MODEL', 'deepseek-v3')})"
    )
    print(f"Cognitive Lagrange Point starting on http://{args.host}:{args.port} [{mode_banner}]")
    uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)
