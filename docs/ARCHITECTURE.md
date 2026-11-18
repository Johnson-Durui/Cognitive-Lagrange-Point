# 认知拉格朗日日点 · 系统架构设计 (System Architecture)

> **Cognitive Lagrange Point** 是一套面向高代价两难决策的双引擎多智能体推演系统。本文档汇总并沉淀仓库重构后的核心架构协议、状态机模型与工程防线（历史阶段性手记归档于 `docs/archive/`）。

---

## 1. 核心命题与双引擎闭环

天体力学中的**拉格朗日点（Lagrange Point）**是两股巨大引力精确抵消的平衡点。本系统将人类面临的复杂纠结问题严格区分为两类结构：

1. **真认知拉格朗日点（Structural Equilibrium）**：正反双方锚定在不可通约的底层价值公理（如后果净收益 vs 绝对权利边界）上，补充任何外部事实或切换视角都无法打破对称平衡。此类问题不应强行给出伪标准答案，而应完成**力场解剖**，揭示你愿意承担哪一种代价。
2. **伪平衡决策困境（Solvable Dilemma）**：表面上 50:50 僵持不下，实则源于**信息黑洞（A）**、**认知窄门（B）**、**经验盲区（C）**或**情绪干扰（D）**。一旦抹平认知卡点、引入可逆试错护栏，正反力矩差就会显著拉开。

系统通过 **Engine A（结构筛子）** 与 **Engine B（决策突破与未来模拟）** 构成双向闭环：

```mermaid
flowchart TD
    Q["用户输入两难问题"] --> DProto["Decision Protocol (decision/pipeline.py)"]
    DProto -->|Quick 档| Flash["极速结构分类与直觉行动建议"]
    DProto -->|Deep / Pro / Ultra 档| EA["Engine A · 三层结构筛子 (research/single_detect.py)"]

    subgraph EngineA ["第一幕：Engine A 结构检测"]
        EA --> F1["筛子 1：多量级信息注入测试"]
        F1 --> F2["筛子 2：多哲学框架力矩检验"]
        F2 --> F3["筛子 3：跨语境重述与消解检验"]
    end

    F3 -->|三层全稳 / 公理对冲| CLP["确认为认知拉格朗日点\n阶段三力量解剖与断层线定位"]
    F1 & F2 & F3 -->|平衡被打破 / 存在突破口| EB["Engine B · 认知抹平运行时 (research/engine_b/)"]

    subgraph EngineB ["第二幕：Engine B 决策突破"]
        EB --> B1["B1 卡点诊断追问"]
        B1 --> B25["B2 信息侦探 · B3 认知解锁 · B4 经验模拟 · B5 情绪镜像"]
        B25 --> B55["B5.5 第三条路（可逆过渡路径）"]
        B55 --> C1["C1 力矩重算与行动方案"]
    end

    C1 -->|力矩差 ≤ 阈值且开启回检| Recheck["A_Recheck · 二次结构复核"]
    Recheck -->|确认真平衡| CLP
    C1 & Recheck -->|形成倾向建议| SimGate{"开启第三幕未来模拟？"}

    subgraph Simulator ["第三幕：未来选择模拟器"]
        SimGate -->|自动(Pro/Ultra) 或 手动(Deep)| B6["B6 安全垫与可逆性参数采集"]
        B6 --> B7["B7 A/B 双路径 × 顺风/平稳/逆风时间线"]
        B7 --> B8["B8 关键岔路口红黄绿灯 + 最坏情况生存卡"]
        B8 --> B9["B9 后悔分数 · 概率对比 · 行动地图"]
        B9 -->|Ultra 档专享| MC["Ultra Monte Carlo 多代理分支碰撞与 LLM 委员会合议"]
    end

    Flash & CLP & SimGate & B9 & MC --> PDF["双轨 PDF 报告引擎 (research/output_formatter.py)\n完整出版级 PDF + AI 一页总结版 PDF"]
```

---

## 2. 模块分层职责

| 模块目录 | 核心文件 | 工程职责 |
| :--- | :--- | :--- |
| `backend/` | `app.py`, `core.py`, `detection.py`, `runtime.py`, `shared.py`, `demo.py` | FastAPI HTTP/SSE 服务层、纯 ASGI 静态无缓存中间件、健康检查与脱敏配置查询、批处理实验进程管理、零 Key 离线演示回退引擎 |
| `server.py` / `start.py` | 根目录统一入口 | 100% 向后兼容符号导出（`app`, `DECISIONS`, `DETECTION`, `RUNTIME`）与跨平台 CLI 启动器（支持 `--host`, `--port`, `--demo`, `--reload`, `--open`） |
| `decision/` | `pipeline.py`, `tiers.py`, `classifier.py`, `reporting.py` | 统一产品决策协议（`/api/decision/*`）、四档预算配置、档位无损升级（`Quick -> Deep -> Pro -> Ultra`）、报告上下文聚合 |
| `research/` | `api.py`, `single_detect.py`, `phase1-4*.py`, `output_formatter.py`, `db.py` | OpenAI 兼容网关调用与三级 JSON 降级修复、Engine A 科研管线、SQLAlchemy/SQLite 状态持久化、矢量/HTML 双渲染 PDF 出版引擎 |
| `research/engine_b/` | `runtime.py`, `agents.py`, `models.py`, `external_signals.py`, `state.py` | B1–B9 多智能体编排、A/B 时间线相似度去同质化重生成、本地外部市场声音快照注入、Ultra Monte Carlo 分支采样器 |
| `frontend/` & `app.js` | `core/`, `components/`, `modules/` | 原生 ESM 模块化前端、Canvas 2D 主星图 + `?webgl=1` PixiJS/WebGL 增强画布、Three.js Quantum Vibe Oracle、单调进度防回跳渲染器 |

---

## 3. 四档思考深度设计 (`decision/tiers.py`)

系统通过显式分层控制 Token 预算、智能体开关与模拟深度：

- **`quick`（⚡ 快速）**：单次结构预分析 + 极速方向建议，跳过多轮筛子与模拟器，适合 5 秒快速校准。
- **`deep`（💡 沉思，默认档）**：第一幕轻量双筛（Filter 1 + Filter 2）+ 第二幕核心突破（B1 + B2 + B3 + B5.5 + C1）；默认在第二幕收束，同时支持用户**按需手动开启**第三幕未来模拟。
- **`pro`（🔥 Pro）**：第一幕完整三筛 + 第二幕全量补齐（含 B4 过来人经验模拟、B5 情绪镜像、A_Recheck 二次复核）+ 第三幕完整未来模拟，面向出版级深度交付。
- **`ultra`（🌌 Ultra）**：在 Pro 之上全面拉高上下文预算与框架密度（全部哲学立场参与），并在 B9 之后追加 **Monte Carlo 多代理碰撞**（默认 800 分支 × 40 人格代理 + 8 个真实 LLM 委员会合议，可通过 `CLP_ULTRA_MC_*` 弹性调节）。

---

## 4. 关键工程防线

### 4.1 离线 / 零 API Key 演示韧性 (`backend/demo.py`)
当用户克隆仓库直接启动服务而未配置 `CLP_API_KEY`（或保留示例占位符 `sk-xxxxxxxx`），或显式传入 `--demo` / `CLP_DEMO_MODE=1` / 请求体 `{"demo": true}` 时：
- 系统自动切换至确定性离线演示管线，无需任何外部网络请求即可完整体验：
  - **公理对冲型问题**（如电车难题/拉格朗日悖论）-> 走通三层筛子与力场解剖（`lagrange_confirmed`）；
  - **现实两难型问题**（如换工作/转行/订阅/创业）-> 走通 Act 1 破局 + Act 2 卡点抹平与第三条路 + Act 3 顺逆风时间线 + 本地 Monte Carlo 采样；
  - 完整支持手动开启第三幕模拟、档位升级以及**完整版 PDF / AI 总结版 PDF** 实时生成。

### 4.2 前端单调进度锁 (`frontend/modules/decision-engine.js`)
针对 SSE 流与异步轮询并发到达可能引起的“旧快照把界面拉回上一阶段”问题，前端为每个 `decision_id` 维护单调递增进度秩（`getDecisionProgressRank`），低进度快照自动丢弃，确保多幕状态切换零闪烁、零回退。

### 4.3 时间线去同质化与跨平台矢量 PDF (`research/output_formatter.py`)
- **A/B 差异化重生成**：第三幕在生成两条路径时间线后自动计算叙事相似度；若高于阈值则注入反向槽位约束重生成，仍过高时启用强差异保底模板。
- **跨平台中文字体自适应**：`fpdf2` 渲染器自动探测 macOS（`STHeiti` / `PingFang`）、Linux（`NotoSansCJK` / `WenQuanYi`）与 Windows（`Deng.ttf` / `simhei.ttf` / `msyh.ttc`）系统字体，也支持通过 `CLP_PDF_FONT_PATH` 指定字体文件。
