from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

import requests


class NewsFetcher:
    """抓取 AI 前沿新闻，优先使用稳定 RSS / Atom feed。"""

    def __init__(self, config: dict[str, Any], keywords: list[str], logger: logging.Logger | None = None) -> None:
        self.config = config
        self.keywords = [keyword.lower() for keyword in keywords]
        self.logger = logger or logging.getLogger(__name__)
        self.max_per_feed = int(config.get("max_per_feed", 8))

    def fetch_candidates(self, since_datetime: datetime) -> list[dict[str, Any]]:
        feeds = self.config.get("feeds", [])
        items: list[dict[str, Any]] = []

        for feed in feeds:
            url = feed.get("url")
            name = feed.get("name", "News")
            if not url:
                continue
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": "AI-Daily-Digest/1.0"},
                    timeout=20,
                )
                response.raise_for_status()
                entries = self._parse_feed(response.text)
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                self.logger.warning("News feed fetch failed for %s: %s", name, exc)
                continue

            count = 0
            for entry in entries:
                published = self._entry_datetime(entry)
                if published and published < since_datetime:
                    continue
                normalized = self._normalize_entry(name, entry, published)
                if self._matches_interest(normalized):
                    items.append(normalized)
                    count += 1
                if count >= self.max_per_feed:
                    break

        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            deduped[item["id"]] = item

        merged = list(deduped.values())
        merged.sort(key=lambda item: item.get("heuristic_score", 0), reverse=True)
        self.logger.info("News candidates prepared: %s items.", len(merged))
        return merged

    def _parse_feed(self, xml_text: str) -> list[dict[str, str]]:
        root = ET.fromstring(xml_text)
        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"

        entries = []
        for node in root.findall(".//item") + root.findall(f".//{namespace}entry"):
            entries.append(
                {
                    "title": self._find_text(node, "title", namespace),
                    "link": self._find_link(node, namespace),
                    "summary": self._find_text(node, "description", namespace) or self._find_text(node, "summary", namespace),
                    "published": self._find_text(node, "pubDate", namespace)
                    or self._find_text(node, "published", namespace)
                    or self._find_text(node, "updated", namespace),
                    "categories": self._find_categories(node, namespace),
                }
            )
        return entries

    def _find_text(self, node: ET.Element, tag: str, namespace: str) -> str:
        child = node.find(tag)
        if child is None and namespace:
            child = node.find(f"{namespace}{tag}")
        return (child.text or "").strip() if child is not None and child.text else ""

    def _find_link(self, node: ET.Element, namespace: str) -> str:
        child = node.find("link")
        if child is None and namespace:
            child = node.find(f"{namespace}link")
        if child is None:
            return ""
        if child.text:
            return child.text.strip()
        return (child.attrib.get("href") or "").strip()

    def _find_categories(self, node: ET.Element, namespace: str) -> list[str]:
        categories = []
        for tag_name in ("category",):
            nodes = node.findall(tag_name)
            if not nodes and namespace:
                nodes = node.findall(f"{namespace}{tag_name}")
            for child in nodes:
                value = (child.text or child.attrib.get("term") or "").strip()
                if value:
                    categories.append(value)
        return categories

    def _normalize_entry(self, source_name: str, entry: dict[str, Any], published: datetime | None) -> dict[str, Any]:
        title = self._clean_text(entry.get("title", ""))
        summary = self._clean_text(entry.get("summary", ""))
        link = entry.get("link", "")
        categories = [self._clean_text(value) for value in entry.get("categories", [])]
        categories = [value for value in categories if value]

        item = {
            "id": f"news::{link or title}",
            "kind": "news",
            "source": "news",
            "source_name": source_name,
            "title": title,
            "html_url": link,
            "description": summary,
            "published_at": published.isoformat() if published else "",
            "categories": categories,
        }
        item["heuristic_score"] = self._news_score(item)
        return item

    def _matches_interest(self, item: dict[str, Any]) -> bool:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("description", ""),
                item.get("source_name", ""),
                " ".join(item.get("categories", [])),
            ]
        ).lower()
        if not text:
            return False
        ai_signals = ["ai", "model", "agent", "llm", "openai", "anthropic", "xai", "robot", "reasoning", "multimodal"]
        return any(keyword in text for keyword in self.keywords) or any(signal in text for signal in ai_signals)

    def _news_score(self, item: dict[str, Any]) -> float:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("description", ""),
                item.get("source_name", ""),
                " ".join(item.get("categories", [])),
            ]
        ).lower()
        keyword_hits = sum(1 for keyword in self.keywords if keyword in text)
        source_bonus = 1.0 if item.get("source_name") in {"TechCrunch", "VentureBeat", "Hugging Face Blog"} else 0.4
        return round(keyword_hits * 2.2 + source_bonus, 3)

    def _entry_datetime(self, entry: dict[str, Any]) -> datetime | None:
        value = entry.get("published", "")
        if not value:
            return None
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _clean_text(self, text: str) -> str:
        text = html.unescape(text or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
