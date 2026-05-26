from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from github_intelligence.pipeline import STAGE_ORDER, run_daily_pipeline


def test_pipeline_dry_run_runs_all_eight_stages_in_order():
    result = run_daily_pipeline(dry_run=True)
    assert result.status == "passed"
    assert [stage.stage for stage in result.stages] == STAGE_ORDER
    assert all(stage.status == "passed" for stage in result.stages)


def test_pipeline_isolates_stage_failure_and_continues():
    calls = []
    def ok(**kwargs):
        calls.append("ok")
        return {"ok": True}
    def bad(**kwargs):
        calls.append("bad")
        raise RuntimeError("boom")
    stages = {name: ok for name in STAGE_ORDER}
    stages["detect"] = bad

    result = run_daily_pipeline(stages=stages)

    assert result.status == "passed_with_stage_failures"
    assert len(result.stages) == 8
    failed = [stage for stage in result.stages if stage.stage == "detect"][0]
    assert failed.status == "failed"
    assert "boom" in failed.error
