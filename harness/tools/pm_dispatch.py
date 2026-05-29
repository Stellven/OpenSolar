#!/usr/bin/env python3
"""pm_dispatch.py — PM 发号施令：从主四分屏 PM pane 向无头算子 pane 派发任务。

用法：
  python3 pm_dispatch.py submit --role builder --objective "检查 gate_check 函数"
  python3 pm_dispatch.py submit --operator mini-claude-sonnet-builder --objective "..."
  python3 pm_dispatch.py fleet-status
  python3 pm_dispatch.py inbox [--limit N]
  python3 pm_dispatch.py result --task-id pm-xxx

直接通过 solar-harness.sh：
  solar-harness pm-dispatch --role builder --objective "..."
  solar-harness pm-fleet status
  solar-harness pm-fleet inbox
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
PHYSICAL_OPERATORS_PATH = Path(
    os.environ.get("SOLAR_MULTI_TASK_OPERATORS", HARNESS_DIR / "config" / "physical-operators.json")
)
PERSONAS_DIR = HARNESS_DIR / "personas"
PM_INBOX_DIR = HARNESS_DIR / "run" / "pm-inbox"
OPERATOR_INBOX_DIR = HARNESS_DIR / "run" / "operator-inbox"
OPERATOR_RESULTS_DIR = HARNESS_DIR / "run" / "operator-results"
OPERATOR_STATUS_DIR = HARNESS_DIR / "run" / "operator-status"
SPRINTS_DIR = Path(os.environ.get("SOLAR_HARNESS_SPRINTS_DIR", HARNESS_DIR / "sprints"))

# ── 角色别名映射 ───────────────────────────────────────────────────────────────
ROLE_ALIASES: dict[str, str] = {
    "build": "builder",
    "implementation": "builder",
    "implementer": "builder",
    "coder": "builder",
    "dev": "builder",
    "plan": "planner",
    "planning": "planner",
    "architect": "planner",
    "design": "planner",
    "eval": "evaluator",
    "review": "evaluator",
    "judge": "evaluator",
    "reviewer": "evaluator",
    "verifier": "evaluator",
    "knowledge": "builder",   # 知识提取走 builder 角色
    "extract": "builder",
    "product": "pm",
    "product-manager": "pm",
}

NON_DISPATCHABLE_STATES = {"leased", "running", "draining", "cooldown", "quota_exhausted", "auth_expired", "disabled"}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short_id() -> str:
    return str(uuid.uuid4())[:8]



def capture_entrypoint_raw_intent(
    *,
    source_channel: str,
    text: str,
    sprint_id: str = "",
    node_id: str = "",
    role: str = "",
    repo: str = "",
) -> dict[str, Any]:
    full_text = text.strip()
    if sprint_id or node_id or role:
        full_text = (
            f"[entrypoint_metadata]\n"
            f"sprint_id: {sprint_id or 'N/A'}\n"
            f"node_id: {node_id or 'N/A'}\n"
            f"role: {role or 'N/A'}\n\n"
            f"[raw_request]\n{full_text}"
        )
    cmd = [
        sys.executable,
        str(HARNESS_DIR / "lib" / "intent_gateway.py"),
        "capture",
        "--source-channel", source_channel,
        "--actor", "user",
        "--device", "mac_mini_pm_dispatch",
        "--repo", repo or str(HARNESS_DIR),
        "--source-trust", source_channel,
        "--text", full_text,
        "--json",
    ]
    if sprint_id:
        cmd.extend(["--sprint-id", sprint_id])
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "intent_gateway capture failed").strip())
    payload = json.loads(proc.stdout)
    intent_id = str(payload.get("intent_id") or "")
    if intent_id:
        consumer_cmd = [
            sys.executable,
            str(HARNESS_DIR / "lib" / "intent_consumer.py"),
            "consume",
            "--intent-id", intent_id,
            "--json",
        ]
        consumer = subprocess.run(consumer_cmd, text=True, capture_output=True, timeout=120)
        if consumer.returncode != 0:
            raise RuntimeError((consumer.stderr or consumer.stdout or "intent_consumer failed").strip())
        payload["consumer"] = json.loads(consumer.stdout)
    return payload


def print_intent_capture(payload: dict[str, Any], entrypoint: str) -> None:
    print("✅ RawIntent 已捕获")
    print(f"   entrypoint  = {entrypoint}")
    print(f"   intent_id   = {payload.get('intent_id', '')}")
    print(f"   title       = {payload.get('title', '')}")
    print(f"   lane        = {payload.get('lane', '')}")
    print(f"   raw_intent  = {payload.get('raw_intent', '')}")
    print(f"   requirement = {payload.get('requirement_ir', '')}")
    print("   direct_dispatch = disabled")


# ── Registry ──────────────────────────────────────────────────────────────────

def load_registry() -> dict[str, Any]:
    if not PHYSICAL_OPERATORS_PATH.exists():
        return {"version": 1, "operators": {}}
    try:
        return json.loads(PHYSICAL_OPERATORS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "operators": {}}


def get_operator_runtime_state(operator_id: str) -> str:
    status_file = OPERATOR_STATUS_DIR / f"{operator_id}.json"
    if not status_file.exists():
        return "idle"
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return str(data.get("runtime_state", "idle"))
    except Exception:
        return "idle"


def get_operator_status_data(operator_id: str) -> dict[str, Any]:
    """Return the full status JSON for an operator, or empty dict if absent/expired."""
    status_file = OPERATOR_STATUS_DIR / f"{operator_id}.json"
    if not status_file.exists():
        return {}
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _format_reset_eta(expires_at: str) -> str:
    """Return a human-readable reset ETA string, or empty string if not available."""
    if not expires_at:
        return ""
    try:
        exp = datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = exp - now
        total_secs = int(delta.total_seconds())
        if total_secs <= 0:
            return "soon"
        hours, rem = divmod(total_secs, 3600)
        minutes = rem // 60
        if hours > 0:
            return f"~{hours}h{minutes:02d}m"
        return f"~{minutes}m"
    except Exception:
        return ""


def is_dispatchable(op: dict[str, Any]) -> tuple[bool, str]:
    if not op.get("enabled", False):
        return False, f"disabled: {op.get('disabled_reason', 'unknown')}"
    if not op.get("available", False):
        return False, f"unavailable: health={op.get('health_status', 'unknown')}"
    operator_id = op.get("operator_id", "")
    state = get_operator_runtime_state(operator_id)
    if state in NON_DISPATCHABLE_STATES:
        if state in ("cooldown", "quota_exhausted", "auth_expired"):
            status = get_operator_status_data(operator_id)
            expires_at = str(status.get("expires_at") or "")
            eta = _format_reset_eta(expires_at)
            reason = f"runtime_state={state}"
            if eta:
                reason += f", resets {eta}"
            if expires_at:
                reason += f" (until {expires_at})"
            return False, reason
        return False, f"runtime_state={state}"
    return True, ""


def load_task_graph_node(sprint_id: str, node_id: str) -> dict[str, Any] | None:
    path = SPRINTS_DIR / f"{sprint_id}.task_graph.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for node in payload.get("nodes", []) or []:
        if str(node.get("id")) == node_id:
            return dict(node)
    return None


def _capsule_submit_metadata(node: dict[str, Any] | None) -> dict[str, Any]:
    if not node:
        return {}
    if not (
        node.get("capability_native")
        or node.get("capability_capsule_id")
        or node.get("execution_capsule_id")
        or node.get("capsule_plan")
    ):
        return {}
    capsule_plan = dict(node.get("capsule_plan") or {})
    return {
        "capability_native": bool(node.get("capability_native", True)),
        "capability_capsule_id": node.get("capability_capsule_id") or capsule_plan.get("capability_capsule_id"),
        "dispatch_task_type": node.get("dispatch_task_type") or capsule_plan.get("dispatch_task_type"),
        "logical_operator": node.get("logical_operator", ""),
        "capsule_plan": capsule_plan,
    }


# ── 算子选择 ──────────────────────────────────────────────────────────────────

def normalize_role(role: str) -> str:
    r = role.strip().lower().replace("_", "-")
    return ROLE_ALIASES.get(r, r)


def select_operator_by_role(
    role: str,
    task_type: str = "",
    prefer_operator: str = "",
    resolved_capsule: dict[str, Any] | None = None,
    logical_operator: str = "",
) -> tuple[str, dict[str, Any], str]:
    """选择最合适的可调度算子。

    Returns:
        (operator_id, operator_config, fallback_reason)
    """
    registry = load_registry()
    operators = registry.get("operators", {})
    norm_role = normalize_role(role)
    capsule_constraints = dict((resolved_capsule or {}).get("operator_constraints") or {})
    preferred_ops = set(capsule_constraints.get("preferred", []) or [])
    forbidden_ops = set(capsule_constraints.get("forbidden", []) or [])
    default_profile = str(capsule_constraints.get("default_operator_profile") or "")

    # 1. 指定 operator 优先
    if prefer_operator:
        if prefer_operator in operators:
            op = dict(operators[prefer_operator])
            op["operator_id"] = prefer_operator
            ok, reason = is_dispatchable(op)
            if ok:
                return prefer_operator, op, ""
            else:
                return "", {}, f"preferred_operator_unavailable: {prefer_operator}: {reason}"
        return "", {}, f"preferred_operator_not_found: {prefer_operator}"

    # 2. 按 role 过滤，优先选 print_once（不占 interactive slot）再选 interactive_repl
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for op_id, spec in operators.items():
        op = dict(spec)
        op["operator_id"] = op_id
        ok, _ = is_dispatchable(op)
        if not ok:
            continue
        if op_id in forbidden_ops:
            continue
        op_roles = [str(r).lower() for r in op.get("roles", [op.get("role", "")])]
        if norm_role not in op_roles:
            continue
        # 评分：print_once > command > interactive_repl（避免占四分屏 slot）
        kind = str(op.get("launch_cmd_kind", "") or op.get("backend", ""))
        if "print_once" in kind or "print" in kind:
            priority = 10
        elif "command" in kind:
            priority = 5
        else:
            priority = 1   # interactive_repl 最后选
        # task_type 加分
        if task_type:
            task_classes = [str(t).lower() for t in op.get("task_classes", [])]
            if any(task_type.lower() in tc for tc in task_classes):
                priority += 3
        preferred_for = [str(item).lower() for item in op.get("preferred_for", [])]
        if logical_operator and logical_operator.lower() in preferred_for:
            priority += 2
        if norm_role in preferred_for:
            priority += 2
        if preferred_ops and op_id in preferred_ops:
            priority += 20
        if default_profile and (op_id == default_profile or str(op.get("profile", "")) == default_profile):
            priority += 8
        candidates.append((priority, op_id, op))

    if not candidates:
        return "", {}, f"no_dispatchable_operator_for_role: {norm_role}"

    candidates.sort(key=lambda x: -x[0])
    _, best_id, best_op = candidates[0]
    return best_id, best_op, ""


# ── Dispatch 文件构建 ──────────────────────────────────────────────────────────

def persona_text(persona: str) -> tuple[str, str]:
    path = PERSONAS_DIR / f"{persona}.md"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return str(path), text[:10000]
    except Exception:
        return str(path), "N/A"


def build_pm_dispatch_text(
    task_id: str,
    operator_id: str,
    operator: dict[str, Any],
    objective: str,
    sprint_id: str,
    node_id: str,
    result_path: str,
    context: str = "",
) -> str:
    persona_name = str(operator.get("persona") or operator.get("role") or "builder")
    persona_path, persona_body = persona_text(persona_name)
    harness = HARNESS_DIR / "solar-harness.sh"

    ctx_block = ""
    if context.strip():
        ctx_block = f"\n## PM Context\n\n{context.strip()}\n"

    return textwrap.dedent(f"""\
        <!-- SOLAR_PM_DISPATCH -->
        # Solar PM Dispatch

        Task ID: `{task_id}`
        Sprint: `{sprint_id}`
        Node: `{node_id}`
        Operator: `{operator_id}`
        Model: `{operator.get("model", "unknown")}`
        Backend: `{operator.get("backend", "unknown")}`
        Issued by: `PM pane (solar-harness:0.0)`
        Issued at: `{_now()}`

        ## Definition of Done

        任务没有完成，除非同时满足：

        1. 真实调用链接入：新增/修改功能已接入真实调用链。
        2. 禁止硬编码：不得硬编码业务数据、路径、token。
        3. 执行证据齐全：列出实际命令和结果摘要。
        4. 结构化收尾：已完成 / 已验证 / 未验证 / 风险 / 后续待办。

        ## Worker Persona

        Persona file: `{persona_path}`

        ```markdown
        {persona_body}
        ```
        {ctx_block}
        ## Objective (PM Order)

        {objective}

        ## Required Closeout

        把结论写到：`{result_path}`

        格式：
        ```
        # PM Task Result — {task_id}

        ## 已完成
        ## 已验证
        ## 结论摘要
        ## 风险/限制
        ## 后续建议
        ```

        完成后运行（标记任务完成）：
        ```bash
        python3 "{HARNESS_DIR}/tools/pm_dispatch.py" complete --task-id "{task_id}"
        ```
    """)


# ── Inbox / Result 管理 ───────────────────────────────────────────────────────

def pm_inbox_dir() -> Path:
    PM_INBOX_DIR.mkdir(parents=True, exist_ok=True)
    return PM_INBOX_DIR


def write_pm_task_record(task_id: str, record: dict[str, Any]) -> Path:
    path = pm_inbox_dir() / f"{task_id}.json"
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    os.replace(tmp, str(path))
    return path


def read_pm_task_record(task_id: str) -> dict[str, Any] | None:
    path = pm_inbox_dir() / f"{task_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_pm_tasks(limit: int = 20) -> list[dict[str, Any]]:
    tasks = []
    d = pm_inbox_dir()
    for p in sorted(d.glob("pm-*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            tasks.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return tasks


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, str(path))


def _append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _new_sprint_id() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("sprint-%Y%m%d-%H%M%S")


def ensure_compiled_sprint_status(sprint_id: str, title: str, summary: str) -> Path:
    status_path = SPRINTS_DIR / f"{sprint_id}.status.json"
    now = _now()
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            status = {}
    else:
        status = {
            "id": sprint_id,
            "title": title,
            "summary": summary,
            "created_at": now,
            "round": 0,
            "history": [],
        }

    status.update(
        {
            "id": sprint_id,
            "title": title,
            "summary": summary,
            "status": "drafting",
            "phase": "prd_ready",
            "handoff_to": "planner",
            "target_role": "planner",
            "updated_at": now,
        }
    )
    history = list(status.get("history") or [])
    history.append({"ts": now, "event": "compiled_requirement_package_created", "by": "codex-pm-router"})
    status["history"] = history[-20:]
    _write_json_atomic(status_path, status)
    _append_event(
        SPRINTS_DIR / f"{sprint_id}.events.jsonl",
        {
            "ts": now,
            "actor": "pm_dispatch",
            "event": "compiled_requirement_package_created",
            "sid": sprint_id,
            "status": "info",
            "detail": {
                "phase": "prd_ready",
                "handoff_to": "planner",
                "target_role": "planner",
            },
        },
    )
    return status_path


def _planner_objective_for_compiled_sprint(sprint_id: str) -> str:
    base = str(SPRINTS_DIR / sprint_id)
    return textwrap.dedent(
        f"""\
        请接手 {sprint_id}：Requirement Compiler 已生成首版需求编译包。

        先读取：
        - {base}.product-brief.md
        - {base}.prd.md
        - {base}.contract.md
        - {base}.task_graph.json
        - {base}.requirement_ir.json
        - {base}.handoff.md

        你的任务：
        1. 基于 compiled requirement package 产出 design.md 和 plan.md。
        2. 如有必要，细化或修正 task_graph.json，但不得绕过 compiled contracts。
        3. 不要直接跳 Builder；保持 PM -> Planner -> task_graph -> Builder 主链。
        4. 如果 compiled package 缺失关键字段，先写明 blocker 和修正建议。
        """
    ).strip()


def cmd_compile_request(args: argparse.Namespace) -> int:
    request_text = str(args.text or "").strip()
    if not request_text and args.input_file:
        request_text = Path(args.input_file).read_text(encoding="utf-8")
    if not request_text:
        request_text = sys.stdin.read().strip()
    if not request_text:
        print("ERROR: request text is required via --text, --input-file, or stdin", file=sys.stderr)
        return 1

    sprint_id = str(args.sprint or "")
    if os.environ.get("SOLAR_PM_DISPATCH_ALLOW_DIRECT") != "1":
        try:
            payload = capture_entrypoint_raw_intent(
                source_channel="pm_compile_request",
                text=request_text,
                sprint_id=sprint_id,
                role="pm",
                repo=str(Path(args.workspace_root or os.getcwd())),
            )
        except Exception as exc:
            print(f"ERROR: RawIntent capture failed: {exc}", file=sys.stderr)
            return 1
        print_intent_capture(payload, "pm_dispatch.compile-request")
        return 0

    sprint_id = str(args.sprint or _new_sprint_id())
    workspace_root = Path(args.workspace_root or os.getcwd())

    router_path = Path(__file__).resolve().parent / "codex_pm_router.py"
    spec = importlib.util.spec_from_file_location("codex_pm_router", router_path)
    if spec is None or spec.loader is None:
        print(f"ERROR: unable to load {router_path}", file=sys.stderr)
        return 1
    router = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(router)

    payload = router.build_pm_intake(
        request_text,
        papers=list(getattr(args, "paper", []) or []),
        logs=list(getattr(args, "log", []) or []),
        repo_context=list(getattr(args, "repo_context", []) or []),
        sprint_id=sprint_id,
        target_system=str(getattr(args, "target_system", "solar-harness") or "solar-harness"),
    )
    validation = router.validate_compiled_package(payload)
    if not validation.get("ok", False):
        print("ERROR: compiled requirement package failed validation", file=sys.stderr)
        for item in validation.get("errors", []) or []:
            print(f" - {item}", file=sys.stderr)
        return 2
    emitted = router.emit_requirement_package(
        payload,
        workspace_root=workspace_root,
        sprint_root=SPRINTS_DIR,
        sprint_id=sprint_id,
    )
    status_path = ensure_compiled_sprint_status(
        sprint_id,
        title=payload["compiled_artifacts"]["product_brief"]["title"],
        summary=payload["compiled_artifacts"]["product_brief"]["problem"][:180],
    )
    emitted["status"] = str(status_path)

    if bool(getattr(args, "dispatch_planner", False)):
        submit_args = argparse.Namespace(
            role="planner",
            objective=_planner_objective_for_compiled_sprint(sprint_id),
            operator="",
            sprint=sprint_id,
            node="N0",
            task_type="planning",
            context=f"compiled_requirement_ir={emitted['requirement_ir']}",
            dry_run=bool(getattr(args, "dry_run", False)),
        )
        rc = cmd_submit(submit_args)
        if rc != 0:
            return rc

    print("✅ Requirement Compiler package ready")
    print(f"   sprint_id   = {sprint_id}")
    print(f"   workspace   = {workspace_root}")
    print(f"   pm_dir      = {emitted['pm_dir']}")
    print(f"   requirement = {emitted['requirement_ir']}")
    print(f"   product_brief = {emitted['sprint_product_brief']}")
    print(f"   prd         = {emitted['sprint_prd']}")
    print(f"   contract    = {emitted['sprint_contract']}")
    print(f"   task_graph  = {emitted['sprint_task_graph']}")
    print(f"   status      = {emitted['status']}")
    return 0


# ── 核心 submit 逻辑 ──────────────────────────────────────────────────────────

def cmd_submit(args: argparse.Namespace) -> int:
    role = str(args.role or "builder")
    objective = str(args.objective or "").strip()
    if not objective:
        print("ERROR: --objective is required", file=sys.stderr)
        return 1

    prefer_operator = str(args.operator or "").strip()
    requested_sprint_id = str(args.sprint or "")
    node_id_for_intent = str(args.node or "N1")
    if os.environ.get("SOLAR_PM_DISPATCH_ALLOW_DIRECT") != "1":
        try:
            payload = capture_entrypoint_raw_intent(
                source_channel="pm_dispatch",
                text=objective + (f"\n\n[context]\n{args.context}" if str(args.context or "").strip() else ""),
                sprint_id=requested_sprint_id,
                node_id=node_id_for_intent,
                role=role,
                repo=str(HARNESS_DIR),
            )
        except Exception as exc:
            print(f"ERROR: RawIntent capture failed: {exc}", file=sys.stderr)
            return 1
        print_intent_capture(payload, "pm_dispatch.submit")
        return 0

    sprint_id = str(args.sprint or f"pm-adhoc-{_short_id()}")
    node_id = str(args.node or "N1")
    task_type = str(args.task_type or "")
    dry_run: bool = bool(args.dry_run)
    context = str(args.context or "")
    task_graph_node = load_task_graph_node(sprint_id, node_id)
    capsule_submit = _capsule_submit_metadata(task_graph_node)
    logical_operator = str(capsule_submit.get("logical_operator") or (task_graph_node or {}).get("logical_operator") or "")
    if not task_type:
        task_type = str(capsule_submit.get("dispatch_task_type") or (task_graph_node or {}).get("type") or "")

    resolved_capsule: dict[str, Any] | None = None
    if capsule_submit.get("capability_capsule_id"):
        try:
            lib_dir = HARNESS_DIR / "lib"
            if str(lib_dir) not in sys.path:
                sys.path.insert(0, str(lib_dir))
            from capability_capsules import resolve_capability_capsule_for_task  # type: ignore

            resolved_capsule = resolve_capability_capsule_for_task(
                {
                    "task_type": task_type,
                    "objective": objective[:300],
                    "capability_capsule_id": capsule_submit["capability_capsule_id"],
                }
            )
        except Exception:
            resolved_capsule = None

    # 1. 选算子
    operator_id, operator, fallback_reason = select_operator_by_role(
        role=role,
        task_type=task_type,
        prefer_operator=prefer_operator,
        resolved_capsule=resolved_capsule,
        logical_operator=logical_operator,
    )
    if not operator_id:
        msg = f"ERROR: 没有可用算子 ({fallback_reason})"
        # Surface cooldown ETA when the fallback reason mentions cooldown/quota
        if any(kw in fallback_reason for kw in ("cooldown", "quota_exhausted", "auth_expired")):
            # Try to find the preferred/blocked operator for ETA details
            _blocked_op = prefer_operator or ""
            if _blocked_op:
                _status = get_operator_status_data(_blocked_op)
                _expires = str(_status.get("expires_at") or "")
                _eta = _format_reset_eta(_expires)
                if _eta:
                    msg += f"\n  ⏳ 冷却中，重置时间: {_eta}"
                if _expires:
                    msg += f" (until {_expires})"
        print(msg, file=sys.stderr)
        return 1

    # 2. 构建 task_id 和结果路径
    task_id = f"pm-{sprint_id}-{node_id}-{_short_id()}"
    result_path = str(SPRINTS_DIR / f"{sprint_id}.{node_id}.pm-result.md")

    # 3. 构建 dispatch 文件
    dispatch_text = build_pm_dispatch_text(
        task_id=task_id,
        operator_id=operator_id,
        operator=operator,
        objective=objective,
        sprint_id=sprint_id,
        node_id=node_id,
        result_path=result_path,
        context=context,
    )

    dispatch_dir = HARNESS_DIR / "run" / "pm-dispatch-files"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    dispatch_file = dispatch_dir / f"{task_id}.md"

    if dry_run:
        print(f"[DRY-RUN] operator_id = {operator_id}")
        print(f"[DRY-RUN] task_id     = {task_id}")
        print(f"[DRY-RUN] result_path = {result_path}")
        print(f"[DRY-RUN] dispatch_file = {dispatch_file}")
        print("\n--- dispatch preview ---")
        print(dispatch_text[:1500])
        return 0

    # 4. 写 dispatch 文件
    dispatch_file.write_text(dispatch_text, encoding="utf-8")

    # 5. 构建 task envelope → operator_runtime.submit
    envelope = {
        "task_id": task_id,
        "sprint_id": sprint_id,
        "node_id": node_id,
        "operator_id": operator_id,
        "task_type": task_type or "pm_order",
        "objective": objective[:300],
        "dispatch_file": str(dispatch_file),
        "result_path": result_path,
        "issued_by": "pm_pane",
        "issued_at": _now(),
        "pm_context": context[:500] if context else "",
    }
    if logical_operator:
        envelope["logical_operator"] = logical_operator
    if task_graph_node:
        envelope["task_graph_node"] = {
            "id": task_graph_node.get("id"),
            "goal": task_graph_node.get("goal"),
            "acceptance": task_graph_node.get("acceptance", []),
            "requirement_ids": task_graph_node.get("requirement_ids", []),
        }
    if capsule_submit.get("capability_capsule_id"):
        envelope["capability_native"] = bool(capsule_submit.get("capability_native", True))
        envelope["capability_capsule_id"] = str(capsule_submit["capability_capsule_id"])
        envelope["capsule_plan"] = capsule_submit.get("capsule_plan", {})

    record: dict[str, Any] = {
        "task_id": task_id,
        "sprint_id": sprint_id,
        "node_id": node_id,
        "operator_id": operator_id,
        "objective": objective,
        "dispatch_file": str(dispatch_file),
        "result_path": result_path,
        "status": "submitted",
        "submitted_at": _now(),
    }
    if capsule_submit.get("capability_capsule_id"):
        record["capability_capsule_id"] = capsule_submit["capability_capsule_id"]
        record["logical_operator"] = logical_operator

    # 尝试通过 operator_runtime.submit 投递
    try:
        lib_dir = HARNESS_DIR / "lib"
        if str(lib_dir) not in sys.path:
            sys.path.insert(0, str(lib_dir))
        tools_dir = HARNESS_DIR / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))

        from operator_runtime import submit  # type: ignore
        result = submit(envelope)
        record["status"] = "submitted"
        record["lease_id"] = result.get("lease_id", "")
        record["inbox_path"] = result.get("inbox_path", "")
        submit_mode = "operator_runtime.submit"
    except Exception as exc:
        # fallback: 直接写 operator inbox（无 lease，operatord 会拾取）
        inbox_dir = OPERATOR_INBOX_DIR / operator_id
        inbox_dir.mkdir(parents=True, exist_ok=True)
        inbox_path = inbox_dir / f"{task_id}.json"
        tmp = str(inbox_path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(inbox_path))
        record["status"] = "submitted_fallback"
        record["inbox_path"] = str(inbox_path)
        record["submit_error"] = str(exc)
        submit_mode = "direct_inbox"

    # 6. 写 PM inbox 记录
    write_pm_task_record(task_id, record)

    # 7. 输出
    print(f"✅ PM 任务已提交")
    print(f"   task_id     = {task_id}")
    print(f"   operator    = {operator_id} ({operator.get('model', '?')})")
    print(f"   submit_mode = {submit_mode}")
    print(f"   dispatch    = {dispatch_file}")
    print(f"   result      = {result_path}")
    print()
    print(f"查看结果：solar-harness pm-fleet inbox")
    print(f"等待完成：watch cat '{result_path}'")

    return 0


def cmd_fleet_status(args: argparse.Namespace) -> int:
    registry = load_registry()
    operators = registry.get("operators", {})
    print(f"{'算子 ID':<40} {'角色':<12} {'模型':<20} {'运行时状态':<18} {'冷却/重置 ETA'}")
    print("-" * 110)
    for op_id, spec in operators.items():
        op = dict(spec)
        enabled = op.get("enabled", False)
        if not enabled:
            rt_state = "disabled"
            cooldown_col = ""
        else:
            rt_state = get_operator_runtime_state(op_id)
            cooldown_col = ""
            if rt_state in ("cooldown", "quota_exhausted", "auth_expired"):
                status = get_operator_status_data(op_id)
                expires_at = str(status.get("expires_at") or "")
                eta = _format_reset_eta(expires_at)
                cooldown_col = f"{rt_state}"
                if eta:
                    cooldown_col += f" resets {eta}"
                if expires_at:
                    cooldown_col += f" [{expires_at}]"
        role = str(op.get("role", "?"))
        model = str(op.get("model", "?"))
        ok_sym = "✅" if enabled else "❌"
        print(f"{ok_sym} {op_id:<38} {role:<12} {model:<20} {rt_state:<18} {cooldown_col}")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    limit = int(getattr(args, "limit", 20))
    tasks = list_pm_tasks(limit=limit)
    if not tasks:
        print("PM inbox 为空（暂无任务记录）")
        return 0
    print(f"{'Task ID':<36} {'算子':<35} {'状态':<20} {'提交时间'}")
    print("-" * 110)
    for t in tasks:
        tid = str(t.get("task_id", "?"))[:35]
        op = str(t.get("operator_id", "?"))[:34]
        st = str(t.get("status", "?"))[:19]
        ts = str(t.get("submitted_at", "?"))[:19]
        print(f"{tid:<36} {op:<35} {st:<20} {ts}")
    return 0


def cmd_result(args: argparse.Namespace) -> int:
    task_id = str(args.task_id or "").strip()
    if not task_id:
        print("ERROR: --task-id required", file=sys.stderr)
        return 1
    record = read_pm_task_record(task_id)
    if not record:
        print(f"ERROR: task {task_id} not found in PM inbox", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2, ensure_ascii=False))

    # Surface any active cooldown for the operator that ran this task
    operator_id = str(record.get("operator_id") or "")
    if operator_id:
        rt_state = get_operator_runtime_state(operator_id)
        if rt_state in ("cooldown", "quota_exhausted", "auth_expired"):
            status = get_operator_status_data(operator_id)
            expires_at = str(status.get("expires_at") or "")
            eta = _format_reset_eta(expires_at)
            print(f"\n⚠️  算子冷却中: operator={operator_id} state={rt_state}", end="")
            if eta:
                print(f", resets {eta}", end="")
            if expires_at:
                print(f" (until {expires_at})", end="")
            print()

    result_path = Path(record.get("result_path", ""))
    if result_path.exists():
        print("\n--- 结果文件内容 ---")
        print(result_path.read_text(encoding="utf-8", errors="replace"))
    else:
        print(f"\n结果文件尚未生成：{result_path}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """算子调用：标记任务完成（写入 PM inbox）"""
    task_id = str(args.task_id or "").strip()
    if not task_id:
        print("ERROR: --task-id required", file=sys.stderr)
        return 1
    record = read_pm_task_record(task_id) or {}
    record["task_id"] = task_id
    record["status"] = "completed"
    record["completed_at"] = _now()
    write_pm_task_record(task_id, record)
    print(f"✅ 任务 {task_id} 已标记为 completed")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        prog="pm_dispatch",
        description="PM 入口：默认只捕获 RawIntent；直接派发需显式 SOLAR_PM_DISPATCH_ALLOW_DIRECT=1",
    )
    sub = p.add_subparsers(dest="cmd")

    # submit
    s = sub.add_parser("submit", help="捕获 PM 原始需求为 RawIntent（默认不直接派发）")
    s.add_argument("--role", default="builder", help="目标角色 (builder/planner/evaluator/knowledge)")
    s.add_argument("--objective", required=True, help="任务描述（自然语言）")
    s.add_argument("--operator", default="", help="指定物理算子 ID（可选）")
    s.add_argument("--sprint", default="", help="关联 sprint ID（可选，默认 pm-adhoc-xxx）")
    s.add_argument("--node", default="N1", help="关联 DAG 节点 ID（默认 N1）")
    s.add_argument("--task-type", default="", help="任务类型提示（用于算子评分）")
    s.add_argument("--context", default="", help="额外上下文（注入 dispatch 文件）")
    s.add_argument("--dry-run", action="store_true", help="预览，不实际提交")

    cr = sub.add_parser("compile-request", help="捕获编译请求为 RawIntent（默认不直接创建 sprint/package）")
    cr.add_argument("--text", default="", help="原始需求文本")
    cr.add_argument("--input-file", default="", help="从文件读取原始需求")
    cr.add_argument("--paper", action="append", default=[], help="论文标题、链接或标识")
    cr.add_argument("--log", action="append", default=[], help="相关日志路径")
    cr.add_argument("--repo-context", action="append", default=[], help="repo/模块上下文")
    cr.add_argument("--sprint", default="", help="目标 sprint id；默认自动生成")
    cr.add_argument("--workspace-root", default="", help="写入 .pm/ 的工作区根目录；默认当前目录")
    cr.add_argument("--target-system", default="solar-harness", choices=["solar-harness", "codex"], help="下游目标系统")
    cr.add_argument("--dispatch-planner", action="store_true", help="编译后自动 handoff 给 planner")
    cr.add_argument("--dry-run", action="store_true", help="和 --dispatch-planner 配合时预览 planner 派单")

    # fleet-status
    sub.add_parser("fleet-status", help="查看所有物理算子的状态")

    # inbox
    ib = sub.add_parser("inbox", help="查看 PM 任务收件箱")
    ib.add_argument("--limit", type=int, default=20, help="显示最近 N 条")

    # result
    r = sub.add_parser("result", help="查看任务结果")
    r.add_argument("--task-id", required=True, help="Task ID")

    # complete
    c = sub.add_parser("complete", help="标记任务完成（由算子调用）")
    c.add_argument("--task-id", required=True, help="Task ID")

    args = p.parse_args()
    dispatch = {
        "submit": cmd_submit,
        "compile-request": cmd_compile_request,
        "fleet-status": cmd_fleet_status,
        "inbox": cmd_inbox,
        "result": cmd_result,
        "complete": cmd_complete,
    }
    fn = dispatch.get(args.cmd or "")
    if fn is None:
        p.print_help()
        return 0
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
