import unittest
from unittest.mock import patch

from research.api import _extract_json, _use_responses_api, call_agent_json


class ApiJsonRescueTest(unittest.TestCase):
    def test_extract_json_accepts_python_style_dict(self) -> None:
        payload = _extract_json(
            "{'missing_info': [{'title': '能力边界', 'content': '先确认是否真有高频场景'}]}"
        )

        self.assertEqual(payload["missing_info"][0]["title"], "能力边界")
        self.assertEqual(payload["missing_info"][0]["content"], "先确认是否真有高频场景")

    @patch("research.api._call_agent_with_model_list")
    def test_call_agent_json_recovers_python_style_text_on_fast_schema_path(self, mock_call) -> None:
        mock_call.return_value = "{'missing_info': []}"

        result = call_agent_json(
            "只输出 JSON",
            "返回缺失信息",
            model="deepseek-v3",
            max_tokens=128,
        )

        self.assertEqual(result, {"missing_info": []})
        self.assertEqual(mock_call.call_args.kwargs.get("response_format"), {"type": "json_object"})

    @patch.dict("os.environ", {"CLP_BASE_URL": "https://api.openai.com/v1"}, clear=False)
    @patch("research.api._call_agent_with_model_list")
    def test_call_agent_json_bypasses_fast_schema_for_official_gpt5_responses_path(self, mock_call) -> None:
        mock_call.return_value = "{'missing_info': []}"

        result = call_agent_json(
            "只输出 JSON",
            "返回缺失信息",
            model="gpt-5.4",
            max_tokens=128,
        )

        self.assertEqual(result, {"missing_info": []})
        self.assertIsNone(mock_call.call_args.kwargs.get("response_format"))

    @patch.dict("os.environ", {"CLP_BASE_URL": "https://kuaipao.ai/v1"}, clear=False)
    def test_gpt5_on_third_party_gateway_prefers_chat_completions(self) -> None:
        self.assertFalse(_use_responses_api("gpt-5.4"))


if __name__ == "__main__":
    unittest.main()
