# 认知拉格朗日点 · 项目手册（2026-04-08 最新完整版）

> **一句话现状**：决策主链路已完整跑通；本地外部声音快照、心理偏差识别、第三条路、后悔分数、概率对比、出版感 PDF 都已经接进真实链路，并用真实案例导出验证。

## 快速启动
```bash
python3 server.py
npm run dev
```

## 当前状态
- 决策主链路 ✅
- 粒子星图 ✅
- 本地外部声音快照注入（非伪实时抓取）✅
- 心理学偏差识别 ✅
- 第三条路 + 后悔最小化 ✅
- 模拟器 `tier_config` 崩溃已修复 ✅
- PDF 升级为星图封面 + 雷达图 + 彩色时间线 + 纪要式附录 ✅
- PDF 导出已拆成两份交付物：完整版 + AI 总结版 ✅
- PDF 的孤页 / 大留白问题已继续收紧 ✅
- PDF 已新增可选 WeasyPrint HTML/CSS 渲染入口，默认仍走 fpdf2 fallback ✅
- B1 旧快照 / render cache 拉回“问题 1/3”的主因已修复 ✅
- 档位已重排：`pro` 承接原 `ultra` 出版级推演能力，新的 `ultra` 在 Pro 基础上追加受控 Monte Carlo 多代理碰撞 ✅
- Ultra Monte Carlo 已进入第三幕结果、前端摘要卡和 PDF 摘要；默认真实调用 LLM 多委员会，Pro 才是省 token 选项 ✅
- PixiJS/WebGL 未来路径画布已接入可选 WebGL 渲染路径；默认 Canvas 星图仍保留为稳定主路径 ✅
- 既有 `npm run verify:all` 曾通过；B1 本轮新增探针已单独通过 ✅
- fresh `ultra` 验证案例：`1e1fae8b` ✅（注意：这是重排前的旧 Ultra 口径案例）
- 最新真实 PDF 导出已生成 ✅

## 任务已完成清单
- 所有 P0/P1 升级已落地

## 这轮新增的真实落地点

- 外部声音快照：
  - 后端新增 [`research/engine_b/external_signals.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/external_signals.py)
  - 当前快照数据在 [`data/external_signals/grok_membership_snapshot.json`](/Users/dutaorui/Desktop/claudecode/data/external_signals/grok_membership_snapshot.json)
  - 已接入 B2 / C1 / B9，并进入第三幕摘要卡片
- PDF 出版感升级：
  - 主链仍走 [`decision/reporting.py`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py) -> [`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
  - 已加：
    - 封面星图背景
    - 第三幕雷达图
    - 彩色时间线故事板
    - 附录从“系统日志”压缩为“形成纪要 + 关键节点摘录”
- AI 总结版 PDF：
  - 新增构建函数：[`build_decision_summary_report_pdf`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py)
  - 新增渲染函数：[`generate_decision_summary_pdf_report`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
  - 新增接口：`GET /api/final-report/summary-pdf`、`GET /api/decision/summary-report`
  - 前端在检测结果页、Engine B 建议页、模拟器结果页均新增 `AI 总结版 PDF` 按钮
  - 摘要版会优先调用 AI 生成客户可读文案；失败时自动降级为本地规则摘要，不影响完整版导出
  - 配置：[`CLP_SUMMARY_REPORT_MAX_TOKENS`](/Users/dutaorui/Desktop/claudecode/.env.clp.example)、[`CLP_SUMMARY_REPORT_DISABLE_AI`](/Users/dutaorui/Desktop/claudecode/.env.clp.example)
- PDF 留白继续修复：
  - 已定位并修掉几类真实排版问题：
    - 封面摘要被挤成单独一页
    - `Engine B 概览` 这类短块被拆成孤页
    - 时间线故事板翻页后仍沿用旧页 `y` 坐标，导致上半页大留白
    - 单个选项页只放一块时间线后，下半页完全空着
  - 当前做法：
    - 改为动态留位 / keep-with-next
    - 时间线卡片高度按实际节点数收缩
    - 单选项页在剩余空间不够放下一块故事板时，自动补“先动哪几步”
- B1 旧快照回退修复：
  - 修复位置：[`frontend/modules/decision-engine.js`](/Users/dutaorui/Desktop/claudecode/frontend/modules/decision-engine.js)
  - 状态存储：[`frontend/core/state.js`](/Users/dutaorui/Desktop/claudecode/frontend/core/state.js)
  - 核心策略：
    - 同一 `decision_id` 维护单调进度 rank
    - 低进度旧 SSE / 轮询快照不再覆盖高进度新视图
    - B1 追问页只允许在 `session.phase === "b1_diagnosis"` 且仍有待答问题时渲染
  - 回归探针：[`tests/stale_decision_snapshot_probe.mjs`](/Users/dutaorui/Desktop/claudecode/tests/stale_decision_snapshot_probe.mjs)
  - 已接入 `npm run verify:all`
- PDF WeasyPrint 可选渲染器：
  - 新增入口：[`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
  - 开关：[`CLP_PDF_RENDERER=weasyprint`](/Users/dutaorui/Desktop/claudecode/.env.clp.example)
  - 默认仍为 `CLP_PDF_RENDERER=fpdf`，保持既有稳定导出
  - 设置为 `weasyprint` / `html` / `auto` 时会优先尝试 HTML/CSS PDF
  - 本机未安装 WeasyPrint 或渲染失败时，会自动回退到 fpdf2
  - HTML/CSS 版已覆盖封面、目录锚点、摘要卡、B1-B5/C1、SVG 雷达图和彩色时间线
- Ultra / Pro 档位重排：
  - 配置入口：[`decision/tiers.py`](/Users/dutaorui/Desktop/claudecode/decision/tiers.py)
  - `pro` 现在承接原 `ultra` 的完整补全、第三幕深度推演和出版级预算口径
  - 新 `ultra` 在 Pro 之上新增 `enable_ultra_monte_carlo`
  - 新 `ultra` 的常规链路也已拉开差距，不再只靠 Monte Carlo：第一幕 `90000 -> 160000`，B7 `8192 -> 12288`，B9 `5120 -> 8192`
  - 采样控制可通过 [`CLP_ULTRA_MC_*`](/Users/dutaorui/Desktop/claudecode/.env.clp.example) 配置
  - 默认 `CLP_ULTRA_MC_LLM_PANELS=8`，会真实发起 8 个 LLM 委员会调用，并追加 1 次最终合议综合
- Ultra Monte Carlo 输出：
  - 多代理工厂和碰撞器：[`research/engine_b/agents.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/agents.py)
  - 第三幕接入点：[`research/engine_b/runtime.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/runtime.py)
  - 前端展示：[`frontend/components/timeline-view.js`](/Users/dutaorui/Desktop/claudecode/frontend/components/timeline-view.js)
  - PDF 展示：[`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
- PixiJS/WebGL 未来路径画布：
  - 组件能力：[`frontend/components/pixi-star-map.js`](/Users/dutaorui/Desktop/claudecode/frontend/components/pixi-star-map.js)
  - 渲染接线：[`frontend/core/renderer.js`](/Users/dutaorui/Desktop/claudecode/frontend/core/renderer.js)
  - 当前通过 `?webgl=1` 显式启用，避免默认替换稳定 Canvas 星图

## 最新验证

- 核心全链：
  - `npm run verify:all`
  - 结果：既有记录通过；本轮文档同步未重新跑完整全量套件
- 这轮 PDF / 外部声音改动：
  - `python3 -m py_compile research/output_formatter.py decision/reporting.py research/engine_b/runtime.py research/engine_b/agents.py research/engine_b/models.py research/engine_b/external_signals.py`
  - 结果：通过
- 真实案例重新导出 PDF：
  - 决策：`1e1fae8b`
  - 最新文件：
    - [`decision_job-a22e58b3_session-856d3591_20260408-130558.pdf`](/Users/dutaorui/Desktop/claudecode/research/output/decision_reports/decision_job-a22e58b3_session-856d3591_20260408-130558.pdf)
- 这轮版式回归：
  - 用真实案例 `1e1fae8b` 本地重生 PDF 并逐页检查
  - 已确认：
    - 原“空白第 2 页”消失，目录直接顶上
    - 原“孤立 Engine B 概览页”不再由重复摘要撑开
    - 第 14 页顶部大留白已修掉
    - 第 13 / 15 页剩余空白改为补入“先动哪几步”内容
- B1 旧快照回归：
  - `node tests/stale_decision_snapshot_probe.mjs`
  - `env PW_BROWSER=webkit node tests/stale_decision_snapshot_probe.mjs`
  - 结果：Chromium + WebKit 均通过
- PDF WeasyPrint fallback 回归：
  - `CLP_PDF_RENDERER=weasyprint python3 -c "...generate_decision_pdf_report(...)"`
  - 结果：本机缺 `weasyprint` 时自动回退到 fpdf2，并生成 `/tmp/clp_weasy_fallback_test.pdf`
- Ultra Monte Carlo / Pixi 接线回归：
  - `python3 -m py_compile decision/tiers.py research/engine_b/agents.py research/engine_b/runtime.py research/output_formatter.py`
  - `node --check app.js frontend/components/timeline-view.js frontend/components/pixi-star-map.js frontend/core/renderer.js frontend/components/tier-selector.js frontend/modules/decision-engine.js`
  - `python3 -m unittest tests.test_decision_tier_regression tests.test_engine_b_runtime tests.test_engine_b_agents`
  - `npm run build`
  - 合成 PDF 冒烟：生成 `/tmp/clp_ultra_monte_pdf_test.pdf`
- AI 总结版 PDF 回归：
  - `python3 -m unittest tests.test_decision_summary_report`
  - `CLP_SUMMARY_REPORT_DISABLE_AI=1` 本地降级路径已能生成 `/tmp/clp_ai_summary_smoke.pdf`

## 当前需要如实说明的边界

- “外部声音”目前是**本地整理快照**，不是请求时实时联网抓取
- 当前只内置了 `Grok 会员` 这组快照；后续可按同样格式继续扩充
- PDF 虽然已经明显更像正式出版物，但仍然是 `fpdf2` 原生矢量绘制，不是 InDesign 级排版系统
- WeasyPrint 目前是可选增强入口，不是强依赖
  - 如果要真正启用，需要额外安装 `weasyprint`
  - 未安装时不会影响现有 PDF 导出
- 新 Ultra 的 Monte Carlo 默认先按“1000万 token”预算口径设计，不是每次点击都会实际消耗到该量级
  - 这个预算是可浮动的，可用 `CLP_ULTRA_MC_ESTIMATED_TOKENS` 改成 3000 万、5 亿或其他值
  - 默认 Ultra 会跑真实 LLM 委员会：8 个委员会调用 + 1 次最终合议综合
  - 只有显式配置 `CLP_ULTRA_MC_LLM_PANELS=0` 才会退回本地采样
  - 如果不想烧 token，请选 `pro`
- PixiJS/WebGL 未来路径画布当前是显式开关能力
  - 使用 `http://127.0.0.1:4173/?webgl=1` 启用
  - 默认仍走 Canvas 主星图，避免旧星图交互被一次性替换
- 目录页本身仍然偏轻，这属于内容密度问题，不是当前发现的排版 bug
- 导出 PDF 时会看到 `feat/morx NOT subset` 这类字体子集提示
  - 这是 `STHeiti` + `fpdf2` 的常见控制台提示
  - 当前不影响 PDF 正常生成
- B1 回退问题目前修的是“旧快照覆盖新阶段”的主因
  - 已有 Chromium / WebKit 探针覆盖
  - 仍建议在用户实机 Safari 上再跑一轮完整 B1 -> B2/B3/C1，确认没有额外遮挡或缓存类问题

## 当前推荐交接入口

- 对外介绍先看 [`PROJECT_OVERVIEW.md`](/Users/dutaorui/Desktop/claudecode/PROJECT_OVERVIEW.md)
- 展示 / 合作对接先看 [`SHOWCASE_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/SHOWCASE_HANDOFF.md)
- 展示路演稿先看 [`SHOWCASE_PITCH.md`](/Users/dutaorui/Desktop/claudecode/SHOWCASE_PITCH.md)
- 升级提案请看 [`EXECUTABLE_UPGRADE_PLAN.md`](/Users/dutaorui/Desktop/claudecode/EXECUTABLE_UPGRADE_PLAN.md)
- 先看 [`TECHNICAL_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/TECHNICAL_HANDOFF.md)
- 再用这个案例做复测：
  - [http://127.0.0.1:4173/api/decision/status?id=1e1fae8b](http://127.0.0.1:4173/api/decision/status?id=1e1fae8b)
