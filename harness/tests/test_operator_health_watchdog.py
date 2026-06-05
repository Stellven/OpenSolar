#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


HARNESS_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = HARNESS_ROOT / "tools"
LIB_DIR = HARNESS_ROOT / "lib"


def _load_watchdog():
    spec = importlib.util.spec_from_file_location("operator_health_watchdog", TOOLS_DIR / "operator_health_watchdog.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_core_watchdog():
    spec = importlib.util.spec_from_file_location("operator_health_watchdog_core", LIB_DIR / "operator_health_watchdog.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_watchdog_dry_run_does_not_prune_or_apply_reconcile(monkeypatch, tmp_path):
    watchdog = _load_watchdog()
    monkeypatch.setattr(watchdog, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(watchdog, "LATEST_REPORT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(watchdog, "HISTORY_PATH", tmp_path / "history.jsonl")
    calls: list[tuple[str, object]] = []

    class FakePM:
        def _prune_expired_operator_blocks(self):
            calls.append(("prune", None))
            return {"ok": True, "pruned": [{"operator_id": "op"}], "kept": []}

        def cmd_reconcile(self, args):
            calls.append(("reconcile", args.apply))
            print('{"ok": true, "summary": {"keep_active": 1}}')
            return 0

    class FakeQuota:
        def refresh_snapshot(self, *, apply=False):
            calls.append(("quota", apply))
            return {
                "ok": True,
                "operators_total": 2,
                "operators_usable": 1,
                "operators_hard_blocked": 1,
                "recommended_level": "high",
                "backlog": 7,
                "groups": {},
            }

    monkeypatch.setattr(watchdog, "_load_tool", lambda name: FakePM() if name == "pm_dispatch" else FakeQuota())

    payload = watchdog.run_watchdog(apply=False, max_age_minutes=30)

    assert payload["ok"] is True
    assert payload["applied"] is False
    assert ("prune", None) not in calls
    assert ("reconcile", False) in calls
    assert ("quota", False) in calls
    assert payload["steps"][0]["result"]["reason"] == "dry_run"


def test_watchdog_apply_prunes_and_applies_reconcile(monkeypatch, tmp_path):
    watchdog = _load_watchdog()
    monkeypatch.setattr(watchdog, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(watchdog, "LATEST_REPORT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(watchdog, "HISTORY_PATH", tmp_path / "history.jsonl")
    calls: list[tuple[str, object]] = []

    class FakePM:
        def _prune_expired_operator_blocks(self):
            calls.append(("prune", None))
            return {"ok": True, "pruned": [{"operator_id": "op-a"}], "kept": [{"operator_id": "op-b"}]}

        def cmd_reconcile(self, args):
            calls.append(("reconcile", args.apply))
            print('{"ok": true, "summary": {"complete": 2, "fail_missing_pm_result": 1}}')
            return 0

    class FakeQuota:
        def refresh_snapshot(self, *, apply=False):
            calls.append(("quota", apply))
            return {
                "ok": True,
                "operators_total": 3,
                "operators_usable": 2,
                "operators_hard_blocked": 1,
                "recommended_level": "burst",
                "backlog": 9,
                "groups": {"claude-opus": {"hard_blocked": 1}},
            }

    monkeypatch.setattr(watchdog, "_load_tool", lambda name: FakePM() if name == "pm_dispatch" else FakeQuota())

    payload = watchdog.run_watchdog(apply=True, max_age_minutes=15)

    assert payload["ok"] is True
    assert payload["applied"] is True
    assert ("prune", None) in calls
    assert ("reconcile", True) in calls
    assert ("quota", True) in calls
    assert payload["summary"]["pruned_blocks"] == 1
    assert payload["summary"]["kept_blocks"] == 1
    assert payload["summary"]["hard_blocked_groups"] == ["claude-opus"]


def test_watchdog_prefers_operator_and_lease_adapters(monkeypatch, tmp_path):
    watchdog = _load_core_watchdog()
    monkeypatch.setattr(watchdog, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(watchdog, "LATEST_REPORT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(watchdog, "HISTORY_PATH", tmp_path / "history.jsonl")
    calls: list[tuple[str, object]] = []

    class FakePM:
        PM_INBOX_DIR = tmp_path / "pm-inbox"

        def __init__(self):
            self.PM_INBOX_DIR.mkdir(parents=True, exist_ok=True)
            (self.PM_INBOX_DIR / "pm-task.json").write_text(
                '{"task_id":"pm-task","status":"completed","sprint_id":"s","node_id":"n"}',
                encoding="utf-8",
            )

        def cmd_reconcile(self, args):
            print('{"ok": true, "summary": {"reconcile_count": 0}}')
            return 0

    class FakeOperatorAdapter:
        def prune_expired_operator_config_blocks(self):
            calls.append(("operator_prune", True))
            return {"ok": True, "pruned": [{"operator_id": "op-a", "runtime_state": "cooldown"}], "kept": []}

        def refresh_snapshot(self, *, apply=False):
            calls.append(("operator_quota", apply))
            return {
                "ok": True,
                "operators_total": 1,
                "operators_usable": 1,
                "operators_hard_blocked": 0,
                "recommended_level": "normal",
                "backlog": 0,
                "groups": {},
            }

    class FakeGraphAdapter:
        def release_builder_assignment_on_transient_failure(self, record):
            return {"ok": False, "released": False, "reason": "not_failed"}

        def release_evaluator_assignment_on_transient_failure(self, record):
            return {"ok": False, "released": False, "reason": "not_failed"}

    class FakeLeaseAdapter:
        def reconcile_stale_leases(self, *, runtime_module=None, apply=True):
            calls.append(("lease_reconcile", apply))
            return {
                "ok": True,
                "actions": [
                    {
                        "action_type": "release_stale_lease",
                        "target": "op-a",
                        "status": "applied",
                        "idempotency_key": "lease|op-a",
                    }
                ],
                "skipped": [],
                "summary": {"released": 1},
            }

        def repair_status_projection(self, record, *, apply=True):
            calls.append(("projection_repair", record.get("task_id")))
            return {
                "ok": True,
                "actions": [
                    {
                        "action_type": "mark_builder_reviewing",
                        "target": record.get("task_id", "pm-task"),
                        "status": "applied",
                        "idempotency_key": "projection|pm-task",
                    }
                ],
                "skipped": [],
                "summary": {"applied": 1},
            }

    class FakeRuntime:
        pass

    def fake_load_tool(name):
        if name == "pm_dispatch":
            return FakePM()
        if name == "operator_health_watchdog_operator_adapters":
            return FakeOperatorAdapter()
        if name == "operator_health_watchdog_graph_adapters":
            return FakeGraphAdapter()
        if name == "operator_health_watchdog_lease_adapters":
            return FakeLeaseAdapter()
        if name == "operator_runtime":
            return FakeRuntime()
        raise FileNotFoundError(name)

    monkeypatch.setattr(watchdog, "_load_tool", fake_load_tool)

    payload = watchdog.run_watchdog(apply=True, max_age_minutes=15)
    phases = {phase["phase"]: phase for phase in payload["phases"]}

    assert payload["ok"] is True
    assert ("operator_prune", True) in calls
    assert ("operator_quota", True) in calls
    assert ("lease_reconcile", True) in calls
    assert ("projection_repair", "pm-task") in calls
    assert phases["repair_status_projection"]["status"] == "ok"
    assert payload["counters"]["stale_leases_released"] == 1


def test_watchdog_safe_drain_uses_pm_drain_dry_run_by_default(monkeypatch, tmp_path):
    watchdog = _load_core_watchdog()
    monkeypatch.setattr(watchdog, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(watchdog, "LATEST_REPORT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(watchdog, "HISTORY_PATH", tmp_path / "history.jsonl")
    calls: list[tuple[str, object]] = []

    class FakePM:
        PM_INBOX_DIR = tmp_path / "pm-inbox"

        def __init__(self):
            self.PM_INBOX_DIR.mkdir(parents=True, exist_ok=True)

        def cmd_reconcile(self, args):
            print('{"ok": true, "summary": {}}')
            return 0

        def cmd_drain_builder_ready(self, args):
            calls.append(("drain", {"dry_run": args.dry_run, "max_items": args.max_items, "json": args.json}))
            print(
                '{"ok": false, "dry_run": true, "latent_builder_ready": 1, '
                '"submitted": [], "marked": [], "skipped": [{"reason": "dry_run"}]}'
            )
            return 1

    class FakeQuota:
        def refresh_snapshot(self, *, apply=False):
            return {
                "ok": True,
                "operators_total": 2,
                "operators_usable": 1,
                "operators_hard_blocked": 0,
                "recommended_level": "normal",
                "backlog": 1,
                "groups": {},
            }

    def fake_load_tool(name):
        if name == "pm_dispatch":
            return FakePM()
        if name == "operator_runtime":
            return SimpleNamespace()
        if name == "quota_refresh":
            return FakeQuota()
        raise FileNotFoundError(name)

    monkeypatch.setattr(watchdog, "_load_tool", fake_load_tool)
    monkeypatch.delenv("SOLAR_OHW_ENABLE_DRAIN_APPLY", raising=False)

    payload = watchdog.run_watchdog(apply=True, max_age_minutes=15)
    phases = {phase["phase"]: phase for phase in payload["phases"]}

    assert calls == [("drain", {"dry_run": True, "max_items": 3, "json": True})]
    assert phases["drain_if_capacity_available"]["status"] == "ok"
    assert phases["drain_if_capacity_available"]["counters"]["dry_run"] == 1
    assert payload["counters"]["drain_submitted"] == 0
