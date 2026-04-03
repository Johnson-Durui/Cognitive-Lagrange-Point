"""认知拉格朗日点 · 阶段一：矿工Agent"""

from .api import call_agent_json
from .models import CandidateQuestion

MINER_SYSTEM = """你是一个"认知拉格朗日点矿工"，专门在{dimension}中寻找"不可回答的问题"。

你要寻找的不是"难题"，而是具有以下结构的问题：
- 支持正方的论证和支持反方的论证在力量上恰好平衡
- 不是因为信息不足才无法回答，而是结构性的平衡
- 换任何一种思考框架都无法打破僵局

请生成20个候选问题。

对每个问题：
1. 用2-3句话描述问题
2. 简述为什么你认为正反力量可能平衡
3. 给出你的"拉格朗日点概率"评分（0-100）

要求：
- 不要用经典的哲学老题（电车难题、忒修斯之船等）
- 优先选择与当代现实相关的问题
- 问题必须是实质性的（不是文字游戏或逻辑悖论）

请以JSON格式输出，格式如下：
[
  {{
    "question_text": "问题描述",
    "balance_rationale": "为什么正反力量可能平衡",
    "initial_score": 85
  }},
  ...
]

只输出JSON数组，不要输出其他内容。"""

MINER_DIMENSIONS = {
    "A": (
        "伦理-现实交界面",
        "在哪些情况下，道德上绝对正确的做法会导致现实中确定性的灾难？"
        "而道德上有瑕疵的做法反而是唯一能避免灾难的路？"
    ),
    "B": (
        "自由-安全交界面",
        "在哪些情况下，保护一个人的自由恰好等于伤害另一个人的安全？"
        "且这种等价关系是精确的，不是近似的？"
    ),
    "C": (
        "个体-集体交界面",
        "在哪些情况下，个体最优选择的总和恰好等于集体最差结果？"
        "且没有任何协调机制可以打破这个陷阱？"
    ),
    "D": (
        "短期-长期交界面",
        "在哪些情况下，短期和长期利益不仅矛盾，"
        "而且矛盾的程度恰好精确对称？"
    ),
    "E": (
        "认知-元认知交界面",
        "有没有这样的问题——思考它本身会改变它的答案？"
        "不思考它反而能维持某种稳定？"
        "但你无法选择不思考因为你已经知道了它的存在？"
    ),
    "F": (
        "存在性交界面",
        "有没有关于意识、自我、意义的问题，"
        "其结构使得任何答案都自我否定？"
        "即：如果答案为是则蕴含否，如果答案为否则蕴含是。"
        "但又不是简单的逻辑悖论——而是关于真实世界的实质性问题？"
    ),
}


def run_miner(miner_id: str = "A") -> list[CandidateQuestion]:
    """运行单个矿工Agent，返回候选问题列表。

    MVP模式只运行矿工A（伦理-现实交界面）。
    """
    dim_name, dim_desc = MINER_DIMENSIONS[miner_id]
    system = MINER_SYSTEM.format(dimension=f"{dim_name}——{dim_desc}")

    print(f"  ⛏  矿工{miner_id}正在 [{dim_name}] 中搜索候选问题...")

    raw = call_agent_json(system, "请开始搜索。", max_tokens=8192)

    candidates = []
    for i, item in enumerate(raw):
        cq = CandidateQuestion(
            id=f"CQ-{miner_id}-{i+1:03d}",
            question_text=item["question_text"],
            miner_source=f"矿工{miner_id}-{dim_name}",
            balance_rationale=item["balance_rationale"],
            initial_score=item["initial_score"],
        )
        candidates.append(cq)

    print(f"  ✓  矿工{miner_id}产出 {len(candidates)} 个候选问题")
    return candidates
