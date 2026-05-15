"""Pluggable writer backends for survey section production."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SurveyWriterBackend(Protocol):
    """Minimal interface for section writer implementations."""

    name: str

    def write(self, prompt_packet: dict, fallback_text: str) -> str:
        """Return a section draft from a prompt packet."""


class HumanResponseMissingError(RuntimeError):
    """Raised when a human-packet backend has no response artifact yet."""

    def __init__(self, response_path: str) -> None:
        super().__init__(f"human_response_missing:{response_path}")
        self.response_path = response_path


class LocalCommandWriterError(RuntimeError):
    """Raised when a local command writer cannot produce a draft."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"local_command_writer_failed:{reason}")
        self.reason = reason


@dataclass
class DeterministicSurveyWriterBackend:
    """Built-in backend used for local/offline verification."""

    name: str = "deterministic"

    def write(self, prompt_packet: dict, fallback_text: str) -> str:
        return fallback_text


@dataclass
class HumanPacketSurveyWriterBackend:
    """Backend that consumes an externally written Markdown response."""

    name: str = "human-packet"
    allow_fallback: bool = False

    def write(self, prompt_packet: dict, fallback_text: str) -> str:
        response_path = str((prompt_packet.get("artifact_paths") or {}).get("human_response") or "")
        if not response_path:
            raise HumanResponseMissingError("N/A")
        path = Path(response_path).expanduser()
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            if self.allow_fallback:
                return fallback_text
            raise HumanResponseMissingError(str(path))
        return path.read_text(encoding="utf-8")


@dataclass
class LocalCommandSurveyWriterBackend:
    """Backend that pipes prompt packet JSON to a local command."""

    command: str
    timeout_seconds: int = 120
    name: str = "local-command"

    def write(self, prompt_packet: dict, fallback_text: str) -> str:
        if not self.command.strip():
            raise LocalCommandWriterError("missing_command")
        payload = json.dumps(prompt_packet, ensure_ascii=False)
        try:
            result = subprocess.run(
                self.command,
                input=payload,
                text=True,
                shell=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LocalCommandWriterError(f"timeout:{self.timeout_seconds}") from exc
        if result.returncode != 0:
            stderr = (result.stderr or "").strip().replace("\n", " ")[:500]
            raise LocalCommandWriterError(f"exit_{result.returncode}:{stderr}")
        output = (result.stdout or "").strip()
        if not output:
            raise LocalCommandWriterError("empty_stdout")
        return output + "\n"


def get_writer_backend(
    name: str | None = None,
    *,
    local_command: str = "",
    timeout_seconds: int = 120,
) -> SurveyWriterBackend:
    normalized = (name or "deterministic").strip().lower()
    if normalized == "deterministic":
        return DeterministicSurveyWriterBackend()
    if normalized == "human-packet":
        return HumanPacketSurveyWriterBackend()
    if normalized in {"human-packet-fallback", "human-fallback"}:
        return HumanPacketSurveyWriterBackend(name="human-packet-fallback", allow_fallback=True)
    if normalized in {"local-command", "local-llm-command", "command"}:
        return LocalCommandSurveyWriterBackend(command=local_command, timeout_seconds=timeout_seconds)
    raise ValueError(f"unsupported_survey_writer_backend:{normalized}")
