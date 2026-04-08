"""认知拉格朗日点 · 阶段三：振荡测量"""

from __future__ import annotations

import os
import statistics

from .api import call_agent_json
from .models import ConfirmedLagrangePoint, OscillationData, OscillationType

OSCILLATION_TOTAL_ROUNDS = max(1, int(os.environ.get("CLP_OSCILLATION_ROUNDS", "50")))
OSCILLATION_CHUNK_SIZE = max(1, int(os.environ.get("CLP_OSCILLATION_CHUNK_SIZE", "10")))
OSCILLATION_NEUTRAL_BAND = max(0, int(os.environ.get("CLP_OSCILLATION_NEUTRAL_BAND", "3")))

OSCILLATION_CHUNK_SYSTEM = """你是一位“振荡观察Agent”，负责记录一个思考者在认知拉格朗日点上的持续振荡轨迹。

现在请基于给定的问题、已有思考历史摘要和最近几轮记录，继续生成接下来的 __ROUND_COUNT__ 轮思考。

输出 JSON：
{{
  "chunk_start": __CHUNK_START__,
  "rounds": [
    {{
      "round_number": 1,
      "new_angle_explored": "本轮探索了什么新角度",
      "lean_direction": "正方",
      "lean_strength": 54,
      "feels_circular": false
    }}
  ],
  "chunk_summary": "这 __ROUND_COUNT__ 轮的整体模式总结"
}}

规则：
- lean_strength 为 0-100 的整数，50 表示最接近中立
- round_number 必须连续，且从 __CHUNK_START__ 开始
- 不要试图得出最终答案，只记录振荡过程
- 如果你感到思考开始重复或自我回环，feels_circular 设为 true
- 只输出 JSON"""


def _signed_lean(direction: str, strength: int) -> int:
    magnitude = int(strength) - 50
    return magnitude if direction == "正方" else -magnitude


def _force_summary(clp: ConfirmedLagrangePoint) -> str:
    pro_names = "、".join(force.name for force in clp.pro_forces[:3]) or "正方力量"
    con_names = "、".join(force.name for force in clp.con_forces[:3]) or "反方力量"
    lines = [
        f"正方核心力量：{pro_names}",
        f"反方核心力量：{con_names}",
        f"当前力量解剖平衡精度：{clp.balance_precision}%",
    ]
    if clp.stability_type is not None:
        lines.append(f"稳定性：{clp.stability_type.value}")
    if clp.stability_summary:
        lines.append(f"稳定性摘要：{clp.stability_summary}")
    return "\n".join(lines)


def _format_recent_rounds(data: list[OscillationData], limit: int = 5) -> str:
    if not data:
        return "暂无历史轮次。"
    recent = data[-limit:]
    return "\n".join(
        f"第{item.round_number}轮 | {item.lean_direction}:{item.lean_strength} | 角度：{item.new_angle_explored} | 循环感：{item.feels_circular}"
        for item in recent
    )


def _format_chunk_summaries(clp: ConfirmedLagrangePoint) -> str:
    if not clp.oscillation_summaries:
        return "暂无压缩摘要。"
    return "\n".join(
        f"{item['start_round']}-{item['end_round']}轮：{item['summary']}"
        for item in clp.oscillation_summaries
    )


def _normalize_chunk(
    data: dict,
    *,
    chunk_start: int,
    chunk_size: int,
    prior_data: list[OscillationData],
) -> tuple[list[OscillationData], dict]:
    normalized: list[OscillationData] = []
    raw_rounds = data.get("rounds", [])
    fallback_direction = prior_data[-1].lean_direction if prior_data else "正方"

    for offset in range(chunk_size):
        expected_round = chunk_start + offset
        raw = raw_rounds[offset] if offset < len(raw_rounds) else {}
        normalized.append(
            OscillationData(
                round_number=int(raw.get("round_number", expected_round)),
                lean_direction=raw.get("lean_direction", fallback_direction),
                lean_strength=int(raw.get("lean_strength", 50)),
                new_angle_explored=raw.get("new_angle_explored", "").strip(),
                feels_circular=bool(raw.get("feels_circular", False)),
            )
        )

    summary = {
        "start_round": chunk_start,
        "end_round": chunk_start + chunk_size - 1,
        "summary": data.get("chunk_summary", "").strip(),
    }
    return normalized, summary


def _generate_chunk(clp: ConfirmedLagrangePoint, chunk_start: int, chunk_size: int) -> tuple[list[OscillationData], dict]:
    system = (
        OSCILLATION_CHUNK_SYSTEM
        .replace("__ROUND_COUNT__", str(chunk_size))
        .replace("__CHUNK_START__", str(chunk_start))
    )
    user_message = (
        f"问题：{clp.question_text}\n\n"
        f"{_force_summary(clp)}\n\n"
        f"历史摘要：\n{_format_chunk_summaries(clp)}\n\n"
        f"最近几轮：\n{_format_recent_rounds(clp.oscillation_data)}\n\n"
        f"请继续生成第 {chunk_start} 到第 {chunk_start + chunk_size - 1} 轮的持续思考记录。"
    )
    data = call_agent_json(system, user_message, max_tokens=2600, temperature=0.5)
    return _normalize_chunk(
        data,
        chunk_start=chunk_start,
        chunk_size=chunk_size,
        prior_data=clp.oscillation_data,
    )


def _dominant_signs(values: list[int]) -> list[int]:
    dominant = []
    last_non_zero = 0
    for value in values:
        if abs(value) <= OSCILLATION_NEUTRAL_BAND:
            dominant.append(last_non_zero)
            continue
        sign = 1 if value > 0 else -1
        dominant.append(sign)
        last_non_zero = sign
    return dominant


def _estimate_period(signs: list[int]) -> float | None:
    change_points = [
        index
        for index in range(1, len(signs))
        if signs[index] != 0 and signs[index - 1] != 0 and signs[index] != signs[index - 1]
    ]
    if len(change_points) < 3:
        return None
    full_cycles = [
        change_points[index + 2] - change_points[index]
        for index in range(len(change_points) - 2)
    ]
    if not full_cycles:
        return None
    return round(sum(full_cycles) / len(full_cycles), 1)


def _classify_oscillation(clp: ConfirmedLagrangePoint) -> tuple[OscillationType, float | None, str]:
    if not clp.oscillation_data:
        return OscillationType.CHAOTIC, None, "尚无振荡数据"

    signed = [_signed_lean(item.lean_direction, item.lean_strength) for item in clp.oscillation_data]
    amplitudes = [abs(value) for value in signed]
    signs = _dominant_signs(signed)
    period = _estimate_period(signs)

    front = amplitudes[: max(1, len(amplitudes) // 3)]
    back = amplitudes[-max(1, len(amplitudes) // 3):]
    front_avg = sum(front) / len(front)
    back_avg = sum(back) / len(back)
    amp_stdev = statistics.pstdev(amplitudes) if len(amplitudes) > 1 else 0.0

    sign_changes = sum(
        1
        for index in range(1, len(signs))
        if signs[index] != 0 and signs[index - 1] != 0 and signs[index] != signs[index - 1]
    )
    circular_ratio = sum(1 for item in clp.oscillation_data if item.feels_circular) / max(len(clp.oscillation_data), 1)

    if back_avg <= max(4, front_avg * 0.65):
        return (
            OscillationType.DAMPED,
            period,
            f"振幅从前段均值 {front_avg:.1f} 降到后段均值 {back_avg:.1f}",
        )

    if back_avg >= max(front_avg * 1.35, front_avg + 6) and max(amplitudes) >= 18:
        return (
            OscillationType.DIVERGENT,
            period,
            f"振幅从前段均值 {front_avg:.1f} 增长到后段均值 {back_avg:.1f}",
        )

    if sign_changes >= 4 and amp_stdev <= max(4, front_avg * 0.35) and abs(back_avg - front_avg) <= max(3, front_avg * 0.2):
        return (
            OscillationType.SUSTAINED,
            period,
            f"多次跨边摆动且振幅较稳定（标准差 {amp_stdev:.1f}）",
        )

    return (
        OscillationType.CHAOTIC,
        period,
        f"共发生 {sign_changes} 次方向切换，循环感比例 {circular_ratio:.2f}，振幅标准差 {amp_stdev:.1f}",
    )


def analyze_oscillation(clp: ConfirmedLagrangePoint, checkpoint_hook=None) -> ConfirmedLagrangePoint:
    """对单个确认点测量 50 轮振荡模式。"""
    print(f"    🌀 振荡测量 {clp.id}: {clp.question_text[:40]}...", flush=True)

    if clp.oscillation_type is not None and len(clp.oscillation_data) >= OSCILLATION_TOTAL_ROUNDS:
        print("      ↺ 已有振荡结果，跳过重复调用", flush=True)
        return clp

    while len(clp.oscillation_data) < OSCILLATION_TOTAL_ROUNDS:
        chunk_start = len(clp.oscillation_data) + 1
        chunk_size = min(OSCILLATION_CHUNK_SIZE, OSCILLATION_TOTAL_ROUNDS - len(clp.oscillation_data))
        try:
            rounds, summary = _generate_chunk(clp, chunk_start, chunk_size)
        except Exception as exc:
            print(f"      ⚠ 第{chunk_start}轮起的振荡块失败: {str(exc)[:80]}", flush=True)
            return clp

        clp.oscillation_data.extend(rounds)
        clp.oscillation_summaries.append(summary)
        if checkpoint_hook is not None:
            checkpoint_hook()

    clp.oscillation_type, clp.oscillation_period, clp.oscillation_summary = _classify_oscillation(clp)
    print(
        f"      {clp.oscillation_type.value} | 周期 {clp.oscillation_period or '未稳定'} 轮",
        flush=True,
    )
    return clp


def run_oscillation_analysis(
    confirmed: list[ConfirmedLagrangePoint],
    checkpoint_hook=None,
) -> list[ConfirmedLagrangePoint]:
    """对所有确认点执行振荡测量。"""
    print(f"\n  🌀 阶段三：振荡测量（{len(confirmed)}个确认点）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    for clp in confirmed:
        analyze_oscillation(clp, checkpoint_hook=checkpoint_hook)
        if checkpoint_hook is not None:
            checkpoint_hook(confirmed_override=confirmed)

    print(f"\n  🌀 振荡测量完成：{len(confirmed)} 个确认点已标注振荡类型", flush=True)
    return confirmed
