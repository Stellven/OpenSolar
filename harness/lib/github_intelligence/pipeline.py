"""Cron-safe daily pipeline orchestrator for GitHub Intelligence."""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable, Any

STAGE_ORDER = ["collect", "delta", "detect", "evidence", "packet", "analysis", "verify", "report"]


@dataclass
class StageResult:
    stage: str
    status: str
    duration_ms: int
    error: str = ""
    output: Any = None


@dataclass
class PipelineResult:
    status: str
    dry_run: bool
    started_at: str
    finished_at: str
    stages: list[StageResult]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stages"] = [asdict(stage) for stage in self.stages]
        return data


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_stage(name: str) -> Callable[..., dict[str, Any]]:
    def _run(**kwargs: Any) -> dict[str, Any]:
        return {"stage": name, "status": "skipped", "reason": "no stage handler configured"}
    return _run


def run_daily_pipeline(
    *,
    stages: dict[str, Callable[..., Any]] | None = None,
    dry_run: bool = False,
    continue_on_error: bool = True,
    context: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run the 8-stage GitHub intelligence pipeline with failure isolation."""
    started = _now()
    stage_results: list[StageResult] = []
    context = dict(context or {})
    stages = stages or {}
    for name in STAGE_ORDER:
        t0 = time.perf_counter()
        try:
            if dry_run:
                output = {"stage": name, "dry_run": True}
            else:
                output = stages.get(name, default_stage(name))(**context)
            status = "passed"
            error = ""
        except Exception as exc:  # failure isolation is the contract
            output = None
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            if not continue_on_error:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                stage_results.append(StageResult(name, status, duration_ms, error, output))
                break
        duration_ms = int((time.perf_counter() - t0) * 1000)
        stage_results.append(StageResult(name, status, duration_ms, error, output))
    overall = "passed" if all(stage.status == "passed" for stage in stage_results) and len(stage_results) == len(STAGE_ORDER) else "passed_with_stage_failures"
    return PipelineResult(overall, dry_run, started, _now(), stage_results)


__all__ = ["STAGE_ORDER", "StageResult", "PipelineResult", "run_daily_pipeline"]
