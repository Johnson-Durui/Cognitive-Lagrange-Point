"""认知拉格朗日点 · 阶段二：重新表述稳定性测试（筛子3）"""

from __future__ import annotations

import os

from .api import call_agent_json
from .models import CandidateQuestion
from .phase2_filter import FILTER2_BALANCE_THRESHOLD, evaluate_question_balance

FILTER3_REQUIRED_STABLE = max(1, int(os.environ.get("CLP_FILTER3_REQUIRED_STABLE", "8")))
FILTER3_VARIANT_LIMIT = max(1, min(10, int(os.environ.get("CLP_FILTER3_VARIANT_LIMIT", "10"))))
FILTER3_DISSOLVE_CONFIDENCE = max(1, min(100, int(os.environ.get("CLP_FILTER3_DISSOLVE_CONFIDENCE", "70"))))

VARIANT_TYPES = [
    ("V1", "抽象哲学版", "把问题重写成更抽象、更去情境的哲学表达。"),
    ("V2", "具体故事版", "用一个虚构人物或小故事呈现这个问题。"),
    ("V3", "第一人称版", "改写成“如果你自己面临这个选择”的表述。"),
    ("V4", "第三人称版", "改写成“如果一个陌生人面临这个选择”的表述。"),
    ("V5", "极端放大版", "把问题规模扩大到全社会、全人类或全物种。"),
    ("V6", "极端缩小版", "把问题规模缩小到最小可成立的两三方场景。"),
    ("V7", "历史版", "把问题放到古代或历史环境中。"),
    ("V8", "未来版", "把问题放到未来、科幻或高技术情境中。"),
    ("V9", "反转版", "把正反方的位置互换，用对立方向重新描述问题。"),
    ("V10", "消解版", "尝试论证这个问题是伪问题、被错误预设构造出来，或本不值得讨论。"),
]

VARIANT_GENERATOR_SYSTEM = """你是一个“问题变形Agent”，负责把同一个候选问题重新表述成多种版本。

请严格按给定变形类型输出 JSON 数组，每个元素必须包含：
{
  "variant_id": "V1",
  "label": "抽象哲学版",
  "question_text": "改写后的问题文本"
}

要求：
- 每种变形都要保留原问题的核心张力
- 不要只是换几个同义词
- 消解版必须明确尝试把问题论证为伪问题或错误问题
- 只输出 JSON 数组"""

DISSOLUTION_SYSTEM = """你是“问题消解评估Agent”，负责判断一个候选问题在“消解版”重写下是否真的被证明为伪问题。

请输出 JSON：
{
  "dissolves_problem": true,
  "confidence": 82,
  "reason": "为什么这个消解版足以让原问题失去讨论价值，或为什么还不够"
}

规则：
- confidence 为 0-100 的整数
- 只有当消解论证真正击穿了问题的前提时，dissolves_problem 才能为 true
- 只输出 JSON"""


def _normalize_variant(raw: dict) -> dict:
    return {
        "variant_id": raw["variant_id"],
        "label": raw["label"],
        "question_text": raw["question_text"].strip(),
    }


def _sorted_variant_details(details: dict[str, dict]) -> list[dict]:
    def key_func(item: dict) -> int:
        return int(item["variant_id"][1:])

    return sorted(details.values(), key=key_func)


def _generate_variants(candidate: CandidateQuestion) -> list[dict]:
    variant_specs = "\n".join(
        f"- {variant_id} / {label}：{instruction}"
        for variant_id, label, instruction in VARIANT_TYPES[:FILTER3_VARIANT_LIMIT]
    )
    user_message = (
        f"原问题：{candidate.question_text}\n\n"
        f"原始平衡理由：{candidate.balance_rationale}\n\n"
        f"请生成以下变形版本：\n{variant_specs}"
    )
    data = call_agent_json(
        VARIANT_GENERATOR_SYSTEM,
        user_message,
        max_tokens=3500,
        temperature=0.4,
    )
    variants = [_normalize_variant(item) for item in data]
    return variants[:FILTER3_VARIANT_LIMIT]


def _evaluate_dissolution(original_question: str, dissolve_variant: str) -> dict:
    user_message = (
        f"原问题：{original_question}\n\n"
        f"消解版：{dissolve_variant}\n\n"
        "请判断这个消解版是否真的成功证明原问题是伪问题。"
    )
    result = call_agent_json(DISSOLUTION_SYSTEM, user_message, max_tokens=700, temperature=0.2)
    return {
        "dissolves_problem": bool(result.get("dissolves_problem", False)),
        "confidence": int(result.get("confidence", 0)),
        "reason": result.get("reason", "").strip(),
    }


def _variant_summary(details: list[dict]) -> str:
    stable = sum(1 for item in details if item.get("balance_passed") is True)
    total = len(details)
    return f"{stable}/{total} 保持平衡"


def evaluate_candidate(candidate: CandidateQuestion) -> CandidateQuestion:
    """对单个候选执行重新表述稳定性测试。"""
    print(f"    🔁 测试 {candidate.id}: {candidate.question_text[:40]}...", flush=True)

    details_by_variant = {
        item["variant_id"]: item
        for item in candidate.filter_3_details
        if isinstance(item, dict) and item.get("variant_id")
    }
    existing_complete = [
        item for item in details_by_variant.values()
        if "balance_passed" in item
    ]
    if candidate.passed_filter_3 is not None:
        if candidate.filter_3_classification == "已淘汰-伪问题" or len(existing_complete) >= FILTER3_VARIANT_LIMIT:
            print("      ↺ 已有筛子3结果，跳过重复调用", flush=True)
            return candidate

    if len(details_by_variant) >= FILTER3_VARIANT_LIMIT and all(item.get("question_text") for item in details_by_variant.values()):
        variants = _sorted_variant_details(details_by_variant)
    else:
        try:
            variants = _generate_variants(candidate)
        except Exception as exc:
            print(f"      ⚠ 生成变形版本失败: {str(exc)[:80]}", flush=True)
            candidate.passed_filter_3 = None
            return candidate

        for variant in variants:
            merged = dict(details_by_variant.get(variant["variant_id"], {}))
            merged.update(variant)
            details_by_variant[variant["variant_id"]] = merged
        candidate.filter_3_details = _sorted_variant_details(details_by_variant)

    for variant in _sorted_variant_details(details_by_variant)[:FILTER3_VARIANT_LIMIT]:
        if variant["variant_id"] == "V10" and "dissolution" not in variant:
            try:
                variant["dissolution"] = _evaluate_dissolution(candidate.question_text, variant["question_text"])
                candidate.filter_3_details = _sorted_variant_details(details_by_variant)
            except Exception as exc:
                print(f"      ⚠ 消解版评估失败: {str(exc)[:80]}", flush=True)
                candidate.passed_filter_3 = None
                return candidate

            dissolve = variant["dissolution"]
            if dissolve["dissolves_problem"] and dissolve["confidence"] >= FILTER3_DISSOLVE_CONFIDENCE:
                candidate.passed_filter_3 = False
                candidate.filter_3_stable_count = sum(
                    1 for item in details_by_variant.values()
                    if item.get("balance_passed") is True
                )
                candidate.filter_3_summary = "消解版成功取消了原问题"
                candidate.filter_3_classification = "已淘汰-伪问题"
                candidate.filter_3_details = _sorted_variant_details(details_by_variant)
                print(
                    f"      ✗ 淘汰 | 消解版成立（置信度 {dissolve['confidence']}%）",
                    flush=True,
                )
                return candidate

        if "balance_passed" in variant:
            continue

        try:
            outcome = evaluate_question_balance(
                variant["question_text"],
                cached_results=variant.get("balance_details", []),
            )
        except Exception as exc:
            print(f"      ⚠ {variant['label']} 失败: {str(exc)[:80]}", flush=True)
            candidate.passed_filter_3 = None
            candidate.filter_3_details = _sorted_variant_details(details_by_variant)
            return candidate

        variant["balance_score"] = outcome["balance_score"]
        variant["distribution"] = outcome["distribution"]
        variant["valid_count"] = outcome["valid_count"]
        variant["balance_details"] = outcome["details"]
        variant["balance_passed"] = outcome["passed"]
        candidate.filter_3_details = _sorted_variant_details(details_by_variant)
        if outcome["passed"] is None:
            candidate.passed_filter_3 = None
            return candidate

    ordered_details = _sorted_variant_details(details_by_variant)[:FILTER3_VARIANT_LIMIT]
    stable_count = sum(1 for item in ordered_details if item.get("balance_passed") is True)
    incomplete = any(item.get("balance_passed") is None for item in ordered_details)

    candidate.filter_3_stable_count = stable_count
    candidate.filter_3_details = ordered_details
    candidate.filter_3_summary = _variant_summary(ordered_details)

    if incomplete or len(ordered_details) < FILTER3_VARIANT_LIMIT:
        candidate.passed_filter_3 = None
        return candidate

    candidate.passed_filter_3 = stable_count >= FILTER3_REQUIRED_STABLE
    if stable_count == FILTER3_VARIANT_LIMIT:
        candidate.filter_3_classification = "无条件拉格朗日点"
    elif candidate.passed_filter_3:
        candidate.filter_3_classification = "条件性拉格朗日点"
    else:
        candidate.filter_3_classification = "已淘汰-变形失稳"

    status = "✓ 通过" if candidate.passed_filter_3 else "✗ 淘汰"
    print(
        f"      {status} | {candidate.filter_3_summary} | 阈值<{FILTER2_BALANCE_THRESHOLD:.0f}%",
        flush=True,
    )
    return candidate


def run_filter3(
    candidates: list[CandidateQuestion],
    checkpoint_hook=None,
) -> list[CandidateQuestion]:
    """对所有筛子2存活候选运行重新表述稳定性测试。"""
    print(f"\n  🔁 筛子3：重新表述稳定性测试（{len(candidates)}个候选 × {FILTER3_VARIANT_LIMIT}种变形）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    survivors = []
    for candidate in candidates:
        evaluate_candidate(candidate)
        if checkpoint_hook is not None:
            checkpoint_hook()
        if candidate.passed_filter_3 is True:
            survivors.append(candidate)

    print(f"\n  🔁 筛子3结果：{len(survivors)}/{len(candidates)} 个候选通过", flush=True)
    return survivors
