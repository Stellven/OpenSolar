"""Production runtime for AI Influence YouTube browser-agent report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .archive import archive_writer_commit
from .browser_agent import BrowserAgentClient, BrowserAgentProvider, ChatGPTReportOperatorProvider
from .evidence_map import build_evidence_map
from .render import render_report_html
from .validator import validator_run


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _slug(value: str, fallback: str = "item") -> str:
    text = "".join(ch if ch.isalnum() or ch in "._-:" else "-" for ch in str(value or "").strip()).strip("-")
    return text or fallback


def _normalize_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        evidence_ref = str(item.get("evidence_ref") or f"E{idx:03d}").strip() or f"E{idx:03d}"
        normalized.append(
            {
                "evidence_ref": evidence_ref,
                "channel": str(item.get("channel") or item.get("channel_name") or "N/A"),
                "title": str(item.get("title") or "N/A"),
                "published_at": str(item.get("published_at") or ""),
                "transcript_grade": str(item.get("transcript_grade") or "T2"),
                "citation_span": str(item.get("citation_span") or item.get("summary") or "")[:400],
                "group_type": str(item.get("group_type") or "other"),
                "summary": str(item.get("summary") or ""),
                "why_it_matters": str(item.get("why_it_matters") or ""),
                "transcript": str(item.get("transcript") or ""),
                "url": str(item.get("url") or ""),
                "category": str(item.get("category") or ""),
                "signal_type": str(item.get("signal_type") or ""),
            }
        )
    return normalized


def _plan_payload(sources: list[dict[str, Any]], *, report_title: str, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "report_title": report_title,
        "sources": sources,
        "instructions": {
            "goal": "基于 transcript 证据先做结构化规划，再拆章写作，最后综合成完整报告。",
            "output_contract": "phase1 必须给出 trends -> chapters -> subsections -> evidence_refs。",
        },
    }


def _parse_plan_text(plan_result: dict[str, Any]) -> dict[str, Any]:
    text = str(plan_result.get("text") or "").strip()
    if not text:
        raise RuntimeError("browser_agent_plan_empty")
    try:
        data = json.loads(text)
    except Exception as exc:
        raise RuntimeError(f"browser_agent_plan_invalid_json:{type(exc).__name__}:{exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("browser_agent_plan_not_object")
    trends = data.get("trends")
    if not isinstance(trends, list) or not trends:
        raise RuntimeError("browser_agent_plan_missing_trends")
    return data


def _flatten_chapters(plan_json: dict[str, Any]) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    for trend_index, trend in enumerate(plan_json.get("trends") or [], start=1):
        if not isinstance(trend, dict):
            continue
        trend_title = str(trend.get("title") or f"Trend {trend_index}")
        for chapter_index, chapter in enumerate(trend.get("chapters") or [], start=1):
            if not isinstance(chapter, dict):
                continue
            chapter_id = str(chapter.get("chapter_id") or f"chapter-{trend_index}-{chapter_index}")
            evidence_refs: list[str] = []
            for subsection in chapter.get("subsections") or []:
                if isinstance(subsection, dict):
                    for ref in subsection.get("evidence_refs") or []:
                        clean = str(ref or "").strip()
                        if clean and clean not in evidence_refs:
                            evidence_refs.append(clean)
            chapters.append(
                {
                    "chapter_id": chapter_id,
                    "title": str(chapter.get("title") or chapter_id),
                    "trend_title": trend_title,
                    "subsections": chapter.get("subsections") or [],
                    "evidence_refs": evidence_refs,
                }
            )
    if not chapters:
        raise RuntimeError("browser_agent_plan_missing_chapters")
    return chapters


def _chapter_payload(chapter: dict[str, Any], evidence_rows: list[dict[str, Any]], *, report_title: str, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "report_title": report_title,
        "chapter": chapter,
        "evidence_rows": evidence_rows,
    }


def _synthesis_payload(chapter_outputs: list[dict[str, Any]], *, report_title: str, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "report_title": report_title,
        "chapters": chapter_outputs,
    }


def generate_browser_agent_report_bundle(
    source_items: list[dict[str, Any]],
    *,
    run_dir: str | Path,
    run_id: str,
    report_title: str,
    requested_model: str = "chatgpt-5.5-thinking-high",
    sprint_id: str = "",
    provider: BrowserAgentProvider | None = None,
    provider_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_dir = _ensure_dir(Path(run_dir).expanduser() / "browser-agent-report")
    sources = _normalize_sources(source_items)
    safe_sources = [item for item in sources if str(item.get("transcript_grade") or "").strip().upper() != "T3"]
    if not safe_sources:
        raise RuntimeError("browser_agent_report_requires_non_t3_sources")

    ledger_path = runtime_dir / "model_call_ledger.jsonl"
    resolved_provider = provider or ChatGPTReportOperatorProvider(
        request_root=runtime_dir / "requests",
        **(provider_options or {}),
    )
    client = BrowserAgentClient(
        resolved_provider,
        ledger_path=ledger_path,
        sprint_id=str(sprint_id or run_id),
    )

    plan_result = client.plan(
        _plan_payload(safe_sources, report_title=report_title, run_id=run_id),
        requested_model=requested_model,
        run_id=run_id,
    )
    plan_json = _parse_plan_text(plan_result)
    chapters = _flatten_chapters(plan_json)
    evidence_by_ref = {str(item["evidence_ref"]): item for item in safe_sources}
    chapter_outputs: list[dict[str, Any]] = []

    for chapter in chapters:
        evidence_rows = [evidence_by_ref[ref] for ref in chapter.get("evidence_refs") or [] if ref in evidence_by_ref]
        if not evidence_rows:
            continue
        chapter_result = client.write_chapter(
            _chapter_payload(chapter, evidence_rows, report_title=report_title, run_id=run_id),
            requested_model=requested_model,
            run_id=run_id,
            chapter_id=str(chapter["chapter_id"]),
        )
        chapter_outputs.append(
            {
                "chapter_id": str(chapter["chapter_id"]),
                "title": str(chapter.get("title") or chapter["chapter_id"]),
                "trend_title": str(chapter.get("trend_title") or ""),
                "evidence_refs": list(chapter.get("evidence_refs") or []),
                "text": str(chapter_result.get("text") or "").strip(),
                "chatgpt_url": str(chapter_result.get("chatgpt_url") or ""),
                "browser_session_id": str(chapter_result.get("browser_session_id") or ""),
            }
        )
    if not chapter_outputs:
        raise RuntimeError("browser_agent_report_no_chapter_outputs")

    synthesis_result = client.synthesize(
        chapter_outputs,
        requested_model=requested_model,
        run_id=run_id,
    )
    synthesis_text = str(synthesis_result.get("text") or "").strip()
    if not synthesis_text:
        raise RuntimeError("browser_agent_report_synthesis_empty")

    sections = [synthesis_text]
    for chapter in chapter_outputs:
        chapter_text = str(chapter.get("text") or "").strip()
        if chapter_text:
            sections.append(f"## {chapter['title']}\n\n{chapter_text}")
    report_md = "\n\n".join(section for section in sections if section.strip()).strip()
    evidence_map = build_evidence_map(safe_sources)
    report_html = render_report_html(report_md, evidence_map, {"title": report_title})
    report_bundle = {
        "run_id": run_id,
        "report_md": report_md,
        "report_html": report_html,
        "evidence_map": evidence_map,
        "plan_json": plan_json,
        "chapter_outputs": chapter_outputs,
        "plan_result": {
            "model_call_id": str(plan_result.get("model_call_id") or ""),
            "chatgpt_url": str(plan_result.get("chatgpt_url") or ""),
            "browser_session_id": str(plan_result.get("browser_session_id") or ""),
            "request_dir": str(plan_result.get("request_dir") or ""),
        },
        "synthesis_result": {
            "model_call_id": str(synthesis_result.get("model_call_id") or ""),
            "chatgpt_url": str(synthesis_result.get("chatgpt_url") or ""),
            "browser_session_id": str(synthesis_result.get("browser_session_id") or ""),
            "request_dir": str(synthesis_result.get("request_dir") or ""),
        },
    }
    validator_report = validator_run(report_bundle).to_dict()
    archive_manifest = archive_writer_commit(
        {
            "archive_dir": str(runtime_dir / "archive"),
            "chatgpt_session_url": str(synthesis_result.get("chatgpt_url") or plan_result.get("chatgpt_url") or ""),
        },
        report_bundle,
        validator_report,
    )
    (runtime_dir / "plan.json").write_text(json.dumps(plan_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (runtime_dir / "evidence_map.json").write_text(json.dumps(evidence_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (runtime_dir / "report.md").write_text(report_md + "\n", encoding="utf-8")
    (runtime_dir / "report.html").write_text(report_html, encoding="utf-8")
    (runtime_dir / "chapter_outputs.json").write_text(json.dumps(chapter_outputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (runtime_dir / "validator_report.json").write_text(json.dumps(validator_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {
        "ok": True,
        "runtime_dir": str(runtime_dir),
        "run_id": run_id,
        "report_title": report_title,
        "report_md_path": str(runtime_dir / "report.md"),
        "report_html_path": str(runtime_dir / "report.html"),
        "plan_json_path": str(runtime_dir / "plan.json"),
        "evidence_map_path": str(runtime_dir / "evidence_map.json"),
        "validator_overall": str(validator_report.get("overall") or ""),
        "archive_dir": str(runtime_dir / "archive"),
        "archive_manifest": archive_manifest,
        "chatgpt_session_url": str(synthesis_result.get("chatgpt_url") or plan_result.get("chatgpt_url") or ""),
        "chapter_count": len(chapter_outputs),
        "source_count": len(safe_sources),
    }
    (runtime_dir / "runtime-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
