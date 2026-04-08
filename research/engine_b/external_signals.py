"""Local external signal snapshots for Engine B."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = ROOT_DIR / "data" / "external_signals"


def _normalize_text(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(value: object) -> list[str]:
    text = _normalize_text(value)
    if not text:
        return []
    return [token for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{3,}", text) if token]


def load_signal_snapshots() -> list[dict]:
    snapshots: list[dict] = []
    if not SNAPSHOT_DIR.exists():
        return snapshots
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            snapshots.append(payload)
    return snapshots


def _score_snapshot(snapshot: dict, query: str) -> float:
    query_text = _normalize_text(query)
    if not query_text:
        return 0.0

    query_tokens = set(_tokenize(query_text))
    aliases = snapshot.get("aliases", []) if isinstance(snapshot.get("aliases"), list) else []
    score = 0.0

    for alias in aliases:
        alias_norm = _normalize_text(alias)
        if alias_norm and alias_norm in query_text:
            score += 4.0

    snapshot_tokens = set(_tokenize(str(snapshot.get("title", "") or "")))
    snapshot_tokens.update(_tokenize(" ".join(str(item or "") for item in aliases)))
    score += len(query_tokens & snapshot_tokens) * 1.2

    signals = snapshot.get("signals", []) if isinstance(snapshot.get("signals"), list) else []
    for item in signals:
        if not isinstance(item, dict):
            continue
        score += len(query_tokens & set(_tokenize(item.get("summary", "")))) * 0.35
    return score


def _signal_entry(snapshot: dict, signal: dict) -> dict:
    stance = str(signal.get("stance", "") or "").strip().lower()
    if stance not in {"positive", "negative", "neutral", "mixed"}:
        stance = "neutral"
    return {
        "id": str(signal.get("id", "") or "").strip(),
        "snapshot_id": str(snapshot.get("id", "") or "").strip(),
        "snapshot_title": str(snapshot.get("title", "") or "").strip(),
        "source": str(snapshot.get("source", "local_snapshot") or "local_snapshot").strip(),
        "captured_at": str(snapshot.get("captured_at", "") or "").strip(),
        "time": str(signal.get("time", "") or "").strip(),
        "stance": stance,
        "summary": str(signal.get("summary", "") or "").strip(),
    }


def retrieve_external_signals(query: str, limit: int = 6) -> list[dict]:
    ranked = []
    for snapshot in load_signal_snapshots():
        score = _score_snapshot(snapshot, query)
        if score > 0:
            ranked.append((score, snapshot))

    if not ranked:
        return []

    ranked.sort(key=lambda item: item[0], reverse=True)
    signals: list[dict] = []
    for _score, snapshot in ranked:
        for item in snapshot.get("signals", []) if isinstance(snapshot.get("signals"), list) else []:
            if not isinstance(item, dict):
                continue
            entry = _signal_entry(snapshot, item)
            if entry["summary"]:
                signals.append(entry)
            if len(signals) >= limit:
                return signals
    return signals[:limit]


def format_external_signals_for_prompt(signals: list[dict] | None) -> str:
    rows = []
    for item in (signals or [])[:6]:
        if not isinstance(item, dict):
            continue
        stance = str(item.get("stance", "neutral") or "neutral").strip()
        time_text = str(item.get("time", "") or item.get("captured_at", "") or "").strip()
        summary = str(item.get("summary", "") or "").strip()
        if not summary:
            continue
        prefix = f"[{time_text}] " if time_text else ""
        rows.append(f"- {prefix}{stance}: {summary}")
    if not rows:
        return "（暂无可用的外部市场声音快照）"
    return "注：以下是本地整理的外部市场声音快照，不是请求时实时抓取。\n" + "\n".join(rows)
