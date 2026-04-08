#!/usr/bin/env python3
"""Single-question detection manager split out from server_core.py."""

from __future__ import annotations

import json
import threading
import uuid

from research.single_detect import detect_single_question

from server_shared import clone_jsonable, now_iso


def _empty_detect_filter() -> dict:
    return {
        "status": "pending",
        "passed": None,
        "summary": "",
        "details": [],
    }


class DetectionManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.latest_job_id: str | None = None

    def _base_job(
        self,
        question: str,
        *,
        display_question: str | None = None,
        mode: str = "initial",
        loop_context: dict | None = None,
    ) -> dict:
        job_id = uuid.uuid4().hex[:8]
        return {
            "job_id": job_id,
            "question": display_question or question,
            "input_question": question,
            "mode": mode,
            "loop_context": clone_jsonable(loop_context or {}),
            "status": "running",
            "phase": "analysis",
            "status_text": "正在分析问题结构…",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "completed_at": None,
            "analysis": None,
            "filters": {
                "filter1": _empty_detect_filter(),
                "filter2": _empty_detect_filter(),
                "filter3": _empty_detect_filter(),
            },
            "result": None,
            "error": None,
            "logs": ["✨ 初始化检测任务..."],
        }

    def start(
        self,
        question: str,
        *,
        display_question: str | None = None,
        mode: str = "initial",
        loop_context: dict | None = None,
    ) -> dict:
        job = self._base_job(
            question,
            display_question=display_question,
            mode=mode,
            loop_context=loop_context,
        )
        with self.lock:
            self.jobs[job["job_id"]] = job
            self.latest_job_id = job["job_id"]

        thread = threading.Thread(
            target=self._run_job,
            args=(job["job_id"], question, mode),
            daemon=True,
        )
        thread.start()
        return self.get_status(job["job_id"])

    def _update_job(self, job_id: str, updater) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return
            updater(job)
            job["updated_at"] = now_iso()

    def _run_job(self, job_id: str, question: str, mode: str = "initial") -> None:
        def progress(event: str, payload: dict) -> None:
            if event == "analysis_ready":
                self._update_job(job_id, lambda job: job.update({
                    "analysis": payload.get("analysis"),
                    "phase": "analysis_ready",
                    "status_text": "问题结构分析完成，准备正式筛选。",
                }))
                self._update_job(job_id, lambda job: job["logs"].append("✅ 语义对立结构分析完成"))
                return

            if event == "logic_probing":
                msg = payload.get("message", "正在探测逻辑一致性...")
                self._update_job(job_id, lambda job: job["logs"].append(f"🔍 {msg}"))
                return

            if event == "filter_started":
                filter_name = payload.get("filter_name")
                if not filter_name:
                    return

                def _start(job):
                    job["phase"] = filter_name
                    job["status_text"] = f"正在运行 {filter_name}…"
                    job["filters"][filter_name]["status"] = "running"

                self._update_job(job_id, _start)
                self._update_job(job_id, lambda job: job["logs"].append(f"⚙️ 启动层级筛选: {filter_name}"))
                return

            if event == "filter_finished":
                filter_name = payload.get("filter_name")
                filter_data = payload.get("filter_data", {})
                if not filter_name:
                    return

                def _finish(job):
                    merged = {**job["filters"][filter_name], **filter_data}
                    passed = merged.get("passed")
                    if passed is True:
                        merged["status"] = "passed"
                    elif passed is False:
                        merged["status"] = "failed"
                    else:
                        merged["status"] = "pending"
                    job["filters"][filter_name] = merged
                    job["status_text"] = merged.get("summary", f"{filter_name} 已完成")

                self._update_job(job_id, _finish)
                self._update_job(job_id, lambda job: job["logs"].append(f"🏁 {filter_name} 筛选结束"))
                return

            if event == "force_analysis_started":
                self._update_job(job_id, lambda job: job.update({
                    "phase": "force_analysis",
                    "status_text": "三层筛子已通过，正在进行力量解剖…",
                }))

        try:
            outcome = detect_single_question(question, progress_callback=progress, mode=mode)

            def _finish(job):
                if outcome.get("analysis") is not None:
                    job["analysis"] = outcome["analysis"]
                if outcome.get("filters"):
                    for name, data in outcome["filters"].items():
                        merged = {**job["filters"].get(name, _empty_detect_filter()), **data}
                        passed = merged.get("passed")
                        if passed is True:
                            merged["status"] = "passed"
                        elif passed is False:
                            merged["status"] = "failed"
                        elif merged.get("status") == "running":
                            merged["status"] = "pending"
                        job["filters"][name] = merged

                job["result"] = outcome.get("result")
                job["status"] = "completed"
                job["phase"] = "completed"
                job["status_text"] = "检测完成"
                job["completed_at"] = now_iso()

            self._update_job(job_id, _finish)
        except Exception as exc:
            self._update_job(job_id, lambda job: job.update({
                "status": "failed",
                "phase": "failed",
                "status_text": "检测失败",
                "error": str(exc),
                "completed_at": now_iso(),
            }))

    def get_status(self, job_id: str | None = None) -> dict:
        with self.lock:
            resolved_id = job_id or self.latest_job_id
            if not resolved_id or resolved_id not in self.jobs:
                return {"active": False, "job": None}
            job = json.loads(json.dumps(self.jobs[resolved_id], ensure_ascii=False))
            return {
                "active": job.get("status") == "running",
                "job": job,
            }

