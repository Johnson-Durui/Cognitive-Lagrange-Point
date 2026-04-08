"""认知拉格朗日点 · 阶段三：力量解剖"""

import statistics

from .api import call_agent_json
from .models import CandidateQuestion, ConfirmedLagrangePoint, Force

FORCE_SYSTEM = """你是一位认知力场分析师。给定一个经验证的认知拉格朗日点问题，请做以下分析：

1. 列出所有拉向"正方"的力量（至少3股，最多6股）
2. 列出所有拉向"反方"的力量（至少3股，最多6股）
3. 找出不属于正反任何一方的"隐藏力量"（如问题框架本身的预设）

对每股力量评估强度（0-100）。

请以JSON格式输出：
{
  "pro_forces": [
    {
      "name": "力量名称",
      "source": "来自什么理论/直觉/经验",
      "strength": 85,
      "best_argument": "最佳论证（3句话内）",
      "known_weakness": "已知弱点（1句话）"
    }
  ],
  "con_forces": [
    {
      "name": "力量名称",
      "source": "来自什么理论/直觉/经验",
      "strength": 80,
      "best_argument": "最佳论证（3句话内）",
      "known_weakness": "已知弱点（1句话）"
    }
  ],
  "hidden_forces": [
    {
      "name": "隐藏力量名称",
      "description": "这股力量如何影响思考者但不被察觉"
    }
  ],
  "balance_analysis": "对整体平衡状态的一段话分析"
}

只输出JSON，不要输出其他内容。"""

# 三次独立评分的温度配置（用于取中位数）
_TRIPLE_TEMPERATURES = (0.3, 0.5, 0.7)


def _median_strength(values: list[int]) -> int:
    """取中位数（强度评分用）。"""
    return int(statistics.median(values))


def _build_forces_from_data(data: dict, direction: str) -> list[Force]:
    """从解析后的数据构建 Force 对象列表（用于单次评分）。"""
    key = "pro_forces" if direction == "正方" else "con_forces"
    forces = []
    for f in data.get(key, []):
        forces.append(Force(
            name=f["name"],
            direction=direction,
            source=f["source"],
            strength=f["strength"],
            best_argument=f["best_argument"],
            known_weakness=f["known_weakness"],
        ))
    return forces


def _run_triple_force_analysis(candidate: CandidateQuestion) -> dict:
    """运行三次独立的力量解剖，取强度中位数。"""
    user_msg = f"请对以下认知拉格朗日点问题进行力量解剖：\n\n{candidate.question_text}"

    all_runs = []
    for temp in _TRIPLE_TEMPERATURES:
        data = call_agent_json(FORCE_SYSTEM, user_msg, max_tokens=4096, temperature=temp)
        all_runs.append(data)

    # 以第一次运行的文本字段为基准
    base = all_runs[0]

    # 对每个 strength 取三次中位数
    for side in ("pro_forces", "con_forces"):
        base_forces = base.get(side, [])
        for i, force_base in enumerate(base_forces):
            strengths = [run.get(side, [])[i]["strength"] for run in all_runs if len(run.get(side, [])) > i]
            if len(strengths) == len(_TRIPLE_TEMPERATURES):
                force_base["strength"] = _median_strength(strengths)

    return base


def analyze_forces(candidate: CandidateQuestion, clp_index: int) -> ConfirmedLagrangePoint:
    """对一个通过筛选的候选问题进行力量解剖（三次评分取中位数）。"""
    clp_id = f"CLP-{clp_index+1:03d}"
    print(f"    🔬 力量解剖 {clp_id}: {candidate.question_text[:40]}...", flush=True)

    data = _run_triple_force_analysis(candidate)

    pro_forces = _build_forces_from_data(data, "正方")
    con_forces = _build_forces_from_data(data, "反方")

    pro_total = sum(f.strength for f in pro_forces)
    con_total = sum(f.strength for f in con_forces)
    max_total = max(pro_total, con_total, 1)
    balance_precision = abs(pro_total - con_total) / max_total * 100

    clp = ConfirmedLagrangePoint(
        id=clp_id,
        question_text=candidate.question_text,
        source_candidate=candidate.id,
        pro_forces=pro_forces,
        con_forces=con_forces,
        pro_total=pro_total,
        con_total=con_total,
        balance_precision=round(balance_precision, 1),
        hidden_forces=data.get("hidden_forces", []),
        balance_analysis=data.get("balance_analysis", ""),
    )

    print(
        f"      正方合力: {pro_total} | 反方合力: {con_total} | 平衡精度: {balance_precision:.1f}%",
        flush=True,
    )
    return clp


def run_force_analysis(
    survivors: list[CandidateQuestion],
    existing_confirmed: list[ConfirmedLagrangePoint] | None = None,
    checkpoint_hook=None,
) -> list[ConfirmedLagrangePoint]:
    """对所有存活候选进行力量解剖，支持从断点恢复。"""
    import concurrent.futures

    print(f"\n  🔬 阶段三：力量解剖（{len(survivors)}个确认点）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    confirmed = list(existing_confirmed or [])
    confirmed_by_source = {item.source_candidate: item for item in confirmed}
    next_index = len(confirmed)

    # Filter out already analyzed
    pending = []
    for cand in survivors:
        existing = confirmed_by_source.get(cand.id)
        if existing is not None:
            print(f"    ↺ 跳过 {existing.id}: {cand.id} 已有力量解剖结果", flush=True)
            continue
        pending.append((cand, next_index))
        next_index += 1

    if not pending:
        return confirmed

    # Parallel execution
    PHASE3_WORKERS = int(os.environ.get("CLP_PHASE3_WORKERS", "3"))
    if len(pending) > 1 and PHASE3_WORKERS > 1:
        print(f"  ⚡ 并行解剖 {len(pending)} 个候选（{PHASE3_WORKERS} workers）", flush=True)

        def analyze_one(item):
            cand, idx = item
            return analyze_forces(cand, idx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(PHASE3_WORKERS, len(pending))) as executor:
            futures = {executor.submit(analyze_one, item): item for item in pending}
            for future in concurrent.futures.as_completed(futures):
                clp = future.result()
                confirmed.append(clp)
                confirmed_by_source[clp.source_candidate] = clp
                print(f"  ✓ {clp.id} 完成：{clp.question_text[:30]}...", flush=True)
                if checkpoint_hook is not None:
                    checkpoint_hook(confirmed_override=confirmed)
    else:
        # Sequential
        for cand, idx in pending:
            clp = analyze_forces(cand, idx)
            confirmed.append(clp)
            confirmed_by_source[clp.source_candidate] = clp
            if checkpoint_hook is not None:
                checkpoint_hook(confirmed_override=confirmed)

    print(f"\n  🔬 力量解剖完成：{len(confirmed)} 个认知拉格朗日点已测绘", flush=True)
    return confirmed
