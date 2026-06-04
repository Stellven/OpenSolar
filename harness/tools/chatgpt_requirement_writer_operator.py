#!/usr/bin/env python3
"""Browser-agent-backed ChatGPT requirement writer operator.

This is the normal requirement-pipeline enhancer.  It turns a raw user
requirement into a chaptered requirement design using the existing ChatGPT
browser-agent wrapper.  DeepDive intentionally does not use this module.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from chatgpt_report_operator import apply_profile_policy, run_wrapper_process, wrapper_cmd  # type: ignore


RAW_REQUIREMENT_ENV_KEYS = (
    "SOLAR_RAW_REQUIREMENT",
    "BROWSER_AGENT_RAW_REQUIREMENT",
    "RAW_USER_REQUIREMENT",
)
RAW_REQUIREMENT_FILE_ENV_KEYS = (
    "SOLAR_RAW_REQUIREMENT_FILE",
    "BROWSER_AGENT_RAW_REQUIREMENT_FILE",
)
RAW_INTENT_FILE_ENV_KEYS = (
    "SOLAR_RAW_INTENT_FILE",
    "BROWSER_AGENT_RAW_INTENT_FILE",
)


def _read_file_text(path_text: str, *, source_label: str) -> tuple[str, str]:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise RuntimeError(f"chatgpt_requirement_writer_operator: missing {source_label}={path}")
    return path.read_text(encoding="utf-8").strip(), str(path)


def _extract_raw_requirement_from_intent(path_text: str, *, source_label: str) -> tuple[str, str]:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise RuntimeError(f"chatgpt_requirement_writer_operator: missing {source_label}={path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
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
    clean = stdin_text.strip()
    if clean:
        return clean, "stdin", ""
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
            "你是 GPTRequirementWriter。你的任务是把用户原始需求展开成完整、系统、章节化的需求设计稿，供后续 requirement compiler 拆分编译。",
            "",
            "## 强约束",
            "1. 只能以用户原始需求为中心展开；不要把上游摘要或路线建议当成用户原话。",
            "2. 信息不足时写成“假设 / 待确认 / 风险”，不能擅自补成事实。",
            "3. 输出必须是章节化 Markdown，标题层级稳定，便于后续拆分。",
            "4. 必须覆盖：背景目标、范围边界、角色场景、功能需求、非功能需求、数据接口、约束依赖、风险、验收标准、实施建议。",
            "5. 功能需求尽量编号化，便于编译器拆段。",
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
        print(f"chatgpt_requirement_writer_operator: invalid action={action}", file=sys.stderr)
        return 2
    expected = (os.environ.get("BROWSER_AGENT_EXPECTED_OUTPUT") or "markdown").strip().lower()
    purpose = (os.environ.get("BROWSER_AGENT_PURPOSE") or "requirement-design").strip()
    if action in {"poll", "collect"}:
        raw_requirement, source_tag = "", "poll_or_collect"
    else:
        try:
            raw_requirement, source_tag, _source_path = resolve_requirement_source(stdin_text)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    prompt = build_prompt(raw_requirement, expected=expected, purpose=purpose, source_tag=source_tag)
    cmd = wrapper_cmd()
    if not cmd:
        print("chatgpt_requirement_writer_operator: Browser Agent ChatGPT wrapper not configured", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.update(
        {
            "CHATGPT_REPORT_OPERATOR_KIND": "chapter_writer",
            "CHATGPT_REPORT_ACTION": action,
            "CHATGPT_MODEL": env.get("CHATGPT_REQUIREMENT_WRITER_MODEL")
            or env.get("CHATGPT_REPORT_CHAPTER_MODEL")
            or "chatgpt-5.5",
            "CHATGPT_REASONING_EFFORT": "high",
            "BROWSER_AGENT_EXPECTED_OUTPUT": expected,
            "BROWSER_AGENT_CHATGPT_MODEL_MODE": "thinking",
            "BROWSER_AGENT_CHATGPT_TOOL_MODE": "none",
            "BROWSER_AGENT_CHATGPT_ACTION": action,
            "BROWSER_AGENT_PURPOSE": purpose,
        }
    )
    try:
        policy_meta = apply_profile_policy(env, purpose=purpose)
    except RuntimeError as exc:
        print(f"chatgpt_requirement_writer_operator: {exc}", file=sys.stderr)
        return 2
    request_dir = env.get("BROWSER_AGENT_REQUEST_DIR")
    if request_dir:
        path = Path(request_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        (path / "requirement_writer_prompt.md").write_text(prompt + "\n", encoding="utf-8")
        (path / "requirement_writer_profile_policy.json").write_text(
            json.dumps(policy_meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    timeout = int(os.environ.get("CHATGPT_REQUIREMENT_WRITER_TIMEOUT_SEC", "2400") or "2400")
    code, output = run_wrapper_process(cmd, prompt=prompt, env=env, timeout=timeout)
    if code != 0:
        print(output, file=sys.stderr)
        return code
    print(output.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

