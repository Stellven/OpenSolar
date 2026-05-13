#!/usr/bin/env python3
"""Inject runtime context projection into a dispatch file.

This bridges the default tmux dispatch path with the managed-agent runtime:
the worker-visible prompt receives a bounded context projection, and the same
projection is appended to the session log as a durable `context_injected` event.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

from context_projection import ContextProjection

START = "<solar-runtime-context>"
END = "</solar-runtime-context>"


def _derive_query(text: str, explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()[:500]
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:500] or "solar harness runtime context"


def inject(
    path: Path,
    *,
    session_id: str,
    pane: str = "unknown",
    dispatch_id: str = "",
    query: str = "",
    budget_tokens: int = 1800,
) -> dict[str, Any]:
    original = path.read_text(encoding="utf-8", errors="replace")
    effective_query = _derive_query(original, query)
    cp = ContextProjection(session_id)
    context_text = cp.build_context_text(
        query=effective_query,
        budget_tokens=budget_tokens,
        policy_name="dispatch-default",
    )
    recorded = cp.record_context_injected(
        query=effective_query,
        policy_name="dispatch-default",
        budget_tokens=budget_tokens,
        actor="coordinator",
        activity_id=dispatch_id or None,
        correlation_id=dispatch_id or None,
        source="runtime_context_inject",
    )

    changed = False
    if START not in original:
        block = (
            f"{START}\n"
            "规则: 这是从 append-only session log + unified KB recall 生成的运行时投影；"
            "它是当前模型工作集，不是事实源。\n"
            f"pane: {pane} | dispatch_id: {dispatch_id or 'N/A'} | session_id: {session_id}\n\n"
            f"{context_text}\n"
            f"{END}\n\n"
        )
        path.write_text(block + original, encoding="utf-8")
        changed = True

    evidence = {
        "ok": True,
        "dispatch_file": str(path),
        "session_id": session_id,
        "pane": pane,
        "dispatch_id": dispatch_id,
        "query": effective_query,
        "changed": changed,
        "context_event_id": recorded.get("event_id"),
        "duplicate": recorded.get("duplicate", False),
        "kb_hit_count": len((recorded.get("payload") or {}).get("kb_hits") or []),
        "included_event_count": len((recorded.get("payload") or {}).get("included_event_ids") or []),
    }
    sidecar = path.with_suffix(path.suffix + ".runtime-context.json")
    sidecar.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="inject runtime context projection into dispatch file")
    parser.add_argument("dispatch_file")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--pane", default="unknown")
    parser.add_argument("--dispatch-id", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--budget-tokens", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    evidence = inject(
        Path(args.dispatch_file),
        session_id=args.session_id,
        pane=args.pane,
        dispatch_id=args.dispatch_id,
        query=args.query,
        budget_tokens=args.budget_tokens,
    )
    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
