"""认知拉格朗日点 · 数据模型"""

from dataclasses import dataclass, field
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


@dataclass
class CandidateQuestion:
    id: str                 # e.g. "CQ-A-003"
    question_text: str
    miner_source: str
    balance_rationale: str
    initial_score: int      # 0-100

    # Filter results
    passed_filter_2: Optional[bool] = None
    filter_2_balance_score: float = 0.0
    filter_2_distribution: str = ""
    filter_2_details: list = field(default_factory=list)


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

    # Metadata
    fault_lines: list[str] = field(default_factory=list)
    tunnel_connections: list[str] = field(default_factory=list)
