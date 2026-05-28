#!/usr/bin/env python3
"""Initialize pane-hygiene.json from tmux list-panes discovery (per data_models.md §1.5).

Does NOT write to real run/pane-hygiene.json when --dry-run is set (default for tests).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Optional

sys.path.insert(0, ".")

from lib.pane_hygiene_registry import PaneHygieneRegistry, PaneState

PANE_ROLE_MAP: dict[str, str] = {
    "solar-harness:0.0": "planner",
    "solar-harness:0.1": "builder",
    "solar-harness:0.2": "evaluator",
    "solar-harness:0.3": "architect",
    "solar-harness-lab:0.0": "builder",
    "solar-harness-lab:0.1": "builder",
    "solar-harness-lab:0.2": "builder",
    "solar-harness-lab:0.3": "builder",
}

DEFAULT_MODEL_MAP: dict[str, str] = {
    "solar-harness:0.0": "anthropic-opus",
    "solar-harness:0.1": "glm-5.1",
    "solar-harness:0.2": "glm-5.1",
    "solar-harness:0.3": "anthropic-opus",
    "solar-harness-lab:0.0": "glm-5.1",
    "solar-harness-lab:0.1": "glm-5.1",
    "solar-harness-lab:0.2": "glm-5.1",
    "solar-harness-lab:0.3": "anthropic-sonnet",
}


def discover_panes(tmux_binary: str = "tmux") -> list[str]:
    try:
        result = subprocess.run(
            [tmux_binary, "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def init_registry(
    output_path: str,
    pane_ids: Optional[list[str]] = None,
    *,
    tmux_binary: str = "tmux",
) -> dict:
    if pane_ids is None:
        pane_ids = discover_panes(tmux_binary)
    registry = PaneHygieneRegistry(output_path)
    registered = []
    for pid in pane_ids:
        role = PANE_ROLE_MAP.get(pid, "builder")
        model = DEFAULT_MODEL_MAP.get(pid)
        try:
            registry.register_pane(pid, role, initial_state=PaneState.clean, model=model)
            registered.append(pid)
        except ValueError:
            pass
    return {"registered": registered, "count": len(registered)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize pane-hygiene.json")
    parser.add_argument("--output", default=".solar/harness/run/pane-hygiene.json")
    parser.add_argument("--tmux", default="tmux")
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    if args.dry_run:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            result = init_registry(f.name, tmux_binary=args.tmux)
        print(json.dumps(result, indent=2))
        return

    result = init_registry(args.output, tmux_binary=args.tmux)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
