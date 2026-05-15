"""Deterministic quality gate for DeepResearch artifacts.

This is intentionally model-free. The model evaluator can still write the
human-readable judgement, but it must not PASS a DeepResearch node unless this
gate can read the research_eval/report_ast/final artifacts and they satisfy the
minimum evidence/citation constraints.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_MAX_UNSUPPORTED_RATE = 0.05
DEFAULT_MIN_CITATION_ACCURACY = 0.95
DEFAULT_MIN_EXPERT_NOVELTY_RATIO = 0.45
DEFAULT_MIN_EXPERT_INSIGHT_DENSITY = 0.20
DEFAULT_MIN_EXPERT_INSIGHT_LINES = 5
DEFAULT_MIN_SECTION_CITATIONS = 1
DEFAULT_MIN_SECTION_ANALYSIS_DENSITY = 0.12
DEFAULT_MIN_SOURCE_TYPE_COUNT = 1
DEFAULT_WARN_SOURCE_TYPE_COUNT = 2
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / "policies" / "source_authority.json"

RESEARCH_PROFILES: dict[str, dict[str, Any]] = {
    "general": {
        "min_source_types": 1,
        "warn_source_types": 2,
        "required_source_types": set(),
        "warn_missing_source_types": set(),
        "min_covered_section_ratio": 1.0,
        "max_low_analysis_density_ratio": 1.0,
        "min_authority_score": 0.3,
        "min_high_authority_sources": 0,
    },
    "technical_architecture": {
        "min_source_types": 2,
        "warn_source_types": 3,
        "required_source_types": {"paper"},
        "warn_missing_source_types": {"code", "official_doc", "benchmark"},
        "min_covered_section_ratio": 1.0,
        "max_low_analysis_density_ratio": 0.5,
        "min_authority_score": 0.55,
        "min_high_authority_sources": 2,
    },
    "scientific_review": {
        "min_source_types": 2,
        "warn_source_types": 3,
        "required_source_types": {"paper"},
        "warn_missing_source_types": {"dataset", "benchmark"},
        "min_covered_section_ratio": 1.0,
        "max_low_analysis_density_ratio": 0.7,
        "min_authority_score": 0.65,
        "min_high_authority_sources": 2,
    },
    "market_landscape": {
        "min_source_types": 3,
        "warn_source_types": 4,
        "required_source_types": {"official_doc"},
        "warn_missing_source_types": {"news", "company", "benchmark"},
        "min_covered_section_ratio": 1.0,
        "max_low_analysis_density_ratio": 0.6,
        "min_authority_score": 0.55,
        "min_high_authority_sources": 2,
    },
}

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{3,}|[\u4e00-\u9fff]{2,}")
ANALYSIS_TERMS_RE = re.compile(
    r"(?i)\b("
    r"architecture|architectural|design|runtime|projection|audit|gate|roadmap|"
    r"implement|implementation|deploy|deployment|evaluate|evaluation|risk|"
    r"tradeoff|trade-off|requires?|should|must|policy|boundary|failure|"
    r"integration|orchestration|pipeline"
    r")\b|架构|设计|运行时|投影|审计|门禁|路线图|实现|部署|评估|风险|取舍|边界|失败|集成|编排|管线"
)
BOILERPLATE_LINE_RE = re.compile(
    r"(?i)^\s*(#|[-*]\s*\*\*P[0-9]\*\*:|\||source:|url:|publisher:|published:|bibliography|references?)"
)
VALIDATED_SOURCE_TYPES = {"paper", "code", "official_doc", "benchmark"}
HIGH_AUTHORITY_THRESHOLD = 0.75


def _normalize_policy_profile(profile: dict[str, Any]) -> dict[str, Any]:
    out = dict(profile)
    out["required_source_types"] = set(out.get("required_source_types") or [])
    out["warn_missing_source_types"] = set(out.get("warn_missing_source_types") or [])
    return out


def _load_policy() -> dict[str, Any]:
    path = Path(os.environ.get("SOLAR_RESEARCH_POLICY_PATH") or DEFAULT_POLICY_PATH).expanduser()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        profiles = raw.get("profiles") if isinstance(raw, dict) else None
        if not isinstance(profiles, dict) or not profiles:
            raise ValueError("policy has no profiles")
        normalized_profiles = {
            str(name).strip().lower().replace("-", "_"): _normalize_policy_profile(profile)
            for name, profile in profiles.items()
            if isinstance(profile, dict)
        }
        if "general" not in normalized_profiles:
            normalized_profiles["general"] = _normalize_policy_profile(RESEARCH_PROFILES["general"])
        raw["profiles"] = normalized_profiles
        raw.setdefault("source_authority", {})
        raw.setdefault("high_authority_threshold", HIGH_AUTHORITY_THRESHOLD)
        raw["policy_path"] = str(path)
        return raw
    except Exception:
        return {
            "version": 0,
            "policy_path": "builtin:fallback",
            "high_authority_threshold": HIGH_AUTHORITY_THRESHOLD,
            "profiles": RESEARCH_PROFILES,
            "source_authority": {},
        }


def _policy() -> dict[str, Any]:
    return _load_policy()


def policy_doctor() -> dict[str, Any]:
    """Return health and schema summary for the active DeepResearch policy."""
    policy = _policy()
    profiles = policy.get("profiles") if isinstance(policy.get("profiles"), dict) else {}
    authority = policy.get("source_authority") if isinstance(policy.get("source_authority"), dict) else {}
    errors: list[str] = []
    warnings: list[str] = []
    if not profiles:
        errors.append("policy_profiles_missing")
    if "general" not in profiles:
        errors.append("policy_general_profile_missing")
    if not authority:
        warnings.append("policy_source_authority_empty")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            errors.append(f"profile_invalid:{name}")
            continue
        for key in ("min_source_types", "warn_source_types", "min_covered_section_ratio", "max_low_analysis_density_ratio"):
            if key not in profile:
                warnings.append(f"profile_{name}_missing_{key}")
    return {
        "ok": not errors,
        "policy_path": policy.get("policy_path", "unknown"),
        "version": policy.get("version", "unknown"),
        "high_authority_threshold": float(policy.get("high_authority_threshold") or HIGH_AUTHORITY_THRESHOLD),
        "profiles": sorted(profiles.keys()),
        "source_authority_types": sorted(authority.keys()),
        "errors": errors,
        "warnings": warnings,
    }


def explain_source_authority(source_type: str, url: str = "", title: str = "", text: str = "") -> dict[str, Any]:
    """Explain the active policy score for one source candidate."""
    normalized_type = str(source_type or "unknown").strip().lower() or "unknown"
    policy = _policy()
    rules = (policy.get("source_authority") or {}).get(normalized_type) or (policy.get("source_authority") or {}).get("unknown") or []
    haystack = f"{url}\n{title}\n{text}".lower()
    host = urlparse(url).netloc.lower()
    matched_rule: dict[str, Any] | None = None
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        host_contains = [str(x).lower() for x in rule.get("host_contains") or []]
        host_prefix = [str(x).lower() for x in rule.get("host_prefix") or []]
        text_contains = [str(x).lower() for x in rule.get("text_contains") or []]
        host_hits = [marker for marker in host_contains if marker in host]
        prefix_hits = [marker for marker in host_prefix if host.startswith(marker)]
        text_hits = [marker for marker in text_contains if marker in haystack]
        if rule.get("default") or host_hits or prefix_hits or text_hits:
            matched_rule = {
                "index": idx,
                "score": float(rule.get("score", 0.30)),
                "default": bool(rule.get("default")),
                "host_hits": host_hits,
                "host_prefix_hits": prefix_hits,
                "text_hits": text_hits,
                "rule": rule,
            }
            break
    if matched_rule is None:
        matched_rule = {"index": -1, "score": _source_authority_score(normalized_type, url, title, text), "default": True, "host_hits": [], "host_prefix_hits": [], "text_hits": [], "rule": {}}
    return {
        "ok": True,
        "policy_path": policy.get("policy_path", "unknown"),
        "source_type": normalized_type,
        "url": url,
        "title": title,
        "score": matched_rule["score"],
        "high_authority": matched_rule["score"] >= float(policy.get("high_authority_threshold") or HIGH_AUTHORITY_THRESHOLD),
        "matched_rule": matched_rule,
    }


def audit_sources(output_dir: str | Path, research_profile: str = "general", strict_profile: bool = False) -> dict[str, Any]:
    """Audit a DeepResearch exported sources.jsonl/evidence.jsonl directory."""
    root = Path(output_dir).expanduser()
    sources = _read_jsonl(root / "sources.jsonl")
    evidence_by_source = {
        str(row.get("source_id") or ""): str(row.get("content") or "")
        for row in _read_jsonl(root / "evidence.jsonl")
    }
    profile, policy = _profile_policy(research_profile)
    required = set(policy.get("required_source_types") or set())
    recommended = set(policy.get("warn_missing_source_types") or set())
    min_source_types = int(policy.get("min_source_types") or 1)
    min_authority = float(policy.get("min_authority_score") or 0.0)
    min_high = int(policy.get("min_high_authority_sources") or 0)
    high_threshold = float(_policy().get("high_authority_threshold") or HIGH_AUTHORITY_THRESHOLD)

    rows: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}
    invalid: list[str] = []
    low_authority: list[str] = []
    scores: list[float] = []
    high_count = 0

    for source in sources:
        source_id = str(source.get("id") or source.get("source_id") or "")
        source_type = str(source.get("source_type") or "unknown").strip().lower() or "unknown"
        type_counts[source_type] = type_counts.get(source_type, 0) + 1
        title = str(source.get("title") or "")
        url = str(source.get("url") or "")
        text = evidence_by_source.get(source_id, "")
        explanation = explain_source_authority(source_type, url=url, title=title, text=text)
        score = float(explanation.get("score") or 0.0)
        valid_type = True
        if source_type in VALIDATED_SOURCE_TYPES:
            valid_type = _source_type_is_plausible(source_type, url, title, text)
        if not valid_type:
            invalid.append(source_id or title or url or source_type)
        if score < min_authority:
            low_authority.append(source_id or title or url or source_type)
        if score >= high_threshold:
            high_count += 1
        scores.append(score)
        rows.append({
            "source_id": source_id,
            "source_type": source_type,
            "title": title,
            "url": url,
            "authority_score": score,
            "high_authority": score >= high_threshold,
            "valid_source_type": valid_type,
            "matched_rule": explanation.get("matched_rule", {}),
        })

    source_types = set(type_counts.keys())
    missing_required = sorted(required - source_types)
    missing_recommended = sorted(recommended - source_types)
    average = round(sum(scores) / len(scores), 4) if scores else 0.0
    warnings: list[str] = []
    errors: list[str] = []
    if missing_recommended:
        warnings.append("missing_recommended_source_types:" + ",".join(missing_recommended))
    if invalid:
        warnings.append("invalid_source_types:" + ",".join(invalid[:5]))
    if low_authority:
        warnings.append("low_authority_sources:" + ",".join(low_authority[:5]))
    if strict_profile:
        if len(source_types) < min_source_types:
            errors.append(f"source_type_count_too_low:{len(source_types)}<{min_source_types}")
        if missing_required:
            errors.append("missing_required_source_types:" + ",".join(missing_required))
        if invalid:
            errors.append(f"invalid_source_type_count:{len(invalid)}>0")
        if scores and average < min_authority:
            errors.append(f"source_authority_average_too_low:{average:.4f}<{min_authority:.4f}")
        if high_count < min_high:
            errors.append(f"high_authority_sources_too_low:{high_count}<{min_high}")

    suggestions = []
    for source_type in missing_required + missing_recommended:
        suggestions.append(f"Add {source_type} source for profile {profile}")
    for source_id in invalid[:5]:
        suggestions.append(f"Replace or relabel invalid source type: {source_id}")
    for source_id in low_authority[:5]:
        suggestions.append(f"Prefer canonical/high-authority source for: {source_id}")

    return {
        "ok": not errors,
        "output_dir": str(root),
        "research_profile": profile,
        "strict_profile": strict_profile,
        "policy_path": _policy().get("policy_path", "unknown"),
        "source_count": len(sources),
        "source_type_counts": type_counts,
        "source_type_count": len(source_types),
        "missing_required_source_types": missing_required,
        "missing_recommended_source_types": missing_recommended,
        "source_authority_average": average,
        "source_high_authority_count": high_count,
        "source_high_authority_threshold": high_threshold,
        "invalid_source_type_count": len(invalid),
        "low_authority_source_count": len(low_authority),
        "sources": rows,
        "replacement_suggestions": suggestions,
        "errors": errors,
        "warnings": warnings,
    }


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_path(raw: Any, base_dir: Path) -> Path:
    raw_text = str(raw or "").strip()
    if not raw_text:
        return base_dir / "__missing_research_artifact__"
    path = Path(raw_text).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path


def _section_count(report_ast: dict[str, Any]) -> int:
    chapters = report_ast.get("chapters") or []
    if not isinstance(chapters, list):
        return 0
    return sum(len(ch.get("sections") or []) for ch in chapters if isinstance(ch, dict))


def _expected_sections(report_ast: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = report_ast.get("chapters") or []
    if not isinstance(chapters, list):
        return []
    sections: list[dict[str, Any]] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        for section in chapter.get("sections") or []:
            if isinstance(section, dict):
                sections.append(section)
    return sections


def _first_number(data: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = data.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in Path(path).expanduser().read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _tokens(text: str) -> set[str]:
    return {tok.lower() for tok in TOKEN_RE.findall(text or "") if len(tok.strip()) >= 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _source_token_sets(output_dir: Path) -> list[set[str]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_read_jsonl(output_dir / "claims.jsonl"))
    rows.extend(_read_jsonl(output_dir / "evidence.jsonl"))
    token_sets: list[set[str]] = []
    for row in rows:
        text = str(row.get("claim_text") or row.get("content") or "").strip()
        if not text:
            continue
        toks = _tokens(text)
        if len(toks) >= 6:
            token_sets.append(toks)
    return token_sets


def _expert_analysis_lines(expert_text: str) -> list[str]:
    lines: list[str] = []
    for raw in (expert_text or "").splitlines():
        line = raw.strip()
        if len(line) < 45:
            continue
        if "[cite:" in line:
            continue
        if BOILERPLATE_LINE_RE.match(line):
            continue
        if re.match(r"^- \[[ xX]\]", line):
            continue
        lines.append(line)
    return lines


def _expert_novelty_metrics(expert_text: str, output_dir: Path) -> dict[str, Any]:
    source_sets = _source_token_sets(output_dir)
    analysis_lines = _expert_analysis_lines(expert_text)
    if not analysis_lines:
        return {
            "expert_analysis_lines": 0,
            "expert_redundant_lines": 0,
            "expert_novelty_ratio": 0.0,
            "expert_insight_density": 0.0,
            "expert_independent_insight_lines": 0,
            "expert_source_material_sets": len(source_sets),
        }

    redundant = 0
    insight_lines = 0
    independent_insight_lines = 0
    for line in analysis_lines:
        toks = _tokens(line)
        max_overlap = max((_jaccard(toks, source) for source in source_sets), default=0.0)
        is_redundant = max_overlap >= 0.72
        if is_redundant:
            redundant += 1
        if ANALYSIS_TERMS_RE.search(line):
            insight_lines += 1
            if not is_redundant:
                independent_insight_lines += 1

    total = len(analysis_lines)
    return {
        "expert_analysis_lines": total,
        "expert_redundant_lines": redundant,
        "expert_novelty_ratio": round((total - redundant) / total, 4),
        "expert_insight_density": round(insight_lines / total, 4),
        "expert_independent_insight_lines": independent_insight_lines,
        "expert_source_material_sets": len(source_sets),
    }


def _section_coverage_metrics(output_dir: Path, report_ast_data: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    expected = _expected_sections(report_ast_data)
    rows = _read_jsonl(output_dir / "sections.jsonl")
    by_id = {str(row.get("id") or ""): row for row in rows}
    by_type = {str(row.get("section_type") or ""): row for row in rows}
    errors: list[str] = []
    warnings: list[str] = []
    covered = 0
    total_citations = 0
    thin_sections: list[str] = []
    no_citation_sections: list[str] = []
    low_analysis_sections: list[str] = []

    for idx, section in enumerate(expected, start=1):
        section_key = str(section.get("db_section_id") or section.get("section_id") or section.get("id") or f"section_{idx}")
        row = by_id.get(str(section.get("db_section_id") or "")) or by_id.get(str(section.get("id") or "")) or by_type.get(str(section.get("section_type") or ""))
        if not row:
            errors.append(f"section_artifact_missing:{section_key}")
            continue
        content = str(row.get("content") or "")
        citations = len(re.findall(r"\[cite:ev_[A-Za-z0-9_-]+", content))
        total_citations += citations
        words = len(_tokens(content))
        analysis_hits = len(ANALYSIS_TERMS_RE.findall(content))
        analysis_density = analysis_hits / max(words, 1)
        if len(content.strip()) < 220:
            thin_sections.append(section_key)
        if citations < DEFAULT_MIN_SECTION_CITATIONS:
            no_citation_sections.append(section_key)
        if analysis_density < DEFAULT_MIN_SECTION_ANALYSIS_DENSITY and str(row.get("section_type") or "") != "source_landscape":
            low_analysis_sections.append(section_key)
        if citations >= DEFAULT_MIN_SECTION_CITATIONS and len(content.strip()) >= 220:
            covered += 1

    if thin_sections:
        errors.append("section_coverage_too_thin:" + ",".join(thin_sections[:5]))
    if no_citation_sections:
        errors.append("section_coverage_missing_citations:" + ",".join(no_citation_sections[:5]))
    if low_analysis_sections:
        warnings.append("section_coverage_low_analysis_density:" + ",".join(low_analysis_sections[:5]))
    metrics = {
        "expected_sections": len(expected),
        "section_artifacts": len(rows),
        "covered_sections": covered,
        "section_total_citations": total_citations,
        "section_thin_count": len(thin_sections),
        "section_missing_citation_count": len(no_citation_sections),
        "section_low_analysis_density_count": len(low_analysis_sections),
    }
    return metrics, errors, warnings


def _source_diversity_metrics(output_dir: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    rows = _read_jsonl(output_dir / "sources.jsonl")
    counts: dict[str, int] = {}
    for row in rows:
        source_type = str(row.get("source_type") or "unknown").strip().lower() or "unknown"
        counts[source_type] = counts.get(source_type, 0) + 1
    type_count = len(counts)
    errors: list[str] = []
    warnings: list[str] = []
    if rows and type_count < DEFAULT_MIN_SOURCE_TYPE_COUNT:
        errors.append(f"source_diversity_type_count_too_low:{type_count}<{DEFAULT_MIN_SOURCE_TYPE_COUNT}")
    if rows and type_count < DEFAULT_WARN_SOURCE_TYPE_COUNT:
        warnings.append(f"source_diversity_single_type:{type_count}<{DEFAULT_WARN_SOURCE_TYPE_COUNT}")
    if rows and max(counts.values(), default=0) / max(len(rows), 1) > 0.85 and len(rows) >= 4:
        warnings.append("source_diversity_dominated_by_single_type")
    return {
        "source_type_count": type_count,
        "source_type_counts": counts,
    }, errors, warnings


def _source_type_is_plausible(source_type: str, url: str, title: str, text: str) -> bool:
    haystack = f"{url}\n{title}\n{text}".lower()
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if source_type == "paper":
        return any(
            marker in haystack
            for marker in (
                "arxiv.org", "doi.org", "openreview.net", "semanticscholar.org",
                "acm.org", "ieee.org", "springer.com", "nature.com", "abstract",
                "proceedings", "preprint", "journal", "conference",
            )
        )
    if source_type == "code":
        return any(
            marker in haystack
            for marker in (
                "github.com", "gitlab.com", "bitbucket.org", "source code",
                "repository", "repo", "readme", "pip install", "npm install",
            )
        )
    if source_type == "official_doc":
        return (
            "docs." in host
            or path.startswith(("/docs", "/documentation", "/developer", "/developers"))
            or any(marker in haystack for marker in ("official documentation", "developer docs", "api reference", "release notes", "changelog"))
        )
    if source_type == "benchmark":
        return any(
            marker in haystack
            for marker in (
                "benchmark", "leaderboard", "evaluation", "eval", "dataset",
                "score", "results", "terminal-bench", "swe-bench", "browsecomp",
            )
        )
    return True


def _source_type_validation_metrics(output_dir: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    sources = _read_jsonl(output_dir / "sources.jsonl")
    evidence_by_source = {
        str(row.get("source_id") or ""): str(row.get("content") or "")
        for row in _read_jsonl(output_dir / "evidence.jsonl")
    }
    validated = 0
    invalid: list[str] = []
    unknown: list[str] = []
    for row in sources:
        source_id = str(row.get("id") or row.get("source_id") or "")
        source_type = str(row.get("source_type") or "").strip().lower()
        if source_type not in VALIDATED_SOURCE_TYPES:
            continue
        validated += 1
        url = str(row.get("url") or "")
        title = str(row.get("title") or "")
        text = evidence_by_source.get(source_id, "")
        if not url and not title and not text:
            unknown.append(source_id or source_type)
            continue
        if not _source_type_is_plausible(source_type, url, title, text):
            invalid.append(f"{source_type}:{source_id or title or url}")

    warnings: list[str] = []
    if invalid:
        warnings.append("source_type_validation_invalid:" + ",".join(invalid[:5]))
    if unknown:
        warnings.append("source_type_validation_unknown:" + ",".join(unknown[:5]))
    return {
        "source_type_validated_count": validated,
        "source_type_invalid_count": len(invalid),
        "source_type_unknown_count": len(unknown),
        "source_type_invalid_examples": invalid[:10],
    }, [], warnings


def _source_authority_score(source_type: str, url: str, title: str, text: str) -> float:
    haystack = f"{url}\n{title}\n{text}".lower()
    host = urlparse(url).netloc.lower()
    rules = _policy().get("source_authority") or {}
    for rule in rules.get(source_type) or rules.get("unknown") or []:
        if not isinstance(rule, dict):
            continue
        score = float(rule.get("score", 0.30))
        if rule.get("default"):
            return score
        host_contains = [str(x).lower() for x in rule.get("host_contains") or []]
        host_prefix = [str(x).lower() for x in rule.get("host_prefix") or []]
        text_contains = [str(x).lower() for x in rule.get("text_contains") or []]
        host_ok = bool(host_contains and any(marker in host for marker in host_contains))
        prefix_ok = bool(host_prefix and any(host.startswith(marker) for marker in host_prefix))
        text_ok = bool(text_contains and any(marker in haystack for marker in text_contains))
        if host_ok or prefix_ok or text_ok:
            return score
    if source_type == "paper":
        if any(domain in host for domain in ("arxiv.org", "openreview.net", "doi.org", "semanticscholar.org")):
            return 0.90
        if any(domain in host for domain in ("acm.org", "ieee.org", "springer.com", "nature.com", "sciencedirect.com")):
            return 0.85
        if any(marker in haystack for marker in ("abstract", "preprint", "journal", "conference", "proceedings")):
            return 0.65
        return 0.30
    if source_type == "code":
        if any(domain in host for domain in ("github.com", "gitlab.com", "bitbucket.org")):
            return 0.85
        if any(marker in haystack for marker in ("source code", "repository", "readme", "pip install", "npm install")):
            return 0.60
        return 0.30
    if source_type == "official_doc":
        if host.startswith("docs.") or any(part in host for part in (".gov", ".edu")):
            return 0.85
        if any(marker in haystack for marker in ("official documentation", "api reference", "developer docs", "release notes", "changelog")):
            return 0.70
        return 0.35
    if source_type == "benchmark":
        if any(domain in host for domain in ("paperswithcode.com", "huggingface.co", "tbench.ai")):
            return 0.85
        if any(marker in haystack for marker in ("leaderboard", "benchmark", "evaluation", "dataset", "score", "results")):
            return 0.65
        return 0.35
    if source_type in {"news", "company", "standard"}:
        return 0.55
    if source_type in {"web", "blog", "other"}:
        return 0.35
    return 0.30


def _source_authority_metrics(output_dir: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    sources = _read_jsonl(output_dir / "sources.jsonl")
    evidence_by_source = {
        str(row.get("source_id") or ""): str(row.get("content") or "")
        for row in _read_jsonl(output_dir / "evidence.jsonl")
    }
    scores: list[float] = []
    examples: list[str] = []
    for row in sources:
        source_id = str(row.get("id") or row.get("source_id") or "")
        source_type = str(row.get("source_type") or "unknown").strip().lower()
        score = _source_authority_score(
            source_type,
            str(row.get("url") or ""),
            str(row.get("title") or ""),
            evidence_by_source.get(source_id, ""),
        )
        scores.append(score)
        examples.append(f"{source_type}:{source_id or row.get('title') or 'unknown'}:{score:.2f}")
    avg = round(sum(scores) / len(scores), 4) if scores else 0.0
    threshold = float(_policy().get("high_authority_threshold") or HIGH_AUTHORITY_THRESHOLD)
    high = sum(1 for score in scores if score >= threshold)
    warnings: list[str] = []
    if scores and avg < 0.50:
        warnings.append(f"source_authority_average_low:{avg:.4f}<0.5000")
    return {
        "source_authority_average": avg,
        "source_high_authority_count": high,
        "source_authority_scored_count": len(scores),
        "source_authority_examples": examples[:10],
        "source_authority_policy_path": _policy().get("policy_path", "unknown"),
        "source_high_authority_threshold": threshold,
    }, [], warnings


def _profile_policy(raw_profile: str | None) -> tuple[str, dict[str, Any]]:
    profiles = _policy().get("profiles")
    if isinstance(profiles, dict) and profiles:
        profile = (raw_profile or "general").strip().lower().replace("-", "_")
        if profile not in profiles:
            profile = "general"
        return profile, profiles[profile]
    profile = (raw_profile or "general").strip().lower().replace("-", "_")
    if profile not in RESEARCH_PROFILES:
        profile = "general"
    return profile, RESEARCH_PROFILES[profile]


def source_requirements_for_profile(raw_profile: str | None = "general") -> dict[str, Any]:
    """Return serializable source-acquisition requirements for a research profile."""
    profile, policy = _profile_policy(raw_profile)
    required = sorted(policy.get("required_source_types") or set())
    recommended = sorted(policy.get("warn_missing_source_types") or set())
    all_types = []
    for source_type in required + recommended:
        if source_type not in all_types:
            all_types.append(source_type)
    return {
        "profile": profile,
        "required_source_types": required,
        "recommended_source_types": recommended,
        "target_source_types": all_types,
        "min_source_types": int(policy.get("min_source_types") or 1),
        "warn_source_types": int(policy.get("warn_source_types") or 1),
        "min_covered_section_ratio": float(policy.get("min_covered_section_ratio") or 1.0),
        "max_low_analysis_density_ratio": float(policy.get("max_low_analysis_density_ratio") or 1.0),
        "min_authority_score": float(policy.get("min_authority_score") or 0.0),
        "min_high_authority_sources": int(policy.get("min_high_authority_sources") or 0),
    }


def _apply_profile_gate(
    profile: str,
    policy: dict[str, Any],
    metrics: dict[str, Any],
    strict_profile: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    source_counts = metrics.get("source_type_counts") if isinstance(metrics.get("source_type_counts"), dict) else {}
    source_types = set(source_counts.keys())
    source_type_count = int(metrics.get("source_type_count") or 0)
    expected_sections = int(metrics.get("expected_sections") or metrics.get("report_ast_sections") or 0)
    covered_sections = int(metrics.get("covered_sections") or 0)
    low_analysis = int(metrics.get("section_low_analysis_density_count") or 0)
    covered_ratio = covered_sections / max(expected_sections, 1) if expected_sections else 0.0
    low_analysis_ratio = low_analysis / max(expected_sections, 1) if expected_sections else 0.0

    missing_required = sorted(set(policy.get("required_source_types") or set()) - source_types)
    missing_warn = sorted(set(policy.get("warn_missing_source_types") or set()) - source_types)
    min_source_types = int(policy.get("min_source_types") or 1)
    warn_source_types = int(policy.get("warn_source_types") or min_source_types)
    min_covered_ratio = float(policy.get("min_covered_section_ratio") or 1.0)
    max_low_analysis_ratio = float(policy.get("max_low_analysis_density_ratio") or 1.0)
    min_authority_score = float(policy.get("min_authority_score") or 0.0)
    min_high_authority_sources = int(policy.get("min_high_authority_sources") or 0)
    authority_average = float(metrics.get("source_authority_average") or 0.0)
    high_authority = int(metrics.get("source_high_authority_count") or 0)

    if source_type_count < warn_source_types:
        warnings.append(f"profile_{profile}_source_type_count_low:{source_type_count}<{warn_source_types}")
    if missing_warn:
        warnings.append(f"profile_{profile}_missing_recommended_source_types:{','.join(missing_warn)}")
    if low_analysis_ratio > max_low_analysis_ratio:
        warnings.append(f"profile_{profile}_low_analysis_density_ratio:{low_analysis_ratio:.4f}>{max_low_analysis_ratio:.4f}")
    if authority_average < min_authority_score and int(metrics.get("source_authority_scored_count") or 0) > 0:
        warnings.append(f"profile_{profile}_source_authority_low:{authority_average:.4f}<{min_authority_score:.4f}")
    if high_authority < min_high_authority_sources:
        warnings.append(f"profile_{profile}_high_authority_sources_low:{high_authority}<{min_high_authority_sources}")

    if strict_profile:
        invalid_source_types = int(metrics.get("source_type_invalid_count") or 0)
        if source_type_count < min_source_types:
            errors.append(f"profile_{profile}_source_type_count_too_low:{source_type_count}<{min_source_types}")
        if missing_required:
            errors.append(f"profile_{profile}_missing_required_source_types:{','.join(missing_required)}")
        if covered_ratio < min_covered_ratio:
            errors.append(f"profile_{profile}_covered_section_ratio_too_low:{covered_ratio:.4f}<{min_covered_ratio:.4f}")
        if low_analysis_ratio > max_low_analysis_ratio:
            errors.append(f"profile_{profile}_low_analysis_density_ratio_too_high:{low_analysis_ratio:.4f}>{max_low_analysis_ratio:.4f}")
        if invalid_source_types > 0:
            errors.append(f"profile_{profile}_invalid_source_type_count:{invalid_source_types}>0")
        if authority_average < min_authority_score and int(metrics.get("source_authority_scored_count") or 0) > 0:
            errors.append(f"profile_{profile}_source_authority_too_low:{authority_average:.4f}<{min_authority_score:.4f}")
        if high_authority < min_high_authority_sources:
            errors.append(f"profile_{profile}_high_authority_sources_too_low:{high_authority}<{min_high_authority_sources}")

    metrics.update({
        "research_profile": profile,
        "strict_profile": strict_profile,
        "profile_required_source_types": sorted(policy.get("required_source_types") or set()),
        "profile_recommended_source_types": sorted(policy.get("warn_missing_source_types") or set()),
        "profile_min_source_types": min_source_types,
        "profile_warn_source_types": warn_source_types,
        "profile_covered_section_ratio": round(covered_ratio, 4),
        "profile_low_analysis_density_ratio": round(low_analysis_ratio, 4),
        "profile_min_authority_score": min_authority_score,
        "profile_min_high_authority_sources": min_high_authority_sources,
    })
    return errors, warnings


def evaluate_artifacts(
    eval_json: str | Path,
    report_ast: str | Path | None = None,
    final_md: str | Path | None = None,
    bibliography: str | Path | None = None,
    expert_md: str | Path | None = None,
    require_expert: bool = False,
    max_unsupported_rate: float = DEFAULT_MAX_UNSUPPORTED_RATE,
    min_citation_accuracy: float = DEFAULT_MIN_CITATION_ACCURACY,
    min_expert_novelty_ratio: float = DEFAULT_MIN_EXPERT_NOVELTY_RATIO,
    min_expert_insight_density: float = DEFAULT_MIN_EXPERT_INSIGHT_DENSITY,
    min_expert_insight_lines: int = DEFAULT_MIN_EXPERT_INSIGHT_LINES,
    research_profile: str = "general",
    strict_profile: bool = False,
) -> dict[str, Any]:
    """Evaluate one DeepResearch artifact set and return a PASS/FAIL payload."""
    eval_path = Path(eval_json).expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}

    if not eval_path.exists():
        return {
            "ok": False,
            "verdict": "FAIL",
            "errors": [f"research_eval_json_missing:{eval_path}"],
            "warnings": [],
            "metrics": metrics,
            "artifacts": {"eval_json": str(eval_path)},
        }

    eval_data = _read_json(eval_path)
    base_dir = eval_path.parent
    output_dir = _resolve_path(eval_data.get("output_dir"), base_dir) if eval_data.get("output_dir") else base_dir
    final_path = (
        Path(final_md).expanduser()
        if final_md
        else (_resolve_path(eval_data.get("final_md"), output_dir) if eval_data.get("final_md") else output_dir / "final.md")
    )
    report_ast_path = Path(report_ast).expanduser() if report_ast else output_dir / "report_ast.json"
    bibliography_path = Path(bibliography).expanduser() if bibliography else output_dir / "final.bibliography.json"
    expert_path = Path(expert_md).expanduser() if expert_md else output_dir / "expert_synthesis.md"

    source_count = int(eval_data.get("source_count") or 0)
    evidence_count = int(eval_data.get("evidence_count") or 0)
    claim_count = int(eval_data.get("claim_count") or 0)
    section_count = int(eval_data.get("section_count") or 0)
    unsupported_rate = _first_number(eval_data, "unsupported_rate", "unsupported_claim_rate")
    citation_accuracy = _first_number(eval_data, "citation_accuracy", "citation_span_accuracy")
    eval_status = str(eval_data.get("status") or "unknown").lower()

    metrics.update({
        "source_count": source_count,
        "evidence_count": evidence_count,
        "claim_count": claim_count,
        "section_count": section_count,
        "unsupported_rate": unsupported_rate,
        "citation_accuracy": citation_accuracy,
        "eval_status": eval_status,
    })

    if eval_status not in {"passed", "pass", "ok"}:
        errors.append(f"research_eval_status_not_passed:{eval_status}")
    if source_count <= 0:
        errors.append("source_count_zero")
    if evidence_count <= 0:
        errors.append("evidence_count_zero")
    if claim_count <= 0:
        errors.append("claim_count_zero")
    if section_count <= 0:
        errors.append("section_count_zero")
    if unsupported_rate > max_unsupported_rate:
        errors.append(f"unsupported_rate_too_high:{unsupported_rate:.4f}>{max_unsupported_rate:.4f}")
    if citation_accuracy < min_citation_accuracy:
        errors.append(f"citation_accuracy_too_low:{citation_accuracy:.4f}<{min_citation_accuracy:.4f}")

    report_ast_data = _read_json(report_ast_path)
    ast_sections = _section_count(report_ast_data)
    metrics["report_ast_sections"] = ast_sections
    if not report_ast_path.exists():
        errors.append(f"report_ast_missing:{report_ast_path}")
    elif ast_sections <= 0:
        errors.append("report_ast_has_no_sections")
    else:
        coverage_metrics, coverage_errors, coverage_warnings = _section_coverage_metrics(output_dir, report_ast_data)
        metrics.update(coverage_metrics)
        errors.extend(coverage_errors)
        warnings.extend(coverage_warnings)

    diversity_metrics, diversity_errors, diversity_warnings = _source_diversity_metrics(output_dir)
    metrics.update(diversity_metrics)
    errors.extend(diversity_errors)
    warnings.extend(diversity_warnings)
    source_validation_metrics, source_validation_errors, source_validation_warnings = _source_type_validation_metrics(output_dir)
    metrics.update(source_validation_metrics)
    errors.extend(source_validation_errors)
    warnings.extend(source_validation_warnings)
    authority_metrics, authority_errors, authority_warnings = _source_authority_metrics(output_dir)
    metrics.update(authority_metrics)
    errors.extend(authority_errors)
    warnings.extend(authority_warnings)
    profile, profile_policy = _profile_policy(research_profile or str(eval_data.get("research_profile") or "general"))
    profile_errors, profile_warnings = _apply_profile_gate(profile, profile_policy, metrics, strict_profile)
    errors.extend(profile_errors)
    warnings.extend(profile_warnings)

    if not final_path.exists():
        errors.append(f"final_md_missing:{final_path}")
        final_text = ""
    else:
        final_text = final_path.read_text(encoding="utf-8", errors="replace")
        if not final_text.strip():
            errors.append("final_md_empty")
        if not re.search(r"\[cite:ev_[A-Za-z0-9_-]+", final_text):
            errors.append("final_md_missing_evidence_citations")
        metadata_noise = len(re.findall(r"(?im)^\s*-?\s*(Title|URL|Publisher|Published|Source Type):", final_text))
        metrics["metadata_noise_lines"] = metadata_noise
        if metadata_noise > 3:
            errors.append(f"final_md_metadata_noise:{metadata_noise}>3")
        if len(re.findall(r"(?im)^##?\s+(Architecture|架构|Taxonomy|技术路线|Engineering Implications|工程)", final_text)) == 0:
            warnings.append("final_md_missing_architecture_or_implication_section")

    if not bibliography_path.exists():
        warnings.append(f"bibliography_missing:{bibliography_path}")
    if require_expert:
        if not expert_path.exists():
            errors.append(f"expert_synthesis_missing:{expert_path}")
            expert_text = ""
        else:
            expert_text = expert_path.read_text(encoding="utf-8", errors="replace")
            tradeoff_count = len(re.findall(r"(?i)tradeoff|trade-off|取舍|vs\\.", expert_text))
            roadmap_count = len(re.findall(r"(?m)^- \*\*P[0-2]\*\*|\bP[0-2]\b", expert_text))
            has_taxonomy = bool(re.search(r"(?i)architecture taxonomy|架构分类|taxonomy", expert_text))
            has_source_strength = bool(re.search(r"(?i)source strength|source score|来源强度|证据强度", expert_text))
            has_contradiction = bool(re.search(r"(?i)contradictions? and uncertainty|contradiction|uncertainty|反证|不确定", expert_text))
            insight_scorecard_rows = len(re.findall(r"(?m)^\| [^|\n]+ \|\s*\d+/5\s*\|", expert_text))
            novelty_metrics = _expert_novelty_metrics(expert_text, output_dir)
            metrics.update({
                "expert_chars": len(expert_text),
                "expert_tradeoff_mentions": tradeoff_count,
                "expert_roadmap_mentions": roadmap_count,
                "expert_has_taxonomy": has_taxonomy,
                "expert_has_source_strength": has_source_strength,
                "expert_has_contradiction_uncertainty": has_contradiction,
                "expert_insight_scorecard_rows": insight_scorecard_rows,
                **novelty_metrics,
            })
            if len(expert_text) < 1800:
                errors.append(f"expert_synthesis_too_short:{len(expert_text)}<1800")
            if not has_taxonomy:
                errors.append("expert_synthesis_missing_taxonomy")
            if tradeoff_count < 1:
                errors.append("expert_synthesis_missing_tradeoffs")
            if roadmap_count < 3:
                errors.append(f"expert_synthesis_missing_p0_p1_p2_roadmap:{roadmap_count}<3")
            if not has_source_strength:
                errors.append("expert_synthesis_missing_source_strength")
            if not has_contradiction:
                errors.append("expert_synthesis_missing_contradiction_uncertainty")
            if insight_scorecard_rows < 3:
                errors.append(f"expert_synthesis_insight_scorecard_too_thin:{insight_scorecard_rows}<3")
            if novelty_metrics["expert_source_material_sets"] > 0:
                if novelty_metrics["expert_novelty_ratio"] < min_expert_novelty_ratio:
                    errors.append(
                        "expert_synthesis_too_redundant:"
                        f"{novelty_metrics['expert_novelty_ratio']:.4f}<{min_expert_novelty_ratio:.4f}"
                    )
                if novelty_metrics["expert_insight_density"] < min_expert_insight_density:
                    errors.append(
                        "expert_synthesis_insight_density_too_low:"
                        f"{novelty_metrics['expert_insight_density']:.4f}<{min_expert_insight_density:.4f}"
                    )
                if novelty_metrics["expert_independent_insight_lines"] < min_expert_insight_lines:
                    errors.append(
                        "expert_synthesis_independent_insight_lines_too_low:"
                        f"{novelty_metrics['expert_independent_insight_lines']}<{min_expert_insight_lines}"
                    )
            else:
                warnings.append("expert_synthesis_novelty_gate_skipped_no_source_material")

    artifacts = {
        "eval_json": str(eval_path),
        "output_dir": str(output_dir),
        "report_ast": str(report_ast_path),
        "final_md": str(final_path),
        "bibliography": str(bibliography_path),
        "expert_synthesis": str(expert_path),
    }
    exists = {name: bool(path and Path(path).exists()) for name, path in artifacts.items()}
    verdict = "FAIL" if errors else "PASS"
    return {
        "ok": verdict == "PASS",
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
        "artifacts": artifacts,
        "artifact_exists": exists,
        "policy": {
            "max_unsupported_rate": max_unsupported_rate,
            "min_citation_accuracy": min_citation_accuracy,
            "min_expert_novelty_ratio": min_expert_novelty_ratio,
            "min_expert_insight_density": min_expert_insight_density,
            "min_expert_insight_lines": min_expert_insight_lines,
            "research_profile": metrics.get("research_profile"),
            "strict_profile": strict_profile,
        },
    }
