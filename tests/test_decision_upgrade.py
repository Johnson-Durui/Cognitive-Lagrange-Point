import unittest
from unittest.mock import patch

from decision.pipeline import DecisionManager


class DummyDetectionManager:
    def get_status(self, job_id: str) -> dict:
        return {"job": {"job_id": job_id, "status": "running"}}


class DecisionUpgradeTest(unittest.TestCase):
    @patch("decision.pipeline.db_save_decision_session")
    def test_upgrade_quick_to_deep_reuses_same_decision_id(self, _mock_save) -> None:
        manager = DecisionManager(detection_manager=DummyDetectionManager())
        decision = manager._base_job("我该不该换工作？", "quick")
        decision["status"] = "completed"
        decision["phase"] = "completed"
        decision["step"] = "done"
        decision["result"] = {"mode": "quick", "summary": "快速建议"}
        manager.jobs[decision["decision_id"]] = decision

        with patch.object(manager, "_spawn_worker") as mock_spawn:
            payload = manager.upgrade(decision["decision_id"], "deep")

        upgraded = payload["decision"]
        self.assertTrue(payload["active"])
        self.assertEqual(upgraded["decision_id"], decision["decision_id"])
        self.assertEqual(upgraded["tier"], "deep")
        self.assertEqual(upgraded["phase"], "act1")
        self.assertIsNone(upgraded["result"])
        self.assertEqual(upgraded["linked_detection_job_id"], "")
        self.assertEqual(upgraded["linked_engineb_session_id"], "")
        self.assertIn("升级到", " ".join(upgraded["logs"]))
        self.assertEqual(
            mock_spawn.call_args[0][1:],
            (decision["decision_id"], "我该不该换工作？", "deep"),
        )

    @patch("decision.pipeline.db_save_decision_session")
    def test_upgrade_deep_to_pro_reuses_detection_snapshot(self, _mock_save) -> None:
        manager = DecisionManager(detection_manager=DummyDetectionManager())
        decision = manager._base_job("我该不该换工作？", "deep")
        decision["status"] = "completed"
        decision["phase"] = "completed"
        decision["step"] = "done"
        decision["linked_detection_job_id"] = "det12345"
        decision["linked_engineb_session_id"] = "sess1234"
        decision["detection_job"] = {
            "job_id": "det12345",
            "status": "completed",
            "result": {
                "failed_at": "filter2",
                "summary": "初检认为这是有方向的问题",
            },
        }
        decision["engineb_session"] = {
            "session_id": "sess1234",
            "phase": "completed",
            "recommendation": "先试一个月",
            "source_detection": decision["detection_job"],
        }
        decision["result"] = {"mode": "engineb_complete"}
        manager.jobs[decision["decision_id"]] = decision

        with patch.object(manager, "_spawn_worker") as mock_spawn:
            payload = manager.upgrade(decision["decision_id"], "pro")

        upgraded = payload["decision"]
        self.assertTrue(payload["active"])
        self.assertEqual(upgraded["decision_id"], decision["decision_id"])
        self.assertEqual(upgraded["tier"], "pro")
        self.assertEqual(upgraded["linked_detection_job_id"], "det12345")
        self.assertEqual(upgraded["linked_engineb_session_id"], "")
        self.assertIsNone(upgraded["result"])
        self.assertEqual(upgraded["phase"], "act2")
        self.assertEqual(upgraded["step"], "b1_diagnosis")
        self.assertIn("第二幕会按新档位重跑", " ".join(upgraded["logs"]))
        self.assertEqual(mock_spawn.call_args[0][1], decision["decision_id"])
        self.assertEqual(mock_spawn.call_args[0][2], "我该不该换工作？")
        self.assertEqual(mock_spawn.call_args[0][3]["job_id"], "det12345")


if __name__ == "__main__":
    unittest.main()
