"""Thinking tier configuration for the rebuilt decision product."""

from __future__ import annotations

import os
from copy import deepcopy

DEFAULT_TIER = "deep"

TIER_ALIASES = {
    "flash": "quick",
    "quick": "quick",
    "deepthink": "deep",
    "deep": "deep",
    "pro": "pro",
    "panorama": "ultra",
    "ultra": "ultra",
}

THINKING_TIERS = {
    "quick": {
        "key": "quick",
        "label": "⚡ 快速",
        "tagline": "5秒 · 一个直觉",
        "estimated_tokens": 4000,
        "act1_estimated_tokens": 4000,
        "estimated_seconds": 5,
        "budget_focus": "只做一次极速结构判断，优先给你一个可行动的直觉方向。",
        "star_visual": "dim",
        "enable_classification": True,
        "detection_mode": None,
        "enable_philosophers": False,
        "enable_info_probe": False,
        "enable_filter3": False,
        "enable_diagnosis": False,
        "diagnosis_count": 0,
        "enable_info_detective": False,
        "enable_cognitive_unlock": False,
        "enable_experience_sim": False,
        "experience_count": 0,
        "enable_emotion_mirror": False,
        "enable_reevaluation": False,
        "enable_recheck": False,
        "enable_simulation": False,
        "simulation_depth": 0,
        "enable_stability_check": False,
        "enable_oscillation": False,
        "enable_c2_final_review": False,
        "enable_dual_temperature": False,
    },
    "deep": {
        "key": "deep",
        "label": "💡 沉思",
        "tagline": "30秒 · 完整分析",
        "estimated_tokens": 42000,
        "act1_estimated_tokens": 18000,
        "estimated_seconds": 30,
        "budget_focus": "预算重点放在第一幕检测、信息补齐和重新评估；默认在第二幕结束，但你也可以按需手动打开未来模拟。",
        "star_visual": "standard",
        "enable_classification": True,
        "detection_mode": "decision_deep",
        "enable_philosophers": True,
        "philosopher_count": 4,
        "enable_info_probe": True,
        "info_probe_levels": 2,
        "enable_filter3": False,
        "enable_diagnosis": True,
        "diagnosis_count": 4,
        "b1_max_tokens": 2048,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": False,
        "experience_count": 0,
        "enable_emotion_mirror": False,
        "enable_reevaluation": True,
        "enable_recheck": False,
        "enable_simulation": False,
        "allow_manual_simulation": True,
        "simulation_depth": 2,
        "b2_max_tokens": 3072,
        "b3_max_tokens": 3072,
        "b4_max_tokens": 4096,
        "b5_max_tokens": 2048,
        "c1_max_tokens": 2048,
        "b6_max_tokens": 1024,
        "choice_extract_max_tokens": 900,
        "b7_max_tokens": 2600,
        "b8_max_tokens": 1800,
        "b9_max_tokens": 1600,
        "enable_stability_check": False,
        "enable_oscillation": False,
        "enable_c2_final_review": False,
        "enable_dual_temperature": False,
    },
    "pro": {
        "key": "pro",
        "label": "🔥 Pro",
        "tagline": "5分钟 · 出版级推演",
        "estimated_tokens": 320000,
        "act1_estimated_tokens": 90000,
        "estimated_seconds": 300,
        "budget_focus": "Pro 现在承接旧 Ultra：预算重点砸在第一幕真实检测、经验模拟、未来时间线和最终对比页，优先追求出版级内容密度。",
        "star_visual": "supernova",
        "enable_classification": True,
        "detection_mode": "decision_ultra",
        "enable_philosophers": True,
        "philosopher_count": 7,
        "enable_info_probe": True,
        "info_probe_levels": 4,
        "enable_filter3": True,
        "enable_diagnosis": True,
        "diagnosis_count": 5,
        "b1_max_tokens": 4096,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": True,
        "experience_count": 5,
        "enable_emotion_mirror": True,
        "enable_reevaluation": True,
        "enable_recheck": True,
        "enable_simulation": True,
        "allow_manual_simulation": True,
        "simulation_depth": 6,
        "b2_max_tokens": 8192,
        "b3_max_tokens": 8192,
        "b4_max_tokens": 12288,
        "b5_max_tokens": 6144,
        "c1_max_tokens": 6144,
        "b6_max_tokens": 3072,
        "choice_extract_max_tokens": 1600,
        "b7_max_tokens": 8192,
        "b8_max_tokens": 6144,
        "b9_max_tokens": 5120,
        "enable_stability_check": True,
        "stability_repeats": 3,
        "enable_oscillation": True,
        "oscillation_rounds": 10,
        "enable_c2_final_review": True,
        "enable_dual_temperature": True,
        "force_full_enrichment": True,
        "enable_ultra_monte_carlo": False,
    },
    "ultra": {
        "key": "ultra",
        "label": "🌌 Ultra",
        "tagline": "高烧 · Monte Carlo 多代理碰撞",
        "estimated_tokens": 10520000,
        "act1_estimated_tokens": 160000,
        "estimated_seconds": 1200,
        "budget_focus": "Ultra 的常规链路已经比 Pro 更厚；最后会默认追加真实 LLM 多委员会碰撞与最终合议综合。如果不想烧 token，请选择 Pro。",
        "star_visual": "supernova",
        "enable_classification": True,
        "detection_mode": "decision_ultra",
        "enable_philosophers": True,
        "philosopher_count": 9,
        "enable_info_probe": True,
        "info_probe_levels": 5,
        "enable_filter3": True,
        "enable_diagnosis": True,
        "diagnosis_count": 5,
        "b1_max_tokens": 6144,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": True,
        "experience_count": 7,
        "enable_emotion_mirror": True,
        "enable_reevaluation": True,
        "enable_recheck": True,
        "enable_simulation": True,
        "allow_manual_simulation": True,
        "simulation_depth": 8,
        "b2_max_tokens": 12288,
        "b3_max_tokens": 12288,
        "b4_max_tokens": 16384,
        "b5_max_tokens": 8192,
        "c1_max_tokens": 8192,
        "b6_max_tokens": 4096,
        "choice_extract_max_tokens": 2400,
        "b7_max_tokens": 12288,
        "b8_max_tokens": 8192,
        "b9_max_tokens": 8192,
        "enable_stability_check": True,
        "stability_repeats": 5,
        "enable_oscillation": True,
        "oscillation_rounds": 16,
        "enable_c2_final_review": True,
        "enable_dual_temperature": True,
        "force_full_enrichment": True,
        "enable_ultra_monte_carlo": True,
        "ultra_mc_estimated_tokens": 10000000,
        "ultra_mc_branches": 800,
        "ultra_mc_min_branches": 500,
        "ultra_mc_max_branches": 2000,
        "ultra_mc_personas": 40,
        "ultra_mc_agents_per_branch": 15,
        "ultra_mc_rounds": 4,
        "ultra_mc_branch_sample_limit": 80,
        "ultra_mc_llm_panels": 8,
        "ultra_mc_llm_max_tokens": 8192,
    },
}


TOKEN_BUDGET_SPEC = [
    ("act1_estimated_tokens", "第一幕 · 真实检测", "整轮第一幕的预估预算上限，用于张力拆解与三层筛选。"),
    ("b1_max_tokens", "B1 · 卡点追问", "用于生成更贴题、更像真人咨询的高质量追问。"),
    ("b2_max_tokens", "B2 · 信息侦探", "补齐净收益、风险边界和现实约束。"),
    ("b3_max_tokens", "B3 · 认知解锁", "补判断框架，避免只在原有视角里打转。"),
    ("b4_max_tokens", "B4 · 经验模拟", "生成过来人案例，对照现实后果。"),
    ("b5_max_tokens", "B5 · 情绪镜像", "拆出真正拉扯判断的情绪因素。"),
    ("c1_max_tokens", "C1 · 重新评估", "把信息、框架、经验和情绪重新压成建议。"),
    ("b6_max_tokens", "B6 · 模拟参数", "问出安全垫、可逆性和最坏情况。"),
    ("choice_extract_max_tokens", "选项提炼", "把原问题压成真正可比较的 A/B 选项。"),
    ("b7_max_tokens", "B7 · 时间线生成", "单条时间线预算；实际通常会跑 A/B 两条，必要时会额外重生成。"),
    ("b8_max_tokens", "B8 · 岔路口预案", "生成红黄绿信号灯、止损和生存方案。"),
    ("b9_max_tokens", "B9 · 最终对比", "压缩成可执行的比较总览与行动地图。"),
    ("ultra_mc_estimated_tokens", "Ultra · Monte Carlo 多代理碰撞", "Ultra 额外预算池；默认会启用真实 LLM 多委员会碰撞。如果不想烧 token，请选 Pro 或显式关闭 CLP_ULTRA_MC_LLM_PANELS。"),
]


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, "").strip() or default)
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _build_budget_breakdown(config: dict) -> list[dict]:
    steps = []
    for key, label, description in TOKEN_BUDGET_SPEC:
        tokens = int(config.get(key) or 0)
        if tokens <= 0:
            continue
        note = description
        if key == "b7_max_tokens":
            if normalize_tier(config.get("key")) == "ultra":
                note = "单条时间线上限；Ultra 通常会跑两条主线，A/B 太像时还会自动补一次重生成。"
            else:
                note = "单条时间线上限；通常会跑 A/B 两条主线。"
        steps.append({
            "key": key,
            "label": label,
            "tokens": tokens,
            "note": note,
        })
    return steps


def _decorate_tier_config(config: dict) -> dict:
    decorated = deepcopy(config)
    if decorated.get("key") == "ultra" and decorated.get("enable_ultra_monte_carlo"):
        min_branches = int(decorated.get("ultra_mc_min_branches") or 500)
        max_branches = int(decorated.get("ultra_mc_max_branches") or 2000)
        default_mc_budget = int(decorated.get("ultra_mc_estimated_tokens") or 10_000_000)
        conventional_budget = max(0, int(decorated.get("estimated_tokens") or 0) - default_mc_budget)
        decorated["ultra_mc_estimated_tokens"] = _env_int(
            "CLP_ULTRA_MC_ESTIMATED_TOKENS",
            default_mc_budget,
            minimum=0,
            maximum=1_000_000_000,
        )
        decorated["estimated_tokens"] = conventional_budget + int(decorated.get("ultra_mc_estimated_tokens") or 0)
        decorated["ultra_mc_branches"] = _env_int("CLP_ULTRA_MC_BRANCHES", int(decorated.get("ultra_mc_branches") or 800), minimum=min_branches, maximum=max_branches)
        decorated["ultra_mc_personas"] = _env_int("CLP_ULTRA_MC_PERSONAS", int(decorated.get("ultra_mc_personas") or 40), minimum=8, maximum=80)
        decorated["ultra_mc_agents_per_branch"] = _env_int("CLP_ULTRA_MC_AGENTS_PER_BRANCH", int(decorated.get("ultra_mc_agents_per_branch") or 15), minimum=4, maximum=50)
        decorated["ultra_mc_rounds"] = _env_int("CLP_ULTRA_MC_ROUNDS", int(decorated.get("ultra_mc_rounds") or 4), minimum=1, maximum=8)
        decorated["ultra_mc_branch_sample_limit"] = _env_int("CLP_ULTRA_MC_BRANCH_SAMPLE_LIMIT", int(decorated.get("ultra_mc_branch_sample_limit") or 80), minimum=12, maximum=240)
        decorated["ultra_mc_llm_panels"] = _env_int("CLP_ULTRA_MC_LLM_PANELS", int(decorated.get("ultra_mc_llm_panels") or 8), minimum=0, maximum=32)
        decorated["ultra_mc_llm_max_tokens"] = _env_int("CLP_ULTRA_MC_LLM_MAX_TOKENS", int(decorated.get("ultra_mc_llm_max_tokens") or 8192), minimum=512, maximum=24000)
    decorated["budget_breakdown"] = _build_budget_breakdown(decorated)
    return decorated


def normalize_tier(tier: str | None) -> str:
    value = str(tier or "").strip().lower()
    aliased = TIER_ALIASES.get(value, value)
    if aliased in THINKING_TIERS:
        return aliased
    return DEFAULT_TIER


def get_tier_config(tier: str | None) -> dict:
    resolved = normalize_tier(tier)
    return _decorate_tier_config(THINKING_TIERS[resolved])
