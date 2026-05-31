from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "lib" / "pane_role_pool.py"
spec = importlib.util.spec_from_file_location("pane_role_pool_under_test", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["pane_role_pool_under_test"] = mod
spec.loader.exec_module(mod)


def test_discover_role_pool_uses_registry_roles_for_multi_task(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "physical-operators.json"
    registry_path.write_text(json.dumps({
        "version": 1,
        "operators": {
            "mini-claude-opus-planner": {
                "role": "planner",
                "roles": ["planner"],
                "enabled": True,
                "available": True,
                "pane": "solar-harness-multi-task:*",
            },
            "mini-antigravity-gemini31-pro": {
                "role": "planner",
                "roles": ["planner", "evaluator"],
                "enabled": True,
                "available": True,
                "pane": "solar-harness-multi-task:*",
            },
        },
    }) + "\n")

    monkeypatch.setattr(mod, "PHYSICAL_OPERATORS_PATH", registry_path)
    monkeypatch.setattr(
        mod,
        "list_tmux_panes",
        lambda: [
            {"pane": "solar-harness:0.1", "title": "Planner 规划者 | 模型:Opus"},
            {"pane": "solar-harness-multi-task:0.0", "title": "solar-harness-multi-task:0.0 | 状态:working/ready_for_planner"},
        ],
    )

    planners = mod.discover_role_pool("planner")
    evaluators = mod.discover_role_pool("evaluator")

    assert [item["pane"] for item in planners][:2] == [
        "solar-harness:0.1",
        "solar-harness-multi-task:0.0",
    ]
    assert planners[1]["host_role"] == "planner"
    assert "planner" in planners[1]["registry_roles"]
    assert [item["pane"] for item in evaluators] == ["solar-harness-multi-task:0.0"]
