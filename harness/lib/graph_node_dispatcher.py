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
STATE_READ_PREFLIGHT = """<!-- SOLAR_STATE_READ_PREFLIGHT -->
## 必须先读状态 (防写入 hook 卡死)

在任何 Write/Edit/handoff/eval/status 更新之前，必须先用 Claude/Codex 的 **Read 工具**读取：

`/Users/sihaoli/.solar/STATE.md`

不要用 `cat` 替代这一步；本地 `state-read-enforcer.sh` hook 只认 Read 工具标记。

如果 Write/Edit hook 仍阻断，立刻 Read 上面的 STATE 文件后重试原写入一次，不要停在“已读”等待。

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
from pane_lease import acquire as acquire_lease, release as release_lease, read_lease  # noqa: E402
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


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


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


def _eval_dispatch_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval-dispatch.md"


def _eval_md_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval.md"


def _eval_json_file(sid: str, node_id: str) -> Path:
    return SPRINTS_DIR / f"{sid}.{_safe_node_id(node_id)}-eval.json"


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
        status = str(result.get("status") or node.get("status") or "pending").lower()
        return {
            "ok": True,
            "status": status,
            "dispatch_id": node.get("dispatch_id") or result.get("dispatch_id") or "",
            "assigned_to": node.get("assigned_to") or result.get("assigned_to") or "",
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
            node["status"] = status
            node["updated_at"] = _utc_now()
            if clear_assignment:
                node.pop("assigned_to", None)
                node.pop("dispatch_id", None)
            else:
                if pane:
                    node["assigned_to"] = pane
                if dispatch_id:
                    node["dispatch_id"] = dispatch_id
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

    return f"""{STATE_READ_PREFLIGHT}

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
   /Users/sihaoli/.solar/harness/solar-harness.sh graph-scheduler mark --graph "{graph_path}" --node "{node_id}" --status reviewing --in-place
   ```
"""


def build_eval_dispatch_text(graph: dict[str, Any], graph_path: str, node: dict[str, Any], pane: str,
                             dispatch_id: str) -> str:
    sid = str(graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", ""))
    node_id = str(node.get("id") or "")
    handoff = _handoff_file(sid, node_id)
    eval_md = _eval_md_file(sid, node_id)
    eval_json = _eval_json_file(sid, node_id)
    node_dispatch = _dispatch_file(sid, node_id)
    contract = SPRINTS_DIR / f"{sid}.contract.md"

    return f"""{STATE_READ_PREFLIGHT}

# DAG Node Evaluation Dispatch — {sid} / {node_id}

Sprint: `{sid}`
Node: `{node_id}`
Pane: `{pane}`
Dispatch ID: `{dispatch_id}`
Graph: `{graph_path}`
Handoff: `{handoff}`

## Evaluation Scope

- 只评审本 DAG node：`{node_id}`。
- 不要评审 parent sprint。
- 不要把 parent sprint 标成 passed。
- 只根据 node goal / acceptance / write_scope / handoff evidence 给 verdict。

## Node Goal

{node.get("goal", "N/A")}

## Acceptance

{_acceptance_lines(node.get("acceptance"))}

## Required Capabilities

{_scope_lines(node.get("required_capabilities"))}

## Write Scope

{_scope_lines(node.get("write_scope"))}

## Required Reads

```bash
cat "{graph_path}"
cat "{contract}"
cat "{node_dispatch}"
cat "{handoff}"
solar-harness session evaluate "{sid}" --json
```

## Log-Native Evaluation Requirement

- 评审必须消费 append-only session log，不得只看最终 handoff 文件。
- 在 eval.md 的 `Evidence Checked` 中写入 `Session Log: solar-harness session evaluate used`。
- 如果 `session evaluate` 返回 errors/warnings，必须逐项解释是否阻塞本 node verdict。

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
     "checked_at": "{_utc_now()}",
     "eval_md_path": "{eval_md}"
   }}
   EOF
   ```

3. 提交节点 verdict。通过时会自动释放下游 ready node；失败时只阻塞依赖它的下游：
   ```bash
   /Users/sihaoli/.solar/harness/solar-harness.sh graph-dispatch node-verdict --graph "{graph_path}" --node "{node_id}" --verdict pass --eval-json "{eval_json}"
   ```

   如果失败，改用：
   ```bash
   /Users/sihaoli/.solar/harness/solar-harness.sh graph-dispatch node-verdict --graph "{graph_path}" --node "{node_id}" --verdict fail --eval-json "{eval_json}" --reason "写清楚失败原因"
   ```
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
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
    except Exception:
        pass


def _send_to_pane(pane: str, instruction_file: Path, dry_run: bool,
                  *, sid: str = "", dispatch_id: str = "") -> bool:
    if dry_run:
        return True
    _set_pane_capability_title(pane, instruction_file)
    instruction_path = str(instruction_file.resolve())
    dispatch_keyword = instruction_file.name
    short_cmd = f"{_visibility_summary(instruction_file)['text']}; 读取并执行 {instruction_path}"
    _record_model_call("request", sid, pane, dispatch_id, instruction_file, status="tmux_submit_requested")
    processing_re = re.compile(
        r"Crafting|Cogitating|Orchestrating|Coalescing|Wandering|Sock-hopping|"
        r"Crunched|Puzzling|Cooking|Baked|Thinking|Considering|Newspapering|Read\(|"
        r"Reading|Bash\(|Edit\(|Write\(|⎿|✻|✶|✳|✽|⏺"
    )
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
            time.sleep(4.0)
            tail = subprocess.run(
                ["tmux", "capture-pane", "-pt", pane, "-S", "-80"],
                text=True,
                capture_output=True,
                timeout=2,
            ).stdout
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
                    tail = subprocess.run(
                        ["tmux", "capture-pane", "-pt", pane, "-S", "-80"],
                        text=True,
                        capture_output=True,
                        timeout=2,
                    ).stdout
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
    if current_status in {"passed", "failed", "skipped", "reviewing"}:
        return {
            "ok": True,
            "reason": "stale_graph_item_node_not_dispatchable",
            "node": node_id,
            "status": current_status,
            "dispatch_id": dispatch_id,
        }
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

    instruction_file = _dispatch_file(sid, node_id)
    text_payload = dict(payload, dispatch_id=dispatch_id, sprint_id=sid)
    # Research node branch: mark fan-out section isolation for R-prefixed nodes
    # from deepresearch DAG templates. No main-loop edits; this is a single
    # if-branch that enriches the payload before dispatch text generation.
    if node_id.startswith("R"):
        text_payload["research_node"] = True
        if node.get("fan_out_parent"):
            text_payload["section_isolation"] = True
            text_payload["section_id"] = node.get("section_id", "")
    instruction_file.parent.mkdir(parents=True, exist_ok=True)
    instruction_file.write_text(build_dispatch_text(text_payload, pane), encoding="utf-8")
    if not dry_run:
        _inject_dispatch_context(instruction_file, sid=sid, pane=pane, dispatch_id=dispatch_id)

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
        "bash", "python", "typescript", "docs", "testing",
        "frontend",
        "product", "planning",
        "architecture", "schema", "state-machine", "distributed-systems",
        "routing", "diagnostics", "evaluation",
        "browser.browse", "browser.qa", "code.review", "document.convert",
        "persona.agent", "multi_agent.research", "debug.systematic",
        "repair.pr-cot",
    ]
    worker_capabilities = [
        "bash", "python", "typescript", "docs", "testing",
        "frontend", "observability",
        "documentation", "schema", "state-machine", "storage", "sources",
        "browser.browse", "browser.qa", "code.review",
        "browser.mcp", "browser.automation", "browser.screenshot",
        "browser.localhost_test",
        "document.convert", "document.markdown_extract", "mcp.markitdown",
        "persona.agent", "agent.catalog", "specialist.routing",
        "multi_agent.research", "browser.agent_experiment", "document.toolkit",
        "agent.inventory", "command.catalog", "rules.catalog", "mcp.catalog",
        "repair.pr-cot", "failure.structured_repair", "routing.complexity_budget",
        "skill.methodology", "workflow.planning", "debug.systematic", "test.tdd",
        "architecture", "distributed-systems", "evaluation",
        "agents_sdk.design", "agents_sdk.guardrails", "agents_sdk.tracing",
        "agents_sdk.handoff_model",
        "ruflo.swarm", "ruflo.plugins", "ruflo.agent_catalog",
        "ruflo.memory", "ruflo.mcp", "ruflo.workflow_templates",
        "product.requirements", "research.scope_rewrite",
        "research.source_matrix", "research.evidence.extract",
        "research.claim.mine", "research.citation.verify",
        "research.report.compile",
    ]
    if dry_run:
        return [
            {"pane": f"{SESSION}:0.2", "models": _models_for_pane(f"{SESSION}:0.2"), "skills": worker_skills, "capabilities": worker_capabilities},
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
    for row in pane_rows:
        pane = row[0].strip()
        title = row[1].strip() if len(row) > 1 else ""
        # Only builder panes can receive DAG build nodes. Main PM/planner/evaluator
        # panes share the session prefix but must not be treated as builders.
        if pane != f"{SESSION}:0.2" and not pane.startswith("solar-harness-lab:"):
            continue
        models = _models_for_pane(pane, title)
        quota_exhausted: list[str] = []
        title_lower = title.lower()
        if "glm" in title_lower:
            if "quota:exhausted" in title_lower or "quota exhausted" in title_lower:
                quota_exhausted.extend(_model_alias_set("glm"))
        workers.append({
            "pane": pane,
            "models": models,
            "skills": worker_skills,
            "capabilities": worker_capabilities,
            "busy": bool(read_lease(pane)) or bool(_pane_health(pane).get("unavailable")),
            "title": title,
            "quota_exhausted": quota_exhausted,
            "health": _pane_health(pane),
        })
    return workers


def _discover_evaluators(dry_run: bool = False) -> list[dict[str, Any]]:
    if dry_run:
        return [{"pane": f"{SESSION}:0.3", "models": _models_for_pane(f"{SESSION}:0.3"), "skills": ["review", "testing", "bash"]}]
    # Graph node evaluation mutates graph verdict state. Keep it on the
    # evaluator persona; falling back to planner/builder panes causes wrong-role
    # dispatch and leaves the real review queue blocked.
    candidates = [
        f"{SESSION}:0.3",
    ]
    evaluators: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pane in candidates:
        if pane in seen:
            continue
        seen.add(pane)
        if _pane_exists(pane):
            evaluators.append({
                "pane": pane,
                "models": _models_for_pane(pane),
                "skills": ["review", "testing", "bash"],
                "busy": bool(read_lease(pane)),
            })
    return evaluators


def _node_eval_needed(graph: dict[str, Any], sid: str, node: dict[str, Any], force: bool = False) -> bool:
    node_id = str(node.get("id") or "")
    if not node_id:
        return False
    results = graph.get("node_results") or {}
    result = results.get(node_id) if isinstance(results, dict) else None
    if isinstance(result, dict) and str(result.get("status", "")).lower() in {"passed", "failed", "skipped"}:
        return False
    if _eval_json_file(sid, node_id).exists() and not force:
        return False
    if node.get("eval_dispatched_at") and not force:
        pane = str(node.get("eval_assigned_to") or "")
        dispatch_id = str(node.get("eval_dispatch_id") or "")
        lease = read_lease(pane) if pane else {}
        lease_matches = bool(
            lease
            and str(lease.get("sid") or lease.get("sprint_id") or "") == sid
            and str(lease.get("dispatch_id") or "") == dispatch_id
        )
        # If the graph says eval was dispatched but no eval artifact exists and
        # the evaluator lease is gone, the pane likely swallowed/stalled the
        # prompt. Treat it as retryable instead of permanently blocking.
        if lease_matches:
            return False
        node.pop("eval_assigned_to", None)
        node.pop("eval_dispatch_id", None)
        node.pop("eval_dispatched_at", None)
        node["eval_retry_reason"] = "eval_dispatched_without_artifact_or_active_lease"
    # Use graph_scheduler.node_status so node_results (the durable scheduler
    # result map) and inline node.status do not drift. A node can be reviewing
    # in node_results while its static node entry still says pending; relying
    # on node.status alone makes evaluator dispatch skip real handoffs forever.
    status = node_status(graph, node_id)
    if status in {"passed", "failed", "skipped"}:
        return False
    return _handoff_file(sid, node_id).exists() and status in {"reviewing", "dispatched", "in_progress", "running", ""}


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

    for node in graph.get("nodes", []):
        if max_items and len(dispatched) >= max_items:
            break
        node_id = str(node.get("id") or "")
        if not _node_eval_needed(graph, sid, node, force=force):
            continue
        evaluator = _first_available_evaluator(dry_run)
        if not evaluator:
            skipped.append({"node": node_id, "reason": "no_available_evaluator"})
            break
        pane = str(evaluator["pane"])
        dispatch_id = f"graph-eval-{sid}-{node_id}-{_utc_now().replace(':', '').replace('-', '')}"
        lease_result = _ensure_lease(pane, sid, dispatch_id, ttl, dry_run)
        if not lease_result.get("acquired"):
            skipped.append({
                "node": node_id,
                "pane": pane,
                "reason": lease_result.get("reason", "lease_failed"),
                "lease": lease_result,
            })
            continue

        instruction_file = _eval_dispatch_file(sid, node_id)
        instruction_file.parent.mkdir(parents=True, exist_ok=True)
        instruction_file.write_text(
            build_eval_dispatch_text(graph, graph_path, node, pane, dispatch_id),
            encoding="utf-8",
        )
        _inject_dispatch_context(instruction_file, sid=sid, pane=pane, dispatch_id=dispatch_id)
        sent = _send_to_pane(pane, instruction_file, dry_run, sid=sid, dispatch_id=dispatch_id)
        if not sent:
            if not dry_run:
                release_lease(pane, dispatch_id, "graph_eval_dispatch_send_failed")
            # Clear eval assignment so the node can be retried on next cycle.
            node.pop("eval_assigned_to", None)
            node.pop("eval_dispatch_id", None)
            node.pop("eval_dispatched_at", None)
            skipped.append({"node": node_id, "pane": pane, "reason": "send_failed"})
            continue

        if not dry_run:
            _write_submit_ack(sid, node_id, pane, dispatch_id)
        node["status"] = "reviewing"
        node["eval_assigned_to"] = pane
        node["eval_dispatch_id"] = dispatch_id
        node["eval_dispatched_at"] = _utc_now()
        dispatched.append({
            "node": node_id,
            "pane": pane,
            "dispatch_id": dispatch_id,
            "instruction_file": str(instruction_file),
        })

    save_graph(graph_path, graph)
    return {
        "ok": not skipped,
        "sprint_id": sid,
        "dispatched": dispatched,
        "skipped": skipped,
    }


def dispatch_ready(graph_path: str, dry_run: bool = False, ttl: int = 900) -> dict[str, Any]:
    if _no_dispatch_enabled() and not dry_run:
        return {"ok": False, "reason": "no_dispatch_flag", "graph": graph_path, "enqueue": {}, "drain": {}}
    graph = load_graph(graph_path)
    sid = graph.get("sprint_id") or Path(graph_path).stem.replace(".task_graph", "")
    enqueue_result = enqueue_ready(
        graph,
        graph_path,
        _discover_workers(dry_run),
        max_parallel=8,
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
    return {"ok": enqueue_result.get("ok") and drain_result.get("ok"), "enqueue": enqueue_result, "drain": drain_result}


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

    note_parts = []
    if reason:
        note_parts.append(reason)
    if eval_json:
        note_parts.append(f"eval_json={eval_json}")
    eval_pane = str(node.get("eval_assigned_to") or "")
    eval_dispatch_id = str(node.get("eval_dispatch_id") or "")
    parent = mark_node_result(graph, node_id, status, gate_status=status, note="; ".join(note_parts) or None)
    node["status"] = status
    node["updated_at"] = _utc_now()
    if eval_json:
        node["eval_json"] = eval_json
    effect_result: dict[str, Any] = {}
    if scan_effect is not None:
        try:
            effect_result = scan_effect(
                _dispatch_file(sid, node_id),
                handoff_file=_handoff_file(sid, node_id),
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
    node.pop("eval_assigned_to", None)
    node.pop("eval_dispatch_id", None)
    save_graph(graph_path, graph)

    lease_released = False
    if not dry_run and eval_pane and eval_dispatch_id:
        lease_released = bool(release_lease(eval_pane, eval_dispatch_id, f"node_{status}").get("released"))

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
        "eval_lease_released": lease_released,
        "parent_status_updated": parent_status_updated,
        "capability_effect": effect_result,
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
        result = dispatch_ready(args.graph, args.dry_run, args.ttl)
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
