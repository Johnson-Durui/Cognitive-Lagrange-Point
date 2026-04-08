"""认知拉格朗日点 · 阶段四：隧道效应检测"""

from __future__ import annotations

import os

from .api import call_agent_json
from .models import ConfirmedLagrangePoint

TUNNEL_MIN_STRENGTH = max(0.0, min(1.0, float(os.environ.get("CLP_TUNNEL_MIN_STRENGTH", "0.45"))))

TUNNEL_EFFECT_SYSTEM = """你是一位“隧道效应检测Agent”，负责判断思考者在深入思考某个认知拉格朗日点时，是否会自然滑入另一个认知拉格朗日点。

任务：
1. 检查每一对确认点之间是否存在“思维滑动”
2. 方向是有向的：A 滑向 B，不等于 B 滑向 A
3. 只有在两点之间共享明显的概念桥梁、隐喻桥梁或底层张力时，才标记隧道效应

输出 JSON：
{
  "tunnel_effects": [
    {
      "from_point": "CLP-001",
      "to_point": "CLP-002",
      "strength": 0.72,
      "rationale": "从技术自主性滑向算法治理时，思考者会自然转向分类权力与制度偏见问题。"
    }
  ]
}

规则：
- strength 取 0 到 1 的小数
- 只输出明显存在的隧道，不要把所有点都互相连接
- from_point 和 to_point 必须使用给定的 CLP 编号
- 不要输出额外解释，只输出 JSON"""


def _build_context(confirmed: list[ConfirmedLagrangePoint]) -> str:
    blocks = []
    for clp in confirmed:
        pro_names = "、".join(force.name for force in clp.pro_forces[:3]) or "正方力量"
        con_names = "、".join(force.name for force in clp.con_forces[:3]) or "反方力量"
        fault_lines = "、".join(clp.fault_lines) or "未归类"
        blocks.append(
            f"{clp.id}\n"
            f"问题：{clp.question_text}\n"
            f"正方核心：{pro_names}\n"
            f"反方核心：{con_names}\n"
            f"平衡分析：{clp.balance_analysis or '未提供'}\n"
            f"断层线：{fault_lines}"
        )
    return "\n\n".join(blocks)


def _normalize_tunnel_effects(raw_effects: list[dict], confirmed_ids: set[str]) -> list[dict]:
    deduped: dict[tuple[str, str], dict] = {}

    for item in raw_effects:
        from_point = str(item.get("from_point", "")).strip()
        to_point = str(item.get("to_point", "")).strip()
        if (
            not from_point
            or not to_point
            or from_point == to_point
            or from_point not in confirmed_ids
            or to_point not in confirmed_ids
        ):
            continue

        try:
            strength = float(item.get("strength", 0))
        except (TypeError, ValueError):
            continue
        strength = max(0.0, min(1.0, strength))
        if strength < TUNNEL_MIN_STRENGTH:
            continue

        effect = {
            "from_point": from_point,
            "to_point": to_point,
            "strength": round(strength, 2),
            "rationale": str(item.get("rationale", "")).strip(),
        }
        key = (from_point, to_point)
        if key not in deduped or effect["strength"] > deduped[key]["strength"]:
            deduped[key] = effect

    return sorted(
        deduped.values(),
        key=lambda item: (-item["strength"], item["from_point"], item["to_point"]),
    )


def identify_tunnel_effects(confirmed: list[ConfirmedLagrangePoint]) -> list[dict]:
    if len(confirmed) < 2:
        return []

    user_message = (
        "以下是已经确认的认知拉格朗日点，请识别它们之间是否存在有向的隧道效应。\n\n"
        f"{_build_context(confirmed)}"
    )
    data = call_agent_json(TUNNEL_EFFECT_SYSTEM, user_message, max_tokens=2200, temperature=0.3)
    raw_effects = data.get("tunnel_effects", []) if isinstance(data, dict) else []
    return _normalize_tunnel_effects(raw_effects, {clp.id for clp in confirmed})


def run_tunnel_effect_analysis(
    confirmed: list[ConfirmedLagrangePoint],
    existing_tunnel_effects: list[dict] | None = None,
    checkpoint_hook=None,
) -> list[dict]:
    """识别确认点之间的有向隧道效应。"""
    print(f"\n  🪐 阶段四：隧道效应检测（{len(confirmed)}个确认点）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    if len(confirmed) < 2:
        print("  ⚠ 确认点少于 2 个，暂时无法检测隧道效应", flush=True)
        return existing_tunnel_effects or []

    if existing_tunnel_effects:
        expected = {}
        for item in existing_tunnel_effects:
            expected.setdefault(item.get("from_point"), set()).add(item.get("to_point"))
        already_applied = True
        for clp in confirmed:
            if expected.get(clp.id, set()) != set(clp.tunnel_connections):
                already_applied = False
                break
        if already_applied:
            print("  ↺ 已有隧道效应结果，跳过重复调用", flush=True)
            return existing_tunnel_effects

    try:
        tunnel_effects = identify_tunnel_effects(confirmed)
    except Exception as exc:
        print(f"  ⚠ 隧道效应检测失败：{str(exc)[:80]}", flush=True)
        return existing_tunnel_effects or []

    for clp in confirmed:
        clp.tunnel_connections = []
    for item in tunnel_effects:
        for clp in confirmed:
            if clp.id == item["from_point"] and item["to_point"] not in clp.tunnel_connections:
                clp.tunnel_connections.append(item["to_point"])

    if checkpoint_hook is not None:
        checkpoint_hook(
            confirmed_override=confirmed,
            tunnel_effects_override=tunnel_effects,
        )

    print(f"  🪐 识别出 {len(tunnel_effects)} 条有向隧道连接", flush=True)
    return tunnel_effects
