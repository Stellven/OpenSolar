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


def test_successful_handoff_marks_graph_reviewing(tmp_path):
    script = _runner_script_text(tmp_path)

    assert '--status reviewing' in script
    assert 'write_status completed "$rc"' in script


def test_review_required_node_uses_same_reviewing_terminal_state(tmp_path):
    script = _runner_script_text(tmp_path, review_required=True)

    assert '--status reviewing' in script
    assert 'write_status completed "$rc"' in script

def test_late_failure_does_not_overwrite_passed_graph_node(tmp_path):
    script = _runner_script_text(tmp_path)

    assert "mark_graph_failed_unless_passed" in script
    assert "late_failure_ignored_graph_already_passed=true" in script
    assert "write_status failed_aligned" in script




def test_runner_rejects_stale_handoff_from_previous_run(tmp_path):
    script = _runner_script_text(tmp_path)

    assert 'RUN_STARTED_MARKER="$TASK_DIR/run.started"' in script
    assert ': > "$RUN_STARTED_MARKER"' in script
    assert '"$HANDOFF" -nt "$RUN_STARTED_MARKER"' in script
    assert 'stale handoff predates current run' in script
    assert 'write_status failed_stale_handoff 66' in script


def test_failed_stale_handoff_is_terminal_status():
    assert "failed_stale_handoff" in multi_task_runner.TERMINAL_TASK_STATUSES

def test_quota_guard_fallback_bypass_requires_explicit_env():
    text = Path(multi_task_runner.__file__).read_text(encoding="utf-8")

    assert 'SOLAR_MULTI_TASK_BYPASS_QUOTA_GUARD_FOR_FALLBACK' in text
    assert 'recent_quota_or_rate_limit_bypassed_for_fallback' in text
