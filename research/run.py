#!/usr/bin/env python3
"""
认知拉格朗日点 · MVP 运行脚本

用法：
  export CLP_API_KEY=sk-...
  export CLP_BASE_URL=https://api.example.com/v1
  python3 -m research.run

可选环境变量：
  CLP_MODEL               使用的主模型（默认 deepseek-v3）
  CLP_MODEL_FALLBACKS     备用模型列表，逗号分隔
  CLP_MINERS              运行哪些矿工，逗号分隔（默认 A；完整版 A,B,C,D,E,F）
  CLP_RESUME              是否从 checkpoint 续跑（默认 1）
  CLP_FRESH_START         是否忽略旧 checkpoint 强制重跑（默认 0）
  CLP_MIN_INITIAL_SCORE   阶段一进入阶段二的最低分（默认 60）
  CLP_MAX_STAGE2          阶段二最多处理多少候选（默认不限）
  CLP_ENABLE_FILTER1      是否启用筛子1：信息注入测试（默认 0）
  CLP_ENABLE_FILTER3      是否启用筛子3：重新表述稳定性测试（默认 0）
  CLP_ENABLE_STABILITY    是否启用阶段三稳定性测试（默认 0）
  CLP_ENABLE_OSCILLATION  是否启用阶段三振荡测量（默认 0）
  CLP_ENABLE_FAULT_LINES  是否启用阶段四断层线识别（默认 0）
  CLP_ENABLE_TUNNELS      是否启用阶段四隧道效应检测（默认 0）
  CLP_ENABLE_SOCIAL_CONFLICTS 是否启用阶段四社会冲突预测（默认 0）
"""

import sys
import time
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.api import QuotaExhaustedError, reset_token_counter, print_token_summary
from research.checkpoint import CHECKPOINT_PATH, load_checkpoint, save_checkpoint
from research.phase1_mining import run_miner
from research.phase2_filter1 import run_filter1
from research.phase2_filter import run_filter2
from research.phase2_filter3 import run_filter3
from research.phase3_analysis import run_force_analysis
from research.phase3_oscillation import run_oscillation_analysis
from research.phase3_stability import run_stability_analysis
from research.phase4_fault_lines import run_fault_line_analysis
from research.phase4_social_conflicts import run_social_conflict_analysis
from research.phase4_tunnel_effects import run_tunnel_effect_analysis
from research.output_formatter import save_results, generate_data_js, generate_pdf


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _candidate_survives_pipeline(candidate, enable_filter1: bool, enable_filter3: bool) -> bool:
    if not candidate.selected_for_pipeline:
        return False
    if enable_filter1 and candidate.passed_filter_1 is not True:
        return False
    if candidate.passed_filter_2 is not True:
        return False
    if enable_filter3 and candidate.passed_filter_3 is not True:
        return False
    return True


def _rebuild_survivors(candidates, enable_filter1: bool, enable_filter3: bool):
    return [
        cand for cand in candidates
        if _candidate_survives_pipeline(cand, enable_filter1, enable_filter3)
    ]


def _select_top_candidates(candidates):
    threshold = int(os.environ.get("CLP_MIN_INITIAL_SCORE", "60"))
    max_stage2_raw = os.environ.get("CLP_MAX_STAGE2", "").strip()
    max_stage2 = int(max_stage2_raw) if max_stage2_raw else None

    for candidate in candidates:
        candidate.selected_for_pipeline = False

    ordered = sorted(candidates, key=lambda item: item.initial_score, reverse=True)
    selected = [cand for cand in ordered if cand.initial_score >= threshold]
    if len(selected) < 5:
        selected = ordered[:10]
    if max_stage2 is not None:
        selected = selected[:max_stage2]
    for candidate in selected:
        candidate.selected_for_pipeline = True
    return selected


def _pipeline_metadata(
    enable_filter1: bool,
    enable_filter3: bool,
    enable_stability: bool,
    enable_oscillation: bool,
    enable_fault_lines: bool,
    enable_tunnels: bool,
    enable_social_conflicts: bool,
) -> dict:
    return {
        "model": os.environ.get("CLP_MODEL", "deepseek-v3"),
        "base_url": os.environ.get("CLP_BASE_URL", "https://api.openai.com/v1"),
        "enable_filter1": enable_filter1,
        "enable_filter3": enable_filter3,
        "enable_stability": enable_stability,
        "enable_oscillation": enable_oscillation,
        "enable_fault_lines": enable_fault_lines,
        "enable_tunnels": enable_tunnels,
        "enable_social_conflicts": enable_social_conflicts,
        "min_initial_score": int(os.environ.get("CLP_MIN_INITIAL_SCORE", "60")),
        "max_stage2": os.environ.get("CLP_MAX_STAGE2", ""),
        "miners": os.environ.get("CLP_MINERS", "A"),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    start = time.time()
    resume_enabled = _env_flag("CLP_RESUME", True)
    fresh_start = _env_flag("CLP_FRESH_START", False)
    enable_filter1 = _env_flag("CLP_ENABLE_FILTER1", False)
    enable_filter3 = _env_flag("CLP_ENABLE_FILTER3", False)
    enable_stability = _env_flag("CLP_ENABLE_STABILITY", False)
    enable_oscillation = _env_flag("CLP_ENABLE_OSCILLATION", False)
    enable_fault_lines = _env_flag("CLP_ENABLE_FAULT_LINES", False)
    enable_tunnels = _env_flag("CLP_ENABLE_TUNNELS", False)
    enable_social_conflicts = _env_flag("CLP_ENABLE_SOCIAL_CONFLICTS", False)

    print()
    print("🌌 ══════════════════════════════════════════════════")
    print("   认知拉格朗日点 · 寻找人类思维的永恒僵局")
    print("   MVP 实验运行")
    print("══════════════════════════════════════════════════════")
    print()

    reset_token_counter()

    all_candidates = []
    survivors = []
    confirmed = []
    fault_lines = []
    tunnel_effects = []
    social_conflict_predictions = []
    key_discoveries = []
    completed_miners = set()
    checkpoint_created_at = None
    unexpected_error = None

    if resume_enabled and not fresh_start:
        checkpoint = load_checkpoint()
        if checkpoint is not None:
            checkpoint_created_at = checkpoint.get("created_at")
            all_candidates = checkpoint.get("candidates", [])
            confirmed = checkpoint.get("confirmed", [])
            fault_lines = checkpoint.get("fault_lines", [])
            tunnel_effects = checkpoint.get("tunnel_effects", [])
            social_conflict_predictions = checkpoint.get("social_conflict_predictions", [])
            key_discoveries = checkpoint.get("key_discoveries", [])
            completed_miners = set(checkpoint.get("completed_miners", []))
            survivors = _rebuild_survivors(all_candidates, enable_filter1, enable_filter3)
            print("  ↺ 已加载断点文件")
            print(f"    checkpoint: {CHECKPOINT_PATH}")
            print(f"    已完成矿工: {', '.join(sorted(completed_miners)) or '无'}")
            print(f"    已有候选: {len(all_candidates)} | 已过筛: {len(survivors)} | 已解剖: {len(confirmed)}")
            print()

    def persist_checkpoint(
        *,
        confirmed_override=None,
        fault_lines_override=None,
        tunnel_effects_override=None,
        social_conflict_predictions_override=None,
        key_discoveries_override=None,
    ):
        save_checkpoint(
            all_candidates,
            confirmed_override if confirmed_override is not None else confirmed,
            fault_lines=(
                fault_lines_override if fault_lines_override is not None else fault_lines
            ),
            tunnel_effects=(
                tunnel_effects_override if tunnel_effects_override is not None else tunnel_effects
            ),
            social_conflict_predictions=(
                social_conflict_predictions_override
                if social_conflict_predictions_override is not None
                else social_conflict_predictions
            ),
            key_discoveries=(
                key_discoveries_override if key_discoveries_override is not None else key_discoveries
            ),
            completed_miners=sorted(completed_miners),
            metadata=_pipeline_metadata(
                enable_filter1,
                enable_filter3,
                enable_stability,
                enable_oscillation,
                enable_fault_lines,
                enable_tunnels,
                enable_social_conflicts,
            ),
            created_at=checkpoint_created_at,
        )

    try:
        # ── 阶段一：候选生成 ──
        print("━━ 阶段一：候选问题生成 ━━")
        miner_ids = os.environ.get("CLP_MINERS", "A").split(",")

        # 并行执行多个矿工
        MINER_WORKERS = int(os.environ.get("CLP_MINER_WORKERS", "3"))
        pending_miners = [mid.strip() for mid in miner_ids if mid.strip() and mid.strip() not in completed_miners]

        if len(pending_miners) > 1 and MINER_WORKERS > 1:
            import concurrent.futures
            print(f"  ⚡ 并行执行 {len(pending_miners)} 个矿工（{MINER_WORKERS} workers）", flush=True)

            def run_single_miner(mid):
                return mid, run_miner(mid)

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(MINER_WORKERS, len(pending_miners))) as executor:
                futures = {executor.submit(run_single_miner, mid): mid for mid in pending_miners}
                for future in concurrent.futures.as_completed(futures):
                    mid, candidates = future.result()
                    all_candidates.extend(candidates)
                    completed_miners.add(mid)
                    print(f"  ✓ 矿工{mid}完成：+{len(candidates)}个候选", flush=True)
                    persist_checkpoint()
        else:
            # Sequential
            for mid in pending_miners:
                if mid in completed_miners:
                    print(f"  ↺ 跳过矿工{mid}：断点中已有结果")
                    continue
                candidates = run_miner(mid)
                all_candidates.extend(candidates)
                completed_miners.add(mid)
                persist_checkpoint()

        print(f"\n  共生成 {len(all_candidates)} 个候选问题")

        top_candidates = _select_top_candidates(all_candidates)
        threshold = int(os.environ.get("CLP_MIN_INITIAL_SCORE", "60"))
        print(f"  预筛选后保留 {len(top_candidates)} 个候选（初始评分>={threshold}）")
        persist_checkpoint()

        pipeline_candidates = top_candidates

        if enable_filter1:
            print("\n━━ 阶段二-筛子1：信息注入测试 ━━")
            pipeline_candidates = run_filter1(pipeline_candidates, checkpoint_hook=persist_checkpoint)
            persist_checkpoint()
            if not pipeline_candidates:
                print("\n  ⚠ 没有候选通过筛子1。")

        if pipeline_candidates:
            print("\n━━ 阶段二-筛子2：多框架稳定性筛选 ━━")
            pipeline_candidates = run_filter2(pipeline_candidates, checkpoint_hook=persist_checkpoint)
            persist_checkpoint()
            if not pipeline_candidates:
                print("\n  ⚠ 没有候选通过筛子2。")

        if pipeline_candidates and enable_filter3:
            print("\n━━ 阶段二-筛子3：重新表述稳定性测试 ━━")
            pipeline_candidates = run_filter3(pipeline_candidates, checkpoint_hook=persist_checkpoint)
            persist_checkpoint()
            if not pipeline_candidates:
                print("\n  ⚠ 没有候选通过筛子3。")

        survivors = pipeline_candidates

        if not survivors:
            print("\n  ⚠ 没有候选通过筛选！")
            print("  这可能意味着：")
            print("    1. 筛选标准过严（可调整平衡度阈值）")
            print("    2. 需要更多矿工搜索更广的维度")
            print("    3. 此次运行的随机性导致（建议重试）")
        else:
            # ── 阶段三：力量解剖 ──
            print("\n━━ 阶段三：力量解剖 ━━")
            confirmed = run_force_analysis(
                survivors,
                existing_confirmed=confirmed,
                checkpoint_hook=persist_checkpoint,
            )
            persist_checkpoint()

            if confirmed and enable_stability:
                print("\n━━ 阶段三-稳定性测试 ━━")
                confirmed = run_stability_analysis(
                    confirmed,
                    checkpoint_hook=persist_checkpoint,
                )
                persist_checkpoint()

            if confirmed and enable_oscillation:
                print("\n━━ 阶段三-振荡测量 ━━")
                confirmed = run_oscillation_analysis(
                    confirmed,
                    checkpoint_hook=persist_checkpoint,
                )
                persist_checkpoint()

            if confirmed and enable_fault_lines:
                print("\n━━ 阶段四-断层线识别 ━━")
                fault_lines = run_fault_line_analysis(
                    confirmed,
                    existing_fault_lines=fault_lines,
                    checkpoint_hook=persist_checkpoint,
                )
                persist_checkpoint()

            if confirmed and enable_tunnels:
                print("\n━━ 阶段四-隧道效应检测 ━━")
                tunnel_effects = run_tunnel_effect_analysis(
                    confirmed,
                    existing_tunnel_effects=tunnel_effects,
                    checkpoint_hook=persist_checkpoint,
                )
                persist_checkpoint()

            if confirmed and enable_social_conflicts:
                print("\n━━ 阶段四-社会冲突预测 ━━")
                social_conflict_predictions, key_discoveries = run_social_conflict_analysis(
                    confirmed,
                    fault_lines,
                    tunnel_effects,
                    existing_predictions=social_conflict_predictions,
                    existing_key_discoveries=key_discoveries,
                    checkpoint_hook=persist_checkpoint,
                )
                persist_checkpoint()

    except QuotaExhaustedError:
        print("\n")
        print("  ⛔ API额度已耗尽！保存已有结果...")
        print()

    except KeyboardInterrupt:
        print("\n\n  ⏸  用户中断，保存已有结果...")

    except Exception as exc:
        unexpected_error = exc
        print(f"\n  💥 运行出现未处理异常：{type(exc).__name__}: {exc}")
        print("  已先保存断点与当前结果。")

    # ── 保存结果（无论是否完成） ──
    print("\n━━ 保存结果 ━━")
    persist_checkpoint()
    survivors = _rebuild_survivors(all_candidates, enable_filter1, enable_filter3)
    save_results(
        all_candidates,
        survivors,
        confirmed,
        fault_lines=fault_lines,
        tunnel_effects=tunnel_effects,
        social_conflict_predictions=social_conflict_predictions,
        key_discoveries=key_discoveries,
        metadata=_pipeline_metadata(
            enable_filter1,
            enable_filter3,
            enable_stability,
            enable_oscillation,
            enable_fault_lines,
            enable_tunnels,
            enable_social_conflicts,
        ),
    )
    generate_data_js(confirmed)

    # ── 生成 PDF 报告 ──
    generate_pdf(
        confirmed,
        fault_lines=fault_lines,
        tunnel_effects=tunnel_effects,
        social_conflict_predictions=social_conflict_predictions,
        metadata=_pipeline_metadata(
            enable_filter1,
            enable_filter3,
            enable_stability,
            enable_oscillation,
            enable_fault_lines,
            enable_tunnels,
            enable_social_conflicts,
        ),
    )

    # ── Token 消耗 ──
    print_token_summary()

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

    if unexpected_error is not None:
        raise unexpected_error


if __name__ == "__main__":
    main()
