#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "solar-autopilot-monitor.py"
spec = importlib.util.spec_from_file_location("solar_autopilot_monitor", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["solar_autopilot_monitor"] = mod
spec.loader.exec_module(mod)


def _utc_after(seconds: int) -> str:
    return (
        dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_pane_gate_clears_stale_assignment_without_graph_or_lease(tmp_path, monkeypatch) -> None:
    assignments = tmp_path / ".pane-assignments"
    assignments.write_text("solar-harness-lab:0.1=stale-sprint:1779000000\n")
    monkeypatch.setattr(mod, "PANE_ASSIGNMENTS", assignments)
    monkeypatch.setattr(mod, "PANE_LEASE_DIR", tmp_path / "pane-leases")
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "assigned_graph_node_for_pane", lambda target: {})
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: False)

    allowed, reason, detail = mod.pane_gate("solar-harness-lab:0.1", "new-sprint")

    assert allowed is True
    assert reason == "ok"
    assert detail["assignment"] == {}
    assert "assignment_cleared" in detail["reconciled"]
    assert mod.pane_assignment("solar-harness-lab:0.1") == {}


def test_pane_gate_clears_stale_live_lease_without_graph_node(tmp_path, monkeypatch) -> None:
    lease_dir = tmp_path / "pane-leases"
    lease_dir.mkdir(parents=True)
    lease_path = lease_dir / f"{mod.pane_safe('solar-harness-lab:0.2')}.json"
    lease_path.write_text(json.dumps({
        "pane": "solar-harness-lab:0.2",
        "sid": "stale-sprint",
        "dispatch_id": "d-1",
        "expires_at": _utc_after(600),
        "ttl_sec": 600,
    }) + "\n")
    monkeypatch.setattr(mod, "PANE_ASSIGNMENTS", tmp_path / ".pane-assignments")
    monkeypatch.setattr(mod, "PANE_LEASE_DIR", lease_dir)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "assigned_graph_node_for_pane", lambda target: {})
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: False)

    allowed, reason, detail = mod.pane_gate("solar-harness-lab:0.2", "fresh-sprint")

    assert allowed is True
    assert reason == "ok"
    assert detail["lease"] == {}
    assert "lease_cleared" in detail["reconciled"]
    assert lease_path.exists() is False


def test_pane_gate_keeps_active_graph_claims_even_when_pane_is_idle(tmp_path, monkeypatch) -> None:
    assignments = tmp_path / ".pane-assignments"
    assignments.write_text("solar-harness-lab:0.3=active-sprint:1779000000\n")
    lease_dir = tmp_path / "pane-leases"
    lease_dir.mkdir(parents=True)
    lease_path = lease_dir / f"{mod.pane_safe('solar-harness-lab:0.3')}.json"
    lease_path.write_text(json.dumps({
        "pane": "solar-harness-lab:0.3",
        "sid": "active-sprint",
        "dispatch_id": "d-2",
        "expires_at": _utc_after(600),
        "ttl_sec": 600,
    }) + "\n")
    monkeypatch.setattr(mod, "PANE_ASSIGNMENTS", assignments)
    monkeypatch.setattr(mod, "PANE_LEASE_DIR", lease_dir)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        mod,
        "assigned_graph_node_for_pane",
        lambda target: {"sid": "active-sprint", "node_id": "S2", "status": "dispatched"},
    )
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: False)

    allowed, reason, detail = mod.pane_gate("solar-harness-lab:0.3", "fresh-sprint")

    assert allowed is False
    assert reason == "pane_leased"
    assert detail["graph_node"]["node_id"] == "S2"
    assert detail["lease"]["sid"] == "active-sprint"
    assert detail["assignment"]["sid"] == "active-sprint"
    assert lease_path.exists() is True


def test_reconcile_preserves_lease_when_graph_claim_is_recoverable_from_runtime_evidence(tmp_path, monkeypatch) -> None:
    lease_dir = tmp_path / "pane-leases"
    lease_dir.mkdir(parents=True)
    lease_path = lease_dir / f"{mod.pane_safe('solar-harness-lab:0.4')}.json"
    lease_path.write_text(json.dumps({
        "pane": "solar-harness-lab:0.4",
        "sid": "recoverable-sprint",
        "dispatch_id": "dispatch-ua-1",
        "expires_at": _utc_after(600),
        "ttl_sec": 600,
    }) + "\n")
    graph_path = tmp_path / "sprints" / "recoverable-sprint.task_graph.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(json.dumps({
        "sprint_id": "recoverable-sprint",
        "nodes": [
            {
                "id": "S1",
                "status": "dispatched",
                "assigned_to": "solar-harness-lab:0.4",
                "dispatch_id": "dispatch-ua-1",
            }
        ],
    }) + "\n")
    monkeypatch.setattr(mod, "PANE_ASSIGNMENTS", tmp_path / ".pane-assignments")
    monkeypatch.setattr(mod, "PANE_LEASE_DIR", lease_dir)
    monkeypatch.setattr(mod, "SPRINTS", graph_path.parent)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "active_statuses", lambda: [])
    monkeypatch.setattr(mod, "load_graph", lambda path: json.loads(Path(path).read_text()))
    monkeypatch.setattr(mod, "node_status", lambda graph, node_id: graph["nodes"][0]["status"])
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: False)

    allowed, reason, detail = mod.pane_gate("solar-harness-lab:0.4", "fresh-sprint")

    assert allowed is False
    assert reason == "pane_leased"
    assert detail["graph_node"]["sid"] == "recoverable-sprint"
    assert detail["graph_node"]["node_id"] == "S1"
    assert detail["graph_node"]["recovered_from_runtime_evidence"] is True
    assert lease_path.exists() is True


def test_inspect_sprints_releases_blocked_dependency_waiting_status_when_route_is_ready(tmp_path, monkeypatch) -> None:
    sprints = tmp_path / "sprints"
    sprints.mkdir(parents=True)
    sid = "sprint-unblock-ready"
    status_path = sprints / f"{sid}.status.json"
    status_path.write_text(json.dumps({
        "sprint_id": sid,
        "status": "blocked",
        "phase": "external_dependency_waiting",
        "handoff_to": "",
        "target_role": "",
    }) + "\n")
    monkeypatch.setattr(mod, "SPRINTS", sprints)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "epic_child_dependency_ready", lambda sid: (True, []))
    monkeypatch.setattr(
        mod,
        "workflow_guard_route",
        lambda sid: {
            "ok": True,
            "violations": [],
            "route_role": "planner",
            "stage": "prd_ready",
            "reason": "pm_prd_ready",
        },
    )

    mod.inspect_sprints()
    payload = json.loads(status_path.read_text())

    assert payload["status"] == "drafting"
    assert payload["phase"] == "prd_ready"
    assert payload["handoff_to"] == "planner"
    assert payload["target_role"] == "planner"


def test_builder_handoff_prefers_idle_lab_builder_when_primary_is_occupied(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "discover_worker_panes",
        lambda: ["solar-harness:0.2", "solar-harness-lab:0.0", "solar-harness-lab:0.1"],
    )
    monkeypatch.setattr(mod, "pane_title_matches_role", lambda pane, role, title="": role == "builder")
    monkeypatch.setattr(
        mod,
        "pane_gate",
        lambda pane, sid: (
            (False, "pane_leased", {}) if pane == "solar-harness:0.2" else (True, "ok", {})
        ),
    )
    monkeypatch.setattr(mod, "pane_is_busy", lambda pane: False)

    assert mod.pane_target_for_handoff("builder_main") == "solar-harness-lab:0.0"


def test_builder_queue_item_reroutes_to_idle_lab_builder(monkeypatch) -> None:
    monkeypatch.setattr(mod, "pane_target_for_handoff", lambda handoff: "solar-harness-lab:0.1")
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    item = {
        "type": "ready_for_builder",
        "target": "solar-harness:0.2",
    }

    target = mod.maybe_reroute_builder_target(item, "sprint-demo")

    assert target == "solar-harness-lab:0.1"
    assert item["target"] == "solar-harness-lab:0.1"


def test_planner_handoff_prefers_idle_planner_pool_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "discover_role_pool",
        lambda role: [
            {"pane": "solar-harness:0.1"},
            {"pane": "solar-harness-lab:0.4"},
        ] if role == "planner" else [],
    )
    monkeypatch.setattr(
        mod,
        "pane_gate",
        lambda pane, sid: (
            (False, "pane_leased", {}) if pane == "solar-harness:0.1" else (True, "ok", {})
        ),
    )
    monkeypatch.setattr(mod, "pane_is_busy", lambda pane: False)

    assert mod.pane_target_for_handoff("planner") == "solar-harness-lab:0.4"


def test_evaluator_handoff_prefers_idle_evaluator_pool_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "discover_role_pool",
        lambda role: [
            {"pane": "solar-harness:0.3"},
            {"pane": "solar-harness-lab:0.1"},
        ] if role == "evaluator" else [],
    )
    monkeypatch.setattr(
        mod,
        "pane_gate",
        lambda pane, sid: (
            (False, "pane_leased", {}) if pane == "solar-harness:0.3" else (True, "ok", {})
        ),
    )
    monkeypatch.setattr(mod, "pane_is_busy", lambda pane: False)

    assert mod.pane_target_for_handoff("evaluator") == "solar-harness-lab:0.1"


def test_ready_for_planner_queue_bypasses_fixed_pane_busy(tmp_path, monkeypatch) -> None:
    sid = "sprint-planner-demo"
    monkeypatch.setattr(mod, "QUEUE", tmp_path / "autopilot-queue.jsonl")
    monkeypatch.setattr(mod, "SPRINTS", tmp_path / "sprints")
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "pane_gate", lambda target, sid: (True, "ok", {}))
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: True)
    monkeypatch.setattr(mod, "clear_current_prompt", lambda target: None)
    wake_calls: list[str] = []
    monkeypatch.setattr(mod, "wake_sid", lambda s: wake_calls.append(s) or True)
    mod.SPRINTS.mkdir(parents=True)
    (mod.SPRINTS / f"{sid}.status.json").write_text(json.dumps({
        "sprint_id": sid,
        "status": "drafting",
        "phase": "prd_ready",
        "handoff_to": "planner",
    }) + "\n")
    mod.QUEUE.write_text(json.dumps({
        "sid": sid,
        "type": "ready_for_planner",
        "target": "solar-harness:0.1",
        "created_at_epoch": 9999999999,
    }) + "\n")

    actions = mod.retry_queue({"actions": {}, "target_actions": {}}, dispatch=True, cooldown=0)

    assert wake_calls == [sid]
    assert actions[0]["dispatched_from_queue"] is True
    assert mod.load_queue() == []


def test_ready_for_planner_finding_bypasses_fixed_pane_busy(monkeypatch) -> None:
    sid = "sprint-planner-demo"
    finding = {
        "sid": sid,
        "type": "ready_for_planner",
        "target": "solar-harness:0.1",
        "message": "planner dispatch",
        "severity": "info",
    }
    state: dict = {"actions": {}, "target_actions": {}}
    monkeypatch.setattr(mod, "should_act", lambda state, f, cooldown: True)
    monkeypatch.setattr(mod, "target_recently_dispatched", lambda state, target, cooldown: False)
    monkeypatch.setattr(mod, "pane_gate", lambda target, sid: (True, "ok", {}))
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: True)
    monkeypatch.setattr(mod, "clear_current_prompt", lambda target: None)
    monkeypatch.setattr(mod, "save_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "load_json", lambda path: {
        "sprint_id": sid,
        "status": "drafting",
        "phase": "prd_ready",
        "handoff_to": "planner",
    })
    monkeypatch.setattr(mod, "mark_action", lambda *args, **kwargs: None)
    wake_calls: list[str] = []
    monkeypatch.setattr(mod, "wake_sid", lambda s: wake_calls.append(s) or True)

    actions = mod.apply_findings([finding], dispatch=True, state=state, cooldown=0)

    assert wake_calls == [sid]
    assert actions[0]["dispatched"] is True
