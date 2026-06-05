#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


HARNESS_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = HARNESS_ROOT / "tools"


def _load_watchdog():
    spec = importlib.util.spec_from_file_location("operator_health_watchdog", TOOLS_DIR / "operator_health_watchdog.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_watchdog_dry_run_does_not_prune_or_apply_reconcile(monkeypatch):
    watchdog = _load_watchdog()
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


def test_watchdog_apply_prunes_and_applies_reconcile(monkeypatch):
    watchdog = _load_watchdog()
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
