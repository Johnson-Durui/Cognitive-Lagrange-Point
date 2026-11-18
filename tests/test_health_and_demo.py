"""Tests for /api/health, /api/system/info, offline Demo Mode, and PDF report exports."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend
import server


class HealthAndDemoResilienceTest(unittest.TestCase):
    def test_root_server_reexports_modular_backend_symbols(self) -> None:
        self.assertIs(server.app, backend.app)
        self.assertIs(server.DECISIONS, backend.DECISIONS)
        self.assertIs(server.DETECTION, backend.DETECTION)
        self.assertIs(server.RUNTIME, backend.RUNTIME)

    def test_cli_arg_parser_supports_host_port_and_demo(self) -> None:
        parser = server.build_arg_parser()
        args = parser.parse_args(["--host", "0.0.0.0", "--port", "8088", "--demo"])
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 8088)
        self.assertTrue(args.demo)
        self.assertFalse(args.reload)

    def test_health_endpoint_reports_engine_and_demo_readiness(self) -> None:
        with (
            patch.dict(os.environ, {"CLP_API_KEY": "", "CLP_DEMO_MODE": "0"}, clear=False),
            patch("backend.shared.load_env_file", return_value={}),
            TestClient(server.app) as client,
        ):
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["engines"]["engine_a"], "ready")
        self.assertEqual(payload["engines"]["engine_b"], "ready")
        self.assertEqual(payload["engines"]["decision_protocol"], "ready")
        self.assertEqual(payload["engines"]["pdf_reporter"], "ready")
        self.assertTrue(payload["database"]["ready"])
        self.assertEqual(set(payload["supported_tiers"]), {"quick", "deep", "pro", "ultra"})
        self.assertFalse(payload["llm_configured"])
        self.assertTrue(payload["demo_fallback_available"])
        self.assertTrue(payload["demo_mode_active"])

    def test_system_info_masks_api_key_and_exposes_tier_matrix(self) -> None:
        raw_secret = "sk-live-super-secret-token-9876543210"
        with (
            patch.dict(
                os.environ,
                {
                    "CLP_API_KEY": raw_secret,
                    "CLP_BASE_URL": "https://api.example.com/v1",
                    "CLP_MODEL": "claude-sonnet-4-6",
                    "CLP_MODEL_FALLBACKS": "deepseek-v3, gpt-4o",
                    "CLP_DEMO_MODE": "0",
                },
                clear=False,
            ),
            patch("backend.shared.load_env_file", return_value={}),
            TestClient(server.app) as client,
        ):
            response = client.get("/api/system/info")

        self.assertEqual(response.status_code, 200)
        body_text = response.text
        self.assertNotIn(raw_secret, body_text)

        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["supported_tiers"], ["quick", "deep", "pro", "ultra"])
        self.assertEqual(payload["default_tier"], "deep")
        self.assertTrue(payload["llm"]["configured"])
        self.assertTrue(payload["llm"]["api_key_present"])
        self.assertEqual(payload["llm"]["api_key_masked"], "sk-l...3210")
        self.assertEqual(payload["llm"]["fallbacks"], ["deepseek-v3", "gpt-4o"])
        self.assertFalse(payload["demo"]["active"])
        self.assertTrue(payload["demo"]["fallback_available"])

    def test_placeholder_api_key_triggers_automatic_demo_fallback(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"CLP_API_KEY": "sk-xxxxxxxx", "CLP_DEMO_MODE": "0"},
                clear=False,
            ),
            patch("backend.shared.load_env_file", return_value={}),
            TestClient(server.app) as client,
        ):
            info_resp = client.get("/api/system/info")
            start_resp = client.post(
                "/api/decision/start",
                json={"question": "我该继续留在稳定工作，还是辞职转行做AI产品？", "tier": "pro"},
            )

        self.assertFalse(info_resp.json()["llm"]["configured"])
        self.assertTrue(info_resp.json()["demo"]["active"])

        self.assertEqual(start_resp.status_code, 200)
        start_payload = start_resp.json()
        self.assertTrue(start_payload["ok"])
        decision = start_payload["decision"]
        self.assertEqual(decision["status"], "completed")
        self.assertEqual(decision["phase"], "completed")
        self.assertTrue(decision["meta"]["demo_mode"])
        self.assertEqual(decision["result"]["mode"], "decision_complete")

        session = decision["engineb_session"]
        self.assertTrue(session["recommendation"])
        self.assertTrue(session["alternative_path"]["title"])
        self.assertIsInstance(session["simulator_output"], dict)
        self.assertGreater(len(session["simulator_output"]["action_map_a"]), 0)
        self.assertGreater(len(session["simulator_output"]["action_map_b"]), 0)

    def test_explicit_demo_flag_runs_ultra_monte_carlo_and_exports_both_pdfs(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"CLP_API_KEY": "sk-live-configured-key-1234567890", "CLP_DEMO_MODE": "0"},
                clear=False,
            ),
            patch("backend.shared.load_env_file", return_value={}),
            TestClient(server.app) as client,
        ):
            start_resp = client.post(
                "/api/decision/start",
                json={
                    "question": "我要不要放弃年终奖提前去创业公司？",
                    "tier": "ultra",
                    "demo": True,
                },
            )
            self.assertEqual(start_resp.status_code, 200)
            decision = start_resp.json()["decision"]
            decision_id = decision["decision_id"]

            mc = decision["engineb_session"]["simulator_output"]["monte_carlo"]
            self.assertEqual(mc["llm_mode"], "local_sampling")
            self.assertGreaterEqual(mc["sample_count"], 100)

            full_pdf_resp = client.get(f"/api/decision/report?id={decision_id}")
            summary_pdf_resp = client.get(f"/api/decision/summary-report?id={decision_id}")

        self.assertEqual(full_pdf_resp.status_code, 200)
        self.assertIn("application/pdf", full_pdf_resp.headers.get("content-type", ""))
        self.assertTrue(full_pdf_resp.content.startswith(b"%PDF-1."))

        self.assertEqual(summary_pdf_resp.status_code, 200)
        self.assertIn("application/pdf", summary_pdf_resp.headers.get("content-type", ""))
        self.assertTrue(summary_pdf_resp.content.startswith(b"%PDF-1."))

    def test_demo_lagrange_archetype_and_deep_manual_simulator_flow(self) -> None:
        with (
            patch.dict(os.environ, {"CLP_API_KEY": "", "CLP_DEMO_MODE": "1"}, clear=False),
            patch("backend.shared.load_env_file", return_value={}),
            TestClient(server.app) as client,
        ):
            clp_resp = client.post(
                "/api/decision/start",
                json={"question": "经典电车难题：是否应该拉动拉杆牺牲一人救五人？", "tier": "deep"},
            )
            self.assertEqual(clp_resp.status_code, 200)
            clp_decision = clp_resp.json()["decision"]
            self.assertEqual(clp_decision["result"]["mode"], "lagrange_confirmed")
            self.assertTrue(clp_decision["detection_job"]["result"]["is_lagrange_point"])

            clp_pdf_resp = client.get(f"/api/decision/report?id={clp_decision['decision_id']}")
            self.assertEqual(clp_pdf_resp.status_code, 200)
            self.assertTrue(clp_pdf_resp.content.startswith(b"%PDF-1."))

            deep_resp = client.post(
                "/api/decision/start",
                json={"question": "我该不该订购 Claude Pro 会员？", "tier": "deep"},
            )
            deep_decision = deep_resp.json()["decision"]
            self.assertEqual(deep_decision["result"]["mode"], "engineb_complete")
            self.assertIsNone(deep_decision["engineb_session"]["simulator_output"])

            sim_resp = client.post(
                "/api/decision/simulate/start",
                json={"decision_id": deep_decision["decision_id"]},
            )
            self.assertEqual(sim_resp.status_code, 200)
            sim_decision = sim_resp.json()["decision"]
            self.assertEqual(sim_decision["result"]["mode"], "decision_complete")
            self.assertIsInstance(sim_decision["engineb_session"]["simulator_output"], dict)


if __name__ == "__main__":
    unittest.main()
