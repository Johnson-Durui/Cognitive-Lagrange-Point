"""认知拉格朗日点 · API 客户端（OpenAI 兼容格式）"""

from __future__ import annotations

import ast
import json
import os
import random
import re
import time
from urllib.parse import urlparse

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)


def _csv_env(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


MODEL = os.environ.get("CLP_MODEL", "deepseek-v3")
MODEL_FALLBACKS = _csv_env("CLP_MODEL_FALLBACKS")
JSON_FALLBACK_MODELS = _csv_env("CLP_JSON_FALLBACK_MODELS")
JSON_LOW_MODELS = _csv_env("CLP_JSON_LOW_MODELS")
JSON_MEDIUM_MODELS = _csv_env("CLP_JSON_MEDIUM_MODELS")
JSON_HIGH_MODELS = _csv_env("CLP_JSON_HIGH_MODELS")
JSON_DOWNGRADE_TIERS = [
    item.strip().lower()
    for item in os.environ.get("CLP_JSON_DOWNGRADE_TIERS", "low,medium,high").split(",")
    if item.strip()
]
API_RETRIES = max(1, int(os.environ.get("CLP_API_RETRIES", "3")))
API_TIMEOUT = float(os.environ.get("CLP_TIMEOUT_SECONDS", "90"))
RETRY_BASE_DELAY = float(os.environ.get("CLP_RETRY_BASE_DELAY", "1.2"))
DIAGNOSTIC_LOG = os.environ.get(
    "CLP_API_LOG_PATH",
    os.path.join(os.path.dirname(__file__), "output", "api_diagnostics.jsonl"),
)

# ── Token 使用量追踪 ──────────────────────────────────────────────────────
_total_prompt_tokens: int = 0
_total_completion_tokens: int = 0
_total_tokens: int = 0
_call_count: int = 0


def get_token_summary() -> dict:
    """返回累计 token 消耗摘要。"""
    return {
        "prompt_tokens": _total_prompt_tokens,
        "completion_tokens": _total_completion_tokens,
        "total_tokens": _total_tokens,
        "api_calls": _call_count,
    }


def print_token_summary() -> None:
    """打印 token 消耗摘要。"""
    s = get_token_summary()
    print(
        f"\n  📊 Token 消耗摘要",
        f"  API 调用次数：{s['api_calls']}",
        f"  Prompt Tokens：{s['prompt_tokens']:,}",
        f"  Completion Tokens：{s['completion_tokens']:,}",
        f"  总消耗：{s['total_tokens']:,}",
        sep="\n  ",
        flush=True,
    )


def reset_token_counter() -> None:
    """重置 token 计数器（每次实验开始时调用）。"""
    global _total_prompt_tokens, _total_completion_tokens, _total_tokens, _call_count
    _total_prompt_tokens = 0
    _total_completion_tokens = 0
    _total_tokens = 0
    _call_count = 0


client: OpenAI | None = None
client_config: tuple[str | None, str | None, float] | None = None


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _diagnostics_enabled() -> bool:
    return _env_flag("CLP_API_LOG", True)


def _log_diagnostic(event: str, **fields) -> None:
    if not _diagnostics_enabled():
        return

    os.makedirs(os.path.dirname(DIAGNOSTIC_LOG), exist_ok=True)
    payload = {"event": event, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **fields}
    with open(DIAGNOSTIC_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _iter_models(
    requested_model: str | None,
    *,
    extra_models: list[str] | None = None,
    include_global_fallbacks: bool = True,
) -> list[str]:
    models = [requested_model or MODEL]
    if include_global_fallbacks:
        models.extend(MODEL_FALLBACKS)
    if extra_models:
        models.extend(extra_models)
    unique_models = []
    seen = set()
    for name in models:
        if not name or name in seen:
            continue
        seen.add(name)
        unique_models.append(name)
    return unique_models


def _expand_model_alias(name: str, requested_model: str) -> list[str]:
    alias = name.strip().lower()
    if alias in {"default", "requested", "primary", "model"}:
        return [requested_model]
    if alias in {"fallback", "fallbacks", "global_fallbacks"}:
        return MODEL_FALLBACKS
    if alias in {"json_fallback", "json_fallbacks"}:
        return JSON_FALLBACK_MODELS
    return [name]


def _resolve_json_tier_models(
    configured_models: list[str],
    requested_model: str,
    *,
    default_models: list[str],
) -> list[str]:
    raw_models = configured_models or default_models
    models: list[str] = []
    seen: set[str] = set()

    for item in raw_models:
        for name in _expand_model_alias(item, requested_model):
            if not name or name in seen:
                continue
            seen.add(name)
            models.append(name)

    return models or [requested_model]


def get_client() -> OpenAI:
    global client, client_config

    api_key = os.environ.get("CLP_API_KEY")
    base_url = os.environ.get("CLP_BASE_URL") or "https://api.openai.com/v1"
    if not api_key:
        raise RuntimeError(
            "请设置 CLP_API_KEY 环境变量\n"
            "  export CLP_API_KEY=sk-..."
        )

    config = (api_key, base_url, API_TIMEOUT)
    if client is None or client_config != config:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=API_TIMEOUT,
            max_retries=0,
        )
        client_config = config
    return client


class QuotaExhaustedError(Exception):
    """中转站额度耗尽"""


def _backoff_delay(attempt: int) -> float:
    jitter = random.uniform(0, 0.35)
    return RETRY_BASE_DELAY * (2 ** attempt) + jitter


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    status_code = getattr(exc, "status_code", None)
    keywords = ("额度", "insufficient", "quota", "余额", "credit", "billing")
    return status_code == 402 or any(keyword in text for keyword in keywords)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
        return True
    if isinstance(exc, APIStatusError):
        return getattr(exc, "status_code", None) in {408, 409, 429, 500, 502, 503, 504}
    return False


def _normalize_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if content is None:
        return ""
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
                continue
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
                continue
            text = getattr(part, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        return "\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()
    return str(content).strip()


def _extract_text_from_mapping(payload: dict) -> str:
    choices = payload.get("choices") or []
    if choices:
        first_choice = choices[0] or {}
        if isinstance(first_choice, dict):
            delta = first_choice.get("delta") or {}
            if isinstance(delta, dict):
                text = _normalize_content(delta.get("content"))
                if text:
                    return text
            message = first_choice.get("message") or {}
            if isinstance(message, dict):
                text = _normalize_content(message.get("content"))
                if text:
                    return text
                refusal = message.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    return refusal.strip()
            text = _normalize_content(first_choice.get("text"))
            if text:
                return text

    output_items = payload.get("output") or []
    if isinstance(output_items, list):
        for item in output_items:
            if not isinstance(item, dict):
                continue
            content_items = item.get("content") or []
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if not isinstance(content, dict):
                    continue
                text = _normalize_content(content.get("text"))
                if text:
                    return text

    for key in ("output_text", "content", "text", "response", "result"):
        value = payload.get(key)
        text = _normalize_content(value)
        if text:
            return text

    return ""


def _extract_text_from_sse_string(resp: str) -> str:
    text = resp.strip()
    if not text.startswith("data:"):
        return text

    chunks: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue

        chunk = ""
        if isinstance(parsed, dict):
            choices = parsed.get("choices") or []
            if choices and isinstance(choices[0], dict):
                delta = choices[0].get("delta") or {}
                if isinstance(delta, dict):
                    content = delta.get("content")
                    if isinstance(content, str):
                        chunk = content
                    elif isinstance(content, list):
                        preserved_parts = []
                        for item in content:
                            if isinstance(item, str):
                                preserved_parts.append(item)
                            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                                preserved_parts.append(item["text"])
                        chunk = "".join(preserved_parts)
            if not chunk:
                chunk = _extract_text_from_mapping(parsed)
        if chunk:
            chunks.append(chunk)

    return "".join(chunk for chunk in chunks if chunk).strip()


def _extract_text(resp) -> str:
    if isinstance(resp, str):
        return _extract_text_from_sse_string(resp)

    if isinstance(resp, dict):
        return _extract_text_from_mapping(resp)

    output_text = getattr(resp, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    choices = getattr(resp, "choices", None) or []
    if not choices:
        if hasattr(resp, "model_dump"):
            try:
                dumped = resp.model_dump()
            except Exception:
                dumped = None
            if isinstance(dumped, dict):
                return _extract_text_from_mapping(dumped)
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        text = _normalize_content(getattr(choices[0], "text", None))
        if text:
            return text
        return ""

    text = _normalize_content(getattr(message, "content", None))
    if text:
        return text

    reasoning = _normalize_content(getattr(message, "reasoning_content", None))
    if reasoning:
        return reasoning

    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str):
        return refusal.strip()
    return ""


def _is_claude_model(model_name: str | None) -> bool:
    return "claude" in (model_name or "").lower()


def _is_official_openai_base_url() -> bool:
    base_url = (os.environ.get("CLP_BASE_URL") or "https://api.openai.com/v1").strip()
    try:
        parsed = urlparse(base_url)
        host = (parsed.netloc or "").lower()
    except Exception:
        host = base_url.lower()
    return host.endswith("api.openai.com")


def _use_responses_api(model_name: str | None) -> bool:
    name = (model_name or "").lower()
    if not name.startswith("gpt-5"):
        return False
    if os.environ.get("CLP_USE_RESPONSES_API") is not None:
        return _env_flag("CLP_USE_RESPONSES_API", False)
    return _is_official_openai_base_url()


def _usage_token_counts(usage) -> tuple[int, int, int]:
    if usage is None:
        return 0, 0, 0

    prompt_tokens = (
        getattr(usage, "prompt_tokens", None)
        or getattr(usage, "input_tokens", None)
        or 0
    )
    completion_tokens = (
        getattr(usage, "completion_tokens", None)
        or getattr(usage, "output_tokens", None)
        or 0
    )
    total_tokens = getattr(usage, "total_tokens", None) or (prompt_tokens + completion_tokens)
    return int(prompt_tokens), int(completion_tokens), int(total_tokens)


def _call_agent_with_model_list(
    models: list[str],
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    response_format: dict | None = None,
    _retries: int | None = None,
    timeout_seconds: float | None = None,
) -> str:
    """按给定模型列表调用，返回第一条有效文本。"""
    retries = max(1, _retries or API_RETRIES)
    last_error: Exception | None = None

    for model_name in models:
        for attempt in range(retries):
            try:
                started = time.time()
                client = get_client()
                request_client = client.with_options(timeout=timeout_seconds) if timeout_seconds else client
                kwargs = {
                    "model": model_name,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                }
                if response_format:
                    kwargs["response_format"] = response_format
                    
                if _use_responses_api(model_name):
                    # For gpt-5 or responses API models
                    resp = request_client.responses.create(
                        model=model_name,
                        instructions=system_prompt,
                        input=user_message,
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    )
                else:
                    resp = request_client.chat.completions.create(**kwargs)
                usage = getattr(resp, "usage", None)
                global _total_prompt_tokens, _total_completion_tokens, _total_tokens, _call_count
                _call_count += 1
                prompt_tokens, completion_tokens, total_tokens = _usage_token_counts(usage)
                if usage is not None:
                    _total_prompt_tokens += prompt_tokens
                    _total_completion_tokens += completion_tokens
                    _total_tokens += total_tokens
                text = _extract_text(resp)
                if text:
                    _log_diagnostic(
                        "request_ok",
                        model=model_name,
                        latency_ms=int((time.time() - started) * 1000),
                        text_len=len(text),
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                    )
                    return text

                last_error = ValueError("模型返回空响应")
                _log_diagnostic(
                    "empty_response",
                    model=model_name,
                    attempt=attempt + 1,
                )
            except Exception as exc:
                last_error = exc
                _log_diagnostic(
                    "request_error",
                    model=model_name,
                    attempt=attempt + 1,
                    error_type=type(exc).__name__,
                    detail=str(exc)[:500],
                )

                if _is_quota_error(exc):
                    if model_name != models[-1]:
                        print(f"      ⚠ {model_name} 额度/限流异常，切换备用模型...", flush=True)
                        break
                    raise QuotaExhaustedError(f"API额度已耗尽或被限流: {exc}") from exc

                if not _is_retryable(exc):
                    raise

            if attempt < retries - 1:
                delay = _backoff_delay(attempt)
                time.sleep(delay)
        else:
            continue

    if last_error is None:
        raise ValueError("模型未返回任何有效响应")
    raise last_error


def call_agent(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    _retries: int | None = None,
    timeout_seconds: float | None = None,
) -> str:
    """单轮调用模型；自动处理空响应、限流和网络抖动。"""
    models = _iter_models(model)
    return _call_agent_with_model_list(
        models,
        system_prompt,
        user_message,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format=None,
        _retries=_retries,
        timeout_seconds=timeout_seconds,
    )


def _extract_json(text: str) -> dict | list:
    """从模型输出中提取JSON，处理各种格式。"""
    text = text.strip().lstrip("\ufeff")

    def _try_load(candidate: str) -> dict | list | None:
        candidate = candidate.strip().lstrip("\ufeff")
        if not candidate:
            return None

        variants = [candidate]
        unfenced = re.sub(r"^\s*```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        unfenced = re.sub(r"\s*```\s*$", "", unfenced, flags=re.IGNORECASE)
        unfenced = unfenced.strip()
        if unfenced and unfenced != candidate:
            variants.append(unfenced)

        for item in variants:
            try:
                return json.loads(item)
            except json.JSONDecodeError:
                normalized = re.sub(r",(\s*[}\]])", r"\1", item)
                if normalized != item:
                    try:
                        return json.loads(normalized)
                    except json.JSONDecodeError:
                        pass

                if item[:1] in {"{", "["}:
                    try:
                        repaired = ast.literal_eval(item)
                    except (ValueError, SyntaxError):
                        repaired = None
                    if isinstance(repaired, (dict, list)):
                        return repaired
        return None

    parsed = _try_load(text)
    if parsed is not None:
        return parsed

    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        parsed = _try_load(m.group(1))
        if parsed is not None:
            return parsed

    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        parsed = _try_load(m.group(1))
        if parsed is not None:
            return parsed

    for start_char, end_char in [("[", "]"), ("{", "}")]:
        idx = text.find(start_char)
        if idx >= 0:
            ridx = text.rfind(end_char)
            if ridx > idx:
                parsed = _try_load(text[idx:ridx + 1])
                if parsed is not None:
                    return parsed

    raise ValueError(f"无法从模型输出中提取JSON。输出前200字符: {text[:200]}")


def _json_has_meaningful_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, dict):
        return any(_json_has_meaningful_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_json_has_meaningful_value(item) for item in value)
    return True


def _validate_json_payload(payload: dict | list) -> dict | list:
    # Disable strict meaningful_value checks because system prompts explicitly 
    # allow returning empty objects (e.g., "返回空的 emotional_insight 对象")
    # if the condition is not met. Modern json_object mode handles this well.
    return payload


JSON_REPAIR_SYSTEM = """你是一个严格的JSON修复器。

任务：
1. 将用户给出的“接近JSON但格式不合法”的内容修复成严格JSON
2. 保留原有字段名、层级和语义，不要编造新信息
3. 删除解释性文字、Markdown代码块标记和多余注释
4. 只输出修复后的JSON本体，不要输出任何额外说明
"""

JSON_DOWNGRADE_SYSTEM = """这是一个严格的结构化输出任务。

输出格式契约：
1. 只能输出合法 JSON，本体之外一个字都不要输出
2. 不要输出解释、前言、后记、免责声明或 Markdown 代码块
3. 如果信息不足，仍然要按要求保留字段结构，允许使用空字符串、0、false、空数组或空对象
4. 如果原始任务中出现自然语言分析要求，请把分析结果直接写入 JSON 字段，不要额外展开说明

下面是原始任务说明，请严格执行：
"""

JSON_DOWNGRADE_USER_SUFFIX = """

再次强调：
- 你的回答必须是可以被 json.loads 直接解析的 JSON
- 不要输出任何前言、后记或解释
"""

JSON_RESCUE_SYSTEM = """这是最终结构化补救阶段。

请把下面的任务结果整理成一个合法 JSON，并严格遵守以下约束：
1. 只输出 JSON 本体
2. 省略所有解释性文字、自然语言前后缀和 Markdown 代码块
3. 如果某些内容无法确定，也必须保留字段结构
4. 默认值规则：
   - 字符串："" 
   - 数字：0
   - 布尔：false
   - 数组：[]
   - 对象：{}

原始任务如下：
"""

JSON_RESCUE_USER_SUFFIX = """

请把这视为字段填空和格式整理任务。
你的输出必须是单个合法 JSON 对象或 JSON 数组。
"""


def _repair_json_with_model(
    raw_text: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict | list:
    repaired_text = call_agent(
        JSON_REPAIR_SYSTEM,
        f"请把下面内容修复成严格JSON，只输出JSON：\n\n{raw_text}",
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        _retries=1,
    )
    return _extract_json(repaired_text)


def _build_json_tiers(
    system_prompt: str,
    user_message: str,
    requested_model: str,
    temperature: float,
    retries: int,
) -> list[dict]:
    low_models = _resolve_json_tier_models(
        JSON_LOW_MODELS,
        requested_model,
        default_models=[requested_model],
    )
    medium_models = _resolve_json_tier_models(
        JSON_MEDIUM_MODELS,
        requested_model,
        default_models=[requested_model],
    )
    high_default_models = JSON_FALLBACK_MODELS or MODEL_FALLBACKS or [requested_model]
    high_models = _resolve_json_tier_models(
        JSON_HIGH_MODELS,
        requested_model,
        default_models=high_default_models,
    )

    medium_temperature = 0.0 if _is_claude_model(requested_model) else min(temperature, 0.2)
    tiers_by_name = {
        "low": {
            "name": "low",
            "label": "低阶",
            "models": low_models,
            "system": system_prompt,
            "user": user_message,
            "temperature": temperature,
            "parse_retries": retries,
        },
        "medium": {
            "name": "medium",
            "label": "中阶",
            "models": medium_models,
            "system": f"{JSON_DOWNGRADE_SYSTEM}\n{system_prompt}",
            "user": f"{user_message}{JSON_DOWNGRADE_USER_SUFFIX}",
            "temperature": medium_temperature,
            "parse_retries": 0,
        },
        "high": {
            "name": "high",
            "label": "高阶",
            "models": high_models,
            "system": f"{JSON_RESCUE_SYSTEM}\n{system_prompt}",
            "user": f"{user_message}{JSON_RESCUE_USER_SUFFIX}",
            "temperature": 0.0,
            "parse_retries": 0,
        },
    }

    tiers = [tiers_by_name[name] for name in JSON_DOWNGRADE_TIERS if name in tiers_by_name]
    return tiers or [tiers_by_name["low"], tiers_by_name["medium"], tiers_by_name["high"]]


def call_agent_json(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.5,
    retries: int = 2,
    allow_downgrade: bool = True,
    response_format: dict | None = {"type": "json_object"},
    timeout_seconds: float | None = None,
) -> dict | list:
    """调用期望 JSON 的 Agent。使用 Pydantic schemas 返回更稳定的结果。"""

    # Fast path for chat-completions style JSON output.
    # GPT-5.* currently走 responses API 兼容路径，很多中转站不会真正执行 response_format；
    # 这时如果模型吐出“接近 JSON”的文本，不能直接 json.loads 后放弃，而要走解析/修复兜底。
    requested_model = model or MODEL
    can_use_fast_schema = bool(response_format) and not _use_responses_api(requested_model)

    if can_use_fast_schema:
        requested_model = model or MODEL
        models = _iter_models(requested_model)
        last_err = None
        for attempt in range(retries + 1):
            for model_name in models:
                try:
                    text = _call_agent_with_model_list(
                        [model_name],
                        system_prompt,
                        user_message,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format=response_format,
                        _retries=1,
                        timeout_seconds=timeout_seconds,
                    )
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError as exc:
                        last_err = exc
                        _log_diagnostic(
                            "json_fast_parse_error",
                            attempt=attempt + 1,
                            model=model_name,
                            detail=str(exc)[:500],
                        )
                        try:
                            return _validate_json_payload(_extract_json(text))
                        except Exception:
                            if text:
                                repaired = _validate_json_payload(_repair_json_with_model(
                                    text,
                                    model=model_name,
                                    max_tokens=max_tokens,
                                ))
                                _log_diagnostic(
                                    "json_fast_repair_ok",
                                    attempt=attempt + 1,
                                    model=model_name,
                                )
                                return repaired
                            raise
                    else:
                        return _validate_json_payload(parsed)
                except Exception as exc:
                    last_err = exc
                    pass
        if last_err:
            raise last_err
        raise ValueError("JSON Schema prompt failed")

    tiers = _build_json_tiers(system_prompt, user_message, requested_model, temperature, retries)
    if not allow_downgrade:
        tiers = tiers[:1]
    last_error: Exception | None = None

    for tier_idx, tier in enumerate(tiers):
        if tier_idx > 0:
            _log_diagnostic(
                "json_strategy_downgrade",
                tier=tier["name"],
                models=",".join(tier["models"]),
            )
            print(f"      ↘ JSON降级切换到{tier['label']}", flush=True)

        for model_name in tier["models"]:
            for attempt in range(tier["parse_retries"] + 1):
                text = ""
                try:
                    text = _call_agent_with_model_list(
                        [model_name],
                        tier["system"],
                        tier["user"],
                        max_tokens=max_tokens,
                        temperature=tier["temperature"],
                        _retries=1,
                        timeout_seconds=timeout_seconds,
                    )
                    return _validate_json_payload(_extract_json(text))
                except (ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
                    _log_diagnostic(
                        "json_parse_error",
                        attempt=attempt + 1,
                        model=model_name,
                        tier=tier["name"],
                        detail=str(exc)[:500],
                    )
                    if text:
                        try:
                            repaired = _validate_json_payload(_repair_json_with_model(
                                text,
                                model=model_name,
                                max_tokens=max_tokens,
                            ))
                            _log_diagnostic(
                                "json_repair_ok",
                                attempt=attempt + 1,
                                model=model_name,
                                tier=tier["name"],
                            )
                            return repaired
                        except Exception as repair_exc:
                            _log_diagnostic(
                                "json_repair_failed",
                                attempt=attempt + 1,
                                model=model_name,
                                tier=tier["name"],
                                detail=str(repair_exc)[:500],
                            )
                    if attempt < tier["parse_retries"]:
                        print(
                            f"      ⟳ {model_name} JSON解析失败，重试 ({attempt + 1}/{tier['parse_retries']})...",
                            flush=True,
                        )
                        time.sleep(_backoff_delay(attempt))
                        continue
                except Exception as exc:
                    last_error = exc
                    _log_diagnostic(
                        "json_request_failed",
                        attempt=attempt + 1,
                        model=model_name,
                        tier=tier["name"],
                        error_type=type(exc).__name__,
                        detail=str(exc)[:500],
                    )
                    break

    if last_error is not None:
        raise last_error
    raise ValueError("无法从模型输出中提取JSON")
