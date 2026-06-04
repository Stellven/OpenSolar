#!/usr/bin/env python3
"""Unified RawIntent gateway for Solar-Harness entrypoints.

Every user-facing entrypoint should write the same RawIntent packet before it
creates PRD/contract/task_graph work.  Model rewriting is pluggable through
SOLAR_INTENT_REWRITE_CMD; deterministic rewriting is the fail-open fallback.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


HARNESS_DIR = Path(os.environ.get("SOLAR_HARNESS_DIR", Path(__file__).resolve().parents[1]))
SPRINTS_DIR = Path(os.environ.get("SOLAR_HARNESS_SPRINTS_DIR", Path.home() / ".solar" / "harness" / "sprints"))
INTENTS_DIR = Path(os.environ.get("SOLAR_INTENT_GATEWAY_DIR", Path.home() / ".solar" / "harness" / "intents"))

DEFAULT_GPT_REQUIREMENT_WRITER_TRIGGER_PHRASES = (
    "研究实现",
    "分析论文并实现",
    "调研并实现",
    "研究并落地",
    "先研究再实现",
)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug(value: str, limit: int = 64) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return (text or "intent")[:limit]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _load_trigger_phrases_from_file(path_text: str) -> list[str]:
    path = Path(path_text).expanduser()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        phrases = data.get("phrases")
        if isinstance(phrases, list):
            return [str(item).strip() for item in phrases if str(item).strip()]
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    raise RuntimeError(f"invalid_requirement_writer_trigger_file:{path}")


def load_requirement_writer_trigger_phrases() -> list[str]:
    raw_file = str(os.environ.get("SOLAR_GPT_REQUIREMENT_WRITER_TRIGGER_FILE") or "").strip()
    if raw_file:
        return _load_trigger_phrases_from_file(raw_file)
    raw = str(os.environ.get("SOLAR_GPT_REQUIREMENT_WRITER_TRIGGER_PHRASES") or "").strip()
    if raw:
        items = [item.strip() for item in re.split(r"[\n,|]+", raw) if item.strip()]
        if items:
            return items
    return list(DEFAULT_GPT_REQUIREMENT_WRITER_TRIGGER_PHRASES)


def parse_markdown_sections(markdown_text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body_lines: list[str] = []
    for line in str(markdown_text or "").splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            if current is not None:
                current["content"] = "\n".join(body_lines).strip()
                sections.append(current)
            heading = match.group(2).strip()
            current = {
                "level": len(match.group(1)),
                "heading": heading,
                "slug": slug(heading, 48).lower(),
            }
            body_lines = []
            continue
        body_lines.append(line)
    if current is not None:
        current["content"] = "\n".join(body_lines).strip()
        sections.append(current)
    return [section for section in sections if section.get("heading")]


def read_text_arg(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.text:
        parts.append(args.text)
    if args.file:
        parts.append(Path(args.file).expanduser().read_text(encoding="utf-8", errors="replace"))
    if args.stdin:
        parts.append(sys.stdin.read())
    text = "\n".join(part.strip() for part in parts if part.strip()).strip()
    if not text:
        raise SystemExit("intent-gateway capture requires --text, --file, or --stdin")
    return text


def extract_research_artifact(args: argparse.Namespace) -> dict[str, Any] | None:
    path = str(getattr(args, "research_artifact", "") or "").strip()
    project_name = str(getattr(args, "research_project_name", "") or "").strip()
    conversation_id = str(getattr(args, "research_conversation_id", "") or "").strip()
    source_url = str(getattr(args, "research_source_url", "") or "").strip()
    if not any((path, project_name, conversation_id, source_url)):
        return None
    return {
        "path": path,
        "project_name": project_name,
        "conversation_id": conversation_id,
        "source_url": source_url,
    }


def requirement_writer_trigger(raw_text: str) -> dict[str, Any]:
    clean = str(raw_text or "").strip()
    phrases = load_requirement_writer_trigger_phrases()
    for phrase in phrases:
        if phrase in clean:
            return {
                "triggered": True,
                "mode": "explicit_keyword",
                "phrase": phrase,
                "required": True,
                "reason": f"matched:{phrase}",
                "configured_phrases": phrases,
            }
    if (
        any(token in clean for token in ("论文", "paper", "research", "调研", "研究"))
        and any(token in clean for token in ("实现", "落地", "接入", "reproduce", "reproduction"))
    ):
        return {
            "triggered": True,
            "mode": "heuristic_research_implementation",
            "phrase": "research+implementation",
            "required": False,
            "reason": "mixed_research_and_implementation_markers",
            "configured_phrases": phrases,
        }
    return {
        "triggered": False,
        "mode": "off",
        "phrase": "",
        "required": False,
        "reason": "no_trigger",
        "configured_phrases": phrases,
    }


def _requirement_writer_cmd() -> list[str]:
    raw = os.environ.get("SOLAR_GPT_REQUIREMENT_WRITER_CMD", "").strip()
    if raw:
        return shlex.split(raw)
    return [sys.executable, str(HARNESS_DIR / "tools" / "chatgpt_requirement_writer_operator.py")]


def invoke_requirement_writer(raw_intent: dict[str, Any], base: Path, *, trigger: dict[str, Any]) -> dict[str, Any]:
    raw_block = raw_intent.get("raw") if isinstance(raw_intent.get("raw"), dict) else {}
    raw_text = str((raw_block or {}).get("text") or "").strip()
    if not raw_text:
        raise RuntimeError("requirement_writer_missing_raw_text")
    request_dir = base / "gpt_requirement_writer"
    request_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["SOLAR_RAW_REQUIREMENT"] = raw_text
    env["SOLAR_RAW_INTENT_FILE"] = str(base / "raw_intent.json")
    env["BROWSER_AGENT_RAW_INTENT_FILE"] = str(base / "raw_intent.json")
    env["BROWSER_AGENT_REQUEST_DIR"] = str(request_dir)
    env["BROWSER_AGENT_EXPECTED_OUTPUT"] = "markdown"
    env["BROWSER_AGENT_PURPOSE"] = f"requirement-design:{trigger.get('mode') or 'unknown'}"
    env["BROWSER_AGENT_SESSION_REUSE"] = env.get("BROWSER_AGENT_SESSION_REUSE") or "true"
    env["SOLAR_BROWSER_SESSION_REUSE"] = env.get("SOLAR_BROWSER_SESSION_REUSE") or env["BROWSER_AGENT_SESSION_REUSE"]
    lineage = f"gpt-requirement-writer:{base.name}"
    env["BROWSER_AGENT_SESSION_LINEAGE"] = env.get("BROWSER_AGENT_SESSION_LINEAGE") or lineage
    env["SOLAR_BROWSER_SESSION_LINEAGE"] = env.get("SOLAR_BROWSER_SESSION_LINEAGE") or env["BROWSER_AGENT_SESSION_LINEAGE"]
    env["CHATGPT_REQUIREMENT_WRITER_ACTION"] = "run"
    cmd = _requirement_writer_cmd()
    proc = subprocess.run(
        cmd,
        input=raw_text,
        text=True,
        capture_output=True,
        timeout=int(os.environ.get("SOLAR_GPT_REQUIREMENT_WRITER_TIMEOUT_SEC", "2400") or "2400"),
        env=env,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0 or not stdout:
        raise RuntimeError(
            "requirement_writer_failed:"
            f"exit={proc.returncode}:trigger={trigger.get('mode')}:{stderr or stdout or 'no_output'}"
        )
    output_md = base / "gpt_requirement_writer_output.md"
    output_md.write_text(stdout.rstrip() + "\n", encoding="utf-8")
    sections = parse_markdown_sections(stdout)
    report = {
        "ok": True,
        "operator": "GPTRequirementWriter",
        "trigger": trigger,
        "request_dir": str(request_dir),
        "output_markdown": str(output_md),
        "stdout_length": len(stdout),
        "sections": sections,
    }
    write_json(base / "gpt_requirement_writer_output.json", report)
    return {
        "ok": True,
        "trigger": trigger,
        "markdown": stdout,
        "output_markdown": str(output_md),
        "request_dir": str(request_dir),
        "report_json": str(base / "gpt_requirement_writer_output.json"),
        "sections": sections,
    }


def infer_mode(text: str) -> str:
    value = text.lower()
    # Engineering intents can contain words like "research" or "Deep Research"
    # as product names. Route explicit implementation/runtime/schema/operator
    # work to strategy before applying generic research keyword matching.
    engineering_markers = (
        "operator", "runtime", "schema", "registry", "scheduler",
        "actorhost", "agentactor", "logical_operator", "physicaloperator",
        "实现", "开发", "接入", "算子", "物理执行", "状态机", "注册",
    )
    if any(token in value for token in engineering_markers):
        return "strategy"
    if any(token in value for token in ("debug", "bug", "失败", "报错", "修复", "卡住")):
        return "debug"
    if any(token in value for token in ("架构", "设计", "strategy", "architecture")):
        return "strategy"
    if any(token in value for token in ("monitor", "heartbeat", "巡检", "监控")):
        return "monitor"
    if any(token in value for token in ("research", "report", "论文", "调研", "报告")):
        return "research"
    return "delivery"


def deterministic_rewrite(raw_text: str) -> dict[str, Any]:
    first = next((line.strip() for line in raw_text.splitlines() if line.strip()), raw_text.strip())
    title = re.sub(r"\s+", " ", first)[:90] or "Untitled Intent"
    mode = infer_mode(raw_text)
    constraints: list[str] = [
        "All execution must enter Solar-Harness through RawIntent and requirement compilation.",
        "Do not bypass task_graph, operator runtime, quota-aware fallback, or evidence logging.",
    ]
    if mode == "debug":
        constraints.append("Capture failure evidence before changing implementation.")
    if mode == "research":
        constraints.append("Claims require source/evidence artifacts before final closeout.")
    acceptance = [
        "RawIntent, rewritten_intent, requirement_ir, and requirement_trace artifacts are persisted.",
        "Compiled work is routable through PM/Planner/task_graph and multi-task operator runtime.",
        "Completion requires evidence artifacts and verifier-visible status.",
    ]
    return {
        "schema_version": "solar.rewritten_intent.v1",
        "rewrite_method": "deterministic_fallback",
        "title": title,
        "problem": raw_text.strip(),
        "objective": title,
        "outcome": "A compiled, dispatchable Solar-Harness work item with acceptance evidence.",
        "constraints": constraints,
        "non_goals": ["Do not dispatch raw natural language directly to builder panes."],
        "acceptance": acceptance,
        "suggested_lane": mode,
        "suggested_logical_operators": [
            "RequirementCompiler",
            "Planner",
            "ImplementationWorker",
            "Verifier",
        ],
    }


def _title_from_requirement_writer(markdown_text: str, fallback: str) -> str:
    for line in str(markdown_text or "").splitlines():
        cleaned = re.sub(r"^#+\s*", "", line).strip()
        if cleaned:
            return re.sub(r"\s+", " ", cleaned)[:90]
    return fallback


def rewrite_from_requirement_writer(
    raw_text: str,
    enhanced_markdown: str,
    *,
    trigger: dict[str, Any],
    model_rewrite_meta: dict[str, Any],
) -> dict[str, Any]:
    title = _title_from_requirement_writer(
        enhanced_markdown,
        re.sub(r"\s+", " ", raw_text.strip())[:90] or "Untitled Intent",
    )
    mode = infer_mode(raw_text)
    constraints: list[str] = [
        "All execution must enter Solar-Harness through RawIntent and requirement compilation.",
        "Do not bypass task_graph, operator runtime, quota-aware fallback, or evidence logging.",
        "Compiled package must preserve the original raw user requirement as provenance.",
        "Requirement compiler must prioritize GPTRequirementWriter enhanced design when present.",
    ]
    if mode == "research":
        constraints.append("Claims require source/evidence artifacts before final closeout.")
    acceptance = [
        "RawIntent, rewritten_intent, requirement_ir, requirement_trace, and GPTRequirementWriter artifacts are persisted.",
        "Compiled work is routable through PM/Planner/task_graph and multi-task operator runtime.",
        "Requirement compiler uses chaptered enhanced requirement design as compile input while retaining raw provenance.",
    ]
    return {
        "schema_version": "solar.rewritten_intent.v1",
        "rewrite_method": "gpt_requirement_writer",
        "title": title,
        "problem": raw_text.strip(),
        "objective": title,
        "outcome": "A compiled, dispatchable Solar-Harness work item with an enhanced chaptered requirement design.",
        "constraints": constraints,
        "non_goals": ["Do not dispatch raw natural language directly to builder panes."],
        "acceptance": acceptance,
        "suggested_lane": mode if mode != "delivery" else "strategy",
        "suggested_logical_operators": [
            "GPTRequirementWriter",
            "Planner",
            "ImplementationWorker",
            "Verifier",
        ],
        "enhanced_requirement_markdown": enhanced_markdown,
        "requirement_enhancement": {
            "triggered": True,
            "trigger_mode": trigger.get("mode") or "unknown",
            "trigger_phrase": trigger.get("phrase") or "",
            "required": bool(trigger.get("required")),
            "operator": "GPTRequirementWriter",
            "configured_phrases": trigger.get("configured_phrases") or [],
        },
        "model_rewrite": model_rewrite_meta,
    }


def model_rewrite(raw_intent: dict[str, Any], prompt_path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    cmd = os.environ.get("SOLAR_INTENT_REWRITE_CMD", "").strip()
    if not cmd:
        return None, {"attempted": False, "reason": "SOLAR_INTENT_REWRITE_CMD_not_set"}
    prompt = {
        "instruction": (
            "Rewrite the RawIntent into strict JSON with keys: title, problem, "
            "objective, outcome, constraints, non_goals, acceptance, suggested_lane, "
            "suggested_logical_operators. Do not invent external facts."
        ),
        "raw_intent": raw_intent,
    }
    write_json(prompt_path, prompt)
    env = dict(os.environ)
    env["SOLAR_INTENT_REWRITE_PROMPT"] = str(prompt_path)
    try:
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            text=True,
            capture_output=True,
            timeout=int(os.environ.get("SOLAR_INTENT_REWRITE_TIMEOUT_SEC", "90") or "90"),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None, {"attempted": True, "status": "timeout"}
    output = (proc.stdout or "").strip()
    meta = {"attempted": True, "exit_code": proc.returncode, "stderr_tail": (proc.stderr or "")[-1000:]}
    if proc.returncode != 0 or not output:
        meta["status"] = "failed"
        return None, meta
    try:
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            parsed.setdefault("schema_version", "solar.rewritten_intent.v1")
            parsed["rewrite_method"] = "model"
            meta["status"] = "ok"
            return parsed, meta
    except Exception:
        pass
    fallback = deterministic_rewrite(output)
    fallback["rewrite_method"] = "model_text_normalized"
    meta["status"] = "text_normalized"
    return fallback, meta


def build_requirement_ir(
    intent_id: str,
    raw_intent: dict[str, Any],
    rewritten: dict[str, Any],
    enhancement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = raw_intent.get("context", {}) if isinstance(raw_intent.get("context"), dict) else {}
    raw_block = raw_intent.get("raw", {}) if isinstance(raw_intent.get("raw"), dict) else {}
    research = raw_intent.get("research") if isinstance(raw_intent.get("research"), dict) else None
    source_inputs: dict[str, Any] = {
        "raw_request": str(raw_block.get("text") or "").strip(),
        "repo_context": [context.get("repo")] if context.get("repo") else [],
    }
    if research:
        source_inputs["research_artifact"] = {
            "path": research.get("path", ""),
            "project_name": research.get("project_name", ""),
            "conversation_id": research.get("conversation_id", ""),
            "source_url": research.get("source_url", ""),
        }
    if enhancement and enhancement.get("ok"):
        enhanced_sections = enhancement.get("sections") if isinstance(enhancement.get("sections"), list) else []
        source_inputs["enhanced_requirement"] = {
            "operator": "GPTRequirementWriter",
            "trigger": enhancement.get("trigger") or {},
            "markdown_path": enhancement.get("output_markdown") or "",
            "report_json": enhancement.get("report_json") or "",
            "request_dir": enhancement.get("request_dir") or "",
            "content": enhancement.get("markdown") or "",
            "sections": enhanced_sections,
            "compile_segments": [
                {
                    "heading": str(section.get("heading") or ""),
                    "level": int(section.get("level") or 0),
                    "text": (
                        f"{section.get('heading')}\n{section.get('content')}".strip()
                    ),
                }
                for section in enhanced_sections
            ],
        }
    return {
        "schema_version": "solar.requirement_ir.v1",
        "intent_id": intent_id,
        "source": raw_intent.get("source", {}),
        "source_inputs": source_inputs,
        "title": rewritten.get("title", ""),
        "problem": rewritten.get("problem", ""),
        "objective": rewritten.get("objective", ""),
        "outcome": rewritten.get("outcome", ""),
        "constraints": rewritten.get("constraints", []),
        "non_goals": rewritten.get("non_goals", []),
        "acceptance": rewritten.get("acceptance", []),
        "lane": rewritten.get("suggested_lane", "delivery"),
        "logical_operators": rewritten.get("suggested_logical_operators", []),
        "compiler_next": "pm_planner_task_graph",
        "requirement_enhancement": rewritten.get("requirement_enhancement") or {
            "triggered": False,
            "operator": "",
        },
    }


def capture(args: argparse.Namespace) -> dict[str, Any]:
    raw_text = read_text_arg(args)
    created = now_iso()
    digest = hashlib.sha1(f"{created}\n{raw_text}".encode("utf-8")).hexdigest()[:10]
    intent_id = args.intent_id or f"intent-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{digest}"
    research = extract_research_artifact(args)
    raw_intent = {
        "schema_version": "solar.raw_intent.v1",
        "intent_id": intent_id,
        "source": {
            "channel": args.source_channel,
            "actor": args.actor,
            "device": args.device,
            "session_id": args.session_id,
            "thread_ref": args.thread_ref,
        },
        "raw": {
            "text": raw_text,
            "attachments": [],
            "quoted_context": [],
            "received_at": created,
        },
        "context": {
            "repo": args.repo or "",
            "cwd": str(Path.cwd()),
            "related_sprints": [],
            "knowledge_query": args.knowledge_query or "",
        },
        "routing_hints": {
            "urgency": args.urgency,
            "mode": args.mode or infer_mode(raw_text),
            "allow_autodispatch": not args.no_autodispatch,
            "requires_human_confirm": args.requires_human_confirm,
            "require_research_artifact": bool(args.require_research_artifact or research),
        },
        "trust": {
            "source_trust": args.source_trust,
            "prompt_injection_risk": "unknown",
            "contains_secrets": "unknown",
        },
    }
    base = INTENTS_DIR / intent_id
    if research:
        raw_intent["research"] = research
    enhancement_trigger = requirement_writer_trigger(raw_text)
    raw_intent["routing_hints"]["requirement_enhancement"] = enhancement_trigger
    write_json(base / "raw_intent.json", raw_intent)
    enhancement: dict[str, Any] | None = None
    if enhancement_trigger.get("triggered"):
        try:
            enhancement = invoke_requirement_writer(raw_intent, base, trigger=enhancement_trigger)
        except RuntimeError as exc:
            if enhancement_trigger.get("required"):
                raise SystemExit(f"intent-gateway requirement enhancement failed: {exc}")
            enhancement = {
                "ok": False,
                "trigger": enhancement_trigger,
                "error": str(exc),
            }
            write_json(base / "gpt_requirement_writer_output.json", enhancement)
    model_result, rewrite_meta = model_rewrite(raw_intent, base / "rewrite_prompt.json")
    if enhancement and enhancement.get("ok"):
        rewritten = rewrite_from_requirement_writer(
            raw_text,
            str(enhancement.get("markdown") or ""),
            trigger=enhancement_trigger,
            model_rewrite_meta=rewrite_meta,
        )
    else:
        rewritten = model_result or deterministic_rewrite(raw_text)
    rewritten["intent_id"] = intent_id
    rewritten["model_rewrite"] = rewrite_meta
    requirement_ir = build_requirement_ir(intent_id, raw_intent, rewritten, enhancement=enhancement)
    trace = {
        "schema_version": "solar.requirement_trace.v1",
        "intent_id": intent_id,
        "created_at": created,
        "artifacts": {
            "raw_intent": str(base / "raw_intent.json"),
            "rewritten_intent": str(base / "rewritten_intent.json"),
            "requirement_ir": str(base / "requirement_ir.json"),
        },
        "stages": [
            {"stage": "raw_intent_capture", "status": "ok"},
            {
                "stage": "requirement_enhancement",
                "status": "ok" if enhancement and enhancement.get("ok") else ("skipped" if not enhancement_trigger.get("triggered") else "warn"),
                "method": (enhancement_trigger.get("mode") if enhancement_trigger.get("triggered") else "not_triggered"),
            },
            {"stage": "intent_rewrite", "status": "ok", "method": rewritten.get("rewrite_method")},
            {"stage": "requirement_ir_compile", "status": "ok"},
        ],
    }
    write_json(base / "rewritten_intent.json", rewritten)
    write_json(base / "requirement_ir.json", requirement_ir)
    write_json(base / "requirement_trace.json", trace)
    if args.sprint_id:
        bind_intent_artifacts(intent_id, args.sprint_id)
    return {
        "ok": True,
        "intent_id": intent_id,
        "title": rewritten.get("title"),
        "lane": requirement_ir.get("lane"),
        "rewrite_method": rewritten.get("rewrite_method"),
        "raw_intent": str(base / "raw_intent.json"),
        "rewritten_intent": str(base / "rewritten_intent.json"),
        "requirement_ir": str(base / "requirement_ir.json"),
        "requirement_trace": str(base / "requirement_trace.json"),
        "requirement_enhancement": enhancement or {"ok": False, "trigger": enhancement_trigger},
    }


def bind_intent_artifacts(intent_id: str, sprint_id: str) -> dict[str, Any]:
    base = INTENTS_DIR / intent_id
    if not (base / "raw_intent.json").exists():
        raise SystemExit(f"unknown intent_id: {intent_id}")
    mapping = {
        "raw_intent.json": SPRINTS_DIR / f"{sprint_id}.raw_intent.json",
        "rewritten_intent.json": SPRINTS_DIR / f"{sprint_id}.rewritten_intent.json",
        "requirement_ir.json": SPRINTS_DIR / f"{sprint_id}.requirement_ir.json",
        "requirement_trace.json": SPRINTS_DIR / f"{sprint_id}.requirement_trace.json",
    }
    for name, dst in mapping.items():
        payload = json.loads((base / name).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["sprint_id"] = sprint_id
        write_json(dst, payload)
    optional_copies = {
        "gpt_requirement_writer_output.json": SPRINTS_DIR / f"{sprint_id}.gpt_requirement_writer_output.json",
        "gpt_requirement_writer_output.md": SPRINTS_DIR / f"{sprint_id}.gpt_requirement_writer_output.md",
    }
    for name, dst in optional_copies.items():
        src = base / name
        if not src.exists():
            continue
        if src.suffix == ".json":
            payload = json.loads(src.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload["sprint_id"] = sprint_id
            write_json(dst, payload)
        else:
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {"ok": True, "intent_id": intent_id, "sprint_id": sprint_id, "artifacts": {k: str(v) for k, v in mapping.items()}}
    write_json(base / "binding.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intent_gateway.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--text", default="")
    cap.add_argument("--file", default="")
    cap.add_argument("--stdin", action="store_true")
    cap.add_argument("--intent-id", default="")
    cap.add_argument("--source-channel", default="cli")
    cap.add_argument("--actor", default="user")
    cap.add_argument("--device", default="")
    cap.add_argument("--session-id", default="")
    cap.add_argument("--thread-ref", default="")
    cap.add_argument("--repo", default="")
    cap.add_argument("--knowledge-query", default="")
    cap.add_argument("--urgency", default="normal")
    cap.add_argument("--mode", default="")
    cap.add_argument("--source-trust", default="user_direct")
    cap.add_argument("--no-autodispatch", action="store_true")
    cap.add_argument("--requires-human-confirm", action="store_true")
    cap.add_argument("--require-research-artifact", action="store_true")
    cap.add_argument("--research-artifact", default="")
    cap.add_argument("--research-project-name", default="")
    cap.add_argument("--research-conversation-id", default="")
    cap.add_argument("--research-source-url", default="")
    cap.add_argument("--sprint-id", default="")
    cap.add_argument("--json", action="store_true")

    bind = sub.add_parser("bind")
    bind.add_argument("--intent-id", required=True)
    bind.add_argument("--sprint-id", required=True)
    bind.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "capture":
        payload = capture(args)
    elif args.cmd == "bind":
        payload = bind_intent_artifacts(args.intent_id, args.sprint_id)
    else:
        raise SystemExit(f"unknown command: {args.cmd}")
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"intent_id={payload.get('intent_id')} rewrite={payload.get('rewrite_method', 'N/A')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
