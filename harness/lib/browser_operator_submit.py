from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
import json
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHATGPT_OPERATOR = ROOT / "tools" / "chatgpt_report_operator.py"
if str(ROOT / "tools") not in sys.path:
    sys.path.append(str(ROOT / "tools"))

from browser_agent_session_control import poll_request  # type: ignore  # noqa: E402


def strip_browser_agent_noise(text: str) -> str:
    if not text:
        return ""
    lines = str(text).splitlines()
    cleaned: list[str] = []
    started = False
    noise_prefixes = ("INFO     [", "WARNING  [", "ERROR    [", "DEBUG    [")
    for line in lines:
        if not started and (line.startswith(noise_prefixes) or not line.strip()):
            continue
        started = True
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def env_override_text(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return None


def env_override_bool(*names: str) -> bool | None:
    raw = env_override_text(*names)
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def default_slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def derive_chatgpt_session_lineage(
    purpose: str,
    *,
    slugify: Callable[[str], str] = default_slugify,
) -> str:
    value = str(purpose or "").strip().lower()
    if not value:
        return "browser-agent:default"
    for prefix, lineage_prefix in (
        ("ai-influence-video-grouping-", "ai-influence-planning:"),
        ("ai-influence-report-plan-", "ai-influence-planning:"),
        ("github-trend-report-", "github-trend-report:"),
        ("hf-paper-l7-high-reasoning-", "hf-paper-l7-high-reasoning:"),
    ):
        if value.startswith(prefix):
            return f"{lineage_prefix}{value[len(prefix):]}"
    if value.startswith("hf-paper-report-plan-"):
        return f"hf-paper-report:{value[len('hf-paper-report-plan-'):]}"
    if value.startswith("hf-paper-report-section-"):
        tail = value[len("hf-paper-report-section-"):]
        date_key = tail.split("-", 3)[0:3]
        if len(date_key) == 3 and all(part.isdigit() for part in date_key):
            return f"hf-paper-report:{'-'.join(date_key)}"
        return f"hf-paper-report:{slugify(tail)[:80]}"
    if value.startswith("ai-influence-report-chapter-"):
        tail = value[len("ai-influence-report-chapter-"):]
        match = re.match(r"(?P<date>\d{4}-\d{2}-\d{2})-(?P<report>.+)-(?P<chapter>[^-]+)$", tail)
        if match:
            return f"ai-influence-report:{match.group('date')}:{slugify(match.group('report'))[:80]}"
        return f"ai-influence-report:{slugify(tail)[:80]}"
    return f"browser-agent:{slugify(value)[:96]}"


def browser_agent_chatgpt_cmd(config: dict[str, Any]) -> list[str]:
    flow_cfg = ((config.get("youtube") or {}).get("ai_influence_report_flow") or {})
    reasoner_cfg = ((config.get("youtube") or {}).get("phase_report_reasoner") or {})
    cmd = (
        os.environ.get("TECH_HOTSPOT_BROWSER_CHATGPT_CMD")
        or os.environ.get("BROWSER_AGENT_CHATGPT_CMD")
        or str((flow_cfg.get("browser_agent") or {}).get("cmd") or "")
        or str(reasoner_cfg.get("browser_agent_cmd") or "")
    ).strip()
    if cmd:
        return shlex.split(cmd)
    if DEFAULT_CHATGPT_OPERATOR.exists():
        return [sys.executable, str(DEFAULT_CHATGPT_OPERATOR)]
    return []


def build_chatgpt_operator_env(
    *,
    model: str,
    reasoning_effort: str,
    expected: str,
    request_dir: str | Path,
    purpose: str,
    session_lineage: str,
    session_reuse: bool,
    operator_kind: str | None = None,
    target_url: str | None = None,
    headless: bool | None = None,
    profile_directory: str | None = None,
    target_account_email: str | None = None,
    scrub_client_state: bool | None = None,
    open_project_first: bool | None = None,
    require_project: bool | None = None,
    force_new_chat: bool | None = None,
    require_isolated_conversation: bool | None = None,
    project_name: str | None = None,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env.update(
        {
            "CHATGPT_MODEL": str(model),
            "CHATGPT_REASONING_EFFORT": str(reasoning_effort),
            "BROWSER_AGENT_EXPECTED_OUTPUT": expected,
            "BROWSER_AGENT_REQUEST_DIR": str(request_dir),
            "BROWSER_AGENT_PURPOSE": purpose,
            "BROWSER_AGENT_CHATGPT_MODEL_MODE": "thinking",
            "BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE": "true",
            "BROWSER_AGENT_SESSION_LINEAGE": session_lineage,
            "SOLAR_BROWSER_SESSION_LINEAGE": session_lineage,
            "BROWSER_AGENT_SESSION_REUSE": "true" if bool(session_reuse) else "false",
            "SOLAR_BROWSER_SESSION_REUSE": "true" if bool(session_reuse) else "false",
        }
    )
    if operator_kind:
        env["CHATGPT_REPORT_OPERATOR_KIND"] = operator_kind
    if target_url:
        env["BROWSER_AGENT_CHATGPT_URL"] = str(target_url)
    if headless is not None:
        env["BROWSER_AGENT_HEADLESS"] = "true" if bool(headless) else "false"
    if profile_directory:
        env["BROWSER_AGENT_PROFILE_DIRECTORY"] = str(profile_directory)
    if target_account_email:
        env["BROWSER_AGENT_TARGET_ACCOUNT_EMAIL"] = str(target_account_email)
        env["BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL"] = str(target_account_email)
    if scrub_client_state is not None:
        env["BROWSER_AGENT_CHATGPT_SCRUB_CLIENT_STATE"] = "true" if bool(scrub_client_state) else "false"
    if open_project_first is not None:
        env["BROWSER_AGENT_CHATGPT_OPEN_PROJECT_FIRST"] = "true" if bool(open_project_first) else "false"
    if require_project is not None:
        env["BROWSER_AGENT_CHATGPT_REQUIRE_PROJECT"] = "true" if bool(require_project) else "false"
    if force_new_chat is not None:
        env["BROWSER_AGENT_CHATGPT_FORCE_NEW_CHAT"] = "true" if bool(force_new_chat) else "false"
    if require_isolated_conversation is not None:
        env["BROWSER_AGENT_CHATGPT_REQUIRE_ISOLATED_CONVERSATION"] = (
            "true" if bool(require_isolated_conversation) else "false"
        )
    if project_name:
        env["BROWSER_AGENT_CHATGPT_PROJECT_NAME"] = str(project_name)
    return env


def submit_chatgpt_operator_request(
    *,
    cmd: list[str],
    prompt: str,
    timeout: int,
    env: Mapping[str, str],
    request_dir: str | Path,
    expected: str,
    use_session_control: bool = False,
    poll_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    request_path = Path(request_dir).expanduser()
    request_path.mkdir(parents=True, exist_ok=True)
    started = time.time()
    if not use_session_control:
        run = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=dict(env),
        )
        output = strip_browser_agent_noise(run.stdout or "")
        (request_path / "stdout.txt").write_text(output + ("\n" if output else ""), encoding="utf-8")
        if run.returncode != 0:
            raise RuntimeError(f"browser_agent_chatgpt failed rc={run.returncode}: {output[-2000:]}")
        min_chars = 500 if expected == "json" else 1000
        if len(output) < min_chars:
            raise ValueError(f"browser_agent_chatgpt output too short: {len(output)} chars")
        return {
            "output": output,
            "latency_ms": int((time.time() - started) * 1000),
        }

    submit_env = dict(env)
    submit_env["CHATGPT_REPORT_ACTION"] = "submit"
    submit_run = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=min(timeout, 120),
        env=submit_env,
    )
    submit_output = strip_browser_agent_noise(submit_run.stdout or "")
    (request_path / "submit-stdout.txt").write_text(submit_output + ("\n" if submit_output else ""), encoding="utf-8")
    if submit_run.returncode != 0:
        raise RuntimeError(f"browser_agent_chatgpt submit failed rc={submit_run.returncode}: {submit_output[-2000:]}")

    submitted_path = request_path / "submitted-run.json"
    task_id = ""
    if submitted_path.exists():
        try:
            submitted_payload = json.loads(submitted_path.read_text(encoding="utf-8"))
            if isinstance(submitted_payload, dict):
                task_id = str(submitted_payload.get("task_id") or "").strip()
        except Exception:
            task_id = ""
    if not task_id:
        try:
            parsed_submit = json.loads(submit_output)
            if isinstance(parsed_submit, dict):
                task_id = str(parsed_submit.get("task_id") or "").strip()
        except Exception:
            task_id = ""
    if not task_id:
        raise RuntimeError("browser_agent_chatgpt submit did not provide task_id")

    poll_deadline = time.time() + max(1, timeout)
    poll_attempts = 0
    while time.time() <= poll_deadline:
        status_payload = poll_request(task_id)
        status = str(status_payload.get("status") or "").strip().lower()
        (request_path / "poll-status.json").write_text(
            json.dumps(status_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if status == "failed":
            latest = status_payload.get("latest_result") if isinstance(status_payload.get("latest_result"), dict) else {}
            raise RuntimeError(
                "browser_agent_chatgpt session task failed: "
                + str((latest or {}).get("error") or status_payload)
        )
        if status == "completed":
            break
        poll_attempts += 1
        multiplier = min(max(poll_attempts, 1), 4)
        if status == "submitted":
            sleep_seconds = min(8.0, max(0.2, float(poll_interval_seconds)) * multiplier)
        else:
            sleep_seconds = min(12.0, max(0.2, float(poll_interval_seconds)) * max(2, multiplier))
        time.sleep(sleep_seconds)
    else:
        raise TimeoutError(f"browser_agent_chatgpt session task timed out waiting for completion: task_id={task_id}")

    collect_env = dict(env)
    collect_env["CHATGPT_REPORT_ACTION"] = "collect"
    collect_run = subprocess.run(
        cmd,
        input="",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=min(timeout, 300),
        env=collect_env,
    )
    output = strip_browser_agent_noise(collect_run.stdout or "")
    (request_path / "stdout.txt").write_text(output + ("\n" if output else ""), encoding="utf-8")
    if collect_run.returncode != 0:
        raise RuntimeError(f"browser_agent_chatgpt collect failed rc={collect_run.returncode}: {output[-2000:]}")
    min_chars = 500 if expected == "json" else 1000
    if len(output) < min_chars:
        raise ValueError(f"browser_agent_chatgpt output too short: {len(output)} chars")
    return {
        "output": output,
        "latency_ms": int((time.time() - started) * 1000),
        "task_id": task_id,
    }


def submit_gemini_operator_request(
    *,
    cmd: list[str],
    prompt: str,
    timeout: int,
    env: Mapping[str, str],
    request_dir: str | Path,
) -> dict[str, Any]:
    request_path = Path(request_dir).expanduser()
    request_path.mkdir(parents=True, exist_ok=True)
    started = time.time()
    run = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=dict(env),
    )
    output = strip_browser_agent_noise(run.stdout or "")
    (request_path / "stdout.txt").write_text(output + ("\n" if output else ""), encoding="utf-8")
    if run.returncode != 0:
        raise RuntimeError(f"browser_agent_gemini failed rc={run.returncode}: {output[-2000:]}")
    if len(output) < 500:
        raise ValueError(f"browser_agent_gemini output too short: {len(output)} chars")
    return {
        "output": output,
        "latency_ms": int((time.time() - started) * 1000),
    }


def submit_youtube_operator_request(
    *,
    cmd: list[str],
    youtube_url: str,
    timeout: int,
    env: Mapping[str, str],
    request_dir: str | Path,
) -> dict[str, Any]:
    request_path = Path(request_dir).expanduser()
    request_path.mkdir(parents=True, exist_ok=True)
    started = time.time()
    run = subprocess.run(
        cmd,
        input=youtube_url,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=dict(env),
    )
    output = strip_browser_agent_noise(run.stdout or "")
    (request_path / "stdout.txt").write_text(output + ("\n" if output else ""), encoding="utf-8")
    if run.returncode != 0:
        raise RuntimeError(f"browser_agent_youtube failed rc={run.returncode}: {output[-2000:]}")
    if len(output) < 2:
        raise ValueError(f"browser_agent_youtube output too short: {len(output)} chars")
    return {
        "output": output,
        "latency_ms": int((time.time() - started) * 1000),
    }
