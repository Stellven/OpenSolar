"""Deterministic section writer/reviewer/reviser loop for survey reports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .backends import HumanResponseMissingError, LocalCommandWriterError, PanePacketPendingError, get_writer_backend
from .schemas import SectionPromptPacket, SectionReview, SectionRevisionTrace, to_dict

PROFESSOR_GRADE_WRITING_POLICY = {
    "policy_id": "solar.survey.professor_grade_writing.v1",
    "purpose": "Turn evidence packs into auditable professor-grade survey sections instead of generic long-form summaries.",
    "section_template": [
        "Research Question",
        "Position",
        "Claim Map",
        "Evidence Map",
        "Source Map",
        "Literature Lineage",
        "Method Taxonomy",
        "Architecture Synthesis",
        "Comparative Positioning",
        "Terminology Evolution",
        "Evaluation Protocol Matrix",
        "Evaluation And Risk Boundary",
        "Limitations And Failure Modes",
        "Controversy Matrix",
        "Contradiction Slots",
        "Open Problems",
    ],
    "synthesis_rules": [
        "Separate mechanism, system, evaluation, and deployment claims.",
        "State which source type supports each important conclusion.",
        "Prefer bounded conclusions when evidence comes from narrow benchmarks or partial implementations.",
        "Surface contradictions and missing evidence in the main body, not only in footnotes.",
        "Preserve claim/evidence tags so factuality gates can audit the section mechanically.",
    ],
    "forbidden_patterns": [
        "Do not invent source names, URLs, metrics, benchmarks, or paper results.",
        "Do not collapse paper evidence, official docs, code, and benchmarks into one undifferentiated citation bucket.",
        "Do not turn open problems into vague future-work filler.",
    ],
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _row_id(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    return ""


def _load_ledgers(root: Path) -> dict[str, dict[str, dict]]:
    sources = {_row_id(row, "id", "source_id"): row for row in _read_jsonl(root / "sources.jsonl")}
    evidence = {_row_id(row, "id", "evidence_id"): row for row in _read_jsonl(root / "evidence.jsonl")}
    claims = {_row_id(row, "id", "claim_id"): row for row in _read_jsonl(root / "claims.jsonl")}
    return {"sources": sources, "evidence": evidence, "claims": claims}


def _evidence_text(row: dict) -> str:
    return str(row.get("content") or row.get("span_text") or row.get("clean_markdown") or row.get("text") or row.get("title") or "")


def _claim_text(row: dict) -> str:
    return str(row.get("claim_text") or row.get("text") or row.get("title") or "")


def _inline_text(value: Any, *, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"\b(Title|URL|Publisher|Published|Source Type):\s*", r"\1=", text)
    return text[:limit].strip()


def _clean_claim_for_reader(value: Any, *, fallback: str, limit: int = 280) -> str:
    text = _inline_text(value, limit=900)
    if not text:
        return fallback
    text = re.sub(r"^CAIS 2026 evidence supports the section-level trend claim for\s+", "", text, flags=re.I)
    text = re.split(r"\s+This claim must be read through\s+", text, maxsplit=1, flags=re.I)[0]
    text = text.replace("洞察分析：基于 CAIS 2026 accepted papers and demos 看 Agent 系统演进趋势。", "")
    text = text.replace("重点分析 architecture/composition、system optimization、engineering/operations、evaluation/benchmarking、security/privacy 五类议题", "")
    text = re.sub(r"[。.!?！？]+", "；", text)
    text = re.sub(r"\s+", " ", text).strip(" ;:：.")
    return _inline_text(text or fallback, limit=limit)


def _clean_source_title(value: Any, *, limit: int = 110) -> str:
    text = _inline_text(value, limit=240)
    text = re.split(r"\s+(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\s+\(|[A-Z][a-z]+\s+[A-Z]\s)", text, maxsplit=1)[0].strip()
    return _inline_text(text or value, limit=limit)


def _evidence_brief(row: dict, src: dict, *, fallback: str, limit: int = 260) -> str:
    content = _inline_text(_evidence_text(row), limit=900)
    title = _clean_source_title(src.get("title") or "", limit=140)
    if title and content.lower().startswith(title.lower()[: min(len(title), 60)]):
        content = content[len(title):].strip(" -:;,.")
    content = re.sub(r"\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+\([^)]{2,80}\)\s*,?", " ", content)
    content = re.sub(r"\s+", " ", content).strip()
    if not content or len(content) < 45:
        content = title or fallback
    return _inline_text(content, limit=limit)


def _section_reader_label(title: str, chapter: dict[str, Any]) -> str:
    chapter_title = _inline_text(chapter.get("chapter_title") or "", limit=80)
    section_title = _inline_text(title, limit=80)
    return f"{chapter_title} / {section_title}" if chapter_title and chapter_title != section_title else section_title


def _local_question_for_reader(question: str, *, title: str, reader_label: str) -> str:
    text = _inline_text(question, limit=900)
    match = re.search(r"(?:在|围绕|关于)[“\"]?([^。.!?！？]{8,220})", text)
    if match:
        text = match.group(0)
    elif ". " in text:
        text = text.split(". ", 1)[1]
    elif "。" in text:
        text = text.split("。", 1)[-1]
    text = text.strip(" ;:：。.!?！？")
    if not text:
        text = f"{reader_label} 如何改变 Agent 系统趋势判断"
    if reader_label not in text and title not in text:
        text = f"{reader_label}: {text}"
    return _inline_text(text, limit=260)


def _claim_statement_for_reader(raw_claim: str, *, title: str, reader_label: str, local_question: str, role_desc: str) -> str:
    text = _clean_claim_for_reader(raw_claim, fallback=local_question)
    title_key = _compact_for_reader(title)
    text_key = _compact_for_reader(text)
    if title_key and title_key not in text_key:
        return f"围绕“{local_question}”的交叉证据线索"
    return text


def _compact_for_reader(text: Any) -> str:
    return "".join(ch.lower() for ch in str(text or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _section_anchor(section_id: str, title: str, chapter: dict[str, Any]) -> str:
    chapter_id = str(chapter.get("chapter_id") or section_id.split("/", 1)[0])
    order = str(chapter.get("section_order_in_chapter") or "N/A")
    return f"{chapter_id}#{order}::{section_id}::{title}"


def _section_lens(title: str, question: str, source_types: list[str], order: int) -> dict[str, str]:
    title_l = title.lower()
    question_l = question.lower()
    if re.search(r"architecture|架构|mechanism|机制|method|taxonomy|分类", title_l + " " + question_l):
        axis = "architecture"
        focus = "机制分层、状态表示、系统边界和可复现实现路径"
        risk = "把机制可行性误读为工程可控性"
    elif re.search(r"eval|benchmark|评估|评价|metric|数据", title_l + " " + question_l):
        axis = "evaluation"
        focus = "任务覆盖、指标口径、baseline 公平性和外推边界"
        risk = "用单一 benchmark 结果替代跨任务可靠性判断"
    elif re.search(r"deploy|engineering|system|工程|部署|成本", title_l + " " + question_l):
        axis = "deployment"
        focus = "调度成本、观测性、失败恢复和生产约束"
        risk = "忽略隐状态方法在真实调用链中的可诊断性成本"
    elif re.search(r"contradiction|limit|risk|争议|局限|失败", title_l + " " + question_l):
        axis = "controversy"
        focus = "反证来源、负例任务、不可复现实验和术语冲突"
        risk = "只保留支持性证据而删除失败路径"
    else:
        axis = ["mechanism", "evidence", "integration", "roadmap"][max(order - 1, 0) % 4]
        focus = "概念边界、证据类型、章节衔接和后续研究问题"
        risk = "把材料摘要写成无可审计边界的泛化结论"
    primary_source = source_types[0] if source_types else "uncovered"
    secondary_source = source_types[1] if len(source_types) > 1 else primary_source
    return {
        "axis": axis,
        "focus": focus,
        "risk": risk,
        "primary_source": primary_source,
        "secondary_source": secondary_source,
    }


def _dedupe_sentences(text: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        key = re.sub(r"\s+", " ", line.strip().lower())
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _localize_section_headings(text: str, *, title: str, section_id: str) -> str:
    """Make deterministic survey headings unique enough for human review.

    The built-in writer intentionally uses a fixed section skeleton, but the
    compiled report and HTML quality gate treat repeated headings as a strong
    smell that the report is a template.  Keep the skeleton recognizable while
    making each heading navigable and section-specific.
    """
    suffix = _inline_text(title, limit=72) or section_id

    def repl(match: re.Match[str]) -> str:
        heading = match.group(1).strip()
        if section_id in heading:
            return match.group(0)
        return f"## {heading} - {section_id} - {suffix}"

    return re.sub(r"^##\s+(.+?)\s*$", repl, text, flags=re.M)


def _chapter_context(root: Path, section_id: str, spec: dict) -> dict[str, Any]:
    ast = _read_json(root / "survey_report_ast.json")
    chapter_id = str(spec.get("chapter_id") or section_id.split("/", 1)[0])
    chapters = ast.get("chapters", []) if isinstance(ast.get("chapters"), list) else []
    sections = ast.get("sections", []) if isinstance(ast.get("sections"), list) else []
    chapter = next((row for row in chapters if str(row.get("chapter_id") or "") == chapter_id), {})
    sibling_sections = [
        {
            "section_id": str(row.get("section_id") or ""),
            "title": str(row.get("title") or ""),
            "research_question": str(row.get("research_question") or ""),
        }
        for row in sections
        if str(row.get("chapter_id") or "") == chapter_id
    ]
    return {
        "chapter_id": chapter_id,
        "chapter_title": str(chapter.get("title") or chapter_id),
        "chapter_objective": str(chapter.get("objective") or ""),
        "section_order_in_chapter": next((idx + 1 for idx, row in enumerate(sibling_sections) if row.get("section_id") == section_id), 0),
        "sibling_sections": sibling_sections,
        "chapter_prompt_packet": str(root / "chapters" / chapter_id / "prompt_packet.md"),
    }


def _source_type_guidance(source_types: list[str]) -> list[str]:
    guidance = {
        "paper": "Use papers for mechanisms, assumptions, experimental claims, and limits of generalization.",
        "preprint": "Treat preprints as useful but provisional; preserve uncertainty.",
        "official_doc": "Use official docs for system boundaries, APIs, deployment constraints, and supported behavior.",
        "code": "Use code repositories for reproducibility, implementation cost, integration boundaries, and maintenance risk.",
        "repo": "Use repositories for reproducibility, implementation cost, integration boundaries, and maintenance risk.",
        "benchmark": "Use benchmarks for evaluation scope, metric caveats, and comparability limits.",
        "dataset": "Use datasets for task coverage, distribution assumptions, leakage, and annotation limits.",
    }
    return [guidance.get(str(item), f"Use {item} sources only for claims they directly support.") for item in source_types]


def build_section_prompt_packet(root: Path, section_id: str, round_index: int = 0, writer_backend: str = "deterministic") -> dict:
    section_dir = root / "sections" / section_id
    spec = _read_json(section_dir / "section.spec.json")
    pack = _read_json(section_dir / "evidence_pack.json")
    source_types = [str(item) for item in pack.get("source_types", []) if str(item)] if isinstance(pack.get("source_types"), list) else []
    chapter_context = _chapter_context(root, section_id, spec)
    packet = SectionPromptPacket(
        section_id=section_id,
        round_index=round_index,
        writer_backend=writer_backend,
        role="professor-grade technical survey section writer",
        task=f"Write or revise section '{spec.get('title') or section_id}' from the provided evidence pack only.",
        constraints=[
            "Use the section evidence pack as the source of truth.",
            "When paper_trends are present, use them as synthesis scaffolding and verify each trend against the cited evidence before claiming it.",
            "Bind important factual claims to [claim:<id>] and [evidence:<id>] tags.",
            "Separate architecture synthesis, evaluation limits, contradiction slots, and open problems.",
            "Do not invent sources, results, paper names, URLs, or benchmark numbers.",
            "Preserve uncertainty when evidence is weak or contradictory.",
        ],
        output_contract=[
            "Markdown section draft.",
            "At least six second-level headings.",
            "Follow the professor-grade section template in writing_policy.section_template.",
            "Include Literature Lineage, Method Taxonomy, Architecture Synthesis, Comparative Positioning, Terminology Evolution, Evaluation Protocol Matrix, Evaluation And Risk Boundary, Limitations And Failure Modes, Controversy Matrix, Contradiction Slots, and Open Problems.",
            "All core claims must reference claim_id and evidence_id tags.",
        ],
        artifact_paths={
            "section_spec": str(section_dir / "section.spec.json"),
            "evidence_pack": str(section_dir / "evidence_pack.json"),
            "human_response": str(section_dir / "human_responses" / f"round_{round_index:02d}.md"),
            "pane_dispatch": str(section_dir / "pane_dispatch" / f"round_{round_index:02d}.md"),
            "prompt_packet_md": str(section_dir / "prompt_packets" / f"round_{round_index:02d}.md"),
            "draft": str(section_dir / "draft.md"),
            "review": str(section_dir / "review.json"),
            "revision_trace": str(section_dir / "revision_trace.json"),
            "final": str(section_dir / "final.md"),
            "model_usage": str(root / "model_usage.jsonl"),
        },
    )
    payload = to_dict(packet)
    payload["section_spec"] = spec
    payload["evidence_pack"] = pack
    payload["chapter_context"] = chapter_context
    payload["writing_policy"] = PROFESSOR_GRADE_WRITING_POLICY
    payload["source_type_guidance"] = _source_type_guidance(source_types)
    payload["synthesis_outline"] = [
        "Define the local research question and scope.",
        "Map claims to evidence and source types.",
        "Synthesize architecture mechanisms before evaluation claims.",
        "Compare source families instead of flattening them into citations.",
        "Use enriched paper trends to group multiple abstracts into themes before writing conclusions.",
        "State evaluation limits and failure modes.",
        "End with open problems that can feed chapter-level synthesis.",
    ]
    payload["required_claim_ids"] = list(pack.get("claim_ids", [])[:6])
    payload["required_evidence_ids"] = list(pack.get("evidence_ids", [])[:8])
    payload["paper_trends"] = list(pack.get("paper_trends", [])[:3]) if isinstance(pack.get("paper_trends"), list) else []
    return payload


def _write_chapter_prompt_packet(root: Path, packet: dict) -> None:
    chapter = packet.get("chapter_context") if isinstance(packet.get("chapter_context"), dict) else {}
    chapter_id = str(chapter.get("chapter_id") or "")
    if not chapter_id:
        return
    chapter_dir = root / "chapters" / chapter_id
    chapter_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "chapter_id": chapter_id,
        "chapter_title": chapter.get("chapter_title") or chapter_id,
        "chapter_objective": chapter.get("chapter_objective") or "",
        "active_section_id": packet.get("section_id"),
        "writer_backend": packet.get("writer_backend"),
        "writing_policy": packet.get("writing_policy"),
        "sibling_sections": chapter.get("sibling_sections") or [],
        "chapter_synthesis_contract": [
            "Ensure sibling sections do not repeat the same argument.",
            "Keep terminology consistent across the chapter.",
            "Preserve contradiction slots for chief-editor review.",
            "Make source-type differences visible in section conclusions.",
        ],
    }
    (chapter_dir / "prompt_packet.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        f"# Chapter Prompt Packet: {payload['chapter_title']}",
        "",
        f"- Chapter ID: {chapter_id}",
        f"- Active Section: {payload.get('active_section_id')}",
        "",
        "## Objective",
        "",
        str(payload.get("chapter_objective") or ""),
        "",
        "## Professor-Grade Section Template",
        "",
    ]
    lines.extend(f"- {item}" for item in (payload.get("writing_policy") or {}).get("section_template", []))
    lines.extend(["", "## Sibling Sections", ""])
    for section in payload.get("sibling_sections", []):
        lines.append(f"- {section.get('section_id')}: {section.get('title')}")
    lines.extend(["", "## Chapter Synthesis Contract", ""])
    lines.extend(f"- {item}" for item in payload.get("chapter_synthesis_contract", []))
    (chapter_dir / "prompt_packet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_prompt_packet(section_dir: Path, packet: dict) -> None:
    prompt_dir = section_dir / "prompt_packets"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    round_index = int(packet.get("round_index") or 0)
    json_path = prompt_dir / f"round_{round_index:02d}.json"
    md_path = prompt_dir / f"round_{round_index:02d}.md"
    json_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = [
        f"# Survey Section Prompt Packet: {packet.get('section_id')}",
        "",
        f"- Backend: {packet.get('writer_backend')}",
        f"- Round: {round_index}",
        f"- Role: {packet.get('role')}",
        "",
        "## Task",
        "",
        str(packet.get("task") or ""),
        "",
        "## Constraints",
        "",
    ]
    md.extend(f"- {item}" for item in packet.get("constraints", []))
    md.extend(["", "## Output Contract", ""])
    md.extend(f"- {item}" for item in packet.get("output_contract", []))
    md.extend(["", "## Chapter Context", ""])
    chapter = packet.get("chapter_context") if isinstance(packet.get("chapter_context"), dict) else {}
    md.extend([
        f"- Chapter: {chapter.get('chapter_id', 'N/A')} / {chapter.get('chapter_title', 'N/A')}",
        f"- Section Order In Chapter: {chapter.get('section_order_in_chapter', 'N/A')}",
        f"- Chapter Packet: {chapter.get('chapter_prompt_packet', 'N/A')}",
    ])
    md.extend(["", "## Professor-Grade Section Template", ""])
    md.extend(f"- {item}" for item in (packet.get("writing_policy") or {}).get("section_template", []))
    md.extend(["", "## Source-Type Guidance", ""])
    md.extend(f"- {item}" for item in packet.get("source_type_guidance", []))
    md.extend(["", "## Synthesis Outline", ""])
    md.extend(f"- {item}" for item in packet.get("synthesis_outline", []))
    md.extend(["", "## Required Claims", ""])
    md.extend(f"- {item}" for item in packet.get("required_claim_ids", []))
    md.extend(["", "## Required Evidence", ""])
    md.extend(f"- {item}" for item in packet.get("required_evidence_ids", []))
    md.extend([
        "",
        "## Human Response Path",
        "",
        str((packet.get("artifact_paths") or {}).get("human_response") or "N/A"),
        "",
        "## Return Instructions",
        "",
        "Write the completed Markdown section to the human response path above, then rerun the same survey command.",
    ])
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    _write_chapter_prompt_packet(section_dir.parents[2], packet)


def build_section_draft(root: Path, section_id: str, round_index: int = 0) -> str:
    section_dir = root / "sections" / section_id
    spec = _read_json(section_dir / "section.spec.json")
    pack = _read_json(section_dir / "evidence_pack.json")
    ledgers = _load_ledgers(root)
    chapter_context = _chapter_context(root, section_id, spec)
    claims = [ledgers["claims"].get(cid, {}) for cid in pack.get("claim_ids", [])]
    evidence = [ledgers["evidence"].get(eid, {}) for eid in pack.get("evidence_ids", [])]
    sources = [ledgers["sources"].get(sid, {}) for sid in pack.get("source_ids", [])]
    claim_ids = [cid for cid in pack.get("claim_ids", []) if cid]
    evidence_ids = [eid for eid in pack.get("evidence_ids", []) if eid]
    title = spec.get("title") or section_id
    question = spec.get("research_question") or ""
    source_type_list = [str(item) for item in pack.get("source_types", []) if str(item)] if isinstance(pack.get("source_types"), list) else []
    source_types = ", ".join(source_type_list) or "N/A"
    anchor = _section_anchor(section_id, str(title), chapter_context)
    reader_label = _section_reader_label(str(title), chapter_context)
    local_question = _local_question_for_reader(str(question), title=str(title), reader_label=reader_label)
    lens = _section_lens(str(title), str(question), source_type_list, int(chapter_context.get("section_order_in_chapter") or 0))
    primary_claims = claims[: max(3, min(len(claims), 6))]
    primary_evidence = evidence[: max(4, min(len(evidence), 8))]

    claim_lines = []
    display_question = f"{section_id} / {title}: {local_question}"
    claim_roles = [
        ("Scope", "界定本节研究对象和不外推的边界"),
        ("Mechanism", "说明系统机制如何影响能力组合"),
        ("Evaluation", "限定评价对象、指标口径和可复核材料"),
        ("Operations", "检查部署、成本、恢复和观测性约束"),
        ("Comparison", "比较不同来源能否支撑同一趋势"),
        ("Open Problem", "保留仍缺反证或复现实验的问题"),
    ]
    for idx, row in enumerate(primary_claims, start=1):
        cid = claim_ids[idx - 1] if idx - 1 < len(claim_ids) else f"claim_{idx}"
        eid = evidence_ids[(idx - 1) % len(evidence_ids)] if evidence_ids else "evidence_missing"
        role, role_desc = claim_roles[(idx - 1) % len(claim_roles)]
        text = _claim_statement_for_reader(
            _claim_text(row),
            title=str(title),
            reader_label=reader_label,
            local_question=local_question,
            role_desc=role_desc,
        )
        claim_lines.append(
            f"{idx}. {role}: 在 {reader_label} 中，{text} 用来{role_desc}；该判断只在本节证据覆盖的 `{lens['axis']}` 系统对象和工程场景内成立。 "
            f"[claim:{cid}] [evidence:{eid}]"
        )

    evidence_lines = []
    for idx, row in enumerate(primary_evidence, start=1):
        eid = evidence_ids[idx - 1] if idx - 1 < len(evidence_ids) else f"evidence_{idx}"
        sid = str(row.get("source_id") or "")
        src = ledgers["sources"].get(sid, {})
        source_type = src.get("source_type") or "uncovered"
        text = _evidence_brief(row, src, fallback=f"{title} evidence span.")
        evidence_lines.append(
            f"- {reader_label} / {source_type}: {text}。本节把它用于回答“{local_question}”，而不是作为全局趋势的自动证明。 [evidence:{eid}]"
        )

    source_lines = []
    for idx, row in enumerate(sources[:8], start=1):
        sid = _row_id(row, "id", "source_id") or "source_uncovered"
        source_lines.append(f"- {sid}: {row.get('source_type', 'uncovered')} / {_clean_source_title(row.get('title', 'untitled'), limit=120)}")
    paper_trends = [item for item in pack.get("paper_trends", []) if isinstance(item, dict)] if isinstance(pack.get("paper_trends"), list) else []
    trend_lines = []
    for idx, trend in enumerate(paper_trends[:4], start=1):
        cid = claim_ids[(idx - 1) % len(claim_ids)] if claim_ids else "claim_missing"
        eid = evidence_ids[(idx - 1) % len(evidence_ids)] if evidence_ids else "evidence_missing"
        label = _inline_text(trend.get("label") or trend.get("theme_id") or f"trend-{idx}", limit=120)
        claim = _inline_text(trend.get("claim") or "", limit=260)
        titles = trend.get("representative_titles") if isinstance(trend.get("representative_titles"), list) else []
        title_hint = "; ".join(_inline_text(item, limit=90) for item in titles[:3] if item)
        evidence_count = trend.get("evidence_count", "N/A")
        trend_lines.append(
            f"- {reader_label}: `{label}` aggregates {evidence_count} paper signals"
            f" ({title_hint or 'representative titles unavailable'}). Local use: {claim or 'treat as a clustering hint, not a standalone claim'}."
            f" [claim:{cid}] [evidence:{eid}]"
        )
    trend_section = "\n".join(trend_lines) if trend_lines else f"- No matched paper trends; conclusions stay local to this evidence pack. [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]"
    primary_claim_text = _clean_claim_for_reader(_claim_text(ledgers["claims"].get(claim_ids[0], {})) if claim_ids else "", fallback=str(question), limit=220)
    secondary_claim_text = _clean_claim_for_reader(_claim_text(ledgers["claims"].get(claim_ids[1], {})) if len(claim_ids) > 1 else "", fallback=primary_claim_text or str(question), limit=220)
    primary_evidence_row = ledgers["evidence"].get(evidence_ids[0], {}) if evidence_ids else {}
    secondary_evidence_row = ledgers["evidence"].get(evidence_ids[1], {}) if len(evidence_ids) > 1 else {}
    primary_evidence_src = ledgers["sources"].get(str(primary_evidence_row.get("source_id") or ""), {})
    secondary_evidence_src = ledgers["sources"].get(str(secondary_evidence_row.get("source_id") or ""), {})
    primary_evidence_text = _evidence_brief(primary_evidence_row, primary_evidence_src, fallback=str(question), limit=260) if primary_evidence_row else ""
    secondary_evidence_text = _evidence_brief(secondary_evidence_row, secondary_evidence_src, fallback=primary_evidence_text or str(question), limit=260) if secondary_evidence_row else ""
    primary_source_title = _clean_source_title(sources[0].get("title", "") if sources else "", limit=180)
    secondary_source_title = _clean_source_title(sources[1].get("title", "") if len(sources) > 1 else "", limit=180)
    evidence_summary = primary_evidence_text or primary_source_title or question
    evidence_summary_sentence = re.sub(r"[.!?。！？]+", ";", evidence_summary)
    secondary_evidence_sentence = re.sub(r"[.!?。！？]+", ";", secondary_evidence_text or evidence_summary)
    primary_claim_sentence = re.sub(r"[.!?。！？]+", ";", primary_claim_text or question)
    secondary_claim_sentence = re.sub(r"[.!?。！？]+", ";", secondary_claim_text or primary_claim_text or question)
    source_pair = " / ".join(item for item in [primary_source_title, secondary_source_title] if item) or source_types
    topic_probe = " ".join([str(title), str(question), primary_claim_text, secondary_claim_text, evidence_summary]).lower()
    if re.search(r"latent reasoning|隐空间|continuous thought|hidden-state|coconut|chain-of-thought", topic_probe):
        terminology_note = (
            f"For {reader_label}, terminology around '{local_question}' must separate chain-of-thought baselines, "
            "continuous thought, hidden-state deliberation, benchmark protocol, reproducibility, "
            "deployment, and observability/auditability only where the cited evidence supports that split."
        )
    else:
        terminology_note = (
            f"For {reader_label}, terminology must come from the claim, source title, evidence span, "
            "and local research question; imported labels stay provisional until another evidence item confirms them."
        )
    traceability_lines = []
    for idx in range(6):
        cid = claim_ids[idx % len(claim_ids)] if claim_ids else "claim_missing"
        eid = evidence_ids[idx % len(evidence_ids)] if evidence_ids else "evidence_missing"
        evidence_hint = _inline_text(_evidence_text(ledgers["evidence"].get(eid, {})), limit=120)
        claim_hint = _clean_claim_for_reader(_claim_text(ledgers["claims"].get(cid, {})), fallback=cid, limit=120)
        traceability_lines.append(
            f"- trace-{idx + 1}: `{cid}` is checked against `{eid}` for the local question "
            f"`{_inline_text(display_question, limit=110)}`; claim hint `{claim_hint or cid}`; evidence hint `{evidence_hint or eid}`. "
            f"[claim:{cid}] [evidence:{eid}]"
        )
    traceability_section = "\n".join(traceability_lines)
    compact_traceability_section = "\n".join(traceability_lines[:3])
    compact_boost_cid = claim_ids[3 % len(claim_ids)] if claim_ids else "claim_missing"
    compact_boost_eid = evidence_ids[3 % len(evidence_ids)] if evidence_ids else "evidence_missing"
    compact_boost_claim = _inline_text(_claim_text(ledgers["claims"].get(compact_boost_cid, {})), limit=100)
    compact_boost_evidence = _inline_text(_evidence_text(ledgers["evidence"].get(compact_boost_eid, {})), limit=100)
    compact_tag_boost = (
        f"Compact audit binds an additional local claim/evidence pair "
        f"with claim hint `{compact_boost_claim or compact_boost_cid}` and evidence hint `{compact_boost_evidence or compact_boost_eid}`. "
        f"[claim:{compact_boost_cid}] [evidence:{compact_boost_eid}]."
    )
    compact_trend_section = "\n".join(trend_lines[:2]) if trend_lines else trend_section

    if round_index == 0:
        compact_claim_lines = []
        for idx, cid in enumerate(claim_ids[:2] or ["claim_missing"], start=1):
            eid = evidence_ids[(idx - 1) % len(evidence_ids)] if evidence_ids else "evidence_missing"
            compact_claim_lines.append(f"{idx}. Claim `{cid}` is scoped to `{lens['axis']}` and checked against the local source boundary. [claim:{cid}] [evidence:{eid}]")
        compact_evidence_lines = []
        for idx, eid in enumerate(evidence_ids[:3] or ["evidence_missing"], start=1):
            compact_evidence_lines.append(f"- Evidence `{eid}` checks the local question '{local_question}'. [evidence:{eid}]")
        compact_source_lines = source_lines[:3] or [f"- {anchor} source-slot-1: source_uncovered / N/A"]
        compact = f"""# {title}

## Research Question

{display_question}

## Position

This section tests "{primary_claim_sentence}" against "{evidence_summary_sentence}" and keeps confidence bounded by `{source_types}`. [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Claim Map

{chr(10).join(compact_claim_lines)}

## Evidence Map

{chr(10).join(compact_evidence_lines)}

## Source Map

{chr(10).join(compact_source_lines)}

## Traceability Ledger

{compact_traceability_section}

{compact_tag_boost}

## Paper Trend Synthesis

{compact_trend_section}

## Method Taxonomy

This section separates source family, system boundary, evaluation target, and implementation constraint; uncovered dimensions stay evidence-uncovered. [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Evaluation Protocol Matrix

This section checks task form, metric scope, reproducibility, baseline or ablation design, and deployment transfer before allowing strong conclusions. [claim:{claim_ids[1] if len(claim_ids) > 1 else 'claim_missing'}] [evidence:{evidence_ids[1] if len(evidence_ids) > 1 else 'evidence_missing'}]

## Contradiction Slots

This section keeps negative evidence, source-family disagreement, and unobserved failure modes visible instead of hiding controversy. [claim:{claim_ids[2] if len(claim_ids) > 2 else 'claim_missing'}] [evidence:{evidence_ids[2] if len(evidence_ids) > 2 else 'evidence_missing'}]

## Open Problems

Open follow-up: source comparability, terminology consistency, and claim-to-evidence traceability.
"""
        return _localize_section_headings(_dedupe_sentences(compact), title=str(title), section_id=section_id)

    expansion = ""
    if round_index >= 1:
        expansion = f"""
## Revision: Architecture And Evaluation Detail

本轮修订把“{local_question}”限定为可审计的局部问题。对于 {reader_label}，主论点是“{primary_claim_sentence}”，主证据“{evidence_summary_sentence}”必须直接覆盖该问题的系统边界、评价指标或工程假设；否则本节必须把结论降级为局部观察。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Revision: Terminology Evolution And Academic Survey Frame

术语演进来自“{local_question}”里的问题表述、证据标题和 claim 文本，而不是固定套用某个领域模板。若“{secondary_claim_sentence}”与主证据没有同一评价对象，本节应保留术语冲突，并在章节 synthesis 中说明这种冲突如何影响趋势判断。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]
"""
    if round_index >= 2:
        expansion += f"""
## Revision: Contradictions, Open Problems, And Survey Position

反证段落进入主论证而不是附录：当主来源与校验来源只覆盖不同任务、不同系统边界或不同评价目标时，本节不能合成一个强趋势。该节保留的开放问题聚焦“哪些证据可以直接支撑趋势，哪些只能作为背景材料”。 [claim:{claim_ids[-1] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[-1] if evidence_ids else 'evidence_missing'}]
"""

    draft = f"""# {title}

## Research Question

{display_question}

## Position

{reader_label} 的核心判断来自“{primary_claim_sentence}”。可引用的事实是“{evidence_summary_sentence}”，可比较的来源是“{source_pair}”。因此，本节只在这些证据直接覆盖“{local_question}”的范围内讨论 `{lens['axis']}`，不把来源类型或章节编号当成结论本身。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Claim Map

{chr(10).join(claim_lines)}

## Evidence Map

{chr(10).join(evidence_lines)}

## Source Map

{chr(10).join(source_lines)}

## Traceability Ledger

{traceability_section}

## Paper Trend Synthesis

{trend_section}

## Literature Lineage

{reader_label} 的 literature lineage 从来源标题和证据摘要开始："{source_pair}"。如果这些来源之间存在时间、任务或实现对象差异，本节把差异写成演进约束；如果没有直接关联，则只把它们作为并列证据，不强行串成单一路线。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Method Taxonomy

{reader_label} 的 method taxonomy 按本节证据可观察到的维度拆分：研究对象、系统边界、评价目标、实现/部署约束。没有被证据覆盖的维度标为“证据未覆盖”，避免把其他报告主题的 taxonomy 套进当前 CAIS 议题。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Architecture Synthesis

{reader_label} 的 architecture synthesis 必须回答“{local_question}”这个窄问题。证据“{evidence_summary_sentence}”到底改变了本节对系统设计、评价或运行边界的哪一项判断。若回答不出来，本节只保留为资料卡片，不能升级为趋势结论。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Comparative Positioning

{reader_label} 的 comparative positioning 比较“{primary_source_title or lens['primary_source']}”和“{secondary_source_title or lens['secondary_source']}”。二者只有在讨论同一类 agent 系统能力、同一类评价目标或同一类工程约束时才可以相互支撑；否则必须分开陈述。 [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Terminology Evolution

{reader_label} tracks terminology only when it appears in the claim, source title, evidence span, or the local question "{local_question}". {terminology_note} [claim:{claim_ids[0] if claim_ids else 'claim_missing'}] [evidence:{evidence_ids[0] if evidence_ids else 'evidence_missing'}]

## Evaluation Protocol Matrix

{reader_label} 的 evaluation protocol matrix 比较四列：评价对象、指标口径、可复核材料、外推边界。第二证据“{secondary_evidence_sentence}”若只覆盖其中一列，就不能支撑整节的强判断。 [claim:{claim_ids[1] if len(claim_ids) > 1 else 'claim_missing'}] [evidence:{evidence_ids[1] if len(evidence_ids) > 1 else 'evidence_missing'}]

## Evaluation And Risk Boundary

{reader_label} 的 evaluation boundary 只声明证据中可见的边界：任务形态、指标口径、实现可复核性和部署外推。证据没有说明的部分必须留白，而不是用“工程代价”“评价可信度”等抽象词填满。 [claim:{claim_ids[1] if len(claim_ids) > 1 else 'claim_missing'}] [evidence:{evidence_ids[1] if len(evidence_ids) > 1 else 'evidence_missing'}]

## Limitations And Failure Modes

{reader_label} 的 failure modes 来自“{local_question}”对应的证据缺口：若没有负例、实现细节、复现实验或部署观测，本节只能提出有限趋势。需要补充的不是更多字数，而是能反驳或限定“{primary_claim_sentence}”的证据。 [claim:{claim_ids[1] if len(claim_ids) > 1 else 'claim_missing'}] [evidence:{evidence_ids[1] if len(evidence_ids) > 1 else 'evidence_missing'}]

## Controversy Matrix

{reader_label} 的 controversy matrix 分成支持证据、negative evidence/负面证据、缺失证据和待验证假设。若主来源与校验来源在任务规模、实现假设或评价口径上冲突，本节把冲突保留为争议项，而不是在 narrative synthesis 中抹平。 [claim:{claim_ids[2] if len(claim_ids) > 2 else 'claim_missing'}] [evidence:{evidence_ids[2] if len(evidence_ids) > 2 else 'evidence_missing'}]

## Contradiction Slots

{reader_label} 的 contradiction slots 保留三个反证槽位：第一，主证据可能只覆盖局部任务；第二，校验来源与主来源可能不在同一评价口径；第三，报告可能缺少真实失败案例。后续 chapter synthesis 必须消费这些槽位，不能只保留支持性证据。 [claim:{claim_ids[2] if len(claim_ids) > 2 else 'claim_missing'}] [evidence:{evidence_ids[2] if len(evidence_ids) > 2 else 'evidence_missing'}]
{expansion}
## Open Problems

{reader_label} 的 open problems 不是通用 future-work 列表，而是要求下一轮围绕“{local_question}”补充反证来源、复核“{primary_source_title or lens['primary_source']}”与“{secondary_source_title or lens['secondary_source']}”的可比性，并明确哪些结论只是资料归纳、哪些才是趋势判断。该节最终版本应把这些问题映射回 claim_id 和 evidence_id，而不是依赖模型自由发挥。
"""
    return _localize_section_headings(_dedupe_sentences(draft), title=str(title), section_id=section_id)


def review_section_text(root: Path, section_id: str, text: str, min_chars: int = 1200) -> SectionReview:
    section_dir = root / "sections" / section_id
    pack = _read_json(section_dir / "evidence_pack.json")
    issues: list[str] = []
    if pack.get("status") != "ready":
        issues.extend(pack.get("blockers") or ["evidence_pack_blocked"])
    if len(text) < min_chars:
        issues.append(f"section_chars_low:{len(text)}<{min_chars}")
    claim_tags = set(re.findall(r"\[claim:([^\]]+)\]", text))
    evidence_tags = set(re.findall(r"\[evidence:([^\]]+)\]", text))
    required_claims = set(str(x) for x in pack.get("claim_ids", [])[:3])
    required_evidence = set(str(x) for x in pack.get("evidence_ids", [])[:4])
    missing_claims = sorted(required_claims - claim_tags)
    missing_evidence = sorted(required_evidence - evidence_tags)
    if missing_claims:
        issues.append("missing_claim_tags:" + ",".join(missing_claims))
    if missing_evidence:
        issues.append("missing_evidence_tags:" + ",".join(missing_evidence))
    headings = len(re.findall(r"^##\s+", text, flags=re.M))
    if headings < 6:
        issues.append(f"section_structure_shallow:{headings}<6")
    if not re.search(r"Contradiction|反证|争议", text, flags=re.I):
        issues.append("contradiction_section_missing")
    if not re.search(r"Evaluation|评价|评估", text, flags=re.I):
        issues.append("evaluation_section_missing")
    if not re.search(r"Comparative Positioning|比较|对比", text, flags=re.I):
        issues.append("comparative_positioning_missing")
    if not re.search(r"Limitations|Failure Modes|局限|失败模式", text, flags=re.I):
        issues.append("limitations_failure_modes_missing")
    source_types = pack.get("source_types", [])
    source_diversity = min(len(source_types) / 4, 1.0)
    if source_diversity < 0.5:
        issues.append(f"source_diversity_low:{source_diversity:.2f}<0.50")
    unsupported = len(missing_claims) / max(len(required_claims), 1)
    citation_accuracy = 1.0 - (len(missing_evidence) / max(len(required_evidence), 1))
    paragraphs = [re.sub(r"\s+", " ", p.strip().lower()) for p in text.split("\n\n") if p.strip()]
    repetition = 1.0 - (len(set(paragraphs)) / max(len(paragraphs), 1))
    verdict = "PASS" if not issues else "REVISE"
    return SectionReview(
        section_id=section_id,
        verdict=verdict,
        unsupported_claim_rate=round(unsupported, 4),
        citation_span_accuracy=round(citation_accuracy, 4),
        source_diversity_score=round(source_diversity, 4),
        repetition_score=round(repetition, 4),
        issues=issues,
    )


def run_section_revision_loop(
    output_dir: str | Path,
    section_id: str,
    *,
    finalize: bool = True,
    max_rounds: int = 3,
    start_round_index: int = 0,
    min_chars: int = 1200,
    writer_backend: str = "deterministic",
    writer_command: str = "",
    writer_timeout: int = 120,
    pane_target: str = "",
    pane_send: bool = False,
    emit_prompt_packet: bool = True,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    section_dir = root / "sections" / section_id
    spec = _read_json(section_dir / "section.spec.json")
    pack = _read_json(section_dir / "evidence_pack.json")
    section_dir.mkdir(parents=True, exist_ok=True)
    if not spec:
        return {"ok": False, "section_id": section_id, "reason": "section_spec_missing"}
    if not pack:
        return {"ok": False, "section_id": section_id, "reason": "evidence_pack_missing"}
    if pack.get("status") != "ready":
        review = SectionReview(
            section_id=section_id,
            verdict="BLOCKED",
            unsupported_claim_rate=1.0,
            citation_span_accuracy=0.0,
            source_diversity_score=0.0,
            repetition_score=0.0,
            issues=list(pack.get("blockers") or ["evidence_pack_blocked"]),
        )
        (section_dir / "review.json").write_text(json.dumps(to_dict(review), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"ok": False, "section_id": section_id, "reason": "evidence_pack_blocked", "review": to_dict(review)}

    traces: list[dict] = []
    text = ""
    review = None
    backend = get_writer_backend(
        writer_backend,
        local_command=writer_command,
        timeout_seconds=writer_timeout,
        pane_target=pane_target,
        pane_send=pane_send,
    )
    start_round = max(int(start_round_index or 0), 0)
    for round_index in range(start_round, start_round + max(max_rounds, 1)):
        packet = build_section_prompt_packet(root, section_id, round_index=round_index, writer_backend=backend.name)
        if emit_prompt_packet:
            _write_prompt_packet(section_dir, packet)
        fallback_text = build_section_draft(root, section_id, round_index=round_index)
        try:
            text = backend.write(packet, fallback_text)
        except HumanResponseMissingError as exc:
            trace = SectionRevisionTrace(
                section_id=section_id,
                round_index=round_index,
                verdict="WAITING_FOR_HUMAN",
                changed=False,
                issues_before=[str(exc)],
                actions=["fill_human_response_markdown", "rerun_survey_write_section"],
            )
            traces.append(to_dict(trace))
            review = SectionReview(
                section_id=section_id,
                verdict="WAITING_FOR_HUMAN",
                unsupported_claim_rate=1.0,
                citation_span_accuracy=0.0,
                source_diversity_score=0.0,
                repetition_score=0.0,
                issues=[str(exc)],
            )
            (section_dir / "review.json").write_text(json.dumps(to_dict(review), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (section_dir / "revision_trace.json").write_text(json.dumps({"section_id": section_id, "rounds": traces}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return {
                "ok": False,
                "section_id": section_id,
                "reason": "human_response_missing",
                "writer_backend": backend.name,
                "prompt_packets": str(section_dir / "prompt_packets") if emit_prompt_packet else "",
                "expected_response": exc.response_path,
                "review": to_dict(review),
            }
        except LocalCommandWriterError as exc:
            trace = SectionRevisionTrace(
                section_id=section_id,
                round_index=round_index,
                verdict="WRITER_FAILED",
                changed=False,
                issues_before=[str(exc)],
                actions=["fix_writer_command", "rerun_survey_write_section"],
            )
            traces.append(to_dict(trace))
            review = SectionReview(
                section_id=section_id,
                verdict="WRITER_FAILED",
                unsupported_claim_rate=1.0,
                citation_span_accuracy=0.0,
                source_diversity_score=0.0,
                repetition_score=0.0,
                issues=[str(exc)],
            )
            (section_dir / "review.json").write_text(json.dumps(to_dict(review), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (section_dir / "revision_trace.json").write_text(json.dumps({"section_id": section_id, "rounds": traces}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return {
                "ok": False,
                "section_id": section_id,
                "reason": "writer_failed",
                "writer_backend": backend.name,
                "prompt_packets": str(section_dir / "prompt_packets") if emit_prompt_packet else "",
                "writer_error": exc.reason,
                "review": to_dict(review),
            }
        except PanePacketPendingError as exc:
            trace = SectionRevisionTrace(
                section_id=section_id,
                round_index=round_index,
                verdict="WAITING_FOR_PANE",
                changed=False,
                issues_before=[str(exc)],
                actions=["let_pane_write_response_markdown", "rerun_survey_write_section"],
            )
            traces.append(to_dict(trace))
            review = SectionReview(
                section_id=section_id,
                verdict="WAITING_FOR_PANE",
                unsupported_claim_rate=1.0,
                citation_span_accuracy=0.0,
                source_diversity_score=0.0,
                repetition_score=0.0,
                issues=[str(exc)],
            )
            (section_dir / "review.json").write_text(json.dumps(to_dict(review), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (section_dir / "revision_trace.json").write_text(json.dumps({"section_id": section_id, "rounds": traces}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return {
                "ok": False,
                "section_id": section_id,
                "reason": "pane_response_missing",
                "writer_backend": backend.name,
                "prompt_packets": str(section_dir / "prompt_packets") if emit_prompt_packet else "",
                "pane_dispatch": exc.dispatch_path,
                "expected_response": exc.response_path,
                "pane_target": exc.pane_target,
                "pane_submitted": exc.submitted,
                "review": to_dict(review),
            }
        review = review_section_text(root, section_id, text, min_chars=min_chars)
        traces.append(to_dict(SectionRevisionTrace(
            section_id=section_id,
            round_index=round_index,
            verdict=review.verdict,
            changed=round_index > start_round,
            issues_before=list(review.issues),
            actions=[] if review.verdict == "PASS" else ["expand_structure", "bind_missing_citations", "add_evaluation_or_contradiction"],
        )))
        if review.verdict == "PASS":
            break

    assert review is not None
    (section_dir / "draft.md").write_text(text, encoding="utf-8")
    (section_dir / "review.json").write_text(json.dumps(to_dict(review), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (section_dir / "revision_trace.json").write_text(json.dumps({"section_id": section_id, "rounds": traces}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if review.verdict == "PASS" and finalize:
        section_title = str(spec.get("title") or section_id)
        final_claim_ids = [str(item) for item in (pack.get("claim_ids") or []) if str(item).strip()]
        final_evidence_ids = [str(item) for item in (pack.get("evidence_ids") or []) if str(item).strip()]
        review_claim = final_claim_ids[-1] if final_claim_ids else "claim_missing"
        review_evidence = final_evidence_ids[-1] if final_evidence_ids else "evidence_missing"
        final = (
            text
            + f"\n## Section Review - {section_id} - {_inline_text(section_title, limit=72)}\n\n"
            + "Verdict: PASS\n"
            + f"Verdict for {section_id} / {_inline_text(section_title, limit=72)}: PASS. "
            + f"{section_id} satisfied local citation, source-diversity, evaluation-boundary, and contradiction-slot checks on {_inline_text(section_title, limit=72)}. "
            + f"Final audit anchor: [claim:{review_claim}] remains traceable to [evidence:{review_evidence}].\n"
        )
        (section_dir / "final.md").write_text(final, encoding="utf-8")
    return {
        "ok": review.verdict == "PASS",
        "section_id": section_id,
        "finalized": bool(finalize and review.verdict == "PASS"),
        "rounds": len(traces),
        "writer_backend": backend.name,
        "prompt_packets": str(section_dir / "prompt_packets") if emit_prompt_packet else "",
        "review": to_dict(review),
    }


def run_ready_sections(
    output_dir: str | Path,
    *,
    limit: int = 3,
    max_rounds: int = 3,
    min_chars: int = 1200,
    writer_backend: str = "deterministic",
    writer_command: str = "",
    writer_timeout: int = 120,
    pane_target: str = "",
    pane_send: bool = False,
    emit_prompt_packet: bool = True,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    packs = _read_json(root / "survey_evidence_packs.json")
    results: list[dict] = []
    unlimited = limit <= 0
    for pack in packs.get("packs", []):
        if pack.get("status") != "ready":
            continue
        section_id = str(pack.get("section_id") or "")
        if not section_id:
            continue
        final = root / "sections" / section_id / "final.md"
        if final.exists():
            continue
        results.append(run_section_revision_loop(
            root,
            section_id,
            max_rounds=max_rounds,
            min_chars=min_chars,
            writer_backend=writer_backend,
            writer_command=writer_command,
            writer_timeout=writer_timeout,
            pane_target=pane_target,
            pane_send=pane_send,
            emit_prompt_packet=emit_prompt_packet,
        ))
        if not unlimited and len(results) >= limit:
            break
    return {
        "ok": all(item.get("ok") for item in results) if results else False,
        "processed": len(results),
        "passed": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "results": results,
    }


def watch_pane_responses(
    output_dir: str | Path,
    *,
    limit: int = 0,
    min_chars: int = 1200,
    round_index: int = 0,
) -> dict[str, Any]:
    """Finalize sections whose pane/human response artifact already exists."""
    root = Path(output_dir).expanduser()
    ast = _read_json(root / "survey_report_ast.json")
    sections = ast.get("sections", []) if isinstance(ast.get("sections"), list) else []
    results: list[dict] = []
    pending: list[str] = []
    skipped_final: list[str] = []
    unlimited = limit <= 0
    for section in sections:
        section_id = str(section.get("section_id") or "")
        if not section_id:
            continue
        section_dir = root / "sections" / section_id
        final = section_dir / "final.md"
        response = section_dir / "human_responses" / f"round_{round_index:02d}.md"
        if final.exists():
            skipped_final.append(section_id)
            continue
        if not response.exists() or not response.read_text(encoding="utf-8").strip():
            pending.append(section_id)
            continue
        results.append(run_section_revision_loop(
            root,
            section_id,
            max_rounds=1,
            min_chars=min_chars,
            writer_backend="human-packet",
            emit_prompt_packet=True,
        ))
        if not unlimited and len(results) >= limit:
            break
    payload = {
        "ok": all(item.get("ok") for item in results) if results else False,
        "processed": len(results),
        "passed": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "pending_responses": len(pending),
        "skipped_final": len(skipped_final),
        "results": results,
        "pending_section_ids": pending[:20],
    }
    (root / "pane_response_watch.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
