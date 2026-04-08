import unittest
from unittest.mock import patch

from decision.classifier import run_flash_classifier


class FlashClassifierTest(unittest.TestCase):
    @patch("decision.classifier.analyze_question_structure")
    def test_flash_result_includes_analysis_context(self, mock_analyze) -> None:
        mock_analyze.return_value = {
            "classifications": {"dilemma": 68, "info_gap": 22, "clp": 10},
            "analysis_summary": "这更像是要在两个有代价的方向里选一个。",
            "balance_rationale": "你卡住的关键不在于没想清楚，而在于两个代价都真实存在。",
        }
        result = run_flash_classifier("我该不该换工作？")["result"]

        self.assertTrue(result["recommendation"])
        self.assertTrue(result["analysis_summary"])
        self.assertIn(result["analysis_summary"], result["recommendation"])
        if result["balance_rationale"]:
            self.assertIn(result["balance_rationale"], result["recommendation"])


if __name__ == "__main__":
    unittest.main()
