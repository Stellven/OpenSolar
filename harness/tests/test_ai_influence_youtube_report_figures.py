from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from ai_influence_youtube_report.figures import (
    FigureSpec,
    _flow_control_retry_delay,
    paint_figure,
)


def test_flow_control_retry_delay_parses_cooldown_timestamp() -> None:
    delay = _flow_control_retry_delay(
        "FlowControlBlocked: operator technology-diagram-painter blocked by flow control: state=cooldown until 2099-01-01T00:00:30Z"
    )
    assert delay > 0


def test_paint_figure_retries_once_after_flow_control_cooldown(monkeypatch, tmp_path: Path) -> None:
    spec = FigureSpec(
        figure_id="fig_01",
        title="Figure",
        figure_type="architecture_overview",
        placement="report_lead",
        source_chapter_ids=["ch_01"],
        evidence_refs=["E1"],
        input_outline=["Section: Demo"],
        render_prompt="Prompt",
        caption="Caption",
    )
    script = tmp_path / "fake_operator.py"
    script.write_text("# fake\n", encoding="utf-8")

    calls = {"count": 0}

    def fake_run(cmd, text, capture_output, timeout, env):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if calls["count"] == 1:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout="",
                stderr="FlowControlBlocked: operator technology-diagram-painter blocked by flow control: state=cooldown until 2099-01-01T00:00:30Z",
            )
        task_dir = Path(env["TASK_DIR"])
        (task_dir / "tech-diagram-result.json").write_text(
            json.dumps(
                {
                    "status": "success",
                    "image_path": str(task_dir / "generated.png"),
                    "url": "https://chatgpt.com/backend-api/estuary/content?id=file_demo",
                    "source": "network-image-response",
                    "original_image_ok": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("ai_influence_youtube_report.figures.subprocess.run", fake_run)
    monkeypatch.setattr("ai_influence_youtube_report.figures.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "ai_influence_youtube_report.figures._flow_control_retry_delay",
        lambda _stderr, cap_seconds=90.0: 0.0 if calls["count"] > 1 else 0.01,
    )

    result = paint_figure(
        spec,
        run_dir=tmp_path,
        operator_script=script,
        python_executable="python3",
        timeout_seconds=60,
    )

    assert calls["count"] == 2
    assert result.status == "painted"
    assert "generated.png" in result.image_path
