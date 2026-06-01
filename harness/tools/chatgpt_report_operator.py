#!/usr/bin/env python3
"""Specialized Browser Agent ChatGPT report operators.

This stdin/stdout adapter exposes three logical report operators over the same
browser automation backend:

- ChatGPT Report Planner
- ChatGPT Report Chapter Writer
- ChatGPT Report Deep Writer

Secrets stay outside the repository. Account hints, profile paths and wrapper
commands are read from environment variables only.
"""
from __future__ import annotations

import json
import os
import signal
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_NAME = "杂项"
DEFAULT_WRAPPER = ROOT / "scripts" / "browser_agent_chatgpt_wrapper.py"
DEFAULT_BROWSER_USE_PYTHON = Path.home() / ".claude" / "mcp-servers" / "browser-use" / ".venv" / "bin" / "python"


def infer_kind(purpose: str, explicit: str = "") -> str:
    value = explicit.strip().lower().replace("-", "_")
    if value in {"planner", "chapter_writer", "deep_writer"}:
        return value
    lowered = purpose.lower()
    if "deep" in lowered or "research" in lowered:
        return "deep_writer"
    if "plan" in lowered or "grouping" in lowered:
        return "planner"
    return "chapter_writer"


def wrapper_cmd() -> list[str]:
    raw = os.environ.get("BROWSER_AGENT_CHATGPT_WRAPPER_CMD", "").strip()
    if raw:
        return shlex.split(raw)
    if DEFAULT_WRAPPER.exists() and DEFAULT_BROWSER_USE_PYTHON.exists():
        return [str(DEFAULT_BROWSER_USE_PYTHON), str(DEFAULT_WRAPPER)]
    return []


def stage_policy(kind: str, expected: str) -> dict[str, Any]:
    if kind == "planner":
        return {
            "display_name": "ChatGPT Report Planner",
            "model_mode": "thinking",
            "reasoning_effort": "high",
            "tool_mode": "none",
            "model": os.environ.get("CHATGPT_REPORT_PLANNER_MODEL") or os.environ.get("CHATGPT_MODEL") or "chatgpt-5.5",
            "instruction": (
                "你是 ChatGPT Report Planner。你的任务不是写正文，而是输出可执行的报告规划。"
                "必须规划：报告拆成几章、每章几节、每节写什么、素材约束、风格约束、证据使用规则、"
                "禁止事项、最终输出格式。若 expected_output=json，必须只输出 JSON。"
            ),
        }
    if kind == "deep_writer":
        return {
            "display_name": "ChatGPT Report Deep Writer",
            "model_mode": "pro",
            "reasoning_effort": "deep_research",
            "tool_mode": "deep_research",
            "model": os.environ.get("CHATGPT_REPORT_DEEP_MODEL") or os.environ.get("CHATGPT_MODEL") or "chatgpt-pro",
            "instruction": (
                "你是 ChatGPT Report Deep Writer。你必须使用 Pro / Deep Research 模式处理长程研究写作。"
                "如果界面提出研究澄清问题，应选择继续研究、扩大证据覆盖、保持技术分析深度，"
                "不要请求人工介入。输出必须是可直接发布的深度研究章节或报告。"
            ),
        }
    return {
        "display_name": "ChatGPT Report Chapter Writer",
        "model_mode": "thinking",
        "reasoning_effort": "high",
        "tool_mode": "none",
        "model": os.environ.get("CHATGPT_REPORT_CHAPTER_MODEL") or os.environ.get("CHATGPT_MODEL") or "chatgpt-5.5",
        "instruction": (
            "你是 ChatGPT Report Chapter Writer。你只写当前指定章节，不重写整份报告规划。"
            "必须严格遵守 Planner 给出的章节目标、风格、约束和素材边界；必须把素材转成面向读者的判断，"
            "不要输出内部处理字段、video_id、transcript_status、raw id。"
        ),
    }


def build_prompt(user_prompt: str, *, kind: str, expected: str, purpose: str) -> str:
    policy = stage_policy(kind, expected)
    return "\n\n".join(
        [
            f"# {policy['display_name']} 固化执行协议",
            f"- operator_kind: {kind}",
            f"- purpose: {purpose or 'N/A'}",
            f"- expected_output: {expected}",
            f"- model_mode: {policy['model_mode']}",
            f"- reasoning_effort: {policy['reasoning_effort']}",
            "",
            "## 必须遵守",
            policy["instruction"],
            "所有结论必须来自用户输入或上游算子提供的素材；不能编造素材；不能暴露内部流水线字段。",
            "如果信息不足，要明确写成限制或待验证事项，而不是补故事。",
            "",
            "## 用户/上游输入",
            user_prompt.strip(),
        ]
    )


def run_wrapper_process(cmd: list[str], *, prompt: str, env: dict[str, str], timeout: int) -> tuple[int, str]:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, _ = proc.communicate(prompt, timeout=timeout)
        return proc.returncode or 0, stdout or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            proc.terminate()
        try:
            stdout, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()
            stdout, _ = proc.communicate()
        return 124, (stdout or "") + f"\nchatgpt_report_operator: wrapper timed out after {timeout}s"


def main() -> int:
    user_prompt = sys.stdin.read()
    action = (os.environ.get("CHATGPT_REPORT_ACTION") or "run").strip().lower()
    if action not in {"run", "submit", "poll", "collect"}:
        print(f"chatgpt_report_operator: invalid CHATGPT_REPORT_ACTION={action}", file=sys.stderr)
        return 2
    if not user_prompt.strip() and action not in {"poll", "collect"}:
        print("chatgpt_report_operator: stdin prompt is empty", file=sys.stderr)
        return 2
    expected = (os.environ.get("BROWSER_AGENT_EXPECTED_OUTPUT") or "markdown").strip().lower()
    purpose = (os.environ.get("BROWSER_AGENT_PURPOSE") or "").strip()
    kind = infer_kind(purpose, os.environ.get("CHATGPT_REPORT_OPERATOR_KIND", ""))
    policy = stage_policy(kind, expected)
    prompt = build_prompt(user_prompt, kind=kind, expected=expected, purpose=purpose) if user_prompt.strip() else "poll/collect"
    cmd = wrapper_cmd()
    if not cmd:
        print("chatgpt_report_operator: Browser Agent ChatGPT wrapper not configured", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.update(
        {
            "CHATGPT_MODEL": str(policy["model"]),
            "CHATGPT_REASONING_EFFORT": str(policy["reasoning_effort"]),
            "BROWSER_AGENT_EXPECTED_OUTPUT": expected,
            "BROWSER_AGENT_CHATGPT_MODEL_MODE": str(policy["model_mode"]),
            "BROWSER_AGENT_CHATGPT_TOOL_MODE": str(policy["tool_mode"]),
            "BROWSER_AGENT_CHATGPT_PROJECT_NAME": env.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME") or DEFAULT_PROJECT_NAME,
            "BROWSER_AGENT_CHATGPT_OPEN_PROJECT_FIRST": env.get("BROWSER_AGENT_CHATGPT_OPEN_PROJECT_FIRST") or "true",
            "BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT": env.get("BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT") or "true",
            "BROWSER_AGENT_CHATGPT_ACTION": action,
        }
    )
    if kind == "deep_writer":
        env["BROWSER_AGENT_CHATGPT_REQUIRE_DEEP_RESEARCH"] = (
            env.get("BROWSER_AGENT_CHATGPT_REQUIRE_DEEP_RESEARCH") or "true"
        )
    else:
        env["BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE"] = (
            env.get("BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE") or "true"
        )
    request_dir = env.get("BROWSER_AGENT_REQUEST_DIR")
    if request_dir:
        Path(request_dir).expanduser().mkdir(parents=True, exist_ok=True)
        (Path(request_dir).expanduser() / "report-operator-request.json").write_text(
            json.dumps(
                {
                    "operator_kind": kind,
                    "display_name": policy["display_name"],
                    "expected_output": expected,
                    "purpose": purpose,
                    "model": policy["model"],
                    "model_mode": policy["model_mode"],
                    "reasoning_effort": policy["reasoning_effort"],
                    "tool_mode": policy["tool_mode"],
                    "project_name": env.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME") or DEFAULT_PROJECT_NAME,
                    "account_email_hint_present": bool(env.get("BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL")),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if action in {"poll", "collect"} and not env.get("BROWSER_AGENT_CHATGPT_CONVERSATION_URL"):
            submitted_path = Path(request_dir).expanduser() / "submitted-run.json"
            if submitted_path.exists():
                try:
                    submitted = json.loads(submitted_path.read_text(encoding="utf-8"))
                    if submitted.get("url"):
                        env["BROWSER_AGENT_CHATGPT_CONVERSATION_URL"] = str(submitted["url"])
                except Exception:
                    pass

    timeout = int(env.get("BROWSER_AGENT_CHATGPT_TIMEOUT") or ("7200" if kind == "deep_writer" else "1800"))
    returncode, raw_output = run_wrapper_process(cmd, prompt=prompt, env=env, timeout=timeout)
    output = (raw_output or "").strip()
    if returncode != 0:
        print(output, file=sys.stderr)
        return returncode
    if kind == "deep_writer":
        if not request_dir:
            print("chatgpt_report_operator: deep_writer missing BROWSER_AGENT_REQUEST_DIR for Deep Research proof", file=sys.stderr)
            return 1
        proof_path = Path(request_dir).expanduser() / "deep-research-state.json"
        if not proof_path.exists():
            print(
                "chatgpt_report_operator: deep_writer did not produce deep-research-state.json; "
                "normal chat output is not accepted as Deep Research",
                file=sys.stderr,
            )
            return 1
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"chatgpt_report_operator: invalid deep-research-state.json: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if not proof.get("ok"):
            print(
                "chatgpt_report_operator: Deep Research mode not confirmed: "
                + json.dumps(proof, ensure_ascii=False),
                file=sys.stderr,
            )
            return 1
    else:
        if not request_dir:
            print("chatgpt_report_operator: missing BROWSER_AGENT_REQUEST_DIR for UI mode proof", file=sys.stderr)
            return 1
        request_path = Path(request_dir).expanduser()
        proof_path = request_path / "chatgpt-mode-state.json"
        post_submit_proof_path = request_path / "chatgpt-mode-post-submit-state.json"
        if not proof_path.exists():
            print(
                "chatgpt_report_operator: planner/chapter did not produce chatgpt-mode-state.json; "
                "normal ChatGPT output is not accepted as Thinking High",
                file=sys.stderr,
            )
            return 1
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"chatgpt_report_operator: invalid chatgpt-mode-state.json: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if not proof.get("ok"):
            if post_submit_proof_path.exists():
                try:
                    post_submit_proof = json.loads(post_submit_proof_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    print(f"chatgpt_report_operator: invalid chatgpt-mode-post-submit-state.json: {type(exc).__name__}: {exc}", file=sys.stderr)
                    return 1
                if post_submit_proof.get("ok"):
                    proof = post_submit_proof
                else:
                    print(
                        "chatgpt_report_operator: required ChatGPT UI mode not confirmed: "
                        + json.dumps(post_submit_proof, ensure_ascii=False),
                        file=sys.stderr,
                    )
                    return 1
            else:
                print(
                    "chatgpt_report_operator: required ChatGPT UI mode not confirmed: "
                    + json.dumps(proof, ensure_ascii=False),
                    file=sys.stderr,
                )
                return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
