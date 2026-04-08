#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env.clp" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.clp"
  set +a
fi

if [[ -z "${CLP_API_KEY:-}" ]]; then
  echo "缺少 CLP_API_KEY。请先在当前 shell 或 .env.clp 中设置。"
  exit 1
fi

if [[ -z "${CLP_BASE_URL:-}" ]]; then
  echo "提示：未设置 CLP_BASE_URL，将回退到官方 OpenAI 兼容地址。"
fi

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

# 首跑保守配置：先追求稳定拿到第一批真实数据，再逐步放量。
export CLP_RESUME="${CLP_RESUME:-1}"
export CLP_FRESH_START="${CLP_FRESH_START:-0}"
export CLP_MINERS="${CLP_MINERS:-A}"
export CLP_MAX_STAGE2="${CLP_MAX_STAGE2:-6}"
export CLP_MIN_INITIAL_SCORE="${CLP_MIN_INITIAL_SCORE:-60}"
export CLP_ENABLE_FILTER1="${CLP_ENABLE_FILTER1:-0}"
export CLP_ENABLE_FILTER3="${CLP_ENABLE_FILTER3:-0}"
export CLP_ENABLE_STABILITY="${CLP_ENABLE_STABILITY:-0}"
export CLP_ENABLE_OSCILLATION="${CLP_ENABLE_OSCILLATION:-0}"
export CLP_ENABLE_FAULT_LINES="${CLP_ENABLE_FAULT_LINES:-0}"
export CLP_ENABLE_TUNNELS="${CLP_ENABLE_TUNNELS:-0}"
export CLP_ENABLE_SOCIAL_CONFLICTS="${CLP_ENABLE_SOCIAL_CONFLICTS:-0}"
export CLP_FILTER_WORKERS="${CLP_FILTER_WORKERS:-7}"
export CLP_FILTER_RETRY_PASSES="${CLP_FILTER_RETRY_PASSES:-4}"
export CLP_FILTER_CANDIDATE_WORKERS="${CLP_FILTER_CANDIDATE_WORKERS:-4}"
export CLP_MINER_WORKERS="${CLP_MINER_WORKERS:-3}"
export CLP_PHASE3_WORKERS="${CLP_PHASE3_WORKERS:-3}"
export CLP_FILTER_RETRY_BACKOFF="${CLP_FILTER_RETRY_BACKOFF:-2}"
export CLP_MIN_VALID_AGENTS="${CLP_MIN_VALID_AGENTS:-4}"
export CLP_FILTER2_BALANCE_THRESHOLD="${CLP_FILTER2_BALANCE_THRESHOLD:-20}"
export CLP_FILTER2_MAX_DIRECTION_SHARE="${CLP_FILTER2_MAX_DIRECTION_SHARE:-0.72}"
export CLP_API_RETRIES="${CLP_API_RETRIES:-4}"
export CLP_TIMEOUT_SECONDS="${CLP_TIMEOUT_SECONDS:-120}"
export CLP_RETRY_BASE_DELAY="${CLP_RETRY_BASE_DELAY:-1.5}"
export CLP_API_LOG="${CLP_API_LOG:-1}"

if [[ -n "${CLP_MODEL:-}" ]]; then
  PRIMARY_MODEL="$CLP_MODEL"
else
  PRIMARY_MODEL="(未显式设置，代码默认值)"
fi

echo
echo "认知拉格朗日点 · 首跑配置"
echo "  cwd: $ROOT_DIR"
echo "  base_url: ${CLP_BASE_URL:-https://api.openai.com/v1}"
echo "  model: $PRIMARY_MODEL"
echo "  fallbacks: ${CLP_MODEL_FALLBACKS:-<none>}"
echo "  miners: $CLP_MINERS"
echo "  max_stage2: $CLP_MAX_STAGE2"
echo "  enable_filter1: $CLP_ENABLE_FILTER1"
echo "  enable_filter3: $CLP_ENABLE_FILTER3"
echo "  enable_stability: $CLP_ENABLE_STABILITY"
echo "  enable_oscillation: $CLP_ENABLE_OSCILLATION"
echo "  enable_fault_lines: $CLP_ENABLE_FAULT_LINES"
echo "  enable_tunnels: $CLP_ENABLE_TUNNELS"
echo "  enable_social_conflicts: $CLP_ENABLE_SOCIAL_CONFLICTS"
echo "  filter_workers: $CLP_FILTER_WORKERS"
echo "  filter_retry_passes: $CLP_FILTER_RETRY_PASSES"
echo "  filter2_balance_threshold: $CLP_FILTER2_BALANCE_THRESHOLD"
echo "  api_retries: $CLP_API_RETRIES"
echo "  timeout_seconds: $CLP_TIMEOUT_SECONDS"
echo "  resume: $CLP_RESUME"
echo
echo "运行中。断点文件: research/output/checkpoint.json"
echo "诊断日志: research/output/api_diagnostics.jsonl"
echo

python3 -m research.run
