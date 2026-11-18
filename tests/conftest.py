"""Pytest configuration and offline Windows ASGI test client support."""

from __future__ import annotations

import json as json_lib
import os
from pathlib import Path
import sys
from unittest.mock import patch
import urllib.parse

import anyio.to_thread
import fastapi.testclient
import httpx
import starlette.testclient

from research.db import init_db


def _drive_coroutine_sync(coro):
    """Drive a non-yielding ASGI coroutine to completion in pure Python memory."""
    value = None
    while True:
        try:
            coro.send(value)
        except StopIteration as stop:
            return stop.value
        else:
            value = None


async def _inline_run_sync(func, *args, **_kwargs):
    return func(*args)


class InProcessASGITestClient:
    """Pure-Python ASGI 2.4 test client for Windows sandboxes without TCP loopback."""

    __test__ = False

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        **_kwargs,
    ) -> None:
        self.app = app
        self.base_url = base_url.rstrip("/")
        self.raise_server_exceptions = raise_server_exceptions

    def __enter__(self) -> InProcessASGITestClient:
        init_db()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | str | None = None,
        data: dict | None = None,
        json=None,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
        **_kwargs,
    ) -> httpx.Response:
        full_url = url if url.startswith(("http://", "https://")) else f"{self.base_url}/{url.lstrip('/')}"
        parsed = urllib.parse.urlsplit(full_url)

        query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if params:
            for k, v in params.items():
                if v is not None:
                    query_items.append((str(k), str(v)))
        encoded_query = urllib.parse.urlencode(query_items)
        if encoded_query:
            full_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, encoded_query, ""))

        req_headers: dict[str, str] = {"host": parsed.netloc or "testserver", "user-agent": "testclient"}
        if headers:
            for k, v in headers.items():
                req_headers[k.lower()] = str(v)

        body_bytes = b""
        if json is not None:
            body_bytes = json_lib.dumps(json, ensure_ascii=False).encode("utf-8")
            req_headers.setdefault("content-type", "application/json")
        elif content is not None:
            body_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        elif data is not None:
            body_bytes = urllib.parse.urlencode(data).encode("utf-8")
            req_headers.setdefault("content-type", "application/x-www-form-urlencoded")

        if body_bytes:
            req_headers.setdefault("content-length", str(len(body_bytes)))

        raw_headers = [(k.encode("latin-1"), v.encode("latin-1")) for k, v in req_headers.items()]
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": parsed.scheme or "http",
            "path": urllib.parse.unquote(parsed.path or "/"),
            "raw_path": (parsed.path or "/").encode("ascii", errors="ignore"),
            "query_string": encoded_query.encode("ascii", errors="ignore"),
            "root_path": "",
            "headers": raw_headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "extensions": {"http.response.pathsend": {}},
        }

        body_consumed = False
        status_code = 500
        resp_headers: list[tuple[str, str]] = []
        resp_chunks: list[bytes] = []

        async def receive():
            nonlocal body_consumed
            if not body_consumed:
                body_consumed = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal status_code, resp_headers
            msg_type = message.get("type")
            if msg_type == "http.response.start":
                status_code = int(message.get("status", 200))
                resp_headers = [
                    (k.decode("latin-1"), v.decode("latin-1"))
                    for k, v in (message.get("headers") or [])
                ]
            elif msg_type == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    resp_chunks.append(bytes(chunk))
            elif msg_type == "http.response.pathsend":
                file_path = Path(message["path"])
                resp_chunks.append(file_path.read_bytes())

        try:
            with patch.object(anyio.to_thread, "run_sync", side_effect=_inline_run_sync):
                _drive_coroutine_sync(self.app(scope, receive, send))
        except Exception:
            if self.raise_server_exceptions:
                raise
            status_code = 500
            resp_headers = [("content-type", "text/plain; charset=utf-8")]
            resp_chunks = [b"Internal Server Error"]

        return httpx.Response(
            status_code=status_code,
            headers=resp_headers,
            content=b"".join(resp_chunks),
            request=httpx.Request(method.upper(), full_url),
        )

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)


if sys.platform == "win32" and os.environ.get("CLP_USE_STARLETTE_TESTCLIENT") != "1":
    starlette.testclient.TestClient = InProcessASGITestClient  # type: ignore[misc]
    fastapi.testclient.TestClient = InProcessASGITestClient  # type: ignore[misc]
    for _mod in list(sys.modules.values()):
        if getattr(_mod, "TestClient", None) is not None and getattr(_mod, "__name__", "").startswith("tests."):
            _mod.TestClient = InProcessASGITestClient  # type: ignore[attr-defined]
