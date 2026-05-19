#!/usr/bin/env python3
"""Role-aware Autoresearch advisor blocks for Solar-Harness panes.

This helper does not execute autoresearch. It only decides whether a pane
dispatch should receive an explicit quality-optimizer hint and renders a small
markdown block that keeps execution gated behind dry-run / --execute rules.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Any


ROLE_MAP = {
    "pm": "pm",
    "product": "pm",
    "产品经理": "pm",
    "planner": "planner",
    "规划者": "planner",
    "architect": "planner",
    "架构师": "planner",
    "builder": "builder",
    "建设者": "builder",
    "lab-builder": "builder",
    "evaluator": "evaluator",
    "审判官": "evaluator",
    "reviewer": "evaluator",
}


@dataclass(frozen=True)
class RoleProfile:
    title: str
    trigger: str
    use: str
    stop: str


PROFILES: dict[str, RoleProfile] = {
    "pm": RoleProfile(
        "PM requirements optimizer",
        "需求复杂、验收标准含糊、用户意图需要拆成可执行 issue 时。",
        "把用户问题改写成候选 local issue、验收 probes、风险/反例清单；只作为 PRD 质量检查，不写代码。",
        "PM 不得运行 --execute，不得替 Builder 生成实现。",
    ),
    "planner": RoleProfile(
        "Planner DAG optimizer",
        "DAG 边界、write_scope、并发切片、score gate 或 stop rules 需要更硬时。",
        "用 autoresearch.issue_loop 的 issue/score-gate 思路反审 task_graph：每个节点是否可独立验证、是否有清晰失败退出条件。",
        "Planner 只把建议写进 plan/task_graph；不得让 autoresearch 直接接管 Builder。",
    ),
    "builder": RoleProfile(
        "Builder execution optimizer",
        "实现轮次复杂、上一轮 FAIL、修复项可转成明确 local issue，或需要多轮评分门禁时。",
        "先 dry-run 生成/检查 local issue 计划；把 issue、命令、score gate 当作实现 checklist 和验证增强。",
        "除非用户明确授权并给出 --execute，否则不得启动 autoresearch 执行循环。",
    ),
    "evaluator": RoleProfile(
        "Evaluator review optimizer",
        "评估需要更强 evidence、反例、score gate、失败复现或修复建议结构化时。",
        "用 score-gate 思路补强 eval：每个 FAIL 要有证据、复现、期望分数/测试门禁和可交给 Builder 的 issue 化修复提示。",
        "Evaluator 不改代码，不运行 --execute；只把检查结果写进 eval.md/eval.json。",
    ),
}


GENERAL_PATTERNS = [
    r"\b(autoresearch|auto research|issue[- ]loop|local issue|score[- ]gate|passing score)\b",
    r"\b(task_graph|write_scope|acceptance|stop rules?|round|fail|review|eval|handoff)\b",
    r"验收|评分门禁|分数门禁|多轮|失败|修复|评审|反例|风险|并发边界|写范围",
]


ROLE_DEFAULT_ENABLED = {"pm", "planner", "builder", "evaluator"}


def normalize_role(role: str) -> str:
    lowered = role.strip().lower()
    for key, value in ROLE_MAP.items():
        if key.lower() in lowered:
            return value
    return lowered or "unknown"


def should_recommend(role: str, task: str) -> tuple[bool, list[str]]:
    canonical = normalize_role(role)
    text = f"{role}\n{task}".lower()
    reasons: list[str] = []
    if canonical in ROLE_DEFAULT_ENABLED:
        reasons.append(f"role:{canonical}")
    for pattern in GENERAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            reasons.append(f"pattern:{pattern}")
    return bool(reasons and canonical in PROFILES), reasons


def advisory_payload(sid: str, role: str, task: str) -> dict[str, Any]:
    canonical = normalize_role(role)
    recommended, reasons = should_recommend(role, task)
    profile = PROFILES.get(canonical)
    return {
        "ok": True,
        "sid": sid,
        "role": role,
        "canonical_role": canonical,
        "recommended": recommended,
        "reasons": reasons,
        "capabilities": [
            "autoresearch.pane_optimizer",
            "autoresearch.issue_loop",
            "autoresearch.score_gate",
        ] if recommended else [],
        "execution_policy": {
            "mode": "advisor_only_by_default",
            "default_command": "dry_run",
            "execute_requires": "--execute",
            "replaces_builder": False,
        },
        "profile": profile.__dict__ if profile else {},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("recommended"):
        return ""
    profile = payload.get("profile") or {}
    caps = ", ".join(payload.get("capabilities") or [])
    return f"""## Autoresearch Pane Optimizer

Status: advisor_only
Capability: {caps}
Role fit: {profile.get("title", payload.get("canonical_role", "unknown"))}

- When to use: {profile.get("trigger", "N/A")}
- How it improves this pane: {profile.get("use", "N/A")}
- Stop rule: {profile.get("stop", "N/A")}
- Execution gate: 默认只 dry-run；只有用户明确授权且命令包含 `--execute` 时，才允许运行 autoresearch 执行循环。
- Boundary: Autoresearch 不替代 PM/Planner/Builder/Evaluator；它只提供 issue 化拆解、score-gate、反例/风险和验证增强建议。
"""


def main() -> int:
    ap = argparse.ArgumentParser(prog="autoresearch_pane_optimizer.py")
    ap.add_argument("--sid", default="")
    ap.add_argument("--role", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = ap.parse_args()

    payload = advisory_payload(args.sid, args.role, args.task)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        text = render_markdown(payload)
        if text:
            print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
