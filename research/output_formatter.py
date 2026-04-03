"""认知拉格朗日点 · 输出格式化"""

import json
import os
from .models import ConfirmedLagrangePoint, CandidateQuestion

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def format_clp_card(clp: ConfirmedLagrangePoint) -> str:
    """生成单个拉格朗日点的文本卡片。"""
    lines = []
    lines.append("╔" + "═" * 65 + "╗")
    lines.append(f"║ 认知拉格朗日点 #{clp.id:<54}║")
    lines.append("║" + " " * 65 + "║")
    # 问题文本（自动换行）
    q = clp.question_text
    while q:
        chunk = q[:55]
        q = q[55:]
        lines.append(f"║   {chunk:<62}║")
    lines.append("║" + " " * 65 + "║")

    # 力量解剖
    lines.append(f"║ 力量解剖：{' ' * 54}║")
    lines.append(f"║   → 正方力量（合成：{clp.pro_total}）{' ' * (43 - len(str(clp.pro_total)))}║")
    for f in clp.pro_forces:
        name_str = f"     ├── {f.name} (强度:{f.strength}%)"
        lines.append(f"║{name_str:<65}║")
    lines.append(f"║   → 反方力量（合成：{clp.con_total}）{' ' * (43 - len(str(clp.con_total)))}║")
    for f in clp.con_forces:
        name_str = f"     ├── {f.name} (强度:{f.strength}%)"
        lines.append(f"║{name_str:<65}║")
    lines.append(f"║   平衡精度：{clp.balance_precision}%{' ' * (50 - len(str(clp.balance_precision)))}║")
    lines.append("║" + " " * 65 + "║")
    lines.append("╚" + "═" * 65 + "╝")
    return "\n".join(lines)


def save_results(
    candidates: list[CandidateQuestion],
    survivors: list[CandidateQuestion],
    confirmed: list[ConfirmedLagrangePoint],
):
    """保存所有结果到文件。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 完整JSON数据
    data = {
        "version": "MVP-0.1",
        "total_candidates": len(candidates),
        "filter2_survivors": len(survivors),
        "confirmed_points": len(confirmed),
        "candidates": [
            {
                "id": c.id,
                "question": c.question_text,
                "miner": c.miner_source,
                "rationale": c.balance_rationale,
                "score": c.initial_score,
                "passed_filter2": c.passed_filter_2,
                "filter2_balance": c.filter_2_balance_score,
                "filter2_dist": c.filter_2_distribution,
            }
            for c in candidates
        ],
        "confirmed": [
            {
                "id": clp.id,
                "question": clp.question_text,
                "source": clp.source_candidate,
                "pro_forces": [
                    {"name": f.name, "source": f.source, "strength": f.strength,
                     "argument": f.best_argument, "weakness": f.known_weakness}
                    for f in clp.pro_forces
                ],
                "con_forces": [
                    {"name": f.name, "source": f.source, "strength": f.strength,
                     "argument": f.best_argument, "weakness": f.known_weakness}
                    for f in clp.con_forces
                ],
                "pro_total": clp.pro_total,
                "con_total": clp.con_total,
                "balance_precision": clp.balance_precision,
            }
            for clp in confirmed
        ],
    }

    json_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📄 JSON数据已保存: {json_path}")

    # 2. 可读文本报告
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  人类认知断层线地图 v0.1（MVP）")
    report_lines.append("  认知拉格朗日点 · 寻找人类思维的永恒僵局")
    report_lines.append("=" * 70)
    report_lines.append("")
    report_lines.append(f"  候选问题总数：{len(candidates)}")
    report_lines.append(f"  筛子2存活数：{len(survivors)}")
    report_lines.append(f"  确认拉格朗日点：{len(confirmed)}")
    report_lines.append("")
    report_lines.append("─" * 70)
    report_lines.append("  一、确认的认知拉格朗日点")
    report_lines.append("─" * 70)
    report_lines.append("")

    for clp in confirmed:
        report_lines.append(format_clp_card(clp))
        report_lines.append("")
        # 详细力量
        report_lines.append("  正方力量详解：")
        for f in clp.pro_forces:
            report_lines.append(f"    [{f.name}] 强度:{f.strength} 来源:{f.source}")
            report_lines.append(f"      论证: {f.best_argument}")
            report_lines.append(f"      弱点: {f.known_weakness}")
        report_lines.append("")
        report_lines.append("  反方力量详解：")
        for f in clp.con_forces:
            report_lines.append(f"    [{f.name}] 强度:{f.strength} 来源:{f.source}")
            report_lines.append(f"      论证: {f.best_argument}")
            report_lines.append(f"      弱点: {f.known_weakness}")
        report_lines.append("")
        report_lines.append("─" * 70)
        report_lines.append("")

    # 3. 被淘汰的候选（简表）
    report_lines.append("  二、被淘汰的候选问题")
    report_lines.append("─" * 70)
    eliminated = [c for c in candidates if not c.passed_filter_2]
    for c in eliminated:
        report_lines.append(f"  ✗ {c.id} | 分布{c.filter_2_distribution} | 平衡度{c.filter_2_balance_score}%")
        report_lines.append(f"    {c.question_text[:60]}...")
    report_lines.append("")
    report_lines.append("=" * 70)

    report_path = os.path.join(OUTPUT_DIR, "report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"  📋 文本报告已保存: {report_path}")


def generate_data_js(confirmed: list[ConfirmedLagrangePoint]):
    """将确认的拉格朗日点转换为前端data.js格式，更新星图数据。"""
    import math

    # 为确认的点分配系统和轨道参数
    # 按力量解剖中的主题自动分组（MVP简化：全部放入一个新系统）
    nodes_js = []
    for i, clp in enumerate(confirmed):
        angle = (2 * math.pi * i) / max(len(confirmed), 1)
        # 从力量中提取张力对
        pro_name = clp.pro_forces[0].name if clp.pro_forces else "正方"
        con_name = clp.con_forces[0].name if clp.con_forces else "反方"

        # 截取问题的核心作为name（取第一个问号前的部分或前15字）
        q = clp.question_text
        name = q[:15].rstrip("，。、？") if len(q) > 15 else q
        # 英文subtitle
        subtitle = f"CLP #{clp.id}"

        # 从问题中提取一句话作为question
        question_text = q if len(q) <= 80 else q[:80] + "..."

        # body保留完整问题
        body = clp.question_text
        if clp.pro_forces and clp.con_forces:
            body += f"\n\n正方核心力量：{clp.pro_forces[0].best_argument}"
            body += f"\n\n反方核心力量：{clp.con_forces[0].best_argument}"
            body += f"\n\n平衡精度：{clp.balance_precision}%"

        node = {
            "name": name,
            "subtitle": subtitle,
            "angle": round(angle, 2),
            "distance": 170 + (i % 3) * 15,
            "orbitSpeed": 0.05 + (i % 4) * 0.01,
            "tension": [pro_name, con_name],
            "question": question_text,
            "body": body,
        }
        nodes_js.append(node)

    # 如果有结果，生成一个新的 system 追加到 data.js
    if not nodes_js:
        print("  ⚠ 没有确认的拉格朗日点，跳过data.js生成")
        return

    # 保存为独立的JSON，供前端可选加载
    new_system = {
        "id": "discovered",
        "name": "新发现的认知拉格朗日点",
        "nameEn": "Discovered Lagrange Points",
        "color": [255, 107, 107],
        "position": {"x": 0, "y": 0},
        "nodes": nodes_js,
    }

    discovered_path = os.path.join(OUTPUT_DIR, "discovered_system.json")
    with open(discovered_path, "w", encoding="utf-8") as f:
        json.dump(new_system, f, ensure_ascii=False, indent=2)
    print(f"  🌟 星图数据已保存: {discovered_path}")
    print(f"     可将此数据追加到 data.js 的 SYSTEMS 数组中")
