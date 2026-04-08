import unittest
from unittest.mock import patch

from research.engine_b.agents import (
    extract_choice_options,
    infer_blockages_from_answers,
    normalize_simulator_output,
    parse_sim_params_from_answers,
    run_b1_diagnosis,
    run_b2_info_gathering,
    run_b3_cognitive_unlock,
    run_b6_sim_params,
    run_b7_timeline,
    run_b5_emotional_mirror,
    run_c1_reevaluation,
    run_ultra_monte_carlo_collision,
)
from research.engine_b.models import DiagnosisQuestion
from research.phase2_filter import evaluate_question_balance


class EngineBAgentsTest(unittest.TestCase):
    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b1_diagnosis_falls_back_when_model_errors(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = ValueError("模型返回空响应")

        questions = run_b1_diagnosis("我该不该开gpt会员")

        self.assertGreaterEqual(len(questions), 3)
        self.assertTrue(all(question.question_text for question in questions))
        self.assertTrue(all(question.options for question in questions))

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b2_info_gathering_falls_back_to_local_items(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = TimeoutError("504 gateway timeout")

        items = run_b2_info_gathering(
            "我该不该开gpt会员",
            ["A"],
            {"b1q1": "我主要不知道到底值不值。"},
        )

        self.assertGreaterEqual(len(items), 2)
        self.assertTrue(any("使用" in item["title"] or "回本" in item["title"] for item in items))

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b3_cognitive_unlock_falls_back_to_local_frames(self, mock_call_agent_json) -> None:
        mock_call_agent_json.return_value = {"cognitive_frames": []}

        frames = run_b3_cognitive_unlock(
            "我该不该开gpt会员",
            ["B"],
            {"b1q1": "我不知道怎么判断"},
            [],
        )

        self.assertGreaterEqual(len(frames), 2)
        self.assertTrue(any(frame["title"] == "使用密度" for frame in frames))

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b5_emotional_mirror_falls_back_to_local_insight(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = ValueError("empty")

        insight = run_b5_emotional_mirror(
            "我该不该开gpt会员",
            ["D"],
            {"b1q1": "我怕花钱不值，也怕错过好工具。"},
        )

        self.assertTrue(insight["dominant_emotions"])
        self.assertTrue(insight["grounding_prompt"])

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b6_sim_params_falls_back_to_local_questions(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = ValueError("empty")

        questions = run_b6_sim_params("我该不该开gpt会员", "仍需更多信息")

        self.assertGreaterEqual(len(questions), 5)
        self.assertTrue(all(question["question_text"] for question in questions))
        self.assertIn("fixed_expenses", {question.get("field_name") for question in questions})
        self.assertIn("reversal_cost", {question.get("field_name") for question in questions})

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b6_sim_params_uses_domain_specific_career_wording(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = ValueError("empty")

        questions = run_b6_sim_params("我要不要去外地工作", "先算清净收益再决定")

        prompts = " ".join(question["question_text"] for question in questions)
        self.assertIn("房租", prompts)
        self.assertTrue(any(question.get("field_name") == "fixed_expenses" for question in questions))

    @patch("research.engine_b.agents.call_agent_json")
    def test_extract_choice_options_falls_back_when_model_errors(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = TimeoutError("timeout")

        choices = extract_choice_options("我该不该开gpt会员", "仍需更多信息", "先列30天真实使用场景")

        self.assertEqual(len(choices), 2)
        self.assertTrue(all(choice["name"] for choice in choices))

    def test_infer_blockages_prefers_emotion_and_experience_signals(self) -> None:
        questions = [
            DiagnosisQuestion(id="b1q1", question_text="关于这件事，你觉得自己最缺乏了解的是什么？"),
            DiagnosisQuestion(id="b1q2", question_text="你身边有没有经历过类似选择的人？他们怎么说的？"),
            DiagnosisQuestion(id="b1q3", question_text="假设你已经做了选择A，你第一个担心的是什么？"),
        ]
        answers = {
            "b1q1": "信息我大致都查过了，不算最缺。",
            "b1q2": "身边基本没人经历过，我也没有可参考的过来人。",
            "b1q3": "我主要是害怕选错之后后悔，还会很焦虑。",
        }

        result = infer_blockages_from_answers(answers, questions)

        self.assertEqual(result[0], "D")
        self.assertIn("C", result)

    def test_parse_sim_params_uses_question_semantics_instead_of_fixed_ids(self) -> None:
        sim_questions = [
            {"id": "p1", "question_text": "如果现在不顺，手里的存款大概能撑几个月？"},
            {"id": "p2", "question_text": "你目前有没有其他收入来源？"},
            {"id": "p3", "question_text": "你最怕出现的最坏情况是什么？"},
            {"id": "p4", "question_text": "如果选错了，最快多久能回头？"},
        ]
        answers = {
            "p1": "保守算大概能撑8个月。",
            "p2": "有一点自由职业收入，但不稳定。",
            "p3": "最怕试了以后现金流断掉，还伤到自信。",
            "p4": "大概三个月可以调整回来。",
        }

        result = parse_sim_params_from_answers(answers, sim_questions, "我要不要辞职创业")

        self.assertEqual(result["savings_months"], 8)
        self.assertEqual(result["other_income"], "有一点自由职业收入，但不稳定。")
        self.assertEqual(result["worst_fear"], "最怕试了以后现金流断掉，还伤到自信。")
        self.assertEqual(result["time_to_reverse"], "大概三个月可以调整回来。")
        self.assertEqual(result["question_context"], "我要不要辞职创业")

    def test_parse_sim_params_falls_back_to_answer_text_for_months(self) -> None:
        answers = {"x": "如果控制开销，半年左右问题不大。"}

        result = parse_sim_params_from_answers(answers)

        self.assertEqual(result["savings_months"], 6)

    def test_normalize_simulator_output_scrubs_placeholders(self) -> None:
        output = normalize_simulator_output({
            "user_params": {"savings_months": 1},
            "choice_a": {
                "choice_name": "推进改变",
                "probability_distribution": {
                    "tailwind": {"percent": 24, "reason": "未说明"},
                    "steady": {"percent": 48, "reason": "正常"},
                    "headwind": {"percent": 28, "reason": "未提供"},
                },
                "timelines": {
                    "steady": {
                        "title": "平稳局",
                        "nodes": [
                            {
                                "time": "第6个月",
                                "external_state": "如果未说明仍压得紧，这条路会显得更现实。",
                                "inner_feeling": "紧绷",
                                "key_action": "按“未说明”准备退路，不等彻底失控。",
                                "signal": "还能撑住",
                            }
                        ],
                    }
                },
            },
            "choice_b": {
                "choice_name": "维持现状",
                "probability_distribution": {
                    "tailwind": {"percent": 18, "reason": "正常"},
                    "steady": {"percent": 48, "reason": "正常"},
                    "headwind": {"percent": 34, "reason": "正常"},
                },
                "timelines": {"steady": {"title": "平稳局", "nodes": []}},
            },
            "comparison_summary": "未说明",
            "action_map_a": ["按“未说明”准备退路"],
            "action_map_b": [],
            "final_insight": "未提供",
        })

        steady_node = output["choice_a"]["timelines"]["steady"]["nodes"][0]
        self.assertNotIn("未说明", steady_node["external_state"])
        self.assertNotIn("未说明", steady_node["key_action"])
        self.assertTrue(output["comparison_summary"])

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b7_timeline_fills_choice_name_when_model_omits_it(self, mock_call_agent_json) -> None:
        mock_call_agent_json.return_value = {
            "probability_distribution": {
                "tailwind": {"percent": 25, "reason": "机会匹配度高"},
                "steady": {"percent": 50, "reason": "正常波动"},
                "headwind": {"percent": 25, "reason": "适应成本高"},
            },
            "timelines": {
                "steady": {
                    "title": "平稳局",
                    "nodes": [
                        {
                            "time": "第1周",
                            "external_state": "开始适应",
                            "inner_feeling": "有点紧张",
                            "key_action": "先稳住作息",
                            "signal": "能按时完成任务",
                        }
                    ],
                }
            },
        }

        result = run_b7_timeline(
            "原始问题：我要不要去外地工作",
            "去外地工作",
            "离开本地去外地接受新的工作机会",
            {"savings_months": 3, "worst_fear": "工作拿不起来"},
        )

        self.assertEqual(result["choice_name"], "去外地工作")
        self.assertIn("tailwind", result["timelines"])
        self.assertIn("steady", result["timelines"])
        self.assertIn("headwind", result["timelines"])

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_b7_timeline_falls_back_when_model_times_out(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = TimeoutError("504 gateway timeout")

        result = run_b7_timeline(
            "原始问题：我要不要去外地工作",
            "去外地工作",
            "离开本地去外地接受新的工作机会",
            {"savings_months": 1, "worst_fear": "被裁员", "time_to_reverse": "1个月内能回头"},
        )

        self.assertEqual(result["choice_name"], "去外地工作")
        self.assertEqual(result["fallback_mode"], "local_fast")
        self.assertEqual(len(result["timelines"]["steady"]["nodes"]), 6)
        self.assertEqual(result["timelines"]["headwind"]["nodes"][1]["time"], "第1个月")

    def test_run_ultra_monte_carlo_collision_returns_stable_distribution(self) -> None:
        result = run_ultra_monte_carlo_collision(
            question="我该不该辞职做AI产品",
            choice_a_sim={
                "choice_name": "继续稳定工作",
                "probability_distribution": {
                    "tailwind": {"percent": 20},
                    "steady": {"percent": 55},
                    "headwind": {"percent": 25},
                },
            },
            choice_b_sim={
                "choice_name": "辞职转行",
                "probability_distribution": {
                    "tailwind": {"percent": 34},
                    "steady": {"percent": 42},
                    "headwind": {"percent": 24},
                },
            },
            user_params={"savings_months": 3, "worst_fear": "现金流断裂"},
            sample_count=24,
            persona_count=8,
            agents_per_branch=4,
            rounds=2,
            branch_sample_limit=12,
            llm_panels=0,
        )

        self.assertEqual(result["sample_count"], 24)
        self.assertEqual(result["persona_count"], 8)
        self.assertEqual(len(result["branches"]), 12)
        self.assertEqual(round(sum(result["smooth_prob"].values()), 1), 100.0)
        self.assertTrue(result["confidence_interval"])
        self.assertTrue(result["disagreement_heatmap"])
        self.assertEqual(result["llm_mode"], "local_sampling")
        self.assertEqual(result["actual_llm_calls"], 0)

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_ultra_monte_carlo_collision_uses_real_llm_panels_when_enabled(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = [
            {
                "panel_name": "风险委员会",
                "position": "先保护现金流",
                "confidence": 0.72,
                "executive_summary": "风险端认为必须设置止损线。",
                "scenario_read": {"pessimistic": "现金流收缩会放大后悔。"},
                "critical_disagreements": ["是否能承受三个月无收入"],
                "decision_guardrails": ["保留三个月现金缓冲"],
                "report_paragraph": "风险委员会建议先锁定退路。",
            },
            {
                "panel_name": "机会委员会",
                "position": "可以小步进攻",
                "confidence": 0.68,
                "executive_summary": "机会端认为窗口存在，但要可逆。",
                "scenario_read": {"optimistic": "小步试验可以换来新筹码。"},
                "critical_disagreements": ["窗口期是否足够短"],
                "decision_guardrails": ["先跑两周小样本试验"],
                "report_paragraph": "机会委员会建议保留进攻姿态。",
            },
            {
                "summary": "最终合议建议：先做可逆试验，不要直接 All in。",
                "client_report_memo": "这不是二选一，而是用护栏把行动拆成可撤回实验。",
                "critical_disagreements": ["现金流承压", "窗口期判断"],
                "decision_guardrails": ["三个月现金缓冲", "两周复盘节点"],
                "premium_report_sections": ["客户段落"],
            },
        ]

        result = run_ultra_monte_carlo_collision(
            question="我该不该辞职做AI产品",
            choice_a_sim={"choice_name": "继续稳定工作", "probability_distribution": {"tailwind": {"percent": 20}, "steady": {"percent": 55}, "headwind": {"percent": 25}}},
            choice_b_sim={"choice_name": "辞职转行", "probability_distribution": {"tailwind": {"percent": 34}, "steady": {"percent": 42}, "headwind": {"percent": 24}}},
            user_params={"savings_months": 3},
            sample_count=12,
            persona_count=8,
            agents_per_branch=4,
            rounds=1,
            branch_sample_limit=6,
            llm_panels=2,
            llm_max_tokens=2048,
        )

        self.assertEqual(mock_call_agent_json.call_count, 3)
        self.assertEqual(result["llm_mode"], "multi_panel_llm")
        self.assertEqual(result["llm_calls_attempted"], 3)
        self.assertEqual(result["actual_llm_calls"], 3)
        self.assertEqual(len(result["llm_panel_reports"]), 2)
        self.assertTrue(result["client_report_memo"])
        self.assertIn("三个月现金缓冲", result["decision_guardrails"])

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_c1_reevaluation_falls_back_when_model_returns_empty_payload(self, mock_call_agent_json) -> None:
        mock_call_agent_json.return_value = {}

        result = run_c1_reevaluation(
            "我该不该开gpt会员",
            50,
            50,
            [],
            cognitive_frames=[],
            experience_cases=[],
            emotional_insight={},
            source_detection={
                "result": {"failed_at": "filter2"},
                "filters": {"filter2": {"distribution": "0:0"}},
            },
            diagnosed_blockages=["A"],
        )

        self.assertGreater(result["updated_pro_total"], result["updated_con_total"])
        self.assertTrue(result["recommendation"])
        self.assertTrue(result["action_plan"])
        self.assertTrue(result["reasoning"])
        self.assertEqual(result["fallback_mode"], "c1_placeholder")
        self.assertTrue(result["skip_recheck"])

    @patch("research.engine_b.agents.call_agent_json")
    def test_run_c1_reevaluation_falls_back_when_model_raises(self, mock_call_agent_json) -> None:
        mock_call_agent_json.side_effect = ValueError("模型返回空响应")

        result = run_c1_reevaluation(
            "我该不该开gpt会员",
            50,
            50,
            [],
            cognitive_frames=[],
            experience_cases=[],
            emotional_insight={},
            source_detection={
                "result": {"failed_at": "filter2_uncertain"},
                "filters": {"filter2": {"distribution": "0/4有效"}},
            },
            diagnosed_blockages=["A"],
        )

        self.assertEqual(result["fallback_mode"], "c1_placeholder")
        self.assertTrue(result["skip_recheck"])
        self.assertTrue(result["recommendation"])

    @patch("research.phase2_filter._evaluate_stance")
    def test_filter2_invalid_stance_payloads_are_not_counted_as_real_votes(self, mock_evaluate_stance) -> None:
        mock_evaluate_stance.return_value = {"format": {"type": "text"}, "verbosity": "medium"}

        result = evaluate_question_balance(
            "我该不该开gpt会员",
            stances=[("功利主义者", "a"), ("义务论者", "b"), ("自由主义者", "c"), ("社群主义者", "d")],
            min_valid_agents=4,
        )

        self.assertIsNone(result["passed"])
        self.assertEqual(result["valid_count"], 0)


if __name__ == "__main__":
    unittest.main()
