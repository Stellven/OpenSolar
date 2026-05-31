#!/usr/bin/env python3
"""Command backend adapter for Webwright Playwright logical operator tasks.

Generates a replayable Playwright script, runs it, and outputs verification artifacts.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))

import operator_flow_control as ofc  # noqa: E402

DEFAULT_OPERATOR_ID = "op.browser.webwright.playwright.01"
DEFAULT_BROWSER_USE_PYTHON = Path.home() / ".claude" / "mcp-servers" / "browser-use" / ".venv" / "bin" / "python"


def _load_envelope() -> dict[str, Any]:
    path = str(os.environ.get("SOLAR_OPERATOR_ENVELOPE_JSON") or "").strip()
    if not path:
        raise RuntimeError("SOLAR_OPERATOR_ENVELOPE_JSON missing")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("operator envelope must be a JSON object")
    return payload


def _task_dir() -> Path:
    raw = str(os.environ.get("TASK_DIR") or "").strip()
    if raw:
        path = Path(raw).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path.cwd()


def _extract_url(text: str) -> str:
    """Extract a target URL from the objective or prompt, default to 知乎 if none found."""
    text_lower = text.lower()
    if "zhihu" in text_lower or "知乎" in text_lower:
        return "https://www.zhihu.com"
    
    # Try regex URL match
    match = re.search(r'https?://[^\s"\'()]+', text)
    if match:
        return match.group(0)
    
    # Check domain patterns
    match_domain = re.search(r'([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
    if match_domain:
        return f"https://{match_domain.group(1)}"
        
    return "https://www.zhihu.com"


def build_request(envelope: dict[str, Any], *, task_dir: Path | None = None) -> dict[str, Any]:
    request = {}
    objective = str(envelope.get("objective") or envelope.get("prompt") or "").strip()
    request["objective"] = objective
    request["url"] = _extract_url(objective)
    request["timeout_seconds"] = int(envelope.get("timeout_seconds") or 300)
    request["max_retries"] = int(envelope.get("max_retries") or 3)
    return request


def _rate_control_settings(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "operator_id": DEFAULT_OPERATOR_ID,
        "success_cooldown_seconds": 60,
        "rate_limit_cooldown_seconds": 600,
        "auth_cooldown_seconds": 3600,
        "defer_on_cooldown": True,
        "defer_on_auth": True,
    }


def _write_script_template(url: str, script_path: Path) -> None:
    content = f"""# -*- coding: utf-8 -*-
import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def run_task():
    script_dir = Path(__file__).resolve().parent
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    headless = os.environ.get("BROWSER_AGENT_HEADLESS", "true").lower() == "true"
    print(f"[Webwright Script] Launching browser (headless={{headless}})...", flush=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        target_url = "{url}"
        print(f"[Webwright Script] Navigating to {{target_url}}...", flush=True)
        await page.goto(target_url, wait_until="domcontentloaded")
        
        # Wait to let page load dynamically
        print("[Webwright Script] Waiting 5 seconds...", flush=True)
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        screenshot_path = screenshots_dir / "page_screenshot.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"[Webwright Script] Screenshot saved to {{screenshot_path}}", flush=True)
        
        # Print page details
        title = await page.title()
        url_curr = page.url
        print(f"[Webwright Script] Title: {{title}}", flush=True)
        print(f"[Webwright Script] URL: {{url_curr}}", flush=True)
        
        await browser.close()
        print("[Webwright Script] Done.", flush=True)

if __name__ == "__main__":
    asyncio.run(run_task())
"""
    script_path.write_text(content, encoding="utf-8")


def run_request(request: dict[str, Any], *, task_dir: Path) -> dict[str, Any]:
    url = request["url"]
    script_path = task_dir / "final_script.py"
    trajectory_path = task_dir / "trajectory.json"
    screenshots_dir = task_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Compile/write script
    _write_script_template(url, script_path)
    
    # 2. Run the script using the playwright venv python
    python_bin = str(DEFAULT_BROWSER_USE_PYTHON) if DEFAULT_BROWSER_USE_PYTHON.exists() else sys.executable
    print(f"[Webwright Operator] Running {script_path} via {python_bin}...", flush=True)
    
    env = os.environ.copy()
    # Force headless unless explicitly overridden
    if "BROWSER_AGENT_HEADLESS" not in env:
        env["BROWSER_AGENT_HEADLESS"] = "true"
        
    start_time = time.time()
    
    proc = subprocess.run(
        [python_bin, str(script_path)],
        text=True,
        capture_output=True,
        env=env,
        timeout=request["timeout_seconds"],
    )
    
    duration = time.time() - start_time
    combined_output = f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    
    (task_dir / "webwright-execution-log.txt").write_text(combined_output, encoding="utf-8")
    
    # 3. Compile trajectory and report
    trajectory = {
        "steps": [
            {
                "action": "generate_script",
                "status": "success",
                "script_path": str(script_path)
            },
            {
                "action": "execute_script",
                "status": "success" if proc.returncode == 0 else "failed",
                "return_code": proc.returncode,
                "duration_seconds": duration,
                "log_preview": combined_output[-1000:]
            }
        ]
    }
    trajectory_path.write_text(json.dumps(trajectory, indent=2), encoding="utf-8")
    
    report = {
        "ok": proc.returncode == 0,
        "target_url": url,
        "duration_seconds": duration,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    (task_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    
    if proc.returncode != 0:
        raise RuntimeError(f"Webwright script execution failed with code {proc.returncode}.\nLog:\n{proc.stderr}")
        
    print(f"\n# Webwright Execution Success\n- Target URL: {url}\n- Duration: {duration:.2f}s\n- Title Log:\n{proc.stdout}", flush=True)
    return report


def main() -> int:
    try:
        envelope = _load_envelope()
    except Exception as exc:
        print(f"Failed to load envelope: {exc}", file=sys.stderr)
        return 1

    task_dir = _task_dir()
    ofc.clear_task_control(task_dir)
    request = build_request(envelope, task_dir=task_dir)
    rate_control = _rate_control_settings(envelope)
    operator_id = str(rate_control["operator_id"])
    try:
        ofc.ensure_operator_available(operator_id)
        run_request(request, task_dir=task_dir)
        ofc.apply_success_cooldown(
            operator_id,
            success_cooldown_seconds=int(rate_control.get("success_cooldown_seconds") or 0),
        )
        return 0
    except Exception as exc:
        ofc.apply_failure_flow_control(
            task_dir,
            operator_id=operator_id,
            failure_text=str(exc),
            rate_limit_cooldown_seconds=int(rate_control.get("rate_limit_cooldown_seconds") or 0),
            auth_cooldown_seconds=int(rate_control.get("auth_cooldown_seconds") or 0),
            defer_on_cooldown=bool(rate_control.get("defer_on_cooldown")),
            defer_on_auth=bool(rate_control.get("defer_on_auth")),
        )
        print(f"webwright_operator failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
