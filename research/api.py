"""认知拉格朗日点 · API 客户端（OpenAI 兼容格式）"""

import json
import re
import os
from openai import OpenAI, APIStatusError

# 默认模型
MODEL = os.environ.get("CLP_MODEL", "deepseek-v3")
client: OpenAI | None = None


def get_client() -> OpenAI:
    global client
    if client is None:
        api_key = os.environ.get("CLP_API_KEY")
        base_url = os.environ.get("CLP_BASE_URL")
        if not api_key:
            raise RuntimeError(
                "请设置 CLP_API_KEY 环境变量\n"
                "  export CLP_API_KEY=sk-..."
            )
        client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
        )
    return client


class QuotaExhaustedError(Exception):
    """中转站额度耗尽"""
    pass


def call_agent(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    _retries: int = 3,
) -> str:
    """Single-turn agent call. Returns the text response. Auto-retries on empty."""
    import time as _time

    for attempt in range(_retries):
        try:
            resp = get_client().chat.completions.create(
                model=model or MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
        except APIStatusError as e:
            if "额度不足" in str(e) or "insufficient" in str(e).lower() or e.status_code == 403:
                raise QuotaExhaustedError(f"API额度已耗尽: {e}") from e
            if attempt < _retries - 1:
                _time.sleep(1)
                continue
            raise

        text = resp.choices[0].message.content
        if text and text.strip():
            return text

        # 空响应，等一下重试
        if attempt < _retries - 1:
            _time.sleep(0.5)
            continue

    raise ValueError("模型连续返回空响应")


def _extract_json(text: str) -> dict | list:
    """从模型输出中提取JSON，处理各种格式。"""
    # 1. 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 尝试从 ```json ... ``` 提取
    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 尝试从 ``` ... ``` 提取
    m = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 4. 尝试找到第一个 [ 或 { 开始的JSON
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        idx = text.find(start_char)
        if idx >= 0:
            ridx = text.rfind(end_char)
            if ridx > idx:
                try:
                    return json.loads(text[idx:ridx + 1])
                except json.JSONDecodeError:
                    pass

    raise ValueError(f"无法从模型输出中提取JSON。输出前200字符: {text[:200]}")


def call_agent_json(
    system_prompt: str,
    user_message: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.5,
    retries: int = 2,
) -> dict | list:
    """Agent call that expects JSON output. Parses and returns the data."""
    for attempt in range(retries + 1):
        try:
            text = call_agent(
                system_prompt,
                user_message,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return _extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            if attempt < retries:
                print(f"      ⟳ JSON解析失败，重试 ({attempt+1}/{retries})...")
                continue
            raise
