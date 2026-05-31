#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tools_graph_scheduler_delegates_to_lib_canonical(tmp_path) -> None:
    tools_path = Path(__file__).resolve().parents[2] / "tools" / "graph_scheduler.py"
    lib_path = Path(__file__).resolve().parents[2] / "lib" / "graph_scheduler.py"

    tool_mod = _load_module(tools_path, "graph_scheduler_tool_wrapper_test")
    lib_mod = _load_module(lib_path, "graph_scheduler_lib_canonical_test")

    graph_path = tmp_path / "sample.task_graph.json"
    payload = {"sprint_id": "sprint-demo", "nodes": []}
    graph_path.write_text(json.dumps(payload), encoding="utf-8")

    assert tool_mod._MODULE_PATH == lib_path  # noqa: SLF001 - wrapper contract
    assert tool_mod.load_graph(graph_path) == lib_mod.load_graph(graph_path)
    assert tool_mod._sprint_id_for_graph(payload, graph_path) == lib_mod._sprint_id_for_graph(payload, graph_path)
