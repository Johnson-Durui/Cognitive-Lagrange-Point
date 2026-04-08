#!/usr/bin/env python3
"""Shared paths and utility helpers for the local web backend."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "research" / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
ENV_PATH = ROOT / ".env.clp"
RUNTIME_STATE_PATH = OUTPUT_DIR / "web_runtime_state.json"
RUN_HISTORY_PATH = OUTPUT_DIR / "run-history.json"


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
    os.environ[_key] = _value


def save_env_file(values: dict[str, str], path: Path = ENV_PATH) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-6:]}"


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

