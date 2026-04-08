"""Minimal act-1 classifier and quick-tier output builder."""

from __future__ import annotations

from research.single_detect import analyze_question_structure


def _sorted_scores(classifications: dict) -> list[tuple[str, int]]:
    pairs = []
    for key in ("dilemma", "info_gap", "clp"):
        try:
            value = int(round(float(classifications.get(key, 0))))
        except (TypeError, ValueError):
            value = 0
        pairs.append((key, max(0, min(100, value))))
    return sorted(pairs, key=lambda item: item[1], reverse=True)


def _build_quick_result(question: str, analysis: dict) -> dict:
    classifications = analysis.get("classifications", {}) if isinstance(analysis, dict) else {}
    analysis_summary = str(analysis.get("analysis_summary", "") or "").strip()
    balance_rationale = str(analysis.get("balance_rationale", "") or "").strip()
    ranking = _sorted_scores(classifications)
    primary, primary_score = ranking[0]
    secondary_score = ranking[1][1] if len(ranking) > 1 else 0
    confidence = max(52, min(91, 55 + primary_score - secondary_score))

    if primary == "info_gap":
        recommendation_title = "先补关键事实，再做选择"
        recommendation = (
            "你眼下更像是被信息缺口卡住了，不是没有判断力。"
            "先查清最影响结果的 1 到 3 个事实，再决定。"
        )
        next_step = "把“如果现在知道答案就能立刻决定”的三个问题写下来，优先补最硬的那个。"
        why = "当前更重的不是价值冲突，而是对现实成本、收益或边界条件的不确定。"
    elif primary == "clp":
        recommendation_title = "这题更像没有唯一标准答案"
        recommendation = (
            "别继续把它当成一道一定能算出唯一正确解的题。"
            "更适合比较你愿意承担哪一种代价，然后选那个更能长期执行的方向。"
        )
        next_step = "各写下“选 A 最坏要承受什么”和“选 B 最坏要承受什么”，看你更能承担哪边。"
        why = "分析里最强的是结构性平衡，不是单纯缺资料。"
    else:
        recommendation_title = "这更像代价很重，但可以选的问题"
        recommendation = (
            "它不是无解，只是每个方向都要付代价。"
            "优先选择更可逆、能先小步试错的那边，而不是继续原地消耗。"
        )
        next_step = "为更想走的方向设计一个 7 天内可执行、可撤回的小实验。"
        why = "目前最强信号是“两难但有方向”，说明卡点主要在承受代价，而不是完全无解。"

    recommendation_parts = []
    if analysis_summary:
        recommendation_parts.append(f"快速判断里最突出的信号是：{analysis_summary}")
    if balance_rationale:
        recommendation_parts.append(f"你现在会卡住，核心更像是：{balance_rationale}")
    recommendation_parts.append(recommendation)

    why_parts = [why]
    if balance_rationale:
        why_parts.append(f"这次快速分析特别指向了：{balance_rationale}")

    return {
        "question": question,
        "decision_type": primary,
        "confidence": confidence,
        "recommendation_title": recommendation_title,
        "recommendation": " ".join(part for part in recommendation_parts if part),
        "next_step": next_step,
        "why": " ".join(part for part in why_parts if part),
        "analysis_summary": analysis_summary,
        "balance_rationale": balance_rationale,
        "classifications": classifications,
    }


def run_quick_classifier(question: str) -> dict:
    analysis = analyze_question_structure(question, allow_fallback=True)
    result = _build_quick_result(question, analysis)
    return {
        "analysis": analysis,
        "result": result,
    }


def run_flash_classifier(question: str) -> dict:
    """Backward-compatible alias for legacy code and tests."""
    return run_quick_classifier(question)
