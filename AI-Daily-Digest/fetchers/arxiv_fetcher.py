from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any


class ArxivFetcher:
    """抓取 arXiv 指定分类下的最新论文。"""

    def __init__(self, config: dict[str, Any], keywords: list[str], logger: logging.Logger | None = None) -> None:
        self.config = config
        self.keywords = [value.lower() for value in keywords]
        self.logger = logger or logging.getLogger(__name__)

    def fetch_candidates(self, since_datetime: datetime) -> list[dict[str, Any]]:
        try:
            import arxiv
        except ImportError:
            self.logger.warning("arxiv package is not installed; skip arXiv fetch.")
            return []

        categories = self.config.get("categories", [])
        query = " OR ".join(f"cat:{category}" for category in categories)
        max_results = int(self.config.get("max_results", 30))

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        client = arxiv.Client(page_size=min(max_results, 100), delay_seconds=3, num_retries=2)

        items: list[dict[str, Any]] = []
        try:
            for result in client.results(search):
                published = result.published
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if published < since_datetime:
                    continue
                normalized = self._normalize_result(result)
                if self._matches_interest(normalized):
                    items.append(normalized)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            self.logger.warning("arXiv fetch failed: %s", exc)

        items.sort(key=lambda item: item.get("heuristic_score", 0), reverse=True)
        self.logger.info("arXiv candidates prepared: %s items.", len(items))
        return items

    def _normalize_result(self, result: Any) -> dict[str, Any]:
        categories = list(getattr(result, "categories", []) or [])
        authors = [author.name for author in getattr(result, "authors", [])]
        summary = " ".join((getattr(result, "summary", "") or "").split())
        item = {
            "id": f"arxiv::{getattr(result, 'entry_id', '')}",
            "kind": "paper",
            "source": "arxiv",
            "source_tags": ["latest"],
            "title": getattr(result, "title", "").strip(),
            "html_url": getattr(result, "entry_id", ""),
            "pdf_url": getattr(result, "pdf_url", ""),
            "description": summary,
            "authors": authors,
            "categories": categories,
            "published_at": getattr(result, "published").replace(tzinfo=timezone.utc).isoformat(),
            "updated_at": getattr(result, "updated").replace(tzinfo=timezone.utc).isoformat(),
            "primary_category": getattr(result, "primary_category", ""),
        }
        item["heuristic_score"] = self._paper_score(item)
        return item

    def _paper_score(self, item: dict[str, Any]) -> float:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("description", ""),
                " ".join(item.get("categories", [])),
            ]
        ).lower()
        keyword_hits = sum(1 for keyword in self.keywords if keyword in text)
        category_bonus = 1.5 if item.get("primary_category") in {"cs.AI", "cs.LG", "cs.CL", "cs.CV"} else 0.0
        abstract_length_bonus = min(len(item.get("description", "")), 1600) / 800
        return round(keyword_hits * 2.4 + category_bonus + abstract_length_bonus, 3)

    def _matches_interest(self, item: dict[str, Any]) -> bool:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("description", ""),
                " ".join(item.get("categories", [])),
            ]
        ).lower()
        if any(keyword in text for keyword in self.keywords):
            return True
        return item.get("primary_category") in {"cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "stat.ML"}
