"""认知拉格朗日点 · 阶段二：信息注入测试（筛子1）"""

from __future__ import annotations

import os

from .api import call_agent_json
from .models import CandidateQuestion

FILTER1_DIFF_THRESHOLD = float(os.environ.get("CLP_FILTER1_DIFF_THRESHOLD", "15"))
FILTER1_LEVEL_LIMIT = max(1, min(4, int(os.environ.get("CLP_FILTER1_LEVEL_LIMIT", "4"))))

INFO_LEVELS = [
    (
        1,
        "量级1",
        "补充约100字的背景信息，只提供最基础的事实补充，不要直接替问题做结论。",
        900,
    ),
    (
        2,
        "量级2",
        "补充约500字的多角度信息，给出彼此冲突的数据、案例和利益相关方视角，但不要替代评估。",
        1400,
    ),
    (
        3,
        "量级3",
        "补充约2000字的深度分析级信息，覆盖历史背景、反方证据、支持方证据、现实约束与反例。",
        3200,
    ),
    (
        4,
        "量级4",
        "你现在假设自己是该问题对应领域的教科书级专家，用专家视角补充最关键知识、常见误解和已知边界。",
        3600,
    ),
]

FILTER1_SYSTEM = """你是一个“信息注入测试Agent”，负责检测一个候选问题的平衡性是否只是源于信息不足。

请你对给定问题执行以下动作：
1. 按指定量级补充背景信息
2. 在注入这些信息后，重新评估该问题的正方力量和反方力量
3. 判断僵局是否被打破

输出 JSON：
{{
  "injected_info": "本量级补充的信息",
  "pro_strength": 68,
  "con_strength": 61,
  "delta": 7,
  "balance_holds": true,
  "reasoning": "为什么在这一级信息下仍然平衡或已经失衡"
}}

规则：
- pro_strength / con_strength 都是 0-100 的整数
- delta = |pro_strength - con_strength|
- 如果 delta > {threshold}，则 balance_holds 必须为 false
- 只输出 JSON，不要输出其他内容"""


def _resolve_threshold(threshold: float | None) -> float:
    try:
        value = float(threshold)
    except (TypeError, ValueError):
        return FILTER1_DIFF_THRESHOLD
    return max(1.0, value)


def _resolve_level_limit(level_limit: int | None) -> int:
    try:
        value = int(level_limit)
    except (TypeError, ValueError):
        return FILTER1_LEVEL_LIMIT
    return max(1, min(len(INFO_LEVELS), value))


def _normalize_detail(level: int, label: str, result: dict, *, threshold: float) -> dict:
    pro = int(result.get("pro_strength", 0))
    con = int(result.get("con_strength", 0))
    delta = abs(pro - con)
    return {
        "level": level,
        "label": label,
        "injected_info": result.get("injected_info", "").strip(),
        "pro_strength": pro,
        "con_strength": con,
        "delta": delta,
        "balance_holds": delta <= threshold,
        "reasoning": result.get("reasoning", "").strip(),
    }


def _detail_summary(details: list[dict]) -> str:
    ordered = sorted(
        (item for item in details if isinstance(item, dict) and item.get("level")),
        key=lambda item: item["level"],
    )
    return " | ".join(
        f"L{item['level']} Δ{item.get('delta', '?')}"
        for item in ordered
    )


def _evaluate_level(
    question: str,
    balance_rationale: str,
    level: int,
    label: str,
    instruction: str,
    max_tokens: int,
    *,
    threshold: float,
) -> dict:
    system = FILTER1_SYSTEM.format(threshold=int(threshold))
    user_message = (
        f"候选问题：{question}\n\n"
        f"初始平衡理由：{balance_rationale}\n\n"
        f"当前测试量级：{label}\n"
        f"信息注入要求：{instruction}\n\n"
        f"请开始本量级测试。"
    )
    data = call_agent_json(system, user_message, max_tokens=max_tokens, temperature=0.3)
    return _normalize_detail(level, label, data, threshold=threshold)


def evaluate_candidate(
    candidate: CandidateQuestion,
    *,
    level_limit: int | None = None,
    threshold: float | None = None,
) -> CandidateQuestion:
    """对单个候选执行信息注入测试。"""
    print(f"    🧪 测试 {candidate.id}: {candidate.question_text[:40]}...", flush=True)
    effective_level_limit = _resolve_level_limit(level_limit)
    effective_threshold = _resolve_threshold(threshold)

    details_by_level = {
        item["level"]: item
        for item in candidate.filter_1_details
        if isinstance(item, dict) and item.get("level")
    }
    level_specs = INFO_LEVELS[:effective_level_limit]

    if candidate.passed_filter_1 is False and candidate.filter_1_details:
        print("      ↺ 已有筛子1淘汰结果，跳过重复调用", flush=True)
        return candidate
    if candidate.passed_filter_1 is True and all(level in details_by_level for level, *_ in level_specs):
        print("      ↺ 已有筛子1结果，跳过重复调用", flush=True)
        return candidate

    for level, label, instruction, max_tokens in level_specs:
        if level in details_by_level and details_by_level[level].get("delta") is not None:
            detail = details_by_level[level]
        else:
            try:
                detail = _evaluate_level(
                    candidate.question_text,
                    candidate.balance_rationale,
                    level,
                    label,
                    instruction,
                    max_tokens,
                    threshold=effective_threshold,
                )
                details_by_level[level] = detail
                candidate.filter_1_details = sorted(details_by_level.values(), key=lambda item: item["level"])
                candidate.filter_1_summary = _detail_summary(candidate.filter_1_details)
            except Exception as exc:
                print(f"      ⚠ {label} 失败: {str(exc)[:80]}", flush=True)
                candidate.passed_filter_1 = None
                candidate.filter_1_details = sorted(details_by_level.values(), key=lambda item: item["level"])
                candidate.filter_1_summary = _detail_summary(candidate.filter_1_details)
                return candidate

        if detail["delta"] > effective_threshold:
            candidate.passed_filter_1 = False
            candidate.filter_1_details = sorted(details_by_level.values(), key=lambda item: item["level"])
            candidate.filter_1_summary = _detail_summary(candidate.filter_1_details)
            print(
                f"      ✗ 淘汰 | {label} 差值 {detail['delta']} > {effective_threshold:.0f}",
                flush=True,
            )
            return candidate

    candidate.passed_filter_1 = True
    candidate.filter_1_details = sorted(details_by_level.values(), key=lambda item: item["level"])
    candidate.filter_1_summary = _detail_summary(candidate.filter_1_details)
    print(
        f"      ✓ 通过 | {candidate.filter_1_summary or '4/4量级稳定'}",
        flush=True,
    )
    return candidate


def run_filter1(
    candidates: list[CandidateQuestion],
    checkpoint_hook=None,
) -> list[CandidateQuestion]:
    """对所有候选运行信息注入测试。"""
    print(f"\n  🧪 筛子1：信息注入测试（{len(candidates)}个候选 × {FILTER1_LEVEL_LIMIT}个量级）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    survivors = []
    for candidate in candidates:
        evaluate_candidate(candidate)
        if checkpoint_hook is not None:
            checkpoint_hook()
        if candidate.passed_filter_1 is True:
            survivors.append(candidate)

    print(f"\n  🧪 筛子1结果：{len(survivors)}/{len(candidates)} 个候选通过", flush=True)
    return survivors
