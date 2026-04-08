import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decision.pipeline import DecisionManager


def main() -> None:
    manager = DecisionManager(None)
    manager._persist = lambda decision: None  # avoid touching the real session store during the smoke test

    decision = manager._base_job("我应该留在这里还是离开？", "pro")
    decision_id = decision["decision_id"]
    manager.jobs[decision_id] = decision
    manager.latest_job_id = decision_id

    waiting_session = {
        "session_id": "sess-test",
        "recommendation": "先等结构判断收束",
        "recheck": {"status": "running"},
    }
    manager._maybe_start_simulator(decision_id, waiting_session)
    manager._maybe_start_simulator(decision_id, waiting_session)

    snapshot = manager.get_status(decision_id)["decision"] or {}
    logs = snapshot.get("logs") or []
    waiting_log_count = sum("Engine A 正在二次检测" in line for line in logs)

    assert waiting_log_count == 1, logs
    assert snapshot.get("meta", {}).get("simulator_started") is False
    assert snapshot.get("meta", {}).get("simulator_ready") is False
    assert snapshot.get("meta", {}).get("simulator_waiting_recheck") is True
    assert snapshot.get("status_text") == "第二幕建议已形成，等待二次检测完成"

    ready_session = {
        "session_id": "sess-test",
        "recommendation": "先从最可逆的那一步开始",
        "phase": "c1_reevaluation",
        "recheck": {
            "status": "completed",
            "job": {"result": {"is_lagrange_point": False}},
        },
    }
    manager._maybe_start_simulator(decision_id, ready_session)
    manager._maybe_start_simulator(decision_id, ready_session)

    ready_snapshot = manager.get_status(decision_id)["decision"] or {}
    ready_logs = ready_snapshot.get("logs") or []
    ready_log_count = sum("可手动启动第三幕未来模拟" in line for line in ready_logs)

    assert ready_log_count == 1, ready_logs
    assert ready_snapshot.get("meta", {}).get("simulator_started") is False
    assert ready_snapshot.get("meta", {}).get("simulator_ready") is True
    assert ready_snapshot.get("meta", {}).get("simulator_waiting_recheck") is None
    assert ready_snapshot.get("status_text") == "第二幕建议已形成，可手动启动第三幕未来模拟"

    print({
        "decision_id": decision_id,
        "waiting_log_count": waiting_log_count,
        "ready_log_count": ready_log_count,
        "status_text": ready_snapshot.get("status_text"),
    })


if __name__ == "__main__":
    main()
