"""Survey-specific source gap detection and human-search handoff rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


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


def assess_source_gap(
    output_dir: str | Path,
    *,
    brief: str = "",
    min_sources: int = 4,
    min_evidence: int = 8,
    min_claims: int = 8,
    required_source_types: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    ast = _read_json(root / "survey_report_ast.json")
    source_matrix = _read_json(root / "survey_source_matrix.json")
    matrix_rows = source_matrix.get("source_matrix") if isinstance(source_matrix.get("source_matrix"), list) else source_matrix
    required = set(required_source_types or [])
    if isinstance(matrix_rows, list):
        for row in matrix_rows:
            if not isinstance(row, dict):
                continue
            required.update(str(item) for item in row.get("required_source_types", []) if item)
    if not required:
        required.update(["paper", "official_doc", "code", "benchmark"])
    sources = _read_jsonl(root / "sources.jsonl")
    evidence = _read_jsonl(root / "evidence.jsonl")
    claims = _read_jsonl(root / "claims.jsonl")
    observed_types = {str(row.get("source_type") or "") for row in sources if row.get("source_type")}
    source_type_counts: dict[str, int] = {}
    for row in sources:
        source_type = str(row.get("source_type") or "unknown")
        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
    missing_types = sorted(required - observed_types)
    issues: list[str] = []
    if len(sources) < min_sources:
        issues.append(f"source_count_low:{len(sources)}<{min_sources}")
    if len(evidence) < min_evidence:
        issues.append(f"evidence_count_low:{len(evidence)}<{min_evidence}")
    if len(claims) < min_claims:
        issues.append(f"claim_count_low:{len(claims)}<{min_claims}")
    if missing_types:
        issues.append("missing_source_types:" + ",".join(missing_types))
    payload = {
        "ok": not issues,
        "brief": brief or ast.get("title") or root.name,
        "output_dir": str(root),
        "source_count": len(sources),
        "evidence_count": len(evidence),
        "claim_count": len(claims),
        "source_type_counts": source_type_counts,
        "required_source_types": sorted(required),
        "missing_source_types": missing_types,
        "issues": issues,
        "handoff_path": str(root / "survey_source_gap_handoff.md"),
    }
    (root / "survey_source_gap.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def render_source_gap_handoff(gap: dict[str, Any], *, max_results: int = 12) -> str:
    brief = str(gap.get("brief") or "N/A")
    missing = list(gap.get("missing_source_types") or [])
    if not missing:
        missing = list(gap.get("required_source_types") or ["paper", "official_doc", "code", "benchmark"])
    query_plan = "\n".join(
        f"| {source_type} | 2 | `{brief} {source_type} primary source architecture evaluation` |"
        for source_type in missing
    )
    issues = "\n".join(f"- {item}" for item in gap.get("issues", [])) or "- N/A"
    return f"""# Solar DeepResearch Survey Source Gap Handoff

你现在扮演外部搜索研究员。请联网搜索并返回可导入 Solar DeepResearch 的 Markdown。不要写最终报告，只补证据。

## Survey Brief
{brief}

## Current Gap
- Output dir: `{gap.get("output_dir", "")}`
- Sources: `{gap.get("source_count", 0)}`
- Evidence: `{gap.get("evidence_count", 0)}`
- Claims: `{gap.get("claim_count", 0)}`
- Required source types: `{", ".join(gap.get("required_source_types") or [])}`
- Missing source types: `{", ".join(missing)}`
- Issues:
{issues}

## Query Plan

| Source Type | Min Results | Query |
|---|---:|---|
{query_plan}

## Rules
- Return at most {max_results} high-quality sources.
- Prefer primary/canonical sources: papers, official docs, GitHub repos, benchmarks, standards, model cards.
- Do not invent links, paper names, benchmark numbers, or quotes.
- Include contradiction/negative evidence when found.
- Keep summaries factual and citation-ready.
- Use Source Type values: `paper`, `official_doc`, `code`, `benchmark`, `dataset`, `standard`, `web`, `other`.

## Required Return Format

```markdown
# External Search Results: {brief}

## Source 1: <title>
URL: <https://...>
Publisher: <publisher or N/A>
Published: <date or N/A>
Source Type: <paper|official_doc|code|benchmark|dataset|standard|web|other>

Summary:
- <2-5 factual bullets>

Key Claims:
- <claim supported by this source>
- <claim supported by this source>

Relevant Quotes:
> <short quote or N/A>

Why this source fixes the gap:
- <which missing source type or claim gap it covers>
```
"""


def write_source_gap_handoff(
    output_dir: str | Path,
    *,
    brief: str = "",
    min_sources: int = 4,
    min_evidence: int = 8,
    min_claims: int = 8,
    required_source_types: list[str] | None = None,
    max_results: int = 12,
) -> dict[str, Any]:
    gap = assess_source_gap(
        output_dir,
        brief=brief,
        min_sources=min_sources,
        min_evidence=min_evidence,
        min_claims=min_claims,
        required_source_types=required_source_types,
    )
    path = Path(gap["handoff_path"]).expanduser()
    path.write_text(render_source_gap_handoff(gap, max_results=max_results), encoding="utf-8")
    gap["handoff_written"] = True
    (Path(output_dir).expanduser() / "survey_source_gap.json").write_text(json.dumps(gap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return gap
