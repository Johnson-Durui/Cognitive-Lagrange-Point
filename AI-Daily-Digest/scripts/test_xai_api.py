from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from requests import Response
from requests.exceptions import RequestException


def load_env_files(project_root: Path) -> list[Path]:
    loaded: list[Path] = []
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
        loaded.append(env_path)
    return loaded


def load_config(project_root: Path) -> dict:
    config_path = project_root / "config.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def mask_secret(value: str) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def build_payload(model: str, prompt: str) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": 32,
        "messages": [
            {"role": "system", "content": "Reply with one short sentence only."},
            {"role": "user", "content": prompt},
        ],
    }


def request_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def summarize_response(response: Response) -> dict[str, Any]:
    body_text = response.text
    try:
        parsed = response.json()
    except Exception:
        parsed = None
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "x_request_id": response.headers.get("x-request-id"),
        "openai_processing_ms": response.headers.get("openai-processing-ms"),
        "body": parsed if parsed is not None else body_text,
    }


def print_response(label: str, response: Response) -> None:
    summary = summarize_response(response)
    print(f"{label}_status_code: {summary['status_code']}")
    print(
        f"{label}_headers: "
        + json.dumps(
            {
                "content-type": summary["content_type"],
                "x-request-id": summary["x_request_id"],
                "openai-processing-ms": summary["openai_processing_ms"],
            },
            ensure_ascii=False,
        )
    )
    print(f"{label}_body:")
    print(json.dumps(summary["body"], ensure_ascii=False, indent=2) if isinstance(summary["body"], dict) else summary["body"])


def fetch_models(base_url: str, api_key: str, timeout: int) -> Response:
    return requests.get(
        f"{base_url}/models",
        headers=request_headers(api_key),
        timeout=timeout,
    )


def model_ids_from_response(response: requests.Response) -> list[str]:
    try:
        body = response.json()
    except Exception:
        return []
    data = body.get("data", [])
    ids: list[str] = []
    for item in data:
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id:
            ids.append(model_id)
    return ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal xAI API probe.")
    parser.add_argument("--prompt", default="Reply with OK only.", help="Prompt to send.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds.")
    parser.add_argument("--list-models", action="store_true", help="List models from /models before probing.")
    parser.add_argument("--probe-grok-models", action="store_true", help="Probe each returned Grok model id with a chat request.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of models to probe.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    loaded_envs = load_env_files(project_root)
    config = load_config(project_root)

    llm_config = config.get("llm", {})
    api_key_env = llm_config.get("api_key_env", "GROK_API_KEY")
    api_key = os.getenv(api_key_env, "").strip()
    base_url = llm_config.get("base_url", "https://api.x.ai/v1").rstrip("/")
    model = llm_config.get("model", "grok-4")
    endpoint = f"{base_url}/chat/completions"
    payload = build_payload(model=model, prompt=args.prompt)

    print("== xAI Probe ==")
    print(f"timestamp_utc: {datetime.now(timezone.utc).isoformat()}")
    print(f"project_root: {project_root}")
    print(f"loaded_env_files: {[str(path) for path in loaded_envs]}")
    print(f"api_key_env: {api_key_env}")
    print(f"api_key_masked: {mask_secret(api_key)}")
    print(f"endpoint: {endpoint}")
    print(f"model: {model}")
    print(f"timeout_seconds: {args.timeout}")
    print(f"request_payload: {json.dumps(payload, ensure_ascii=False)}")

    if not api_key:
        print("error: missing API key")
        return 2

    final_status = 0
    models_response: Response | None = None
    model_ids: list[str] = []

    if args.list_models or args.probe_grok_models:
        models_response = fetch_models(base_url=base_url, api_key=api_key, timeout=args.timeout)
        print_response("models", models_response)
        model_ids = model_ids_from_response(models_response)
        print(f"models_count: {len(model_ids)}")
        print(f"models_ids: {json.dumps(model_ids, ensure_ascii=False)}")
        if not models_response.ok:
            return 1
        if args.list_models and not args.probe_grok_models:
            return 0

    if args.probe_grok_models:
        grok_models = [model_id for model_id in model_ids if "grok" in model_id.lower()]
        grok_models = grok_models[: args.limit]
        print(f"probe_targets: {json.dumps(grok_models, ensure_ascii=False)}")
        if not grok_models:
            print("probe_result: no grok-like model ids returned by /models")
            return 1

        any_success = False
        for candidate in grok_models:
            candidate_payload = build_payload(model=candidate, prompt=args.prompt)
            print(f"== model_probe: {candidate} ==")
            try:
                response = requests.post(
                    endpoint,
                    headers=request_headers(api_key),
                    json=candidate_payload,
                    timeout=args.timeout,
                )
                print_response("probe", response)
                if response.ok:
                    any_success = True
                    try:
                        body = response.json()
                        content = body["choices"][0]["message"]["content"]
                        print(f"probe_parsed_content: {content!r}")
                    except Exception:
                        pass
                else:
                    final_status = 1
            except RequestException as exc:
                final_status = 1
                print("probe_error:")
                print(repr(exc))

        return 0 if any_success else final_status or 1

    response = requests.post(
        endpoint,
        headers=request_headers(api_key),
        json=payload,
        timeout=args.timeout,
    )

    print_response("chat", response)

    if response.ok:
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            print(f"parsed_content: {content!r}")
        except Exception:
            pass
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
