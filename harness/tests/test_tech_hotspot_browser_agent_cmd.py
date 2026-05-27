from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "harness" / "scripts" / "tech_hotspot_radar.py"


def _load_namespace() -> dict:
    ns: dict = {"__file__": str(SCRIPT), "__name__": "tech_hotspot_radar_test"}
    code = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
    exec(code, ns)
    return ns


def test_browser_agent_chatgpt_cmd_falls_back_to_bundled_wrapper(monkeypatch):
    monkeypatch.delenv("TECH_HOTSPOT_BROWSER_CHATGPT_CMD", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_CHATGPT_CMD", raising=False)
    ns = _load_namespace()
    cmd = ns["browser_agent_chatgpt_cmd"]({})
    assert cmd, "expected bundled wrapper fallback command"
    assert cmd[-1].endswith("browser_agent_chatgpt_wrapper.py")
    assert "browser-use/.venv/bin/python" in cmd[0]


def test_browser_agent_chatgpt_cmd_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("TECH_HOTSPOT_BROWSER_CHATGPT_CMD", "python3 /tmp/custom-wrapper.py")
    ns = _load_namespace()
    cmd = ns["browser_agent_chatgpt_cmd"]({})
    assert cmd == ["python3", "/tmp/custom-wrapper.py"]


def test_browser_agent_notebooklm_cmd_falls_back_to_bundled_wrapper(monkeypatch):
    monkeypatch.delenv("TECH_HOTSPOT_BROWSER_NOTEBOOKLM_CMD", raising=False)
    monkeypatch.delenv("BROWSER_AGENT_NOTEBOOKLM_CMD", raising=False)
    ns = _load_namespace()
    cmd = ns["browser_agent_notebooklm_cmd"]({})
    assert cmd, "expected bundled wrapper fallback command"
    assert cmd[-1].endswith("browser_agent_notebooklm_wrapper.py")
    assert "browser-use/.venv/bin/python" in cmd[0]


def test_ai_influence_html_render_uses_reader_facing_sources():
    ns = _load_namespace()
    html = ns["render_ai_influence_report_html_anything"](
        "测试报告标题\n证据边界\n这里只基于素材。\n一页结论\n这是结论。\n核心趋势\n1. 主趋势\n判断\n这是判断。",
        {
            "date": "2026-05-26",
            "videos": [
                {
                    "channel": "Google for Developers",
                    "title": "What's new in Google AI",
                    "published_at": "2026-05-23T00:45:21+00:00",
                    "duration_min": 18.2,
                    "summary_zh": "聚焦 Gemini 3.5、AI Studio 与开发者工作流。",
                    "url": "https://www.youtube.com/watch?v=SSe1VmVrtw0",
                    "video_ref": "V001",
                }
            ],
            "report_spec": {
                "title": "测试报告标题",
                "chapters": [
                    {"title": "Gemini 平台化", "material_video_refs": ["V001"]},
                ],
            },
        },
        {"headline": "测试报告标题"},
    )
    assert "本期素材" in html
    assert "章节与视频素材对应表" in html
    assert "V001" in html
    assert "ai-material-ref" in html
    assert "ai-material-chip" in html
    assert "Google for Developers" in html
    assert "What&#x27;s new in Google AI" in html
    assert "聚焦 Gemini 3.5、AI Studio 与开发者工作流。" in html
    assert "<table>" in html
    assert "<th>频道</th>" in html
    assert "<th>视频标题</th>" in html
    assert "<th>发布时间 / 时长</th>" in html
    assert 'href="https://www.youtube.com/watch?v=SSe1VmVrtw0"' in html
    assert 'target="_blank"' in html
    assert "html-anything profile=" not in html
    assert "Browser Agent + ChatGPT 5.5 Thinking high" not in html
    assert "证据边界" not in html
    assert "本报告只基于本次证据包写作，不补外部事实。" not in html
    assert '<section class="ai-report-section"' in html
    assert "<h2>摘要</h2>" in html
    assert "<h4>1. 主趋势</h4>" in html


def test_ai_influence_html_render_injects_notebooklm_figures():
    ns = _load_namespace()
    html = ns["render_ai_influence_report_html_anything"](
        "测试报告标题\n一页结论\n这是结论。\n核心趋势\n1. 主趋势\n判断\n这是判断。\n产品 / 研究 / 工程启示\n这里是落点。",
        {
            "date": "2026-05-26",
            "videos": [],
            "report_spec": {"title": "测试报告标题"},
            "notebooklm": {
                "infographics": [
                    {
                        "title": "平台关系图",
                        "placement_section": "正文",
                        "material_video_refs": ["V001", "V002"],
                        "prompt_text": "画出平台关系与层次",
                        "status": "ready",
                        "image_path": "notebooklm/figure-1.png",
                    }
                ]
            },
        },
        {"headline": "测试报告标题"},
    )
    assert "平台关系图" in html
    assert "notebooklm/figure-1.png" in html
    assert "素材：V001 / V002" in html
    assert "状态：ready" in html


def test_ai_influence_html_render_drops_internal_preamble():
    ns = _load_namespace()
    html = ns["render_ai_influence_report_html_anything"](
        "测试报告标题\n证据边界\n本报告只基于本次证据包写作，不补外部事实。\n需要先把材料质量说清楚：这里是内部前言。\n一页结论\n这是结论。\n核心趋势\n1. 主趋势\n判断\n这是判断。",
        {
            "date": "2026-05-26",
            "videos": [],
            "report_spec": {"title": "测试报告标题"},
        },
        {"headline": "测试报告标题"},
    )
    assert "证据边界" not in html
    assert "本报告只基于本次证据包写作，不补外部事实。" not in html
    assert "需要先把材料质量说清楚" not in html
    assert "<h2>摘要</h2>" in html


def test_ai_influence_reader_tone_polish_rewrites_internal_phrasing():
    ns = _load_namespace()
    polished = ns["_polish_ai_influence_reader_tone"](
        "由于 transcript 几乎没有有效语义，本报告不引用其具体观点，只把标题作为“行业正在讨论空间化 Agent UI”的主题证据。"
        "\n第一，证据中的 200 秒持续推理能力来自自动转写和语义整理，虽然方向可信，但精确表述仍需后续用原视频或官方材料确认。"
    )
    assert "transcript" not in polished
    assert "本报告不引用其具体观点" not in polished
    assert "方向参考" in polished
    assert "公开视频转写" in polished


def test_ai_influence_heading_system_is_editorialized():
    ns = _load_namespace()
    normalized = ns["_normalize_ai_influence_report_markdown"](
        "标题\n一页结论\n这是结论。\n核心趋势\n1. 中心判断：Google 正在变\n判断\n这是判断。\n证据来自哪些频道/视频\n这里是来源。\n为什么重要\n这里是影响。\n对产品/研究/工程/投资的启示\n这里是落点。\n反向证据或不确定性\n这里是待验证。",
        "标题",
    )
    assert "## 摘要" in normalized
    assert "## 正文" in normalized
    assert "### 1. 主线：Google 正在变" in normalized
    assert "#### 观察" in normalized
    assert "#### 素材来源" in normalized
    assert "#### 影响" in normalized
    assert "#### 落点" in normalized
    assert "#### 仍待验证" in normalized


def test_ai_influence_material_map_does_not_leak_planner_fields():
    ns = _load_namespace()
    html = ns["render_ai_influence_report_html_anything"](
        "# 测试报告\n\n## 一页结论\n本节素材：V001《测试视频》。\n\n## 核心趋势\n正文。\n\n## 关键视频证据\n- V001\n\n## 产品 / 研究 / 工程启示\n启示。\n\n## Open Questions\n- 待验证。\n\n## Provenance\n- final_reasoner: chatgpt-5.5\n- local_preprocess: ThunderOMLX/Qwen3.6 semantic packets\n- input_videos: 1\n",
        {
            "date": "2026-05-26",
            "videos": [
                {
                    "video_ref": "V001",
                    "video_id": "abc123",
                    "channel": "AI Engineer",
                    "title": "测试视频",
                    "published_at": "2026-05-23T00:00:00+00:00",
                    "duration_min": 42,
                    "summary_zh": "面向读者的摘要。",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "_internal_debug": "SHOULD_NOT_RENDER",
                }
            ],
            "report_spec": {
                "title": "测试报告",
                "internal_notes": "SHOULD_NOT_RENDER",
                "chapters": [
                    {
                        "title": "中心判断：Coding Agent 的竞争点正在转向工程运行面",
                        "purpose": "把素材组织成一个清晰判断：这是内部写作指令。",
                        "material_video_refs": ["V001"],
                        "debug_prompt": "SHOULD_NOT_RENDER",
                    }
                ],
            },
        },
        {"headline": "测试报告"},
    )
    assert "Coding Agent 的竞争点正在转向工程运行面" in html
    assert "中心判断：" not in html
    assert "把素材组织成" not in html
    assert "purpose" not in html
    assert "material_video_refs" not in html
    assert "internal_notes" not in html
    assert "SHOULD_NOT_RENDER" not in html


def test_plan_prompt_requires_figure_slots():
    ns = _load_namespace()
    prompt = ns["build_ai_influence_report_plan_prompt"](
        [{
            "video_ref": "V001",
            "channel": "Google for Developers",
            "title": "What's new in Google AI",
            "published_at": "2026-05-23T00:45:21+00:00",
            "duration_min": 18.2,
            "language": "en",
            "summary_zh": "摘要",
            "key_points": ["A"],
            "topic_tags": ["agent"],
            "why_it_matters": "重要",
            "transcript_chars": 12000,
        }],
        date_str="2026-05-26",
        days=7,
        model_name="chatgpt-5.5",
    )
    assert '"figure_slots"' in prompt
    assert "NotebookLM" in prompt
    assert "generation_text" in prompt


def test_grouping_prompt_uses_transcript_and_material_type_contract():
    ns = _load_namespace()
    prompt = ns["build_ai_influence_video_grouping_prompt"](
        [{
            "video_ref": "V001",
            "channel": "Google for Developers",
            "title": "Conference keynote about Gemini",
            "published_at": "2026-05-23T00:45:21+00:00",
            "duration_min": 32.0,
            "language": "en",
            "summary_zh": "发布会摘要",
            "key_points": ["Agent platform"],
            "topic_tags": ["agent"],
            "why_it_matters": "重要",
            "transcript_chars": 12000,
            "transcript_truncated_for_grouping": False,
            "transcript_excerpt": "This is a keynote transcript about Gemini agent platform primitives.",
        }],
        date_str="2026-05-26",
        days=7,
        model_name="chatgpt-5.5",
    )
    assert "语义分组" in prompt
    assert "重要展会" in prompt
    assert "大咖访谈" in prompt
    assert "tutorial_demo" in prompt
    assert "transcript_excerpt" in prompt
    assert "不要只按关键词或发布时间聚类" in prompt


def test_plan_prompt_consumes_video_groups_and_requires_hierarchy():
    ns = _load_namespace()
    prompt = ns["build_ai_influence_report_plan_prompt"](
        [{
            "video_ref": "V001",
            "channel": "Google for Developers",
            "title": "What's new in Google AI",
            "published_at": "2026-05-23T00:45:21+00:00",
            "duration_min": 18.2,
            "language": "en",
            "summary_zh": "摘要",
            "key_points": ["A"],
            "topic_tags": ["agent"],
            "why_it_matters": "重要",
            "transcript_chars": 12000,
        }],
        date_str="2026-05-26",
        days=7,
        model_name="chatgpt-5.5",
        video_group_plan={
            "video_groups": [
                {
                    "group_id": "google-io-keynotes",
                    "group_type": "conference",
                    "group_title": "Google I/O 相关发布",
                    "material_video_refs": ["V001"],
                }
            ]
        },
    )
    assert "前置语义分组 JSON" in prompt
    assert "google-io-keynotes" in prompt
    assert '"trends"' in prompt
    assert '"subsections"' in prompt
    assert "趋势 X → 章节 Y → 小结 Z" in prompt


def test_plan_material_refs_recurses_trends_chapters_subsections():
    ns = _load_namespace()
    refs = ns["_plan_material_refs"]({
        "material_video_refs": ["V001"],
        "trends": [
            {
                "material_video_refs": ["V002"],
                "chapters": [
                    {
                        "material_video_refs": ["V003"],
                        "subsections": [
                            {"material_video_refs": ["V004"], "supporting_video_refs": ["V005"]}
                        ],
                    }
                ],
            }
        ],
    })
    assert refs == ["V001", "V002", "V003", "V004", "V005"]


def test_build_planned_report_evidence_pack_skips_missing_status_transcript(tmp_path):
    ns = _load_namespace()
    conn = sqlite3.connect(":memory:")
    conn.executescript(ns["SCHEMA_SQL"])
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO youtube_channels(channel_id,channel_name,channel_url,category,enabled,imported_at) VALUES(?,?,?,?,?,?)",
        ("UCtest", "AI Engineer", "https://www.youtube.com/@aiDotEngineer", "AI / Tech", 1, "2026-05-26T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO youtube_videos(video_id,channel_id,title,channel_name,video_url,published_at,duration_seconds,fetched_at) VALUES(?,?,?,?,?,?,?,?)",
        ("bad001", "UCtest", "Prompt to Pipeline", "AI Engineer", "https://www.youtube.com/watch?v=bad001", "2026-05-23T00:00:00+00:00", 1200, "2026-05-26T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO youtube_transcripts(video_id,transcript_raw,transcript_clean,transcript_status,language,char_count) VALUES(?,?,?,?,?,?)",
        ("bad001", "我 我 我", "我 我 我\n研究\n研究\n机构\n" * 60, "missing", "mixed", 0),
    )
    pack = ns["build_planned_report_evidence_pack"](
        conn,
        [{
            "video_ref": "V001",
            "video_id": "bad001",
            "title": "Prompt to Pipeline",
            "channel": "AI Engineer",
            "url": "https://www.youtube.com/watch?v=bad001",
            "published_at": "2026-05-23T00:00:00+00:00",
        }],
        {"material_video_refs": ["V001"]},
        date_str="2026-05-26",
        days=7,
    )
    assert pack["videos"] == []
    assert pack["skipped_material_refs"] == ["V001"]


def test_notebooklm_bundle_and_request_are_built(tmp_path):
    ns = _load_namespace()
    evidence_pack = {
        "date": "2026-05-26",
        "report_spec": {
            "title": "测试报告",
            "figure_slots": [
                {
                    "figure_id": "agent-map",
                    "placement_section": "正文",
                    "placement_heading": "Gemini 平台化",
                    "title": "Agent 平台关系图",
                    "material_video_refs": ["V001"],
                    "generation_text": "画平台关系图",
                }
            ],
        },
        "videos": [
            {
                "video_ref": "V001",
                "title": "What's new in Google AI",
                "channel": "Google for Developers",
                "published_at": "2026-05-23T00:45:21+00:00",
                "url": "https://www.youtube.com/watch?v=SSe1VmVrtw0",
                "summary_zh": "摘要",
                "transcript_clean": "transcript body",
            }
        ],
    }
    request = ns["build_ai_influence_notebooklm_request"](
        evidence_pack,
        tmp_path / "report",
        notebook_name="AI Influence 2026-05",
    )
    assert request["notebook_name"] == "AI Influence 2026-05"
    assert request["mindmap"]["enabled"] is True
    assert request["infographics"][0]["figure_id"] == "agent-map"
    bundle_text = Path(request["source_files"][0]).read_text(encoding="utf-8")
    assert "Transcript 原文" in bundle_text
    assert "What's new in Google AI" in bundle_text


def test_attach_notebooklm_context_to_evidence_pack():
    ns = _load_namespace()
    pack = ns["attach_notebooklm_context_to_evidence_pack"](
        {"date": "2026-05-26", "videos": []},
        {
            "notebook_name": "AI Influence 2026-05",
            "notebook_url": "https://notebooklm.google.com/notebook/abc",
            "source_summary": "summary",
            "mindmap": {"status": "ready"},
            "infographics": [{"title": "图一"}],
        },
    )
    assert pack["notebooklm"]["notebook_name"] == "AI Influence 2026-05"
    assert pack["notebooklm"]["mindmap"]["status"] == "ready"
    assert pack["notebooklm"]["infographics"][0]["title"] == "图一"


def test_transcript_path_for_video_uses_week_bucket(tmp_path):
    ns = _load_namespace()
    db_path = tmp_path / "tech-hotspot-radar.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE youtube_videos (video_id TEXT PRIMARY KEY, published_at TEXT)")
    conn.execute(
        "INSERT INTO youtube_videos(video_id, published_at) VALUES (?, ?)",
        ("PvFMT58lgvk", "2026-05-07T19:36:01+00:00"),
    )
    conn.commit()
    conn.close()
    config = {
        "output": {
            "state_dir": str(tmp_path / "state"),
            "database": str(db_path),
        }
    }
    path = ns["transcript_path_for_video"]("PvFMT58lgvk", config)
    assert path.name == "PvFMT58lgvk.txt"
    assert path.parent.name == ns["transcript_week_key"]("2026-05-07T19:36:01+00:00")


def test_transcript_state_dirs_migrates_flat_cache_and_rewrites_sources(tmp_path):
    ns = _load_namespace()
    state_dir = tmp_path / "state"
    transcripts_dir = state_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    legacy = transcripts_dir / "PvFMT58lgvk.txt"
    legacy.write_text("hello\n", encoding="utf-8")
    result_dir = state_dir / "transcript-results" / "done"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_json = result_dir / "job.json"
    result_json.write_text(
        '{"source": "%s", "status": "completed"}\n' % str(legacy),
        encoding="utf-8",
    )
    db_path = tmp_path / "tech-hotspot-radar.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE youtube_videos (video_id TEXT PRIMARY KEY, published_at TEXT)")
    conn.execute(
        "INSERT INTO youtube_videos(video_id, published_at) VALUES (?, ?)",
        ("PvFMT58lgvk", "2026-05-07T19:36:01+00:00"),
    )
    conn.commit()
    conn.close()
    config = {
        "output": {
            "state_dir": str(state_dir),
            "database": str(db_path),
        }
    }
    ns["transcript_state_dirs"](config)
    migrated = transcripts_dir / ns["transcript_week_key"]("2026-05-07T19:36:01+00:00") / "PvFMT58lgvk.txt"
    assert migrated.exists()
    assert legacy.exists() is False
    payload = result_json.read_text(encoding="utf-8")
    assert str(migrated) in payload
    found = ns["find_transcript_file"]("PvFMT58lgvk", config)
    assert found == migrated


def test_ai_influence_validation_rejects_raw_video_id_leak(tmp_path):
    ns = _load_namespace()
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    complete_md = """# 测试报告

## 一页结论
本节素材：V001《测试视频》。这里不能出现 SSe1VmVrtw0。

## 核心趋势
### 趋势一
判断。

## 关键视频证据
- V001《测试视频》

## 产品 / 研究 / 工程启示
启示。

## Open Questions
- 待验证。

## Provenance
- final_reasoner: chatgpt-5.5
- local_preprocess: ThunderOMLX/Qwen3.6 semantic packets
- input_videos: 1
"""
    (report_dir / "report.md").write_text(complete_md, encoding="utf-8")
    (report_dir / "report.html").write_text(
        "章节与视频素材对应表 <span class='ai-material-ref'>V001</span> <span class='ai-material-chip'>测试视频</span>",
        encoding="utf-8",
    )
    (report_dir / "report-result.json").write_text('{"request_dir": ""}\n', encoding="utf-8")
    (report_dir / "evidence-pack.json").write_text(
        '{"videos":[{"video_ref":"V001","video_id":"SSe1VmVrtw0","title":"测试视频","channel":"Google for Developers","transcript_clean":"This is a clean English transcript about Gemini, agent workflows, developer tools, and platform strategy. It contains enough meaningful sentences for validation."}]}\n',
        encoding="utf-8",
    )
    (report_dir / "transcripts.txt").write_text("raw\n", encoding="utf-8")
    (report_dir / "transcripts-cleaned.txt").write_text("clean\n", encoding="utf-8")
    result = ns["validate_ai_influence_planned_report_dir"](report_dir)
    assert result["status"] == "error"
    assert "raw_video_id_leaked:SSe1VmVrtw0" in result["errors"]


def test_ai_influence_validation_accepts_hardened_report_with_project_archive(tmp_path):
    ns = _load_namespace()
    report_dir = tmp_path / "report"
    request_dir = tmp_path / "browser-request"
    report_dir.mkdir()
    request_dir.mkdir()
    (request_dir / "project-archive-result.json").write_text(
        '{"status":"ok","project_name":"杂项"}\n',
        encoding="utf-8",
    )
    complete_md = """# 测试报告

## 一页结论
本节素材：V001《测试视频》。这是结论。

## 核心趋势
### 趋势一
判断。

## 关键视频证据
- V001《测试视频》

## 产品 / 研究 / 工程启示
启示。

## Open Questions
- 待验证。

## Provenance
- final_reasoner: chatgpt-5.5
- local_preprocess: ThunderOMLX/Qwen3.6 semantic packets
- input_videos: 1
"""
    (report_dir / "report.md").write_text(complete_md, encoding="utf-8")
    (report_dir / "report.html").write_text(
        "章节与视频素材对应表 <span class='ai-material-ref'>V001</span> <span class='ai-material-chip'>测试视频</span>",
        encoding="utf-8",
    )
    (report_dir / "report-result.json").write_text(
        '{"request_dir": "%s"}\n' % str(request_dir),
        encoding="utf-8",
    )
    (report_dir / "evidence-pack.json").write_text(
        '{"videos":[{"video_ref":"V001","video_id":"SSe1VmVrtw0","title":"测试视频","channel":"Google for Developers","transcript_clean":"This is a clean English transcript about Gemini, agent workflows, developer tools, and platform strategy. It contains enough meaningful sentences for validation."}]}\n',
        encoding="utf-8",
    )
    (report_dir / "transcripts.txt").write_text("raw\n", encoding="utf-8")
    (report_dir / "transcripts-cleaned.txt").write_text("clean\n", encoding="utf-8")
    result = ns["validate_ai_influence_planned_report_dir"](
        report_dir,
        expected_chatgpt_project="杂项",
        require_project_archive=True,
    )
    assert result["status"] == "ok"
    assert result["errors"] == []


def test_ai_influence_validation_rejects_bad_transcript_in_evidence_pack(tmp_path):
    ns = _load_namespace()
    report_dir = tmp_path / "report"
    request_dir = tmp_path / "browser-request"
    report_dir.mkdir()
    request_dir.mkdir()
    (request_dir / "project-archive-result.json").write_text(
        '{"status":"ok","project_name":"杂项"}\n',
        encoding="utf-8",
    )
    complete_md = """# 测试报告

## 一页结论
本节素材：V001《测试视频》。这是结论。

## 核心趋势
### 趋势一
判断。

## 关键视频证据
- V001《测试视频》

## 产品 / 研究 / 工程启示
启示。

## Open Questions
- 待验证。

## Provenance
- final_reasoner: chatgpt-5.5
- local_preprocess: ThunderOMLX/Qwen3.6 semantic packets
- input_videos: 1
"""
    (report_dir / "report.md").write_text(complete_md, encoding="utf-8")
    (report_dir / "report.html").write_text(
        "章节与视频素材对应表 <span class='ai-material-ref'>V001</span> <span class='ai-material-chip'>测试视频</span>",
        encoding="utf-8",
    )
    (report_dir / "report-result.json").write_text(
        '{"request_dir": "%s"}\n' % str(request_dir),
        encoding="utf-8",
    )
    bad = "我叫Page\n研究\n研究\n机构\n互相\n针钛 针钛\n" * 80
    (report_dir / "evidence-pack.json").write_text(
        '{"videos":[{"video_ref":"V001","video_id":"ns9f1fjLD7Y","title":"Prompt to Pipeline","channel":"AI Engineer","transcript_clean":%s}]}\n'
        % __import__("json").dumps(bad, ensure_ascii=False),
        encoding="utf-8",
    )
    (report_dir / "transcripts.txt").write_text("raw\n", encoding="utf-8")
    (report_dir / "transcripts-cleaned.txt").write_text("clean\n", encoding="utf-8")
    result = ns["validate_ai_influence_planned_report_dir"](
        report_dir,
        expected_chatgpt_project="杂项",
        require_project_archive=True,
    )
    assert result["status"] == "error"
    assert any("bad_transcript_in_evidence_pack" in err for err in result["errors"])


def test_cleanup_transcript_cache_removes_nested_week_files(tmp_path):
    ns = _load_namespace()
    state_dir = tmp_path / "state"
    week_dir = state_dir / "transcripts" / "2026-W19"
    week_dir.mkdir(parents=True, exist_ok=True)
    old_txt = week_dir / "old.txt"
    old_txt.write_text("stale\n", encoding="utf-8")
    stale_ts = 1_700_000_000
    os.utime(old_txt, (stale_ts, stale_ts))
    config = {
        "output": {
            "state_dir": str(state_dir),
            "database": str(tmp_path / "missing.sqlite"),
            "retention_days": 1,
        }
    }
    removed = ns["cleanup_transcript_cache"](config)
    assert removed == 1
    assert old_txt.exists() is False
