#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _adapter_module():
    return _load_module(
        Path(__file__).resolve().parents[1] / "lib" / "operator_health_watchdog_operator_adapters.py",
        "operator_health_watchdog_operator_adapters_test",
    )


def _watchdog_module():
    return _load_module(
        Path(__file__).resolve().parents[1] / "lib" / "operator_health_watchdog.py",
        "operator_health_watchdog_tool_test",
    )


def test_prune_adapter_preserves_future_blocks_and_marks_expired_idempotency_keys():
    module = _adapter_module()
    fixed_now = dt.datetime(2026, 6, 5, 0, 0, 0, tzinfo=dt.timezone.utc)
    fake_flow_control = SimpleNamespace(
        prune_expired_operator_config_blocks=lambda: {
            "ok": True,
            "checked": 3,
            "pruned": [
                {
                    "operator_id": "op-expired",
                    "runtime_state": "cooldown",
                    "expires_at": "2026-06-01T00:00:00Z",
                },
                {
                    "operator_id": "op-future",
                    "runtime_state": "cooldown",
                    "expires_at": "2099-01-01T00:00:00Z",
                },
            ],
            "kept": [
                {
                    "operator_id": "op-future-kept",
                    "runtime_state": "cooldown",
                    "expires_at": "2099-06-01T00:00:00Z",
                },
            ],
        }
    )

    payload = module.prune_expired_operator_config_blocks(now=fixed_now, flow_control_module=fake_flow_control)

    assert payload["ok"] is True
    assert payload["summary"]["pruned"] == 1
    assert payload["summary"]["kept"] == 2
    assert payload["pruned"][0]["idempotency_key"] == "op-expired|2026-06-01T00:00:00Z"
    future_kept = next(item for item in payload["kept"] if item["operator_id"] == "op-future")
    assert future_kept["source"] == "future_expiry_retained"
    assert future_kept["retry_at"] == "2099-01-01T00:00:00Z"
    preserved_kept = next(item for item in payload["kept"] if item["operator_id"] == "op-future-kept")
    assert preserved_kept["source"] == "preserved_by_flow_control"
    assert "|" in preserved_kept["idempotency_key"]


def test_refresh_snapshot_failure_is_degraded_and_has_reason():
    module = _adapter_module()
    bad_refresh = SimpleNamespace(refresh_snapshot=lambda apply=False: {"ok": False, "reason": "provider unavailable"})

    payload = module.refresh_snapshot(apply=False, quota_refresh_module=bad_refresh)
    assert payload["ok"] is False
    assert payload["degraded"] is True
    assert payload["degradation_summary"]["degraded"] is True
    assert payload["degradation_summary"]["reason"] == "provider unavailable"

    def _raise(*, apply=False):
        raise RuntimeError("quota command timeout")

    hard_payload = module.refresh_snapshot(apply=True, quota_refresh_module=SimpleNamespace(refresh_snapshot=_raise))
    assert hard_payload["ok"] is False
    assert hard_payload["degraded"] is True
    assert "RuntimeError" in hard_payload["reason"]

    assert module.summarize_quota_refresh_failure(payload) == "quota_refresh_degraded:provider unavailable"


def test_run_watchdog_writes_report_when_quota_snapshot_fails(monkeypatch, tmp_path):
    adapter = _adapter_module()
    watchdog = _watchdog_module()

    fixed_now = dt.datetime(2026, 6, 5, 0, 0, 0, tzinfo=dt.timezone.utc)
    fake_flow_control = SimpleNamespace(
        prune_expired_operator_config_blocks=lambda: {
            "ok": True,
            "checked": 1,
            "pruned": [],
            "kept": [
                {
                    "operator_id": "op-future",
                    "runtime_state": "cooldown",
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ],
        }
    )
    monkeypatch.setattr(adapter, "_load_flow_control_module", lambda: fake_flow_control)
    monkeypatch.setattr(adapter, "_now", lambda: fixed_now)

    def failing_refresh_snapshot(*, apply=False):
        raise RuntimeError("quota provider not reachable")

    fake_quota = SimpleNamespace(refresh_snapshot=failing_refresh_snapshot)

    class FakePM:
        PM_INBOX_DIR = tmp_path / "pm-inbox"
        TRANSIENT_OPERATOR_FAILURE_RE = __import__("re").compile(r"quota|cooldown|auth")

        def __init__(self):
            self.PM_INBOX_DIR.mkdir(parents=True, exist_ok=True)

        def cmd_reconcile(self, args):
            print('{"ok": true, "summary": {"reconcile_count": 0}}')
            return 0

    fake_pm = FakePM()
    payload = watchdog.run_watchdog(
        apply=True,
        max_age_minutes=30,
        lock_path=tmp_path / "lock",
        latest_path=tmp_path / "latest.json",
        history_path=tmp_path / "history.jsonl",
        pm_dispatch_module=fake_pm,
        prune_module=adapter,
        quota_refresh_module=fake_quota,
    )

    phases = {phase["phase"]: phase for phase in payload["phases"]}
    assert payload["ok"] is False
    assert "lock_acquire" in phases
    assert phases["refresh_capacity_snapshot"]["status"] in {"warn", "error"}
    assert any("quota" in str(item).lower() for item in payload["blockers"])
    assert "latest" not in payload
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "history.jsonl").exists()
