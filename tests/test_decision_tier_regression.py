import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from decision.tiers import get_tier_config, normalize_tier


def make_decision(tier: str):
    return {
        "active": tier != "quick",
        "decision": {
            "decision_id": f"{tier}-demo",
            "question": "我该不该换工作？",
            "tier": tier,
            "status": "completed" if tier == "quick" else "running",
            "phase": "completed" if tier == "quick" else "act2",
            "status_text": f"{tier} 模式已启动",
        },
    }


class DecisionTierRegressionTest(unittest.TestCase):
    def test_normalize_tier_defaults_to_deep(self):
        self.assertEqual(normalize_tier(""), "deep")
        self.assertEqual(normalize_tier("unknown"), "deep")
        self.assertEqual(normalize_tier("PANORAMA"), "ultra")
        self.assertEqual(normalize_tier("FLASH"), "quick")

    def test_tier_configs_keep_expected_capabilities(self):
        quick = get_tier_config("quick")
        deep = get_tier_config("deep")
        pro = get_tier_config("pro")
        ultra = get_tier_config("ultra")

        self.assertFalse(quick["enable_simulation"])
        self.assertFalse(deep["enable_simulation"])
        self.assertTrue(pro["enable_simulation"])
        self.assertTrue(pro["force_full_enrichment"])
        self.assertEqual(pro["choice_extract_max_tokens"], 1600)
        self.assertFalse(pro["enable_ultra_monte_carlo"])
        self.assertTrue(ultra["enable_emotion_mirror"])
        self.assertTrue(ultra["enable_oscillation"])
        self.assertTrue(ultra["enable_ultra_monte_carlo"])
        self.assertGreaterEqual(ultra["ultra_mc_branches"], 500)
        self.assertEqual(ultra["ultra_mc_estimated_tokens"], 10_000_000)
        self.assertEqual(ultra["estimated_tokens"], 10_520_000)
        self.assertEqual(ultra["ultra_mc_llm_panels"], 8)
        self.assertEqual(ultra["ultra_mc_llm_max_tokens"], 8192)
        self.assertGreater(ultra["act1_estimated_tokens"], pro["act1_estimated_tokens"])
        self.assertGreater(ultra["b7_max_tokens"], pro["b7_max_tokens"])
        self.assertGreater(ultra["b9_max_tokens"], pro["b9_max_tokens"])

    def test_ultra_monte_carlo_budget_can_float_by_env(self):
        with patch.dict("os.environ", {"CLP_ULTRA_MC_ESTIMATED_TOKENS": "30000000"}):
            ultra = get_tier_config("ultra")

        self.assertEqual(ultra["ultra_mc_estimated_tokens"], 30_000_000)
        self.assertEqual(ultra["estimated_tokens"], 30_520_000)

    def test_api_exposes_all_four_tiers(self):
        with TestClient(server.app) as client:
            response = client.get("/api/decision/tiers")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(set(payload["tiers"].keys()), {"quick", "deep", "pro", "ultra"})
        self.assertEqual(payload["default_tier"], "deep")

    def test_api_accepts_new_and_legacy_tiers_on_start(self):
        with TestClient(server.app) as client:
            for tier in ("quick", "deep", "pro", "ultra", "flash", "panorama"):
                normalized = normalize_tier(tier)
                with patch.object(server.DECISIONS, "start", return_value=make_decision(normalized)) as mocked_start:
                    response = client.post(
                        "/api/decision/start",
                        json={"question": "我该不该换工作？", "tier": tier},
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["decision"]["tier"], normalized)
                mocked_start.assert_called_once_with("我该不该换工作？", tier)

    def test_api_upgrade_uses_existing_decision(self):
        upgraded = make_decision("deep")
        upgraded["decision"]["decision_id"] = "quick-demo"
        upgraded["decision"]["meta"] = {"upgraded_from": "quick-demo"}

        with TestClient(server.app) as client:
            with patch.object(server.DECISIONS, "upgrade", return_value=upgraded) as mocked_upgrade:
                response = client.post(
                    "/api/decision/upgrade",
                    json={"decision_id": "quick-demo", "tier": "deep"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["decision"]["decision_id"], "quick-demo")
        self.assertEqual(payload["decision"]["tier"], "deep")
        mocked_upgrade.assert_called_once_with("quick-demo", "deep")

    def test_api_accepts_feedback_submission(self):
        feedback_payload = make_decision("pro")
        feedback_payload["decision"]["decision_id"] = "pro-demo"
        feedback_payload["decision"]["feedback"] = {
            "user_choice": "先试一个月",
            "satisfaction": 4,
            "note": "记录使用频率再决定",
        }

        with TestClient(server.app) as client:
            with patch.object(server.DECISIONS, "submit_feedback", return_value=feedback_payload) as mocked_feedback:
                response = client.post(
                    "/api/decision/feedback",
                    json={
                        "decision_id": "pro-demo",
                        "user_choice": "先试一个月",
                        "satisfaction": 4,
                        "follow_up_note": "记录使用频率再决定",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["decision"]["decision_id"], "pro-demo")
        mocked_feedback.assert_called_once_with(
            "pro-demo",
            user_choice="先试一个月",
            satisfaction=4,
            note="记录使用频率再决定",
        )


if __name__ == "__main__":
    unittest.main()
