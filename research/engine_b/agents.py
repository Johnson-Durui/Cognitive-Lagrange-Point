"""Engine B - Agent 实现 (B1-B9/C1)"""

import hashlib
import json
import math
import random
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine_b.models import BlockageType, DiagnosisQuestion
from api import call_agent_json
from db import db_get_all_confirmed_clps


BLOCKAGE_SIGNAL_KEYWORDS = {
    BlockageType.A_INFO_VOID.value: [
        "不知道", "不了解", "没查过", "不清楚", "没了解过", "没看过", "信息",
        "数据", "成本", "薪资", "概率", "风险", "政策", "行情", "事实",
    ],
    BlockageType.B_COGNITIVE_NARROW.value: [
        "看不懂", "不理解", "不知道怎么选", "搞不清楚", "怎么判断", "怎么权衡",
        "标准", "框架", "角度", "优先级", "长期", "短期", "机会成本",
    ],
    BlockageType.C_EXPERIENCE_BLANK.value: [
        "没经历过", "经历过", "第一次", "没经验", "没见过", "没听过", "没人做过",
        "身边没人", "不知道别人怎么", "过来人", "案例",
    ],
    BlockageType.D_EMOTIONAL_INTERFERENCE.value: [
        "舍不得", "害怕", "担心", "不敢", "纠结", "难过", "焦虑",
        "后悔", "亏", "丢脸", "压力", "内耗", "自责",
    ],
}

SIM_PARAM_FIELD_HINTS = {
    "savings_months": ["安全垫", "存款", "现金流", "几个月", "能撑多久", "撑多久"],
    "other_income": ["其他收入", "副业", "兼职", "第二收入", "收入来源"],
    "fixed_expenses": ["固定支出", "硬性支出", "房租", "房贷", "贷款", "家庭开销"],
    "time_to_reverse": ["多久能回头", "多久可以回头", "多久可逆", "回头需要多久"],
    "reversal_cost": ["回头的代价", "回头成本", "代价", "成本"],
    "point_of_no_return": ["不可逆", "回不了头", "无法回头", "节点"],
    "worst_fear": ["最坏情况", "最怕", "最担心", "最糟", "害怕什么"],
}

CHINESE_NUMBER_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}

CRITICAL_SIM_PARAM_FIELDS = (
    "savings_months",
    "fixed_expenses",
    "time_to_reverse",
    "reversal_cost",
    "worst_fear",
)

SIM_PARAM_LABELS = {
    "savings_months": "安全垫",
    "other_income": "其他收入",
    "fixed_expenses": "固定支出",
    "time_to_reverse": "回头时间",
    "reversal_cost": "回头代价",
    "point_of_no_return": "不可逆节点",
    "worst_fear": "最怕的情况",
}

SIMULATOR_SIMILARITY_THRESHOLD = 0.78
SIMULATOR_RETRY_SIMILARITY_THRESHOLD = 0.72

SIM_PLACEHOLDER_VALUES = {
    "",
    "未说明",
    "未提供",
    "未明确说明",
    "未知",
    "未识别",
    "未识别明确不可逆节点",
}

DECISION_PSYCHOLOGY_BIASES = {
    "framing_effect": "框架效应 - 同一信息换个说法，风险偏好就会反转。",
    "loss_aversion": "损失厌恶 - 人对损失的痛感通常强于同等收益的快感。",
    "sunk_cost": "沉没成本谬误 - 已经投入过，不代表现在还该继续投入。",
    "regret_theory": "后悔理论 - 人常常不是在选最优，而是在选未来最不容易后悔的版本。",
    "winner_curse": "赢者诅咒 - 越乐观、越漂亮的选项，越可能把真实代价藏在后面。",
    "paradox_of_choice": "选择悖论 - 选项越多，越容易在想象里过拟合，反而更难行动。",
    "status_quo_bias": "现状偏差 - 仅仅因为熟悉，就高估不动的安全性。",
    "confirmation_bias": "确认偏差 - 只挑支持自己预设立场的证据，忽略相反信号。",
}

BIAS_LABELS = {
    "framing_effect": "框架效应",
    "loss_aversion": "损失厌恶",
    "sunk_cost": "沉没成本",
    "regret_theory": "后悔预期",
    "winner_curse": "赢家诅咒",
    "paradox_of_choice": "选择悖论",
    "status_quo_bias": "现状偏差",
    "confirmation_bias": "确认偏差",
}

VALUE_DIMENSIONS = {
    "stability": "稳定与现金流",
    "growth": "成长与长期筹码",
    "freedom": "自由与掌控感",
    "belonging": "关系与归属",
    "meaning": "成就与意义感",
}


def _question_domain(question: str) -> str:
    text = str(question or "").strip().lower()
    if any(keyword in text for keyword in ["会员", "订阅", "plus", "pro", "付费", "升级"]):
        return "subscription"
    if any(keyword in text for keyword in ["工作", "offer", "跳槽", "外地", "搬家", "辞职", "入职"]):
        return "career"
    if any(keyword in text for keyword in ["创业", "副业", "项目", "开店", "公司"]):
        return "business"
    if any(keyword in text for keyword in ["分手", "结婚", "恋爱", "感情", "对象", "婚"]):
        return "relationship"
    return "generic"


def _question_domain_label(question: str) -> str:
    return {
        "subscription": "订阅/工具付费",
        "career": "职业/工作变化",
        "business": "创业/项目推进",
        "relationship": "关系/情感选择",
        "generic": "通用决策",
    }[_question_domain(question)]


def _adaptive_timeout(max_tokens: int, *, floor: int = 18, ceiling: int = 60, ratio: int = 220) -> int:
    tokens = max(0, int(max_tokens or 0))
    return max(floor, min(ceiling, floor + int(round(tokens / max(ratio, 1)))))


def _build_b1_prompt_context(question: str) -> str:
    domain = _question_domain(question)
    focus_map = {
        "subscription": [
            "真实使用频率和场景，而不是泛泛问“值不值”",
            "替代方案能否覆盖 70% 需求",
            "用户是在缺事实，还是在为“怕错过”焦虑",
        ],
        "career": [
            "净收益差：薪资、房租、通勤、生活成本、社保",
            "成长兑现率：平台、项目、技能、晋升是否真实可验证",
            "回撤成本：如果去错了，多久能回、代价有多大",
        ],
        "business": [
            "现金跑道和固定支出，而不是只谈理想结果",
            "真实需求验证和付费信号",
            "止损线和回头路径是否明确",
        ],
        "relationship": [
            "这段关系里最难承受的真实代价是什么",
            "用户缺的是事实判断、经验参照还是情绪确认",
            "有没有把身份、面子和害怕孤独混进判断里",
        ],
        "generic": [
            "净收益、最坏代价、可逆性",
            "用户最怕失去什么，而不是表面的“纠结”",
            "有没有低成本试错版本",
        ],
    }
    focus_lines = "\n".join(f"- {item}" for item in focus_map[domain])
    return f"""问题领域：{_question_domain_label(question)}
高质量追问优先抓这些变量：
{focus_lines}

请避免：
- 不要问“你更想选哪个”这种低信息量问题
- 不要把四种卡点写成模板套话
- 不要出现两个几乎同义的选项"""


def _build_b6_prompt_context(question: str, recommendation: str = "") -> str:
    domain = _question_domain(question)
    focus_map = {
        "subscription": [
            "每月固定支出和预算紧张度",
            "如果开了又发现不值，取消和回头成本几乎是多少",
            "最怕的是浪费钱，还是怕效率落后",
        ],
        "career": [
            "房租、家里承担、贷款等固定支出",
            "换工作/去外地后，如果不合适多久能回撤",
            "最坏情况是净收益没变好，还是基本生活被打乱",
        ],
        "business": [
            "现金跑道到底能撑几个月",
            "失败后的回头成本是亏钱、伤履历还是两者都有",
            "最怕的最坏情况是现金流见底还是长期拖垮状态",
        ],
        "relationship": [
            "这次选择会不会牵动居住、金钱或生活结构",
            "如果选错了，回头是情绪代价更大还是现实代价更大",
            "最怕的是受伤、失去稳定，还是未来长期后悔",
        ],
        "generic": [
            "安全垫和固定支出",
            "回头窗口和回头代价",
            "最怕的最坏情况",
        ],
    }
    focus_lines = "\n".join(f"- {item}" for item in focus_map[domain])
    recommendation_line = f"\n当前建议方向：{recommendation}" if recommendation else ""
    return f"""问题领域：{_question_domain_label(question)}{recommendation_line}
请优先围绕这些真实变量发问：
{focus_lines}

要求：
- 问题必须贴着原问题场景，不要泛化
- 优先问最能改变模拟结果的变量
- 每个问题都要让用户更容易回答，而不是更抽象"""


def _build_bias_reference() -> str:
    return "\n".join(
        f"- {key}: {description}"
        for key, description in DECISION_PSYCHOLOGY_BIASES.items()
    )


def _normalize_bias_entries(data: object) -> list[dict]:
    entries = []
    if isinstance(data, list):
        source = data
    else:
        source = []
    for item in source[:4]:
        if isinstance(item, str):
            key = item.strip()
            if key in DECISION_PSYCHOLOGY_BIASES:
                entries.append({
                    "key": key,
                    "label": BIAS_LABELS.get(key, key),
                    "hint": DECISION_PSYCHOLOGY_BIASES.get(key, ""),
                })
            continue
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "") or "").strip()
        label = str(item.get("label", "") or item.get("name", "") or BIAS_LABELS.get(key, "")).strip()
        hint = _sanitize_generated_text(item.get("hint") or item.get("description"), default="")
        if key not in DECISION_PSYCHOLOGY_BIASES and not label:
            continue
        resolved_key = key if key in DECISION_PSYCHOLOGY_BIASES else next(
            (bias_key for bias_key, bias_label in BIAS_LABELS.items() if bias_label == label),
            "",
        )
        if not resolved_key:
            resolved_key = key or next(
                (bias_key for bias_key, desc in DECISION_PSYCHOLOGY_BIASES.items() if label and label in desc),
                "",
            )
        if not resolved_key:
            continue
        entries.append({
            "key": resolved_key,
            "label": label or BIAS_LABELS.get(resolved_key, resolved_key),
            "hint": hint or DECISION_PSYCHOLOGY_BIASES.get(resolved_key, ""),
        })
    deduped = []
    seen = set()
    for item in entries:
        key = item.get("key")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _merge_bias_entries(*groups: object) -> list[dict]:
    merged = []
    seen = set()
    for group in groups:
        for item in _normalize_bias_entries(group):
            key = item.get("key")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def infer_decision_biases(
    question: str,
    answers: dict[str, str] | None = None,
    blockages: list[str] | None = None,
    *,
    recommendation: str = "",
) -> list[dict]:
    text = " ".join([str(question or ""), str(recommendation or "")] + [str(value or "") for value in (answers or {}).values()])
    normalized = _normalize_text(text)
    hits = []
    if _contains_any(normalized, ["后悔", "错过", "遗憾", "要不要试", "怕以后"]):
        hits.append("regret_theory")
    if _contains_any(normalized, ["亏", "损失", "失去", "不敢", "稳", "安全", "风险"]):
        hits.append("loss_aversion")
    if _contains_any(normalized, ["已经投入", "都花了", "舍不得", "投入了", "做了这么久"]):
        hits.append("sunk_cost")
    if _contains_any(normalized, ["继续", "先这样", "不动", "留在", "维持现状"]):
        hits.append("status_quo_bias")
    if _contains_any(normalized, ["很多选项", "太多选择", "不知道选哪个", "越想越乱"]):
        hits.append("paradox_of_choice")
    if _contains_any(normalized, ["最好的", "完美", "一把", "翻盘", "理想中的"]):
        hits.append("winner_curse")
    if _contains_any(normalized, ["其实我知道", "我就是想确认", "证明自己", "只想听建议"]):
        hits.append("confirmation_bias")
    if _contains_any(normalized, ["值不值", "该不该", "要不要"]):
        hits.append("framing_effect")
    if "D" in (blockages or []) and "loss_aversion" not in hits:
        hits.append("loss_aversion")
    return _normalize_bias_entries(hits[:4])


def infer_value_profile(question: str, answers: dict[str, str] | None = None) -> dict:
    text = " ".join([str(question or "")] + [str(value or "") for value in (answers or {}).values()])
    normalized = _normalize_text(text)
    scores = {
        "stability": 0,
        "growth": 0,
        "freedom": 0,
        "belonging": 0,
        "meaning": 0,
    }
    keyword_map = {
        "stability": ["稳定", "现金流", "安全", "房租", "开销", "基本盘", "别亏"],
        "growth": ["成长", "机会", "发展", "长期", "筹码", "晋升", "上升"],
        "freedom": ["自由", "掌控", "选择权", "自己决定", "不被绑定", "灵活"],
        "belonging": ["家人", "关系", "陪伴", "归属", "社交", "照顾", "责任"],
        "meaning": ["值得", "意义", "热爱", "成就", "理想", "想做成"],
    }
    for key, keywords in keyword_map.items():
        scores[key] += sum(1 for keyword in keywords if keyword in normalized)

    domain = _question_domain(question)
    if domain == "career":
        scores["growth"] += 1
        scores["stability"] += 1
    elif domain == "business":
        scores["freedom"] += 1
        scores["meaning"] += 1
    elif domain == "relationship":
        scores["belonging"] += 2
    elif domain == "subscription":
        scores["stability"] += 1

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top = []
    weight = 5
    for key, score in ranked:
        if len(top) >= 3:
            break
        if score <= 0 and top:
            continue
        top.append({
            "key": key,
            "label": VALUE_DIMENSIONS[key],
            "weight": weight,
        })
        weight -= 1
    if not top:
        top = [
            {"key": "stability", "label": VALUE_DIMENSIONS["stability"], "weight": 5},
            {"key": "growth", "label": VALUE_DIMENSIONS["growth"], "weight": 4},
            {"key": "freedom", "label": VALUE_DIMENSIONS["freedom"], "weight": 3},
        ]
    summary = f"你现在更优先守住「{top[0]['label']}」"
    if len(top) > 1:
        summary += f"，其次在意「{top[1]['label']}」"
    if len(top) > 2:
        summary += f"，最后才是「{top[2]['label']}」"
    return {
        "top_values": top,
        "summary": summary,
    }


def _build_value_profile_text(value_profile: dict | None) -> str:
    if not isinstance(value_profile, dict):
        return "（暂无明确价值排序）"
    values = value_profile.get("top_values") if isinstance(value_profile.get("top_values"), list) else []
    if not values:
        return str(value_profile.get("summary", "") or "（暂无明确价值排序）")
    rows = [f"- {item.get('label', '')}: 权重 {item.get('weight', '')}" for item in values if isinstance(item, dict)]
    summary = str(value_profile.get("summary", "") or "").strip()
    return "\n".join(([summary] if summary else []) + rows) or "（暂无明确价值排序）"


def _build_bias_text(biases: list[dict] | None) -> str:
    normalized = _normalize_bias_entries(biases or [])
    if not normalized:
        return "（暂未识别明显决策偏差）"
    return "\n".join(
        f"- {item['label']}: {item['hint']}"
        for item in normalized
    )


def _build_bias_reminder(biases: list[dict] | None) -> str:
    normalized = _normalize_bias_entries(biases or [])
    if not normalized:
        return ""
    lead = normalized[0]
    return f"先留意「{lead['label']}」：别让它替你提前做了决定。"


def _build_external_signals_text(signals: list[dict] | None) -> str:
    rows = []
    for item in (signals or [])[:6]:
        if not isinstance(item, dict):
            continue
        stance = str(item.get("stance", "neutral") or "neutral").strip()
        time_text = _sanitize_generated_text(item.get("time") or item.get("captured_at"), default="")
        summary = _sanitize_generated_text(item.get("summary"), default="")
        if not summary:
            continue
        prefix = f"{time_text} / " if time_text else ""
        rows.append(f"- {prefix}{stance}: {summary}")
    if not rows:
        return "（暂无可参考的外部市场声音快照）"
    return "以下是本地整理的外部市场声音快照，不是请求时实时抓取。\n" + "\n".join(rows)


def _normalize_market_signals(data: object) -> list[dict]:
    normalized = []
    if not isinstance(data, list):
        return normalized
    for item in data[:6]:
        if not isinstance(item, dict):
            continue
        summary = _sanitize_generated_text(item.get("summary"), default="")
        if not summary:
            continue
        stance = _sanitize_generated_text(item.get("stance"), default="neutral").lower() or "neutral"
        if stance not in {"positive", "negative", "neutral", "mixed"}:
            stance = "neutral"
        normalized.append({
            "id": _sanitize_generated_text(item.get("id"), default=""),
            "snapshot_id": _sanitize_generated_text(item.get("snapshot_id"), default=""),
            "snapshot_title": _sanitize_generated_text(item.get("snapshot_title"), default=""),
            "source": _sanitize_generated_text(item.get("source"), default="local_snapshot"),
            "captured_at": _sanitize_generated_text(item.get("captured_at"), default=""),
            "time": _sanitize_generated_text(item.get("time"), default=""),
            "stance": stance,
            "summary": summary,
        })
    return normalized


def _normalize_alternative_path(data: object) -> dict:
    if not isinstance(data, dict):
        return {}
    title = _sanitize_generated_text(data.get("title") or data.get("name"), default="")
    summary = _sanitize_generated_text(data.get("summary") or data.get("description"), default="")
    if not title and not summary:
        return {}
    return {
        "title": title or "第三条路",
        "summary": summary,
        "why_it_works": _sanitize_generated_text(data.get("why_it_works"), default=""),
        "first_step": _sanitize_generated_text(data.get("first_step"), default=""),
        "when_not_to_use": _sanitize_generated_text(data.get("when_not_to_use"), default=""),
    }


def _choice_question(question_id: str, question_text: str, options: list[str]) -> DiagnosisQuestion:
    return DiagnosisQuestion(
        id=question_id,
        question_text=question_text,
        options=[str(option or "").strip() for option in options if str(option or "").strip()],
    )


def _fallback_b1_questions(question: str) -> list[DiagnosisQuestion]:
    domain = _question_domain(question)
    domain_hint = {
        "subscription": "这笔持续付费",
        "career": "这次职业变动",
        "business": "这次创业/项目尝试",
        "relationship": "这段关系选择",
        "generic": "这个决定",
    }[domain]
    return [
        _choice_question(
            "b1q1",
            f"面对{domain_hint}，你现在最缺的到底是哪一类东西？",
            ["缺关键事实和数据", "缺判断标准/权衡框架", "缺过来人经验参照", "其实心里有数，只是情绪过不去"],
        ),
        _choice_question(
            "b1q2",
            "如果明天必须定下来，你最怕付出的代价是什么？",
            ["花了钱/时间才发现不值", "错过机会以后长期后悔", "影响关系、身份或面子", "短期代价都能承受，只是拿不准"],
        ),
        _choice_question(
            "b1q3",
            "这件事有没有一个低成本试一下的版本？",
            ["有，可以先试用/试错", "可能有，但我还没设计出来", "几乎没有，一上来就是重成本", "我现在也不确定"],
        ),
        _choice_question(
            "b1q4",
            "如果只能先守住一个，你现在最不愿意丢掉的是什么？",
            ["稳定和现金流", "成长和长期机会", "自由和选择权", "关系与内心安定"],
        ),
        _choice_question(
            "b1q5",
            "你更怕哪种后悔？",
            ["试了以后发现代价太大", "没试，几年后一直惦记", "两种都怕，所以一直不动", "我更怕被别人证明我选错"],
        ),
    ]


def _infer_missing_info_items(question: str, answers: dict[str, str] | None = None) -> list[dict]:
    domain = _question_domain(question)
    answer_blob = " ".join(str(value or "") for value in (answers or {}).values())

    if domain == "subscription":
        return [
            {
                "title": "使用密度",
                "content": "你还没把真实高频场景写清楚，比如一周会不会稳定用在写作、检索、代码、翻译或学习上。",
                "impact": "strong",
                "why_critical": "低频使用时，会员价值会迅速塌掉。",
                "source_suggestion": "先记录 7 天真实使用次数和场景。",
            },
            {
                "title": "替代方案",
                "content": "要搞清楚免费版、其他工具或共享方案能不能覆盖你 70% 以上的需求，而不是先默认只能靠付费解决。",
                "impact": "strong",
                "why_critical": "决定你是在买效率，还是在为焦虑付费。",
                "source_suggestion": "对比免费版、同类工具和你的现有工作流。",
            },
            {
                "title": "月度回本",
                "content": "你需要算的是每月省下多少时间、提升多少产出，是否真的值回订阅费，而不是只看功能新鲜感。",
                "impact": "medium",
                "why_critical": "能把“想要”变成“值不值”。",
                "source_suggestion": "按月预算和时间收益做一页小账本。",
            },
        ]

    if domain == "career":
        return [
            {
                "title": "净收益差",
                "content": "不能只看名义薪资，要把房租、通勤、城市生活成本和社保差异一起算进去。",
                "impact": "strong",
                "why_critical": "很多看起来更好的机会，净结余并没有显著变好。",
                "source_suggestion": "列一张去和不去的月度收支对照表。",
            },
            {
                "title": "成长兑现",
                "content": "要确认这份机会带来的平台、项目、晋升和技能积累，是宣传话术还是可验证收益。",
                "impact": "strong",
                "why_critical": "决定它是短期苦换长期筹码，还是只是换个地方继续消耗。",
                "source_suggestion": "找同岗在职/离职的人核验真实发展路径。",
            },
            {
                "title": "回撤成本",
                "content": "你还没把试错失败后的退路写清楚，包括多久能回、回头损失什么、手头现金能撑多久。",
                "impact": "medium",
                "why_critical": "可逆性会直接影响你该不该现在动。",
                "source_suggestion": "写清退租、转岗、回流和现金垫的边界。",
            },
        ]

    if domain == "business":
        return [
            {
                "title": "现金跑道",
                "content": "你要明确自己在没有稳定收入的情况下，现金流到底能撑几个月，而不是凭感觉觉得还能扛。",
                "impact": "strong",
                "why_critical": "决定你是在试错，还是在裸奔。",
                "source_suggestion": "把存款、固定支出和最保守收入写成月度跑道。",
            },
            {
                "title": "验证信号",
                "content": "还没验证有没有真实付费意愿、复购可能或可持续需求，只靠热情容易把试错拉成长亏。",
                "impact": "strong",
                "why_critical": "需求验证比主观相信更重要。",
                "source_suggestion": "先拿到 3 个真实用户或付费信号。",
            },
            {
                "title": "止损线",
                "content": "你需要先定义什么情况下立刻收缩，而不是等到钱和状态都快见底才回头。",
                "impact": "medium",
                "why_critical": "一次试错不该拖垮后面几年。",
                "source_suggestion": "提前写好 1 个月、3 个月、6 个月检查点。",
            },
        ]

    base_content = "你还没把净收益、最坏代价和可逆性三件事并排写清楚。"
    if answer_blob:
        base_content = f"从你现在的回答看，{base_content}"
    return [
        {
            "title": "净收益",
            "content": "别只看最好结果，要把投入、收益和持续成本一起看，算清这件事长期到底值不值。",
            "impact": "strong",
            "why_critical": "很多纠结其实卡在账没算清。",
            "source_suggestion": "把投入、回报和机会成本列成三栏。",
        },
        {
            "title": "最坏代价",
            "content": "先定义最坏情况会损失什么，再判断这个损失你承不承受得住，而不是只看理想版本。",
            "impact": "strong",
            "why_critical": "决定你是在理性判断，还是在幻想判断。",
            "source_suggestion": "直接写下最坏情况和对应后果。",
        },
        {
            "title": "可逆程度",
            "content": base_content,
            "impact": "medium",
            "why_critical": "越可逆，越适合先行动后微调。",
            "source_suggestion": "给这件事标注可回头时间和回撤成本。",
        },
    ]


def _infer_cognitive_frames(question: str) -> list[dict]:
    domain = _question_domain(question)
    if domain == "subscription":
        return [
            {
                "title": "使用密度",
                "core_insight": "会员值不值，不看功能多不多，看你会不会稳定高频使用。",
                "why_it_matters": "它能把“想体验一下”与“真的会进入日常工作流”分开。",
                "reframe_question": "我是在买高频效率，还是在买一时安心？",
                "try_now": "先列出未来 30 天会重复用到它的 5 个场景。",
                "bias_alert": "避免因为焦虑错过而高估付费价值。",
            },
            {
                "title": "回本视角",
                "core_insight": "把订阅费换算成节省的时间、产出质量或机会成本，而不是只比较价格。",
                "why_it_matters": "这样才能判断你是在消费，还是在投资效率。",
                "reframe_question": "它每月能帮我省下多少钱或多少时间？",
                "try_now": "拿最近 3 件任务做一次有无会员的效率对比。",
                "bias_alert": "防止框架效应把“贵/便宜”误当成“值/不值”。",
            },
            {
                "title": "可逆试用",
                "core_insight": "可取消、可限期的选择，不适合被想成一次永久站队。",
                "why_it_matters": "能把高压纠结改成低成本试错。",
                "reframe_question": "我能不能用一个月试出真实价值？",
                "try_now": "设定 30 天使用目标和取消条件。",
                "bias_alert": "防止损失厌恶让你把一次月付想成永久绑定。",
            },
        ]

    return [
        {
            "title": "可逆性",
            "core_insight": "越能回头的选择，越应该优先用小步试错而不是脑内内耗。",
            "why_it_matters": "它能帮你区分这是“生死决定”还是“可验证决定”。",
            "reframe_question": "如果选错了，我多久、花多大代价能退回来？",
            "try_now": "写下最短回撤路径和可接受损失上限。",
            "bias_alert": "别让损失厌恶把可逆问题想成绝境题。",
        },
        {
            "title": "净收益",
            "core_insight": "决定不是比谁更好看，而是比谁的真实净收益更高。",
            "why_it_matters": "可以把感觉层面的纠结压回现实账本。",
            "reframe_question": "这条路扣掉成本后，还剩下什么真实收益？",
            "try_now": "把收益、成本、机会成本做成并排三栏。",
            "bias_alert": "防止只盯着单一好处，忽略隐藏成本。",
        },
        {
            "title": "一年后筹码",
            "core_insight": "别只问现在舒不舒服，要问一年后你手里的筹码会不会更多。",
            "why_it_matters": "很多短期难受的选择，长期反而更值；反过来也一样。",
            "reframe_question": "一年后，这个选择会给我留下什么新筹码？",
            "try_now": "分别写下两条路一年后最可能沉淀的东西。",
            "bias_alert": "防止现状偏差把短期安稳误当成长远最优。",
        },
    ]


def _infer_experience_cases(question: str) -> list[dict]:
    domain = _question_domain(question)
    if domain == "subscription":
        return [
            {
                "title": "高频重度用",
                "starting_point": "本来就在写作、检索和代码辅助上高频使用，付费前先做了 2 周使用记录。",
                "choice_made": "开会员，并设定每月复盘是否继续。",
                "outcome": "因为确实高频，效率提升明显，订阅费很快被时间收益覆盖。",
                "lesson": "高频刚需用户，付费更像买工具，不像冲动消费。",
                "transfer_hint": "借鉴他的记录方法，不要照抄他的使用密度。",
            },
            {
                "title": "焦虑型订阅",
                "starting_point": "担心落后别人，怕不用会员就错过机会，但平时真实使用并不高。",
                "choice_made": "先冲动开了会员。",
                "outcome": "前三天很兴奋，后面逐渐闲置，最后发现自己买的是安心感，不是效率。",
                "lesson": "低频需求时，情绪会把“可有可无”包装成“必须拥有”。",
                "transfer_hint": "借鉴他的反思，不要等到买完才看使用记录。",
            },
            {
                "title": "先试再开",
                "starting_point": "不确定值不值，但能明确说出几个高价值场景。",
                "choice_made": "先用免费版和替代工具压测，再决定是否短期订阅。",
                "outcome": "最后按需短期付费，既没错过效率，也没陷入长期浪费。",
                "lesson": "可逆选择最适合先做小试验，再做长期承诺。",
                "transfer_hint": "借鉴他的试验路径，不要把一次月付想成永久绑定。",
            },
        ]

    return [
        {
            "title": "冲得太快",
            "starting_point": "一开始主要靠情绪和想象推动自己做决定，没有把最坏情况写清楚。",
            "choice_made": "直接选了更激进的路。",
            "outcome": "前期有兴奋感，但很快被现实成本追上，不得不被动止损。",
            "lesson": "不是不能冲，而是不能在看不清代价时硬冲。",
            "transfer_hint": "借鉴他的止损意识，不要照抄他的出手速度。",
        },
        {
            "title": "稳中推进",
            "starting_point": "先把最坏情况和回撤路径做清楚，再决定要不要推进。",
            "choice_made": "保留基本盘，同时做一轮低成本试错。",
            "outcome": "虽然没立刻痛快，但后续判断越来越稳，最后更能接受自己的选择。",
            "lesson": "很多正确推进，不是猛冲，而是把风险拆小。",
            "transfer_hint": "借鉴他的节奏设计，不要误解成无限拖延。",
        },
        {
            "title": "改题而不是硬选",
            "starting_point": "原本一直在 A 和 B 中纠结，后来发现问题其实问错了。",
            "choice_made": "没有直接二选一，而是先补条件，再重新定义选项。",
            "outcome": "虽然路径更绕一点，但最终拿到的是更适合自己的方案。",
            "lesson": "有些纠结不是没答案，而是原题太粗。",
            "transfer_hint": "借鉴他拆问题的方法，不要机械复制第三条路。",
        },
    ]


def _infer_emotional_insight(question: str, answers: dict[str, str] | None, blockages: list[str] | None) -> dict:
    text = " ".join([str(question or "")] + [str(value or "") for value in (answers or {}).values()])
    if "D" not in (blockages or []) and not _contains_any(text, ["怕", "害怕", "焦虑", "后悔", "舍不得", "压力", "纠结", "不敢"]):
        return {}

    emotions = []
    if _contains_any(text, ["怕", "害怕", "担心", "不敢", "风险"]):
        emotions.append({"emotion": "害怕", "intensity": "strong", "evidence": "你对损失和失控的表述明显多于对收益的描述。"})
    if _contains_any(text, ["后悔", "错过", "遗憾"]):
        emotions.append({"emotion": "后悔预期", "intensity": "medium", "evidence": "你不只是怕选错，也在怕多年后觉得自己错过了窗口。"})
    if _contains_any(text, ["舍不得", "已经投入", "亏", "丢脸", "面子"]):
        emotions.append({"emotion": "沉没成本/面子压力", "intensity": "medium", "evidence": "你的顾虑里混进了已经投入过的时间、身份或面子。"})
    if not emotions:
        emotions.append({"emotion": "纠结", "intensity": "medium", "evidence": "目前更像长期拉扯造成的内耗，而不是信息已经足够后的轻松判断。"})

    domain = _question_domain(question)
    hidden_need = {
        "subscription": "你真正想保护的是预算不被无效消费吞掉，同时也不想因为吝啬错过效率工具。",
        "career": "你真正想保护的是生活稳定性、收入安全和对自己选择的掌控感。",
        "business": "你真正想保护的是现金流和自我价值感，怕一次试错把两边都伤到。",
        "relationship": "你真正想保护的是被理解、被接住和不把自己交给一段错误关系。",
        "generic": "这些情绪真正想保护的，是你的安全感、自尊和可承受边界。",
    }[domain]

    biases = infer_decision_biases(question, answers, blockages)
    return {
        "dominant_emotions": emotions[:3],
        "hidden_need": hidden_need,
        "decision_distortion": "它会让你放大短期损失，低估小步试错和后续修正的空间。",
        "grounding_prompt": "先别证明自己勇敢或保守，先确认哪种后果你真的扛得住。",
        "gentle_reminder": "你现在最需要的不是再想十遍，而是把害怕翻译成可验证的条件。",
        "decision_biases": biases,
        "bias_reminder": _build_bias_reminder(biases),
    }


def _fallback_sim_questions(question: str, recommendation: str = "") -> list[dict]:
    domain = _question_domain(question)
    fear_hint = {
        "subscription": "你最怕的是花了钱却没有形成稳定使用",
        "career": "你最怕的是去了以后净收益没有变好，还打乱基本生活",
        "business": "你最怕的是现金流撑不住，试错拖成长期亏损",
        "relationship": "你最怕的是投入感情后发现代价远高于预期",
        "generic": "你最怕的是行动后发现代价比想象大得多",
    }[domain]
    return [
        {
            "id": "simq1",
            "field_name": "savings_months",
            "question_text": (
                "如果你去工作/换城市后发现不适合，扣掉房租和基本生活，你手里的缓冲大概能撑多久？"
                if domain == "career"
                else "如果这次尝试不顺，你手里的缓冲大概能撑多久？"
            ),
            "options": ["1个月内", "3个月左右", "6个月左右", "12个月以上"],
        },
        {
            "id": "simq2",
            "field_name": "fixed_expenses",
            "question_text": (
                "你每个月必须扛住的固定支出，主要落在哪个范围？把房租、贷款、家庭开销都算进去。"
                if domain in {"career", "business"}
                else "你每个月最硬的固定支出，大概落在哪个范围？"
            ),
            "options": ["3000元内", "3000-8000元", "8000-15000元", "15000元以上", "几乎没有固定支出"],
        },
        {
            "id": "simq3",
            "field_name": "time_to_reverse",
            "question_text": "如果发现这条路不值，最快多久能回头？",
            "options": ["一周内就能停", "1个月内能停", "3个月内能停", "半年以上才回得来"],
        },
        {
            "id": "simq4",
            "field_name": "reversal_cost",
            "question_text": "如果要回头，最伤你的代价会落在哪一类？",
            "options": (
                ["会亏搬家/租房成本", "会让简历出现折返记录", "会错过当前机会窗口", "三种代价都会叠加"]
                if domain == "career"
                else ["几乎没成本", "会损失一笔钱", "会伤到关系/机会", "几种代价会一起出现"]
            ),
        },
        {
            "id": "simq5",
            "field_name": "worst_fear",
            "question_text": f"{fear_hint}。哪种最接近你现在的担心？",
            "options": ["花钱/投入后发现不值", "短期折腾但还能承受", "会伤到现金流或基本盘", "更怕长期后悔没试"],
        },
    ]


def _normalize_sim_questions(data: object) -> list[dict]:
    if not isinstance(data, list):
        return []
    normalized = []
    for index, item in enumerate(data[:6]):
        if not isinstance(item, dict):
            continue
        question_text = str(item.get("question_text", "") or "").strip()
        if not question_text:
            continue
        options = item.get("options", [])
        if not isinstance(options, list):
            options = []
        field_name = str(item.get("field_name", "") or "").strip() or _classify_sim_param_question(question_text) or ""
        normalized.append({
            "id": str(item.get("id", f"simq{index + 1}") or f"simq{index + 1}"),
            "question_text": _sanitize_generated_text(question_text),
            "options": [str(option or "").strip() for option in options if str(option or "").strip()],
            "field_name": field_name,
        })
    return normalized


def _normalize_missing_info_items(data: object) -> list[dict]:
    if not isinstance(data, list):
        return []
    normalized = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        content = str(item.get("content", "") or "").strip()
        if not title or not content:
            continue
        normalized.append({
            "title": title[:16],
            "content": content,
            "impact": str(item.get("impact", "medium") or "medium").strip(),
            "why_critical": str(item.get("why_critical", "") or "").strip(),
            "source_suggestion": str(item.get("source_suggestion", "") or "").strip(),
        })
    return normalized


def _normalize_cognitive_frames(data: object) -> list[dict]:
    if not isinstance(data, list):
        return []
    normalized = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        core = str(item.get("core_insight", "") or "").strip()
        if not title or not core:
            continue
        normalized.append({
            "title": title[:16],
            "core_insight": core,
            "why_it_matters": str(item.get("why_it_matters", "") or "").strip(),
            "reframe_question": str(item.get("reframe_question", "") or "").strip(),
            "try_now": str(item.get("try_now", "") or "").strip(),
            "bias_alert": _sanitize_generated_text(item.get("bias_alert"), default=""),
        })
    return normalized


def _normalize_experience_cases(data: object) -> list[dict]:
    if not isinstance(data, list):
        return []
    normalized = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        outcome = str(item.get("outcome", "") or "").strip()
        if not title or not outcome:
            continue
        normalized.append({
            "title": title[:20],
            "starting_point": str(item.get("starting_point", "") or "").strip(),
            "choice_made": str(item.get("choice_made", "") or "").strip(),
            "outcome": outcome,
            "lesson": str(item.get("lesson", "") or "").strip(),
            "transfer_hint": str(item.get("transfer_hint", "") or "").strip(),
        })
    return normalized


def _normalize_emotional_insight(data: object) -> dict:
    if not isinstance(data, dict):
        return {}
    emotions = []
    for item in data.get("dominant_emotions", []):
        if not isinstance(item, dict):
            continue
        emotion = str(item.get("emotion", "") or "").strip()
        if not emotion:
            continue
        emotions.append({
            "emotion": emotion,
            "intensity": str(item.get("intensity", "") or "").strip(),
            "evidence": str(item.get("evidence", "") or "").strip(),
        })
    insight = {
        "dominant_emotions": emotions,
        "hidden_need": str(data.get("hidden_need", "") or "").strip(),
        "decision_distortion": str(data.get("decision_distortion", "") or "").strip(),
        "grounding_prompt": str(data.get("grounding_prompt", "") or "").strip(),
        "gentle_reminder": str(data.get("gentle_reminder", "") or "").strip(),
        "decision_biases": _normalize_bias_entries(data.get("decision_biases", [])),
        "bias_reminder": _sanitize_generated_text(data.get("bias_reminder"), default=""),
    }
    has_meaning = bool(
        insight["dominant_emotions"]
        or insight["hidden_need"]
        or insight["decision_distortion"]
        or insight["grounding_prompt"]
        or insight["gentle_reminder"]
        or insight["decision_biases"]
        or insight["bias_reminder"]
    )
    return insight if has_meaning else {}


# ============================================================
# B1 System Prompt - 卡点诊断
# ============================================================
B1_SYSTEM = """你是一位"认知卡点诊断专家"。用户面临一个决策困境，但无法做出选择。

你的任务是诊断用户卡在哪个认知环节。不是要帮用户做决定，而是找出：
- 用户是否缺少关键信息？（信息黑洞）
- 用户是否缺少理解信息的认知框架？（认知窄门）
- 用户是否缺少类似经验作为参照？（经验盲区）
- 用户的情绪是否干扰了判断？（情绪干扰）

请通过3-5个精准的追问来诊断。

追问策略：
- 优先使用封闭式问题（选择题），让用户快速回答
- 只有在需要深入了解时才用开放式问题
- 每个问题应该简洁有力，直击要害
- 每个问题都必须服务于区分：信息黑洞 / 认知窄门 / 经验盲区 / 情绪干扰
- 问题必须贴合用户的真实场景，不要写成通用模板
- 优先问能显著改变结论的高杠杆变量：净收益、最坏代价、可逆性、过来人参照、真正害怕失去什么
- 不要问“你更想选哪个”“你更喜欢哪个”这种低信息量问题
- 在 3-5 个问题里，至少加入 1 个“核心价值排序”问题，帮后续阶段知道用户更优先守住什么
- 允许加入 1 个“你更怕哪种后悔”问题，用来识别后悔理论和损失厌恶

请以JSON格式输出：
{
  "diagnosis_questions": [
    {
      "id": "b1q1",
      "question_text": "追问内容",
      "options": ["选项A", "选项B", "选项C", "都不符合"],
      "type": "choice"
    },
    {
      "id": "b1q2",
      "question_text": "追问内容（开放式）",
      "options": [],
      "type": "open"
    }
  ]
}

只输出JSON，不要输出其他内容。"""


CHOICE_EXTRACTION_SYSTEM = """你是一位决策选项提炼师。

请根据用户的原始问题、当前建议和行动方案，提炼用户真正面临的两个选择。

要求：
1. 优先提炼成互相排斥、可比较的两个选项
2. 名称简短，描述具体，不要写成“推荐选项/备选选项”
3. 如果原问题本身就是“要不要做X”，请保留“做X / 暂不做X”这样的结构
4. 只输出 JSON

返回格式：
{
  "choices": [
    {"name": "选项A短名", "description": "选项A的具体做法"},
    {"name": "选项B短名", "description": "选项B的具体做法"}
  ]
}
"""


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_text(value: object) -> str:
    return str(value or "").strip().lower()


def _sanitize_generated_text(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return default

    replacements = {
        "如果未说明仍压得紧": "如果现实压力仍然偏紧",
        "未识别明确不可逆节点": "目前看还没有明显一去不回头的节点",
        "point_of_no_return": "不可逆节点",
        "reversal_cost": "回头代价",
        "fixed_expenses": "固定支出",
        "other_income": "其他收入",
        "savings_months": "安全垫",
        "time_to_reverse": "回头时间",
        "worst_fear": "最怕的情况",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = re.sub(r'按[“"]?(?:未说明|未提供|未明确说明)[”"]?准备退路', "按可回头窗口准备退路", text)
    text = re.sub(r'如果(?:未说明|未提供|未明确说明)仍压得紧', "如果现实压力仍然偏紧", text)
    text = re.sub(r'[“"]?(?:未说明|未提供|未明确说明|未知)[”"]?', "现实条件还没完全坐实", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or default


def _is_sim_placeholder(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text in SIM_PLACEHOLDER_VALUES:
        return True
    return any(token in text for token in ("未说明", "未提供", "未明确说明"))


def _sim_param_is_meaningful(field_name: str, value: object) -> bool:
    if field_name == "savings_months":
        return value is not None
    return not _is_sim_placeholder(value)


def missing_critical_sim_params(user_params: dict | None) -> list[str]:
    params = user_params if isinstance(user_params, dict) else {}
    return [
        field_name
        for field_name in CRITICAL_SIM_PARAM_FIELDS
        if not _sim_param_is_meaningful(field_name, params.get(field_name))
    ]


def _asked_sim_fields(sim_questions: list[dict] | None) -> set[str]:
    fields: set[str] = set()
    for item in sim_questions or []:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name", "") or "").strip()
        if not field_name:
            field_name = _classify_sim_param_question(str(item.get("question_text", "") or "")) or ""
        if field_name:
            fields.add(field_name)
    return fields


def _count_sim_field_attempts(sim_questions: list[dict] | None, field_name: str) -> int:
    count = 0
    for item in sim_questions or []:
        if not isinstance(item, dict):
            continue
        current = str(item.get("field_name", "") or "").strip()
        if not current:
            current = _classify_sim_param_question(str(item.get("question_text", "") or "")) or ""
        if current == field_name:
            count += 1
    return count


def _sim_param_question_template(
    field_name: str,
    *,
    attempt: int = 1,
    question_id: str | None = None,
    question_context: str = "",
) -> dict:
    qid = question_id or f"sim_{field_name}_{attempt}"
    domain = _question_domain(question_context)
    if field_name == "savings_months":
        if domain == "career":
            base_question = "如果你去工作/换城市后发现不适合，扣掉房租和基本生活，你手里的现金还能撑多久？"
        elif domain == "business":
            base_question = "如果项目 3 个月没有起色，扣掉必要开支后，你的现金跑道还能撑多久？"
        else:
            base_question = "如果这次尝试不顺，你手里的现金或存款大概还能撑多久？"
        if attempt == 1:
            return {
                "id": qid,
                "field_name": field_name,
                "question_text": base_question,
                "options": ["0-1个月", "2-3个月", "4-6个月", "7-12个月", "12个月以上"],
            }
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": "请直接写一个更接近现实的安全垫范围，例如“2个月”或“不到1个月”。",
            "options": [],
        }
    if field_name == "fixed_expenses":
        if domain == "career":
            first_question = "你每个月最硬的固定支出，大概落在哪个范围？把房租、房贷、家庭分担都算进去。"
            followup_question = "请直接写固定支出的主要构成，例如“房租+家里支持约6500/月”。"
        elif domain == "business":
            first_question = "你现在每个月最硬的固定支出，大概在哪个范围？把房租、团队成本、贷款和家庭开销都算进去。"
            followup_question = "请直接写清固定支出的主要构成，例如“房租+贷款+家庭开销约9000/月”。"
        else:
            first_question = "你每个月最硬的固定支出，大概落在哪个范围？"
            followup_question = "请直接写固定支出的主要构成或范围，例如“房租+贷款约6500/月”。"
        if attempt == 1:
            return {
                "id": qid,
                "field_name": field_name,
                "question_text": first_question,
                "options": ["3000元内", "3000-8000元", "8000-15000元", "15000元以上", "几乎没有固定支出"],
            }
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": followup_question,
            "options": [],
        }
    if field_name == "time_to_reverse":
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": (
                "如果你发现这条路并不值，现实里最快多久能回头？"
                if domain in {"career", "business"}
                else "如果发现这条路不值，最快多久能回头？"
            ),
            "options": ["一周内", "1个月内", "3个月内", "半年以上", "几乎回不了头"],
        }
    if field_name == "reversal_cost":
        options = ["几乎没成本", "会损失一笔钱或一个月缓冲", "会伤到简历/关系/机会", "三者都会受影响"]
        if domain == "career":
            options = ["会亏搬家/租房成本", "会让简历出现一段折返记录", "会错过当前机会窗口", "三种代价都会叠加"]
        elif domain == "business":
            options = ["亏一笔启动金", "现金流会明显变紧", "会伤到职业回撤或关系", "几项代价都会出现"]
        if attempt == 1:
            return {
                "id": qid,
                "field_name": field_name,
                "question_text": "如果要回头，主要代价会落在哪一类？",
                "options": options,
            }
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": "请直接写回头代价，哪怕只是保守估计，例如“会亏1个月房租”或“会错过当前机会窗口”。",
            "options": [],
        }
    if field_name == "worst_fear":
        options = ["花钱/投入后发现根本不值", "现金流或基本盘被打穿", "回头成本太大，自己被锁死", "长期后悔当初没试"]
        if domain == "career":
            options = ["去了之后净收益并没变好", "基本生活和现金流被打乱", "回头会伤简历和机会窗口", "多年后后悔自己没抓住机会"]
        elif domain == "business":
            options = ["投进去后根本没有需求验证", "现金流或基本盘被打穿", "回头时钱和状态都见底", "以后会一直后悔没认真试过"]
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": "你最怕的最坏情况，到底更接近下面哪一种？",
            "options": options,
        }
    if field_name == "other_income":
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": "除了主收入，你现在还有其他稳定或半稳定收入吗？",
            "options": ["没有", "有一点但不稳定", "有，能部分兜底", "有，足够明显缓冲风险"],
        }
    if field_name == "point_of_no_return":
        return {
            "id": qid,
            "field_name": field_name,
            "question_text": "这件事有没有一个过了就很难回头的节点？",
            "options": ["没有明显节点", "签约/搬家后明显变难", "投入大额金钱后变难", "身份/关系变化后几乎回不了头"],
        }
    return {
        "id": qid,
        "field_name": field_name,
        "question_text": f"请补充「{SIM_PARAM_LABELS.get(field_name, field_name)}」这个关键参数。",
        "options": [],
    }


def ensure_sim_question_coverage(
    questions: list[dict] | None,
    *,
    include_optional: bool = False,
    question_context: str = "",
) -> list[dict]:
    normalized = _normalize_sim_questions(questions or [])
    asked = _asked_sim_fields(normalized)
    required_fields = list(CRITICAL_SIM_PARAM_FIELDS)
    if include_optional:
        required_fields.extend(["other_income", "point_of_no_return"])

    for field_name in required_fields:
        if field_name in asked:
            continue
        normalized.append(_sim_param_question_template(field_name, attempt=1, question_context=question_context))
        asked.add(field_name)
    return normalized


def build_followup_sim_questions(
    user_params: dict | None,
    sim_questions: list[dict] | None,
    *,
    question_context: str = "",
) -> list[dict]:
    params = user_params if isinstance(user_params, dict) else {}
    missing_fields = missing_critical_sim_params(params)
    followups = []
    for field_name in missing_fields:
        attempt = _count_sim_field_attempts(sim_questions, field_name) + 1
        followups.append(_sim_param_question_template(
            field_name,
            attempt=attempt,
            question_context=question_context,
        ))
    return followups


def _flatten_choice_for_similarity(choice_data: dict | None) -> str:
    choice = choice_data if isinstance(choice_data, dict) else {}
    fragments = [_sanitize_generated_text(choice.get("choice_name"), default="")]
    distribution = choice.get("probability_distribution") if isinstance(choice.get("probability_distribution"), dict) else {}
    for scenario in ("tailwind", "steady", "headwind"):
        bucket = distribution.get(scenario) if isinstance(distribution.get(scenario), dict) else {}
        fragments.append(_sanitize_generated_text(bucket.get("reason"), default=""))
        timeline = (choice.get("timelines") or {}).get(scenario) if isinstance(choice.get("timelines"), dict) else {}
        nodes = timeline.get("nodes") if isinstance(timeline, dict) else []
        for node in nodes[:6]:
            if not isinstance(node, dict):
                continue
            fragments.extend([
                _sanitize_generated_text(node.get("external_state"), default=""),
                _sanitize_generated_text(node.get("inner_feeling"), default=""),
                _sanitize_generated_text(node.get("key_action"), default=""),
                _sanitize_generated_text(node.get("signal"), default=""),
            ])
    return re.sub(r"\s+", "", " ".join(part for part in fragments if part))


def simulator_choice_similarity(choice_a: dict | None, choice_b: dict | None) -> float:
    a_text = _flatten_choice_for_similarity(choice_a)
    b_text = _flatten_choice_for_similarity(choice_b)
    if not a_text or not b_text:
        return 0.0
    return SequenceMatcher(None, a_text, b_text).ratio()


def _question_signal_type(question_text: str) -> Optional[str]:
    text = _normalize_text(question_text)
    if _contains_any(text, ["缺乏了解", "了解", "信息", "数据", "事实"]):
        return BlockageType.A_INFO_VOID.value
    if _contains_any(text, ["新角度", "框架", "怎么看", "判断标准", "怎么选"]):
        return BlockageType.B_COGNITIVE_NARROW.value
    if _contains_any(text, ["经历过", "别人怎么", "过来人", "经验"]):
        return BlockageType.C_EXPERIENCE_BLANK.value
    if _contains_any(text, ["担心", "害怕", "舍不得", "最怕"]):
        return BlockageType.D_EMOTIONAL_INTERFERENCE.value
    return None


def _is_negative_or_missing(text: str) -> bool:
    return _contains_any(text, ["没有", "没", "不", "不知道", "不清楚", "不了解"])


def _indicates_already_covered(text: str) -> bool:
    return _contains_any(
        text,
        ["都查过", "都了解", "已经查过", "不算最缺", "不是最缺", "挺清楚", "很清楚", "不是这个问题"],
    )


def _extract_months(text: str) -> Optional[int]:
    normalized = str(text or "").replace("个半月", "1.5个月")
    if _contains_any(normalized, ["没有存款", "没有缓冲", "撑不了", "不到一个月", "0-1个月"]):
        return 1
    match = re.search(r"(\d+(?:\.\d+)?)\s*(年|个月|月|周)", normalized)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        if unit == "年":
            value *= 12
        elif unit == "周":
            value /= 4
        return max(0, int(round(value)))

    for word, number in sorted(CHINESE_NUMBER_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if f"{word}年" in normalized:
            return number * 12
        if f"{word}个月" in normalized or f"{word}月" in normalized:
            return number
        if f"{word}周" in normalized:
            return max(0, int(round(number / 4)))
    if "半年" in normalized:
        return 6
    if "一年" in normalized:
        return 12
    return None


def _classify_sim_param_question(question_text: str) -> Optional[str]:
    text = _normalize_text(question_text)
    if _contains_any(text, ["回头", "可逆", "不可逆"]):
        if _contains_any(text, ["代价", "成本"]):
            return "reversal_cost"
        if _contains_any(text, ["不可逆", "节点", "回不了头", "无法回头"]):
            return "point_of_no_return"
        return "time_to_reverse"
    for field_name, hints in SIM_PARAM_FIELD_HINTS.items():
        if _contains_any(text, hints):
            return field_name
    return None


def _fallback_choice_options(original_question: str, recommendation: str, action_plan: str) -> list[dict]:
    question = str(original_question or "").strip()
    if "还是" in question:
        left, right = question.split("还是", 1)
        left = left.strip(" ，。？?要不要该是否选择去留")
        right = right.strip(" ，。？?")
        if left and right:
            return [
                {"name": left[:12], "description": left},
                {"name": right[:12], "description": right},
            ]
    if "要不要" in question:
        action = question.split("要不要", 1)[1].strip(" ，。？?")
        if action:
            return [
                {"name": f"做{action}"[:12], "description": f"主动去做{action}"},
                {"name": f"暂不做{action}"[:12], "description": f"先不做{action}，继续观察或维持现状"},
            ]

    primary = action_plan.strip() or recommendation.strip() or "按当前建议行动"
    return [
        {"name": "推进改变", "description": primary},
        {"name": "维持现状", "description": "暂不推进改变，保留现有安排并继续观察"},
    ]


def _normalize_probability_distribution(raw: dict | None) -> dict:
    defaults = {
        "tailwind": {"percent": 30, "reason": ""},
        "steady": {"percent": 50, "reason": ""},
        "headwind": {"percent": 20, "reason": ""},
    }
    normalized = {}
    raw = raw if isinstance(raw, dict) else {}
    for key, fallback in defaults.items():
        item = raw.get(key, {})
        if not isinstance(item, dict):
            item = {}
        percent = item.get("percent", fallback["percent"])
        try:
            percent = int(percent)
        except (TypeError, ValueError):
            percent = fallback["percent"]
        normalized[key] = {
            "percent": percent,
            "reason": _sanitize_generated_text(item.get("reason", fallback["reason"]), default=""),
        }
    return normalized


def _normalize_timeline_nodes(nodes) -> list[dict]:
    if not isinstance(nodes, list):
        return []

    normalized = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        normalized.append({
            "time": _sanitize_generated_text(node.get("time", ""), default=""),
            "external_state": _sanitize_generated_text(node.get("external_state", node.get("external", "")), default=""),
            "inner_feeling": _sanitize_generated_text(node.get("inner_feeling", node.get("feeling", "")), default=""),
            "key_action": _sanitize_generated_text(node.get("key_action", node.get("action", "")), default=""),
            "signal": _sanitize_generated_text(node.get("signal", ""), default=""),
        })
    return normalized


def _normalize_timeline_buckets(raw_timelines) -> dict:
    timeline_order = ["tailwind", "steady", "headwind"]
    default_titles = {
        "tailwind": "顺风局：比预期更顺利",
        "steady": "平稳局：最可能发生",
        "headwind": "逆风局：遇到困难但还能应对",
    }

    buckets: dict[str, dict] = {}

    if isinstance(raw_timelines, dict):
        for key in timeline_order:
            item = raw_timelines.get(key, {})
            if not isinstance(item, dict):
                item = {}
            buckets[key] = {
                "title": _sanitize_generated_text(item.get("title", default_titles[key]), default=default_titles[key]),
                "nodes": _normalize_timeline_nodes(item.get("nodes", [])),
            }
        return buckets

    if isinstance(raw_timelines, list):
        for index, item in enumerate(raw_timelines[:3]):
            if not isinstance(item, dict):
                continue
            bucket_key = str(item.get("scenario_type", item.get("type", "")) or "").strip().lower()
            if bucket_key not in timeline_order:
                bucket_key = timeline_order[index]
            buckets[bucket_key] = {
                "title": _sanitize_generated_text(item.get("title", default_titles[bucket_key]), default=default_titles[bucket_key]),
                "nodes": _normalize_timeline_nodes(item.get("nodes", [])),
            }

    for key in timeline_order:
        buckets.setdefault(key, {
            "title": default_titles[key],
            "nodes": [],
        })
    return buckets


def _normalize_b7_timeline_output(data, choice_name: str, choice_description: str) -> dict:
    payload = data if isinstance(data, dict) else {}
    resolved_name = str(
        payload.get("choice_name")
        or payload.get("choice")
        or payload.get("option_name")
        or choice_name
        or choice_description
        or "当前选项"
    ).strip()

    raw_timelines = payload.get("timelines")
    if raw_timelines is None:
        raw_timelines = {
            key: payload.get(key)
            for key in ("tailwind", "steady", "headwind")
            if payload.get(key) is not None
        }

    return {
        "choice_name": _sanitize_generated_text(resolved_name, default=choice_name or choice_description or "当前选项"),
        "probability_distribution": _normalize_probability_distribution(
            payload.get("probability_distribution")
        ),
        "timelines": _normalize_timeline_buckets(raw_timelines),
    }


def _contains_phrase(text: str, phrases: list[str]) -> bool:
    normalized = str(text or "").strip().lower()
    return any(item.lower() in normalized for item in phrases)


def _detect_choice_style(choice_name: str, choice_description: str) -> str:
    text = f"{choice_name} {choice_description}"
    hold_markers = ["暂不", "先不", "不去", "留在", "继续", "观望", "等等", "保留", "不换", "不辞"]
    move_markers = ["去", "换", "转", "辞", "搬", "开始", "接受", "创业", "尝试", "行动"]
    if _contains_phrase(text, hold_markers):
        return "hold"
    if _contains_phrase(text, move_markers):
        return "move"
    return "move"


def _build_choice_semantic_slot(
    choice_name: str,
    choice_description: str,
    *,
    slot_index: int = 0,
) -> dict:
    style = _detect_choice_style(choice_name, choice_description)
    if style == "hold":
        return {
            "style": style,
            "label": "保留观察槽位" if slot_index else "保守保留槽位",
            "must": [
                "这条线必须体现保基本盘、补关键变量、推迟重承诺。",
                "关键动作优先写核验、记录、设检查点、保留可逆性。",
                "长期代价要体现“速度变慢”或“遗憾累积”，而不是直接写成另一条行动线。",
            ],
            "must_not": [
                "不要把这条线写成立刻重投入、迅速换环境或直接 All in。",
                "不要把它写成和主动推进路线同一套适应/入场/加码叙事。",
            ],
        }
    return {
        "style": style,
        "label": "主动推进槽位" if slot_index == 0 else "行动加码槽位",
        "must": [
            "这条线必须体现进入新局、承担变化成本、换取新筹码。",
            "关键动作优先写启动、适应、验证、加码或止损，不要停留在纯观察。",
            "长期结果要体现行动带来的新筹码，而不是只是继续考虑。",
        ],
        "must_not": [
            "不要把这条线写成只是再观察、再收集信息、继续原地保守等待。",
            "不要和保留现状路线共用同一套“先查资料再说”的节点动作。",
        ],
    }


def _normalize_probability_triplet(tailwind: int, steady: int, headwind: int) -> tuple[int, int, int]:
    values = [max(5, int(tailwind)), max(5, int(steady)), max(5, int(headwind))]
    total = sum(values) or 1
    normalized = [round(value * 100 / total) for value in values]
    diff = 100 - sum(normalized)
    normalized[1] += diff
    normalized = [max(5, value) for value in normalized]
    diff = 100 - sum(normalized)
    normalized[1] += diff
    return normalized[0], normalized[1], normalized[2]


def _build_probability_distribution(user_params: dict, style: str) -> dict:
    savings_months = int(user_params.get("savings_months") or 0)
    reverse_text = str(user_params.get("time_to_reverse", "") or "")
    other_income = str(user_params.get("other_income", "") or "")

    tailwind = 30 if style == "move" else 24
    steady = 50
    headwind = 20 if style == "move" else 26

    if savings_months <= 1:
        tailwind -= 6
        steady -= 2
        headwind += 8
    elif savings_months >= 6:
        tailwind += 4
        headwind -= 4

    if _contains_phrase(other_income, ["有", "副业", "兼职", "兜底", "收入"]):
        tailwind += 2
        headwind -= 2

    if _contains_phrase(reverse_text, ["很难", "回不了", "长期", "更大经济损失", "违约"]):
        headwind += 5
        steady -= 2
        tailwind -= 3

    tailwind, steady, headwind = _normalize_probability_triplet(tailwind, steady, headwind)
    if style == "hold":
        tailwind_reason = "你把大风险留在门外，所以顺风来自保住基本盘后再等到更好窗口。"
        steady_reason = "更常见的是先稳住节奏，再用复盘和核验慢慢把选择看清。"
        headwind_reason = "这条路的逆风不是崩盘，而是拖久了之后机会流失和遗憾感累积。"
    else:
        tailwind_reason = "你愿意承担变化成本，顺风时能更快把行动换成新筹码。"
        steady_reason = "大多数行动都落在可承受但不完美的中间地带，要边走边校准。"
        headwind_reason = "安全垫、可逆性和你最怕的风险决定了逆风局不会太低。"
    return {
        "tailwind": {
            "percent": tailwind,
            "reason": tailwind_reason,
        },
        "steady": {
            "percent": steady,
            "reason": steady_reason,
        },
        "headwind": {
            "percent": headwind,
            "reason": headwind_reason,
        },
    }


def _make_timeline_node(
    time_label: str,
    external_state: str,
    inner_feeling: str,
    key_action: str,
    signal: str,
) -> dict:
    return {
        "time": time_label,
        "external_state": external_state,
        "inner_feeling": inner_feeling,
        "key_action": key_action,
        "signal": signal,
    }


def _fallback_timeline_nodes(
    style: str,
    scenario: str,
    choice_name: str,
    user_params: dict,
) -> list[dict]:
    fear = _sanitize_generated_text(user_params.get("worst_fear"), default="投入后发现不值或现金流突然吃紧")
    reverse_text = _sanitize_generated_text(user_params.get("time_to_reverse"), default="尽快回头")
    fixed_expenses = _sanitize_generated_text(user_params.get("fixed_expenses"), default="现实压力")

    if style == "hold":
        templates = {
            "tailwind": [
                ("第1周", f"你先按下{choice_name}的冲动，开始补关键资料。", "心里没那么炸，但仍会担心错过机会。", "先把工资、住宿和回头成本列成表。", "你开始从情绪纠结转成具体核算。"),
                ("第1个月", "你补到了几条关键事实，判断变得更实。", "焦虑下降，开始觉得自己不是在拖。", "做一次实地问询或找在岗人核验。", "你能说清楚自己到底在担心什么。"),
                ("第3个月", "你保住了现金缓冲，也看清外地机会真假。", "虽然没有立刻翻盘，但心更稳。", "如果数据明显变好，再决定是否启动。", "你不再被单个高薪数字带着跑。"),
                ("第6个月", "你要么等到更好的窗口，要么确认这条路不值。", "开始接受“慢一点不等于错”。", "根据净结余和家庭安排做二次决策。", "判断依据从感觉变成账本。"),
                ("1年后", "你避免了仓促外出带来的回撤。", "偶尔会想如果当时直接去会怎样。", "保留试错资金和离场方案。", "生活稳定性明显强于冲动决策时。"),
                ("3年后", "你更可能是在更合适的节点行动，而不是硬扛。", "最大的变化是决策更稳，不再只凭一口气。", "继续用可逆性和净收益框架判断下一步。", "你对自己承受风险的边界更清楚。"),
            ],
            "steady": [
                ("第1周", f"生活表面没变，但你开始认真处理{choice_name}背后的现实条件。", "会有点不甘，也会松一口气。", "先把固定支出和最差情况写清楚。", "你开始记录而不是空想。"),
                ("第1个月", "信息补得差不多，但机会也没有自己消失。", "你会反复问自己是不是太保守。", "给自己设一个明确复盘点。", "你不再无限期拖延。"),
                ("第3个月", "如果没有更优机会，你会意识到问题核心是收益质量而不是地点。", "开始从“去不去”转成“值不值”。", "比较净结余、工时和可持续性。", "你更看重长期可承受。"),
                ("第6个月", "你可能找到更稳的替代方案，也可能确认暂缓是对的。", "情绪波动还在，但没有最初那么大。", "复盘这半年真正增加了什么筹码。", "你能说出继续等的代价。"),
                ("1年后", "如果一直没有更优选择，你会需要重新启动行动。", "最大的不舒服来自‘没动’而不是‘动错’。", "决定继续准备还是正式出发。", "你对拖延和审慎的边界更敏感。"),
                ("3年后", "这条路的收益在于避险，但代价是速度可能偏慢。", "你会更在意有没有把窗口用在真正值得的机会。", "只为高质量机会行动，不为焦虑行动。", "你能区分稳住和停滞。"),
            ],
            "headwind": [
                ("第1周", f"你暂缓了{choice_name}，但内耗没有立刻消失。", "会反复刷招聘信息，怕自己错过。", "给“再看一看”设截止日期。", "如果三天后你还只是刷消息，说明在原地打转。"),
                ("第1个月", f"最怕的事换了形态出现: {fear}。", "你会怀疑自己是不是既没抓住机会也没真正避险。", "找出一个可验证指标，不靠情绪猜。", "你开始因为不确定而失眠或暴躁。"),
                ("第3个月", "如果现实没改善，暂缓会开始变成被动拖延。", "挫败感会比当初直接行动更闷。", "要么补齐关键条件，要么承认当前方案不成立。", "你已经说不清自己在等什么。"),
                ("第6个月", "原问题仍在，且机会窗口可能变窄。", "你会更怕自己输给犹豫。", "把下一步写成可执行动作，不再空等。", "继续拖会让你对自己更没信心。"),
                ("1年后", "这条线的问题不是大失败，而是慢性消耗。", "你最难受的会是‘什么都没真正推进’。", "必要时换问题定义，而不是继续消耗。", "你对时间流失的痛感明显高于短期损失。"),
                ("3年后", "如果一直停在这里，遗憾感会慢慢压过安全感。", "你会把很多不满归因到当初没动。", "重新为自己创造更低风险的试错入口。", "你开始更怕长期后悔而不是短期吃亏。"),
            ],
        }
    else:
        templates = {
            "tailwind": [
                ("第1周", f"你正式启动“{choice_name}”，落地比预想顺。", "新鲜感很强，但晚上仍会反复确认自己有没有冲动。", "先守住作息和现金流，不急着证明自己。", "第一周就出现一个实打实的正反馈。"),
                ("第1个月", "你开始熟悉节奏，关键关系也慢慢建立。", "紧绷感下降，开始看到这次行动的价值。", "把有效做法固化成固定流程。", "工作和生活都没有明显失控。"),
                ("第3个月", "这条路的真实收益开始显形。", "你仍会累，但心态明显比刚开始稳。", "检查净结余、成长和身体负担是否同时成立。", "你能说出自己为什么继续。"),
                ("第6个月", "如果顺风继续，你会拿到比原地更大的确定性。", "开始从‘扛过去’变成‘我能把它做好’。", "扩大有效投入，同时保留回撤方案。", "你的筹码比出发前多了。"),
                ("1年后", "你大概率已经验证这条路能不能长期做。", "成就感和疲惫并存，但不是瞎忙。", "复盘哪些收获能沉淀成下一步机会。", "你开始有主动挑选机会的能力。"),
                ("3年后", "这条线的回报是经验、收入或视野至少有一项明显提升。", "最大的变化不是兴奋，而是底气。", "把这次成功经验转成更高质量选择。", "你不再只为逃离现状而行动。"),
            ],
            "steady": [
                ("第1周", f"你开始执行“{choice_name}”，但杂事和适应成本比想象多。", "白天忙，晚上会短暂怀疑自己。", "先稳住最基础的现金流和节奏。", "虽然累，但事情在往前走。"),
                ("第1个月", "现实没有惊喜，也没有崩掉。", "你会经历一段‘值不值得’的摇摆。", "继续核算净收益，不被单天情绪左右。", "你还能按计划做事，而不是天天救火。"),
                ("第3个月", "第一个验证点出现：收益、强度和适应度需要一起看。", "你会更冷静地判断而不是只靠希望。", "给自己设红黄绿信号。", "你已经能看出这条路是辛苦还是消耗。"),
                ("第6个月", f"如果{fixed_expenses}仍压得紧，这条路会显得更现实。", "累是真累，但心里开始有比较依据。", "决定加码、维持，还是准备回撤。", "你能明确看到继续和回头的成本。"),
                ("1年后", "你会得到一个不浪漫但足够真实的结论。", "最大变化是从幻想走到判断。", "留下可复制经验，避免下次重走弯路。", "这条路是不是长期可做，已经比较清楚。"),
                ("3年后", "这条线的价值通常不在爆发，而在给你更稳的下一跳。", "你会更相信自己能处理陌生局面。", "把经验换成更高质量选择，而不是一直硬撑。", "你不再把变化自动等同于危险。"),
            ],
            "headwind": [
                ("第1周", f"你启动“{choice_name}”后，最难的不是工作本身，而是适应和成本。", "一开始就会感到紧绷，怕自己选错。", "先保命，不逞强。", "开销、强度或孤独感明显高于预期。"),
                ("第1个月", f"你最怕的情况开始冒头：{fear}。", "会产生强烈的回头念头，但又怕前功尽弃。", "立刻盘点可回头路径和手头现金。", "你已经在消耗睡眠和耐心。"),
                ("第3个月", "这是第一道真正的止损线。", "你会意识到继续扛和硬扛不是一回事。", f"按“{reverse_text}”准备退路，不等彻底失控。", "如果还在借情绪硬撑，说明该撤了。"),
                ("第6个月", "逆风局下，最重要的是别让一次试错拖垮后面几年。", "羞耻感会比损失更刺痛。", "把损失封顶，先恢复基本盘。", "你开始更在意能不能活下去，而不是面子。"),
                ("1年后", "即使这次没跑通，只要及时止损，也不会是世界末日。", "你会比以前更清楚自己能承受什么。", "整理失败经验，避免把同样的坑再踩一遍。", "你从这次试错里拿回了边界感。"),
                ("3年后", "逆风局留下的不是完蛋，而是一次昂贵但有用的校准。", "真正的损失通常小于当时脑内想象。", "下一次只在准备更充分时再冲。", "你会更尊重可逆性和安全垫。"),
            ],
        }

    return [
        _make_timeline_node(time_label, external_state, inner_feeling, key_action, signal)
        for time_label, external_state, inner_feeling, key_action, signal in templates[scenario]
    ]


def _build_b7_timeline_fallback(choice_name: str, choice_description: str, user_params: dict) -> dict:
    style = _detect_choice_style(choice_name, choice_description)
    distribution = _build_probability_distribution(user_params, style)
    if style == "hold":
        titles = {
            "tailwind": "顺风局：稳住基本盘并等到更好窗口",
            "steady": "平稳局：先保留选择，再持续校准",
            "headwind": "逆风局：拖久了会慢慢变成消耗",
        }
    else:
        titles = {
            "tailwind": "顺风局：推进顺且回报开始显形",
            "steady": "平稳局：辛苦但判断越来越清楚",
            "headwind": "逆风局：遇到压力但还能止损",
        }
    return {
        "choice_name": choice_name or choice_description or "当前选项",
        "probability_distribution": distribution,
        "timelines": {
            key: {
                "title": titles[key],
                "nodes": _fallback_timeline_nodes(style, key, choice_name or choice_description, user_params),
            }
            for key in ("tailwind", "steady", "headwind")
        },
        "fallback_mode": "local_fast",
    }


def _build_b8_fallback(choice_a_timelines: dict, choice_b_timelines: dict, user_params: dict) -> dict:
    fear = _sanitize_generated_text(user_params.get("worst_fear"), default="现金流突然吃紧")
    runway = max(0, int(user_params.get("savings_months") or 0))
    choice_a_name = str(choice_a_timelines.get("choice_name", "选项A") or "选项A")
    choice_b_name = str(choice_b_timelines.get("choice_name", "选项B") or "选项B")
    return {
        "crossroads": [
            {
                "id": 1,
                "time": "第1个月",
                "description": "确认这条路只是新鲜期，还是已经出现可持续信号。",
                "signals": {
                    "green": {"signal": "节奏已稳住，现金流没失控", "action": f"继续执行 {choice_a_name if '去' in choice_a_name else choice_b_name}，先别乱改方向。"},
                    "yellow": {"signal": "能撑住，但收益和消耗都一般", "action": "维持动作，同时补最关键的信息和人脉核验。"},
                    "red": {"signal": "开销、强度或情绪明显超线", "action": "立即准备回撤，不要再拿运气硬顶。"},
                },
                "reversal_cost": "此时回头通常还是短期损失，可控但要果断。",
            },
            {
                "id": 2,
                "time": "第3个月",
                "description": "第一道正式检查站，要判断是否值得继续投入。",
                "signals": {
                    "green": {"signal": "净收益、成长和身体状态至少有两项在变好", "action": "可以加码，但保留退路。"},
                    "yellow": {"signal": "只有一项好转，其余仍模糊", "action": "再给自己一个月验证，不盲目加码。"},
                    "red": {"signal": fear, "action": "立刻按止损方案执行，不把一次试错拖成长期损耗。"},
                },
                "reversal_cost": "此时回头会有沉没成本，但还没到伤筋动骨。",
            },
            {
                "id": 3,
                "time": "第6个月",
                "description": "决定继续深耕，还是及时换路。",
                "signals": {
                    "green": {"signal": "这条路已经证明自己跑得通", "action": "开始把短期收益沉淀成长期筹码。"},
                    "yellow": {"signal": "能活，但不够值", "action": "准备平移到更优版本，不在原地死扛。"},
                    "red": {"signal": "你靠透支自己才勉强维持", "action": "马上收缩战线，先恢复基本盘。"},
                },
                "reversal_cost": "继续拖下去的代价，通常开始高过立刻调整。",
            },
        ],
        "worst_case_survival_plan": {
            "trigger": fear,
            "day_1": "先停下硬扛，把现金、住处、工作状态三件事盘清楚。",
            "week_1": "联系可回撤的人和渠道，砍掉非必要支出，保住基本盘。",
            "month_1": "优先恢复稳定收入或稳定住处，再决定下一跳。",
            "safety_runway": f"按当前回答估算，安全垫约还能支撑 {runway} 个月。",
            "emotional_note": "最难受的通常不是损失本身，而是觉得自己白折腾了。先活下来，再谈值不值。",
        },
        "milestone_check_system": [
            {"time": "1个月", "check": "看节奏是否稳住，现金流是否还能承受。"},
            {"time": "3个月", "check": "看净收益、成长和消耗是否同时成立。"},
            {"time": "6个月", "check": "决定继续深耕、微调，还是果断止损。"},
            {"time": "12个月", "check": "复盘这条路到底给你留下了什么长期筹码。"},
        ],
        "fallback_mode": "local_fast",
    }


def _scenario_score(choice_data: dict) -> tuple[int, int, int]:
    probs = choice_data.get("probability_distribution", {}) if isinstance(choice_data, dict) else {}
    tailwind = int(((probs.get("tailwind") or {}).get("percent") or 0))
    steady = int(((probs.get("steady") or {}).get("percent") or 0))
    headwind = int(((probs.get("headwind") or {}).get("percent") or 0))
    return tailwind, steady, headwind


def _build_action_map(choice_data: dict) -> list[str]:
    choice_name = str(choice_data.get("choice_name", "当前选项") or "当前选项")
    steady_nodes = (((choice_data.get("timelines") or {}).get("steady") or {}).get("nodes") or [])
    mapped = []
    label_map = {
        "第1周": "今天",
        "第1个月": "本周",
        "第3个月": "第1个月",
        "第6个月": "第3个月★检查站",
        "1年后": "第6个月★检查站",
        "3年后": "第12个月",
    }
    for node in steady_nodes[:6]:
        time_label = label_map.get(str(node.get("time", "")).strip(), str(node.get("time", "")).strip() or "下一步")
        action = str(node.get("key_action", "") or "").strip() or f"继续推进 {choice_name}"
        mapped.append(f"{time_label}：{action}")

    if len(mapped) < 6:
        defaults = [
            f"今天：先确认 {choice_name} 的最低可行动作。",
            "本周：把现金流、时间和精力约束写清楚。",
            "第1个月：复盘这条路带来的真实变化。",
            "第3个月★检查站：用数据判断要不要继续。",
            "第6个月★检查站：决定加码、维持还是回撤。",
            "第12个月：回看这条路有没有沉淀成长期筹码。",
        ]
        mapped.extend(defaults[len(mapped):])
    return mapped[:6]


def _estimate_regret_score(choice_data: dict, user_params: dict) -> int:
    tailwind, steady, headwind = _scenario_score(choice_data)
    savings_months = int(user_params.get("savings_months") or 0)
    reversal_cost = _sanitize_generated_text(user_params.get("reversal_cost"), default="")
    regret = headwind
    regret += max(0, 42 - steady) // 2
    if savings_months <= 1:
        regret += 14
    elif savings_months <= 3:
        regret += 8
    if _contains_any(reversal_cost, ["大", "高", "伤", "违约", "回不了"]):
        regret += 8
    return max(5, min(95, int(regret)))


def _baseline_probability_weights(choice_a_sim: dict, choice_b_sim: dict) -> tuple[int, int, int]:
    a_tailwind, a_steady, a_headwind = _scenario_score(choice_a_sim)
    b_tailwind, b_steady, b_headwind = _scenario_score(choice_b_sim)
    optimistic = max(12, min(45, int(round((a_tailwind + b_tailwind) / 2))))
    baseline = max(30, min(60, int(round((a_steady + b_steady) / 2))))
    pessimistic = max(10, min(40, 100 - optimistic - baseline))
    optimistic, baseline, pessimistic = _normalize_probability_triplet(optimistic, baseline, pessimistic)
    return optimistic, baseline, pessimistic


def _build_b9_fallback(
    choice_a_sim: dict,
    choice_b_sim: dict,
    user_params: dict,
    *,
    decision_biases: Optional[list[dict]] = None,
    alternative_path: Optional[dict] = None,
) -> dict:
    a_tailwind, a_steady, a_headwind = _scenario_score(choice_a_sim)
    b_tailwind, b_steady, b_headwind = _scenario_score(choice_b_sim)
    a_name = str(choice_a_sim.get("choice_name", "选项A") or "选项A")
    b_name = str(choice_b_sim.get("choice_name", "选项B") or "选项B")
    savings_months = int(user_params.get("savings_months") or 0)
    regret_a = _estimate_regret_score(choice_a_sim, user_params)
    regret_b = _estimate_regret_score(choice_b_sim, user_params)
    optimistic, baseline, pessimistic = _baseline_probability_weights(choice_a_sim, choice_b_sim)
    merged_biases = _merge_bias_entries(decision_biases or [])

    a_score = (100 - a_headwind) + a_steady
    b_score = (100 - b_headwind) + b_steady
    recommended = "A" if a_score >= b_score else "B"
    better_name = a_name if recommended == "A" else b_name
    more_stable_name = a_name if a_headwind <= b_headwind else b_name

    if savings_months <= 1:
        core_reason = f"你现在安全垫偏薄，先选最坏情况更可承受的那条路更重要。当前更稳的是「{more_stable_name}」。"
    else:
        core_reason = f"两条路都不是零成本，但从顺逆风占比看，「{better_name}」的综合承受度更高。"

    return {
        "comparison_summary": (
            f"对比来看，「{a_name}」的顺风概率约 {a_tailwind}%，逆风概率约 {a_headwind}%；"
            f"「{b_name}」的顺风概率约 {b_tailwind}%，逆风概率约 {b_headwind}%。\n"
            f"{core_reason}\n"
            "判断重点不是哪条路更漂亮，而是哪条路在不顺时你也扛得住。"
        ),
        "action_map_a": _build_action_map(choice_a_sim),
        "action_map_b": _build_action_map(choice_b_sim),
        "final_insight": (
            f"你真正怕的往往不是吃苦，而是吃了苦之后还回不了头，所以先选可承受的那条。"
        ),
        "regret_score_a": regret_a,
        "regret_score_b": regret_b,
        "probability_optimistic": optimistic,
        "probability_baseline": baseline,
        "probability_pessimistic": pessimistic,
        "decision_biases": merged_biases,
        "bias_reminder": _build_bias_reminder(merged_biases),
        "third_path": _normalize_alternative_path(alternative_path or {}),
        "fallback_mode": "local_fast",
    }


ULTRA_PERSONA_BASE = [
    {"name": "乐观派", "stance": "optimistic", "bias": "强调机会、复利与正反馈", "weight": 0.18},
    {"name": "悲观派", "stance": "pessimistic", "bias": "专注最坏结果与连锁风险", "weight": -0.20},
    {"name": "数据派", "stance": "baseline", "bias": "只看历史数据与可验证信号", "weight": 0.02},
    {"name": "风险控", "stance": "pessimistic", "bias": "极端保守，优先计算不可逆损失", "weight": -0.24},
    {"name": "黑天鹅猎手", "stance": "pessimistic", "bias": "专门寻找小概率突发变量", "weight": -0.16},
    {"name": "历史复盘师", "stance": "baseline", "bias": "用类似案例校准想象", "weight": -0.02},
    {"name": "现金流守门员", "stance": "pessimistic", "bias": "只盯安全垫、固定支出和断供风险", "weight": -0.18},
    {"name": "机会成本审计师", "stance": "baseline", "bias": "比较不行动的隐性损失", "weight": 0.08},
    {"name": "行动派", "stance": "optimistic", "bias": "偏向可逆试验和先做起来", "weight": 0.14},
    {"name": "退出机制设计师", "stance": "baseline", "bias": "偏向先设计回头路再下注", "weight": -0.04},
]


ULTRA_BRANCH_FACTORS = [
    {"key": "policy_tailwind", "label": "政策/平台利好", "delta": 0.16},
    {"key": "market_pullback", "label": "市场突然回撤", "delta": -0.18},
    {"key": "cashflow_break", "label": "现金流承压", "delta": -0.22},
    {"key": "tooling_jump", "label": "AI工具大升级", "delta": 0.13},
    {"key": "support_network", "label": "出现关键支持者", "delta": 0.10},
    {"key": "execution_drag", "label": "执行拖延/精力不足", "delta": -0.12},
    {"key": "neutral", "label": "无明显突发变量", "delta": 0.0},
]


ULTRA_PANEL_SPECS = [
    ("风险委员会", "只盯失败链条、资金压力、不可逆损失和延迟爆雷。"),
    ("机会委员会", "只盯上行空间、复利窗口、能力迁移和非线性机会。"),
    ("数据委员会", "只看概率、基线、样本代表性和过拟合风险。"),
    ("黑天鹅委员会", "专门寻找低概率高冲击变量，以及被正常叙事忽略的尾部事件。"),
    ("执行委员会", "评估用户能否持续执行、什么时候会掉队、怎样设计最小行动。"),
    ("客户视角委员会", "把结论改写成客户愿意付费阅读的高级交付语言。"),
    ("反方律师团", "强行攻击当前建议，找出最可能误导用户的漏洞。"),
    ("董事会合议团", "把冲突观点压缩成可执行决策、护栏和检查点。"),
]


def _stable_seed(*parts) -> int:
    text = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def generate_dynamic_personas(count: int = 40, *, seed_text: str = "") -> list[dict]:
    """为 Ultra Monte Carlo 生成稳定、可复现的动态代理。"""
    count = max(1, int(count or 40))
    rng = random.Random(_stable_seed("ultra_personas", seed_text, count))
    personas = []
    for index in range(count):
        base = dict(ULTRA_PERSONA_BASE[index % len(ULTRA_PERSONA_BASE)])
        jitter = rng.uniform(-0.055, 0.055)
        personas.append({
            "id": f"agent_{index + 1:02d}",
            "name": f"{base['name']}{index + 1:02d}",
            "base_name": base["name"],
            "stance": base["stance"],
            "desc": f"{base['bias']}（第{index + 1}号）",
            "weight": round(base["weight"] + jitter, 4),
        })
    rng.shuffle(personas)
    return personas


def _normal_ci(percent: float, total: int) -> list[float]:
    total = max(1, int(total or 1))
    p = max(0.0, min(float(percent) / 100, 1.0))
    margin = 1.96 * math.sqrt((p * (1 - p)) / total) * 100
    return [round(max(0.0, percent - margin), 1), round(min(100.0, percent + margin), 1)]


def _choice_resilience_score(choice: dict, user_params: dict) -> float:
    tailwind, steady, headwind = _scenario_score(choice)
    regret = _estimate_regret_score(choice, user_params)
    return (tailwind * 0.55 + steady * 0.28 - headwind * 0.48 - regret * 0.16) / 100


def _external_signal_delta(signals: Optional[list[dict]]) -> float:
    if not isinstance(signals, list) or not signals:
        return 0.0
    score = 0.0
    for item in signals[:8]:
        if not isinstance(item, dict):
            continue
        stance = str(item.get("stance", "") or "").lower()
        summary = str(item.get("summary", "") or "")
        if stance in {"positive", "supportive", "tailwind"} or _contains_any(summary, ["值得", "利好", "增长", "提效", "机会"]):
            score += 0.025
        if stance in {"negative", "risk", "headwind"} or _contains_any(summary, ["退款", "焦虑", "不值", "风险", "崩"]):
            score -= 0.025
    return max(-0.12, min(0.12, score))


def _unique_nonempty_lines(items: Optional[list], *, limit: int = 8) -> list[str]:
    if not isinstance(items, list):
        return []
    seen = set()
    lines: list[str] = []
    for item in items:
        text = _sanitize_generated_text(item, default="")
        if not text or text in seen:
            continue
        seen.add(text)
        lines.append(text)
        if len(lines) >= limit:
            break
    return lines


def _ultra_branch_vote(
    *,
    base_score: float,
    factor_delta: float,
    persona: dict,
    rng: random.Random,
    savings_months: int,
) -> float:
    cashflow_penalty = -0.10 if savings_months <= 1 and persona.get("stance") == "pessimistic" else 0.0
    execution_noise = rng.uniform(-0.08, 0.08)
    return base_score + factor_delta + float(persona.get("weight") or 0) + cashflow_penalty + execution_noise


def run_ultra_monte_carlo_collision(
    *,
    question: str,
    choice_a_sim: dict,
    choice_b_sim: dict,
    user_params: dict,
    value_profile: Optional[dict] = None,
    decision_biases: Optional[list[dict]] = None,
    external_signals: Optional[list[dict]] = None,
    sample_count: int = 800,
    persona_count: int = 40,
    agents_per_branch: int = 15,
    rounds: int = 4,
    branch_sample_limit: int = 80,
    llm_panels: int = 0,
    llm_max_tokens: int = 4096,
) -> dict:
    """Ultra Monte Carlo：可控本地分支采样 + 可选 LLM 代表团总结。"""
    sample_count = max(1, int(sample_count or 800))
    persona_count = max(4, int(persona_count or 40))
    agents_per_branch = max(1, min(int(agents_per_branch or 15), persona_count))
    rounds = max(1, int(rounds or 4))
    branch_sample_limit = max(0, int(branch_sample_limit or 80))
    llm_panels = max(0, int(llm_panels or 0))
    personas = generate_dynamic_personas(persona_count, seed_text=question)
    rng = random.Random(_stable_seed("ultra_mc", question, choice_a_sim.get("choice_name"), choice_b_sim.get("choice_name"), sample_count))

    a_resilience = _choice_resilience_score(choice_a_sim, user_params)
    b_resilience = _choice_resilience_score(choice_b_sim, user_params)
    base_tailwind, base_steady, base_headwind = _baseline_probability_weights(choice_a_sim, choice_b_sim)
    base_score = ((base_tailwind - base_headwind) / 100) + ((a_resilience + b_resilience) / 2)
    base_score += _external_signal_delta(external_signals)

    try:
        savings_months = int(user_params.get("savings_months") or 0)
    except (TypeError, ValueError):
        savings_months = 0

    counts = {"optimistic": 0, "baseline": 0, "pessimistic": 0}
    persona_votes: dict[str, dict[str, int]] = {
        persona["id"]: {"persona": persona["name"], "optimistic": 0, "baseline": 0, "pessimistic": 0}
        for persona in personas
    }
    factor_stats: dict[str, dict] = {}
    branches = []

    for branch_id in range(sample_count):
        factor = rng.choice(ULTRA_BRANCH_FACTORS)
        factor_stats.setdefault(factor["key"], {
            "key": factor["key"],
            "label": factor["label"],
            "seen": 0,
            "optimistic": 0,
            "baseline": 0,
            "pessimistic": 0,
            "total_score": 0.0,
        })
        factor_stats[factor["key"]]["seen"] += 1

        sampled_personas = rng.sample(personas, k=agents_per_branch)
        branch_scores = []
        for _round in range(rounds):
            for persona in sampled_personas:
                vote_score = _ultra_branch_vote(
                    base_score=base_score,
                    factor_delta=float(factor["delta"]),
                    persona=persona,
                    rng=rng,
                    savings_months=savings_months,
                )
                branch_scores.append(vote_score)
                vote_bucket = "optimistic" if vote_score >= 0.34 else ("pessimistic" if vote_score <= -0.18 else "baseline")
                persona_votes[persona["id"]][vote_bucket] += 1

        final_score = sum(branch_scores) / max(len(branch_scores), 1)
        bucket = "optimistic" if final_score >= 0.30 else ("pessimistic" if final_score <= -0.12 else "baseline")
        counts[bucket] += 1
        factor_stats[factor["key"]][bucket] += 1
        factor_stats[factor["key"]]["total_score"] += final_score
        if len(branches) < branch_sample_limit:
            branches.append({
                "branch_id": branch_id + 1,
                "factor": factor["label"],
                "final_score": round(final_score, 3),
                "classification": bucket,
                "agents": [persona["base_name"] for persona in sampled_personas[:6]],
            })

    optimistic, baseline, pessimistic = _normalize_probability_triplet(
        counts["optimistic"],
        counts["baseline"],
        counts["pessimistic"],
    )
    smooth_prob = {
        "optimistic": optimistic,
        "baseline": baseline,
        "pessimistic": pessimistic,
    }
    confidence_interval = {
        "optimistic": _normal_ci(optimistic, sample_count),
        "baseline": _normal_ci(baseline, sample_count),
        "pessimistic": _normal_ci(pessimistic, sample_count),
    }
    heatmap = []
    for item in factor_stats.values():
        seen = max(int(item["seen"]), 1)
        heatmap.append({
            "key": item["key"],
            "label": item["label"],
            "seen": seen,
            "avg_score": round(item["total_score"] / seen, 3),
            "optimistic_share": round(item["optimistic"] / seen * 100, 1),
            "baseline_share": round(item["baseline"] / seen * 100, 1),
            "pessimistic_share": round(item["pessimistic"] / seen * 100, 1),
        })
    heatmap.sort(key=lambda item: abs(item["avg_score"]), reverse=True)

    top_personas = sorted(
        persona_votes.values(),
        key=lambda item: max(item["optimistic"], item["baseline"], item["pessimistic"]),
        reverse=True,
    )[:12]

    result = {
        "mode": "ultra_monte_carlo_v1",
        "sample_count": sample_count,
        "persona_count": persona_count,
        "agents_per_branch": agents_per_branch,
        "rounds": rounds,
        "base_probability": {
            "optimistic": base_tailwind,
            "baseline": base_steady,
            "pessimistic": base_headwind,
        },
        "smooth_prob": smooth_prob,
        "confidence_interval": confidence_interval,
        "disagreement_heatmap": heatmap,
        "persona_votes": top_personas,
        "branches": branches,
        "branch_sample_limit": branch_sample_limit,
        "llm_panels_requested": llm_panels,
        "llm_mode": "multi_panel_llm" if llm_panels > 0 else "local_sampling",
        "llm_max_tokens": llm_max_tokens,
        "llm_calls_attempted": 0,
        "actual_llm_calls": 0,
        "llm_panel_reports": [],
        "llm_collision_summary": "",
        "critical_disagreements": [],
        "decision_guardrails": [],
        "client_report_memo": "",
    }

    if llm_panels > 0:
        panel_reports = []
        panel_count = max(1, int(llm_panels))
        for panel_index in range(panel_count):
            panel_name, panel_mandate = ULTRA_PANEL_SPECS[panel_index % len(ULTRA_PANEL_SPECS)]
            branch_slice = branches[panel_index::panel_count][:8] or branches[:8]
            user_msg = f"""用户问题：{question}
选项A：{choice_a_sim.get('choice_name')}
选项B：{choice_b_sim.get('choice_name')}
价值排序：{_build_value_profile_text(value_profile)}
可能偏差：{_build_bias_text(decision_biases)}
外部信号：{json.dumps(external_signals[:8] if isinstance(external_signals, list) else [], ensure_ascii=False)}
Monte Carlo 平滑分布：{smooth_prob}
置信区间：{confidence_interval}
关键分歧热力图：{heatmap[:8]}
代表分支样本：{json.dumps(branch_slice, ensure_ascii=False)}

你是【{panel_name}】，职责：{panel_mandate}
请做一次真正尖锐的 Ultra 决策碰撞，不要温吞，不要模板化。输出 JSON：
{{
  "panel_name": "{panel_name}",
  "position": "一句话立场",
  "confidence": 0.0,
  "executive_summary": "220字内高级摘要",
  "scenario_read": {{
    "optimistic": "顺风局最可能怎样展开",
    "baseline": "平稳局最可能怎样展开",
    "pessimistic": "逆风局最可能怎样展开"
  }},
  "critical_disagreements": ["最关键分歧1", "最关键分歧2", "最关键分歧3"],
  "decision_guardrails": ["必须设置的护栏1", "必须设置的护栏2", "必须设置的护栏3"],
  "report_paragraph": "可直接放进客户报告的一段出版级文字"
}}"""
            try:
                result["llm_calls_attempted"] += 1
                panel = call_agent_json(
                    f"你是 Ultra 模式的{panel_name}，正在参与付费级决策委员会。只输出合法 JSON。",
                    user_msg,
                    max_tokens=llm_max_tokens,
                    temperature=0.35,
                    retries=1,
                    allow_downgrade=True,
                    timeout_seconds=90,
                )
                if isinstance(panel, dict):
                    result["actual_llm_calls"] += 1
                    panel_reports.append({
                        "panel_name": _sanitize_generated_text(panel.get("panel_name"), default=panel_name),
                        "position": _sanitize_generated_text(panel.get("position"), default=""),
                        "confidence": panel.get("confidence", ""),
                        "executive_summary": _sanitize_generated_text(panel.get("executive_summary"), default=""),
                        "scenario_read": panel.get("scenario_read") if isinstance(panel.get("scenario_read"), dict) else {},
                        "critical_disagreements": _unique_nonempty_lines(panel.get("critical_disagreements"), limit=5),
                        "decision_guardrails": _unique_nonempty_lines(panel.get("decision_guardrails"), limit=5),
                        "report_paragraph": _sanitize_generated_text(panel.get("report_paragraph"), default=""),
                    })
            except Exception as exc:
                panel_reports.append({
                    "panel_name": panel_name,
                    "position": "该委员会调用失败",
                    "confidence": "",
                    "executive_summary": f"该委员会未能完成结构化输出：{exc}",
                    "scenario_read": {},
                    "critical_disagreements": [],
                    "decision_guardrails": [],
                    "report_paragraph": "",
                    "error": str(exc),
                })

        result["llm_panel_reports"] = panel_reports
        aggregated_disagreements = []
        aggregated_guardrails = []
        for panel in panel_reports:
            aggregated_disagreements.extend(panel.get("critical_disagreements") or [])
            aggregated_guardrails.extend(panel.get("decision_guardrails") or [])
        result["critical_disagreements"] = _unique_nonempty_lines(aggregated_disagreements, limit=8)
        result["decision_guardrails"] = _unique_nonempty_lines(aggregated_guardrails, limit=8)

        if panel_reports:
            synthesis_msg = f"""用户问题：{question}
Monte Carlo 分布：{smooth_prob}
置信区间：{confidence_interval}
各委员会报告：{json.dumps(panel_reports, ensure_ascii=False)}

请把这些委员会报告合成为最终客户交付稿。输出 JSON：
{{
  "summary": "300字内最终合议结论",
  "client_report_memo": "500字以内，适合放进PDF首页后的高级摘要",
  "critical_disagreements": ["压缩后的关键分歧1", "关键分歧2", "关键分歧3", "关键分歧4"],
  "decision_guardrails": ["最终护栏1", "最终护栏2", "最终护栏3", "最终护栏4"],
  "premium_report_sections": ["报告段落1", "报告段落2", "报告段落3"]
}}"""
            try:
                result["llm_calls_attempted"] += 1
                synthesis = call_agent_json(
                    "你是 Ultra 决策总编辑，负责把多委员会碰撞写成客户可读的高级报告。只输出合法 JSON。",
                    synthesis_msg,
                    max_tokens=llm_max_tokens,
                    temperature=0.25,
                    retries=1,
                    allow_downgrade=True,
                    timeout_seconds=90,
                )
                if isinstance(synthesis, dict):
                    result["actual_llm_calls"] += 1
                    result["llm_collision_summary"] = _sanitize_generated_text(synthesis.get("summary"), default="")
                    result["client_report_memo"] = _sanitize_generated_text(synthesis.get("client_report_memo"), default="")
                    result["critical_disagreements"] = _unique_nonempty_lines(
                        synthesis.get("critical_disagreements") if isinstance(synthesis.get("critical_disagreements"), list) else result["critical_disagreements"],
                        limit=8,
                    )
                    result["decision_guardrails"] = _unique_nonempty_lines(
                        synthesis.get("decision_guardrails") if isinstance(synthesis.get("decision_guardrails"), list) else result["decision_guardrails"],
                        limit=8,
                    )
                    result["premium_report_sections"] = _unique_nonempty_lines(
                        synthesis.get("premium_report_sections"),
                        limit=6,
                    )
            except Exception:
                pass

        if not result["llm_collision_summary"]:
            successful_summaries = [
                panel.get("executive_summary")
                for panel in panel_reports
                if panel.get("executive_summary") and not panel.get("error")
            ]
            result["llm_collision_summary"] = "；".join(successful_summaries[:3])

    return result


def normalize_simulator_output(output: dict | None) -> dict:
    """补齐历史会话或部分 LLM 返回里缺失的模拟器摘要字段。"""
    if not isinstance(output, dict):
        return {}

    choice_a_sim = output.get("choice_a") if isinstance(output.get("choice_a"), dict) else {}
    choice_b_sim = output.get("choice_b") if isinstance(output.get("choice_b"), dict) else {}
    user_params = output.get("user_params") if isinstance(output.get("user_params"), dict) else {}
    fallback = _build_b9_fallback(
        choice_a_sim,
        choice_b_sim,
        user_params,
        decision_biases=output.get("decision_biases", []),
        alternative_path=output.get("third_path", {}),
    )

    normalized = dict(output)

    summary = _sanitize_generated_text(output.get("comparison_summary"), default="")
    insight = _sanitize_generated_text(output.get("final_insight"), default="")

    action_map_a = [
        _sanitize_generated_text(item, default="")
        for item in (output.get("action_map_a") if isinstance(output.get("action_map_a"), list) else [])
        if _sanitize_generated_text(item, default="")
    ]
    action_map_b = [
        _sanitize_generated_text(item, default="")
        for item in (output.get("action_map_b") if isinstance(output.get("action_map_b"), list) else [])
        if _sanitize_generated_text(item, default="")
    ]

    normalized["comparison_summary"] = summary or fallback["comparison_summary"]
    normalized["final_insight"] = insight or fallback["final_insight"]
    normalized["action_map_a"] = action_map_a or fallback["action_map_a"]
    normalized["action_map_b"] = action_map_b or fallback["action_map_b"]
    normalized["regret_score_a"] = int(output.get("regret_score_a") or fallback["regret_score_a"])
    normalized["regret_score_b"] = int(output.get("regret_score_b") or fallback["regret_score_b"])
    normalized["probability_optimistic"] = int(output.get("probability_optimistic") or fallback["probability_optimistic"])
    normalized["probability_baseline"] = int(output.get("probability_baseline") or fallback["probability_baseline"])
    normalized["probability_pessimistic"] = int(output.get("probability_pessimistic") or fallback["probability_pessimistic"])
    normalized["decision_biases"] = _merge_bias_entries(output.get("decision_biases", []), fallback.get("decision_biases", []))
    normalized["bias_reminder"] = _sanitize_generated_text(output.get("bias_reminder"), default=fallback["bias_reminder"])
    normalized["third_path"] = _normalize_alternative_path(output.get("third_path", {})) or fallback.get("third_path", {})
    normalized["market_signals"] = _normalize_market_signals(output.get("market_signals", []))
    normalized["choice_a"] = _normalize_b7_timeline_output(choice_a_sim, str(choice_a_sim.get("choice_name", "") or ""), "")
    normalized["choice_b"] = _normalize_b7_timeline_output(choice_b_sim, str(choice_b_sim.get("choice_name", "") or ""), "")

    survival = output.get("worst_case_survival_plan")
    if isinstance(survival, dict):
        normalized["worst_case_survival_plan"] = {
            "trigger": _sanitize_generated_text(survival.get("trigger"), default=""),
            "day_1": _sanitize_generated_text(survival.get("day_1"), default=""),
            "week_1": _sanitize_generated_text(survival.get("week_1"), default=""),
            "month_1": _sanitize_generated_text(survival.get("month_1"), default=""),
            "safety_runway": _sanitize_generated_text(survival.get("safety_runway"), default=""),
            "emotional_note": _sanitize_generated_text(survival.get("emotional_note"), default=""),
        }
    crossroads = output.get("crossroads")
    if isinstance(crossroads, list):
        normalized["crossroads"] = [
            {
                "id": item.get("id"),
                "time": _sanitize_generated_text(item.get("time"), default=""),
                "description": _sanitize_generated_text(item.get("description"), default=""),
                "signals": {
                    signal_key: {
                        "signal": _sanitize_generated_text((((item.get("signals") if isinstance(item.get("signals"), dict) else {}).get(signal_key)) or {}).get("signal"), default=""),
                        "action": _sanitize_generated_text((((item.get("signals") if isinstance(item.get("signals"), dict) else {}).get(signal_key)) or {}).get("action"), default=""),
                    }
                    for signal_key in ("green", "yellow", "red")
                },
                "reversal_cost": _sanitize_generated_text(item.get("reversal_cost"), default=""),
            }
            for item in crossroads
            if isinstance(item, dict)
        ]
    milestones = output.get("milestones")
    if isinstance(milestones, list):
        normalized["milestones"] = [
            {
                "time": _sanitize_generated_text(item.get("time"), default=""),
                "check": _sanitize_generated_text(item.get("check"), default=""),
            }
            if isinstance(item, dict) else _sanitize_generated_text(item, default="")
            for item in milestones
        ]
    return normalized


# ============================================================
# B2 System Prompt - 信息侦探
# ============================================================
B2_SYSTEM = """你是一位"信息侦探"，专门发现决策者遗漏的关键信息。

给定用户的原始问题和诊断结果（用户卡在哪个环节），请：

1. 识别用户当前掌握的信息（已知的已知）
2. 发现用户遗漏的关键信息（未知的未知）
3. 对每个遗漏信息提供：
   - 这个信息是什么
   - 为什么它对决策至关重要
   - 目前公开可得的相关数据或合理估计
   - 如何验证这个信息

请以JSON格式输出：
{
  "missing_info": [
    {
      "title": "信息项标题（10字内）",
      "content": "具体的遗漏信息内容（150字内）",
      "impact": "strong|medium|weak",
      "why_critical": "为什么这个信息重要（50字内）",
      "source_suggestion": "可以从哪里获取这个信息（50字内）"
    }
  ]
}

如果诊断结果显示用户主要不是信息问题（而是认知框架/经验/情绪问题），请返回空的 missing_info 数组。

只输出JSON，不要输出其他内容。"""


# ============================================================
# B3 System Prompt - 认知解锁
# ============================================================
B3_SYSTEM = """你是一位"认知解锁教练"。用户并非完全缺信息，而是缺少理解问题的认知框架。

给定用户的原始问题、诊断结果和已补充的信息，请：

1. 提炼出 2-3 个最适合这个决策的思考框架
2. 每个框架都要帮用户"换一个角度看同一个问题"
3. 不要空泛说教，要能马上拿去判断
4. 请识别用户当前可能陷入的决策心理学偏差（framing_effect / loss_aversion / sunk_cost / regret_theory 等），并给每个框架补一句“偏差提醒”

请以JSON格式输出：
{
  "cognitive_frames": [
    {
      "title": "框架名称（10字内）",
      "core_insight": "这个框架最核心的一句话（60字内）",
      "why_it_matters": "为什么它能帮这个具体问题（80字内）",
      "reframe_question": "用这个框架重问一次原问题（40字内）",
      "try_now": "用户现在就能做的一个判断动作（40字内）",
      "bias_alert": "这个框架最能纠正的偏差（30字内）"
    }
  ]
}

如果诊断显示用户主要不是认知框架问题，请返回空的 cognitive_frames 数组。

只输出JSON，不要输出其他内容。"""


# ============================================================
# B4 System Prompt - 经验模拟
# ============================================================
B4_SYSTEM = """你是一位"经验对照师"。用户缺的不是信息，而是可参照的真实经验。

请基于用户的问题生成 3 个高度真实、彼此不同的经验对照案例。案例可以是抽象后的典型人物，不需要真实姓名，但要足够像现实。

每个案例必须包含：
1. 当事人起点和处境
2. 他/她最后怎么选
3. 之后发生了什么
4. 这个案例对用户最有价值的提醒

请以JSON格式输出：
{
  "experience_cases": [
    {
      "title": "案例标题（15字内）",
      "starting_point": "他/她当时的处境（80字内）",
      "choice_made": "最终怎么选",
      "outcome": "后续结果（100字内）",
      "lesson": "这个案例真正说明了什么（60字内）",
      "transfer_hint": "用户该借鉴什么，不该照抄什么（60字内）"
    }
  ]
}

如果诊断显示用户主要不是经验盲区，请返回空的 experience_cases 数组。

只输出JSON，不要输出其他内容。"""


# ============================================================
# B5 System Prompt - 情绪镜像
# ============================================================
B5_SYSTEM = """你是一位"情绪镜像师"。你的任务不是安慰用户，而是帮用户看清情绪正在如何影响判断。

给定用户的原始问题和回答，请识别：
1. 当前最强的 1-3 个情绪
2. 这些情绪背后在保护什么
3. 它可能让用户高估或低估了什么风险
4. 一个能让用户回到更清醒位置的提醒
5. 请识别用户当前可能陷入的决策心理学偏差（framing_effect / loss_aversion / sunk_cost / regret_theory 等），并在输出中给出1-2句针对性提醒。

请以JSON格式输出：
{
  "emotional_insight": {
    "dominant_emotions": [
      {"emotion": "害怕", "intensity": "strong|medium|light", "evidence": "从哪里看出来"}
    ],
    "hidden_need": "这些情绪真正想保护的东西（50字内）",
    "decision_distortion": "它可能让判断偏向哪里（60字内）",
    "grounding_prompt": "一句帮助用户稳住自己的提醒（40字内）",
    "gentle_reminder": "一个温和但诚实的镜像结论（60字内）",
    "decision_biases": [{"key": "loss_aversion", "label": "损失厌恶", "hint": "它会让你..." }],
    "bias_reminder": "1-2句偏差提醒（60字内）"
  }
}

如果诊断显示用户主要不是情绪干扰，请返回空的 emotional_insight 对象。

只输出JSON，不要输出其他内容。"""


# ============================================================
# B5.5 System Prompt - 第三条路
# ============================================================
B5_5_SYSTEM = """你是一位"第三条路发现者"。

当用户被困在 A / B 二选一时，请主动寻找一个既不是 A、也不是 B 的可执行过渡路径。

要求：
1. 第三条路必须现实，不要鸡汤，不要幻想型“全都要”
2. 它应该降低不可逆风险，或者把大决策拆成更小的验证动作
3. 说明它为什么比直接二选一更适合当前用户

请以 JSON 输出：
{
  "alternative_path": {
    "title": "第三条路名称（12字内）",
    "summary": "这条路具体是什么（80字内）",
    "why_it_works": "为什么它适合当前局面（60字内）",
    "first_step": "现在就能做的第一步（40字内）",
    "when_not_to_use": "什么情况下不要用这条路（40字内）"
  }
}

只输出 JSON。"""


# ============================================================
# C1 System Prompt - 认知力场再评估
# ============================================================
C1_SYSTEM = """你是一位"认知力场再评估专家"。

给定：
1. 用户的原始问题
2. 用户已经知道的信息和补充的关键信息
3. 新补上的认知框架、经验参照、情绪镜像
4. 第一幕留下来的原始力量对比（可能平衡，也可能已经轻度偏向一边）
5. 用户当前最看重的价值排序
6. 用户可能落入的决策心理学偏差

请重新评估力量分布，给出：

1. 更新后的正方/反方力量对比（0-100）
2. 力量变化的原因
3. 一个具体的行动建议
4. 一个具体的下一步行动

力量评估标准：
- 70+：强烈倾向
- 55-69：轻度倾向
- 45-54：接近平衡
- 30-44：轻度反对
- <30：强烈反对

非常重要：
- 不要因为原始分数看起来接近，就机械复制原始数值。
- 不要默认输出 50:50。
- 只有当你明确判断：补充后的信息、框架、经验和情绪镜像仍然让两边保持结构性对称，才输出 50:50。
- 如果证据还不够、但又看不出绝对平衡，请给一个“轻微但暂定”的力量差，比如 52:48、54:46，并在 recommendation / reasoning 里说明这是暂时结论，不是终局判决。
- recommendation 必须明确写出：倾向支持 / 倾向反对 / 仍需更多信息 / 结构性平衡 之一。
- 请识别用户当前可能陷入的决策心理学偏差（framing_effect / loss_aversion / sunk_cost / regret_theory 等），并在输出中给出1-2句针对性提醒。

请以JSON格式输出：
{
  "updated_pro_total": 65,
  "updated_con_total": 58,
  "balance_shift": "力量变化的原因说明（100字内）",
  "recommendation": "建议方向：推荐/倾向反对/仍需更多信息",
  "action_plan": "具体的第一步行动（30字内）",
  "reasoning": "完整的推理过程（200字内）",
  "decision_biases": [{"key": "regret_theory", "label": "后悔预期", "hint": "它会让你..." }],
  "bias_reminder": "1-2句偏差提醒（60字内）"
}

只输出JSON，不要输出其他内容。"""


# ============================================================
# Agent 运行函数
# ============================================================

def run_b1_diagnosis(question: str, *, max_tokens: int = 2048) -> list[DiagnosisQuestion]:
    """
    运行 B1 卡点诊断 Agent
    返回诊断问题列表
    """
    user_msg = f"""请诊断以下决策困境中用户卡在哪个环节：

用户原始问题：
{question}

{_build_b1_prompt_context(question)}

请给出3-5个精准的追问。"""

    try:
        data = call_agent_json(
            B1_SYSTEM,
            user_msg,
            max_tokens=max_tokens,
            timeout_seconds=_adaptive_timeout(max_tokens, floor=16, ceiling=40, ratio=180),
        )
    except Exception:
        data = {}

    questions = []
    for q_data in data.get("diagnosis_questions", []) if isinstance(data, dict) else []:
        if not isinstance(q_data, dict):
            continue
        question_text = str(q_data.get("question_text", "") or "").strip()
        if not question_text:
            continue
        options = q_data.get("options", [])
        if not isinstance(options, list):
            options = []
        questions.append(DiagnosisQuestion(
            id=str(q_data.get("id", f"b1q{len(questions)+1}") or f"b1q{len(questions)+1}"),
            question_text=question_text,
            options=[str(option or "").strip() for option in options if str(option or "").strip()],
        ))

    if len(questions) < 3:
        return _fallback_b1_questions(question)
    return questions[:5]


def infer_blockages_from_answers(answers: dict, questions: list[DiagnosisQuestion]) -> list[str]:
    """
    根据用户回答推断卡点类型
    用轻量规则做首轮筛分，避免把所有案例都默认归类为信息黑洞。
    """
    scores = {
        BlockageType.A_INFO_VOID.value: 0,
        BlockageType.B_COGNITIVE_NARROW.value: 0,
        BlockageType.C_EXPERIENCE_BLANK.value: 0,
        BlockageType.D_EMOTIONAL_INTERFERENCE.value: 0,
    }

    question_lookup = {q.id: q for q in questions}

    for question_id, raw_answer in answers.items():
        answer = _normalize_text(raw_answer)
        if not answer:
            continue

        question = question_lookup.get(question_id)
        signal_type = _question_signal_type(question.question_text if question else "")
        if signal_type and _indicates_already_covered(answer):
            scores[signal_type] -= 1
        elif signal_type and not _contains_any(answer, ["没有", "都了解", "很清楚", "有人", "不担心"]):
            scores[signal_type] += 2
        elif signal_type and _is_negative_or_missing(answer):
            scores[signal_type] += 1

        for blockage, keywords in BLOCKAGE_SIGNAL_KEYWORDS.items():
            if blockage == signal_type and _indicates_already_covered(answer):
                continue
            match_count = sum(1 for keyword in keywords if keyword in answer)
            scores[blockage] += match_count

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    primary_blockage, primary_score = ordered[0]
    if primary_score <= 0:
        return [BlockageType.A_INFO_VOID.value]

    selected = [primary_blockage]
    if len(ordered) > 1:
        secondary_blockage, secondary_score = ordered[1]
        if secondary_score > 0 and secondary_score >= primary_score - 2:
            selected.append(secondary_blockage)

    return selected


def run_b2_info_gathering(
    question: str,
    blockages: list[str],
    answers: dict[str, str],
    external_signals: Optional[list[dict]] = None,
    *,
    max_tokens: int = 3072,
) -> list[dict]:
    """
    运行 B2 信息侦探 Agent
    返回遗漏信息列表
    """
    blockage_str = ", ".join(blockages) if blockages else "信息黑洞"
    answers_str = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())

    user_msg = f"""原始问题：{question}

用户诊断结果：{blockage_str}

用户对诊断问题的回答：
{answers_str}

近期外部市场声音：
{_build_external_signals_text(external_signals)}

请找出用户遗漏的关键信息。如果用户的主要问题不是信息缺失，请返回空的 missing_info 数组。"""

    try:
        data = call_agent_json(B2_SYSTEM, user_msg, max_tokens=max_tokens)
    except Exception:
        data = {}

    missing_info = _normalize_missing_info_items(data.get("missing_info", []) if isinstance(data, dict) else [])
    if missing_info:
        return missing_info
    return _infer_missing_info_items(question, answers)


def run_b3_cognitive_unlock(
    question: str,
    blockages: list[str],
    answers: dict[str, str],
    missing_info: list[dict],
    value_profile: Optional[dict] = None,
    *,
    max_tokens: int = 3072,
) -> list[dict]:
    """
    运行 B3 认知解锁 Agent
    返回认知框架列表
    """
    blockage_str = ", ".join(blockages) if blockages else "未明确"
    answers_str = "\n".join(f"{qid}: {ans}" for qid, ans in answers.items()) or "（暂无）"
    info_text = "\n".join(
        f"- {item.get('title', '')}: {item.get('content', '')}"
        for item in missing_info
    ) or "（暂无补充信息）"

    user_msg = f"""原始问题：{question}

诊断结果：{blockage_str}

用户回答：
{answers_str}

已补充的关键信息：
{info_text}

用户当前价值排序：
{_build_value_profile_text(value_profile)}

可参考的决策心理学偏差：
{_build_bias_reference()}

请提供最能帮助用户做判断的认知框架。如果主要不是认知框架问题，请返回空数组。"""

    try:
        data = call_agent_json(B3_SYSTEM, user_msg, max_tokens=max_tokens)
    except Exception:
        data = {}

    frames = _normalize_cognitive_frames(data.get("cognitive_frames", []) if isinstance(data, dict) else [])
    inferred_biases = infer_decision_biases(question, answers, blockages)
    default_bias_alert = _build_bias_reminder(inferred_biases)
    frames = [
        {
            **frame,
            "bias_alert": frame.get("bias_alert") or default_bias_alert,
        }
        for frame in frames
    ]
    if frames:
        return frames
    return _infer_cognitive_frames(question)


def _score_clp_relevance(clp: dict, target_text: str) -> float:
    """计算星图点与当前问题的相关度权重（关键词重合度）。"""
    text = str(clp.get("question_text") or "").lower()
    target = str(target_text or "").lower()
    
    # 提取有意义的词（简单按长度过滤，后续可扩充停用词列表）
    keywords = [w for w in re.findall(r"[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}", target)]
    if not keywords:
        return 0.0
        
    score = 0.0
    for kw in keywords:
        if kw in text:
            score += 1.0
            
    # 如果断层线重合，加权
    fault_lines = " ".join(clp.get("fault_lines", [])).lower()
    for kw in keywords:
        if kw in fault_lines:
            score += 0.5
            
    return score


def run_b4_experience_simulation(
    question: str,
    blockages: list[str],
    answers: dict[str, str],
    missing_info: list[dict],
    cognitive_frames: list[dict],
    *,
    max_tokens: int = 4096,
    experience_limit: int = 3,
) -> list[dict]:
    """
    运行 B4 经验模拟 Agent
    返回经验案例列表 (融合 RAG 逻辑)
    """
    blockage_str = ", ".join(blockages) if blockages else "未明确"
    answers_str = "\n".join(f"{qid}: {ans}" for qid, ans in answers.items()) or "（暂无）"
    info_text = "\n".join(
        f"- {item.get('title', '')}: {item.get('content', '')}"
        for item in missing_info
    ) or "（暂无补充信息）"
    frame_text = "\n".join(
        f"- {item.get('title', '')}: {item.get('core_insight', '')}"
        for item in cognitive_frames
    ) or "（暂无认知框架）"

    # --- RAG 2.0 (Similarity-based) ---
    real_nodes = db_get_all_confirmed_clps()
    context_stars = ""
    if real_nodes:
        # 按照相关度排序
        scored_nodes = []
        for node in real_nodes:
            score = _score_clp_relevance(node, question)
            scored_nodes.append((score, node))
            
        # 按分数降序排列，取前 6 个
        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        top_nodes = [n for score, n in scored_nodes[:6]]
        
        for node in top_nodes:
            context_stars += f"--- 星图真实点 #{node.get('id')} (评分:{_score_clp_relevance(node, question)}) ---\n"
            context_stars += f"问题：{node.get('question_text')}\n"
            context_stars += f"稳定性：{node.get('stability_type')}\n"
            context_stars += f"断层线：{', '.join(node.get('fault_lines', []))}\n\n"

    rag_instruction = ""
    if context_stars:
        rag_instruction = f"以下是 Engine A 到目前为止挖掘出的真实星图节点数据（已按相关度排序），请优先从中挑选相近的案例进行分析和关联：\n\n{context_stars}\n"

    user_msg = f"""原始问题：{question}

诊断结果：{blockage_str}

用户回答：
{answers_str}

已补充信息：
{info_text}

当前认知框架：
{frame_text}

{rag_instruction}

请生成 3 个经验对照案例。如果是基于星图真实点生成的，请在 title 中注明。如果主要不是经验盲区，请返回空数组。"""

    try:
        data = call_agent_json(B4_SYSTEM, user_msg, max_tokens=max_tokens)
    except Exception:
        data = {}

    cases = _normalize_experience_cases(data.get("experience_cases", []) if isinstance(data, dict) else [])
    if cases:
        return cases[:max(1, int(experience_limit or 3))]
    return _infer_experience_cases(question)[:max(1, int(experience_limit or 3))]


def run_b5_emotional_mirror(
    question: str,
    blockages: list[str],
    answers: dict[str, str],
    value_profile: Optional[dict] = None,
    *,
    max_tokens: int = 2048,
) -> dict:
    """
    运行 B5 情绪镜像 Agent
    返回情绪洞察
    """
    blockage_str = ", ".join(blockages) if blockages else "未明确"
    answers_str = "\n".join(f"{qid}: {ans}" for qid, ans in answers.items()) or "（暂无）"

    user_msg = f"""原始问题：{question}

诊断结果：{blockage_str}

用户回答：
{answers_str}

用户当前价值排序：
{_build_value_profile_text(value_profile)}

可参考的决策心理学偏差：
{_build_bias_reference()}

请识别情绪如何影响这个决策。如果主要不是情绪问题，请返回空对象。"""

    try:
        data = call_agent_json(B5_SYSTEM, user_msg, max_tokens=max_tokens)
    except Exception:
        data = {}

    insight = _normalize_emotional_insight(data.get("emotional_insight", {}) if isinstance(data, dict) else {})
    inferred_biases = infer_decision_biases(question, answers, blockages)
    if insight:
        insight["decision_biases"] = _merge_bias_entries(insight.get("decision_biases", []), inferred_biases)
        insight["bias_reminder"] = insight.get("bias_reminder") or _build_bias_reminder(insight["decision_biases"])
    if insight:
        return insight
    fallback = _infer_emotional_insight(question, answers, blockages)
    if fallback:
        fallback["decision_biases"] = inferred_biases
        fallback["bias_reminder"] = _build_bias_reminder(inferred_biases)
    return fallback


def run_b5_5_alternative_path(
    question: str,
    answers: dict[str, str],
    value_profile: Optional[dict] = None,
    recommendation_hint: str = "",
    *,
    max_tokens: int = 1800,
) -> dict:
    user_msg = f"""原始问题：{question}

用户回答：
{chr(10).join(f"{qid}: {ans}" for qid, ans in answers.items()) or "（暂无）"}

用户当前价值排序：
{_build_value_profile_text(value_profile)}

当前建议方向：
{recommendation_hint or "尚未形成明确建议"}

请提出一个既不是 A 也不是 B 的第三条路。"""
    try:
        data = call_agent_json(B5_5_SYSTEM, user_msg, max_tokens=max_tokens)
    except Exception:
        data = {}

    alternative = _normalize_alternative_path(data.get("alternative_path", {}) if isinstance(data, dict) else {})
    if alternative:
        return alternative

    top_values = value_profile.get("top_values", []) if isinstance(value_profile, dict) else []
    top_label = top_values[0].get("label") if top_values and isinstance(top_values[0], dict) else "当前最重要的东西"
    return {
        "title": "先做低成本试验",
        "summary": "先别急着把自己锁死在 A 或 B，上一个更小、更可逆的试验版本。",
        "why_it_works": f"这样能先守住「{top_label}」，同时把最影响判断的不确定因素跑出来。",
        "first_step": "把未来两周内能完成的最小验证动作写成清单。",
        "when_not_to_use": "如果这件事本身已经不可逆，或者窗口极短，就不要再假装还有无限试错空间。",
    }


def run_c1_reevaluation(
    question: str,
    original_pro: int,
    original_con: int,
    filled_info: list[dict],
    cognitive_frames: Optional[list[dict]] = None,
    experience_cases: Optional[list[dict]] = None,
    emotional_insight: Optional[dict] = None,
    source_detection: Optional[dict] = None,
    diagnosed_blockages: Optional[list[str]] = None,
    value_profile: Optional[dict] = None,
    decision_biases: Optional[list[dict]] = None,
    external_signals: Optional[list[dict]] = None,
    *,
    max_tokens: int = 2048,
) -> dict:
    """
    运行 C1 重新评估 Agent
    返回更新后的力量对比和建议
    """
    # 构建补充信息文本
    info_text = ""
    if filled_info:
        for item in filled_info:
            info_text += f"- 【{item.get('title', '')}】{item.get('content', '')}\n"
    else:
        info_text = "（暂无补充信息）"

    frame_text = ""
    if cognitive_frames:
        for item in cognitive_frames:
            frame_text += (
                f"- 【{item.get('title', '')}】"
                f"{item.get('core_insight', '')} / {item.get('try_now', '')}\n"
            )
    else:
        frame_text = "（暂无新增认知框架）"

    experience_text = ""
    if experience_cases:
        for item in experience_cases:
            experience_text += (
                f"- 【{item.get('title', '')}】"
                f"{item.get('choice_made', '')}，结果：{item.get('outcome', '')}，"
                f"提醒：{item.get('lesson', '')}\n"
            )
    else:
        experience_text = "（暂无经验参照）"

    emotional_text = ""
    if emotional_insight:
        emotions = emotional_insight.get("dominant_emotions", [])
        emotion_list = "、".join(
            f"{item.get('emotion', '')}({item.get('intensity', '')})"
            for item in emotions
            if item.get("emotion")
        ) or "未识别"
        emotional_text = (
            f"主要情绪：{emotion_list}\n"
            f"隐藏需求：{emotional_insight.get('hidden_need', '')}\n"
            f"判断偏差：{emotional_insight.get('decision_distortion', '')}\n"
            f"稳定提醒：{emotional_insight.get('grounding_prompt', '')}\n"
        )
    else:
        emotional_text = "（暂无情绪镜像）"

    user_msg = f"""原始问题：{question}

原始力量对比（上一幕留下来的起点，不代表最终结论）：
正方总分：{original_pro}
反方总分：{original_con}

补充的关键信息：
{info_text}

新增认知框架：
{frame_text}

经验参照：
{experience_text}

情绪镜像：
{emotional_text}

用户价值排序：
{_build_value_profile_text(value_profile)}

当前可能的决策偏差：
{_build_bias_text(decision_biases)}

近期外部市场声音：
{_build_external_signals_text(external_signals)}

请重新评估并给出建议。"""

    def _derive_fallback_balance() -> tuple[int, int]:
        if original_pro != original_con:
            return (
                max(0, min(100, int(original_pro))),
                max(0, min(100, int(original_con))),
            )

        blockages = diagnosed_blockages or []
        source_result = source_detection.get("result", {}) if isinstance(source_detection, dict) else {}
        analysis = source_detection.get("analysis", {}) if isinstance(source_detection, dict) else {}
        classes = analysis.get("classifications", {}) if isinstance(analysis, dict) else {}
        failed_at = str(source_result.get("failed_at", "") or "").strip()

        gap = 4
        if "D" in blockages:
            gap = 10
        elif "A" in blockages or failed_at == "filter1":
            gap = 8
        elif "B" in blockages or failed_at == "filter2":
            gap = 6
        elif "C" in blockages or failed_at == "filter3":
            gap = 5

        def _safe_int(value: object) -> int:
            try:
                return int(round(float(value)))
            except (TypeError, ValueError):
                return 0

        info_gap_score = _safe_int(classes.get("info_gap", 0))
        dilemma_score = _safe_int(classes.get("dilemma", 0))
        clp_score = _safe_int(classes.get("clp", 0))
        if clp_score >= max(info_gap_score, dilemma_score) and clp_score >= 45:
            gap = min(gap, 4)
        elif max(info_gap_score, dilemma_score) >= 55:
            gap = max(gap, 8)

        pro = min(100, 50 + (gap // 2) + (gap % 2))
        con = max(0, 50 - (gap // 2))
        return pro, con

    try:
        result = call_agent_json(C1_SYSTEM, user_msg, max_tokens=max_tokens)
    except Exception:
        result = {}

    fallback_pro, fallback_con = _derive_fallback_balance()

    def _normalize_score(value: object, fallback: int) -> int:
        try:
            return max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return fallback

    normalized = {
        "updated_pro_total": _normalize_score(result.get("updated_pro_total"), fallback_pro),
        "updated_con_total": _normalize_score(result.get("updated_con_total"), fallback_con),
        "balance_shift": str(result.get("balance_shift", "") or "").strip(),
        "recommendation": str(result.get("recommendation", "") or "").strip(),
        "action_plan": str(result.get("action_plan", "") or "").strip(),
        "reasoning": str(result.get("reasoning", "") or "").strip(),
        "decision_biases": _merge_bias_entries(
            result.get("decision_biases", []),
            decision_biases,
            emotional_insight.get("decision_biases", []) if isinstance(emotional_insight, dict) else [],
            infer_decision_biases(question, {}, diagnosed_blockages, recommendation=str(result.get("recommendation", "") or "")),
        ),
        "bias_reminder": _sanitize_generated_text(result.get("bias_reminder"), default=""),
    }

    def _build_generic_action(text: str) -> str:
        raw = str(text or "").strip(" ，。？?")
        if "会员" in raw:
            return "先列30天真实使用场景、预算上限和免费替代方案"
        if "还是" in raw:
            return "把两个选项的最坏代价、可逆性和一个月试错成本并排写出来"
        if "要不要" in raw or "该不该" in raw:
            return "先写下决定这件事的三个关键条件，再补最影响结果的那个"
        return "先把最影响结果的三个条件写出来，再补最关键的一条"

    def _build_c1_fallback() -> dict:
        source_result = source_detection.get("result", {}) if isinstance(source_detection, dict) else {}
        source_filters = source_detection.get("filters", {}) if isinstance(source_detection, dict) else {}
        filter2 = source_filters.get("filter2", {}) if isinstance(source_filters, dict) else {}
        failed_at = str(source_result.get("failed_at", "") or "").strip()
        blockages = diagnosed_blockages or []
        info_gap_like = "A" in blockages or failed_at == "filter1"
        filter2_broken = (
            failed_at == "filter2"
            and str(filter2.get("distribution", "") or "").strip() == "0:0"
        )

        if info_gap_like:
            recommendation = "仍需更多信息"
            action_plan = _build_generic_action(question)
            reasoning = (
                "这次重评没有形成可靠的偏向。当前显示的 50:50 只代表还没拉开有效力矩，"
                "不代表这个问题天然完全平衡。先补关键事实，再决定。"
            )
            balance_shift = "目前新增信息还不够，力量没有被有效拉开。"
        elif filter2_broken:
            recommendation = "先不要把它当成 50:50 的无解题"
            action_plan = _build_generic_action(question)
            reasoning = (
                "第一幕的多框架结果本轮没有形成可用力矩，所以第二幕暂时拿不到稳定方向。"
                "眼下的 50:50 更像检测链路缺少有效框架权重，不是你这个问题真的永远平衡。"
            )
            balance_shift = "当前多框架权重缺失，暂时无法把倾向稳定压出来。"
        else:
            recommendation = "先做一个小范围验证"
            action_plan = _build_generic_action(question)
            reasoning = (
                "这次重评内容不足，暂时不适合把数字当成结论。与其继续脑内拉扯，"
                "更适合先做一个低成本验证动作，再用真实反馈更新判断。"
            )
            balance_shift = "这轮补充还不足以形成新的稳定结论。"

        return {
            "updated_pro_total": fallback_pro,
            "updated_con_total": fallback_con,
            "balance_shift": balance_shift,
            "recommendation": recommendation,
            "action_plan": action_plan,
            "reasoning": reasoning,
            "decision_biases": _normalize_bias_entries(decision_biases or infer_decision_biases(question, {}, diagnosed_blockages)),
            "bias_reminder": _build_bias_reminder(decision_biases or infer_decision_biases(question, {}, diagnosed_blockages)),
            "fallback_mode": "c1_placeholder",
            "skip_recheck": True,
        }

    is_meaningless = (
        normalized["updated_pro_total"] == fallback_pro
        and normalized["updated_con_total"] == fallback_con
        and not normalized["recommendation"]
        and not normalized["action_plan"]
        and not normalized["reasoning"]
        and not normalized["balance_shift"]
    )
    if is_meaningless:
        return _build_c1_fallback()

    if (
        normalized["updated_pro_total"] == normalized["updated_con_total"]
        and fallback_pro != fallback_con
        and (
            not normalized["balance_shift"]
            or not normalized["reasoning"]
            or "仍需更多信息" in normalized["recommendation"]
        )
    ):
        normalized["updated_pro_total"] = fallback_pro
        normalized["updated_con_total"] = fallback_con

    if (
        not normalized["recommendation"]
        and abs(normalized["updated_pro_total"] - normalized["updated_con_total"]) >= 12
    ):
        normalized["recommendation"] = (
            "倾向支持"
            if normalized["updated_pro_total"] > normalized["updated_con_total"]
            else "倾向反对"
        )
    if not normalized["action_plan"]:
        normalized["action_plan"] = _build_generic_action(question)
    if not normalized["reasoning"]:
        normalized["reasoning"] = (
            normalized["balance_shift"]
            or "这轮重评已经形成初步倾向，建议先做一个低成本验证动作。"
        )
    if not normalized["bias_reminder"]:
        normalized["bias_reminder"] = _build_bias_reminder(normalized["decision_biases"])
    return normalized


# ============================================================
# B6 System Prompt - 模拟参数收集
# ============================================================
B6_SYSTEM = """你是一位未来模拟器的数据采集员。用户即将做一个重大选择，你需要快速收集2-3个关键参数来让模拟更准确。

必须收集的参数：
1. 用户当前的"安全垫"有多厚？（存款能撑几个月？有无其他收入？有无硬性支出？）
2. 用户的"可逆性窗口"有多大？（如果选错了最快多久能回头？回头的代价是什么？）
3. 用户最怕的"最坏情况"是什么？（不要猜，直接问）

要求：
- 生成 3-5 个精准问题，优先选择题
- 问题必须贴着用户场景，不要使用抽象模板
- 必须覆盖安全垫、固定支出、回头时间、回头代价、最坏情况
- 不要把用户已经在原题里说清楚的内容再问一遍
- 问法要像高质量咨询，不要像表单堆字段

请以JSON格式输出：
{
  "param_questions": [
    {
      "id": "b6q1",
      "field_name": "savings_months/fixed_expenses/time_to_reverse/reversal_cost/worst_fear 之一",
      "question_text": "你的问题",
      "options": ["选项1", "选项2", "选项3"],
      "type": "choice|open"
    }
  ]
}

只输出JSON。"""


# ============================================================
# B7 System Prompt - 时间线生成
# ============================================================
B7_SYSTEM = """你是一位人生轨迹模拟器。根据用户的具体情况和选择，模拟三条可能的未来时间线。

用户情况会在用户消息里提供。
用户的选择会在用户消息里提供。
用户消息里还会提供：
- 当前选项的语义槽位（例如主动推进 / 保留观察）
- 对照选项
- 必须遵守 / 明确避免 的差异化要求

请生成三条时间线：

时间线1：顺风局（概率约25-35%）
  - 一切比预期更顺利，但不要"开挂式成功"
  - 要有小波折但总体向上

时间线2：平稳局（概率约40-55%）
  - 最可能发生的情况
  - 不特别好也不特别坏
  - 这条线要最详细

时间线3：逆风局（概率约15-25%）
  - 遇到比较大的困难
  - 但不是"世界末日"
  - 必须包含用户说的"最怕的情况"

每条时间线需要6个节点：
- 第1周：刚做完选择的状态和感受
- 第1个月：初步影响开始显现
- 第3个月：第一个重要验证节点（设置检查站和信号灯）
- 第6个月：第二个重要验证节点（要不要调整方向）
- 1年后：中期结果
- 3年后：长期结果

每个节点必须包含：
- external_state：外部客观变化
- inner_feeling：内心感受（要真实具体，不要空洞）
- key_action：这个节点该做什么
- signal：什么迹象说明你在这条线上

压缩要求：
- 每个字段尽量 18-30 字
- 直接写结论，不要铺垫
- 不要写任何额外解释
- 只保留对决策真正有用的信息

概率分配要求：
- 三条线概率之和 = 100%
- 概率要附带一句话解释

请以JSON格式输出：
{
  "choice_name": "选项描述",
  "probability_distribution": {
    "tailwind": {"percent": 30, "reason": "为什么给这个概率"},
    "steady": {"percent": 50, "reason": "为什么给这个概率"},
    "headwind": {"percent": 20, "reason": "为什么给这个概率"}
  },
  "timelines": {
    "tailwind": {
      "title": "顺风局：比预期更顺利",
      "nodes": [
        {"time": "第1周", "external_state": "...", "inner_feeling": "...", "key_action": "...", "signal": "..."}
      ]
    },
    "steady": {...},
    "headwind": {...}
  }
}

只输出JSON。"""


# ============================================================
# B8 System Prompt - 应对预案Agent
# ============================================================
B8_SYSTEM = """你是一位应急预案设计师。基于模拟出的时间线，为用户设计"未来的自己该怎么办"的预案。

你的任务：

1. 识别所有时间线中的"关键岔路口"
   即：用户在未来某个时刻需要做出新决策的节点

2. 为每个岔路口设计"如果-那么"预案
   - 如果看到绿/黄/红信号，分别该怎么行动

3. 为逆风局的最坏节点设计"生存方案"
   - 如果最怕的事真的发生了，具体该怎么办

4. 设计"里程碑检查系统"
   - 在未来12个月的哪些时间点做自检

压缩要求：
- 每个 signal 和 action 尽量 12-24 字
- 每个 check 尽量一句话
- 只保留最关键的 2-4 个岔路口

请以JSON格式输出：
{
  "crossroads": [
    {
      "id": 1,
      "time": "入职第3个月",
      "description": "第一个重要验证节点",
      "signals": {
        "green": {"signal": "团队在扩招", "action": "加大投入"},
        "yellow": {"signal": "人员不变", "action": "稳步推进"},
        "red": {"signal": "冻结招聘", "action": "立刻更新简历"}
      },
      "reversal_cost": "此时回头的代价"
    }
  ],
  "worst_case_survival_plan": {
    "trigger": "最怕的情况",
    "day_1": "第1天做什么",
    "week_1": "第1周做什么",
    "month_1": "第1个月做什么",
    "safety_runway": "安全垫能撑多久",
    "emotional_note": "情绪上的预期"
  },
  "milestone_check_system": [
    {"time": "1个月", "check": "检查什么"},
    {"time": "3个月", "check": "检查什么"},
    {"time": "6个月", "check": "检查什么"},
    {"time": "12个月", "check": "检查什么"}
  ]
}

只输出JSON。"""


# ============================================================
# B9 System Prompt - 对比总览Agent
# ============================================================
B9_SYSTEM = """你是最终的决策可视化师。用户面前有两个选择，每个选择都有三条模拟时间线和应对预案。你的任务是生成一张清晰的"对比总览"。

请生成：
1. 选项A vs 选项B 全景对比表
2. 两个选择的行动地图
3. 结合后悔风险、价值排序和心理偏差给出最终结论
4. 如果前面已经提供了第三条路，请把它作为补充策略写进结果

行动地图格式：
今天 → 本周 → 第1个月 → 第3个月(检查站) → 第6个月(检查站) → 第12个月

最后一句话要根据模拟结果个性化：
- 分析两个选择的本质区别
- 指出用户更怕短期的痛还是长期的遗憾

压缩要求：
- comparison_summary 控制在 180 字内
- final_insight 控制在 40 字内
- 行动地图每一项尽量一句话
- 请识别用户当前可能陷入的决策心理学偏差（framing_effect / loss_aversion / sunk_cost / regret_theory 等），并在输出中给出1-2句针对性提醒。

请以JSON格式输出：
{
  "comparison_summary": "对比总览文本（Markdown格式）",
  "action_map_a": ["今天：...", "本周：...", "第1个月：...", "第3个月★检查站：...", "第6个月★检查站：...", "第12个月：回顾"],
  "action_map_b": ["同上格式"],
  "final_insight": "最后一句个性化总结（50字内）",
  "regret_score_a": 42,
  "regret_score_b": 57,
  "probability_optimistic": 28,
  "probability_baseline": 49,
  "probability_pessimistic": 23,
  "decision_biases": [{"key": "loss_aversion", "label": "损失厌恶", "hint": "它会让你..." }],
  "bias_reminder": "1-2句偏差提醒（60字内）"
}

只输出JSON。"""


# ============================================================
# B6-B9 Agent 运行函数
# ============================================================

def run_b6_sim_params(question: str = "", recommendation: str = "", *, max_tokens: int = 1024) -> list[dict]:
    """
    运行 B6 模拟参数收集 Agent
    返回参数收集问题列表
    """
    user_msg = f"""用户即将做一个重大选择，需要收集关键参数来让模拟更准确。

原始问题：{question or "未提供"}
当前建议：{recommendation or "未提供"}

{_build_b6_prompt_context(question, recommendation)}

请基于这个具体问题生成 3-5 个最关键的参数收集问题。"""
    try:
        data = call_agent_json(
            B6_SYSTEM,
            user_msg,
            max_tokens=max_tokens,
            timeout_seconds=_adaptive_timeout(max_tokens, floor=16, ceiling=42, ratio=160),
        )
    except Exception:
        data = {}

    questions = _normalize_sim_questions(data.get("param_questions", []) if isinstance(data, dict) else [])
    if not questions:
        questions = _fallback_sim_questions(question, recommendation)
    return ensure_sim_question_coverage(questions, question_context=question)


def parse_sim_params_from_answers(
    answers: dict[str, str],
    sim_questions: Optional[list[dict]] = None,
    original_question: str = "",
) -> dict:
    """
    从用户回答中解析模拟参数
    优先结合问题文本做字段映射，避免依赖固定 question id。
    """
    parsed = {
        "savings_months": None,
        "other_income": None,
        "fixed_expenses": None,
        "time_to_reverse": None,
        "reversal_cost": None,
        "point_of_no_return": None,
        "worst_fear": None,
        "question_context": original_question or "",
    }

    question_lookup = {
        str(item.get("id", "")): item
        for item in (sim_questions or [])
        if isinstance(item, dict)
    }

    for question_id, answer in answers.items():
        answer_text = _sanitize_generated_text(answer, default="")
        if not answer_text:
            continue

        question_meta = question_lookup.get(question_id, {}) if isinstance(question_lookup.get(question_id, {}), dict) else {}
        question_text = str(question_meta.get("question_text", ""))
        field_name = str(question_meta.get("field_name", "") or "").strip() or _classify_sim_param_question(question_text)

        if field_name == "savings_months":
            months = _extract_months(answer_text)
            if months is not None:
                parsed["savings_months"] = months
        elif field_name in parsed:
            parsed[field_name] = answer_text

        if parsed["savings_months"] is None:
            months = _extract_months(answer_text)
            if months is not None:
                parsed["savings_months"] = months

        if parsed["worst_fear"] is None and _contains_any(answer_text, ["最怕", "担心", "害怕", "失败", "后悔"]):
            parsed["worst_fear"] = answer_text

    return parsed


def extract_choice_options(
    original_question: str,
    recommendation: str = "",
    action_plan: str = "",
    *,
    max_tokens: int = 900,
) -> list[dict]:
    """
    提炼模拟器需要比较的两个真实选项，避免退化成“推荐/备选”这类空标签。
    """
    user_msg = f"""原始问题：{original_question}

当前建议：{recommendation or "未提供"}
行动方案：{action_plan or "未提供"}

请提炼用户真正面临的两个选择。"""

    try:
        data = call_agent_json(
            CHOICE_EXTRACTION_SYSTEM,
            user_msg,
            max_tokens=max_tokens,
            timeout_seconds=_adaptive_timeout(max_tokens, floor=14, ceiling=30, ratio=200),
        )
    except Exception:
        data = {}
    choices = data.get("choices", []) if isinstance(data, dict) else []
    normalized = []
    for item in choices[:2]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if name and description:
            normalized.append({"name": name, "description": description})

    if len(normalized) >= 2:
        return normalized[:2]
    return _fallback_choice_options(original_question, recommendation, action_plan)


def run_b7_timeline(
    user_context: str,
    choice_name: str,
    choice_description: str,
    user_params: dict,
    *,
    max_tokens: int = 2600,
    temperature: float = 0.2,
    slot_index: int = 0,
    contrast_choice: Optional[dict] = None,
    regenerate_hint: str = "",
) -> dict:
    """
    运行 B7 时间线生成 Agent
    返回三条时间线
    """
    slot = _build_choice_semantic_slot(choice_name, choice_description, slot_index=slot_index)
    contrast_choice = contrast_choice if isinstance(contrast_choice, dict) else {}
    contrast_name = _sanitize_generated_text(contrast_choice.get("name"), default="")
    contrast_description = _sanitize_generated_text(contrast_choice.get("description"), default="")

    param_lines = []
    if user_params.get("savings_months") is not None:
        param_lines.append(f"安全垫：约 {user_params.get('savings_months')} 个月")
    if not _is_sim_placeholder(user_params.get("other_income")):
        param_lines.append(f"其他收入：{_sanitize_generated_text(user_params.get('other_income'))}")
    if not _is_sim_placeholder(user_params.get("fixed_expenses")):
        param_lines.append(f"固定支出：{_sanitize_generated_text(user_params.get('fixed_expenses'))}")
    if not _is_sim_placeholder(user_params.get("time_to_reverse")):
        param_lines.append(f"回头时间：{_sanitize_generated_text(user_params.get('time_to_reverse'))}")
    if not _is_sim_placeholder(user_params.get("reversal_cost")):
        param_lines.append(f"回头代价：{_sanitize_generated_text(user_params.get('reversal_cost'))}")
    if not _is_sim_placeholder(user_params.get("worst_fear")):
        param_lines.append(f"最怕的情况：{_sanitize_generated_text(user_params.get('worst_fear'))}")
    param_block = "\n".join(param_lines) if param_lines else "关键参数已由上游整理，请按已有信息推演。"

    must_rules = "\n".join(f"- {rule}" for rule in slot["must"])
    avoid_rules = "\n".join(f"- {rule}" for rule in slot["must_not"])
    contrast_block = ""
    if contrast_name or contrast_description:
        contrast_block = f"\n对照选项：{contrast_name or '另一条路'}\n对照选项描述：{contrast_description or '见上下文'}\n"

    hint_block = f"\n额外纠偏要求：{regenerate_hint}\n" if regenerate_hint else ""

    user_msg = f"""用户情况：{user_context}

当前选项名称：{choice_name}
当前选项描述：{choice_description}
当前选项语义槽位：{slot['label']}
{contrast_block}
关键参数：
{param_block}

必须遵守：
{must_rules}

明确避免：
{avoid_rules}
{hint_block}
请生成三条时间线。"""
    try:
        data = call_agent_json(
            B7_SYSTEM,
            user_msg,
            max_tokens=max_tokens,
            temperature=temperature,
            retries=0,
            allow_downgrade=False,
            timeout_seconds=_adaptive_timeout(max_tokens, floor=25, ceiling=60, ratio=180),
        )
        return _normalize_b7_timeline_output(data, choice_name, choice_description)
    except Exception:
        return _build_b7_timeline_fallback(choice_name, choice_description, user_params)


def build_distinct_timeline_fallback(choice_name: str, choice_description: str, user_params: dict) -> dict:
    return _build_b7_timeline_fallback(choice_name, choice_description, user_params)


def run_b8_coping_plan(
    choice_a_timelines: dict,
    choice_b_timelines: dict,
    user_params: dict,
    *,
    max_tokens: int = 1800,
) -> dict:
    """
    运行 B8 应对预案 Agent
    返回关键岔路口和生存方案
    """
    user_msg = f"""用户的安全垫：存款{user_params.get('savings_months', '未知')}个月
用户最怕的情况：{user_params.get('worst_fear', '未知')}

选项A的时间线：{choice_a_timelines}
选项B的时间线：{choice_b_timelines}

请生成应对预案。"""
    try:
        data = call_agent_json(
            B8_SYSTEM,
            user_msg,
            max_tokens=max_tokens,
            temperature=0.2,
            retries=0,
            allow_downgrade=False,
            timeout_seconds=_adaptive_timeout(max_tokens, floor=20, ceiling=48, ratio=180),
        )
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return _build_b8_fallback(choice_a_timelines, choice_b_timelines, user_params)


def run_b9_comparison(
    choice_a_sim: dict,
    choice_b_sim: dict,
    user_params: dict,
    *,
    value_profile: Optional[dict] = None,
    decision_biases: Optional[list[dict]] = None,
    alternative_path: Optional[dict] = None,
    external_signals: Optional[list[dict]] = None,
    max_tokens: int = 1600,
) -> dict:
    """
    运行 B9 对比总览 Agent
    返回对比表和行动地图
    """
    user_msg = f"""用户情况：
- 安全垫：存款{user_params.get('savings_months', '未知')}个月
- 固定支出：{user_params.get('fixed_expenses', '未知')}
- 最怕的情况：{user_params.get('worst_fear', '未知')}
- 价值排序：
{_build_value_profile_text(value_profile)}
- 可能的决策偏差：
{_build_bias_text(decision_biases)}
- 近期外部市场声音：
{_build_external_signals_text(external_signals)}

选项A模拟结果：{choice_a_sim}
选项B模拟结果：{choice_b_sim}
第三条路：{_normalize_alternative_path(alternative_path or {})}

请生成对比总览和行动地图。"""
    try:
        data = call_agent_json(
            B9_SYSTEM,
            user_msg,
            max_tokens=max_tokens,
            temperature=0.2,
            retries=0,
            allow_downgrade=False,
            timeout_seconds=_adaptive_timeout(max_tokens, floor=20, ceiling=45, ratio=180),
        )
        if isinstance(data, dict):
            merged = dict(data)
            merged["decision_biases"] = _merge_bias_entries(data.get("decision_biases", []), decision_biases)
            merged["bias_reminder"] = _sanitize_generated_text(data.get("bias_reminder"), default=_build_bias_reminder(merged["decision_biases"]))
            merged["third_path"] = _normalize_alternative_path(alternative_path or {})
            return merged
    except Exception:
        pass
    return _build_b9_fallback(
        choice_a_sim,
        choice_b_sim,
        user_params,
        decision_biases=decision_biases,
        alternative_path=alternative_path,
    )
