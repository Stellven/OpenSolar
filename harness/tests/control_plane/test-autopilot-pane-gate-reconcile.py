#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


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
    role_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: role_calls.append((s, t)) or (True, {"role": "planner"}))
    monkeypatch.setattr(mod, "wake_sid", lambda s: False)
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

    assert role_calls == [(sid, "ready_for_planner")]
    assert actions[0]["dispatched_from_queue"] is True
    assert actions[0]["role_pool_dispatch"]["role"] == "planner"
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
    role_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: role_calls.append((s, t)) or (True, {"role": "planner"}))
    monkeypatch.setattr(mod, "wake_sid", lambda s: False)

    actions = mod.apply_findings([finding], dispatch=True, state=state, cooldown=0)

    assert role_calls == [(sid, "ready_for_planner")]
    assert actions[0]["dispatched"] is True
    assert actions[0]["role_pool_dispatch"]["role"] == "planner"


def test_role_pool_handoffs_do_not_share_fixed_target_cooldown(monkeypatch) -> None:
    findings = [
        {"sid": "sprint-a", "type": "ready_for_planner", "target": "solar-harness:0.1", "message": "a"},
        {"sid": "sprint-b", "type": "ready_for_planner", "target": "solar-harness:0.1", "message": "b"},
    ]
    state: dict = {"actions": {}, "target_actions": {}}
    monkeypatch.setattr(mod, "should_act", lambda state, f, cooldown: True)
    monkeypatch.setattr(mod, "target_recently_dispatched", lambda state, target, cooldown: True)
    monkeypatch.setattr(mod, "pane_gate", lambda target, sid: (False, "pane_leased", {}))
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: True)
    monkeypatch.setattr(mod, "clear_current_prompt", lambda target: None)
    monkeypatch.setattr(mod, "save_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "load_json", lambda path: {
        "sprint_id": "x",
        "status": "drafting",
        "phase": "prd_ready",
        "handoff_to": "planner",
    })
    monkeypatch.setattr(mod, "mark_action", lambda *args, **kwargs: None)
    role_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: role_calls.append((s, t)) or (True, {"role": "planner"}))

    actions = mod.apply_findings(findings, dispatch=True, state=state, cooldown=300)

    assert role_calls == [
        ("sprint-a", "ready_for_planner"),
        ("sprint-b", "ready_for_planner"),
    ]
    assert [item["dispatched"] for item in actions] == [True, True]


def test_epic_filter_keeps_target_epic_and_child_sprints(tmp_path, monkeypatch) -> None:
    epic_id = "epic-target"
    target_sid = "sprint-target"
    other_sid = "sprint-other"
    sprints_dir = tmp_path / "sprints"
    sprints_dir.mkdir()
    monkeypatch.setattr(mod, "SPRINTS", sprints_dir)
    (sprints_dir / f"{target_sid}.status.json").write_text(json.dumps({
        "sprint_id": target_sid,
        "epic_id": epic_id,
    }) + "\n")
    (sprints_dir / f"{other_sid}.status.json").write_text(json.dumps({
        "sprint_id": other_sid,
        "epic_id": "epic-other",
    }) + "\n")

    findings = [
        {"sid": "epic-target", "type": "epic_ready_children"},
        {"sid": target_sid, "type": "ready_for_planner"},
        {"sid": other_sid, "type": "ready_for_planner"},
        {"sid": "", "type": "model_registry_doctor_failed"},
    ]

    filtered = mod.filter_findings_by_epic(findings, epic_id)

    assert [item["sid"] for item in filtered] == ["epic-target", target_sid]


def test_retry_queue_epic_filter_preserves_unrelated_items(tmp_path, monkeypatch) -> None:
    epic_id = "epic-target"
    target_sid = "sprint-target"
    other_sid = "sprint-other"
    monkeypatch.setattr(mod, "QUEUE", tmp_path / "autopilot-queue.jsonl")
    monkeypatch.setattr(mod, "SPRINTS", tmp_path / "sprints")
    mod.SPRINTS.mkdir()
    (mod.SPRINTS / f"{target_sid}.status.json").write_text(json.dumps({
        "sprint_id": target_sid,
        "status": "active",
        "epic_id": epic_id,
    }) + "\n")
    (mod.SPRINTS / f"{other_sid}.status.json").write_text(json.dumps({
        "sprint_id": other_sid,
        "status": "active",
        "epic_id": "epic-other",
    }) + "\n")
    mod.QUEUE.write_text(
        json.dumps({"sid": target_sid, "type": "ready_for_planner", "target": "solar-harness:0.1", "created_at_epoch": 9999999999}) + "\n"
        + json.dumps({"sid": other_sid, "type": "ready_for_planner", "target": "solar-harness:0.1", "created_at_epoch": 9999999999}) + "\n"
    )
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "target_recently_dispatched", lambda state, target, cooldown: False)
    monkeypatch.setattr(mod, "pane_gate", lambda target, sid: (True, "ok", {}))
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: False)
    monkeypatch.setattr(mod, "clear_current_prompt", lambda target: None)
    monkeypatch.setattr(mod, "mark_action", lambda *args, **kwargs: None)
    role_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: role_calls.append((s, t)) or (True, {"role": "planner"}))

    actions = mod.retry_queue({"actions": {}, "target_actions": {}}, dispatch=True, cooldown=0, epic_filter=epic_id)

    assert role_calls == [(target_sid, "ready_for_planner")]
    assert actions == [{
        "sid": target_sid,
        "action": "ready_for_planner",
        "dispatched_from_queue": True,
        "target": "solar-harness:0.1",
        "role_pool_dispatch": {"role": "planner"},
    }]
    assert [item["sid"] for item in mod.load_queue()] == [other_sid]


def test_scan_once_epic_filter_applies_before_action_budget(tmp_path, monkeypatch) -> None:
    epic_id = "epic-target"
    target_a = "sprint-target-a"
    target_b = "sprint-target-b"
    other_sids = [f"sprint-other-{idx}" for idx in range(7)]
    sprints_dir = tmp_path / "sprints"
    sprints_dir.mkdir()
    monkeypatch.setattr(mod, "SPRINTS", sprints_dir)
    monkeypatch.setattr(mod, "QUEUE", tmp_path / "autopilot-queue.jsonl")
    monkeypatch.setenv("SOLAR_AUTOPILOT_MAX_ACTIONS", "6")
    for sid in [target_a, target_b]:
        (sprints_dir / f"{sid}.status.json").write_text(json.dumps({
            "sprint_id": sid,
            "status": "active",
            "phase": "prd_ready",
            "handoff_to": "planner",
            "epic_id": epic_id,
        }) + "\n")
    for sid in other_sids:
        (sprints_dir / f"{sid}.status.json").write_text(json.dumps({
            "sprint_id": sid,
            "status": "active",
            "phase": "prd_ready",
            "handoff_to": "planner",
            "epic_id": "epic-other",
        }) + "\n")

    target_findings = [{"sid": sid, "type": "ready_for_planner", "target": "solar-harness:0.1", "message": sid} for sid in [target_a, target_b]]
    unrelated_findings = [{"sid": sid, "type": "ready_for_planner", "target": "solar-harness:0.1", "message": sid} for sid in other_sids]
    monkeypatch.setattr(mod, "inspect_epics", lambda: [])
    monkeypatch.setattr(mod, "inspect_epic_child_state_drift", lambda: [])
    monkeypatch.setattr(mod, "inspect_sprints", lambda: unrelated_findings + target_findings)
    monkeypatch.setattr(mod, "inspect_deepresearch_quality_gates", lambda: [])
    monkeypatch.setattr(mod, "inspect_panes", lambda state, stall_seconds: [])
    monkeypatch.setattr(mod, "inspect_knowledge_context", lambda state: [])
    monkeypatch.setattr(mod, "inspect_model_registry", lambda state: [])
    monkeypatch.setattr(mod, "reconcile_pm_inbox", lambda: {})
    monkeypatch.setattr(mod, "update_idle_pane_titles", lambda state: [])
    monkeypatch.setattr(mod, "save_state", lambda state: None)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "should_act", lambda state, f, cooldown: True)
    monkeypatch.setattr(mod, "target_recently_dispatched", lambda state, target, cooldown: False)
    monkeypatch.setattr(mod, "save_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "mark_action", lambda *args, **kwargs: None)
    role_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: role_calls.append((s, t)) or (True, {"role": "planner"}))

    payload = mod.scan_once(
        SimpleNamespace(apply=True, dispatch=True, cooldown=0, loop=False, stall_seconds=300, epic=epic_id),
        {"actions": {}, "target_actions": {}},
    )

    assert payload["findings_before_epic_filter"] == 9
    assert [item["sid"] for item in payload["findings"]] == [target_a, target_b]
    assert role_calls == [(target_a, "ready_for_planner"), (target_b, "ready_for_planner")]
    assert not [item for item in payload["actions"] if item.get("skipped") == "autopilot_action_budget"]


def test_ready_for_planner_role_pool_failure_queues_without_wake(monkeypatch) -> None:
    sid = "sprint-planner-no-capacity"
    finding = {
        "sid": sid,
        "type": "ready_for_planner",
        "target": "solar-harness:0.1",
        "message": "planner dispatch",
        "severity": "info",
    }
    state: dict = {"actions": {}, "target_actions": {}}
    queued: list[tuple[dict, str, dict]] = []
    monkeypatch.setattr(mod, "should_act", lambda state, f, cooldown: True)
    monkeypatch.setattr(mod, "target_recently_dispatched", lambda state, target, cooldown: False)
    monkeypatch.setattr(mod, "pane_gate", lambda target, sid: (False, "pane_leased", {}))
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
    monkeypatch.setattr(mod, "enqueue_action", lambda f, reason, detail=None: queued.append((f, reason, detail or {})))
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: (False, {"role": "planner", "stderr": "no planner"}))
    wake_calls: list[str] = []
    monkeypatch.setattr(mod, "wake_sid", lambda s: wake_calls.append(s) or True)

    actions = mod.apply_findings([finding], dispatch=True, state=state, cooldown=0)

    assert wake_calls == []
    assert queued[0][1] == "role_pool_unavailable"
    assert actions[0]["queued"] is True
    assert actions[0]["reason"] == "role_pool_unavailable"


def test_ready_for_planner_does_not_downgrade_active_epic_child(monkeypatch) -> None:
    sid = "sprint-epic-child"
    saved: list[dict] = []
    monkeypatch.setattr(mod, "should_act", lambda state, f, cooldown: True)
    monkeypatch.setattr(mod, "target_recently_dispatched", lambda state, target, cooldown: False)
    monkeypatch.setattr(mod, "pane_gate", lambda target, sid: (True, "ok", {}))
    monkeypatch.setattr(mod, "pane_is_busy", lambda target: False)
    monkeypatch.setattr(mod, "clear_current_prompt", lambda target: None)
    monkeypatch.setattr(mod, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        mod,
        "load_json",
        lambda path: {
            "sprint_id": sid,
            "status": "active",
            "phase": "prd_ready",
            "handoff_to": "planner",
            "target_role": "planner",
            "epic_id": "epic-demo",
            "dependency_policy": "activated_by_epic_dag",
            "history": [],
        },
    )
    monkeypatch.setattr(mod, "save_json", lambda path, data: saved.append(dict(data)))
    monkeypatch.setattr(mod, "mark_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(mod, "dispatch_role_handoff", lambda s, t: (True, {"role": "planner"}))

    actions = mod.apply_findings(
        [{"sid": sid, "type": "ready_for_planner", "target": "solar-harness:0.1", "message": "planner dispatch"}],
        dispatch=True,
        state={"actions": {}, "target_actions": {}},
        cooldown=0,
    )

    assert actions[0]["dispatched"] is True
    assert saved[0]["status"] == "active"
    assert saved[0]["phase"] == "prd_ready"
    assert saved[0]["handoff_to"] == "planner"


def test_role_pool_unavailable_cache_expires(monkeypatch) -> None:
    mod.ROLE_POOL_UNAVAILABLE_CACHE.clear()
    monkeypatch.setattr(mod, "ROLE_POOL_UNAVAILABLE_CACHE_TTL_SEC", 1)
    calls: list[int] = []

    class _Proc:
        def __init__(self, rc: int, stderr: str):
            self.returncode = rc
            self.stdout = ""
            self.stderr = stderr

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: calls.append(1) or _Proc(1, "ERROR: 没有可用算子 (no_dispatchable_operator_for_role: planner)\n"),
    )

    ok1, detail1 = mod.dispatch_role_handoff("sprint-a", "ready_for_planner")
    ok2, detail2 = mod.dispatch_role_handoff("sprint-a", "ready_for_planner")
    assert ok1 is False and ok2 is False
    assert detail2.get("cached") is True
    assert len(calls) == 1

    original_time = mod.time.time
    monkeypatch.setattr(mod.time, "time", lambda: original_time() + 5)
    ok3, detail3 = mod.dispatch_role_handoff("sprint-a", "ready_for_planner")
    assert ok3 is False
    assert detail3.get("cached") is not True
    assert len(calls) == 2
