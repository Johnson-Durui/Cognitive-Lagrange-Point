import unittest
from unittest.mock import Mock, patch

from research.engine_b.models import DiagnosisQuestion, EngineBPhase, EngineBSession
from research.engine_b import runtime as engine_b_runtime
from research.engine_b.runtime import (
    enrich_engine_b_session,
    get_engine_b_status_for_session,
    start_engine_b_session,
    start_simulator,
    submit_sim_answer,
)


def make_session(phase: EngineBPhase) -> EngineBSession:
    return EngineBSession(
        session_id="sess1234",
        original_question="我该不该开 Claude",
        tier="deep",
        phase=phase,
        recommendation="先小步验证",
        created_at="2026-04-07T09:00:00+08:00",
        updated_at="2026-04-07T09:00:00+08:00",
    )


class EngineBRuntimeTest(unittest.TestCase):
    @patch("research.engine_b.runtime.threading.Thread")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.run_b1_diagnosis")
    def test_start_engine_b_auto_continues_when_no_diagnosis_questions(
        self,
        mock_run_b1,
        mock_save_session,
        mock_trace,
        mock_thread_cls,
    ) -> None:
        mock_run_b1.return_value = []
        thread_instance = Mock()
        mock_thread_cls.return_value = thread_instance

        session = start_engine_b_session("我该不该开 Claude")

        self.assertEqual(session.phase, EngineBPhase.B2_INFO_FILL)
        mock_run_b1.assert_called_once()
        self.assertGreaterEqual(mock_save_session.call_count, 2)
        mock_trace.assert_called()
        thread_instance.start.assert_called_once()

    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.run_b1_diagnosis")
    def test_start_engine_b_respects_tier_diagnosis_count(
        self,
        mock_run_b1,
        _mock_save_session,
    ) -> None:
        mock_run_b1.return_value = [
            DiagnosisQuestion(id=f"q{i}", question_text=f"Q{i}")
            for i in range(1, 6)
        ]

        deep_session = start_engine_b_session("我该不该开 Claude", tier="deep")
        ultra_session = start_engine_b_session("我该不该开 Claude", tier="ultra")

        self.assertEqual(deep_session.tier, "deep")
        self.assertEqual(len(deep_session.diagnosis_questions), 4)
        self.assertEqual(ultra_session.tier, "ultra")
        self.assertEqual(len(ultra_session.diagnosis_questions), 5)
        self.assertEqual(mock_run_b1.call_args_list[0].kwargs.get("max_tokens"), 2048)
        self.assertEqual(mock_run_b1.call_args_list[1].kwargs.get("max_tokens"), 6144)

    @patch("research.engine_b.runtime._maybe_start_engine_b_recheck")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.external_signal_store.retrieve_external_signals")
    @patch("research.engine_b.runtime.engine_b_agents.run_c1_reevaluation")
    @patch("research.engine_b.runtime.engine_b_agents.run_b5_emotional_mirror")
    @patch("research.engine_b.runtime.engine_b_agents.run_b4_experience_simulation")
    @patch("research.engine_b.runtime.engine_b_agents.run_b3_cognitive_unlock")
    @patch("research.engine_b.runtime.engine_b_agents.run_b2_info_gathering")
    @patch("research.engine_b.runtime.engine_b_agents.infer_blockages_from_answers")
    def test_enrich_session_respects_deep_tier_agent_gates(
        self,
        mock_infer,
        mock_b2,
        mock_b3,
        mock_b4,
        mock_b5,
        mock_c1,
        mock_signals,
        _mock_save_session,
        _mock_trace,
        mock_recheck,
    ) -> None:
        session = make_session(EngineBPhase.B2_INFO_FILL)
        session.tier = "deep"
        session.diagnosis_questions = [DiagnosisQuestion(id="q1", question_text="Q1")]
        session.diagnosis_answers = {"q1": "A"}
        mock_signals.return_value = [{"summary": "高频用户更容易觉得值回票价", "stance": "positive"}]
        mock_infer.return_value = ["A", "B", "C", "D"]
        mock_b2.return_value = [{"title": "信息"}]
        mock_b3.return_value = [{"title": "框架"}]
        mock_c1.return_value = {
            "updated_pro_total": 62,
            "updated_con_total": 38,
            "recommendation": "先试一个月",
            "action_plan": "列出试用场景",
            "reasoning": "deep 档不跑经验和情绪",
        }
        mock_recheck.side_effect = lambda current: current

        enrich_engine_b_session(session, force=True)

        mock_b2.assert_called_once()
        mock_b3.assert_called_once()
        mock_b4.assert_not_called()
        mock_b5.assert_not_called()
        self.assertEqual(session.external_signals, mock_signals.return_value)
        self.assertEqual(mock_b2.call_args.kwargs.get("external_signals"), mock_signals.return_value)
        self.assertEqual(mock_c1.call_args.kwargs.get("external_signals"), mock_signals.return_value)

    @patch("research.engine_b.runtime._maybe_start_engine_b_recheck")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.run_c1_reevaluation")
    @patch("research.engine_b.runtime.engine_b_agents.run_b5_emotional_mirror")
    @patch("research.engine_b.runtime.engine_b_agents.run_b4_experience_simulation")
    @patch("research.engine_b.runtime.engine_b_agents.run_b3_cognitive_unlock")
    @patch("research.engine_b.runtime.engine_b_agents.run_b2_info_gathering")
    @patch("research.engine_b.runtime.engine_b_agents.infer_blockages_from_answers")
    def test_ultra_can_force_full_enrichment(
        self,
        mock_infer,
        mock_b2,
        mock_b3,
        mock_b4,
        mock_b5,
        mock_c1,
        _mock_save_session,
        _mock_trace,
        mock_recheck,
    ) -> None:
        session = make_session(EngineBPhase.B2_INFO_FILL)
        session.tier = "ultra"
        session.diagnosis_questions = [DiagnosisQuestion(id="q1", question_text="Q1")]
        session.diagnosis_answers = {"q1": "A"}
        mock_infer.return_value = []
        mock_b2.return_value = [{"title": "信息"}]
        mock_b3.return_value = [{"title": "框架"}]
        mock_b4.return_value = [{"title": "经验"}]
        mock_b5.return_value = {"dominant_emotions": [{"emotion": "害怕"}]}
        mock_c1.return_value = {
            "updated_pro_total": 58,
            "updated_con_total": 42,
            "recommendation": "全景继续",
            "action_plan": "先做最小试验",
            "reasoning": "ultra 全量补齐",
        }
        mock_recheck.side_effect = lambda current: current

        enrich_engine_b_session(session, force=True)

        mock_b2.assert_called_once()
        mock_b3.assert_called_once()
        mock_b4.assert_called_once()
        mock_b5.assert_called_once()

    @patch("research.engine_b.runtime.db_register_engine_b_as_clp")
    @patch("research.engine_b.runtime._maybe_start_engine_b_recheck")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.run_c1_reevaluation")
    @patch("research.engine_b.runtime.engine_b_agents.run_b5_emotional_mirror")
    @patch("research.engine_b.runtime.engine_b_agents.run_b4_experience_simulation")
    @patch("research.engine_b.runtime.engine_b_agents.run_b3_cognitive_unlock")
    @patch("research.engine_b.runtime.engine_b_agents.run_b2_info_gathering")
    @patch("research.engine_b.runtime.engine_b_agents.infer_blockages_from_answers")
    def test_c1_placeholder_result_skips_recheck_and_clp_registration(
        self,
        mock_infer,
        mock_b2,
        mock_b3,
        mock_b4,
        mock_b5,
        mock_c1,
        _mock_save_session,
        _mock_trace,
        mock_recheck,
        mock_register_clp,
    ) -> None:
        session = make_session(EngineBPhase.B2_INFO_FILL)
        session.tier = "deep"
        session.diagnosis_questions = [DiagnosisQuestion(id="q1", question_text="Q1")]
        session.diagnosis_answers = {"q1": "A"}
        mock_infer.return_value = ["A"]
        mock_b2.return_value = []
        mock_b3.return_value = []
        mock_c1.return_value = {
            "updated_pro_total": 50,
            "updated_con_total": 50,
            "recommendation": "仍需更多信息",
            "action_plan": "先列关键条件",
            "reasoning": "这次 50:50 只是占位状态。",
            "skip_recheck": True,
            "fallback_mode": "c1_placeholder",
        }

        result = enrich_engine_b_session(session, force=True)

        self.assertIs(result, session)
        self.assertEqual(session.recheck.get("status"), "skipped")
        mock_recheck.assert_not_called()
        mock_register_clp.assert_not_called()

    @patch("research.engine_b.runtime.threading.Thread")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.run_b6_sim_params")
    @patch("research.engine_b.runtime.session_has_c1_result")
    @patch("research.engine_b.runtime.engine_b_state.load_session")
    def test_start_simulator_generates_required_param_questions_even_if_model_returns_empty(
        self,
        mock_load_session,
        mock_has_c1,
        mock_run_b6,
        _mock_save_session,
        _mock_trace,
        mock_thread_cls,
    ) -> None:
        session = make_session(EngineBPhase.C1_REEVALUATION)
        mock_load_session.return_value = session
        mock_has_c1.return_value = True
        mock_run_b6.return_value = []
        thread_instance = Mock()
        mock_thread_cls.return_value = thread_instance
        session.tier = "pro"

        result = start_simulator("sess1234")

        self.assertEqual(result.phase, EngineBPhase.B6_SIM_PARAMS)
        mock_run_b6.assert_called_once()
        mock_thread_cls.assert_not_called()
        thread_instance.start.assert_not_called()
        self.assertGreaterEqual(len(result.sim_questions), 5)

    @patch("research.engine_b.runtime.threading.Thread")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.run_b6_sim_params")
    @patch("research.engine_b.runtime.session_has_c1_result")
    @patch("research.engine_b.runtime.engine_b_state.load_session")
    def test_start_simulator_is_idempotent_after_generation_begins(
        self,
        mock_load_session,
        mock_has_c1,
        mock_run_b6,
        _mock_save_session,
        _mock_trace,
        mock_thread_cls,
    ) -> None:
        session = make_session(EngineBPhase.B7_SIM_TIMELINES)
        session.tier = "pro"
        mock_load_session.return_value = session
        mock_has_c1.return_value = True

        result = start_simulator("sess1234")

        self.assertIs(result, session)
        mock_run_b6.assert_not_called()
        mock_thread_cls.assert_not_called()

    @patch("research.engine_b.runtime.engine_b_state.load_session")
    def test_get_engine_b_status_backfills_empty_simulator_summary(self, mock_load_session) -> None:
        session = make_session(EngineBPhase.SIMULATOR_COMPLETE)
        session.simulator_output = {
            "user_params": {"savings_months": 2},
            "choice_a": {
                "choice_name": "留下",
                "probability_distribution": {
                    "tailwind": {"percent": 25},
                    "steady": {"percent": 50},
                    "headwind": {"percent": 25},
                },
                "timelines": {
                    "steady": {
                        "nodes": [
                            {"time": "第1周", "key_action": "列出留下后的试运行目标"},
                        ],
                    },
                },
            },
            "choice_b": {
                "choice_name": "离开",
                "probability_distribution": {
                    "tailwind": {"percent": 20},
                    "steady": {"percent": 45},
                    "headwind": {"percent": 35},
                },
                "timelines": {
                    "steady": {
                        "nodes": [
                            {"time": "第1周", "key_action": "先验证外部机会的现金流"},
                        ],
                    },
                },
            },
            "comparison_summary": "",
            "action_map_a": [],
            "action_map_b": [],
            "final_insight": "",
        }
        mock_load_session.return_value = session

        payload = get_engine_b_status_for_session("sess1234")

        self.assertTrue(payload["active"])
        output = payload["session"]["simulator_output"]
        self.assertTrue(output["comparison_summary"])
        self.assertTrue(output["final_insight"])
        self.assertGreater(len(output["action_map_a"]), 0)
        self.assertGreater(len(output["action_map_b"]), 0)

    @patch("research.engine_b.runtime.engine_b_state.load_session")
    def test_start_simulator_rejects_quick_tier(self, mock_load_session) -> None:
        session = make_session(EngineBPhase.C1_REEVALUATION)
        session.tier = "quick"
        mock_load_session.return_value = session

        with self.assertRaisesRegex(ValueError, "没有开启未来模拟"):
            start_simulator("sess1234")

    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_state.load_session")
    def test_submit_sim_answer_adds_followup_when_critical_params_missing(
        self,
        mock_load_session,
        _mock_save_session,
        _mock_trace,
    ) -> None:
        session = make_session(EngineBPhase.B6_SIM_PARAMS)
        session.sim_questions = [
            {"id": "q1", "field_name": "savings_months", "question_text": "安全垫？", "options": ["1个月内"]},
            {"id": "q2", "field_name": "time_to_reverse", "question_text": "多久回头？", "options": ["1个月内"]},
            {"id": "q3", "field_name": "worst_fear", "question_text": "最怕什么？", "options": ["花钱后不值"]},
        ]
        session.sim_answers = {"q1": "1个月内", "q2": "1个月内"}
        mock_load_session.return_value = session

        result = submit_sim_answer("sess1234", "q3", "花钱后发现不值")

        self.assertEqual(result.phase, EngineBPhase.B6_SIM_PARAMS)
        self.assertGreater(len(result.sim_questions), 3)
        field_names = [item.get("field_name") for item in result.sim_questions]
        self.assertIn("fixed_expenses", field_names)
        self.assertIn("reversal_cost", field_names)

    @patch("research.engine_b.runtime._mark_engine_b_error")
    @patch("research.engine_b.runtime._append_processing_trace")
    @patch("research.engine_b.runtime.engine_b_state.save_session")
    @patch("research.engine_b.runtime.engine_b_agents.normalize_simulator_output")
    @patch("research.engine_b.runtime.engine_b_agents.run_ultra_monte_carlo_collision")
    @patch("research.engine_b.runtime.engine_b_agents.run_b9_comparison")
    @patch("research.engine_b.runtime.engine_b_agents.run_b8_coping_plan")
    @patch("research.engine_b.runtime._regenerate_similar_timeline_if_needed")
    @patch("research.engine_b.runtime.engine_b_agents.run_b7_timeline")
    @patch("research.engine_b.runtime.engine_b_agents.extract_choice_options")
    @patch("research.engine_b.runtime._build_simulator_user_context")
    @patch("research.engine_b.runtime.engine_b_agents.parse_sim_params_from_answers")
    @patch("research.engine_b.runtime.engine_b_state.load_session")
    def test_run_simulator_async_uses_tier_config_before_choice_extraction(
        self,
        mock_load_session,
        mock_parse_params,
        mock_build_context,
        mock_extract_choices,
        mock_run_b7,
        mock_regenerate,
        mock_run_b8,
        mock_run_b9,
        mock_monte_carlo,
        mock_normalize,
        _mock_save_session,
        _mock_trace,
        mock_mark_error,
    ) -> None:
        session = make_session(EngineBPhase.B7_SIM_TIMELINES)
        session.tier = "ultra"
        session.external_signals = [{"summary": "有人担心订阅后退款链路麻烦", "stance": "negative"}]
        session.sim_answers = {
            "simq1": "1个月内",
            "simq2": "3000元内",
            "simq3": "一周内就能停",
            "simq4": "会亏搬家/租房成本",
            "simq5": "花钱/投入后发现不值",
        }
        session.sim_questions = [
            {"id": "simq1", "field_name": "savings_months"},
            {"id": "simq2", "field_name": "fixed_expenses"},
            {"id": "simq3", "field_name": "time_to_reverse"},
            {"id": "simq4", "field_name": "reversal_cost"},
            {"id": "simq5", "field_name": "worst_fear"},
        ]
        mock_load_session.side_effect = [session, session, session, session]
        mock_parse_params.return_value = {
            "savings_months": 1,
            "fixed_expenses": "3000元内",
            "time_to_reverse": "一周内就能停",
            "reversal_cost": "会亏搬家/租房成本",
            "worst_fear": "花钱/投入后发现不值",
        }
        mock_build_context.return_value = "context"
        mock_extract_choices.return_value = [
            {"name": "继续工作", "description": "保留稳定现金流"},
            {"name": "辞职读研", "description": "争取长期转行筹码"},
        ]
        mock_run_b7.side_effect = [
            {"choice_name": "继续工作", "timelines": {}, "probability_distribution": {}},
            {"choice_name": "辞职读研", "timelines": {}, "probability_distribution": {}},
        ]
        mock_regenerate.side_effect = lambda *_args, **kwargs: (
            kwargs["choice_a_timelines"],
            kwargs["choice_b_timelines"],
        )
        mock_run_b8.return_value = {
            "crossroads": [],
            "worst_case_survival_plan": {},
            "milestone_check_system": [],
        }
        mock_run_b9.return_value = {
            "comparison_summary": "先稳住现金流，同时做低成本试验。",
            "action_map_a": ["保留当前收入，先验证目标方向"],
            "action_map_b": ["把读研转行拆成可逆试验"],
            "final_insight": "真正的问题不是选哪条，而是怎么降低第一次出手成本。",
            "regret_score_a": 42,
            "regret_score_b": 58,
            "probability_optimistic": 28,
            "probability_baseline": 49,
            "probability_pessimistic": 23,
        }
        mock_monte_carlo.return_value = {
            "sample_count": 800,
            "smooth_prob": {"optimistic": 31, "baseline": 47, "pessimistic": 22},
            "disagreement_heatmap": [],
        }
        mock_normalize.side_effect = lambda payload: payload

        engine_b_runtime._run_simulator_async("sess1234")

        self.assertEqual(
            mock_extract_choices.call_args.kwargs.get("max_tokens"),
            2400,
        )
        self.assertEqual(
            mock_run_b9.call_args.kwargs.get("external_signals"),
            session.external_signals,
        )
        self.assertEqual(session.phase, EngineBPhase.SIMULATOR_COMPLETE)
        self.assertTrue(session.simulator_output)
        self.assertEqual(
            session.simulator_output.get("market_signals"),
            session.external_signals,
        )
        self.assertEqual(session.simulator_output.get("monte_carlo"), mock_monte_carlo.return_value)
        self.assertEqual(session.simulator_output.get("probability_optimistic"), 31)
        self.assertEqual(session.simulator_output.get("probability_baseline"), 47)
        self.assertEqual(session.simulator_output.get("probability_pessimistic"), 22)
        mock_monte_carlo.assert_called_once()
        mock_mark_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
