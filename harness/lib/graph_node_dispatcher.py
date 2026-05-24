#!/usr/bin/env python3
"""graph_node_dispatcher.py — dispatch queued DAG nodes to builder panes.

The graph scheduler decides which nodes are ready. This dispatcher consumes
`task_queue.py` items with intent `graph_node|node_id=...`, creates explicit
per-node dispatch files, binds/verifies pane leases, and sends the node task to
the assigned pane.
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SPRINTS_DIR = HARNESS_DIR / "sprints"
SESSION = os.environ.get("SOLAR_HARNESS_SESSION", "solar-harness")
NO_DISPATCH_FLAG = HARNESS_DIR / "run" / "no-dispatch.flag"
DISPATCH_LEDGER = HARNESS_DIR / "run" / "dispatch-ledger.jsonl"
PANE_TUI_BUSY_RE = re.compile(
    r"Compacting conversation|压缩上下文|Reticulating|Scurrying|Roosting|"
    r"Mustering|Herding|Baking|Cogitating|Churning|Ruminating|Thinking|"
    r"Whirring|Smooshing|Unhandled node type|Do you want to proceed\?|"
    r"Enter to confirm|Esc to cancel|Bash command|"
    r"[·✳✶✽✢]\s+[A-Za-z][A-Za-z-]*…|✳|✶|✽|✢",
    re.I,
)
PANE_TUI_UNAVAILABLE_RE = re.compile(
    r"You(?:'|’)ve hit your limit|rate[- ]limit|rate limit|"
    r"resets\s+\d|/rate-limit-options|Upgrade your plan|"
    r"API Error:\s*400|Invalid API parameter|error\"\s*:\s*\{",
    re.I,
)
PANE_QUOTA_EXHAUSTED_RE = re.compile(
    r"You(?:'|’)ve hit (?:your|the org(?:anization)?(?:'s)?) .*limit|"
    r"monthly usage limit|quota exhausted|quota:exhausted|"
    r"rate[- ]limit|rate limit|RESOURCE_EXHAUSTED|429",
    re.I,
)
PANE_DISPATCH_FAILED_IDLE_RE = re.compile(
    r"API Error:\s*Request timed out|Check your internet connection and proxy settings",
    re.I,
)
PANE_QUEUED_PROMPT_RE = re.compile(r"Press up to edit queued messages", re.I)
PANE_SURVEY_PROMPT_RE = re.compile(
    r"How is Claude doing this session\?|1:\s*Bad\s+2:\s*Fine\s+3:\s*Good\s+0:\s*Dismiss",
    re.I,
)
PANE_APPROVAL_PROMPT_RE = re.compile(
    r"bypass permissions on|"
    r"Do you want to make this edit|"
    r"allow all edits during this session|"
    r"accept edits on|"
    r"Press up to edit queued messages",
    re.I,
)
PANE_CONFIRMATION_PROMPT_RE = re.compile(r"Unhandled node type|Do you want to proceed\?|Enter to confirm|Esc to cancel|Bash command", re.I)
PANE_PROMPT_RESIDUE_RE = re.compile(r"^\s*❯(?![\s\u00a0]+Try\s+\")[\s\u00a0]+[^\s\u00a0─]", re.M)
STATE_READ_PREFLIGHT = """<!-- SOLAR_STATE_READ_PREFLIGHT -->
## 必须先读状态 (防写入 hook 卡死)

在任何 Write/Edit/handoff/eval/status 更新之前，必须先用 Claude/Codex 的 **Read 工具**读取：

`~/.solar/STATE.md`

不要用 `cat` 替代这一步；本地 `state-read-enforcer.sh` hook 只认 Read 工具标记。

如果 Write/Edit hook 仍阻断，立刻 Read 上面的 STATE 文件后重试原写入一次，不要停在“已读”等待。

---
"""

DEFINITION_OF_DONE_POLICY = """## DEFINITION OF DONE · 强制完成约束

任务没有完成，除非同时满足以下 7 条。交付不是输出代码；交付是用证据证明功能真的工作。

1. 真实调用链接入 — 所有新增/修改功能已接入真实调用链，不允许只写孤立模块。
2. 禁止硬编码 — 不允许硬编码业务数据、测试数据、路径、token、feature flag。
3. 测试必须运行 — 必须运行相关测试；如果不能运行，必须明确说明原因。
4. 执行证据齐全 — 必须给出实际执行过的命令和结果摘要，不接受“应该可以工作”。
5. Diff 自审 — 必须检查 diff，列出每个改动文件的目的。
6. 禁用乐观词 — 如果存在未完成项，禁止使用 “done / complete / implemented”。
7. 结构化收尾 — 最终回答必须分为：已完成 · 已验证 · 未验证 · 风险 · 后续待办。

硬性判定：没有证据，不许报喜；存在未验证项时只能标 `未验证` 或 `风险`，不能标完成。

---
"""

sys.path.insert(0, str(HARNESS_DIR / "lib"))
from graph_scheduler import (  # noqa: E402
    load_graph,
    save_graph,
    enqueue_ready,
    set_node_status,
    node_status,
    mark_node_result,
    parent_ready_check,
)
from pane_lease import acquire as acquire_lease, release as release_lease, read_lease, list_leases  # noqa: E402
from task_queue import enqueue  # noqa: E402
try:
    from model_registry import load_registry as _load_model_registry, normalize as _normalize_model  # noqa: E402
except Exception:  # pragma: no cover - partial fixtures can omit registry helper
    _load_model_registry = None  # type: ignore
    _normalize_model = None  # type: ignore
try:
    from runtime_bridge import record_legacy_event  # noqa: E402
    from runtime_status import transition_status  # noqa: E402
except Exception:  # pragma: no cover - fail-open in partial test fixtures
    record_legacy_event = None  # type: ignore
    transition_status = None  # type: ignore
try:
    from capability_effects import scan_effect  # noqa: E402
except Exception:  # pragma: no cover - fail-open in partial test fixtures
    scan_effect = None  # type: ignore
try:
    from architecture_guard import dispatch_policy_block  # noqa: E402
except Exception:  # pragma: no cover - architecture guard is additive
    dispatch_policy_block = None  # type: ignore
try:
    from research import storage as research_storage  # noqa: E402
    from research.cli import render_human_search_handoff  # noqa: E402
    from research.evaluator import evaluate_artifacts as evaluate_research_artifacts  # noqa: E402
except Exception:  # pragma: no cover - DeepResearch is additive
    research_storage = None  # type: ignore
    render_human_search_handoff = None  # type: ignore
    evaluate_research_artifacts = None  # type: ignore


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


HUMAN_SEARCH_CAPABILITIES = {
    "source.search",
    "research.source.search",
    "research.source.web",
    "research.source.academic",
    "research.web.search",
    "research.academic.search",
    "research.contradiction.search",
}

EVALUATION_REVIEW_MODES = {"single", "staged", "dual", "committee"}


def _node_capabilities(node: dict[str, Any]) -> set[str]:
    caps: set[str] = set()
    for key in ("required_capabilities", "capabilities"):
        raw = node.get(key, [])
        if isinstance(raw, str):
            caps.add(raw)
        elif isinstance(raw, list):
            caps.update(str(item) for item in raw if str(item))
    return caps


def _node_requires_human_search(node: dict[str, Any]) -> bool:
    if node.get("human_search") is False or node.get("human_loop_search") is False:
        return False
    if _node_capabilities(node) & HUMAN_SEARCH_CAPABILITIES:
        return True
    haystack = " ".join(str(node.get(k, "")) for k in ("id", "goal", "description")).lower()
    return bool(re.search(r"external[_ -]?search|web[_ -]?search|academic[_ -]?search|source[_ -]?search|contradiction[_ -]?search", haystack))


def _node_requires_deepresearch_quality_gate(node: dict[str, Any]) -> bool:
    caps = _node_capabilities(node)
    if any(cap.startswith("research.") for cap in caps):
        return True
    if caps & {"citation.verify", "factuality.evaluate", "report.compile", "evidence.extract", "claim.mine"}:
        return True
    artifact_values: list[str] = []
    artifacts = node.get("artifacts") if isinstance(node.get("artifacts"), dict) else {}
    artifact_values.extend(str(value) for value in artifacts.values())
    for key in (
        "research_eval",
        "research_eval_json",
        "eval_artifacts_json",
        "report_ast",
        "final_report",
        "final_md",
    ):
        if node.get(key):
            artifact_values.append(str(node.get(key)))
    raw_scope = node.get("write_scope", [])
    if isinstance(raw_scope, str):
        artifact_values.append(raw_scope)
    elif isinstance(raw_scope, list):
        artifact_values.extend(str(item) for item in raw_scope)
    artifact_text = " ".join(artifact_values).lower()
    return bool(re.search(r"research_eval|report_ast|final\\.md|final_report|evidence\\.jsonl|claims\\.jsonl", artifact_text))


def _evaluation_selector(node: dict[str, Any]) -> dict[str, Any]:
    selector = node.get("operator_selector")
    return selector if isinstance(selector, dict) else {}


def _node_task_type(node: dict[str, Any]) -> str:
    selector = _evaluation_selector(node)
    return str(node.get("task_type") or selector.get("task_type") or "").strip().upper()


def _node_constraints(node: dict[str, Any]) -> dict[str, Any]:
    selector = _evaluation_selector(node)
    constraints = node.get("constraints") or selector.get("constraints") or {}
    return constraints if isinstance(constraints, dict) else {}


def _node_write_scope(node: dict[str, Any]) -> list[str]:
    raw = node.get("write_scope") or []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item)]
    return []


def _node_required_capability_names(node: dict[str, Any]) -> set[str]:
    raw = node.get("required_capabilities") or _evaluation_selector(node).get("required_capabilities") or {}
    if isinstance(raw, dict):
        return {str(name).strip().lower() for name in raw.keys() if str(name).strip()}
    if isinstance(raw, list):
        return {str(item).strip().lower() for item in raw if str(item).strip()}
    if isinstance(raw, str) and raw.strip():
        return {raw.strip().lower()}
    return set()


def _risk_tier_for_node(node: dict[str, Any]) -> str:
    task_type = _node_task_type(node)
    constraints = _node_constraints(node)
    explicit = str(
        constraints.get("risk_tier")
        or node.get("risk_tier")
        or ""
    ).strip().lower()
    if explicit in {"low", "medium", "high", "critical"}:
        return explicit
    capability_names = _node_required_capability_names(node)
    write_scope = _node_write_scope(node)
    if task_type in {"SECURITY_SENSITIVE"}:
        return "critical"
    if task_type in {"ARCH_DESIGN", "ACADEMIC_CRITIQUE", "ROOT_CAUSE_DEBUG", "SOFT_HW_OPT"}:
        return "high"
    if capability_names & {"security.review", "security", "benchmark.analysis", "benchmark", "root-cause.debug"}:
        return "high"
    if len(write_scope) > 1 or bool(write_scope):
        return "medium"
    return "low"


def _evaluation_mode_required_evaluators(mode: str) -> int:
    return {
        "single": 1,
        "staged": 1,
        "dual": 2,
        "committee": 3,
    }.get(mode, 1)


def _default_evaluation_mode(node: dict[str, Any]) -> str:
    task_type = _node_task_type(node)
    risk_tier = _risk_tier_for_node(node)
    verifier_required = bool(node.get("verifier_required")) or bool(_evaluation_selector(node).get("verifier_required"))
    if task_type == "SECURITY_SENSITIVE" or risk_tier == "critical":
        return "committee"
    if task_type in {"ARCH_DESIGN", "ACADEMIC_CRITIQUE"}:
        return "dual"
    if verifier_required or task_type in {"CODE_IMPL", "MULTI_FILE_REFACTOR", "TEST_GEN", "TEST_RUN", "DOC_REPORT", "ROOT_CAUSE_DEBUG", "SOFT_HW_OPT"}:
        return "staged"
    return "single"


def _evaluation_evidence_requirements(node: dict[str, Any], mode: str) -> list[str]:
    task_type = _node_task_type(node)
    requirements = ["handoff_md", "session_log"]
    if _node_write_scope(node):
        requirements.append("scope_compliance")
    if task_type in {"CODE_IMPL", "MULTI_FILE_REFACTOR", "TEST_GEN", "TEST_RUN", "ROOT_CAUSE_DEBUG", "SOFT_HW_OPT"}:
        requirements.extend(["patch_diff", "test_report"])
    if task_type in {"ARCH_DESIGN", "RESEARCH_SYNTHESIS", "ACADEMIC_CRITIQUE", "DOC_REPORT"}:
        requirements.append("design_or_report_artifact")
    if mode in {"dual", "committee"}:
        requirements.append("cross_evaluator_consistency")
    deduped: list[str] = []
    for item in requirements:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _normalized_evaluation_plan(plan: dict[str, Any], node: dict[str, Any], source: str) -> dict[str, Any]:
    raw_mode = str(plan.get("review_mode") or "").strip().lower()
    mode = raw_mode if raw_mode in EVALUATION_REVIEW_MODES else _default_evaluation_mode(node)
    raw_required = plan.get("required_evaluators")
    try:
        required_evaluators = max(1, int(raw_required)) if raw_required is not None else _evaluation_mode_required_evaluators(mode)
    except Exception:
        required_evaluators = _evaluation_mode_required_evaluators(mode)
    evaluator_classes = plan.get("evaluator_classes")
    if isinstance(evaluator_classes, str):
        evaluator_classes_list = [evaluator_classes] if evaluator_classes else []
    elif isinstance(evaluator_classes, list):
        evaluator_classes_list = [str(item) for item in evaluator_classes if str(item)]
    else:
        evaluator_classes_list = []
    if not evaluator_classes_list:
        evaluator_classes_list = ["Verifier"]
    independence_policy = plan.get("independence_policy")
    if not isinstance(independence_policy, dict):
        independence_policy = {}
    independence_policy = {
        "writer_same_operator": str(independence_policy.get("writer_same_operator") or "denied"),
        "writer_same_provider": str(
            independence_policy.get("writer_same_provider")
            or ("avoid" if mode in {"dual", "committee"} else "allowed")
        ),
    }
    evidence_requirements = plan.get("evidence_requirements")
    if isinstance(evidence_requirements, str):
        evidence_requirements_list = [evidence_requirements] if evidence_requirements else []
    elif isinstance(evidence_requirements, list):
        evidence_requirements_list = [str(item) for item in evidence_requirements if str(item)]
    else:
        evidence_requirements_list = []
    if not evidence_requirements_list:
        evidence_requirements_list = _evaluation_evidence_requirements(node, mode)
    escalation_on_fail = plan.get("escalation_on_fail")
    if isinstance(escalation_on_fail, str):
        escalation = [escalation_on_fail] if escalation_on_fail else []
    elif isinstance(escalation_on_fail, list):
        escalation = [str(item) for item in escalation_on_fail if str(item)]
    else:
        escalation = []
    if not escalation:
        escalation = ["HumanReview"] if mode == "committee" else ["Verifier"]
    parallelizable = bool(plan.get("parallelizable", mode in {"dual", "committee"}))
    cross_provider_required = bool(plan.get("cross_provider_required", mode in {"dual", "committee"}))
    return {
        "planning_source": source,
        "task_type": _node_task_type(node) or "N/A",
        "risk_tier": _risk_tier_for_node(node),
        "review_mode": mode,
        "required_evaluators": required_evaluators,
        "evaluator_classes": evaluator_classes_list,
        "parallelizable": parallelizable,
        "cross_provider_required": cross_provider_required,
        "independence_policy": independence_policy,
        "evidence_requirements": evidence_requirements_list,
        "escalation_on_fail": escalation,
    }


def _plan_node_evaluation(graph: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    explicit = node.get("evaluation_plan")
    if isinstance(explicit, dict) and explicit:
        return _normalized_evaluation_plan(explicit, node, "explicit")
    return _normalized_evaluation_plan({}, node, "derived")


def _evaluation_capacity_snapshot(plan: dict[str, Any], evaluators: list[dict[str, Any]]) -> dict[str, Any]:
    available = [item for item in evaluators if not item.get("busy")]
    available_panes = [str(item.get("pane") or "") for item in available if str(item.get("pane") or "")]
    required = max(1, int(plan.get("required_evaluators") or 1))
    mode = str(plan.get("review_mode") or "single")
    selected = available[:required]
    selected_panes = [str(item.get("pane") or "") for item in selected if str(item.get("pane") or "")]
    capacity_satisfied = len(selected) >= required
    quorum_dispatch_supported = True
    dispatchable_now = capacity_satisfied and quorum_dispatch_supported
    return {
        "available_evaluators": len(available),
        "available_panes": available_panes,
        "required_evaluators": required,
        "selected_panes": selected_panes,
        "capacity_satisfied": capacity_satisfied,
        "quorum_dispatch_supported": quorum_dispatch_supported,
        "review_mode": mode,
        "dispatchable_now": dispatchable_now,
    }


def _runtime_fallback_evaluation_plan(plan: dict[str, Any], capacity: dict[str, Any]) -> dict[str, Any]:
    mode = str(plan.get("review_mode") or "single")
    required = max(1, int(plan.get("required_evaluators") or 1))
    available = int(capacity.get("available_evaluators") or 0)
    if available < 1:
        return plan
    if mode not in {"dual", "committee"}:
        return plan
    if capacity.get("dispatchable_now", False):
        return plan

    fallback = dict(plan)
    fallback["requested_review_mode"] = mode
    fallback["requested_required_evaluators"] = required
    fallback["fallback_applied"] = True
    fallback["fallback_reason"] = (
        "multi_evaluator_quorum_not_implemented"
        if capacity.get("capacity_satisfied", False)
        else "insufficient_evaluator_capacity"
    )
    fallback["followup_review_required"] = True
    fallback["review_mode"] = "staged"
    fallback["required_evaluators"] = 1
    fallback["parallelizable"] = False
    fallback["cross_provider_required"] = False
    evidence = list(fallback.get("evidence_requirements", []) or [])
    for item in ["runtime_fallback_notice", "followup_independent_review_pending"]:
        if item not in evidence:
            evidence.append(item)
    fallback["evidence_requirements"] = evidence
    escalation = list(fallback.get("escalation_on_fail", []) or [])
    for item in ["Verifier", "HumanReview"]:
        if item not in escalation:
            escalation.append(item)
    fallback["escalation_on_fail"] = escalation
    return fallback


def _evaluation_plan_block(plan: dict[str, Any]) -> str:
    lines = [
        f"- Review Mode: `{plan.get('review_mode', 'single')}`",
        f"- Required Evaluators: `{plan.get('required_evaluators', 1)}`",
        f"- Risk Tier: `{plan.get('risk_tier', 'low')}`",
        f"- Evaluator Classes: {', '.join(f'`{item}`' for item in plan.get('evaluator_classes', []) or ['Verifier'])}",
        f"- Cross Provider Required: `{str(bool(plan.get('cross_provider_required'))).lower()}`",
        f"- Parallelizable: `{str(bool(plan.get('parallelizable'))).lower()}`",
        f"- Evidence Requirements: {', '.join(f'`{item}`' for item in plan.get('evidence_requirements', []) or ['handoff_md'])}",
        f"- Independence: writer_same_operator=`{((plan.get('independence_policy') or {}).get('writer_same_operator', 'denied'))}`, writer_same_provider=`{((plan.get('independence_policy') or {}).get('writer_same_provider', 'allowed'))}`",
        f"- Escalation On Fail: {', '.join(f'`{item}`' for item in plan.get('escalation_on_fail', []) or ['Verifier'])}",
    ]
    if plan.get("fallback_applied"):
        lines.append(f"- Runtime Fallback Applied: `true`")
        lines.append(f"- Requested Review Mode: `{plan.get('requested_review_mode', 'N/A')}`")
        lines.append(f"- Requested Evaluators: `{plan.get('requested_required_evaluators', 'N/A')}`")
        lines.append(f"- Fallback Reason: `{plan.get('fallback_reason', 'N/A')}`")
        lines.append(f"- Follow-up Review Required: `{str(bool(plan.get('followup_review_required'))).lower()}`")
    return "\n".join(lines)


def _read_json_file(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _deepresearch_quality_gate_from_eval(eval_json: str | Path) -> dict[str, Any]:
    data = _read_json_file(eval_json)
    gate = data.get("research_quality_gate") or data.get("deepresearch_quality_gate") or {}
    if isinstance(gate, dict) and gate:
        ok = bool(gate.get("ok")) or str(gate.get("verdict") or "").upper() == "PASS"
        return {"present": True, "ok": ok, "gate": gate}
    return {"present": False, "ok": False, "gate": {}}


def _looks_like_research_eval_data(data: dict[str, Any]) -> bool:
    return any(key in data for key in (
        "source_count",
        "evidence_count",
        "claim_count",
        "section_count",
        "unsupported_rate",
        "citation_accuracy",
        "output_dir",
        "final_md",
        "report_ast",
    ))


def _first_existing_path(candidates: list[Any], base_dir: Path | None = None, *, want_dir: bool | None = None) -> Path:
    for raw in candidates:
        raw_text = str(raw or "").strip()
        if not raw_text:
            continue
        path = Path(raw_text).expanduser()
        if not path.is_absolute() and base_dir is not None:
            path = base_dir / path
        if path.exists() and (want_dir is None or (path.is_dir() if want_dir else path.is_file())):
            return path
    return Path("")


def _discover_deepresearch_artifacts(sid: str, node: dict[str, Any], eval_json: str | Path) -> dict[str, str]:
    """Find DeepResearch artifacts from evaluator JSON, node metadata, and sprint paths."""
    eval_path = Path(eval_json).expanduser()
    eval_data = _read_json_file(eval_path) if eval_path.exists() else {}
    node_artifacts = node.get("research_artifacts") if isinstance(node.get("research_artifacts"), dict) else {}
    explicit_research_eval = [
        eval_data.get("research_eval"),
        eval_data.get("research_eval_json"),
        eval_data.get("eval_artifacts_json"),
        node_artifacts.get("research_eval"),
        node_artifacts.get("research_eval_json"),
        node_artifacts.get("eval_artifacts_json"),
        node.get("research_eval"),
        node.get("research_eval_json"),
        node.get("eval_artifacts_json"),
    ]
    research_eval = _first_existing_path(explicit_research_eval, eval_path.parent if str(eval_path) else None, want_dir=False)
    if not research_eval and eval_path.exists() and _looks_like_research_eval_data(eval_data):
        research_eval = eval_path
    if not research_eval:
        for base in [eval_path.parent if str(eval_path) else Path(""), SPRINTS_DIR / sid, SPRINTS_DIR]:
            if not str(base) or not base.exists():
                continue
            found = _first_existing_path(
                [base / "research_eval.json", base / f"{sid}-research_eval.json", base / "run-research_eval.json"],
                want_dir=False,
            )
            if found:
                research_eval = found
                break
    research_eval_data = _read_json_file(research_eval) if research_eval else {}
    base_dirs = [
        eval_path.parent if str(eval_path) else Path(""),
        SPRINTS_DIR / sid,
        SPRINTS_DIR,
    ]
    output_dir = _first_existing_path([
        research_eval_data.get("output_dir"),
        eval_data.get("output_dir"),
        node_artifacts.get("output_dir"),
        node.get("research_output_dir"),
        node.get("output_dir"),
    ], eval_path.parent if str(eval_path) else None, want_dir=True)
    if str(output_dir) not in {"", "."}:
        base_dirs.insert(0, output_dir)

    def pick(keys: list[str], names: list[str]) -> Path:
        explicit: list[Any] = []
        for key in keys:
            explicit.extend([eval_data.get(key), node_artifacts.get(key), node.get(key)])
        for base in base_dirs:
            found = _first_existing_path(explicit, base if str(base) else None, want_dir=False)
            if found:
                return found
        for base in base_dirs:
            if not str(base) or not base.exists():
                continue
            for name in names:
                candidate = base / name
                if candidate.exists():
                    return candidate
        return Path("")

    report_ast = pick(["report_ast", "report_ast_json"], ["report_ast.json"])
    final_md = pick(["final_md", "final_report", "final_report_md"], ["final.md"])
    bibliography = pick(["bibliography", "bibliography_json"], ["final.bibliography.json"])
    def file_str(path: Path) -> str:
        return str(path) if str(path) not in {"", "."} and path.exists() and path.is_file() else ""

    artifacts = {
        "eval_json": file_str(research_eval),
        "report_ast": file_str(report_ast),
        "final_md": file_str(final_md),
        "bibliography": file_str(bibliography),
    }
    if str(output_dir) not in {"", "."}:
        artifacts["output_dir"] = str(output_dir)
    return artifacts


def _deepresearch_quality_gate_auto_run(sid: str, node: dict[str, Any], eval_json: str | Path) -> dict[str, Any]:
    """Run deterministic DeepResearch gate during closeout when evaluator omitted it."""
    if evaluate_research_artifacts is None:
        return {
            "present": True,
            "ok": False,
            "auto_run": True,
            "gate": {
                "ok": False,
                "verdict": "FAIL",
                "errors": ["research_evaluator_unavailable"],
            },
        }
    artifacts = _discover_deepresearch_artifacts(sid, node, eval_json)
    research_eval = artifacts.get("eval_json") or ""
    if not research_eval or not Path(research_eval).expanduser().exists():
        return {
            "present": False,
            "ok": False,
            "auto_run": True,
            "gate": {
                "ok": False,
                "verdict": "FAIL",
                "errors": [f"research_eval_artifact_missing:{research_eval or 'N/A'}"],
                "artifacts": artifacts,
            },
        }
    gate = evaluate_research_artifacts(
        research_eval,
        report_ast=artifacts.get("report_ast") or None,
        final_md=artifacts.get("final_md") or None,
        bibliography=artifacts.get("bibliography") or None,
    )
    gate["auto_run"] = True
    gate["discovered_artifacts"] = artifacts
    return {"present": True, "ok": bool(gate.get("ok")), "auto_run": True, "gate": gate}


def _ensure_research_run(db_path: Path, topic: str, existing_run_id: str = "") -> str:
    if research_storage is None:
        raise RuntimeError("research storage unavailable")
    conn = research_storage.init_db(str(db_path))
    if existing_run_id:
        row = conn.execute("SELECT id FROM research_runs WHERE id = ?", (existing_run_id,)).fetchone()
        if row:
            conn.close()
            return existing_run_id
    conn.execute(
        "INSERT INTO research_runs (topic, depth_tier, status) VALUES (?, 'standard', 'pending')",
        (topic or "Human search run",),
    )
    conn.commit()
    run_id = conn.execute("SELECT id FROM research_runs ORDER BY created_at DESC LIMIT 1").fetchone()["id"]
    conn.close()
    return run_id


def _prepare_human_search_handoff(sid: str, graph_path: str | Path, node: dict[str, Any], dry_run: bool = False) -> dict[str, Any] | None:
    """Create a durable human-search handoff instead of dispatching a pane."""
    if not _node_requires_human_search(node):
        return None
    if render_human_search_handoff is None:
        return {"ok": False, "reason": "human_search_renderer_unavailable", "node": node.get("id")}

    node_id = str(node.get("id") or "")
    metadata = node.get("human_search") if isinstance(node.get("human_search"), dict) else {}
    db_path = Path(str(metadata.get("db_path") or SPRINTS_DIR / f"{sid}.research.sqlite"))
    handoff_md = Path(str(metadata.get("handoff_md") or SPRINTS_DIR / f"{sid}.{node_id}-human-search-handoff.md"))
    results_md = Path(str(metadata.get("results_md") or SPRINTS_DIR / f"{sid}.{node_id}-human-search-results.md"))
    query = str(node.get("search_query") or node.get("goal") or node_id)
    topic = str(node.get("topic") or node.get("goal") or sid)
    max_results = int(node.get("max_results") or metadata.get("max_results") or 8)

    if dry_run:
        return {
            "ok": True,
            "reason": "human_search_handoff_required",
            "node": node_id,
            "handoff_md": str(handoff_md),
            "results_md": str(results_md),
            "dry_run": True,
        }

    run_id = _ensure_research_run(db_path, topic, str(metadata.get("run_id") or ""))
    handoff_md.parent.mkdir(parents=True, exist_ok=True)
    handoff_md.write_text(
        render_human_search_handoff(topic=topic, query=query, run_id=run_id, max_results=max_results),
        encoding="utf-8",
    )

    graph = load_graph(graph_path)
    live = next((n for n in graph.get("nodes", []) if n.get("id") == node_id), node)
    live["status"] = "waiting_human_search"
    live["human_search"] = {
        "provider": "human-in-the-loop",
        "status": "waiting",
        "db_path": str(db_path),
        "run_id": run_id,
        "handoff_md": str(handoff_md),
        "results_md": str(results_md),
        "import_command": (
            f"solar-harness research import-search {db_path} --run-id {run_id} "
            f"--input-md {results_md} --continue --output-dir {SPRINTS_DIR / (sid + '.research-out')} "
            f"--output-md {SPRINTS_DIR / (sid + '.final.md')} --graph {graph_path} --node {node_id}"
        ),
    }
    graph.setdefault("node_results", {})[node_id] = {
        "status": "waiting_human_search",
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "handoff_md": str(handoff_md),
        "results_md": str(results_md),
        "run_id": run_id,
    }
    save_graph(graph_path, graph)
    try:
        _append_event(sid, {
            "event": "human_search_handoff_created",
            "by": "graph-dispatch",
            "data": {"node": node_id, "handoff_md": str(handoff_md), "results_md": str(results_md), "run_id": run_id},
        })
    except Exception:
        pass
    return {
        "ok": True,
        "reason": "waiting_human_search",
        "node": node_id,
        "handoff_md": str(handoff_md),
        "results_md": str(results_md),
        "run_id": run_id,
        "graph_updated": True,
    }


def _no_dispatch_enabled() -> bool:
    return os.environ.get("SOLAR_NO_DISPATCH") == "1" or NO_DISPATCH_FLAG.exists()


def _model_registry() -> dict[str, Any]:
    if _load_model_registry is not None:
        try:
            return _load_model_registry()
        except Exception:
            pass
    path = HARNESS_DIR / "config" / "model-registry.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "defaults": {"main_model": "opus", "lab_builder_matrix": "glm,glm,glm,anthropic-sonnet"},
            "models": {},
        }


def _normalize_model_alias(alias: str) -> str:
    reg = _model_registry()
    if _normalize_model is not None:
        try:
            return str(_normalize_model(reg, alias))
        except Exception:
            pass
    value = str(alias or "").strip().lower()
    fallback = {
        "opus": "claude-opus",
        "claude-opus": "claude-opus",
        "anthropic-sonnet": "claude-sonnet",
        "claude-sonnet": "claude-sonnet",
        "claude": "claude-sonnet",
        "glm": "zhipu-glm-5.1",
        "glm-5": "zhipu-glm-5.1",
        "glm-5.1": "zhipu-glm-5.1",
        "sonnet": "zhipu-glm-4.7",
        "glm-4.7": "zhipu-glm-4.7",
        "deepseek": "deepseek-v4-pro",
        "deepseek-v4-pro": "deepseek-v4-pro",
    }
    return fallback.get(value, value)


def _model_alias_set(alias: str) -> list[str]:
    reg = _model_registry()
    model_id = _normalize_model_alias(alias)
    spec = (reg.get("models") or {}).get(model_id) or {}
    values = {model_id, str(alias or "").strip().lower()}
    values.update(str(x).strip().lower() for x in (spec.get("aliases") or []) if str(x).strip())
    if spec.get("model_key"):
        values.add(str(spec["model_key"]).strip().lower())
    return sorted(v for v in values if v)


def _matrix_items(matrix: str) -> list[str]:
    return [x.strip() for x in str(matrix or "").split(",") if x.strip()]


def _load_user_config() -> dict[str, Any]:
    try:
        return json.loads((HARNESS_DIR / "config" / "solar-user-config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _configured_main_model(role: str) -> str:
    reg = _model_registry()
    cfg = _load_user_config()
    models = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    default = (reg.get("defaults") or {}).get("main_model") or "opus"
    return str(models.get(role) or default)


def _configured_lab_model_for_pane(pane: str) -> str:
    reg = _model_registry()
    cfg = _load_user_config()
    models = cfg.get("models") if isinstance(cfg.get("models"), dict) else {}
    matrix = str(models.get("lab_builder_matrix") or (reg.get("defaults") or {}).get("lab_builder_matrix") or "glm,glm,glm,anthropic-sonnet")
    items = _matrix_items(matrix)
    if not items:
        return "anthropic-sonnet"
    try:
        index = int(str(pane).rsplit(".", 1)[1])
    except Exception:
        index = 0
    return items[index] if index < len(items) else items[-1]


def _models_for_pane(pane: str, title: str = "") -> list[str]:
    if pane == f"{SESSION}:0.2":
        return _model_alias_set(_configured_main_model("builder"))
    if pane == f"{SESSION}:0.3":
        return _model_alias_set(_configured_main_model("evaluator"))
    if pane.startswith("solar-harness-lab:"):
        return _model_alias_set(_configured_lab_model_for_pane(pane))
    title_lower = title.lower()
    if "deepseek" in title_lower:
        return _model_alias_set("deepseek")
    if "glm-5.1" in title_lower or "glm" in title_lower:
        return _model_alias_set("glm")
    if "opus" in title_lower:
        return _model_alias_set("opus")
    if "sonnet" in title_lower:
        return _model_alias_set("anthropic-sonnet")
    return _model_alias_set("anthropic-sonnet")


def _quota_models_for_provider(provider: str) -> list[str]:
    provider = str(provider or "").strip().lower()
    if provider in {"anthropic", "claude", "claude-code"}:
        values = set(_model_alias_set("anthropic-sonnet"))
        values.update(_model_alias_set("claude-opus"))
        values.update({"anthropic", "claude", "sonnet", "opus"})
        return sorted(values)
    if provider in {"zhipu", "glm", "bigmodel"}:
        return _model_alias_set("glm")
    if provider == "deepseek":
        return _model_alias_set("deepseek")
    return []


def _quota_exhausted_models(title: str, tail: str, health: dict[str, Any], models: list[str]) -> list[str]:
    values: set[str] = set()
    combined = f"{title}\n{tail}".lower()
    health_reason = str(health.get("reason") or health.get("status") or "").lower()
    health_provider = str(health.get("provider") or health.get("vendor") or "").lower()

    if PANE_QUOTA_EXHAUSTED_RE.search(combined) or "quota" in health_reason or "rate_limit" in health_reason:
        values.update(str(model).lower() for model in models if str(model).strip())

    if ("anthropic" in combined or "claude" in combined or "monthly usage limit" in combined
            or health_provider in {"anthropic", "claude", "claude-code"}):
        if PANE_QUOTA_EXHAUSTED_RE.search(combined) or "quota" in health_reason or "rate_limit" in health_reason:
            values.update(_quota_models_for_provider("anthropic"))

    if "glm" in combined or health_provider in {"zhipu", "glm", "bigmodel"}:
        if PANE_QUOTA_EXHAUSTED_RE.search(combined) or "quota" in health_reason or "rate_limit" in health_reason:
            values.update(_quota_models_for_provider("zhipu"))

    if "deepseek" in combined or health_provider == "deepseek":
        if PANE_QUOTA_EXHAUSTED_RE.search(combined) or "quota" in health_reason or "rate_limit" in health_reason:
            values.update(_quota_models_for_provider("deepseek"))

    return sorted(v for v in values if v)


def _node_id_from_intent(intent: str) -> str:
    match = re.search(r"(?:^|\|)node_id=([^|]+)", intent or "")
    return match.group(1) if match else ""


def _scope_lines(values: Any) -> str:
    if not values:
        return "- N/A"
    if isinstance(values, str):
        values = [values]
    return "\n".join(f"- `{v}`" for v in values)


def _acceptance_lines(values: Any) -> str:
    if not values:
        return "- N/A"
    return "\n".join(f"- [ ] {v}" for v in values)


def _dispatch_file(sid: str, node_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", node_id).strip("-") or "node"
    return SPRINTS_DIR / f"{sid}.{safe}-dispatch.md"


def _safe_node_id(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", node_id).strip("-") or "node"


def _pane_safe(pane: str) -> str:
    return pane.replace(":", "_").replace(".", "_")


def _pane_health(pane: str) -> dict[str, Any]:
    path = HARNESS_DIR / "run" / "provider-health" / f"{_pane_safe(pane)}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    until = str(data.get("quarantine_until") or "")
    if until and until <= _utc_now():
        return {}
    if _provider_health_stale(data):
        return {}
    return data


def _parse_health_ts(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(text, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            pass
    return None


def _provider_health_stale(data: dict[str, Any]) -> bool:
    """Do not let old temporary quota failures permanently remove panes."""
    if not data.get("unavailable") and str(data.get("status") or "").lower() != "unavailable":
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    reset_at = _parse_health_ts(data.get("reset_at_provider_time"))
    if reset_at and reset_at <= now:
        return True
    checked_at = _parse_health_ts(data.get("checked_at"))
    if not checked_at:
        return False
    ttl = int(os.environ.get("SOLAR_PROVIDER_HEALTH_UNAVAILABLE_TTL_SEC", "21600"))
    return (now - checked_at).total_seconds() > ttl


def _handoff_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-handoff.md"


def _legacy_handoff_aliases(node_id: str) -> list[str]:
    aliases: list[str] = []
    raw = str(node_id or "").strip()
    if not raw:
        return aliases

    short = raw.split("_", 1)[0].strip()
    if short and short != raw and re.fullmatch(r"[A-Za-z]+\d+", short):
        aliases.append(short)

    match = re.match(r"^([A-Za-z]+\d+)\b", raw)
    if match:
        alias = match.group(1).strip()
        if alias and alias != raw and alias not in aliases:
            aliases.append(alias)
    return aliases


def _node_handoff_candidates(sid: str, node: dict[str, Any], graph: dict[str, Any]) -> list[Path]:
    node_id = str(node.get("id") or "")
    candidates = [_handoff_file(sid, node_id)]
    for alias in _legacy_handoff_aliases(node_id):
        candidates.append(_handoff_file(sid, alias))
    parent_handoff = f"sprints/{sid}.handoff.md"
    for scope in node.get("write_scope") or []:
        if str(scope).endswith(parent_handoff) or str(scope).endswith(f"{sid}.handoff.md"):
            candidates.append(SPRINTS_DIR / f"{sid}.handoff.md")
            break
    return candidates


def _existing_node_handoff(sid: str, node: dict[str, Any], graph: dict[str, Any]) -> Path | None:
    for candidate in _node_handoff_candidates(sid, node, graph):
        if candidate.exists():
            return candidate
    return None


def _ledger_dispatch_for(sid: str, instruction_file: Path) -> dict[str, Any]:
    if not DISPATCH_LEDGER.exists():
        return {}
    needle = str(instruction_file)
    found: dict[str, Any] = {}
    for raw in DISPATCH_LEDGER.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if row.get("sid") != sid or row.get("kind") != "intent_injected":
            continue
        text = json.dumps(row, ensure_ascii=False)
        if needle not in text:
            continue
        found = row
    return found


def _reconcile_existing_dispatches(graph: dict[str, Any], graph_path: str | Path) -> list[dict[str, Any]]:
    sid = str(graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", ""))
    repaired: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        status = node_status(graph, node_id)
        handoff_file = _existing_node_handoff(sid, node, graph)
        if handoff_file and status in {"pending", "queued", "blocked", "assigned", "dispatched", "in_progress", "running", ""}:
            set_node_status(graph, node_id, "reviewing")
            node["status"] = "reviewing"
            node["updated_at"] = _utc_now()
            repaired.append({"node": node_id, "status": "reviewing", "reason": "handoff_file_exists", "handoff": str(handoff_file)})
            continue
        if status in {"assigned", "dispatched", "in_progress", "running"}:
            pane = str(node.get("assigned_to") or "").strip()
            dispatch_id = str(node.get("dispatch_id") or "").strip()
            if pane and dispatch_id:
                unavailable_reason = _pane_runtime_unavailable_reason(pane, _pane_title(pane)) or _pane_unavailable_reason(pane)
                if unavailable_reason:
                    release_lease(pane, dispatch_id, f"graph_dispatch_reconcile_unavailable:{unavailable_reason}")
                    node.pop("assigned_to", None)
                    node.pop("dispatch_id", None)
                    node["dispatch_retry_reason"] = unavailable_reason
                    node["updated_at"] = _utc_now()
                    graph.setdefault("node_results", {})
                    graph["node_results"][node_id] = {
                        "status": "worker_blocked",
                        "updated_at": node["updated_at"],
                        "blocking_reason": unavailable_reason,
                    }
                    node["status"] = "worker_blocked"
                    repaired.append(
                        {
                            "node": node_id,
                            "pane": pane,
                            "dispatch_id": dispatch_id,
                            "status": "worker_blocked",
                            "reason": unavailable_reason,
                        }
                    )
                    continue
        if status in {"reviewing", "ready_for_review", "needs_human_review", "failed_review"}:
            assignments = _node_eval_assignments(node)
            blocked_assignment = None
            for assignment in assignments:
                pane = str(assignment.get("pane") or "").strip()
                if not pane:
                    continue
                unavailable_reason = _pane_runtime_unavailable_reason(pane, _pane_title(pane)) or _pane_unavailable_reason(pane)
                if unavailable_reason:
                    blocked_assignment = {
                        "pane": pane,
                        "dispatch_id": str(assignment.get("dispatch_id") or "").strip(),
                        "reason": unavailable_reason,
                    }
                    break
            if blocked_assignment:
                if blocked_assignment["dispatch_id"]:
                    release_lease(
                        blocked_assignment["pane"],
                        blocked_assignment["dispatch_id"],
                        f"graph_eval_reconcile_unavailable:{blocked_assignment['reason']}",
                    )
                _clear_eval_assignments(node)
                node["eval_retry_reason"] = blocked_assignment["reason"]
                node["updated_at"] = _utc_now()
                repaired.append(
                    {
                        "node": node_id,
                        "pane": blocked_assignment["pane"],
                        "dispatch_id": blocked_assignment["dispatch_id"],
                        "status": status,
                        "reason": blocked_assignment["reason"],
                    }
                )
                continue
        if status not in {"pending", "queued", "blocked", ""}:
            continue
        instruction_file = _dispatch_file(sid, node_id)
        if not instruction_file.exists():
            continue
        ledger = _ledger_dispatch_for(sid, instruction_file)
        if not ledger:
            continue
        pane = str(ledger.get("pane") or "")
        dispatch_id = str(ledger.get("dispatch_id") or "")
        ack_file = HARNESS_DIR / "sprints" / "graph-acks" / f"{sid}.{node_id}-submit-ack.json"
        if not ack_file.exists():
            continue
        try:
            ack = json.loads(ack_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(ack.get("dispatch_id") or "") != dispatch_id:
            continue
        set_node_status(graph, node_id, "dispatched", pane=pane or None, dispatch_id=dispatch_id or None)
        repaired.append({"node": node_id, "pane": pane, "dispatch_id": dispatch_id, "reason": "submit_ack_exists"})
    return repaired


def _eval_dispatch_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval-dispatch.md"


def _eval_md_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval.md"


def _eval_json_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval.json"


def _eval_peer_md_file(sid: str, node_id: str, index: int) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval-q{index}.md"


def _eval_peer_json_file(sid: str, node_id: str, index: int) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval-q{index}.json"


def _eval_dispatch_member_file(sid: str, node_id: str, index: int) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval-dispatch-q{index}.md"


def _node_eval_assignments(node: dict[str, Any]) -> list[dict[str, Any]]:
    raw = node.get("eval_assignments")
    if isinstance(raw, list):
        normalized: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            pane = str(item.get("pane") or "").strip()
            dispatch_id = str(item.get("dispatch_id") or "").strip()
            if not pane or not dispatch_id:
                continue
            normalized.append(
                {
                    "pane": pane,
                    "dispatch_id": dispatch_id,
                    "role": str(item.get("role") or "secondary"),
                    "eval_md_path": str(item.get("eval_md_path") or ""),
                    "eval_json_path": str(item.get("eval_json_path") or ""),
                }
            )
        if normalized:
            return normalized
    pane = str(node.get("eval_assigned_to") or "").strip()
    dispatch_id = str(node.get("eval_dispatch_id") or "").strip()
    if pane and dispatch_id:
        return [
            {
                "pane": pane,
                "dispatch_id": dispatch_id,
                "role": "primary",
                "eval_md_path": str(node.get("eval_md_path") or ""),
                "eval_json_path": str(node.get("eval_json") or ""),
            }
        ]
    return []


def _store_eval_assignments(node: dict[str, Any], assignments: list[dict[str, Any]], dispatched_at: str) -> None:
    normalized = [
        {
            "pane": str(item.get("pane") or ""),
            "dispatch_id": str(item.get("dispatch_id") or ""),
            "role": str(item.get("role") or "secondary"),
            "eval_md_path": str(item.get("eval_md_path") or ""),
            "eval_json_path": str(item.get("eval_json_path") or ""),
        }
        for item in assignments
        if str(item.get("pane") or "") and str(item.get("dispatch_id") or "")
    ]
    node["eval_assignments"] = normalized
    primary = next((item for item in normalized if item.get("role") == "primary"), normalized[0] if normalized else {})
    node["eval_assigned_to"] = str(primary.get("pane") or "")
    node["eval_dispatch_id"] = str(primary.get("dispatch_id") or "")
    node["eval_dispatched_at"] = dispatched_at


def _clear_eval_assignments(node: dict[str, Any]) -> None:
    node.pop("eval_assignments", None)
    node.pop("eval_assigned_to", None)
    node.pop("eval_dispatch_id", None)
    node.pop("eval_dispatched_at", None)


def _queue_file(sprint_id: str) -> Path:
    qdir = HARNESS_DIR / "run" / "queue"
    qdir.mkdir(parents=True, exist_ok=True)
    return qdir / f"{sprint_id}.jsonl"


def _is_graph_queue_item(item: dict[str, Any]) -> bool:
    intent = item.get("intent", "")
    return "graph_node|" in intent or bool((item.get("payload") or {}).get("node"))


def _pop_graph_queue_item(sprint_id: str) -> dict[str, Any] | None:
    """Pop only graph-node items so legacy PM/planner queue entries do not block DAG dispatch."""
    qf = _queue_file(sprint_id)
    if not qf.exists():
        return None
    lock_path = str(qf) + ".lock"
    with open(lock_path, "a") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            items: list[dict[str, Any]] = []
            for line in qf.read_text().splitlines():
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
            pending = sorted(
                [item for item in items if not item.get("consumed") and _is_graph_queue_item(item)],
                key=lambda x: (-x.get("priority", 0), x.get("enqueued_at", "")),
            )
            if not pending:
                return None
            target = pending[0]
            target["consumed"] = True
            target["consumed_at"] = _utc_now()
            for idx, item in enumerate(items):
                if item.get("id") == target.get("id"):
                    items[idx] = target
                    break
            tmp = str(qf) + ".tmp"
            with open(tmp, "w") as f:
                for item in items:
                    f.write(json.dumps(item) + "\n")
            os.replace(tmp, str(qf))
            return target
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
            # The lock is advisory and fd-scoped. Leaving an empty sidecar
            # behind makes patrols treat a healthy queue read as a stale lock.
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _node_by_id(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _graph_node_runtime_state(graph_path: str, node_id: str) -> dict[str, Any]:
    try:
        graph = load_graph(graph_path)
        node = _node_by_id(graph, node_id) or {}
        result = (graph.get("node_results") or {}).get(node_id) or {}
        status = str(node_status(graph, node_id) or "pending").lower()
        active_statuses = {"assigned", "dispatched", "in_progress", "running"}
        return {
            "ok": True,
            "status": status,
            "dispatch_id": (node.get("dispatch_id") or result.get("dispatch_id") or "") if status in active_statuses else "",
            "assigned_to": (node.get("assigned_to") or result.get("assigned_to") or "") if status in active_statuses else "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "status": ""}


def _mark_graph_node(graph_path: str, node_id: str, status: str,
                     pane: str | None = None, dispatch_id: str | None = None,
                     clear_assignment: bool = False) -> bool:
    try:
        graph = load_graph(graph_path)
        for node in graph.get("nodes", []):
            if node.get("id") != node_id:
                continue
            updated_at = _utc_now()
            node["status"] = status
            node["updated_at"] = updated_at
            results = graph.setdefault("node_results", {})
            if status in {"pending", "queued", "blocked", ""}:
                results.pop(node_id, None)
            else:
                results[node_id] = {"status": status, "updated_at": updated_at}
            if clear_assignment:
                node.pop("assigned_to", None)
                node.pop("dispatch_id", None)
                if isinstance(results.get(node_id), dict):
                    results[node_id].pop("assigned_to", None)
                    results[node_id].pop("dispatch_id", None)
            else:
                if pane:
                    node["assigned_to"] = pane
                    if isinstance(results.get(node_id), dict):
                        results[node_id]["assigned_to"] = pane
                if dispatch_id:
                    node["dispatch_id"] = dispatch_id
                    if isinstance(results.get(node_id), dict):
                        results[node_id]["dispatch_id"] = dispatch_id
            save_graph(graph_path, graph)
            return True
    except Exception:
        return False
    return False


def build_dispatch_text(payload: dict[str, Any], pane: str) -> str:
    node = payload.get("node") or {}
    sid = payload.get("sprint_id") or payload.get("sid") or ""
    node_id = node.get("id") or payload.get("node_id") or _node_id_from_intent(payload.get("intent", ""))
    graph_path = payload.get("graph") or str(SPRINTS_DIR / f"{sid}.task_graph.json")
    dispatch_id = payload.get("dispatch_id", "")
    graph_for_policy: dict[str, Any] = {}
    try:
        graph_for_policy = load_graph(graph_path)
    except Exception:
        graph_for_policy = {"nodes": [node]}
    architecture_block = dispatch_policy_block(node, graph_for_policy) if dispatch_policy_block else "## Architecture Guard\n\n- unavailable"

    return f"""{STATE_READ_PREFLIGHT}
{DEFINITION_OF_DONE_POLICY}

# DAG Node Dispatch — {sid} / {node_id}

Sprint: `{sid}`
Node: `{node_id}`
Pane: `{pane}`
Dispatch ID: `{dispatch_id or "N/A"}`
Graph: `{graph_path}`

## Goal

{node.get("goal", "N/A")}

## Required Skills

{_scope_lines(node.get("required_skills"))}

## Required Capabilities

{_scope_lines(node.get("required_capabilities"))}

## Read Scope

{_scope_lines(node.get("read_scope"))}

## Write Scope

{_scope_lines(node.get("write_scope"))}

{architecture_block}

## Acceptance

{_acceptance_lines(node.get("acceptance"))}

## Rules

- 只做本节点，不接手其他 DAG node。
- 只允许修改 `Write Scope` 里的文件/目录；需要扩大范围时写入 handoff 的 `Scope Change Request`，不要直接扩大。
- 不要把 parent sprint 标成 passed。
- 不要等待用户确认；遇到阻塞先写清楚证据和最小修复建议。
- 不要停在“继续/要不要继续/等待 review”提示；只要本节点 acceptance 未完成，就自主继续执行。
- 完成后必须写 handoff 并把本节点标记为 `reviewing`；这是释放下游和 evaluator 的唯一闭环。

## Work Steps

1. 读取 graph 和合约：
   ```bash
   cat "{graph_path}"
   cat "{SPRINTS_DIR / f'{sid}.contract.md'}"
   ```

2. 按本节点 goal/acceptance 实现。

3. 运行本节点相关验证；把命令和结果写入 handoff。

4. 写节点 handoff：
   ```bash
   cat > "{SPRINTS_DIR / f'{sid}.{node_id}-handoff.md'}" <<'EOF'
   # Handoff — {sid} / {node_id}

   ## Summary

   ## Changed Files

   ## Verification Evidence

   ## Capability / KB Usage Evidence

   - 写明实际使用了 dispatch 中哪些 Solar capability / skill / KB context。
   - 如果未使用，写明原因；不要把“被注入”当成“已使用”。

   ## Scope Compliance

   ## Known Risks

   ## Not Done
   EOF
   ```

5. 将节点状态置为 reviewing，等待 evaluator：
   ```bash
   {HARNESS_DIR}/solar-harness.sh graph-scheduler mark --graph "{graph_path}" --node "{node_id}" --status reviewing --in-place
   ```
"""


def build_eval_dispatch_text(graph: dict[str, Any], graph_path: str, node: dict[str, Any], pane: str,
                             dispatch_id: str, *, evaluator_role: str = "primary",
                             evaluator_index: int = 1, evaluator_total: int = 1,
                             eval_md_override: Path | None = None,
                             eval_json_override: Path | None = None,
                             peer_eval_json_paths: list[str] | None = None,
                             canonical_eval_json_path: str = "",
                             canonical_eval_md_path: str = "") -> str:
    sid = str(graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", ""))
    node_id = str(node.get("id") or "")
    evaluation_plan = node.get("evaluation_plan_runtime") or node.get("evaluation_plan")
    if not isinstance(evaluation_plan, dict) or not evaluation_plan:
        evaluation_plan = _plan_node_evaluation(graph, node)
    handoff = _existing_node_handoff(sid, node, graph) or _handoff_file(sid, node_id)
    handoff_candidates = "\n".join(f"- `{candidate}`" for candidate in _node_handoff_candidates(sid, node, graph))
    eval_md = eval_md_override or _eval_md_file(sid, node_id)
    eval_json = eval_json_override or _eval_json_file(sid, node_id)
    node_dispatch = _dispatch_file(sid, node_id)
    contract = SPRINTS_DIR / f"{sid}.contract.md"
    architecture_block = dispatch_policy_block(node, graph) if dispatch_policy_block else "## Architecture Guard\n\n- unavailable"
    peer_eval_json_paths = peer_eval_json_paths or []
    canonical_eval_json_path = canonical_eval_json_path or str(_eval_json_file(sid, node_id))
    canonical_eval_md_path = canonical_eval_md_path or str(_eval_md_file(sid, node_id))
    peer_block = "\n".join(f"- `{path}`" for path in peer_eval_json_paths) if peer_eval_json_paths else "- `N/A`"
    verdict_step = f"""3. 提交节点 verdict。通过时会自动释放下游 ready node；失败时只阻塞依赖它的下游：
   ```bash
   {HARNESS_DIR}/solar-harness.sh graph-dispatch node-verdict --graph "{graph_path}" --node "{node_id}" --verdict pass --eval-json "{eval_json}"
   ```

   如果失败，改用：
   ```bash
   {HARNESS_DIR}/solar-harness.sh graph-dispatch node-verdict --graph "{graph_path}" --node "{node_id}" --verdict fail --eval-json "{eval_json}" --reason "写清楚失败原因"
   ```
""" if evaluator_role == "primary" else f"""3. 不要直接提交 node verdict。你是并行副评审，只负责产出 sidecar 评审结果：
   - Markdown sidecar: `{eval_md}`
   - JSON sidecar: `{eval_json}`
   - Canonical evaluator 负责最终合并并提交：`{canonical_eval_json_path}`
"""
    role_rules = """- 你是主评审（primary），负责读取所有副评审 sidecar 并合并成 canonical verdict。
- 对于 dual/committee 模式，若副评审 sidecar 尚未出现，先轮询等待这些文件；不要抢先在没有 peer evidence 的情况下提交 PASS。""" if evaluator_role == "primary" and evaluator_total > 1 else (
"""- 你是并行副评审（secondary），不要写 canonical eval.json，也不要直接调用 node-verdict。
- 专注给出独立证据与 verdict sidecar，供主评审合并。""" if evaluator_role != "primary" else "- 当前只有一个 evaluator；直接完成 canonical verdict。"
)

    return f"""{STATE_READ_PREFLIGHT}
{DEFINITION_OF_DONE_POLICY}

# DAG Node Evaluation Dispatch — {sid} / {node_id}

Sprint: `{sid}`
Node: `{node_id}`
Pane: `{pane}`
Dispatch ID: `{dispatch_id}`
Evaluator Role: `{evaluator_role}`
Evaluator Index: `{evaluator_index}/{evaluator_total}`
Graph: `{graph_path}`
Handoff: `{handoff}`

## Handoff Candidates

{handoff_candidates}

## Evaluation Scope

- 只评审本 DAG node：`{node_id}`。
- 不要评审 parent sprint。
- 不要把 parent sprint 标成 passed。
- 只根据 node goal / acceptance / write_scope / handoff evidence 给 verdict。
- {role_rules}

## Node Goal

{node.get("goal", "N/A")}

## Acceptance

{_acceptance_lines(node.get("acceptance"))}

## Required Capabilities

{_scope_lines(node.get("required_capabilities"))}

## Evaluation Plan

{_evaluation_plan_block(evaluation_plan)}

## Write Scope

{_scope_lines(node.get("write_scope"))}

{architecture_block}

## Required Reads

```bash
cat "{graph_path}"
cat "{contract}"
cat "{node_dispatch}"
test -f "{handoff}" && cat "{handoff}"
solar-harness session evaluate "{sid}" --json
```

## Log-Native Evaluation Requirement

- 评审必须消费 append-only session log，不得只看最终 handoff 文件。
- 在 eval.md 的 `Evidence Checked` 中写入 `Session Log: solar-harness session evaluate used`。
- 如果 `session evaluate` 返回 errors/warnings，必须逐项解释是否阻塞本 node verdict。
- 必须检查 `Architecture Guard`：新能力是否为 package/plugin/skill/connector；如触碰 protected core，必须有 `core_patch_allowed=true`、rollback 和 P0 bugfix 证据，否则 FAIL。
- 涉及 online exploration 的 node 必须验证 >=2 个候选方向和 kill_criteria；否则 FAIL。
- 如果本 node 涉及 DeepResearch / evidence ledger / claim ledger / citation / report compiler，必须先运行 deterministic artifact gate：
  ```bash
  solar-harness research eval-artifacts --eval-json "<path-to-research_eval.json>" --json
  ```
  并把返回 JSON 原样写入 `{eval_json}` 的 `research_quality_gate` 字段。没有 `research_quality_gate.ok=true` 不允许 PASS。

## Required Outputs

1. 写 Markdown 评审：
   ```bash
   cat > "{eval_md}" <<'EOF'
   # Node Evaluation — {sid} / {node_id}

   ## Verdict

   PASS 或 FAIL

   ## Evidence Checked

   ## Capability / KB Usage Evidence Checked

   - 检查 handoff 是否说明实际使用了哪些 capability / KB context。
   - 如果 eval PASS，必须说明这些能力证据是否支撑验收。

   ## Acceptance Result

   ## Scope Compliance

   ## Architecture Guard Compliance

   ## Risks

   ## Required Fixes
   EOF
   ```

2. 写机器可读 JSON：
   ```bash
   cat > "{eval_json}" <<'EOF'
   {{
     "node_id": "{node_id}",
     "verdict": "PASS",
     "summary": "",
     "evaluation_plan": {json.dumps(evaluation_plan, ensure_ascii=False, indent=2)},
     "research_quality_gate": {{}},
     "checked_at": "{_utc_now()}",
     "eval_md_path": "{eval_md}"
    }}
    EOF
   ```

## Peer Evaluator Sidecars

{peer_block}

## Canonical Eval Outputs

- Markdown: `{canonical_eval_md_path}`
- JSON: `{canonical_eval_json_path}`

{verdict_step}
"""


def _pane_exists(pane: str) -> bool:
    try:
        return subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane, "#{pane_id}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).returncode == 0
    except Exception:
        return False


def _pane_title(pane: str) -> str:
    try:
        return subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane, "#{pane_title}"],
            text=True,
            capture_output=True,
            timeout=2,
        ).stdout.strip()
    except Exception:
        return ""


def _pane_title_matches_role(pane: str, title: str, role: str) -> bool:
    if os.environ.get("SOLAR_GRAPH_ALLOW_ANY_ROLE_PANE") == "1":
        return True
    title = title or _pane_title(pane)
    # Ignore trailing `| 状态:working/...:sprint-...pm-pane-...` metadata so a
    # sprint id containing `pm-pane` does not look like a PM role conflict.
    title = re.split(r"\s+\|\s+状态:", title or "", maxsplit=1)[0].strip()
    negative = re.compile(r"PM|产品经理|Planner|规划者|Builder|建设者|Evaluator|审判官", re.I)
    if role == "builder":
        if (
            pane.startswith("solar-harness-lab:")
            or pane.startswith("solar-harness-multi-task:")
        ):
            return bool(re.search(r"Builder|建设者|lab-builder", title, re.I)) and not bool(
                re.search(r"PM|产品经理|Planner|规划者|Evaluator|审判官", title, re.I)
            )
        return False
    if role == "evaluator":
        if not (
            pane == f"{SESSION}:0.3"
            or pane.startswith("solar-harness-lab:")
            or pane.startswith("solar-harness-multi-task:")
            or pane.startswith(f"{SESSION}:")
        ):
            return False
        non_role_title = re.sub(r"Evaluator|审判官", "", title, flags=re.I)
        return bool(re.search(r"Evaluator|审判官", title, re.I)) and not bool(
            negative.search(non_role_title)
        )
    return False


def _pane_execution_priority(pane: str) -> tuple[int, str]:
    if pane.startswith("solar-harness-multi-task:"):
        return (0, pane)
    if pane.startswith("solar-harness-lab:"):
        return (1, pane)
    if pane.startswith(f"{SESSION}:"):
        return (2, pane)
    return (9, pane)


def _pane_tail(pane: str, lines: int = 80) -> str:
    try:
        return subprocess.run(
            ["tmux", "capture-pane", "-pt", pane, "-S", f"-{lines}"],
            text=True,
            capture_output=True,
            timeout=2,
        ).stdout
    except Exception:
        return ""


def _pane_current_command(pane: str) -> str:
    try:
        return subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane, "#{pane_current_command}"],
            text=True,
            capture_output=True,
            timeout=2,
        ).stdout.strip()
    except Exception:
        return ""


def _pane_current_prompt_has_residue(text: str) -> bool:
    """Return true only when the visible current prompt has unsubmitted text.

    `capture-pane` includes prompt history. Searching the whole tail for
    `❯ text` makes an idle pane unavailable after any recent submitted command.
    Only inspect the final prompt line and stop at status/footer lines.
    """
    lines = [line.rstrip() for line in text.splitlines()]
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("⏵", "?", "────────────────", "Esc ", "esc ", "Tab ", "Press up ")):
            continue
        if stripped.startswith("❯"):
            remainder = stripped[1:].strip()
            return bool(remainder) and not remainder.startswith("Try ")
        return False
    return False


def _pane_prompt_residue_is_stale_scrollback(pane: str, text: str) -> bool:
    """Return true for old completed Claude output, not live editable input.

    In some panes `capture-pane` keeps the last completed Claude prompt visible
    after the process has returned to a shell. That prompt line is scrollback,
    but treating it as live input makes evaluator discovery report
    `no_available_evaluator` forever.
    """
    if not _pane_current_prompt_has_residue(text):
        return False
    command = _pane_current_command(pane).lower()
    if command not in {"bash", "zsh", "sh", "fish"}:
        return False
    return any(
        marker in text
        for marker in (
            "✻ Churned for",
            "✻ Cogitated for",
            "✻ Baked for",
            "✻ Brewed for",
            "✻ Cooked for",
            "✻ Sautéed for",
            "✻ Thought for",
            "✻ Worked for",
            "✻ Crunched for",
        )
    )


def _pane_tui_busy(pane: str) -> bool:
    tail = _pane_tail(pane)
    bottom = "\n".join(tail.splitlines()[-40:])
    if PANE_TUI_UNAVAILABLE_RE.search(bottom):
        return True
    if PANE_SURVEY_PROMPT_RE.search(bottom):
        return True
    if PANE_CONFIRMATION_PROMPT_RE.search(bottom):
        return True
    prompt_is_empty = "❯" in bottom and not _pane_current_prompt_has_residue(bottom)
    if PANE_TUI_BUSY_RE.search(bottom):
        if prompt_is_empty:
            return False
        return True
    # Queued prompt residue means this pane needs to drain or be cleared before
    # another graph dispatch. Treat it as unavailable instead of piling more
    # instructions into Claude Code's prompt buffer.
    if PANE_QUEUED_PROMPT_RE.search(bottom):
        return True
    # A non-empty Claude prompt at the bottom is unsubmitted input residue. If
    # we dispatch into it, Claude may concatenate unrelated tasks or open the
    # queued-message UI instead of executing the new node.
    if _pane_current_prompt_has_residue(bottom) and not _pane_prompt_residue_is_stale_scrollback(pane, tail):
        return True
    return False


def _pane_runtime_unavailable_reason(pane: str, title: str = "") -> str:
    command = _pane_current_command(pane).lower()
    if command not in {"bash", "zsh", "sh", "fish"}:
        return ""
    title_lower = title.lower()
    if "idle/no active sprint" not in title_lower:
        return ""
    tail = _pane_tail(pane)
    bottom = "\n".join(tail.splitlines()[-12:])
    if _pane_current_prompt_has_residue(bottom) or PANE_QUEUED_PROMPT_RE.search(bottom):
        return "worker_runtime_not_running"
    return ""


def _clear_stale_prompt_residue(pane: str) -> bool:
    """Clear idle Claude prompt residue in harness-owned worker panes.

    This is intentionally conservative: it only runs when the bottom of the
    pane is not actively processing and the visible prompt contains unsubmitted
    text. Without this, one stale "continue ..." prompt can make a builder pane
    look permanently busy and strand DAG nodes with no_matching_worker.
    """
    tail = _pane_tail(pane)
    bottom = "\n".join(tail.splitlines()[-12:])
    has_residue = bool(PANE_QUEUED_PROMPT_RE.search(bottom) or _pane_current_prompt_has_residue(bottom))
    if PANE_TUI_UNAVAILABLE_RE.search(bottom):
        return False
    if not has_residue:
        if PANE_TUI_BUSY_RE.search(bottom):
            return False
        return False
    try:
        # Claude Code prompt editing has varied across versions. Check after
        # each conservative idle-prompt clear path so active output is never
        # touched unless the pane already looked idle-with-residue.
        for keys in (("C-a", "C-k"), ("C-u",), ("C-c",), ("Escape", "C-u")):
            subprocess.run(["tmux", "send-keys", "-t", pane, *keys], timeout=2)
            time.sleep(0.2)
            after = "\n".join(_pane_tail(pane).splitlines()[-12:])
            if not (PANE_QUEUED_PROMPT_RE.search(after) or _pane_current_prompt_has_residue(after)):
                return True
    except Exception:
        return False
    after = "\n".join(_pane_tail(pane).splitlines()[-12:])
    return not (PANE_QUEUED_PROMPT_RE.search(after) or _pane_current_prompt_has_residue(after))


def _pane_unavailable_reason(pane: str) -> str:
    health = _pane_health(pane)
    if health.get("unavailable"):
        return str(health.get("reason") or "provider_health_unavailable")
    tail = _pane_tail(pane)
    bottom = "\n".join(tail.splitlines()[-40:])
    if PANE_TUI_UNAVAILABLE_RE.search(bottom):
        return "rate_limit_or_api_error"
    if PANE_SURVEY_PROMPT_RE.search(bottom):
        return "survey_prompt_blocked"
    if PANE_QUEUED_PROMPT_RE.search(bottom):
        return "queued_prompt_residue"
    if _pane_current_prompt_has_residue(bottom) and not _pane_prompt_residue_is_stale_scrollback(pane, tail):
        return "unsubmitted_prompt_residue"
    return ""


def _pane_has_matching_queued_prompt(pane: str, instruction_file: Path) -> bool:
    tail = _pane_tail(pane, lines=30)
    if not PANE_QUEUED_PROMPT_RE.search(tail):
        return False
    instruction_path = str(instruction_file.resolve())
    return instruction_file.name in tail or instruction_path in tail


def _pane_dispatch_prompt_reason(tail: str) -> str:
    bottom = "\n".join((tail or "").splitlines()[-40:])
    if "Do you want to make this edit" in bottom or "allow all edits during this session" in bottom:
        return "edit_confirmation_prompt"
    if "accept edits on" in bottom:
        return "accept_edits_footer"
    if "bypass permissions on" in bottom:
        return "permissions_prompt"
    if PANE_QUEUED_PROMPT_RE.search(bottom):
        return "queued_prompt_residue"
    return ""


def _dismiss_dispatch_prompt(pane: str, reason: str) -> bool:
    try:
        if reason in {"permissions_prompt", "accept_edits_footer", "edit_confirmation_prompt"}:
            subprocess.run(["tmux", "send-keys", "-t", pane, "BTab"], timeout=2)
            time.sleep(0.2)
            subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
            return True
        if reason == "queued_prompt_residue":
            subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
            return True
    except Exception:
        return False
    return False


def _write_submit_ack(sid: str, node_id: str, pane: str, dispatch_id: str) -> None:
    """Write observable submit evidence so evaluators can verify pane received the dispatch."""
    try:
        ack_dir = HARNESS_DIR / "sprints" / "graph-acks"
        ack_dir.mkdir(parents=True, exist_ok=True)
        ack_file = ack_dir / f"{sid}.{node_id}-submit-ack.json"
        ack = {
            "sid": sid,
            "node_id": node_id,
            "pane": pane,
            "dispatch_id": dispatch_id,
            "submitted_at": _utc_now(),
        }
        ack_file.write_text(json.dumps(ack, indent=2), encoding="utf-8")
    except Exception:
        pass  # fail-open: ack write failure must not block dispatch


def _broker_env(sprint_id: str | None = None) -> dict[str, str]:
    """Return os.environ copy with broker control vars forwarded to child subprocesses.

    SOLAR_BROKER_ENABLED is forwarded as-is (defaulting to "0" when absent) so
    child tools honour the same gate the dispatcher sees.
    SOLAR_BROKER_SPRINT_ID is set from sprint_id when not already in the env.
    When SOLAR_BROKER_ENABLED="0" the returned dict is os.environ with "0" set,
    preserving the unchanged-dispatch-path guarantee (LR-04).
    """
    env = os.environ.copy()
    env.setdefault("SOLAR_BROKER_ENABLED", "0")
    if sprint_id:
        env.setdefault("SOLAR_BROKER_SPRINT_ID", sprint_id)
    return env


def _record_model_call(event: str, sid: str, pane: str, dispatch_id: str,
                       instruction_file: Path, *, tries: int = 0,
                       status: str = "", error: str = "") -> None:
    if not sid:
        return
    recorder = HARNESS_DIR / "lib" / "model_call_runtime.py"
    if not recorder.exists():
        return
    cmd = [
        sys.executable, str(recorder), event,
        "--session-id", sid,
        "--pane", pane,
        "--dispatch-id", dispatch_id,
        "--instruction-file", str(instruction_file),
        "--actor", "graph-dispatcher",
        "--tries", str(tries),
    ]
    if status:
        cmd += ["--status", status]
    if error:
        cmd += ["--error", error]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8,
                       env=_broker_env(sid))
    except Exception:
        pass


def _send_to_pane(pane: str, instruction_file: Path, dry_run: bool,
                  *, sid: str = "", dispatch_id: str = "") -> bool:
    if dry_run:
        return True
    processing_re = re.compile(
        r"Crafting|Cogitating|Orchestrating|Coalescing|Wandering|Sock-hopping|"
        r"Puzzling|Cooking|Baked|Thinking|Considering|Newspapering|"
        r"Reticulating|Scurrying|Roosting|Mustering|Herding|Ruminating|"
        r"Churning|Baking|Effecting|Swooping|Whirring|Smooshing|[·✳✶✽✢]\s+[A-Za-z][A-Za-z-]*…|Read\(|"
        r"Reading|Bash\(|Edit\(|Write\(|⎿|✻|✶|✳|✽|⏺"
    )
    if _pane_tui_busy(pane):
        if _pane_has_matching_queued_prompt(pane, instruction_file):
            for tries in range(1, 3):
                try:
                    subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
                    time.sleep(3.0)
                    tail = _pane_tail(pane)
                    if processing_re.search(tail) or not PANE_QUEUED_PROMPT_RE.search(tail):
                        _record_model_call(
                            "succeeded",
                            sid,
                            pane,
                            dispatch_id,
                            instruction_file,
                            tries=tries,
                            status="matching_queued_prompt_submitted",
                        )
                        return True
                except Exception:
                    time.sleep(0.5)
        prompt_reason = _pane_dispatch_prompt_reason(_pane_tail(pane))
        if prompt_reason and _dismiss_dispatch_prompt(pane, prompt_reason):
            time.sleep(2.0)
            tail = _pane_tail(pane)
            if processing_re.search(tail) or not _pane_dispatch_prompt_reason(tail):
                _record_model_call(
                    "succeeded",
                    sid,
                    pane,
                    dispatch_id,
                    instruction_file,
                    tries=1,
                    status=f"dispatch_prompt_dismissed:{prompt_reason}",
                )
                return True
        _record_model_call(
            "failed",
            sid,
            pane,
            dispatch_id,
            instruction_file,
            status="pane_tui_busy_before_send",
            error="pane is compacting, processing, or has queued prompt residue",
        )
        return False
    _set_pane_capability_title(pane, instruction_file)
    instruction_path = str(instruction_file.resolve())
    dispatch_keyword = instruction_file.name
    short_cmd = f"{_visibility_summary(instruction_file)['text']}; 读取并执行 {instruction_path}"
    _record_model_call("request", sid, pane, dispatch_id, instruction_file, status="tmux_submit_requested")
    last_error = ""
    for tries in range(1, 4):
        try:
            subprocess.run(["tmux", "send-keys", "-t", pane, "C-u"], timeout=2)
            time.sleep(0.2)
            # Send as literal text; otherwise tmux may parse punctuation in a
            # path-like instruction as key names and discard the input.
            subprocess.run(["tmux", "send-keys", "-t", pane, "-l", short_cmd], timeout=2)
            time.sleep(0.8)
            # Claude Code TUI can swallow the first return or leave literal
            # prompt text queued. A second return with no text is harmless, but
            # leaving a graph node in the prompt is a hard dispatch failure.
            subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
            time.sleep(0.35)
            subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
            if os.environ.get("SOLAR_GRAPH_DISPATCH_ASYNC_SUBMIT") == "1":
                _record_model_call(
                    "succeeded",
                    sid,
                    pane,
                    dispatch_id,
                    instruction_file,
                    tries=tries,
                    status="async_submit_tmux_send_accepted",
                )
                return True
            time.sleep(4.0)
            tail = _pane_tail(pane)
            prompt_reason = _pane_dispatch_prompt_reason(tail)
            if prompt_reason:
                _dismiss_dispatch_prompt(pane, prompt_reason)
                time.sleep(2.0)
                tail = _pane_tail(pane)
                prompt_reason = _pane_dispatch_prompt_reason(tail)
            has_keyword = dispatch_keyword in tail or instruction_path in tail
            has_processing = bool(processing_re.search(tail))
            if has_keyword and has_processing:
                _record_model_call(
                    "succeeded",
                    sid,
                    pane,
                    dispatch_id,
                    instruction_file,
                    tries=tries,
                    status="keyword_processing_verified",
                )
                return True
            if has_keyword and not has_processing:
                # Residual prompt rescue. Some Claude Code builds show the
                # instruction in the prompt, but the real key event is not
                # accepted until the next standalone Enter. Do not cancel first:
                # cancellation can convert a recoverable prompt residue into an
                # interrupted task that waits for human choice.
                for _ in range(2):
                    subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], timeout=2)
                    time.sleep(3.0)
                    tail = _pane_tail(pane)
                    if processing_re.search(tail):
                        _record_model_call(
                            "succeeded",
                            sid,
                            pane,
                            dispatch_id,
                            instruction_file,
                            tries=tries,
                            status="keyword_processing_verified_after_residual_rescue",
                        )
                        return True
            if has_keyword:
                if prompt_reason:
                    last_error = f"dispatch blocked by {prompt_reason}"
                    time.sleep(1.0)
                    continue
                # Do not send C-c after the instruction is visible. Claude Code
                # may start processing after our verification window; cancelling
                # here is what creates repeated "Interrupted · What should
                # Claude do instead?" deadlocks in builder panes. Treat visible
                # instruction as accepted but unverified, and let watchdog /
                # handoff detection judge progress from durable artifacts.
                _record_model_call(
                    "succeeded",
                    sid,
                    pane,
                    dispatch_id,
                    instruction_file,
                    tries=tries,
                    status="keyword_visible_submit_unverified_no_cancel",
                )
                return True
            if has_processing:
                # Pre-send busy detection already verified the pane was not
                # active. If it starts processing after our send, the prompt was
                # accepted even when the wrapped screen tail no longer contains
                # the full filename. Treat that as a successful submit; durable
                # handoff/eval artifacts remain the completion source of truth.
                _record_model_call(
                    "succeeded",
                    sid,
                    pane,
                    dispatch_id,
                    instruction_file,
                    tries=tries,
                    status="processing_verified_without_keyword",
                )
                return True
            last_error = "dispatch text not accepted by pane"
            # Never send C-c from the dispatcher. Claude Code treats C-c as an
            # interactive interruption and can leave the pane in a Rewind prompt
            # that blocks automation. If the text was not accepted, report
            # send_failed and let the caller decide whether to retry, quarantine,
            # or respawn the pane.
            time.sleep(1.0)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)
    tail = _pane_tail(pane)
    prompt_reason = _pane_dispatch_prompt_reason(tail)
    if (dispatch_keyword in tail or instruction_path in tail or processing_re.search(tail)) and not prompt_reason:
        _record_model_call(
            "succeeded",
            sid,
            pane,
            dispatch_id,
            instruction_file,
            tries=3,
            status="late_submit_verification",
        )
        return True
    _record_model_call(
        "failed",
        sid,
        pane,
        dispatch_id,
        instruction_file,
        tries=3,
        status="tmux_submit_failed",
        error=last_error,
    )
    return False


def _append_dispatch_ledger(kind: str, sid: str, pane: str, dispatch_id: str, extra: dict[str, Any]) -> None:
    record = {
        "ts": _utc_now(),
        "kind": kind,
        "sid": sid,
        "pane": pane,
        "dispatch_id": dispatch_id,
    }
    record.update(extra)
    DISPATCH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    try:
        with DISPATCH_LEDGER.open("a", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass


def _intent_telemetry_summary(instruction_file: Path) -> dict[str, Any]:
    sidecar = instruction_file.with_name(instruction_file.name + ".intent.json")
    if not sidecar.exists():
        return {"intent_telemetry_file": "", "intent_telemetry_missing": True}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"intent_telemetry_file": str(sidecar), "intent_telemetry_error": str(exc)}
    intent = data.get("intent") or {}
    matches = intent.get("matches") or []
    caps = data.get("capabilities") or []
    return {
        "instruction_file": data.get("dispatch_file", str(instruction_file)),
        "intent_telemetry_file": str(sidecar),
        "intent_matched": bool(intent.get("matched")),
        "intent_matches": [
            {
                "kind": m.get("kind"),
                "type": m.get("type"),
                "source": m.get("source"),
                "skill": m.get("skill"),
                "target": m.get("target"),
                "confidence": m.get("confidence"),
            }
            for m in matches
        ],
        "capability_providers": [c.get("provider") for c in caps],
        "worker_visible": data.get("worker_visible") or {},
        "effect_status": (data.get("effect") or {}).get("status", "pending_worker_evidence"),
        "effect": data.get("effect") or {},
    }


def _visibility_summary(instruction_file: Path) -> dict[str, str]:
    sidecar = instruction_file.with_name(instruction_file.name + ".intent.json")
    if not sidecar.exists():
        return {
            "text": "Solar能力: intent=N/A | caps=N/A | effect=N/A",
            "title": "能力:N/A",
        }
    summary = _intent_telemetry_summary(instruction_file)
    intent_labels: list[str] = []
    for m in summary.get("intent_matches", []):
        label = m.get("skill") or m.get("target") or m.get("type") or m.get("source")
        if label:
            intent_labels.append(str(label))
    cap_labels = [str(x) for x in summary.get("capability_providers", []) if x]

    def short(value: str, limit: int) -> str:
        return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"

    intent_text = ",".join(short(x, 22) for x in intent_labels[:3]) if intent_labels else "N/A"
    cap_text = ",".join(short(x, 22) for x in cap_labels[:4]) if cap_labels else "N/A"
    effect = short(str(summary.get("effect_status") or "pending_worker_evidence"), 20)
    title_parts: list[str] = []
    if intent_labels:
        title_parts.append("I:" + ",".join(short(x, 10) for x in intent_labels[:2]))
    if cap_labels:
        title_parts.append("C:" + ",".join(short(x, 10) for x in cap_labels[:3]))
    return {
        "text": f"Solar能力: intent={intent_text} | caps={cap_text} | effect={effect}",
        "title": " | ".join(title_parts) if title_parts else "能力:N/A",
    }


def _set_pane_capability_title(pane: str, instruction_file: Path) -> None:
    try:
        current = subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane, "#{pane_title}"],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        base = re.sub(r"\s+\|\s+能力:.*$", "", current) or pane
        title = _visibility_summary(instruction_file)["title"]
        subprocess.run(["tmux", "select-pane", "-t", pane, "-T", f"{base} | 能力:{title}"], timeout=2)
    except Exception:
        pass


def _inject_dispatch_context(instruction_file: Path, sid: str = "", pane: str = "", dispatch_id: str = "") -> None:
    """Fail-open Solar skills/KB/capability context injection for DAG dispatch files."""
    injector = HARNESS_DIR / "lib" / "solar_skills.py"
    if not instruction_file.exists():
        return
    if injector.exists():
        try:
            subprocess.run(
                [sys.executable, str(injector), "inject", str(instruction_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
                env=_broker_env(sid),
            )
        except Exception:
            pass
    runtime_injector = HARNESS_DIR / "lib" / "runtime_context_inject.py"
    if sid and dispatch_id and runtime_injector.exists():
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(runtime_injector),
                    str(instruction_file),
                    "--session-id",
                    sid,
                    "--pane",
                    pane or "unknown",
                    "--dispatch-id",
                    dispatch_id,
                    "--budget-tokens",
                    "1800",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
                env=_broker_env(sid),
            )
        except Exception:
            pass
    if sid and dispatch_id:
        _append_dispatch_ledger(
            "intent_injected",
            sid,
            pane or "unknown",
            dispatch_id,
            _intent_telemetry_summary(instruction_file),
        )


def _lease_active_for(pane: str, sid: str, dispatch_id: str) -> bool:
    lease = read_lease(pane)
    if not lease:
        return False
    return (
        lease.get("sprint_id", lease.get("sid")) == sid
        and lease.get("dispatch_id") == dispatch_id
        and lease.get("expires_at", "") > _utc_now()
    )


def _pane_has_active_lease(pane: str) -> bool:
    lease = read_lease(pane)
    if not lease or lease.get("expires_at", "") <= _utc_now():
        return False
    tail = _pane_tail(pane)
    bottom = "\n".join(tail.splitlines()[-12:])
    if PANE_DISPATCH_FAILED_IDLE_RE.search(tail) and not PANE_TUI_BUSY_RE.search(bottom):
        release_lease(
            pane,
            str(lease.get("dispatch_id") or ""),
            "active_lease_released_after_idle_api_timeout",
        )
        return False
    return True


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_event(sid: str, event: dict[str, Any]) -> None:
    event_file = SPRINTS_DIR / f"{sid}.events.jsonl"
    event = dict(event)
    event.setdefault("ts", _utc_now())
    event.setdefault("sid", sid)
    try:
        with event_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if record_legacy_event is not None:
        try:
            payload = event.get("data") if isinstance(event.get("data"), dict) else dict(event)
            record_legacy_event(
                sid,
                str(event.get("event") or "graph_event"),
                str(event.get("by") or event.get("actor") or "graph-dispatch"),
                payload,
                harness_dir=HARNESS_DIR,
            )
        except Exception:
            pass


def _mark_parent_sprint_passed_if_ready(sid: str, parent: dict[str, Any], dry_run: bool) -> bool:
    if dry_run or not parent.get("ready"):
        return False
    status_file = SPRINTS_DIR / f"{sid}.status.json"
    if not status_file.exists():
        return False
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return False

    now = _utc_now()
    if transition_status is not None:
        transition_status(
            status_file,
            "passed",
            "graph_parent_ready_passed",
            "graph-dispatch",
            extra={
                "status_fields": {
                    "phase": "completed",
                    "handoff_to": "done",
                    "target_role": "done",
                    "completed_at": now,
                    "graph_parent_ready": parent,
                },
                "note": "All DAG nodes and required gates passed via parent_ready_check.",
            },
        )
    else:
        history = data.get("history")
        if not isinstance(history, list):
            history = []
        history.append({
            "ts": now,
            "event": "graph_parent_ready_passed",
            "by": "graph-dispatch",
            "note": "All DAG nodes and required gates passed via parent_ready_check.",
        })
        data.update({
            "status": "passed",
            "phase": "completed",
            "handoff_to": "done",
            "target_role": "done",
            "updated_at": now,
            "completed_at": now,
            "graph_parent_ready": parent,
            "history": history,
        })
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_event(sid, {
        "event": "graph_parent_ready_passed",
        "by": "graph-dispatch",
        "data": {"node_count": parent.get("node_count"), "required_gates": parent.get("required_gates", [])},
    })
    return True


def _ensure_lease(pane: str, sid: str, dispatch_id: str, ttl: int, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"acquired": True, "dry_run": True}
    if _lease_active_for(pane, sid, dispatch_id):
        return {"acquired": True, "existing": True}
    return acquire_lease(pane, sid, dispatch_id, ttl)


def dispatch_queue_item(item: dict[str, Any], dry_run: bool = False, ttl: int = 900) -> dict[str, Any]:
    payload = item.get("payload") or {}
    sid = payload.get("sprint_id") or item.get("sprint_id") or item.get("sid") or ""
    node = payload.get("node") or {}
    node_id = node.get("id") or _node_id_from_intent(item.get("intent", ""))
    assignment = payload.get("assignment") or {}
    pane = assignment.get("pane") or payload.get("pane") or ""
    graph_path = payload.get("graph") or str(SPRINTS_DIR / f"{sid}.task_graph.json")
    dispatch_id = payload.get("dispatch_id") or f"graph-{sid}-{node_id}"

    if not sid or not node_id:
        return {"ok": False, "reason": "invalid_graph_queue_item", "item": item}
    if not pane:
        return {"ok": False, "reason": "missing_assigned_pane", "node": node_id}
    runtime_state = _graph_node_runtime_state(graph_path, node_id)
    current_status = str(runtime_state.get("status") or "")
    current_dispatch_id = str(runtime_state.get("dispatch_id") or "")
    if current_status in {"assigned", "dispatched", "in_progress", "running"} and current_dispatch_id == dispatch_id:
        instruction_file = _dispatch_file(sid, node_id)
        if _pane_tui_busy(pane):
            if _pane_has_matching_queued_prompt(pane, instruction_file):
                sent = _send_to_pane(pane, instruction_file, dry_run, sid=sid, dispatch_id=dispatch_id)
                if sent:
                    _write_submit_ack(sid, node_id, pane, dispatch_id)
                    return {
                        "ok": True,
                        "reason": "matching_queued_prompt_submitted",
                        "node": node_id,
                        "pane": pane,
                        "dispatch_id": dispatch_id,
                        "instruction_file": str(instruction_file),
                    }
            _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
            return {
                "ok": True,
                "reason": "pane_busy_retry_later",
                "node": node_id,
                "pane": pane,
                "dispatch_id": dispatch_id,
                "instruction_file": str(instruction_file),
                "requeued": False,
            }
    if current_status in {"passed", "failed", "skipped", "reviewing", "waiting_human_search"}:
        return {
            "ok": True,
            "reason": "stale_graph_item_node_not_dispatchable",
            "node": node_id,
            "status": current_status,
            "dispatch_id": dispatch_id,
        }
    human_handoff = _prepare_human_search_handoff(sid, graph_path, node, dry_run=dry_run)
    if human_handoff is not None:
        return human_handoff
    if current_status in {"assigned", "dispatched", "in_progress", "running"} and current_dispatch_id and current_dispatch_id != dispatch_id:
        return {
            "ok": True,
            "reason": "stale_graph_item_superseded",
            "node": node_id,
            "status": current_status,
            "current_dispatch_id": current_dispatch_id,
            "stale_dispatch_id": dispatch_id,
        }
    if not dry_run and not _pane_exists(pane):
        enqueue(sid, item.get("intent", f"graph_node|node_id={node_id}"), item.get("priority", 80), payload)
        _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
        return {"ok": False, "reason": "pane_missing", "node": node_id, "pane": pane, "requeued": True}

    lease_result = _ensure_lease(pane, sid, dispatch_id, ttl, dry_run)
    if not lease_result.get("acquired"):
        enqueue(sid, item.get("intent", f"graph_node|node_id={node_id}"), item.get("priority", 80), payload)
        _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
        return {
            "ok": False,
            "reason": lease_result.get("reason", "lease_failed"),
            "node": node_id,
            "pane": pane,
            "lease": lease_result,
            "requeued": True,
        }

    text_payload = dict(payload, dispatch_id=dispatch_id, sprint_id=sid)
    # Research node branch: mark fan-out section isolation for R-prefixed nodes
    # from deepresearch DAG templates. No main-loop edits; this is a single
    # if-branch that enriches the payload before dispatch text generation.
    if node_id.startswith("R"):
        text_payload["research_node"] = True
        if node.get("fan_out_parent"):
            text_payload["section_isolation"] = True
            text_payload["section_id"] = node.get("section_id", "")
    instruction_file = _dispatch_file(sid, node_id)
    instruction_file.parent.mkdir(parents=True, exist_ok=True)
    instruction_file.write_text(build_dispatch_text(text_payload, pane), encoding="utf-8")
    if not dry_run:
        _inject_dispatch_context(instruction_file, sid=sid, pane=pane, dispatch_id=dispatch_id)
    if dry_run:
        return {
            "ok": True,
            "node": node_id,
            "pane": pane,
            "dispatch_id": dispatch_id,
            "instruction_file": str(instruction_file),
            "dry_run": True,
            "graph_updated": False,
        }

    sent = _send_to_pane(pane, instruction_file, dry_run, sid=sid, dispatch_id=dispatch_id)
    graph_updated = False
    if sent:
        if not dry_run:
            _write_submit_ack(sid, node_id, pane, dispatch_id)
            try:
                graph = load_graph(graph_path)
                set_node_status(graph, node_id, "dispatched", pane=pane, dispatch_id=dispatch_id)
                save_graph(graph_path, graph)
                graph_updated = True
            except Exception:
                graph_updated = False
        return {
            "ok": True,
            "node": node_id,
            "pane": pane,
            "dispatch_id": dispatch_id,
            "instruction_file": str(instruction_file),
            "dry_run": dry_run,
            "graph_updated": graph_updated,
        }

    if not dry_run:
        release_lease(pane, dispatch_id, "graph_dispatch_send_failed")
    if _pane_tui_busy(pane):
        # The pane is already doing work, compacting, or carrying queued prompt
        # residue. Do not keep an unsent node in assigned/dispatched state:
        # that strands the node forever. Also do not requeue immediately,
        # because that creates duplicate prompt lines. Leave it pending so the
        # next scheduler cycle can pick any then-idle worker.
        _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
        return {
            "ok": True,
            "reason": "pane_busy_retry_later",
            "node": node_id,
            "pane": pane,
            "instruction_file": str(instruction_file),
            "dispatch_id": dispatch_id,
            "requeued": False,
        }
    enqueue(sid, item.get("intent", f"graph_node|node_id={node_id}"), item.get("priority", 80), payload)
    _mark_graph_node(graph_path, node_id, "pending", clear_assignment=True)
    return {
        "ok": False,
        "reason": "send_failed",
        "node": node_id,
        "pane": pane,
        "instruction_file": str(instruction_file),
        "requeued": True,
    }


def drain_queue(sprint_id: str, dry_run: bool = False, max_items: int = 0, ttl: int = 900) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    processed = 0
    while True:
        if max_items and processed >= max_items:
            break
        item = _pop_graph_queue_item(sprint_id)
        if item is None:
            break
        results.append(dispatch_queue_item(item, dry_run=dry_run, ttl=ttl))
        processed += 1
    return {
        "ok": all(r.get("ok") for r in results) if results else True,
        "sprint_id": sprint_id,
        "processed": processed,
        "results": results,
    }


def _discover_workers(dry_run: bool = False) -> list[dict[str, Any]]:
    worker_skills = [
        "bash", "shell", "python", "python-read", "dataclasses", "pytest", "subprocess", "sqlite", "sqlite3", "pure-functions", "time-injection", "timeouts", "concurrency", "io", "fsm", "integration", "integration-testing", "integration-tests", "regression", "regression-tests", "bash-tests", "jq", "json", "json-patch", "jsonl-tail", "typescript", "docs", "testing",
        "http-testing", "negative-testing", "activation-proof", "knowledge-ingest", "release-gate", "documentation",
        "solar-harness-verification", "solar-harness-compat-review", "harness.verification", "verification",
        "stub-llm", "e2e-test", "cli-view-assertion", "negative-control", "verifier", "registry-introspection",
        "technical-writing", "markdown", "regex", "markdown-parse", "pandoc", "evidence-aggregation", "handoff-authoring", "traceability-patch", "knowledge-raw-writeback",
        "architecture-writing", "solar-harness-control-plane", "algorithm_design",
        "frontend", "observability", "ui", "terminal-ui", "tvs", "vdl", "snapshot", "snapshot-testing", "flask", "http", "curl", "http-routing", "http-endpoint", "autopilot-hooks", "json-traversal", "html", "jinja", "javascript", "vanilla-dom",
        "security", "grep", "secret-scan", "code-audit",
        "deepresearch", "cli", "cli-audit", "cli-design", "argparse", "argparse-bridge", "json-schema", "json-shape-inspect", "validation", "claude-cli", "survey", "fixture", "release", "evidence", "evidence-collection", "evaluator-summary", "autopilot", "epic",
        "product", "planning", "optimization", "runtime_design", "workflow.planning", "governance", "risk", "risk-register",
        "architecture", "schema", "state-machine", "state-schema-design", "distributed-systems",
        "code-audit", "docs-audit", "type-hints", "type-protocols", "refactor", "tmux-inspect", "data-aggregation", "shutil", "urllib", "atomic-writes", "hashing", "unittest-mock",
        "api-design", "data-modeling", "compatibility", "compat-review",
        "scheduler.design", "algorithm", "state-machine.design",
        "routing", "diagnostics", "evaluation", "capability-graph", "event-sourcing",
        "ai-rag-pipeline", "reporting",
        "lazy-import",
        "browser.browse", "browser.qa", "code.review", "document.convert",
        "persona.agent", "multi_agent.research", "debug.systematic",
        "autoresearch.pane_optimizer", "autoresearch.issue_loop", "autoresearch.local_issue",
        "autoresearch.agent_iteration", "autoresearch.score_gate",
        "repair.pr-cot",
        "DeepArchitect", "ImplementationWorker", "Critic", "Verifier",
        "code_impl", "test_generation", "test_execution",
    ]
    worker_capabilities = [
        "bash", "python", "typescript", "docs", "testing",
        "frontend", "observability", "evidence",
        "solar-harness-verification", "solar-harness-compat-review", "harness.verification", "verification",
        "env-passthrough", "metrics",
        "harness.context_preflight", "harness.intent", "harness.dispatch_visibility", "harness.contracts",
        "harness.dag", "harness.status", "harness.model_routing", "model.routing",
        "intent.match", "intent.audit", "dispatch.intent_telemetry",
        "models.show", "models.lab_matrix", "models.footer_labels",
        "context.inject", "wiki.status", "data_plane.audit",
        "dag.validate", "dag.ready_nodes", "dag.join_gate",
        "harness.testing", "harness.failure_recovery", "harness.autopilot",
        "harness.activation_proof", "harness.reporting", "harness.knowledge", "harness.contracts",
        "reporting", "ai-rag-pipeline",
        "lazy-import", "cli",
        "activation.proof", "negative_control", "runtime_artifacts",
        "autopilot.monitor", "autopilot.safe_apply", "pane.deadlock_detection",
        "documentation", "governance", "risk", "schema", "state-machine", "storage", "sources",
        "browser.browse", "browser.qa", "code.review", "code-audit",
        "browser.mcp", "browser.automation", "browser.screenshot",
        "browser.localhost_test",
        "document.convert", "document.markdown_extract", "mcp.markitdown",
        "persona.agent", "agent.catalog", "specialist.routing",
        "multi_agent.research", "browser.agent_experiment", "document.toolkit",
        "agent.inventory", "command.catalog", "rules.catalog", "mcp.catalog",
        "repair.pr-cot", "failure.structured_repair", "routing.complexity_budget",
        "optimization", "runtime_design",
        "algorithm_design", "solar-harness-control-plane", "architecture-writing",
        "code_impl", "test_generation", "test_execution",
        "skill.methodology", "workflow.planning", "debug.systematic", "test.tdd",
        "architecture", "distributed-systems", "evaluation",
        "agents_sdk.design", "agents_sdk.guardrails", "agents_sdk.tracing",
        "agents_sdk.handoff_model",
        "ruflo.swarm", "ruflo.plugins", "ruflo.agent_catalog",
        "ruflo.memory", "ruflo.mcp", "ruflo.workflow_templates",
        "product.requirements", "research.scope_rewrite",
        "research.empirical_pipeline", "research.literature_review",
        "analysis.causal_inference",
        "research.source_matrix", "research.evidence.extract",
        "research.claim.mine", "research.citation.verify",
        "research.report.compile", "report.compile",
        "research.long_report_compiler", "research.report_ast",
        "scheduler.design", "algorithm", "state-machine.design",
        "autoresearch.pane_optimizer", "autoresearch.issue_loop", "autoresearch.local_issue",
        "autoresearch.agent_iteration", "autoresearch.score_gate",
        "schema_design", "fixture_design", "mapping_design",
        "compatibility_design", "feedback_design", "gate_design",
        "metric_design", "replay_design", "shell_design", "synthesis",
        "security_review",
    ]
    restrict_to_session = os.environ.get("SOLAR_GRAPH_DISPATCH_RESTRICT_SESSION") == "1"
    if dry_run and os.environ.get("SOLAR_GRAPH_DISPATCH_FAKE_WORKERS") == "1":
        if restrict_to_session:
            return []
        return [
            {"pane": "solar-harness-lab:0.0", "models": _models_for_pane("solar-harness-lab:0.0"), "skills": worker_skills, "capabilities": worker_capabilities},
            {"pane": "solar-harness-lab:0.1", "models": _models_for_pane("solar-harness-lab:0.1"), "skills": worker_skills, "capabilities": worker_capabilities},
            {"pane": "solar-harness-lab:0.2", "models": _models_for_pane("solar-harness-lab:0.2"), "skills": worker_skills, "capabilities": worker_capabilities},
            {"pane": "solar-harness-lab:0.3", "models": _models_for_pane("solar-harness-lab:0.3"), "skills": worker_skills, "capabilities": worker_capabilities},
        ]
    try:
        out = subprocess.check_output(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode()
        pane_rows = [p.rstrip("\n").split("\t", 1) for p in out.splitlines() if p.strip()]
    except Exception:
        pane_rows = []
    workers = []
    pane_rows.sort(key=lambda row: _pane_execution_priority((row[0].strip() if row else "")))
    for row in pane_rows:
        pane = row[0].strip()
        title = row[1].strip() if len(row) > 1 else ""
        # Only builder panes can receive DAG build nodes. Main PM/planner/evaluator
        # panes share the session prefix but must not be treated as builders.
        if restrict_to_session:
            continue
        if not (
            pane.startswith("solar-harness-lab:")
            or pane.startswith("solar-harness-multi-task:")
        ):
            continue
        if not _pane_title_matches_role(pane, title, "builder"):
            continue
        models = _models_for_pane(pane, title)
        tail = _pane_tail(pane)
        health = _pane_health(pane)
        quota_exhausted = _quota_exhausted_models(title, tail, health, models)
        if pane.startswith("solar-harness-lab:") or pane.startswith("solar-harness-multi-task:"):
            _clear_stale_prompt_residue(pane)
        runtime_unavailable_reason = _pane_runtime_unavailable_reason(pane, title)
        unavailable_reason = (
            runtime_unavailable_reason
            or _pane_unavailable_reason(pane)
            or ("rate_limit_or_api_error" if quota_exhausted else "")
        )
        workers.append({
            "pane": pane,
            "models": models,
            "skills": worker_skills,
            "capabilities": worker_capabilities,
            "busy": _pane_has_active_lease(pane) or _pane_tui_busy(pane) or bool(unavailable_reason),
            "title": title,
            "quota_exhausted": quota_exhausted,
            "health": health,
            "unavailable_reason": unavailable_reason,
            "current_command": _pane_current_command(pane),
        })
    workers.sort(key=lambda item: _pane_execution_priority(str(item.get("pane") or "")))
    return workers


def _discover_evaluators(dry_run: bool = False) -> list[dict[str, Any]]:
    if dry_run:
        return [{"pane": f"{SESSION}:0.3", "models": _models_for_pane(f"{SESSION}:0.3"), "skills": ["review", "testing", "bash"]}]
    # Graph node evaluation mutates graph verdict state. Keep it on evaluator
    # personas only, but allow a pool of evaluator hosts instead of pinning the
    # runtime to one pane. Planning still decides whether a node may use a
    # single evaluator or require quorum semantics.
    restrict_to_session = os.environ.get("SOLAR_GRAPH_DISPATCH_RESTRICT_SESSION") == "1"
    candidates = [f"{SESSION}:0.3"]
    try:
        out = subprocess.check_output(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}:#{window_index}.#{pane_index}\t#{pane_title}"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode()
        pane_rows = [p.rstrip("\n").split("\t", 1) for p in out.splitlines() if p.strip()]
    except Exception:
        pane_rows = []
    for row in pane_rows:
        pane = row[0].strip()
        if not pane or pane in candidates:
            continue
        if restrict_to_session:
            if not pane.startswith(f"{SESSION}:"):
                continue
        else:
            if not (
                pane.startswith(f"{SESSION}:")
                or pane.startswith("solar-harness-lab:")
                or pane.startswith("solar-harness-multi-task:")
            ):
                continue
        candidates.append(pane)
    evaluators: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pane in candidates:
        if pane in seen:
            continue
        seen.add(pane)
        if _pane_exists(pane):
            title = _pane_title(pane)
            if not _pane_title_matches_role(pane, title, "evaluator"):
                continue
            runtime_unavailable_reason = _pane_runtime_unavailable_reason(pane, title)
            unavailable_reason = runtime_unavailable_reason or _pane_unavailable_reason(pane)
            evaluators.append({
                "pane": pane,
                "models": _models_for_pane(pane),
                "skills": ["review", "testing", "bash"],
                "busy": _pane_has_active_lease(pane) or _pane_tui_busy(pane) or bool(unavailable_reason),
                "title": title,
                "unavailable_reason": unavailable_reason,
                "current_command": _pane_current_command(pane),
            })
    evaluators.sort(key=lambda item: _pane_execution_priority(str(item.get("pane") or "")))
    return evaluators


def _node_eval_needed(graph: dict[str, Any], sid: str, node: dict[str, Any], force: bool = False) -> bool:
    node_id = str(node.get("id") or "")
    if not node_id:
        return False
    repair_mode = bool(node.get("quality_gate_repair_requested_at")) and _node_requires_deepresearch_quality_gate(node)
    results = graph.get("node_results") or {}
    result = results.get(node_id) if isinstance(results, dict) else None
    result_status = str(result.get("status", "")).lower() if isinstance(result, dict) else ""
    if result_status == "passed":
        return False
    if result_status in {"failed", "skipped"} and not force:
        return False
    if _eval_json_file(sid, node_id).exists() and not force and not repair_mode:
        return False
    if not force:
        recovered: list[dict[str, Any]] = []
        recovered_at = ""
        for lease in list_leases():
            dispatch_id = str(lease.get("dispatch_id") or "")
            lease_sid = str(lease.get("sid") or lease.get("sprint_id") or "")
            if (
                not lease.get("_expired")
                and lease_sid == sid
                and f"-{node_id}-" in dispatch_id
                and dispatch_id.startswith(f"graph-eval-{sid}-")
            ):
                recovered.append(
                    {
                        "pane": str(lease.get("pane") or ""),
                        "dispatch_id": dispatch_id,
                        "role": "secondary",
                    }
                )
                recovered_at = str(lease.get("acquired_at") or recovered_at or _utc_now())
        if recovered:
            if recovered:
                recovered[0]["role"] = "primary"
            _store_eval_assignments(node, recovered, recovered_at or _utc_now())
            node["eval_recovered_from_lease"] = True
            return False
    if node.get("eval_dispatched_at") and not force:
        assignments = _node_eval_assignments(node)
        lease_matches = False
        for assignment in assignments:
            pane = str(assignment.get("pane") or "")
            dispatch_id = str(assignment.get("dispatch_id") or "")
            lease = read_lease(pane) if pane else {}
            if (
                lease
                and str(lease.get("sid") or lease.get("sprint_id") or "") == sid
                and str(lease.get("dispatch_id") or "") == dispatch_id
            ):
                lease_matches = True
                break
        # If the graph says eval was dispatched but no eval artifact exists and
        # the evaluator lease is gone, the pane likely swallowed/stalled the
        # prompt. Treat it as retryable instead of permanently blocking.
        if lease_matches:
            return False
        _clear_eval_assignments(node)
        node["eval_retry_reason"] = "eval_dispatched_without_artifact_or_active_lease"
    # Use graph_scheduler.node_status so node_results (the durable scheduler
    # result map) and inline node.status do not drift. A node can be reviewing
    # in node_results while its static node entry still says pending; relying
    # on node.status alone makes evaluator dispatch skip real handoffs forever.
    status = node_status(graph, node_id)
    if status == "passed":
        return False
    if status in {"failed", "skipped"}:
        if not force:
            return False
        return bool(_existing_node_handoff(sid, node, graph))
    if repair_mode and status in {"reviewing", "dispatched", "in_progress", "running", ""}:
        return True
    return bool(_existing_node_handoff(sid, node, graph)) and status in {"reviewing", "dispatched", "in_progress", "running", ""}


def _first_available_evaluator(dry_run: bool = False) -> dict[str, Any] | None:
    for evaluator in _discover_evaluators(dry_run):
        pane = str(evaluator.get("pane", ""))
        if pane and not evaluator.get("busy"):
            return evaluator
    return None


def dispatch_node_evals(graph_path: str, dry_run: bool = False, ttl: int = 900,
                        force: bool = False, max_items: int = 0) -> dict[str, Any]:
    graph = load_graph(graph_path)
    sid = str(graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", ""))
    dispatched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    dry_run_used_panes: set[str] = set()
    evaluators = _discover_evaluators(dry_run)

    for node in graph.get("nodes", []):
        if max_items and len(dispatched) >= max_items:
            break
        node_id = str(node.get("id") or "")
        if not _node_eval_needed(graph, sid, node, force=force):
            continue
        requested_plan = _plan_node_evaluation(graph, node)
        requested_capacity = _evaluation_capacity_snapshot(requested_plan, evaluators)
        requested_plan["capacity"] = requested_capacity
        runtime_plan = _runtime_fallback_evaluation_plan(requested_plan, requested_capacity)
        runtime_capacity = _evaluation_capacity_snapshot(runtime_plan, evaluators)
        runtime_plan["capacity"] = runtime_capacity
        node["evaluation_plan_requested"] = requested_plan
        node["evaluation_plan_runtime"] = runtime_plan
        node["evaluation_plan"] = runtime_plan
        node["evaluation_plan_updated_at"] = _utc_now()
        if not runtime_capacity.get("available_evaluators"):
            skipped.append({
                "node": node_id,
                "reason": "no_available_evaluator",
                "evaluation_plan": runtime_plan,
            })
            break
        if not runtime_capacity.get("capacity_satisfied", False):
            skipped.append({
                "node": node_id,
                "reason": "insufficient_evaluator_capacity",
                "evaluation_plan": runtime_plan,
            })
            break
        if not runtime_capacity.get("quorum_dispatch_supported", True):
            skipped.append({
                "node": node_id,
                "reason": "multi_evaluator_quorum_not_implemented",
                "evaluation_plan": runtime_plan,
            })
            break
        if not runtime_capacity.get("dispatchable_now"):
            skipped.append({
                "node": node_id,
                "reason": "insufficient_evaluator_capacity",
                "evaluation_plan": runtime_plan,
            })
            break
        selected_panes = [
            str(pane)
            for pane in runtime_capacity.get("selected_panes", [])
            if str(pane)
        ]
        selected_evaluators = [
            item
            for item in evaluators
            if not item.get("busy") and str(item.get("pane") or "") in selected_panes
        ]
        if len(selected_evaluators) < int(runtime_plan.get("required_evaluators") or 1):
            skipped.append({
                "node": node_id,
                "reason": "insufficient_selected_evaluators",
                "evaluation_plan": runtime_plan,
            })
            break
        total_evaluators = int(runtime_plan.get("required_evaluators") or 1)
        dispatch_group_id = f"graph-eval-{sid}-{node_id}-{_utc_now().replace(':', '').replace('-', '')}"
        planned_assignments: list[dict[str, Any]] = []
        for idx, evaluator in enumerate(selected_evaluators[:total_evaluators], start=1):
            pane = str(evaluator.get("pane") or "")
            if dry_run and pane in dry_run_used_panes:
                skipped.append({
                    "node": node_id,
                    "reason": "dry_run_evaluator_capacity",
                    "pane": pane,
                    "evaluation_plan": runtime_plan,
                })
                planned_assignments = []
                break
            role = "primary" if idx == 1 else "secondary"
            eval_md_path = _eval_md_file(sid, node_id) if idx == 1 else _eval_peer_md_file(sid, node_id, idx)
            eval_json_path = _eval_json_file(sid, node_id) if idx == 1 else _eval_peer_json_file(sid, node_id, idx)
            planned_assignments.append(
                {
                    "pane": pane,
                    "dispatch_id": f"{dispatch_group_id}-q{idx}",
                    "role": role,
                    "index": idx,
                    "eval_md_path": str(eval_md_path),
                    "eval_json_path": str(eval_json_path),
                }
            )
        if not planned_assignments:
            break

        lease_results: list[dict[str, Any]] = []
        lease_failed = None
        for assignment in planned_assignments:
            lease_result = _ensure_lease(
                str(assignment["pane"]),
                sid,
                str(assignment["dispatch_id"]),
                ttl,
                dry_run,
            )
            lease_results.append(lease_result)
            if not lease_result.get("acquired"):
                lease_failed = {"assignment": assignment, "lease": lease_result}
                break
        if lease_failed:
            if not dry_run:
                for assignment, lease_result in zip(planned_assignments, lease_results):
                    if lease_result.get("acquired"):
                        release_lease(str(assignment["pane"]), str(assignment["dispatch_id"]), "graph_eval_dispatch_partial_lease_failed")
            skipped.append({
                "node": node_id,
                "pane": str(lease_failed["assignment"]["pane"]),
                "reason": lease_failed["lease"].get("reason", "lease_failed"),
                "lease": lease_failed["lease"],
                "evaluation_plan": runtime_plan,
            })
            continue

        canonical_eval_md = str(_eval_md_file(sid, node_id))
        canonical_eval_json = str(_eval_json_file(sid, node_id))
        sent_records: list[dict[str, Any]] = []
        send_failed = None
        for assignment in planned_assignments:
            pane = str(assignment["pane"])
            peer_paths = [
                str(item["eval_json_path"])
                for item in planned_assignments
                if item["dispatch_id"] != assignment["dispatch_id"]
            ]
            instruction_file = _eval_dispatch_member_file(sid, node_id, int(assignment["index"]))
            instruction_file.parent.mkdir(parents=True, exist_ok=True)
            instruction_file.write_text(
                build_eval_dispatch_text(
                    graph,
                    graph_path,
                    node,
                    pane,
                    str(assignment["dispatch_id"]),
                    evaluator_role=str(assignment["role"]),
                    evaluator_index=int(assignment["index"]),
                    evaluator_total=total_evaluators,
                    eval_md_override=Path(str(assignment["eval_md_path"])),
                    eval_json_override=Path(str(assignment["eval_json_path"])),
                    peer_eval_json_paths=peer_paths,
                    canonical_eval_json_path=canonical_eval_json,
                    canonical_eval_md_path=canonical_eval_md,
                ),
                encoding="utf-8",
            )
            _inject_dispatch_context(instruction_file, sid=sid, pane=pane, dispatch_id=str(assignment["dispatch_id"]))
            if dry_run:
                dry_run_used_panes.add(pane)
                sent_records.append({
                    "node": node_id,
                    "pane": pane,
                    "dispatch_id": str(assignment["dispatch_id"]),
                    "instruction_file": str(instruction_file),
                    "evaluation_plan": runtime_plan,
                    "role": assignment["role"],
                    "dry_run": True,
                })
                continue
            sent = _send_to_pane(pane, instruction_file, dry_run, sid=sid, dispatch_id=str(assignment["dispatch_id"]))
            if not sent:
                send_failed = {"assignment": assignment, "instruction_file": str(instruction_file)}
                break
            _write_submit_ack(sid, node_id, pane, str(assignment["dispatch_id"]))
            sent_records.append({
                "node": node_id,
                "pane": pane,
                "dispatch_id": str(assignment["dispatch_id"]),
                "instruction_file": str(instruction_file),
                "evaluation_plan": runtime_plan,
                "role": assignment["role"],
            })
        if send_failed:
            if not dry_run:
                for assignment in planned_assignments:
                    release_lease(str(assignment["pane"]), str(assignment["dispatch_id"]), "graph_eval_dispatch_send_failed")
            _clear_eval_assignments(node)
            skipped.append({
                "node": node_id,
                "pane": str(send_failed["assignment"]["pane"]),
                "reason": "send_failed",
                "evaluation_plan": runtime_plan,
            })
            continue

        node["status"] = "reviewing"
        node["eval_dispatch_group_id"] = dispatch_group_id
        _store_eval_assignments(node, planned_assignments, _utc_now())
        for item in sent_records:
            dispatched.append(item)

    if not dry_run:
        save_graph(graph_path, graph)
    return {
        "ok": not skipped,
        "sprint_id": sid,
        "dispatched": dispatched,
        "skipped": skipped,
    }


def dispatch_ready(graph_path: str, dry_run: bool = False, ttl: int = 900,
                   max_parallel: int = 8) -> dict[str, Any]:
    if _no_dispatch_enabled() and not dry_run:
        return {"ok": False, "reason": "no_dispatch_flag", "graph": graph_path, "enqueue": {}, "drain": {}}
    graph = load_graph(graph_path)
    sid = graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", "")
    reconciled: list[dict[str, Any]] = []
    if not dry_run:
        reconciled = _reconcile_existing_dispatches(graph, graph_path)
        if reconciled:
            save_graph(graph_path, graph)
    enqueue_result = enqueue_ready(
        graph,
        graph_path,
        _discover_workers(dry_run),
        max_parallel=max_parallel,
        lease=not dry_run,
        ttl=ttl,
        dry_run=dry_run,
    )
    if not dry_run:
        save_graph(graph_path, graph)
    if dry_run:
        results = []
        for enqueued in enqueue_result.get("enqueued", []):
            payload = enqueued.get("payload")
            if not isinstance(payload, dict):
                continue
            results.append(dispatch_queue_item({
                "sprint_id": sid,
                "intent": f"graph_node|node_id={enqueued.get('node')}",
                "priority": 80,
                "payload": payload,
            }, dry_run=True, ttl=ttl))
        drain_result = {"ok": all(r.get("ok", False) for r in results), "processed": len(results), "results": results}
    else:
        drain_result = drain_queue(str(sid), dry_run=dry_run, max_items=len(enqueue_result.get("enqueued", [])), ttl=ttl)
    return {
        "ok": enqueue_result.get("ok") and drain_result.get("ok"),
        "reconciled": reconciled,
        "enqueue": enqueue_result,
        "drain": drain_result,
    }


def node_verdict(graph_path: str, node_id: str, verdict: str, reason: str = "",
                 eval_json: str = "", dry_run: bool = False, ttl: int = 900,
                 dispatch_downstream: bool = True) -> dict[str, Any]:
    graph = load_graph(graph_path)
    sid = str(graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", ""))
    node = _node_by_id(graph, node_id)
    if not node:
        return {"ok": False, "reason": "unknown_node", "node": node_id}

    normalized = verdict.strip().lower()
    if normalized in {"pass", "passed", "ok"}:
        status = "passed"
    elif normalized in {"fail", "failed", "error"}:
        status = "failed"
    else:
        return {"ok": False, "reason": "invalid_verdict", "verdict": verdict}

    research_quality_gate: dict[str, Any] = {"required": False}
    if status == "passed" and _node_requires_deepresearch_quality_gate(node):
        resolved_eval_json = eval_json or _eval_json_file(sid, node_id)
        research_quality_gate = {
            "required": True,
            **_deepresearch_quality_gate_from_eval(resolved_eval_json),
        }
        if not research_quality_gate.get("present"):
            research_quality_gate = {
                "required": True,
                **_deepresearch_quality_gate_auto_run(sid, node, resolved_eval_json),
            }
            if not research_quality_gate.get("present"):
                return {
                    "ok": False,
                    "reason": "missing_deepresearch_quality_gate",
                    "node": node_id,
                    "status": "blocked",
                    "eval_json": str(resolved_eval_json),
                    "required_field": "research_quality_gate",
                    "research_quality_gate": research_quality_gate,
                }
        if not research_quality_gate.get("ok"):
            return {
                "ok": False,
                "reason": "deepresearch_quality_gate_failed",
                "node": node_id,
                "status": "blocked",
                "eval_json": str(resolved_eval_json),
                "research_quality_gate": research_quality_gate,
            }

    note_parts = []
    if reason:
        note_parts.append(reason)
    if eval_json:
        note_parts.append(f"eval_json={eval_json}")
    eval_assignments = _node_eval_assignments(node)
    parent = mark_node_result(graph, node_id, status, gate_status=status, note="; ".join(note_parts) or None)
    node["status"] = status
    node["updated_at"] = _utc_now()
    if eval_json:
        node["eval_json"] = eval_json
    if research_quality_gate.get("required"):
        node["research_quality_gate"] = research_quality_gate.get("gate") or research_quality_gate
    worker_pane = str(node.get("assigned_to") or "")
    worker_dispatch_id = str(node.get("dispatch_id") or "")
    effect_result: dict[str, Any] = {}
    if scan_effect is not None:
        try:
            observed_handoff = _existing_node_handoff(sid, node, graph) or _handoff_file(sid, node_id)
            effect_result = scan_effect(
                _dispatch_file(sid, node_id),
                handoff_file=observed_handoff,
                eval_file=_eval_md_file(sid, node_id),
                eval_json_file=eval_json or _eval_json_file(sid, node_id),
                verdict=status,
                record_db=not dry_run,
            )
            node["capability_effect"] = effect_result.get("effect", {})
        except Exception as exc:
            effect_result = {"ok": False, "reason": f"effect_scan_failed:{type(exc).__name__}", "error": str(exc)}
    node.pop("assigned_to", None)
    node.pop("dispatch_id", None)
    node.pop("eval_dispatch_group_id", None)
    _clear_eval_assignments(node)
    save_graph(graph_path, graph)

    worker_lease_released = False
    eval_lease_released = False
    if not dry_run and worker_pane and worker_dispatch_id:
        worker_lease_released = bool(
            release_lease(worker_pane, worker_dispatch_id, f"node_{status}").get("released")
        )
    if not dry_run and eval_assignments:
        eval_lease_released = any(
            bool(
                release_lease(
                    str(assignment.get("pane") or ""),
                    str(assignment.get("dispatch_id") or ""),
                    f"node_{status}",
                ).get("released")
            )
            for assignment in eval_assignments
            if str(assignment.get("pane") or "") and str(assignment.get("dispatch_id") or "")
        )

    downstream: dict[str, Any] = {"ok": True, "skipped": "verdict_not_passed"}
    if status == "passed" and dispatch_downstream and not parent.get("ready"):
        downstream = dispatch_ready(graph_path, dry_run=dry_run, ttl=ttl)
    elif status == "passed" and parent.get("ready"):
        downstream = {"ok": True, "skipped": "parent_ready"}
    parent_status_updated = _mark_parent_sprint_passed_if_ready(sid, parent, dry_run)

    return {
        "ok": bool(downstream.get("ok", True)),
        "node": node_id,
        "status": status,
        "parent": parent,
        "downstream": downstream,
        "dry_run": dry_run,
        "worker_lease_released": worker_lease_released,
        "eval_lease_released": eval_lease_released,
        "parent_status_updated": parent_status_updated,
        "capability_effect": effect_result,
        "research_quality_gate": research_quality_gate,
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="graph_node_dispatcher.py")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("drain-queue")
    p.add_argument("--sprint", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-items", type=int, default=0)
    p.add_argument("--ttl", type=int, default=900)

    p = sub.add_parser("dispatch-ready")
    p.add_argument("--graph", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ttl", type=int, default=900)
    p.add_argument("--max-parallel", type=int, default=8)

    p = sub.add_parser("dispatch-evals")
    p.add_argument("--graph", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ttl", type=int, default=900)
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-items", type=int, default=0)

    p = sub.add_parser("node-verdict")
    p.add_argument("--graph", required=True)
    p.add_argument("--node", required=True)
    p.add_argument("--verdict", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--eval-json", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ttl", type=int, default=900)
    p.add_argument("--no-dispatch-downstream", action="store_true")

    args = ap.parse_args()
    if args.cmd == "drain-queue":
        result = drain_queue(args.sprint, args.dry_run, args.max_items, args.ttl)
    elif args.cmd == "dispatch-ready":
        result = dispatch_ready(args.graph, args.dry_run, args.ttl, args.max_parallel)
    elif args.cmd == "dispatch-evals":
        result = dispatch_node_evals(args.graph, args.dry_run, args.ttl, args.force, args.max_items)
    elif args.cmd == "node-verdict":
        result = node_verdict(
            args.graph,
            args.node,
            args.verdict,
            reason=args.reason,
            eval_json=args.eval_json,
            dry_run=args.dry_run,
            ttl=args.ttl,
            dispatch_downstream=not args.no_dispatch_downstream,
        )
    else:
        ap.print_help()
        return 1

    print(_json(result))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
