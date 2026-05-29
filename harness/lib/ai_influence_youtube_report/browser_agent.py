"""Browser Agent wrapper contract for ChatGPT 5.5 Thinking high.

This module defines the seam and fake-provider behavior for tests. It does not
call ChatGPT directly; production integration is injected through provider.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from .ledger import append_model_call_ledger


class BrowserAgentProvider(Protocol):
    def call(self, stage: str, payload: dict[str, Any], *, requested_model: str) -> dict[str, Any]: ...


class LocalModelSubstitutionError(RuntimeError):
    pass


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
        result = self.provider.call(stage, payload, requested_model=requested_model)
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

    def synthesize(self, chapter_outputs: list[dict[str, Any]], *, requested_model: str, run_id: str) -> dict[str, Any]:
        return self._call("phase3", {"chapters": chapter_outputs}, requested_model=requested_model, run_id=run_id)
