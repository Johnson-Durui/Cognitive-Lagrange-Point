"""Checkpoint summary and discovered-payload helpers."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "research" / "output"


def _read_json(path: Path) -> dict | list | None:
  if not path.exists():
    return None
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None


def _now_iso() -> str:
  return datetime.now().astimezone().isoformat(timespec="seconds")


def _get_field(value: Any, key: str, default: Any = None) -> Any:
  if isinstance(value, dict):
    return value.get(key, default)
  return getattr(value, key, default)


def summarize_checkpoint_payload(data: dict | None, path: Path | None = None) -> dict:
  checkpoint_path = path or (OUTPUT_DIR / "checkpoint.json")
  if not isinstance(data, dict):
    return {
      "exists": False,
      "path": str(checkpoint_path),
      "updated_at": None,
      "selected_count": 0,
      "filter2_survivors": 0,
      "confirmed_count": 0,
      "fault_line_count": 0,
      "tunnel_effect_count": 0,
      "social_prediction_count": 0,
      "confirmed_points": [],
      "key_discoveries": [],
    }

  candidates = data.get("candidates", [])
  selected = [item for item in candidates if _get_field(item, "selected_for_pipeline", False)]
  confirmed = data.get("confirmed", [])
  fault_lines = data.get("fault_lines", [])
  tunnel_effects = data.get("tunnel_effects", [])
  social_predictions = data.get("social_conflict_predictions", [])

  confirmed_points = []
  for item in confirmed:
    confirmed_points.append({
      "id": _get_field(item, "id"),
      "question_text": _get_field(item, "question_text", ""),
      "source_candidate": _get_field(item, "source_candidate"),
      "balance_precision": _get_field(item, "balance_precision"),
      "stability_type": _get_field(item, "stability_type"),
      "oscillation_type": _get_field(item, "oscillation_type"),
      "oscillation_period": _get_field(item, "oscillation_period"),
      "fault_lines": _get_field(item, "fault_lines", []),
      "tunnel_connections": _get_field(item, "tunnel_connections", []),
      "stability_run_count": len(_get_field(item, "stability_runs", [])),
      "oscillation_round_count": len(_get_field(item, "oscillation_data", [])),
    })

  return {
    "exists": True,
    "path": str(checkpoint_path),
    "updated_at": data.get("updated_at"),
    "selected_count": len(selected),
    "filter2_survivors": sum(1 for item in selected if _get_field(item, "passed_filter_2", None) is True),
    "confirmed_count": len(confirmed),
    "fault_line_count": len(fault_lines),
    "tunnel_effect_count": len(tunnel_effects),
    "social_prediction_count": len(social_predictions),
    "confirmed_points": confirmed_points,
    "key_discoveries": data.get("key_discoveries", []),
  }


def summarize_checkpoint() -> dict:
  checkpoint_path = OUTPUT_DIR / "checkpoint.json"
  return summarize_checkpoint_payload(_read_json(checkpoint_path), checkpoint_path)


def checkpoint_to_results_payload(checkpoint_data: dict | None) -> dict | None:
  if not isinstance(checkpoint_data, dict):
    return None

  summary = summarize_checkpoint_payload(checkpoint_data)
  metadata = checkpoint_data.get("metadata")
  if not isinstance(metadata, dict):
    metadata = {}

  return {
    "confirmed": checkpoint_data.get("confirmed", []),
    "fault_lines": checkpoint_data.get("fault_lines", []),
    "tunnel_effects": checkpoint_data.get("tunnel_effects", []),
    "social_conflict_predictions": checkpoint_data.get("social_conflict_predictions", []),
    "metadata": {
      **metadata,
      "selected_for_pipeline": summary["selected_count"],
      "filter2_survivors": summary["filter2_survivors"],
      "confirmed_count": summary["confirmed_count"],
    },
  }


def get_run_artifacts(run_dir: Path) -> dict:
  return {
    "run_dir": str(run_dir),
    "has_log": (run_dir / "run.log").exists(),
    "has_results": (run_dir / "results.json").exists(),
    "has_checkpoint": (run_dir / "checkpoint.json").exists(),
    "has_report_txt": (run_dir / "report.txt").exists(),
    "has_report_pdf": (run_dir / "report.pdf").exists(),
    "has_api_diagnostics": (run_dir / "api_diagnostics.jsonl").exists(),
  }


def _candidate_survives_pipeline(candidate: Any, enable_filter1: bool, enable_filter3: bool) -> bool:
  if not _get_field(candidate, "selected_for_pipeline", False):
    return False
  if enable_filter1 and _get_field(candidate, "passed_filter_1", None) is not True:
    return False
  if _get_field(candidate, "passed_filter_2", None) is not True:
    return False
  if enable_filter3 and _get_field(candidate, "passed_filter_3", None) is not True:
    return False
  return True


def rebuild_survivors_from_checkpoint(checkpoint: dict) -> list:
  metadata = checkpoint.get("metadata", {}) if isinstance(checkpoint, dict) else {}
  enable_filter1 = bool(metadata.get("enable_filter1", False))
  enable_filter3 = bool(metadata.get("enable_filter3", False))
  candidates = checkpoint.get("candidates", []) if isinstance(checkpoint, dict) else []
  return [
    candidate for candidate in candidates
    if _candidate_survives_pipeline(candidate, enable_filter1, enable_filter3)
  ]


def generate_discovered_payload_from_checkpoint(checkpoint_data: dict | None) -> dict:
  if not checkpoint_data or not checkpoint_data.get("exists"):
    return {"systems": [], "generated_at": _now_iso(), "checkpoint_updated_at": None}

  confirmed = checkpoint_data.get("confirmed_points", [])
  if not confirmed:
    return {
      "systems": [],
      "generated_at": _now_iso(),
      "checkpoint_updated_at": checkpoint_data.get("updated_at"),
    }

  fault_line_map: dict[str, list[int]] = {}
  for index, clp in enumerate(confirmed):
    for fault_line in (clp.get("fault_lines") or []):
      fault_line_map.setdefault(fault_line, []).append(index)

  fault_line_connections = []
  for fault_line_name, node_indices in fault_line_map.items():
    if len(node_indices) >= 2:
      fault_line_connections.append({
        "fault_line": fault_line_name,
        "nodes": node_indices,
      })

  tunnel_connections = []
  for index, clp in enumerate(confirmed):
    for tunnel_to in (clp.get("tunnel_connections") or []):
      for target_index, other in enumerate(confirmed):
        if other.get("id") == tunnel_to:
          tunnel_connections.append({"from": index, "to": target_index})
          break

  nodes_js = []
  for index, clp in enumerate(confirmed):
    angle = (2 * math.pi * index) / max(len(confirmed), 1)
    question_text = clp.get("question_text", "")
    name = question_text[:15].rstrip("，。、？") if len(question_text) > 15 else question_text
    subtitle = f"CLP #{clp.get('id', '?')}"
    short_question = question_text if len(question_text) <= 80 else f"{question_text[:80]}..."

    body = question_text
    if clp.get("balance_precision") is not None:
      body += f"\n\n平衡精度：{clp['balance_precision']}%"
    if clp.get("stability_type"):
      body += f"\n\n稳定性：{clp['stability_type']}"
    if clp.get("oscillation_type"):
      body += f"\n\n振荡类型：{clp['oscillation_type']}"
      if clp.get("oscillation_period"):
        body += f"\n振荡周期：约 {clp['oscillation_period']} 轮"
    if clp.get("fault_lines"):
      body += f"\n\n所在断层线：{'、'.join(clp['fault_lines'])}"
    if clp.get("tunnel_connections"):
      body += f"\n\n隧道连接：{'、'.join(clp['tunnel_connections'])}"

    nodes_js.append({
      "name": name,
      "subtitle": subtitle,
      "angle": round(angle, 2),
      "distance": 170 + (index % 3) * 15,
      "orbitSpeed": 0.05 + (index % 4) * 0.01,
      "tension": ["正方", "反方"],
      "question": short_question,
      "body": body,
      "node_index": index,
      "clp_data": clp,
    })

  return {
    "systems": [{
      "id": "discovered",
      "name": "新发现的认知拉格朗日点",
      "nameEn": "Discovered Lagrange Points",
      "color": [255, 107, 107],
      "position": {"x": 0, "y": 0},
      "nodes": nodes_js,
      "fault_line_connections": fault_line_connections,
      "tunnel_connections": tunnel_connections,
    }],
    "generated_at": _now_iso(),
    "checkpoint_updated_at": checkpoint_data.get("updated_at"),
  }
