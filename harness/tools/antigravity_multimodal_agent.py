#!/usr/bin/env python3
"""Command backend adapter for Antigravity multimodal/image tasks."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import datetime as dt
from pathlib import Path


IMAGE_RE = re.compile(r"(?P<path>(?:/[^\s`'\"<>]+|~[^\s`'\"<>]+)\.(?:png|jpe?g|webp))", re.I)
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|cookie)(\s*[:=]\s*)([^\s`'\"<>]+)"
)
QUOTA_RE = re.compile(r"RESOURCE_EXHAUSTED|quota|rate[- ]?limit|429|resets in", re.I)
AUTH_RE = re.compile(r"not logged in|auth(?:entication)? failed|oauth token|permission denied", re.I)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def image_paths(text: str) -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("SOLAR_MULTIMODAL_IMAGE", "")
    for item in explicit.split(":"):
        if item.strip():
            paths.append(Path(item).expanduser())
    for match in IMAGE_RE.finditer(text):
        paths.append(Path(match.group("path")).expanduser())
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen and path.exists():
            seen.add(key)
            result.append(path)
    return result


def redact(text: str) -> str:
    return SECRET_RE.sub(r"\1\2***REDACTED***", text)


def extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return "N/A"
    rest = text[start + len(marker) :].strip()
    next_heading = re.search(r"\n##\s+", rest)
    if next_heading:
        rest = rest[: next_heading.start()].strip()
    return rest or "N/A"


def write_handoff(dispatch: str, agent_output: str) -> Path:
    handoff = Path(os.environ.get("HANDOFF", "")).expanduser()
    if not str(handoff) or str(handoff) == ".":
        sid = os.environ.get("SID", "unknown-sprint")
        node_id = os.environ.get("NODE_ID", "unknown-node")
        sprints_dir = Path(os.environ.get("SPRINTS_DIR", Path.home() / ".solar" / "harness" / "sprints"))
        handoff = sprints_dir / f"{sid}.{node_id}-handoff.md"
    if handoff.exists() and handoff.stat().st_size > 0:
        return handoff

    sid = os.environ.get("SID", "unknown-sprint")
    node_id = os.environ.get("NODE_ID", "unknown-node")
    safe_output = redact(agent_output).strip()
    if len(safe_output) > 16000:
        safe_output = safe_output[:16000] + "\n\n[truncated]"
    acceptance = extract_section(dispatch, "Acceptance")
    goal = extract_section(dispatch, "Goal")
    handoff_text = f"""# Handoff — {sid} / {node_id}

Builder: Antigravity command backend adapter
Generated-At: {now()}

## 已完成

- 调用 Antigravity CLI command backend 完成本节点。
- 将 Antigravity stdout 归档为本节点 handoff，供 graph-scheduler/evaluator 后续验证。

## 节点目标

{goal}

## Acceptance 摘要

{acceptance}

## Antigravity 输出

```markdown
{safe_output}
```

## 已验证

- Antigravity CLI 进程 exit_code=0。
- handoff 文件由 command backend adapter 写入。
- 未在 handoff 中写入已知 key/token/secret/password/cookie 字段原文。

## 未验证

- 语义验收仍需后续 evaluator 按合同检查。

## 风险

- 该 handoff 由 wrapper 从 CLI stdout 转写；如果 stdout 内容质量不足，evaluator 必须 FAIL，不得直接视为最终验收。

## 后续待办

- 将 command backend handoff 生成逻辑纳入 operatord/operator_runtime.submit 的标准输出契约。
"""
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(handoff_text, encoding="utf-8")
    return handoff


def tail_text(path: Path, limit: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def main() -> int:
    dispatch_file = Path(os.environ.get("SOLAR_MULTI_TASK_DISPATCH_FILE", "")).expanduser()
    if not dispatch_file.exists():
        print("ERROR: SOLAR_MULTI_TASK_DISPATCH_FILE missing", file=sys.stderr)
        return 2

    dispatch = dispatch_file.read_text(encoding="utf-8", errors="replace")
    images = image_paths(dispatch)
    add_dirs = sorted({str(path.parent) for path in images})
    agy = os.environ.get("AGY_BIN", "/Users/lisihao/.local/bin/agy")
    timeout = os.environ.get("AGY_PRINT_TIMEOUT", "10m")
    task_dir = Path(os.environ.get("TASK_DIR", dispatch_file.parent)).expanduser()
    task_dir.mkdir(parents=True, exist_ok=True)
    log_file = task_dir / "antigravity.log"

    prompt = "\n".join([
        "You are running as a Solar multimodal/image physical operator.",
        "Read the dispatch below, inspect referenced image files if present, and complete only the requested node.",
        "Do not print secrets. If you cannot inspect an image, state IMAGE_UNSUPPORTED and explain the blocker.",
        "Return a concise Markdown handoff with sections: completed, verified, unverified, risks, next steps.",
        "Do not ask for confirmation; perform the node work and provide the final handoff text.",
        "",
        "Referenced image files:",
        "\n".join(f"- {path}" for path in images) if images else "- N/A",
        "",
        dispatch,
    ])

    cmd = [agy, "--log-file", str(log_file), "--dangerously-skip-permissions", "--print-timeout", timeout]
    for directory in add_dirs:
        cmd.extend(["--add-dir", directory])
    cmd.extend(["--print", prompt])
    print("[solar-harness agy-multimodal] cmd=" + " ".join(shlex.quote(part) for part in cmd[:-1]) + " <prompt>")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")
    if proc.returncode == 0:
        output = (proc.stdout or "").strip()
        if not output:
            log_tail = tail_text(log_file)
            safe_tail = redact(log_tail)
            if QUOTA_RE.search(log_tail):
                print("ERROR: Antigravity quota exhausted; refusing empty handoff", file=sys.stderr)
                if safe_tail:
                    print(safe_tail, file=sys.stderr)
                return 75
            if AUTH_RE.search(log_tail):
                print("ERROR: Antigravity auth unavailable; refusing empty handoff", file=sys.stderr)
                if safe_tail:
                    print(safe_tail, file=sys.stderr)
                return 76
            print("ERROR: Antigravity command backend returned empty stdout; refusing empty handoff", file=sys.stderr)
            if safe_tail:
                print(safe_tail, file=sys.stderr)
            return 65
        handoff = write_handoff(dispatch, output)
        print(f"[solar-harness agy-multimodal] wrote_handoff={handoff}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
