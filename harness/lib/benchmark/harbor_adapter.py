"""Harbor CLI adapter for Terminal-Bench 2.0.

S03 N2: Pure-function Harbor argv builder + environment probes.
Never executes Harbor/Docker in this module — only detects availability
and constructs command arguments for downstream execution.

Functions:
    detect() — check if harbor/uvx binary is on PATH
    docker_available() — check if Docker daemon is responding
    build_argv(req) — construct Harbor CLI argv list
    api_key_env_for(agent) — map agent name to API key env var name
    probe_api_key(agent) — check env var presence (never reads value)
    probe_dataset(dataset) — HEAD-check Harbor registry for dataset
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from typing import Optional

from .schemas import DEFAULT_DATASET, BenchmarkRunRequest

_AGENT_KEY_MAP: dict[str, str] = {
    "claude-code": "ANTHROPIC_API_KEY",
    "deepagents-cli": "ANTHROPIC_API_KEY",
    "openai-cli": "OPENAI_API_KEY",
}

_REGISTRY_BASE_URL = "https://www.harborframework.com/registry"


def detect() -> tuple[bool, str]:
    """Check if Harbor CLI is available on PATH.

    Returns:
        (available, kind) where kind is 'binary', 'uvx', or 'missing'.
    """
    if shutil.which("harbor"):
        return True, "binary"
    if shutil.which("uvx"):
        return True, "uvx"
    return False, "missing"


def docker_available() -> bool:
    """Check if Docker daemon is reachable.

    Uses `docker info --format {{.ServerVersion}}` with 2s timeout.
    Returns False on any error or non-zero exit.
    """
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def build_argv(req: BenchmarkRunRequest) -> list[str]:
    """Construct the Harbor CLI argv list for a benchmark run.

    This is a pure function — it never executes the command.
    The returned argv starts with 'harbor' or 'uvx harbor' depending
    on which is available; falls back to 'harbor' if detect fails.

    Per S02 §5.1, the command shape is:
        harbor run --dataset terminal-bench@2.0 --agent <agent>
            --model <model> --n-concurrent <n>
            [--env docker|...] [task...]
    """
    _, kind = detect()
    if kind == "binary":
        argv = ["harbor"]
    elif kind == "uvx":
        argv = ["uvx", "harbor"]
    else:
        argv = ["harbor"]

    argv.append("run")
    argv.extend(["--dataset", req.adapter_id or DEFAULT_DATASET])
    argv.extend(["--agent", req.agent])
    argv.extend(["--model", req.model])
    argv.extend(["--n-concurrent", str(req.n_concurrent)])

    if req.env:
        argv.extend(["--env", req.env])

    if req.tasks:
        argv.extend(req.tasks)

    return argv


def api_key_env_for(agent: str) -> Optional[str]:
    """Return the env var name holding the API key for the given agent.

    Returns None for unknown agents. Never reads or returns the value.
    """
    return _AGENT_KEY_MAP.get(agent)


def probe_api_key(agent: str) -> bool:
    """Check whether the API key env var for the agent is present.

    Uses os.environ.get(name) is not None — never reads or logs the value.
    """
    env_name = api_key_env_for(agent)
    if env_name is None:
        return False
    return os.environ.get(env_name) is not None


def probe_dataset(dataset: str, timeout: float = 5.0) -> bool:
    """Probe the Harbor registry to see if a dataset is listed.

    Uses urllib HEAD-style request with short timeout.
    Returns False on any network error.
    """
    url = f"{_REGISTRY_BASE_URL}/{dataset}"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception:
        return False
