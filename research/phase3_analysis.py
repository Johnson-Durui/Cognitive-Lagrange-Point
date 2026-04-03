"""认知拉格朗日点 · 阶段三：力量解剖"""

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


def analyze_forces(candidate: CandidateQuestion, clp_index: int) -> ConfirmedLagrangePoint:
    """对一个通过筛选的候选问题进行力量解剖。"""
    clp_id = f"CLP-{clp_index+1:03d}"
    print(f"    🔬 力量解剖 {clp_id}: {candidate.question_text[:40]}...")

    user_msg = f"请对以下认知拉格朗日点问题进行力量解剖：\n\n{candidate.question_text}"
    data = call_agent_json(FORCE_SYSTEM, user_msg, max_tokens=4096)

    pro_forces = []
    for f in data.get("pro_forces", []):
        pro_forces.append(Force(
            name=f["name"],
            direction="正方",
            source=f["source"],
            strength=f["strength"],
            best_argument=f["best_argument"],
            known_weakness=f["known_weakness"],
        ))

    con_forces = []
    for f in data.get("con_forces", []):
        con_forces.append(Force(
            name=f["name"],
            direction="反方",
            source=f["source"],
            strength=f["strength"],
            best_argument=f["best_argument"],
            known_weakness=f["known_weakness"],
        ))

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
    )

    print(f"      正方合力: {pro_total} | 反方合力: {con_total} | 平衡精度: {balance_precision:.1f}%")
    return clp


def run_force_analysis(survivors: list[CandidateQuestion]) -> list[ConfirmedLagrangePoint]:
    """对所有存活候选进行力量解剖。"""
    print(f"\n  🔬 阶段三：力量解剖（{len(survivors)}个确认点）")
    print(f"  {'─' * 60}")

    confirmed = []
    for i, cand in enumerate(survivors):
        clp = analyze_forces(cand, i)
        confirmed.append(clp)

    print(f"\n  🔬 力量解剖完成：{len(confirmed)} 个认知拉格朗日点已测绘")
    return confirmed
