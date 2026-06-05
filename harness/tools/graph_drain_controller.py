#!/usr/bin/env python3
"""CLI facade for the graph drain controller."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

CORE_MODULE_PATH = Path(__file__).resolve().parents[1] / "lib" / "graph_drain_controller.py"


def _load_core() -> Any:
    lib_dir = str(CORE_MODULE_PATH.parent)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    spec = importlib.util.spec_from_file_location("solar_graph_drain_controller_core", CORE_MODULE_PATH)
    if not spec or not spec.loader:
        raise FileNotFoundError(f"core module not found: {CORE_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def run_graph_drain(**kwargs: Any) -> dict[str, Any]:
    return _load_core().run_graph_drain(**kwargs)


def main() -> int:
    return int(_load_core().main())


if __name__ == "__main__":
    raise SystemExit(main())
