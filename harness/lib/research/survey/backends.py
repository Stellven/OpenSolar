"""Pluggable writer backends for survey section production."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SurveyWriterBackend(Protocol):
    """Minimal interface for section writer implementations."""

    name: str

    def write(self, prompt_packet: dict, fallback_text: str) -> str:
        """Return a section draft from a prompt packet."""


@dataclass
class DeterministicSurveyWriterBackend:
    """Built-in backend used for local/offline verification."""

    name: str = "deterministic"

    def write(self, prompt_packet: dict, fallback_text: str) -> str:
        return fallback_text


def get_writer_backend(name: str | None = None) -> SurveyWriterBackend:
    normalized = (name or "deterministic").strip().lower()
    if normalized == "deterministic":
        return DeterministicSurveyWriterBackend()
    raise ValueError(f"unsupported_survey_writer_backend:{normalized}")
