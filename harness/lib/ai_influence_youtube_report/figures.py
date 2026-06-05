"""Figure spec compilation and TechnologyDiagramPainter integration."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .schema import FigureManifest, FigureResult, FigureSpec


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR_SCRIPT = ROOT / "tools" / "technology_diagram_painter_operator.py"

_ARCHITECTURE_HINTS = (
    "architecture",
    "架构",
    "system",
    "平台",
    "infra",
    "infrastructure",
    "生态",
    "component",
    "模块",
)
_FLOW_HINTS = (
    "flow",
    "流程",
    "pipeline",
    "route",
    "路径",
    "loop",
    "趋势",
    "演进",
    "project implications",
)
_STACK_HINTS = (
    "stack",
    "技术栈",
    "layer",
    "分层",
    "toolchain",
    "模型",
    "数据",
    "tool",
)


def _slug(value: str, fallback: str = "item") -> str:
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip()).strip("-")
    return text or fallback


def _chapter_signal_text(chapter: dict[str, Any], evidence_entries: dict[str, dict[str, Any]]) -> str:
    parts = [
        str(chapter.get("title") or ""),
        str(chapter.get("trend_title") or ""),
        str(chapter.get("text") or ""),
    ]
    for ref in chapter.get("evidence_refs") or []:
        row = evidence_entries.get(str(ref))
        if not row:
            continue
        parts.extend(
            [
                str(row.get("title") or ""),
                str(row.get("citation_span") or ""),
                str(row.get("group_type") or ""),
            ]
        )
    return " ".join(parts).lower()


def _pick_figure_type(signal_text: str) -> str | None:
    if any(token in signal_text for token in _STACK_HINTS):
        return "technology_stack"
    if any(token in signal_text for token in _FLOW_HINTS):
        return "trend_flow"
    if any(token in signal_text for token in _ARCHITECTURE_HINTS):
        return "architecture_overview"
    return None


def _render_prompt(spec: FigureSpec) -> str:
    outline = "\n".join(f"- {item}" for item in spec.input_outline if str(item).strip())
    evidence = ", ".join(spec.evidence_refs) if spec.evidence_refs else "N/A"
    chapters = ", ".join(spec.source_chapter_ids) if spec.source_chapter_ids else "N/A"
    return "\n".join(
        [
            f"Figure Type: {spec.figure_type}",
            f"Figure Title: {spec.title}",
            f"Placement: {spec.placement}",
            f"Source Chapters: {chapters}",
            f"Evidence Refs: {evidence}",
            "",
            "必须基于以下结构化要点生成图，不得臆造正文中不存在的模块、流程或技术栈：",
            outline or "- N/A",
            "",
            "请输出一张适合技术洞察报告正文内嵌的正式 Figure。",
        ]
    ).strip()


def build_figure_specs(
    plan_json: dict[str, Any],
    chapter_outputs: list[dict[str, Any]],
    evidence_map: dict[str, Any],
    *,
    report_title: str,
) -> list[FigureSpec]:
    evidence_entries = {
        str(entry.get("evidence_ref") or "").strip(): entry
        for entry in evidence_map.get("entries") or []
        if str(entry.get("evidence_ref") or "").strip()
    }
    specs: list[FigureSpec] = []
    seen_types: set[str] = set()

    lead_refs: list[str] = []
    lead_outline: list[str] = []
    for chapter in chapter_outputs[:3]:
        for ref in chapter.get("evidence_refs") or []:
            clean = str(ref or "").strip()
            if clean and clean not in lead_refs:
                lead_refs.append(clean)
        title = str(chapter.get("title") or "").strip()
        trend = str(chapter.get("trend_title") or "").strip()
        if title:
            lead_outline.append(f"Chapter: {title}")
        if trend:
            lead_outline.append(f"Trend: {trend}")
    if lead_refs:
        lead_spec = FigureSpec(
            figure_id="fig_01",
            title=f"{report_title} - Architecture Overview",
            figure_type="architecture_overview",
            placement="report_lead",
            source_chapter_ids=[str(ch.get("chapter_id") or "") for ch in chapter_outputs[:3] if str(ch.get("chapter_id") or "").strip()],
            evidence_refs=lead_refs[:6],
            input_outline=lead_outline[:8] or ["Report lead architecture overview"],
            render_prompt="",
            caption="图 1：基于已通过验证章节总结的整体结构图。",
        )
        specs.append(lead_spec)
        seen_types.add(lead_spec.figure_type)

    for chapter in chapter_outputs:
        if len(specs) >= 3:
            break
        signal_text = _chapter_signal_text(chapter, evidence_entries)
        figure_type = _pick_figure_type(signal_text)
        if not figure_type or figure_type in seen_types:
            continue
        refs = [str(ref or "").strip() for ref in chapter.get("evidence_refs") or [] if str(ref or "").strip()]
        if not refs:
            continue
        subsections = []
        for trend in plan_json.get("trends") or []:
            for plan_chapter in trend.get("chapters") or []:
                if str(plan_chapter.get("chapter_id") or "") == str(chapter.get("chapter_id") or ""):
                    for subsection in plan_chapter.get("subsections") or []:
                        title = str(subsection.get("title") or "").strip()
                        if title:
                            subsections.append(title)
        spec = FigureSpec(
            figure_id=f"fig_{len(specs) + 1:02d}",
            title=str(chapter.get("title") or chapter.get("chapter_id") or f"Figure {len(specs) + 1}"),
            figure_type=figure_type,
            placement="chapter_inline",
            source_chapter_ids=[str(chapter.get("chapter_id") or "")],
            evidence_refs=refs[:6],
            input_outline=(
                [f"Trend: {chapter.get('trend_title') or 'N/A'}", f"Chapter: {chapter.get('title') or 'N/A'}"]
                + [f"Subsection: {item}" for item in subsections[:4]]
            ),
            render_prompt="",
            caption=f"图 {len(specs) + 1}：{chapter.get('title') or '章节'} 对应的 {figure_type}。",
        )
        specs.append(spec)
        seen_types.add(figure_type)

    rendered_specs: list[FigureSpec] = []
    for spec in specs:
        rendered_specs.append(
            FigureSpec(
                figure_id=spec.figure_id,
                title=spec.title,
                figure_type=spec.figure_type,
                placement=spec.placement,
                source_chapter_ids=list(spec.source_chapter_ids),
                evidence_refs=list(spec.evidence_refs),
                input_outline=list(spec.input_outline),
                render_prompt=_render_prompt(spec),
                caption=spec.caption,
                status=spec.status,
            )
        )
    return rendered_specs


def _coerce_figure_result(spec: FigureSpec, payload: dict[str, Any]) -> FigureResult:
    raw_status = str(payload.get("status") or "").strip().lower()
    status = "painted" if raw_status in {"success", "painted"} else (raw_status or "failed")
    return FigureResult(
        figure_id=spec.figure_id,
        title=spec.title,
        figure_type=spec.figure_type,
        placement=spec.placement,
        source_chapter_ids=list(spec.source_chapter_ids),
        evidence_refs=list(spec.evidence_refs),
        status=status,
        image_path=str(payload.get("image_path") or "").strip(),
        request_dir=str(payload.get("request_dir") or "").strip(),
        chatgpt_url=str(payload.get("url") or payload.get("chatgpt_url") or "").strip(),
        browser_session_id=str(payload.get("browser_session_id") or "").strip(),
        original_image_ok=bool(payload.get("original_image_ok")),
        error=str(payload.get("error") or "").strip(),
        caption=spec.caption,
    )


def paint_figure(
    spec: FigureSpec,
    *,
    run_dir: str | Path,
    operator_runner: Callable[[dict[str, Any], Path], dict[str, Any]] | None = None,
    operator_script: str | Path | None = None,
    python_executable: str | Path | None = None,
    timeout_seconds: int = 900,
) -> FigureResult:
    task_dir = Path(run_dir).expanduser() / spec.figure_id
    task_dir.mkdir(parents=True, exist_ok=True)
    request_payload = {
        "input_text": "\n".join(spec.input_outline).strip(),
        "prompt": spec.render_prompt,
        "timeout_seconds": max(int(timeout_seconds), 60),
        "max_retries": 1,
        "request_dir": str((task_dir / "tech-diagram-request").resolve()),
    }
    if operator_runner is not None:
        return _coerce_figure_result(spec, operator_runner(request_payload, task_dir))

    envelope = {
        "operator_id": "technology-diagram-painter",
        "technology_diagram_request": request_payload,
    }
    envelope_path = task_dir / "technology-diagram-envelope.json"
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    script = Path(operator_script or DEFAULT_OPERATOR_SCRIPT).expanduser()
    if not script.exists():
        return FigureResult(
            figure_id=spec.figure_id,
            title=spec.title,
            figure_type=spec.figure_type,
            placement=spec.placement,
            source_chapter_ids=list(spec.source_chapter_ids),
            evidence_refs=list(spec.evidence_refs),
            status="failed",
            error=f"operator_not_found:{script}",
            caption=spec.caption,
        )
    env = os.environ.copy()
    env["SOLAR_OPERATOR_ENVELOPE_JSON"] = str(envelope_path)
    env["TASK_DIR"] = str(task_dir)
    env.setdefault("BROWSER_AGENT_HEADLESS", "true")
    cmd = [str(python_executable or sys.executable), str(script)]
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=max(int(timeout_seconds), 60) + 120,
            env=env,
        )
        (task_dir / "operator.stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (task_dir / "operator.stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        result_path = task_dir / "tech-diagram-result.json"
        if proc.returncode != 0:
            return FigureResult(
                figure_id=spec.figure_id,
                title=spec.title,
                figure_type=spec.figure_type,
                placement=spec.placement,
                source_chapter_ids=list(spec.source_chapter_ids),
                evidence_refs=list(spec.evidence_refs),
                status="failed",
                error=f"operator_rc_{proc.returncode}",
                caption=spec.caption,
            )
        if not result_path.exists():
            return FigureResult(
                figure_id=spec.figure_id,
                title=spec.title,
                figure_type=spec.figure_type,
                placement=spec.placement,
                source_chapter_ids=list(spec.source_chapter_ids),
                evidence_refs=list(spec.evidence_refs),
                status="failed",
                error="missing_tech_diagram_result_json",
                caption=spec.caption,
            )
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        return _coerce_figure_result(spec, payload if isinstance(payload, dict) else {})
    except Exception as exc:
        return FigureResult(
            figure_id=spec.figure_id,
            title=spec.title,
            figure_type=spec.figure_type,
            placement=spec.placement,
            source_chapter_ids=list(spec.source_chapter_ids),
            evidence_refs=list(spec.evidence_refs),
            status="failed",
            error=f"{type(exc).__name__}:{exc}",
            caption=spec.caption,
        )


def build_figure_manifest(
    run_id: str,
    figure_results: list[FigureResult],
    *,
    validator_overall: str = "",
) -> FigureManifest:
    painted_count = sum(1 for item in figure_results if item.status == "painted")
    skipped_count = sum(1 for item in figure_results if item.status == "skipped")
    failed_count = sum(1 for item in figure_results if item.status == "failed")
    return FigureManifest(
        run_id=run_id,
        figures=[item.to_dict() for item in figure_results],
        painted_count=painted_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        validator_overall=validator_overall,
    )


def render_figure_markdown(figure: dict[str, Any]) -> str:
    image_path = str(figure.get("image_path") or "").strip()
    if not image_path:
        return ""
    title = str(figure.get("title") or figure.get("figure_id") or "Figure")
    caption = str(figure.get("caption") or "").strip()
    evidence = ", ".join(str(ref) for ref in figure.get("evidence_refs") or [])
    parts = [f"![{title}]({image_path})"]
    if caption:
        parts.append(caption)
    if evidence:
        parts.append(f"Evidence: {evidence}")
    return "\n\n".join(parts).strip()
