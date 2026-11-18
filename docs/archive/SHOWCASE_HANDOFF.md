# 认知拉格朗日点 · 展示 / 对接交接文件

> 用途：发给协作者、展示对象、接手开发者或其他 AI。  
> 目标：让对方 3 分钟内看懂项目现状，10 分钟内跑起演示。

---

## 1. 项目当前状态

截至 **2026-04-08**，项目已进入“可展示、可复测、可继续迭代”的阶段。

当前真实状态：

- 决策主链路已完整跑通
- 第三幕未来模拟已修复真实崩溃问题
- 本地外部声音快照已接进真实链路
- 决策心理偏差识别已接入
- 第三条路发现已接入
- 后悔分数和走势概率已接入
- PDF 已升级为更完整的出版感交付
- PDF 现在支持双报告交付：完整版 + AI 总结版
- PDF 的大留白和孤页问题已继续收紧
- PDF 已新增可选 WeasyPrint HTML/CSS 渲染入口，默认保留 fpdf2 稳定导出
- B1 卡点诊断旧快照回退问题已完成主因修复
- `pro` 已承接旧 `ultra` 的出版级推演能力
- 新 `ultra` 已新增受控 Monte Carlo 多代理碰撞，结果会进入第三幕摘要和 PDF
- PixiJS/WebGL 未来路径画布已作为可选增强接入，默认仍保留稳定 Canvas 星图
- Web 前端、后端、SSE、报告导出均已成型
- 既有 `npm run verify:all` 曾通过；B1 本轮新增探针已单独通过

---

## 2. 给别人一句话介绍

> 这是一个 AI 决策引擎：用户输入一个纠结问题，系统先判断它到底有没有标准答案；如果有，就定位卡点、补齐缺失认知，再把不同选择的未来推演出来；如果没有，就证明它为什么无解。

---

## 3. 推荐展示路径

### 3.1 直接展示网页

启动：

```bash
python3 server.py
npm run dev
```

打开：

- [http://127.0.0.1:4173](http://127.0.0.1:4173)

### 3.2 直接展示一个已完成案例

推荐 `decision_id`：

- `1e1fae8b`

查看接口：

- [http://127.0.0.1:4173/api/decision/status?id=1e1fae8b](http://127.0.0.1:4173/api/decision/status?id=1e1fae8b)

这条案例的问题是：

- `我该继续留在稳定工作，还是辞职读研转行做AI产品？`

这条案例已经确认包含：

- B1 卡点诊断
- 外部声音快照摘要
- 心理偏差提醒
- 第三条路
- 手动启动第三幕
- 完整未来模拟
- 岔路口 / 生存方案 / 行动地图

最新已确认存在的真实 PDF 产物：

- [`decision_job-a22e58b3_session-856d3591_20260408-130558.pdf`](/Users/dutaorui/Desktop/claudecode/research/output/decision_reports/decision_job-a22e58b3_session-856d3591_20260408-130558.pdf)

---

## 4. 当前产品结构

### 4.1 四档思考深度

- `quick`
  - 快速方向判断
- `deep`
  - 完整分析
- `pro`
  - 出版级推演，承接旧 Ultra 能力
- `ultra`
  - 高烧 Monte Carlo 多代理碰撞，在 Pro 基础上追加分支采样

### 4.2 三幕流程

1. 第一幕：真实检测
2. 第二幕：决策突破
3. 第三幕：未来模拟

### 4.3 当前新增能力

- 本地外部声音快照注入
- 心理偏差提醒
- 第三条路发现
- 后悔分数与概率对比
- Ultra Monte Carlo 平滑概率分布 / 置信区间 / 分歧热区
- 出版感 PDF 报告
- AI 总结版 PDF 报告

---

## 5. 这次最新修复

### 5.0 本轮档位与星图升级

这轮把旧 `ultra` 的深度推演能力迁到了 `pro`，新的 `ultra` 不再只是“更大一点的 Pro”，而是在 Pro 第三幕完成后追加受控 Monte Carlo 多代理碰撞。随后又把 Ultra 的常规链路也加厚一档：第一幕、B1-B9、经验案例、模拟深度、稳定性/振荡轮次都高于 Pro。

关键落点：

- 档位配置：[`decision/tiers.py`](/Users/dutaorui/Desktop/claudecode/decision/tiers.py)
- Monte Carlo 引擎：[`research/engine_b/agents.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/agents.py)
- 第三幕接入：[`research/engine_b/runtime.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/runtime.py)
- 前端结果展示：[`frontend/components/timeline-view.js`](/Users/dutaorui/Desktop/claudecode/frontend/components/timeline-view.js)
- PixiJS 未来路径画布：[`frontend/components/pixi-star-map.js`](/Users/dutaorui/Desktop/claudecode/frontend/components/pixi-star-map.js)

说明：默认 Ultra Monte Carlo 会真实调用 8 个 LLM 委员会，并追加 1 次最终合议综合；只有显式设置 `CLP_ULTRA_MC_LLM_PANELS=0` 才会退成本地采样。PixiJS 画布当前通过 `?webgl=1` 显式启用。

### 5.1 模拟器后端崩溃已修复

问题：

- 第三幕在时间线阶段会因为 `tier_config` 初始化顺序错误而崩溃
- 报错：
  - `cannot access local variable 'tier_config' where it is not associated with a value`

修复位置：

- [`research/engine_b/runtime.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/runtime.py#L1122)

回归测试：

- [`tests/test_engine_b_runtime.py`](/Users/dutaorui/Desktop/claudecode/tests/test_engine_b_runtime.py#L365)

### 5.2 Safari 雷达图区空白已修复

问题：

- Safari / WebKit 下，“后悔与走势雷达”会把 canvas 错误拉成超高区域
- 用户表现为：
  - 图例有了
  - 下面是一整块空白

修复位置：

- [`frontend/components/timeline-view.js`](/Users/dutaorui/Desktop/claudecode/frontend/components/timeline-view.js)
- [`style.css`](/Users/dutaorui/Desktop/claudecode/style.css)

处理方式：

- 给雷达图加独立固定高度容器
- 避免 Safari 把 canvas 高度错误撑到几千像素

### 5.3 PDF 报告已完成一轮出版感升级

主链仍走：

- [`decision/reporting.py`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py)
- [`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)

这轮已落地：

- 星图封面
- 后悔/走势雷达图
- 彩色时间线故事板
- 附录压缩为“形成纪要 + 关键节点摘录”
- 几类真实留白修复：
  - 第 2 页空白页
  - 摘要中的孤立概览页
  - 时间线翻页后的顶部大留白
  - 单选项页下半页完全空着

### 5.4 AI 总结版 PDF 已接入

这轮新增了第二份可交付报告：用户可以同时导出“完整版 PDF”和“AI 总结版 PDF”。完整版保留全流程、时间线、日志和附录；AI 总结版只保留客户最容易读懂的结论、理由、7 天行动、三种未来情景、风险护栏和备忘。

关键落点：

- 后端接口：`GET /api/final-report/summary-pdf`
- 决策接口：`GET /api/decision/summary-report?id=xxx`
- 构建入口：[`decision/reporting.py`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py)
- 渲染入口：[`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
- 前端按钮：检测结果页、Engine B 建议页、模拟器结果页均已新增 `AI 总结版 PDF`

实现策略：

- 默认优先调用 AI 把复杂材料压缩成客户可读摘要
- 如果 AI 总结失败，会自动退回本地规则摘要
- 不影响原来的完整版 PDF 导出

### 5.5 B1 卡点诊断旧快照回退已修复主因

问题：

- 用户在 Safari 上选择 B1 答案后，页面偶发回到“问题 1/3”
- 后端实际已经进入 B2/B3/C1，但前端被旧 SSE / 轮询快照覆盖回旧视图

修复位置：

- [`frontend/modules/decision-engine.js`](/Users/dutaorui/Desktop/claudecode/frontend/modules/decision-engine.js)
- [`frontend/core/state.js`](/Users/dutaorui/Desktop/claudecode/frontend/core/state.js)

处理方式：

- 同一 `decision_id` 维护单调进度 rank
- 低进度旧快照不能覆盖高进度新视图
- B1 追问页只在 `b1_diagnosis` 阶段渲染

回归测试：

- [`tests/stale_decision_snapshot_probe.mjs`](/Users/dutaorui/Desktop/claudecode/tests/stale_decision_snapshot_probe.mjs)
- Chromium + WebKit 已通过

### 5.6 WeasyPrint PDF 渲染器已接入为可选增强

现状：

- 现有稳定链路仍默认使用 fpdf2
- 新增 `CLP_PDF_RENDERER=weasyprint` / `auto` 开关
- 本机未安装 WeasyPrint 或 HTML/CSS 渲染失败时，会自动回退到 fpdf2

已覆盖：

- HTML/CSS 封面
- 目录锚点
- 摘要卡
- B1-B5 / C1 章节
- SVG 雷达图
- 彩色未来时间线

修复位置：

- [`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
- [`.env.clp.example`](/Users/dutaorui/Desktop/claudecode/.env.clp.example)

---

## 6. 已验证结果

本轮已确认通过：

- `python3 -m unittest tests.test_engine_b_runtime`
- `npm run verify:all`
  - 既有记录通过；本轮只新增并单独验证 B1 旧快照探针
- `python3 -m py_compile research/output_formatter.py decision/reporting.py research/engine_b/runtime.py research/engine_b/agents.py research/engine_b/models.py research/engine_b/external_signals.py`
- `node tests/stale_decision_snapshot_probe.mjs`
- `env PW_BROWSER=webkit node tests/stale_decision_snapshot_probe.mjs`
- `CLP_PDF_RENDERER=weasyprint ... generate_decision_pdf_report(...)`
  - 本机缺 WeasyPrint 时已确认自动回退 fpdf2 并成功生成 PDF
- fresh `ultra` live 决策（档位重排前旧 Ultra 口径案例）：
  - `1e1fae8b`
- Ultra Monte Carlo / Pixi 接线回归：
  - `python3 -m unittest tests.test_decision_tier_regression tests.test_engine_b_runtime tests.test_engine_b_agents`
  - `npm run build`
  - 合成 PDF 冒烟：`/tmp/clp_ultra_monte_pdf_test.pdf`
- PDF 版式人工回看：
  - 已对用户指出的第 2 / 6 / 13 / 14 页留白做定向排查并修复

验证结论：

- 决策链路能从第一幕走到第三幕
- 新增字段不是“写在代码里没用上”，而是已在真实完成案例里产出
- PDF 现在仍有自然留白，但已不是之前那种明显错误分页

---

## 7. 当前还剩什么可继续做

当前也需要如实说明几个边界：

- “外部声音”目前是本地整理快照，不是实时联网抓取
- 当前快照样本量还不大，主要用于证明这条链路已经打通
- PDF 已经明显更像正式出版物，但仍不是 InDesign 级排版系统
- WeasyPrint 目前是可选增强，不是默认强依赖；展示前如果要看 HTML/CSS 版本，需要先安装 `weasyprint`
- 目录页会相对轻一些，这属于内容密度而不是当前已知 bug
- B1 回退已修旧快照主因，但仍建议展示前用实机 Safari 跑一轮完整 B1 -> B2/B3/C1

如果后续继续迭代，优先建议：

1. 外部声音快照继续扩容
2. PDF 报告继续做精修而不是重做
3. 旧研究台残留继续清理
4. style.css 继续减重
5. 继续优化上游超时时的体验
6. 把“流式思考输出”再做得更像真实连续推演

---

## 8. 如果是给其他 AI 接手

推荐阅读顺序：

1. [`PROJECT_OVERVIEW.md`](/Users/dutaorui/Desktop/claudecode/PROJECT_OVERVIEW.md)
2. [`HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/HANDOFF.md)
3. [`TECHNICAL_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/TECHNICAL_HANDOFF.md)

如果只看一个文件，请先看：

- [`TECHNICAL_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/TECHNICAL_HANDOFF.md)
