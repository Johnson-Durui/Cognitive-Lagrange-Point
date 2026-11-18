# 认知拉格朗日点 · 可执行升级方案

> 目的：把“听起来很酷但不能直接并入”的升级提案，重写成**当前仓库可落地**的 roadmap。  
> 原则：不写假完成，不写伪代码式承诺，只写和当前代码结构兼容的实施路径。

---

## 0. 先说结论

下面四个方向都值得做：

1. 实时外部信号注入
2. 出版感 PDF 升级
3. 展示用一页纸 / Pitch 包
4. 第三条路与更强模拟器增强

但它们**不能直接按外部提案原样复制进当前仓库**，原因是：

- 当前项目里没有 `chromadb`
- 当前项目里没有 `langchain_community`
- 当前项目里没有 `reportlab`
- 当前项目里没有统一 `get_llm_client().embed()` 能力
- 当前 PDF 生成链路已经存在，不能平行新起一套假生成器

所以正确做法不是“贴进去就跑”，而是按当前工程真实结构逐步接入。

---

## 1. 方向一：实时外部信号注入

### 1.1 目标

让 `pro / ultra` 决策在第二幕和第三幕里，不只是依赖模型内部知识，还能引用**近 24-72 小时的外部讨论信号**，例如：

- X / 社区讨论
- 产品评价
- 用户吐槽 / 好评
- 舆情分歧点

### 1.2 当前仓库的真实接入点

建议接在：

- [`research/engine_b/runtime.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/runtime.py)
- [`research/engine_b/agents.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/agents.py)

最合适的注入阶段：

- `B2` 信息侦探
- `C1` 重新评估
- `B9` 最终比较总览

### 1.3 正确的 MVP 做法

不要一上来就硬上 `chromadb + embed + 实时抓 X`。

先做这个最小可用版：

1. 新建一个**外部信号快照层**
   - 文件建议：
     - `research/engine_b/external_signals.py`
2. 定义统一数据结构
   - 例如：
     - `source`
     - `time`
     - `author`
     - `text`
     - `url`
     - `topic`
     - `stance`
3. 先支持“导入快照 JSON”
   - 不直接承诺实时抓取
   - 先允许外部把舆情整理成 JSON 丢进来
4. 在 `B2 / C1 / B9` prompt 中注入 Top-N 信号摘要
5. 前端结果页增加一块“近期外部信号”

### 1.4 推荐实施顺序

#### Phase A：离线快照版

- 新建 `data/external_signals/`
- 支持按 query 导入 JSON 快照
- 用关键词或简易相似度做检索
- 注入到 `B2 / C1 / B9`

#### Phase B：真实抓取版

- 再接入真实外部工具
- 如果要上向量库，再补依赖和迁移文档

### 1.5 不建议直接做的事

- 不建议现在直接把“实时 X 抓取”写成已完成卖点
- 不建议现在直接引入一套和现有 `research/api.py` 平行的新 LLM 客户端
- 不建议现在就把 `embed()` 当成已存在接口

---

## 2. 方向二：PDF 出版感升级

### 2.1 目标

让报告从“可读”升级成“更适合展示和对外发送”。

### 2.2 当前仓库真实链路

现在项目已经有正式 PDF 生成链路：

- [`decision/reporting.py`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py)
- [`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)

所以正确做法是：

> **增强现有 PDF 生成器，而不是平行新建一个完全独立的 PDF 方案。**

### 2.3 推荐升级项

优先级从高到低：

1. 封面和摘要页强化
2. 时间线页可视化
3. 行动地图页层级优化
4. 第三条路、偏差提醒、后悔分数写进报告
5. 日志页和附录页继续压缩

### 2.4 当前最稳妥的实现方式

基于现有 `fpdf` 管线继续增强：

- 加彩色 section header
- 加摘要信息卡
- 加概率 / 后悔分迷你图
- 加更清晰的 A/B 对比页

而不是立刻切 `reportlab + matplotlib`，因为那会带来：

- 新依赖
- 新字体问题
- 新布局兼容问题
- 双维护成本

### 2.5 正确的文件落点

- 继续改：
  - [`research/output_formatter.py`](/Users/dutaorui/Desktop/claudecode/research/output_formatter.py)
- 辅助上下文：
  - [`decision/reporting.py`](/Users/dutaorui/Desktop/claudecode/decision/reporting.py)

---

## 3. 方向三：展示材料升级

### 3.1 当前已经就绪的展示文件

现在仓库里已经有：

- [`PROJECT_OVERVIEW.md`](/Users/dutaorui/Desktop/claudecode/PROJECT_OVERVIEW.md)
- [`SHOWCASE_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/SHOWCASE_HANDOFF.md)
- [`SHOWCASE_PITCH.md`](/Users/dutaorui/Desktop/claudecode/SHOWCASE_PITCH.md)

这三份已经够支撑：

- 对外介绍
- 展示合作
- 快速路演

### 3.2 还可以继续做什么

后续可以继续补：

- 一页纸产品海报版
- 英文版 Pitch
- Demo script 逐页解说版

---

## 4. 方向四：第三条路 / 模拟器增强

### 4.1 当前真实状态

第三条路不是空白功能，已经在当前仓库中存在，并且已在真实案例 `1e1fae8b` 中产出。

当前实现主要在：

- [`research/engine_b/agents.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/agents.py)
- [`research/engine_b/runtime.py`](/Users/dutaorui/Desktop/claudecode/research/engine_b/runtime.py)

### 4.2 真正值得做的下一步

不是“从 0 新建第三条路代理”，而是继续强化现有能力：

1. 让第三条路更像“过渡方案”而不是一句口号
2. 让第三条路进入 B9 对比总览
3. 让 PDF 报告也展示第三条路
4. 在未来模拟里给第三条路单独一张轻量时间线

### 4.3 模拟器增强建议

目前最值得继续做的是：

- 增强 A / B 时间线差异度约束
- 减少 fallback 输出的模板感
- 提高 `ultra` 里 B7/B8/B9 的展示质量
- 把“流式思考输出”继续做得更连续、更像实时推演

---

## 5. 下一步最推荐怎么排

### P0

- 把这份文档发给接手者，避免再出现“把伪完成包直接当真代码”并进仓库

### P1

- 外部信号注入先做“离线快照版”

### P2

- 继续升级现有 PDF 输出链路

### P3

- 第三条路 / 模拟器继续往更强展示版推进

---

## 6. 接手时必须知道的现实约束

- 当前主档位是：
  - `quick / deep / pro / ultra`
- 当前推荐真实演示案例是：
  - `1e1fae8b`
- 当前第三幕 `tier_config` 崩溃已经修复
- 当前 Safari 雷达图区空白问题已经修复
- 当前 `npm run verify:all` 已通过

如果后续要继续开发，请优先阅读：

1. [`PROJECT_OVERVIEW.md`](/Users/dutaorui/Desktop/claudecode/PROJECT_OVERVIEW.md)
2. [`SHOWCASE_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/SHOWCASE_HANDOFF.md)
3. [`TECHNICAL_HANDOFF.md`](/Users/dutaorui/Desktop/claudecode/TECHNICAL_HANDOFF.md)

