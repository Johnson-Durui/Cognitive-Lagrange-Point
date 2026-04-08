"""Decision pipeline manager for the rebuilt product protocol."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from research.db import (
    db_list_decision_sessions,
    db_load_decision_session,
    db_save_decision_session,
)
from research.engine_b.agents import normalize_simulator_output

from .classifier import run_quick_classifier
from .tiers import get_tier_config, normalize_tier


ENGINEB_ACT2_PHASES = {
    "b1_diagnosis",
    "b2_info_fill",
    "b3_cognitive_unlock",
    "b4_experience_sim",
    "b5_emotional_mirror",
    "b5_5_alternative",
    "c1_reevaluation",
    "a_recheck",
}

ENGINEB_ACT3_PHASES = {
    "b6_sim_params",
    "b7_sim_timelines",
    "b8_sim_coping",
    "b9_sim_comparison",
    "simulator_complete",
}

TIER_UPGRADE_ORDER = {
    "quick": 0,
    "deep": 1,
    "pro": 2,
    "ultra": 3,
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _clone_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _has_c1_result(session_data: dict | None) -> bool:
    if not isinstance(session_data, dict):
        return False
    return bool(
        session_data.get("recommendation")
        or session_data.get("action_plan")
        or session_data.get("reasoning")
        or session_data.get("updated_pro_total")
        or session_data.get("updated_con_total")
    )


def _has_simulator_result(session_data: dict | None) -> bool:
    if not isinstance(session_data, dict):
        return False
    return bool(session_data.get("simulator_output"))


def _has_pending_questions(session_data: dict | None, questions_key: str, answers_key: str) -> bool:
    if not isinstance(session_data, dict):
        return False
    questions = session_data.get(questions_key) or []
    answers = session_data.get(answers_key) or {}
    return bool(questions) and len(answers) < len(questions)


def _normalize_engineb_session_snapshot(session_data: dict | None) -> dict | None:
    if not isinstance(session_data, dict):
        return session_data
    normalized = _clone_jsonable(session_data)
    simulator_output = normalized.get("simulator_output")
    if isinstance(simulator_output, dict):
        normalized["simulator_output"] = normalize_simulator_output(simulator_output)
    return normalized


def _normalize_decision_payload(decision: dict | None) -> dict | None:
    if not isinstance(decision, dict):
        return decision
    normalized = _clone_jsonable(decision)
    normalized["tier"] = normalize_tier(normalized.get("tier"))
    normalized["tier_config"] = get_tier_config(normalized.get("tier"))
    normalized["engineb_session"] = _normalize_engineb_session_snapshot(normalized.get("engineb_session"))
    if isinstance(normalized["engineb_session"], dict):
        normalized["engineb_session"]["tier"] = normalize_tier(normalized["engineb_session"].get("tier"))
    return normalized


def _append_decision_log_line(decision: dict, line: str, *, recent_window: int = 1, max_entries: int = 160) -> bool:
    text = str(line or "").strip()
    if not text:
        return False

    logs = decision.setdefault("logs", [])
    if recent_window > 0:
        recent = [str(item or "").strip() for item in logs[-recent_window:]]
        if text in recent:
            return False

    logs.append(text)
    if max_entries > 0 and len(logs) > max_entries:
        del logs[:-max_entries]
    return True


class DecisionManager:
    """Decision state manager that fronts the rebuilt `/api/decision/*` protocol."""

    def __init__(self, detection_manager) -> None:
        self.detection_manager = detection_manager
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.latest_job_id: str | None = None
        self.monitoring: set[str] = set()

    def _persist(self, decision: dict) -> None:
        payload = {k: v for k, v in decision.items() if not k.startswith("_")}
        db_save_decision_session(
            payload["decision_id"],
            payload["tier"],
            payload["status"],
            payload["phase"],
            payload["updated_at"],
            payload,
        )

    def _base_job(self, question: str, tier: str) -> dict:
        config = get_tier_config(tier)
        decision_id = uuid.uuid4().hex[:8]
        return {
            "decision_id": decision_id,
            "question": question,
            "tier": normalize_tier(tier),
            "tier_config": config,
            "status": "running",
            "phase": "act1",
            "step": "classification",
            "status_text": f"正在启动 {config['label']}…",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "completed_at": None,
            "analysis": None,
            "result": None,
            "error": "",
            "logs": [
                f"✨ 已创建决策任务：{config['label']}",
                f"🧭 当前问题：{question}",
            ],
            "linked_detection_job_id": "",
            "linked_engineb_session_id": "",
            "detection_job": None,
            "engineb_session": None,
            "meta": {
                "pipeline_mode": "product_protocol",
                "star_visual": config.get("star_visual", "standard"),
                "simulator_started": False,
                "simulator_ready": False,
                "upgraded_from": "",
            },
        }

    def start(self, question: str, tier: str | None = None) -> dict:
        normalized_tier = normalize_tier(tier)
        decision = self._base_job(question.strip(), normalized_tier)
        with self.lock:
            self.jobs[decision["decision_id"]] = decision
            self.latest_job_id = decision["decision_id"]
            self._persist(decision)

        self._spawn_worker(self._run_job, decision["decision_id"])
        return self.get_status(decision["decision_id"])

    def _spawn_worker(self, target, *args) -> None:
        worker = threading.Thread(
            target=target,
            args=args,
            daemon=True,
        )
        worker.start()

    def _update_job(self, decision_id: str, updater) -> None:
        with self.lock:
            decision = self.jobs.get(decision_id)
            if decision is None:
                persisted = db_load_decision_session(decision_id)
                if not persisted:
                    return
                self.jobs[decision_id] = persisted
                decision = persisted
            updater(decision)
            decision["updated_at"] = now_iso()
            self._persist(decision)

    def _complete(self, decision_id: str, *, result: dict | None = None) -> None:
        def updater(decision: dict) -> None:
            if result is not None:
                decision["result"] = result
            decision["status"] = "completed"
            decision["phase"] = "completed"
            decision["step"] = "done"
            decision["status_text"] = "决策完成"
            decision["completed_at"] = now_iso()

        self._update_job(decision_id, updater)

    def _fail(self, decision_id: str, error: str) -> None:
        def updater(decision: dict) -> None:
            decision["status"] = "failed"
            decision["phase"] = "failed"
            decision["step"] = "error"
            decision["status_text"] = "决策失败"
            decision["error"] = error
            decision["completed_at"] = now_iso()
            _append_decision_log_line(decision, f"⚠️ {error}")

        self._update_job(decision_id, updater)

    def _append_log(self, decision_id: str, line: str) -> None:
        self._update_job(decision_id, lambda job: _append_decision_log_line(job, line))

    def _run_quick(self, decision_id: str, question: str) -> None:
        self._append_log(decision_id, "⚡ 快速模式：执行一次极速结构判断")
        outcome = run_quick_classifier(question)

        def updater(decision: dict) -> None:
            decision["analysis"] = outcome.get("analysis")
            decision["result"] = outcome.get("result")
            _append_decision_log_line(decision, "✅ 快速判断完成")
            decision["status_text"] = "快速建议已生成"

        self._update_job(decision_id, updater)
        self._complete(decision_id)

    def _apply_detect_snapshot(self, decision: dict, detect_job: dict | None) -> None:
        if not isinstance(detect_job, dict):
            return
        decision["analysis"] = detect_job.get("analysis")
        decision["detection_job"] = _clone_jsonable(detect_job)
        decision["status_text"] = detect_job.get("status_text", "正在检测")
        decision["logs"] = list(detect_job.get("logs") or decision.get("logs") or [])
        decision["step"] = detect_job.get("phase", "classification")
        decision["phase"] = "act1" if detect_job.get("status") == "running" else "act1_complete"
        if detect_job.get("status") == "failed":
            decision["phase"] = "failed"
            decision["error"] = str(detect_job.get("error", "") or "检测失败")

    def _apply_engineb_snapshot(self, decision: dict, session_data: dict | None) -> None:
        if not isinstance(session_data, dict):
            return
        normalized_session = _normalize_engineb_session_snapshot(session_data) or {}
        decision["engineb_session"] = normalized_session
        decision["linked_engineb_session_id"] = str(normalized_session.get("session_id", "") or "")
        decision["logs"] = list(decision.get("logs") or [])

        trace = normalized_session.get("processing_trace") or []
        for item in trace[-5:]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "") or "").strip()
            detail = str(item.get("detail", "") or "").strip()
            line = f"{title}：{detail}" if title and detail else title or detail
            if line and line not in decision["logs"]:
                decision["logs"].append(line)

        phase = str(normalized_session.get("phase", "") or "")
        decision["status_text"] = str(normalized_session.get("last_error", "") or "").strip() or phase or "Engine B 处理中"
        decision["step"] = phase or "engineb"
        if phase in ENGINEB_ACT2_PHASES:
            decision["phase"] = "act2"
        elif phase in ENGINEB_ACT3_PHASES:
            decision["phase"] = "act3"
        elif phase == "completed":
            decision["phase"] = "act2_complete"
        elif phase == "abandoned":
            decision["phase"] = "failed"
            decision["error"] = str(normalized_session.get("last_error", "") or "决策流程中断")

    def _ensure_engineb_monitoring(self, decision_id: str) -> None:
        with self.lock:
            if decision_id in self.monitoring:
                return
            self.monitoring.add(decision_id)
        threading.Thread(
            target=self._monitor_engineb_flow,
            args=(decision_id,),
            daemon=True,
        ).start()

    def _start_engineb_for_decision(self, decision_id: str, question: str, source_detection: dict) -> None:
        from server_core import start_engine_b_session

        tier = str((self.get_status(decision_id).get("decision") or {}).get("tier", "") or "deep")
        session = start_engine_b_session(question, source_detection=source_detection, tier=tier)
        session_snapshot = session.to_dict()
        session_phase = str(session_snapshot.get("phase", "") or "b1_diagnosis")
        status_text = (
            "开始第二幕：卡点诊断"
            if session_phase == "b1_diagnosis"
            else "开始第二幕：信息补齐与重评"
        )

        def updater(decision: dict) -> None:
            decision["linked_engineb_session_id"] = session.session_id
            decision["engineb_session"] = session_snapshot
            decision["phase"] = "act2"
            decision["step"] = session_phase
            decision["status_text"] = status_text
            _append_decision_log_line(
                decision,
                "🚀 第一幕已完成，进入第二幕信息抹平"
                if session_phase == "b1_diagnosis"
                else "🚀 第一幕已完成，本轮无需追问，直接进入补信息与重评"
            )

        self._update_job(decision_id, updater)
        self._ensure_engineb_monitoring(decision_id)

    def _run_detect_proxy(self, decision_id: str, question: str, tier: str) -> None:
        config = get_tier_config(tier)
        self._append_log(
            decision_id,
            f"🛰️ {config['label']} 正在进行第一幕分类，复用现有检测链路。"
        )
        detect_mode = config.get("detection_mode") or f"decision_{tier}"
        detect_status = self.detection_manager.start(question, mode=detect_mode)
        detect_job = detect_status.get("job") or {}
        linked_job_id = str(detect_job.get("job_id", "") or "")

        self._update_job(
            decision_id,
            lambda job: job.update({
                "linked_detection_job_id": linked_job_id,
                "status_text": "已接入第一幕真实检测链路",
            }),
        )

        while True:
            current = self.detection_manager.get_status(linked_job_id).get("job")
            if not current:
                self._fail(decision_id, "底层检测任务状态丢失")
                return

            self._update_job(decision_id, lambda job, snapshot=current: self._apply_detect_snapshot(job, snapshot))

            if current.get("status") == "failed":
                self._fail(decision_id, str(current.get("error", "") or "检测失败"))
                return

            if current.get("status") == "completed":
                result = current.get("result") if isinstance(current.get("result"), dict) else {}
                if result.get("is_lagrange_point") is True:
                    final_result = {
                        "mode": "lagrange_confirmed",
                        "summary": result.get("summary", "第一幕确认这是一个认知拉格朗日点。"),
                        "detection_result": result,
                    }

                    def final_updater(decision: dict) -> None:
                        decision["result"] = final_result
                        decision["status_text"] = "第一幕确认：结构性平衡"
                        _append_decision_log_line(decision, "🔴 第一幕确认这是认知拉格朗日点")

                    self._update_job(decision_id, final_updater)
                    self._complete(decision_id, result=final_result)
                    return

                self._start_engineb_for_decision(decision_id, question, current)
                return

            time.sleep(0.5)

    def _resume_detect_flow(self, decision_id: str) -> None:
        try:
            decision = self.get_status(decision_id).get("decision") or {}
            linked_job_id = str(decision.get("linked_detection_job_id", "") or "")
            question = str(decision.get("question", "") or "")
            if not linked_job_id:
                return

            while True:
                current = self.detection_manager.get_status(linked_job_id).get("job")
                if not current:
                    self._fail(decision_id, "底层检测任务状态丢失")
                    return

                self._update_job(decision_id, lambda job, snapshot=current: self._apply_detect_snapshot(job, snapshot))

                if current.get("status") == "failed":
                    self._fail(decision_id, str(current.get("error", "") or "检测失败"))
                    return

                if current.get("status") == "completed":
                    result = current.get("result") if isinstance(current.get("result"), dict) else {}
                    if result.get("is_lagrange_point") is True:
                        final_result = {
                            "mode": "lagrange_confirmed",
                            "summary": result.get("summary", "第一幕确认这是一个认知拉格朗日点。"),
                            "detection_result": result,
                        }
                        self._update_job(
                            decision_id,
                            lambda decision: _append_decision_log_line(decision, "🔴 第一幕确认这是认知拉格朗日点"),
                        )
                        self._complete(decision_id, result=final_result)
                        return

                    if not self.get_status(decision_id).get("decision", {}).get("linked_engineb_session_id"):
                        self._start_engineb_for_decision(decision_id, question, current)
                    return

                time.sleep(0.5)
        finally:
            with self.lock:
                self.monitoring.discard(decision_id)

    def _maybe_start_simulator(self, decision_id: str, session_data: dict) -> None:
        status = self.get_status(decision_id).get("decision") or {}
        meta = status.get("meta") or {}
        if meta.get("simulator_started"):
            return

        tier = status.get("tier")
        config = get_tier_config(tier)
        if not config.get("enable_simulation"):
            return

        session_phase = str(session_data.get("phase", "") or "")
        if session_phase in ENGINEB_ACT3_PHASES or _has_simulator_result(session_data):
            return

        recheck = session_data.get("recheck") if isinstance(session_data.get("recheck"), dict) else {}
        recheck_status = str(recheck.get("status", "") or "").strip()
        recheck_job = recheck.get("job") if isinstance(recheck.get("job"), dict) else {}
        recheck_result = recheck_job.get("result") if isinstance(recheck_job.get("result"), dict) else {}
        if recheck_status in {"pending", "running"}:
            if meta.get("simulator_waiting_recheck"):
                return

            def updater(decision: dict, snapshot=session_data) -> None:
                decision["engineb_session"] = _normalize_engineb_session_snapshot(snapshot)
                decision["status_text"] = "第二幕建议已形成，等待二次检测完成"
                decision.setdefault("meta", {})["simulator_waiting_recheck"] = True
                decision.setdefault("meta", {})["simulator_ready"] = False
                _append_decision_log_line(
                    decision,
                    "⏳ 第二幕建议已形成，Engine A 正在二次检测。检测完成后，你可以手动决定是否进入未来模拟。",
                )

            self._update_job(decision_id, updater)
            return
        if recheck.get("status") == "completed" and recheck_result.get("is_lagrange_point") is True:
            return

        if meta.get("simulator_ready"):
            return

        def updater(decision: dict, snapshot=session_data) -> None:
            decision["engineb_session"] = _normalize_engineb_session_snapshot(snapshot)
            decision["status_text"] = "第二幕建议已形成，可手动启动第三幕未来模拟"
            decision.setdefault("meta", {})["simulator_ready"] = True
            decision.setdefault("meta", {})["simulator_started"] = False
            decision["meta"].pop("simulator_waiting_recheck", None)
            _append_decision_log_line(decision, "🧭 第二幕建议已形成。准备好后，可手动启动第三幕未来模拟。")

        self._update_job(decision_id, updater)

    def _monitor_engineb_flow(self, decision_id: str) -> None:
        try:
            while True:
                decision = self.get_status(decision_id).get("decision") or {}
                session_id = str(decision.get("linked_engineb_session_id", "") or "")
                if not session_id:
                    return

                from server_core import get_engine_b_status_for_session

                status = get_engine_b_status_for_session(session_id)
                session_data = status.get("session")
                if not session_data:
                    self._fail(decision_id, "Engine B 会话状态丢失")
                    return

                self._update_job(decision_id, lambda job, snapshot=session_data: self._apply_engineb_snapshot(job, snapshot))

                phase = str(session_data.get("phase", "") or "")
                recheck = session_data.get("recheck") if isinstance(session_data.get("recheck"), dict) else {}
                recheck_job = recheck.get("job") if isinstance(recheck.get("job"), dict) else {}
                recheck_result = recheck_job.get("result") if isinstance(recheck_job.get("result"), dict) else {}

                if recheck.get("status") == "completed" and recheck_result.get("is_lagrange_point") is True:
                    final_result = {
                        "mode": "recheck_lagrange",
                        "summary": recheck_result.get("summary", "补全后再次确认这是一个认知拉格朗日点。"),
                        "detection_result": recheck_result,
                    }

                    def updater(decision: dict) -> None:
                        decision["result"] = final_result
                        decision["status_text"] = "补全后再次确认为认知拉格朗日点"
                        _append_decision_log_line(decision, "🔴 第二幕补全后，问题被重新确认为认知拉格朗日点")

                    self._update_job(decision_id, updater)
                    self._complete(decision_id, result=final_result)
                    return

                if phase == "abandoned":
                    self._fail(decision_id, str(session_data.get("last_error", "") or "决策流程中断"))
                    return

                if _has_c1_result(session_data):
                    try:
                        self._maybe_start_simulator(decision_id, session_data)
                    except Exception as exc:
                        self._append_log(decision_id, f"⚠️ 自动启动模拟器失败：{exc}")

                decision = self.get_status(decision_id).get("decision") or {}
                config = get_tier_config(decision.get("tier"))
                if _has_simulator_result(session_data):
                    final_result = {
                        "mode": "decision_complete",
                        "summary": "三幕决策流程已完成。",
                        "engineb_session_id": session_id,
                        "can_export_report": True,
                    }
                    self._complete(decision_id, result=final_result)
                    return

                if (
                    _has_c1_result(session_data)
                    and not config.get("enable_simulation")
                    and not _has_pending_questions(session_data, "sim_questions", "sim_answers")
                    and not _has_simulator_result(session_data)
                    and phase not in ENGINEB_ACT3_PHASES
                ):
                    final_result = {
                        "mode": "engineb_complete",
                        "summary": "第二幕决策建议已完成。",
                        "engineb_session_id": session_id,
                        "can_export_report": True,
                    }
                    self._complete(decision_id, result=final_result)
                    return

                if phase == "b6_sim_params" and _has_pending_questions(session_data, "sim_questions", "sim_answers"):
                    time.sleep(0.5)
                    continue
                if phase == "b1_diagnosis" and _has_pending_questions(session_data, "diagnosis_questions", "diagnosis_answers"):
                    time.sleep(0.5)
                    continue

                time.sleep(0.6)
        finally:
            with self.lock:
                self.monitoring.discard(decision_id)

    def _run_job(self, decision_id: str) -> None:
        try:
            with self.lock:
                decision = self.jobs.get(decision_id)
            if not decision:
                return
            question = decision["question"]
            tier = decision["tier"]
            if tier == "quick":
                self._run_quick(decision_id, question)
                return
            self._run_detect_proxy(decision_id, question, tier)
        except Exception as exc:
            self._fail(decision_id, str(exc))

    def _hydrate_persisted_running_job(self, decision_id: str, persisted: dict) -> dict:
        with self.lock:
            if decision_id not in self.jobs:
                self.jobs[decision_id] = persisted
        if persisted.get("linked_engineb_session_id"):
            self._ensure_engineb_monitoring(decision_id)
        elif persisted.get("linked_detection_job_id"):
            with self.lock:
                if decision_id not in self.monitoring:
                    self.monitoring.add(decision_id)
                    self._spawn_worker(self._resume_detect_flow, decision_id)
        return self.jobs[decision_id]

    def _ensure_detection_monitoring(self, decision_id: str) -> None:
        with self.lock:
            if decision_id in self.monitoring:
                return
            self.monitoring.add(decision_id)
        self._spawn_worker(self._resume_detect_flow, decision_id)

    def upgrade(self, decision_id: str, tier: str) -> dict:
        status = self.get_status(decision_id)
        decision = status.get("decision") or {}
        if not decision:
            raise ValueError("找不到该决策会话。")

        current_tier = normalize_tier(decision.get("tier"))
        target_tier = normalize_tier(tier)
        if target_tier == current_tier:
            return status
        if TIER_UPGRADE_ORDER.get(target_tier, 0) <= TIER_UPGRADE_ORDER.get(current_tier, 0):
            raise ValueError("当前只支持升级到更高档位。")

        question = str(decision.get("question", "") or "").strip()
        if not question:
            raise ValueError("当前决策缺少原始问题，无法升级。")

        detect_snapshot = decision.get("detection_job")
        if not isinstance(detect_snapshot, dict) or not detect_snapshot:
            session_snapshot = decision.get("engineb_session") or {}
            source_detection = session_snapshot.get("source_detection")
            if isinstance(source_detection, dict) and source_detection:
                detect_snapshot = _clone_jsonable(source_detection)

        linked_detection_job_id = str(decision.get("linked_detection_job_id", "") or "").strip()
        if (not isinstance(detect_snapshot, dict) or not detect_snapshot) and linked_detection_job_id:
            latest_detection = self.detection_manager.get_status(linked_detection_job_id).get("job")
            if isinstance(latest_detection, dict) and latest_detection:
                detect_snapshot = _clone_jsonable(latest_detection)

        detect_result = detect_snapshot.get("result") if isinstance(detect_snapshot, dict) else {}
        if isinstance(detect_result, dict) and detect_result.get("is_lagrange_point") is True:
            raise ValueError("这个问题已经被确认为认知拉格朗日点，不需要再升级决策档位。")

        current_label = get_tier_config(current_tier)["label"]
        target_config = get_tier_config(target_tier)
        target_label = target_config["label"]
        should_restart_from_flash = current_tier == "quick"
        can_continue_detect = bool(linked_detection_job_id) and not decision.get("linked_engineb_session_id")
        can_restart_from_detect = isinstance(detect_snapshot, dict) and bool(detect_snapshot)
        upgrade_entry = {
            "from_tier": current_tier,
            "to_tier": target_tier,
            "at": now_iso(),
            "from_phase": str(decision.get("phase", "") or ""),
        }

        def updater(job: dict) -> None:
            meta = job.setdefault("meta", {})
            history = meta.get("upgrade_history")
            if not isinstance(history, list):
                history = []
            history.append(upgrade_entry)
            meta["upgrade_history"] = history[-10:]
            meta["upgraded_from"] = decision_id
            meta["upgraded_from_tier"] = current_tier
            meta["star_visual"] = target_config.get("star_visual", meta.get("star_visual", "standard"))
            meta["simulator_started"] = False
            meta["simulator_ready"] = False
            meta.pop("simulator_waiting_recheck", None)

            job["tier"] = target_tier
            job["tier_config"] = target_config
            job["status"] = "running"
            job["error"] = ""
            job["result"] = None
            job["completed_at"] = None

            if should_restart_from_flash:
                job["analysis"] = None
                job["detection_job"] = None
                job["linked_detection_job_id"] = ""
                job["engineb_session"] = None
                job["linked_engineb_session_id"] = ""
                job["phase"] = "act1"
                job["step"] = "classification"
                job["status_text"] = f"已从 {current_label} 升级到 {target_label}，开始正式接入第一幕"
                _append_decision_log_line(
                    job,
                    f"⬆️ 已从 {current_label} 升级到 {target_label}，快速结果会保留在历史里，后续改走完整决策链路。",
                )
                return

            if can_continue_detect:
                job["phase"] = "act1"
                job["status_text"] = f"已从 {current_label} 升级到 {target_label}，继续等待第一幕完成"
                _append_decision_log_line(
                    job,
                    f"⬆️ 已从 {current_label} 升级到 {target_label}，当前直接沿用正在运行的第一幕检测。",
                )
                return

            if can_restart_from_detect:
                job["engineb_session"] = None
                job["linked_engineb_session_id"] = ""
                job["phase"] = "act2"
                job["step"] = "b1_diagnosis"
                job["status_text"] = f"已从 {current_label} 升级到 {target_label}，复用第一幕结果重新展开第二幕"
                _append_decision_log_line(
                    job,
                    f"⬆️ 已从 {current_label} 升级到 {target_label}，第一幕结果保留，第二幕会按新档位重跑。",
                )
                return

            job["analysis"] = None
            job["detection_job"] = None
            job["linked_detection_job_id"] = ""
            job["engineb_session"] = None
            job["linked_engineb_session_id"] = ""
            job["phase"] = "act1"
            job["step"] = "classification"
            job["status_text"] = f"已从 {current_label} 升级到 {target_label}，重新接入第一幕"
            _append_decision_log_line(
                job,
                f"⬆️ 已从 {current_label} 升级到 {target_label}，由于缺少可复用快照，这次会重新接入第一幕。",
            )

        self._update_job(decision_id, updater)
        with self.lock:
            self.latest_job_id = decision_id

        if should_restart_from_flash:
            self._spawn_worker(self._run_detect_proxy, decision_id, question, target_tier)
            return self.get_status(decision_id)

        if can_continue_detect:
            self._ensure_detection_monitoring(decision_id)
            return self.get_status(decision_id)

        if can_restart_from_detect:
            self._spawn_worker(self._start_engineb_for_decision, decision_id, question, detect_snapshot)
            return self.get_status(decision_id)

        self._spawn_worker(self._run_detect_proxy, decision_id, question, target_tier)
        return self.get_status(decision_id)

    def submit_answer(self, decision_id: str, question_id: str, answer: str) -> dict:
        from server_core import submit_engine_b_answer, submit_sim_answer

        decision = self.get_status(decision_id).get("decision") or {}
        session_id = str(decision.get("linked_engineb_session_id", "") or "")
        if not session_id:
            raise ValueError("当前决策还没有进入需要回答的问题阶段。")

        session_data = decision.get("engineb_session") or {}
        if not session_data:
            raise ValueError("当前会话状态尚未同步，请稍后再试。")

        if _has_pending_questions(session_data, "diagnosis_questions", "diagnosis_answers"):
            session = submit_engine_b_answer(session_id, question_id, answer)
            self._update_job(decision_id, lambda job, snapshot=session.to_dict(): self._apply_engineb_snapshot(job, snapshot))
            self._ensure_engineb_monitoring(decision_id)
            return self.get_status(decision_id)

        if _has_pending_questions(session_data, "sim_questions", "sim_answers"):
            session = submit_sim_answer(session_id, question_id, answer)
            self._update_job(decision_id, lambda job, snapshot=session.to_dict(): self._apply_engineb_snapshot(job, snapshot))
            self._ensure_engineb_monitoring(decision_id)
            return self.get_status(decision_id)

        raise ValueError("当前没有待提交的问题。")

    def start_simulator(self, decision_id: str) -> dict:
        decision = self.get_status(decision_id).get("decision") or {}
        session_id = str(decision.get("linked_engineb_session_id", "") or "")
        if not session_id:
            raise ValueError("当前决策还没有进入可模拟阶段。")

        from server_core import start_simulator

        session = start_simulator(session_id)

        def updater(job: dict, snapshot=session.to_dict()) -> None:
            job["engineb_session"] = snapshot
            job["status"] = "running"
            job["phase"] = "act3"
            job["step"] = str(snapshot.get("phase", "") or "b6_sim_params")
            job["error"] = ""
            job["result"] = None
            job["completed_at"] = None
            job["status_text"] = (
                "开始第三幕：未来模拟"
                if snapshot.get("phase") == "b6_sim_params"
                else "第三幕已进入未来推演"
            )
            job["meta"]["simulator_started"] = True
            job["meta"]["simulator_ready"] = False
            job["meta"].pop("simulator_waiting_recheck", None)
            _append_decision_log_line(job, "🔮 已手动启动第三幕未来模拟。")

        self._update_job(decision_id, updater)
        self._ensure_engineb_monitoring(decision_id)
        return self.get_status(decision_id)

    def submit_feedback(
        self,
        decision_id: str,
        *,
        user_choice: str = "",
        satisfaction: int | None = None,
        note: str = "",
    ) -> dict:
        status = self.get_status(decision_id)
        decision = status.get("decision") or {}
        if not decision:
            raise ValueError("找不到该决策会话。")

        sanitized_choice = str(user_choice or "").strip()
        sanitized_note = str(note or "").strip()
        normalized_satisfaction = None
        if satisfaction is not None:
            try:
                normalized_satisfaction = max(1, min(5, int(satisfaction)))
            except (TypeError, ValueError):
                raise ValueError("满意度必须是 1 到 5 之间的整数。")

        def updater(job: dict) -> None:
            feedback = {
                "user_choice": sanitized_choice,
                "satisfaction": normalized_satisfaction,
                "note": sanitized_note,
                "updated_at": now_iso(),
            }
            job["feedback"] = feedback
            job["user_choice"] = sanitized_choice
            job["user_satisfaction"] = normalized_satisfaction
            job["follow_up_note"] = sanitized_note
            _append_decision_log_line(job, "📝 已记录这次决策的事后反馈。", recent_window=3)

        self._update_job(decision_id, updater)
        return self.get_status(decision_id)

    def get_status(self, decision_id: str | None = None) -> dict:
        with self.lock:
            resolved_id = decision_id or self.latest_job_id
            if resolved_id and resolved_id in self.jobs:
                decision = _normalize_decision_payload(self.jobs[resolved_id])
                return {"active": decision.get("status") == "running", "decision": decision}

        if resolved_id:
            persisted = db_load_decision_session(resolved_id)
            if persisted:
                if persisted.get("status") == "running":
                    hydrated = self._hydrate_persisted_running_job(resolved_id, persisted)
                    decision = _normalize_decision_payload(hydrated)
                    return {"active": decision.get("status") == "running", "decision": decision}
                decision = _normalize_decision_payload(persisted)
                return {"active": decision.get("status") == "running", "decision": decision}
        return {"active": False, "decision": None}

    def list_history(self) -> list[dict]:
        history = []
        for item in db_list_decision_sessions():
            normalized = dict(item)
            normalized["tier"] = normalize_tier(normalized.get("tier"))
            history.append(normalized)
        return history
