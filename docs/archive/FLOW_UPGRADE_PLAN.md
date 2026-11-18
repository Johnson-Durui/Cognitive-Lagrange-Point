# 决策流程升级方案（6 项）

> 基于 2026-04-07 的完整代码审查，以下是除 50:50 死锁外的所有流程级改进点。
> 按优先级排列，每项都给出根因、修改位置和具体方案。

---

## 1. 🔴 Tier 配置未驱动 Agent 选择（三档无区别）

### 问题

`decision/tiers.py` 精心定义了三档开关（`enable_experience_sim`, `enable_emotion_mirror` 等），但 `runtime.py` 的 `enrich_engine_b_session()` **完全不读这些配置**。

当前的判断逻辑是靠 `blockages` 类型硬编码的：
```python
if "A" in blockages: → 跑 B2
if "B" in blockages: → 跑 B3  
if "C" in blockages: → 跑 B4
if "D" in blockages: → 跑 B5
```

这意味着：
- 用户选了 `deep`（`enable_experience_sim: False`），但卡点是 C → B4 照跑
- 用户选了 `panorama`（全开），但没发现 D 型卡点 → B5 不跑
- **三个等级在第二幕完全没有区别**，`tiers.py` 的配置是死代码

### 涉及文件

| 文件 | 说明 |
|------|------|
| `research/engine_b/runtime.py` L455-710 | `enrich_engine_b_session()` 函数 |
| `research/engine_b/models.py` | `EngineBSession` 模型（需加 `tier` 字段） |
| `decision/tiers.py` | 配置定义（不改，只是被读取） |

### 修复方案

**第一步**：给 `EngineBSession` 模型加 `tier` 字段

```python
# models.py EngineBSession
tier: str = "deep"  # 新增，默认 deep
```

**第二步**：在 `start_engine_b_session()` 里传入 tier

当前 `start_engine_b_session()` (runtime.py ~L728) 没有 tier 参数。需要：

```python
def start_engine_b_session(question: str, *, source_detection: dict | None = None, tier: str = "deep") -> EngineBSession:
    ...
    session.tier = tier
```

然后从 `pipeline.py` 的 `_start_engineb_for_decision()` (L286) 传入：

```python
session = start_engine_b_session(question, source_detection=source_detection, tier=decision.get("tier", "deep"))
```

**第三步**：在 `enrich_engine_b_session()` 里用 tier 配置控制 Agent 执行

新增一个辅助函数：

```python
def _should_run_agent(session, blockages, blockage_type, tier_key):
    """只有 tier 允许且卡点匹配时才运行对应 Agent。
    panorama 模式额外规则：即使没有对应卡点也强制运行。
    """
    from decision.tiers import get_tier_config
    config = get_tier_config(session.tier)
    tier_allowed = config.get(tier_key, True)
    if not tier_allowed:
        return False
    if session.tier == "panorama":
        return True  # 全景模式全部强跑
    return blockage_type in blockages or not blockages
```

然后把所有条件判断从：
```python
if "A" in blockages or not blockages:
    session.missing_info_items = run_b2(...)
```
改为：
```python
if _should_run_agent(session, blockages, "A", "enable_info_detective"):
    session.missing_info_items = run_b2(...)
```

对 B3/B4/B5 同理：
- B3 → `_should_run_agent(session, blockages, "B", "enable_cognitive_unlock")`
- B4 → `_should_run_agent(session, blockages, "C", "enable_experience_sim")`
- B5 → `_should_run_agent(session, blockages, "D", "enable_emotion_mirror")`

> **注意**：刚才查代码时看到 runtime.py 已经有 `tier_config = _get_session_tier_config(session)` 和 `_should_run_agent()` 的雏形（L477, L489），说明这块可能已经部分实现了。请先确认这些函数的实际内容，再决定是补齐还是从头写。

---

## 2. 🔴 Flash 模式输出太简陋

### 问题

`flash` 调用 `run_flash_classifier()` 后直接输出一段**固定模板文案**（三种类型选一个），没有任何针对用户问题的个性化内容。

`classifier.py` 的 `_build_flash_result()` 里，`recommendation` 和 `next_step` 是写死的句子，而 `analysis_summary` 和 `balance_rationale` 虽然从 LLM 返回了，但只是原样塞进结果对象，没有融入推荐文案。

### 涉及文件

| 文件 | 位置 |
|------|------|
| `decision/classifier.py` L19-62 | `_build_flash_result()` |

### 修复方案

把 `analysis_summary` 和 `balance_rationale` 融入 `recommendation`：

```python
def _build_flash_result(question: str, analysis: dict) -> dict:
    classifications = analysis.get("classifications", {}) if isinstance(analysis, dict) else {}
    ranking = _sorted_scores(classifications)
    primary, primary_score = ranking[0]
    secondary_score = ranking[1][1] if len(ranking) > 1 else 0
    confidence = max(52, min(91, 55 + primary_score - secondary_score))

    # 从 LLM 分析中提取个性化内容
    analysis_summary = str(analysis.get("analysis_summary", "") or "").strip()
    balance_rationale = str(analysis.get("balance_rationale", "") or "").strip()
    
    # 将模板与个性化分析拼接
    if primary == "info_gap":
        recommendation_title = "先补关键事实，再做选择"
        base_recommendation = "你眼下更像是被信息缺口卡住了，不是没有判断力。"
        next_step = "把"如果现在知道答案就能立刻决定"的三个问题写下来，优先补最硬的那个。"
    elif primary == "clp":
        recommendation_title = "这题更像没有唯一标准答案"
        base_recommendation = "别继续把它当成一道一定能算出唯一正确解的题。"
        next_step = "各写下"选 A 最坏要承受什么"和"选 B 最坏要承受什么"，看你更能承担哪边。"
    else:
        recommendation_title = "这更像代价很重，但可以选的问题"
        base_recommendation = "它不是无解，只是每个方向都要付代价。"
        next_step = "为更想走的方向设计一个 7 天内可执行、可撤回的小实验。"

    # ✅ 把 LLM 的个性化分析揉进推荐文案
    recommendation_parts = [base_recommendation]
    if analysis_summary:
        recommendation_parts.append(analysis_summary)
    if balance_rationale:
        recommendation_parts.append(balance_rationale)
    recommendation = " ".join(recommendation_parts)
    
    return { ... }
```

---

## 3. 🟡 模拟器自动启动：用户没有控制权

### 问题

`pipeline.py` 的 `_monitor_engineb_flow()` 在 C1 完成后**自动**调用 `_maybe_start_simulator()`（L510-514），用户还没看完 C1 建议就被推进第三幕，token 已经开始消耗了。

### 涉及文件

| 文件 | 位置 |
|------|------|
| `decision/pipeline.py` L510-514 | 自动启动模拟器逻辑 |
| `frontend/modules/decision-engine.js` L366-371 | C1 结果渲染（需加"启动模拟"按钮） |
| `frontend/components/decision-flow-view.js` | `renderC1Result()` 方法 |

### 修复方案

**方案 A：改为手动启动（推荐）**

1. 在 `_monitor_engineb_flow()` 里注释掉自动启动逻辑：
```python
# pipeline.py L510-514
if _has_c1_result(session_data):
    # 不再自动启动模拟器，让用户在 C1 页面点击按钮
    pass  # 原来的 self._maybe_start_simulator(decision_id, session_data) 注释掉
```

2. 前端 C1 结果页加一个明确的 CTA 按钮：
```
"想看两条路各自的未来走向吗？"  
[🔮 启动未来模拟器（约消耗 2 万 token）]  
[✓ 当前建议已经足够，跳过模拟]
```

3. "跳过模拟"按钮直接调用 `_complete(decision_id)` 完成决策。

**方案 B：自动但加窗口期**

如果仍想保留自动，在 `_maybe_start_simulator` 前加 5 秒延迟和前端 toast：
```python
self._append_log(decision_id, "⏳ 5 秒后将自动进入未来模拟，点击"跳过"可阻止")
time.sleep(5)
# 检查用户是否在这 5 秒内点了"跳过"
decision = self.get_status(decision_id).get("decision") or {}
if decision.get("meta", {}).get("skip_simulator"):
    self._complete(decision_id)
    return
self._maybe_start_simulator(decision_id, session_data)
```

---

## 4. 🟡 SSE 断线后不会重连

### 问题

`decision-engine.js` L397-399：
```javascript
source.onerror = () => {
    closeDecisionStream();  // 直接关掉，不恢复
};
```

如果用户网络闪断或合盖再开，页面停在当时的状态，再也不更新。

### 涉及文件

| 文件 | 位置 |
|------|------|
| `frontend/modules/decision-engine.js` L378-400 | `startDecisionEvents()` |

### 修复方案

```javascript
export function startDecisionEvents(decisionId) {
  closeDecisionStream();
  let retryCount = 0;
  const maxRetries = 5;

  function connect() {
    const source = new EventSource(`/api/decision/events?id=${encodeURIComponent(decisionId)}`);
    state.decisionEventSource = source;

    source.onmessage = (event) => {
      retryCount = 0;  // 收到消息就重置重试计数
      try {
        const payload = JSON.parse(event.data);
        const decision = payload.decision;
        if (!decision) return;
        renderDecisionSession(decision);
        if (decision.status === 'completed' || decision.status === 'failed') {
          closeDecisionStream();
        }
      } catch (error) {
        console.error('Decision SSE parse failed', error);
      }
    };

    source.onerror = () => {
      closeDecisionStream();
      if (retryCount < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retryCount), 10000);
        retryCount++;
        console.warn(`SSE 断线，${delay}ms 后第 ${retryCount} 次重连`);
        setTimeout(connect, delay);
      } else {
        showToast('连接已断开，请刷新页面重试', 'warning');
      }
    };
  }

  connect();
}
```

---

## 5. 🟡 `/api/decision/upgrade` 升级功能空实现

### 问题

路由存在但 `DecisionManager` 没有 `upgrade()` 方法。用户 flash→deep 要完全重跑。

### 涉及文件

| 文件 | 位置 |
|------|------|
| `decision/pipeline.py` | 需新增 `upgrade()` 方法 |
| `server.py` L292 | `/api/decision/upgrade` 路由（已存在但可能是空壳） |

### 修复方案

在 `DecisionManager` 中新增：

```python
def upgrade(self, decision_id: str, new_tier: str) -> dict:
    """从低等级升级到高等级，复用已有结果。"""
    decision = self.get_status(decision_id).get("decision")
    if not decision:
        raise ValueError("找不到要升级的决策。")
    
    old_tier = decision.get("tier", "flash")
    new_tier = normalize_tier(new_tier)
    
    if old_tier == new_tier:
        raise ValueError("已在当前等级。")
    
    # 不允许降级
    tier_order = {"flash": 0, "deep": 1, "panorama": 2}
    if tier_order.get(new_tier, 0) <= tier_order.get(old_tier, 0):
        raise ValueError("只能升级，不能降级。")

    new_config = get_tier_config(new_tier)

    def updater(job: dict) -> None:
        job["tier"] = new_tier
        job["tier_config"] = new_config
        job["status"] = "running"
        job["meta"]["upgraded_from"] = old_tier
        job["meta"]["star_visual"] = new_config.get("star_visual", "standard")
        _append_decision_log_line(job, f"⬆️ 已从 {old_tier} 升级到 {new_config['label']}")

    self._update_job(decision_id, updater)

    # 从当前阶段继续
    current_phase = decision.get("phase", "")
    question = decision.get("question", "")

    if current_phase in {"completed", "failed"} and old_tier == "flash":
        # flash 只做了 classify，从检测阶段重新开始
        worker = threading.Thread(
            target=self._run_detect_proxy,
            args=(decision_id, question, new_tier),
            daemon=True,
        )
        worker.start()
    elif decision.get("linked_engineb_session_id"):
        # 已有 Engine B 会话，重新启动监听
        self._ensure_engineb_monitoring(decision_id)
    
    return self.get_status(decision_id)
```

---

## 6. 🟢 决策后跟踪缺入口

### 问题

决策完成后没有入口让用户标记"我最终选了什么"、"满意吗"。

### 涉及文件

| 文件 | 说明 |
|------|------|
| `research/db.py` | 检查 `decisions` 表是否已有 `user_choice` / `user_satisfaction` / `follow_up_note` 列 |
| `server.py` | 新增 `POST /api/decision/feedback` |
| `decision/pipeline.py` | 新增 `submit_feedback()` |

### 修复方案

```python
# server.py
@app.post("/api/decision/feedback")
async def submit_decision_feedback(request: Request):
    body = await request.json()
    decision_id = body.get("decision_id")
    user_choice = body.get("user_choice", "")
    satisfaction = body.get("satisfaction", 0)  # 1-5
    note = body.get("follow_up_note", "")
    # 写入 decisions 表
    db_update_decision_feedback(decision_id, user_choice, satisfaction, note)
    return {"status": "ok"}
```

前端在决策完成页底部加一行：

```
你最终选了什么？ [选项A] [选项B] [其他]
这个分析有帮助吗？ ⭐⭐⭐⭐⭐
```

---

## 优先级总览

| # | 问题 | 影响 | 工作量 | 建议优先级 |
|---|------|------|--------|-----------|
| 1 | Tier 配置无效 | 三档没区别 | 中（2-3h） | 🔴 P0 |
| 2 | Flash 输出简陋 | 用户觉得没用 | 小（30min） | 🔴 P0 |
| 3 | 模拟器自动启动 | token 被自动消耗 | 小（1h） | 🟡 P1 |
| 4 | SSE 不重连 | 页面会停更 | 小（30min） | 🟡 P1 |
| 5 | Upgrade 空实现 | 升级要重跑 | 中（1-2h） | 🟡 P1 |
| 6 | 决策后跟踪 | 产品闭环 | 小（1h） | 🟢 P2 |

加上已有的 `FIX_50_50_DEADLOCK.md`，这个管线从"能跑"到"好用"的关键改进就齐了。
