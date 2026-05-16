"""Import human/Gemini/GPT search Markdown into survey ledger JSONL files."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SOURCE_TYPE_ALIASES = {
    "official": "official_doc",
    "official docs": "official_doc",
    "official_doc": "official_doc",
    "documentation": "official_doc",
    "repo": "code",
    "repository": "code",
    "github": "code",
    "paper": "paper",
    "arxiv": "paper",
    "benchmark": "benchmark",
    "dataset": "dataset",
    "standard": "standard",
    "web": "web",
    "other": "other",
}


def _stable_id(prefix: str, *parts: str) -> str:
    text = "\n".join(parts)
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _normalize_source_type(value: str) -> str:
    cleaned = re.sub(r"[<>|].*$", "", str(value or "")).strip().lower()
    return SOURCE_TYPE_ALIASES.get(cleaned, cleaned if cleaned in set(SOURCE_TYPE_ALIASES.values()) else "web")


def _field(block: str, name: str) -> str:
    match = re.search(rf"(?im)^{re.escape(name)}:\s*(.+)$", block)
    return match.group(1).strip() if match else ""


def _section_lines(block: str, heading: str) -> list[str]:
    pattern = rf"(?ims)^{re.escape(heading)}:\s*\n(.*?)(?=^\w[\w ]+:\s*$|^##\s+Source\s+\d+\s*:|\Z)"
    match = re.search(pattern, block)
    if not match:
        return []
    lines: list[str] = []
    for line in match.group(1).splitlines():
        item = line.strip()
        if not item:
            continue
        item = re.sub(r"^[-*>]\s*", "", item).strip()
        if item and item.upper() != "N/A":
            lines.append(item)
    return lines


def parse_survey_search_markdown(markdown: str) -> list[dict[str, Any]]:
    text = markdown or ""
    blocks = re.split(r"(?im)^##\s+Source\s+\d+\s*:\s*", text)
    records: list[dict[str, Any]] = []
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip(" #\t") or "External search source"
        url = _field(block, "URL")
        if not url:
            urls = re.findall(r"https?://[^\s>)]+", block)
            url = urls[0] if urls else ""
        url = url.strip("<>")
        if not url:
            continue
        source_type = _normalize_source_type(_field(block, "Source Type") or "web")
        summary = _section_lines(block, "Summary")
        key_claims = _section_lines(block, "Key Claims")
        quotes = _section_lines(block, "Relevant Quotes")
        if not key_claims:
            key_claims = summary[:2] or [title]
        content = "\n".join([
            f"Title: {title}",
            f"URL: {url}",
            f"Publisher: {_field(block, 'Publisher') or 'N/A'}",
            f"Published: {_field(block, 'Published') or 'N/A'}",
            "",
            "Summary:",
            *[f"- {item}" for item in summary],
            "",
            "Key Claims:",
            *[f"- {item}" for item in key_claims],
            "",
            "Relevant Quotes:",
            *[f"> {item}" for item in quotes],
        ]).strip()
        records.append({
            "title": title,
            "url": url,
            "publisher": _field(block, "Publisher") or "",
            "published": _field(block, "Published") or "",
            "source_type": source_type,
            "summary": summary,
            "key_claims": key_claims,
            "quotes": quotes,
            "content": content,
        })
    return records


def import_survey_search_results(
    output_dir: str | Path,
    input_md: str | Path,
    *,
    continue_finalize: bool = False,
    brief: str = "",
    section_limit: int = 3,
    repair_limit: int = 0,
    min_finalized: int | None = None,
    min_chars: int = 1200,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    markdown = Path(input_md).expanduser().read_text(encoding="utf-8")
    records = parse_survey_search_markdown(markdown)
    if not records:
        payload = {"ok": False, "reason": "no_importable_sources", "imported_sources": 0}
        (root / "survey_import_search_results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return payload

    sources = _read_jsonl(root / "sources.jsonl")
    evidence = _read_jsonl(root / "evidence.jsonl")
    claims = _read_jsonl(root / "claims.jsonl")
    links = _read_jsonl(root / "claim_evidence.jsonl")
    existing_urls = {str(row.get("url") or "") for row in sources}
    imported_sources = 0
    imported_evidence = 0
    imported_claims = 0
    imported_links = 0
    for rec in records:
        source_id = _stable_id("src", rec["url"])
        if rec["url"] not in existing_urls:
            sources.append({
                "id": source_id,
                "source_id": source_id,
                "url": rec["url"],
                "title": rec["title"],
                "source_type": rec["source_type"],
                "publisher": rec.get("publisher") or "",
                "published_at": rec.get("published") or "",
                "content_hash": _stable_id("hash", rec["content"]),
            })
            existing_urls.add(rec["url"])
            imported_sources += 1
        for claim_text in rec["key_claims"]:
            evidence_text = "\n".join([
                f"Source: {rec['title']}",
                f"URL: {rec['url']}",
                f"Claim: {claim_text}",
                "",
                rec["content"],
            ]).strip()
            evidence_id = _stable_id("ev", rec["url"], claim_text)
            if not any(str(row.get("id") or row.get("evidence_id")) == evidence_id for row in evidence):
                evidence.append({
                    "id": evidence_id,
                    "evidence_id": evidence_id,
                    "source_id": source_id,
                    "content": evidence_text,
                    "span_text": evidence_text,
                    "evidence_type": "human_search_claim_span",
                    "confidence": 0.75,
                    "span_start": 0,
                    "span_end": len(evidence_text),
                    "content_hash": _stable_id("hash", evidence_text),
                })
                imported_evidence += 1
            claim_id = _stable_id("cl", rec["url"], claim_text)
            if not any(str(row.get("id") or row.get("claim_id")) == claim_id for row in claims):
                claims.append({
                    "id": claim_id,
                    "claim_id": claim_id,
                    "claim_text": claim_text,
                    "text": claim_text,
                    "claim_type": "factual",
                    "stance": "support",
                    "confidence": 0.75,
                    "section_ref": "",
                    "content_hash": _stable_id("hash", claim_text),
                })
                imported_claims += 1
            link_id = _stable_id("link", claim_id, evidence_id)
            if not any(str(row.get("id")) == link_id for row in links):
                links.append({
                    "id": link_id,
                    "claim_id": claim_id,
                    "evidence_id": evidence_id,
                    "relation": "supports",
                    "strength": 0.75,
                })
                imported_links += 1

    _write_jsonl(root / "sources.jsonl", sources)
    _write_jsonl(root / "evidence.jsonl", evidence)
    _write_jsonl(root / "claims.jsonl", claims)
    _write_jsonl(root / "claim_evidence.jsonl", links)
    payload: dict[str, Any] = {
        "ok": True,
        "records_parsed": len(records),
        "imported_sources": imported_sources,
        "imported_evidence": imported_evidence,
        "imported_claims": imported_claims,
        "imported_links": imported_links,
        "sources_path": str(root / "sources.jsonl"),
        "evidence_path": str(root / "evidence.jsonl"),
        "claims_path": str(root / "claims.jsonl"),
        "claim_evidence_path": str(root / "claim_evidence.jsonl"),
        "run_path": str(root / "survey_import_search_results.json"),
    }
    if continue_finalize:
        from .finalize_run import finalize_survey_run

        payload["finalize"] = finalize_survey_run(
            root,
            brief=brief,
            skip_plan=(root / "survey_report_ast.json").exists(),
            skip_pack=False,
            section_limit=section_limit,
            repair_limit=repair_limit,
            min_finalized=min_finalized,
            min_chars=min_chars,
        )
    (root / "survey_import_search_results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
