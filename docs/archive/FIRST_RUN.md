# 首次 MVP 运行说明

这个入口的目标不是一次性跑满规格书，而是先用最保守的参数拿到第一批真实数据，并确保中途失败后可以续跑。

## 运行前

在当前 shell 里设置这些环境变量，或者写到根目录的 `.env.clp`：

```bash
export CLP_API_KEY="你的 key"
export CLP_BASE_URL="你的 OpenAI 兼容中转地址"
export CLP_MODEL="你最稳定、额度最够的模型"
export CLP_MODEL_FALLBACKS="备用模型1,备用模型2"
```

如果你暂时不确定模型，建议先只设置一个你确认能用的主模型，再逐步补 fallback。

## 启动

```bash
./run-first-mvp.sh
```

这个脚本默认使用以下保守参数：

- `CLP_MINERS=A`
- `CLP_MAX_STAGE2=6`
- `CLP_ENABLE_FILTER1=0`
- `CLP_ENABLE_FILTER3=0`
- `CLP_ENABLE_STABILITY=0`
- `CLP_ENABLE_OSCILLATION=0`
- `CLP_ENABLE_FAULT_LINES=0`
- `CLP_ENABLE_TUNNELS=0`
- `CLP_ENABLE_SOCIAL_CONFLICTS=0`
- `CLP_FILTER_WORKERS=1`
- `CLP_FILTER_RETRY_PASSES=4`
- `CLP_FILTER2_BALANCE_THRESHOLD=20`
- `CLP_API_RETRIES=4`
- `CLP_TIMEOUT_SECONDS=120`
- `CLP_RESUME=1`

## 看哪里

首跑时重点看这几个文件：

- `research/output/checkpoint.json`
- `research/output/api_diagnostics.jsonl`
- `research/output/results.json`
- `research/output/report.txt`
- `discovered-data.js`

## 什么时候放量

满足下面三个条件后，再考虑把 `CLP_MAX_STAGE2` 提高到 `10` 或把 `CLP_MINERS` 扩到 `A,B`：

1. 阶段二大部分 Agent 不再频繁空响应。
2. `checkpoint.json` 能稳定续跑，不会反复从头开始。
3. 你已经确认当前中转站不会在一次首跑里很快耗尽额度。

如果要切换到“更接近完整规格书”的模式，再逐步打开：

- `CLP_ENABLE_FILTER1=1`
- `CLP_ENABLE_FILTER3=1`
- `CLP_ENABLE_STABILITY=1`
- `CLP_ENABLE_OSCILLATION=1`
- `CLP_ENABLE_FAULT_LINES=1`
- `CLP_ENABLE_TUNNELS=1`
- `CLP_ENABLE_SOCIAL_CONFLICTS=1`
