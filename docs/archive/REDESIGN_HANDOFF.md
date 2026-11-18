# 认知拉格朗日点 · 产品重构交接文件

> **日期**: 2026-04-08
> **目标**: 从"研究平台"重构为"两难决策 AI 助手"，保留星图作为决策画布
> **核心理念**: 帮用户做最不后悔的选择

---

## 一、产品愿景

### 用户故事
> "我正在纠结要不要辞职去创业。我不知道该怎么选。"

用户打开应用 → 输入问题 → 选择思考深度 → AI 分析 → 获得推荐 + 行动路线图 + 未来模拟 → 决策永久记录在个人星图上。

### 三个核心原则
1. **为决策服务**：每一行代码都服务于"帮用户做选择"这一件事
2. **星图即画布**：星图不是装饰，而是贯穿全程的交互层
3. **深度分级**：用户自选投入多少 AI 算力

### 当前真实进度（截至 2026-04-07 下午）

这份文件最早偏“目标设计稿”。为了方便接手，这里补一份基于当前仓库和本轮复核结果的真实状态：

| 模块 | 当前状态 |
|---|---|
| 后端框架 | **FastAPI + Uvicorn 已正式落地**，`lifespan` 已挂上，`4173` 为主入口，静态资源已加 `no-store` 防缓存 |
| 产品协议 | **`/api/decision/*` 已落地第一版**，`/api/decision/start/status/events/history/answer/simulate/start/upgrade/report` 全部可用 |
| 决策管线 | **`decision/tiers.py`、`decision/pipeline.py`、`decision/classifier.py` 已建成**，三档 `flash / deep / panorama` 已接入真实后端 |
| 后端拆分 | **`server_core.py` 已拆成兼容 facade**，核心运行时已分流到 `server_runtime.py`、`server_detection.py`、`server_shared.py` |
| 前端工程 | **Vite 已接入**，`4174` 为 dev 端口，`npm run build` 输出 `dist/`，`4173` 由 FastAPI 直接托管构建产物 |
| 决策主线 | **单题真实检测 + Engine B + 自动/手动模拟器 + 历史恢复 + PDF/文本报告** 已能跑通 |
| 检测策略 | **`decision_deep` 已改为轻量检测档**：filter1/filter2 减负、跳过 filter3，且在不确定时 fail-open 到 Engine B，避免“看起来卡死/总超时” |
| 交互稳定性 | **提交回答链路已补齐**；B1 旧快照回退主因已用单调进度 rank 修复；recheck 期间会阻止过早启动模拟器；渲染签名去重后 flicker 探针结果为 `0 mutation`；历史完成态的模拟器摘要已补兜底 |
| 首页体验 | **首页 Hero 已重做**，标题截断已修复，副标题/说明卡/开始区块层级已调整，并补了桌面端与移动端 smoke |
| 思考流 | **检测页顶部实时思考流已上线**：连续输出、可折叠、重复日志自动归并，不再被同一句等待/失败提示反复刷屏 |
| 可视化层 | **`tier-selector.js`、`timeline-view.js`、`decision-engine.js` 已上线**；星图已有命中增强、网格/信标效果；`PixiStarMap` 仍是增强占位 |
| 报告导出 | **决策 PDF 已升级到出版感第一版**：封面、目录、章节概览、时间线页、行动地图页、过程日志与结构化轨迹都已纳入同一份报告；新增 AI 总结版 PDF，用户可同时拿到完整版与客户可读短版；已新增可选 WeasyPrint HTML/CSS 渲染器，默认仍保留 fpdf2 |
| 旧研究台残留 | **仍存在**。旧控制台、旧文案、旧 detail panel / fault map 风格、部分研究模式 DOM 还没清干净 |

一句话判断：

> 当前仓库已经不是“规划中”，而是**新决策协议第一版已经能跑、能测、能恢复、能导出**；真正还没收尾的，是旧研究台残留清理、星图继续产品化，以及 CSS / 语义 / 移动端这类工程收边。

### 本轮可复现验证

- `python3 -m py_compile server.py server_core.py server_shared.py server_runtime.py server_detection.py decision/pipeline.py research/api.py research/engine_b/runtime.py`
  结果：通过
- `python3 -m unittest tests.test_api_json_rescue tests.test_engine_b_runtime tests.test_decision_pipeline_normalization tests.test_decision_tier_regression tests.test_decision_api_smoke`
  结果：通过
- `python3 -m py_compile research/output_formatter.py decision/reporting.py server.py`
  结果：通过
- `npm run build`
  结果：通过，成功输出最新 `dist/`
- `python3 tests/pipeline_recheck_guard.py`
  结果：通过，recheck 进行中不会重复自动启动模拟器
- `node tests/thinking_log_dedupe.mjs`
  结果：通过，重复思考日志会归并为单条并显示次数
- `env PW_BROWSER=webkit node tests/submit_button_e2e.mjs`
  结果：提交回答链路通过
- `env PW_BROWSER=webkit node tests/tier_selector_ui_regression.mjs`
  结果：三档选择器 UI 回归通过
- `env PW_BROWSER=webkit node tests/home_hero_layout_smoke.mjs`
  结果：首页标题、Hero 布局与主要 CTA 通过
- `env PW_BROWSER=webkit node tests/home_mobile_surface_smoke.mjs`
  结果：首页移动端主视觉与输入区通过
- `env PW_BROWSER=webkit DECISION_ID=b0801898 node tests/star_map_v3_smoke.mjs`
  结果：星图第三版 smoke 通过
- `env PW_BROWSER=webkit DECISION_ID=b0801898 node tests/mobile_layout_smoke.mjs`
  结果：移动端布局 smoke 通过
- `env PW_BROWSER=webkit DECISION_ID=b0801898 node tests/star_map_hit_e2e.mjs`
  结果：星图点击命中链路通过
- `env PW_BROWSER=webkit DECISION_ID=eb15fdf3 node tests/decision_flicker_probe.mjs`
  结果：`mutations: 0`、`attributeChanges: 0`、`htmlChanged: false`
- `node tests/stale_decision_snapshot_probe.mjs`
  结果：Chromium 通过，旧 B1 快照不会覆盖 B3 处理视图
- `env PW_BROWSER=webkit node tests/stale_decision_snapshot_probe.mjs`
  结果：WebKit 通过，旧 B1 快照不会覆盖 B3 处理视图
- `CLP_PDF_RENDERER=weasyprint python3 -c "...generate_decision_pdf_report(...)"`
  结果：本机缺 WeasyPrint 时自动回退到 fpdf2，并生成 `/tmp/clp_weasy_fallback_test.pdf`
- `env DECISION_ID=b0801898 node tests/decision_full_flow_live.mjs`
  结果：live flow 跑到 `completed`，新会话不再卡在 `b1_diagnosis`
- 决策 PDF 最新人工产物
  - `research/output/decision_reports/decision_job-82afe344_session-6b4ef986_20260407-125755.pdf`
  - 封面缩略图人工检查：`/tmp/decision_job-82afe344_session-6b4ef986_20260407-125755.pdf.png`

### 当前明确未完成项

这 5 条是现在真正还值得继续做的收尾项：

1. 旧研究台清理
   - `title-screen`、历史面板注释、`detail-panel` / `fault-map` 风格和部分旧 DOM 仍在
   - 当前能在 [index.html](/Users/dutaorui/Desktop/claudecode/index.html)、[app.js](/Users/dutaorui/Desktop/claudecode/app.js)、[style.css](/Users/dutaorui/Desktop/claudecode/style.css) 看到残留
2. 星图产品化继续推进
   - 命中增强、个人星座网格、信标效果已经有了第一批实现
   - 但“引力场 / 粒子 / 决策节点映射 / 完整产品视觉”还没完全收束
3. `style.css` 继续减重
   - 当前文件长度约 `4322` 行
   - 仍含较多旧研究台样式、fault map、历史面板和兼容期规则
4. 工程收边
   - 升级语义
   - 继续压移动端细节
   - 维持 `flash / deep / panorama` 三档回归基线
5. PDF 继续做人工视觉复核
   - 新版版式已落地
   - 但目录页、时间线页、行动地图页仍值得继续做人工阅读检查与微调
   - WeasyPrint 已有可选入口，但要真正默认切换前需要先安装依赖并做一轮完整视觉回归

---

## 二、产品架构

### 2.1 三幕决策流程

```
用户输入问题 → 选择思考深度(⚡💡🌌)
    ↓
┌─── 第一幕：分类 ─────────────────┐
│  这是什么类型的问题？              │
│  · 快速分类(1次LLM)              │
│  · 7哲学家验证(💡🌌)             │
│  · 信息注入探测(🌌)              │
│                                   │
│  → 95%判定为"可做选择"            │
│  → 5%判定为"拉格朗日点"           │
└───────────────────────────────────┘
    ↓
┌─── 第二幕：信息抹平 ──────────────┐
│  消除认知盲区                      │
│  · B1 卡点诊断(3-5个追问)          │
│  · B2 信息侦探(找出盲区)          │
│  · B3 认知解锁(换角度看问题)       │
│  · B4 经验模拟(相似案例)   (🌌)   │
│  · B5 情绪镜像(情绪干扰)   (🌌)   │
│  · C1 力量重估(天平更新)           │
└───────────────────────────────────┘
    ↓
┌─── 第三幕：未来模拟 ──────────────┐
│  看两条路的未来                     │
│  · B6 参数收集(安全垫/可逆性)      │
│  · B7 时间线生成(×2选项×3情景)     │
│  · B8 十字路口(检查站+信号灯)      │
│  · B9 最终洞察(对比+建议)          │
│  · 稳定性验证(可选)         (🌌)  │
│  · 振荡检测(可选)           (🌌)  │
└───────────────────────────────────┘
    ↓
输出：推荐 + 路线图 + PDF报告 + 星图节点
```

### 2.2 三级思考深度

| | ⚡ 闪念 | 💡 深思 | 🌌 全景推演 |
|---|---|---|---|
| **第一幕** | ① 快速分类 | ①②③ 分类+哲学家+注入 | ①②③ 全部 |
| **第二幕** | 跳过 | ④⑤⑥⑨ | ④⑤⑥⑦⑧⑨ 全部 |
| **第三幕** | 跳过 | ⑩⑪⑫⑭ | ⑩⑪⑫⑬⑭⑮⑯ 全部 |
| **LLM 调用** | 1次 | ~10次 | ~20次 |
| **Token** | ~2K | ~30K | ~100K |
| **耗时** | 5秒 | 30秒 | 2-3分钟 |
| **星图样式** | `·` 暗淡小点 | `✦` 标准星 | `✺` 完整星系 |

### 2.3 星图联动设计

星图贯穿整个决策过程，不同阶段有不同视觉反馈：

| 阶段 | 星图表现 |
|------|---------|
| 问题输入 | 一颗新节点在宇宙中亮起 |
| AI 分类中 | 两个引力源(选项A/B)出现，参照星系浮现 |
| 信息补全中 | 每条信息变成粒子飞入对应引力源，天平倾斜 |
| 未来模拟中 | 两条时间线星轨从引力源延伸 |
| 完成决策 | 选定路径高亮，形成永久星座 |
| 下次回来 | 看到个人决策宇宙（所有历史决策组成的星座） |

星图节点分三种视觉等级，对应思考深度：
- ⚡ 闪念 → 最小光晕，最简信息
- 💡 深思 → 标准节点，有引力场和连接线
- 🌌 全景 → 完整星系，有卫星环、时间线星轨、参照星围绕

---

## 三、技术架构

### 3.0 当前已落地架构（真实代码）

```text
前端（Vite + 原生 JS ESM）
├── index.html
├── style.css
├── app.js                         # 现在是模块入口与页面编排
├── package.json
├── vite.config.mjs
├── dist/                          # 构建产物，由 FastAPI 4173 托管
├── frontend/
│   ├── core/
│   │   ├── state.js
│   │   ├── renderer.js
│   │   └── interaction.js
│   ├── components/
│   │   ├── decision-flow-view.js
│   │   ├── tier-selector.js
│   │   ├── timeline-view.js
│   │   └── pixi-star-map.js
│   └── modules/
│       ├── decision-engine.js
│       ├── engine-a.js
│       ├── engine-b.js
│       ├── ui-handlers.js
│       ├── ui-bridge.js
│       └── utils.js

后端（FastAPI + decision 协议 + server_core 兼容桥）
├── server.py                      # FastAPI 路由入口
├── server_core.py                 # 兼容 facade（当前约 39 行）
├── server_runtime.py              # RuntimeManager 拆出
├── server_detection.py            # DetectionManager 拆出
├── server_shared.py               # 共享工具拆出
├── decision/
│   ├── __init__.py
│   ├── tiers.py
│   ├── pipeline.py
│   └── classifier.py
├── research/
│   ├── api.py
│   ├── db.py
│   ├── single_detect.py
│   ├── output_formatter.py
│   └── engine_b/
│       ├── agents.py
│       ├── models.py
│       └── state.py
```

当前判断：

- **FastAPI + SSE 已经落地**
- **Vite + 前端模块拆分已经落地**
- **`decision/` 新协议第一版已经建出来并接上真实后端**
- **`server_core.py` 已经拆成兼容 facade，真正待继续收敛的是 bridge 状态结构**
- **旧研究平台 UI 仍与新产品协议并存，页面还没有彻底“最终形态化”**

### 3.1 目标架构

> 注意：以下是**目标架构**，不是当前仓库已经完成的结构。

```
前端 (Vite + 原生 JS ESM)
├── index.html                    # 单页入口
├── style.css                     # 设计系统
├── app.js                        # 主控
├── core/
│   ├── state.js                  # 全局状态
│   ├── renderer.js               # Canvas 星图渲染
│   └── interaction.js            # 拖拽/缩放/点击
├── components/
│   ├── decision-flow.js          # 三幕决策流程 UI
│   ├── star-map.js               # 星图节点/引力场/粒子
│   ├── tier-selector.js          # 思考深度选择器
│   └── timeline-view.js          # 未来时间线对比
└── modules/
    ├── api.js                    # 后端通信
    ├── decision-engine.js        # 决策状态机
    └── star-data.js              # 星图数据管理

后端 (FastAPI)
├── server.py                     # FastAPI 入口 + 路由
├── decision/
│   ├── pipeline.py               # 决策管线调度
│   ├── classifier.py             # 第一幕：分类
│   ├── leveler.py                # 第二幕：信息抹平
│   ├── simulator.py              # 第三幕：未来模拟
│   └── tiers.py                  # 三级配置
├── agents/
│   ├── philosopher.py            # 7哲学家 (从 phase2_filter.py 搬)
│   ├── info_probe.py             # 信息注入 (从 phase2_filter1.py 搬)
│   ├── diagnosis.py              # B1 卡点诊断 (从 engine_b/agents.py 搬)
│   ├── info_detective.py         # B2 信息侦探
│   ├── cognitive_unlock.py       # B3 认知解锁
│   ├── experience_sim.py         # B4 经验模拟
│   ├── emotion_mirror.py         # B5 情绪镜像
│   ├── evaluator.py              # C1 力量重估
│   ├── param_collector.py        # B6 参数收集
│   ├── timeline_gen.py           # B7 时间线生成
│   ├── crossroads.py             # B8 十字路口
│   └── insight.py                # B9 最终洞察
├── llm/
│   ├── api.py                    # LLM 调用封装 (现有 research/api.py)
│   └── token_tracker.py          # Token 消耗追踪
├── storage/
│   ├── db.py                     # SQLite (现有 research/db.py)
│   └── star_data.py              # 星图持久化
└── report/
    └── pdf_builder.py            # PDF 报告生成
```

### 3.2 从现有代码的搬迁映射

> **核心原则：不是重写，是拆分重组。** 所有核心算法代码已经写好了。

| 现有文件 | 行数 | 搬到哪里 | 做什么改动 |
|---------|------|---------|-----------|
| `research/phase2_filter.py` | 256 | `agents/philosopher.py` | STANCES + evaluate_question_balance 直接搬，去掉batch逻辑 |
| `research/phase2_filter1.py` | 183 | `agents/info_probe.py` | INFO_LEVELS + _evaluate_level 直接搬，只保留L1/L2 |
| `research/phase3_stability.py` | 267 | `agents/` 下新增 `stability.py` | _simulate_trace + _classify_stability 搬过来 |
| `research/phase3_oscillation.py` | 260 | `agents/` 下新增 `oscillation.py` | 缩减到20轮(从50)，只做🌌等级 |
| `research/engine_b/agents.py` | 1539 | 拆分到 `agents/` 下各文件 | 按B1-B9/C1拆分，每个Agent一个文件 |
| `research/api.py` | 842 | `llm/api.py` | 基本不动，加 token_tracker 集成 |
| `research/db.py` | 307 | `storage/db.py` | 加决策历史表，加星图节点表 |
| `server.py` | 261 | `server.py` | 精简路由，加 lifespan 挂载，修复API路径 |
| `server_core.py` | 39 | 已拆到 `server_runtime.py` / `server_detection.py` / `server_shared.py` | 当前已成为兼容入口，后续只需继续收敛 bridge 状态 |
| `frontend/core/renderer.js` | 195 | 保留，增强 | 加引力场、粒子系统、时间线星轨 |
| `frontend/core/state.js` | ~60 | 保留，扩展 | 加决策状态机、星图历史 |

### 3.3 可直接复用的代码清单

以下代码**基本不需要修改**，直接搬到新位置即可：

```python
# 1. 7哲学家的 prompt 和评估逻辑
#    来源: research/phase2_filter.py L9-L165
#    包含: STANCES, STANCE_SYSTEM, evaluate_question_balance()

# 2. 信息注入的 prompt 和分级逻辑
#    来源: research/phase2_filter1.py L13-L38, L40-L101
#    包含: INFO_LEVELS, FILTER1_SYSTEM, _evaluate_level()

# 3. Engine B 全部 Agent prompts
#    来源: research/engine_b/agents.py
#    包含: B1_SYSTEM ~ B9 + C1_SYSTEM (全部 system prompt)
#    包含: run_b1_diagnosis ~ run_b9 (全部运行函数)
#    包含: 所有 fallback 函数 (_build_b7_timeline_fallback 等)

# 4. 稳定性测试逻辑
#    来源: research/phase3_stability.py L16-L60, L120-L193
#    包含: TRACE_SYSTEM, _simulate_trace(), _classify_stability()

# 5. 振荡测量逻辑
#    来源: research/phase3_oscillation.py L15-L39, L113-L212
#    包含: OSCILLATION_CHUNK_SYSTEM, _generate_chunk(), _classify_oscillation()

# 6. LLM 调用封装
#    来源: research/api.py (全部)
#    包含: call_agent_json(), 重试逻辑, token 计数

# 7. 数据库操作
#    来源: research/db.py (全部)
#    包含: init_db(), 所有 db_* 函数

# 8. PDF 报告生成
#    来源: research/output_formatter.py (部分)
#    包含: generate_pdf() 相关逻辑
```

### 3.4 仍需补强的代码

```
1. `frontend/core/interaction.js`
   - 继续补复杂星图交互测试（拖拽/缩放/多节点命中/边缘态）
2. `frontend/core/renderer.js` + `frontend/components/pixi-star-map.js`
   - 继续做引力场、粒子、时间线星轨、历史决策节点增强
3. `app.js` + `index.html` + `style.css`
   - 彻底清理旧研究台控制台、旧文案、旧 DOM 残留
4. `server_core.py`
   - 持续把遗留逻辑下沉到 `decision/` / `research/engine_b/` 更清晰的边界里
5. 报告与历史
   - 新版 `/api/decision/report` / PDF 版式已经落地
   - 处理历史列表中的旧 `running` 残留记录
```

---

## 四、数据库设计

### 4.1 新增表

```sql
-- 决策记录（每次用户决策一条）
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'flash',  -- flash/deep/panorama
    classification TEXT,                 -- 'decision'/'lagrange_point'
    status TEXT DEFAULT 'in_progress',   -- in_progress/completed/abandoned
    
    -- 第一幕结果
    philosopher_results TEXT,            -- JSON: 7哲学家评估结果
    balance_score REAL,
    info_probe_result TEXT,              -- JSON: 信息注入结果
    
    -- 第二幕结果
    diagnosis_answers TEXT,              -- JSON: 用户回答
    blockages TEXT,                      -- JSON: 卡点类型
    missing_info TEXT,                   -- JSON: 补全的信息
    cognitive_frames TEXT,               -- JSON: 认知框架
    experience_cases TEXT,               -- JSON: 经验案例
    emotional_insight TEXT,              -- JSON: 情绪镜像
    pro_total INTEGER DEFAULT 50,
    con_total INTEGER DEFAULT 50,
    recommendation TEXT,
    action_plan TEXT,
    
    -- 第三幕结果
    sim_params TEXT,                     -- JSON: 模拟参数
    choices TEXT,                        -- JSON: 提炼的两个选项
    timeline_a TEXT,                     -- JSON: 选项A时间线
    timeline_b TEXT,                     -- JSON: 选项B时间线
    crossroads TEXT,                     -- JSON: 十字路口
    final_insight TEXT,                  -- JSON: 最终洞察
    stability_result TEXT,              -- JSON: 稳定性验证(🌌)
    oscillation_result TEXT,            -- JSON: 振荡检测(🌌)
    
    -- 星图数据
    star_visual TEXT DEFAULT 'dim',      -- dim/standard/galaxy
    star_x REAL,                        -- 星图坐标
    star_y REAL,
    
    -- 元数据
    token_used INTEGER DEFAULT 0,
    created_at TEXT,
    completed_at TEXT,
    
    -- 用户事后反馈（可选）
    user_choice TEXT,                    -- 用户最终选了什么
    user_satisfaction INTEGER,           -- 1-5 满意度
    follow_up_note TEXT                  -- 事后备注
);
```

### 4.2 保留的现有表
- `engine_b_sessions` → 兼容保留，逐步迁移到 `decisions`
- `confirmed_clps` → 保留，作为"研究模式"的星图数据源

---

## 五、API 设计

### 5.1 新 API 路由

```
POST /api/decision/start           # 开始决策（带 tier 参数）
GET  /api/decision/status?id=xxx   # 获取决策状态
GET  /api/decision/events?id=xxx   # SSE 实时流
POST /api/decision/answer          # 提交用户回答
POST /api/decision/upgrade         # 升级思考深度（差额token）
GET  /api/decision/history         # 决策历史列表
GET  /api/decision/report?id=xxx   # 导出 PDF
GET  /api/decision/summary-report?id=xxx # 导出 AI 总结版 PDF

GET  /api/starmap/nodes            # 获取所有星图节点（历史决策+研究发现）
GET  /api/starmap/connections      # 获取节点间连接（相似决策）
```

### 5.2 SSE 事件格式

```json
{
  "phase": "act1",          // act1/act2/act3
  "step": "philosophers",   // 当前步骤
  "progress": 3,            // 已完成的哲学家数
  "total": 7,
  "data": {                 // 该步骤的结果数据
    "stance": "功利主义者",
    "lean_direction": "正方",
    "lean_strength": 72
  },
  "star_event": {           // 星图动画指令
    "type": "particle_in",
    "target": "pro",
    "color": [255, 107, 107]
  }
}
```

---

## 六、前端页面结构

### 6.1 页面流转

```
[开屏/星图] → [输入问题] → [选择深度] → [决策流程] → [结果/星图]
     ↑                                                    │
     └────────────── 查看历史决策 ←─────────────────────────┘
```

### 6.2 关键 UI 组件

#### 思考深度选择器
```
┌────────────────────────────────────────────┐
│  选择思考深度                               │
│                                            │
│  ⚡ 闪念    [5秒·一个直觉]                  │
│  💡 深思    [30秒·完整分析]         推荐     │
│  🌌 全景    [3分钟·全方位推演]              │
└────────────────────────────────────────────┘
```

#### 引力场画布
```
用户的问题节点悬浮在中央，两个引力源分列两侧。
AI 分析过程中，信息粒子从对应方向飞入。
天平实时倾斜，用户一眼看出当前力量对比。
```

#### 平行时间线
```
选项A                              选项B
┌──────────┐                ┌──────────┐
│ 📅 1个月  │                │ 📅 1个月  │
│ 顺风/稳/逆│                │ 顺风/稳/逆│
│ 📅 3个月  │                │ 📅 3个月  │
│ 📅 6个月  │                │ 📅 6个月  │
│ 📅 1年    │                │ 📅 1年    │
│ 📅 3年    │                │ 📅 3年    │
│           │                │           │
│ 后悔指数  │                │ 后悔指数  │
└──────────┘                └──────────┘
```

### 6.3 要删除的现有 UI

> 当前真实状态：**这一节列的 UI 还基本都在仓库里**，只能作为“后续删除清单”，不能按已完成理解。

- 实验控制台 (`console-panel`) 的全部配置区（API Key、预设档位、实时指标）
- "执行模式"选择器
- 运行日志区
- "历史实验"区
- 比较模态框 (`compare-modal`)

### 6.4 要保留并改造的 UI

当前实际情况：

- `title-screen` 还在，但首页已经做成新版 Hero，旧研究味显著下降
- `home-entry` 还在，并且已经接入思考深度选择器、说明卡和新 CTA 层级
- `detection-screen` 已承担真实检测与 Engine B 流程，顶部有连续输出、可折叠的实时思考流
- `detail-panel` / 星图 / fault map 仍偏旧版研究平台风格

- 标题屏幕 (`title-screen`) → 保留，改文案
- 星图画布 (`cosmos`) → 保留，增强交互
- 问题输入 (`home-entry`) → 保留，加思考深度选择
- 检测流程 (`detection-screen`) → 保留骨架，调整步骤内容
- 力量天平 (`balance-display`) → 保留，改为实时联动星图
- 详情面板 (`detail-panel`) → 保留，用于查看历史决策

---

## 七、实施任务拆分

### 当前阶段判断

| Phase | 状态 | 说明 |
|---|---|---|
| Phase 0 | 已完成 | `lifespan`、重复 `nav-hint`、`ui-bridge.js` 路由错位、旧紧急脚本等基线问题已处理 |
| Phase 1 | 已完成 | `decision/` 管线、`/api/decision/*`、`decisions` 表、SSE、报告导出均已落地；`server_core.py` 已拆为兼容 facade + 独立运行时模块 |
| Phase 2 | 大部分完成 | Vite、tier selector、timeline view、decision-engine 已接上；旧研究台清理与少量移动端收边未完成 |
| Phase 3 | 第三版基线已落地 | Canvas 主星图、命中增强、网格/信标效果、时间线对比 UI 已有；PixiJS/WebGL 未来路径画布已作为显式开关能力接入，默认仍保留 Canvas 主路径 |
| Phase 4 | 大部分完成 | 单测、构建、提交按钮 E2E、首页 smoke、thinking log 去重、flicker probe、完整 live flow 都有验证；语义升级与 CSS 减重未完成 |

### Phase 0：紧急修复（0.5天）

修复现有代码中的直接 bug，确保重构前基线稳定。

```
[x] 修复 server.py: FastAPI 已挂载 `lifespan=lifespan`
[x] 修复 server_core.py L837-838: `start_run` 末尾死代码已清理
[x] 修复 index.html: 重复的 `#nav-hint` 已删除
[x] 修复 ui-bridge.js: API 路径与 `server.py` 已对齐
    - /api/engineb/simulate → /api/engineb/simulate/start
    - /api/engineb/b1/submit → /api/engineb/answer
    - /api/engineb/report → /api/final-report/pdf
[x] 删除旧的 `EMERGENCY UI RECOVERY` 内联脚本，避免继续覆盖模块事件
[x] 首页输入已加 IME 回车保护，Engine B / 模拟器提交已改为当前模块链路
```

### Phase 1：后端管线重构（2-3天）

```
[x] server.py 已迁到 FastAPI
[x] /api/detect/events 和 /api/engineb/events 已有 SSE
[x] /api/decision/events 已有 SSE
[x] /api/final-report/pdf 已存在
[x] 创建 decision/ 目录结构
[x] 创建 decision/tiers.py — 三级配置定义
[x] `pro` 承接旧 `ultra` 出版级推演能力；新 `ultra` 追加受控 Monte Carlo 多代理碰撞
[x] 创建 decision/pipeline.py — 决策管线调度器
[x] 创建 decision/classifier.py — 第一幕分类器
[x] 更新 server.py — 已新增 /api/decision/* 路由
[x] 更新数据库 — 已新增 decisions 表
[x] `decision_deep` 检测已轻量化，并接入 fail-open 到 Engine B
[x] `server_core.py` 已拆成兼容 facade，核心已迁到 `server_runtime.py` / `server_detection.py` / `server_shared.py`
[ ] 把 `decision/*` 的状态结构再做一轮收敛，减少桥接层重复字段
```

### Phase 2：前端重构（2-3天）

```
[x] 已切到原生 JS ESM 模块入口
[x] 已创建 `frontend/core` / `frontend/modules` / `frontend/components`
[x] 已抽出 `decision-flow-view.js`
[x] 已安装 Vite，配置开发环境
[x] 已创建 `components/tier-selector.js`
[x] home-entry 已加入思考深度选择
[x] detection-screen 已适配新三幕决策主线
[x] 已创建 `components/timeline-view.js`
[x] `state.js` 已增加决策状态机字段
[x] 已创建 `modules/decision-engine.js`
[x] 提交按钮链路、recheck gating、anti-flicker 去重已接入前端
[x] 首页 Hero / 副标题 / 右侧说明卡 / 开始区块已重设计，标题截断问题已修复
[x] 实时思考流已改为顶部连续输出，可折叠，重复日志自动归并
[ ] 删除不需要的 UI — 实验控制台配置区、预设选择、运行日志等仍有残留
[ ] 改造 `index.html` / `style.css` — 继续精简旧研究平台 DOM 与样式
[ ] renderer.js / star-map 继续增强为更完整的“决策画布”
```

### Phase 3：星图增强（1-2天）

```
[x] 已有 `PixiStarMap` 占位实现
[x] `renderer.js` / `interaction.js` 已拆出
[x] 已有思考深度对应的视觉等级数据（dim/standard/galaxy）
[x] timeline view 第一版已落地
[ ] 实现更完整的决策节点类型与动画细节
[ ] 实现引力场 + 粒子系统的产品版，而不只是样式层预埋
[ ] 实现时间线星轨与历史决策映射
[ ] 实现参照星系 / 个人星座
[x] 已补齐基础星图点击命中与交互 smoke / e2e
```

### Phase 4：完善与验证（1天）

```
[x] 构建验证 — `npm run build`
[x] 后端/API 单测 — `tests.test_single_detect_profiles` + `tests.test_decision_api_smoke`
[x] 交互验证 — `submit_button_e2e.mjs`
[x] 首页桌面端 smoke — `home_hero_layout_smoke.mjs`
[x] 首页移动端 smoke — `home_mobile_surface_smoke.mjs`
[x] 抖动验证 — `decision_flicker_probe.mjs`
[x] 思考流去重验证 — `thinking_log_dedupe.mjs`
[x] recheck 守卫验证 — `pipeline_recheck_guard.py`
[x] 完整 live flow — `decision_full_flow_live.mjs`
[x] PDF 报告 — 已升级为封面 / 目录 / 时间线 / 行动地图 / 日志 / 轨迹一体化布局
[x] 错误处理 — 已有部分 SSE 断线兜底、LLM 超时 fallback
[ ] 升级功能 — 从闪念升级到深思，不重跑已有步骤
[ ] 响应式 — 继续做移动端收边
[ ] 冒烟测试 — 把 `flash / deep / panorama` 三档都做成稳定回归测试
[ ] style.css 清理 — 删除不再使用的样式
```

---

## 八、关键配置定义

### decision/tiers.py 的具体配置

```python
THINKING_TIERS = {
    "flash": {
        "label": "⚡ 闪念",
        "estimated_tokens": 2000,
        "estimated_seconds": 5,
        "star_visual": "dim",
        
        # 第一幕
        "enable_classification": True,
        "enable_philosophers": False,
        "enable_info_probe": False,
        
        # 第二幕
        "enable_diagnosis": False,
        "enable_info_detective": False,
        "enable_cognitive_unlock": False,
        "enable_experience_sim": False,
        "enable_emotion_mirror": False,
        "enable_reevaluation": False,
        
        # 第三幕
        "enable_simulation": False,
        "enable_stability": False,
        "enable_oscillation": False,
    },
    "deep": {
        "label": "💡 深思",
        "estimated_tokens": 30000,
        "estimated_seconds": 30,
        "star_visual": "standard",
        
        # 第一幕
        "enable_classification": True,
        "enable_philosophers": True,
        "philosopher_count": 4,  # 只用4个哲学家
        "enable_info_probe": True,
        "info_probe_levels": 2,  # L1+L2
        
        # 第二幕
        "enable_diagnosis": True,
        "diagnosis_count": 3,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": False,
        "enable_emotion_mirror": False,
        "enable_reevaluation": True,
        
        # 第三幕
        "enable_simulation": True,
        "simulation_depth": 3,  # 3个时间节点
        "enable_stability": False,
        "enable_oscillation": False,
    },
    "panorama": {
        "label": "🌌 全景推演",
        "estimated_tokens": 100000,
        "estimated_seconds": 180,
        "star_visual": "galaxy",
        
        # 第一幕
        "enable_classification": True,
        "enable_philosophers": True,
        "philosopher_count": 7,  # 全部7个
        "enable_info_probe": True,
        "info_probe_levels": 2,
        
        # 第二幕
        "enable_diagnosis": True,
        "diagnosis_count": 5,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": True,
        "experience_count": 3,
        "enable_emotion_mirror": True,
        "enable_reevaluation": True,
        
        # 第三幕
        "enable_simulation": True,
        "simulation_depth": 6,  # 6个时间节点
        "enable_stability": True,
        "stability_repeats": 3,
        "stability_rounds": 10,
        "enable_oscillation": True,
        "oscillation_rounds": 20,
    },
}
```

---

## 九、需要注意的坑

### 9.1 已知 Bug（必须先修）
1. `frontend/core/interaction.js` 的命中测试闭环已经补上，但星图整体仍未完全达到最终产品视觉
2. 旧研究台 UI 残留仍多，导致页面虽然能跑，但视觉和 DOM 结构仍非最终形态
3. 上游模型在大 JSON / 长推理场景下仍有 504 / 高延迟风险；现在主要靠轻量检测与 fallback 扛住
4. `research/output/app_state.db` 里的历史还保留了一批修复前的 `running` 决策记录，后续需要归档/清理策略
5. `checkpoint.py` 仍保留数据库初始化兜底逻辑，后续迁入正式存储层时需要统一清理
6. 2026-04-08 更新：Safari 上 B1 卡点诊断回退 bug 的主因已修
   - 用户症状曾是选完答案后回到“问题 1/3”，随后进入“正在切换判断框架”转圈
   - 修复位置：`frontend/modules/decision-engine.js`、`frontend/core/state.js`
   - 修复方式：同一 `decision_id` 维护单调进度 rank，旧 SSE / 轮询快照不能覆盖新阶段
   - 回归探针：`tests/stale_decision_snapshot_probe.mjs`
   - Chromium + WebKit 已过；仍建议实机 Safari 再跑一轮完整 B1 -> B2/B3/C1
7. 2026-04-07 晚间新增：Safari 上 C1 页“启动选择模拟器”仍有死点击反馈
   - Chromium E2E 已通过，说明主链路不是全坏
   - 但用户实机 Safari 仍反馈按钮显示但点击不推进
   - 需要把 Safari Network / Console / loaded asset / localStorage restore 一起排查

### 9.1.1 2026-04-07 晚间已做但未完全收口的修复

这轮已经落地、但仍需要下一位 AI 接着验证 Safari 的改动：

- `decision/tiers.py`
  - `deep` 新增 `allow_manual_simulation: True`
- `research/engine_b/runtime.py`
  - 手动模拟器允许读取 `allow_manual_simulation`
- `decision/pipeline.py`
  - 已完成决策也能重新 hydrate 后进入 act3
  - 监控线程不会在第三幕刚启动时又把 `deep` 决策误写回 completed
- `frontend/modules/decision-engine.js`
  - `deep/pro/ultra` 的模拟器按钮显示条件已重写
  - 已在模拟器阶段时，重新点按钮会强制刷新到第三幕
  - B1 旧快照回退主因已用单调进度 rank 修复
- `tests/simulator_entry_regression.mjs`
  - 新增真实浏览器回归
  - Chromium 已验证：
    - `deep` 建议页按钮可见
    - 点击后进入 step5
    - `ultra` 已完成历史也能从建议页重入 step5
- `tests/stale_decision_snapshot_probe.mjs`
  - 新增旧快照回退回归
  - Chromium + WebKit 已验证：
    - 高进度 B3 处理视图不会被旧 B1 快照覆盖

### 9.2 engine_b/agents.py 的 fallback 机制
`agents.py`（1539行）中包含大量 `_build_b7_timeline_fallback`、`_build_b8_fallback`、`_build_b9_fallback` 等本地回退函数。这些是在 LLM 调用失败时的降级方案。**搬迁时必须保留这些 fallback**，它们是系统稳定性的关键保障。

### 9.3 并发安全
现有的 `RuntimeManager` 使用 `threading.RLock()` 做并发安全。新的决策管线如果支持多用户同时使用，需要注意：
- SQLite 默认不支持多线程写入，需要 `check_same_thread=False` + 写锁
- SSE 连接的生命周期管理
- Engine B 状态存储 (`engine_b/state.py`) 使用文件 JSON，多用户场景需改为数据库

### 9.4 `research/api.py` 的重试机制
`call_agent_json()` 已经内置了完善的重试、超时、fallback 逻辑。搬迁时保持不变即可。关键参数：
- `CLP_API_RETRIES`: 重试次数（默认4）
- `CLP_TIMEOUT_SECONDS`: 超时时间（默认120秒）
- 自动 JSON 修复（尝试修复模型输出的非法 JSON）

### 9.5 前端的"紧急恢复脚本"
这段内联 `EMERGENCY UI RECOVERY` 脚本已经删除，原因是它会覆盖模块里的真实事件绑定，导致首页和检测页出现“点了没反应 / 路由跳错”的问题。后续如果再出现白屏或模块初始化失败，应该优先修复模块加载链路，而不是重新加回这类兜底脚本。

---

## 十、可以完全删除的文件

> 这一节是**目标态删除清单**，不是“现在马上删”。  
> 当前仓库里很多文件仍被实际引用，尤其是：
>
> - `server_core.py`
> - `research/output_formatter.py`
> - `frontend/components/pixi-star-map.js`
> - `data.js`
> - `discovered-data.js`
> - `TECHNICAL_HANDOFF.md`
>
> 在新产品主链路真正替换完成之前，不建议直接删除。

以下文件在新产品中不再需要，可以安全删除（或移到 `archive/` 目录）：

```
research/phase1_mining.py          # 矿工（用户版不需要批量挖矿）
research/phase2_filter3.py         # 筛子3（重述稳定性，用户版不需要）
research/phase3_analysis.py        # 力量解剖（改用 C1 重估替代）
research/phase4_fault_lines.py     # 断层线识别（用户版不需要）
research/phase4_social_conflicts.py # 社会冲突预测
research/phase4_tunnel_effects.py  # 隧道效应检测
research/run.py                    # 批量运行脚本
research/models.py                 # 候选/确认点模型（需保留部分）
research/checkpoint.py             # 断点恢复（研究模式专属）
research/output_formatter.py       # 需保留，当前承担新版决策 PDF 版式与章节组织
frontend/components/pixi-star-map.js # 目标态可删，但当前仍被 renderer.js 引用
run-first-mvp.sh                   # 初始化脚本
run-web.sh                         # 启动脚本（改用 vite dev）
data.js                            # 预置星图数据（改用数据库）
discovered-data.js                 # 发现数据（改用数据库）
FIRST_RUN.md                       # 初始引导
TECHNICAL_HANDOFF.md               # 旧交接文件（当前仍可作为历史参考）
WEB_APP.md                         # 旧架构说明
```

---

## 十一、优先级建议

如果只有有限时间，按以下优先级实施：

### P0（必须做，1天）
1. 清理旧研究台残留 DOM / 样式 / 文案，让 4173 页面真正进入产品形态
2. 扩展 `frontend/core/interaction.js` 的复杂交互测试，覆盖拖拽/缩放/多节点命中边缘态
3. 继续收敛 `decision/*` 与 compatibility bridge 的重复状态
4. 清理历史中的脏 `running` 会话，并补最小归档策略
5. 对新版 PDF 做一轮人工视觉复核，优先看目录页、时间线页、行动地图页

### P1（应该做，2天）
6. 做星图增强第一版：引力场、粒子、时间线星轨、历史节点映射
7. 继续压缩 detection / Engine B / simulator 之间的桥接代码
8. 移动端和样式减重
9. 把 `flash / deep / panorama` 三档都纳入自动化回归

### P2（锦上添花，2天）
10. 升级功能（闪念→深思不重跑）
11. 个人决策星座
12. 更完整的参照星系 / 相似决策联动
13. 更产品化的导出报告与分享视图

### P3（后续迭代）
14. Token 消耗可视化 / 计费系统
15. 决策事后跟踪（用户回来标记"我最终选了什么"）
16. 社交功能（分享决策报告）

---

> **这份文件包含了完整的设计决策、技术细节和实施路径。任何开发者（或 AI）拿到这份文件，都应该能独立完成重构。**
