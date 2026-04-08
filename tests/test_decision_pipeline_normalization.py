import unittest
from unittest.mock import patch

from decision.pipeline import DecisionManager


class DecisionPipelineNormalizationTest(unittest.TestCase):
    @patch("decision.pipeline.db_load_decision_session")
    def test_get_status_backfills_completed_simulator_output(self, mock_load_decision) -> None:
        mock_load_decision.return_value = {
            "decision_id": "dec12345",
            "question": "我该不该换工作？",
            "tier": "deep",
            "status": "completed",
            "phase": "completed",
            "status_text": "决策完成",
            "created_at": "2026-04-07T10:00:00+08:00",
            "updated_at": "2026-04-07T10:10:00+08:00",
            "engineb_session": {
                "session_id": "sess1234",
                "phase": "simulator_complete",
                "simulator_output": {
                    "user_params": {"savings_months": 1},
                    "choice_a": {
                        "choice_name": "继续做",
                        "probability_distribution": {
                            "tailwind": {"percent": 30},
                            "steady": {"percent": 45},
                            "headwind": {"percent": 25},
                        },
                        "timelines": {
                            "steady": {
                                "nodes": [
                                    {"time": "第1周", "key_action": "先做小范围验证"},
                                ],
                            },
                        },
                    },
                    "choice_b": {
                        "choice_name": "暂缓做",
                        "probability_distribution": {
                            "tailwind": {"percent": 20},
                            "steady": {"percent": 40},
                            "headwind": {"percent": 40},
                        },
                        "timelines": {
                            "steady": {
                                "nodes": [
                                    {"time": "第1周", "key_action": "先把风险预算算清楚"},
                                ],
                            },
                        },
                    },
                    "comparison_summary": "",
                    "action_map_a": [],
                    "action_map_b": [],
                    "final_insight": "",
                },
            },
        }

        manager = DecisionManager(detection_manager=None)
        payload = manager.get_status("dec12345")

        self.assertFalse(payload["active"])
        output = payload["decision"]["engineb_session"]["simulator_output"]
        self.assertTrue(output["comparison_summary"])
        self.assertTrue(output["final_insight"])
        self.assertGreater(len(output["action_map_a"]), 0)
        self.assertGreater(len(output["action_map_b"]), 0)


if __name__ == "__main__":
    unittest.main()
