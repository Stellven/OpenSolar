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
