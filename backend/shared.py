#!/usr/bin/env python3
"""Shared paths, configuration inspection, and utility helpers for the web backend."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "research" / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
ENV_PATH = ROOT / ".env.clp"
RUNTIME_STATE_PATH = OUTPUT_DIR / "web_runtime_state.json"
RUN_HISTORY_PATH = OUTPUT_DIR / "run-history.json"

PLACEHOLDER_SECRETS = {
    "",
    "sk-xxxxxxxx",
    "sk-your-key",
    "sk-your-api-key",
    "your_key",
    "your-api-key",
    "你的_key",
    "changeme",
    "replace-me",
}


def load_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


BOOTSTRAPPED_ENV = load_env_file()
for _key, _value in BOOTSTRAPPED_ENV.items():
    os.environ.setdefault(_key, _value)


def get_effective_env(path: Path = ENV_PATH) -> dict[str, str]:
    """Merge persisted `.env.clp` values with live process `CLP_*` environment overrides."""
    merged = load_env_file(path)
    for key, value in os.environ.items():
        if key.startswith("CLP_"):
            merged[key] = value
    return merged


def save_env_file(values: dict[str, str], path: Path = ENV_PATH) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def is_placeholder_secret(value: str | None) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if lowered in PLACEHOLDER_SECRETS:
        return True
    return lowered.startswith("sk-xxxx")


def is_llm_configured(env: dict[str, str] | None = None) -> bool:
    resolved = env if env is not None else get_effective_env()
    api_key = str(resolved.get("CLP_API_KEY", "") or "").strip()
    return not is_placeholder_secret(api_key)


def is_demo_env_enabled(env: dict[str, str] | None = None) -> bool:
    resolved = env if env is not None else get_effective_env()
    flag = str(resolved.get("CLP_DEMO_MODE", "") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def get_demo_status(env: dict[str, str] | None = None) -> dict:
    resolved = env if env is not None else get_effective_env()
    llm_ok = is_llm_configured(resolved)
    demo_env = is_demo_env_enabled(resolved)
    active = demo_env or not llm_ok
    if demo_env:
        reason = "explicit_env"
    elif not llm_ok:
        reason = "unconfigured_api_key"
    else:
        reason = "disabled"
    return {
        "fallback_available": True,
        "demo_mode_env": demo_env,
        "llm_configured": llm_ok,
        "active": active,
        "reason": reason,
    }


def should_use_demo_mode(explicit_demo: bool | None = None) -> bool:
    if explicit_demo is True:
        return True
    if explicit_demo is False:
        return False
    return bool(get_demo_status()["active"])


def mask_secret(value: str | None) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or is_placeholder_secret(cleaned):
        return ""
    if len(cleaned) <= 10:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"


def tail_lines(path: Path, line_count: int = 120) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-line_count:]


def read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clone_jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def find_external_runs(exclude_pid: int | None = None) -> list[dict]:
    if os.name == "nt" or shutil.which("ps") is None:
        return []
    try:
        output = subprocess.check_output(
            ["ps", "-axo", "pid=,command="],
            text=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    runs = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "research.run" not in line or "server.py" in line:
            continue
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if not parts:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if exclude_pid and pid == exclude_pid:
            continue
        command = parts[1] if len(parts) > 1 else ""
        runs.append({"pid": pid, "command": command})
    return runs
