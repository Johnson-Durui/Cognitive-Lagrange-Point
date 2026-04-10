from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main as digest_main  # noqa: E402


class PipelineSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        for directory in ("fetchers", "templates", "static", "data/digests"):
            (self.project_root / directory).mkdir(parents=True, exist_ok=True)

        for filename in ("config.yaml", "main.py", "summarizer.py", "notifier.py"):
            source = PROJECT_ROOT / filename
            if source.exists():
                (self.project_root / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        (self.project_root / "history.json").write_text(
            json.dumps({"generated_at": None, "items": {}, "digests": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for filename in ("__init__.py", "github_fetcher.py", "arxiv_fetcher.py", "news_fetcher.py"):
            source = PROJECT_ROOT / "fetchers" / filename
            (self.project_root / "fetchers" / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        for filename in ("app.js", "app.css"):
            source = PROJECT_ROOT / "static" / filename
            (self.project_root / "static" / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        for filename in ("digest_template.jinja", "site_index.jinja", "site_detail.jinja", "site_report.jinja"):
            source = PROJECT_ROOT / "templates" / filename
            (self.project_root / "templates" / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_generates_digest_outputs(self) -> None:
        config = digest_main.load_config(self.project_root / "config.yaml")
        logger = digest_main.build_logger("INFO")

        repo_item = {
            "id": "github::demo/repo",
            "kind": "repo",
            "source": "github",
            "title": "demo/repo",
            "full_name": "demo/repo",
            "html_url": "https://github.com/demo/repo",
            "description": "An AI coding agent toolkit",
            "topics": ["ai", "agent"],
            "language": "Python",
            "stars": 123,
            "stars_today": 11,
            "heuristic_score": 8.2,
            "summary": "这是一个值得关注的 AI 开源工具。",
            "core_innovation": "把代理工作流做成了可以复用的工具集。",
            "highlights": ["支持代理编排", "适合快速试验"],
            "practicality": "适合跟踪。",
            "relevance_score": 9,
            "tags": ["agent", "python"],
            "summary_markdown": "mock",
        }
        paper_item = {
            "id": "arxiv::http://arxiv.org/abs/1234.5678",
            "kind": "paper",
            "source": "arxiv",
            "title": "A Useful AI Paper",
            "html_url": "https://arxiv.org/abs/1234.5678",
            "pdf_url": "https://arxiv.org/pdf/1234.5678.pdf",
            "description": "A paper about reasoning models",
            "authors": ["Ada Lovelace"],
            "categories": ["cs.AI"],
            "primary_category": "cs.AI",
            "published_at": "2026-04-09T00:00:00+00:00",
            "updated_at": "2026-04-09T00:00:00+00:00",
            "heuristic_score": 7.4,
            "summary": "这篇论文总结了新型推理模型的做法。",
            "core_innovation": "提出了更稳定的推理路径。",
            "highlights": ["聚焦推理", "适合快速阅读"],
            "practicality": "适合进入跟踪清单。",
            "relevance_score": 8,
            "tags": ["reasoning"],
            "summary_markdown": "mock",
        }
        news_item = {
            "id": "news::https://example.com/news",
            "kind": "news",
            "source": "news",
            "source_name": "TechCrunch",
            "title": "AI company ships new agent platform",
            "html_url": "https://example.com/news",
            "description": "A new AI agent platform was announced.",
            "published_at": "2026-04-09T00:00:00+00:00",
            "heuristic_score": 7.2,
            "summary": "这条新闻概述了一家 AI 公司发布新的智能体平台。",
            "brief": "新的智能体平台发布。",
            "problem": "新闻体现了智能体产品化速度正在加快。",
            "why_it_matters": "适合用来判断近期 AI 产品与竞争节奏。",
            "target_reader": "适合关注 AI 行业动态的人。",
            "core_innovation": "更偏行业动态，不是技术论文。",
            "highlights": ["来源 TechCrunch", "偏产品发布"],
            "practicality": "适合快速扫读。",
            "relevance_score": 8,
            "tags": ["agent"],
            "themes": ["智能体"],
            "selection_reason": "它能反映 AI 行业产品方向。",
            "summary_markdown": "mock",
        }

        with patch.object(digest_main.GitHubFetcher, "fetch_candidates", return_value=[repo_item]), patch.object(
            digest_main.ArxivFetcher, "fetch_candidates", return_value=[paper_item]
        ), patch.object(
            digest_main.NewsFetcher, "fetch_candidates", return_value=[news_item]
        ), patch.object(
            digest_main.Summarizer, "summarize_repositories", return_value=[repo_item]
        ), patch.object(
            digest_main.Summarizer, "summarize_papers", return_value=[paper_item]
        ), patch.object(
            digest_main.Summarizer, "summarize_news", return_value=[news_item]
        ), patch.object(
            digest_main.Notifier, "send_markdown", return_value={"ok": True}
        ):
            app = digest_main.DailyDigestApp(self.project_root, config, logger)
            result = app.run()

        self.assertTrue(result["notify_result"]["ok"])
        latest_json = self.project_root / "data" / "latest.json"
        archive_index = self.project_root / "site" / "data" / "search-index.json"
        archive_page = self.project_root / "site" / "archive" / "index.html"
        weekly_report = self.project_root / "site" / "reports" / "weekly.html"

        self.assertTrue(latest_json.exists())
        self.assertTrue(archive_index.exists())
        self.assertTrue(archive_page.exists())
        self.assertTrue(weekly_report.exists())

        payload = json.loads(latest_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["stats"]["total_count"], 3)
        self.assertIn("sections", payload)
        self.assertIn("reports", payload)
        self.assertIn("notification_messages", payload)


if __name__ == "__main__":
    unittest.main()
