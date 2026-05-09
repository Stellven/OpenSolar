#!/usr/bin/env python3
"""Solar unified context injector.

Routes agent context through Mirage search, which fans out to safe filesystem
mounts, QMD, and Solar DB. Output is bounded and fail-open so it is safe for
Claude hooks, Codex startup instructions, and Solar dispatch prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


HOME = Path.home()
HARNESS = Path(os.environ.get("HARNESS_DIR", str(HOME / ".solar" / "harness")))
MIRAGE = HARNESS / "lib" / "solar_mirage.py"
DEFAULT_MAX_CHARS = int(os.environ.get("SOLAR_CONTEXT_MAX_CHARS", "2600"))
DEFAULT_MAX_HITS = int(os.environ.get("SOLAR_CONTEXT_MAX_HITS", "8"))
DEFAULT_TIMEOUT_MS = int(os.environ.get("SOLAR_CONTEXT_TIMEOUT_MS", "2500"))


def _run_mirage(query: str, max_hits: int, max_chars: int, timeout_ms: int) -> dict:
    if not MIRAGE.exists():
        return {"hits": [], "degraded_sources": ["mirage:missing"], "query": query}
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(MIRAGE),
                "search",
                query,
                "--json",
                "--max-hits",
                str(max_hits),
                "--max-chars",
                str(max_chars),
            ],
            text=True,
            capture_output=True,
            timeout=max(1.0, timeout_ms / 1000.0),
        )
    except subprocess.TimeoutExpired:
        return {"hits": [], "degraded_sources": ["mirage:timeout"], "query": query}
    except Exception as exc:
        return {"hits": [], "degraded_sources": [f"mirage:error:{type(exc).__name__}"], "query": query}
    if proc.returncode != 0:
        return {
            "hits": [],
            "degraded_sources": ["mirage:nonzero"],
            "query": query,
            "stderr": proc.stderr[-500:],
        }
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"hits": [], "degraded_sources": ["mirage:bad_json"], "query": query}
    data.setdefault("query", query)
    return data


def _compact_hit(hit: dict) -> dict:
    path = hit.get("path") or ""
    mount = hit.get("mount") or ""
    source_type = hit.get("source_type") or ""
    return {
        "source": source_type,
        "mount": mount,
        "path": path,
        "title": hit.get("title") or path.rsplit("/", 1)[-1],
        "snippet": (hit.get("snippet") or "")[:450],
        "provenance": hit.get("provenance") or "",
        "score": hit.get("score_or_rank", 0),
    }


def retrieve(query: str, max_hits: int, max_chars: int, timeout_ms: int) -> dict:
    started = time.monotonic()
    data = _run_mirage(query, max_hits=max_hits, max_chars=max_chars, timeout_ms=timeout_ms)
    if not data.get("hits") and any("\u4e00" <= ch <= "\u9fff" for ch in query):
        fallback_query = "obsidian wiki integration solar harness"
        data = _run_mirage(fallback_query, max_hits=max_hits, max_chars=max_chars, timeout_ms=timeout_ms)
        data["fallback_query"] = fallback_query
    hits = [_compact_hit(h) for h in data.get("hits", []) if isinstance(h, dict)]
    if not hits:
        hits = [
            {
                "source": "default",
                "mount": "/knowledge",
                "path": "/Users/sihaoli/Knowledge",
                "title": "Solar Obsidian Vault",
                "snippet": "本机默认知识库。优先用 `solar-harness wiki qmd-search \"<query>\" --json` 或 `solar-harness mirage search \"<query>\" --json` 检索。",
                "provenance": "static:solar-unified-context",
                "score": 0.1,
            },
            {
                "source": "default",
                "mount": "/qmd",
                "path": "qmd://solar-wiki",
                "title": "QMD solar-wiki",
                "snippet": "MinerU Document Explorer 负责 PDF/Markdown/文档索引和语义检索；后台 `solar-harness wiki qmd-embed status` 处理 embedding backlog。",
                "provenance": "static:solar-unified-context",
                "score": 0.1,
            },
            {
                "source": "default",
                "mount": "/solar_db",
                "path": str(HOME / ".solar" / "solar.db"),
                "title": "Solar DB",
                "snippet": "Solar DB 保存 sprint、cortex、accepted artifacts、obsidian_vault_index 和 FTS 索引。设计/开发前先查已有资产，避免重复造轮子。",
                "provenance": "static:solar-unified-context",
                "score": 0.1,
            },
        ][:max_hits]
    priority = {"qmd": 0, "solar_db": 1, "mirage_path": 2}
    hits.sort(key=lambda h: (priority.get(h.get("source", ""), 9), -float(h.get("score") or 0)))
    total = 0
    kept = []
    for hit in hits:
        payload = f"{hit['source']} {hit['path']} {hit['snippet']}"
        if total + len(payload) > max_chars:
            break
        kept.append(hit)
        total += len(payload)
    return {
        "query": query,
        "hits": kept,
        "degraded_sources": data.get("degraded_sources", []),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        "total_chars": total,
        "backend": "mirage+qmd+solar_db+obsidian",
    }


def format_hook(data: dict, max_chars: int) -> str:
    hits = data.get("hits") or []
    if not hits:
        return ""
    lines = [
        "<solar-unified-context>",
        "来源: Mirage + QMD solar-wiki + Obsidian Vault + Solar DB",
        "规则: 开始开发/设计/分析前，优先参考这些命中；如不足，再主动搜索 vault/qmd。",
    ]
    total = sum(len(x) for x in lines)
    for hit in hits:
        path = str(hit.get("path") or "")
        mount = "" if "://" in path or path.startswith(str(HOME)) else str(hit.get("mount") or "")
        entry = f"- [{hit.get('source')}] {hit.get('title') or 'N/A'} ({mount}{path}): {hit.get('snippet')}"
        if total + len(entry) > max_chars:
            break
        lines.append(entry)
        total += len(entry)
    degraded = data.get("degraded_sources") or []
    if degraded:
        lines.append("降级源: " + ", ".join(str(x) for x in degraded[:5]))
    lines.append("</solar-unified-context>")
    return "\n".join(lines)


def format_markdown(data: dict, max_chars: int) -> str:
    text = format_hook(data, max_chars)
    if not text:
        return "没有命中统一知识上下文。"
    return text.replace("<solar-unified-context>", "## Solar Unified Context").replace("</solar-unified-context>", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Solar unified knowledge context")
    parser.add_argument("--query", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=("hook", "markdown"), default="hook")
    parser.add_argument("--max-hits", type=int, default=DEFAULT_MAX_HITS)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    parser.add_argument("--fail-open", action="store_true")
    args = parser.parse_args()

    try:
        data = retrieve(args.query, args.max_hits, args.max_chars, args.timeout_ms)
    except Exception as exc:
        if args.fail_open:
            data = {"query": args.query, "hits": [], "degraded_sources": [str(exc)], "backend": "error"}
        else:
            raise

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(data, args.max_chars))
    else:
        text = format_hook(data, args.max_chars)
        if text:
            print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
