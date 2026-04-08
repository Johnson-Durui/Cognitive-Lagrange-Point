import unittest
from unittest.mock import patch

import research.single_detect as single_detect


def fake_analysis(*_args, **_kwargs):
    return {
        "tensions": [{"pro": "做", "con": "不做"}],
        "classifications": {"dilemma": 60, "info_gap": 30, "clp": 10},
        "balance_rationale": "正反两边都有现实牵引。",
        "initial_score": 72,
        "analysis_summary": "这是一个真实世界的高代价选择。",
    }


def mark_filter1_pass(candidate, **_kwargs):
    candidate.passed_filter_1 = True
    candidate.filter_1_details = [{"level": 1, "label": "量级1", "delta": 6}]
    candidate.filter_1_summary = "L1 Δ6"
    return candidate


def mark_filter1_uncertain(candidate, **_kwargs):
    candidate.passed_filter_1 = None
    candidate.filter_1_details = []
    candidate.filter_1_summary = ""
    return candidate


def mark_filter2_pass(candidate, **_kwargs):
    candidate.passed_filter_2 = True
    candidate.filter_2_details = [
        {"stance": "功利主义者", "lean_direction": "正方", "lean_strength": 60},
        {"stance": "义务论者", "lean_direction": "反方", "lean_strength": 55},
        {"stance": "自由主义者", "lean_direction": "正方", "lean_strength": 58},
        {"stance": "社群主义者", "lean_direction": "反方", "lean_strength": 57},
    ]
    candidate.filter_2_distribution = "2:2"
    candidate.filter_2_balance_score = 5.0
    return candidate


def mark_filter3_pass(candidate, **_kwargs):
    candidate.passed_filter_3 = True
    candidate.filter_3_details = [{"label": "重述1", "delta": 4}]
    candidate.filter_3_summary = "3/3 保持稳定"
    candidate.filter_3_stable_count = 3
    candidate.filter_3_classification = "stable"
    return candidate


class SingleDetectProfilesTest(unittest.TestCase):
    def test_decision_deep_skips_filter3_and_opens_to_engine_b(self):
        with patch.object(single_detect, "analyze_question_structure", side_effect=fake_analysis), patch.object(
            single_detect, "evaluate_filter1_candidate", side_effect=mark_filter1_pass
        ), patch.object(
            single_detect, "evaluate_filter2_candidate", side_effect=mark_filter2_pass
        ), patch.object(
            single_detect, "evaluate_filter3_candidate"
        ) as mocked_filter3:
            outcome = single_detect.detect_single_question("我该不该换工作", mode="decision_deep")

        self.assertFalse(outcome["result"]["is_lagrange_point"])
        self.assertTrue(outcome["result"]["recommend_engine_b"])
        self.assertEqual(outcome["result"]["failed_at"], "filter3_skipped")
        self.assertIn("不跑筛子3", outcome["filters"]["filter3"]["summary"])
        mocked_filter3.assert_not_called()

    def test_decision_deep_filter1_uncertain_fails_open(self):
        with patch.object(single_detect, "analyze_question_structure", side_effect=fake_analysis), patch.object(
            single_detect, "evaluate_filter1_candidate", side_effect=mark_filter1_uncertain
        ):
            outcome = single_detect.detect_single_question("我该不该换工作", mode="decision_deep")

        self.assertFalse(outcome["result"]["is_lagrange_point"])
        self.assertEqual(outcome["result"]["failed_at"], "filter1_uncertain")
        self.assertIn("Engine B", outcome["result"]["summary"])

    def test_decision_pro_enables_filter3(self):
        class DummyClp:
            def to_dict(self):
                return {"id": "CLP-TEST"}

        with patch.object(single_detect, "analyze_question_structure", side_effect=fake_analysis), patch.object(
            single_detect, "evaluate_filter1_candidate", side_effect=mark_filter1_pass
        ), patch.object(
            single_detect, "evaluate_filter2_candidate", side_effect=mark_filter2_pass
        ), patch.object(
            single_detect, "evaluate_filter3_candidate", side_effect=mark_filter3_pass
        ), patch.object(
            single_detect, "analyze_forces", return_value=DummyClp()
        ) as mocked_filter3:
            outcome = single_detect.detect_single_question("我该不该换工作", mode="decision_pro")

        mocked_filter3.assert_called()
        self.assertTrue(outcome["result"]["is_lagrange_point"])

    def test_decision_ultra_uses_all_frameworks(self):
        profile = single_detect.resolve_detection_profile("decision_ultra")
        self.assertEqual(profile.philosopher_count, len(single_detect.STANCES))
        self.assertTrue(profile.enable_filter3)


if __name__ == "__main__":
    unittest.main()
