"""Pluggable writer backends for survey section production."""

from __future__ import annotations

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


def get_writer_backend(name: str | None = None) -> SurveyWriterBackend:
    normalized = (name or "deterministic").strip().lower()
    if normalized == "deterministic":
        return DeterministicSurveyWriterBackend()
    if normalized == "human-packet":
        return HumanPacketSurveyWriterBackend()
    if normalized in {"human-packet-fallback", "human-fallback"}:
        return HumanPacketSurveyWriterBackend(name="human-packet-fallback", allow_fallback=True)
    raise ValueError(f"unsupported_survey_writer_backend:{normalized}")
