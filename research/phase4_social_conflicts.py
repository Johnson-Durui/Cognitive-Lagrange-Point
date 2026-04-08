"""认知拉格朗日点 · 阶段四：社会冲突预测"""

from __future__ import annotations

from .api import call_agent_json
from .models import ConfirmedLagrangePoint, FaultLine

SOCIAL_CONFLICT_SYSTEM = """你是一位“社会冲突预测Agent”，负责根据已确认的认知拉格朗日点、断层线和隧道效应，提炼关键发现，并预测最可能被激活的社会冲突热点。

输出 JSON：
{
  "key_discoveries": [
    "一句关键发现"
  ],
  "social_conflict_predictions": [
    {
      "title": "冲突热点名称",
      "related_fault_lines": ["公平-效率张力带"],
      "related_points": ["CLP-002", "CLP-004"],
      "activation_signal": "什么现实条件会触发它",
      "prediction": "为什么它结构上容易爆发"
    }
  ]
}

规则：
- 关键发现控制在 3-6 条
- 冲突预测控制在 2-5 条
- 只使用给定的断层线名称和 CLP 编号
- prediction 要具体，不要空泛
- 只输出 JSON"""


def _build_context(
    confirmed: list[ConfirmedLagrangePoint],
    fault_lines: list[FaultLine],
    tunnel_effects: list[dict],
) -> str:
    point_lines = []
    for clp in confirmed:
        point_lines.append(
            f"{clp.id}\n"
            f"问题：{clp.question_text}\n"
            f"平衡精度：{clp.balance_precision}%\n"
            f"断层线：{'、'.join(clp.fault_lines) or '未归类'}\n"
            f"隧道连接：{'、'.join(clp.tunnel_connections) or '无'}"
        )

    fault_lines_text = []
    for line in fault_lines:
        fault_lines_text.append(
            f"{line.name} | 点位：{', '.join(line.points_on_line)} | 描述：{line.description}"
        )

    tunnels_text = []
    for item in tunnel_effects:
        tunnels_text.append(
            f"{item['from_point']} -> {item['to_point']} | 强度：{item['strength']} | 原因：{item.get('rationale', '')}"
        )

    return (
        "确认点：\n"
        f"{chr(10).join(point_lines)}\n\n"
        "断层线：\n"
        f"{chr(10).join(fault_lines_text) or '无'}\n\n"
        "隧道效应：\n"
        f"{chr(10).join(tunnels_text) or '无'}"
    )


def _normalize_predictions(
    raw_predictions: list[dict],
    valid_fault_lines: set[str],
    valid_points: set[str],
) -> list[dict]:
    normalized = []
    seen_titles = set()

    for item in raw_predictions:
        title = str(item.get("title", "")).strip()
        prediction = str(item.get("prediction", "")).strip()
        if not title or not prediction or title in seen_titles:
            continue

        related_fault_lines = [
            name
            for name in (str(value).strip() for value in item.get("related_fault_lines", []))
            if name in valid_fault_lines
        ]
        related_points = [
            point_id
            for point_id in (str(value).strip() for value in item.get("related_points", []))
            if point_id in valid_points
        ]

        normalized.append({
            "title": title,
            "related_fault_lines": related_fault_lines,
            "related_points": related_points,
            "activation_signal": str(item.get("activation_signal", "")).strip(),
            "prediction": prediction,
        })
        seen_titles.add(title)

    return normalized[:5]


def identify_social_conflicts(
    confirmed: list[ConfirmedLagrangePoint],
    fault_lines: list[FaultLine],
    tunnel_effects: list[dict],
) -> tuple[list[dict], list[str]]:
    user_message = (
        "以下是已经确认的认知拉格朗日点、断层线和隧道效应，请提炼关键发现并预测未来社会冲突热点。\n\n"
        f"{_build_context(confirmed, fault_lines, tunnel_effects)}"
    )
    data = call_agent_json(SOCIAL_CONFLICT_SYSTEM, user_message, max_tokens=2600, temperature=0.4)

    key_discoveries = []
    for item in data.get("key_discoveries", []) if isinstance(data, dict) else []:
        text = str(item).strip()
        if text and text not in key_discoveries:
            key_discoveries.append(text)

    predictions = _normalize_predictions(
        data.get("social_conflict_predictions", []) if isinstance(data, dict) else [],
        valid_fault_lines={line.name for line in fault_lines},
        valid_points={clp.id for clp in confirmed},
    )
    return predictions, key_discoveries[:6]


def run_social_conflict_analysis(
    confirmed: list[ConfirmedLagrangePoint],
    fault_lines: list[FaultLine],
    tunnel_effects: list[dict],
    *,
    existing_predictions: list[dict] | None = None,
    existing_key_discoveries: list[str] | None = None,
    checkpoint_hook=None,
) -> tuple[list[dict], list[str]]:
    """基于断层线与隧道效应预测社会冲突热点。"""
    print(f"\n  🔮 阶段四：社会冲突预测（{len(confirmed)}个确认点）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    if not confirmed:
        print("  ⚠ 当前没有确认点，暂时无法做社会冲突预测", flush=True)
        return existing_predictions or [], existing_key_discoveries or []

    if existing_predictions and existing_key_discoveries:
        print("  ↺ 已有社会冲突预测结果，跳过重复调用", flush=True)
        return existing_predictions, existing_key_discoveries

    try:
        predictions, key_discoveries = identify_social_conflicts(
            confirmed,
            fault_lines,
            tunnel_effects,
        )
    except Exception as exc:
        print(f"  ⚠ 社会冲突预测失败：{str(exc)[:80]}", flush=True)
        return existing_predictions or [], existing_key_discoveries or []

    if checkpoint_hook is not None:
        checkpoint_hook(
            confirmed_override=confirmed,
            fault_lines_override=fault_lines,
            tunnel_effects_override=tunnel_effects,
            social_conflict_predictions_override=predictions,
            key_discoveries_override=key_discoveries,
        )

    print(f"  🔮 生成 {len(predictions)} 条社会冲突预测", flush=True)
    return predictions, key_discoveries
