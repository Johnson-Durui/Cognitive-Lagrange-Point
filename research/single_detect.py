"""单题认知拉格朗日点检测。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Callable, Optional

try:
    from .api import call_agent_json
    from .models import CandidateQuestion, ConfirmedLagrangePoint
    from .phase2_filter import (
        FILTER2_BALANCE_THRESHOLD,
        FILTER2_MAX_DIRECTION_SHARE,
        STANCES,
        evaluate_candidate as evaluate_filter2_candidate,
    )
    from .phase2_filter1 import FILTER1_DIFF_THRESHOLD, evaluate_candidate as evaluate_filter1_candidate
    from .phase2_filter3 import FILTER3_REQUIRED_STABLE, evaluate_candidate as evaluate_filter3_candidate
    from .phase3_analysis import analyze_forces
except ImportError:  # pragma: no cover - allow top-level import from server.py
    from api import call_agent_json
    from models import CandidateQuestion, ConfirmedLagrangePoint
    from phase2_filter import (
        FILTER2_BALANCE_THRESHOLD,
        FILTER2_MAX_DIRECTION_SHARE,
        STANCES,
        evaluate_candidate as evaluate_filter2_candidate,
    )
    from phase2_filter1 import FILTER1_DIFF_THRESHOLD, evaluate_candidate as evaluate_filter1_candidate
    from phase2_filter3 import FILTER3_REQUIRED_STABLE, evaluate_candidate as evaluate_filter3_candidate
    from phase3_analysis import analyze_forces

ProgressCallback = Callable[[str, dict], None]

DETECTION_ANALYSIS_SYSTEM = """你是一位“认知拉格朗日点预分析师”。

给定用户输入的一个纠结问题，请先做进入正式筛选前的结构预判。你的目标不是直接下最终结论，而是：

1. 提炼 2-3 组真正冲突的核心张力
2. 估计这个问题更像哪一类：
   - 两难选择（有答案但代价大）
   - 信息不足（补信息后会明显偏向一边）
   - 拉格朗日点（结构性无解）
3. 给出一句“为什么它看起来可能平衡”的解释，供后续筛子1使用

请输出 JSON：
{
  "tensions": [
    {"pro": "张力A左侧", "con": "张力A右侧"},
    {"pro": "张力B左侧", "con": "张力B右侧"}
  ],
  "classifications": {
    "dilemma": 35,
    "info_gap": 25,
    "clp": 40
  },
  "balance_rationale": "一句话说明为什么它暂时看起来像平衡问题",
  "initial_score": 78,
  "analysis_summary": "对问题结构的简短判断"
}

规则：
- classifications 三项是 0-100 的整数，总和尽量为 100，允许有 1-2 点误差
- initial_score 表示“值得进入正式检测”的程度，0-100
- balance_rationale 必须具体，不要空话
- 只输出 JSON
"""


@dataclass(frozen=True)
class DetectionProfile:
    name: str
    analysis_max_tokens: int = 2200
    enable_filter1: bool = True
    filter1_level_limit: int = 4
    filter1_threshold: float = FILTER1_DIFF_THRESHOLD
    philosopher_count: int = len(STANCES)
    filter2_balance_threshold: float = FILTER2_BALANCE_THRESHOLD
    filter2_max_direction_share: float = FILTER2_MAX_DIRECTION_SHARE
    enable_filter3: bool = True
    fail_open_to_engine_b: bool = False


def resolve_detection_profile(mode: str | None) -> DetectionProfile:
    normalized = str(mode or "initial").strip().lower()
    if normalized == "decision_deep":
        return DetectionProfile(
            name=normalized,
            analysis_max_tokens=1400,
            filter1_level_limit=2,
            philosopher_count=4,
            filter2_balance_threshold=max(FILTER2_BALANCE_THRESHOLD, 28),
            filter2_max_direction_share=max(FILTER2_MAX_DIRECTION_SHARE, 0.80),
            enable_filter3=False,
            fail_open_to_engine_b=True,
        )
    if normalized == "decision_pro":
        return DetectionProfile(
            name=normalized,
            analysis_max_tokens=2600,
            filter1_level_limit=4,
            philosopher_count=5,
            enable_filter3=True,
            fail_open_to_engine_b=True,
        )
    if normalized == "decision_ultra":
        return DetectionProfile(
            name=normalized,
            analysis_max_tokens=3600,
            filter1_level_limit=4,
            philosopher_count=len(STANCES),
            enable_filter3=True,
            fail_open_to_engine_b=True,
        )
    if normalized == "engine_b_recheck":
        return DetectionProfile(
            name=normalized,
            analysis_max_tokens=1600,
            filter1_level_limit=2,
            philosopher_count=4,
            filter2_balance_threshold=max(FILTER2_BALANCE_THRESHOLD, 26),
            filter2_max_direction_share=max(FILTER2_MAX_DIRECTION_SHARE, 0.80),
            enable_filter3=False,
            fail_open_to_engine_b=True,
        )
    return DetectionProfile(name=normalized or "initial")


def _emit(callback: Optional[ProgressCallback], event: str, **payload) -> None:
    if callback is not None:
        callback(event, payload)


def _normalize_percent(value, default: int = 0) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, num))


def _fallback_analysis(question: str) -> dict:
    trimmed = str(question or "").strip()
    return {
        "tensions": [{"pro": "尝试改变以换取更大收益", "con": "维持现状以降低现实代价"}],
        "classifications": {"dilemma": 58, "info_gap": 32, "clp": 10},
        "balance_rationale": "这个问题看起来平衡，往往是因为收益诱惑和代价恐惧都很具体，彼此都不愿轻易退场。",
        "initial_score": 68,
        "analysis_summary": f"快速兜底分析：{trimmed or '这个问题'}更像现实世界里的高代价选择，不像纯结构性无解。",
    }


def analyze_question_structure(
    question: str,
    *,
    max_tokens: int = 2200,
    allow_fallback: bool = False,
) -> dict:
    try:
        data = call_agent_json(
            DETECTION_ANALYSIS_SYSTEM,
            f"请分析这个问题：\n\n{question}",
            max_tokens=max_tokens,
            temperature=0.4,
        )
    except Exception:
        if not allow_fallback:
            raise
        data = _fallback_analysis(question)

    tensions = []
    for item in data.get("tensions", [])[:3]:
        if not isinstance(item, dict):
            continue
        pro = str(item.get("pro", "")).strip()
        con = str(item.get("con", "")).strip()
        if pro and con:
            tensions.append({"pro": pro, "con": con})

    if not tensions:
        tensions = [{"pro": "支持做出改变", "con": "支持维持现状"}]

    raw_cls = data.get("classifications", {}) if isinstance(data.get("classifications"), dict) else {}
    classifications = {
        "dilemma": _normalize_percent(raw_cls.get("dilemma"), 34),
        "info_gap": _normalize_percent(raw_cls.get("info_gap"), 33),
        "clp": _normalize_percent(raw_cls.get("clp"), 33),
    }

    return {
        "tensions": tensions,
        "classifications": classifications,
        "balance_rationale": str(data.get("balance_rationale", "")).strip() or "这个问题表面平衡，是因为正反两边都各自抓住了一个无法轻易让步的现实约束。",
        "initial_score": _normalize_percent(data.get("initial_score"), 70),
        "analysis_summary": str(data.get("analysis_summary", "")).strip(),
    }


def _build_candidate(question: str, analysis: dict) -> CandidateQuestion:
    return CandidateQuestion(
        id=f"DQ-{uuid.uuid4().hex[:8]}",
        question_text=question,
        miner_source="manual-detect",
        balance_rationale=analysis["balance_rationale"],
        initial_score=analysis["initial_score"],
        selected_for_pipeline=True,
    )


def _summarize_filter1(candidate: CandidateQuestion) -> dict:
    details = candidate.filter_1_details or []
    failed_detail = next((item for item in details if item.get("delta", 0) > FILTER1_DIFF_THRESHOLD), None)
    summary = candidate.filter_1_summary or "信息注入测试已完成"
    if candidate.passed_filter_1 is False and failed_detail:
        summary = (
            f"{failed_detail.get('label', '当前量级')} 注入后，"
            f"正反差值扩大到 {failed_detail.get('delta', '?')}，僵局被打破。"
        )
    return {
        "passed": candidate.passed_filter_1,
        "summary": summary,
        "details": details,
    }


def _summarize_filter2(candidate: CandidateQuestion) -> dict:
    details = candidate.filter_2_details or []
    framework_count = len(details) or len(STANCES)
    summary = (
        f"{framework_count} 个框架里形成 {candidate.filter_2_distribution or '?'} 分布，"
        f"力矩差 {candidate.filter_2_balance_score:.1f}% 。"
    )
    if candidate.passed_filter_2 is False:
        summary += "多数框架已明显偏向同一方向。"
    elif candidate.passed_filter_2 is True:
        summary += "多数框架没有压倒性共识。"
    return {
        "passed": candidate.passed_filter_2,
        "summary": summary,
        "details": details,
        "distribution": candidate.filter_2_distribution,
        "balance_score": candidate.filter_2_balance_score,
    }


def _summarize_filter3(candidate: CandidateQuestion) -> dict:
    details = candidate.filter_3_details or []
    summary = candidate.filter_3_summary or "重述稳定性测试已完成"
    if candidate.filter_3_classification:
        summary = f"{summary}；分类：{candidate.filter_3_classification}"
    return {
        "passed": candidate.passed_filter_3,
        "summary": summary,
        "details": details,
        "stable_count": candidate.filter_3_stable_count,
        "classification": candidate.filter_3_classification,
    }


def _build_failure_result(candidate: CandidateQuestion, stage: str) -> dict:
    if stage == "filter1":
        failure_reason = "补充足够信息后，平衡被打破，这更像信息不足而不是结构性无解。"
    elif stage == "filter2":
        failure_reason = "跨哲学框架后，多数框架开始明显偏向一边，这说明问题存在倾向性答案。"
    else:
        failure_reason = "一旦换一种表达方式，这个问题就不再稳定平衡，因此不是稳定的拉格朗日点。"

    return {
        "is_lagrange_point": False,
        "failed_at": stage,
        "summary": failure_reason,
        "recommend_engine_b": True,
        "candidate": candidate.to_dict(),
        "clp": None,
    }


def _build_success_result(candidate: CandidateQuestion, clp: ConfirmedLagrangePoint) -> dict:
    return {
        "is_lagrange_point": True,
        "failed_at": None,
        "summary": "三层筛子之后仍保持平衡，这个问题更接近真正的认知拉格朗日点。",
        "recommend_engine_b": False,
        "candidate": candidate.to_dict(),
        "clp": clp.to_dict(),
    }


def _build_open_result(candidate: CandidateQuestion, stage: str, summary: str) -> dict:
    return {
        "is_lagrange_point": False,
        "failed_at": stage,
        "summary": summary,
        "recommend_engine_b": True,
        "candidate": candidate.to_dict(),
        "clp": None,
    }


def _empty_filter3_summary(summary: str) -> dict:
    return {
        "passed": None,
        "summary": summary,
        "details": [],
        "stable_count": 0,
        "classification": "",
    }


def detect_single_question(
    question: str,
    progress_callback: Optional[ProgressCallback] = None,
    *,
    mode: str = "initial",
) -> dict:
    profile = resolve_detection_profile(mode)
    analysis = analyze_question_structure(
        question,
        max_tokens=profile.analysis_max_tokens,
        allow_fallback=profile.fail_open_to_engine_b,
    )
    _emit(progress_callback, "analysis_ready", analysis=analysis)

    candidate = _build_candidate(question, analysis)

    if profile.enable_filter1:
        _emit(progress_callback, "filter_started", filter_name="filter1")
        evaluate_filter1_candidate(
            candidate,
            level_limit=profile.filter1_level_limit,
            threshold=profile.filter1_threshold,
        )
        filter1 = _summarize_filter1(candidate)
        _emit(progress_callback, "filter_finished", filter_name="filter1", filter_data=filter1, candidate=candidate.to_dict())
        if candidate.passed_filter_1 is None:
            if profile.fail_open_to_engine_b:
                return {
                    "analysis": analysis,
                    "filters": {
                        "filter1": filter1,
                        "filter2": {"passed": None, "summary": "", "details": []},
                        "filter3": _empty_filter3_summary("首幕检测未拿到稳定结果，直接转入 Engine B 补全。"),
                    },
                    "result": _build_open_result(
                        candidate,
                        "filter1_uncertain",
                        "筛子1超时或数据不足。为避免页面一直卡住，我先把它当作可通过补全推进的问题，直接交给 Engine B。",
                    ),
                }
            raise RuntimeError("筛子1没有拿到足够稳定的结果，请稍后重试。")
        if candidate.passed_filter_1 is not True:
            return {
                "analysis": analysis,
                "filters": {
                    "filter1": filter1,
                    "filter2": {"passed": None, "summary": "", "details": []},
                    "filter3": {"passed": None, "summary": "", "details": []},
                },
                "result": _build_failure_result(candidate, "filter1"),
            }
    else:
        candidate.passed_filter_1 = True
        filter1 = {"passed": True, "summary": "当前档位跳过筛子1。", "details": []}

    _emit(progress_callback, "filter_started", filter_name="filter2")
    evaluate_filter2_candidate(
        candidate,
        stances=STANCES[: max(1, min(profile.philosopher_count, len(STANCES)))],
        balance_threshold=profile.filter2_balance_threshold,
        max_direction_share=profile.filter2_max_direction_share,
    )
    filter2 = _summarize_filter2(candidate)
    _emit(progress_callback, "filter_finished", filter_name="filter2", filter_data=filter2, candidate=candidate.to_dict())
    if candidate.passed_filter_2 is None:
        if profile.fail_open_to_engine_b:
            return {
                "analysis": analysis,
                "filters": {
                    "filter1": filter1,
                    "filter2": filter2,
                    "filter3": _empty_filter3_summary("首幕检测未拿到稳定结果，直接转入 Engine B 补全。"),
                },
                "result": _build_open_result(
                    candidate,
                    "filter2_uncertain",
                    "筛子2超时或有效框架不足。为了让完整流程继续推进，我直接把它送入 Engine B 做补全和建议。",
                ),
            }
        raise RuntimeError("筛子2没有拿到足够稳定的结果，请稍后重试。")
    if candidate.passed_filter_2 is not True:
        return {
            "analysis": analysis,
            "filters": {
                "filter1": filter1,
                "filter2": filter2,
                "filter3": {"passed": None, "summary": "", "details": []},
            },
            "result": _build_failure_result(candidate, "filter2"),
        }

    if not profile.enable_filter3:
        filter3 = _empty_filter3_summary("当前档位先不跑筛子3，直接进入 Engine B 做补全、复核和未来模拟。")
        return {
            "analysis": analysis,
            "filters": {
                "filter1": filter1,
                "filter2": filter2,
                "filter3": filter3,
            },
            "result": _build_open_result(
                candidate,
                "filter3_skipped",
                "前两层筛选后问题仍有拉扯，但当前档位优先给你可执行答案，所以先进入 Engine B 补全并保留后续复核。",
            ),
        }

    _emit(progress_callback, "filter_started", filter_name="filter3")
    evaluate_filter3_candidate(candidate)
    filter3 = _summarize_filter3(candidate)
    _emit(progress_callback, "filter_finished", filter_name="filter3", filter_data=filter3, candidate=candidate.to_dict())
    if candidate.passed_filter_3 is None:
        if profile.fail_open_to_engine_b:
            return {
                "analysis": analysis,
                "filters": {
                    "filter1": filter1,
                    "filter2": filter2,
                    "filter3": filter3,
                },
                "result": _build_open_result(
                    candidate,
                    "filter3_uncertain",
                    "筛子3超时或不够稳定。为了不让流程悬空，我先按“需要 Engine B 补全”处理。",
                ),
            }
        raise RuntimeError("筛子3没有拿到足够稳定的结果，请稍后重试。")
    if candidate.passed_filter_3 is not True:
        return {
            "analysis": analysis,
            "filters": {
                "filter1": filter1,
                "filter2": filter2,
                "filter3": filter3,
            },
            "result": _build_failure_result(candidate, "filter3"),
        }

    _emit(progress_callback, "force_analysis_started")
    clp = analyze_forces(candidate, 0)
    return {
        "analysis": analysis,
        "filters": {
            "filter1": filter1,
            "filter2": filter2,
            "filter3": filter3,
        },
        "result": _build_success_result(candidate, clp),
    }
