"""认知拉格朗日点 · 数据模型"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class OscillationType(Enum):
    DAMPED = "衰减振荡-收敛型"
    SUSTAINED = "等幅振荡-最纯粹型"
    DIVERGENT = "发散振荡-危险型"
    CHAOTIC = "混沌振荡-不可预测型"


class StabilityType(Enum):
    STABLE = "稳定-扰动后回归"
    NEUTRAL = "中性-保持扰动后状态"
    UNSTABLE = "不稳定-扰动后远离"


@dataclass
class Force:
    name: str
    direction: str          # "正方" or "反方"
    source: str
    strength: int           # 0-100
    best_argument: str
    known_weakness: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Force":
        return cls(**data)


@dataclass
class OscillationData:
    round_number: int
    lean_direction: str
    lean_strength: int
    new_angle_explored: str
    feels_circular: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OscillationData":
        return cls(**data)


@dataclass
class FaultLine:
    name: str
    description: str
    points_on_line: list[str] = field(default_factory=list)
    intersections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FaultLine":
        return cls(**data)


@dataclass
class CandidateQuestion:
    id: str                 # e.g. "CQ-A-003"
    question_text: str
    miner_source: str
    balance_rationale: str
    initial_score: int      # 0-100
    selected_for_pipeline: bool = False

    # Filter results
    passed_filter_1: Optional[bool] = None
    filter_1_summary: str = ""
    filter_1_details: list = field(default_factory=list)
    passed_filter_2: Optional[bool] = None
    filter_2_balance_score: float = 0.0
    filter_2_distribution: str = ""
    filter_2_details: list = field(default_factory=list)
    passed_filter_3: Optional[bool] = None
    filter_3_stable_count: int = 0
    filter_3_summary: str = ""
    filter_3_classification: str = ""
    filter_3_details: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CandidateQuestion":
        return cls(**data)


@dataclass
class ConfirmedLagrangePoint:
    id: str                 # e.g. "CLP-001"
    question_text: str
    source_candidate: str

    # Force anatomy
    pro_forces: list[Force] = field(default_factory=list)
    con_forces: list[Force] = field(default_factory=list)
    pro_total: float = 0.0
    con_total: float = 0.0
    balance_precision: float = 0.0
    hidden_forces: list[dict] = field(default_factory=list)
    balance_analysis: str = ""
    stability_type: Optional[StabilityType] = None
    perturbation_responses: list[dict] = field(default_factory=list)
    stability_runs: list[dict] = field(default_factory=list)
    stability_summary: str = ""
    oscillation_type: Optional[OscillationType] = None
    oscillation_data: list[OscillationData] = field(default_factory=list)
    oscillation_period: Optional[float] = None
    oscillation_summaries: list[dict] = field(default_factory=list)
    oscillation_summary: str = ""

    # Metadata
    fault_lines: list[str] = field(default_factory=list)
    tunnel_connections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["pro_forces"] = [force.to_dict() for force in self.pro_forces]
        data["con_forces"] = [force.to_dict() for force in self.con_forces]
        data["stability_type"] = self.stability_type.value if self.stability_type else None
        data["oscillation_type"] = self.oscillation_type.value if self.oscillation_type else None
        data["oscillation_data"] = [item.to_dict() for item in self.oscillation_data]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ConfirmedLagrangePoint":
        payload = dict(data)
        payload["pro_forces"] = [Force.from_dict(force) for force in payload.get("pro_forces", [])]
        payload["con_forces"] = [Force.from_dict(force) for force in payload.get("con_forces", [])]
        stability_value = payload.get("stability_type")
        oscillation_value = payload.get("oscillation_type")
        payload["stability_type"] = StabilityType(stability_value) if stability_value else None
        payload["oscillation_type"] = OscillationType(oscillation_value) if oscillation_value else None
        payload["oscillation_data"] = [
            OscillationData.from_dict(item)
            for item in payload.get("oscillation_data", [])
        ]
        return cls(**payload)
