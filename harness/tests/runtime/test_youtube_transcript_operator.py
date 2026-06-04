#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import youtube_transcript_operator as yto  # noqa: E402


def test_run_request_uses_submit_helper_and_preserves_duration(monkeypatch, tmp_path, capsys):
    request_dir = tmp_path / "youtube-transcript-request"
    request_dir.mkdir(parents=True, exist_ok=True)
    (request_dir / "assistant-response.txt").write_text("[00:00] hello world\n", encoding="utf-8")
    (request_dir / "page.json").write_text(
        json.dumps(
            {
                "video_id": "wQE2ItbsnVo",
                "title": "TAP - UII",
                "channel": "Open Compute Project",
                "duration_seconds": 725,
                "duration_iso": "PT12M5S",
                "segment_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (request_dir / "transcript.json").write_text(
        json.dumps(
            {
                "duration_seconds": 725,
                "duration_iso": "PT12M5S",
            }
        ),
        encoding="utf-8",
    )

    helper_calls = []

    def _fake_submit(**kwargs):
        helper_calls.append(kwargs)
        assert kwargs["env"]["BROWSER_AGENT_HEADLESS"] == "true"
        (request_dir / "stdout.txt").write_text("ok\n", encoding="utf-8")
        return {"output": "ok", "latency_ms": 1}

    monkeypatch.setattr(yto, "_wrapper_cmd", lambda: ["fake-wrapper"])
    monkeypatch.delenv("BROWSER_AGENT_HEADLESS", raising=False)
    monkeypatch.setattr(yto, "submit_youtube_operator_request", _fake_submit)

    result = yto.run_request(
        {"youtube_url": "https://www.youtube.com/watch?v=wQE2ItbsnVo", "timeout_seconds": 30, "max_retries": 1},
        task_dir=tmp_path,
    )

    assert len(helper_calls) == 1
    transcript_detail = json.loads((request_dir / "transcript.json").read_text(encoding="utf-8"))
    assert transcript_detail["duration_seconds"] == 725
    assert transcript_detail["duration_iso"] == "PT12M5S"
    assert result["text"] == "[00:00] hello world"
    assert (tmp_path / "youtube-transcript-result.json").exists()
    assert (tmp_path / "transcript.txt").exists()

    out = capsys.readouterr().out
    assert "YouTube Transcript Extraction Result" in out
