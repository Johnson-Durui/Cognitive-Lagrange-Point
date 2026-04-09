from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from fetchers.arxiv_fetcher import ArxivFetcher
from fetchers.github_fetcher import GitHubFetcher
from notifier import Notifier
from summarizer import Summarizer


def load_env_files(project_root: Path) -> None:
    """加载本地 .env 文件，优先级低于系统已有环境变量。"""
    for name in (".env.local", ".env"):
        env_path = project_root / name
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_logger(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("ai_daily_digest")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


class DailyDigestApp:
    """主流程：抓取 -> 去重 -> 摘要 -> 渲染 -> 通知 -> 生成站点。"""

    def __init__(self, project_root: Path, config: dict[str, Any], logger: logging.Logger) -> None:
        self.project_root = project_root
        self.config = config
        self.logger = logger
        self.timezone = ZoneInfo(config["project"].get("timezone", "Asia/Shanghai"))
        self.storage_config = config["storage"]
        self.website_config = config["website"]
        self.filtering_config = config["filtering"]
        self.ranking_config = config.get("ranking", {})
        self.reports_config = config.get("reports", {})
        self.runtime_config = config["runtime"]

        self.history_path = self.project_root / self.storage_config.get("history_path", "history.json")
        self.data_dir = self.project_root / self.storage_config.get("data_dir", "data")
        self.digests_dir = self.data_dir / "digests"
        self.site_dir = self.project_root / "site"

        all_keywords = self._keywords()
        self.github_fetcher = GitHubFetcher(
            {
                **config["sources"]["github"],
                "token_env": config["github"].get("token_env", "GITHUB_TOKEN"),
            },
            logger=logger,
        )
        self.arxiv_fetcher = ArxivFetcher(config["sources"]["arxiv"], all_keywords, logger=logger)
        self.summarizer = Summarizer(config["llm"], all_keywords, logger=logger)
        self.notifier = Notifier(config["notification"], logger=logger)
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.project_root / "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def run(self, *, skip_notify: bool = False) -> dict[str, Any]:
        self._ensure_runtime_dirs()
        history = self._load_history()
        now_bjt = datetime.now(self.timezone)
        generated_at = now_bjt.isoformat()
        today = now_bjt.date().isoformat()

        github_since = now_bjt.date() - timedelta(days=int(self.config["sources"]["github"].get("created_lookback_days", 1)))
        arxiv_since = now_bjt - timedelta(days=int(self.config["sources"]["arxiv"].get("lookback_days", 2)))

        self.logger.info("Starting digest run for %s", today)
        github_candidates = self.github_fetcher.fetch_candidates(github_since)
        arxiv_candidates = self.arxiv_fetcher.fetch_candidates(arxiv_since.astimezone(timezone.utc))

        repo_candidates = self._filter_candidates(github_candidates, history)
        paper_candidates = self._filter_candidates(arxiv_candidates, history)

        repo_items = self.summarizer.summarize_repositories(
            repo_candidates,
            top_k=int(self.config["sources"]["github"].get("top_k", 8)),
            max_candidates=int(self.config["sources"]["github"].get("max_candidates", 18)),
        )
        paper_items = self.summarizer.summarize_papers(
            paper_candidates,
            top_k=int(self.config["sources"]["arxiv"].get("top_k", 6)),
            max_candidates=int(self.config["sources"]["arxiv"].get("max_candidates", 16)),
        )
        repo_items = self._decorate_ranked_items(repo_items, source="github")
        paper_items = self._decorate_ranked_items(paper_items, source="arxiv")
        repo_items = self._same_day_items(history, digest_date=today, source="github", fallback_items=repo_items)
        paper_items = self._same_day_items(history, digest_date=today, source="arxiv", fallback_items=paper_items)

        digest = self._build_digest(today, generated_at, repo_items, paper_items)
        self._update_history(history, digest, notified_at=None)
        digest["reports"] = self._build_reports(history, digest)
        digest["markdown"] = self._render_markdown(digest)
        digest["notification_markdown"] = self._render_notification_markdown(digest)
        self._persist_digest_files(history, digest)
        self._generate_site(history, digest)

        notify_result: dict[str, Any] = {"ok": False, "skipped": True}
        if not skip_notify:
            try:
                notify_result = self.notifier.send_markdown(digest["title"], digest["notification_markdown"])
                if notify_result.get("ok"):
                    notified_at = datetime.now(timezone.utc).isoformat()
                    self._update_history(history, digest, notified_at=notified_at)
                    digest["reports"] = self._build_reports(history, digest)
                    self._persist_digest_files(history, digest)
                    self._generate_site(history, digest)
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                self.logger.error("Notification failed: %s", exc)
                notify_result = {"ok": False, "error": str(exc), "provider": self.config["notification"].get("provider")}

        self.logger.info(
            "Digest finished: %s repos, %s papers, notify=%s",
            len(repo_items),
            len(paper_items),
            notify_result.get("ok", False),
        )

        return {
            "digest": digest,
            "notify_result": notify_result,
            "site_dir": str(self.site_dir),
            "history_path": str(self.history_path),
        }

    def _ensure_runtime_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.digests_dir.mkdir(parents=True, exist_ok=True)

    def _keywords(self) -> list[str]:
        github_keywords = self.config["sources"]["github"].get("keywords", [])
        user_keywords = self.filtering_config.get("user_keywords", [])
        deduped = list(dict.fromkeys([*github_keywords, *user_keywords]))
        return [keyword.strip() for keyword in deduped if keyword.strip()]

    def _load_history(self) -> dict[str, Any]:
        if not self.history_path.exists():
            return {"generated_at": None, "items": {}, "digests": []}
        with self.history_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save_history(self, history: dict[str, Any]) -> None:
        with self.history_path.open("w", encoding="utf-8") as handle:
            json.dump(history, handle, ensure_ascii=False, indent=2)

    def _filter_candidates(self, items: list[dict[str, Any]], history: dict[str, Any]) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        dedupe_days = int(self.storage_config.get("dedupe_days", 7))
        exclude_keywords = [keyword.lower() for keyword in self.filtering_config.get("exclude_keywords", [])]

        for item in items:
            haystack = " ".join(
                [
                    item.get("title", ""),
                    item.get("description", ""),
                    " ".join(item.get("topics", [])),
                    " ".join(item.get("categories", [])),
                ]
            ).lower()
            if any(keyword in haystack for keyword in exclude_keywords):
                continue

            previous = history.get("items", {}).get(item["id"])
            if not previous:
                filtered.append(item)
                continue

            last_notified_at = previous.get("last_notified_at")
            if not last_notified_at:
                filtered.append(item)
                continue

            last_notified = datetime.fromisoformat(last_notified_at)
            cutoff = datetime.now(timezone.utc) - timedelta(days=dedupe_days)
            if last_notified <= cutoff:
                filtered.append(item)

        filtered.sort(key=lambda item: item.get("heuristic_score", 0), reverse=True)
        return filtered

    def _build_digest(
        self,
        digest_date: str,
        generated_at: str,
        repo_items: list[dict[str, Any]],
        paper_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_items = len(repo_items) + len(paper_items)
        empty_allowed = bool(self.runtime_config.get("keep_empty_digest", True))
        if total_items == 0 and not empty_allowed:
            raise RuntimeError("No items found and empty digests are disabled.")

        title = f"{self.config['notification'].get('title_prefix', 'AI Daily Digest')} · {digest_date}"
        digest = {
            "title": title,
            "date": digest_date,
            "generated_at": generated_at,
            "repos": repo_items,
            "papers": paper_items,
            "items": [*repo_items, *paper_items],
            "stats": {
                "repo_count": len(repo_items),
                "paper_count": len(paper_items),
                "total_count": total_items,
            },
            "sections": self._build_sections(repo_items, paper_items),
            "theme_clusters": self._theme_clusters([*repo_items, *paper_items]),
            "empty_message": "今天没有筛出足够新的高相关项目，系统已保留历史站点内容。" if total_items == 0 else "",
        }
        return digest

    def _decorate_ranked_items(self, items: list[dict[str, Any]], *, source: str) -> list[dict[str, Any]]:
        decorated = [self._apply_personalization(item, source=source) for item in items]
        decorated.sort(
            key=lambda item: (
                item.get("personalized_score", 0.0),
                item.get("relevance_score", 0),
                item.get("heuristic_score", 0),
            ),
            reverse=True,
        )
        return decorated

    def _apply_personalization(self, item: dict[str, Any], *, source: str) -> dict[str, Any]:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("full_name", ""),
                item.get("summary", ""),
                item.get("brief", ""),
                item.get("problem", ""),
                item.get("why_it_matters", ""),
                item.get("description", ""),
                " ".join(item.get("tags", [])),
                " ".join(item.get("themes", [])),
                " ".join(item.get("topics", [])),
                " ".join(item.get("categories", [])),
            ]
        ).lower()
        focus_hits: list[dict[str, Any]] = []
        score = float(item.get("relevance_score", 0)) * 10.0

        for keyword, weight in self.ranking_config.get("focus_areas", {}).items():
            if keyword.lower() in text:
                focus_hits.append({"keyword": keyword, "weight": weight})
                score += float(weight) * 10.0

        if source == "github":
            score += min(float(item.get("stars", 0)), 50000) / 2500
            score += min(float(item.get("stars_today", 0)), 300) / 18
        else:
            category = item.get("primary_category") or ""
            if category in {"cs.AI", "cs.LG", "cs.CL", "cs.CV"}:
                score += 8

        primary_match = focus_hits[0]["keyword"] if focus_hits else ""
        selection_reason = item.get("selection_reason") or self._default_selection_reason(item, source=source, primary_match=primary_match)

        enriched = dict(item)
        enriched["focus_hits"] = focus_hits
        enriched["primary_match"] = primary_match
        enriched["personalized_score"] = round(score, 2)
        enriched["selection_reason"] = selection_reason
        if not enriched.get("themes"):
            enriched["themes"] = self._infer_themes(enriched)
        return enriched

    def _default_selection_reason(self, item: dict[str, Any], *, source: str, primary_match: str) -> str:
        if source == "github":
            if primary_match:
                return f"它和你关注的 {primary_match} 方向高度相关，适合优先看是否能直接复用。"
            return "它兼具热度和主题相关性，适合进入今天的 GitHub 观察清单。"
        if primary_match:
            return f"它和你关注的 {primary_match} 方向重合度高，适合放进今天的论文精读候选。"
        return "它代表了一个值得继续追踪的研究方向，适合先把核心方法抓住。"

    def _infer_themes(self, item: dict[str, Any]) -> list[str]:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("summary", ""),
                item.get("description", ""),
                " ".join(item.get("tags", [])),
                " ".join(item.get("topics", [])),
                " ".join(item.get("categories", [])),
            ]
        ).lower()
        theme_rules = [
            ("智能体", ["agent", "agentic"]),
            ("编码", ["code", "coding", "repo", "developer"]),
            ("RAG", ["rag", "retrieval", "knowledge graph"]),
            ("推理", ["reasoning", "inference"]),
            ("多模态", ["multimodal", "vision-language", "video"]),
            ("机器人", ["robot", "android", "motion"]),
            ("基础设施", ["power", "data center", "infrastructure"]),
            ("评测", ["benchmark", "evaluation"]),
        ]
        themes = [label for label, keys in theme_rules if any(key in text for key in keys)]
        return themes[:3] or ["AI 前沿"]

    def _build_sections(self, repo_items: list[dict[str, Any]], paper_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        combined = [*repo_items, *paper_items]
        combined.sort(
            key=lambda item: (
                item.get("personalized_score", 0),
                item.get("relevance_score", 0),
            ),
            reverse=True,
        )
        must_watch_count = int(self.ranking_config.get("must_watch_count", 3))
        worth_scan_count = int(self.ranking_config.get("worth_scan_count", 5))
        paper_spotlight_count = int(self.ranking_config.get("paper_spotlight_count", 3))
        return {
            "must_watch": combined[:must_watch_count],
            "worth_scan": combined[must_watch_count : must_watch_count + worth_scan_count],
            "paper_spotlight": paper_items[:paper_spotlight_count],
            "repo_spotlight": repo_items[:paper_spotlight_count],
        }

    def _theme_clusters(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            for theme in item.get("themes", [])[:2]:
                buckets[theme].append(item)

        clusters = []
        for theme, themed_items in buckets.items():
            themed_items.sort(key=lambda item: item.get("personalized_score", 0), reverse=True)
            clusters.append(
                {
                    "theme": theme,
                    "count": len(themed_items),
                    "leaders": [item.get("title") or item.get("full_name") for item in themed_items[:3]],
                }
            )

        clusters.sort(key=lambda cluster: cluster["count"], reverse=True)
        return clusters[: int(self.ranking_config.get("theme_count", 5))]

    def _same_day_items(
        self,
        history: dict[str, Any],
        *,
        digest_date: str,
        source: str,
        fallback_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """支持同一天重发：已有当日条目时优先复用，避免被 dedupe 清空。"""
        indexed = {item["id"]: item for item in fallback_items}
        for item in history.get("items", {}).values():
            if item.get("source") != source:
                continue
            effective_ts = item.get("last_notified_at") or item.get("last_curated_at")
            if not effective_ts:
                continue
            try:
                dt = datetime.fromisoformat(effective_ts).astimezone(self.timezone)
            except ValueError:
                continue
            if dt.date().isoformat() == digest_date:
                indexed.setdefault(item["id"], item)
        merged = list(indexed.values())
        merged.sort(
            key=lambda item: (
                item.get("last_notified_at") or item.get("last_curated_at") or "",
                item.get("relevance_score", 0),
                item.get("heuristic_score", 0),
            ),
            reverse=True,
        )
        merged = [self._apply_personalization(item, source=source) for item in merged]
        merged.sort(
            key=lambda item: (
                item.get("personalized_score", 0),
                item.get("relevance_score", 0),
                item.get("heuristic_score", 0),
            ),
            reverse=True,
        )
        limit_key = "top_k" if source == "github" else "top_k"
        top_k = int(self.config["sources"][source].get(limit_key, len(merged)))
        return merged[:top_k]

    def _render_markdown(self, digest: dict[str, Any]) -> str:
        template = self.jinja_env.get_template("digest_template.jinja")
        return template.render(digest=digest)

    def _render_notification_markdown(self, digest: dict[str, Any]) -> str:
        """企业微信适合读详细扫描版：不放 URL，但尽量给到可快速判断的信息。"""
        notification_config = self.config.get("notification", {})
        target_chars = int(notification_config.get("target_chars", 3000))
        hard_max_chars = int(notification_config.get("hard_max_chars", 3900))
        wecom_max_bytes = int(notification_config.get("wecom_max_bytes", 3900))
        title = digest["title"]
        lines = [
            f"## {digest['date']} AI Daily Digest",
            f"GitHub {digest['stats']['repo_count']} 个 | arXiv {digest['stats']['paper_count']} 篇",
            "",
        ]

        if digest["empty_message"]:
            lines.append(digest["empty_message"])
            return "\n".join(lines)

        if digest["repos"]:
            lines.append("### GitHub 精选")
            for index, item in enumerate(digest["repos"], start=1):
                lines.extend(self._notification_item_lines(index, item, kind="repo", detail_level="detailed"))
            lines.append("")

        if digest["papers"]:
            lines.append("### arXiv 精选")
            for index, item in enumerate(digest["papers"], start=1):
                lines.extend(self._notification_item_lines(index, item, kind="paper", detail_level="detailed"))
            lines.append("")

        site_url = self.website_config.get("base_url", "").strip()
        if site_url:
            lines.append(f"站点：{site_url}")

        rendered = "\n".join(lines).strip()
        if len(rendered) < target_chars:
            rendered = self._expand_notification_markdown(digest, base_lines=lines, target_chars=target_chars, hard_max_chars=hard_max_chars)
        if len(rendered) > hard_max_chars or not self._fits_wecom_markdown(title, rendered, wecom_max_bytes):
            lines = [
                f"## {digest['date']} AI Daily Digest",
                f"GitHub {digest['stats']['repo_count']} 个 | arXiv {digest['stats']['paper_count']} 篇",
                "",
            ]
            if digest["repos"]:
                lines.append("### GitHub 精选")
                for index, item in enumerate(digest["repos"], start=1):
                    lines.extend(self._notification_item_lines(index, item, kind="repo", detail_level="medium"))
                lines.append("")
            if digest["papers"]:
                lines.append("### arXiv 精选")
                for index, item in enumerate(digest["papers"], start=1):
                    lines.extend(self._notification_item_lines(index, item, kind="paper", detail_level="medium"))
            rendered = "\n".join(lines).strip()
        if len(rendered) > hard_max_chars or not self._fits_wecom_markdown(title, rendered, wecom_max_bytes):
            lines = [
                f"## {digest['date']} AI Daily Digest",
                f"GitHub {digest['stats']['repo_count']} 个 | arXiv {digest['stats']['paper_count']} 篇",
                "",
            ]
            if digest["repos"]:
                lines.append("### GitHub 精选")
                for index, item in enumerate(digest["repos"], start=1):
                    lines.extend(self._notification_item_lines(index, item, kind="repo", detail_level="compact"))
                lines.append("")
            if digest["papers"]:
                lines.append("### arXiv 精选")
                for index, item in enumerate(digest["papers"], start=1):
                    lines.extend(self._notification_item_lines(index, item, kind="paper", detail_level="compact"))
            rendered = "\n".join(lines).strip()
        return rendered

    def _expand_notification_markdown(
        self,
        digest: dict[str, Any],
        *,
        base_lines: list[str],
        target_chars: int,
        hard_max_chars: int,
    ) -> str:
        """尽量把微信文案扩展到接近目标长度，但不碰企业微信上限。"""
        lines = list(base_lines)
        rendered = "\n".join(lines).strip()
        if len(rendered) >= target_chars:
            return rendered

        if digest["repos"] or digest["papers"]:
            lines.append("### 今日判断建议")
            if digest["repos"]:
                lines.append("- GitHub 侧更偏工具与工程落地，适合先看能否直接复用到你的工作流。")
            if digest["papers"]:
                lines.append("- 论文侧更偏研究趋势和方法进展，适合挑与你当前关注方向最接近的 2-3 篇深入。")
            lines.append("")
            rendered = "\n".join(lines).strip()

        if len(rendered) > hard_max_chars:
            return rendered[:hard_max_chars]
        return rendered

    def _fits_wecom_markdown(self, title: str, content: str, max_bytes: int) -> bool:
        payload_text = f"# {title}\n\n{content}"
        return len(payload_text.encode("utf-8")) <= max_bytes

    def _notification_item_lines(self, index: int, item: dict[str, Any], *, kind: str, detail_level: str) -> list[str]:
        title = self._notification_title(item, kind=kind)
        score = item.get("relevance_score", 0)
        if detail_level == "compact":
            return [f"{index}. {title} ({score}/10)：{self._notification_brief(item, kind=kind, limit=64)}"]

        if detail_level == "medium":
            return [
                f"{index}. {title} ({score}/10)",
                f"   在做：{self._notification_brief(item, kind=kind, limit=84)}",
                f"   值得看：{self._notification_followup(item, kind=kind, limit=88)}",
            ]

        return [
            f"{index}. {title} ({score}/10)",
            f"   在做：{self._notification_brief(item, kind=kind, limit=92)}",
            f"   为什么看：{self._notification_followup(item, kind=kind, limit=92)}",
            f"   怎么看：{self._notification_takeaway(item, kind=kind, limit=88)}",
        ]

    def _notification_title(self, item: dict[str, Any], *, kind: str) -> str:
        if kind == "repo":
            return item.get("name") or item.get("full_name") or item.get("title", "项目")
        title = item.get("title", "论文")
        return self._trim_text(title, 34)

    def _notification_brief(self, item: dict[str, Any], *, kind: str, limit: int) -> str:
        heuristic = self._heuristic_notification_detail(item, kind=kind)
        if heuristic:
            text = heuristic["brief"]
            if not text.endswith(("。", "！", "？")):
                text += "。"
            return self._trim_text(text, limit)

        candidates = [
            item.get("brief", ""),
            item.get("core_innovation", ""),
            item.get("summary", ""),
            item.get("description", ""),
        ]
        text = ""
        for candidate in candidates:
            cleaned = self._clean_notification_candidate(item, str(candidate))
            if cleaned:
                text = cleaned
                break

        if not text:
            text = "值得加入今天的重点跟踪清单"

        if kind == "repo" and not text.endswith(("。", "！", "？")):
            text += "。"
        if kind == "paper" and not text.endswith(("。", "！", "？")):
            text += "。"
        return self._trim_text(text, limit)

    def _notification_followup(self, item: dict[str, Any], *, kind: str, limit: int) -> str:
        heuristic = self._heuristic_notification_detail(item, kind=kind)
        if heuristic:
            text = heuristic["followup"]
            if not text.endswith(("。", "！", "？")):
                text += "。"
            return self._trim_text(text, limit)

        candidates = [
            item.get("practicality", ""),
            item.get("core_innovation", ""),
            item.get("summary", ""),
            item.get("description", ""),
        ]
        for candidate in candidates:
            cleaned = self._clean_notification_candidate(item, str(candidate))
            if cleaned:
                if not cleaned.endswith(("。", "！", "？")):
                    cleaned += "。"
                return self._trim_text(cleaned, limit)

        fallback = "今天的高相关候选，适合放进后续观察清单。"
        return self._trim_text(fallback, limit)

    def _notification_takeaway(self, item: dict[str, Any], *, kind: str, limit: int) -> str:
        if kind == "repo":
            tags = " / ".join((item.get("tags") or item.get("topics") or [])[:2])
            if "agent" in tags.lower():
                text = "如果你最近在看 agent 工程，可以优先打开它的 README 和示例流程。"
            elif "rag" in tags.lower():
                text = "如果你关注知识库问答或检索增强，先看它的整体架构和可复用部分。"
            elif item.get("stars", 0) >= 10000:
                text = "热度已经很高，建议先判断它是可直接上手的工具，还是更偏概念展示。"
            else:
                text = "建议先看 README、使用方式和最近提交，再判断成熟度。"
            return self._trim_text(text, limit)

        category = item.get("primary_category") or (item.get("categories") or [""])[0]
        if category in {"cs.AI", "cs.LG", "cs.CL", "cs.CV"}:
            text = "如果这正好贴近你的跟踪方向，建议放进本周精读候选，再决定是否深入。"
        else:
            text = "更适合作为趋势信号来读，先抓核心方法、场景和它解决的问题即可。"
        return self._trim_text(text, limit)

    def _heuristic_notification_detail(self, item: dict[str, Any], *, kind: str) -> dict[str, str] | None:
        text = " ".join(
            [
                item.get("title", ""),
                item.get("full_name", ""),
                item.get("name", ""),
                item.get("description", ""),
                " ".join(item.get("tags", [])),
                " ".join(item.get("topics", [])),
                " ".join(item.get("categories", [])),
            ]
        ).lower()

        if kind == "repo":
            repo_rules = [
                (["on-device", "genai", "gallery"], "展示端侧 AI 场景，方便本地试跑模型", "偏应用展示和本地体验，适合快速判断哪些模型能在设备侧真正跑起来"),
                (["framework", "agentic", "skills"], "面向智能体开发的技能框架和工程方法", "更适合拿来规范代理协作、任务拆解和工程执行方式"),
                (["knowledge graph", "graph rag", "browser"], "在浏览器里把代码仓库转成知识图谱，并支持 Graph RAG", "适合做代码理解、仓库问答和项目知识沉淀"),
                (["claude.md", "claude code"], "用规则文件提升 Claude Code 的编码表现", "看点在于把常见 LLM 编码坑沉淀成可复用的协作规范"),
                (["hedge fund"], "用多智能体模拟投研与对冲基金工作流", "适合观察 agent 在金融分析与决策协作场景里的组织方式"),
                (["seo", "blog", "content"], "用 AI 批量生成 SEO 长文内容", "更偏内容生产工作流，适合关注自动化写作与流量运营的人"),
                (["agentcore", "bedrock", "assistant"], "基于 AgentCore 的全栈 AI 助手示例", "适合看 Bedrock 与 AgentCore 的工程接入方式和全栈样例"),
                (["litert", "edge"], "面向端侧模型推理和本地运行的轻量项目", "重点看小模型在设备侧部署和运行时优化路径"),
            ]
            for keys, brief, followup in repo_rules:
                if all(key in text for key in keys):
                    return {"brief": brief, "followup": followup}

            tag = (item.get("tags") or item.get("topics") or ["AI"])[0]
            if item.get("language"):
                return {
                    "brief": f"一个围绕 {tag} 的 {item['language']} 开源项目",
                    "followup": "如果你关注工程落地，可以优先看它是否提供现成能力、工作流或可复用组件",
                }
            return {
                "brief": f"一个围绕 {tag} 的开源 AI 项目",
                "followup": "适合快速判断它是工具型项目、工作流项目，还是值得长期跟踪的新方向",
            }

        paper_rules = [
            (["cross-cultural", "benchmark", "metadata"], "做跨文化视觉理解基准，测试模型能否从图像推断文化信息", "适合关注视觉模型在文化语境理解上的盲点和评测方法"),
            (["retrieval", "medical", "question"], "系统比较医疗问答中的 RAG 检索链路设计", "重点看不同检索策略如何影响准确率、召回和最终回答质量"),
            (["motion", "video"], "研究动作可控视频生成，让动作与视角控制更稳定", "更适合关注视频生成、运动控制和时序一致性的研究进展"),
            (["training data", "data deletion"], "研究训练数据如何影响模型，并探索更快的数据删除", "这类工作和模型可解释性、隐私删除以及数据治理都高度相关"),
            (["android", "agent", "training"], "提升 Android 智能体在线训练效率，减少高成本交互", "适合关注手机端 agent、强化学习和低成本训练策略的人"),
            (["power", "data center"], "分析生成式 AI 负载功耗，为数据中心规划提供依据", "更偏基础设施层，适合关注 AI 成本、算力规划和能耗评估"),
        ]
        for keys, brief, followup in paper_rules:
            if all(key in text for key in keys):
                return {"brief": brief, "followup": followup}

        category = item.get("primary_category") or (item.get("categories") or ["AI"])[0]
        return {
            "brief": f"一篇聚焦 {category} 方向的最新论文",
            "followup": "适合先看它解决了什么问题，再判断是否值得进入你的精读列表",
        }

    def _clean_notification_candidate(self, item: dict[str, Any], text: str) -> str:
        text = " ".join((text or "").split())
        if not text:
            return ""

        titles = [item.get("title", ""), item.get("full_name", ""), item.get("name", "")]
        for title in titles:
            if title and text.startswith(title):
                text = text[len(title) :].lstrip(" ：:，,。")

        noise_phrases = [
            "是今天值得关注的 GitHub AI 项目。",
            "是最近值得追踪的一篇 AI 论文。",
            "它当前的公开描述是：",
            "论文摘要显示：",
            "结合关键词命中和热度信号，它适合加入今日重点观察列表。",
            "它与当前关注方向具有较强重合，适合快速阅读后决定是否深入。",
            "项目亮点主要体现在当前描述、主题标签和热度信号上，建议进一步查看 README 与近期提交。",
            "核心创新需要结合正文确认，但从标题和摘要看，它具备进入每日情报清单的价值。",
            "如果你关注开源 AI 工具链、模型应用或代理工作流，这个项目有较高的跟进价值。",
            "如果你关心最新研究趋势、模型能力或应用落地，这篇论文值得列入后续阅读。",
        ]
        for phrase in noise_phrases:
            text = text.replace(phrase, "")

        text = self._localize_tech_text(text)
        text = re.sub(r"\s*([,;:])\s*", r"\1 ", text)
        text = re.sub(r"\s+", " ", text).strip(" .;,:，；：")
        if len(text) < 6:
            return ""
        return text

    def _localize_tech_text(self, text: str) -> str:
        replacements = [
            (r"\bon-device\b", "端侧"),
            (r"\blocal(?:ly)?\b", "本地"),
            (r"\bml\b", "机器学习"),
            (r"\bgenai\b", "生成式 AI"),
            (r"\buse cases?\b", "使用场景"),
            (r"\bshowcases?\b", "展示"),
            (r"\bgallery\b", "展示库"),
            (r"\bframework\b", "框架"),
            (r"\bskills?\b", "技能"),
            (r"\bsoftware development methodology\b", "软件开发方法"),
            (r"\bagentic\b", "智能体"),
            (r"\bassistant\b", "助手"),
            (r"\bknowledge graph\b", "知识图谱"),
            (r"\bzero-server\b", "零服务端"),
            (r"\bclient-side\b", "纯浏览器端"),
            (r"\binteractive\b", "可交互"),
            (r"\bcode intelligence engine\b", "代码智能引擎"),
            (r"\bgraph rag\b", "Graph RAG"),
            (r"\bbrowser\b", "浏览器"),
            (r"\bretrieval-augmented\b", "RAG"),
            (r"\bretrieval pipeline\b", "检索链路"),
            (r"\bbenchmark\b", "评测基准"),
            (r"\breasoning\b", "推理"),
            (r"\bmotion-controlled videos?\b", "动作可控视频"),
            (r"\bwhole-facility data center infrastructure planning\b", "整机房数据中心基础设施规划"),
            (r"\bonline reinforcement learning\b", "在线强化学习"),
            (r"\bpower profiles\b", "功耗画像"),
            (r"\blong-form\b", "长文"),
        ]
        localized = text
        for pattern, replacement in replacements:
            localized = re.sub(pattern, replacement, localized, flags=re.IGNORECASE)
        return localized

    def _trim_text(self, text: str, limit: int) -> str:
        text = " ".join((text or "").split())
        return text[:limit] + ("..." if len(text) > limit else "")

    def _build_reports(self, history: dict[str, Any], digest: dict[str, Any]) -> dict[str, Any]:
        if not self.reports_config.get("enabled", True):
            return {}
        archive_items = self._archive_items(history)
        return {
            "weekly": self._build_period_report(
                archive_items,
                window_days=int(self.reports_config.get("weekly_window_days", 7)),
                label="周报",
                top_limit=int(self.reports_config.get("top_items_per_report", 8)),
                generated_at=digest["generated_at"],
            ),
            "monthly": self._build_period_report(
                archive_items,
                window_days=int(self.reports_config.get("monthly_window_days", 30)),
                label="月报",
                top_limit=int(self.reports_config.get("top_items_per_report", 8)),
                generated_at=digest["generated_at"],
            ),
        }

    def _build_period_report(
        self,
        items: list[dict[str, Any]],
        *,
        window_days: int,
        label: str,
        top_limit: int,
        generated_at: str,
    ) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        selected = []
        for item in items:
            timestamp = item.get("last_notified_at") or item.get("last_curated_at")
            if not timestamp:
                continue
            try:
                dt = datetime.fromisoformat(timestamp)
            except ValueError:
                continue
            if dt >= cutoff:
                selected.append(item)

        selected.sort(
            key=lambda item: (
                item.get("personalized_score", 0),
                item.get("relevance_score", 0),
            ),
            reverse=True,
        )
        top_items = selected[:top_limit]
        theme_counter = Counter()
        for item in top_items:
            for theme in item.get("themes", [])[:2]:
                theme_counter[theme] += 1

        highlights = []
        for item in top_items[:3]:
            title = item.get("title") or item.get("full_name") or item.get("name")
            highlights.append(
                {
                    "title": title,
                    "source": item.get("source"),
                    "selection_reason": item.get("selection_reason") or item.get("why_it_matters") or item.get("summary"),
                }
            )

        summary = f"近 {window_days} 天里，最集中的主题是 {'、'.join([name for name, _ in theme_counter.most_common(3)]) or 'AI 前沿'}。"
        return {
            "label": label,
            "window_days": window_days,
            "generated_at": generated_at,
            "count": len(selected),
            "summary": summary,
            "top_items": top_items,
            "top_themes": [{"theme": theme, "count": count} for theme, count in theme_counter.most_common(5)],
            "highlights": highlights,
        }

    def _update_history(self, history: dict[str, Any], digest: dict[str, Any], *, notified_at: str | None) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        items = history.setdefault("items", {})

        for item in [*digest["repos"], *digest["papers"]]:
            existing = items.get(item["id"], {})
            detail_slug = self._detail_slug(item)
            normalized = {
                **existing,
                **item,
                "detail_path": f"items/{detail_slug}.html",
                "first_seen_at": existing.get("first_seen_at", now_utc),
                "last_seen_at": now_utc,
                "last_curated_at": now_utc,
                "last_notified_at": notified_at or existing.get("last_notified_at"),
            }
            items[item["id"]] = normalized

        digests = history.setdefault("digests", [])
        digest_record = {
            "date": digest["date"],
            "title": digest["title"],
            "generated_at": digest["generated_at"],
            "notified_at": notified_at,
            "repo_ids": [item["id"] for item in digest["repos"]],
            "paper_ids": [item["id"] for item in digest["papers"]],
            "digest_json": f"data/digests/{digest['date']}.json",
            "digest_markdown": f"data/digests/{digest['date']}.md",
        }
        digests = [record for record in digests if record.get("date") != digest["date"]]
        digests.append(digest_record)
        digests.sort(key=lambda record: record.get("date", ""), reverse=True)

        history["digests"] = digests[: max(45, int(self.website_config.get("max_archive_items", 200)))]
        history["generated_at"] = now_utc

        archive_days = int(self.storage_config.get("archive_days", 30))
        cutoff = datetime.now(timezone.utc) - timedelta(days=archive_days)
        retained = {}
        for key, item in items.items():
            last_seen_at = item.get("last_seen_at")
            if not last_seen_at:
                retained[key] = item
                continue
            last_seen = datetime.fromisoformat(last_seen_at)
            if last_seen >= cutoff:
                retained[key] = item
        history["items"] = retained
        self._save_history(history)

    def _persist_digest_files(self, history: dict[str, Any], digest: dict[str, Any]) -> None:
        json_path = self.digests_dir / f"{digest['date']}.json"
        markdown_path = self.digests_dir / f"{digest['date']}.md"
        latest_json_path = self.data_dir / "latest.json"
        archive_json_path = self.data_dir / "archive.json"
        reports_dir = self.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(digest, handle, ensure_ascii=False, indent=2)
        markdown_path.write_text(digest["markdown"], encoding="utf-8")
        latest_json_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")

        archive_payload = {
            "generated_at": history.get("generated_at"),
            "items": self._archive_items(history),
            "digests": history.get("digests", []),
            "reports": digest.get("reports", {}),
        }
        archive_json_path.write_text(json.dumps(archive_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for period, report in (digest.get("reports") or {}).items():
            (reports_dir / f"{period}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _archive_items(self, history: dict[str, Any]) -> list[dict[str, Any]]:
        items = list(history.get("items", {}).values())
        items.sort(
            key=lambda item: (
                item.get("last_notified_at") or item.get("last_curated_at") or "",
                item.get("relevance_score", 0),
            ),
            reverse=True,
        )
        return items[: int(self.website_config.get("max_archive_items", 200))]

    def _generate_site(self, history: dict[str, Any], digest: dict[str, Any]) -> None:
        if self.site_dir.exists():
            shutil.rmtree(self.site_dir)

        (self.site_dir / "archive").mkdir(parents=True, exist_ok=True)
        (self.site_dir / "items").mkdir(parents=True, exist_ok=True)
        (self.site_dir / "reports").mkdir(parents=True, exist_ok=True)
        (self.site_dir / "assets").mkdir(parents=True, exist_ok=True)
        (self.site_dir / "data").mkdir(parents=True, exist_ok=True)
        (self.site_dir / ".nojekyll").write_text("", encoding="utf-8")

        self._copy_static_assets()

        archive_items = self._archive_items(history)
        search_index_path = self.site_dir / "data" / "search-index.json"
        search_index_path.write_text(
            json.dumps({"items": archive_items, "generated_at": digest["generated_at"]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        latest_bootstrap = {
            "mode": "latest",
            "title": digest["title"],
            "subtitle": "每天早上推送的 AI 项目与论文精选，含必看清单、主题聚类与历史归档。",
            "items": [*digest["repos"], *digest["papers"]],
            "sections": digest.get("sections", {}),
            "themeClusters": digest.get("theme_clusters", []),
            "reports": digest.get("reports", {}),
            "generatedAt": digest["generated_at"],
            "baseUrl": self.website_config.get("base_url", ""),
            "searchIndexUrl": "data/search-index.json",
        }
        archive_bootstrap = {
            "mode": "archive",
            "title": "近 30 天历史归档",
            "subtitle": "支持搜索、筛选、收藏、已读状态与主题回看。",
            "items": archive_items,
            "sections": {},
            "themeClusters": digest.get("theme_clusters", []),
            "reports": digest.get("reports", {}),
            "generatedAt": digest["generated_at"],
            "baseUrl": self.website_config.get("base_url", ""),
            "searchIndexUrl": "../data/search-index.json",
        }

        template = self.jinja_env.get_template("site_index.jinja")
        latest_html = template.render(
            page_title=digest["title"],
            page_description="AI Daily Digest 最新日报",
            bootstrap_json=json.dumps(latest_bootstrap, ensure_ascii=False),
            asset_prefix="",
        )
        (self.site_dir / "index.html").write_text(latest_html, encoding="utf-8")

        archive_html = template.render(
            page_title="历史归档",
            page_description="AI Daily Digest 近 30 天历史",
            bootstrap_json=json.dumps(archive_bootstrap, ensure_ascii=False),
            asset_prefix="../",
        )
        (self.site_dir / "archive" / "index.html").write_text(archive_html, encoding="utf-8")

        detail_template = self.jinja_env.get_template("site_detail.jinja")
        for item in archive_items:
            detail_html = detail_template.render(
                page_title=item.get("title", "详情"),
                page_description=item.get("summary", item.get("description", "")),
                item=item,
                bootstrap_json=json.dumps({"mode": "detail", "item": item}, ensure_ascii=False),
                asset_prefix="../",
            )
            detail_name = self._detail_slug(item)
            (self.site_dir / "items" / f"{detail_name}.html").write_text(detail_html, encoding="utf-8")

        report_template = self.jinja_env.get_template("site_report.jinja")
        for period, report in (digest.get("reports") or {}).items():
            report_html = report_template.render(
                page_title=f"AI Daily Digest {report.get('label', period)}",
                page_description=report.get("summary", ""),
                report=report,
                asset_prefix="../",
            )
            (self.site_dir / "reports" / f"{period}.html").write_text(report_html, encoding="utf-8")

    def _copy_static_assets(self) -> None:
        for filename in ("app.js", "app.css"):
            source = self.project_root / "static" / filename
            target = self.site_dir / "assets" / filename
            shutil.copy2(source, target)

    def _detail_slug(self, item: dict[str, Any]) -> str:
        source = item.get("source", "item")
        title = item.get("full_name") or item.get("title") or item.get("name") or item.get("id", "item")
        raw = f"{source}-{title}".lower()
        slug = []
        for char in raw:
            if char.isalnum():
                slug.append(char)
            elif char in {"-", "_"}:
                slug.append(char)
            else:
                slug.append("-")
        compact = "".join(slug)
        while "--" in compact:
            compact = compact.replace("--", "-")
        return compact.strip("-")[:96]


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI Daily Digest.")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML.")
    parser.add_argument("--skip-notify", action="store_true", help="Generate site/data only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    load_env_files(project_root)
    config_candidate = Path(args.config)
    if config_candidate.is_absolute():
        config_path = config_candidate
    elif config_candidate.exists():
        config_path = config_candidate.resolve()
    else:
        config_path = (project_root / args.config).resolve()
    config = load_config(config_path)
    logger = build_logger()

    try:
        app = DailyDigestApp(project_root, config, logger)
        app.run(skip_notify=args.skip_notify)
        return 0
    except Exception as exc:
        logger.exception("Digest run failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
