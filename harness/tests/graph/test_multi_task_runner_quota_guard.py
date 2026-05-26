from __future__ import annotations

import json
import sys
from pathlib import Path


HARNESS_LIB = Path(__file__).resolve().parents[2] / "lib"
sys.path.insert(0, str(HARNESS_LIB))

import multi_task_runner  # noqa: E402


def test_quota_guard_ignores_recovered_fallback_hit(monkeypatch, tmp_path):
    harness = tmp_path / "harness"
    run_dir = harness / "run" / "multi-task"
    task_dir = run_dir / "mt-quota-N1"
    task_dir.mkdir(parents=True)
    (task_dir / "output.log").write_text("You've hit your org's monthly usage limit\n", encoding="utf-8")
    graph_path = tmp_path / "sprint-quota.task_graph.json"
    (task_dir / "status.json").write_text(
        json.dumps(
            {
                "id": "mt-quota-N1",
                "status": "failed",
                "profile": "gemini-builder",
                "graph": str(graph_path),
                "node_id": "N1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-quota",
                "nodes": [
                    {
                        "id": "N1",
                        "status": "active",
                        "quota_failure_task_id": "mt-quota-N1",
                        "preferred_profile": "knowledge-extractor",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(multi_task_runner, "RUN_DIR", run_dir)

    assert multi_task_runner.quota_guard(3600)["ok"] is True


def test_quota_guard_ignores_late_hit_after_node_already_recovered(monkeypatch, tmp_path):
    harness = tmp_path / "harness"
    run_dir = harness / "run" / "multi-task"
    task_dir = run_dir / "mt-quota-late-N1"
    task_dir.mkdir(parents=True)
    (task_dir / "output.log").write_text("You've hit your org's monthly usage limit\n", encoding="utf-8")
    graph_path = tmp_path / "sprint-quota.task_graph.json"
    (task_dir / "status.json").write_text(
        json.dumps(
            {
                "id": "mt-quota-late-N1",
                "status": "failed",
                "profile": "gemini-builder",
                "graph": str(graph_path),
                "node_id": "N1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps(
            {
                "sprint_id": "sprint-quota",
                "nodes": [
                    {
                        "id": "N1",
                        "status": "pending",
                        "quota_failure_reason": "quota_exhausted",
                        "quota_failure_task_id": "mt-quota-earlier-N1",
                        "preferred_profile": "knowledge-extractor",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(multi_task_runner, "RUN_DIR", run_dir)

    assert multi_task_runner.quota_guard(3600)["ok"] is True


def test_quota_guard_ignores_hit_for_already_passed_node(monkeypatch, tmp_path):
    harness = tmp_path / "harness"
    run_dir = harness / "run" / "multi-task"
    task_dir = run_dir / "mt-quota-passed-N1"
    task_dir.mkdir(parents=True)
    (task_dir / "output.log").write_text("Antigravity quota exhausted\n", encoding="utf-8")
    graph_path = tmp_path / "sprint-quota.task_graph.json"
    (task_dir / "status.json").write_text(
        json.dumps(
            {
                "id": "mt-quota-passed-N1",
                "status": "failed",
                "profile": "antigravity-multimodal",
                "graph": str(graph_path),
                "node_id": "N1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps({"sprint_id": "sprint-quota", "nodes": [{"id": "N1", "status": "passed"}]}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(multi_task_runner, "RUN_DIR", run_dir)

    assert multi_task_runner.quota_guard(3600)["ok"] is True


def test_quota_recovered_preferred_profile_is_not_overridden_by_operator(monkeypatch):
    monkeypatch.setattr(
        multi_task_runner,
        "load_profiles",
        lambda: {
            "profiles": {
                "knowledge-extractor": {"role": "builder", "backend": "command", "model": "local"},
                "gemini-builder": {"role": "builder", "backend": "command", "model": "gemini-3.5-flash"},
            },
            "defaults": {"profile": "gemini-builder"},
        },
    )
    monkeypatch.setattr(multi_task_runner, "capability_for_profile", lambda profile, include_probe=True: {"status": "ok", "provider": "local"})
    monkeypatch.setattr(
        multi_task_runner,
        "select_operator",
        lambda node, profile: (
            {
                "operator_id": "mini-antigravity-gemini35-flash-image",
                "profile": "gemini-builder",
                "role": "builder",
                "backend": "command",
                "model": "gemini-3.5-flash",
            },
            "",
        ),
    )
    node = {
        "id": "N1",
        "role": "builder",
        "preferred_profile": "knowledge-extractor",
        "quota_failure_reason": "quota_exhausted",
    }

    selected = multi_task_runner.select_profile(node)

    assert selected["name"] == "knowledge-extractor"
    assert selected["model"] == "local"
    assert selected.get("operator_id") is None
