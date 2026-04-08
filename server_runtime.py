#!/usr/bin/env python3
"""Runtime manager split out from server_core.py."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from research.checkpoint_utils import (
    checkpoint_to_results_payload,
    get_run_artifacts,
    rebuild_survivors_from_checkpoint,
    summarize_checkpoint,
    summarize_checkpoint_payload,
)

from server_shared import (
    ENV_PATH,
    OUTPUT_DIR,
    ROOT,
    RUNS_DIR,
    RUN_HISTORY_PATH,
    RUNTIME_STATE_PATH,
    find_external_runs,
    load_env_file,
    mask_secret,
    now_iso,
    pid_alive,
    read_json,
    save_env_file,
    tail_lines,
)


class RuntimeManager:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        self.state = self._load_state()

    def _load_state(self) -> dict:
        data = read_json(RUNTIME_STATE_PATH)
        if isinstance(data, dict):
            return data
        return {
            "status": "idle",
            "pid": None,
            "started_at": None,
            "stopped_at": None,
            "exit_code": None,
            "log_path": None,
            "command": [],
            "preset": None,
        }

    def _save_state(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_STATE_PATH.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _refresh_process_state(self) -> None:
        if self.process is not None:
            exit_code = self.process.poll()
            if exit_code is not None:
                self.state["status"] = "exited"
                self.state["exit_code"] = exit_code
                self.state["stopped_at"] = now_iso()
                self.process = None
                if self.log_handle is not None:
                    try:
                        self.log_handle.close()
                    except OSError:
                        pass
                    self.log_handle = None
                run_id = self.state.get("run_id")
                if run_id:
                    checkpoint = summarize_checkpoint()
                    self._update_history_completed(
                        run_id,
                        exit_code=exit_code,
                        completed_at=self.state["stopped_at"],
                        total_candidates=checkpoint.get("selected_count", 0),
                        confirmed_count=checkpoint.get("confirmed_count", 0),
                    )
                self._save_state()
            return

        if self.state.get("status") == "running" and not pid_alive(self.state.get("pid")):
            self.state["status"] = "exited"
            self.state["stopped_at"] = now_iso()
            run_id = self.state.get("run_id")
            if run_id:
                checkpoint = summarize_checkpoint()
                self._update_history_completed(
                    run_id,
                    exit_code=None,
                    completed_at=self.state["stopped_at"],
                    total_candidates=checkpoint.get("selected_count", 0),
                    confirmed_count=checkpoint.get("confirmed_count", 0),
                )
            self._save_state()

    def get_status(self) -> dict:
        with self.lock:
            self._refresh_process_state()
            process_state = {
                "status": self.state.get("status", "idle"),
                "running": self.state.get("status") == "running" and pid_alive(self.state.get("pid")),
                "pid": self.state.get("pid"),
                "started_at": self.state.get("started_at"),
                "stopped_at": self.state.get("stopped_at"),
                "exit_code": self.state.get("exit_code"),
                "log_path": self.state.get("log_path"),
                "preset": self.state.get("preset"),
                "command": self.state.get("command", []),
            }
            return {
                "process": process_state,
                "external_runs": find_external_runs(exclude_pid=process_state["pid"]),
                "checkpoint": summarize_checkpoint(),
                "config": self.get_config_summary(),
            }

    def get_config_summary(self) -> dict:
        env = load_env_file()
        return {
            "base_url": env.get("CLP_BASE_URL", ""),
            "model": env.get("CLP_MODEL", ""),
            "fallbacks": env.get("CLP_MODEL_FALLBACKS", ""),
            "api_key_present": bool(env.get("CLP_API_KEY")),
            "api_key_preview": mask_secret(env.get("CLP_API_KEY", "")),
        }

    def save_config(self, payload: dict) -> dict:
        env = load_env_file()
        current_key = env.get("CLP_API_KEY", "")
        api_key = str(payload.get("api_key") or "").strip()
        env["CLP_API_KEY"] = api_key or current_key
        env["CLP_BASE_URL"] = str(payload.get("base_url") or env.get("CLP_BASE_URL", "")).strip()
        env["CLP_MODEL"] = str(payload.get("model") or env.get("CLP_MODEL", "")).strip()
        env["CLP_MODEL_FALLBACKS"] = str(payload.get("fallbacks") or env.get("CLP_MODEL_FALLBACKS", "")).strip()
        save_env_file(env)
        return self.get_config_summary()

    def _preset_env(self, preset: str) -> dict[str, str]:
        if preset == "quick":
            return {
                "CLP_FRESH_START": "1",
                "CLP_MINERS": "A",
                "CLP_MAX_STAGE2": "6",
                "CLP_ENABLE_FILTER1": "0",
                "CLP_ENABLE_FILTER3": "0",
                "CLP_FILTER2_BALANCE_THRESHOLD": "40",
                "CLP_FILTER2_MAX_DIRECTION_SHARE": "0.80",
                "CLP_ENABLE_STABILITY": "0",
                "CLP_ENABLE_OSCILLATION": "0",
                "CLP_ENABLE_FAULT_LINES": "0",
                "CLP_ENABLE_TUNNELS": "0",
                "CLP_ENABLE_SOCIAL_CONFLICTS": "0",
                "CLP_FILTER_WORKERS": "7",
                "CLP_FILTER_CANDIDATE_WORKERS": "4",
                "CLP_MINER_WORKERS": "2",
                "CLP_PHASE3_WORKERS": "3",
            }

        if preset == "normal":
            return {
                "CLP_FRESH_START": "1",
                "CLP_MINERS": "A,B,C",
                "CLP_MAX_STAGE2": "24",
                "CLP_ENABLE_FILTER1": "1",
                "CLP_ENABLE_FILTER3": "0",
                "CLP_FILTER1_DIFF_THRESHOLD": "45",
                "CLP_FILTER1_LEVEL_LIMIT": "2",
                "CLP_FILTER2_BALANCE_THRESHOLD": "38",
                "CLP_FILTER2_MAX_DIRECTION_SHARE": "0.80",
                "CLP_ENABLE_STABILITY": "1",
                "CLP_ENABLE_OSCILLATION": "0",
                "CLP_ENABLE_FAULT_LINES": "1",
                "CLP_ENABLE_TUNNELS": "0",
                "CLP_ENABLE_SOCIAL_CONFLICTS": "0",
                "CLP_STABILITY_REPEATS": "2",
                "CLP_STABILITY_ROUNDS": "5",
                "CLP_FILTER_WORKERS": "7",
                "CLP_FILTER_CANDIDATE_WORKERS": "6",
                "CLP_MINER_WORKERS": "3",
                "CLP_PHASE3_WORKERS": "4",
            }

        if preset == "high-concurrency":
            return {
                "CLP_FRESH_START": "1",
                "CLP_MINERS": "A,B,C,D,E,F",
                "CLP_MAX_STAGE2": "",
                "CLP_ENABLE_FILTER1": "1",
                "CLP_ENABLE_FILTER3": "1",
                "CLP_FILTER1_DIFF_THRESHOLD": "50",
                "CLP_FILTER1_LEVEL_LIMIT": "2",
                "CLP_FILTER2_BALANCE_THRESHOLD": "40",
                "CLP_FILTER2_MAX_DIRECTION_SHARE": "0.82",
                "CLP_FILTER3_REQUIRED_STABLE": "6",
                "CLP_FILTER3_VARIANT_LIMIT": "8",
                "CLP_FILTER3_DISSOLVE_CONFIDENCE": "85",
                "CLP_ENABLE_STABILITY": "1",
                "CLP_ENABLE_OSCILLATION": "1",
                "CLP_ENABLE_FAULT_LINES": "1",
                "CLP_ENABLE_TUNNELS": "1",
                "CLP_ENABLE_SOCIAL_CONFLICTS": "1",
                "CLP_STABILITY_REPEATS": "3",
                "CLP_STABILITY_ROUNDS": "10",
                "CLP_OSCILLATION_ROUNDS": "50",
                "CLP_OSCILLATION_CHUNK_SIZE": "10",
                "CLP_FILTER_WORKERS": "7",
                "CLP_FILTER_CANDIDATE_WORKERS": "10",
                "CLP_MINER_WORKERS": "6",
                "CLP_PHASE3_WORKERS": "8",
            }

        return {
            "CLP_FRESH_START": "0",
            "CLP_MINERS": "A,B,C",
            "CLP_MAX_STAGE2": "18",
            "CLP_ENABLE_FILTER1": "0",
            "CLP_ENABLE_FILTER3": "0",
            "CLP_FILTER2_BALANCE_THRESHOLD": "32",
            "CLP_FILTER2_MAX_DIRECTION_SHARE": "0.78",
            "CLP_ENABLE_STABILITY": "1",
            "CLP_ENABLE_OSCILLATION": "1",
            "CLP_ENABLE_FAULT_LINES": "1",
            "CLP_ENABLE_TUNNELS": "1",
            "CLP_ENABLE_SOCIAL_CONFLICTS": "1",
            "CLP_STABILITY_REPEATS": "3",
            "CLP_STABILITY_ROUNDS": "10",
            "CLP_OSCILLATION_ROUNDS": "50",
            "CLP_OSCILLATION_CHUNK_SIZE": "10",
            "CLP_FILTER_WORKERS": "7",
            "CLP_FILTER_CANDIDATE_WORKERS": "6",
            "CLP_MINER_WORKERS": "3",
            "CLP_PHASE3_WORKERS": "4",
        }

    def start_run(self, preset: str) -> dict:
        with self.lock:
            self._refresh_process_state()
            if self.state.get("status") == "running" and pid_alive(self.state.get("pid")):
                raise RuntimeError("已有网页控制台启动的实验正在运行")

            external_runs = find_external_runs()
            if external_runs:
                raise RuntimeError("检测到终端里已有实验在运行，请先等待它结束或停止它")

            env_file = load_env_file()
            if not env_file.get("CLP_API_KEY") or not env_file.get("CLP_BASE_URL") or not env_file.get("CLP_MODEL"):
                raise RuntimeError("请先在网页里保存 API Key、Base URL 和模型名")

            runtime_env = os.environ.copy()
            runtime_env.update(env_file)
            runtime_env.update(self._preset_env(preset))
            runtime_env.setdefault("PYTHONUNBUFFERED", "1")
            runtime_env.setdefault("CLP_RESUME", "1")
            runtime_env.setdefault("CLP_API_RETRIES", "4")
            runtime_env.setdefault("CLP_TIMEOUT_SECONDS", "120")
            runtime_env.setdefault("CLP_FILTER_WORKERS", "1")
            runtime_env.setdefault("CLP_FILTER_RETRY_PASSES", "4")
            runtime_env.setdefault("CLP_API_LOG", "1")

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            run_id = f"run-{timestamp}"
            run_dir = RUNS_DIR / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            runtime_env["CLP_ARCHIVE_DIR"] = str(run_dir)
            runtime_env["CLP_RUN_ID"] = run_id
            runtime_env["CLP_API_LOG_PATH"] = str(run_dir / "api_diagnostics.jsonl")
            log_path = run_dir / "run.log"
            self.log_handle = open(log_path, "a", encoding="utf-8")

            command = [sys.executable, "-m", "research.run"]
            self.process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                env=runtime_env,
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

            self.state = {
                "status": "running",
                "pid": self.process.pid,
                "started_at": now_iso(),
                "stopped_at": None,
                "exit_code": None,
                "log_path": str(log_path),
                "command": command,
                "preset": preset,
                "run_id": run_id,
                "run_dir": str(run_dir),
            }

            self._append_to_history({
                "id": run_id,
                "started_at": self.state["started_at"],
                "completed_at": None,
                "preset": preset,
                "exit_code": None,
                "total_candidates": 0,
                "selected_for_pipeline": 0,
                "confirmed_count": 0,
                "has_results": False,
            })

            self._save_state()
            return self.get_status()

    def stop_run(self) -> dict:
        with self.lock:
            self._refresh_process_state()
            pid = self.state.get("pid")
            if not pid or not pid_alive(pid):
                self.state["status"] = "idle"
                self._save_state()
                return self.get_status()

            try:
                os.killpg(pid, signal.SIGINT)
            except ProcessLookupError:
                pass

            if self.process is not None:
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass

            self._refresh_process_state()
            return self.get_status()

    def get_log_payload(self, line_count: int = 160) -> dict:
        with self.lock:
            self._refresh_process_state()
            log_path = self.state.get("log_path")
            path = Path(log_path) if log_path else None
            lines = tail_lines(path, line_count=line_count) if path else []
            return {
                "path": str(path) if path else None,
                "lines": lines,
            }

    def _materialize_missing_run_outputs(self, run_dir: Path) -> None:
        checkpoint_path = OUTPUT_DIR / "checkpoint.json"
        if not checkpoint_path.exists():
            return

        archive_checkpoint_path = run_dir / "checkpoint.json"
        if not archive_checkpoint_path.exists():
            try:
                shutil.copy2(checkpoint_path, archive_checkpoint_path)
            except OSError:
                pass

        needs_results = not (OUTPUT_DIR / "results.json").exists() or not (run_dir / "results.json").exists()
        needs_report = not (OUTPUT_DIR / "report.txt").exists() or not (run_dir / "report.txt").exists()
        if not needs_results and not needs_report:
            return

        try:
            from research.checkpoint import load_checkpoint
            from research.output_formatter import generate_data_js, save_results
        except Exception:
            return

        checkpoint = load_checkpoint(str(checkpoint_path))
        if not checkpoint:
            return

        previous_archive_dir = os.environ.get("CLP_ARCHIVE_DIR")
        try:
            os.environ["CLP_ARCHIVE_DIR"] = str(run_dir)
            save_results(
                checkpoint.get("candidates", []),
                rebuild_survivors_from_checkpoint(checkpoint),
                checkpoint.get("confirmed", []),
                fault_lines=checkpoint.get("fault_lines", []),
                tunnel_effects=checkpoint.get("tunnel_effects", []),
                social_conflict_predictions=checkpoint.get("social_conflict_predictions", []),
                key_discoveries=checkpoint.get("key_discoveries", []),
                metadata=checkpoint.get("metadata", {}),
            )
            generate_data_js(checkpoint.get("confirmed", []))
        except Exception:
            return
        finally:
            if previous_archive_dir is None:
                os.environ.pop("CLP_ARCHIVE_DIR", None)
            else:
                os.environ["CLP_ARCHIVE_DIR"] = previous_archive_dir

    def _archive_run_outputs(self, run_id: str) -> None:
        run_dir = RUNS_DIR / run_id
        if not run_dir.exists():
            return

        self._materialize_missing_run_outputs(run_dir)

        output_files = [
            OUTPUT_DIR / "results.json",
            OUTPUT_DIR / "report.txt",
            OUTPUT_DIR / "report.pdf",
            OUTPUT_DIR / "checkpoint.json",
            OUTPUT_DIR / "discovered_system.json",
            OUTPUT_DIR / "api_diagnostics.jsonl",
        ]
        for source in output_files:
            if not source.exists():
                continue
            target = run_dir / source.name
            try:
                shutil.copy2(source, target)
            except OSError:
                continue

    def _append_to_history(self, run_info: dict) -> None:
        history = {"runs": [], "latest_run_id": None}
        if RUN_HISTORY_PATH.exists():
            try:
                history = json.loads(RUN_HISTORY_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                history = {"runs": [], "latest_run_id": None}

        history.setdefault("runs", [])
        history["runs"].insert(0, run_info)
        history["runs"] = history["runs"][:50]
        history["latest_run_id"] = run_info["id"]

        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        RUN_HISTORY_PATH.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _update_history_completed(
        self,
        run_id: str,
        exit_code: int | None,
        completed_at: str,
        total_candidates: int,
        confirmed_count: int,
    ) -> None:
        if not RUN_HISTORY_PATH.exists():
            return
        try:
            history = json.loads(RUN_HISTORY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self._archive_run_outputs(run_id)
        selected_for_pipeline = 0
        checkpoint_data = read_json(OUTPUT_DIR / "checkpoint.json")
        if isinstance(checkpoint_data, dict):
            candidates = checkpoint_data.get("candidates", [])
            selected_for_pipeline = sum(1 for item in candidates if item.get("selected_for_pipeline"))
        for run in history.get("runs", []):
            if run.get("id") == run_id:
                run["completed_at"] = completed_at
                run["exit_code"] = exit_code
                run["total_candidates"] = total_candidates
                run["selected_for_pipeline"] = selected_for_pipeline
                run["confirmed_count"] = confirmed_count
                run["has_results"] = confirmed_count > 0
                break
        RUN_HISTORY_PATH.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_runs(self) -> list:
        if not RUN_HISTORY_PATH.exists():
            return []
        try:
            runs = json.loads(RUN_HISTORY_PATH.read_text(encoding="utf-8")).get("runs", [])
        except (json.JSONDecodeError, OSError):
            return []
        enriched_runs = []
        for run in runs:
            item = dict(run)
            run_dir = RUNS_DIR / str(item.get("id") or "")
            artifacts = get_run_artifacts(run_dir)
            item["artifacts"] = artifacts

            if artifacts["has_checkpoint"]:
                checkpoint_path = run_dir / "checkpoint.json"
                checkpoint_data = read_json(checkpoint_path)
                summary = summarize_checkpoint_payload(checkpoint_data, checkpoint_path)
                item["selected_for_pipeline"] = summary["selected_count"]
                item["confirmed_count"] = summary["confirmed_count"]
                item["has_results"] = artifacts["has_results"] or summary["confirmed_count"] > 0
            elif artifacts["has_results"]:
                results_path = run_dir / "results.json"
                results_data = read_json(results_path)
                if isinstance(results_data, dict):
                    confirmed = results_data.get("confirmed", [])
                    item["confirmed_count"] = len(confirmed)
                    metadata = results_data.get("metadata", {})
                    if isinstance(metadata, dict):
                        item["selected_for_pipeline"] = metadata.get(
                            "selected_for_pipeline",
                            item.get("selected_for_pipeline", 0),
                        )
                item["has_results"] = True

            enriched_runs.append(item)
        return enriched_runs

    def get_run_detail(self, run_id: str) -> dict | None:
        run_dir = RUNS_DIR / run_id
        if not run_dir.exists():
            return None
        run_meta = next((item for item in self.list_runs() if item.get("id") == run_id), None)
        metadata = dict(run_meta or {})
        metadata.pop("artifacts", None)
        result = {
            "metadata": metadata,
            "artifacts": get_run_artifacts(run_dir),
        }
        for fname in ["results.json", "report.txt", "checkpoint.json"]:
            fpath = run_dir / fname
            if fpath.exists():
                key = fname.replace(".json", "").replace(".txt", "")
                try:
                    if fname.endswith(".json"):
                        result[key] = json.loads(fpath.read_text(encoding="utf-8"))
                    else:
                        result[key] = fpath.read_text(encoding="utf-8")
                except (json.JSONDecodeError, OSError):
                    pass
        checkpoint_data = result.get("checkpoint")
        if isinstance(checkpoint_data, dict):
            result["summary"] = summarize_checkpoint_payload(checkpoint_data, run_dir / "checkpoint.json")
            if not result.get("results"):
                derived_results = checkpoint_to_results_payload(checkpoint_data)
                if derived_results:
                    result["results"] = derived_results

        if result["artifacts"].get("has_log"):
            result["log_excerpt"] = tail_lines(run_dir / "run.log", line_count=36)

        return result

