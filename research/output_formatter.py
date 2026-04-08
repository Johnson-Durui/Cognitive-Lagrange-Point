"""认知拉格朗日点 · 输出格式化"""

import json
import os
import re
import shutil
import math
import hashlib
from html import escape as html_escape
from difflib import SequenceMatcher
from datetime import datetime
from .models import ConfirmedLagrangePoint, CandidateQuestion, FaultLine

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DISCOVERED_DATA_JS = os.path.join(PROJECT_ROOT, "discovered-data.js")


def _archive_dir() -> str | None:
    value = os.environ.get("CLP_ARCHIVE_DIR", "").strip()
    return value or None


def _write_json_targets(filename: str, payload: dict) -> str:
    targets = [os.path.join(OUTPUT_DIR, filename)]
    archive_root = _archive_dir()
    if archive_root:
        archive_path = os.path.join(archive_root, filename)
        if os.path.abspath(archive_path) != os.path.abspath(targets[0]):
            targets.append(archive_path)

    for path in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    return targets[0]


def _write_text_targets(filename: str, content: str) -> str:
    targets = [os.path.join(OUTPUT_DIR, filename)]
    archive_root = _archive_dir()
    if archive_root:
        archive_path = os.path.join(archive_root, filename)
        if os.path.abspath(archive_path) != os.path.abspath(targets[0]):
            targets.append(archive_path)

    for path in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    return targets[0]


def _copy_to_archive(path: str) -> None:
    archive_root = _archive_dir()
    if not archive_root or not os.path.exists(path):
        return
    archive_path = os.path.join(archive_root, os.path.basename(path))
    if os.path.abspath(archive_path) == os.path.abspath(path):
        return
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    shutil.copy2(path, archive_path)


def generate_pdf(
    confirmed: list[ConfirmedLagrangePoint],
    fault_lines: list[FaultLine] | None = None,
    tunnel_effects: list[dict] | None = None,
    social_conflict_predictions: list[dict] | None = None,
    metadata: dict | None = None,
):
    """生成美观的 PDF 研究报告。"""
    try:
        from fpdf import FPDF
    except ImportError:
        print("  ⚠ fpdf2 未安装，无法生成 PDF。请运行: pip install fpdf2")
        return

    fault_lines = fault_lines or []
    tunnel_effects = tunnel_effects or []
    social_conflict_predictions = social_conflict_predictions or []
    metadata = metadata or {}

    CN_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

    class PDF(FPDF):
        def header(self):
            if self.page_no() == 1:
                return
            self.set_font("STHeiti", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "认知拉格朗日点 · 研究报告", align="R")
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("STHeiti", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"第 {self.page_no()} 页", align="C")

        def chapter_title(self, title: str):
            self.set_font("STHeiti", "B", 14)
            self.set_text_color(60, 60, 80)
            self.cell(0, 10, title, ln=True)
            self.ln(2)

        def section_title(self, title: str):
            self.set_font("STHeiti", "B", 11)
            self.set_text_color(80, 80, 100)
            self.cell(0, 8, title, ln=True)
            self.ln(1)

        def body_text(self, text: str, indent: int = 0):
            self.set_font("STHeiti", "", 10)
            self.set_text_color(50, 50, 60)
            self.set_x(self.l_margin + indent)
            self.multi_cell(0, 6, text)
            self.ln(2)

        def clp_card(self, clp: ConfirmedLagrangePoint):
            # 顶部色条
            self.set_fill_color(255, 107, 107)
            self.rect(self.l_margin, self.get_y(), 190, 1, "F")

            self.ln(4)
            self.set_font("STHeiti", "B", 13)
            self.set_text_color(40, 40, 55)
            self.cell(0, 8, f"CLP #{clp.id}", ln=True)

            self.set_font("STHeiti", "", 10)
            self.set_text_color(100, 100, 120)
            self.multi_cell(0, 6, clp.question_text)
            self.ln(3)

            # 张力标签
            if clp.pro_forces and clp.con_forces:
                pro_name = clp.pro_forces[0].name
                con_name = clp.con_forces[0].name
                self.set_font("STHeiti", "B", 9)
                self.set_text_color(180, 80, 80)
                self.cell(80, 7, f"  正方: {pro_name}", ln=True)
                self.set_text_color(80, 80, 180)
                self.cell(0, 7, f"  反方: {con_name}", ln=True)

            self.set_text_color(60, 60, 75)
            self.set_font("STHeiti", "", 10)
            self.cell(0, 7, f"  平衡精度: {clp.balance_precision}%", ln=True)

            if clp.stability_type is not None:
                self.cell(0, 6, f"  稳定性: {clp.stability_type.value}", ln=True)
            if clp.oscillation_type is not None:
                self.cell(0, 6, f"  振荡: {clp.oscillation_type.value}", ln=True)
            if clp.fault_lines:
                self.cell(0, 6, f"  断层线: {'、'.join(clp.fault_lines)}", ln=True)
            if clp.tunnel_connections:
                self.cell(0, 6, f"  隧道连接: {'、'.join(clp.tunnel_connections)}", ln=True)

            # 力量详解
            if clp.pro_forces:
                self.ln(3)
                self.set_font("STHeiti", "B", 10)
                self.set_text_color(180, 80, 80)
                self.cell(0, 6, "  正方力量", ln=True)
                for f in clp.pro_forces:
                    self.set_font("STHeiti", "B", 9)
                    self.set_text_color(160, 80, 80)
                    self.set_x(self.l_margin + 5)
                    self.cell(0, 5, f"[{f.name}] 强度: {f.strength}%", ln=True)
                    self.set_font("STHeiti", "", 9)
                    self.set_text_color(60, 60, 70)
                    self.set_x(self.l_margin + 8)
                    self.multi_cell(0, 5, f"论证: {f.best_argument}")
                    self.set_x(self.l_margin + 8)
                    self.set_text_color(130, 130, 140)
                    self.multi_cell(0, 5, f"弱点: {f.known_weakness}")

            if clp.con_forces:
                self.ln(2)
                self.set_font("STHeiti", "B", 10)
                self.set_text_color(80, 80, 180)
                self.cell(0, 6, "  反方力量", ln=True)
                for f in clp.con_forces:
                    self.set_font("STHeiti", "B", 9)
                    self.set_text_color(80, 80, 160)
                    self.set_x(self.l_margin + 5)
                    self.cell(0, 5, f"[{f.name}] 强度: {f.strength}%", ln=True)
                    self.set_font("STHeiti", "", 9)
                    self.set_text_color(60, 60, 70)
                    self.set_x(self.l_margin + 8)
                    self.multi_cell(0, 5, f"论证: {f.best_argument}")
                    self.set_x(self.l_margin + 8)
                    self.set_text_color(130, 130, 140)
                    self.multi_cell(0, 5, f"弱点: {f.known_weakness}")

            self.ln(5)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=25)

    # 注册中文字体
    _heiti = "/System/Library/Fonts/STHeiti Medium.ttc"
    pdf.add_font("STHeiti", "", _heiti)
    pdf.add_font("STHeiti", "B", _heiti)
    pdf.add_font("STHeiti", "I", _heiti)

    # ── 封面 ──
    pdf.add_page()
    pdf.set_fill_color(8, 14, 24)
    pdf.rect(0, 0, 210, 297, "F")

    # 标题
    pdf.set_font("STHeiti", "B", 28)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(70)
    pdf.cell(0, 15, "认知拉格朗日点", align="C", ln=True)
    pdf.set_font("STHeiti", "", 14)
    pdf.set_text_color(180, 180, 200)
    pdf.cell(0, 10, "Cognitive Lagrange Points", align="C", ln=True)
    pdf.ln(8)
    pdf.set_font("STHeiti", "I", 11)
    pdf.set_text_color(130, 130, 150)
    pdf.cell(0, 8, "寻找人类思维的永恒僵局", align="C", ln=True)

    pdf.ln(30)
    pdf.set_font("STHeiti", "", 10)
    pdf.set_text_color(120, 120, 140)
    pdf.cell(0, 7, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C", ln=True)
    pdf.cell(0, 7, f"确认拉格朗日点: {len(confirmed)} 个", align="C", ln=True)
    model = metadata.get("model", "deepseek-v3")
    pdf.cell(0, 7, f"模型: {model}", align="C", ln=True)

    pdf.ln(50)
    pdf.set_font("STHeiti", "", 9)
    pdf.set_text_color(80, 80, 100)
    pdf.cell(0, 6, "本报告由认知拉格朗日点研究系统自动生成", align="C", ln=True)

    # ── 内容页 ──
    if confirmed:
        pdf.add_page()
        pdf.chapter_title("一、确认的认知拉格朗日点")
        pdf.ln(2)
        for clp in confirmed:
            pdf.clp_card(clp)
            if pdf.get_y() > 250:
                pdf.add_page()

    if fault_lines:
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.ln(5)
        pdf.chapter_title("二、断层线列表")
        for line in fault_lines:
            pdf.section_title(f"[{line.name}]")
            pdf.body_text(line.description, indent=5)
            if line.points_on_line:
                pdf.body_text(f"点位: {', '.join(line.points_on_line)}", indent=8)
            if line.intersections:
                pdf.body_text(f"交叉: {', '.join(line.intersections)}", indent=8)
            pdf.ln(3)

    if tunnel_effects:
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.ln(5)
        pdf.chapter_title("三、隧道效应网络")
        for item in tunnel_effects:
            pdf.set_font("STHeiti", "B", 10)
            pdf.set_text_color(60, 60, 80)
            pdf.cell(0, 7, f"  {item['from_point']} → {item['to_point']} (强度: {item['strength']})", ln=True)
            if item.get("rationale"):
                pdf.body_text(item["rationale"], indent=8)
            pdf.ln(2)

    if social_conflict_predictions:
        if pdf.get_y() > 200:
            pdf.add_page()
        pdf.ln(5)
        pdf.chapter_title("四、社会冲突预测")
        for item in social_conflict_predictions:
            pdf.section_title(f"[{item.get('title', '未命名')}]")
            if item.get("related_fault_lines"):
                pdf.body_text(f"相关断层线: {', '.join(item['related_fault_lines'])}", indent=5)
            if item.get("related_points"):
                pdf.body_text(f"相关点位: {', '.join(item['related_points'])}", indent=5)
            if item.get("activation_signal"):
                pdf.body_text(f"触发信号: {item['activation_signal']}", indent=5)
            pdf.body_text(f"预测: {item.get('prediction', '')}", indent=5)
            pdf.ln(3)

    # 保存
    pdf_path = os.path.join(OUTPUT_DIR, "report.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    pdf.output(pdf_path)
    _copy_to_archive(pdf_path)
    print(f"  📕 PDF报告已保存: {pdf_path}")


def _decision_report_text(value, default: str = "未提供") -> str:
    if value is None:
        return default
    text = str(value).strip()
    replacements = {
        "local_fast": "本地极速补齐",
        "如果未说明仍压得紧": "如果现实压力仍然偏紧",
        "未识别明确不可逆节点": "暂无明确不可逆节点",
    }
    for src, target in replacements.items():
        text = text.replace(src, target)
    return text or default


def _decision_report_is_placeholder(value) -> bool:
    text = _decision_report_text(value, default="").strip()
    if not text:
        return True
    placeholder_values = {
        "未说明",
        "未提供",
        "未明确说明",
        "未知",
        "暂无明确不可逆节点",
        "未提供问题",
    }
    if text in placeholder_values:
        return True
    return any(token in text for token in ("未说明", "未提供", "未明确说明"))


def _decision_report_compact_appendix(items, *, head: int = 6, tail: int = 6) -> tuple[list, list, int]:
    seq = list(items or [])
    if len(seq) <= head + tail:
        return seq, [], 0
    return seq[:head], seq[-tail:], len(seq) - head - tail


def _decision_report_int(value, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _decision_report_choice_snapshot(choice: dict | None) -> dict:
    choice = choice if isinstance(choice, dict) else {}
    distribution = choice.get("probability_distribution") if isinstance(choice.get("probability_distribution"), dict) else {}
    return {
        "name": _decision_report_text(choice.get("choice_name"), default="未命名选项"),
        "tailwind": _decision_report_int((distribution.get("tailwind") or {}).get("percent"), 0),
        "steady": _decision_report_int((distribution.get("steady") or {}).get("percent"), 0),
        "headwind": _decision_report_int((distribution.get("headwind") or {}).get("percent"), 0),
    }


def _decision_report_pick_safer_choice(simulator_output: dict) -> tuple[str, str]:
    left = _decision_report_choice_snapshot(simulator_output.get("choice_a"))
    right = _decision_report_choice_snapshot(simulator_output.get("choice_b"))

    def _score(snapshot: dict) -> float:
        return snapshot["tailwind"] * 1.15 + snapshot["steady"] * 0.35 - snapshot["headwind"] * 1.2

    left_score = _score(left)
    right_score = _score(right)
    if left_score == right_score:
        return "两条路当前承受力接近", "顺风与逆风分布接近，建议重点看你更能承受哪一边的坏结果。"
    winner = left if left_score > right_score else right
    loser = right if winner is left else left
    return (
        winner["name"],
        f"{winner['name']} 的逆风占比更低或顺风占比更高，当前比 {loser['name']} 更稳。",
    )


def _decision_report_similarity_note(simulator_output: dict) -> str:
    choice_a = simulator_output.get("choice_a") if isinstance(simulator_output.get("choice_a"), dict) else {}
    choice_b = simulator_output.get("choice_b") if isinstance(simulator_output.get("choice_b"), dict) else {}
    action_map_a = _decision_report_lines(simulator_output.get("action_map_a") or [])
    action_map_b = _decision_report_lines(simulator_output.get("action_map_b") or [])

    def _flatten_choice(choice: dict) -> str:
        texts = []
        distribution = choice.get("probability_distribution") if isinstance(choice.get("probability_distribution"), dict) else {}
        for scenario in ("tailwind", "steady", "headwind"):
            bucket = distribution.get(scenario) if isinstance(distribution.get(scenario), dict) else {}
            texts.append(_decision_report_text(bucket.get("reason"), default=""))
            timeline = (choice.get("timelines") or {}).get(scenario) if isinstance(choice.get("timelines"), dict) else {}
            nodes = timeline.get("nodes") if isinstance(timeline, dict) else []
            for node in nodes[:6]:
                if not isinstance(node, dict):
                    continue
                texts.extend([
                    _decision_report_text(node.get("external_state"), default=""),
                    _decision_report_text(node.get("inner_feeling"), default=""),
                    _decision_report_text(node.get("key_action"), default=""),
                    _decision_report_text(node.get("signal"), default=""),
                ])
        return re.sub(r"\s+", "", " ".join(texts))

    a_text = _flatten_choice(choice_a)
    b_text = _flatten_choice(choice_b)
    if not a_text or not b_text:
        return ""
    similarity = SequenceMatcher(None, a_text, b_text).ratio()
    if action_map_a and action_map_b and action_map_a == action_map_b:
        return "本轮两条路的行动地图高度相似，说明你现在更需要补关键变量，而不是提前把自己锁死在某一个答案上。"
    if similarity >= 0.78:
        return "本轮两条路的未来文案相似度偏高，建议把固定支出、回头代价等关键参数补齐后，再重新生成第三幕。"
    return ""


def _decision_report_sim_param_rows(user_params: dict) -> tuple[list[tuple[str, str]], list[str]]:
    rows: list[tuple[str, str]] = []
    pending: list[str] = []

    def _append(label: str, value, *, formatter=None):
        if _decision_report_is_placeholder(value):
            pending.append(label)
            return
        text = formatter(value) if formatter else _decision_report_text(value)
        rows.append((label, text))

    if "savings_months" in user_params and user_params.get("savings_months") not in (None, ""):
        rows.append(("安全垫", f"{_decision_report_text(user_params.get('savings_months'), default='--')} 个月"))
    else:
        pending.append("安全垫")
    _append("其他收入", user_params.get("other_income"))
    _append("固定支出", user_params.get("fixed_expenses"))
    _append("回头时间", user_params.get("time_to_reverse"))
    _append("回头代价", user_params.get("reversal_cost"))
    _append("不可逆节点", user_params.get("point_of_no_return"))
    _append("最怕的情况", user_params.get("worst_fear"))
    return rows, pending


def _decision_report_palette(scenario: str) -> dict:
    palettes = {
        "tailwind": {
            "accent": (74, 153, 119),
            "fill": (237, 246, 241),
            "soft": (201, 230, 214),
            "line": (74, 153, 119),
        },
        "steady": {
            "accent": (214, 180, 106),
            "fill": (250, 246, 234),
            "soft": (239, 226, 184),
            "line": (184, 142, 82),
        },
        "headwind": {
            "accent": (194, 112, 104),
            "fill": (252, 240, 238),
            "soft": (238, 207, 202),
            "line": (194, 112, 104),
        },
    }
    return palettes.get(scenario, {
        "accent": (90, 132, 198),
        "fill": (241, 245, 251),
        "soft": (210, 224, 242),
        "line": (90, 132, 198),
    })


def _decision_report_seeded_unit(seed_text: str, slot: str) -> float:
    digest = hashlib.sha256(f"{seed_text}:{slot}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _decision_report_radar_metrics(simulator_output: dict) -> list[dict]:
    choice_a = _decision_report_choice_snapshot(simulator_output.get("choice_a"))
    choice_b = _decision_report_choice_snapshot(simulator_output.get("choice_b"))
    regret_a = max(0, 100 - _decision_report_int(simulator_output.get("regret_score_a"), 50))
    regret_b = max(0, 100 - _decision_report_int(simulator_output.get("regret_score_b"), 50))
    return [
        {"label": "顺风势能", "a": choice_a.get("tailwind", 0), "b": choice_b.get("tailwind", 0)},
        {"label": "平稳承接", "a": choice_a.get("steady", 0), "b": choice_b.get("steady", 0)},
        {"label": "抗逆风", "a": max(0, 100 - choice_a.get("headwind", 0)), "b": max(0, 100 - choice_b.get("headwind", 0))},
        {"label": "后悔可控", "a": regret_a, "b": regret_b},
    ]


def _decision_report_appendix_text(value, *, limit: int | None = None) -> str:
    text = _decision_report_text(value, default="").strip()
    if not text:
        return ""
    replacements = {
        "Engine B 已启动": "第二幕启动",
        "Engine A 初检": "第一幕初检",
        "接到 Engine A 初检结果": "接到第一幕初检结果",
        "直接交给 Engine B": "直接交给第二幕",
        "Engine A": "第一幕",
        "Engine B": "第二幕",
        "filter1_uncertain": "第一层筛选未稳定完成",
        "filter1": "第一层筛选",
        "filter2": "第二层筛选",
        "filter3": "第三层筛选",
        "极速模式": "本地补齐模式",
        "总览已切到本地补齐模式": "最终对比改为本地补齐",
        "预案已切到本地补齐模式": "预案改为本地补齐",
    }
    for src, target in replacements.items():
        text = text.replace(src, target)
    text = re.sub(r"^[^\u4e00-\u9fffA-Za-z0-9]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fffA-Za-z0-9])", "", text)
    text = re.sub(r"(?<=[A-Za-z0-9\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    if limit and len(text) > limit:
        return text[: max(limit - 1, 1)].rstrip("，。、；;,. ") + "…"
    return text


def _decision_report_trace_digest(trace: list[dict] | None) -> list[dict]:
    phase_labels = {
        "b1_diagnosis": "定位卡点",
        "b2_info_fill": "补齐关键事实",
        "b3_cognitive_unlock": "重建判断框架",
        "b4_experience_sim": "经验校准",
        "b5_emotional_mirror": "情绪镜像",
        "b5_5_alternative": "寻找第三条路",
        "c1_reevaluation": "重新评估",
        "a_recheck": "回到第一幕复核",
        "b6_sim_params": "补齐模拟基线",
        "b7_sim_timelines": "推演未来时间线",
        "b8_sim_coping": "编排风险预案",
        "b9_sim_comparison": "压缩成总览",
        "simulator_complete": "第三幕收束",
    }
    phase_notes = {
        "b1_diagnosis": "确认这次难题到底卡在事实、框架、经验还是情绪。",
        "b2_info_fill": "把最影响结果的现实变量补齐，避免继续空转。",
        "b3_cognitive_unlock": "换一组更能做判断的视角，而不是在原题里硬拉扯。",
        "b4_experience_sim": "用过来人案例校准直觉，避免纯靠想象下注。",
        "b5_emotional_mirror": "识别真正拉偏判断的情绪和保护机制。",
        "b5_5_alternative": "把原来的二选一，拆出更可逆的第三条路。",
        "c1_reevaluation": "把前面所有补齐过的材料重新压成建议。",
        "a_recheck": "当问题仍过于平衡时，重新回到第一幕做复核。",
        "b6_sim_params": "补齐安全垫、可逆性和最坏情况这些模拟基线。",
        "b7_sim_timelines": "把两条路分别推演到不同时间节点，而不是共享模板。",
        "b8_sim_coping": "把未来的不确定节点改写成可执行的信号与预案。",
        "b9_sim_comparison": "把所有推演压成一张可以比较、可以行动的总览。",
        "simulator_complete": "第三幕收束，报告开始回到最终结论。",
    }

    groups = []
    current = None
    for item in trace or []:
        if not isinstance(item, dict):
            continue
        phase = _decision_report_text(item.get("phase"), default="")
        line_title = _decision_report_appendix_text(item.get("title"), limit=26)
        line_detail = _decision_report_appendix_text(item.get("detail"), limit=54)
        if not line_title and not line_detail:
            continue
        line = line_title
        if line_detail and line_detail not in line_title:
            line = f"{line_title}：{line_detail}" if line_title else line_detail
        if current is None or current["phase"] != phase:
            current = {
                "phase": phase,
                "label": phase_labels.get(phase, _decision_report_phase_label(phase)),
                "note": phase_notes.get(phase, ""),
                "lines": [],
            }
            groups.append(current)
        if line and line not in current["lines"]:
            current["lines"].append(line)

    digested = []
    for group in groups[:8]:
        lines = group["lines"][:3]
        if not lines:
            continue
        digested.append({
            "title": group["label"],
            "meta": group["note"],
            "lines": lines,
        })
    return digested


def _decision_report_appendix_sections(
    *,
    detection_job: dict | None,
    detection_result: dict | None,
    detection_status: str,
    engineb_session: dict | None,
    simulator_output: dict | None,
    safer_choice_name: str,
    safer_choice_reason: str,
    simulator_warning: str,
) -> list[dict]:
    sections = []

    detection_job = detection_job if isinstance(detection_job, dict) else {}
    detection_result = detection_result if isinstance(detection_result, dict) else {}
    engineb_session = engineb_session if isinstance(engineb_session, dict) else {}
    simulator_output = simulator_output if isinstance(simulator_output, dict) else {}

    if detection_job:
        analysis = detection_job.get("analysis") if isinstance(detection_job.get("analysis"), dict) else {}
        lines = []
        if analysis.get("analysis_summary"):
            lines.append(_decision_report_appendix_text(analysis.get("analysis_summary"), limit=80))
        if analysis.get("balance_rationale"):
            lines.append(f"看似平衡的原因：{_decision_report_appendix_text(analysis.get('balance_rationale'), limit=72)}")
        if detection_result.get("summary"):
            lines.append(f"第一幕判定：{_decision_report_appendix_text(detection_result.get('summary'), limit=78)}")
        elif detection_status:
            lines.append(f"第一幕状态：{_decision_report_appendix_text(detection_status)}")
        if lines:
            sections.append({
                "title": "第一幕 · 结构判断如何收束",
                "meta": "系统先确认：这是真正的结构性平衡，还是一个可以靠补齐现实变量拆开的问题。",
                "body": "\n".join(lines[:3]),
                "accent": (90, 132, 198),
            })

    if engineb_session:
        lines = []
        blockages = _decision_report_lines(engineb_session.get("diagnosed_blockages") or [])
        if blockages:
            lines.append(f"主要卡点：{' / '.join(blockages)}")
        info_items = engineb_session.get("missing_info_items") if isinstance(engineb_session.get("missing_info_items"), list) else []
        if info_items:
            titles = "、".join(_decision_report_text(item.get("title"), default="") for item in info_items[:3] if isinstance(item, dict))
            if titles:
                lines.append(f"补齐的关键现实变量：{titles}")
        frames = engineb_session.get("cognitive_frames") if isinstance(engineb_session.get("cognitive_frames"), list) else []
        if frames:
            titles = "、".join(_decision_report_text(item.get("title"), default="") for item in frames[:3] if isinstance(item, dict))
            if titles:
                lines.append(f"新加入的判断框架：{titles}")
        if engineb_session.get("recommendation"):
            lines.append(f"第二幕建议：{_decision_report_appendix_text(engineb_session.get('recommendation'), limit=70)}")
        if engineb_session.get("action_plan"):
            lines.append(f"立即动作：{_decision_report_appendix_text(engineb_session.get('action_plan'), limit=56)}")
        if lines:
            sections.append({
                "title": "第二幕 · 建议是如何浮现的",
                "meta": "不是直接给答案，而是先补事实、补框架，再看力量是否真正拉开。",
                "body": "\n".join(lines[:4]),
                "accent": (214, 180, 106),
            })

    if simulator_output:
        lines = []
        if simulator_output.get("comparison_summary"):
            lines.append(_decision_report_appendix_text(simulator_output.get("comparison_summary"), limit=92))
        if safer_choice_name or safer_choice_reason:
            lines.append(f"当前更稳的一侧：{_decision_report_appendix_text(safer_choice_name or safer_choice_reason, limit=70)}")
        if simulator_output.get("final_insight"):
            lines.append(f"最终洞察：{_decision_report_appendix_text(simulator_output.get('final_insight'), limit=72)}")
        if simulator_warning:
            lines.append(f"完整性提醒：{_decision_report_appendix_text(simulator_warning, limit=76)}")
        if lines:
            sections.append({
                "title": "第三幕 · 未来预演如何回到结论",
                "meta": "第三幕不是为了制造戏剧性，而是为了把两条路的真实代价和回头空间摊开。",
                "body": "\n".join(lines[:4]),
                "accent": (194, 112, 104),
            })

    return sections


def _decision_report_short_text(value, limit: int = 38) -> str:
    text = _decision_report_text(value, default="").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip("，。、；;,. ") + "…"


def _decision_report_timeline_digest(choice: dict, scenario: str) -> list[str]:
    if not isinstance(choice, dict):
        return []

    lines: list[str] = []
    distribution = choice.get("probability_distribution") if isinstance(choice.get("probability_distribution"), dict) else {}
    bucket = distribution.get(scenario) if isinstance(distribution.get(scenario), dict) else {}
    percent = bucket.get("percent")
    if percent not in (None, ""):
        lines.append(f"概率 {_decision_report_text(percent)}%")
    reason = _decision_report_short_text(bucket.get("reason"), limit=34)
    if reason:
        lines.append(reason)

    timelines = choice.get("timelines") if isinstance(choice.get("timelines"), dict) else {}
    timeline = timelines.get(scenario) if isinstance(timelines.get(scenario), dict) else {}
    nodes = timeline.get("nodes") if isinstance(timeline.get("nodes"), list) else []
    preferred_indexes = [0, 2, 4]
    used_indexes = [idx for idx in preferred_indexes if idx < len(nodes)]
    if not used_indexes:
        used_indexes = list(range(min(len(nodes), 3)))

    for idx in used_indexes[:3]:
        node = nodes[idx]
        if not isinstance(node, dict):
            continue
        time_label = _decision_report_text(node.get("time"), default="节点")
        external = _decision_report_short_text(node.get("external_state"), limit=18)
        action = _decision_report_short_text(node.get("key_action"), limit=14)
        parts = [part for part in (external, f"动作：{action}" if action else "") if part]
        if parts:
            lines.append(f"{time_label}：{' / '.join(parts[:2])}")

    return lines[:5]


def _decision_report_bias_lines(biases, reminder: str = "") -> list[str]:
    lines: list[str] = []
    if reminder and not _decision_report_is_placeholder(reminder):
        lines.append(f"偏差提醒：{_decision_report_text(reminder)}")
    if isinstance(biases, list):
        for item in biases[:4]:
            if not isinstance(item, dict):
                continue
            label = _decision_report_text(item.get("label"), default="")
            hint = _decision_report_short_text(item.get("hint"), limit=34)
            if label and hint:
                lines.append(f"{label}：{hint}")
            elif label:
                lines.append(label)
    return lines[:5]


def _decision_report_value_lines(value_profile: dict | None) -> list[str]:
    if not isinstance(value_profile, dict):
        return []
    lines: list[str] = []
    top_values = value_profile.get("top_values") if isinstance(value_profile.get("top_values"), list) else []
    if top_values:
        labels = []
        for item in top_values[:3]:
            if not isinstance(item, dict):
                continue
            label = _decision_report_text(item.get("label"), default="")
            weight = item.get("weight")
            if label:
                labels.append(f"{label}{f'({weight})' if weight not in (None, '') else ''}")
        if labels:
            lines.append(f"优先级：{' / '.join(labels)}")
    if value_profile.get("summary"):
        lines.append(_decision_report_short_text(value_profile.get("summary"), limit=44))
    return lines[:4]


def _decision_report_alternative_path_lines(path: dict | None) -> list[str]:
    if not isinstance(path, dict):
        return []
    lines: list[str] = []
    title = _decision_report_text(path.get("title"), default="")
    summary = _decision_report_short_text(path.get("summary"), limit=40)
    why_it_works = _decision_report_short_text(path.get("why_it_works"), limit=40)
    first_step = _decision_report_short_text(path.get("first_step"), limit=36)
    if title:
        lines.append(title)
    if summary:
        lines.append(summary)
    if why_it_works:
        lines.append(f"为什么可行：{why_it_works}")
    if first_step:
        lines.append(f"第一步：{first_step}")
    return lines[:5]


def _decision_report_external_signal_lines(signals, *, limit: int = 4) -> list[str]:
    if not isinstance(signals, list):
        return []
    lines: list[str] = []
    for item in signals[:limit]:
        if not isinstance(item, dict):
            continue
        time_text = _decision_report_text(item.get("time") or item.get("captured_at"), default="")
        stance = _decision_report_text(item.get("stance"), default="")
        summary = _decision_report_short_text(item.get("summary"), limit=42)
        prefix = ""
        if time_text and stance:
            prefix = f"[{time_text} / {stance}] "
        elif time_text:
            prefix = f"[{time_text}] "
        elif stance:
            prefix = f"[{stance}] "
        if summary:
            lines.append(prefix + summary)
    return lines[:limit]


def _decision_report_pdf_text(value, default: str = "未提供") -> str:
    text = _decision_report_text(value, default=default)
    cleaned = []
    for ch in text:
        code = ord(ch)
        if ch == "\ufe0f":
            continue
        if code > 0xFFFF:
            continue
        if 0x2600 <= code <= 0x27BF:
            continue
        cleaned.append(ch)
    result = "".join(cleaned).strip()
    return result or default


def _decision_report_lines(items) -> list[str]:
    if not isinstance(items, list):
        return []
    lines = []
    for item in items:
        text = _decision_report_text(item, default="")
        if text:
            lines.append(text)
    return lines


def _decision_report_compact_lines(items) -> list[dict]:
    groups: list[dict] = []
    for text in _decision_report_lines(items):
        previous = groups[-1] if groups else None
        if previous and previous["text"] == text:
            previous["count"] += 1
            continue
        groups.append({"text": text, "count": 1})
    return groups


def _decision_report_phase_label(phase: str) -> str:
    value = _decision_report_text(phase, default="")
    phase_map = {
        "b1_diagnosis": "B1 诊断追问",
        "b2_info_fill": "B2 信息补齐",
        "b3_cognitive_unlock": "B3 认知框架",
        "b4_experience_sim": "B4 经验模拟",
        "b5_emotional_mirror": "B5 情绪镜像",
        "c1_reevaluation": "C1 重新评估",
        "a_recheck": "A 二次检测",
        "b6_sim_params": "B6 模拟参数",
        "b7_sim_timelines": "B7 时间线推演",
        "b8_sim_coping": "B8 应对预案",
        "b9_sim_comparison": "B9 对比总览",
        "simulator_complete": "模拟完成",
        "completed": "已完成",
        "abandoned": "已中断",
    }
    return phase_map.get(value, value or "处理节点")


def _decision_report_detect_status_label(status: str) -> str:
    value = _decision_report_text(status, default="")
    status_map = {
        "completed": "已完成",
        "running": "进行中",
        "failed": "失败",
        "pending": "等待中",
    }
    return status_map.get(value, value or "未运行")


def _decision_report_html(value, default: str = "", *, limit: int | None = None) -> str:
    text = _decision_report_text(value, default=default)
    if limit and len(text) > limit:
        text = text[: max(limit - 1, 1)].rstrip("，。、；;,. ") + "…"
    return html_escape(text).replace("\n", "<br>")


def _decision_report_html_list(items, *, empty: str = "暂无记录", limit: int = 8) -> str:
    lines = _decision_report_lines(items)[:limit]
    if not lines:
        return f"<p class=\"muted\">{_decision_report_html(empty)}</p>"
    return "<ul>" + "".join(f"<li>{_decision_report_html(line)}</li>" for line in lines) + "</ul>"


def _decision_report_probability_bucket(choice: dict, scenario: str) -> dict:
    distribution = choice.get("probability_distribution") if isinstance(choice.get("probability_distribution"), dict) else {}
    bucket = distribution.get(scenario) if isinstance(distribution.get(scenario), dict) else {}
    return bucket


def _decision_report_weasy_radar_svg(metrics: list[dict], *, left_title: str, right_title: str) -> str:
    if not metrics:
        return "<p class=\"muted\">暂无雷达图数据。</p>"

    cx, cy, radius = 148, 128, 82
    axis_count = max(len(metrics), 1)

    def point(index: int, factor: float) -> tuple[float, float]:
        angle = -math.pi / 2 + 2 * math.pi * index / axis_count
        return (cx + math.cos(angle) * radius * factor, cy + math.sin(angle) * radius * factor)

    def polygon(values: list[int]) -> str:
        points = []
        for idx, value in enumerate(values):
            x, y = point(idx, max(0, min(_decision_report_int(value, 0), 100)) / 100)
            points.append(f"{x:.1f},{y:.1f}")
        return " ".join(points)

    left_values = [metric.get("a", 0) for metric in metrics]
    right_values = [metric.get("b", 0) for metric in metrics]
    rings = []
    for ring in (0.25, 0.5, 0.75, 1):
        rings.append(f"<polygon class=\"radar-ring\" points=\"{polygon([int(ring * 100)] * axis_count)}\" />")

    axes = []
    labels = []
    for idx, metric in enumerate(metrics):
        x, y = point(idx, 1)
        lx, ly = point(idx, 1.22)
        axes.append(f"<line class=\"radar-axis\" x1=\"{cx}\" y1=\"{cy}\" x2=\"{x:.1f}\" y2=\"{y:.1f}\" />")
        labels.append(
            f"<text class=\"radar-label\" x=\"{lx:.1f}\" y=\"{ly:.1f}\" text-anchor=\"middle\">"
            f"{_decision_report_html(metric.get('label'), limit=8)}</text>"
        )

    legend = (
        f"<div class=\"radar-legend\"><span class=\"legend-dot a\"></span>{_decision_report_html(left_title)}"
        f"<span class=\"legend-gap\"></span><span class=\"legend-dot b\"></span>{_decision_report_html(right_title)}</div>"
    )
    return f"""
    <div class="radar-card">
      <svg class="radar-svg" viewBox="0 0 296 256" role="img" aria-label="后悔与走势雷达">
        {''.join(rings)}
        {''.join(axes)}
        <polygon class="radar-poly a" points="{polygon(left_values)}" />
        <polygon class="radar-poly b" points="{polygon(right_values)}" />
        {''.join(labels)}
      </svg>
      {legend}
    </div>
    """


def _decision_report_weasy_timeline(choice: dict, *, title: str, accent: str) -> str:
    if not isinstance(choice, dict):
        return f"<p class=\"muted\">{_decision_report_html(title)} 暂无时间线数据。</p>"
    timelines = choice.get("timelines") if isinstance(choice.get("timelines"), dict) else {}
    parts = [f"<section class=\"choice-block\" style=\"--accent:{accent}\"><h3>{_decision_report_html(title)}</h3>"]
    for scenario in ("tailwind", "steady", "headwind"):
        timeline = timelines.get(scenario) if isinstance(timelines.get(scenario), dict) else {}
        nodes = timeline.get("nodes") if isinstance(timeline.get("nodes"), list) else []
        bucket = _decision_report_probability_bucket(choice, scenario)
        scenario_title = {"tailwind": "顺风局", "steady": "平稳局", "headwind": "逆风局"}.get(scenario, scenario)
        percent = bucket.get("percent")
        reason = _decision_report_html(bucket.get("reason"), default="", limit=80)
        parts.append("<article class=\"scenario-card\">")
        parts.append(
            f"<h4>{scenario_title}"
            f"<span>{_decision_report_html(percent, default='--')}%</span></h4>"
        )
        if reason:
            parts.append(f"<p class=\"muted\">{reason}</p>")
        if nodes:
            parts.append("<ol class=\"timeline-list\">")
            for node in nodes[:5]:
                if not isinstance(node, dict):
                    continue
                parts.append(
                    "<li>"
                    f"<strong>{_decision_report_html(node.get('time'), default='未来节点')}</strong>"
                    f"<p>{_decision_report_html(node.get('external_state'), default='外部状态未说明', limit=110)}</p>"
                    f"<p class=\"muted\">行动信号：{_decision_report_html(node.get('key_action') or node.get('signal'), default='继续观察关键变量', limit=90)}</p>"
                    "</li>"
                )
            parts.append("</ol>")
        else:
            parts.append("<p class=\"muted\">暂无节点。</p>")
        parts.append("</article>")
    parts.append("</section>")
    return "".join(parts)


def generate_decision_weasyprint_report(
    question: str,
    *,
    detection_job: dict | None = None,
    engineb_session: dict | None = None,
    decision_data: dict | None = None,
    metadata: dict | None = None,
    output_path: str | None = None,
) -> str:
    """用 WeasyPrint 生成 HTML/CSS 决策 PDF；缺依赖时由调用方回退到 fpdf2。"""
    from weasyprint import HTML

    detection_job = detection_job if isinstance(detection_job, dict) else {}
    engineb_session = engineb_session if isinstance(engineb_session, dict) else {}
    decision_data = decision_data if isinstance(decision_data, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}

    generated_at = metadata.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    decision_result = decision_data.get("result") if isinstance(decision_data.get("result"), dict) else {}
    tier_config = decision_data.get("tier_config") if isinstance(decision_data.get("tier_config"), dict) else {}
    tier_label = _decision_report_text(tier_config.get("label") or decision_data.get("tier"), default="未指定")
    detection_result = detection_job.get("result") if isinstance(detection_job.get("result"), dict) else {}
    detection_status = _decision_report_detect_status_label(detection_job.get("status"))
    engineb_phase = _decision_report_phase_label(engineb_session.get("phase"))
    simulator_output = engineb_session.get("simulator_output") if isinstance(engineb_session.get("simulator_output"), dict) else {}
    has_simulator = bool(simulator_output)
    monte_carlo = simulator_output.get("monte_carlo") if isinstance(simulator_output.get("monte_carlo"), dict) else {}
    choice_a = simulator_output.get("choice_a") if isinstance(simulator_output.get("choice_a"), dict) else {}
    choice_b = simulator_output.get("choice_b") if isinstance(simulator_output.get("choice_b"), dict) else {}
    choice_a_name = _decision_report_text(choice_a.get("choice_name"), default="选项 A")
    choice_b_name = _decision_report_text(choice_b.get("choice_name"), default="选项 B")
    radar_metrics = _decision_report_radar_metrics(simulator_output) if has_simulator else []
    bias_lines = _decision_report_bias_lines(
        engineb_session.get("decision_biases") if isinstance(engineb_session.get("decision_biases"), list) else [],
        _decision_report_text(engineb_session.get("bias_reminder"), default=""),
    )
    value_lines = _decision_report_value_lines(engineb_session.get("value_profile") if isinstance(engineb_session.get("value_profile"), dict) else {})
    alternative_lines = _decision_report_alternative_path_lines(
        engineb_session.get("alternative_path") if isinstance(engineb_session.get("alternative_path"), dict) else {}
    )
    signal_lines = _decision_report_external_signal_lines(
        engineb_session.get("external_signals") if isinstance(engineb_session.get("external_signals"), list) else []
    )
    trace_digest = _decision_report_trace_digest(engineb_session.get("processing_trace") if isinstance(engineb_session.get("processing_trace"), list) else [])
    monte_smooth = monte_carlo.get("smooth_prob") if isinstance(monte_carlo.get("smooth_prob"), dict) else {}
    monte_ci = monte_carlo.get("confidence_interval") if isinstance(monte_carlo.get("confidence_interval"), dict) else {}
    monte_heatmap = monte_carlo.get("disagreement_heatmap") if isinstance(monte_carlo.get("disagreement_heatmap"), list) else []
    monte_lines = []
    if monte_carlo:
        monte_lines.append(
            f"采样 {_decision_report_html(monte_carlo.get('sample_count'), default='--')} 次 · "
            f"代理 {_decision_report_html(monte_carlo.get('persona_count'), default='--')} 个 · "
            f"每分支 {_decision_report_html(monte_carlo.get('agents_per_branch'), default='--')} 代理"
        )
        monte_lines.append(
            "平滑分布："
            f"顺风 {_decision_report_html(monte_smooth.get('optimistic'), default='--')}% / "
            f"平稳 {_decision_report_html(monte_smooth.get('baseline'), default='--')}% / "
            f"逆风 {_decision_report_html(monte_smooth.get('pessimistic'), default='--')}%"
        )
        ci_parts = []
        for key, label in (("optimistic", "顺风"), ("baseline", "平稳"), ("pessimistic", "逆风")):
            item = monte_ci.get(key)
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                ci_parts.append(f"{label} {_decision_report_html(item[0], default='--')}%-{_decision_report_html(item[1], default='--')}%")
            elif isinstance(item, dict):
                ci_parts.append(f"{label} {_decision_report_html(item.get('low'), default='--')}%-{_decision_report_html(item.get('high'), default='--')}%")
        if ci_parts:
            monte_lines.append("置信区间：" + "；".join(ci_parts))
        if monte_heatmap:
            top_heat = []
            for item in monte_heatmap[:5]:
                if isinstance(item, dict):
                    top_heat.append(
                        f"{_decision_report_html(item.get('label') or item.get('factor') or item.get('key'), default='变量')}: "
                        f"{_decision_report_html(item.get('avg_score') or item.get('disagreement'), default='--')}"
                    )
            if top_heat:
                monte_lines.append("关键分歧热区：" + "；".join(top_heat))
        monte_lines.append(
            f"LLM 委员会：请求 {monte_carlo.get('llm_panels_requested', 0)} 个面板，"
            f"发起 {monte_carlo.get('llm_calls_attempted', monte_carlo.get('actual_llm_calls', 0))} 次，"
            f"成功 {monte_carlo.get('actual_llm_calls', 0)} 次。"
        )
        if monte_carlo.get("llm_collision_summary"):
            monte_lines.append("合议结论：" + _decision_report_text(monte_carlo.get("llm_collision_summary")))
        if monte_carlo.get("client_report_memo"):
            monte_lines.append("客户摘要：" + _decision_report_text(monte_carlo.get("client_report_memo")))
        for item in (monte_carlo.get("critical_disagreements") if isinstance(monte_carlo.get("critical_disagreements"), list) else [])[:4]:
            monte_lines.append("核心分歧：" + _decision_report_text(item))
        for item in (monte_carlo.get("decision_guardrails") if isinstance(monte_carlo.get("decision_guardrails"), list) else [])[:4]:
            monte_lines.append("决策护栏：" + _decision_report_text(item))
        for item in (monte_carlo.get("premium_report_sections") if isinstance(monte_carlo.get("premium_report_sections"), list) else [])[:3]:
            monte_lines.append("报告段落：" + _decision_report_text(item))

    summary_lines = []
    if detection_job:
        summary_lines.append(f"第一幕：{detection_status}")
    if engineb_session.get("recommendation"):
        summary_lines.append(f"第二幕建议：{_decision_report_text(engineb_session.get('recommendation'))}")
    elif engineb_session:
        summary_lines.append(f"第二幕阶段：{engineb_phase}")
    if has_simulator and simulator_output.get("final_insight"):
        summary_lines.append(f"第三幕洞察：{_decision_report_text(simulator_output.get('final_insight'))}")
    if not summary_lines:
        summary_lines.append("当前报告记录了这次推演已完成的阶段。")

    b1_rows = []
    questions = engineb_session.get("diagnosis_questions") if isinstance(engineb_session.get("diagnosis_questions"), list) else []
    answers = engineb_session.get("diagnosis_answers") if isinstance(engineb_session.get("diagnosis_answers"), list) else []
    for idx, item in enumerate(questions[:6]):
        if not isinstance(item, dict):
            continue
        answer = answers[idx] if idx < len(answers) else "未回答"
        b1_rows.append(
            f"<div class=\"qa\"><dt>Q{idx + 1}. {_decision_report_html(item.get('question_text'), default='诊断问题')}</dt>"
            f"<dd>{_decision_report_html(answer)}</dd></div>"
        )

    info_cards = []
    for item in (engineb_session.get("missing_info_items") if isinstance(engineb_session.get("missing_info_items"), list) else [])[:5]:
        if not isinstance(item, dict):
            continue
        info_cards.append(
            "<article class=\"mini-card\">"
            f"<h4>{_decision_report_html(item.get('title'), default='信息项')}</h4>"
            f"<p>{_decision_report_html(item.get('content'), default='', limit=180)}</p>"
            f"<p class=\"muted\">为什么关键：{_decision_report_html(item.get('why_critical'), default='未说明', limit=120)}</p>"
            "</article>"
        )

    frame_cards = []
    for item in (engineb_session.get("cognitive_frames") if isinstance(engineb_session.get("cognitive_frames"), list) else [])[:5]:
        if not isinstance(item, dict):
            continue
        frame_cards.append(
            "<article class=\"mini-card\">"
            f"<h4>{_decision_report_html(item.get('title'), default='判断框架')}</h4>"
            f"<p>{_decision_report_html(item.get('core_insight'), default='', limit=190)}</p>"
            f"<p class=\"muted\">换个问法：{_decision_report_html(item.get('reframe_question'), default='未提供', limit=120)}</p>"
            "</article>"
        )

    css = """
    @page {
      size: A4;
      margin: 18mm 16mm 20mm;
      @bottom-center {
        content: "认知拉格朗日点 · " counter(page);
        color: #7a8192;
        font-size: 9px;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: #162033;
      font-family: "PingFang SC", "STHeiti", "Noto Serif SC", serif;
      line-height: 1.72;
      background: #f5f0e6;
      font-size: 12px;
    }
    a { color: #2e5b97; text-decoration: none; }
    .cover {
      min-height: 248mm;
      margin: -18mm -16mm -20mm;
      padding: 42mm 24mm 24mm;
      color: #fff;
      background:
        radial-gradient(circle at 24% 22%, rgba(218,182,107,.55), transparent 12%),
        radial-gradient(circle at 78% 32%, rgba(105,144,212,.45), transparent 16%),
        linear-gradient(145deg, #07101f 0%, #11192b 52%, #050914 100%);
    }
    .cover h1 { font-size: 34px; margin: 0 0 8px; letter-spacing: .08em; }
    .cover .subtitle { color: #cbd4e5; font-size: 15px; margin-bottom: 26px; }
    .cover-question {
      border: 1px solid rgba(232,201,132,.45);
      background: rgba(255,255,255,.08);
      border-radius: 22px;
      padding: 22px;
      font-size: 20px;
      line-height: 1.58;
      margin: 36px 0 30px;
    }
    .cover-grid, .summary-grid, .mini-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }
    .cover-tile, .summary-card, .mini-card, .scenario-card, .choice-block, .qa {
      break-inside: avoid;
      border-radius: 16px;
      padding: 14px 16px;
      background: rgba(255,255,255,.9);
      border: 1px solid rgba(30,42,68,.12);
      box-shadow: 0 10px 30px rgba(18, 28, 45, .08);
    }
    .cover-tile { color: #fff; background: rgba(255,255,255,.09); border-color: rgba(255,255,255,.18); }
    .cover-tile strong, .summary-card strong { display: block; font-size: 16px; margin-top: 4px; }
    .toc a { display: block; padding: 10px 0; border-bottom: 1px solid #d8d1c4; }
    section.chapter { break-before: page; }
    h2 {
      margin: 0 0 16px;
      padding-bottom: 8px;
      border-bottom: 3px solid #d6b46a;
      color: #0f1727;
      font-size: 23px;
    }
    h3 { color: #223552; font-size: 16px; margin: 16px 0 8px; }
    h4 { margin: 0 0 6px; color: #253753; font-size: 13px; }
    .muted { color: #697386; }
    .pill {
      display: inline-block;
      padding: 2px 9px;
      border-radius: 999px;
      background: #efe4c9;
      color: #765d28;
      font-size: 10px;
      margin-right: 6px;
    }
    .panel {
      break-inside: avoid;
      border-left: 4px solid #d6b46a;
      background: #fffaf0;
      padding: 14px 18px;
      border-radius: 12px;
      margin: 14px 0;
    }
    .qa { margin: 8px 0; }
    .qa dt { font-weight: 700; color: #223552; }
    .qa dd { margin: 6px 0 0; color: #4a5568; }
    .mini-grid { grid-template-columns: repeat(2, 1fr); }
    .choice-block {
      margin: 18px 0;
      border-top: 5px solid var(--accent);
      background: #fff;
    }
    .scenario-card { margin: 10px 0; background: #fbfcff; }
    .scenario-card h4 { display: flex; justify-content: space-between; }
    .timeline-list { margin: 8px 0 0; padding-left: 18px; }
    .timeline-list li { margin-bottom: 8px; }
    .radar-card {
      break-inside: avoid;
      margin: 14px 0 20px;
      border-radius: 18px;
      padding: 16px;
      background: #ffffff;
      border: 1px solid #dce3ef;
    }
    .radar-svg { width: 100%; max-height: 260px; }
    .radar-ring { fill: none; stroke: #dfe5ef; stroke-width: 1; }
    .radar-axis { stroke: #d5dce8; stroke-width: 1; }
    .radar-poly.a { fill: rgba(86,128,196,.38); stroke: #5680c4; stroke-width: 2; }
    .radar-poly.b { fill: rgba(214,180,106,.42); stroke: #d6b46a; stroke-width: 2; }
    .radar-label { fill: #657083; font-size: 10px; }
    .radar-legend { text-align: center; color: #536074; }
    .legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 5px; }
    .legend-dot.a { background: #5680c4; }
    .legend-dot.b { background: #d6b46a; }
    .legend-gap { display: inline-block; width: 22px; }
    """

    html = f"""<!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8">
      <title>认知拉格朗日点 · 决策报告</title>
      <style>{css}</style>
    </head>
    <body>
      <section class="cover">
        <div class="pill">Decision Journey Report</div>
        <h1>认知拉格朗日点</h1>
        <div class="subtitle">一份从结构检测、决策突破到未来模拟的完整记录</div>
        <div class="cover-question">{_decision_report_html(question, default='未提供问题')}</div>
        <div class="cover-grid">
          <div class="cover-tile">生成时间<strong>{_decision_report_html(generated_at)}</strong></div>
          <div class="cover-tile">思考档位<strong>{_decision_report_html(tier_label)}</strong></div>
          <div class="cover-tile">当前阶段<strong>{_decision_report_html(engineb_phase)}</strong></div>
        </div>
      </section>

      <section class="chapter toc" id="toc">
        <h2>目录</h2>
        <a href="#summary">一、报告摘要</a>
        <a href="#detect">二、第一幕 · 结构检测</a>
        <a href="#engineb">三、第二幕 · 决策突破</a>
        <a href="#simulator">四、第三幕 · 未来选择模拟器</a>
        <a href="#appendix">附录 · 形成纪要</a>
      </section>

      <section class="chapter" id="summary">
        <h2>一、报告摘要</h2>
        <div class="summary-grid">
          <div class="summary-card">第一幕<strong>{_decision_report_html(detection_status)}</strong></div>
          <div class="summary-card">第二幕<strong>{_decision_report_html(engineb_phase)}</strong></div>
          <div class="summary-card">第三幕<strong>{'已生成' if has_simulator else '未生成'}</strong></div>
        </div>
        <div class="panel">{_decision_report_html_list(summary_lines)}</div>
        <h3>价值锚点与偏差提醒</h3>
        {_decision_report_html_list(value_lines + bias_lines + alternative_lines, empty='暂无偏差或第三条路数据。', limit=10)}
      </section>

      <section class="chapter" id="detect">
        <h2>二、第一幕 · 结构检测</h2>
        <p><span class="pill">状态</span>{_decision_report_html(detection_status)}</p>
        <div class="panel">
          <strong>结构结论</strong>
          <p>{_decision_report_html(detection_result.get('summary') or decision_result.get('summary'), default='暂无第一幕结论。')}</p>
        </div>
      </section>

      <section class="chapter" id="engineb">
        <h2>三、第二幕 · 决策突破</h2>
        <h3>B1 · 诊断追问</h3>
        {''.join(b1_rows) if b1_rows else '<p class="muted">暂无 B1 诊断问答。</p>'}
        <h3>B2 · 需要补齐的信息</h3>
        <div class="mini-grid">{''.join(info_cards) if info_cards else '<p class="muted">暂无信息补齐项。</p>'}</div>
        <h3>B3 · 新的判断框架</h3>
        <div class="mini-grid">{''.join(frame_cards) if frame_cards else '<p class="muted">暂无认知框架。</p>'}</div>
        <h3>B2+ · 外部声音快照</h3>
        {_decision_report_html_list(signal_lines, empty='暂无外部声音快照。', limit=6)}
        <h3>C1 · 最终建议</h3>
        <div class="panel">
          <p><strong>{_decision_report_html(engineb_session.get('recommendation'), default='暂无明确建议。')}</strong></p>
          <p>{_decision_report_html(engineb_session.get('action_plan'), default='暂无行动方案。')}</p>
          <p class="muted">{_decision_report_html(engineb_session.get('reasoning'), default='暂无推理说明。')}</p>
        </div>
      </section>

      <section class="chapter" id="simulator">
        <h2>四、第三幕 · 未来选择模拟器</h2>
        {'<h3>后悔与走势雷达</h3>' + _decision_report_weasy_radar_svg(radar_metrics, left_title=choice_a_name, right_title=choice_b_name) if has_simulator else '<p class="muted">当前还没有第三幕模拟结果。</p>'}
        {'<div class="panel"><strong>Ultra 决策委员会 · Monte Carlo 合议摘要</strong>' + _decision_report_html_list(monte_lines, empty='暂无 Monte Carlo 数据。', limit=12) + '</div>' if monte_carlo else ''}
        {_decision_report_weasy_timeline(choice_a, title=choice_a_name, accent='#5680c4') if has_simulator else ''}
        {_decision_report_weasy_timeline(choice_b, title=choice_b_name, accent='#d6b46a') if has_simulator else ''}
        <div class="panel">
          <strong>最终洞察</strong>
          <p>{_decision_report_html(simulator_output.get('final_insight'), default='暂无最终洞察。')}</p>
        </div>
      </section>

      <section class="chapter" id="appendix">
        <h2>附录 · 形成纪要</h2>
        {_decision_report_html_list([f"{item.get('title', '')}：{'；'.join(item.get('lines', []))}" for item in trace_digest], empty='暂无结构化轨迹摘要。', limit=10)}
      </section>
    </body>
    </html>
    """

    final_path = output_path or os.path.join(OUTPUT_DIR, "decision-report.pdf")
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    HTML(string=html, base_url=PROJECT_ROOT).write_pdf(final_path)
    _copy_to_archive(final_path)
    return final_path


def generate_decision_pdf_report(
    question: str,
    *,
    detection_job: dict | None = None,
    engineb_session: dict | None = None,
    decision_data: dict | None = None,
    metadata: dict | None = None,
    output_path: str | None = None,
) -> str:
    """生成单题检测 / Engine B / 模拟器的整合 PDF 报告。"""
    renderer = os.environ.get("CLP_PDF_RENDERER", "fpdf").strip().lower()
    if renderer in {"weasyprint", "html", "auto"}:
        try:
            return generate_decision_weasyprint_report(
                question,
                detection_job=detection_job,
                engineb_session=engineb_session,
                decision_data=decision_data,
                metadata=metadata,
                output_path=output_path,
            )
        except ImportError as exc:
            if renderer in {"weasyprint", "html"}:
                print(f"  ⚠ WeasyPrint 不可用，已回退到 fpdf2: {exc}")
        except Exception as exc:
            print(f"  ⚠ WeasyPrint PDF 生成失败，已回退到 fpdf2: {exc}")

    try:
        from fpdf import FPDF
    except ImportError:
        # Fallback to text report if fpdf is missing
        return generate_decision_text_report(
            question,
            detection_job=detection_job,
            engineb_session=engineb_session,
            metadata=metadata,
            output_path=output_path.replace(".pdf", ".txt") if output_path else None
        )

    detection_job = detection_job if isinstance(detection_job, dict) else {}
    engineb_session = engineb_session if isinstance(engineb_session, dict) else {}
    decision_data = decision_data if isinstance(decision_data, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}

    font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
    safe_question = _decision_report_pdf_text(question, default="未提供问题")
    generated_at = metadata.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    decision_logs = _decision_report_lines(decision_data.get("logs") or [])
    compact_decision_logs = _decision_report_compact_lines(decision_data.get("logs") or [])
    decision_result = decision_data.get("result") if isinstance(decision_data.get("result"), dict) else {}
    decision_created_at = _decision_report_text(decision_data.get("created_at"), default="")
    decision_completed_at = _decision_report_text(decision_data.get("completed_at"), default="")
    decision_updated_at = _decision_report_text(decision_data.get("updated_at"), default="")
    decision_status = _decision_report_text(decision_data.get("status"), default="")
    decision_phase = _decision_report_text(decision_data.get("phase"), default="")
    tier_config = decision_data.get("tier_config") if isinstance(decision_data.get("tier_config"), dict) else {}
    tier_label = _decision_report_pdf_text(
        tier_config.get("label") or decision_data.get("tier"),
        default="未指定",
    )
    tier_tagline = _decision_report_pdf_text(tier_config.get("tagline"), default="")
    detection_result = detection_job.get("result") if isinstance(detection_job.get("result"), dict) else {}
    detection_status = _decision_report_text(detection_job.get("status"), default="未运行")
    engineb_phase = _decision_report_text(engineb_session.get("phase"), default="未运行")
    simulator_output = engineb_session.get("simulator_output") if isinstance(engineb_session.get("simulator_output"), dict) else {}
    has_simulator = bool(simulator_output)
    monte_carlo = simulator_output.get("monte_carlo") if isinstance(simulator_output.get("monte_carlo"), dict) else {}
    trace = engineb_session.get("processing_trace") if isinstance(engineb_session.get("processing_trace"), list) else []
    simulator_warning = _decision_report_similarity_note(simulator_output) if has_simulator else ""
    safer_choice_name, safer_choice_reason = _decision_report_pick_safer_choice(simulator_output) if has_simulator else ("", "")
    summary_choice_a = _decision_report_choice_snapshot(simulator_output.get("choice_a")) if has_simulator else {}
    summary_choice_b = _decision_report_choice_snapshot(simulator_output.get("choice_b")) if has_simulator else {}
    decision_biases = engineb_session.get("decision_biases") if isinstance(engineb_session.get("decision_biases"), list) else []
    bias_reminder = _decision_report_text(engineb_session.get("bias_reminder"), default="")
    value_profile = engineb_session.get("value_profile") if isinstance(engineb_session.get("value_profile"), dict) else {}
    alternative_path = engineb_session.get("alternative_path") if isinstance(engineb_session.get("alternative_path"), dict) else {}
    external_signals = engineb_session.get("external_signals") if isinstance(engineb_session.get("external_signals"), list) else []
    if not external_signals and has_simulator:
        external_signals = simulator_output.get("market_signals") if isinstance(simulator_output.get("market_signals"), list) else []
    bias_lines = _decision_report_bias_lines(decision_biases, bias_reminder)
    value_lines = _decision_report_value_lines(value_profile)
    alternative_lines = _decision_report_alternative_path_lines(alternative_path or (simulator_output.get("third_path") if has_simulator else {}))
    signal_lines = _decision_report_external_signal_lines(external_signals)

    report_outline = [("一、报告摘要", "整合结论与关键阶段总览")]
    if detection_job:
        report_outline.append(("二、第一幕 · 结构检测", "问题张力、三层筛子与第一幕判定"))
    if engineb_session:
        report_outline.append(("三、第二幕 · 决策突破", "卡点诊断、补全与建议形成"))
    if has_simulator:
        report_outline.append(("四、第三幕 · 未来选择模拟器", "未来时间线、行动地图与风险预案"))
    if compact_decision_logs:
        report_outline.append(("附录A · 系统过程摘要", "压缩后的过程日志，只保留关键前后文"))
    if trace:
        report_outline.append(("附录B · 内部轨迹摘要", "结构化处理节点的摘要视图"))

    def _scenario_label(key: str) -> str:
        return {
            "tailwind": "顺风局",
            "steady": "平稳局",
            "headwind": "逆风局",
        }.get(key, key)

    class PDF(FPDF):
        def accent_rule(self, y: float | None = None, color: tuple[int, int, int] = (214, 180, 106)):
            current_y = self.get_y() if y is None else y
            self.set_draw_color(*color)
            self.set_line_width(1)
            self.line(self.l_margin, current_y, self.l_margin + 28, current_y)

        def _constellation_points(
            self,
            seed_text: str,
            *,
            left: float,
            top: float,
            right: float,
            bottom: float,
            count: int = 32,
        ) -> list[tuple[float, float, float]]:
            width = max(right - left, 1)
            height = max(bottom - top, 1)
            points = []
            for index in range(count):
                x = left + width * _decision_report_seeded_unit(seed_text, f"{index}:x")
                y = top + height * _decision_report_seeded_unit(seed_text, f"{index}:y")
                size = 0.5 + 1.8 * _decision_report_seeded_unit(seed_text, f"{index}:r")
                points.append((x, y, size))
            return points

        def cosmic_background(
            self,
            *,
            seed_text: str,
            left: float = 10,
            top: float = 10,
            right: float | None = None,
            bottom: float | None = None,
            star_count: int = 38,
            accent: tuple[int, int, int] = (214, 180, 106),
            secondary: tuple[int, int, int] = (116, 154, 214),
        ):
            right = self.w - 10 if right is None else right
            bottom = self.h - 20 if bottom is None else bottom
            stars = self._constellation_points(
                seed_text,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                count=star_count,
            )
            anchor_indexes = [2, 5, 9, 14, 20, 26, 31]
            anchors = [stars[idx] for idx in anchor_indexes if idx < len(stars)]
            self.set_draw_color(54, 76, 110)
            self.set_line_width(0.25)
            for index in range(max(len(anchors) - 1, 0)):
                x1, y1, _ = anchors[index]
                x2, y2, _ = anchors[index + 1]
                self.line(x1, y1, x2, y2)
            if len(anchors) >= 4:
                self.line(anchors[1][0], anchors[1][1], anchors[4][0], anchors[4][1])
            for idx, (x, y, radius) in enumerate(stars):
                if idx % 4 == 0:
                    self.set_fill_color(*secondary)
                else:
                    self.set_fill_color(*accent)
                self.circle(x, y, radius, style="F")

        def chapter_constellation(self, *, y: float, accent: tuple[int, int, int] = (214, 180, 106)):
            nodes = [
                (self.w - self.r_margin - 38, y + 2),
                (self.w - self.r_margin - 26, y - 1.5),
                (self.w - self.r_margin - 15, y + 4.5),
                (self.w - self.r_margin - 4, y + 1),
            ]
            self.set_draw_color(196, 204, 218)
            self.set_line_width(0.4)
            for index in range(len(nodes) - 1):
                self.line(nodes[index][0], nodes[index][1], nodes[index + 1][0], nodes[index + 1][1])
            self.set_fill_color(*accent)
            for index, (x, y_pos) in enumerate(nodes):
                radius = 1.1 if index in (0, len(nodes) - 1) else 0.8
                self.circle(x, y_pos, radius, style="F")

        def radar_compare(
            self,
            *,
            title: str,
            metrics: list[dict],
            left_title: str,
            right_title: str,
            left_color: tuple[int, int, int] = (86, 128, 196),
            right_color: tuple[int, int, int] = (214, 180, 106),
            meta: str = "",
        ):
            if not metrics:
                return
            self.ensure_room(108)
            self.section_title(title)
            if meta:
                self.muted_text(meta, indent=2)

            left = self.l_margin
            top = self.get_y() + 2
            total_w = self.w - self.l_margin - self.r_margin
            box_h = 88
            self.set_fill_color(247, 249, 252)
            self.set_draw_color(228, 232, 238)
            self.rect(left, top, total_w, box_h, "DF")

            center_x = left + total_w * 0.36
            center_y = top + box_h * 0.56
            radius = min(total_w * 0.22, box_h * 0.32)
            axis_count = len(metrics)

            def _axis_point(index: int, factor: float) -> tuple[float, float]:
                angle = -math.pi / 2 + 2 * math.pi * index / axis_count
                return (
                    center_x + math.cos(angle) * radius * factor,
                    center_y + math.sin(angle) * radius * factor,
                )

            self.set_draw_color(220, 224, 232)
            self.set_line_width(0.25)
            for ring in (0.25, 0.5, 0.75, 1.0):
                ring_points = [_axis_point(idx, ring) for idx in range(axis_count)]
                self.polygon(ring_points, style="D")
            for idx, metric in enumerate(metrics):
                outer_x, outer_y = _axis_point(idx, 1.0)
                self.line(center_x, center_y, outer_x, outer_y)
                label_x, label_y = _axis_point(idx, 1.18)
                self.set_xy(label_x - 12, label_y - 2)
                self.set_font("STHeiti", "", 8)
                self.set_text_color(118, 124, 138)
                self.cell(24, 4, _decision_report_pdf_text(metric.get("label"), default=""), align="C")

            left_points = [_axis_point(idx, max(0, min(_decision_report_int(metric.get("a"), 0), 100)) / 100) for idx, metric in enumerate(metrics)]
            right_points = [_axis_point(idx, max(0, min(_decision_report_int(metric.get("b"), 0), 100)) / 100) for idx, metric in enumerate(metrics)]

            self.set_fill_color(222, 233, 249)
            self.set_draw_color(*left_color)
            self.set_line_width(0.8)
            self.polygon(left_points, style="DF")
            self.set_fill_color(247, 234, 201)
            self.set_draw_color(*right_color)
            self.polygon(right_points, style="DF")

            for x, y in left_points:
                self.set_fill_color(*left_color)
                self.circle(x, y, 0.85, style="F")
            for x, y in right_points:
                self.set_fill_color(*right_color)
                self.circle(x, y, 0.85, style="F")

            legend_x = left + total_w * 0.66
            legend_y = top + 10
            for title_text, color, values in (
                (left_title, left_color, [metric.get("a") for metric in metrics]),
                (right_title, right_color, [metric.get("b") for metric in metrics]),
            ):
                self.set_fill_color(*color)
                self.rect(legend_x, legend_y + 1.2, 4.5, 4.5, "F")
                self.set_xy(legend_x + 7, legend_y)
                self.set_font("STHeiti", "B", 9.2)
                self.set_text_color(56, 62, 76)
                self.cell(48, 5.2, _decision_report_pdf_text(title_text), new_x="LMARGIN", new_y="NEXT")
                self.set_x(legend_x + 7)
                self.set_font("STHeiti", "", 8.4)
                self.set_text_color(116, 122, 138)
                score_text = " / ".join(str(max(0, min(_decision_report_int(value, 0), 100))) for value in values)
                self.multi_cell(52, 4.6, f"四维分布：{score_text}")
                legend_y += 15

            self.set_y(top + box_h + 4)

        def timeline_storyboard(
            self,
            *,
            title: str,
            probability: str,
            reason: str,
            nodes: list[dict],
            accent: tuple[int, int, int],
            fill: tuple[int, int, int],
            soft: tuple[int, int, int],
        ):
            if not nodes:
                return
            node_items = nodes[:6]
            card_h = 28
            row_count = max(1, math.ceil(len(node_items) / 3))
            board_h = 24 + row_count * card_h + max(row_count - 1, 0) * 8 + 8
            self.ensure_room(board_h + 8)
            x = self.l_margin
            y = self.get_y()
            total_w = self.w - self.l_margin - self.r_margin
            card_w = (total_w - 12) / 3

            self.set_fill_color(*fill)
            self.set_draw_color(228, 232, 238)
            self.rect(x, y, total_w, board_h, "DF")
            self.set_fill_color(*accent)
            self.rect(x, y, total_w, 3, "F")

            self.set_xy(x + 6, y + 6)
            self.set_font("STHeiti", "B", 10.8)
            self.set_text_color(56, 62, 78)
            self.cell(total_w - 48, 6, _decision_report_pdf_text(title))
            if probability:
                self.set_fill_color(*soft)
                self.set_draw_color(*soft)
                self.rect(x + total_w - 33, y + 5, 27, 8, "DF")
                self.set_xy(x + total_w - 33, y + 6.2)
                self.set_font("STHeiti", "B", 8.5)
                self.set_text_color(*accent)
                self.cell(27, 4.2, _decision_report_pdf_text(probability), align="C")
            if reason:
                self.set_xy(x + 6, y + 14)
                self.set_font("STHeiti", "", 8.4)
                self.set_text_color(118, 124, 138)
                self.multi_cell(total_w - 12, 4.6, _decision_report_short_text(reason, limit=86))

            grid_y = y + 24
            self.set_draw_color(*soft)
            self.set_line_width(0.5)
            for row in range(row_count):
                row_y = grid_y + row * (card_h + 8) + card_h / 2
                self.line(x + 8, row_y, x + total_w - 8, row_y)

            for idx, node in enumerate(node_items):
                col = idx % 3
                row = idx // 3
                card_x = x + 4 + col * (card_w + 2)
                card_y = grid_y + row * (card_h + 8)
                self.set_fill_color(255, 255, 255)
                self.set_draw_color(*soft)
                self.rect(card_x, card_y, card_w, card_h, "DF")
                self.set_fill_color(*accent)
                self.circle(card_x + 5, card_y + 5, 1.2, style="F")

                self.set_xy(card_x + 9, card_y + 2.8)
                self.set_font("STHeiti", "B", 8.8)
                self.set_text_color(56, 62, 78)
                self.cell(card_w - 12, 4.4, _decision_report_short_text(node.get("time"), limit=12))

                content_lines = []
                external = _decision_report_short_text(node.get("external_state"), limit=18)
                feeling = _decision_report_short_text(node.get("inner_feeling"), limit=18)
                action = _decision_report_short_text(node.get("key_action"), limit=18)
                signal = _decision_report_short_text(node.get("signal"), limit=16)
                if external:
                    content_lines.append(external)
                elif feeling:
                    content_lines.append(feeling)
                if action:
                    content_lines.append(f"动作：{action}")
                if signal:
                    content_lines.append(f"信号：{signal}")

                self.set_xy(card_x + 4, card_y + 8.6)
                self.set_font("STHeiti", "", 7.7)
                self.set_text_color(106, 112, 126)
                self.multi_cell(card_w - 8, 3.9, "\n".join(content_lines[:3]))

            self.set_y(y + board_h + 4)

        def header(self):
            if self.page_no() == 1:
                return
            self.set_font("STHeiti", "I", 8)
            self.set_text_color(130, 130, 140)
            self.cell(0, 8, "认知拉格朗日点 · 决策报告", align="R", new_x="LMARGIN", new_y="NEXT")

        def footer(self):
            self.set_y(-15)
            self.set_font("STHeiti", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"第 {self.page_no()} 页", align="C")

        def chapter_title(self, title: str):
            self.accent_rule()
            self.ln(4)
            self.chapter_constellation(y=self.get_y() + 2)
            self.set_font("STHeiti", "B", 14)
            self.set_text_color(60, 60, 80)
            self.cell(0, 9, _decision_report_pdf_text(title), new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

        def section_title(self, title: str):
            self.set_font("STHeiti", "", 8)
            self.set_text_color(150, 156, 170)
            self.cell(0, 4, "SECTION", new_x="LMARGIN", new_y="NEXT")
            self.set_font("STHeiti", "B", 11)
            self.set_text_color(82, 82, 110)
            self.cell(0, 8, _decision_report_pdf_text(title), new_x="LMARGIN", new_y="NEXT")

        def subsection_title(self, title: str):
            self.set_font("STHeiti", "B", 10)
            self.set_text_color(98, 104, 132)
            self.cell(0, 7, _decision_report_pdf_text(title), new_x="LMARGIN", new_y="NEXT")

        def body_text(self, text: str, indent: int = 0):
            self.set_font("STHeiti", "", 10)
            self.set_text_color(48, 48, 60)
            self.set_x(self.l_margin + indent)
            self.multi_cell(0, 6, _decision_report_pdf_text(text))
            self.ln(1)

        def muted_text(self, text: str, indent: int = 0):
            self.set_font("STHeiti", "", 9)
            self.set_text_color(110, 116, 130)
            self.set_x(self.l_margin + indent)
            self.multi_cell(0, 5.4, _decision_report_pdf_text(text))
            self.ln(0.8)

        def kv(self, label: str, value: str, indent: int = 0):
            label_text = _decision_report_pdf_text(label)
            value_text = _decision_report_pdf_text(value)
            x = self.l_margin + indent
            available_width = self.w - self.r_margin - x
            label_width = min(36, max(24, available_width * 0.28))
            self.set_font("STHeiti", "B", 10)
            self.set_text_color(65, 65, 85)
            self.set_x(x)
            if self.get_string_width(f"{label_text}：") > label_width:
                self.multi_cell(available_width, 6, f"{label_text}：")
                self.set_x(x + 4)
                self.set_font("STHeiti", "", 10)
                self.set_text_color(48, 48, 60)
                self.multi_cell(max(available_width - 4, 0), 6, value_text)
                self.ln(1)
                return

            self.cell(label_width, 6, f"{label_text}：")
            self.set_font("STHeiti", "", 10)
            self.set_text_color(48, 48, 60)
            self.multi_cell(0, 6, value_text)
            self.ln(1)

        def bullet_list(self, items: list[str], indent: int = 0):
            for item in items:
                text = _decision_report_pdf_text(item, default="")
                if not text:
                    continue
                self.set_x(self.l_margin + indent)
                self.set_font("STHeiti", "B", 10)
                self.set_text_color(90, 90, 110)
                self.cell(6, 6, "•")
                self.set_font("STHeiti", "", 10)
                self.set_text_color(48, 48, 60)
                self.multi_cell(0, 6, text)
                self.ln(1)

        def divider(self):
            self.set_draw_color(220, 224, 232)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(3)

        def ensure_space(self, threshold: int = 250):
            if self.get_y() > threshold:
                self.add_page()

        def ensure_room(self, needed_height: float, *, min_bottom: float = 4):
            if self.get_y() + needed_height > self.h - self.b_margin - min_bottom:
                self.add_page()

        def timeline_node(self, node: dict, indent: int = 0):
            if not isinstance(node, dict):
                return
            time_label = _decision_report_text(node.get("time"), default="节点")
            self.kv(time_label, _decision_report_text(node.get("external_state"), default="暂无外部变化"), indent=indent)
            if node.get("inner_feeling"):
                self.kv("当下感受", _decision_report_text(node.get("inner_feeling")), indent=indent + 6)
            if node.get("key_action"):
                self.kv("关键动作", _decision_report_text(node.get("key_action")), indent=indent + 6)
            if node.get("signal"):
                self.kv("判断信号", _decision_report_text(node.get("signal")), indent=indent + 6)
            self.ln(0.5)

        def process_entry(
            self,
            *,
            title: str,
            detail: str = "",
            meta: str = "",
            repeat_count: int = 1,
        ):
            estimated_height = 22 + 6 * max(len(_decision_report_pdf_text(detail, default="").splitlines()), 1)
            self.ensure_room(max(estimated_height, 28))
            start_y = self.get_y()
            x = self.l_margin + 7
            width = self.w - self.r_margin - x

            self.set_xy(x, start_y)
            self.set_font("STHeiti", "B", 10.5)
            self.set_text_color(50, 58, 78)
            self.multi_cell(width, 6, _decision_report_pdf_text(title))

            if meta:
                self.set_x(x)
                self.set_font("STHeiti", "", 8.6)
                self.set_text_color(118, 124, 138)
                self.multi_cell(width, 5.2, _decision_report_pdf_text(meta))

            if detail:
                self.set_x(x)
                self.set_font("STHeiti", "", 10)
                self.set_text_color(58, 58, 72)
                self.multi_cell(width, 5.8, _decision_report_pdf_text(detail))

            if repeat_count > 1:
                self.set_x(x)
                self.set_font("STHeiti", "", 8.6)
                self.set_text_color(166, 126, 56)
                self.multi_cell(width, 5, f"连续重复 {repeat_count} 次")

            end_y = self.get_y()
            self.set_draw_color(214, 180, 106)
            self.set_line_width(0.8)
            self.line(self.l_margin + 2, start_y + 1, self.l_margin + 2, max(start_y + 9, end_y - 1))
            self.ln(1.4)

        def metric_tile(
            self,
            x: float,
            y: float,
            w: float,
            h: float,
            *,
            label: str,
            value: str,
            fill: tuple[int, int, int] = (18, 26, 40),
            border: tuple[int, int, int] = (48, 60, 82),
        ):
            self.set_fill_color(*fill)
            self.set_draw_color(*border)
            self.rect(x, y, w, h, "DF")
            self.set_xy(x + 4, y + 4)
            self.set_font("STHeiti", "", 8.4)
            self.set_text_color(150, 160, 178)
            self.multi_cell(w - 8, 4.8, _decision_report_pdf_text(label))
            self.set_x(x + 4)
            self.set_font("STHeiti", "B", 11)
            self.set_text_color(255, 255, 255)
            self.multi_cell(w - 8, 5.6, _decision_report_pdf_text(value))

        def summary_card(
            self,
            x: float,
            y: float,
            w: float,
            h: float,
            *,
            title: str,
            lines: list[str],
            accent: tuple[int, int, int] = (214, 180, 106),
            fill: tuple[int, int, int] = (246, 248, 252),
            border: tuple[int, int, int] = (226, 230, 236),
        ):
            self.set_fill_color(*fill)
            self.set_draw_color(*border)
            self.rect(x, y, w, h, "DF")
            self.set_draw_color(*accent)
            self.set_line_width(1.2)
            self.line(x, y + 1, x, y + h - 1)
            self.set_xy(x + 6, y + 5)
            self.set_font("STHeiti", "B", 10.5)
            self.set_text_color(50, 58, 78)
            self.multi_cell(w - 10, 5.6, _decision_report_pdf_text(title))
            self.set_font("STHeiti", "", 8.8)
            self.set_text_color(88, 96, 112)
            for line in lines[:3]:
                self.set_x(x + 6)
                self.multi_cell(w - 10, 4.8, _decision_report_pdf_text(line))

        def narrative_panel(
            self,
            *,
            title: str,
            body: str = "",
            meta: str = "",
            fill: tuple[int, int, int] = (244, 246, 250),
            border: tuple[int, int, int] = (224, 228, 236),
            accent: tuple[int, int, int] = (214, 180, 106),
        ):
            body_lines = max(_decision_report_pdf_text(body, default="").count("\n") + 1, 1) if body else 0
            meta_lines = max(_decision_report_pdf_text(meta, default="").count("\n") + 1, 1) if meta else 0
            estimated_height = 20 + body_lines * 6 + meta_lines * 5 + 12
            self.ensure_room(max(estimated_height, 34))
            start_y = self.get_y()
            x = self.l_margin
            width = self.w - self.l_margin - self.r_margin
            inner_x = x + 8
            inner_width = width - 16

            self.set_xy(inner_x, start_y + 5)
            self.set_font("STHeiti", "B", 12)
            self.set_text_color(50, 58, 78)
            self.multi_cell(inner_width, 6.2, _decision_report_pdf_text(title))
            if meta:
                self.set_x(inner_x)
                self.set_font("STHeiti", "", 8.8)
                self.set_text_color(118, 124, 138)
                self.multi_cell(inner_width, 5.2, _decision_report_pdf_text(meta))
            if body:
                self.set_x(inner_x)
                self.set_font("STHeiti", "", 10)
                self.set_text_color(58, 58, 72)
                self.multi_cell(inner_width, 5.8, _decision_report_pdf_text(body))

            end_y = self.get_y() + 4
            self.set_draw_color(*accent)
            self.set_line_width(1.2)
            self.line(x, start_y + 1, x, end_y - 1)
            self.set_draw_color(*border)
            self.set_line_width(0.4)
            self.line(inner_x, end_y, x + width, end_y)
            self.set_y(end_y + 2)

        def timeline_checkpoint(self, node: dict, *, accent: tuple[int, int, int]):
            if not isinstance(node, dict):
                return
            title = _decision_report_text(node.get("time"), default="节点")
            detail_parts = [
                f"外部变化：{_decision_report_text(node.get('external_state'), default='暂无外部变化')}",
            ]
            if node.get("inner_feeling"):
                detail_parts.append(f"当下感受：{_decision_report_text(node.get('inner_feeling'))}")
            if node.get("key_action"):
                detail_parts.append(f"关键动作：{_decision_report_text(node.get('key_action'))}")
            if node.get("signal"):
                detail_parts.append(f"判断信号：{_decision_report_text(node.get('signal'))}")
            self.narrative_panel(
                title=title,
                body="\n".join(detail_parts),
                fill=(249, 250, 252),
                border=(230, 234, 240),
                accent=accent,
            )

        def roadmap_steps(self, title: str, steps: list[str], *, accent: tuple[int, int, int]):
            if not steps:
                return
            self.section_title(title)
            for idx, step in enumerate(steps, start=1):
                self.process_entry(
                    title=f"{idx:02d} · {_decision_report_text(step)}",
                    meta="行动地图",
                )

        def _compare_metric_tile(
            self,
            x: float,
            y: float,
            w: float,
            *,
            title: str,
            value: int,
            accent: tuple[int, int, int],
        ) -> float:
            h = 18
            inner_w = max(w - 8, 1)
            self.set_draw_color(226, 230, 236)
            self.rect(x, y, w, h)
            self.set_draw_color(*accent)
            self.set_line_width(1.2)
            self.line(x, y + 1, x, y + h - 1)
            self.set_xy(x + 4, y + 3)
            self.set_font("STHeiti", "B", 10)
            self.set_text_color(50, 58, 78)
            self.multi_cell(inner_w, 5.2, _decision_report_pdf_text(title))
            self.set_xy(x + 4, y + 9.8)
            self.set_font("STHeiti", "B", 12)
            self.set_text_color(*accent)
            self.cell(inner_w, 5.4, f"{max(min(int(value), 100), 0)}%")
            bar_x = x + 24
            bar_y = y + h - 5.2
            bar_w = max(w - 30, 8)
            self.set_fill_color(238, 241, 246)
            self.rect(bar_x, bar_y, bar_w, 2.6, "F")
            self.set_fill_color(*accent)
            self.rect(bar_x, bar_y, bar_w * max(min(int(value), 100), 0) / 100, 2.6, "F")
            return y + h

        def compare_meter_row(
            self,
            *,
            label: str,
            left_title: str,
            left_value: int,
            right_title: str,
            right_value: int,
            left_accent: tuple[int, int, int] = (86, 128, 196),
            right_accent: tuple[int, int, int] = (214, 180, 106),
            note: str = "",
        ):
            self.ensure_room(32 if note else 26)
            self.subsection_title(label)
            if note:
                self.muted_text(note, indent=2)
            top_y = self.get_y() + 1
            total_w = self.w - self.l_margin - self.r_margin
            gap = 6
            col_w = (total_w - gap) / 2
            left_bottom = self._compare_metric_tile(
                self.l_margin,
                top_y,
                col_w,
                title=left_title,
                value=left_value,
                accent=left_accent,
            )
            right_bottom = self._compare_metric_tile(
                self.l_margin + col_w + gap,
                top_y,
                col_w,
                title=right_title,
                value=right_value,
                accent=right_accent,
            )
            self.set_y(max(left_bottom, right_bottom) + 3)

        def _compare_column_box(
            self,
            x: float,
            y: float,
            w: float,
            *,
            title: str,
            lines: list[str],
            accent: tuple[int, int, int],
        ) -> float:
            self.set_xy(x + 4, y + 4)
            self.set_font("STHeiti", "B", 10.5)
            self.set_text_color(50, 58, 78)
            self.multi_cell(max(w - 8, 1), 5.6, _decision_report_pdf_text(title))
            self.set_font("STHeiti", "", 9)
            self.set_text_color(76, 82, 96)
            for line in lines[:6]:
                self.set_x(x + 4)
                self.multi_cell(max(w - 8, 1), 4.8, _decision_report_pdf_text(line))
            bottom = self.get_y() + 3
            self.set_draw_color(228, 232, 238)
            self.rect(x + 1, y, max(w - 1, 1), max(bottom - y, 8))
            self.set_draw_color(*accent)
            self.set_line_width(1.2)
            self.line(x, y + 1, x, bottom - 1)
            return bottom

        def compare_columns(
            self,
            *,
            title: str,
            left_title: str,
            left_lines: list[str],
            right_title: str,
            right_lines: list[str],
            left_accent: tuple[int, int, int] = (86, 128, 196),
            right_accent: tuple[int, int, int] = (214, 180, 106),
            meta: str = "",
        ):
            line_count = max(len(left_lines or []), len(right_lines or []), 1)
            estimated_height = 22 + (5.2 if meta else 0) + 13 + line_count * 5.0
            self.ensure_room(max(estimated_height, 42))
            self.subsection_title(title)
            if meta:
                self.muted_text(meta, indent=2)
            top_y = self.get_y() + 1
            total_w = self.w - self.l_margin - self.r_margin
            gap = 6
            col_w = (total_w - gap) / 2
            left_bottom = self._compare_column_box(
                self.l_margin,
                top_y,
                col_w,
                title=left_title,
                lines=left_lines,
                accent=left_accent,
            )
            right_bottom = self._compare_column_box(
                self.l_margin + col_w + gap,
                top_y,
                col_w,
                title=right_title,
                lines=right_lines,
                accent=right_accent,
            )
            self.set_y(max(left_bottom, right_bottom) + 3)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_font("STHeiti", "", font_path)
    pdf.add_font("STHeiti", "B", font_path)
    pdf.add_font("STHeiti", "I", font_path)

    pdf.add_page()
    pdf.set_fill_color(8, 14, 24)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.cosmic_background(
        seed_text=safe_question,
        left=14,
        top=18,
        right=196,
        bottom=210,
        star_count=54,
        accent=(214, 180, 106),
        secondary=(116, 154, 214),
    )
    pdf.set_draw_color(34, 54, 86)
    pdf.set_line_width(0.45)
    pdf.ellipse(14, 24, 182, 166, style="D")
    pdf.ellipse(28, 38, 154, 138, style="D")
    pdf.set_draw_color(214, 180, 106)
    pdf.set_line_width(1.4)
    pdf.line(28, 38, 74, 38)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("STHeiti", "B", 24)
    pdf.set_y(52)
    pdf.cell(0, 14, "认知拉格朗日点", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("STHeiti", "", 14)
    pdf.set_text_color(190, 196, 212)
    pdf.cell(0, 10, "Decision Journey Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("STHeiti", "B", 12)
    pdf.set_text_color(243, 214, 133)
    pdf.cell(0, 8, "本次问题", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("STHeiti", "", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(24)
    pdf.multi_cell(162, 8, safe_question, align="C")
    pdf.ln(14)
    pdf.set_font("STHeiti", "", 10)
    pdf.set_text_color(150, 160, 178)
    pdf.cell(0, 7, f"生成时间: {generated_at}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"思考档位: {tier_label}", align="C", new_x="LMARGIN", new_y="NEXT")
    if tier_tagline and tier_tagline != "未提供":
        pdf.cell(0, 7, tier_tagline, align="C", new_x="LMARGIN", new_y="NEXT")
    if metadata.get("model"):
        pdf.cell(0, 7, f"模型: {metadata['model']}", align="C", new_x="LMARGIN", new_y="NEXT")
    cover_outcome = (
        _decision_report_text(decision_result.get("summary"), default="")
        or _decision_report_text(detection_result.get("summary"), default="")
        or _decision_report_text(engineb_session.get("recommendation"), default="")
        or "当前报告主要整理了这次推演已经完成的决策阶段。"
    )
    pdf.ln(14)
    pdf.set_x(26)
    pdf.multi_cell(158, 6.4, _decision_report_pdf_text(cover_outcome), align="C")

    pdf.metric_tile(24, 186, 50, 26, label="第一幕状态", value=_decision_report_detect_status_label(detection_status))
    cover_stage_label = "第三幕状态" if has_simulator else "第二幕阶段"
    cover_stage_value = _decision_report_phase_label(engineb_phase)
    pdf.metric_tile(80, 186, 50, 26, label=cover_stage_label, value=cover_stage_value)
    pdf.metric_tile(136, 186, 50, 26, label="报告深度", value=f"{len(report_outline)} 章")

    pdf.ln(58)
    pdf.set_font("STHeiti", "", 9)
    pdf.set_text_color(120, 128, 140)
    pdf.cell(0, 6, "本报告根据当前检测、决策突破与未来模拟结果自动整理。", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    pdf.chapter_title("目录")
    pdf.muted_text("这份报告按真实决策流程组织，先看结论，再看过程，最后回到完整日志与轨迹。", indent=2)
    for idx, (title, desc) in enumerate(report_outline, start=1):
        pdf.process_entry(
            title=title,
            detail=desc,
            meta=f"章节 {idx:02d}",
        )

    pdf.add_page()
    pdf.chapter_title("一、报告摘要")
    journey_summary = []
    if detection_job:
        if detection_status == "completed" and detection_result.get("is_lagrange_point") is True:
            journey_summary.append("检测结论：通过三层筛子，当前问题被确认为认知拉格朗日点。")
        elif detection_status == "completed":
            failed_at = _decision_report_text(detection_result.get("failed_at"), default="某个筛子阶段")
            journey_summary.append(f"检测结论：问题在 {failed_at} 被淘汰，更像可拆解的困难问题。")
        elif detection_status == "failed":
            journey_summary.append("检测结论：真实检测已经启动，但本次没有顺利跑完。")
        else:
            journey_summary.append(f"检测状态：{detection_status}。")
    if engineb_session:
        if engineb_session.get("recommendation"):
            journey_summary.append(f"Engine B 建议：{_decision_report_text(engineb_session.get('recommendation'))}")
        else:
            journey_summary.append(f"Engine B 当前阶段：{_decision_report_phase_label(engineb_phase)}")
    if has_simulator:
        output = engineb_session.get("simulator_output") or {}
        if output.get("final_insight"):
            journey_summary.append(f"未来模拟结论：{_decision_report_text(output.get('final_insight'))}")
    if not journey_summary:
        journey_summary.append("当前还没有足够结果，报告主要记录了已完成的流程信息。")
    pdf.bullet_list(journey_summary)

    summary_focus = (
        _decision_report_text(engineb_session.get("recommendation"), default="")
        or _decision_report_text(decision_result.get("summary"), default="")
        or _decision_report_text(detection_result.get("summary"), default="")
    )
    summary_action = _decision_report_text(engineb_session.get("action_plan"), default="")
    summary_insight = _decision_report_text(simulator_output.get("final_insight"), default="") if has_simulator else ""
    if summary_focus or summary_action or summary_insight:
        pdf.ensure_room(54)
        pdf.divider()
        pdf.section_title("先看这三个结论")
        card_y = pdf.get_y() + 2
        pdf.summary_card(
            12,
            card_y,
            58,
            30,
            title="建议方向",
            lines=[summary_focus or "当前还没有稳定结论", summary_action or "先把最影响结果的变量补齐。"],
            accent=(92, 126, 196),
        )
        pdf.summary_card(
            76,
            card_y,
            58,
            30,
            title="马上行动",
            lines=[summary_action or "先做一个低成本验证动作", "别先把自己锁死在唯一答案上。"],
            accent=(214, 180, 106),
        )
        pdf.summary_card(
            140,
            card_y,
            58,
            30,
            title="一句提醒",
            lines=[summary_insight or "先看最坏情况你扛不扛得住，再看最好情况有多诱人。"],
            accent=(194, 112, 104),
        )
        pdf.set_y(card_y + 36)

    if has_simulator:
        pdf.ensure_room(66)
        pdf.divider()
        pdf.section_title("未来推演快照")
        snapshot_y = pdf.get_y() + 2
        pdf.summary_card(
            12,
            snapshot_y,
            58,
            32,
            title=summary_choice_a.get("name") or "选项 A",
            lines=[f"顺风 {summary_choice_a.get('tailwind', 0)}% / 平稳 {summary_choice_a.get('steady', 0)}% / 逆风 {summary_choice_a.get('headwind', 0)}%"],
            accent=(86, 128, 196),
        )
        pdf.summary_card(
            76,
            snapshot_y,
            58,
            32,
            title=summary_choice_b.get("name") or "选项 B",
            lines=[f"顺风 {summary_choice_b.get('tailwind', 0)}% / 平稳 {summary_choice_b.get('steady', 0)}% / 逆风 {summary_choice_b.get('headwind', 0)}%"],
            accent=(214, 180, 106),
        )
        pdf.summary_card(
            140,
            snapshot_y,
            58,
            32,
            title="当前更稳",
            lines=[safer_choice_name or "尚未形成", safer_choice_reason or "这次重点仍然是先看最坏情况的承受力。"],
            accent=(90, 132, 198),
        )
        pdf.set_y(snapshot_y + 38)

        if monte_carlo:
            monte_smooth = monte_carlo.get("smooth_prob") if isinstance(monte_carlo.get("smooth_prob"), dict) else {}
            monte_ci = monte_carlo.get("confidence_interval") if isinstance(monte_carlo.get("confidence_interval"), dict) else {}
            monte_heatmap = monte_carlo.get("disagreement_heatmap") if isinstance(monte_carlo.get("disagreement_heatmap"), list) else []
            monte_lines = [
                (
                    f"采样 {monte_carlo.get('sample_count', '--')} 次 / "
                    f"代理 {monte_carlo.get('persona_count', '--')} 个 / "
                    f"每分支 {monte_carlo.get('agents_per_branch', '--')} 代理"
                ),
                (
                    "平滑分布："
                    f"顺风 {monte_smooth.get('optimistic', '--')}% / "
                    f"平稳 {monte_smooth.get('baseline', '--')}% / "
                    f"逆风 {monte_smooth.get('pessimistic', '--')}%"
                ),
            ]
            ci_parts = []
            for key, label in (("optimistic", "顺风"), ("baseline", "平稳"), ("pessimistic", "逆风")):
                item = monte_ci.get(key)
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    ci_parts.append(f"{label} {item[0]}%-{item[1]}%")
                elif isinstance(item, dict):
                    ci_parts.append(f"{label} {item.get('low', '--')}%-{item.get('high', '--')}%")
            if ci_parts:
                monte_lines.append("置信区间：" + "；".join(ci_parts))
            heat_parts = []
            for item in monte_heatmap[:5]:
                if isinstance(item, dict):
                    heat_parts.append(f"{item.get('label') or item.get('factor') or item.get('key') or '变量'} {item.get('avg_score', item.get('disagreement', '--'))}")
            if heat_parts:
                monte_lines.append("关键分歧热区：" + "；".join(heat_parts))
            monte_lines.append(
                f"LLM 委员会：请求 {monte_carlo.get('llm_panels_requested', 0)} 个面板，"
                f"发起 {monte_carlo.get('llm_calls_attempted', monte_carlo.get('actual_llm_calls', 0))} 次，"
                f"成功 {monte_carlo.get('actual_llm_calls', 0)} 次。"
            )
            if monte_carlo.get("llm_collision_summary"):
                monte_lines.append("合议结论：" + _decision_report_text(monte_carlo.get("llm_collision_summary")))
            if monte_carlo.get("client_report_memo"):
                monte_lines.append("客户摘要：" + _decision_report_text(monte_carlo.get("client_report_memo")))
            for item in (monte_carlo.get("critical_disagreements") if isinstance(monte_carlo.get("critical_disagreements"), list) else [])[:4]:
                monte_lines.append("核心分歧：" + _decision_report_text(item))
            for item in (monte_carlo.get("decision_guardrails") if isinstance(monte_carlo.get("decision_guardrails"), list) else [])[:4]:
                monte_lines.append("决策护栏：" + _decision_report_text(item))
            for item in (monte_carlo.get("premium_report_sections") if isinstance(monte_carlo.get("premium_report_sections"), list) else [])[:3]:
                monte_lines.append("报告段落：" + _decision_report_text(item))
            pdf.narrative_panel(
                title="Ultra 决策委员会 · Monte Carlo 合议摘要",
                body="\n".join(_decision_report_text(line) for line in monte_lines),
                meta="基于第三幕 A/B 时间线、Monte Carlo 分支采样与 LLM 委员会合议形成，不代表确定预测。",
                accent=(112, 219, 197),
            )

        survival = simulator_output.get("worst_case_survival_plan") if isinstance(simulator_output.get("worst_case_survival_plan"), dict) else {}
        if survival:
            survival_lines = []
            if survival.get("trigger"):
                survival_lines.append(f"触发：{_decision_report_text(survival.get('trigger'))}")
            if survival.get("day_1"):
                survival_lines.append(f"第1天：{_decision_report_text(survival.get('day_1'))}")
            if survival.get("week_1"):
                survival_lines.append(f"第1周：{_decision_report_text(survival.get('week_1'))}")
            if survival.get("safety_runway"):
                survival_lines.append(f"安全垫：{_decision_report_text(survival.get('safety_runway'))}")
            pdf.narrative_panel(
                title="最坏情况保护卡",
                body="\n".join(survival_lines),
                meta="如果你只先看一段，请先看这里。",
                accent=(194, 112, 104),
            )
        if simulator_warning:
            pdf.narrative_panel(
                title="模拟质量提醒",
                body=simulator_warning,
                meta="第三幕完整性提示",
                accent=(184, 142, 82),
            )

    if bias_lines or value_lines or alternative_lines or signal_lines:
        pdf.ensure_room(64)
        pdf.divider()
        pdf.compare_columns(
            title="这次判断里新增的关键信息层",
            left_title="价值锚点与偏差提醒",
            left_lines=(value_lines + bias_lines)[:6] or ["当前还没有明确的价值锚点。"],
            right_title="第三条路与外部参照",
            right_lines=(alternative_lines + signal_lines)[:6] or ["当前还没有可展示的第三条路或外部声音。"],
            meta="把真正影响判断的信息前置展示，尽量不要把页面留给空白占位。",
        )

    if decision_data:
        pdf.ensure_room(76)
        pdf.divider()
        pdf.section_title("任务总览")
        if decision_data.get("decision_id"):
            pdf.kv("任务编号", _decision_report_text(decision_data.get("decision_id")))
        pdf.kv("思考档位", tier_label)
        if decision_created_at:
            pdf.kv("开始时间", decision_created_at)
        if decision_completed_at:
            pdf.kv("完成时间", decision_completed_at)
        elif decision_updated_at:
            pdf.kv("最近更新时间", decision_updated_at)
        if decision_status:
            pdf.kv("当前状态", decision_status)
        if decision_phase:
            pdf.kv("当前阶段", decision_phase)
        if decision_result.get("summary"):
            pdf.kv("最终结论", _decision_report_text(decision_result.get("summary")))

        overview_steps = [
            "开始：用户提交问题，并选择思考深度。",
        ]
        if detection_job:
            overview_steps.append("第一幕：系统做结构识别与三层筛子检测，判断问题更像无解平衡还是可拆解决策。")
        if engineb_session:
            overview_steps.append("第二幕：系统进入卡点诊断、补信息、补框架、补经验与力量重估。")
        if has_simulator:
            overview_steps.append("第三幕：系统模拟两条路的未来时间线，并给出行动地图、岔路口与最坏情况预案。")
        if decision_result.get("summary"):
            overview_steps.append(f"收束：{_decision_report_text(decision_result.get('summary'))}")
        pdf.subsection_title("从开始到最终")
        pdf.bullet_list(overview_steps, indent=2)

    if detection_job:
        pdf.ensure_room(54)
        pdf.divider()
        pdf.section_title("检测概览")
        pdf.kv("任务编号", _decision_report_text(detection_job.get("job_id")))
        pdf.kv("显示问题", _decision_report_text(detection_job.get("question") or detection_job.get("input_question") or safe_question))
        pdf.kv("检测模式", _decision_report_text(detection_job.get("mode"), default="initial"))
        pdf.kv("任务状态", detection_status)
        if detection_job.get("status_text"):
            pdf.kv("状态说明", _decision_report_text(detection_job.get("status_text")))

    if engineb_session:
        pdf.ensure_room(66)
        pdf.divider()
        pdf.section_title("Engine B 概览")
        pdf.kv("会话编号", _decision_report_text(engineb_session.get("session_id")))
        pdf.kv("当前阶段", _decision_report_phase_label(engineb_phase))
        blockages = _decision_report_lines(engineb_session.get("diagnosed_blockages") or [])
        if blockages:
            pdf.kv("诊断卡点", " / ".join(blockages))
        if engineb_session.get("updated_pro_total") or engineb_session.get("updated_con_total"):
            pdf.kv(
                "补全后力量",
                f"正方 {_decision_report_text(engineb_session.get('updated_pro_total'), default='0')} / "
                f"反方 {_decision_report_text(engineb_session.get('updated_con_total'), default='0')}",
            )

    if detection_job:
        pdf.add_page()
        pdf.chapter_title("二、第一幕 · 结构检测")
        analysis = detection_job.get("analysis") if isinstance(detection_job.get("analysis"), dict) else {}
        tensions = analysis.get("tensions") if isinstance(analysis.get("tensions"), list) else []
        if tensions:
            pdf.section_title("核心张力")
            for idx, tension in enumerate(tensions, start=1):
                if not isinstance(tension, dict):
                    continue
                pdf.kv(
                    f"张力 {idx}",
                    f"{_decision_report_text(tension.get('pro'))} vs {_decision_report_text(tension.get('con'))}"
                )
        classifications = analysis.get("classifications") if isinstance(analysis.get("classifications"), dict) else {}
        if classifications:
            pdf.section_title("结构预判")
            pdf.kv(
                "分类概率",
                f"两难选择 {classifications.get('dilemma', '--')} / "
                f"信息不足 {classifications.get('info_gap', '--')} / "
                f"拉格朗日点 {classifications.get('clp', '--')}"
            )
            if analysis.get("balance_rationale"):
                pdf.kv("看似平衡的原因", _decision_report_text(analysis.get("balance_rationale")))
            if analysis.get("analysis_summary"):
                pdf.kv("结构判断", _decision_report_text(analysis.get("analysis_summary")))

        filters = detection_job.get("filters") if isinstance(detection_job.get("filters"), dict) else {}
        detect_logs = _decision_report_lines(detection_job.get("logs") or [])
        if filters:
            pdf.section_title("三层筛子")
            filter_labels = {
                "filter1": "筛子1 · 信息注入测试",
                "filter2": "筛子2 · 多框架稳定性测试",
                "filter3": "筛子3 · 重述稳定性测试",
            }
            for key in ("filter1", "filter2", "filter3"):
                data = filters.get(key)
                if not isinstance(data, dict):
                    continue
                status = _decision_report_text(data.get("status"), default="pending")
                passed = data.get("passed")
                if passed is True:
                    status = "passed"
                elif passed is False:
                    status = "failed"
                pdf.kv(filter_labels.get(key, key), f"{status} | {_decision_report_text(data.get('summary'))}")
                detail_lines = _decision_report_lines(data.get("details") or [])
                if detail_lines:
                    pdf.bullet_list(detail_lines[:6], indent=6)

        if detection_status == "failed":
            pdf.section_title("失败说明")
            pdf.body_text(_decision_report_text(detection_job.get("error"), default="检测未返回具体错误信息。"))

        if detection_result:
            pdf.section_title("最终判定")
            pdf.body_text(_decision_report_text(detection_result.get("summary")))
            if detection_result.get("is_lagrange_point") is True:
                clp = detection_result.get("clp") if isinstance(detection_result.get("clp"), dict) else {}
                pdf.kv("确认点编号", _decision_report_text(clp.get("id"), default="CLP"))
                pdf.kv("平衡精度", f"{_decision_report_text(clp.get('balance_precision'), default='--')}%")
                if clp.get("balance_analysis"):
                    pdf.kv("平衡分析", _decision_report_text(clp.get("balance_analysis")))
                pro_forces = clp.get("pro_forces") if isinstance(clp.get("pro_forces"), list) else []
                con_forces = clp.get("con_forces") if isinstance(clp.get("con_forces"), list) else []
                if pro_forces:
                    pdf.section_title("正方力量")
                    for force in pro_forces[:5]:
                        if not isinstance(force, dict):
                            continue
                        pdf.kv(
                            _decision_report_text(force.get("name"), default="未命名力量"),
                            f"强度 {force.get('strength', '--')} | {_decision_report_text(force.get('best_argument'))}",
                            indent=4,
                        )
                if con_forces:
                    pdf.section_title("反方力量")
                    for force in con_forces[:5]:
                        if not isinstance(force, dict):
                            continue
                        pdf.kv(
                            _decision_report_text(force.get("name"), default="未命名力量"),
                            f"强度 {force.get('strength', '--')} | {_decision_report_text(force.get('best_argument'))}",
                            indent=4,
                        )

        if detect_logs:
            pdf.section_title("第一幕处理记录")
            pdf.bullet_list(detect_logs[:24], indent=2)

    if engineb_session:
        pdf.add_page()
        pdf.chapter_title("三、第二幕 · 决策突破")
        answers = engineb_session.get("diagnosis_answers") if isinstance(engineb_session.get("diagnosis_answers"), dict) else {}
        questions = engineb_session.get("diagnosis_questions") if isinstance(engineb_session.get("diagnosis_questions"), list) else []
        if questions:
            pdf.section_title("B1 · 诊断追问")
            for idx, item in enumerate(questions, start=1):
                if not isinstance(item, dict):
                    continue
                answer = answers.get(item.get("id", ""))
                pdf.kv(f"Q{idx}", _decision_report_text(item.get("question_text")))
                if answer:
                    pdf.kv("回答", _decision_report_text(answer), indent=6)
                pdf.ensure_space()

        info_items = engineb_session.get("missing_info_items") if isinstance(engineb_session.get("missing_info_items"), list) else []
        if info_items:
            pdf.section_title("B2 · 需要补齐的信息")
            for item in info_items[:6]:
                if not isinstance(item, dict):
                    continue
                pdf.kv(_decision_report_text(item.get("title"), default="信息项"), _decision_report_text(item.get("content")))
                if item.get("why_critical"):
                    pdf.kv("为什么关键", _decision_report_text(item.get("why_critical")), indent=6)
                if item.get("source_suggestion"):
                    pdf.kv("建议获取方式", _decision_report_text(item.get("source_suggestion")), indent=6)
                pdf.ensure_space()

        frames = engineb_session.get("cognitive_frames") if isinstance(engineb_session.get("cognitive_frames"), list) else []
        if frames:
            pdf.section_title("B3 · 新的判断框架")
            for frame in frames[:5]:
                if not isinstance(frame, dict):
                    continue
                pdf.kv(_decision_report_text(frame.get("title"), default="未命名框架"), _decision_report_text(frame.get("core_insight")))
                if frame.get("why_it_matters"):
                    pdf.kv("为什么有用", _decision_report_text(frame.get("why_it_matters")), indent=6)
                if frame.get("reframe_question"):
                    pdf.kv("换个问法", _decision_report_text(frame.get("reframe_question")), indent=6)
                if frame.get("try_now"):
                    pdf.kv("现在就能试", _decision_report_text(frame.get("try_now")), indent=6)
                pdf.ensure_space()

        cases = engineb_session.get("experience_cases") if isinstance(engineb_session.get("experience_cases"), list) else []
        if cases:
            pdf.section_title("B4 · 经验对照")
            for item in cases[:4]:
                if not isinstance(item, dict):
                    continue
                pdf.kv(_decision_report_text(item.get("title"), default="案例"), _decision_report_text(item.get("starting_point")))
                if item.get("choice_made"):
                    pdf.kv("当时怎么选", _decision_report_text(item.get("choice_made")), indent=6)
                if item.get("outcome"):
                    pdf.kv("后来发生了什么", _decision_report_text(item.get("outcome")), indent=6)
                if item.get("lesson"):
                    pdf.kv("真正提醒", _decision_report_text(item.get("lesson")), indent=6)
                if item.get("transfer_hint"):
                    pdf.kv("对你的借鉴", _decision_report_text(item.get("transfer_hint")), indent=6)
                pdf.ensure_space()

        emotional = engineb_session.get("emotional_insight") if isinstance(engineb_session.get("emotional_insight"), dict) else {}
        dominant_emotions = emotional.get("dominant_emotions") if isinstance(emotional.get("dominant_emotions"), list) else []
        if dominant_emotions or emotional:
            pdf.section_title("B5 · 情绪镜像")
            for item in dominant_emotions[:6]:
                if not isinstance(item, dict):
                    continue
                emotion = _decision_report_text(item.get("emotion"), default="情绪")
                evidence = _decision_report_text(item.get("evidence"))
                intensity = _decision_report_text(item.get("intensity"), default="")
                prefix = f"{emotion} ({intensity})" if intensity else emotion
                pdf.kv(prefix, evidence)
            if emotional.get("hidden_need"):
                pdf.kv("它在保护什么", _decision_report_text(emotional.get("hidden_need")))
            if emotional.get("decision_distortion"):
                pdf.kv("可能带来的偏差", _decision_report_text(emotional.get("decision_distortion")))
            if emotional.get("grounding_prompt"):
                pdf.kv("稳住自己的提醒", _decision_report_text(emotional.get("grounding_prompt")))
            if emotional.get("gentle_reminder"):
                pdf.kv("镜像结论", _decision_report_text(emotional.get("gentle_reminder")))

        if value_lines or bias_lines:
            pdf.section_title("B5+ · 价值锚点与偏差提醒")
            pdf.bullet_list((value_lines + bias_lines)[:8], indent=2)

        if alternative_lines:
            pdf.section_title("B5.5 · 第三条路")
            pdf.bullet_list(alternative_lines[:6], indent=2)

        if signal_lines:
            pdf.section_title("B2+ · 外部声音快照")
            pdf.muted_text("以下是本地整理的外部声音快照，不是请求时实时联网抓取。", indent=2)
            pdf.bullet_list(signal_lines[:6], indent=2)

        if engineb_session.get("recommendation") or engineb_session.get("action_plan") or engineb_session.get("reasoning"):
            pdf.section_title("C1 · 最终建议")
            pdf.kv(
                "力量变化",
                f"原始 {engineb_session.get('original_pro_total', '--')} / {engineb_session.get('original_con_total', '--')} -> "
                f"补全后 {engineb_session.get('updated_pro_total', '--')} / {engineb_session.get('updated_con_total', '--')}"
            )
            if engineb_session.get("recommendation"):
                pdf.kv("建议方向", _decision_report_text(engineb_session.get("recommendation")))
            if engineb_session.get("action_plan"):
                pdf.kv("行动方案", _decision_report_text(engineb_session.get("action_plan")))
            if engineb_session.get("reasoning"):
                pdf.kv("推理过程", _decision_report_text(engineb_session.get("reasoning")))

        recheck = engineb_session.get("recheck") if isinstance(engineb_session.get("recheck"), dict) else {}
        if recheck:
            pdf.section_title("A ↔ B 闭环")
            pdf.kv("二次检测状态", _decision_report_text(recheck.get("status"), default="idle"))
            if recheck.get("reason"):
                pdf.kv("触发原因", _decision_report_text(recheck.get("reason")))
            if recheck.get("error"):
                pdf.kv("异常说明", _decision_report_text(recheck.get("error")))

    if simulator_output:
        pdf.add_page()
        pdf.chapter_title("四、第三幕 · 未来选择模拟器")
        user_params = simulator_output.get("user_params") if isinstance(simulator_output.get("user_params"), dict) else {}
        choice_a = simulator_output.get("choice_a") if isinstance(simulator_output.get("choice_a"), dict) else {}
        choice_b = simulator_output.get("choice_b") if isinstance(simulator_output.get("choice_b"), dict) else {}
        choice_a_name = _decision_report_text(choice_a.get("choice_name"), default="选项A")
        choice_b_name = _decision_report_text(choice_b.get("choice_name"), default="选项B")
        summary_parts = []
        if simulator_output.get("comparison_summary"):
            summary_parts.append(_decision_report_text(simulator_output.get("comparison_summary")))
        if simulator_output.get("final_insight"):
            summary_parts.append(f"最终洞察：{_decision_report_text(simulator_output.get('final_insight'))}")
        pdf.narrative_panel(
            title="未来预演给出的核心结论",
            body="\n\n".join(part for part in summary_parts if part).strip(),
            meta="第三幕总览",
            accent=(90, 132, 198),
        )
        param_rows, pending_params = _decision_report_sim_param_rows(user_params)
        if param_rows or pending_params:
            pdf.section_title("本轮模拟依据")
            for label, value in param_rows:
                pdf.kv(label, value)
            if pending_params:
                pdf.muted_text(
                    f"本轮仍待确认：{'、'.join(pending_params)}。这些变量缺失时，第三幕会更保守，也更容易出现两条路写得太像的情况。",
                    indent=2,
                )

        survival = simulator_output.get("worst_case_survival_plan") if isinstance(simulator_output.get("worst_case_survival_plan"), dict) else {}
        if survival:
            survival_lines = []
            if survival.get("trigger"):
                survival_lines.append(f"触发条件：{_decision_report_text(survival.get('trigger'))}")
            if survival.get("day_1"):
                survival_lines.append(f"第1天：{_decision_report_text(survival.get('day_1'))}")
            if survival.get("week_1"):
                survival_lines.append(f"第1周：{_decision_report_text(survival.get('week_1'))}")
            if survival.get("month_1"):
                survival_lines.append(f"第1个月：{_decision_report_text(survival.get('month_1'))}")
            if survival.get("safety_runway"):
                survival_lines.append(f"安全垫：{_decision_report_text(survival.get('safety_runway'))}")
            pdf.narrative_panel(
                title="最坏情况保护卡",
                body="\n".join(survival_lines),
                meta="先看最差情况你能不能活下来，再决定要不要走这条路。",
                accent=(194, 112, 104),
            )

        pdf.section_title("A / B 快速对比")
        pdf.radar_compare(
            title="后悔与走势雷达",
            metrics=_decision_report_radar_metrics(simulator_output),
            left_title=choice_a_name,
            right_title=choice_b_name,
            left_color=(86, 128, 196),
            right_color=(214, 180, 106),
            meta="同一组指标下，把两条路的顺风势能、平稳承接、抗逆风和后悔可控度放在一起看。",
        )
        pdf.compare_meter_row(
            label="顺风概率",
            left_title=choice_a_name,
            left_value=summary_choice_a.get("tailwind", 0),
            right_title=choice_b_name,
            right_value=summary_choice_b.get("tailwind", 0),
        )
        pdf.compare_meter_row(
            label="平稳概率",
            left_title=choice_a_name,
            left_value=summary_choice_a.get("steady", 0),
            right_title=choice_b_name,
            right_value=summary_choice_b.get("steady", 0),
        )
        pdf.compare_meter_row(
            label="逆风概率",
            left_title=choice_a_name,
            left_value=summary_choice_a.get("headwind", 0),
            right_title=choice_b_name,
            right_value=summary_choice_b.get("headwind", 0),
            note=safer_choice_reason,
        )

        for scenario in ("tailwind", "steady", "headwind"):
            left_lines = _decision_report_timeline_digest(choice_a, scenario)
            right_lines = _decision_report_timeline_digest(choice_b, scenario)
            if not left_lines and not right_lines:
                continue
            pdf.compare_columns(
                title=f"{_scenario_label(scenario)} · 两条路怎么分开",
                left_title=choice_a_name,
                left_lines=left_lines or ["这一侧还没有足够时间线数据。"],
                right_title=choice_b_name,
                right_lines=right_lines or ["这一侧还没有足够时间线数据。"],
                meta="先看 1 周 / 3 个月 / 1 年的关键差异，再决定你更想承受哪种代价。",
            )

        if simulator_warning:
            pdf.narrative_panel(
                title="模拟质量提醒",
                body=simulator_warning,
                meta="如果你觉得两条路写得太像，这通常不是排版问题，而是关键信息还没补够。",
                accent=(184, 142, 82),
            )

        def _render_choice(choice_key: str, fallback_label: str, accent: tuple[int, int, int]):
            choice = simulator_output.get(choice_key)
            if not isinstance(choice, dict):
                return
            pdf.add_page()
            choice_name = _decision_report_text(choice.get("choice_name"), default=fallback_label)
            support_lines = _decision_report_lines(
                simulator_output.get("action_map_a") if choice_key == "choice_a" else simulator_output.get("action_map_b")
            )
            pdf.chapter_title(f"四、第三幕 · {choice_name}")
            distribution = choice.get("probability_distribution") if isinstance(choice.get("probability_distribution"), dict) else {}
            fallback_mode = _decision_report_text(choice.get("fallback_mode"), default="")
            distribution_lines = []
            for scenario in ("tailwind", "steady", "headwind"):
                bucket = distribution.get(scenario)
                if isinstance(bucket, dict):
                    distribution_lines.append(
                        f"{_scenario_label(scenario)} {_decision_report_text(bucket.get('percent'), default='--')}% · "
                        f"{_decision_report_text(bucket.get('reason'))}"
                    )
            pdf.narrative_panel(
                title=choice_name,
                body="\n".join(distribution_lines),
                meta=f"未来时间线概览{' · ' + fallback_mode if fallback_mode and fallback_mode != '未提供' else ''}",
                accent=accent,
            )
            timelines = choice.get("timelines") if isinstance(choice.get("timelines"), dict) else {}
            rendered_support_panel = False
            ordered_scenarios = ("tailwind", "steady", "headwind")

            def _storyboard_need(node_count: int) -> int:
                row_count = max(1, math.ceil(max(node_count, 1) / 3))
                board_h = 24 + row_count * 28 + max(row_count - 1, 0) * 8 + 8
                return board_h + 24

            for index, scenario in enumerate(ordered_scenarios):
                timeline = timelines.get(scenario)
                if not isinstance(timeline, dict):
                    continue
                bucket = distribution.get(scenario) if isinstance(distribution.get(scenario), dict) else {}
                palette = _decision_report_palette(scenario)
                meta_parts = []
                if bucket.get("percent") not in (None, ""):
                    meta_parts.append(f"概率 {_decision_report_text(bucket.get('percent'))}%")
                if bucket.get("reason"):
                    meta_parts.append(_decision_report_text(bucket.get("reason")))
                nodes = timeline.get("nodes") if isinstance(timeline.get("nodes"), list) else []
                pdf.timeline_storyboard(
                    title=f"{_scenario_label(scenario)} · {_decision_report_text(timeline.get('title'), default='未命名时间线')}",
                    probability=f"{_decision_report_text(bucket.get('percent'), default='--')}%",
                    reason=_decision_report_text(bucket.get("reason") or timeline.get("probability_reason"), default=""),
                    nodes=nodes[:6],
                    accent=palette["accent"],
                    fill=palette["fill"],
                    soft=palette["soft"],
                )

                if rendered_support_panel or not support_lines:
                    continue

                next_timeline = None
                for next_scenario in ordered_scenarios[index + 1:]:
                    candidate = timelines.get(next_scenario)
                    if isinstance(candidate, dict):
                        next_timeline = candidate
                        break
                if not isinstance(next_timeline, dict):
                    continue

                next_nodes = next_timeline.get("nodes") if isinstance(next_timeline.get("nodes"), list) else []
                remaining_room = pdf.h - pdf.b_margin - pdf.get_y()
                if remaining_room <= 48:
                    continue
                if remaining_room >= _storyboard_need(len(next_nodes[:6])):
                    continue

                pdf.narrative_panel(
                    title="如果你真选这条路，先动哪几步",
                    body="\n".join(support_lines[:3]),
                    meta="本页补充",
                    accent=accent,
                )
                rendered_support_panel = True

        _render_choice("choice_a", "选项A", (86, 128, 196))
        _render_choice("choice_b", "选项B", (214, 180, 106))

        action_map_a = _decision_report_lines(simulator_output.get("action_map_a") or [])
        action_map_b = _decision_report_lines(simulator_output.get("action_map_b") or [])
        crossroads = simulator_output.get("crossroads") if isinstance(simulator_output.get("crossroads"), list) else []
        milestones = simulator_output.get("milestones") if isinstance(simulator_output.get("milestones"), list) else []
        if action_map_a or action_map_b or crossroads or milestones or survival:
            pdf.ensure_room(110)
            pdf.chapter_title("四、第三幕 · 行动地图与风险预案")
            if action_map_a or action_map_b:
                pdf.compare_columns(
                    title="未来 12 个月行动地图",
                    left_title=choice_a_name,
                    left_lines=action_map_a[:6] or ["这一侧还没有生成行动地图。"],
                    right_title=choice_b_name,
                    right_lines=action_map_b[:6] or ["这一侧还没有生成行动地图。"],
                    meta="这页不是要你现在拍板，而是让你看到两条路分别要付出什么。",
                )

        if crossroads:
            pdf.section_title("关键岔路口")
            for item in crossroads[:6]:
                if not isinstance(item, dict):
                    continue
                detail_lines = [_decision_report_text(item.get("description"))]
                signals = item.get("signals") if isinstance(item.get("signals"), dict) else {}
                for signal_key, label in (("green", "顺风信号"), ("yellow", "平稳信号"), ("red", "逆风信号")):
                    signal_data = signals.get(signal_key)
                    if isinstance(signal_data, dict) and (signal_data.get("signal") or signal_data.get("action")):
                        detail_lines.append(
                            f"{label}：{_decision_report_text(signal_data.get('signal'))} / {_decision_report_text(signal_data.get('action'))}"
                        )
                if item.get("reversal_cost"):
                    detail_lines.append(f"回撤代价：{_decision_report_text(item.get('reversal_cost'))}")
                pdf.narrative_panel(
                    title=_decision_report_text(item.get("time"), default="关键节点"),
                    body="\n".join(detail_lines),
                    meta="红黄绿信号控制",
                    accent=(214, 180, 106),
                )

        if milestones:
            pdf.section_title("里程碑检查")
            for item in milestones:
                if isinstance(item, dict):
                    pdf.process_entry(
                        title=_decision_report_text(item.get("time"), default="检查点"),
                        detail=_decision_report_text(item.get("check")),
                        meta="里程碑检查",
                    )
                else:
                    text = _decision_report_text(item, default="")
                    if text:
                        pdf.process_entry(title=text, meta="里程碑检查")

        if survival and survival.get("emotional_note"):
            pdf.narrative_panel(
                title="逆风局的情绪提醒",
                body=_decision_report_text(survival.get("emotional_note")),
                meta="真正难的往往不是损失本身，而是你怎么解释这次损失。",
                accent=(194, 112, 104),
            )

    appendix_sections = _decision_report_appendix_sections(
        detection_job=detection_job,
        detection_result=detection_result,
        detection_status=detection_status,
        engineb_session=engineb_session,
        simulator_output=simulator_output,
        safer_choice_name=safer_choice_name,
        safer_choice_reason=safer_choice_reason,
        simulator_warning=simulator_warning,
    )
    trace_digest = _decision_report_trace_digest(trace)

    if appendix_sections or trace_digest:
        pdf.add_page()
        pdf.chapter_title("附录A · 形成纪要")
        pdf.muted_text("这一部分不再逐条复现系统日志，而是只保留这次推演如何一步步形成结论的关键阶段。", indent=2)
        for section in appendix_sections:
            pdf.narrative_panel(
                title=section.get("title", "阶段纪要"),
                body=section.get("body", ""),
                meta=section.get("meta", ""),
                accent=section.get("accent", (184, 142, 82)),
            )

        if trace_digest:
            pdf.ensure_room(78)
            pdf.chapter_title("附录B · 关键节点摘录")
            pdf.muted_text("以下只摘录少量内部处理节点，用来说明结论如何形成；它不是原始后台日志。", indent=2)
            for group in trace_digest:
                pdf.section_title(group.get("title", "处理节点"))
                if group.get("meta"):
                    pdf.muted_text(group.get("meta"), indent=2)
                pdf.bullet_list(group.get("lines", [])[:3], indent=4)
                pdf.ln(1)

    final_path = output_path or os.path.join(OUTPUT_DIR, "decision-report.pdf")
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    pdf.output(final_path)
    return final_path


def generate_decision_summary_pdf_report(
    question: str,
    *,
    detection_job: dict | None = None,
    engineb_session: dict | None = None,
    decision_data: dict | None = None,
    metadata: dict | None = None,
    output_path: str | None = None,
    use_ai: bool = True,
) -> str:
    """生成客户可直接阅读的 AI 摘要版 PDF。"""
    try:
        from fpdf import FPDF, XPos, YPos
    except ImportError:
        return generate_decision_text_report(
            question,
            detection_job=detection_job,
            engineb_session=engineb_session,
            metadata=metadata,
            output_path=output_path.replace(".pdf", ".txt") if output_path else None,
        )

    detection_job = detection_job if isinstance(detection_job, dict) else {}
    engineb_session = engineb_session if isinstance(engineb_session, dict) else {}
    decision_data = decision_data if isinstance(decision_data, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}

    decision_result = decision_data.get("result") if isinstance(decision_data.get("result"), dict) else {}
    detection_result = detection_job.get("result") if isinstance(detection_job.get("result"), dict) else {}
    simulator_output = engineb_session.get("simulator_output") if isinstance(engineb_session.get("simulator_output"), dict) else {}
    monte_carlo = simulator_output.get("monte_carlo") if isinstance(simulator_output.get("monte_carlo"), dict) else {}
    choice_a = _decision_report_choice_snapshot(simulator_output.get("choice_a")) if simulator_output else {}
    choice_b = _decision_report_choice_snapshot(simulator_output.get("choice_b")) if simulator_output else {}
    safer_choice_name, safer_choice_reason = _decision_report_pick_safer_choice(simulator_output) if simulator_output else ("", "")
    value_lines = _decision_report_value_lines(engineb_session.get("value_profile") if isinstance(engineb_session.get("value_profile"), dict) else {})
    bias_lines = _decision_report_bias_lines(
        engineb_session.get("decision_biases") if isinstance(engineb_session.get("decision_biases"), list) else [],
        _decision_report_text(engineb_session.get("bias_reminder"), default=""),
    )
    alternative_lines = _decision_report_alternative_path_lines(
        engineb_session.get("alternative_path") if isinstance(engineb_session.get("alternative_path"), dict) else {}
    )
    external_signals = engineb_session.get("external_signals") if isinstance(engineb_session.get("external_signals"), list) else []
    if not external_signals and simulator_output:
        external_signals = simulator_output.get("market_signals") if isinstance(simulator_output.get("market_signals"), list) else []
    signal_lines = _decision_report_external_signal_lines(external_signals)

    def compact_list(value, *, limit: int = 5) -> list[str]:
        lines = _decision_report_lines(value)
        return [
            _decision_report_short_text(item, limit=88)
            for item in lines
            if item and not _decision_report_is_placeholder(item)
        ][:limit]

    def extend_unique(target: list[str], values) -> None:
        seen = {item.strip() for item in target}
        for item in compact_list(values, limit=8):
            cleaned = item.strip()
            if cleaned and cleaned not in seen:
                target.append(cleaned)
                seen.add(cleaned)

    recommendation = _decision_report_text(
        engineb_session.get("recommendation")
        or decision_result.get("recommendation")
        or decision_result.get("recommendation_title")
        or detection_result.get("summary"),
        default="建议先把当前问题拆成可验证的小步，再决定是否加码。",
    )
    action_plan = _decision_report_text(
        engineb_session.get("action_plan")
        or decision_result.get("next_step")
        or (alternative_lines[0] if alternative_lines else ""),
        default="先做一轮低成本验证，避免在信息不足时一次性承诺过重。",
    )
    reasoning = _decision_report_text(
        engineb_session.get("reasoning")
        or decision_result.get("why")
        or detection_result.get("summary"),
        default="当前材料显示，这不是单纯靠更多情绪用力就能解决的问题，关键在于缩小不可逆承诺。",
    )
    client_memo = _decision_report_text(
        monte_carlo.get("client_report_memo")
        or simulator_output.get("final_insight")
        or reasoning,
        default=reasoning,
    )

    why = []
    extend_unique(why, [reasoning, safer_choice_reason, client_memo])
    extend_unique(why, value_lines)
    if not why:
        why = [recommendation]

    next_steps = []
    extend_unique(next_steps, [action_plan])
    extend_unique(next_steps, simulator_output.get("action_map_a"))
    extend_unique(next_steps, alternative_lines)
    if not next_steps:
        next_steps = ["未来 7 天先完成一次小规模验证，把风险限制在可承受范围内。"]

    watch_points = []
    extend_unique(watch_points, monte_carlo.get("critical_disagreements"))
    extend_unique(watch_points, signal_lines)
    extend_unique(watch_points, bias_lines)
    if not watch_points:
        watch_points = ["如果现金流、精力或关键关系开始明显恶化，就暂停加码，先回到保护动作。"]

    guardrails = []
    extend_unique(guardrails, monte_carlo.get("decision_guardrails"))
    survival_plan = simulator_output.get("worst_case_survival_plan")
    if isinstance(survival_plan, dict):
        extend_unique(guardrails, list(survival_plan.values()))
    extend_unique(guardrails, [safer_choice_reason])
    if not guardrails:
        guardrails = ["不要一次性押上不可逆成本；先设置止损点、复盘日和退出条件。"]

    scenario_summary = {
        "optimistic": _decision_report_text(monte_carlo.get("llm_collision_summary") or simulator_output.get("final_insight"), default="顺风局重点看是否能把优势沉淀成长期结构。"),
        "baseline": _decision_report_text(safer_choice_reason, default="平稳局重点看节奏、现金流和精力是否能持续。"),
        "pessimistic": _decision_report_text((guardrails[0] if guardrails else ""), default="逆风局重点看止损条件是否清楚。"),
    }
    if choice_a and choice_b:
        scenario_summary["baseline"] = (
            f"{choice_a.get('name')}：顺风{choice_a.get('tailwind', 0)}% / 平稳{choice_a.get('steady', 0)}% / 逆风{choice_a.get('headwind', 0)}%；"
            f"{choice_b.get('name')}：顺风{choice_b.get('tailwind', 0)}% / 平稳{choice_b.get('steady', 0)}% / 逆风{choice_b.get('headwind', 0)}%。"
        )

    summary = {
        "executive_title": _decision_report_text(decision_result.get("recommendation_title"), default="一页读懂这次决策"),
        "one_sentence_answer": recommendation,
        "decision": action_plan,
        "why": why[:5],
        "next_7_days": next_steps[:5],
        "watch_points": watch_points[:5],
        "risk_guardrails": guardrails[:5],
        "scenario_summary": scenario_summary,
        "client_memo": client_memo,
    }

    if use_ai and os.environ.get("CLP_SUMMARY_REPORT_DISABLE_AI", "").strip() not in {"1", "true", "yes"}:
        try:
            try:
                from research.api import call_agent_json
            except Exception:
                from .api import call_agent_json

            max_tokens = max(800, min(6000, int(os.environ.get("CLP_SUMMARY_REPORT_MAX_TOKENS", "3200"))))
            ai_payload = call_agent_json(
                "你是顶级商业决策顾问和报告编辑。请把复杂决策材料压缩成客户一眼看懂的中文摘要版 PDF 文案，只输出严格 JSON。",
                json.dumps(
                    {
                        "question": question,
                        "tier": decision_data.get("tier"),
                        "detection": {
                            "status": detection_job.get("status"),
                            "summary": detection_result.get("summary"),
                        },
                        "recommendation": recommendation,
                        "action_plan": action_plan,
                        "reasoning": reasoning,
                        "values": value_lines,
                        "biases": bias_lines,
                        "alternative": alternative_lines,
                        "external_signals": signal_lines,
                        "simulator": {
                            "final_insight": simulator_output.get("final_insight"),
                            "safer_choice": safer_choice_name,
                            "safer_choice_reason": safer_choice_reason,
                            "choice_a": choice_a,
                            "choice_b": choice_b,
                        },
                        "monte_carlo": {
                            "smooth_prob": monte_carlo.get("smooth_prob"),
                            "confidence_interval": monte_carlo.get("confidence_interval"),
                            "llm_mode": monte_carlo.get("llm_mode"),
                            "actual_llm_calls": monte_carlo.get("actual_llm_calls"),
                            "critical_disagreements": monte_carlo.get("critical_disagreements"),
                            "decision_guardrails": monte_carlo.get("decision_guardrails"),
                            "client_report_memo": monte_carlo.get("client_report_memo"),
                            "premium_report_sections": monte_carlo.get("premium_report_sections"),
                        },
                    },
                    ensure_ascii=False,
                ),
                max_tokens=max_tokens,
                temperature=0.25,
                retries=1,
                timeout_seconds=90,
            )
            if isinstance(ai_payload, dict):
                for key in ("executive_title", "one_sentence_answer", "decision", "client_memo"):
                    if ai_payload.get(key):
                        summary[key] = _decision_report_text(ai_payload.get(key))
                for key in ("why", "next_7_days", "watch_points", "risk_guardrails"):
                    lines = compact_list(ai_payload.get(key), limit=5)
                    if lines:
                        summary[key] = lines
                scenario = ai_payload.get("scenario_summary")
                if isinstance(scenario, dict):
                    summary["scenario_summary"] = {
                        "optimistic": _decision_report_text(scenario.get("optimistic"), default=summary["scenario_summary"]["optimistic"]),
                        "baseline": _decision_report_text(scenario.get("baseline"), default=summary["scenario_summary"]["baseline"]),
                        "pessimistic": _decision_report_text(scenario.get("pessimistic"), default=summary["scenario_summary"]["pessimistic"]),
                    }
        except Exception as exc:
            print(f"  ⚠ AI 摘要 PDF 生成使用本地降级文案: {exc}")

    font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
    generated_at = metadata.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    safe_question = _decision_report_pdf_text(question, default="未提供问题")

    class SummaryPDF(FPDF):
        def header(self):
            if self.page_no() == 1:
                return
            self.set_font("STHeiti", "", 8)
            self.set_text_color(126, 136, 152)
            self.cell(0, 8, "AI Executive Summary", align="R")
            self.ln(8)

        def footer(self):
            self.set_y(-14)
            self.set_font("STHeiti", "", 8)
            self.set_text_color(150, 158, 172)
            self.cell(0, 8, f"摘要版 · 第 {self.page_no()} 页", align="C")

        def ensure_room(self, height: float = 34):
            if self.get_y() + height > self.h - self.b_margin:
                self.add_page()

        def section_title(self, title: str):
            self.ensure_room(20)
            self.set_font("STHeiti", "B", 14)
            self.set_text_color(20, 27, 40)
            self.cell(0, 9, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_draw_color(214, 180, 106)
            self.set_line_width(0.7)
            y = self.get_y()
            self.line(self.l_margin, y, self.l_margin + 34, y)
            self.ln(4)

        def muted(self, text: str):
            self.set_font("STHeiti", "", 9)
            self.set_text_color(108, 119, 136)
            self.multi_cell(0, 5.4, _decision_report_pdf_text(text, default=""))
            self.ln(1.5)

        def body(self, text: str, *, size: int = 10, line_h: float = 6.2):
            self.set_font("STHeiti", "", size)
            self.set_text_color(43, 51, 66)
            self.multi_cell(0, line_h, _decision_report_pdf_text(text, default=""))
            self.ln(2)

        def bullet_list(self, items: list[str], *, limit: int = 5):
            self.set_font("STHeiti", "", 10)
            self.set_text_color(43, 51, 66)
            for item in items[:limit]:
                self.ensure_room(10)
                self.set_x(self.l_margin + 2)
                self.multi_cell(0, 6, f"• {_decision_report_pdf_text(item, default='')}")
            self.ln(2)

        def highlight_box(self, title: str, text: str, *, fill=(246, 248, 252), border=(218, 224, 235)):
            self.ensure_room(44)
            x = self.l_margin
            y = self.get_y()
            w = self.w - self.l_margin - self.r_margin
            self.set_fill_color(*fill)
            self.set_draw_color(*border)
            self.rect(x, y, w, 38, style="DF")
            self.set_xy(x + 6, y + 5)
            self.set_font("STHeiti", "B", 10)
            self.set_text_color(72, 84, 105)
            self.cell(w - 12, 6, _decision_report_pdf_text(title, default=""), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_x(x + 6)
            self.set_font("STHeiti", "", 11)
            self.set_text_color(20, 27, 40)
            self.multi_cell(w - 12, 6.2, _decision_report_pdf_text(text, default=""))
            self.set_y(y + 42)

        def scenario_card(self, label: str, text: str, color: tuple[int, int, int]):
            self.ensure_room(30)
            x = self.l_margin
            y = self.get_y()
            w = self.w - self.l_margin - self.r_margin
            self.set_fill_color(250, 251, 253)
            self.set_draw_color(226, 231, 240)
            self.rect(x, y, w, 24, style="DF")
            self.set_fill_color(*color)
            self.rect(x, y, 3, 24, "F")
            self.set_xy(x + 7, y + 4)
            self.set_font("STHeiti", "B", 10)
            self.set_text_color(*color)
            self.cell(30, 6, label)
            self.set_xy(x + 38, y + 4)
            self.set_font("STHeiti", "", 9)
            self.set_text_color(43, 51, 66)
            self.multi_cell(w - 44, 5.2, _decision_report_pdf_text(text, default=""))
            self.set_y(y + 28)

    pdf = SummaryPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("STHeiti", "", font_path)
    pdf.add_font("STHeiti", "B", font_path)
    pdf.add_font("STHeiti", "I", font_path)

    pdf.add_page()
    pdf.set_fill_color(8, 14, 24)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.set_fill_color(214, 180, 106)
    pdf.rect(0, 0, 8, 297, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("STHeiti", "B", 24)
    pdf.set_xy(24, 52)
    pdf.multi_cell(162, 12, "AI 决策摘要报告")
    pdf.set_font("STHeiti", "", 12)
    pdf.set_text_color(190, 198, 214)
    pdf.set_x(24)
    pdf.multi_cell(162, 7, "给客户直接阅读的清晰版结论")
    pdf.ln(18)
    pdf.set_x(24)
    pdf.set_font("STHeiti", "B", 12)
    pdf.set_text_color(243, 214, 133)
    pdf.cell(0, 8, "本次问题", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(24)
    pdf.set_font("STHeiti", "", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(162, 7.4, safe_question)
    pdf.ln(12)
    pdf.set_x(24)
    pdf.set_font("STHeiti", "", 10)
    pdf.set_text_color(160, 170, 190)
    pdf.multi_cell(162, 6.2, f"生成时间：{generated_at}    模型：{_decision_report_pdf_text(metadata.get('model'), default='当前配置模型')}")
    pdf.ln(18)
    pdf.set_x(24)
    pdf.set_font("STHeiti", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(162, 9, _decision_report_pdf_text(summary.get("executive_title"), default="一页读懂这次决策"))
    pdf.set_x(24)
    pdf.set_font("STHeiti", "", 12)
    pdf.set_text_color(218, 224, 238)
    pdf.multi_cell(162, 7, _decision_report_pdf_text(summary.get("one_sentence_answer"), default=recommendation))

    pdf.add_page()
    pdf.section_title("直接结论")
    pdf.highlight_box("一句话答案", _decision_report_text(summary.get("one_sentence_answer"), default=recommendation), fill=(252, 248, 235), border=(229, 207, 145))
    pdf.highlight_box("建议怎么做", _decision_report_text(summary.get("decision"), default=action_plan), fill=(244, 248, 255), border=(194, 211, 242))
    pdf.section_title("为什么是这个方向")
    pdf.bullet_list(summary.get("why") if isinstance(summary.get("why"), list) else why)

    pdf.section_title("未来 7 天行动")
    pdf.bullet_list(summary.get("next_7_days") if isinstance(summary.get("next_7_days"), list) else next_steps)

    pdf.section_title("三种未来情景")
    scenario = summary.get("scenario_summary") if isinstance(summary.get("scenario_summary"), dict) else scenario_summary
    pdf.scenario_card("顺风", _decision_report_text(scenario.get("optimistic"), default=scenario_summary["optimistic"]), (38, 145, 96))
    pdf.scenario_card("平稳", _decision_report_text(scenario.get("baseline"), default=scenario_summary["baseline"]), (191, 137, 40))
    pdf.scenario_card("逆风", _decision_report_text(scenario.get("pessimistic"), default=scenario_summary["pessimistic"]), (190, 71, 73))

    pdf.section_title("需要盯住的信号")
    pdf.bullet_list(summary.get("watch_points") if isinstance(summary.get("watch_points"), list) else watch_points)

    pdf.section_title("风险护栏")
    pdf.bullet_list(summary.get("risk_guardrails") if isinstance(summary.get("risk_guardrails"), list) else guardrails)

    pdf.section_title("给客户看的备忘")
    pdf.body(_decision_report_text(summary.get("client_memo"), default=client_memo), size=10, line_h=6.4)

    if monte_carlo:
        smooth = monte_carlo.get("smooth_prob") if isinstance(monte_carlo.get("smooth_prob"), dict) else {}
        calls = _decision_report_int(monte_carlo.get("actual_llm_calls"), 0)
        requested = _decision_report_int(monte_carlo.get("llm_panels_requested"), 0)
        pdf.section_title("Ultra 委员会摘要")
        pdf.muted(
            f"Monte Carlo 概率：顺风 {smooth.get('optimistic', '--')}% / 平稳 {smooth.get('baseline', '--')}% / 逆风 {smooth.get('pessimistic', '--')}%。"
            f" LLM 委员会：成功 {calls} 次 / 请求 {requested} 组。"
        )

    final_path = output_path or os.path.join(OUTPUT_DIR, "decision-summary-report.pdf")
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    pdf.output(final_path)
    return final_path


def generate_decision_text_report(
    question: str,
    *,
    detection_job: dict | None = None,
    engineb_session: dict | None = None,
    metadata: dict | None = None,
    output_path: str | None = None,
) -> str:
    """生成决策报告的纯文本版本（作为 PDF 缺失时的降级方案）。"""
    detection_job = detection_job if isinstance(detection_job, dict) else {}
    engineb_session = engineb_session if isinstance(engineb_session, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    
    lines = []
    lines.append("=" * 60)
    lines.append("  认知拉格朗日点 · 决策报告  ")
    lines.append("=" * 60)
    lines.append(f"问题: {question}")
    lines.append(f"生成时间: {metadata.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}")
    lines.append("-" * 60)
    
    # 摘要
    lines.append("[ 一、报告摘要 ]")
    status = detection_job.get("status", "未运行")
    lines.append(f"- 检测状态: {status}")
    if engineb_session.get("recommendation"):
        lines.append(f"- 核心建议: {engineb_session.get('recommendation')}")
    lines.append("")
    
    # 检测详情
    if detection_job:
        lines.append("[ 二、检测结果 ]")
        res = detection_job.get("result", {})
        if res:
            lines.append(f"- 最终评估: {res.get('summary', '无')}")
            lines.append(f"- 是否为拉格朗日点: {'是' if res.get('is_lagrange_point') else '否'}")
        lines.append("")
        
    # Engine B 详情
    if engineb_session:
        lines.append("[ 三、Engine B 决策突破 ]")
        if engineb_session.get("action_plan"):
            lines.append(f"- 行动方案: {engineb_session.get('action_plan')}")
        if engineb_session.get("reasoning"):
            lines.append(f"- 推理逻辑: {engineb_session.get('reasoning')}")
        lines.append("")
        
    final_content = "\n".join(lines)
    
    final_path = output_path or os.path.join(OUTPUT_DIR, "decision-report.txt")
    if not final_path.endswith(".txt"):
        final_path = os.path.splitext(final_path)[0] + ".txt"
        
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(final_content)
    return final_path

def format_clp_card(clp: ConfirmedLagrangePoint) -> str:
    """生成单个拉格朗日点的文本卡片。"""
    lines = []
    lines.append("╔" + "═" * 65 + "╗")
    lines.append(f"║ 认知拉格朗日点 #{clp.id:<54}║")
    lines.append("║" + " " * 65 + "║")
    # 问题文本（自动换行）
    q = clp.question_text
    while q:
        chunk = q[:55]
        q = q[55:]
        lines.append(f"║   {chunk:<62}║")
    lines.append("║" + " " * 65 + "║")

    # 力量解剖
    lines.append(f"║ 力量解剖：{' ' * 54}║")
    lines.append(f"║   → 正方力量（合成：{clp.pro_total}）{' ' * (43 - len(str(clp.pro_total)))}║")
    for f in clp.pro_forces:
        name_str = f"     ├── {f.name} (强度:{f.strength}%)"
        lines.append(f"║{name_str:<65}║")
    lines.append(f"║   → 反方力量（合成：{clp.con_total}）{' ' * (43 - len(str(clp.con_total)))}║")
    for f in clp.con_forces:
        name_str = f"     ├── {f.name} (强度:{f.strength}%)"
        lines.append(f"║{name_str:<65}║")
    lines.append(f"║   平衡精度：{clp.balance_precision}%{' ' * (50 - len(str(clp.balance_precision)))}║")
    if clp.stability_type is not None:
        stability_text = f"║   稳定性：{clp.stability_type.value}"
        lines.append(f"{stability_text:<66}║")
    if clp.oscillation_type is not None:
        oscillation_text = f"║   振荡类型：{clp.oscillation_type.value}"
        lines.append(f"{oscillation_text:<66}║")
        if clp.oscillation_period is not None:
            period_text = f"║   振荡周期：约 {clp.oscillation_period} 轮"
            lines.append(f"{period_text:<66}║")
    if clp.fault_lines:
        fault_line_text = f"║   所在断层线：{'、'.join(clp.fault_lines)}"
        lines.append(f"{fault_line_text:<66}║")
    if clp.tunnel_connections:
        tunnel_text = f"║   隧道连接：{'、'.join(clp.tunnel_connections)}"
        lines.append(f"{tunnel_text:<66}║")
    lines.append("║" + " " * 65 + "║")
    lines.append("╚" + "═" * 65 + "╝")
    return "\n".join(lines)


def save_results(
    candidates: list[CandidateQuestion],
    survivors: list[CandidateQuestion],
    confirmed: list[ConfirmedLagrangePoint],
    fault_lines: list[FaultLine] | None = None,
    tunnel_effects: list[dict] | None = None,
    social_conflict_predictions: list[dict] | None = None,
    key_discoveries: list[str] | None = None,
    metadata: dict | None = None,
):
    """保存所有结果到文件。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fault_lines = fault_lines or []
    tunnel_effects = tunnel_effects or []
    social_conflict_predictions = social_conflict_predictions or []
    key_discoveries = key_discoveries or []
    metadata = metadata or {}
    enable_filter1 = bool(metadata.get("enable_filter1", False))
    enable_filter3 = bool(metadata.get("enable_filter3", False))

    selected_candidates = [c for c in candidates if c.selected_for_pipeline]
    filter1_survivors = [c for c in selected_candidates if c.passed_filter_1 is True]
    filter2_survivors = [c for c in selected_candidates if c.passed_filter_2 is True]
    filter3_survivors = [c for c in selected_candidates if c.passed_filter_3 is True]

    # 1. 完整JSON数据
    data = {
        "version": "MVP-0.4",
        "metadata": metadata,
        "total_candidates": len(candidates),
        "selected_for_pipeline": len(selected_candidates),
        "filter1_survivors": len(filter1_survivors),
        "filter2_survivors": len(filter2_survivors),
        "filter3_survivors": len(filter3_survivors),
        "confirmed_count": len(confirmed),
        "confirmed_points": len(confirmed),
        "fault_lines": [line.to_dict() for line in fault_lines],
        "tunnel_effects": tunnel_effects,
        "social_conflict_predictions": social_conflict_predictions,
        "key_discoveries": key_discoveries,
        "candidates": [c.to_dict() for c in candidates],
        "confirmed": [clp.to_dict() for clp in confirmed],
    }

    json_path = _write_json_targets("results.json", data)
    print(f"  📄 JSON数据已保存: {json_path}")

    # 2. 可读文本报告
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  人类认知断层线地图 v0.4")
    report_lines.append("  认知拉格朗日点 · 寻找人类思维的永恒僵局")
    report_lines.append("=" * 70)
    report_lines.append("")
    report_lines.append(f"  候选问题总数：{len(candidates)}")
    report_lines.append(f"  进入本轮深筛：{len(selected_candidates)}")
    if enable_filter1:
        report_lines.append(f"  筛子1存活数：{len(filter1_survivors)}")
    report_lines.append(f"  筛子2存活数：{len(filter2_survivors)}")
    if enable_filter3:
        report_lines.append(f"  筛子3存活数：{len(filter3_survivors)}")
    report_lines.append(f"  确认拉格朗日点：{len(confirmed)}")
    report_lines.append("")
    report_lines.append("─" * 70)
    report_lines.append("  一、确认的认知拉格朗日点")
    report_lines.append("─" * 70)
    report_lines.append("")

    for clp in confirmed:
        report_lines.append(format_clp_card(clp))
        report_lines.append("")
        # 详细力量
        report_lines.append("  正方力量详解：")
        for f in clp.pro_forces:
            report_lines.append(f"    [{f.name}] 强度:{f.strength} 来源:{f.source}")
            report_lines.append(f"      论证: {f.best_argument}")
            report_lines.append(f"      弱点: {f.known_weakness}")
        report_lines.append("")
        report_lines.append("  反方力量详解：")
        for f in clp.con_forces:
            report_lines.append(f"    [{f.name}] 强度:{f.strength} 来源:{f.source}")
            report_lines.append(f"      论证: {f.best_argument}")
            report_lines.append(f"      弱点: {f.known_weakness}")
        if clp.stability_type is not None:
            report_lines.append("")
            report_lines.append(f"  稳定性：{clp.stability_type.value}")
            if clp.stability_summary:
                report_lines.append(f"    {clp.stability_summary}")
            for item in clp.perturbation_responses:
                report_lines.append(
                    f"    扰动测试 | 扰动后 {item.get('after_perturbation_direction')}:{item.get('after_perturbation_strength')} "
                    f"| 移除后 {item.get('after_removal_direction')}:{item.get('after_removal_strength')}"
                )
        if clp.oscillation_type is not None:
            report_lines.append("")
            report_lines.append(f"  振荡类型：{clp.oscillation_type.value}")
            if clp.oscillation_period is not None:
                report_lines.append(f"    振荡周期：约 {clp.oscillation_period} 轮")
            if clp.oscillation_summary:
                report_lines.append(f"    {clp.oscillation_summary}")
        if clp.fault_lines:
            report_lines.append("")
            report_lines.append(f"  所在断层线：{'、'.join(clp.fault_lines)}")
        if clp.tunnel_connections:
            report_lines.append("")
            report_lines.append(f"  隧道连接：{'、'.join(clp.tunnel_connections)}")
        report_lines.append("")
        report_lines.append("─" * 70)
        report_lines.append("")

    if fault_lines:
        report_lines.append("  二、断层线列表")
        report_lines.append("─" * 70)
        for line in fault_lines:
            report_lines.append(f"  [{line.name}]")
            report_lines.append(f"    描述: {line.description}")
            report_lines.append(f"    点位: {', '.join(line.points_on_line) or '无'}")
            report_lines.append(f"    交叉: {', '.join(line.intersections) or '无'}")
        report_lines.append("")

    if tunnel_effects:
        report_lines.append("  三、隧道效应网络")
        report_lines.append("─" * 70)
        for item in tunnel_effects:
            report_lines.append(
                f"  {item['from_point']} -> {item['to_point']} | 强度 {item['strength']}"
            )
            if item.get("rationale"):
                report_lines.append(f"    {item['rationale']}")
        report_lines.append("")

    if key_discoveries:
        report_lines.append("  四、关键发现")
        report_lines.append("─" * 70)
        for item in key_discoveries:
            report_lines.append(f"  · {item}")
        report_lines.append("")

    if social_conflict_predictions:
        report_lines.append("  五、社会冲突预测")
        report_lines.append("─" * 70)
        for item in social_conflict_predictions:
            report_lines.append(f"  [{item['title']}]")
            if item.get("related_fault_lines"):
                report_lines.append(f"    相关断层线: {', '.join(item['related_fault_lines'])}")
            if item.get("related_points"):
                report_lines.append(f"    相关点位: {', '.join(item['related_points'])}")
            if item.get("activation_signal"):
                report_lines.append(f"    触发信号: {item['activation_signal']}")
            report_lines.append(f"    预测: {item['prediction']}")
        report_lines.append("")

    skipped = [c for c in candidates if not c.selected_for_pipeline]
    filter1_eliminated = [c for c in selected_candidates if c.passed_filter_1 is False]
    filter2_eliminated = [
        c for c in selected_candidates
        if (not enable_filter1 or c.passed_filter_1 is True) and c.passed_filter_2 is False
    ]
    filter3_eliminated = [
        c for c in selected_candidates
        if c.passed_filter_2 is True and c.passed_filter_3 is False
    ]

    pending = []
    for candidate in selected_candidates:
        if enable_filter1 and candidate.passed_filter_1 is None:
            pending.append(candidate)
            continue
        if candidate.passed_filter_2 is None:
            pending.append(candidate)
            continue
        if enable_filter3 and candidate.passed_filter_3 is None:
            pending.append(candidate)

    extra_sections = 0
    if fault_lines:
        extra_sections += 1
    if tunnel_effects:
        extra_sections += 1
    if key_discoveries:
        extra_sections += 1
    if social_conflict_predictions:
        extra_sections += 1
    section_index = 2 + extra_sections
    report_lines.append(f"  {['零','一','二','三','四','五','六','七','八','九'][section_index]}、未进入本轮深筛的候选")
    report_lines.append("─" * 70)
    for c in skipped:
        report_lines.append(f"  · {c.id} | 初始分{c.initial_score}")
        report_lines.append(f"    {c.question_text[:60]}...")

    if enable_filter1:
        section_index += 1
        report_lines.append("")
        report_lines.append(f"  {['零','一','二','三','四','五','六','七','八','九'][section_index]}、筛子1淘汰")
        report_lines.append("─" * 70)
        for c in filter1_eliminated:
            report_lines.append(f"  ✗ {c.id} | {c.filter_1_summary}")
            report_lines.append(f"    {c.question_text[:60]}...")

    section_index += 1
    report_lines.append("")
    report_lines.append(f"  {['零','一','二','三','四','五','六','七','八','九'][section_index]}、筛子2淘汰")
    report_lines.append("─" * 70)
    for c in filter2_eliminated:
        report_lines.append(f"  ✗ {c.id} | 分布{c.filter_2_distribution} | 平衡度{c.filter_2_balance_score}%")
        report_lines.append(f"    {c.question_text[:60]}...")

    if enable_filter3:
        section_index += 1
        report_lines.append("")
        report_lines.append(f"  {['零','一','二','三','四','五','六','七','八','九'][section_index]}、筛子3淘汰")
        report_lines.append("─" * 70)
        for c in filter3_eliminated:
            report_lines.append(f"  ✗ {c.id} | {c.filter_3_summary} | {c.filter_3_classification}")
            report_lines.append(f"    {c.question_text[:60]}...")

    if pending:
        section_index += 1
        report_lines.append("")
        report_lines.append(f"  {['零','一','二','三','四','五','六','七','八','九'][section_index]}、待补跑的候选问题")
        report_lines.append("─" * 70)
        for c in pending:
            if enable_filter1 and c.passed_filter_1 is None:
                status = c.filter_1_summary or "筛子1处理中"
            elif c.passed_filter_2 is None:
                status = c.filter_2_distribution or "筛子2处理中"
            else:
                status = c.filter_3_summary or "筛子3处理中"
            report_lines.append(f"  … {c.id} | {status}")
            report_lines.append(f"    {c.question_text[:60]}...")
    report_lines.append("")
    report_lines.append("=" * 70)

    report_path = _write_text_targets("report.txt", "\n".join(report_lines))
    print(f"  📋 文本报告已保存: {report_path}")


def generate_discovered_payload(confirmed: list[ConfirmedLagrangePoint]) -> dict:
    """将确认的拉格朗日点转换为前端星图所需的 discovered 系统数据（dict格式）。"""
    import math

    nodes_js = []
    fault_line_map: dict[str, list[int]] = {}
    tunnel_connections = []
    for i, clp in enumerate(confirmed):
        angle = (2 * math.pi * i) / max(len(confirmed), 1)
        pro_name = clp.pro_forces[0].name if clp.pro_forces else "正方"
        con_name = clp.con_forces[0].name if clp.con_forces else "反方"

        q = clp.question_text
        name = q[:15].rstrip("，。、？") if len(q) > 15 else q
        subtitle = f"CLP #{clp.id}"
        question_text = q if len(q) <= 80 else q[:80] + "..."

        body = clp.question_text
        if clp.pro_forces and clp.con_forces:
            body += f"\n\n正方核心力量：{clp.pro_forces[0].best_argument}"
            body += f"\n\n反方核心力量：{clp.con_forces[0].best_argument}"
            body += f"\n\n平衡精度：{clp.balance_precision}%"
        if clp.stability_type is not None:
            body += f"\n\n稳定性：{clp.stability_type.value}"
            if clp.stability_summary:
                body += f"\n{clp.stability_summary}"
        if clp.oscillation_type is not None:
            body += f"\n\n振荡类型：{clp.oscillation_type.value}"
            if clp.oscillation_period is not None:
                body += f"\n振荡周期：约 {clp.oscillation_period} 轮"
            if clp.oscillation_summary:
                body += f"\n{clp.oscillation_summary}"
        if clp.fault_lines:
            body += f"\n\n所在断层线：{'、'.join(clp.fault_lines)}"
        if clp.tunnel_connections:
            body += f"\n\n隧道连接：{'、'.join(clp.tunnel_connections)}"

        node = {
            "name": name,
            "subtitle": subtitle,
            "angle": round(angle, 2),
            "distance": 170 + (i % 3) * 15,
            "orbitSpeed": 0.05 + (i % 4) * 0.01,
            "tension": [pro_name, con_name],
            "question": question_text,
            "body": body,
            "node_index": i,
            "clp_data": clp.to_dict(),
        }
        nodes_js.append(node)
        for line in clp.fault_lines:
            fault_line_map.setdefault(line, []).append(i)
        for tunnel_to in clp.tunnel_connections:
            tunnel_connections.append((i, tunnel_to))

    if not nodes_js:
        return {"systems": []}

    fault_line_connections = []
    for line_name, node_indices in fault_line_map.items():
        if len(node_indices) >= 2:
            for idx in range(len(node_indices) - 1):
                fault_line_connections.append({
                    "fault_line": line_name,
                    "nodes": [node_indices[idx], node_indices[idx + 1]],
                })

    tunnel_index_lookup = {clp.id: index for index, clp in enumerate(confirmed)}
    tunnel_edges = []
    for from_index, tunnel_to in tunnel_connections:
        to_index = tunnel_index_lookup.get(tunnel_to)
        if to_index is None:
            continue
        tunnel_edges.append({"from": from_index, "to": to_index})

    return {
        "systems": [{
            "id": "discovered",
            "name": "新发现的认知拉格朗日点",
            "nameEn": "Discovered Lagrange Points",
            "color": [255, 107, 107],
            "position": {"x": 0, "y": 0},
            "nodes": nodes_js,
            "fault_line_connections": fault_line_connections,
            "tunnel_connections": tunnel_edges,
        }]
    }


def generate_data_js(confirmed: list[ConfirmedLagrangePoint]):
    """将确认的拉格朗日点转换为前端可直接加载的 discovered-data.js。"""
    payload = generate_discovered_payload(confirmed)
    systems = payload.get("systems", [])

    if not systems:
        with open(DISCOVERED_DATA_JS, "w", encoding="utf-8") as f:
            f.write("window.DISCOVERED_SYSTEMS = [];\n")
        print("  ⚠ 没有确认的拉格朗日点，已清空 discovered-data.js")
        return

    # 保存为独立的JSON，供前端可选加载
    discovered_path = _write_json_targets("discovered_system.json", systems[0])
    print(f"  🌟 星图数据已保存: {discovered_path}")

    js_payload = "window.DISCOVERED_SYSTEMS = " + json.dumps(systems, ensure_ascii=False, indent=2) + ";\n"
    with open(DISCOVERED_DATA_JS, "w", encoding="utf-8") as f:
        f.write(js_payload)
    print(f"  🌠 前端增量数据已更新: {DISCOVERED_DATA_JS}")
