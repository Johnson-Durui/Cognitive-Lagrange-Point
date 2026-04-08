"""认知拉格朗日点 · 阶段二：多框架稳定性筛选（筛子2）"""

import concurrent.futures
import os
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

FILTER_WORKERS = max(1, int(os.environ.get("CLP_FILTER_WORKERS", "7")))
FILTER_RETRY_PASSES = max(1, int(os.environ.get("CLP_FILTER_RETRY_PASSES", "3")))
FILTER_RETRY_BACKOFF = float(os.environ.get("CLP_FILTER_RETRY_BACKOFF", "2"))
FILTER2_BALANCE_THRESHOLD = float(os.environ.get("CLP_FILTER2_BALANCE_THRESHOLD", "20"))
FILTER2_MAX_DIRECTION_SHARE = float(os.environ.get("CLP_FILTER2_MAX_DIRECTION_SHARE", "0.72"))

# 最少需要多少个Agent成功才算有效评估
MIN_VALID_AGENTS = max(1, int(os.environ.get("CLP_MIN_VALID_AGENTS", "4")))


def _normalize_direction(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"正方", "pro", "support", "支持", "赞成", "yes"}:
        return "正方"
    if text in {"反方", "con", "oppose", "反对", "不支持", "no"}:
        return "反方"
    return ""


def _normalize_strength(value: object) -> int | None:
    try:
        strength = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, strength))


def _normalize_stance_result(raw: object, stance_name: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    direction = _normalize_direction(raw.get("lean_direction", raw.get("direction")))
    strength = _normalize_strength(raw.get("lean_strength", raw.get("strength")))
    if not direction or strength is None:
        return None
    return {
        "stance": stance_name,
        "lean_direction": direction,
        "lean_strength": strength,
        "core_argument": str(raw.get("core_argument", raw.get("argument", "")) or "").strip(),
        "self_doubt": str(raw.get("self_doubt", raw.get("weakness", "")) or "").strip(),
    }


def _evaluate_stance(stance_name: str, stance_desc: str, question: str) -> dict:
    """让单个哲学立场Agent评估一个问题。"""
    system = STANCE_SYSTEM.format(stance_name=stance_name, stance_desc=stance_desc)
    user_msg = f"请评估以下问题：\n\n{question}"
    return call_agent_json(system, user_msg, max_tokens=1024)


def _resolve_stances(stances: list[tuple[str, str]] | None) -> list[tuple[str, str]]:
    if not stances:
        return list(STANCES)
    normalized = []
    for name, desc in stances:
        normalized.append((str(name), str(desc)))
    return normalized or list(STANCES)


def _resolve_min_valid_agents(
    stances: list[tuple[str, str]],
    min_valid_agents: int | None,
) -> int:
    total = max(1, len(stances))
    try:
        if min_valid_agents is not None:
            value = int(min_valid_agents)
            return max(1, min(total, value))
    except (TypeError, ValueError):
        pass
    if total >= MIN_VALID_AGENTS:
        return MIN_VALID_AGENTS
    if total <= 2:
        return total
    return max(2, total - 1)


def _normalize_results_order(
    results_by_stance: dict[str, dict],
    stances: list[tuple[str, str]] | None = None,
) -> list[dict]:
    ordered = []
    for stance_name, _ in _resolve_stances(stances):
        if stance_name in results_by_stance:
            ordered.append(results_by_stance[stance_name])
    return ordered


def _evaluate_pending_stances(
    question: str,
    pending_stances: list[tuple[str, str]],
    *,
    worker_limit: int = FILTER_WORKERS,
) -> tuple[dict[str, dict], list[str]]:
    """并发评估尚未成功的立场，返回成功结果和失败名单。"""
    successes: dict[str, dict] = {}
    failed: list[str] = []

    worker_count = min(max(1, worker_limit), len(pending_stances))
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_evaluate_stance, name, desc, question): name
            for name, desc in pending_stances
        }
        for future in concurrent.futures.as_completed(futures):
            stance_name = futures[future]
            try:
                result = future.result()
                normalized = _normalize_stance_result(result, stance_name)
                if normalized is None:
                    print(f"      ⚠ {stance_name} 返回了无效结构，记为失败并等待补跑", flush=True)
                    failed.append(stance_name)
                    continue
                successes[stance_name] = normalized
            except Exception as exc:
                short_err = str(exc)
                if len(short_err) > 80:
                    short_err = short_err[:80]
                print(f"      ⚠ {stance_name} 失败: {short_err}", flush=True)
                failed.append(stance_name)

    return successes, failed


def evaluate_question_balance(
    question: str,
    *,
    cached_results: list | None = None,
    stances: list[tuple[str, str]] | None = None,
    balance_threshold: float | None = None,
    max_direction_share: float | None = None,
    min_valid_agents: int | None = None,
) -> dict:
    """对任意问题运行 7 个哲学立场 Agent，返回平衡评估结果。"""
    selected_stances = _resolve_stances(stances)
    selected_names = {name for name, _ in selected_stances}
    effective_balance_threshold = (
        FILTER2_BALANCE_THRESHOLD if balance_threshold is None else float(balance_threshold)
    )
    effective_max_direction_share = (
        FILTER2_MAX_DIRECTION_SHARE if max_direction_share is None else float(max_direction_share)
    )
    effective_min_valid_agents = _resolve_min_valid_agents(selected_stances, min_valid_agents)

    results_by_stance = {
        item["stance"]: item
        for item in (cached_results or [])
        if isinstance(item, dict) and item.get("stance") in selected_names
    }

    pending = [
        (name, desc)
        for name, desc in selected_stances
        if name not in results_by_stance
    ]

    for round_idx in range(FILTER_RETRY_PASSES):
        if not pending:
            break

        if round_idx > 0:
            delay = FILTER_RETRY_BACKOFF * round_idx
            print(f"      ⟳ 补跑 {len(pending)} 个失败Agent，等待 {delay:.1f}s...", flush=True)
            time.sleep(delay)

        successes, failed_names = _evaluate_pending_stances(question, pending)
        results_by_stance.update(successes)
        pending = [(name, desc) for name, desc in selected_stances if name in failed_names]

    results = _normalize_results_order(results_by_stance, selected_stances)
    valid_count = len(results)

    if valid_count < effective_min_valid_agents:
        return {
            "passed": None,
            "balance_score": -1,
            "distribution": f"{valid_count}/{len(selected_stances)}有效",
            "details": results,
            "valid_count": valid_count,
            "pro_count": sum(1 for r in results if r.get("lean_direction") == "正方"),
            "con_count": sum(1 for r in results if r.get("lean_direction") == "反方"),
            "pro_moment": sum(r.get("lean_strength", 0) for r in results if r.get("lean_direction") == "正方"),
            "con_moment": sum(r.get("lean_strength", 0) for r in results if r.get("lean_direction") == "反方"),
        }

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
    direction_ok = total_valid > 0 and max(pro_count, con_count) / total_valid <= effective_max_direction_share
    balance_ok = balance_score < effective_balance_threshold

    return {
        "passed": direction_ok and balance_ok,
        "balance_score": round(balance_score, 1),
        "distribution": distribution,
        "details": results,
        "valid_count": valid_count,
        "pro_count": pro_count,
        "con_count": con_count,
        "pro_moment": pro_moment,
        "con_moment": con_moment,
    }


def evaluate_candidate(
    candidate: CandidateQuestion,
    *,
    stances: list[tuple[str, str]] | None = None,
    balance_threshold: float | None = None,
    max_direction_share: float | None = None,
    min_valid_agents: int | None = None,
) -> CandidateQuestion:
    """对单个候选问题运行7个哲学立场Agent的评估。"""
    print(f"    ⚖  测试 {candidate.id}: {candidate.question_text[:40]}...", flush=True)
    selected_stances = _resolve_stances(stances)
    selected_names = {name for name, _ in selected_stances}
    effective_min_valid_agents = _resolve_min_valid_agents(selected_stances, min_valid_agents)

    cached_valid = sum(
        1
        for item in candidate.filter_2_details
        if isinstance(item, dict) and item.get("stance") in selected_names
    )
    cached_names = {
        item.get("stance")
        for item in candidate.filter_2_details
        if isinstance(item, dict) and item.get("stance") in selected_names
    }
    if candidate.passed_filter_2 is not None and cached_valid >= effective_min_valid_agents and selected_names.issubset(cached_names):
        print("      ↺ 已有筛选结果，跳过重复调用", flush=True)
        return candidate

    outcome = evaluate_question_balance(
        candidate.question_text,
        cached_results=candidate.filter_2_details,
        stances=selected_stances,
        balance_threshold=balance_threshold,
        max_direction_share=max_direction_share,
        min_valid_agents=effective_min_valid_agents,
    )

    if outcome["passed"] is None:
        print(
            f"      ⚠ 仅{outcome['valid_count']}/{len(selected_stances)}个Agent成功，数据不足，保留断点等待下次补跑",
            flush=True,
        )
        candidate.passed_filter_2 = None
        candidate.filter_2_balance_score = outcome["balance_score"]
        candidate.filter_2_distribution = outcome["distribution"]
        candidate.filter_2_details = outcome["details"]
        return candidate

    candidate.passed_filter_2 = outcome["passed"]
    candidate.filter_2_balance_score = outcome["balance_score"]
    candidate.filter_2_distribution = outcome["distribution"]
    candidate.filter_2_details = outcome["details"]

    status = "✓ 通过" if candidate.passed_filter_2 else "✗ 淘汰"
    print(
        f"      {status} | 分布 {candidate.filter_2_distribution} ({outcome['valid_count']}/{len(selected_stances)}有效) | 平衡度 {candidate.filter_2_balance_score:.1f}%",
        flush=True,
    )

    return candidate


def run_filter2(
    candidates: list[CandidateQuestion],
    checkpoint_hook=None,
) -> list[CandidateQuestion]:
    """对所有候选问题运行筛子2，返回通过的候选。"""
    import concurrent.futures

    print(f"\n  ⚖  筛子2：多框架稳定性测试（{len(candidates)}个候选 × 7个哲学Agent）", flush=True)
    print(f"  {'─' * 60}", flush=True)

    survivors = []

    # Process candidates in parallel
    # Use ThreadPoolExecutor since API calls are I/O-bound and release GIL
    max_workers = int(os.environ.get("CLP_FILTER_CANDIDATE_WORKERS", "4"))

    def process_candidate(cand):
        """Process single candidate, returns (candidate, passed)"""
        evaluate_candidate(cand)
        return cand

    if max_workers > 1 and len(candidates) > 1:
        print(f"  ⚡ 并行处理 {len(candidates)} 个候选（{max_workers} workers）", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_candidate, cand): cand for cand in candidates}
            for future in concurrent.futures.as_completed(futures):
                cand = future.result()
                if checkpoint_hook is not None:
                    checkpoint_hook()
                if cand.passed_filter_2 is True:
                    survivors.append(cand)
                # Progress indicator
                done = len(survivors) + sum(1 for f in futures if f.done())
                print(f"  \r  进度: {done}/{len(candidates)} 已处理 | 通过: {len(survivors)}", flush=True)
    else:
        # Sequential processing
        for cand in candidates:
            process_candidate(cand)
            if checkpoint_hook is not None:
                checkpoint_hook()
            if cand.passed_filter_2 is True:
                survivors.append(cand)

    print(f"\n  ⚖  筛子2结果：{len(survivors)}/{len(candidates)} 个候选通过", flush=True)
    return survivors
