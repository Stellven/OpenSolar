from __future__ import annotations

import sys
from pathlib import Path


HARNESS_LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(HARNESS_LIB))

import multi_task_runner  # noqa: E402


def _payload(tmp_path: Path, *, review_required: bool = False) -> dict:
    graph = tmp_path / "sprint-test.task_graph.json"
    graph.write_text('{"sprint_id":"sprint-test","nodes":[]}\n', encoding="utf-8")
    return {
        "graph": str(graph),
        "handoff": str(tmp_path / "sprint-test.N1-handoff.md"),
        "node_id": "N1",
        "sprint_id": "sprint-test",
        "role": "builder",
        "profile": "builder",
        "backend": "command",
        "model": "sonnet",
        "provider": "anthropic",
        "capability_status": "ok",
        "approval_mode": "yolo",
        "review_required": review_required,
    }


def _runner_script_text(tmp_path: Path, *, review_required: bool = False) -> str:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    runner = multi_task_runner.runner_script(
        task_dir,
        _payload(tmp_path, review_required=review_required),
    )
    return runner.read_text(encoding="utf-8")


def test_successful_handoff_defaults_to_passed(tmp_path):
    script = _runner_script_text(tmp_path)

    assert 'success_status="${SOLAR_MULTI_TASK_SUCCESS_STATUS:-passed}"' in script
    assert '--status "$success_status"' in script
    assert "REVIEW_REQUIRED=0" in script


def test_review_required_node_can_still_stop_at_reviewing(tmp_path):
    script = _runner_script_text(tmp_path, review_required=True)

    assert "REVIEW_REQUIRED=1" in script
    assert 'success_status="reviewing"' in script
