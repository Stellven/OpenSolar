"""Browser Agent wrapper contract for ChatGPT 5.5 Thinking high.

This module defines the seam and fake-provider behavior for tests. Production
integration is injected through provider and can reuse the existing
``chatgpt_report_operator`` + browser session control chain.
"""

from __future__ import annotations

import time
import json
import os
import re
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from .ledger import append_model_call_ledger
from .prompts import PHASE1_PLAN_PROMPT, PHASE2_BATCH_PROMPT, PHASE2_CHAPTER_PROMPT, PHASE3_SYNTHESIS_PROMPT


class BrowserAgentProvider(Protocol):
    def call(
        self,
        stage: str,
        payload: dict[str, Any],
        *,
        requested_model: str,
        run_id: str = "",
        chapter_id: str = "",
        sprint_id: str = "",
    ) -> dict[str, Any]: ...


class LocalModelSubstitutionError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHATGPT_REPORT_OPERATOR = ROOT / "tools" / "chatgpt_report_operator.py"


def _slug(value: str, *, fallback: str = "default", limit: int = 96) -> str:
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip()).strip("-")
    return (text or fallback)[:limit]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _phase_instruction(stage: str) -> str:
    if stage == "phase1":
        return PHASE1_PLAN_PROMPT
    if stage == "phase2":
        return PHASE2_CHAPTER_PROMPT
    if stage == "phase2_batch":
        return PHASE2_BATCH_PROMPT
    if stage == "phase3":
        return PHASE3_SYNTHESIS_PROMPT
    raise RuntimeError(f"unsupported_browser_agent_stage:{stage}")


def _stage_kind(stage: str) -> str:
    if stage == "phase1":
        return "planner"
    return "chapter_writer"


def _stage_expected_output(stage: str) -> str:
    if stage in {"phase1", "phase2_batch"}:
        return "json"
    return "markdown"


def _stage_purpose(stage: str) -> str:
    mapping = {
        "phase1": "ai-influence-youtube-report:phase1-plan",
        "phase2": "ai-influence-youtube-report:phase2-chapter",
        "phase2_batch": "ai-influence-youtube-report:phase2-batch",
        "phase3": "ai-influence-youtube-report:phase3-synthesis",
    }
    return mapping.get(stage, f"ai-influence-youtube-report:{stage}")


def _render_stage_prompt(stage: str, payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# AI Influence YouTube {stage}",
            "",
            "## 执行要求",
            _phase_instruction(stage),
            "",
            "## 输入载荷(JSON)",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    ).strip()


class ChatGPTReportOperatorProvider:
    """Production provider backed by chatgpt_report_operator.

    This keeps AI Influence YouTube browser-agent calls on the same session
    control path already used by the main ChatGPT report operators.
    """

    def __init__(
        self,
        *,
        operator_script: str | Path | None = None,
        python_executable: str | Path | None = None,
        request_root: str | Path | None = None,
        project_name: str = "杂项",
        target_account_email: str | None = None,
        profile_directory: str | None = None,
        timeout_seconds: int = 1800,
        headless: bool = True,
        session_reuse: bool = True,
        lineage_prefix: str = "ai-influence-youtube-report",
    ) -> None:
        self.operator_script = Path(operator_script or DEFAULT_CHATGPT_REPORT_OPERATOR)
        self.python_executable = str(python_executable or sys.executable)
        self.request_root = Path(
            request_root or (Path.home() / ".solar" / "harness" / "run" / "ai-influence-youtube-report-browser-agent")
        ).expanduser()
        self.project_name = str(project_name or "杂项")
        self.target_account_email = str(target_account_email or "").strip() or None
        self.profile_directory = str(profile_directory or "").strip() or None
        self.timeout_seconds = max(int(timeout_seconds), 60)
        self.headless = bool(headless)
        self.session_reuse = bool(session_reuse)
        self.lineage_prefix = _slug(str(lineage_prefix or "ai-influence-youtube-report"), fallback="ai-influence-youtube-report")

    def _request_dir(self, *, stage: str, run_id: str, chapter_id: str, sprint_id: str, payload: dict[str, Any]) -> Path:
        scope = _slug(sprint_id or run_id or "adhoc", fallback="adhoc")
        chapter_scope = _slug(chapter_id, fallback="stage") if chapter_id else "stage"
        payload_digest = uuid4().hex[:8]
        if payload:
            payload_digest = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:8]
        return self.request_root / scope / f"{stage}-{chapter_scope}-{payload_digest}"

    def _session_lineage(self, *, stage: str, run_id: str, chapter_id: str) -> str:
        pieces = [self.lineage_prefix, stage]
        if run_id:
            pieces.append(_slug(run_id, fallback="run"))
        if chapter_id:
            pieces.append(_slug(chapter_id, fallback="chapter"))
        return ":".join(pieces)

    def call(
        self,
        stage: str,
        payload: dict[str, Any],
        *,
        requested_model: str,
        run_id: str = "",
        chapter_id: str = "",
        sprint_id: str = "",
    ) -> dict[str, Any]:
        if not self.operator_script.exists():
            raise RuntimeError(f"chatgpt_report_operator not found: {self.operator_script}")
        request_dir = self._request_dir(stage=stage, run_id=run_id, chapter_id=chapter_id, sprint_id=sprint_id, payload=payload)
        request_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["BROWSER_AGENT_REQUEST_DIR"] = str(request_dir)
        env["BROWSER_AGENT_PURPOSE"] = _stage_purpose(stage)
        env["CHATGPT_REPORT_ACTION"] = "run"
        env["CHATGPT_REPORT_OPERATOR_KIND"] = _stage_kind(stage)
        env["BROWSER_AGENT_EXPECTED_OUTPUT"] = _stage_expected_output(stage)
        env["CHATGPT_MODEL"] = str(requested_model)
        env["BROWSER_AGENT_HEADLESS"] = "true" if self.headless else "false"
        env["BROWSER_AGENT_SESSION_REUSE"] = "true" if self.session_reuse else "false"
        env["SOLAR_BROWSER_SESSION_REUSE"] = env["BROWSER_AGENT_SESSION_REUSE"]
        env["BROWSER_AGENT_SESSION_LINEAGE"] = self._session_lineage(stage=stage, run_id=run_id, chapter_id=chapter_id)
        env["SOLAR_BROWSER_SESSION_LINEAGE"] = env["BROWSER_AGENT_SESSION_LINEAGE"]
        env["BROWSER_AGENT_CHATGPT_PROJECT_NAME"] = self.project_name
        if self.target_account_email:
            env["BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL"] = self.target_account_email
            env["BROWSER_AGENT_TARGET_ACCOUNT_EMAIL"] = self.target_account_email
        if self.profile_directory:
            env["BROWSER_AGENT_PROFILE_DIRECTORY"] = self.profile_directory

        prompt = _render_stage_prompt(stage, payload)
        proc = subprocess.run(
            [self.python_executable, str(self.operator_script)],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=env,
        )
        (request_dir / "provider.stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (request_dir / "provider.stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        if proc.returncode != 0:
            combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            raise RuntimeError(f"chatgpt_report_operator_failed rc={proc.returncode}: {combined[-1600:]}")

        text = str(proc.stdout or "").strip()
        if not text:
            text = str((request_dir / "assistant-response.txt").read_text(encoding="utf-8")).strip() if (request_dir / "assistant-response.txt").exists() else ""
        submitted = _load_json(request_dir / "submitted-run.json")
        page = _load_json(request_dir / "page.json")
        conversation = _load_json(request_dir / "conversation.json")
        browser_session_id = (
            str(submitted.get("conversation_id") or "").strip()
            or str(page.get("conversation_id") or "").strip()
            or str(conversation.get("conversation_id") or "").strip()
            or str(submitted.get("task_id") or "").strip()
            or f"{stage}-{uuid4().hex[:12]}"
        )
        chatgpt_url = (
            str(submitted.get("url") or "").strip()
            or str(page.get("url") or "").strip()
            or str(conversation.get("url") or "").strip()
            or "about:blank"
        )
        model_call_id = str(submitted.get("task_id") or "").strip() or f"{stage}-{uuid4().hex}"
        return {
            "schema_version": "chatgpt_report_operator_provider.v1",
            "model_call_id": model_call_id,
            "browser_session_id": browser_session_id,
            "chatgpt_url": chatgpt_url,
            "resolved_model": str(requested_model),
            "status": "succeeded",
            "text": text,
            "request_dir": str(request_dir),
            "task_id": str(submitted.get("task_id") or ""),
        }


class YoutubeTranscriptExtractor:
    """Production adapter for the YouTube transcript browser-agent operator.

    The report BrowserAgentClient below is for ChatGPT report planning/writing.
    Transcript capture is a separate logical operator; this adapter exposes it
    from the AI Influence YouTube module while reusing the existing operator
    implementation instead of duplicating browser automation.
    """

    def __init__(
        self,
        *,
        operator_script: str | Path | None = None,
        python_executable: str | Path | None = None,
        target_account_email: str | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        self.operator_script = Path(operator_script or root / "tools" / "youtube_transcript_operator.py")
        self.python_executable = str(python_executable or sys.executable)
        self.target_account_email = target_account_email

    def extract(
        self,
        youtube_url: str,
        *,
        task_dir: str | Path,
        timeout_seconds: int = 300,
        max_retries: int = 1,
        output_format: str = "timestamped",
        headless: bool = True,
    ) -> dict[str, Any]:
        url = str(youtube_url or "").strip()
        if not url:
            raise RuntimeError("YoutubeTranscriptExtractor requires youtube_url")
        if not self.operator_script.exists():
            raise RuntimeError(f"YouTube transcript operator not found: {self.operator_script}")

        run_dir = Path(task_dir).expanduser()
        run_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = run_dir / "envelope.json"
        envelope_path.write_text(
            json.dumps(
                {
                    "operator_id": "mini-youtube-transcript-extractor",
                    "youtube_url": url,
                    "timeout_seconds": max(int(timeout_seconds), 300),
                    "max_retries": int(max_retries),
                    "output_format": output_format,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["SOLAR_OPERATOR_ENVELOPE_JSON"] = str(envelope_path)
        env["TASK_DIR"] = str(run_dir)
        env.setdefault("BROWSER_AGENT_HEADLESS", "true" if headless else "false")
        if self.target_account_email:
            env["BROWSER_AGENT_TARGET_ACCOUNT_EMAIL"] = self.target_account_email

        proc = subprocess.run(
            [self.python_executable, str(self.operator_script)],
            env=env,
            text=True,
            capture_output=True,
            timeout=max(int(timeout_seconds), 300) + 60,
        )
        (run_dir / "operator.stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (run_dir / "operator.stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        result_path = run_dir / "youtube-transcript-result.json"
        if proc.returncode != 0 or not result_path.exists():
            combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            raise RuntimeError(f"browser transcript operator failed rc={proc.returncode}: {combined[-1200:]}")
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("youtube-transcript-result.json must contain a JSON object")
        return payload


class BrowserAgentClient:
    def __init__(self, provider: BrowserAgentProvider, *, ledger_path: str | Path, sprint_id: str) -> None:
        self.provider = provider
        self.ledger_path = Path(ledger_path)
        self.sprint_id = sprint_id
        self._chapter_calls: set[str] = set()

    def _call(self, stage: str, payload: dict[str, Any], *, requested_model: str, run_id: str, chapter_id: str = "") -> dict[str, Any]:
        if requested_model.lower() in {"qwen", "qwen3.6", "thunderomlx", "local"}:
            raise LocalModelSubstitutionError("local model substitution is forbidden for judgment-bearing phases")
        started = time.time()
        result = self.provider.call(
            stage,
            payload,
            requested_model=requested_model,
            run_id=run_id,
            chapter_id=chapter_id,
            sprint_id=self.sprint_id,
        )
        latency_ms = int((time.time() - started) * 1000)
        call_id = str(result.get("model_call_id") or f"call_{uuid4().hex}")
        append_model_call_ledger(self.ledger_path, {
            "schema_version": "model_call_ledger.v1",
            "call_id": call_id,
            "stage": stage,
            "cost_estimate_usd": float(result.get("cost_estimate_usd", 0.0)),
            "sprint_id": self.sprint_id,
            "browser_session_id": str(result.get("browser_session_id", "fake-session")),
            "chatgpt_url": str(result.get("chatgpt_url", "about:blank")),
            "latency_ms": latency_ms,
            "run_id": run_id,
            "chapter_id": chapter_id,
            "requested_model": requested_model,
            "resolved_model": str(result.get("resolved_model", requested_model)),
            "status": str(result.get("status", "succeeded")),
        })
        result["model_call_id"] = call_id
        return result

    def plan(self, corpus: dict[str, Any], *, requested_model: str, run_id: str) -> dict[str, Any]:
        return self._call("phase1", corpus, requested_model=requested_model, run_id=run_id)

    def write_chapter(self, chapter_spec: dict[str, Any], *, requested_model: str, run_id: str, chapter_id: str) -> dict[str, Any]:
        if chapter_id in self._chapter_calls:
            raise ValueError(f"duplicate phase2 chapter call: {chapter_id}")
        self._chapter_calls.add(chapter_id)
        return self._call("phase2", chapter_spec, requested_model=requested_model, run_id=run_id, chapter_id=chapter_id)

    def write_chapter_batch(
        self,
        chapter_specs: list[dict[str, Any]],
        *,
        requested_model: str,
        run_id: str,
        batch_id: str,
    ) -> dict[str, Any]:
        chapter_ids: list[str] = []
        for item in chapter_specs:
            chapter = item.get("chapter") if isinstance(item, dict) else {}
            chapter_id = str((chapter or {}).get("chapter_id") or "").strip()
            if not chapter_id:
                raise ValueError("phase2_batch_missing_chapter_id")
            if chapter_id in self._chapter_calls:
                raise ValueError(f"duplicate phase2 chapter call: {chapter_id}")
            chapter_ids.append(chapter_id)
        self._chapter_calls.update(chapter_ids)
        return self._call(
            "phase2_batch",
            {"chapters": chapter_specs},
            requested_model=requested_model,
            run_id=run_id,
            chapter_id=batch_id,
        )

    def synthesize(self, chapter_outputs: list[dict[str, Any]], *, requested_model: str, run_id: str) -> dict[str, Any]:
        return self._call("phase3", {"chapters": chapter_outputs}, requested_model=requested_model, run_id=run_id)
