from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import youtube_influence_digest as yid


def _base_meta() -> dict[str, str]:
    return {
        "video_id": "abc123xyz00",
        "channel_id": "chan1",
        "channel_name": "Demo Channel",
        "category": "AI / Tech",
        "priority": "tier1",
        "title": "Build an AI agent demo with tools",
        "url": "https://www.youtube.com/watch?v=abc123xyz00",
        "published_at": "2026-05-30T10:00:00Z",
        "fetched_at": "2026-05-30T11:00:00Z",
        "source": "fixture:feed",
    }


def test_assess_transcript_quality_marks_short_text_t3():
    result = yid.assess_transcript_quality(
        meta=_base_meta(),
        transcript="bad",
        status="ok_asr",
        source="browser_agent_operator:abc123xyz00",
        config={"analysis_keywords": {"agent": ["agent", "tools"]}},
    )
    assert result["tier"] == "T3"
    assert result["status"] == "degraded"


def test_render_transcript_for_report_hides_t3_body():
    video = yid.build_video(
        _base_meta(),
        "bad",
        "ok_asr",
        "browser_agent_operator:abc123xyz00",
        {"analysis_keywords": {"agent": ["agent", "tools"]}},
    )
    rendered = yid.render_transcript_for_report(video)
    assert "质量门禁判定为 `T3`" in rendered


def test_maybe_write_browser_agent_report_respects_enabled_flag(tmp_path: Path):
    video = yid.build_video(
        _base_meta(),
        "Today we build an AI agent demo with tools. The workflow shows automation and evaluation.",
        "ok",
        "browser_agent_operator:abc123xyz00",
        {"analysis_keywords": {"agent": ["agent", "tools"]}},
    )
    disabled = yid.maybe_write_browser_agent_report(
        [video],
        config={"output": {"browser_agent_report": {"enabled": False}}},
        run_dir=tmp_path,
        run_id="run-1",
        dry_run=False,
    )
    assert disabled["enabled"] is False
    assert disabled["status"] == "disabled"


def test_write_markdown_attaches_browser_agent_report_when_enabled(tmp_path: Path):
    video = yid.build_video(
        _base_meta(),
        "Today we build an AI agent demo with tools. The workflow shows automation and evaluation.",
        "ok",
        "browser_agent_operator:abc123xyz00",
        {"analysis_keywords": {"agent": ["agent", "tools"]}},
    )
    config = {
        "output": {
            "raw_dir": str(tmp_path / "raw"),
            "state_dir": str(tmp_path / "state"),
            "browser_agent_report": {"enabled": True},
        }
    }
    with mock.patch.object(
        yid,
        "maybe_write_browser_agent_report",
        return_value={"enabled": True, "ok": True, "status": "generated", "runtime_dir": str(tmp_path / "report")},
    ) as patched:
        result = yid.write_markdown([video], [], config, dry_run=False)
    assert patched.called
    assert result["browser_agent_report"]["ok"] is True
    assert Path(result["digest_path"]).exists()
