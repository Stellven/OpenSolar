import sys
from pathlib import Path
import json


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from ai_influence_youtube_report.archive import archive_writer_commit  # noqa: E402
from ai_influence_youtube_report.browser_agent import BrowserAgentProvider  # noqa: E402
from ai_influence_youtube_report.evidence_map import build_evidence_map  # noqa: E402
from ai_influence_youtube_report.figures import build_figure_specs  # noqa: E402
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


def test_build_figure_specs_selects_grounded_report_and_chapter_figures() -> None:
    evidence = build_evidence_map([
        {
            "evidence_ref": "E001",
            "channel": "AI Engineer",
            "title": "Agent Infra Stack",
            "published_at": "2026-05-25T00:00:00Z",
            "transcript_grade": "T1",
            "citation_span": "agent stack and workflow pipeline",
            "group_type": "conference",
        }
    ])
    specs = build_figure_specs(
        {
            "trends": [
                {
                    "title": "Agent Platforms",
                    "chapters": [
                        {
                            "chapter_id": "chapter-1",
                            "title": "平台化趋势",
                            "subsections": [{"title": "技术栈分层"}],
                        }
                    ],
                }
            ]
        },
        [
            {
                "chapter_id": "chapter-1",
                "title": "平台化趋势",
                "trend_title": "Agent Platforms",
                "evidence_refs": ["E001"],
                "text": "讨论 agent stack, workflow pipeline 与 infra layer。",
            }
        ],
        evidence,
        report_title="AI Influence 平台化报告",
    )

    assert specs
    assert specs[0].figure_type == "architecture_overview"
    assert all(spec.evidence_refs for spec in specs)


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


def _fake_figure_runner(request: dict, task_dir: Path) -> dict:
    image_path = task_dir / "generated_diagram.png"
    image_path.write_bytes(b"fake-png")
    return {
        "status": "success",
        "image_path": str(image_path),
        "request_dir": str(task_dir / "tech-diagram-request"),
        "url": "https://chatgpt.com/c/figure-1",
        "browser_session_id": "figure-session-1",
        "original_image_ok": True,
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
        figure_operator_runner=_fake_figure_runner,
    )

    assert result["ok"] is True
    assert result["validator_overall"] == "PASS"
    runtime_dir = Path(result["runtime_dir"])
    assert (runtime_dir / "report.md").exists()
    assert (runtime_dir / "report.html").exists()
    assert (runtime_dir / "plan.json").exists()
    assert (runtime_dir / "figure_manifest.json").exists()
    assert (runtime_dir / "archive" / "archive_manifest.json").exists()
    assert (runtime_dir / "archive" / "figures" / "figure-manifest.json").exists()
    report_md = (runtime_dir / "report.md").read_text(encoding="utf-8")
    assert "中心判断：Agent 平台化" in report_md
    assert "## 平台化趋势" in report_md
    assert "关键图示" in report_md
    figure_manifest = json.loads((runtime_dir / "figure_manifest.json").read_text(encoding="utf-8"))
    assert figure_manifest["painted_count"] >= 1
    assert result["painted_figure_count"] >= 1
    report_html = (runtime_dir / "report.html").read_text(encoding="utf-8")
    assert "<img src=" in report_html
