"""Engine B - Data Models"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional
import uuid


class BlockageType(Enum):
    """四类卡点类型"""
    A_INFO_VOID = "A"  # 信息黑洞 - missing critical information
    B_COGNITIVE_NARROW = "B"  # 认知窄门 - missing cognitive frameworks
    C_EXPERIENCE_BLANK = "C"  # 经验盲区 - no experience reference
    D_EMOTIONAL_INTERFERENCE = "D"  # 情绪干扰 - emotions block the answer


class EngineBPhase(Enum):
    """Engine B 会话阶段"""
    INITIAL = "initial"  # 问题已提交，等待 B1 诊断
    B1_DIAGNOSIS = "b1_diagnosis"  # 追问中
    B2_INFO_FILL = "b2_info_fill"  # 信息补全中
    B3_COGNITIVE_UNLOCK = "b3_cognitive_unlock"  # 认知框架补全中
    B4_EXPERIENCE_SIM = "b4_experience_sim"  # 经验参照生成中
    B5_EMOTIONAL_MIRROR = "b5_emotional_mirror"  # 情绪镜像分析中
    B5_5_ALTERNATIVE = "b5_5_alternative"  # 第三条路生成中
    C1_REEVALUATION = "c1_reevaluation"  # 重新评估中
    A_RECHECK = "a_recheck"  # 回送 Engine A 二次检测中
    B6_SIM_PARAMS = "b6_sim_params"  # 模拟器参数收集中
    B7_SIM_TIMELINES = "b7_sim_timelines"  # 时间线生成中
    B8_SIM_COPING = "b8_sim_coping"  # 应对预案生成中
    B9_SIM_COMPARISON = "b9_sim_comparison"  # 对比总览生成中
    SIMULATOR_COMPLETE = "simulator_complete"  # 模拟器完成
    COMPLETED = "completed"  # 完成
    ABANDONED = "abandoned"  # 已放弃


@dataclass
class DiagnosisQuestion:
    """B1 阶段的一个追问"""
    id: str
    question_text: str
    options: list[str] = field(default_factory=list)  # 选择题选项
    user_answer: Optional[str] = None
    answered_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosisQuestion":
        return cls(**data)


@dataclass
class EngineBSession:
    """Engine B 完整会话状态"""
    session_id: str
    original_question: str
    tier: str = "deep"
    phase: EngineBPhase = EngineBPhase.INITIAL

    # B1 - 诊断
    diagnosis_questions: list[DiagnosisQuestion] = field(default_factory=list)
    diagnosis_answers: dict[str, str] = field(default_factory=dict)  # q_id -> answer
    diagnosed_blockages: list[str] = field(default_factory=list)  # BlockageType.value 列表

    # B2 - 信息补全
    missing_info_items: list[dict] = field(default_factory=list)
    cognitive_frames: list[dict] = field(default_factory=list)
    experience_cases: list[dict] = field(default_factory=list)
    emotional_insight: dict = field(default_factory=dict)
    value_profile: dict = field(default_factory=dict)
    decision_biases: list[dict] = field(default_factory=list)
    bias_reminder: str = ""
    alternative_path: dict = field(default_factory=dict)
    external_signals: list[dict] = field(default_factory=list)

    # C1 - 重新评估
    original_pro_total: int = 50
    original_con_total: int = 50
    updated_pro_total: int = 0
    updated_con_total: int = 0
    recommendation: str = ""
    action_plan: str = ""
    reasoning: str = ""

    # A ↔ B 闭环
    source_detection: dict = field(default_factory=dict)
    recheck: dict = field(default_factory=dict)

    # 选择模拟器 - B6-B9
    simulator_output: Optional[dict] = None  # SimulatorOutput
    sim_questions: list[dict] = field(default_factory=list)  # B6 模拟参数收集的追问
    sim_answers: dict[str, str] = field(default_factory=dict)  # B6 回答

    # 元数据
    created_at: str = ""
    updated_at: str = ""
    token_used: int = 0
    last_error: str = ""
    processing_trace: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "original_question": self.original_question,
            "tier": self.tier,
            "phase": self.phase.value,
            "diagnosis_questions": [q.to_dict() for q in self.diagnosis_questions],
            "diagnosis_answers": self.diagnosis_answers,
            "diagnosed_blockages": self.diagnosed_blockages,
            "missing_info_items": self.missing_info_items,
            "cognitive_frames": self.cognitive_frames,
            "experience_cases": self.experience_cases,
            "emotional_insight": self.emotional_insight,
            "value_profile": self.value_profile,
            "decision_biases": self.decision_biases,
            "bias_reminder": self.bias_reminder,
            "alternative_path": self.alternative_path,
            "external_signals": self.external_signals,
            "original_pro_total": self.original_pro_total,
            "original_con_total": self.original_con_total,
            "updated_pro_total": self.updated_pro_total,
            "updated_con_total": self.updated_con_total,
            "recommendation": self.recommendation,
            "action_plan": self.action_plan,
            "reasoning": self.reasoning,
            "source_detection": self.source_detection,
            "recheck": self.recheck,
            "simulator_output": self.simulator_output,
            "sim_questions": self.sim_questions,
            "sim_answers": self.sim_answers,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "token_used": self.token_used,
            "last_error": self.last_error,
            "processing_trace": self.processing_trace,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EngineBSession":
        phase = EngineBPhase(data.get("phase", "initial"))
        questions = [DiagnosisQuestion.from_dict(q) for q in data.get("diagnosis_questions", [])]
        return cls(
            session_id=data["session_id"],
            original_question=data["original_question"],
            tier=data.get("tier", "deep"),
            phase=phase,
            diagnosis_questions=questions,
            diagnosis_answers=data.get("diagnosis_answers", {}),
            diagnosed_blockages=data.get("diagnosed_blockages", []),
            missing_info_items=data.get("missing_info_items", []),
            cognitive_frames=data.get("cognitive_frames", []),
            experience_cases=data.get("experience_cases", []),
            emotional_insight=data.get("emotional_insight", {}),
            value_profile=data.get("value_profile", {}),
            decision_biases=data.get("decision_biases", []),
            bias_reminder=data.get("bias_reminder", ""),
            alternative_path=data.get("alternative_path", {}),
            external_signals=data.get("external_signals", []),
            original_pro_total=data.get("original_pro_total", 50),
            original_con_total=data.get("original_con_total", 50),
            updated_pro_total=data.get("updated_pro_total", 0),
            updated_con_total=data.get("updated_con_total", 0),
            recommendation=data.get("recommendation", ""),
            action_plan=data.get("action_plan", ""),
            reasoning=data.get("reasoning", ""),
            source_detection=data.get("source_detection", {}),
            recheck=data.get("recheck", {}),
            simulator_output=data.get("simulator_output"),
            sim_questions=data.get("sim_questions", []),
            sim_answers=data.get("sim_answers", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            token_used=data.get("token_used", 0),
            last_error=data.get("last_error", ""),
            processing_trace=data.get("processing_trace", []),
        )

    @classmethod
    def create_new(cls, question: str, created_at: str, *, tier: str = "deep") -> "EngineBSession":
        return cls(
            session_id=uuid.uuid4().hex[:8],
            original_question=question,
            tier=tier,
            phase=EngineBPhase.INITIAL,
            created_at=created_at,
            updated_at=created_at,
        )


# ============================================================
# 选择模拟器数据结构
# ============================================================

@dataclass
class TimelineNode:
    """时间线上的一个节点"""
    time: str                    # "第1周" / "第3个月" / "1年后"
    external_state: str           # 外部客观变化
    inner_feeling: str           # 内心感受（要真实具体）
    key_action: str              # 在这个节点该做什么
    signal: str                  # 什么迹象说明你在这条线上

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TimelineNode":
        return cls(**data)


@dataclass
class Timeline:
    """一条完整的时间线"""
    scenario_type: str          # "tailwind" / "steady" / "headwind"
    title: str                   # "顺风局：比预期更顺利"
    probability: int            # 25-55
    probability_reason: str       # 为什么给这个概率
    nodes: list[dict] = field(default_factory=list)  # TimelineNode list

    def to_dict(self) -> dict:
        return {
            "scenario_type": self.scenario_type,
            "title": self.title,
            "probability": self.probability,
            "probability_reason": self.probability_reason,
            "nodes": [n.to_dict() if isinstance(n, TimelineNode) else n for n in self.nodes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Timeline":
        nodes = [TimelineNode.from_dict(n) if isinstance(n, dict) else n for n in data.get("nodes", [])]
        return cls(
            scenario_type=data["scenario_type"],
            title=data["title"],
            probability=data["probability"],
            probability_reason=data["probability_reason"],
            nodes=nodes,
        )


@dataclass
class Crossroad:
    """未来的一个关键岔路口"""
    id: int
    time: str                   # "入职第3个月"
    description: str
    green_signal: str           # 顺风信号
    green_action: str
    yellow_signal: str          # 平稳信号
    yellow_action: str
    red_signal: str            # 逆风信号
    red_action: str
    reversal_cost: str         # 此时回头的代价

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Crossroad":
        return cls(**data)


@dataclass
class SurvivalPlan:
    """最坏情况生存方案"""
    trigger: str                # 什么情况触发
    day_1: str
    week_1: str
    month_1: str
    safety_runway: str          # 安全垫能撑多久
    emotional_note: str         # 情绪上的预期和建议

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SurvivalPlan":
        return cls(**data)


@dataclass
class MilestoneCheck:
    """里程碑检查点"""
    time: str                   # "1个月" / "3个月"
    check_content: str          # 检查什么

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MilestoneCheck":
        return cls(**data)


@dataclass
class ChoiceSimulation:
    """单个选项的完整模拟"""
    choice_name: str           # "A-跳槽到目标公司"
    timelines: list[dict] = field(default_factory=list)  # Timeline list
    crossroads: list[dict] = field(default_factory=list)  # Crossroad list
    survival_plan: Optional[dict] = None  # SurvivalPlan
    milestones: list[dict] = field(default_factory=list)  # MilestoneCheck list

    def to_dict(self) -> dict:
        return {
            "choice_name": self.choice_name,
            "timelines": [t.to_dict() if isinstance(t, Timeline) else t for t in self.timelines],
            "crossroads": [c.to_dict() if isinstance(c, Crossroad) else c for c in self.crossroads],
            "survival_plan": self.survival_plan.to_dict() if isinstance(self.survival_plan, SurvivalPlan) else self.survival_plan,
            "milestones": [m.to_dict() if isinstance(m, MilestoneCheck) else m for m in self.milestones],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChoiceSimulation":
        timelines = [Timeline.from_dict(t) if isinstance(t, dict) else t for t in data.get("timelines", [])]
        crossroads = [Crossroad.from_dict(c) if isinstance(c, dict) else c for c in data.get("crossroads", [])]
        survival_plan = SurvivalPlan.from_dict(data["survival_plan"]) if data.get("survival_plan") else None
        milestones = [MilestoneCheck.from_dict(m) if isinstance(m, dict) else m for m in data.get("milestones", [])]
        return cls(
            choice_name=data["choice_name"],
            timelines=timelines,
            crossroads=crossroads,
            survival_plan=survival_plan,
            milestones=milestones,
        )


@dataclass
class UserSimParams:
    """用户的模拟参数"""
    savings_months: int         # 存款能撑几个月
    other_income: str
    fixed_expenses: str          # 硬性支出
    time_to_reverse: str        # 回头需要多久
    reversal_cost: str           # 回头的代价
    point_of_no_return: str      # 不可逆节点
    worst_fear: str             # 最怕什么

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserSimParams":
        return cls(**data)


@dataclass
class SimulatorOutput:
    """选择模拟器完整输出"""
    user_params: dict = None     # UserSimParams
    choice_a: Optional[dict] = None  # ChoiceSimulation
    choice_b: Optional[dict] = None  # ChoiceSimulation
    comparison_summary: str = ""   # 对比总览文本
    action_map_a: list[str] = field(default_factory=list)  # 选A的行动地图
    action_map_b: list[str] = field(default_factory=list)  # 选B的行动地图
    final_insight: str = ""      # 最后一句个性化总结

    def to_dict(self) -> dict:
        return {
            "user_params": self.user_params.to_dict() if isinstance(self.user_params, UserSimParams) else self.user_params,
            "choice_a": self.choice_a.to_dict() if isinstance(self.choice_a, ChoiceSimulation) else self.choice_a,
            "choice_b": self.choice_b.to_dict() if isinstance(self.choice_b, ChoiceSimulation) else self.choice_b,
            "comparison_summary": self.comparison_summary,
            "action_map_a": self.action_map_a,
            "action_map_b": self.action_map_b,
            "final_insight": self.final_insight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SimulatorOutput":
        user_params = UserSimParams.from_dict(data["user_params"]) if data.get("user_params") else None
        choice_a = ChoiceSimulation.from_dict(data["choice_a"]) if data.get("choice_a") else None
        choice_b = ChoiceSimulation.from_dict(data["choice_b"]) if data.get("choice_b") else None
        return cls(
            user_params=user_params,
            choice_a=choice_a,
            choice_b=choice_b,
            comparison_summary=data.get("comparison_summary", ""),
            action_map_a=data.get("action_map_a", []),
            action_map_b=data.get("action_map_b", []),
            final_insight=data.get("final_insight", ""),
        )
