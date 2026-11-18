# 四档思考深度重构方案

> 目标：快速 / 沉思 / Pro / Ultra 四档，每档 token 花费逐级拉开，Ultra 必须输出最完美的文档。

---

## 一、当前 Token 消耗拆解（每次 LLM 调用 ≈ 输入 + 输出）

### 第一幕：分类检测

| 步骤 | 输出上限 | 估算总消耗（含输入） | 说明 |
|------|---------|-------------------|------|
| 结构预分析 | 1400-2200 | ~3,000-4,000 | `analyze_question_structure()` |
| 筛子1（信息注入） | 每级 ~2000 | 2-4级 × ~3,000 = 6,000-12,000 | `filter1_level_limit` 控制级数 |
| 筛子2（多框架） | 每框架 ~1500 | 4-7框架 × ~2,500 = 10,000-17,500 | `philosopher_count` 控制框架数 |
| 筛子3（重述稳定性） | ~2000 | ~4,000 | 3次重述检验 |

### 第二幕：Engine B

| 步骤 | 输出上限 | 估算总消耗 | 说明 |
|------|---------|-----------|------|
| B1 卡点诊断 | 2048 | ~4,000 | 生成 3-5 个追问 |
| B2 信息补齐 | 3072 | ~6,000 | 多维度信息采集 |
| B3 认知解锁 | 3072 | ~6,000 | 新判断框架 |
| B4 经验模拟 | 4096 | ~8,000 | 3个参照案例 |
| B5 情绪镜像 | 2048 | ~4,000 | 情绪干扰识别 |
| C1 重评估 | 2048 | ~5,000 | 力量重算+建议 |
| A_recheck | ~12,000-25,000 | 二次检测全流程 | 重跑检测链路 |

### 第三幕：模拟器

| 步骤 | 输出上限 | 估算总消耗 | 说明 |
|------|---------|-----------|------|
| B6 参数收集 | 1024 | ~2,000 | 2-3个参数问题 |
| 选项提炼 | 900 | ~2,000 | 提炼两个选项 |
| B7 时间线 ×2 | 2600 × 2 | ~10,000 | 两条路各3种时间线 |
| B8 应对预案 | 1800 | ~4,000 | 岔路口+生存方案 |
| B9 对比总览 | 1600 | ~4,000 | 行动地图+最终洞察 |

---

## 二、四档设计

### ⚡ 快速（Quick）

**定位**：5 秒出直觉，花最少的钱  
**预估 Token**：3,000 - 5,000  
**时间**：3-8 秒

```
管线：分类预分析 → 闪念建议 → 完成
跳过：全部筛子、Engine B、模拟器
```

| 执行步骤 | 开/关 |
|---------|------|
| 结构预分析 | ✅ 1400 tokens |
| 筛子1 | ❌ |
| 筛子2 | ❌ |
| 筛子3 | ❌ |
| B1 诊断追问 | ❌ |
| B2-B5 补全 | ❌ |
| C1 重评 | ❌ |
| A_recheck | ❌ |
| B6-B9 模拟器 | ❌ |

**输出**：基于分类得分的个性化一段话建议 + 一个可执行的下一步行动。

---

### 💡 沉思（DeepThink）

**定位**：30 秒完整分析，补信息补框架，给出决策建议  
**预估 Token**：25,000 - 40,000  
**时间**：20-45 秒

```
管线：分类预分析 → 轻量筛子(1+2) → Engine B(B1+B2+B3+C1) → 完成
跳过：筛子3、B4经验、B5情绪、模拟器
```

| 执行步骤 | 开/关 |
|---------|------|
| 结构预分析 | ✅ 1600 tokens |
| 筛子1 | ✅ 2级 |
| 筛子2 | ✅ 4个框架 |
| 筛子3 | ❌ |
| B1 诊断追问 | ✅ 3-5题 |
| B2 信息补齐 | ✅ |
| B3 认知解锁 | ✅ |
| B4 经验模拟 | ❌ |
| B5 情绪镜像 | ❌ |
| C1 重评 | ✅ |
| A_recheck | ❌（差值<15 时跳过，直接标记接近平衡） |
| B6-B9 模拟器 | ❌ |

**输出**：力量天平 + 建议方向 + 行动方案 + 推理过程。

---

### 🔥 Pro

**定位**：2 分钟深度推演，完整三幕全打通  
**预估 Token**：60,000 - 90,000  
**时间**：1.5-3 分钟

```
管线：分类预分析 → 完整筛子(1+2+3) → Engine B 全流程(B1-B5+C1+recheck) → 模拟器(B6-B9) → 完成
```

| 执行步骤 | 开/关 |
|---------|------|
| 结构预分析 | ✅ 2200 tokens |
| 筛子1 | ✅ 4级 |
| 筛子2 | ✅ 5个框架 |
| 筛子3 | ✅ |
| B1 诊断追问 | ✅ 5题 |
| B2 信息补齐 | ✅ |
| B3 认知解锁 | ✅ |
| B4 经验模拟 | ✅ 3个案例 |
| B5 情绪镜像 | ✅ |
| C1 重评 | ✅ |
| A_recheck | ✅（差值<15 时触发） |
| B6 参数收集 | ✅ |
| B7 时间线 | ✅ 每选项 1 次 |
| B8 应对预案 | ✅ |
| B9 对比总览 | ✅ |

**输出**：力量天平 + 建议 + 两条路时间线 + 岔路口预案 + 行动地图 + PDF 报告。

---

### 🌌 Ultra

**定位**：5 分钟全方位推演，多次验证/交叉检验，输出出版级报告  
**预估 Token**：150,000 - 250,000  
**时间**：3-6 分钟

```
管线：分类预分析 → 完整筛子(1+2+3)
     → Engine B 全流程(B1-B5+C1+recheck)
     → 模拟器(B6-B9) 
     → ⭐ C2 二次重评（用模拟结果验证第二幕结论）
     → ⭐ B7 时间线双跑验证（temperature 0.2 + 0.7，取交集）
     → ⭐ 稳定性测试（3 轮 C1 取均值）
     → ⭐ 认知振荡检测（10 轮正反辩论）
     → 完成
```

| 执行步骤 | 开/关 | Ultra 增强 |
|---------|------|-----------|
| 结构预分析 | ✅ 2200 tokens | — |
| 筛子1 | ✅ 4级 | — |
| 筛子2 | ✅ **7个框架（全部哲学立场）** | 比 Pro 多 2 个框架 |
| 筛子3 | ✅ | — |
| B1 诊断追问 | ✅ 5题 | — |
| B2 信息补齐 | ✅ **max_tokens=4096** | 允许更长输出 |
| B3 认知解锁 | ✅ **max_tokens=4096** | 允许更长输出 |
| B4 经验模拟 | ✅ **5个案例**（含 RAG 星图参照） | 比 Pro 多 2 个案例 |
| B5 情绪镜像 | ✅ **max_tokens=3072** | 更深度情绪分析 |
| C1 重评 | ✅ **max_tokens=3072** | 更充分的推理 |
| ⭐ C1 稳定性验证 | ✅ **跑 3 次 C1，取力量均值** | Ultra 独有 |
| A_recheck | ✅ | — |
| B6 参数收集 | ✅ | — |
| B7 时间线 | ✅ **每选项跑 2 次（T=0.2 + T=0.7）** | Ultra 独有：双温度交叉验证 |
| B8 应对预案 | ✅ **max_tokens=2600** | 更细致预案 |
| B9 对比总览 | ✅ **max_tokens=2400** | 更完整对比 |
| ⭐ C2 终评 | ✅ **模拟完成后再跑一次重评** | Ultra 独有 |
| ⭐ 认知振荡检测 | ✅ **10 轮正反辩论** | Ultra 独有 |

### Ultra 独有的 4 个增强模块

#### ⭐ C1 稳定性验证（新增）
跑 3 次 C1 reevaluation（不同 temperature: 0.2, 0.5, 0.8），取 `updated_pro_total` 和 `updated_con_total` 的均值。如果 3 次结果标准差 > 12，标记为"结论不够稳固"并在报告中说明。

```python
# 伪代码
results = []
for temp in [0.2, 0.5, 0.8]:
    r = run_c1_reevaluation(..., temperature=temp)
    results.append(r)
avg_pro = mean([r["updated_pro_total"] for r in results])
avg_con = mean([r["updated_con_total"] for r in results])
stability = "稳固" if std([r["updated_pro_total"] for r in results]) < 12 else "结论有波动"
```

**预估额外 token**: ~10,000（2 次额外 C1 调用）

#### ⭐ B7 双温度验证（新增）
每个选项跑两次 B7（T=0.2 保守 + T=0.7 激进），将两次结果合并。如果两次的概率分布差距 > 15%，在报告中标注"这条路的预测不够确定"。

**预估额外 token**: ~10,000（2 次额外 B7 调用）

#### ⭐ C2 终评（新增）
模拟器跑完后，拿着 B7-B9 的结果再跑一次"终局重评"，验证第二幕的建议是否被模拟结果强化或推翻。

```python
C2_SYSTEM = """你是终局裁判。前面的分析给出了建议，后面的模拟器也跑完了两条路。
请根据模拟结果重新审视建议是否合理。
如果模拟结果与建议一致 → 加固信心
如果模拟结果推翻建议 → 更新建议并解释原因"""
```

**预估额外 token**: ~5,000

#### ⭐ 10 轮认知振荡检测（新增）
复用 `research/phase3_oscillation.py` 的逻辑，跑 10 轮正反辩论（而不是研究管线的 50 轮），看最终结论是否稳定。

**预估额外 token**: ~30,000-50,000

---

## 三、Token 预算总览

| 档位 | 图标 | 调用次数 | 预估 Token | 预估时间 | 输出物 |
|------|------|---------|-----------|---------|--------|
| 快速 | ⚡ | 1 次 | **3,000-5,000** | 3-8秒 | 一段话建议 |
| 沉思 | 💡 | 8-12 次 | **25,000-40,000** | 20-45秒 | 力量天平 + 建议 + 行动方案 |
| Pro | 🔥 | 18-24 次 | **60,000-90,000** | 1.5-3分钟 | 上述 + 时间线 + 行动地图 + PDF |
| Ultra | 🌌 | 30-40 次 | **150,000-250,000** | 3-6分钟 | 上述 + 稳定性验证 + 终局重评 + 出版级PDF |

**Token 倍率**：快速 × 1 → 沉思 × 8 → Pro × 20 → Ultra × 50

---

## 四、`tiers.py` 新配置

```python
THINKING_TIERS = {
    "quick": {
        "label": "⚡ 快速",
        "tagline": "5秒 · 一个直觉",
        "estimated_tokens": 4000,
        "estimated_seconds": 5,
        "star_visual": "dim",
        # --- 第一幕 ---
        "enable_classification": True,
        "detection_mode": None,  # 不走检测链路，只做 classify
        # --- 第二幕 ---
        "enable_diagnosis": False,
        "enable_info_detective": False,
        "enable_cognitive_unlock": False,
        "enable_experience_sim": False,
        "enable_emotion_mirror": False,
        "enable_reevaluation": False,
        # --- 第三幕 ---
        "enable_simulation": False,
        # --- Ultra 增强 ---
        "enable_stability_check": False,
        "enable_oscillation": False,
        "enable_c2_final_review": False,
        "enable_dual_temperature": False,
    },
    "deep": {
        "label": "💡 沉思",
        "tagline": "30秒 · 完整分析",
        "estimated_tokens": 32000,
        "estimated_seconds": 30,
        "star_visual": "standard",
        # --- 第一幕 ---
        "enable_classification": True,
        "detection_mode": "decision_deep",
        "filter1_level_limit": 2,
        "philosopher_count": 4,
        "enable_filter3": False,
        # --- 第二幕 ---
        "enable_diagnosis": True,
        "diagnosis_count": 4,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": False,
        "enable_emotion_mirror": False,
        "enable_reevaluation": True,
        "enable_recheck": False,
        # --- 第三幕 ---
        "enable_simulation": False,
        # --- Ultra 增强 ---
        "enable_stability_check": False,
        "enable_oscillation": False,
        "enable_c2_final_review": False,
        "enable_dual_temperature": False,
    },
    "pro": {
        "label": "🔥 Pro",
        "tagline": "2分钟 · 深度推演",
        "estimated_tokens": 75000,
        "estimated_seconds": 120,
        "star_visual": "galaxy",
        # --- 第一幕 ---
        "enable_classification": True,
        "detection_mode": "decision_pro",
        "filter1_level_limit": 4,
        "philosopher_count": 5,
        "enable_filter3": True,
        # --- 第二幕 ---
        "enable_diagnosis": True,
        "diagnosis_count": 5,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": True,
        "experience_count": 3,
        "enable_emotion_mirror": True,
        "enable_reevaluation": True,
        "enable_recheck": True,
        # --- 第三幕 ---
        "enable_simulation": True,
        "simulation_depth": 3,
        # --- 增强 ---
        "b2_max_tokens": 3072,
        "b3_max_tokens": 3072,
        "b4_max_tokens": 4096,
        "b5_max_tokens": 2048,
        "c1_max_tokens": 2048,
        "b7_max_tokens": 2600,
        "b8_max_tokens": 1800,
        "b9_max_tokens": 1600,
        # --- Ultra 增强 ---
        "enable_stability_check": False,
        "enable_oscillation": False,
        "enable_c2_final_review": False,
        "enable_dual_temperature": False,
    },
    "ultra": {
        "label": "🌌 Ultra",
        "tagline": "5分钟 · 出版级推演",
        "estimated_tokens": 200000,
        "estimated_seconds": 300,
        "star_visual": "supernova",
        # --- 第一幕 ---
        "enable_classification": True,
        "detection_mode": "decision_ultra",
        "filter1_level_limit": 4,
        "philosopher_count": 7,       # 全部哲学立场
        "enable_filter3": True,
        # --- 第二幕 ---
        "enable_diagnosis": True,
        "diagnosis_count": 5,
        "enable_info_detective": True,
        "enable_cognitive_unlock": True,
        "enable_experience_sim": True,
        "experience_count": 5,         # 比 Pro 多 2 个
        "enable_emotion_mirror": True,
        "enable_reevaluation": True,
        "enable_recheck": True,
        # --- 第三幕 ---
        "enable_simulation": True,
        "simulation_depth": 6,
        # --- 增大输出限制 ---
        "b2_max_tokens": 4096,
        "b3_max_tokens": 4096,
        "b4_max_tokens": 4096,
        "b5_max_tokens": 3072,
        "c1_max_tokens": 3072,
        "b7_max_tokens": 3200,
        "b8_max_tokens": 2600,
        "b9_max_tokens": 2400,
        # --- Ultra 独有 ---
        "enable_stability_check": True,   # C1 跑 3 次取均值
        "stability_repeats": 3,
        "enable_oscillation": True,       # 10 轮认知振荡
        "oscillation_rounds": 10,
        "enable_c2_final_review": True,   # 模拟后再重评
        "enable_dual_temperature": True,  # B7 双温度验证
    },
}
```

---

## 五、检测链路新增 profile

**文件**: `research/single_detect.py` 的 `resolve_detection_profile()`

需要新增两个 profile：

```python
if normalized == "decision_pro":
    return DetectionProfile(
        name=normalized,
        analysis_max_tokens=2200,
        filter1_level_limit=4,
        philosopher_count=5,
        enable_filter3=True,
        fail_open_to_engine_b=True,
    )
if normalized == "decision_ultra":
    return DetectionProfile(
        name=normalized,
        analysis_max_tokens=2200,
        filter1_level_limit=4,
        philosopher_count=7,  # 全部哲学立场
        enable_filter3=True,
        fail_open_to_engine_b=True,
    )
```

---

## 六、Agent 调用需读取 tier max_tokens

**文件**: `research/engine_b/agents.py`

当前所有 Agent 的 `max_tokens` 都是硬编码的。需要改为从 tier config 读取：

```python
# 当前
data = call_agent_json(B2_SYSTEM, user_msg, max_tokens=3072)

# 改为
data = call_agent_json(B2_SYSTEM, user_msg, max_tokens=tier_config.get("b2_max_tokens", 3072))
```

这意味着 `run_b2_info_gathering()` 等所有 Agent 函数需要新增一个 `tier_config` 参数（或 `max_tokens` 参数），从 `enrich_engine_b_session()` 传入。

涉及函数：
- `run_b2_info_gathering()` → 加 `max_tokens` 参数
- `run_b3_cognitive_unlock()` → 加 `max_tokens` 参数
- `run_b4_experience_simulation()` → 加 `max_tokens` + `experience_count` 参数
- `run_b5_emotional_mirror()` → 加 `max_tokens` 参数
- `run_c1_reevaluation()` → 加 `max_tokens` 参数
- `run_b7_timeline()` → 加 `max_tokens` + `dual_temperature` 参数
- `run_b8_coping_plan()` → 加 `max_tokens` 参数
- `run_b9_comparison()` → 加 `max_tokens` 参数

---

## 七、Ultra 独有模块实现指引

### 7.1 C1 稳定性验证

**在 `runtime.py` 的 `enrich_engine_b_session()` 中，C1 之后加入**：

```python
if tier_config.get("enable_stability_check"):
    repeats = tier_config.get("stability_repeats", 3)
    all_results = [c1_result]
    for temp in [0.5, 0.8]:  # 第一次用默认温度已经跑过
        extra = engine_b_agents.run_c1_reevaluation(
            session.original_question,
            session.original_pro_total,
            session.original_con_total,
            session.missing_info_items,
            ...,
            temperature=temp,
        )
        all_results.append(extra)
    
    pro_values = [r.get("updated_pro_total", 50) for r in all_results]
    con_values = [r.get("updated_con_total", 50) for r in all_results]
    session.updated_pro_total = round(sum(pro_values) / len(pro_values))
    session.updated_con_total = round(sum(con_values) / len(con_values))
    
    import statistics
    stability_std = statistics.stdev(pro_values) if len(pro_values) > 1 else 0
    session.stability_verdict = "稳固" if stability_std < 12 else "结论有波动，建议谨慎参考"
    
    _append_processing_trace(session, ..., 
        f"稳定性验证：{repeats} 次评估的标准差为 {stability_std:.1f}，结论{session.stability_verdict}。")
```

### 7.2 B7 双温度验证

**在 `_run_simulator_async()` 中改 B7 调用**：

```python
if tier_config.get("enable_dual_temperature"):
    timeline_conservative = run_b7_timeline(..., temperature=0.2)
    timeline_creative = run_b7_timeline(..., temperature=0.7)
    # 合并：取概率的均值，节点取保守版
    merged = merge_dual_timelines(timeline_conservative, timeline_creative)
    choice_a_timelines = merged
else:
    choice_a_timelines = run_b7_timeline(...)
```

### 7.3 C2 终评

**在 `_run_simulator_async()` 末尾，模拟器 output 写入后**：

```python
if tier_config.get("enable_c2_final_review"):
    c2_result = engine_b_agents.run_c2_final_review(
        session.original_question,
        session.recommendation,
        session.simulator_output,
    )
    session.simulator_output["c2_final_review"] = c2_result
    _append_processing_trace(session, ..., 
        f"终局裁判：{c2_result.get('verdict', '建议维持')}")
```

`C2_SYSTEM` prompt 单独定义在 `agents.py` 里：

```python
C2_SYSTEM = """你是终局裁判。
前面的分析建议用户：{recommendation}
模拟器跑完两条路后的结果如下：
{simulator_output_summary}

请判断：
1. 模拟结果是否支持前面的建议？
2. 如果不支持，应该如何修正？
3. 最终一句话总结

输出 JSON:
{
  "verdict": "支持/部分支持/需要修正",
  "confidence_change": "+10 / -5 / 0",
  "revised_recommendation": "如果需要修正则填写",
  "one_liner": "最终一句话"
}"""
```

### 7.4 认知振荡检测

**复用 `research/phase3_oscillation.py` 的逻辑**，但把轮数从 50 改为 10：

```python
if tier_config.get("enable_oscillation"):
    rounds = tier_config.get("oscillation_rounds", 10)
    oscillation_result = run_cognitive_oscillation(
        session.original_question,
        rounds=rounds,
    )
    session.oscillation_data = oscillation_result
    _append_processing_trace(session, ..., 
        f"认知振荡：{rounds} 轮辩论后，立场变化 {oscillation_result.get('flip_count', 0)} 次")
```

---

## 八、PDF 报告分级

**文件**: `research/output_formatter.py` + `decision/reporting.py`

| 档位 | 报告内容 |
|------|---------|
| ⚡ 快速 | 无 PDF，只有前端结果页 |
| 💡 沉思 | 简版 PDF：封面 + 问题概述 + 力量天平 + 建议 + 行动方案（2-3 页） |
| 🔥 Pro | 完整 PDF：封面 + 目录 + 分析概览 + 时间线页 + 岔路口预案 + 行动地图 + 过程日志（8-12 页） |
| 🌌 Ultra | 出版级 PDF：Pro 全部内容 + 稳定性验证章节 + 认知振荡图 + 终局裁判意见 + 双温度对比 + 信心评级（15-20 页） |

Ultra 的 PDF 独有章节：
1. **「结论稳定性」**：展示 3 次 C1 的数值分布和标准差
2. **「双温度时间线对比」**：保守版 vs 激进版时间线差异
3. **「认知振荡轨迹」**：10 轮辩论的立场变化折线图
4. **「终局裁判」**：C2 的最终裁定和信心变化
5. **「信心评级」**：综合所有验证环节的最终可信度评级（A/B/C/D/F）

---

## 九、涉及文件总览

| 文件 | 改动 |
|------|------|
| `decision/tiers.py` | **重写**：3档→4档，新增所有 max_tokens / Ultra 开关 |
| `research/single_detect.py` | 新增 `decision_pro` 和 `decision_ultra` 检测 profile |
| `research/engine_b/agents.py` | 所有 Agent 函数加 `max_tokens` 参数；新增 `C2_SYSTEM` + `run_c2_final_review()`；`run_c1_reevaluation()` 加 `temperature` 参数 |
| `research/engine_b/runtime.py` | `enrich_engine_b_session()` 读 tier config 驱动 Agent 选择；`_run_simulator_async()` 加双温度和 C2 终评；新增稳定性验证和振荡检测路径 |
| `research/engine_b/models.py` | `EngineBSession` 加 `tier`, `stability_verdict`, `oscillation_data` 字段 |
| `decision/pipeline.py` | `_start_engineb_for_decision()` 传入 tier；`_run_flash()` 更名为 `_run_quick()` |
| `decision/classifier.py` | `_build_flash_result()` 融入个性化分析内容 |
| `research/output_formatter.py` | 按档位输出不同深度的 PDF 章节 |
| `frontend/components/tier-selector.js` | 3个选项→4个选项 |
| `frontend/modules/decision-engine.js` | 新增 `ultra` 相关渲染逻辑 |
| `server.py` | `/api/decision/tiers` 返回 4 档 |
| `tests/test_decision_tier_regression.py` | 扩展为 4 档回归测试 |

---

## 十、前端 Tier 选择器视觉

```
 ⚡ 快速        💡 沉思        🔥 Pro         🌌 Ultra
┌───────┐    ┌───────┐    ┌───────┐    ┌───────────┐
│ ~4K   │    │ ~32K  │    │ ~75K  │    │ ~200K     │
│ 5秒   │    │ 30秒  │    │ 2分钟 │    │ 5分钟     │
│ 直觉  │    │ 分析  │    │ 推演  │    │ 出版级    │
└───────┘    └───────┘    └───────┘    └───────────┘
                                        ★ 多重验证
                                        ★ 终局裁判
                                        ★ 信心评级
```
