"""认知拉格朗日点 · 阶段二：多框架稳定性筛选（筛子2）"""

import concurrent.futures
import time
from .api import call_agent_json
from .models import CandidateQuestion

STANCES = [
    ("功利主义者", "你坚信行为的正确性完全取决于其后果。最大化总体幸福是唯一的道德标准。"),
    ("义务论者", "你坚信某些行为本身就是对或错的，与后果无关。道德规则是绝对的。"),
    ("自由主义者", "你坚信个人自由和权利至上。任何限制个人自由的行为都需要极强的正当理由。"),
    ("社群主义者", "你坚信个人身份和价值根植于社群。集体利益和传统的重要性优先于抽象的个人权利。"),
    ("实用主义者", "你不关心抽象原则，只关心什么在实践中行得通。理论必须接受现实的检验。"),
    ("虚无主义者", "你认为不存在客观的道德真理。所有价值体系都是人为建构。但你仍然可以分析论证的力量。"),
    ("关怀伦理者", "你坚信道德的核心是关系和关怀。抽象原则必须让位于具体情境中对具体他人的责任。"),
]

STANCE_SYSTEM = """你是一个坚定的{stance_name}。{stance_desc}

请基于你的核心哲学立场，对以下问题给出你的立场。

请以JSON格式输出：
{{
  "lean_direction": "正方或反方",
  "lean_strength": 75,
  "core_argument": "用3句话说明你的理由",
  "self_doubt": "你自己论证中最薄弱的环节"
}}

注意：
- "正方"表示你倾向于问题描述中隐含的第一种立场（即"应该"的一方）
- "反方"表示你倾向于问题描述中隐含的对立立场（即"不应该"的一方）
- lean_strength是0-100的整数，100表示绝对确信
- 如果你真的无法决定，lean_strength可以是50，但要解释为什么
- lean_direction必须是"正方"或"反方"二选一

只输出JSON对象，不要输出其他任何内容。"""

# 最少需要多少个Agent成功才算有效评估
MIN_VALID_AGENTS = 4


def _evaluate_stance(stance_name: str, stance_desc: str, question: str) -> dict:
    """让单个哲学立场Agent评估一个问题。"""
    system = STANCE_SYSTEM.format(stance_name=stance_name, stance_desc=stance_desc)
    user_msg = f"请评估以下问题：\n\n{question}"
    return call_agent_json(system, user_msg, max_tokens=1024)


def evaluate_candidate(candidate: CandidateQuestion) -> CandidateQuestion:
    """对单个候选问题运行7个哲学立场Agent的评估。"""
    print(f"    ⚖  测试 {candidate.id}: {candidate.question_text[:40]}...")

    results = []
    # 降低并发到3，减少中转站空响应
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for name, desc in STANCES:
            f = executor.submit(_evaluate_stance, name, desc, candidate.question_text)
            futures[f] = name

        for future in concurrent.futures.as_completed(futures):
            stance_name = futures[future]
            try:
                result = future.result()
                result["stance"] = stance_name
                results.append(result)
            except Exception as e:
                err_msg = str(e)
                # 只打印简短错误
                short_err = err_msg[:80] if len(err_msg) > 80 else err_msg
                print(f"      ⚠ {stance_name} 失败: {short_err}")
                continue

    valid_count = len(results)

    # 如果成功的Agent太少，标记为无效
    if valid_count < MIN_VALID_AGENTS:
        print(f"      ⚠ 仅{valid_count}/{len(STANCES)}个Agent成功，数据不足，标记为待重试")
        candidate.passed_filter_2 = None  # None = 无效，需重试
        candidate.filter_2_balance_score = -1
        candidate.filter_2_distribution = f"{valid_count}/7有效"
        candidate.filter_2_details = results
        return candidate

    # 计算力矩
    pro_count = sum(1 for r in results if r.get("lean_direction") == "正方")
    con_count = sum(1 for r in results if r.get("lean_direction") == "反方")
    pro_moment = sum(r.get("lean_strength", 0) for r in results if r.get("lean_direction") == "正方")
    con_moment = sum(r.get("lean_strength", 0) for r in results if r.get("lean_direction") == "反方")

    max_moment = max(pro_moment, con_moment, 1)
    balance_score = abs(pro_moment - con_moment) / max_moment * 100

    distribution = f"{pro_count}:{con_count}"

    # 判定（按有效Agent比例调整阈值）
    total_valid = pro_count + con_count
    direction_ok = total_valid > 0 and max(pro_count, con_count) / total_valid <= 0.72  # 不超过约5:2
    balance_ok = balance_score < 20  # 稍微放宽到20%

    candidate.passed_filter_2 = direction_ok and balance_ok
    candidate.filter_2_balance_score = round(balance_score, 1)
    candidate.filter_2_distribution = distribution
    candidate.filter_2_details = results

    status = "✓ 通过" if candidate.passed_filter_2 else "✗ 淘汰"
    print(f"      {status} | 分布 {distribution} ({valid_count}/7有效) | 平衡度 {balance_score:.1f}%")

    return candidate


def run_filter2(candidates: list[CandidateQuestion]) -> list[CandidateQuestion]:
    """对所有候选问题运行筛子2，返回通过的候选。"""
    print(f"\n  ⚖  筛子2：多框架稳定性测试（{len(candidates)}个候选 × 7个哲学Agent）")
    print(f"  {'─' * 60}")

    survivors = []
    retry_queue = []

    for cand in candidates:
        evaluate_candidate(cand)
        if cand.passed_filter_2 is True:
            survivors.append(cand)
        elif cand.passed_filter_2 is None:
            retry_queue.append(cand)

    # 重试失败的候选（一次）
    if retry_queue:
        print(f"\n  ⟳ 重试 {len(retry_queue)} 个数据不足的候选...")
        time.sleep(2)  # 给中转站一点喘息时间
        for cand in retry_queue:
            cand.passed_filter_2 = None  # reset
            evaluate_candidate(cand)
            if cand.passed_filter_2 is True:
                survivors.append(cand)

    print(f"\n  ⚖  筛子2结果：{len(survivors)}/{len(candidates)} 个候选通过")
    return survivors
