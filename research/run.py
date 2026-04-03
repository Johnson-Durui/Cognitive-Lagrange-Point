#!/usr/bin/env python3
"""
认知拉格朗日点 · MVP 运行脚本

用法：
  export ANTHROPIC_API_KEY=sk-...
  export ANTHROPIC_BASE_URL=https://api.favorais.com
  python3 -m research.run

可选环境变量：
  CLP_MODEL    使用的模型（默认 claude-sonnet-4-6）
  CLP_MINERS   运行哪些矿工，逗号分隔（默认 A；完整版 A,B,C,D,E,F）
"""

import sys
import time
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.api import QuotaExhaustedError
from research.phase1_mining import run_miner
from research.phase2_filter import run_filter2
from research.phase3_analysis import run_force_analysis
from research.output_formatter import save_results, generate_data_js


def main():
    start = time.time()

    print()
    print("🌌 ══════════════════════════════════════════════════")
    print("   认知拉格朗日点 · 寻找人类思维的永恒僵局")
    print("   MVP 实验运行")
    print("══════════════════════════════════════════════════════")
    print()

    all_candidates = []
    survivors = []
    confirmed = []

    try:
        # ── 阶段一：候选生成 ──
        print("━━ 阶段一：候选问题生成 ━━")
        miner_ids = os.environ.get("CLP_MINERS", "A").split(",")

        for mid in miner_ids:
            mid = mid.strip()
            candidates = run_miner(mid)
            all_candidates.extend(candidates)

        print(f"\n  共生成 {len(all_candidates)} 个候选问题")

        # 按初始评分排序，取 top 候选（MVP优化：只取评分>=60的）
        all_candidates.sort(key=lambda c: c.initial_score, reverse=True)
        top_candidates = [c for c in all_candidates if c.initial_score >= 60]
        if len(top_candidates) < 5:
            top_candidates = all_candidates[:10]
        print(f"  预筛选后保留 {len(top_candidates)} 个候选（初始评分>=60）")

        # ── 阶段二：多框架筛选 ──
        print("\n━━ 阶段二：多框架稳定性筛选 ━━")
        survivors = run_filter2(top_candidates)

        if not survivors:
            print("\n  ⚠ 没有候选通过筛选！")
            print("  这可能意味着：")
            print("    1. 筛选标准过严（可调整平衡度阈值）")
            print("    2. 需要更多矿工搜索更广的维度")
            print("    3. 此次运行的随机性导致（建议重试）")
        else:
            # ── 阶段三：力量解剖 ──
            print("\n━━ 阶段三：力量解剖 ━━")
            confirmed = run_force_analysis(survivors)

    except QuotaExhaustedError:
        print("\n")
        print("  ⛔ API额度已耗尽！保存已有结果...")
        print()

    except KeyboardInterrupt:
        print("\n\n  ⏸  用户中断，保存已有结果...")

    # ── 保存结果（无论是否完成） ──
    print("\n━━ 保存结果 ━━")
    save_results(all_candidates, survivors, confirmed)
    if confirmed:
        generate_data_js(confirmed)

    # ── 总结 ──
    elapsed = time.time() - start
    print()
    print("🌌 ══════════════════════════════════════════════════")
    print(f"   实验{'完成' if confirmed else '部分完成'}！")
    print(f"   候选问题：{len(all_candidates)}")
    print(f"   通过筛选：{len(survivors)}")
    print(f"   确认拉格朗日点：{len(confirmed)}")
    print(f"   用时：{elapsed:.0f}秒")
    print("══════════════════════════════════════════════════════")
    print()

    for clp in confirmed:
        print(f"  ★ {clp.id}: {clp.question_text[:60]}...")
        print(f"    平衡精度: {clp.balance_precision}%")
        print()


if __name__ == "__main__":
    main()
