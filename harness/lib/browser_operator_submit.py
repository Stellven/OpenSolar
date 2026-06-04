from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHATGPT_OPERATOR = ROOT / "tools" / "chatgpt_report_operator.py"


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
        raise RuntimeError(f"browser_agent_chatgpt failed rc={run.returncode}: {output[-2000:]}")
    min_chars = 500 if expected == "json" else 1000
    if len(output) < min_chars:
        raise ValueError(f"browser_agent_chatgpt output too short: {len(output)} chars")
    return {
        "output": output,
        "latency_ms": int((time.time() - started) * 1000),
    }
