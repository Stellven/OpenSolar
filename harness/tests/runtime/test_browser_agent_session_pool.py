from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from browser_agent_session_pool import BrowserAgentSessionPool


def test_pool_ensure_and_acquire_release():
    with tempfile.TemporaryDirectory() as td:
        pool = BrowserAgentSessionPool(Path(td), service="chatgpt", pool_size=2)
        slots = pool.ensure_slots()
        assert len(slots) == 2
        assert slots[0]["slot_id"] == "slot-01"
        assert slots[1]["slot_id"] == "slot-02"

        first = pool.acquire_slot(task_id="task-1", request_lineage="lineage-a", request_dir="/tmp/task-1")
        second = pool.acquire_slot(task_id="task-2", request_lineage="lineage-b", request_dir="/tmp/task-2")
        assert first["slot_id"] != second["slot_id"]
        assert first["state"] == "running"
        assert second["state"] == "running"

        released = pool.release_slot(first["slot_id"], keep_warm=True)
        assert released["state"] == "idle"
        assert released["warm"] is True
        assert released["assigned_task_id"] == ""
