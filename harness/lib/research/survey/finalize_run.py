"""End-to-end professor-grade survey finalization orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .auto_repair import run_auto_repair
from .evaluator import evaluate_survey
from .evidence_pack import build_evidence_packs
from .planner import create_survey_plan, write_survey_plan
from .section_compiler import compile_survey
from .source_gap import write_source_gap_handoff
from .writing_loop import run_ready_sections


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _prepare_deepdive_entry_contract(
    root: Path,
    brief: str,
    *,
    target_chars: int,
    audience: str,
    domain: str,
) -> dict[str, Any]:
    from research.deepdive_brief_expander import expand_deepdive_brief
    from research.deepdive_requirement_compiler import (
        DeepDiveCompileOptions,
        compile_deepdive_brief,
        validate_deepdive_contract,
    )

    expansion = expand_deepdive_brief(brief, root)
    effective_brief = str(expansion.get("expanded_brief") or brief).strip()
    contract = compile_deepdive_brief(
        brief,
        options=DeepDiveCompileOptions(
            profile="deepdive",
            source_channel="survey_finalize",
            target_chars=target_chars,
        ),
        expansion=expansion,
    )
    validation = validate_deepdive_contract(contract)
    contract_path = root / "deepdive_requirement_contract.json"
    trace_path = root / "deepdive_traceability.json"
    _write_json(contract_path, contract)
    _write_json(trace_path, contract.get("traceability", {}))
    return {
        "ok": bool(validation.get("ok")),
        "effective_brief": effective_brief,
        "contract_path": str(contract_path),
        "traceability_path": str(trace_path),
        "expansion_path": expansion.get("output_json_path", ""),
        "validation": validation,
        "audience": audience,
        "domain": domain,
    }


def finalize_survey_run(
    output_dir: str | Path,
    *,
    brief: str = "",
    target_chars: int = 50000,
    audience: str = "technical",
    domain: str = "ai",
    run_id: str = "",
    section_limit: int = 3,
    repair_limit: int = 0,
    max_revisions: int = 3,
    repair_passes: int = 2,
    min_chars: int = 1200,
    min_finalized: int | None = None,
    require_complete: bool = False,
    writer_backend: str = "deterministic",
    writer_command: str = "",
    writer_timeout: int = 120,
    pane_target: str = "",
    pane_send: bool = False,
    emit_prompt_packet: bool = True,
    skip_plan: bool = False,
    skip_pack: bool = False,
    allow_source_gap: bool = False,
    min_sources: int = 4,
    min_evidence: int = 8,
    min_claims: int = 8,
    narrative_backend: str = "",
    narrative_model: str = "",
    narrative_fallback_models: list[str] | None = None,
    narrative_command: str = "",
    narrative_timeout: int = 0,
    narrative_max_budget_usd: float = 0.0,
    narrative_min_chars: int = 0,
    narrative_require_hitl: bool = False,
    premium_figures: bool | None = None,
    premium_figure_command: str = "",
    premium_figure_limit: int = 3,
    premium_figure_timeout: int = 600,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []

    ast = _read_json(root / "survey_report_ast.json")
    deepdive_entry: dict[str, Any] = {}
    if not skip_plan or not ast:
        if not brief.strip():
            return {"ok": False, "reason": "brief_required_for_plan"}
        deepdive_entry = _prepare_deepdive_entry_contract(
            root,
            brief,
            target_chars=target_chars,
            audience=audience,
            domain=domain,
        )
        planning_brief = deepdive_entry["effective_brief"]
        plan = create_survey_plan(
            planning_brief,
            target_chars=target_chars,
            audience=audience,
            domain=domain,
            run_id=run_id or None,
        )
        files = write_survey_plan(plan, root)
        ast = plan["report_ast"]
        steps.append({"step": "deepdive_entry", **deepdive_entry})
        steps.append({"step": "plan", "ok": True, "files": files, "section_count": len(ast.get("sections", []))})
    else:
        steps.append({"step": "plan", "ok": True, "skipped": True, "section_count": len(ast.get("sections", []))})

    section_count = len(ast.get("sections", [])) if isinstance(ast.get("sections"), list) else 0
    effective_min_evidence = max(min_evidence, section_count) if require_complete else min_evidence
    effective_min_claims = max(min_claims, section_count) if require_complete else min_claims
    source_gap = write_source_gap_handoff(
        root,
        brief=(deepdive_entry.get("effective_brief") or brief or ast.get("title", "")),
        min_sources=min_sources,
        min_evidence=effective_min_evidence,
        min_claims=effective_min_claims,
    )
    steps.append({"step": "source_gap", "ok": source_gap.get("ok"), "issues": source_gap.get("issues", []), "handoff_path": source_gap.get("handoff_path")})
    if not source_gap.get("ok") and not allow_source_gap:
        payload = {
            "ok": False,
            "reason": "source_gap_handoff_required",
            "steps": steps,
            "source_gap": source_gap,
            "handoff_path": source_gap.get("handoff_path"),
            "run_path": str(root / "survey_finalize_run.json"),
        }
        (root / "survey_finalize_run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return payload

    packs = _read_json(root / "survey_evidence_packs.json")
    if not skip_pack or not packs:
        packs = build_evidence_packs(root, ast)
        steps.append({"step": "pack", "ok": packs.get("ok"), "ready": packs.get("ready"), "blocked": packs.get("blocked")})
    else:
        steps.append({"step": "pack", "ok": True, "skipped": True, "ready": packs.get("ready"), "blocked": packs.get("blocked")})

    write_result = run_ready_sections(
        root,
        limit=section_limit,
        max_rounds=max_revisions,
        min_chars=min_chars,
        writer_backend=writer_backend,
        writer_command=writer_command,
        writer_timeout=writer_timeout,
        pane_target=pane_target,
        pane_send=pane_send,
        emit_prompt_packet=emit_prompt_packet,
    )
    steps.append({"step": "write", **write_result})

    initial_eval = evaluate_survey(root, strict=True, min_finalized=min_finalized, require_complete=require_complete)
    steps.append({"step": "eval", "ok": initial_eval.get("ok"), "issues": (initial_eval.get("scorecard") or {}).get("issues", [])})

    repair = {"ok": initial_eval.get("ok"), "reason": "not_needed", "iterations": []}
    if not initial_eval.get("ok"):
        repair = run_auto_repair(
            root,
            max_passes=repair_passes,
            per_pass_limit=repair_limit,
            max_rounds=max_revisions,
            min_chars=min_chars,
            min_finalized=min_finalized,
            require_complete=require_complete,
            writer_backend=writer_backend,
            writer_command=writer_command,
            writer_timeout=writer_timeout,
            pane_target=pane_target,
            pane_send=pane_send,
            emit_prompt_packet=emit_prompt_packet,
        )
    steps.append({"step": "auto_repair", "ok": repair.get("ok"), "reason": repair.get("reason"), "waiting": repair.get("waiting", 0)})

    compiled = compile_survey(
        root,
        premium_figures=premium_figures,
        premium_figure_command=premium_figure_command,
        premium_figure_limit=premium_figure_limit,
        premium_timeout_seconds=premium_figure_timeout,
    )
    steps.append({"step": "compile", **compiled})
    final_eval = evaluate_survey(root, strict=True, min_finalized=min_finalized, require_complete=require_complete)
    steps.append({"step": "final_eval", "ok": final_eval.get("ok"), "issues": (final_eval.get("scorecard") or {}).get("issues", [])})

    final_ok = bool(final_eval.get("ok"))
    payload = {
        "ok": final_ok,
        "reason": "passed" if final_ok else "final_eval_failed",
        "closeout_gate": "passed" if final_ok else "repairable_fail",
        "steps": steps,
        "initial_eval": initial_eval,
        "repair": repair,
        "compile": compiled,
        "final_eval": final_eval,
        "final_md": compiled.get("final_md", str(root / "final.md")),
        "run_path": str(root / "survey_finalize_run.json"),
    }
    (root / "survey_finalize_run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload
