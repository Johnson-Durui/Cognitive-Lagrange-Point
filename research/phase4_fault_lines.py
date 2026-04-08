"""认知拉格朗日点 · 阶段四：断层线识别"""

from __future__ import annotations

from .api import call_agent_json
from .models import ConfirmedLagrangePoint, FaultLine

FAULT_LINE_SYSTEM = """你是一位“断层线识别Agent”，负责在多个认知拉格朗日点之间识别共享的底层张力结构。

你的任务：
1. 找出哪些确认点沿着相同的底层张力聚集
2. 为每条张力线命名
3. 给出每条断层线的简洁描述
4. 标出哪些断层线彼此交叉

输出 JSON：
{
  "fault_lines": [
    {
      "name": "自由-安全张力带",
      "description": "围绕自由扩张与风险控制之间的结构性对冲而形成的断层线",
      "points_on_line": ["CLP-001", "CLP-003"],
      "intersections": ["技术治理断裂带"]
    }
  ]
}

规则：
- 只有当多个确认点确实共享底层张力时才建立断层线
- points_on_line 只能使用已给定的 CLP 编号
- intersections 只能填写本次输出里出现的断层线名称
- 不要为了凑数量强行造线
- 只输出 JSON"""


def _build_context(confirmed: list[ConfirmedLagrangePoint]) -> str:
    lines = []
    for clp in confirmed:
        pro_names = "、".join(force.name for force in clp.pro_forces[:3]) or "正方力量"
        con_names = "、".join(force.name for force in clp.con_forces[:3]) or "反方力量"
        stability = clp.stability_type.value if clp.stability_type else "未测"
        oscillation = clp.oscillation_type.value if clp.oscillation_type else "未测"
        lines.append(
            f"{clp.id}\n"
            f"问题：{clp.question_text}\n"
            f"正方核心：{pro_names}\n"
            f"反方核心：{con_names}\n"
            f"平衡分析：{clp.balance_analysis or '未提供'}\n"
            f"稳定性：{stability}\n"
            f"振荡：{oscillation}"
        )
    return "\n\n".join(lines)


def _normalize_fault_lines(raw_lines: list[dict], confirmed_ids: set[str]) -> list[FaultLine]:
    normalized: list[FaultLine] = []
    seen_names: set[str] = set()

    for item in raw_lines:
        name = str(item.get("name", "")).strip()
        if not name or name in seen_names:
            continue

        points = []
        for point in item.get("points_on_line", []):
            point_id = str(point).strip()
            if point_id in confirmed_ids and point_id not in points:
                points.append(point_id)

        if len(points) < 2:
            continue

        normalized.append(
            FaultLine(
                name=name,
                description=str(item.get("description", "")).strip(),
                points_on_line=points,
                intersections=[],
            )
        )
        seen_names.add(name)

    valid_names = {line.name for line in normalized}
    raw_by_name = {
        str(item.get("name", "")).strip(): item
        for item in raw_lines
        if str(item.get("name", "")).strip()
    }
    for line in normalized:
        requested = raw_by_name.get(line.name, {}).get("intersections", [])
        line.intersections = [
            str(name).strip()
            for name in requested
            if str(name).strip() in valid_names and str(name).strip() != line.name
        ]

    return normalized


def identify_fault_lines(confirmed: list[ConfirmedLagrangePoint]) -> list[FaultLine]:
    """识别确认点之间的断层线。"""
    if len(confirmed) < 2:
        return []

    user_message = (
        "以下是已经确认的认知拉格朗日点，请识别它们之间的断层线。\n\n"
        f"{_build_context(confirmed)}"
    )
    data = call_agent_json(FAULT_LINE_SYSTEM, user_message, max_tokens=2400, temperature=0.3)
    raw_lines = data.get("fault_lines", []) if isinstance(data, dict) else []
    return _normalize_fault_lines(raw_lines, {clp.id for clp in confirmed})


def run_fault_line_analysis(
    confirmed: list[ConfirmedLagrangePoint],
    existing_fault_lines: list[FaultLine] | None = None,
    checkpoint_hook=None,
) -> list[FaultLine]:
    """执行断层线识别，并把结果回写到各确认点。"""
    print(f"\n  🗺 阶段四：断层线识别（{len(confirmed)}个确认点）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    if len(confirmed) < 2:
        print("  ⚠ 确认点少于 2 个，暂时无法识别断层线", flush=True)
        return existing_fault_lines or []

    if existing_fault_lines:
        target_ids = {
            point_id
            for line in existing_fault_lines
            for point_id in line.points_on_line
        }
        already_assigned = True
        for clp in confirmed:
            if clp.id not in target_ids:
                continue
            expected = {
                line.name
                for line in existing_fault_lines
                if clp.id in line.points_on_line
            }
            if not expected.issubset(set(clp.fault_lines)):
                already_assigned = False
                break
        if already_assigned and target_ids:
            print("  ↺ 已有断层线结果，跳过重复调用", flush=True)
            return existing_fault_lines

    fault_lines = identify_fault_lines(confirmed)

    for clp in confirmed:
        clp.fault_lines = []
    for line in fault_lines:
        for point_id in line.points_on_line:
            for clp in confirmed:
                if clp.id == point_id and line.name not in clp.fault_lines:
                    clp.fault_lines.append(line.name)

    if checkpoint_hook is not None:
        checkpoint_hook(
            confirmed_override=confirmed,
            fault_lines_override=fault_lines,
        )

    print(f"  🗺 识别出 {len(fault_lines)} 条断层线", flush=True)
    return fault_lines
