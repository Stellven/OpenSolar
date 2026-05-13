"""Solar Harness — Context Projection Policy.

Builds model-visible context views from session events and optional
KB hits. Context is a projection, never a source of truth — it
never deletes or rewrites session events.

Provenance tracks: included event IDs, summarized event ranges,
dropped event ranges, and KB/knowledge hits.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from runtime_interfaces import ContextView
from session_log import SessionLog

HARNESS_DIR = os.path.expanduser("~/.solar/harness")

# Default secret patterns for redaction
_SECRET_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[=:]\s*\S+"),
    re.compile(r"(?i)token\s*[=:]\s*\S{8,}"),
    re.compile(r"(?i)password\s*[=:]\s*\S+"),
    re.compile(r"(?i)secret\s*[=:]\s*\S+"),
    re.compile(r"(?i)credential\s*[=:]\s*\S+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    re.compile(r"sk-[0-9a-zA-Z]{20,}"),
]

# Event types that are always included in context
_HIGH_VALUE_TYPES = frozenset({
    "command_issued", "activity_started", "activity_succeeded",
    "activity_failed", "activity_handoff", "state_transition",
    "human_feedback", "context_injected",
})

# Event types that can be summarized/dropped to save tokens
_LOW_VALUE_TYPES = frozenset({
    "log_message", "activity_retry_scheduled",
})


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _redact_secrets(text: str) -> str:
    result = text
    for pat in _SECRET_PATTERNS:
        result = pat.sub("[REDACTED]", result)
    return result


class ContextProjection:
    """Builds model-visible context from session events."""

    def __init__(
        self,
        session_id: str,
        *,
        harness_dir: Optional[str] = None,
    ) -> None:
        self.session_id = session_id
        self._harness_dir = harness_dir or HARNESS_DIR
        self._log = SessionLog(session_id, harness_dir=harness_dir)

    def build_context(
        self,
        *,
        policy_name: str = "default",
        query: Optional[str] = None,
        budget_tokens: Optional[int] = None,
    ) -> ContextView:
        """Build a ContextView from session events.

        The view includes:
        - included_event_ids: events that are included verbatim
        - summarized_ranges: ranges of events that were summarized
        - dropped_ranges: ranges of events that were dropped entirely
        - kb_hits: (placeholder for future KB integration)
        """
        budget = budget_tokens or 8000  # default ~32K chars
        events = self._log.all_events()
        if not events:
            return ContextView(
                session_id=self.session_id,
                policy_name=policy_name,
                built_at=_now_ts(),
                budget_tokens=budget,
            )

        included_ids: List[str] = []
        included_events: List[Dict[str, Any]] = []
        summarized_ranges: List[Dict[str, Any]] = []
        dropped_ranges: List[Dict[str, Any]] = []
        total_tokens = 0

        # Phase 1: Include high-value events, summarize/drop low-value
        current_summary_start: Optional[int] = None
        current_summary_events: List[Dict[str, Any]] = []

        for ev in events:
            etype = ev.get("type", "")
            event_json = json.dumps(ev, ensure_ascii=False)
            event_tokens = _estimate_tokens(event_json)
            is_high_value = etype in _HIGH_VALUE_TYPES
            is_low_value = etype in _LOW_VALUE_TYPES

            if is_low_value:
                # Summarize low-value events
                if current_summary_start is None:
                    current_summary_start = ev.get("seq", 0)
                current_summary_events.append(ev)
                continue

            # Flush any pending summary range
            if current_summary_events:
                summarized_ranges.append({
                    "start_seq": current_summary_start,
                    "end_seq": current_summary_events[-1].get("seq", 0),
                    "summary": f"{len(current_summary_events)} {current_summary_events[0].get('type', 'log')} events summarized",
                    "event_count": len(current_summary_events),
                })
                current_summary_start = None
                current_summary_events = []

            if is_high_value:
                if total_tokens + event_tokens <= budget:
                    included_ids.append(ev.get("event_id", ""))
                    included_events.append(ev)
                    total_tokens += event_tokens
                else:
                    # Budget exceeded — drop remaining
                    break
            else:
                # Medium-value events: include if budget allows
                if total_tokens + event_tokens <= budget * 0.8:
                    included_ids.append(ev.get("event_id", ""))
                    included_events.append(ev)
                    total_tokens += event_tokens
                # else: silently drop (no range tracking for medium-value)

        # Flush final summary range
        if current_summary_events:
            summarized_ranges.append({
                "start_seq": current_summary_start,
                "end_seq": current_summary_events[-1].get("seq", 0),
                "summary": f"{len(current_summary_events)} {current_summary_events[0].get('type', 'log')} events summarized",
                "event_count": len(current_summary_events),
            })

        # Track dropped ranges (events after budget cutoff)
        if events and included_events:
            last_included_seq = included_events[-1].get("seq", 0)
            last_event_seq = events[-1].get("seq", 0)
            if last_event_seq > last_included_seq:
                dropped_ranges.append({
                    "start_seq": last_included_seq + 1,
                    "end_seq": last_event_seq,
                    "reason": "budget exceeded",
                })

        # Phase 2: Build text from included events
        included_event_data = []
        for ev in included_events:
            payload = ev.get("payload", {})
            event_text = json.dumps({
                "seq": ev.get("seq"),
                "type": ev.get("type"),
                "actor": ev.get("actor"),
                "activity_id": ev.get("activity_id"),
                "payload": payload,
            }, ensure_ascii=False)
            included_event_data.append(_redact_secrets(event_text))

        # Phase 3: KB hits (placeholder — actual KB integration would
        # call solar-harness mirage search here)
        kb_hits: List[Dict[str, Any]] = []
        if query:
            kb_hits.append({
                "source": "solar-harness",
                "query": query,
                "title": "context projection query",
                "relevance_score": 0.0,
                "note": "KB integration placeholder — real hits require mirage",
            })

        return ContextView(
            session_id=self.session_id,
            included_event_ids=included_ids,
            summarized_ranges=summarized_ranges,
            dropped_ranges=dropped_ranges,
            kb_hits=kb_hits,
            token_estimate=total_tokens,
            budget_tokens=budget,
            policy_name=policy_name,
            built_at=_now_ts(),
            _included_event_data=included_event_data,
        )

    def build_context_text(
        self,
        *,
        policy_name: str = "default",
        query: Optional[str] = None,
        budget_tokens: Optional[int] = None,
    ) -> str:
        """Build a text representation of the context view."""
        view = self.build_context(
            policy_name=policy_name,
            query=query,
            budget_tokens=budget_tokens,
        )

        parts = [
            f"# Context Projection: {view.session_id}",
            f"Policy: {view.policy_name} | "
            f"Tokens: ~{view.token_estimate}/{view.budget_tokens or 'unlimited'} | "
            f"Built: {view.built_at}",
        ]

        if view.included_event_ids:
            parts.append(f"\n## Included Events ({len(view.included_event_ids)})")
            parts.append(f"Event IDs: {', '.join(view.included_event_ids[:20])}")

            # Include redacted event data for model consumption
            event_data = getattr(view, '_included_event_data', [])
            if event_data:
                parts.append("\n### Event Details (redacted)")
                for ed in event_data[:50]:  # cap at 50 events
                    parts.append(f"```json\n{ed}\n```")

        if view.summarized_ranges:
            parts.append("\n## Summarized Ranges")
            for sr in view.summarized_ranges:
                parts.append(
                    f"- seq {sr['start_seq']}-{sr['end_seq']}: "
                    f"{sr['summary']}"
                )

        if view.dropped_ranges:
            parts.append("\n## Dropped Ranges")
            for dr in view.dropped_ranges:
                parts.append(
                    f"- seq {dr['start_seq']}-{dr['end_seq']}: {dr['reason']}"
                )

        if view.kb_hits:
            parts.append("\n## Knowledge Base Hits")
            for hit in view.kb_hits:
                parts.append(f"- [{hit['source']}] {hit.get('title', '')}")

        parts.append("\n## Provenance")
        parts.append("This context is a projection over session events.")
        parts.append("It does not modify or replace the source event log.")
        parts.append(f"Total events in session: see SessionLog.replay()")

        text = "\n".join(parts)
        return _redact_secrets(text)
