"""Engine B runtime orchestration and simulator flow."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from decision.tiers import get_tier_config, normalize_tier
from research.db import db_register_engine_b_as_clp
from research.engine_b import agents as engine_b_agents
from research.engine_b import external_signals as external_signal_store
from research.engine_b import state as engine_b_state
from research.engine_b.models import EngineBPhase, EngineBSession


ENGINE_B_RECHECK_THRESHOLD = max(0, int(os.environ.get("CLP_ENGINE_B_RECHECK_THRESHOLD", "15")))
_DETECTION_MANAGER = None


def configure_detection_manager(detection_manager) -> None:
    global _DETECTION_MANAGER
    _DETECTION_MANAGER = detection_manager


def _require_detection_manager():
    if _DETECTION_MANAGER is None:
        raise RuntimeError("Engine B runtime 尚未绑定 DetectionManager。")
    return _DETECTION_MANAGER


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _append_processing_trace(
    session: EngineBSession,
    phase: EngineBPhase | str,
    title: str,
    detail: str,
    *,
    persist: bool = True,
) -> None:
    phase_value = phase.value if isinstance(phase, EngineBPhase) else str(phase or "")
    entry = {
        "id": uuid.uuid4().hex[:8],
        "phase": phase_value,
        "title": str(title or "").strip(),
        "detail": str(detail or "").strip(),
        "at": now_iso(),
    }
    session.processing_trace = list(session.processing_trace or [])
    session.processing_trace.append(entry)
    session.processing_trace = session.processing_trace[-40:]
    session.updated_at = now_iso()
    if persist:
        engine_b_state.save_session(session)


def _format_titles(items: list[dict], key: str = "title", *, limit: int = 3) -> str:
    titles = [
        str(item.get(key, "") or "").strip()
        for item in (items or [])
        if isinstance(item, dict) and str(item.get(key, "") or "").strip()
    ]
    if not titles:
        return ""
    if len(titles) <= limit:
        return "、".join(titles)
    return "、".join(titles[:limit]) + f" 等{len(titles)}项"


def _clone_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _to_int(value, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _sum_filter2_moments(filter2_state: dict | None) -> tuple[int, int]:
    details = filter2_state.get("details", []) if isinstance(filter2_state, dict) else []
    pro_total = 0
    con_total = 0
    for item in details:
        if not isinstance(item, dict):
            continue
        strength = max(0, min(100, _to_int(item.get("lean_strength"), 0)))
        direction = str(item.get("lean_direction", "")).strip()
        if direction == "正方":
            pro_total += strength
        elif direction == "反方":
            con_total += strength
    return pro_total, con_total


def _derive_initial_balance(source_detection: dict) -> tuple[int, int]:
    """从检测结果推导有意义的初始力量对比，避免永远返回 50:50。

    优先级：
    1. filter2 的 lean_strength/lean_direction 明细
    2. 分类得分 (dilemma / info_gap / clp)
    3. filter2 的 distribution 文本 (如 '60:40')
    4. 最终 fallback  →  50:50
    """
    filters = source_detection.get("filters", {})
    filter2 = filters.get("filter2", {}) if isinstance(filters, dict) else {}
    pro, con = _sum_filter2_moments(filter2)
    if pro > 0 or con > 0:
        return pro, con

    # --- 从 classification scores 推导 ---
    analysis = source_detection.get("analysis")
    if isinstance(analysis, dict):
        classifications = analysis.get("classifications", {}) if isinstance(analysis.get("classifications"), dict) else {}
        dilemma = max(0, min(100, _to_int(classifications.get("dilemma"), 0)))
        info_gap = max(0, min(100, _to_int(classifications.get("info_gap"), 0)))
        clp = max(0, min(100, _to_int(classifications.get("clp"), 0)))
        if dilemma > 0 or info_gap > 0 or clp > 0:
            # dilemma 高 → 两边都有道理，但某一边可能略强
            # info_gap 高 → 缺信息导致看起来均等
            # clp 高 → 结构性平衡
            if clp >= dilemma and clp >= info_gap:
                # 真正的结构性平衡，给一个接近但不完全等于 50:50 的值
                return 48, 52
            if info_gap > dilemma:
                # 信息缺口 → 正方略弱（因为缺信息无法充分支撑）
                gap_ratio = min(15, info_gap // 6)
                return max(35, 50 - gap_ratio), min(65, 50 + gap_ratio)
            if dilemma > 0:
                # 两难 → 有真实张力，从 dilemma 得分推导偏移
                shift = min(18, max(5, dilemma // 5))
                return 50 + shift, 50 - shift

    # --- 从 filter2 distribution 文本推导 ---
    distribution = str(filter2.get("distribution", "") or "").strip()
    if ":" in distribution:
        parts = distribution.split(":")
        try:
            left = int(parts[0].strip())
            right = int(parts[1].strip())
            if left > 0 or right > 0:
                return max(10, min(90, left)), max(10, min(90, right))
        except (ValueError, IndexError):
            pass

    return 50, 50


def _normalize_source_detection(source_detection: dict | None) -> dict:
    if not isinstance(source_detection, dict):
        return {}

    filters = source_detection.get("filters", {})
    result = source_detection.get("result", {})
    pro_total, con_total = _derive_initial_balance(source_detection)
    return {
        "job_id": str(source_detection.get("job_id", "") or "").strip(),
        "question": str(source_detection.get("question", "") or "").strip(),
        "mode": str(source_detection.get("mode", "initial") or "initial").strip(),
        "analysis": _clone_jsonable(source_detection.get("analysis") or {}),
        "filters": _clone_jsonable(filters if isinstance(filters, dict) else {}),
        "result": _clone_jsonable(result if isinstance(result, dict) else {}),
        "original_pro_total": pro_total,
        "original_con_total": con_total,
    }


def _normalize_session_snapshot(session_data: dict | None) -> dict:
    if not isinstance(session_data, dict):
        return {}
    normalized = _clone_jsonable(session_data)
    simulator_output = normalized.get("simulator_output")
    if isinstance(simulator_output, dict):
        normalized["simulator_output"] = engine_b_agents.normalize_simulator_output(simulator_output)
    return normalized


def _default_recheck_state() -> dict:
    return {
        "needed": False,
        "status": "idle",
        "threshold": ENGINE_B_RECHECK_THRESHOLD,
        "difference": None,
        "reason": "",
        "job_id": "",
        "job": None,
        "error": "",
        "requested_at": "",
        "completed_at": "",
    }


def _build_recheck_reason(diff: int) -> str:
    return f"补全后正反力量差值只有 {diff}，仍低于二次检测阈值 {ENGINE_B_RECHECK_THRESHOLD}。"


def _format_recheck_items(items: list[dict], formatter, *, empty: str) -> str:
    lines = []
    for item in (items or [])[:3]:
        if not isinstance(item, dict):
            continue
        text = formatter(item).strip()
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines) if lines else empty


def _build_recheck_question(session: EngineBSession) -> str:
    source = session.source_detection or {}
    source_result = source.get("result", {}) if isinstance(source, dict) else {}
    source_filters = source.get("filters", {}) if isinstance(source, dict) else {}

    filter_lines = []
    for filter_name in ("filter1", "filter2", "filter3"):
        state = source_filters.get(filter_name, {}) if isinstance(source_filters, dict) else {}
        summary = str(state.get("summary", "") or "").strip()
        if summary:
            filter_lines.append(f"- {filter_name}: {summary}")
    filter_summary = "\n".join(filter_lines) if filter_lines else "（初次检测没有留下可复用的筛子摘要）"

    info_summary = _format_recheck_items(
        session.missing_info_items,
        lambda item: f"【{item.get('title', '')}】{item.get('content', '')}",
        empty="（暂无新增关键信息）",
    )
    frame_summary = _format_recheck_items(
        session.cognitive_frames,
        lambda item: f"【{item.get('title', '')}】{item.get('core_insight', '')}；现在可用：{item.get('try_now', '')}",
        empty="（暂无新增判断框架）",
    )
    experience_summary = _format_recheck_items(
        session.experience_cases,
        lambda item: f"【{item.get('title', '')}】{item.get('choice_made', '')}；结果：{item.get('outcome', '')}；提醒：{item.get('lesson', '')}",
        empty="（暂无新增经验参照）",
    )

    emotional = session.emotional_insight if isinstance(session.emotional_insight, dict) else {}
    emotion_lines = []
    for item in emotional.get("dominant_emotions", [])[:3]:
        if not isinstance(item, dict):
            continue
        emotion = str(item.get("emotion", "") or "").strip()
        evidence = str(item.get("evidence", "") or "").strip()
        intensity = str(item.get("intensity", "") or "").strip()
        if emotion:
            emotion_lines.append(f"- {emotion}{f'({intensity})' if intensity else ''}：{evidence}")
    emotion_summary = "\n".join(emotion_lines) if emotion_lines else "（暂无明显情绪干扰线索）"

    return f"""你现在是 Engine A 的二次检测员。

用户原始问题：{session.original_question}

【初次检测摘要】
初次检测结论：{str(source_result.get('summary', '') or '无')}
初次检测失败阶段：{str(source_result.get('failed_at', '') or '未知')}
初次检测筛子摘要：
{filter_summary}

【Engine B 新增信息】
1. 关键信息：
{info_summary}

2. 新框架：
{frame_summary}

3. 经验参照：
{experience_summary}

4. 情绪线索：
{emotion_summary}

【当前重估结果】
补全前：正方 {session.original_pro_total} / 反方 {session.original_con_total}
补全后：正方 {session.updated_pro_total} / 反方 {session.updated_con_total}
当前建议：{session.recommendation or '尚未形成'}

请重新运行你的三轮检测逻辑：
1. 信息注入测试
2. 多框架稳定性测试
3. 重新表述稳定性测试

目标不是给建议，而是判断：补完认知后，这个问题是否应被重新确认为认知拉格朗日点。
"""


def hydrate_recheck_from_detection(session_data: dict) -> None:
    recheck = session_data.get("recheck")
    if not isinstance(recheck, dict):
        return
    job_id = str(recheck.get("job_id", "") or "").strip()
    if not job_id:
        return
    latest = _require_detection_manager().get_status(job_id).get("job")
    if not latest:
        return
    recheck["job"] = latest
    if latest.get("status") == "running":
        recheck["status"] = "running"
    elif latest.get("status") == "completed":
        recheck["status"] = "completed"
    elif latest.get("status") == "failed":
        recheck["status"] = "failed"


def _should_trigger_engine_b_recheck(session: EngineBSession) -> tuple[bool, int, str]:
    diff = abs(_to_int(session.updated_pro_total, 0) - _to_int(session.updated_con_total, 0))
    source = session.source_detection if isinstance(session.source_detection, dict) else {}
    if not source.get("job_id"):
        return False, diff, ""
    if str(source.get("mode", "initial") or "initial") == "engine_b_recheck":
        return False, diff, ""

    recheck = session.recheck if isinstance(session.recheck, dict) else {}
    if str(recheck.get("status", "") or "").strip() in {"pending", "running", "completed"}:
        return False, diff, ""
    if diff > ENGINE_B_RECHECK_THRESHOLD:
        return False, diff, f"补全后正反力量差值扩大到 {diff}，已经超过二次检测阈值 {ENGINE_B_RECHECK_THRESHOLD}。"
    return True, diff, _build_recheck_reason(diff)


def _run_engine_b_recheck_async(session_id: str) -> None:
    try:
        session = engine_b_state.load_session(session_id)
        if not session:
            return

        detect_status = _require_detection_manager().start(
            _build_recheck_question(session),
            display_question=session.original_question,
            mode="engine_b_recheck",
            loop_context={
                "loop_stage": "engine_b_recheck",
                "engine_b_session_id": session.session_id,
                "source_job_id": (session.source_detection or {}).get("job_id", ""),
            },
        )
        detect_job = detect_status.get("job") or {}
        job_id = str(detect_job.get("job_id", "") or "").strip()
        if not job_id:
            raise RuntimeError("二次检测任务没有成功创建。")

        session = engine_b_state.load_session(session_id)
        if not session:
            return
        recheck = dict(session.recheck or _default_recheck_state())
        recheck.update({
            "status": "running",
            "job_id": job_id,
            "job": _clone_jsonable(detect_job),
            "error": "",
        })
        session.recheck = recheck
        session.updated_at = now_iso()
        engine_b_state.save_session(session)

        while True:
            latest_status = _require_detection_manager().get_status(job_id)
            latest_job = latest_status.get("job")
            if not latest_job:
                raise RuntimeError("二次检测任务状态丢失。")
            if latest_job.get("status") == "running":
                time.sleep(1.2)
                continue

            session = engine_b_state.load_session(session_id)
            if not session:
                return
            recheck = dict(session.recheck or _default_recheck_state())
            recheck.update({
                "job_id": job_id,
                "job": _clone_jsonable(latest_job),
                "completed_at": now_iso(),
            })
            if latest_job.get("status") == "completed":
                recheck["status"] = "completed"
                recheck["error"] = ""
                session.recheck = recheck
                session.phase = EngineBPhase.COMPLETED
                session.last_error = ""
                session.updated_at = now_iso()
                engine_b_state.save_session(session)
                result = latest_job.get("result", {}) if isinstance(latest_job.get("result"), dict) else {}
                _append_processing_trace(
                    session,
                    EngineBPhase.A_RECHECK,
                    "Engine A 二次检测已完成",
                    result.get("summary", "二次检测已经结束，最终结论已准备好。"),
                )
            else:
                recheck["status"] = "failed"
                recheck["error"] = str(latest_job.get("error", "") or "二次检测失败")
                session.recheck = recheck
                session.phase = EngineBPhase.C1_REEVALUATION
                session.updated_at = now_iso()
                engine_b_state.save_session(session)
                _append_processing_trace(
                    session,
                    EngineBPhase.A_RECHECK,
                    "Engine A 二次检测失败",
                    recheck["error"],
                )
            return
    except Exception as exc:
        session = engine_b_state.load_session(session_id)
        if not session:
            return
        recheck = dict(session.recheck or _default_recheck_state())
        recheck.update({
            "status": "failed",
            "error": str(exc),
            "completed_at": now_iso(),
        })
        session.recheck = recheck
        session.phase = EngineBPhase.C1_REEVALUATION
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.A_RECHECK,
            "Engine A 二次检测失败",
            str(exc),
        )


def _maybe_start_engine_b_recheck(session: EngineBSession) -> EngineBSession:
    recheck = dict(session.recheck or _default_recheck_state())
    needed, diff, reason = _should_trigger_engine_b_recheck(session)
    recheck.update({
        "threshold": ENGINE_B_RECHECK_THRESHOLD,
        "difference": diff,
    })

    if not needed:
        if session.source_detection:
            recheck.update({
                "needed": False,
                "status": "skipped" if reason else recheck.get("status", "idle") or "idle",
                "reason": reason,
            })
        session.recheck = recheck
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        return session

    recheck.update({
        "needed": True,
        "status": "pending",
        "reason": reason,
        "error": "",
        "requested_at": now_iso(),
        "completed_at": "",
    })
    session.recheck = recheck
    session.phase = EngineBPhase.A_RECHECK
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.A_RECHECK,
        "仍接近平衡，已送回 Engine A 二次检测",
        reason,
    )
    threading.Thread(
        target=_run_engine_b_recheck_async,
        args=(session.session_id,),
        daemon=True,
    ).start()
    return session


def session_has_c1_result(session: EngineBSession) -> bool:
    return bool(
        session.recommendation
        or session.action_plan
        or session.reasoning
        or session.updated_pro_total
        or session.updated_con_total
    )


def _get_session_tier_config(session: EngineBSession) -> dict:
    return get_tier_config(getattr(session, "tier", "deep"))


def _should_run_agent(session: EngineBSession, blockages: list[str], blockage_key: str, config_key: str) -> bool:
    config = _get_session_tier_config(session)
    if not config.get(config_key):
        return False
    normalized_tier = normalize_tier(getattr(session, "tier", "deep"))
    if config.get("force_full_enrichment") or normalized_tier == "ultra":
        return True
    if blockage_key == "A":
        return blockage_key in blockages or not blockages
    return blockage_key in blockages


def enrich_engine_b_session(session: EngineBSession, *, force: bool = False) -> EngineBSession:
    """运行 Engine B 的 B2-B5-C1 主流程。"""
    if (
        not force
        and session.phase in {
            EngineBPhase.C1_REEVALUATION,
            EngineBPhase.A_RECHECK,
            EngineBPhase.B6_SIM_PARAMS,
            EngineBPhase.B7_SIM_TIMELINES,
            EngineBPhase.B8_SIM_COPING,
            EngineBPhase.B9_SIM_COMPARISON,
            EngineBPhase.SIMULATOR_COMPLETE,
            EngineBPhase.COMPLETED,
        }
        and session_has_c1_result(session)
    ):
        return session

    blockages = engine_b_agents.infer_blockages_from_answers(
        session.diagnosis_answers,
        session.diagnosis_questions,
    )
    session.diagnosed_blockages = blockages
    session.value_profile = engine_b_agents.infer_value_profile(
        session.original_question,
        session.diagnosis_answers,
    )
    session.decision_biases = engine_b_agents.infer_decision_biases(
        session.original_question,
        session.diagnosis_answers,
        blockages,
    )
    session.external_signals = external_signal_store.retrieve_external_signals(
        session.original_question,
        limit=6,
    )
    tier_config = _get_session_tier_config(session)
    if session.external_signals:
        signal_titles = "；".join(
            str(item.get("summary", "") or "").strip()
            for item in session.external_signals[:2]
            if isinstance(item, dict) and str(item.get("summary", "") or "").strip()
        )
        _append_processing_trace(
            session,
            EngineBPhase.B2_INFO_FILL,
            "已接入外部市场声音",
            f"这轮额外参考了近期外部声音快照。{signal_titles}",
        )

    session.phase = EngineBPhase.B2_INFO_FILL
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B2_INFO_FILL,
        "开始补齐关键事实",
        "我在先补收入差额、成长兑现率、退出成本这些最容易影响判断的硬信息。",
    )

    if _should_run_agent(session, blockages, "A", "enable_info_detective"):
        session.missing_info_items = engine_b_agents.run_b2_info_gathering(
            session.original_question,
            blockages,
            session.diagnosis_answers,
            external_signals=session.external_signals,
            max_tokens=int(tier_config.get("b2_max_tokens") or 3072),
        )
    else:
        session.missing_info_items = []
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    if session.missing_info_items:
        _append_processing_trace(
            session,
            EngineBPhase.B2_INFO_FILL,
            "信息缺口已定位",
            f"识别到 {len(session.missing_info_items)} 个关键缺口：{_format_titles(session.missing_info_items)}。",
        )
    else:
        _append_processing_trace(
            session,
            EngineBPhase.B2_INFO_FILL,
            "这一轮没有新增信息缺口",
            (
                "当前档位没有启用信息侦探，或诊断结果里没有明显的信息黑洞。"
                if not tier_config.get("enable_info_detective")
                else "目前更像不是缺事实，而是缺判断框架或经验参照。"
            ),
        )

    session.phase = EngineBPhase.B3_COGNITIVE_UNLOCK
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B3_COGNITIVE_UNLOCK,
        "开始切换判断框架",
        "我在把这个问题从可逆性、成长兑现率和替代方案这些角度重新拆开。",
    )

    if _should_run_agent(session, blockages, "B", "enable_cognitive_unlock"):
        session.cognitive_frames = engine_b_agents.run_b3_cognitive_unlock(
            session.original_question,
            blockages,
            session.diagnosis_answers,
            session.missing_info_items,
            value_profile=session.value_profile,
            max_tokens=int(tier_config.get("b3_max_tokens") or 3072),
        )
    else:
        session.cognitive_frames = []
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    if session.cognitive_frames:
        _append_processing_trace(
            session,
            EngineBPhase.B3_COGNITIVE_UNLOCK,
            "判断框架已补上",
            f"生成了 {len(session.cognitive_frames)} 个可直接拿来判断的框架：{_format_titles(session.cognitive_frames)}。",
        )
    else:
        _append_processing_trace(
            session,
            EngineBPhase.B3_COGNITIVE_UNLOCK,
            "这一轮没有新增框架",
            (
                "当前档位没有启用认知解锁，或诊断结果里没有明显的认知窄门。"
                if not tier_config.get("enable_cognitive_unlock")
                else "当前更像不是认知窄门，先继续看经验和情绪层面的阻力。"
            ),
        )

    session.phase = EngineBPhase.B4_EXPERIENCE_SIM
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B4_EXPERIENCE_SIM,
        "开始找经验参照",
        "我在模拟类似处境的人会怎么走，以及各自后来发生了什么。",
    )

    if _should_run_agent(session, blockages, "C", "enable_experience_sim"):
        session.experience_cases = engine_b_agents.run_b4_experience_simulation(
            session.original_question,
            blockages,
            session.diagnosis_answers,
            session.missing_info_items,
            session.cognitive_frames,
            max_tokens=int(tier_config.get("b4_max_tokens") or 4096),
            experience_limit=int(tier_config.get("experience_count") or 3),
        )
    else:
        session.experience_cases = []
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    if session.experience_cases:
        _append_processing_trace(
            session,
            EngineBPhase.B4_EXPERIENCE_SIM,
            "经验参照已生成",
            f"补了 {len(session.experience_cases)} 个参考案例：{_format_titles(session.experience_cases)}。",
        )
    else:
        _append_processing_trace(
            session,
            EngineBPhase.B4_EXPERIENCE_SIM,
            "这一步暂时跳过",
            (
                "当前档位没有启用经验模拟，所以我先不展开过来人案例。"
                if not tier_config.get("enable_experience_sim")
                else "当前信号里没有明显的经验盲区，所以我没有强行编一组过来人案例。"
            ),
        )

    session.phase = EngineBPhase.B5_EMOTIONAL_MIRROR
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B5_EMOTIONAL_MIRROR,
        "开始识别情绪干扰",
        "我在看你真正怕失去什么，以及这种害怕有没有把理性判断拉偏。",
    )

    if _should_run_agent(session, blockages, "D", "enable_emotion_mirror"):
        session.emotional_insight = engine_b_agents.run_b5_emotional_mirror(
            session.original_question,
            blockages,
            session.diagnosis_answers,
            value_profile=session.value_profile,
            max_tokens=int(tier_config.get("b5_max_tokens") or 2048),
        )
    else:
        session.emotional_insight = {}
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    emotions = session.emotional_insight.get("dominant_emotions", []) if isinstance(session.emotional_insight, dict) else []
    if emotions:
        emotion_names = [
            str(item.get("emotion", "") or "").strip()
            for item in emotions
            if isinstance(item, dict) and str(item.get("emotion", "") or "").strip()
        ]
        _append_processing_trace(
            session,
            EngineBPhase.B5_EMOTIONAL_MIRROR,
            "情绪线索已识别",
            f"当前最强的情绪线索是：{'、'.join(emotion_names[:3])}。",
        )
    else:
        _append_processing_trace(
            session,
            EngineBPhase.B5_EMOTIONAL_MIRROR,
            "情绪不是主阻力",
            (
                "当前档位没有启用情绪镜像，所以这一步先不展开。"
                if not tier_config.get("enable_emotion_mirror")
                else "这一轮没有发现足够强的情绪干扰，核心问题更偏向信息和判断。"
            ),
        )

    session.phase = EngineBPhase.B5_5_ALTERNATIVE
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B5_5_ALTERNATIVE,
        "开始寻找第三条路",
        "我会试着把这个二选一题拆成一个更可逆、更现实的过渡方案，避免你被原题困死。",
    )
    session.alternative_path = engine_b_agents.run_b5_5_alternative_path(
        session.original_question,
        session.diagnosis_answers,
        session.value_profile,
        session.recommendation,
        max_tokens=int(tier_config.get("b5_max_tokens") or 2048),
    )
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    if session.alternative_path:
        _append_processing_trace(
            session,
            EngineBPhase.B5_5_ALTERNATIVE,
            "第三条路已生成",
            f"我补出了一条过渡路径：「{session.alternative_path.get('title', '第三条路')}」。",
        )

    session.phase = EngineBPhase.C1_REEVALUATION
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.C1_REEVALUATION,
        "开始重新评估",
        "前面的信息、框架和情绪线索正在汇总，我会把它们压缩成新的力量对比和建议。",
    )

    c1_result = engine_b_agents.run_c1_reevaluation(
        session.original_question,
        session.original_pro_total,
        session.original_con_total,
        session.missing_info_items,
        cognitive_frames=session.cognitive_frames,
        experience_cases=session.experience_cases,
        emotional_insight=session.emotional_insight,
        source_detection=session.source_detection,
        diagnosed_blockages=session.diagnosed_blockages,
        value_profile=session.value_profile,
        decision_biases=engine_b_agents._merge_bias_entries(
            session.decision_biases,
            session.emotional_insight.get("decision_biases", []) if isinstance(session.emotional_insight, dict) else [],
        ),
        external_signals=session.external_signals,
        max_tokens=int(tier_config.get("c1_max_tokens") or 2048),
    )

    session.updated_pro_total = c1_result.get("updated_pro_total", 50)
    session.updated_con_total = c1_result.get("updated_con_total", 50)
    session.recommendation = c1_result.get("recommendation", "")
    session.action_plan = c1_result.get("action_plan", "")
    session.reasoning = c1_result.get("reasoning", "")
    session.decision_biases = c1_result.get("decision_biases", [])
    session.bias_reminder = c1_result.get("bias_reminder", "")
    session.updated_at = now_iso()

    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.C1_REEVALUATION,
        "结论已生成",
        f"力量从 {session.original_pro_total}:{session.original_con_total} 调整到 {session.updated_pro_total}:{session.updated_con_total}，当前建议是「{session.recommendation or '尚未形成有效建议'}」。",
    )

    diff = abs(int(session.updated_pro_total) - int(session.updated_con_total))
    if diff <= 15 and not c1_result.get("skip_recheck"):
        try:
            clp_id = db_register_engine_b_as_clp(session.to_dict())
            _append_processing_trace(
                session,
                EngineBPhase.C1_REEVALUATION,
                "发现新的认知拉格朗日点",
                f"该议题已被注册为星图新节点：{clp_id}。您的决策案例已反哺进入系统谱系。",
            )
        except Exception:
            pass

    if c1_result.get("skip_recheck"):
        session.recheck = {
            **_default_recheck_state(),
            "needed": False,
            "status": "skipped",
            "reason": "本轮 C1 只形成了占位性结论，暂不进入 Engine A 二次检测。",
        }
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.C1_REEVALUATION,
            "这轮先不送回 Engine A",
            "当前 50:50 只表示还没形成可靠力矩，不再把占位结果误判成认知拉格朗日点。",
        )
        return session

    if not tier_config.get("enable_recheck", True):
        session.recheck = {
            **_default_recheck_state(),
            "needed": False,
            "status": "skipped",
            "reason": "当前档位关闭了 Engine A 二次检测，这轮结果直接作为决策建议输出。",
        }
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.C1_REEVALUATION,
            "当前档位跳过二次检测",
            "这档重点是尽快形成建议，不再把接近平衡的问题重新送回 Engine A。",
        )
        return session

    return _maybe_start_engine_b_recheck(session)


def start_engine_b_session(
    question: str,
    *,
    source_detection: dict | None = None,
    tier: str = "deep",
) -> EngineBSession:
    """启动一个新的 Engine B 会话。"""
    created = now_iso()
    normalized_tier = normalize_tier(tier)
    tier_config = get_tier_config(normalized_tier)
    session = EngineBSession.create_new(question, created, tier=normalized_tier)
    session.phase = EngineBPhase.B1_DIAGNOSIS
    normalized_source = _normalize_source_detection(source_detection)
    session.source_detection = normalized_source
    session.recheck = _default_recheck_state()
    if normalized_source:
        session.original_pro_total = normalized_source.get("original_pro_total", 50)
        session.original_con_total = normalized_source.get("original_con_total", 50)

    diagnosis_questions = engine_b_agents.run_b1_diagnosis(
        question,
        max_tokens=int(tier_config.get("b1_max_tokens") or 2048),
    )
    diagnosis_limit = int(tier_config.get("diagnosis_count") or 0)
    if diagnosis_limit > 0:
        diagnosis_questions = diagnosis_questions[:diagnosis_limit]
    session.diagnosis_questions = diagnosis_questions
    session.processing_trace = [{
        "id": uuid.uuid4().hex[:8],
        "phase": EngineBPhase.B1_DIAGNOSIS.value,
        "title": "Engine B 已启动",
        "detail": (
            f"Engine A 初检把这个问题送了过来。我先生成了 {len(diagnosis_questions)} 个追问，准备判断你卡在信息、框架、经验还是情绪。"
            if normalized_source else
            f"我先生成了 {len(diagnosis_questions)} 个追问，用来判断你卡在信息、框架、经验还是情绪。"
        ),
        "at": now_iso(),
    }]
    if normalized_source:
        result = normalized_source.get("result", {}) if isinstance(normalized_source.get("result"), dict) else {}
        failed_at = str(result.get("failed_at", "") or "未知阶段")
        summary = str(result.get("summary", "") or "").strip() or "初次检测认为它更像有方向的决策问题。"
        session.processing_trace.append({
            "id": uuid.uuid4().hex[:8],
            "phase": EngineBPhase.B1_DIAGNOSIS.value,
            "title": "接到 Engine A 初检结果",
            "detail": f"上一次检测在 {failed_at} 停下，摘要是：{summary}",
            "at": now_iso(),
        })

    engine_b_state.save_session(session)
    if not diagnosis_questions:
        session.phase = EngineBPhase.B2_INFO_FILL
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.B2_INFO_FILL,
            "这次无需追问，直接进入补齐阶段",
            "当前表述已经足够清晰，我直接开始补信息、补框架并重新评估。",
        )
        threading.Thread(
            target=_run_engine_b_enrichment_async,
            args=(session.session_id,),
            daemon=True,
        ).start()
    return session


def submit_engine_b_answer(session_id: str, question_id: str, answer: str) -> EngineBSession:
    """提交 B1 追问的回答。"""
    session = engine_b_state.load_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    session.diagnosis_answers[question_id] = answer
    session.last_error = ""
    session.updated_at = now_iso()

    answered_count = len(session.diagnosis_answers)
    total_questions = len(session.diagnosis_questions)

    if answered_count < total_questions:
        engine_b_state.save_session(session)
        return session

    session.phase = EngineBPhase.B2_INFO_FILL
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B2_INFO_FILL,
        "诊断回答已收齐",
        "我已经拿到你的全部回答，开始进入补信息、补框架和重新评估阶段。",
    )
    threading.Thread(
        target=_run_engine_b_enrichment_async,
        args=(session.session_id,),
        daemon=True,
    ).start()
    return session


def get_engine_b_status() -> dict:
    """获取 Engine B 当前状态。"""
    session = engine_b_state.load_active_session()
    if not session:
        return {"active": False}
    session_data = _normalize_session_snapshot(session.to_dict())
    hydrate_recheck_from_detection(session_data)
    return {
        "active": True,
        "session": session_data,
    }


def get_engine_b_status_for_session(session_id: str | None = None) -> dict:
    """按 session_id 获取 Engine B 状态；未提供时返回当前活跃会话。"""
    if session_id:
        session = engine_b_state.load_session(session_id)
    else:
        session = engine_b_state.load_active_session()
    if not session:
        return {"active": False}
    session_data = _normalize_session_snapshot(session.to_dict())
    hydrate_recheck_from_detection(session_data)
    return {
        "active": True,
        "session": session_data,
    }


def _mark_engine_b_error(session_id: str, error: Exception | str) -> None:
    session = engine_b_state.load_session(session_id)
    if not session:
        return
    session.phase = EngineBPhase.ABANDONED
    session.last_error = str(error)
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.ABANDONED,
        "这次处理没有顺利完成",
        f"技术原因：{session.last_error}",
    )


def _run_engine_b_enrichment_async(session_id: str) -> None:
    try:
        session = engine_b_state.load_session(session_id)
        if not session:
            return
        enrich_engine_b_session(session, force=True)
    except Exception as exc:
        _mark_engine_b_error(session_id, exc)


def _build_simulator_user_context(session: EngineBSession) -> str:
    return f"""原始问题：{session.original_question}
诊断卡点：{', '.join(session.diagnosed_blockages)}
价值排序：{session.value_profile.get('summary', '') if isinstance(session.value_profile, dict) else ''}
偏差提醒：{session.bias_reminder}
补充信息：{session.missing_info_items}
力量对比：正方{session.updated_pro_total} vs 反方{session.updated_con_total}
建议方向：{session.recommendation}
行动方案：{session.action_plan}
第三条路：{session.alternative_path.get('summary', '') if isinstance(session.alternative_path, dict) else ''}"""


def _format_sim_param_labels(fields: list[str]) -> str:
    labels = [
        engine_b_agents.SIM_PARAM_LABELS.get(field_name, field_name)
        for field_name in (fields or [])
    ]
    return "、".join(labels)


def _stage_followup_sim_questions(
    session: EngineBSession,
    *,
    user_params: dict | None = None,
    reason: str,
) -> EngineBSession:
    params = user_params if isinstance(user_params, dict) else engine_b_agents.parse_sim_params_from_answers(
        session.sim_answers,
        session.sim_questions,
        session.original_question,
    )
    missing_fields = engine_b_agents.missing_critical_sim_params(params)
    followups = engine_b_agents.build_followup_sim_questions(
        params,
        session.sim_questions,
        question_context=session.original_question,
    )
    if not followups:
        session.phase = EngineBPhase.B6_SIM_PARAMS
        session.last_error = "关键参数仍不足，暂时无法生成最终模拟。"
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.B6_SIM_PARAMS,
            "关键参数仍不足",
            f"{reason}。还缺：{_format_sim_param_labels(missing_fields)}。",
        )
        return session

    existing_ids = {
        str(item.get("id", "") or "").strip()
        for item in (session.sim_questions or [])
        if isinstance(item, dict)
    }
    next_questions = list(session.sim_questions or [])
    for index, item in enumerate(followups, start=1):
        candidate = dict(item)
        question_id = str(candidate.get("id", "") or "").strip()
        if not question_id or question_id in existing_ids:
            candidate["id"] = f"sim_followup_{candidate.get('field_name', 'field')}_{len(next_questions) + index}"
        next_questions.append(candidate)

    session.sim_questions = next_questions
    session.phase = EngineBPhase.B6_SIM_PARAMS
    session.last_error = ""
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B6_SIM_PARAMS,
        "关键参数还不够，继续补问",
        f"{reason}。我还缺 {_format_sim_param_labels(missing_fields)}，所以先不出最终量化推演。",
    )
    return session


def _regenerate_similar_timeline_if_needed(
    session: EngineBSession,
    *,
    user_context: str,
    choice_a: dict,
    choice_b: dict,
    user_params: dict,
    choice_a_timelines: dict,
    choice_b_timelines: dict,
    max_tokens: int,
) -> tuple[dict, dict]:
    similarity = engine_b_agents.simulator_choice_similarity(choice_a_timelines, choice_b_timelines)
    if similarity < engine_b_agents.SIMULATOR_SIMILARITY_THRESHOLD:
        return choice_a_timelines, choice_b_timelines

    _append_processing_trace(
        session,
        EngineBPhase.B7_SIM_TIMELINES,
        "两条路写得太像，触发重生成",
        f"当前 A/B 时间线相似度约 {similarity:.2f}。我会按不同语义槽位重推一次，强行拉开差异。",
    )
    regenerated_b = engine_b_agents.run_b7_timeline(
        user_context,
        choice_b["name"],
        choice_b["description"],
        user_params,
        max_tokens=max_tokens,
        temperature=0.42,
        slot_index=1,
        contrast_choice=choice_a,
        regenerate_hint="上一次和对照项太像。这次必须明确写出当前选项独有的代价、独有的关键动作、独有的长期后果。",
    )
    retry_similarity = engine_b_agents.simulator_choice_similarity(choice_a_timelines, regenerated_b)
    if retry_similarity < engine_b_agents.SIMULATOR_RETRY_SIMILARITY_THRESHOLD:
        _append_processing_trace(
            session,
            EngineBPhase.B7_SIM_TIMELINES,
            "相似度已拉开",
            f"重生成后相似度降到 {retry_similarity:.2f}，两条路已经不再共用同一套叙事。",
        )
        return choice_a_timelines, regenerated_b

    _append_processing_trace(
        session,
        EngineBPhase.B7_SIM_TIMELINES,
        "重生成后仍偏像，切换到强差异保底版",
        f"重生成后相似度仍有 {retry_similarity:.2f}，我改用强差异保底时间线，避免报告继续像模板复读。",
    )
    fallback_b = engine_b_agents.build_distinct_timeline_fallback(
        choice_b["name"],
        choice_b["description"],
        user_params,
    )
    return choice_a_timelines, fallback_b


def _run_simulator_async(session_id: str) -> None:
    try:
        session = engine_b_state.load_session(session_id)
        if not session:
            return
        tier_config = _get_session_tier_config(session)

        user_params = engine_b_agents.parse_sim_params_from_answers(
            session.sim_answers,
            session.sim_questions,
            session.original_question,
        )
        missing_fields = engine_b_agents.missing_critical_sim_params(user_params)
        if missing_fields:
            _stage_followup_sim_questions(
                session,
                user_params=user_params,
                reason=f"进入第三幕前发现关键参数仍缺 {_format_sim_param_labels(missing_fields)}",
            )
            return
        _append_processing_trace(
            session,
            EngineBPhase.B6_SIM_PARAMS,
            "模拟参数已解析",
            f"已拿到关键参数：安全垫约 {user_params.get('savings_months')} 个月，回头时间「{user_params.get('time_to_reverse')}」，最怕的是「{user_params.get('worst_fear')}」。",
        )
        user_context = _build_simulator_user_context(session)

        choice_options = engine_b_agents.extract_choice_options(
            session.original_question,
            session.recommendation,
            session.action_plan,
            max_tokens=int(tier_config.get("choice_extract_max_tokens") or 900),
        )
        choice_a = choice_options[0]
        choice_b = choice_options[1]
        _append_processing_trace(
            session,
            EngineBPhase.B7_SIM_TIMELINES,
            "比较选项已提炼",
            f"我会重点推演「{choice_a['name']}」和「{choice_b['name']}」两条路。",
        )

        _append_processing_trace(
            session,
            EngineBPhase.B7_SIM_TIMELINES,
            f"开始写 {choice_a['name']} 的未来",
            f"我先沿着「{choice_a['name']}」这条路写顺风局、平稳局和逆风局，看它最可能把你带到哪里。",
        )
        choice_a_timelines = engine_b_agents.run_b7_timeline(
            user_context,
            choice_a["name"],
            choice_a["description"],
            user_params,
            max_tokens=int(tier_config.get("b7_max_tokens") or 2600),
            slot_index=0,
            contrast_choice=choice_b,
        )
        if isinstance(choice_a_timelines, dict) and choice_a_timelines.get("fallback_mode") == "local_fast":
            _append_processing_trace(
                session,
                EngineBPhase.B7_SIM_TIMELINES,
                f"{choice_a['name']} 已切到极速模式",
                "上游模型响应太慢，我先用本地极速模拟补出这条时间线，避免整轮卡死。",
            )
        _append_processing_trace(
            session,
            EngineBPhase.B7_SIM_TIMELINES,
            f"已推演 {choice_a['name']}",
            "这一条路的顺风局、平稳局和逆风局已经生成。",
        )
        _append_processing_trace(
            session,
            EngineBPhase.B7_SIM_TIMELINES,
            f"开始写 {choice_b['name']} 的未来",
            f"接着我会沿着「{choice_b['name']}」这条路重写一遍，确保两条路不是共用同一套模板叙事。",
        )
        choice_b_timelines = engine_b_agents.run_b7_timeline(
            user_context,
            choice_b["name"],
            choice_b["description"],
            user_params,
            max_tokens=int(tier_config.get("b7_max_tokens") or 2600),
            slot_index=1,
            contrast_choice=choice_a,
        )
        if isinstance(choice_b_timelines, dict) and choice_b_timelines.get("fallback_mode") == "local_fast":
            _append_processing_trace(
                session,
                EngineBPhase.B7_SIM_TIMELINES,
                f"{choice_b['name']} 已切到极速模式",
                "第二条路也改用本地极速模拟继续生成，确保你能拿到完整对比。",
            )
        _append_processing_trace(
            session,
            EngineBPhase.B7_SIM_TIMELINES,
            f"已推演 {choice_b['name']}",
            "另一条路的三种走势也已经生成，接下来开始找关键岔路口。",
        )
        choice_a_timelines, choice_b_timelines = _regenerate_similar_timeline_if_needed(
            session,
            user_context=user_context,
            choice_a=choice_a,
            choice_b=choice_b,
            user_params=user_params,
            choice_a_timelines=choice_a_timelines,
            choice_b_timelines=choice_b_timelines,
            max_tokens=int(tier_config.get("b7_max_tokens") or 2600),
        )

        session = engine_b_state.load_session(session_id)
        if not session:
            return
        session.phase = EngineBPhase.B8_SIM_COPING
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.B8_SIM_COPING,
            "开始拆岔路口预案",
            "我在把未来节点拆成绿灯、黄灯、红灯三种信号，并补上最坏情况生存方案。",
        )

        coping_plan = engine_b_agents.run_b8_coping_plan(
            choice_a_timelines,
            choice_b_timelines,
            user_params,
            max_tokens=int(tier_config.get("b8_max_tokens") or 1800),
        )
        if isinstance(coping_plan, dict) and coping_plan.get("fallback_mode") == "local_fast":
            _append_processing_trace(
                session,
                EngineBPhase.B8_SIM_COPING,
                "预案已切到极速模式",
                "上游响应偏慢，我先用本地规则补齐岔路口和最坏情况生存方案。",
            )
        crossroads = coping_plan.get("crossroads", []) if isinstance(coping_plan, dict) else []
        _append_processing_trace(
            session,
            EngineBPhase.B8_SIM_COPING,
            "预案已生成",
            f"一共识别到 {len(crossroads)} 个关键岔路口，并补上了逆风局下的应对方案。",
        )

        session = engine_b_state.load_session(session_id)
        if not session:
            return
        session.phase = EngineBPhase.B9_SIM_COMPARISON
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.B9_SIM_COMPARISON,
            "开始压缩成行动地图",
            "我在把两条路放到同一张图里，收成你可以直接执行的未来对比和行动建议。",
        )

        comparison = engine_b_agents.run_b9_comparison(
            choice_a_timelines,
            choice_b_timelines,
            user_params,
            value_profile=session.value_profile,
            decision_biases=session.decision_biases,
            alternative_path=session.alternative_path,
            external_signals=session.external_signals,
            max_tokens=int(tier_config.get("b9_max_tokens") or 1600),
        )
        if isinstance(comparison, dict) and comparison.get("fallback_mode") == "local_fast":
            _append_processing_trace(
                session,
                EngineBPhase.B9_SIM_COMPARISON,
                "总览已切到极速模式",
                "最终对比改用本地压缩逻辑生成，所以你不会再因为上游超时拿不到结果。",
            )

        monte_carlo = {}
        if tier_config.get("enable_ultra_monte_carlo"):
            _append_processing_trace(
                session,
                EngineBPhase.B9_SIM_COMPARISON,
                "Ultra Monte Carlo 开始",
                (
                    f"将在 Pro 级未来推演基础上追加 {int(tier_config.get('ultra_mc_branches') or 800)} 次分支采样，"
                    f"{int(tier_config.get('ultra_mc_personas') or 40)} 个代理参与碰撞。"
                    + (
                        "当前显式关闭 LLM 面板，只做本地采样；如需 Ultra 真实烧 token，请把 CLP_ULTRA_MC_LLM_PANELS 设为大于 0。"
                        if int(tier_config.get("ultra_mc_llm_panels") or 0) <= 0
                        else f"本轮会追加 {int(tier_config.get('ultra_mc_llm_panels') or 0)} 个真实 LLM 委员会，并在最后做一次合议综合。"
                    )
                ),
            )
            monte_carlo = engine_b_agents.run_ultra_monte_carlo_collision(
                question=session.original_question,
                choice_a_sim=choice_a_timelines,
                choice_b_sim=choice_b_timelines,
                user_params=user_params,
                value_profile=session.value_profile,
                decision_biases=session.decision_biases,
                external_signals=session.external_signals,
                sample_count=int(tier_config.get("ultra_mc_branches") or 800),
                persona_count=int(tier_config.get("ultra_mc_personas") or 40),
                agents_per_branch=int(tier_config.get("ultra_mc_agents_per_branch") or 15),
                rounds=int(tier_config.get("ultra_mc_rounds") or 4),
                branch_sample_limit=int(tier_config.get("ultra_mc_branch_sample_limit") or 80),
                llm_panels=int(tier_config.get("ultra_mc_llm_panels") or 0),
                llm_max_tokens=int(tier_config.get("ultra_mc_llm_max_tokens") or 4096),
            )
            smooth_prob = monte_carlo.get("smooth_prob") if isinstance(monte_carlo, dict) else {}
            if not isinstance(smooth_prob, dict):
                smooth_prob = {}
            if isinstance(smooth_prob, dict):
                comparison = dict(comparison)
                comparison["probability_optimistic"] = smooth_prob.get("optimistic", comparison.get("probability_optimistic"))
                comparison["probability_baseline"] = smooth_prob.get("baseline", comparison.get("probability_baseline"))
                comparison["probability_pessimistic"] = smooth_prob.get("pessimistic", comparison.get("probability_pessimistic"))
            _append_processing_trace(
                session,
                EngineBPhase.B9_SIM_COMPARISON,
                "Ultra Monte Carlo 完成",
                (
                    "平滑概率分布："
                    f"顺风 {smooth_prob.get('optimistic', '--')}% / "
                    f"平稳 {smooth_prob.get('baseline', '--')}% / "
                    f"逆风 {smooth_prob.get('pessimistic', '--')}%。"
                    f"LLM 面板调用 {monte_carlo.get('actual_llm_calls', 0) if isinstance(monte_carlo, dict) else 0} 次。"
                ),
            )

        session = engine_b_state.load_session(session_id)
        if not session:
            return
        session.simulator_output = engine_b_agents.normalize_simulator_output({
            "user_params": user_params,
            "choice_a": choice_a_timelines,
            "choice_b": choice_b_timelines,
            "crossroads": coping_plan.get("crossroads", []),
            "worst_case_survival_plan": coping_plan.get("worst_case_survival_plan", {}),
            "milestones": coping_plan.get("milestone_check_system", []),
            "comparison_summary": comparison.get("comparison_summary", ""),
            "action_map_a": comparison.get("action_map_a", []),
            "action_map_b": comparison.get("action_map_b", []),
            "final_insight": comparison.get("final_insight", ""),
            "regret_score_a": comparison.get("regret_score_a"),
            "regret_score_b": comparison.get("regret_score_b"),
            "probability_optimistic": comparison.get("probability_optimistic"),
            "probability_baseline": comparison.get("probability_baseline"),
            "probability_pessimistic": comparison.get("probability_pessimistic"),
            "decision_biases": comparison.get("decision_biases", session.decision_biases),
            "bias_reminder": comparison.get("bias_reminder", session.bias_reminder),
            "third_path": comparison.get("third_path", session.alternative_path),
            "market_signals": session.external_signals,
            "value_profile": session.value_profile,
            "monte_carlo": monte_carlo,
        })
        session.phase = EngineBPhase.SIMULATOR_COMPLETE
        session.last_error = ""
        session.updated_at = now_iso()
        engine_b_state.save_session(session)
        _append_processing_trace(
            session,
            EngineBPhase.SIMULATOR_COMPLETE,
            "未来预演已完成",
            f"最终洞察：{session.simulator_output.get('final_insight', '两条路的时间线、预案和行动地图都已经准备好了。')}",
        )
    except Exception as exc:
        _mark_engine_b_error(session_id, exc)


def reset_engine_b() -> None:
    """重置 Engine B 会话。"""
    active_id = engine_b_state.get_active_session_id()
    if active_id:
        engine_b_state.delete_session(active_id)
    engine_b_state.clear_active_session()


def _kickoff_simulator_generation(
    session: EngineBSession,
    *,
    detail: str,
) -> EngineBSession:
    session.phase = EngineBPhase.B7_SIM_TIMELINES
    session.last_error = ""
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B7_SIM_TIMELINES,
        "参数已收齐",
        detail,
    )
    threading.Thread(
        target=_run_simulator_async,
        args=(session.session_id,),
        daemon=True,
    ).start()
    return session


def start_simulator(session_id: str) -> EngineBSession:
    """启动选择模拟器。"""
    session = engine_b_state.load_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    tier_config = _get_session_tier_config(session)
    if not (tier_config.get("enable_simulation") or tier_config.get("allow_manual_simulation")):
        raise ValueError("当前思考档位没有开启未来模拟。")

    if session.diagnosis_questions and len(session.diagnosis_answers) < len(session.diagnosis_questions):
        raise ValueError("请先完成 Engine B 诊断问答")

    if not session_has_c1_result(session):
        session = enrich_engine_b_session(session, force=True)

    recheck = session.recheck if isinstance(session.recheck, dict) else {}
    recheck_status = str(recheck.get("status", "") or "").strip()
    if recheck_status in {"pending", "running"}:
        raise ValueError("Engine A 二次检测仍在进行，请先等待最终结论。")
    recheck_job = recheck.get("job") if isinstance(recheck.get("job"), dict) else {}
    recheck_result = recheck_job.get("result") if isinstance(recheck_job.get("result"), dict) else {}
    if recheck_status == "completed" and recheck_result.get("is_lagrange_point") is True:
        raise ValueError("二次检测已经确认这是认知拉格朗日点，不需要再启动选择模拟器。")

    if session.phase in {
        EngineBPhase.B7_SIM_TIMELINES,
        EngineBPhase.B8_SIM_COPING,
        EngineBPhase.B9_SIM_COMPARISON,
        EngineBPhase.SIMULATOR_COMPLETE,
    }:
        return session

    if session.phase == EngineBPhase.B6_SIM_PARAMS:
        pending = session.sim_questions and len(session.sim_answers) < len(session.sim_questions)
        if pending:
            return session
        if not session.simulator_output:
            user_params = engine_b_agents.parse_sim_params_from_answers(
                session.sim_answers,
                session.sim_questions,
                session.original_question,
            )
            missing_fields = engine_b_agents.missing_critical_sim_params(user_params)
            if missing_fields:
                return _stage_followup_sim_questions(
                    session,
                    user_params=user_params,
                    reason=f"还不能开始未来模拟，因为缺少 {_format_sim_param_labels(missing_fields)}",
                )
            return _kickoff_simulator_generation(
                session,
                detail="关键参数已经收齐，开始推演两条路各自的未来时间线。",
            )

    session.phase = EngineBPhase.B6_SIM_PARAMS
    session.last_error = ""
    sim_questions = engine_b_agents.run_b6_sim_params(
        session.original_question,
        session.recommendation,
        max_tokens=int(tier_config.get("b6_max_tokens") or 1024),
    )
    if not sim_questions:
        sim_questions = engine_b_agents.ensure_sim_question_coverage(
            [],
            question_context=session.original_question,
        )
    session.sim_questions = sim_questions
    session.sim_answers = {}
    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    _append_processing_trace(
        session,
        EngineBPhase.B6_SIM_PARAMS,
        "模拟器已启动",
        f"我先准备了 {len(sim_questions)} 个参数问题，用来补齐安全垫、固定支出、可逆性和最坏情况，补齐前不会直接出最终量化推演。",
    )
    return session


def submit_sim_answer(session_id: str, question_id: str, answer: str) -> EngineBSession:
    """提交模拟参数收集的回答。"""
    session = engine_b_state.load_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    session.sim_answers[question_id] = answer
    session.last_error = ""
    session.updated_at = now_iso()

    answered_count = len(session.sim_answers)
    total_questions = len(session.sim_questions)

    if answered_count < total_questions:
        engine_b_state.save_session(session)
        return session

    user_params = engine_b_agents.parse_sim_params_from_answers(
        session.sim_answers,
        session.sim_questions,
        session.original_question,
    )
    missing_fields = engine_b_agents.missing_critical_sim_params(user_params)
    if missing_fields:
        return _stage_followup_sim_questions(
            session,
            user_params=user_params,
            reason=f"关键参数还没收齐，暂时不能出最终量化报告。当前还缺 {_format_sim_param_labels(missing_fields)}",
        )

    return _kickoff_simulator_generation(
        session,
        detail="我已经拿到模拟所需的关键参数，开始推演两条路各自的未来时间线。",
    )
