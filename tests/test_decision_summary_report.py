import tempfile
import unittest
from pathlib import Path

from research.output_formatter import generate_decision_summary_pdf_report


class DecisionSummaryReportTest(unittest.TestCase):
    def test_summary_pdf_can_be_generated_without_ai(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "summary.pdf"
            generated = generate_decision_summary_pdf_report(
                "我该不该接受这个新工作机会？",
                engineb_session={
                    "recommendation": "建议先做一轮低风险验证，再决定是否长期投入。",
                    "action_plan": "未来 7 天约谈关键人、确认现金流、列出退出条件。",
                    "reasoning": "当前主要风险不在机会本身，而在承诺过快。",
                },
                metadata={"generated_at": "2026-04-08 20:20", "model": "smoke"},
                output_path=str(output_path),
                use_ai=False,
            )

            self.assertEqual(Path(generated), output_path)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes()[:8], b"%PDF-1.3")


if __name__ == "__main__":
    unittest.main()
