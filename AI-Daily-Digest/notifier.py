from __future__ import annotations

import logging
import os
from typing import Any

import requests


class Notifier:
    """支持企业微信 Webhook 与 PushPlus 两种通知方式。"""

    def __init__(self, config: dict[str, Any], logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.provider = config.get("provider", "wecom")
        self.timeout = int(config.get("timeout_seconds", 20))
        self.title_prefix = config.get("title_prefix", "AI Daily Digest")
        self.wecom_webhook = os.getenv(config.get("wecom_webhook_env", "WECOM_WEBHOOK_URL"), "").strip()
        self.pushplus_token = os.getenv(config.get("pushplus_token_env", "PUSHPLUS_TOKEN"), "").strip()

    def send_markdown(self, title: str, content: str) -> dict[str, Any]:
        if self.provider == "pushplus":
            return self._send_pushplus(title, content)
        return self._send_wecom(title, content)

    def _send_wecom(self, title: str, content: str) -> dict[str, Any]:
        if not self.wecom_webhook:
            self.logger.info("WECOM_WEBHOOK_URL is not configured; skip notification.")
            return {"ok": False, "skipped": True, "provider": "wecom"}

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"# {title}\n\n{content}",
            },
        }
        response = requests.post(self.wecom_webhook, json=payload, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        ok = result.get("errcode", 1) == 0
        if not ok:
            raise RuntimeError(f"WeCom notification failed: {result}")
        return {"ok": True, "provider": "wecom", "response": result}

    def _send_pushplus(self, title: str, content: str) -> dict[str, Any]:
        if not self.pushplus_token:
            self.logger.info("PUSHPLUS_TOKEN is not configured; skip notification.")
            return {"ok": False, "skipped": True, "provider": "pushplus"}

        payload = {
            "token": self.pushplus_token,
            "title": f"{self.title_prefix} | {title}",
            "content": content,
            "template": "markdown",
        }
        response = requests.post("https://www.pushplus.plus/send", json=payload, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        ok = result.get("code") == 200
        if not ok:
            raise RuntimeError(f"PushPlus notification failed: {result}")
        return {"ok": True, "provider": "pushplus", "response": result}

