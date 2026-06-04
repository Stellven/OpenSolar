#!/usr/bin/env python3
"""Browser-agent-backed ChatGPT requirement writer operator.

This operator specializes in turning the user's original requirement into a
chaptered, compiler-friendly requirement design using ChatGPT Thinking High.
It must prefer raw/original requirement sources over upstream rewritten input.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from chatgpt_report_operator import (  # type: ignore
    DEFAULT_PROJECT_NAME,
    _run_via_session_control,
    _session_control_enabled,
    apply_profile_policy,
    run_wrapper_process,
    wrapper_cmd,
)


RAW_REQUIREMENT_ENV_KEYS = (
    "SOLAR_RAW_REQUIREMENT",
    "BROWSER_AGENT_RAW_REQUIREMENT",
    "BROWSER_AGENT_USER_RAW_REQUIREMENT",
    "RAW_REQUIREMENT",
    "RAW_USER_REQUIREMENT",
)
RAW_REQUIREMENT_FILE_ENV_KEYS = (
    "SOLAR_RAW_REQUIREMENT_FILE",
    "BROWSER_AGENT_RAW_REQUIREMENT_FILE",
    "RAW_REQUIREMENT_FILE",
)
RAW_INTENT_FILE_ENV_KEYS = (
    "SOLAR_RAW_INTENT_FILE",
    "BROWSER_AGENT_RAW_INTENT_FILE",
    "RAW_INTENT_FILE",
)


def _slug(value: str, limit: int = 96) -> str:
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip()).strip("-")
    return (text or "default")[:limit]


def _default_session_lineage(*, purpose: str, request_dir: str) -> str:
    clean_purpose = str(purpose or "").strip()
    if clean_purpose:
        return f"gpt-requirement-writer:{_slug(clean_purpose)}"
    request_name = Path(str(request_dir or "requirement-design")).name
    return f"gpt-requirement-writer:{_slug(request_name)}"


def _read_file_text(path_text: str, *, source_label: str) -> tuple[str, str]:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise RuntimeError(f"chatgpt_requirement_writer_operator: missing {source_label}={path}")
    return path.read_text(encoding="utf-8").strip(), str(path)


def _extract_raw_requirement_from_intent(path_text: str, *, source_label: str) -> tuple[str, str]:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise RuntimeError(f"chatgpt_requirement_writer_operator: missing {source_label}={path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"chatgpt_requirement_writer_operator: invalid {source_label}={path}: {type(exc).__name__}: {exc}"
        ) from exc
    if isinstance(payload, dict):
        raw = payload.get("raw")
        if isinstance(raw, dict):
            text = str(raw.get("text") or "").strip()
            if text:
                return text, str(path)
        text = str(payload.get("raw_requirement") or "").strip()
        if text:
            return text, str(path)
    raise RuntimeError(f"chatgpt_requirement_writer_operator: no raw requirement found in {source_label}={path}")


def resolve_requirement_source(stdin_text: str) -> tuple[str, str, str]:
    for key in RAW_REQUIREMENT_ENV_KEYS:
        value = str(os.environ.get(key) or "").strip()
        if value:
            return value, f"env:{key}", ""
    for key in RAW_REQUIREMENT_FILE_ENV_KEYS:
        value = str(os.environ.get(key) or "").strip()
        if value:
            text, path = _read_file_text(value, source_label=key)
            if text:
                return text, f"file:{key}", path
    for key in RAW_INTENT_FILE_ENV_KEYS:
        value = str(os.environ.get(key) or "").strip()
        if value:
            text, path = _extract_raw_requirement_from_intent(value, source_label=key)
            if text:
                return text, f"raw_intent:{key}", path
    clean_stdin = stdin_text.strip()
    if clean_stdin:
        return clean_stdin, "stdin", ""
    raise RuntimeError("chatgpt_requirement_writer_operator: no requirement input available")


def build_prompt(raw_requirement: str, *, expected: str, purpose: str, source_tag: str) -> str:
    return "\n\n".join(
        [
            "# GPTRequirementWriter 固化执行协议",
            "- operator_kind: requirement_writer",
            f"- purpose: {purpose or 'N/A'}",
            f"- expected_output: {expected}",
            "- model_mode: thinking",
            "- reasoning_effort: high",
            f"- source_priority: {source_tag}",
            "",
            "## 角色定义",
            "你是 GPTRequirementWriter。你的任务是把用户原始需求展开成一份完整、详细、系统、章节化的需求设计稿，供后续 requirement compiler 按章节拆分编译。",
            "",
            "## 强约束",
            "1. 只能以用户原始需求为中心展开；不要把上游算子的改写稿、摘要稿、路线建议稿当成用户原话。",
            "2. 如果原始需求信息不足，必须明确写成“假设 / 待确认 / 风险”，不能擅自补成既定事实。",
            "3. 输出必须是章节化 Markdown，并使用稳定标题层级，便于后续拆分。",
            "4. 必须同时覆盖：背景与目标、范围边界、角色与场景、功能需求、非功能需求、数据与接口、约束依赖、风险与待确认、验收标准、实施建议。",
            "5. 每章先给章节目标，再给细项；功能需求要尽量编号化，便于编译器拆段。",
            "6. 不要输出内部流水线字段、operator 元信息、raw id 或调度说明。",
            "",
            "## 推荐章节骨架",
            "1. 需求概述与业务目标",
            "2. 问题定义与范围边界",
            "3. 干系人与目标用户",
            "4. 关键使用场景与用户旅程",
            "5. 功能需求清单",
            "6. 非功能需求",
            "7. 数据模型、接口与外部依赖",
            "8. 约束、风险、失败模式与安全边界",
            "9. 验收标准与交付定义",
            "10. 待确认问题与建议决策",
            "",
            "## 用户原始需求",
            raw_requirement.strip(),
        ]
    )


def main() -> int:
    stdin_text = sys.stdin.read()
    action = (os.environ.get("CHATGPT_REQUIREMENT_WRITER_ACTION") or "run").strip().lower()
    if action not in {"run", "submit", "poll", "collect"}:
        print(
            f"chatgpt_requirement_writer_operator: invalid CHATGPT_REQUIREMENT_WRITER_ACTION={action}",
            file=sys.stderr,
        )
        return 2
    expected = (os.environ.get("BROWSER_AGENT_EXPECTED_OUTPUT") or "markdown").strip().lower()
    purpose = (os.environ.get("BROWSER_AGENT_PURPOSE") or "requirement-design").strip()
    if action in {"poll", "collect"}:
        raw_requirement, source_tag, source_path = "", "", ""
    else:
        try:
            raw_requirement, source_tag, source_path = resolve_requirement_source(stdin_text)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    prompt = build_prompt(raw_requirement, expected=expected, purpose=purpose, source_tag=source_tag)
    cmd = wrapper_cmd()
    if not _session_control_enabled() and not cmd:
        print("chatgpt_requirement_writer_operator: Browser Agent ChatGPT wrapper not configured", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("BROWSER_AGENT_HEADLESS", "true")
    env.setdefault("BROWSER_AGENT_SESSION_REUSE", "true")
    env.setdefault("SOLAR_BROWSER_SESSION_REUSE", env["BROWSER_AGENT_SESSION_REUSE"])
    request_dir = str(env.get("BROWSER_AGENT_REQUEST_DIR") or "").strip()
    default_lineage = _default_session_lineage(purpose=purpose, request_dir=request_dir)
    env.setdefault("BROWSER_AGENT_SESSION_LINEAGE", default_lineage)
    env.setdefault("SOLAR_BROWSER_SESSION_LINEAGE", env["BROWSER_AGENT_SESSION_LINEAGE"])
    env.update(
        {
            "CHATGPT_MODEL": str(
                env.get("CHATGPT_REQUIREMENT_WRITER_MODEL")
                or env.get("CHATGPT_MODEL")
                or "chatgpt-5.5"
            ),
            "CHATGPT_REASONING_EFFORT": "high",
            "BROWSER_AGENT_EXPECTED_OUTPUT": expected,
            "BROWSER_AGENT_CHATGPT_MODEL_MODE": "thinking",
            "BROWSER_AGENT_CHATGPT_TOOL_MODE": env.get("BROWSER_AGENT_CHATGPT_TOOL_MODE") or "none",
            "BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE": "true",
            "BROWSER_AGENT_CHATGPT_PROJECT_NAME": env.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME") or DEFAULT_PROJECT_NAME,
            "BROWSER_AGENT_CHATGPT_OPEN_PROJECT_FIRST": env.get("BROWSER_AGENT_CHATGPT_OPEN_PROJECT_FIRST") or "true",
            "BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT": env.get("BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT") or "true",
            "BROWSER_AGENT_CHATGPT_ACTION": action,
        }
    )
    try:
        policy_meta = apply_profile_policy(env, purpose=purpose)
    except RuntimeError as exc:
        print(f"chatgpt_requirement_writer_operator: {exc}", file=sys.stderr)
        return 2

    request_dir = env.get("BROWSER_AGENT_REQUEST_DIR")
    if request_dir:
        request_path = Path(request_dir).expanduser()
        request_path.mkdir(parents=True, exist_ok=True)
        upstream_input_ignored = bool(stdin_text.strip()) and source_tag != "stdin" and stdin_text.strip() != raw_requirement.strip()
        (request_path / "requirement-writer-request.json").write_text(
            json.dumps(
                {
                    "operator_kind": "GPTRequirementWriter",
                    "display_name": "GPT Requirement Writer",
                    "expected_output": expected,
                    "purpose": purpose,
                    "model": env.get("CHATGPT_MODEL") or "",
                    "model_mode": env.get("BROWSER_AGENT_CHATGPT_MODEL_MODE") or "thinking",
                    "reasoning_effort": env.get("CHATGPT_REASONING_EFFORT") or "high",
                    "tool_mode": env.get("BROWSER_AGENT_CHATGPT_TOOL_MODE") or "none",
                    "project_name": env.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME") or DEFAULT_PROJECT_NAME,
                    "raw_requirement_source": source_tag,
                    "raw_requirement_source_path": source_path,
                    "raw_requirement_sha256": hashlib.sha256(raw_requirement.encode("utf-8")).hexdigest(),
                    "raw_requirement_length": len(raw_requirement),
                    "upstream_input_present": bool(stdin_text.strip()),
                    "upstream_input_ignored": upstream_input_ignored,
                    "profile_directory": env.get("BROWSER_AGENT_PROFILE_DIRECTORY") or "",
                    "target_account_email": env.get("BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL")
                    or env.get("BROWSER_AGENT_TARGET_ACCOUNT_EMAIL")
                    or "",
                    "profile_policy": policy_meta,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    timeout = int(env.get("CHATGPT_REQUIREMENT_WRITER_TIMEOUT") or env.get("BROWSER_AGENT_CHATGPT_TIMEOUT") or "2400")
    if _session_control_enabled():
        returncode, raw_output = _run_via_session_control(prompt=prompt, env=env, timeout=timeout, action=action)
    else:
        returncode, raw_output = run_wrapper_process(cmd, prompt=prompt, env=env, timeout=timeout)
    output = (raw_output or "").strip()
    if returncode != 0:
        print(output, file=sys.stderr)
        return returncode
    if not request_dir:
        print("chatgpt_requirement_writer_operator: missing BROWSER_AGENT_REQUEST_DIR for UI mode proof", file=sys.stderr)
        return 1
    proof_path = Path(request_dir).expanduser() / "chatgpt-mode-state.json"
    post_submit_proof_path = Path(request_dir).expanduser() / "chatgpt-mode-post-submit-state.json"
    if not proof_path.exists():
        print(
            "chatgpt_requirement_writer_operator: did not produce chatgpt-mode-state.json; "
            "normal ChatGPT output is not accepted as Thinking High",
            file=sys.stderr,
        )
        return 1
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"chatgpt_requirement_writer_operator: invalid chatgpt-mode-state.json: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    if not proof.get("ok"):
        if post_submit_proof_path.exists():
            try:
                post_submit_proof = json.loads(post_submit_proof_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(
                    "chatgpt_requirement_writer_operator: invalid chatgpt-mode-post-submit-state.json: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                return 1
            if not post_submit_proof.get("ok"):
                print(
                    "chatgpt_requirement_writer_operator: required ChatGPT UI mode not confirmed: "
                    + json.dumps(post_submit_proof, ensure_ascii=False),
                    file=sys.stderr,
                )
                return 1
        else:
            print(
                "chatgpt_requirement_writer_operator: required ChatGPT UI mode not confirmed: "
                + json.dumps(proof, ensure_ascii=False),
                file=sys.stderr,
            )
            return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
