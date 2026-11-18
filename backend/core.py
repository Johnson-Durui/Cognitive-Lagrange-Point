#!/usr/bin/env python3
"""Core runtime and Engine A / Engine B facade for the web backend."""

from __future__ import annotations

from research.engine_b.runtime import (
    configure_detection_manager as configure_engine_b_detection,
    get_engine_b_status_for_session,
    hydrate_recheck_from_detection as _hydrate_recheck_from_detection,
    reset_engine_b,
    start_engine_b_session,
    start_simulator,
    submit_engine_b_answer,
    submit_sim_answer,
)

from .detection import DetectionManager
from .runtime import RuntimeManager

RUNTIME = RuntimeManager()
DETECTION = DetectionManager()
configure_engine_b_detection(DETECTION)

hydrate_recheck_from_detection = _hydrate_recheck_from_detection

__all__ = [
    "DETECTION",
    "RUNTIME",
    "DetectionManager",
    "RuntimeManager",
    "get_engine_b_status_for_session",
    "hydrate_recheck_from_detection",
    "reset_engine_b",
    "start_engine_b_session",
    "start_simulator",
    "submit_engine_b_answer",
    "submit_sim_answer",
]
