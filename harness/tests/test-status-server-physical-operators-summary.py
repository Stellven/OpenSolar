#!/usr/bin/env python3
"""Regression tests for full physical-operator fleet exposure in status-server."""

import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "lib" / "symphony" / "status-server.py"
spec = importlib.util.spec_from_file_location("status_server", MODULE)
status_server = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(status_server)


def test_physical_operator_summary_returns_full_fleet_and_prioritizes_idle(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    config_dir = harness / "config"
    config_dir.mkdir(parents=True)
    registry = {
        "version": 1,
        "operators": {
            "op-disabled": {
                "role": "builder",
                "backend": "command",
                "enabled": False,
                "available": False,
            },
            "op-idle": {
                "role": "planner",
                "backend": "claude-cli",
                "enabled": True,
                "available": True,
            },
            "op-busy": {
                "role": "evaluator",
                "backend": "claude-cli",
                "enabled": True,
                "available": True,
            },
        },
    }
    (config_dir / "physical-operators.json").write_text(json.dumps(registry), encoding="utf-8")

    lease_dir = harness / "run" / "operator-leases"
    lease_dir.mkdir(parents=True)
    (lease_dir / "op-busy.json").write_text(
        json.dumps({"state": "leased", "expires_at": "2099-01-01T00:00:00Z"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(status_server, "HARNESS_DIR", harness)

    summary = status_server._physical_operator_summary(limit=2)

    assert summary["count"] == 3
    assert len(summary["items"]) == 3
    assert summary["items"][0]["operator_id"] == "op-idle"
    assert summary["items"][-1]["operator_id"] == "op-disabled"


def test_physical_operator_summary_exposes_planner_evaluator_role_pools(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    config_dir = harness / "config"
    config_dir.mkdir(parents=True)
    registry = {
        "version": 1,
        "operators": {
            "planner-cooldown": {
                "role": "planner",
                "roles": ["planner"],
                "backend": "claude-cli",
                "pane": "solar-harness:0.1",
                "enabled": True,
                "available": True,
                "quota_guard_state": "cooldown",
                "quota_refresh_at": "2099-01-01T00:00:00Z",
            },
            "planner-evaluator-auth": {
                "role": "planner",
                "roles": ["planner", "evaluator"],
                "backend": "antigravity",
                "pane": "solar-harness-multi-task:*",
                "enabled": True,
                "available": True,
                "quota_guard_state": "auth_expired",
                "quota_refresh_at": "2099-01-02T00:00:00Z",
            },
            "evaluator-idle": {
                "role": "evaluator",
                "roles": ["evaluator"],
                "backend": "claude-cli",
                "pane": "",
                "enabled": True,
                "available": True,
            },
        },
    }
    (config_dir / "physical-operators.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(status_server, "HARNESS_DIR", harness)

    summary = status_server._physical_operator_summary(limit=4)

    planner = summary["role_pools"]["planner"]
    evaluator = summary["role_pools"]["evaluator"]
    assert planner["total"] == 2
    assert planner["dispatchable"] == 0
    assert planner["status"] == "blocked"
    assert planner["counts"]["cooldown"] == 1
    assert planner["counts"]["auth_expired"] == 1
    assert planner["block_counts"]["true_quota_cooldown"] == 1
    assert planner["block_counts"]["auth_expired"] == 1
    assert planner["capacity_mix"]["dedicated"] == 1
    assert planner["capacity_mix"]["elastic"] == 1
    assert planner["next_available_at"] == "2099-01-01T00:00:00Z"
    assert evaluator["total"] == 2
    assert evaluator["dispatchable"] == 1
    assert evaluator["status"] == "ok"
    assert evaluator["capacity_mix"]["elastic"] == 1
    assert evaluator["capacity_mix"]["headless"] == 1


def test_physical_operator_summary_separates_stale_local_cooldown(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    config_dir = harness / "config"
    status_dir = harness / "run" / "operator-status"
    config_dir.mkdir(parents=True)
    status_dir.mkdir(parents=True)
    registry = {
        "version": 1,
        "operators": {
            "planner-stale": {
                "role": "planner",
                "roles": ["planner"],
                "backend": "claude-cli",
                "enabled": True,
                "available": True,
            },
        },
    }
    (config_dir / "physical-operators.json").write_text(json.dumps(registry), encoding="utf-8")
    (status_dir / "planner-stale.json").write_text(
        json.dumps({"runtime_state": "cooldown", "expires_at": "2099-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(status_server, "HARNESS_DIR", harness)

    summary = status_server._physical_operator_summary(limit=4)
    planner = summary["role_pools"]["planner"]

    assert planner["counts"]["cooldown"] == 1
    assert planner["block_counts"]["stale_local_cooldown"] == 1
    assert planner["items"][0]["block_detail"] == "stale_local_cooldown"


def test_pane_overlay_detail_splits_live_overlay_from_stale_scrollback():
    live_tail = "\n".join([
        "Some task output",
        "Do you want to proceed?",
        "  1. Yes",
    ])
    stale_tail = "\n".join([
        "Do you want to proceed?",
        "  1. Yes",
        "❯ ",
        "⏵ auto mode on",
    ])

    live = status_server._pane_overlay_detail(live_tail)
    stale = status_server._pane_overlay_detail(stale_tail)

    assert live["state"] == "pane_overlay_blocked"
    assert live["type"] == "proceed"
    assert status_server._runtime_from_tail(live_tail) == "pane_overlay_blocked"
    assert stale["state"] == "stale_scrollback_ignored"
    assert status_server._runtime_from_tail(stale_tail) == "idle"


def test_warning_breakdown_keeps_operator_and_pane_causes_separate():
    physical = {
        "role_pools": {
            "planner": {
                "block_counts": {
                    "true_quota_cooldown": 1,
                    "stale_local_cooldown": 1,
                    "output_token_limit": 1,
                    "cooldown_unclassified": 0,
                }
            }
        }
    }
    main = {
        "panes": [
            {
                "target": "solar-harness:0.1",
                "role": "Planner",
                "pane_overlay": {"state": "pane_overlay_blocked", "type": "permission", "detail": "approval required"},
            },
            {
                "target": "solar-harness:0.3",
                "role": "Evaluator",
                "pane_overlay": {"state": "stale_scrollback_ignored", "type": "survey", "detail": "Do you want to proceed?"},
            },
        ]
    }

    breakdown = status_server._pane_warning_breakdown(
        main,
        {"panes": []},
        {"pane_overlay_blocked": 1, "stale_scrollback_ignored": 2},
        physical,
    )

    assert breakdown["operator_cooldown"] == 3
    assert breakdown["operator_cooldown_breakdown"]["true_quota_cooldown"] == 1
    assert breakdown["pane_overlay_blocked"] == 2
    assert breakdown["stale_scrollback_ignored"] == 3
    assert breakdown["overlay_samples"][0]["target"] == "solar-harness:0.1"


def test_headless_pane_status_ignores_stale_blocked_title_when_tail_is_idle():
    tail = "\n".join([
        "old permissions prompt text",
        "────────────────────────",
        "❯ ",
        "────────────────────────",
        "  ⏵⏵ accept edits on (shift+tab to cycle)",
    ])

    assert status_server._headless_pane_status(
        "bash",
        "Builder | 状态:working/pane_permissions_prompt_blocked:old",
        tail,
    ) == "idle"


def test_headless_pane_status_uses_live_spinner_tail_as_running():
    tail = "\n".join([
        "✻ Cooking… (21s · ↓ 182 tokens · still thinking)",
        "────────────────────────",
        "❯ ",
        "────────────────────────",
        "  ⏵⏵ accept edits on (shift+tab to cycle) · esc to interrupt",
    ])

    assert status_server._headless_pane_status("bash", "Builder | stale title", tail) == "running"
