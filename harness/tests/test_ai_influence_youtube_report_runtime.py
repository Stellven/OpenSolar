import sys
from pathlib import Path
import json


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from ai_influence_youtube_report.archive import archive_writer_commit  # noqa: E402
from ai_influence_youtube_report.browser_agent import BrowserAgentProvider  # noqa: E402
from ai_influence_youtube_report.evidence_map import build_evidence_map  # noqa: E402
from ai_influence_youtube_report.render import render_report_html  # noqa: E402
from ai_influence_youtube_report.runtime import generate_browser_agent_report_bundle  # noqa: E402
from ai_influence_youtube_report.validator import validator_run  # noqa: E402


def test_runtime_minimal_report_bundle_passes_and_archives(tmp_path: Path) -> None:
    evidence = build_evidence_map([
        {
            "evidence_ref": "E1",
            "channel": "AI Engineer",
            "title": "Agent Platforms",
            "published_at": "2026-05-25T00:00:00Z",
            "transcript_grade": "T1",
            "citation_span": "agent runtime",
            "group_type": "conference",
        }
    ])
    html = render_report_html("中心判断：Agent 平台化。", evidence, {"title": "Agent 平台"})
    bundle = {
        "run_id": "run-1",
        "report_md": "中心判断：Agent 平台化。",
        "report_html": html,
        "evidence_map": evidence,
        "plan_json": {"trends": [{"chapters": []}]},
    }
    verdict = validator_run(bundle).to_dict()
    manifest = archive_writer_commit({"archive_dir": str(tmp_path / "archive")}, bundle, verdict)

    assert verdict["overall"] == "PASS"
    assert manifest["schema_version"] == "archive_manifest.v1"


class _FakeBrowserProvider(BrowserAgentProvider):
    def call(self, stage, payload, *, requested_model, run_id="", chapter_id="", sprint_id=""):
        if stage == "phase1":
            return {
                "model_call_id": "plan-1",
                "browser_session_id": "session-plan",
                "chatgpt_url": "https://chatgpt.com/c/plan-1",
                "resolved_model": requested_model,
                "text": json.dumps(
                    {
                        "trends": [
                            {
                                "title": "Agent Platforms",
                                "chapters": [
                                    {
                                        "chapter_id": "chapter-1",
                                        "title": "平台化趋势",
                                        "subsections": [
                                            {
                                                "subsection_id": "sub-1",
                                                "title": "核心证据",
                                                "evidence_refs": ["E001"],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            }
        if stage == "phase2":
            return {
                "model_call_id": f"chapter-{chapter_id}",
                "browser_session_id": f"session-{chapter_id}",
                "chatgpt_url": f"https://chatgpt.com/c/{chapter_id}",
                "resolved_model": requested_model,
                "text": f"{payload['chapter']['title']} 正文章节。",
            }
        return {
            "model_call_id": "synth-1",
            "browser_session_id": "session-synth",
            "chatgpt_url": "https://chatgpt.com/c/synth-1",
            "resolved_model": requested_model,
            "text": "中心判断：Agent 平台化正在从工具走向工作流基础设施。",
        }


def test_generate_browser_agent_report_bundle_emits_runtime_artifacts(tmp_path: Path) -> None:
    result = generate_browser_agent_report_bundle(
        [
            {
                "evidence_ref": "E001",
                "channel": "AI Engineer",
                "title": "Agent Platforms",
                "published_at": "2026-05-25T00:00:00Z",
                "transcript_grade": "T1",
                "citation_span": "agent runtime",
                "group_type": "conference",
                "summary": "平台趋势总结",
                "transcript": "agent runtime and workflow infrastructure",
            }
        ],
        run_dir=tmp_path / "run",
        run_id="run-1",
        report_title="AI Influence 平台化报告",
        provider=_FakeBrowserProvider(),
        requested_model="chatgpt-5.5-thinking-high",
    )

    assert result["ok"] is True
    assert result["validator_overall"] == "PASS"
    runtime_dir = Path(result["runtime_dir"])
    assert (runtime_dir / "report.md").exists()
    assert (runtime_dir / "report.html").exists()
    assert (runtime_dir / "plan.json").exists()
    assert (runtime_dir / "archive" / "archive_manifest.json").exists()
    report_md = (runtime_dir / "report.md").read_text(encoding="utf-8")
    assert "中心判断：Agent 平台化" in report_md
    assert "## 平台化趋势" in report_md
