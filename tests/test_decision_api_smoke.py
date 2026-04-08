import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import server


def make_decision(**overrides):
    base = {
        "decision_id": "dec12345",
        "question": "我该不该换工作？",
        "tier": "deep",
        "status": "running",
        "phase": "act2",
        "status_text": "正在进入第二幕",
        "engineb_session": {
          "session_id": "sess1234",
          "phase": "b1_diagnosis",
          "diagnosis_questions": [
            {"id": "q1", "text": "你最担心失去什么？"}
          ],
          "diagnosis_answers": {},
        },
    }
    base.update(overrides)
    return {"active": base.get("status") == "running", "decision": base}


class DecisionApiSmokeTest(unittest.TestCase):
    def test_decision_start_returns_decision_status(self):
        with TestClient(server.app) as client, patch.object(
            server.DECISIONS,
            "start",
            return_value=make_decision(),
        ) as mocked_start:
            response = client.post(
                "/api/decision/start",
                json={"question": "我该不该换工作？", "tier": "deep"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["decision"]["decision_id"], "dec12345")
        mocked_start.assert_called_once_with("我该不该换工作？", "deep")

    def test_decision_start_rejects_blank_question(self):
        with TestClient(server.app) as client:
            response = client.post(
                "/api/decision/start",
                json={"question": "   ", "tier": "deep"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不能为空", response.text)

    def test_decision_answer_routes_to_manager(self):
        updated = make_decision(
            engineb_session={
                "session_id": "sess1234",
                "phase": "c1_reevaluation",
                "diagnosis_questions": [{"id": "q1", "text": "你最担心失去什么？"}],
                "diagnosis_answers": {"q1": "成长机会"},
                "recommendation": "更偏向去新岗位",
            },
            status_text="建议已生成",
        )

        with TestClient(server.app) as client, patch.object(
            server.DECISIONS,
            "submit_answer",
            return_value=updated,
        ) as mocked_submit:
            response = client.post(
                "/api/decision/answer",
                json={
                    "decision_id": "dec12345",
                    "question_id": "q1",
                    "answer": "成长机会",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["decision"]["engineb_session"]["diagnosis_answers"]["q1"],
            "成长机会",
        )
        mocked_submit.assert_called_once_with("dec12345", "q1", "成长机会")

    def test_decision_simulate_start_routes_to_manager(self):
        simulated = make_decision(
            phase="act3",
            status_text="开始第三幕：未来模拟",
            engineb_session={
                "session_id": "sess1234",
                "phase": "b6_sim_params",
                "sim_questions": [{"id": "s1", "text": "你的安全垫有多久？"}],
                "sim_answers": {},
            },
        )

        with TestClient(server.app) as client, patch.object(
            server.DECISIONS,
            "start_simulator",
            return_value=simulated,
        ) as mocked_simulate:
            response = client.post(
                "/api/decision/simulate/start",
                json={"decision_id": "dec12345"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["decision"]["phase"], "act3")
        self.assertEqual(payload["decision"]["engineb_session"]["phase"], "b6_sim_params")
        mocked_simulate.assert_called_once_with("dec12345")

    def test_decision_history_returns_saved_rows(self):
        history = [
            {
                "decision_id": "dec12345",
                "question": "我该不该换工作？",
                "tier": "deep",
                "status": "completed",
                "phase": "completed",
                "created_at": "2026-04-06T18:00:00+08:00",
                "updated_at": "2026-04-06T18:10:00+08:00",
            }
        ]

        with TestClient(server.app) as client, patch.object(
            server.DECISIONS,
            "list_history",
            return_value=history,
        ):
            response = client.get("/api/decision/history")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["decisions"][0]["decision_id"], "dec12345")


if __name__ == "__main__":
    unittest.main()
