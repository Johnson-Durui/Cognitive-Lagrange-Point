from __future__ import annotations

import json
import logging
import os
import re
from typing import Any


class Summarizer:
    """负责生成中文摘要和 1-10 分相关性评分。"""

    def __init__(self, config: dict[str, Any], keywords: list[str], logger: logging.Logger | None = None) -> None:
        self.config = config
        self.keywords = keywords
        self.logger = logger or logging.getLogger(__name__)
        self.api_key = os.getenv(config.get("api_key_env", "GROK_API_KEY"), "").strip()
        self.model = config.get("model", "grok-4")
        self.base_url = config.get("base_url", "https://api.x.ai/v1")
        self.temperature = float(config.get("temperature", 0.2))
        self.llm_disabled_reason = ""

    def summarize_repositories(
        self,
        items: list[dict[str, Any]],
        *,
        top_k: int,
        max_candidates: int,
    ) -> list[dict[str, Any]]:
        return self._summarize_items(items, kind="repo", top_k=top_k, max_candidates=max_candidates)

    def summarize_papers(
        self,
        items: list[dict[str, Any]],
        *,
        top_k: int,
        max_candidates: int,
    ) -> list[dict[str, Any]]:
        return self._summarize_items(items, kind="paper", top_k=top_k, max_candidates=max_candidates)

    def summarize_repo(self, item: dict[str, Any]) -> dict[str, Any]:
        return self._summarize_single(item, kind="repo")

    def summarize_paper(self, item: dict[str, Any]) -> dict[str, Any]:
        return self._summarize_single(item, kind="paper")

    def summarize_news(
        self,
        items: list[dict[str, Any]],
        *,
        top_k: int,
        max_candidates: int,
    ) -> list[dict[str, Any]]:
        return self._summarize_items(items, kind="news", top_k=top_k, max_candidates=max_candidates)

    def _summarize_items(
        self,
        items: list[dict[str, Any]],
        *,
        kind: str,
        top_k: int,
        max_candidates: int,
    ) -> list[dict[str, Any]]:
        shortlisted = items[:max_candidates]
        enriched = [self._summarize_single(item, kind=kind) for item in shortlisted]
        enriched.sort(
            key=lambda item: (
                item.get("relevance_score", 0),
                item.get("heuristic_score", 0),
            ),
            reverse=True,
        )
        return enriched[:top_k]

    def _summarize_single(self, item: dict[str, Any], *, kind: str) -> dict[str, Any]:
        llm_result = self._call_model(item, kind=kind)
        if llm_result is None:
            llm_result = self._fallback_summary(item, kind=kind)

        enriched = dict(item)
        enriched.update(llm_result)
        enriched["summary_markdown"] = self._summary_markdown(enriched)
        return enriched

    def _call_model(self, item: dict[str, Any], *, kind: str) -> dict[str, Any] | None:
        if self.llm_disabled_reason:
            return None
        if not self.api_key:
            self.logger.info("LLM API key is not configured; use fallback summary for %s.", item.get("id"))
            return None

        try:
            from openai import OpenAI
        except ImportError:
            self.logger.warning("openai package is not installed; use fallback summary.")
            return None

        user_prompt = self._build_prompt(item, kind=kind)
        schema_hint = (
            '{"summary":"",'
            '"brief":"",'
            '"problem":"",'
            '"why_it_matters":"",'
            '"target_reader":"",'
            '"core_innovation":"",'
            '"highlights":["", ""],'
            '"practicality":"",'
            '"relevance_score":8,'
            '"tags":["", ""],'
            '"themes":["", ""],'
            '"selection_reason":""}'
        )

        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个非常强的 AI 研究编辑和开源情报分析师。"
                            "请只返回 JSON，不要输出额外解释。"
                            f"JSON 结构必须是：{schema_hint}"
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=700,
            )
            content = response.choices[0].message.content or ""
            parsed = self._parse_json_payload(content)
            if not parsed:
                raise ValueError("Empty JSON payload from model.")
            return self._normalize_llm_result(parsed)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            message = str(exc)
            lowered = message.lower()
            if "429" in message or "exhausted" in lowered or "spending limit" in lowered:
                self.llm_disabled_reason = message
                self.logger.warning("LLM quota exhausted; fallback summaries will be used for remaining items.")
            self.logger.warning("LLM summarization failed for %s: %s", item.get("id"), exc)
            return None

    def _build_prompt(self, item: dict[str, Any], *, kind: str) -> str:
        base = [
            "请用中文输出一个结构化 JSON，用于个人每日 AI 情报摘要。",
            "要求：summary 必须是 2-4 句话，简洁、专业、能帮人快速判断是否值得点开。",
            "brief 必须是 1 句话，适合微信里快速扫描。",
            "problem 用 1 句话写清它在解决什么问题。",
            "why_it_matters 用 1 句话写清为什么值得现在关注。",
            "target_reader 用短句写适合谁先看。",
            "highlights 至少 2 条，短句即可。",
            "relevance_score 取值范围 1-10，只能是整数。",
            "themes 输出 1-3 个中文短标签，例如 智能体 / 编码 / 多模态 / RAG / 推理 / 视频生成。",
            "selection_reason 用 1 句话解释为什么它应该进入今天的摘要。",
            f"用户长期关注关键词：{', '.join(self.keywords)}。",
        ]

        if kind == "repo":
            base.extend(
                [
                    f"仓库：{item.get('full_name', item.get('title', ''))}",
                    f"描述：{item.get('description', '')}",
                    f"Topics：{', '.join(item.get('topics', []))}",
                    f"语言：{item.get('language', '')}",
                    f"Stars：{item.get('stars', 0)}",
                    f"今日热度：{item.get('stars_today', 0)}",
                    "请重点评价：这个仓库是否代表一个值得追踪的新方向、实用工具或高势能开源项目。",
                ]
            )
        elif kind == "paper":
            base.extend(
                [
                    f"论文标题：{item.get('title', '')}",
                    f"摘要：{item.get('description', '')}",
                    f"分类：{', '.join(item.get('categories', []))}",
                    f"作者：{', '.join(item.get('authors', []))}",
                    "请重点评价：这篇论文的核心创新、落地潜力，以及是否值得加入每日重点关注列表。",
                ]
            )
        elif kind == "news":
            base.extend(
                [
                    f"新闻标题：{item.get('title', '')}",
                    f"来源：{item.get('source_name', '')}",
                    f"内容摘要：{item.get('description', '')}",
                    "请重点评价：这条新闻对 AI 前沿趋势、产品方向或行业格局意味着什么。",
                ]
            )

        return "\n".join(base)

    def _parse_json_payload(self, content: str) -> dict[str, Any] | None:
        content = content.strip()
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"```$", "", content)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    def _normalize_llm_result(self, result: dict[str, Any]) -> dict[str, Any]:
        highlights = result.get("highlights") or []
        if not isinstance(highlights, list):
            highlights = [str(highlights)]

        tags = result.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]

        relevance_score = result.get("relevance_score", 6)
        try:
            relevance_score = int(relevance_score)
        except (TypeError, ValueError):
            relevance_score = 6

        return {
            "summary": str(result.get("summary", "")).strip(),
            "brief": str(result.get("brief", "")).strip(),
            "problem": str(result.get("problem", "")).strip(),
            "why_it_matters": str(result.get("why_it_matters", "")).strip(),
            "target_reader": str(result.get("target_reader", "")).strip(),
            "core_innovation": str(result.get("core_innovation", "")).strip(),
            "highlights": [str(item).strip() for item in highlights if str(item).strip()],
            "practicality": str(result.get("practicality", "")).strip(),
            "relevance_score": max(1, min(10, relevance_score)),
            "tags": [str(item).strip() for item in tags if str(item).strip()],
            "themes": [str(item).strip() for item in (result.get("themes") or []) if str(item).strip()],
            "selection_reason": str(result.get("selection_reason", "")).strip(),
        }

    def _fallback_summary(self, item: dict[str, Any], *, kind: str) -> dict[str, Any]:
        description = item.get("description", "").strip()
        short_description = description[:240] + ("..." if len(description) > 240 else "")
        title = item.get("title") or item.get("full_name") or item.get("name") or "该项目"
        heuristic_score = float(item.get("heuristic_score", 0.0))
        heuristic_relevance = max(5, min(10, int(round(heuristic_score / 1.8)) or 6))
        matched_tags = [keyword for keyword in self.keywords if keyword.lower() in description.lower()][:4]

        if kind == "repo":
            summary = (
                f"{title} 是今天值得关注的 GitHub AI 项目。"
                f"它当前的公开描述是：{short_description or '暂无详细介绍。'}"
                "结合关键词命中和热度信号，它适合加入今日重点观察列表。"
            )
            brief = "这是一个值得快速关注的开源 AI 项目。"
            problem = "它试图把某类 AI 能力做成可直接使用的工具、框架或工作流。"
            why_it_matters = "如果你关注 AI 工程落地，这类项目通常能最快转化成实际产出。"
            target_reader = "适合正在看 agent、工具链或模型应用的人优先阅读。"
            innovation = "项目亮点主要体现在当前描述、主题标签和热度信号上，建议进一步查看 README 与近期提交。"
            practicality = "如果你关注开源 AI 工具链、模型应用或代理工作流，这个项目有较高的跟进价值。"
            highlights = [
                f"Stars: {item.get('stars', 0)}",
                f"语言: {item.get('language', 'Unknown')}",
            ]
            themes = matched_tags or ["开源工具"]
            selection_reason = "它兼具热度和相关性，适合进入今天的开源观察清单。"
        elif kind == "paper":
            summary = (
                f"{title} 是最近值得追踪的一篇 AI 论文。"
                f"论文摘要显示：{short_description or '暂无摘要。'}"
                "它与当前关注方向具有较强重合，适合快速阅读后决定是否深入。"
            )
            brief = "这是一篇值得加入今日论文雷达的最新工作。"
            problem = "它在某个细分 AI 方向上提出了新的方法、评测或系统设计。"
            why_it_matters = "如果这类问题正在升温，这篇论文通常能帮助你快速把握趋势。"
            target_reader = "适合正在追踪研究进展、方法演化或评测方向的人优先阅读。"
            innovation = "核心创新需要结合正文确认，但从标题和摘要看，它具备进入每日情报清单的价值。"
            practicality = "如果你关心最新研究趋势、模型能力或应用落地，这篇论文值得列入后续阅读。"
            highlights = [
                f"分类: {', '.join(item.get('categories', [])[:2]) or item.get('primary_category', 'N/A')}",
                f"作者数: {len(item.get('authors', []))}",
            ]
            themes = matched_tags or [item.get("primary_category") or "研究进展"]
            selection_reason = "它与当前高关注研究方向重合度高，适合进入今天的论文观察列表。"
        else:
            source_name = item.get("source_name", "新闻源")
            summary = (
                f"{source_name} 的这条 AI 新闻值得关注。"
                f"核心内容是：{short_description or '暂无更多摘要。'}"
                "它更适合作为判断行业方向和产品动作的快速信号。"
            )
            brief = "一条值得加入今日 AI 前沿观察的行业新闻。"
            problem = "它反映了 AI 产品、模型、资本或行业竞争格局中的新变化。"
            why_it_matters = "这类新闻往往决定接下来一段时间最值得跟进的公司、技术和叙事方向。"
            target_reader = "适合关注 AI 行业动态、产品发布和公司动作的人优先阅读。"
            innovation = "新闻类条目更强调行业动向和趋势信号，而不是技术细节。"
            practicality = "适合快速判断最近行业关注点，再决定是否继续追原文。"
            highlights = [
                f"来源: {source_name}",
                "价值: 趋势判断",
            ]
            themes = matched_tags or ["AI 新闻"]
            selection_reason = "它能帮助你快速感知今天 AI 行业里最值得注意的动态。"

        return {
            "summary": summary,
            "brief": brief,
            "problem": problem,
            "why_it_matters": why_it_matters,
            "target_reader": target_reader,
            "core_innovation": innovation,
            "highlights": highlights,
            "practicality": practicality,
            "relevance_score": heuristic_relevance,
            "tags": matched_tags or ["daily-pick"],
            "themes": themes[:3],
            "selection_reason": selection_reason,
        }

    def _summary_markdown(self, item: dict[str, Any]) -> str:
        highlights = "\n".join(f"- {highlight}" for highlight in item.get("highlights", []))
        return (
            f"**摘要**：{item.get('summary', '')}\n\n"
            f"**核心创新**：{item.get('core_innovation', '')}\n\n"
            f"**实用性**：{item.get('practicality', '')}\n\n"
            f"**相关性评分**：{item.get('relevance_score', 0)}/10\n\n"
            f"**亮点**：\n{highlights}"
        )
