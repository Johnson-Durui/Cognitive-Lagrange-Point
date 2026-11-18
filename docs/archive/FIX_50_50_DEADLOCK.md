# 修复力量天平永远 50:50 的死锁 Bug

## 问题现象

用户无论输入什么问题、选什么思考深度，C1 最终输出的 **正方力量 / 反方力量** 永远是 **50 : 50**，建议方向显示"继续观察"或"分析中..."。

## 根因链条（三层叠加）

```
层级1（源头）→ _sum_filter2_moments() 解析不到 filter2.details
                ↓ 返回 (0, 0) → 默认 (50, 50)
层级2（放大）→ C1 系统 prompt 写死"正方/反方各50，初始平衡"
                ↓ LLM 被锚定，不敢偏离
层级3（兜底）→ fallback 用 original_pro(=50) 做默认值
                ↓ 闭环锁死 50:50
```

---

## 层级1：源头初始值 ✅ 已修复

**文件**: `research/engine_b/runtime.py`

**已完成的改动**：
- `_sum_filter2_moments()` 不再在 (0,0) 时默认返回 (50,50)，而是返回真实的 (0,0)
- 新增 `_derive_initial_balance()` 函数，按优先级尝试从多个来源推导初始值：
  1. filter2 的 `lean_strength` / `lean_direction` 明细 → 直接累加
  2. `analysis.classifications` 的 dilemma / info_gap / clp 得分 → 推导偏移
  3. filter2 的 `distribution` 文本（如 `"60:40"`）→ 直接解析
  4. 最终 fallback → 50:50（只有前三层都没数据时才触发）

**注意**：这个改动已经写入代码，不需要重做。

---

## 层级2：C1 系统 prompt 去锚定 ❌ 待修复

**文件**: `research/engine_b/agents.py`  
**位置**: 第 1238-1270 行，`C1_SYSTEM` 变量

### 当前 prompt（有问题的）

```python
C1_SYSTEM = """你是一位"认知力场再评估专家"。

给定：
1. 用户的原始问题
2. 用户已经知道的信息和补充的关键信息
3. 新补上的认知框架、经验参照、情绪镜像
4. 原始的力量对比（正方/反方各50，初始平衡）  ← ⚠️ 锚定在这里

请重新评估力量分布，给出：
...
```

### 应改为

```python
C1_SYSTEM = """你是一位"认知力场再评估专家"。

给定：
1. 用户的原始问题
2. 用户已经知道的信息和补充的关键信息
3. 新补上的认知框架、经验参照、情绪镜像
4. 初检提供的力量对比起点（可能是从检测链路推导的，也可能是默认估算值）

你的核心任务：
- 如果初检给出的正方/反方力量看起来接近（差值<10），**不要直接确认"平衡"**
- 你必须根据补充信息、框架和情绪线索，**独立判断力量的真实分布**
- 输出的 updated_pro_total 和 updated_con_total 应反映你的独立评估，不要被初检数字锚定
- 如果你认为一边明显更有道理，大胆给出 65:35 甚至 75:25 这样的结论

力量评估标准：
- 70+：强烈倾向
- 55-69：轻度倾向
- 45-54：接近平衡（只有在双方确实旗鼓相当时才给这个区间）
- 30-44：轻度反对
- <30：强烈反对

重要：50:50 意味着"完全无法区分"，现实中极少出现。请给出你的真实判断。

请以JSON格式输出：
{
  "updated_pro_total": 65,
  "updated_con_total": 42,
  "balance_shift": "力量变化的原因说明（100字内）",
  "recommendation": "建议方向（推荐/倾向反对/仍需更多信息/先做小范围验证）",
  "action_plan": "具体的第一步行动（30字内）",
  "reasoning": "完整的推理过程（200字内）"
}

只输出JSON，不要输出其他内容。"""
```

### 关键改动点

1. **删除** `"正方/反方各50，初始平衡"` — 这句话在心理上锚定 LLM 输出 50:50
2. **新增** `"不要被初检数字锚定"` — 明确指示 LLM 做独立判断
3. **新增** `"50:50 意味着完全无法区分，现实中极少出现"` — 降低 LLM 给 50:50 的倾向
4. **示例 JSON** 里的数字从 `65:58` 改为 `65:42` — 示例本身就应该体现倾斜

---

## 层级3：C1 fallback 去死值 ❌ 待修复

**文件**: `research/engine_b/agents.py`  
**位置**: 第 1650-1720 行

### 问题1：`_normalize_score` 的 fallback 值

```python
# 当前（第 1657-1658 行）
"updated_pro_total": _normalize_score(result.get("updated_pro_total"), original_pro),
"updated_con_total": _normalize_score(result.get("updated_con_total"), original_con),
```

当 C1 LLM 没有返回有效数字时，`fallback` 是 `original_pro`（=50）和 `original_con`（=50），再次锁死。

### 应改为

```python
# 如果 LLM 没给出有效数字，不要直接回退到 original，而是尝试从卡点类型推导
def _derive_fallback_balance(original_pro, original_con, diagnosed_blockages):
    """当 C1 LLM 没返回有效数字时，根据卡点类型给一个比 50:50 更有意义的估算。"""
    blockages = diagnosed_blockages or []
    # 如果有多种卡点，说明问题复杂但不代表 50:50
    if "A" in blockages:
        # 信息缺口 → 倾向"先补信息"，正方因缺信息而稍弱
        return max(35, original_pro - 8), min(65, original_con + 8)
    if "B" in blockages:
        # 认知窄门 → 换框架后通常能看出偏向
        return max(40, original_pro - 5), min(60, original_con + 5)
    if "D" in blockages:
        # 情绪干扰 → 情绪倾向某一边，理性倾向另一边
        return min(60, original_pro + 6), max(40, original_con - 6)
    return original_pro, original_con
```

然后把第 1657-1658 行改为：

```python
fb_pro, fb_con = _derive_fallback_balance(original_pro, original_con, diagnosed_blockages)
normalized = {
    "updated_pro_total": _normalize_score(result.get("updated_pro_total"), fb_pro),
    "updated_con_total": _normalize_score(result.get("updated_con_total"), fb_con),
    ...
}
```

### 问题2：`_build_c1_fallback()` 也锁死 50:50

```python
# 当前（第 1713-1714 行）
return {
    "updated_pro_total": original_pro,   # ← 又是 50
    "updated_con_total": original_con,   # ← 又是 50
    ...
}
```

### 应改为

```python
fb_pro, fb_con = _derive_fallback_balance(original_pro, original_con, blockages)
return {
    "updated_pro_total": fb_pro,
    "updated_con_total": fb_con,
    ...
}
```

---

## 层级2+3 的修改注意事项

1. `_derive_fallback_balance` 需要 `diagnosed_blockages` 参数 — 当前 `run_c1_reevaluation()` 已经接收了 `diagnosed_blockages`（第 1573 行），可以直接用

2. 修改后需要验证：启动服务 → 提随便一个两难问题 → 观察 C1 输出的 `updated_pro_total` 和 `updated_con_total` 是否不再是 50:50

3. 如果 C1 LLM 真的认为某个问题就是旗鼓相当，它仍然可以输出接近 50:50 的值 — 但这应该是 LLM 的独立判断，而不是被锚定或默认值驱动的

---

## 验证方法

```bash
# 1. 编译检查
python3 -m py_compile research/engine_b/agents.py
python3 -m py_compile research/engine_b/runtime.py

# 2. 现有C1测试（如果有）
python3 -m unittest tests.test_engine_b_agents -v

# 3. 手动验证：启动服务后输入任意两难问题
#    观察 C1 完成后 正方/反方 是否不再是 50:50
#    例：输入"要不要辞职去创业"
#    预期：正方力量和反方力量至少有 5 分以上的差距

# 4. 回归验证
python3 -m unittest tests.test_decision_pipeline_normalization -v
env PW_BROWSER=webkit node tests/decision_full_flow_live.mjs
```

---

## 涉及文件清单

| 文件 | 改动 | 状态 |
|------|------|------|
| `research/engine_b/runtime.py` | 新增 `_derive_initial_balance()`，替换 `_sum_filter2_moments()` 的默认值逻辑 | ✅ 已完成 |
| `research/engine_b/agents.py` L1238-1270 | 重写 `C1_SYSTEM` prompt，去掉 "各50" 锚定 | ❌ 待修 |
| `research/engine_b/agents.py` L1650-1658 | `_normalize_score` 的 fallback 改用卡点推导 | ❌ 待修 |
| `research/engine_b/agents.py` L1675-1721 | `_build_c1_fallback()` 的返回值改用卡点推导 | ❌ 待修 |
