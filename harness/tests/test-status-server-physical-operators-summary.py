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
