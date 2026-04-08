"""Decision report helpers extracted from the legacy server core."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from research.engine_b.agents import normalize_simulator_output


def session_has_insight_result(session_data: dict | None) -> bool:
  if not isinstance(session_data, dict):
    return False
  return bool(
    session_data.get("recommendation")
    or session_data.get("action_plan")
    or session_data.get("reasoning")
    or int(session_data.get("updated_pro_total") or 0) > 0
    or int(session_data.get("updated_con_total") or 0) > 0
  )


def session_has_simulator_result(session_data: dict | None) -> bool:
  if not isinstance(session_data, dict):
    return False
  return bool(session_data.get("simulator_output"))


def resolve_decision_report_context(
  *,
  job_id: str | None = None,
  session_id: str | None = None,
  detection_manager,
  load_session: Callable[[str], object | None],
  load_active_session: Callable[[], object | None],
  hydrate_recheck: Callable[[dict], None],
) -> tuple[str, dict | None, dict | None]:
  detection_job = None
  engineb_session = None

  resolved_job_id = str(job_id or "").strip() or None
  resolved_session_id = str(session_id or "").strip() or None

  if resolved_job_id:
    detection_job = detection_manager.get_status(resolved_job_id).get("job")
  else:
    detection_job = detection_manager.get_status().get("job")

  session = load_session(resolved_session_id) if resolved_session_id else load_active_session()
  if session:
    engineb_session = session.to_dict()
    simulator_output = engineb_session.get("simulator_output")
    if isinstance(simulator_output, dict):
      engineb_session["simulator_output"] = normalize_simulator_output(simulator_output)
    hydrate_recheck(engineb_session)
    if not detection_job:
      source = engineb_session.get("source_detection")
      if isinstance(source, dict) and source.get("job_id"):
        detection_job = source

  question = ""
  if engineb_session:
    question = str(engineb_session.get("original_question", "") or "").strip()
  if not question and detection_job:
    question = str(
      detection_job.get("question")
      or detection_job.get("input_question")
      or ""
    ).strip()

  if not question:
    raise ValueError("当前还没有可导出的最终结果，请先完成一次检测或决策流程。")

  return question, detection_job, engineb_session


def build_decision_report_path(output_dir: Path, question: str, job_id: str | None, session_id: str | None) -> Path:
  reports_dir = output_dir / "decision_reports"
  reports_dir.mkdir(parents=True, exist_ok=True)
  stem = "".join(
    ch for ch in question[:18]
    if ch.isascii() and (ch.isalnum() or ch in {"-", "_"})
  )
  if not stem:
    stem = "decision"
  parts = [stem]
  if job_id:
    parts.append(f"job-{job_id}")
  if session_id:
    parts.append(f"session-{session_id}")
  parts.append(datetime.now().strftime("%Y%m%d-%H%M%S"))
  return reports_dir / ("_".join(parts) + ".pdf")


def build_decision_report_pdf(
  *,
  output_dir: Path,
  job_id: str | None = None,
  session_id: str | None = None,
  decision_data: dict | None = None,
  detection_manager,
  load_session: Callable[[str], object | None],
  load_active_session: Callable[[], object | None],
  hydrate_recheck: Callable[[dict], None],
) -> Path:
  decision_data = decision_data if isinstance(decision_data, dict) else None
  if decision_data:
    detection_job = decision_data.get("detection_job") if isinstance(decision_data.get("detection_job"), dict) else None
    engineb_session = decision_data.get("engineb_session") if isinstance(decision_data.get("engineb_session"), dict) else None
    if engineb_session and isinstance(engineb_session.get("simulator_output"), dict):
      engineb_session["simulator_output"] = normalize_simulator_output(engineb_session.get("simulator_output"))
    question = str(decision_data.get("question", "") or "").strip()
    if not question:
      question, detection_job, engineb_session = resolve_decision_report_context(
        job_id=job_id,
        session_id=session_id,
        detection_manager=detection_manager,
        load_session=load_session,
        load_active_session=load_active_session,
        hydrate_recheck=hydrate_recheck,
      )
    elif (job_id or session_id) and (not detection_job or not engineb_session):
      _, fallback_detection_job, fallback_engineb_session = resolve_decision_report_context(
        job_id=job_id,
        session_id=session_id,
        detection_manager=detection_manager,
        load_session=load_session,
        load_active_session=load_active_session,
        hydrate_recheck=hydrate_recheck,
      )
      if not detection_job:
        detection_job = fallback_detection_job
      if not engineb_session:
        engineb_session = fallback_engineb_session
  else:
    question, detection_job, engineb_session = resolve_decision_report_context(
      job_id=job_id,
      session_id=session_id,
      detection_manager=detection_manager,
      load_session=load_session,
      load_active_session=load_active_session,
      hydrate_recheck=hydrate_recheck,
    )
  report_path = build_decision_report_path(
    output_dir,
    question,
    detection_job.get("job_id") if isinstance(detection_job, dict) else None,
    engineb_session.get("session_id") if isinstance(engineb_session, dict) else None,
  )

  from research.output_formatter import generate_decision_pdf_report

  generate_decision_pdf_report(
    question,
    detection_job=detection_job,
    engineb_session=engineb_session,
    decision_data=decision_data,
    metadata={
      "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
      "model": os.environ.get("CLP_MODEL", "").strip(),
    },
    output_path=str(report_path),
  )
  return report_path


def build_decision_summary_report_pdf(
  *,
  output_dir: Path,
  job_id: str | None = None,
  session_id: str | None = None,
  decision_data: dict | None = None,
  detection_manager,
  load_session: Callable[[str], object | None],
  load_active_session: Callable[[], object | None],
  hydrate_recheck: Callable[[dict], None],
) -> Path:
  decision_data = decision_data if isinstance(decision_data, dict) else None
  if decision_data:
    detection_job = decision_data.get("detection_job") if isinstance(decision_data.get("detection_job"), dict) else None
    engineb_session = decision_data.get("engineb_session") if isinstance(decision_data.get("engineb_session"), dict) else None
    if engineb_session and isinstance(engineb_session.get("simulator_output"), dict):
      engineb_session["simulator_output"] = normalize_simulator_output(engineb_session.get("simulator_output"))
    question = str(decision_data.get("question", "") or "").strip()
    if not question:
      question, detection_job, engineb_session = resolve_decision_report_context(
        job_id=job_id,
        session_id=session_id,
        detection_manager=detection_manager,
        load_session=load_session,
        load_active_session=load_active_session,
        hydrate_recheck=hydrate_recheck,
      )
    elif (job_id or session_id) and (not detection_job or not engineb_session):
      _, fallback_detection_job, fallback_engineb_session = resolve_decision_report_context(
        job_id=job_id,
        session_id=session_id,
        detection_manager=detection_manager,
        load_session=load_session,
        load_active_session=load_active_session,
        hydrate_recheck=hydrate_recheck,
      )
      if not detection_job:
        detection_job = fallback_detection_job
      if not engineb_session:
        engineb_session = fallback_engineb_session
  else:
    question, detection_job, engineb_session = resolve_decision_report_context(
      job_id=job_id,
      session_id=session_id,
      detection_manager=detection_manager,
      load_session=load_session,
      load_active_session=load_active_session,
      hydrate_recheck=hydrate_recheck,
    )

  base_path = build_decision_report_path(
    output_dir,
    question,
    detection_job.get("job_id") if isinstance(detection_job, dict) else None,
    engineb_session.get("session_id") if isinstance(engineb_session, dict) else None,
  )
  report_path = base_path.with_name(f"{base_path.stem}_ai-summary.pdf")

  from research.output_formatter import generate_decision_summary_pdf_report

  generate_decision_summary_pdf_report(
    question,
    detection_job=detection_job,
    engineb_session=engineb_session,
    decision_data=decision_data,
    metadata={
      "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
      "model": os.environ.get("CLP_MODEL", "").strip(),
    },
    output_path=str(report_path),
  )
  return report_path
