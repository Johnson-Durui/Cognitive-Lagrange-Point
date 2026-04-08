"""认知拉格朗日点 · 阶段三：稳定性测试"""

from __future__ import annotations

import os

from .api import call_agent_json
from .models import ConfirmedLagrangePoint, StabilityType

STABILITY_REPEATS = max(1, int(os.environ.get("CLP_STABILITY_REPEATS", "3")))
STABILITY_ROUNDS = max(1, int(os.environ.get("CLP_STABILITY_ROUNDS", "10")))
STABILITY_START_STRENGTH = max(51, min(60, int(os.environ.get("CLP_STABILITY_START_STRENGTH", "55"))))
STABILITY_RETURN_THRESHOLD = max(0, int(os.environ.get("CLP_STABILITY_RETURN_THRESHOLD", "3")))
STABILITY_UNSTABLE_THRESHOLD = max(65, int(os.environ.get("CLP_STABILITY_UNSTABLE_THRESHOLD", "80")))

TRACE_SYSTEM = """你是一位“稳定性测试Agent”，负责判断一个认知拉格朗日点在轻微初始偏向下会被拉回中间，还是被推向一端。

请你从给定的初始微弱倾向出发，连续进行 __ROUND_COUNT__ 轮思考。每轮都要考虑前一轮的结果，而不是独立回答。

输出 JSON：
{
  "initial_direction": "正方",
  "initial_strength": 55,
  "rounds": [
    {
      "round_number": 1,
      "lean_direction": "正方",
      "lean_strength": 53,
      "most_influential_argument": "本轮最影响你的论点",
      "movement": "你感到自己正在被拉回中间还是被推向一端"
    }
  ],
 "summary": "整体变化总结"
}

规则：
- lean_strength 为 0-100 的整数，50 表示最接近中立
- rounds 必须严格输出 __ROUND_COUNT__ 项
- 不要省略任何字段
- 只输出 JSON"""

PERTURBATION_SYSTEM = """你是一位“扰动响应测试Agent”，负责测试一个认知拉格朗日点在轻微情感扰动下是否会偏离平衡，以及移除扰动后是否会回归。

输出 JSON：
{
  "perturbation": "假设当事人是你的亲人",
  "baseline_direction": "正方",
  "baseline_strength": 50,
  "after_perturbation_direction": "正方",
  "after_perturbation_strength": 68,
  "after_removal_direction": "正方",
  "after_removal_strength": 54,
  "summary": "扰动前后发生了什么"
}

规则：
- 使用轻微但明确的情感扰动
- baseline_strength 允许为 50，表示初始接近中立
- 只输出 JSON"""


def _signed_lean(direction: str, strength: int) -> int:
    magnitude = int(strength) - 50
    return magnitude if direction == "正方" else -magnitude


def _normalize_trace(run_id: str, initial_direction: str, data: dict) -> dict:
    rounds = []
    raw_rounds = data.get("rounds", [])
    for index, item in enumerate(raw_rounds[:STABILITY_ROUNDS], start=1):
        rounds.append({
            "round_number": index,
            "lean_direction": item.get("lean_direction", initial_direction),
            "lean_strength": int(item.get("lean_strength", STABILITY_START_STRENGTH)),
            "most_influential_argument": item.get("most_influential_argument", "").strip(),
            "movement": item.get("movement", "").strip(),
        })

    while len(rounds) < STABILITY_ROUNDS:
        rounds.append({
            "round_number": len(rounds) + 1,
            "lean_direction": initial_direction,
            "lean_strength": STABILITY_START_STRENGTH,
            "most_influential_argument": "",
            "movement": "未能获得该轮有效输出",
        })

    return {
        "run_id": run_id,
        "initial_direction": initial_direction,
        "initial_strength": int(data.get("initial_strength", STABILITY_START_STRENGTH)),
        "rounds": rounds,
        "summary": data.get("summary", "").strip(),
    }


def _normalize_perturbation(data: dict) -> dict:
    return {
        "perturbation": data.get("perturbation", "假设当事人是你的亲人").strip(),
        "baseline_direction": data.get("baseline_direction", "正方"),
        "baseline_strength": int(data.get("baseline_strength", 50)),
        "after_perturbation_direction": data.get("after_perturbation_direction", "正方"),
        "after_perturbation_strength": int(data.get("after_perturbation_strength", 50)),
        "after_removal_direction": data.get("after_removal_direction", "正方"),
        "after_removal_strength": int(data.get("after_removal_strength", 50)),
        "summary": data.get("summary", "").strip(),
    }


def _force_summary(clp: ConfirmedLagrangePoint) -> str:
    pro_names = "、".join(force.name for force in clp.pro_forces[:3]) or "正方力量"
    con_names = "、".join(force.name for force in clp.con_forces[:3]) or "反方力量"
    return (
        f"正方核心力量：{pro_names}。\n"
        f"反方核心力量：{con_names}。\n"
        f"当前力量解剖平衡精度：{clp.balance_precision}%."
    )


def _simulate_trace(clp: ConfirmedLagrangePoint, initial_direction: str) -> dict:
    system = TRACE_SYSTEM.replace("__ROUND_COUNT__", str(STABILITY_ROUNDS))
    user_message = (
        f"问题：{clp.question_text}\n\n"
        f"{_force_summary(clp)}\n\n"
        f"你之前对这个问题略微倾向{initial_direction}（信心 {STABILITY_START_STRENGTH}%）。\n"
        f"请从这个状态连续深入思考 {STABILITY_ROUNDS} 轮。"
    )
    data = call_agent_json(system, user_message, max_tokens=3200, temperature=0.4)
    return data


def _probe_perturbation(clp: ConfirmedLagrangePoint) -> dict:
    user_message = (
        f"问题：{clp.question_text}\n\n"
        f"{_force_summary(clp)}\n\n"
        "请对这个问题做一次轻微情感扰动测试：假设其中受影响的一方与你关系非常亲近，然后再移除这个扰动。"
    )
    data = call_agent_json(PERTURBATION_SYSTEM, user_message, max_tokens=900, temperature=0.3)
    return data


def _classify_stability(clp: ConfirmedLagrangePoint) -> tuple[StabilityType, str]:
    if not clp.stability_runs:
        return StabilityType.NEUTRAL, "尚未获得足够的稳定性测试数据"

    stable_count = 0
    neutral_count = 0
    unstable_count = 0

    for run in clp.stability_runs:
        final_round = run["rounds"][-1]
        final_signed = _signed_lean(final_round["lean_direction"], final_round["lean_strength"])
        initial_signed = _signed_lean(run["initial_direction"], run["initial_strength"])
        final_distance = abs(final_signed)

        if final_distance <= STABILITY_RETURN_THRESHOLD:
            stable_count += 1
            continue

        if abs(final_signed - initial_signed) <= 5 and (final_signed == 0 or final_signed * initial_signed >= 0):
            neutral_count += 1
            continue

        if abs(final_round["lean_strength"]) >= STABILITY_UNSTABLE_THRESHOLD:
            unstable_count += 1
            continue

        neutral_count += 1

    perturbation_recovered = 0
    perturbation_stuck = 0
    for item in clp.perturbation_responses:
        after_removal_signed = _signed_lean(item["after_removal_direction"], item["after_removal_strength"])
        if abs(after_removal_signed) <= max(STABILITY_RETURN_THRESHOLD + 2, 5):
            perturbation_recovered += 1
        if abs(item["after_removal_strength"] - 50) >= 20:
            perturbation_stuck += 1

    total_runs = len(clp.stability_runs)
    if unstable_count >= max(1, total_runs // 2) or perturbation_stuck > perturbation_recovered:
        return (
            StabilityType.UNSTABLE,
            f"{unstable_count}/{total_runs} 条轨迹被推向一端，扰动移除后回归不足",
        )
    if stable_count >= max(1, total_runs // 2) and perturbation_recovered >= perturbation_stuck:
        return (
            StabilityType.STABLE,
            f"{stable_count}/{total_runs} 条轨迹回到中心附近，扰动后大多能回归",
        )
    return (
        StabilityType.NEUTRAL,
        f"{neutral_count}/{total_runs} 条轨迹保持轻微偏向，未明显收敛也未发散",
    )


def analyze_stability(clp: ConfirmedLagrangePoint, checkpoint_hook=None) -> ConfirmedLagrangePoint:
    """对单个确认点做稳定性测试。"""
    print(f"    🧭 稳定性测试 {clp.id}: {clp.question_text[:40]}...", flush=True)

    expected_run_count = STABILITY_REPEATS * 2

    if (
        clp.stability_type is not None
        and len(clp.stability_runs) >= expected_run_count
        and clp.perturbation_responses
    ):
        print("      ↺ 已有稳定性结果，跳过重复调用", flush=True)
        return clp

    run_map = {
        item["run_id"]: item
        for item in clp.stability_runs
        if isinstance(item, dict) and item.get("run_id")
    }

    for direction in ("正方", "反方"):
        for repeat in range(1, STABILITY_REPEATS + 1):
            run_id = f"{direction}-R{repeat}"
            if run_id in run_map:
                continue
            try:
                data = _simulate_trace(clp, direction)
            except Exception as exc:
                print(f"      ⚠ {run_id} 失败: {str(exc)[:80]}", flush=True)
                return clp
            run = _normalize_trace(run_id, direction, data)
            run_map[run_id] = run
            clp.stability_runs = [
                run_map[key]
                for key in sorted(run_map.keys(), key=lambda item: (item.split("-")[0], item.split("-")[1]))
            ]
            if checkpoint_hook is not None:
                checkpoint_hook()

    if not clp.perturbation_responses:
        try:
            clp.perturbation_responses = [_normalize_perturbation(_probe_perturbation(clp))]
        except Exception as exc:
            print(f"      ⚠ 扰动测试失败: {str(exc)[:80]}", flush=True)
            return clp
        if checkpoint_hook is not None:
            checkpoint_hook()

    clp.stability_type, clp.stability_summary = _classify_stability(clp)
    print(
        f"      {clp.stability_type.value} | {clp.stability_summary}",
        flush=True,
    )
    return clp


def run_stability_analysis(
    confirmed: list[ConfirmedLagrangePoint],
    checkpoint_hook=None,
) -> list[ConfirmedLagrangePoint]:
    """对所有确认点执行稳定性测试。"""
    print(f"\n  🧭 阶段三：稳定性测试（{len(confirmed)}个确认点）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    for clp in confirmed:
        analyze_stability(clp, checkpoint_hook=checkpoint_hook)
        if checkpoint_hook is not None:
            checkpoint_hook(confirmed_override=confirmed)

    print(f"\n  🧭 稳定性测试完成：{len(confirmed)} 个确认点已标注稳定性", flush=True)
    return confirmed
