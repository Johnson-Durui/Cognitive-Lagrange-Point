from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any


class GitHubFetcher:
    """抓取 GitHub 新项目与 Trending，并统一成同一种结构。"""

    def __init__(self, config: dict[str, Any], logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.token_env = config.get("token_env", "GITHUB_TOKEN")
        self.request_keywords = [value.lower() for value in config.get("keywords", [])]
        self.topics = config.get("topics", [])
        self.min_stars = int(config.get("min_stars", 5))
        self.max_new_per_topic = int(config.get("max_new_per_topic", 8))
        self.max_trending_items = int(config.get("max_trending_items", 30))

    def fetch_candidates(self, since_date: date) -> list[dict[str, Any]]:
        """合并新项目和 Trending，并按启发式分数排序。"""
        new_projects = self._fetch_new_projects(since_date)
        trending_projects = self._fetch_trending_projects()
        merged = self._dedupe_and_merge(new_projects + trending_projects)
        merged.sort(key=lambda item: item.get("heuristic_score", 0), reverse=True)
        self.logger.info(
            "GitHub candidates prepared: %s merged (%s new, %s trending).",
            len(merged),
            len(new_projects),
            len(trending_projects),
        )
        return merged

    def _fetch_new_projects(self, since_date: date) -> list[dict[str, Any]]:
        try:
            from github import Github
        except ImportError:
            self.logger.warning("PyGithub is not installed; skip GitHub new-project fetch.")
            return []

        token = os.getenv(self.token_env, "").strip() or None
        client = Github(login_or_token=token) if token else Github()
        projects: list[dict[str, Any]] = []

        for topic in self.topics:
            query = (
                f"topic:{topic} created:>{since_date.isoformat()} "
                f"stars:>={self.min_stars} archived:false fork:false is:public"
            )
            self.logger.debug("GitHub search query: %s", query)
            try:
                results = client.search_repositories(query=query, sort="stars", order="desc")
                for index, repo in enumerate(results):
                    if index >= self.max_new_per_topic:
                        break
                    normalized = self._normalize_repo(repo, source_tag="new")
                    if self._matches_interest(normalized):
                        projects.append(normalized)
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                self.logger.warning("GitHub search failed for topic=%s: %s", topic, exc)

        return projects

    def _fetch_trending_projects(self) -> list[dict[str, Any]]:
        try:
            import gtrending
        except ImportError:
            self.logger.warning("gtrending is not installed; skip GitHub trending fetch.")
            return []

        fetch_methods = [
            getattr(gtrending, "get_repos", None),
            getattr(gtrending, "fetch_repos", None),
            getattr(gtrending, "trending_repositories", None),
        ]
        projects: list[dict[str, Any]] = []

        for method in fetch_methods:
            if method is None:
                continue
            try:
                results = method(language=None, since="daily")
                for index, repo in enumerate(results or []):
                    if index >= self.max_trending_items:
                        break
                    normalized = self._normalize_trending(repo)
                    if self._matches_interest(normalized):
                        projects.append(normalized)
                if projects:
                    return projects
            except TypeError:
                try:
                    results = method(language=None, timeframe="daily")
                    for index, repo in enumerate(results or []):
                        if index >= self.max_trending_items:
                            break
                        normalized = self._normalize_trending(repo)
                        if self._matches_interest(normalized):
                            projects.append(normalized)
                    if projects:
                        return projects
                except Exception as exc:  # pragma: no cover - depends on third-party API
                    self.logger.warning("Trending fetch failed: %s", exc)
            except Exception as exc:  # pragma: no cover - depends on third-party API
                self.logger.warning("Trending fetch failed: %s", exc)

        return projects

    def _dedupe_and_merge(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in items:
            key = item["id"]
            existing = merged.get(key)
            if not existing:
                merged[key] = item
                continue
            merged[key] = self._merge_duplicate(existing, item)
        return list(merged.values())

    def _merge_duplicate(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        merged = dict(left)
        merged["source_tags"] = sorted(set(left.get("source_tags", []) + right.get("source_tags", [])))
        merged["stars"] = max(left.get("stars", 0), right.get("stars", 0))
        merged["stars_today"] = max(left.get("stars_today", 0), right.get("stars_today", 0))
        merged["topics"] = sorted(set(left.get("topics", []) + right.get("topics", [])))
        merged["heuristic_score"] = max(left.get("heuristic_score", 0), right.get("heuristic_score", 0))
        return merged

    def _normalize_repo(self, repo: Any, source_tag: str) -> dict[str, Any]:
        topics = self._safe_repo_topics(repo)
        description = (getattr(repo, "description", "") or "").strip()
        item = {
            "id": f"github::{getattr(repo, 'full_name', getattr(repo, 'name', 'unknown'))}",
            "kind": "repo",
            "source": "github",
            "source_tags": [source_tag],
            "name": getattr(repo, "name", ""),
            "title": getattr(repo, "full_name", getattr(repo, "name", "")),
            "full_name": getattr(repo, "full_name", getattr(repo, "name", "")),
            "html_url": getattr(repo, "html_url", ""),
            "description": description,
            "stars": int(getattr(repo, "stargazers_count", 0) or 0),
            "stars_today": 0,
            "language": getattr(repo, "language", "") or "Unknown",
            "topics": topics,
            "created_at": self._to_iso(getattr(repo, "created_at", None)),
            "updated_at": self._to_iso(getattr(repo, "updated_at", None)),
        }
        item["heuristic_score"] = self._repo_score(item)
        return item

    def _normalize_trending(self, repo: Any) -> dict[str, Any]:
        raw = repo if isinstance(repo, dict) else self._object_to_dict(repo)
        full_name = raw.get("fullname") or raw.get("full_name") or raw.get("repository") or raw.get("name") or ""
        stars_today = raw.get("stars_today") or raw.get("current_period_stars") or raw.get("today_stars") or 0
        topics = raw.get("topics") or []
        description = (raw.get("description") or "").strip()
        item = {
            "id": f"github::{full_name or raw.get('url', 'unknown')}",
            "kind": "repo",
            "source": "github",
            "source_tags": ["trending"],
            "name": full_name.split("/")[-1] if "/" in full_name else full_name,
            "title": full_name,
            "full_name": full_name,
            "html_url": raw.get("url") or raw.get("repo") or "",
            "description": description,
            "stars": self._to_int(raw.get("stars")),
            "stars_today": self._to_int(stars_today),
            "language": raw.get("language") or "Unknown",
            "topics": topics if isinstance(topics, list) else [],
            "created_at": "",
            "updated_at": "",
        }
        item["heuristic_score"] = self._repo_score(item)
        return item

    def _repo_score(self, item: dict[str, Any]) -> float:
        text = " ".join(
            [
                item.get("name", ""),
                item.get("full_name", ""),
                item.get("description", ""),
                " ".join(item.get("topics", [])),
                item.get("language", ""),
            ]
        ).lower()
        keyword_hits = sum(1 for keyword in self.request_keywords if keyword in text)
        stars_component = min(item.get("stars", 0), 5000) / 500
        today_component = min(item.get("stars_today", 0), 300) / 60
        fresh_component = 1.2 if "new" in item.get("source_tags", []) else 0.0
        return round(keyword_hits * 2.6 + stars_component + today_component + fresh_component, 3)

    def _matches_interest(self, item: dict[str, Any]) -> bool:
        text = " ".join(
            [
                item.get("name", ""),
                item.get("full_name", ""),
                item.get("description", ""),
                " ".join(item.get("topics", [])),
            ]
        ).lower()
        return any(keyword in text for keyword in self.request_keywords)

    def _safe_repo_topics(self, repo: Any) -> list[str]:
        topics = getattr(repo, "topics", None)
        if isinstance(topics, list):
            return topics
        try:
            getter = getattr(repo, "get_topics", None)
            return getter() if callable(getter) else []
        except Exception:  # pragma: no cover - depends on API/client behavior
            return []

    def _object_to_dict(self, value: Any) -> dict[str, Any]:
        return {
            name: getattr(value, name)
            for name in dir(value)
            if not name.startswith("_") and not callable(getattr(value, name))
        }

    def _to_iso(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    def _to_int(self, value: Any) -> int:
        try:
            if isinstance(value, str):
                return int(value.replace(",", "").strip())
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

