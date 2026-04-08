# 认知拉格朗日点 · 技术交接文档

> 目标读者：接手这个项目的开发者或 AI。  
> 这份文档基于当前仓库真实实现，不再按最早规格书叙述。

> 2026-04-08 起请优先看「0. 最新交接快照」。
> 下文仍保留部分 2026-04-07 的历史验收记录，便于追溯，但不应覆盖最新结论。

---

## 0. 2026-04-08 最新交接快照

### 0.1 当前一句话状态

当前仓库的决策主链路已经能从第一幕检测一路跑到第三幕未来模拟，并且这次新增的本地外部声音快照、心理偏差提醒、第三条路、后悔分数、概率对比、出版感 PDF 都已经在真实新决策里跑出来了。

### 0.2 今天刚落地的关键修复

- 修复了第三幕未来模拟的真实后端崩溃：
  - 文件：[`research/engine_b/runtime.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/runtime.py#L1122)
  - 问题：`_run_simulator_async()` 在提炼 A/B 选项时先使用 `tier_config`，后面才赋值，导致模拟器在 `b7_sim_timelines` 后报错：
    - `cannot access local variable 'tier_config' where it is not associated with a value`
  - 处理：把 `tier_config = _get_session_tier_config(session)` 提前到函数开头
- 新增了专门的回归测试：
  - 文件：[`tests/test_engine_b_runtime.py`](/Users/dutaorui/Desktop/claudecode/tests/test_engine_b_runtime.py#L365)
  - 覆盖点：保证第三幕在 choice extraction 阶段能正确读取当前 `ultra.choice_extract_max_tokens = 2400`，并最终完成到 `SIMULATOR_COMPLETE`
- 新增了本地外部声音快照注入：
  - 文件：[`research/engine_b/external_signals.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/external_signals.py)
  - 数据：[`data/external_signals/grok_membership_snapshot.json`](/Users/dutaorui/Desktop/claudecode/data/external_signals/grok_membership_snapshot.json)
  - 现状：已接入 B2 / C1 / B9，并进入第三幕结果摘要
- 完成了 PDF 出版感升级与附录压缩：
  - 主链仍走 [`decision/reporting.py`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py) -> [`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
  - 已落地：
    - 星图封面
    - 后悔/走势雷达图
    - 彩色时间线故事板
    - 附录从“系统导出日志”压缩为“形成纪要 + 关键节点摘录”
- 新增了可选 WeasyPrint HTML/CSS PDF 渲染器：
  - 文件：[`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
  - 新增函数：`generate_decision_weasyprint_report()`
  - 开关：`CLP_PDF_RENDERER=weasyprint` / `html` / `auto`
  - 默认：仍为 `fpdf`，避免缺依赖时破坏当前稳定导出
  - fallback：WeasyPrint 未安装或渲染失败时自动回退到 fpdf2
  - 示例配置：[`CLP_PDF_RENDERER=fpdf`](/Users/dutaorui/Desktop/claudecode/.env.clp.example)
- 修复了 PDF 的几类真实留白 / 孤页问题：
  - 文件：[`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
  - 复现来源：用户提供的 [`grok_job-6128ca21_session-69372b41_20260408-135823.pdf`](/Users/dutaorui/Downloads/grok_job-6128ca21_session-69372b41_20260408-135823.pdf)
  - 典型问题：
    - 第 2 页几乎整页留白
    - 第 6 页只剩极少概览内容却单独占页
    - 第 14 页顶部大留白
    - 第 13 / 15 页下半页空得过头
  - 根因：
    - 封面末尾摘要被硬挤到下一页
    - 摘要页里的短块没有 keep-with-next 保护
    - `timeline_storyboard()` 先记旧页 `y`，翻页后仍沿用旧坐标绘制
    - 单选项页缺少“剩余空间补位”逻辑
  - 处理：
    - 去掉封面尾部的重复结论块
    - 对摘要 / 对比 / 面板块补 `ensure_room()`
    - 时间线故事板按实际节点数动态缩高，并在翻页后重新取 `y`
    - 选项页剩余空间不够放下一块故事板时，自动补“如果真选这条路，先动哪几步”

### 0.3 今天的真实验收结果

- `python3 -m unittest tests.test_engine_b_runtime`
  - 结果：通过
- `npm run verify:all`
  - 结果：通过
  - 末尾输出：`✅ 全链路验证通过！`
- `python3 -m py_compile research/output_formatter.py decision/reporting.py research/engine_b/runtime.py research/engine_b/agents.py research/engine_b/models.py research/engine_b/external_signals.py`
  - 结果：通过
- PDF 版式局部回归：
  - 用真实案例 `decision_id = 1e1fae8b` 重新生成本地回归 PDF，并逐页检查 `2 / 5 / 6 / 13 / 14 / 15`
  - 结果：通过
  - 已确认：
    - 旧“空白第 2 页”消失
    - 旧“Engine B 概览孤页”消失
    - 第 14 页顶部大留白消失
    - 第 13 / 15 页空白被补位卡片吃掉一部分
- 本轮 fresh `ultra` live 决策已完整跑通（说明：这是档位重排前的旧 Ultra 口径案例；当前 `pro` 已承接该能力，新 `ultra` 另加 Monte Carlo）：
  - `decision_id = 1e1fae8b`
  - 状态：`completed`
  - 包含字段：
    - `external_signals`
    - `decision_biases`
    - `bias_reminder`
    - `third_path`
    - `regret_score_a`
    - `regret_score_b`
    - `probability_optimistic`
    - `probability_baseline`
    - `probability_pessimistic`
- 最新真实 PDF 导出：
  - [`decision_job-a22e58b3_session-856d3591_20260408-130558.pdf`](/Users/dutaorui/Desktop/claudecode/research/output/decision_reports/decision_job-a22e58b3_session-856d3591_20260408-130558.pdf)

### 0.4 当前建议用来复测的真实案例

- 推荐直接复测：
  - 决策详情接口：
    - [http://127.0.0.1:4173/api/decision/status?id=1e1fae8b](http://127.0.0.1:4173/api/decision/status?id=1e1fae8b)
  - 这条案例的问题：
    - `我该继续留在稳定工作，还是辞职读研转行做AI产品？`
- 这条案例已经确认出现了：
  - 第二幕卡点诊断
  - 心理偏差提醒
  - 第三条路
  - 手动启动第三幕
  - 完整未来模拟
  - 行动地图 / 岔路口 / 最坏情况方案

### 0.5 当前用户可见的真实档位

当前产品主档位以四档为准：

- `quick`
- `deep`
- `pro`
- `ultra`

补充说明：

- 文档下方保留的 `flash / panorama` 提法属于旧阶段命名或兼容别名记录
- 接手时请以当前代码里的 [`decision/tiers.py`](/Users/dutaorui/Desktop/claudecode/decision/tiers.py) 为准
- 当前 `pro` 承接原 `ultra` 的出版级推演能力
- 当前 `ultra` 在 Pro 基础上新增受控 Monte Carlo 多代理碰撞
- 当前 `ultra` 的常规链路也已比 Pro 更厚：第一幕 `90000 -> 160000`，B1 `4096 -> 6144`，B7 `8192 -> 12288`，B9 `5120 -> 8192`
- `CLP_ULTRA_MC_*` 环境变量用于控制采样量、代理数量和 LLM 委员会调用规模

### 0.6 当前仍要注意的风险

- 上游模型慢或大 JSON 输出不稳定时，模拟器仍可能进入 `local_fast` fallback
  - 这是当前为了“别让用户一直转圈最后啥都没有”而保留的保底策略
- “外部声音”目前是本地整理快照，不是请求时实时联网抓取
- 当前只内置了 `Grok 会员` 这组快照；后续可以继续按相同 JSON 结构扩充
- 历史旧决策不会自动补出真正的第三条路内容
  - 新字段的真实效果请用新跑出来的决策验证，不要只看旧 `decision_id`
- PDF 虽然已经明显更像正式出版物，但仍然是 `fpdf2` 原生矢量绘制，不是 InDesign 级排版系统
- WeasyPrint 目前只是可选增强，不是默认强依赖
  - 本机检测结果：`weasyprint` 未安装
  - 已验证设置 `CLP_PDF_RENDERER=weasyprint` 时会回退 fpdf2 并生成 PDF
- 新 Ultra 的 Monte Carlo 默认先按 1000 万 token 预算口径设计，不代表默认每次都会真实消耗到该量级
  - 预算口径可通过 `CLP_ULTRA_MC_ESTIMATED_TOKENS` 浮动配置
  - 默认 `CLP_ULTRA_MC_LLM_PANELS=8`，会真实发起 8 个 LLM 委员会调用，并追加 1 次最终合议综合
  - 只有显式设置 `CLP_ULTRA_MC_LLM_PANELS=0` 才会退回 `llm_mode=local_sampling`
  - 如果不想烧 token，请使用 `pro`
- PixiJS/WebGL 未来路径画布当前走显式开关：`?webgl=1`
  - 默认仍走 Canvas 主星图，避免旧星图浏览/命中/历史节点一次性回归风险
- 目录页本身仍会显得偏轻，这是当前内容量决定的自然留白，不是已知排版 bug
- 导出 PDF 时会出现 `feat/morx NOT subset` 这类字体子集提示
  - 这是 `STHeiti` + `fpdf2` 的常见控制台提示
  - 当前不影响 PDF 正常生成
- 下文保留的旧验收记录里有部分“三档”“flash / panorama”表述
  - 这些是历史记录，不是当前前台产品文案

---

## 1. 项目是什么

这个项目是一个本地运行的 Web 应用，包含两条主线：

1. 研究主线  
   用批处理方式从候选问题里筛选“认知拉格朗日点”，并做力量解剖、稳定性、振荡、断层线、隧道效应等分析。

2. 决策主线（Engine B）  
   面向单个用户问题，先做卡点诊断，再补信息/补框架/补经验/补情绪，然后给出建议，并进一步做“选择模拟器”来展示未来时间线。

一句话总结：

> 用户输入一个纠结问题，系统判断它到底是“真无解”还是“暂时看不见答案”，并给出结构化输出。

---

## 2. 当前实现状态

目前仓库已经不是纯研究脚本，而是一个可本地交互使用的产品雏形。

已经可用的部分：

- 本地 Web 控制台与星图主页
- 首页新版 Hero、四档思考深度选择器与输入主 CTA
- API 配置保存
- 单题真实检测（不是前端 mock）
- `/api/decision/*` 产品协议第一版
- 当前主档位：`quick / deep / pro / ultra`
- Engine B 完整交互链路
- 选择模拟器
- 会话恢复
- 顶部连续思考流 + 处理过程 trace 展示
- 模拟器失败态稳定展示
- 模拟器超时自动降级
- 最终 PDF / 文本报告导出
- AI 总结版 PDF 导出
- 本地外部声音快照注入
- PDF 出版感升级：
  - 星图封面
  - 雷达图
  - 彩色时间线
  - 纪要式附录
- 检测页 / Engine B / 模拟器视图模块化
- 提交按钮 E2E 与 flicker probe 自动化验证

当前最重要的现实结论：

- `decision/tiers.py`、`decision/pipeline.py`、`decision/classifier.py` 已经落地
- `/api/decision/start/status/events/history/answer/simulate/start/upgrade/report` 已接到真实后端
- 前端“提交回答按不动”的问题已修复，并有浏览器自动化测试覆盖
- recheck 与 simulator 的竞态已处理，recheck 未结束时不会抢跑第三幕
- `decision/pipeline.py` 已增加 recheck 等待守卫，不会再因为自动启动模拟器而刷出同一句失败日志
- 页面闪烁问题已通过渲染签名去重压住，当前 flicker probe 结果为 `0 mutation`
- 检测页顶部思考流已支持连续输出、折叠查看和重复内容归并
- 首页标题截断问题已修复，首页 Hero 与移动端主视觉已经过 smoke 验证
- `decision_deep` 检测已经轻量化，避免深度模式把用户卡在漫长筛子里
- `quick` 快速结果不再是纯模板文案，而会把 `analysis_summary` / `balance_rationale` 融进快速建议
- Engine B 第二幕现在真的受 `tier` 配置驱动：`deep` 不再偷跑 B4/B5，`ultra` 会完整补齐经验与情绪层
- 第三幕默认改为手动启动，C1 结论出来后由用户决定是否继续消耗 token 做未来模拟
- `/api/decision/events` 前端已补 SSE 自动重连，临时断线后会做指数退避恢复
- `/api/decision/upgrade` 现在是真升级，不再偷偷新开一单；升级后会保留同一个 `decision_id`
- `server_core.py` 已拆成 39 行兼容 facade，核心逻辑已迁往 `server_runtime.py` / `server_detection.py` / `server_shared.py`
- 完成态 simulator 输出现在会自动补齐摘要 / 洞察 / 行动地图，历史会话不再只剩空壳
- PDF 生成器已升级为封面、目录、时间线叙事页、行动地图页、完整日志、结构化轨迹一体化布局
- PDF 排版现在额外具备：
  - 动态留位，避免短块被拆成孤页
  - 时间线故事板按实际节点数缩高
  - 单选项页的剩余空间补位
- PDF 已能展示 Ultra Monte Carlo 碰撞摘要，包括采样规模、平滑概率、置信区间和关键分歧热区
- PDF 导出现在是双报告交付：`完整版 PDF` 走原完整报告，`AI 总结版 PDF` 走新增摘要报告；摘要版优先调用 AI 压缩客户可读文案，失败自动降级为本地规则摘要
- AI 总结版 PDF 可通过 `CLP_SUMMARY_REPORT_MAX_TOKENS` 控制总结调用上限；如需演示离线降级路径，可设 `CLP_SUMMARY_REPORT_DISABLE_AI=1`
- 全页 `fault-map-view` DOM + CSS 已移除，首页第二个入口已改成定位最近决策记录，旧研究台残留进一步收缩
- 新版 Engine B / Simulator 已包含：
  - 决策心理学偏差识别
  - 价值观权重摘要
  - 第三条路发现
  - 后悔分数和概率对比
- 第三幕 `tier_config` 未初始化导致的崩溃已修复，并已通过 live 决策复验
- `pro` / `ultra` 已完成档位重排：`pro` 等于旧 Ultra 出版级推演，新 `ultra` 追加 Monte Carlo 多代理碰撞
- PixiJS/WebGL 未来路径画布已在 [`frontend/components/pixi-star-map.js`](/Users/dutaorui/Desktop/claudecode/frontend/components/pixi-star-map.js) 和 [`frontend/core/renderer.js`](/Users/dutaorui/Desktop/claudecode/frontend/core/renderer.js) 接线，当前通过 `?webgl=1` 启用
- 上游模型网关对大 JSON 输出仍可能返回 `504`
- 为了避免整轮失败，模拟器仍保留本地 fallback
- 静态资源已加入 `no-store`，Safari/缓存问题已显著下降

也就是说：

- 现在最主要的风险不再是“按钮没绑上”
- 而是上游模型稳定性与旧研究台残留带来的工程复杂度
- 但决策主链路本身已经可跑、可测、可恢复、可导出

### 2.1 2026-04-07 历史验收记录

本轮重新核过的结果：

- `python3 -m py_compile server.py server_core.py server_shared.py server_runtime.py server_detection.py decision/pipeline.py research/api.py research/engine_b/runtime.py`
  结果：通过
- `python3 -m unittest tests.test_api_json_rescue tests.test_engine_b_runtime tests.test_decision_pipeline_normalization tests.test_decision_tier_regression tests.test_decision_api_smoke`
  结果：通过
- `python3 -m py_compile research/output_formatter.py decision/reporting.py server.py`
  结果：通过
- `npm run build`
  结果：成功产出最新 `dist/`
- `curl -s http://127.0.0.1:4173/api/decision/tiers`
  结果：当时成功返回旧阶段的三档配置
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
- `env DECISION_ID=b0801898 node tests/decision_full_flow_live.mjs`
  结果：live 决策链路跑到 `completed`，新会话不再卡在 `b1_diagnosis`
- `node tests/decision_full_flow_live.mjs flash`
  结果：`5d81d14c` 完整跑到 `completed`
- `node tests/decision_full_flow_live.mjs deep`
  结果：`945ca3cd` 完整跑到 `completed`
- `node tests/decision_full_flow_live.mjs panorama`
  结果：`5e36212f` 完整跑到 `completed`
- `python3 -m unittest tests.test_decision_upgrade`
  结果：通过，验证 `flash -> deep` 复用同一 `decision_id`，`deep -> panorama` 复用第一幕快照重开第二幕
- live 升级验证：`08a500d9`
  结果：先以 `flash` 完成，再调用 `/api/decision/upgrade` 升到 `deep`，保持同一 `decision_id` 并最终跑到 `completed`
- `python3 -m unittest tests.test_engine_b_runtime tests.test_flash_classifier`
  结果：通过
- 最新 PDF 产物：
  - `research/output/decision_reports/decision_job-82afe344_session-6b4ef986_20260407-125755.pdf`
  - 封面缩略图人工检查：`/tmp/decision_job-82afe344_session-6b4ef986_20260407-125755.pdf.png`

### 2.1.1 2026-04-07 晚间追加交接补充

这一轮是围绕“未来模拟器消失 / 点了没反应”做的定向修复，但用户在 Safari 上又复现出两处新问题，所以这里单独追加一段，方便下一位 AI 直接接手。

本轮已经写入代码并重新构建 `dist/` 的改动：

- `decision/tiers.py`
  - 给 `deep` 增加 `allow_manual_simulation: True`
  - `deep` 的 budget 文案改成“默认停在第二幕，但允许按需手动进入第三幕”
- `research/engine_b/runtime.py`
  - `start_simulator()` 不再只认 `enable_simulation`
  - 只要 `allow_manual_simulation` 为真，也允许进入第三幕
- `decision/pipeline.py`
  - `_update_job()` 现在会先 hydrate 已持久化的 completed 决策，再做状态更新
  - `_monitor_engineb_flow()` 不会在 `deep` 已进入 `b6/b7/b8/b9` 或已有 `sim_questions` 时，又把决策错误打回 `completed`
  - `DecisionManager.start_simulator()` 启动第三幕后会显式把决策写回 `running / act3 / b6_sim_params`
- `frontend/modules/decision-engine.js`
  - tier fallback 现在内建 `allow_manual_simulation`
  - `deep` / `pro` / `ultra` 的模拟器按钮显示逻辑已重写
  - 已在模拟器阶段时，重新点击按钮会强制 `renderDecisionSession(..., { force: true })`
  - 对 completed 历史决策，重新点“启动选择模拟器”会重新走 `/api/decision/simulate/start`，而不是只在前端空转
- `tests/simulator_entry_regression.mjs`
  - 新增浏览器级回归
  - 覆盖 “建议页能看到模拟器按钮” 和 “点击后能进入第三幕”

这一轮重新执行并通过的关键验证：

- `python3 -m py_compile decision/tiers.py research/engine_b/runtime.py decision/pipeline.py server.py`
  - 结果：通过
- `node --check frontend/modules/decision-engine.js`
  - 结果：通过
- `node --check tests/simulator_entry_regression.mjs`
  - 结果：通过
- `npm run build`
  - 结果：通过，`4173` 实际使用的是最新 `dist/`
- `env PW_BROWSER=chromium DEEP_DECISION_ID=098da099 node tests/simulator_entry_regression.mjs`
  - 结果：通过
  - 输出要点：
    - `deepBefore.display = "block"`
    - `deepAfter.step5Active = true`
    - `deepAfter.simQuestionVisible = true`
- `env PW_BROWSER=chromium DEEP_DECISION_ID=098da099 ULTRA_DECISION_ID=4430a3ba node tests/simulator_entry_regression.mjs`
  - 结果：通过
  - 输出要点：
    - `deep` 与 `ultra` 两条已完成决策都能从建议页重新进入第三幕

数据库侧我也补核了一次：

- `decision_id = 098da099`
  - 触发手动模拟器后，SQLite 中状态已变成：
  - `status = running`
  - `phase = act3`
  - `step = b6_sim_params`
  - `engineb_session.phase = b6_sim_params`

但请注意：

- 上面这些通过的是 Chromium 真实浏览器回归
- 用户在 Safari 上仍反馈出两个新问题，见下方“15.6 / 15.7”
- 所以下一位 AI 不要把“模拟器完全没问题”当成结论
- 更准确的结论是：
  - `4173` 当前 bundle 与 Chromium 主链路已修通
  - Safari / 用户真实会话恢复链路仍有回归

### 2.2 当前明确未完成项

这 5 条是当前 handoff 里最该被接手者优先看到的未完成项：

1. 旧研究台清理
   - `title-screen`、部分历史面板文案、`detail-panel` 和 `force-faultmap-view` 等旧研究视图残留仍在
   - 典型残留位于 [index.html](/Users/dutaorui/Desktop/claudecode/index.html)、[app.js](/Users/dutaorui/Desktop/claudecode/app.js)、[style.css](/Users/dutaorui/Desktop/claudecode/style.css)
2. 星图增强未完成
   - 命中增强、个人星座网格、信标效果已有第一版
   - 但引力场 / 粒子 / 决策映射 / 完整产品视觉还没完全收束
3. `style.css` 减重
   - 当前约 `4322` 行
   - 仍含旧研究台、force faultmap、小型分析面板、历史面板和兼容期样式
4. Phase 4 剩余项
   - 移动端细节收边
   - 当前四档 `quick / deep / pro / ultra` 回归基线继续维护
5. PDF 内页人工复核
   - 新版版式已经稳定生成，且封面 / 雷达图 / 彩色时间线 / 纪要式附录都已接进主链
   - 当前剩余工作是继续人工阅读检查目录页、时间线页、行动地图页，不是“还没有新版 PDF”

---

## 3. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vite + Vanilla JS ESM + HTML + CSS | `4174` 为 dev，构建产物输出到 `dist/` |
| 后端 | FastAPI + Uvicorn | `server.py` 提供 API、SSE 和静态资源托管，主入口 `4173` |
| 模型接入 | OpenAI-compatible API | 使用 `openai` Python SDK |
| 状态持久化 | SQLite（SQLAlchemy）+ localStorage + JSON 输出文件 | `decisions` / `engine_b_sessions` / `detection_jobs` 已落 SQLite |
| 运行方式 | 本地服务 | 默认 `127.0.0.1:4173`，Vite dev 为 `127.0.0.1:4174` |

---

## 4. 项目结构

```text
claudecode/
├── index.html
├── app.js
├── style.css
├── package.json
├── vite.config.mjs
├── dist/
│   ├── index.html
│   └── assets/
│       ├── index-qixQisxR.js
│       └── index-BIBJILkY.css
├── server.py
├── server_core.py
├── server_runtime.py
├── server_detection.py
├── server_shared.py
├── decision/
│   ├── __init__.py
│   ├── tiers.py
│   ├── pipeline.py
│   ├── classifier.py
│   └── reporting.py
├── frontend/
│   ├── core/
│   │   ├── state.js
│   │   ├── renderer.js
│   │   └── interaction.js
│   ├── components/
│   │   ├── decision-flow-view.js
│   │   ├── thinking-log-utils.js
│   │   ├── tier-selector.js
│   │   ├── timeline-view.js
│   │   └── pixi-star-map.js
│   └── modules/
│       ├── decision-engine.js
│       ├── engine-a.js
│       ├── engine-b.js
│       ├── ui-bridge.js
│       ├── ui-handlers.js
│       └── utils.js
├── data.js
├── discovered-data.js
├── FIRST_RUN.md
├── README.md
├── REDESIGN_HANDOFF.md
├── TECHNICAL_HANDOFF.md
├── WEB_APP.md
├── .env.clp
├── .env.clp.example
│
├── tests/
│   ├── decision_flicker_probe.mjs
│   ├── decision_full_flow_live.mjs
│   ├── home_hero_layout_smoke.mjs
│   ├── home_mobile_surface_smoke.mjs
│   ├── mobile_layout_smoke.mjs
│   ├── pipeline_recheck_guard.py
│   ├── star_map_hit_e2e.mjs
│   ├── star_map_v3_smoke.mjs
│   ├── submit_button_e2e.mjs
│   ├── thinking_log_dedupe.mjs
│   ├── tier_selector_ui_regression.mjs
│   ├── test_api_extract_text.py
│   ├── test_api_json_rescue.py
│   ├── test_decision_api_smoke.py
│   ├── test_flash_classifier.py
│   ├── test_decision_pipeline_normalization.py
│   ├── test_decision_tier_regression.py
│   ├── test_engine_b_agents.py
│   ├── test_engine_b_runtime.py
│   └── test_single_detect_profiles.py
│
├── research/
│   ├── api.py
│   ├── checkpoint.py
│   ├── db.py
│   ├── models.py
│   ├── output_formatter.py
│   ├── run.py
│   ├── single_detect.py
│   ├── phase1_mining.py
│   ├── phase2_filter.py
│   ├── phase2_filter1.py
│   ├── phase2_filter3.py
│   ├── phase3_analysis.py
│   ├── phase3_stability.py
│   ├── phase3_oscillation.py
│   ├── phase4_fault_lines.py
│   ├── phase4_tunnel_effects.py
│   ├── phase4_social_conflicts.py
│   └── engine_b/
│       ├── __init__.py
│       ├── agents.py
│       ├── models.py
│       └── state.py
```

---

## 5. 关键模块职责

### 5.1 前端

`index.html`

- 页面骨架
- 检测页、Engine B、模拟器、控制台容器

`app.js`

- 前端主入口和页面编排
- 初始化各模块
- 首页/星图/旧研究台残留视图的总控
- 报告导出、历史恢复等全局桥接

`frontend/components/decision-flow-view.js`

- 检测页视图渲染
- Engine B 问题卡渲染
- C1 建议结果渲染
- 模拟器问题卡 / 结果页渲染
- 检测页内部交互状态（选项选中、输入提交保护）
- 多段 render cache，避免重复重绘导致闪烁

`frontend/components/thinking-log-utils.js`

- 思考流日志压缩与归并
- 避免同一句等待 / 失败提示反复刷屏

`frontend/modules/decision-engine.js`

- 新产品协议 `/api/decision/*` 的前端主入口
- 四档思考深度加载与选择
- 决策会话恢复
- SSE 订阅与状态同步
- recheck / simulator 流程门控
- 决策渲染签名去重，避免页面无效闪烁

`frontend/components/tier-selector.js`

- 首页思考深度选择器
- `quick / deep / pro / ultra` 视觉切换

`frontend/components/timeline-view.js`

- 第三幕时间线对比 UI
- 行动地图、岔路口、生存方案渲染

`frontend/core/state.js`

- 全局运行态
- 当前决策、当前会话、SSE 句柄、render signature 等统一状态

`style.css`

- 星图样式
- 控制台样式
- Engine B 样式
- 模拟器样式
- trace、loading、error 样式

### 5.2 后端

`server.py`

- FastAPI 入口
- 研究主线接口
- 单题检测接口
- `/api/decision/*` 产品协议
- `/api/engineb/*` 兼容接口
- SSE 接口
- 最终 PDF / 文本报告接口
- AI 总结版 PDF 接口
- 静态资源 no-store 处理

`research/api.py`

- 模型客户端初始化
- OpenAI-compatible 调用封装
- Responses API / Chat Completions 兼容
- JSON 提取、修复、降级
- 重试、超时、诊断日志

`decision/pipeline.py`

- 决策主状态机
- act1 检测代理、act2 Engine B 监控、act3 模拟器接续
- 历史持久化与恢复
- 决策完成态封装

`decision/tiers.py`

- 四档思考深度配置
- 默认档位与配置归一化

`decision/reporting.py`

- 决策报告路径规划
- 检测 / Engine B / 模拟器结果聚合后调用 PDF 生成器
- 新增 `build_decision_summary_report_pdf`，用于生成客户可读的 AI 摘要版 PDF

`research/db.py`

- SQLite 持久化
- `decisions` / `engine_b_sessions` / `detection_jobs` 三类数据存储

### 5.3 Engine B

`research/engine_b/models.py`

- Engine B 数据结构
- 会话对象
- 阶段枚举

`research/engine_b/state.py`

- Engine B 会话的文件持久化
- 活跃会话索引

`research/engine_b/agents.py`

- B1-B9/C1 的 prompt 和运行函数
- 参数解析
- 时间线归一化
- fallback 生成逻辑

### 5.4 研究主线

`research/run.py`

- 批处理主入口

`research/phase*`

- 各阶段研究分析逻辑

---

## 6. 运行方式

### 6.1 启动

```bash
cd /Users/dutaorui/Desktop/claudecode
python3 server.py
```

打开：

```text
http://127.0.0.1:4173
```

### 6.2 配置

配置文件：

- `.env.clp`
- `.env.clp.example`

关键环境变量：

- `CLP_API_KEY`
- `CLP_BASE_URL`
- `CLP_MODEL`
- `CLP_MODEL_FALLBACKS`
- `CLP_TIMEOUT_SECONDS`

不要提交任何真实密钥。

### 6.3 常用验证命令

```bash
node --check /Users/dutaorui/Desktop/claudecode/app.js
node --check /Users/dutaorui/Desktop/claudecode/frontend/modules/decision-engine.js
python3 -m unittest tests.test_single_detect_profiles tests.test_decision_api_smoke
npm run build
curl -s http://127.0.0.1:4173/api/decision/tiers
curl -s http://127.0.0.1:4173/api/decision/history
node tests/submit_button_e2e.mjs
node tests/decision_flicker_probe.mjs
node tests/decision_full_flow_live.mjs
```

---

## 7. 研究主线说明

研究主线用于批量挖掘“认知拉格朗日点”，不是当前最常交互的路径，但仍是项目的理论主干。

典型流程：

1. `phase1_mining`  
   产生候选问题

2. `phase2_filter*`  
   进行多轮筛选

3. `phase3_*`  
   做力量分析、稳定性、振荡

4. `phase4_*`  
   计算断层线、隧道效应、社会冲突预测

研究结果主要写入：

- `research/output/checkpoint.json`
- `research/output/results.json`
- `research/output/report.txt`
- `research/output/api_diagnostics.jsonl`
- `discovered-data.js`

---

### 7.1 单题真实检测（当前首页主入口）

首页“开始检测”现在已经不是前端随机演示，而是走后端真实检测。

核心实现：

- `research/single_detect.py`
- `server.py` 里的 `DetectionManager`
- 前端 `app.js` / `frontend/modules/decision-engine.js`

真实流程：

1. 前端调用 `POST /api/detect/start`
2. 后端创建 `job_id`
3. 异步执行：
   - 结构预分析
   - 根据模式选择检测 profile
   - 执行筛子1 / 筛子2 / 可选筛子3
   - 如通过则进入力量解剖
4. 前端轮询 `GET /api/detect/status`
5. 根据真实结果决定：
   - 确认为 CLP
   - 不是 CLP，建议进入 Engine B
   - 或诚实显示检测失败

现实说明：

- 这里已经不再是前端 `Math.random()` 假结果
- 如果模型没有稳定返回 JSON，会显示真实失败，而不是伪造结论
- `research/single_detect.py` 里已经加入 `resolve_detection_profile()`
- `decision_deep` 会走轻量检测档：减轻 filter1/filter2，直接跳过 filter3
- 深思模式下，如果检测结果不够稳定，系统会 fail-open 到 Engine B，而不是继续把用户困在长时间等待里

---

## 8. Engine B 当前真实流程

Engine B 仍是当前最重要的交互链路，但对前端来说，**现在优先走的是 `/api/decision/*` 产品协议**；`/api/engineb/*` 更多是兼容层和底层桥接。

### 8.1 流程总览

1. 用户提交问题
2. `decision/pipeline.py` 先走 act1 检测代理
3. 非拉格朗日点则自动进入 B1 诊断
4. 用户回答 B1
5. 后端异步执行 B2-B5 + C1
6. 前端展示建议结论
7. 如需要，进入 recheck（`a_recheck`）
8. recheck 结束后才允许进入模拟器
9. B6 收集模拟参数
10. 用户回答 B6
11. 后端异步执行 B7-B9
12. 前端展示未来时间线、预案、行动地图

### 8.2 核心后端入口

主产品协议入口在 `server.py`：

- `decision_start`
- `decision_status`
- `decision_events`
- `decision_history`
- `decision_answer`
- `decision_simulate_start`
- `decision_upgrade`
- `decision_report`

真正的状态调度在：

- `decision/pipeline.py`
  - `DecisionManager.start`
  - `DecisionManager.upgrade`
  - `DecisionManager.submit_answer`
  - `DecisionManager.start_simulator`
  - `DecisionManager.get_status`
  - `DecisionManager.list_history`

底层 Engine B 兼容入口仍在：

- `start_engine_b_session`
- `submit_engine_b_answer`
- `get_engine_b_status_for_session`
- `start_simulator`
- `submit_sim_answer`

### 8.3 核心前端入口

新产品协议入口不再主要写在 `app.js`，而是在：

- `frontend/modules/decision-engine.js`
  - `bootstrapDecisionProtocol`
  - `restoreDecisionSession`
  - `startDecision`
  - `submitDecisionAnswer`
  - `startDecisionSimulator`
  - `renderDecisionSession`

视图层在：

- `frontend/components/decision-flow-view.js`
  - B1 提问卡
  - C1 结果卡
  - 模拟器问答卡
  - 时间线结果页
  - thinking / trace 折叠展示

`app.js` 现在更多负责页面级编排、星图入口和全局桥接。

---

## 9. Engine B API

补充说明：

- 当前真正给前端使用的主协议已经是：
  - 单题检测：`/api/detect/*`
  - 产品化决策链路：`/api/decision/*`
  - 兼容/底层 Engine B：`/api/engineb/*`
  - 最终报告导出：`/api/final-report/pdf` 与 `/api/decision/report`

### 9.0 优先使用哪个 API

如果是接前端页面、补流程、修用户问题：

- **优先接 `/api/decision/*`**

如果是研究底层 Engine B 行为、调单个阶段、做兼容排查：

- 使用 `/api/engineb/*`

### 9.1 启动 Engine B

`POST /api/engineb/start`

请求：

```json
{"question":"我该不该去外地工作？"}
```

作用：

- 创建会话
- 进入 `b1_diagnosis`
- 返回诊断问题

### 9.2 提交 B1 回答

`POST /api/engineb/answer`

请求：

```json
{"session_id":"...","question_id":"b1q1","answer":"..."}
```

作用：

- 保存回答
- 如果最后一题已答完，则异步进入 B2-B5/C1

### 9.2A 提交产品协议里的回答

`POST /api/decision/answer`

请求：

```json
{"decision_id":"...","question_id":"...","answer":"..."}
```

作用：

- 自动判断当前是在答 B1 还是 B6
- 透传到底层 Engine B / simulator
- 回写统一的 decision 状态
- 这是前端“提交回答”按钮当前走的正式接口

### 9.3 获取状态

`GET /api/engineb/status`

作用：

- 返回当前活跃 Engine B 会话
- 前端轮询依赖这个接口

产品协议对应接口：

- `GET /api/decision/status?id=...`
- `GET /api/decision/events?id=...`

### 9.4 重置会话

`POST /api/engineb/reset`

作用：

- 删除当前活跃会话
- 清空恢复状态

### 9.5 启动模拟器

`POST /api/engineb/simulate/start`

作用：

- 进入 B6
- 返回参数问题

产品协议对应接口：

- `POST /api/decision/simulate/start`

### 9.6 提交模拟器参数

`POST /api/engineb/simulate/answer`

作用：

- 保存 B6 回答
- 最后一题提交后，异步进入 B7-B9

### 9.7 单题检测接口

`POST /api/detect/start`

请求：

```json
{"question":"我该不该去外地工作？"}
```

作用：

- 创建检测任务
- 返回 `job_id`
- 后台异步执行真实筛子流程

`GET /api/detect/status?job_id=...`

作用：

- 查询当前检测任务状态
- 返回分析、筛子状态、最终结果或错误信息

### 9.8 最终 PDF 报告

`GET /api/final-report/pdf`

`GET /api/final-report/summary-pdf`

`GET /api/decision/report?id=xxx`

`GET /api/decision/summary-report?id=xxx`

支持查询参数：

- `job_id`
- `session_id`

作用：

- 按当前检测任务 / Engine B 会话 / 模拟器结果整合生成一份 PDF
- `/summary-pdf` 和 `/summary-report` 会生成第二份 AI 总结版 PDF
- 如果只有其中一段结果，也会尽量导出当前已有内容
- 产物会写入 `research/output/decision_reports/`

---

## 10. Engine B 阶段状态

会话阶段定义在 `research/engine_b/models.py`。

常用阶段：

- `b1_diagnosis`
- `b2_info_fill`
- `b3_cognitive_unlock`
- `b4_experience_sim`
- `b5_emotional_mirror`
- `c1_reevaluation`
- `a_recheck`
- `b6_sim_params`
- `b7_sim_timelines`
- `b8_sim_coping`
- `b9_sim_comparison`
- `simulator_complete`
- `abandoned`

说明：

- `abandoned` 不是用户主动放弃，而是后端本轮处理失败后的统一错误态
- 前端现在已经单独为 `abandoned` 做了稳定错误面板

---

## 11. 会话持久化

### 11.1 前端

前端现在优先用 `localStorage` 记住活跃 `decision_id`：

- `clp_decision_session_id`

旧链路仍可能用到：

- `clp_engineb_session_id`

页面刷新后会优先尝试恢复决策协议会话。

### 11.2 后端

当前后端持久化分两层：

1. 产品协议主状态：SQLite

```text
research/output/app_state.db
```

其中包含：

- `decisions`
- `engine_b_sessions`
- `detection_jobs`

2. Engine B 的旧文件态仍保留，作为兼容恢复与调试辅助：

```text
research/output/engine_b_sessions/
```

### 11.3 恢复逻辑

页面加载时：

1. 先读前端保存的 `decision_id`
2. 请求 `/api/decision/status`
3. 如果 SQLite 中有对应状态，就恢复 decision UI
4. 根据 `phase` / `engineb_session.phase` 决定进入 B1、C1、recheck、Simulator 或完成态
5. 如果是旧链路或兼容排查，再回退查 `/api/engineb/status`

---

## 12. 模型调用层说明

`research/api.py` 是整个项目最关键的基础设施之一。

它负责：

- 初始化 `OpenAI` 客户端
- 兼容 `responses.create(...)` 和 `chat.completions.create(...)`
- 提取纯文本
- 结构化 JSON 提取
- JSON 修复
- 失败重试
- 超时控制
- API 诊断日志

### 12.1 当前稳定性策略

当前已经加上的保护：

- GPT-5 系列使用 Responses API
- 兼容不同返回结构的文本提取
- `JSON_REPAIR_SYSTEM` 自动修复畸形 JSON
- JSON 调用支持分层降级
- 单请求支持显式 `timeout_seconds`

当前 JSON 降级策略已经不是单层 fallback，而是：

- `low`
- `medium`
- `high`

对应实现：

- `research/api.py`
- `call_agent_json()`

对应环境变量：

- `CLP_JSON_DOWNGRADE_TIERS`
- `CLP_JSON_LOW_MODELS`
- `CLP_JSON_MEDIUM_MODELS`
- `CLP_JSON_HIGH_MODELS`
- `CLP_JSON_FALLBACK_MODELS`

目的：

- 当 Claude 或其他模型连续不出稳定 JSON 时
- 先强化结构化提示
- 再切到更稳的候选模型
- 避免一轮检测直接报废

诊断日志文件：

```text
research/output/api_diagnostics.jsonl
```

---

## 13. 最近已经修过的问题

### 13.1 API 兼容性

已修：

- Responses API 返回格式解析
- `output_text` / list content / mapping content 等多种结构提取

### 13.2 按钮看起来“按不动”

已修：

- 最后一题提交时，前端先立即切 processing 状态
- 不再等后端完整返回才改界面

最近又补过：

- B1 / B6 选择题按钮改为更直接的点击绑定
- 提交按钮不再因为错误禁用状态把用户卡死
- 选项按钮增加显式高亮态
- Safari 端为 `app.js` / `style.css` 增加版本号，降低旧缓存干扰
- `node tests/submit_button_e2e.mjs` 已能稳定验证“问题 2/5 → 问题 3/5”

现实说明：

- 这部分已经比最初稳定很多
- 但如果用户浏览器标签页长期不刷新，仍可能继续吃旧脚本
- 排查时优先让用户重开标签页，而不是只普通刷新

### 13.3 处理过程不可见

已修：

- 检测页顶部已有连续输出的实时思考流
- Engine B 与 Simulator 都有 trace 展示
- 支持处理中自动展开
- 支持处理后折叠查看
- 重复日志会归并显示，不再被同一句等待/失败提示反复刷屏

### 13.4 模拟器 `choice_name` 崩溃

根因：

- B7 prompt 用 `.format(...)` 时误把 JSON 里的花括号当模板字段

已修：

- 去掉危险格式化
- 加入 `_normalize_b7_timeline_output`

### 13.5 模拟器错误页闪屏

根因：

- 失败态与 loading/questions/results 共用渲染路径
- `abandoned` 分支顺序不稳

已修：

- 独立错误面板
- `abandoned` 前置
- 避免重复面板切换
- 决策渲染签名去重
- trace 面板重复内容去重
- `node tests/decision_flicker_probe.mjs` 当前结果为 `0 mutation`

### 13.6 模拟器总是超时

根因：

- B7/B8/B9 单次请求太大
- 上游网关对 `gpt-5.4` 的大 JSON 输出经常 504

已修：

- 压缩 B7/B8/B9 输出要求
- 缩短单次请求超时
- 关闭不必要的长重试
- 超时后自动切本地 fallback

### 13.7 单题检测从假流程改成真实流程

根因：

- 最初首页“开始检测”只是演示型前端动画
- 结果生成过快，但并不代表真实筛选

已修：

- 新增 `research/single_detect.py`
- 后端接入真实 `POST /api/detect/start` / `GET /api/detect/status`
- 前端改为轮询真实状态，而不是本地拼结果

影响：

- 现在检测会真实调用模型
- 如果筛子阶段出错，会显示真实失败原因

### 13.8 最终 PDF 报告输出

已修：

- 最终结果页新增 PDF 导出
- 报告会整合：
  - 单题检测结果
  - Engine B 建议
  - 模拟器结果
- 封面、目录、报告摘要、时间线页、行动地图页、完整日志、结构化轨迹已进入同一版式
- 生成器复用了 `fpdf2` 能力，不依赖浏览器截图打印

主要文件：

- `research/output_formatter.py`
- `server.py`
- `index.html`
- `app.js`

最新产物：

- `research/output/decision_reports/decision_job-82afe344_session-6b4ef986_20260407-125755.pdf`

### 13.9 输入法回车误提交

根因：

- 中文输入法在联想/上屏阶段也会触发 `Enter`
- 前端把第一次回车当成真正提交

已修：

- 首页输入框加了 IME composing 保护
- Engine B 开放题输入框加了 IME composing 保护
- 模拟器开放题输入框加了 IME composing 保护
- 自定义问题输入框也做了同类保护

### 13.10 recheck / simulator 竞态

根因：

- C1 完成后，recheck 与 simulator 启动都可能抢同一段状态
- 用户会感觉“按钮点了没反应”或“状态一直跳”

已修：

- `frontend/modules/decision-engine.js` 现在会在 `a_recheck` 未结束时阻止启动模拟器
- recheck 完成为拉格朗日点时，会直接走完成态，而不是继续错误进入第三幕
- `decision/pipeline.py` 现在会在后端监控层标记 `simulator_waiting_recheck`
- 同一条“等待二次检测完成后再进入未来模拟”的提示不会重复灌进思考流

### 13.11 深思模式总像卡住

根因：

- 旧的检测链路对 `deep` 档过重
- 过滤器跑太满时，用户会误以为整页死掉或超时

已修：

- `research/single_detect.py` 增加 `resolve_detection_profile()`
- `decision_deep` 改为轻量检测 profile
- filter3 在深思模式下跳过
- 不确定结果 fail-open 到 Engine B

### 13.12 产品协议第一版落地

已修：

- `decision/tiers.py` 已提供三档配置
- `decision/pipeline.py` 已接管产品态主流程
- `server.py` 已提供 `/api/decision/*`
- `research/db.py` 已落 `decisions` 表

---

## 14. 模拟器 fallback 机制

这是当前版本最重要的稳定性改动。

### 14.1 触发条件

当 B7/B8/B9 调用模型超时或失败时，不再直接把整轮会话打成失败，而是走本地快速生成逻辑。

### 14.2 fallback 内容

在 `research/engine_b/agents.py` 中已实现：

- B7 时间线 fallback
- B8 岔路口/生存方案 fallback
- B9 对比总览 fallback

这些 fallback 会返回：

```json
{"fallback_mode":"local_fast"}
```

### 14.3 前后端表现

后端：

- 继续写入 `processing_trace`
- 标记“已切到极速模式”

前端：

- 正常渲染结果
- 用户不再只看到失败页

### 14.4 限制

fallback 的文本质量不如完整大模型版细腻，但它的目标是：

- 先稳定出结果
- 不再因为上游波动而整条链路不可用

---

## 15. 当前已知问题和风险

### 15.1 上游网关依然不稳定

现在已经不会因为超时整轮报废，但如果网关持续差，模拟器会更频繁走 fallback。

单题检测也有类似问题：

- 某些模型能连通，但不一定稳定输出结构化 JSON
- 这类问题现在会暴露成真实失败，而不是被前端假结果掩盖

### 15.2 前端仍然偏单体，但已开始拆模块

目前已经做了第一阶段拆分：

- `frontend/components/decision-flow-view.js` 已接管检测页、Engine B、模拟器的主要视图渲染
- `frontend/modules/decision-engine.js` 已接管 `/api/decision/*` 的主流程
- `app.js` 更多保留为页面编排和全局桥接

但当前还不算完全组件化：

- 星图渲染、控制台、Force View、Fault Map 仍在 `app.js`
- 旧研究台 DOM / 文案 / 样式残留仍较多
- 还没有做真正的框架级状态管理

### 15.3 Engine A 与 Engine B 没有完全统一

二者现在是：

- 同仓库
- 部分共享底层模型调用
- 但不共享统一产品协议

这意味着：

- 研究主线偏离线批处理
- Engine B 偏在线交互
- 未来做统一产品化时需要重新整理边界

### 15.4 二次检测已打通第一版，但还需要继续产品化

当前真实状态：

- `a_recheck` 已经在后端、数据结构、前端状态机里贯通
- recheck 完成前，模拟器不会抢跑
- recheck 若确认拉格朗日点，决策会直接走完成态

仍需继续做的部分：

- 更多场景覆盖测试
- 更清晰的 UI 文案和状态提示
- 与旧 Engine A 研究协议的进一步边界收束

### 15.5 Safari / 缓存仍可能放大前端假象

虽然现在已经加入：

- `Cache-Control: no-store`
- 构建产物指纹文件名

但排查用户反馈时仍建议优先做：

1. 关闭旧标签页
2. 重新打开 `http://127.0.0.1:4173`
3. 再观察是否复现

### 15.6 B1 卡点诊断会回退到“问题 1/3”，随后按钮失效并进入转圈

2026-04-08 已做一轮针对性修复：

- 文件：[`frontend/modules/decision-engine.js`](/Users/dutaorui/Desktop/claudecode/frontend/modules/decision-engine.js)
- 处理：
  - 新增同一 `decision_id` 的单调进度 rank，低进度旧快照不再允许覆盖高进度新快照
  - `renderDecisionSession()` 在入口拦截旧 SSE / 旧轮询快照
  - B1 追问页现在只会在 `session.phase === "b1_diagnosis"` 且仍有待答问题时渲染
- 回归探针：
  - [`tests/stale_decision_snapshot_probe.mjs`](/Users/dutaorui/Desktop/claudecode/tests/stale_decision_snapshot_probe.mjs)
  - 已接入 `npm run verify:all`
  - 已用 Chromium + WebKit 本地通过

这是 2026-04-07 晚间用户在 Safari 上复现出的 bug，截图时间约为 `21:56`。下面保留历史症状，方便如果再次复现时对照排查。

用户症状：

- 在 B1 卡点诊断阶段选择答案后
- UI 会突然回到“问题 1/3”
- 底部按钮开始无法继续点击
- 等一会后进入 loading / 转圈
- 页面中央显示类似“正在切换判断框架”
- 但顶部思考流里已经出现：
  - “诊断回答已收齐”
  - “开始切换判断框架”
  - “开始补关键事实”

这说明：

- 后端大概率已经推进到了 `b2/b3/c1`
- 但前端还停留在 `detection-step0`
- 很像是旧快照、SSE 事件顺序或 render cache 把视图重新拉回了 B1

历史优先怀疑文件：

- `frontend/modules/decision-engine.js`
  - `renderDecisionSession()`
  - `hasPendingQuestions()`
  - `startDecisionEvents()`
- `frontend/components/decision-flow-view.js`
  - `renderB1Questions()`
  - `showB1Processing()`
  - `renderCache.b1QuestionSignature`
  - `renderCache.b1ProcessingSignature`

如果修复后仍复现，下一位 AI 建议先做的事：

1. 复现这条 bug 时记录对应 `decision_id`
2. 同时抓：
   - `/api/decision/status?id=...`
   - `/api/decision/events?id=...` 的事件顺序
3. 对照看 bug 当刻：
   - 后端是否已在 `b2_info_fill / b3_cognitive_unlock / c1_reevaluation`
   - 前端却仍满足 `hasPendingQuestions(session, 'diagnosis_questions', 'diagnosis_answers')`
4. 如果仍像旧快照覆盖新快照：
   - 优先检查 `getDecisionProgressRank()` 的 rank 是否遗漏了新的阶段名
   - 再检查是否有 `force: true` 绕过了旧快照门禁
5. 如果是 UI 缓存没有清掉：
   - 重点看 `renderB1Questions()` 与 `showB1Processing()` 切换时是否完整重置 DOM / cache

当前状态：

- 代码层已修旧快照回退主因，并有 Chromium / WebKit 探针覆盖
- 仍建议用户实机 Safari 再跑一轮完整 B1 -> B2/B3/C1，确认没有其它点击遮挡或缓存类问题

### 15.7 Safari 上“启动选择模拟器”仍有用户实机死点击反馈

这是 2026-04-07 晚间第二张截图，时间约为 `22:02`。

用户症状：

- C1 建议页里按钮已经显示出来了
- 文案是“🔮 启动选择模拟器”
- 但用户点下去没有切到第三幕

当前已确认的事实：

- Chromium 实机回归已经通过
- `4173` 当前确实在服务最新 `dist/`
- `deep` 手动进入第三幕的后端状态也已核到 SQLite：
  - `running / act3 / b6_sim_params`

所以这条问题更精确的描述应该是：

- “模拟器入口主链路已在 Chromium 修通”
- “Safari / 用户真实环境仍存在点击后不推进的回归，需要单独确认”

下一位 AI 应优先验证：

1. Safari 强刷后，Network 面板里点击按钮是否真的发出：
   - `POST /api/decision/simulate/start`
2. 点击后 loaded 的 JS 资源是否是最新构建：
   - `dist/assets/index-Bmb2ucQB.js`
   - 如果不是，先排缓存
3. 若请求已发出但页面不跳：
   - 查前端 `window.startSimulator -> startDecisionSimulator -> renderDecisionSession`
4. 若请求没发出：
   - 查 Safari 的 click 事件、overlay、focus、pointer 事件是否被挡
5. 若请求已成功且 SQLite 状态已进 `act3`，但页面仍停在 step4：
   - 查 `renderDecisionSession()` 是否被旧 completed 快照覆盖

当前状态：

- Chromium：通过
- Safari：用户仍反馈“点不了”
- 这条不能从 handoff 中删掉，必须保留给下一位 AI

---

## 16. 接手建议优先级

### 第一优先级

继续收尾产品态页面和交互闭环。

重点文件：

- `app.js`
- `index.html`
- `style.css`
- `frontend/core/interaction.js`
- `frontend/core/renderer.js`

目标：

- 清理旧研究台残留
- 补齐星图点击/命中闭环
- 降低“能跑但页面还不像最终产品”的落差

### 第二优先级

继续收敛 bridge 协议与重复状态。

重点文件：

- `server_runtime.py`
- `server_detection.py`
- `decision/pipeline.py`
- `server.py`
- `research/engine_b/agents.py`

目标：

- 让 `/api/decision/*` 尽量少依赖 legacy bridge
- 继续收敛重复状态结构
- 降低后续改动时的牵一发而动全身

### 第三优先级

继续稳定模型调用层。

重点文件：

- `research/api.py`
- `research/single_detect.py`
- `research/engine_b/agents.py`

目标：

- 降低 504 对结果的影响
- 优化轻量检测与 fallback 策略
- 继续提高结构化 JSON 的稳定性

---

## 17. 中长期架构优化方向

这一节记录的是未来升级建议，不代表当前仓库已经完成。

### 17.1 前端架构升级

现状：

- `app.js` 仍是超大单文件
- 但检测页 / Engine B / 模拟器视图已经拆出 `frontend/components/decision-flow-view.js`
- `/api/decision/*` 主流程已经拆到 `frontend/modules/decision-engine.js`
- 星图渲染、控制台、检测流程、Engine B、模拟器、trace、会话恢复都堆在一起
- 这会持续放大监听器丢失、状态覆盖、缓存错觉和维护成本

建议方向：

- 继续拆 ES modules 即可，短期不必急着上 React / Vue
- 将星图渲染、旧研究台控制台、历史/报告、trace 再拆开
- 利用现有 Vite 构建链做资源与开发体验收敛

目标：

- 从“单体脚本 + 局部模块化”走向“更清晰的模块边界”
- 降低前端幽灵 Bug 的排查成本

### 17.2 通信协议从轮询升级到流式

现状：

- `/api/detect/events`、`/api/engineb/events`、`/api/decision/events` 的 SSE 已经落地
- 但部分旧路径和兼容逻辑仍混用轮询与 SSE

建议方向：

- 继续统一到 `/api/decision/events`
- 压缩旧的轮询兜底逻辑
- 把 trace / phase / completed 信号统一成更稳定的事件协议

目标：

- 降低轮询逻辑复杂度
- 让用户能看到更连续的处理过程

### 17.3 后端并发与持久层升级

现状：

- 后端已经迁到 FastAPI + Uvicorn
- `research/db.py` 已经接管 `decisions` / `engine_b_sessions` / `detection_jobs`
- 但 legacy 文件态与兼容 bridge 仍然并存

建议方向：

- 继续把 legacy 文件态逐步收束到 SQLite
- 视并发需求决定是否引入 Redis
- 把任务状态、报告索引、检测任务进一步从 compatibility bridge 收敛到明确模块

目标：

- 提升并发可靠性
- 降低文件锁、状态不一致和恢复复杂度

### 17.4 大模型结构化输出继续工程化

现状：

- 项目已经有 JSON repair、重试、分层降级
- 但依旧要为“模型不稳定输出 JSON”付出大量兼容代码

建议方向：

- 优先拥抱 Structured Outputs / JSON Schema 约束
- 尽量把 prompt 驱动的“约定 JSON”升级为接口层强约束
- 继续减少解析容错逻辑、无效重试和 504 后的无谓等待

目标：

- 提升检测和模拟器的稳定性
- 降低模型响应格式漂移带来的维护成本

### 17.5 星图可视化引擎升级

现状：

- 当前星图主要基于 2D Canvas
- 随着确认点、断层线、隧道连接增加，渲染压力会持续上升

建议方向：

- 如果未来数据量和视觉目标继续提升，可迁移到 PixiJS / Three.js / WebGL
- 把大规模节点、连线、发光、分层动画交给 GPU

目标：

- 支撑更大的图谱规模
- 提升视觉表现力和流畅度

一句话总结：

- 当前阶段最重要的是先把产品链路做稳
- 中长期则要从“脚本式堆功能”过渡到“工程化架构演进”

---

## 18. 快速定位建议

如果接手者只想快速开始，请按下面顺序看：

1. `server.py`  
   先看 API 和主调度

2. `app.js`  
   再看前端状态机和 simulator 渲染

3. `research/api.py`  
   再看模型调用与 JSON 修复

4. `research/engine_b/agents.py`  
   最后看 Engine B 的 prompt 和 fallback

5. `research/output_formatter.py`
   如果接手报告样式或 PDF 内容组织，这个文件现在已经是主入口

---

## 19. 一句话交接版

这是一个本地运行的“认知拉格朗日点研究 + 人生决策突破”Web 应用。研究主线负责筛选结构性无解问题，首页单题检测已经接到真实后端筛子流程；Engine B 负责帮助用户诊断纠结、给出建议并模拟未来。当前版本已完成首页产品化第一版、单题真实检测、顶部连续思考流、recheck/simulator 竞态保护、失败态稳定渲染、超时 fallback、本地外部声音快照注入，以及新版出版感 PDF 决策报告导出；下一步重点是继续清理旧研究台残留、压缩样式和把星图真正做成完整决策画布。
