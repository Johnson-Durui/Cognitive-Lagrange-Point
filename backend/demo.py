#!/usr/bin/env python3
"""Deterministic Offline / Demo Mode walkthrough builders for Cognitive Lagrange Point."""

from __future__ import annotations

import uuid

from decision.classifier import _build_quick_result
from decision.tiers import get_tier_config, normalize_tier
from research.engine_b import agents as engine_b_agents
from research.engine_b import external_signals as external_signal_store
from research.engine_b import state as engine_b_state
from research.engine_b.models import DiagnosisQuestion, EngineBPhase, EngineBSession
from research.models import CandidateQuestion, ConfirmedLagrangePoint, Force, StabilityType

from .shared import now_iso

LAGRANGE_KEYWORDS = (
    "拉格朗日",
    "电车难题",
    "trolley",
    "结构性无解",
    "牺牲一人救五人",
    "自由与安全精确",
    "意识悖论",
)


def is_lagrange_demo_question(question: str) -> bool:
    lowered = str(question or "").strip().lower()
    return any(keyword in lowered for keyword in LAGRANGE_KEYWORDS)


def build_demo_analysis(question: str, *, lagrange: bool = False) -> dict:
    trimmed = str(question or "").strip() or "未命名决策问题"
    if lagrange:
        return {
            "tensions": [
                {"pro": "功利后果总和最大化（减少总体确定性伤害）", "con": "义务论底线不可逾越（不得将个体工具化）"},
                {"pro": "主动干预承担道德责任", "con": "保持不伤害原则的边界完整性"},
            ],
            "classifications": {"dilemma": 22, "info_gap": 10, "clp": 68},
            "balance_rationale": "正反双方分别锚定在后果主义与绝对权利公理上，任何信息补充都无法消解底层价值公理的对称冲突。",
            "initial_score": 89,
            "analysis_summary": f"离线演示分析：「{trimmed}」呈现典型的公理级对冲特征，高度接近真正的认知拉格朗日点。",
        }

    choices = engine_b_agents._fallback_choice_options(trimmed, "", "")
    left_name = choices[0]["name"] if choices else "主动推进改变"
    right_name = choices[1]["name"] if len(choices) > 1 else "稳住现有基本盘"
    return {
        "tensions": [
            {"pro": f"{left_name}：换取长期成长上限与新筹码", "con": f"{right_name}：保护确定性现金流与低回撤安全垫"},
            {"pro": "窗口期行动降低踏空后悔", "con": "先验证可逆性避免冲动沉没成本"},
        ],
        "classifications": {"dilemma": 56, "info_gap": 32, "clp": 12},
        "balance_rationale": "表面上两边势均力敌，实则是关键验证指标、安全垫厚度与退出机制尚未拆清。",
        "initial_score": 76,
        "analysis_summary": f"离线演示分析：「{trimmed}」并非无解悖论，而是需要补齐关键约束与可逆试错路径的现实高代价决策。",
    }


def build_demo_detection_outcome(question: str, *, mode: str = "decision_deep") -> dict:
    lagrange = is_lagrange_demo_question(question)
    analysis = build_demo_analysis(question, lagrange=lagrange)
    candidate = CandidateQuestion(
        id=f"DQ-DEMO-{uuid.uuid4().hex[:6].upper()}",
        question_text=question,
        miner_source="demo-detect",
        balance_rationale=analysis["balance_rationale"],
        initial_score=analysis["initial_score"],
        selected_for_pipeline=True,
    )

    if lagrange:
        candidate.passed_filter_1 = True
        candidate.filter_1_details = [
            {"level": 1, "label": "量级1", "pro_strength": 52, "con_strength": 48, "delta": 4, "balance_holds": True, "reasoning": "基础情境事实下双方张力完全对称。"},
            {"level": 2, "label": "量级2", "pro_strength": 51, "con_strength": 49, "delta": 2, "balance_holds": True, "reasoning": "引入利益相关方视角后，后果与权利冲突依旧精确对等。"},
        ]
        candidate.filter_1_summary = "4 级信息注入后最大差值仅 4%，信息增量无法打破结构平衡。"

        candidate.passed_filter_2 = True
        candidate.filter_2_distribution = "4:3"
        candidate.filter_2_balance_score = 6.5
        candidate.filter_2_details = [
            {"stance": "功利主义者", "lean_direction": "正方", "lean_strength": 78, "core_argument": "总体净伤害最小化具有可度量的优先性。", "self_doubt": "个体权利一旦可被折算，社会信任底座可能动摇。"},
            {"stance": "义务论者", "lean_direction": "反方", "lean_strength": 82, "core_argument": "人永远是目的而非纯粹手段，程序正义不可让渡。", "self_doubt": "面对极端确定性灾难时，绝对禁令会承受沉重后果代价。"},
            {"stance": "自由主义者", "lean_direction": "反方", "lean_strength": 74, "core_argument": "未经同意侵害无辜个体边界缺乏正当授权。", "self_doubt": "紧急避险边界难以用单一规则覆盖。"},
            {"stance": "实用主义者", "lean_direction": "正方", "lean_strength": 70, "core_argument": "真实世界必须在坏选项与更坏选项之间做出可承担的决断。", "self_doubt": "长期制度外溢成本难以在当下准确估算。"},
        ]

        candidate.passed_filter_3 = True
        candidate.filter_3_stable_count = 8
        candidate.filter_3_classification = "stable_lagrange"
        candidate.filter_3_summary = "8/10 种跨语境重述下仍保持高强度对冲，消解测试未能击穿前提。"
        candidate.filter_3_details = [
            {"variant_id": "V1", "label": "抽象哲学版", "stable": True, "delta": 4},
            {"variant_id": "V3", "label": "第一人称版", "stable": True, "delta": 6},
            {"variant_id": "V9", "label": "反转版", "stable": True, "delta": 5},
        ]

        clp = ConfirmedLagrangePoint(
            id=f"CLP-DEMO-{uuid.uuid4().hex[:4].upper()}",
            question_text=question,
            source_candidate=candidate.id,
            pro_forces=[
                Force(
                    name="后果净收益引力",
                    direction="正方",
                    source="结果主义伦理与风险最小化直觉",
                    strength=84,
                    best_argument="在资源与时间锁死的封闭系统中，减少总体不可逆损失是最直接的理性责任。",
                    known_weakness="难以避免将局部个体承担的代价工具化。",
                ),
                Force(
                    name="现实止损本能",
                    direction="正方",
                    source="工程决策与危机响应准则",
                    strength=76,
                    best_argument="不作为同样是一种选择，且往往导致更大范围的确定性受损。",
                    known_weakness="容易低估突破规则后的次生制度溃坝效应。",
                ),
            ],
            con_forces=[
                Force(
                    name="个体权利不可侵犯边界",
                    direction="反方",
                    source="康德义务论与现代权利契约",
                    strength=85,
                    best_argument="一旦允许为了总体指标主动牺牲无辜个体，所有人的安全边界都将沦为概率计算。",
                    known_weakness="在极端情境下需要直面沉重的总体后果。",
                ),
                Force(
                    name="制度滑坡防御力",
                    direction="反方",
                    source="规则功利与社会信任演化",
                    strength=74,
                    best_argument="守住不可逾越的红线，长期看保护了整个协作系统的可预期性。",
                    known_weakness="短期内显得僵化且难以安抚具体受害方。",
                ),
            ],
            pro_total=50.3,
            con_total=49.7,
            balance_precision=99.4,
            hidden_forces=[
                {"name": "二元封闭框架预设", "description": "题目排除了延迟决策、第三方介入与补偿机制，使两股公理正面锁死。"}
            ],
            balance_analysis="正反双方分别代表『结果最优』与『权利底线』两条不可通约的人类核心公理，在封闭条件下形成高精度认知拉格朗日平衡。",
            stability_type=StabilityType.STABLE,
            stability_summary="微扰注入后仍迅速回归 50:50 力场中心。",
            fault_lines=["功利后果—绝对权利断层线"],
            tunnel_connections=["紧急避险悖论", "算法伦理分配困境"],
        )

        return {
            "analysis": analysis,
            "filters": {
                "filter1": {"passed": True, "status": "passed", "summary": candidate.filter_1_summary, "details": candidate.filter_1_details},
                "filter2": {
                    "passed": True,
                    "status": "passed",
                    "summary": "4 个核心哲学框架形成 2:2 对称分布，力矩差仅 1.2%。",
                    "details": candidate.filter_2_details,
                    "distribution": "2:2",
                    "balance_score": 1.2,
                },
                "filter3": {
                    "passed": True,
                    "status": "passed",
                    "summary": candidate.filter_3_summary,
                    "details": candidate.filter_3_details,
                    "stable_count": 8,
                    "classification": "stable_lagrange",
                },
            },
            "result": {
                "is_lagrange_point": True,
                "failed_at": None,
                "summary": "离线演示确认：三层筛子验证后仍保持公理级平衡，这是一个标准认知拉格朗日点。",
                "recommend_engine_b": False,
                "candidate": candidate.to_dict(),
                "clp": clp.to_dict(),
            },
        }

    # Practical real-life dilemma -> breaks symmetry at Filter 2 and routes into Engine B
    candidate.passed_filter_1 = True
    candidate.filter_1_details = [
        {"level": 1, "label": "量级1", "pro_strength": 54, "con_strength": 46, "delta": 8, "balance_holds": True, "reasoning": "浅层背景信息下，改变收益与维持现状安全感仍然拉扯。"},
        {"level": 2, "label": "量级2", "pro_strength": 58, "con_strength": 42, "delta": 16, "balance_holds": True, "reasoning": "引入现金流与可逆试错视角后，天平开始出现松动。"},
    ]
    candidate.filter_1_summary = "前两级背景注入显示表面僵局仍在，需进一步跨框架检验。"

    candidate.passed_filter_2 = False
    candidate.filter_2_distribution = "3:1"
    candidate.filter_2_balance_score = 34.0
    candidate.filter_2_details = [
        {"stance": "实用主义者", "lean_direction": "正方", "lean_strength": 76, "core_argument": "只要能把试错成本控制在安全垫之内，小步验证远优于原地内耗。", "self_doubt": "前提是必须设定明确的止损检查站。"},
        {"stance": "功利主义者", "lean_direction": "正方", "lean_strength": 71, "core_argument": "长期能力复利与选择权扩展的期望收益高于静态防守。", "self_doubt": "短期波动期的心理消耗需要纳入成本。"},
        {"stance": "自由主义者", "lean_direction": "正方", "lean_strength": 68, "core_argument": "保留主动探索与随时撤回的自由度，能最大化个人掌控感。", "self_doubt": "需确保不透支核心生活底线。"},
        {"stance": "关怀伦理者", "lean_direction": "反方", "lean_strength": 62, "core_argument": "需要兼顾现有生活节奏与身边重要关系的可承受度。", "self_doubt": "长期压抑真实诉求同样会反噬关系质量。"},
    ]

    return {
        "analysis": analysis,
        "filters": {
            "filter1": {"passed": True, "status": "passed", "summary": candidate.filter_1_summary, "details": candidate.filter_1_details},
            "filter2": {
                "passed": False,
                "status": "failed",
                "summary": "4 个框架形成 3:1 倾向（力矩差 34.0%），表明这不是无解悖论，而是可通过补齐约束突破的现实决策。",
                "details": candidate.filter_2_details,
                "distribution": "3:1",
                "balance_score": 34.0,
            },
            "filter3": {
                "passed": None,
                "status": "pending",
                "summary": f"当前模式（{mode}）已在筛子2识别出突破方向，直接转交 Engine B 做深度拆解。",
                "details": [],
                "stable_count": 0,
                "classification": "",
            },
        },
        "result": {
            "is_lagrange_point": False,
            "failed_at": "filter2",
            "summary": "跨框架检验发现明显突破口：问题并非结构性无解，核心卡点在于信息缺口与试错护栏尚未建立，已移交 Engine B。",
            "recommend_engine_b": True,
            "candidate": candidate.to_dict(),
            "clp": None,
        },
    }


def build_demo_simulator_for_session(session: EngineBSession, *, tier: str | None = None) -> dict:
    resolved_tier = normalize_tier(tier or session.tier)
    tier_config = get_tier_config(resolved_tier)
    user_params = {
        "savings_months": 6,
        "other_income": "保留基础副业/备用现金缓冲",
        "fixed_expenses": "每月核心刚性支出控制在安全线内",
        "time_to_reverse": "30-60 天内可低损回撤",
        "reversal_cost": "主要是前 4 周时间投入与少量试错预算，不伤及核心现金流",
        "point_of_no_return": "正式放弃原有退路或一次性投入超过 3 个月安全垫之前均可撤回",
        "worst_fear": "投入时间精力后发现新方向兑现慢、同时丢掉原有确定性节奏",
        "question_context": session.original_question,
    }
    choices = engine_b_agents._fallback_choice_options(
        session.original_question,
        session.recommendation,
        session.action_plan,
    )
    choice_a = choices[0]
    choice_b = choices[1]

    choice_a_sim = engine_b_agents._build_b7_timeline_fallback(
        choice_a["name"],
        choice_a["description"],
        user_params,
    )
    choice_b_sim = engine_b_agents.build_distinct_timeline_fallback(
        choice_b["name"],
        choice_b["description"],
        user_params,
    )
    coping = engine_b_agents._build_b8_fallback(choice_a_sim, choice_b_sim, user_params)
    comparison = engine_b_agents._build_b9_fallback(
        choice_a_sim,
        choice_b_sim,
        user_params,
        decision_biases=session.decision_biases,
        alternative_path=session.alternative_path,
    )

    monte_carlo = {}
    if tier_config.get("enable_ultra_monte_carlo"):
        monte_carlo = engine_b_agents.run_ultra_monte_carlo_collision(
            question=session.original_question,
            choice_a_sim=choice_a_sim,
            choice_b_sim=choice_b_sim,
            user_params=user_params,
            value_profile=session.value_profile,
            decision_biases=session.decision_biases,
            external_signals=session.external_signals,
            sample_count=160,
            persona_count=16,
            agents_per_branch=6,
            rounds=2,
            branch_sample_limit=24,
            llm_panels=0,
        )
        smooth_prob = monte_carlo.get("smooth_prob") if isinstance(monte_carlo, dict) else {}
        if isinstance(smooth_prob, dict) and smooth_prob:
            comparison["probability_optimistic"] = smooth_prob.get("optimistic", comparison.get("probability_optimistic"))
            comparison["probability_baseline"] = smooth_prob.get("baseline", comparison.get("probability_baseline"))
            comparison["probability_pessimistic"] = smooth_prob.get("pessimistic", comparison.get("probability_pessimistic"))

    raw_output = {
        "user_params": user_params,
        "choice_a": choice_a_sim,
        "choice_b": choice_b_sim,
        "crossroads": coping.get("crossroads", []),
        "worst_case_survival_plan": coping.get("worst_case_survival_plan", {}),
        "milestones": coping.get("milestone_check_system", []),
        "comparison_summary": comparison.get("comparison_summary", ""),
        "action_map_a": comparison.get("action_map_a", []),
        "action_map_b": comparison.get("action_map_b", []),
        "final_insight": comparison.get("final_insight", ""),
        "regret_score_a": comparison.get("regret_score_a"),
        "regret_score_b": comparison.get("regret_score_b"),
        "probability_optimistic": comparison.get("probability_optimistic"),
        "probability_baseline": comparison.get("probability_baseline"),
        "probability_pessimistic": comparison.get("probability_pessimistic"),
        "decision_biases": comparison.get("decision_biases", session.decision_biases),
        "bias_reminder": comparison.get("bias_reminder", session.bias_reminder),
        "third_path": comparison.get("third_path", session.alternative_path),
        "market_signals": session.external_signals,
        "value_profile": session.value_profile,
        "monte_carlo": monte_carlo,
        "demo_mode": True,
    }
    return engine_b_agents.normalize_simulator_output(raw_output)


def build_demo_engineb_session(
    question: str,
    *,
    tier: str,
    source_detection: dict,
    include_simulator: bool = False,
) -> EngineBSession:
    normalized_tier = normalize_tier(tier)
    created = now_iso()
    session = EngineBSession.create_new(question, created, tier=normalized_tier)
    session.source_detection = source_detection
    session.original_pro_total = 52
    session.original_con_total = 48

    choices = engine_b_agents._fallback_choice_options(question, "", "")
    choice_a_name = choices[0]["name"] if choices else "推进新方案"
    choice_b_name = choices[1]["name"] if len(choices) > 1 else "稳住原方案"

    diag_questions = [
        DiagnosisQuestion(
            id="demo_q1",
            question_text=f"围绕「{question[:24]}」，当前最让你犹豫的核心变量是什么？",
            options=["真实净收益与兑现周期不明", "担心退出成本与安全垫不足", "怕错过窗口期后悔"],
            user_answer="担心退出成本与安全垫不足",
            answered_at=created,
        ),
        DiagnosisQuestion(
            id="demo_q2",
            question_text="如果先做一轮 14-30 天的低成本试运行，你最希望验证哪个信号？",
            options=["真实高频使用率/产出密度", "现金流与精力损耗是否可控", "外部正反馈是否持续"],
            user_answer="现金流与精力损耗是否可控",
            answered_at=created,
        ),
    ]
    session.diagnosis_questions = diag_questions
    session.diagnosis_answers = {q.id: str(q.user_answer or "") for q in diag_questions}
    session.diagnosed_blockages = ["A", "B", "D"]

    session.value_profile = {
        "primary_values": ["可逆安全垫", "长期成长复利", "掌控感"],
        "summary": "你优先看重下限可控前提下的长期成长空间，不希望在缺乏退路时盲目重仓。",
    }
    session.decision_biases = [
        {
            "name": "现状偏差与损失厌恶叠加",
            "signal": "容易把短期切换摩擦放大为永久性损失，同时忽略原地不动的时间机会成本。",
            "counter_move": "把『一次性终局决定』改写为『带止损线的 30 天可逆实验』。",
        }
    ]
    session.bias_reminder = "警惕把可逆试错当成不可逆赌注：先锁定安全垫上限，再用真实样本替代脑内空转。"
    session.external_signals = external_signal_store.retrieve_external_signals(question, limit=4) or [
        {
            "source": "本地决策基准快照",
            "stance": "balanced",
            "summary": "高满意度决策者普遍先跑 2-4 周最小闭环验证，确认真实投入产出比后再做长期承诺。",
        }
    ]

    session.missing_info_items = [
        {
            "title": "最小验证闭环的真实兑现率",
            "why_critical": f"决定「{choice_a_name}」究竟是真实增益还是短期新鲜感。",
            "how_to_verify": "用未来 14 天的实际产出时长、净收益或问题解决率做硬指标核验。",
            "content": "在不切断现有安全垫的前提下，先统计连续两周的真实有效产出与使用密度。",
        },
        {
            "title": "回撤边界与最大可承受亏损线",
            "why_critical": "一旦明确最坏损失上限，焦虑感会迅速回落到可计算区间。",
            "how_to_verify": "列出 30 天试运行期间的硬性预算上限与一键回退触发条件。",
            "content": "将首次试错成本严格限制在 1 个月可支配缓冲以内，保留随时回退通道。",
        },
    ]
    session.cognitive_frames = [
        {
            "title": "单向门 vs 双向门框架",
            "core_insight": f"不必把「{choice_a_name} vs {choice_b_name}」当成不可逆终局判决，先把它拆成可随时撤回的双向门实验。",
            "try_now": "写下如果 30 天后效果不及预期，具体用哪三步退回安全区。",
        },
        {
            "title": "后悔最小化与下限保护",
            "core_insight": "先用安全垫锁死最坏结果，再比较一年后哪条路更少带来『当初连试都没试』的遗憾。",
            "try_now": "对比 6 个月后维持原状与小步验证两种状态的真实筹码增量。",
        },
    ]

    if normalized_tier in {"pro", "ultra"}:
        session.experience_cases = [
            {
                "title": "先做副线验证再切换的稳健派案例",
                "choice_made": f"保留「{choice_b_name}」底座的同时，用 4 周业余/小范围窗口验证「{choice_a_name}」。",
                "outcome": "第 3 周拿到真实反馈数据，既避免了裸奔焦虑，又顺利完成了方向校准。",
                "lesson": "决定成败的往往不是勇气大小，而是第一次出手时有没有保留安全垫。",
            },
            {
                "title": "直接全仓切换但缺少止损线的激进派案例",
                "choice_made": "未做小样本测试便一次性押注新方向。",
                "outcome": "遇到正常磨合期波动时因现金流和心理双重紧绷被迫提前退场。",
                "lesson": "没有检查站的全仓投入，容易在黎明前的常规逆风期心态失衡。",
            },
        ]
        session.emotional_insight = {
            "dominant_emotions": [
                {"emotion": "对沉没成本与踏空的双重焦虑", "intensity": "中高", "evidence": "既怕乱动伤及现有稳定盘，又怕拖延错失成长窗口。"}
            ],
            "grounding_prompt": "你不需要今天就签下未来三年的卖身契，只需要决定未来 14 天跑哪个最小实验。",
            "decision_biases": session.decision_biases,
        }

    session.alternative_path = {
        "title": f"第三条路：保留「{choice_b_name}」底盘 + 30天「{choice_a_name}」可逆试运行",
        "summary": "不急于二选一硬切，先设定 30 天低成本实验窗口与硬性止损指标，达标再加码、不达标零内伤回撤。",
        "first_step": "今天先划定实验预算上限与第 14 天、第 30 天两个量化复盘指标。",
        "guardrail": "实验期内绝不动用核心安全垫，不提前切断原有退路。",
    }

    session.updated_pro_total = 66
    session.updated_con_total = 34
    session.recommendation = f"建议采用「先护住下限，再以 30 天可逆实验推进 {choice_a_name}」的渐进突破策略"
    session.action_plan = (
        f"1. 第 1-3 天：保留「{choice_b_name}」核心安全垫，明确最多可投入的时间与资金上限；\n"
        f"2. 第 4-14 天：围绕「{choice_a_name}」跑通一个最小真实闭环，记录实际产出与消耗；\n"
        "3. 第 30 天检查站：若净收益与状态双达标则正式加码，否则按预案低损回撤。"
    )
    session.reasoning = (
        "离线演示引擎综合拆解显示：原问题的表面 52:48 僵局主要来自『全有或全无』的二元假设。"
        "一旦引入双向门可逆实验与 30 天止损护栏，行动风险显著下降，正反力矩比清晰拉开至 66:34。"
    )
    session.recheck = {
        "needed": False,
        "status": "skipped",
        "threshold": 15,
        "difference": 32,
        "reason": "补全信息与第三条路后，力矩差已扩大至 32（高于阈值 15），无需回送 Engine A 二次检测。",
        "job_id": "",
        "job": None,
        "error": "",
        "requested_at": "",
        "completed_at": "",
    }

    session.processing_trace = [
        {"id": uuid.uuid4().hex[:8], "phase": "b1_diagnosis", "title": "离线演示 · 卡点定位完成", "detail": "识别出信息缺口、二元框架束缚与损失厌恶三类核心阻力。", "at": created},
        {"id": uuid.uuid4().hex[:8], "phase": "b2_info_fill", "title": "离线演示 · 关键事实与框架补齐", "detail": "已补齐最小验证指标、回撤边界与『单向门/双向门』判断框架。", "at": created},
        {"id": uuid.uuid4().hex[:8], "phase": "b5_5_alternative", "title": "离线演示 · 第三条路已生成", "detail": session.alternative_path["title"], "at": created},
        {"id": uuid.uuid4().hex[:8], "phase": "c1_reevaluation", "title": "离线演示 · 力量重估 66:34", "detail": session.recommendation, "at": created},
    ]

    if include_simulator:
        session.simulator_output = build_demo_simulator_for_session(session, tier=normalized_tier)
        session.phase = EngineBPhase.SIMULATOR_COMPLETE
        session.processing_trace.append({
            "id": uuid.uuid4().hex[:8],
            "phase": "simulator_complete",
            "title": "离线演示 · 未来时间线与行动地图已生成",
            "detail": session.simulator_output.get("final_insight", "顺风/平稳/逆风三条时间线与止损护栏已就绪。"),
            "at": now_iso(),
        })
    else:
        session.phase = EngineBPhase.COMPLETED

    session.updated_at = now_iso()
    engine_b_state.save_session(session)
    return session


def run_demo_decision_into(decision: dict, *, detection_manager=None) -> dict:
    """Populate `decision` deterministically in-place for Offline / Demo Mode."""
    question = str(decision.get("question", "") or "").strip()
    tier = normalize_tier(decision.get("tier"))
    tier_config = get_tier_config(tier)
    ts = now_iso()

    decision.setdefault("meta", {})["demo_mode"] = True
    decision["logs"] = list(decision.get("logs") or [])
    decision["logs"].append("🧪 离线演示模式已启用（无需配置 CLP_API_KEY 即可完整体验全链路推演与 PDF 导出）")

    if tier == "quick":
        analysis = build_demo_analysis(question, lagrange=is_lagrange_demo_question(question))
        quick_result = _build_quick_result(question, analysis)
        quick_result["demo_mode"] = True
        decision["analysis"] = analysis
        decision["result"] = quick_result
        decision["status"] = "completed"
        decision["phase"] = "completed"
        decision["step"] = "done"
        decision["status_text"] = "离线演示 · 快速判断已生成"
        decision["completed_at"] = ts
        decision["updated_at"] = ts
        decision["logs"].append("✅ 快速结构判断已完成")
        return decision

    detect_mode = tier_config.get("detection_mode") or f"decision_{tier}"
    outcome = build_demo_detection_outcome(question, mode=detect_mode)
    detect_job_id = f"demo-{uuid.uuid4().hex[:6]}"
    detect_job = {
        "job_id": detect_job_id,
        "question": question,
        "input_question": question,
        "mode": detect_mode,
        "loop_context": {"demo_mode": True},
        "status": "completed",
        "phase": "completed",
        "status_text": "离线演示 · 第一幕结构检测完成",
        "created_at": decision.get("created_at") or ts,
        "updated_at": ts,
        "completed_at": ts,
        "analysis": outcome["analysis"],
        "filters": outcome["filters"],
        "result": outcome["result"],
        "error": None,
        "logs": [
            "✨ 初始化离线演示检测任务...",
            "✅ 语义对立结构分析完成",
            "🏁 多层结构稳定性检验完成",
        ],
    }

    if detection_manager is not None and hasattr(detection_manager, "jobs"):
        with detection_manager.lock:
            detection_manager.jobs[detect_job_id] = detect_job
            detection_manager.latest_job_id = detect_job_id

    decision["linked_detection_job_id"] = detect_job_id
    decision["detection_job"] = detect_job
    decision["analysis"] = outcome["analysis"]

    if outcome["result"].get("is_lagrange_point") is True:
        final_result = {
            "mode": "lagrange_confirmed",
            "summary": outcome["result"]["summary"],
            "detection_result": outcome["result"],
            "can_export_report": True,
            "demo_mode": True,
        }
        decision["result"] = final_result
        decision["status"] = "completed"
        decision["phase"] = "completed"
        decision["step"] = "done"
        decision["status_text"] = "离线演示 · 确认为认知拉格朗日点"
        decision["completed_at"] = ts
        decision["updated_at"] = ts
        decision["logs"].append("🔴 第一幕确认这是认知拉格朗日点，可直接查看力场解剖并导出 PDF 报告")
        return decision

    include_simulator = bool(tier_config.get("enable_simulation"))
    session = build_demo_engineb_session(
        question,
        tier=tier,
        source_detection=detect_job,
        include_simulator=include_simulator,
    )
    session_dict = session.to_dict()

    decision["linked_engineb_session_id"] = session.session_id
    decision["engineb_session"] = session_dict
    decision["meta"]["simulator_ready"] = not include_simulator and bool(tier_config.get("allow_manual_simulation"))
    decision["meta"]["simulator_started"] = include_simulator
    decision["status"] = "completed"
    decision["phase"] = "completed"
    decision["step"] = "done"
    decision["completed_at"] = now_iso()
    decision["updated_at"] = decision["completed_at"]

    if include_simulator:
        decision["status_text"] = "离线演示 · 三幕全流程推演已完成"
        decision["result"] = {
            "mode": "decision_complete",
            "summary": "离线演示三幕决策流程已完成，可查看未来时间线并导出双版本 PDF 报告。",
            "engineb_session_id": session.session_id,
            "can_export_report": True,
            "demo_mode": True,
        }
        decision["logs"].append("🔮 第三幕未来选择模拟器与行动地图已生成")
    else:
        decision["status_text"] = "离线演示 · 第二幕决策建议已完成（可手动开启未来模拟或导出 PDF）"
        decision["result"] = {
            "mode": "engineb_complete",
            "summary": "离线演示第二幕决策突破已完成，可导出报告或继续启动第三幕未来模拟。",
            "engineb_session_id": session.session_id,
            "can_export_report": True,
            "demo_mode": True,
        }
        decision["logs"].append("🧭 第二幕建议已形成，可随时导出 PDF 或进入第三幕未来模拟")

    return decision
