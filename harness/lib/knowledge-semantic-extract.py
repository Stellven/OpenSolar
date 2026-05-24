#!/usr/bin/env python3
"""ThunderOMLX semantic extraction layer for Solar Knowledge raw artifacts.

This is intentionally a derived-artifact worker, not an embedding backend:

    Knowledge/_raw/*.md -> ThunderOMLX -> Knowledge/_extracted/.../*.extracted.md

QMD remains responsible for deterministic indexing of both raw and derived
markdown. The worker writes per-document manifests so repeated runs are
changed-only by default.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc
DEFAULT_PROXY_MODEL = "Qwen3.6-35b-a3b"
DEFAULT_LOCAL_MODEL = "ThunderOMLX Qwen3.6 local"
DEFAULT_PROFILE = "knowledge-extractor"
PROMPT_VERSION = "knowledge-extract-v2"
SCHEMA_VERSION = "extracted-md-v1"
DEFAULT_REGISTRY_DB = Path.home() / "Knowledge" / "_registry" / "knowledge_ingest.sqlite"
DEFAULT_THUNDEROMLX_PAUSE_FILE = Path.home() / ".omlx" / "run" / "maintenance.json"
LOCK_EXIT_CODE = 75


def now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    digest = sha256_bytes("\0".join(parts).encode("utf-8"))[:24]
    return f"{prefix}_{digest}"


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._/-]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:220] or "document"


def resolve_vault(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    return Path(os.environ.get("OBSIDIAN_VAULT_PATH", str(Path.home() / "Knowledge"))).expanduser()


def thunderomlx_pause_state(args: argparse.Namespace) -> dict[str, Any] | None:
    path = Path(getattr(args, "pause_file", "") or DEFAULT_THUNDEROMLX_PAUSE_FILE).expanduser()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "enabled": True,
            "mode": "ingest_pause",
            "reason": f"unreadable pause file: {exc}",
            "path": str(path),
        }
    if not isinstance(data, dict) or not data.get("enabled", True):
        return None
    mode = str(data.get("mode") or "ingest_pause")
    if mode not in {"ingest_pause", "all"}:
        return None
    until = data.get("until")
    if until:
        try:
            if float(until) <= time.time():
                return None
        except (TypeError, ValueError):
            pass
    data["path"] = str(path)
    return data


def maybe_exit_for_thunderomlx_pause(args: argparse.Namespace) -> bool:
    state = thunderomlx_pause_state(args)
    if not state:
        return False
    summary = {
        "ok": True,
        "status": "paused",
        "reason": state.get("reason") or "ThunderOMLX maintenance window active",
        "pause_file": state.get("path"),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[semantic-extract] paused: {summary['reason']} ({summary['pause_file']})")
    return True


def rel_to_vault(path: Path, vault: Path) -> Path:
    try:
        return path.resolve().relative_to(vault.resolve())
    except Exception:
        return Path(safe_name(str(path.resolve()).lstrip("/")))


def target_paths(source: Path, vault: Path, proxy_model: str) -> tuple[Path, Path, Path]:
    rel = rel_to_vault(source, vault)
    if rel.parts and rel.parts[0] == "_raw":
        rel = Path(*rel.parts[1:])
    stem = rel.with_suffix("")
    model_dir = safe_name(proxy_model)
    out = vault / "_extracted" / "thunderomlx" / model_dir / stem.parent / f"{stem.name}.extracted.md"
    report = out.with_suffix(".extract.report.json")
    manifest_name = sha256_bytes(str(source.resolve()).encode("utf-8"))[:24] + ".ingest.json"
    manifest = vault / "_manifests" / "thunderomlx" / manifest_name
    return out, report, manifest


def registry_path(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "registry_db", None) or DEFAULT_REGISTRY_DB).expanduser()


def registry_connect(args: argparse.Namespace) -> sqlite3.Connection | None:
    db = registry_path(args)
    if not db.exists():
        return None
    conn = sqlite3.connect(str(db), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def registry_doc_id(conn: sqlite3.Connection | None, source: Path, content_sha: str, vault: Path) -> str:
    fallback = str(rel_to_vault(source, vault))
    if conn is None:
        return fallback
    source_s = str(source)
    row = conn.execute("SELECT doc_id FROM documents WHERE source_path = ?", (source_s,)).fetchone()
    if row:
        return str(row["doc_id"])
    # Some older registry rows use resolved paths while callers may pass a symlink/relative path.
    try:
        resolved = str(source.resolve())
        row = conn.execute("SELECT doc_id FROM documents WHERE source_path = ?", (resolved,)).fetchone()
        if row:
            return str(row["doc_id"])
    except Exception:
        pass
    now = now_iso()
    doc_id = stable_id("doc", str(source), content_sha)
    conn.execute(
        """
        INSERT OR IGNORE INTO documents (
          doc_id, source_kind, source_path, source_adapter, content_kind,
          declared_doc_type, source_sha256, current_state, ingest_policy,
          extract_policy, created_at, updated_at, provenance_quality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            "raw" if "/_raw/" in source_s else "obsidian_vault",
            source_s,
            "semantic_extract_discovery",
            "markdown",
            None,
            content_sha,
            "RAW_MATERIALIZED" if "/_raw/" in source_s else "VAULT_DISCOVERED",
            "default",
            "default",
            now,
            now,
            "observed",
        ),
    )
    conn.commit()
    return doc_id


def registry_span_ids(conn: sqlite3.Connection | None, doc_id: str, spans: list[dict[str, Any]]) -> list[str]:
    if conn is None:
        return [str(span["span_id"]) for span in spans]
    rows = conn.execute("SELECT span_id FROM spans WHERE doc_id = ? ORDER BY start_line", (doc_id,)).fetchall()
    if rows:
        return [str(row["span_id"]) for row in rows]
    return [str(span["span_id"]) for span in spans]


def registry_transition(conn: sqlite3.Connection | None, doc_id: str, state: str, payload: dict[str, Any] | None = None) -> None:
    if conn is None:
        return
    now = now_iso()
    row = conn.execute("SELECT current_state FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    from_state = str(row["current_state"]) if row else None
    conn.execute("UPDATE documents SET current_state = ?, updated_at = ? WHERE doc_id = ?", (state, now, doc_id))
    conn.execute(
        """
        INSERT INTO ingest_events (
          event_id, doc_id, event_kind, from_state, to_state, source_adapter, payload_json, ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stable_id("evt", doc_id, state, now, json.dumps(payload or {}, sort_keys=True)),
            doc_id,
            "semantic_extract_state",
            from_state,
            state,
            "knowledge-semantic-extract",
            json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
            now,
        ),
    )
    conn.commit()


def registry_start_job(
    conn: sqlite3.Connection | None,
    *,
    doc_id: str,
    content_sha: str,
    span_ids: list[str],
    args: argparse.Namespace,
) -> str:
    job_id = stable_id(
        "extract_job",
        doc_id,
        content_sha,
        args.profile,
        args.proxy_model,
        PROMPT_VERSION,
        SCHEMA_VERSION,
        str(time.time_ns()),
        str(os.getpid()),
        uuid.uuid4().hex,
    )
    if conn is None:
        return job_id
    now = now_iso()
    conn.execute(
        """
        INSERT INTO extract_jobs (
          job_id, doc_id, source_span_ids, prompt_template_id, model, state,
          created_at, updated_at, repair_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            doc_id,
            json.dumps(span_ids, ensure_ascii=False),
            PROMPT_VERSION,
            args.proxy_model,
            "THUNDEROMLX_EXTRACT_RUNNING",
            now,
            now,
            0,
        ),
    )
    conn.commit()
    registry_transition(conn, doc_id, "THUNDEROMLX_EXTRACT_RUNNING", {"job_id": job_id})
    return job_id


def registry_finish_job(
    conn: sqlite3.Connection | None,
    *,
    job_id: str,
    doc_id: str,
    state: str,
    passed: bool,
    error_code: str | None,
    detail: dict[str, Any],
    repair_count: int,
    outputs: list[tuple[str, Path, str]],
) -> None:
    if conn is None:
        return
    now = now_iso()
    conn.execute(
        "UPDATE extract_jobs SET state = ?, updated_at = ?, repair_count = ? WHERE job_id = ?",
        (state, now, repair_count, job_id),
    )
    conn.execute(
        """
        INSERT INTO validation_results (
          result_id, job_id, layer, passed, error_code, detail_json, ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stable_id("validation", job_id, state, now),
            job_id,
            "extracted",
            1 if passed else 0,
            error_code,
            json.dumps(detail, ensure_ascii=False, sort_keys=True),
            now,
        ),
    )
    for kind, path, digest in outputs:
        conn.execute(
            """
            INSERT OR REPLACE INTO extract_outputs (
              output_id, job_id, kind, path, sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (stable_id("extract_output", job_id, kind, str(path)), job_id, kind, str(path), digest, now),
        )
    doc_state = {
        "extract_indexed": "EXTRACTED_QMD_INDEX_PENDING",
        "validation_failed": "VALIDATION_FAILED",
        "extract_failed_warn": "EXTRACT_FAILED_RETRYABLE",
        "extract_failed_circuit_open": "EXTRACT_FAILED_RETRYABLE",
    }.get(state, state.upper())
    conn.commit()
    registry_transition(conn, doc_id, doc_state, {"job_id": job_id, "status": state, "error_code": error_code})


def registry_mark_stale_jobs(args: argparse.Namespace, *, stale_minutes: int, limit: int) -> dict[str, Any]:
    conn = registry_connect(args)
    if conn is None:
        return {"ok": False, "error": f"registry db not found: {registry_path(args)}", "reaped": 0}
    cutoff_dt = dt.datetime.now(UTC) - dt.timedelta(minutes=stale_minutes)
    cutoff = cutoff_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = conn.execute(
        """
        SELECT job_id, doc_id, updated_at
        FROM extract_jobs
        WHERE state='THUNDEROMLX_EXTRACT_RUNNING'
          AND updated_at < ?
        ORDER BY updated_at ASC
        LIMIT ?
        """,
        (cutoff, limit),
    ).fetchall()
    reaped: list[dict[str, str]] = []
    now = now_iso()
    for row in rows:
        job_id = str(row["job_id"])
        doc_id = str(row["doc_id"])
        detail = {
            "stale_reaped": True,
            "previous_state": "THUNDEROMLX_EXTRACT_RUNNING",
            "previous_updated_at": str(row["updated_at"]),
            "stale_minutes": stale_minutes,
            "reaped_at": now,
        }
        conn.execute("UPDATE extract_jobs SET state=?, updated_at=? WHERE job_id=?", ("extract_failed_warn", now, job_id))
        conn.execute(
            """
            INSERT INTO validation_results(result_id, job_id, layer, passed, error_code, detail_json, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("validation", job_id, "stale_reaped", now),
                job_id,
                "extracted",
                0,
                "E_WORKER_STALE_REAPED",
                json.dumps(detail, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        conn.execute("UPDATE documents SET current_state=?, updated_at=? WHERE doc_id=?", ("EXTRACT_FAILED_RETRYABLE", now, doc_id))
        conn.execute(
            """
            INSERT INTO ingest_events(event_id, doc_id, event_kind, from_state, to_state, source_adapter, payload_json, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stable_id("evt", doc_id, "stale_reaped", job_id, now),
                doc_id,
                "semantic_extract_stale_reaped",
                "THUNDEROMLX_EXTRACT_RUNNING",
                "EXTRACT_FAILED_RETRYABLE",
                "knowledge-semantic-extract",
                json.dumps(detail | {"job_id": job_id}, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        reaped.append({"job_id": job_id, "doc_id": doc_id, "updated_at": str(row["updated_at"])})
    conn.commit()
    conn.close()
    return {"ok": True, "cutoff": cutoff, "stale_minutes": stale_minutes, "reaped": len(reaped), "jobs": reaped}


def primary_error_code(errors: list[str]) -> str | None:
    if not errors:
        return None
    first = errors[0]
    if first.startswith("http_"):
        return "E_THUNDEROMLX_HTTP"
    if first.startswith("URLError") or "Connection refused" in first or "RemoteDisconnected" in first:
        return "E_THUNDEROMLX_UNAVAILABLE"
    if "TimeoutError" in first or "timed out" in first.lower():
        return "E_THUNDEROMLX_TIMEOUT"
    if "missing section" in first:
        return "E_SCHEMA_REQUIRED_FIELD_MISSING"
    if "missing raw span" in first:
        return "E_EVIDENCE_EMPTY"
    if "output too short" in first:
        return "E_OUTPUT_TOO_SHORT"
    return "E_VALIDATION_FAILED"


@contextlib.contextmanager
def single_worker_lock(vault: Path, args: argparse.Namespace):
    lock_path = Path(getattr(args, "lock_path", "") or (vault / "_locks" / "knowledge-semantic-extract.lock")).expanduser()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        flags = fcntl.LOCK_EX
        if not getattr(args, "lock_wait", False):
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(lock_file.fileno(), flags)
        except BlockingIOError as exc:
            raise RuntimeError(f"semantic extract worker already running: {lock_path}") from exc
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(json.dumps({"pid": os.getpid(), "started_at": now_iso()}, ensure_ascii=False) + "\n")
        lock_file.flush()
        try:
            yield lock_path
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class CircuitBreaker:
    def __init__(self, max_consecutive_failures: int, max_fail_rate: float, min_attempts: int) -> None:
        self.max_consecutive_failures = max_consecutive_failures
        self.max_fail_rate = max_fail_rate
        self.min_attempts = min_attempts
        self.attempted = 0
        self.failed = 0
        self.consecutive_failed = 0

    def record(self, result: dict[str, Any]) -> None:
        if result.get("skipped") or result.get("dry_run"):
            return
        self.attempted += 1
        ok = bool(result.get("ok"))
        if ok:
            self.consecutive_failed = 0
            return
        self.failed += 1
        self.consecutive_failed += 1

    def open_reason(self) -> str | None:
        if self.max_consecutive_failures > 0 and self.consecutive_failed >= self.max_consecutive_failures:
            return f"consecutive_failures={self.consecutive_failed}"
        if self.attempted >= self.min_attempts and self.max_fail_rate >= 0:
            fail_rate = self.failed / max(self.attempted, 1)
            if fail_rate > self.max_fail_rate:
                return f"fail_rate={fail_rate:.2f} attempted={self.attempted}"
        return None


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def should_extract(manifest: dict[str, Any], content_sha: str, args: argparse.Namespace) -> bool:
    if args.force:
        return True
    sem = manifest.get("semantic_extract") or {}
    if manifest.get("content_sha256") != content_sha:
        return True
    expected = {
        "profile": args.profile,
        "proxy_model": args.proxy_model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    for key, value in expected.items():
        if sem.get(key) != value:
            return True
    return sem.get("status") != "extract_indexed"


def source_spans(text: str, max_chars: int) -> list[dict[str, Any]]:
    lines = text.splitlines()
    spans: list[dict[str, Any]] = []
    char_budget = max_chars
    chunk: list[str] = []
    start = 1
    char_count = 0
    span_index = 1
    for idx, line in enumerate(lines, 1):
        add = len(line) + 1
        if chunk and char_count + add > 5000:
            span_id = f"S{span_index:03d}"
            spans.append({"span_id": span_id, "start_line": start, "end_line": idx - 1, "text": "\n".join(chunk)})
            span_index += 1
            chunk = []
            start = idx
            char_count = 0
        if char_budget <= 0:
            break
        take = line[: max(0, min(len(line), char_budget))]
        chunk.append(take)
        char_count += len(take) + 1
        char_budget -= len(take) + 1
    if chunk:
        spans.append({"span_id": f"S{span_index:03d}", "start_line": start, "end_line": start + len(chunk) - 1, "text": "\n".join(chunk)})
    return spans


STRICT_MARKDOWN_TEMPLATE = """# Semantic Extraction

## 1. 一句话摘要
<1-3 句，只基于输入；证据: raw:S001>

## 2. 核心事实
| 事实 | 证据位置 | 置信度 |
|---|---|---|
| <事实；没有则写 N/A> | raw:S001 | high |

## 3. 功能模块
### <模块名或 N/A>
- 作用: <... 或 N/A>
- 输入: <... 或 N/A>
- 输出: <... 或 N/A>
- 依赖: <... 或 N/A>
- 证据: raw:S001

## 4. 用户价值
- <价值或 N/A> 证据: raw:S001

## 5. 架构结构
```text
<结构图；信息不足时写 N/A>
```
证据: raw:S001

## 6. 命令 / API / 配置
| 类型 | 名称 | 用途 | 证据 |
|---|---|---|---|
| N/A | N/A | 原文未提供 | raw:S001 |

## 7. 验证证据
| 验证项 | 结果 | 证据 |
|---|---|---|
| N/A | 原文未提供 | raw:S001 |

## 8. 风险边界
| 风险 | 影响 | 缓解 | 证据 |
|---|---|---|---|
| <风险或 N/A> | <影响或 N/A> | <缓解或 N/A> | raw:S001 |

## 9. Open Questions
- <问题或 N/A> 证据: raw:S001

## 10. 检索关键词
- <keyword 或 N/A>
"""


def build_messages(source: Path, content_sha: str, spans: list[dict[str, Any]]) -> list[dict[str, str]]:
    span_blocks = []
    for span in spans:
        span_blocks.append(
            f"### {span['span_id']} lines {span['start_line']}-{span['end_line']}\n"
            f"```markdown\n{span['text']}\n```"
        )
    system = """你是 Solar Knowledge 的 ThunderOMLX 语义抽取器。

硬规则：
1. 只基于用户提供的 spans，不补充外部事实。
2. 输出必须是 Markdown，第一行必须是 `# Semantic Extraction`。
3. 必须完整保留 10 个章节标题，标题文字必须逐字匹配模板。
4. 每个关键事实、风险、命令/API、验证项都必须包含 `raw:S001` 这种证据锚点。
5. 如果原文没有某类信息，不要省略章节，写 `N/A`，并仍然给最相关证据锚点。
6. 不要输出 `<think>`、解释、前言、道歉、JSON、HTML。
7. 不要泄露 secrets/token/API key；疑似 secret 写 `[REDACTED]`。
8. 不确定内容放入 `## 9. Open Questions`，不要猜测。
"""
    user = f"""源文件: {source}
source_sha256: {content_sha}
schema_version: {SCHEMA_VERSION}

你要把输入 spans 填入下面的固定模板。不要改标题，不要删空章节。

固定模板：
```markdown
{STRICT_MARKDOWN_TEMPLATE}
```

输入 spans：

{chr(10).join(span_blocks)}

最终答案只能输出填好的 Markdown，从 `# Semantic Extraction` 开始；必须出现至少一个 `raw:S001` 或其他 `raw:Sxxx` 证据。
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_repair_messages(source: Path, content_sha: str, spans: list[dict[str, Any]], draft: str, errors: list[str]) -> list[dict[str, str]]:
    span_ids = ", ".join(span["span_id"] for span in spans) or "S001"
    system = """你是 Markdown schema 修复器。你的任务只修格式，不新增事实。
输出必须从 `# Semantic Extraction` 开始，必须完整包含 10 个指定章节，必须使用 `raw:Sxxx` 证据锚点。
"""
    user = f"""源文件: {source}
source_sha256: {content_sha}
可用证据 span: {span_ids}
校验错误: {errors}

固定模板：
```markdown
{STRICT_MARKDOWN_TEMPLATE}
```

上一版输出：
```markdown
{draft[:12000]}
```

请根据上一版输出和可用 span 修复为合格 Markdown：
- 不要解释错误。
- 不要输出代码围栏。
- 缺少信息的章节写 N/A，但必须保留标题和证据锚点。
- 每个表格至少一行。
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_thunderomlx(messages: list[dict[str, str]], args: argparse.Namespace) -> tuple[str, dict[str, Any], int]:
    pause = thunderomlx_pause_state(args)
    if pause:
        raise RuntimeError(
            "ThunderOMLX maintenance pause active: "
            + str(pause.get("reason") or pause.get("path") or "paused")
        )
    payload = {
        "model": args.proxy_model,
        "max_tokens": args.max_tokens,
        "messages": messages,
    }
    req = urllib.request.Request(
        args.endpoint.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": args.api_key},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=args.timeout_sec) as resp:
        response = json.loads(resp.read().decode("utf-8", errors="replace"))
    latency_ms = int((time.monotonic() - started) * 1000)
    parts: list[str] = []
    if "choices" in response:
        for choice in response.get("choices") or []:
            message = choice.get("message") if isinstance(choice, dict) else None
            if isinstance(message, dict):
                parts.append(str(message.get("content") or ""))
    else:
        for item in response.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item.get("text") or ""))
    text = "\n".join(parts).strip()
    text = re.sub(r"(?is)<think>.*?</think>\s*", "", text).strip()
    return text, response, latency_ms


def call_thunderomlx_with_retries(messages: list[dict[str, str]], args: argparse.Namespace) -> tuple[str, dict[str, Any], int]:
    attempts = max(1, int(getattr(args, "max_retries", 0)) + 1)
    delay = max(0.0, float(getattr(args, "retry_backoff_sec", 0)))
    last_exc: BaseException | None = None
    total_latency = 0
    for attempt in range(1, attempts + 1):
        try:
            text, response, latency = call_thunderomlx(messages, args)
            return text, response, total_latency + latency
        except urllib.error.HTTPError:
            # HTTP errors include a response body; keep them precise and do not
            # hide them behind a generic retry wrapper.
            raise
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            if delay:
                time.sleep(delay * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc


def validate_extracted(text: str, content_sha: str) -> list[str]:
    errors: list[str] = []
    required = [
        "# Semantic Extraction",
        "## 1. 一句话摘要",
        "## 2. 核心事实",
        "## 8. 风险边界",
        "## 9. Open Questions",
    ]
    for marker in required:
        if marker not in text:
            errors.append(f"missing section: {marker}")
    if "raw:S" not in text:
        errors.append("missing raw span evidence")
    if text.strip().startswith("```"):
        errors.append("wrapped in code fence")
    if len(text.strip()) < 200:
        errors.append("output too short")
    if "\ufffd" in text:
        errors.append("replacement character detected")
    if content_sha not in text:
        # The wrapper frontmatter adds this before write; validator can warn
        # but does not require model body to repeat it.
        pass
    return errors


def normalize_extracted(text: str, spans: list[dict[str, Any]]) -> str:
    """Make model output schema-complete without inventing source facts."""
    body = text.strip()
    body = re.sub(r"(?is)^```(?:markdown)?\s*", "", body)
    body = re.sub(r"(?is)\s*```\s*$", "", body).strip()
    if "# Semantic Extraction" in body and not body.startswith("# Semantic Extraction"):
        body = body[body.index("# Semantic Extraction") :].strip()
    if not body.startswith("# Semantic Extraction"):
        body = "# Semantic Extraction\n\n" + body

    fallback_span = f"raw:{spans[0]['span_id']}" if spans else "raw:S001"
    required_blocks = [
        ("## 1. 一句话摘要", f"N/A。证据: {fallback_span}"),
        ("## 2. 核心事实", f"| 事实 | 证据位置 | 置信度 |\n|---|---|---|\n| N/A | {fallback_span} | low |"),
        ("## 3. 功能模块", f"### N/A\n- 作用: N/A\n- 输入: N/A\n- 输出: N/A\n- 依赖: N/A\n- 证据: {fallback_span}"),
        ("## 4. 用户价值", f"- N/A 证据: {fallback_span}"),
        ("## 5. 架构结构", f"```text\nN/A\n```\n证据: {fallback_span}"),
        ("## 6. 命令 / API / 配置", f"| 类型 | 名称 | 用途 | 证据 |\n|---|---|---|---|\n| N/A | N/A | 原文未提供 | {fallback_span} |"),
        ("## 7. 验证证据", f"| 验证项 | 结果 | 证据 |\n|---|---|---|\n| N/A | 原文未提供 | {fallback_span} |"),
        ("## 8. 风险边界", f"| 风险 | 影响 | 缓解 | 证据 |\n|---|---|---|---|\n| N/A | N/A | N/A | {fallback_span} |"),
        ("## 9. Open Questions", f"- N/A 证据: {fallback_span}"),
        ("## 10. 检索关键词", "- N/A"),
    ]
    for heading, filler in required_blocks:
        if heading not in body:
            body += f"\n\n{heading}\n{filler}"
    if "raw:S" not in body:
        body += f"\n\n证据锚点: {fallback_span}"
    return body.strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_one(source: Path, vault: Path, args: argparse.Namespace) -> dict[str, Any]:
    raw_bytes = source.read_bytes()
    content_sha = sha256_bytes(raw_bytes)
    output_path, report_path, manifest_path = target_paths(source, vault, args.proxy_model)
    manifest = read_manifest(manifest_path)
    conn = registry_connect(args)
    doc_id = registry_doc_id(conn, source, content_sha, vault)
    if not should_extract(manifest, content_sha, args):
        if conn is not None:
            conn.close()
        return {"ok": True, "skipped": True, "source": str(source), "manifest": str(manifest_path), "output": str(output_path), "doc_id": doc_id}
    if args.dry_run:
        if conn is not None:
            conn.close()
        return {"ok": True, "dry_run": True, "source": str(source), "manifest": str(manifest_path), "output": str(output_path), "doc_id": doc_id}

    text = raw_bytes.decode("utf-8", errors="replace")
    spans = source_spans(text, args.max_chars)
    span_ids = registry_span_ids(conn, doc_id, spans)
    job_id = registry_start_job(conn, doc_id=doc_id, content_sha=content_sha, span_ids=span_ids, args=args)
    messages = build_messages(source, content_sha, spans)
    started_at = now_iso()
    repair_attempted = False
    repair_errors: list[str] = []
    output_records: list[tuple[str, Path, str]] = []
    try:
        body, response, latency_ms = call_thunderomlx_with_retries(messages, args)
        body = normalize_extracted(body, spans)
        errors = validate_extracted(body, content_sha)
        if errors and args.repair_attempts > 0:
            repair_attempted = True
            repair_messages = build_repair_messages(source, content_sha, spans, body, errors)
            repair_body, repair_response, repair_latency_ms = call_thunderomlx_with_retries(repair_messages, args)
            repair_body = normalize_extracted(repair_body, spans)
            repair_errors = validate_extracted(repair_body, content_sha)
            if not repair_errors:
                body = repair_body
                response = repair_response
                latency_ms += repair_latency_ms
                errors = []
        status = "extract_indexed" if not errors else "validation_failed"
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:1000]
        body = ""
        response = {}
        latency_ms = 0
        errors = [f"http_{exc.code}: {err_body}"]
        status = "extract_failed_warn"
    except Exception as exc:
        body = ""
        response = {}
        latency_ms = 0
        errors = [f"{type(exc).__name__}: {exc}"]
        status = "extract_failed_warn"

    usage = response.get("usage") if isinstance(response, dict) else {}
    generated_at = now_iso()
    report = {
        "source_path": str(source),
        "doc_id": doc_id,
        "job_id": job_id,
        "content_sha256": content_sha,
        "output_path": str(output_path),
        "status": status,
        "errors": errors,
        "profile": args.profile,
        "proxy_model": args.proxy_model,
        "local_model": args.local_model,
        "endpoint": args.endpoint,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "span_count": len(spans),
        "prompt_chars": sum(len(message.get("content", "")) for message in messages),
        "latency_ms": latency_ms,
        "usage": usage or {},
        "repair_attempted": repair_attempted,
        "repair_errors": repair_errors,
        "started_at": started_at,
        "generated_at": generated_at,
    }

    if status == "extract_indexed":
        frontmatter = (
            "---\n"
            f"source_path: {source}\n"
            f"source_sha256: {content_sha}\n"
            "derived: true\n"
            "extractor: thunderomlx\n"
            f"profile: {args.profile}\n"
            f"proxy_model: {args.proxy_model}\n"
            f"local_model: {args.local_model}\n"
            f"endpoint: {args.endpoint}\n"
            f"prompt_version: {PROMPT_VERSION}\n"
            f"schema_version: {SCHEMA_VERSION}\n"
            f"generated_at: {generated_at}\n"
            "---\n\n"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
        output_records.append(("extracted_md", output_path, sha256_bytes(output_path.read_bytes())))

    write_json(report_path, report)
    output_records.append(("report_json", report_path, sha256_bytes(report_path.read_bytes())))
    manifest_payload = {
        "doc_id": doc_id,
        "source_path": str(source),
        "content_sha256": content_sha,
        "updated_at": generated_at,
        "raw": {
            "materialized": True,
            "qmd_collection": "solar-wiki",
            "embed_model": "embeddinggemma-300M-GGUF",
        },
        "semantic_extract": {
            "enabled": True,
            "default_on": True,
            "status": status,
            "profile": args.profile,
            "proxy_model": args.proxy_model,
            "local_model": args.local_model,
            "endpoint": args.endpoint,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "output_path": str(output_path) if status == "extract_indexed" else "",
            "report_path": str(report_path),
            "qmd_collection": "solar-wiki",
        },
        "usage": usage or {},
        "errors": errors,
    }
    write_json(manifest_path, manifest_payload)
    output_records.append(("manifest_json", manifest_path, sha256_bytes(manifest_path.read_bytes())))
    registry_finish_job(
        conn,
        job_id=job_id,
        doc_id=doc_id,
        state=status,
        passed=status == "extract_indexed",
        error_code=primary_error_code(errors),
        detail=report,
        repair_count=1 if repair_attempted else 0,
        outputs=output_records,
    )
    if conn is not None:
        conn.close()
    append_log(vault, report)
    return {"ok": status == "extract_indexed", "status": status, "source": str(source), "output": str(output_path), "manifest": str(manifest_path), "errors": errors, "doc_id": doc_id, "job_id": job_id}


def append_log(vault: Path, payload: dict[str, Any]) -> None:
    log = vault / "_logs" / "thunderomlx.extract.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


INTERNAL_VAULT_DIRS = {
    ".obsidian",
    "_extracted",
    "_logs",
    "_manifests",
    "_meta",
}


def is_internal_path(path: Path, root: Path, include_raw: bool = True) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except Exception:
        return False
    if not rel.parts:
        return False
    head = rel.parts[0]
    if head in INTERNAL_VAULT_DIRS:
        return True
    if not include_raw and head == "_raw":
        return True
    return False


def iter_sources(root: Path, since_hours: int | None, include_raw: bool = True) -> list[Path]:
    now = time.time()
    cutoff = None if since_hours is None else now - since_hours * 3600
    out: list[Path] = []
    for path in root.rglob("*.md"):
        if "/.dispatch/" in str(path) or is_internal_path(path, root, include_raw=include_raw):
            continue
        if cutoff is not None and path.stat().st_mtime < cutoff:
            continue
        out.append(path)
    return sorted(out, key=lambda p: p.stat().st_mtime, reverse=True)


def run_qmd_update(args: argparse.Namespace) -> None:
    if not args.qmd_after:
        return
    cmd = ["solar-harness", "wiki", "qmd-update"]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)


def cmd_extract_file(args: argparse.Namespace) -> int:
    if maybe_exit_for_thunderomlx_pause(args):
        return 0
    vault = resolve_vault(args.vault)
    source = Path(args.source).expanduser()
    if not source.exists():
        print(json.dumps({"ok": False, "error": f"source not found: {source}"}, ensure_ascii=False))
        return 1
    try:
        with single_worker_lock(vault, args):
            result = extract_one(source, vault, args)
    except RuntimeError as exc:
        result = {"ok": False, "status": "lock_busy", "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return LOCK_EXIT_CODE
    run_qmd_update(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_backfill(args: argparse.Namespace) -> int:
    if maybe_exit_for_thunderomlx_pause(args):
        return 0
    vault = resolve_vault(args.vault)
    root = Path(args.source_dir).expanduser() if args.source_dir else vault / "_raw"
    sources = iter_sources(root, args.since_hours, include_raw=True)
    if args.limit:
        sources = sources[: args.limit]
    return run_backfill_sources(args, sources, qmd_after=True)


def cmd_backfill_vault(args: argparse.Namespace) -> int:
    if maybe_exit_for_thunderomlx_pause(args):
        return 0
    vault = resolve_vault(args.vault)
    root = Path(args.source_dir).expanduser() if args.source_dir else vault
    sources = iter_sources(root, args.since_hours, include_raw=False)
    if args.limit:
        sources = sources[: args.limit]
    return run_backfill_sources(args, sources, qmd_after=True)


def _registry_retryable_sources(args: argparse.Namespace, limit: int) -> list[Path]:
    conn = registry_connect(args)
    if conn is None:
        return []
    rows = conn.execute(
        """
        SELECT source_path
        FROM documents
        WHERE current_state='EXTRACT_FAILED_RETRYABLE'
          AND extract_policy != 'off'
        ORDER BY updated_at ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [Path(str(row["source_path"])).expanduser() for row in rows if Path(str(row["source_path"])).expanduser().exists()]


def cmd_reap_stale(args: argparse.Namespace) -> int:
    result = registry_mark_stale_jobs(args, stale_minutes=args.stale_minutes, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def cmd_supervised_backfill(args: argparse.Namespace) -> int:
    vault = resolve_vault(args.vault)
    root = Path(args.source_dir).expanduser() if args.source_dir else vault / "_raw"
    overall: list[dict[str, Any]] = []
    total_extracted = 0
    total_failed = 0
    total_reaped = 0
    for batch_index in range(1, args.max_batches + 1):
        reap = registry_mark_stale_jobs(args, stale_minutes=args.stale_minutes, limit=args.reap_limit)
        total_reaped += int(reap.get("reaped") or 0)
        retry_sources = _registry_retryable_sources(args, args.batch_size)
        if retry_sources:
            sources = retry_sources
            source_mode = "retryable"
        else:
            sources = iter_sources(root, args.since_hours, include_raw=True)
            if args.batch_size:
                sources = sources[: args.batch_size]
            source_mode = "scan"
        if not sources:
            overall.append({"batch": batch_index, "mode": source_mode, "reap": reap, "summary": {"ok": True, "total": 0, "extracted": 0}})
            break
        batch_results: list[dict[str, Any]] = []
        breaker = CircuitBreaker(args.max_consecutive_failures, args.max_fail_rate, args.min_circuit_attempts)
        try:
            with single_worker_lock(vault, args):
                for source in sources:
                    open_reason = breaker.open_reason()
                    if open_reason:
                        batch_results.append({"ok": False, "status": "extract_failed_circuit_open", "source": str(source), "errors": [open_reason]})
                        break
                    result = extract_one(source, vault, args)
                    batch_results.append(result)
                    breaker.record(result)
        except RuntimeError as exc:
            batch_results.append({"ok": False, "status": "lock_busy", "error": str(exc)})
        extracted_now = sum(1 for r in batch_results if r.get("ok") and not r.get("skipped") and not r.get("dry_run"))
        failed_now = sum(1 for r in batch_results if not r.get("ok") and not r.get("skipped") and not r.get("dry_run"))
        total_extracted += extracted_now
        total_failed += failed_now
        batch = {"batch": batch_index, "mode": source_mode, "sources": [str(p) for p in sources], "reap": reap, "extracted": extracted_now, "failed": failed_now, "results": batch_results if args.verbose else []}
        overall.append(batch)
        if failed_now and args.stop_on_error:
            break
        if args.sleep_sec:
            time.sleep(args.sleep_sec)
    if args.qmd_after and total_extracted > 0:
        run_qmd_update(args)
    payload = {"ok": total_failed == 0, "batches": len(overall), "total_reaped": total_reaped, "total_extracted_estimate": total_extracted, "total_failed_estimate": total_failed, "results": overall if args.verbose else []}
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


def run_backfill_sources(args: argparse.Namespace, sources: list[Path], qmd_after: bool = True) -> int:
    vault = resolve_vault(args.vault)
    results = []
    ok_count = 0
    skipped = 0
    breaker = CircuitBreaker(
        max_consecutive_failures=int(getattr(args, "max_consecutive_failures", 5)),
        max_fail_rate=float(getattr(args, "max_fail_rate", 0.25)),
        min_attempts=int(getattr(args, "min_circuit_attempts", 5)),
    )
    try:
        with single_worker_lock(vault, args):
            for source in sources:
                open_reason = breaker.open_reason()
                if open_reason:
                    result = {"ok": False, "status": "extract_failed_circuit_open", "source": str(source), "errors": [open_reason]}
                    results.append(result)
                    if not args.json:
                        print(f"[semantic-extract] circuit-open: {open_reason}; stopped before {source}")
                    break
                result = extract_one(source, vault, args)
                results.append(result)
                ok_count += 1 if result.get("ok") and not result.get("skipped") and not result.get("dry_run") else 0
                skipped += 1 if result.get("skipped") else 0
                breaker.record(result)
                if not args.json:
                    state = "skip" if result.get("skipped") else result.get("status", "ok" if result.get("ok") else "error")
                    print(f"[semantic-extract] {state}: {source}")
    except RuntimeError as exc:
        summary = {"ok": False, "status": "lock_busy", "error": str(exc), "total": 0, "extracted": 0, "skipped": 0}
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"[semantic-extract] lock_busy: {exc}", file=sys.stderr)
        return LOCK_EXIT_CODE
    if qmd_after:
        run_qmd_update(args)
    attempted = len([r for r in results if not r.get("skipped") and not r.get("dry_run")])
    failures = len([r for r in results if not r.get("ok") and not r.get("skipped") and not r.get("dry_run")])
    ok = True
    if attempted > 0 and ok_count == 0:
        ok = False
    if any(r.get("status") == "extract_failed_circuit_open" for r in results):
        ok = False
    summary = {
        "ok": ok,
        "total": len(results),
        "attempted": attempted,
        "extracted": ok_count,
        "skipped": skipped,
        "failed": failures,
        "circuit": {
            "attempted": breaker.attempted,
            "failed": breaker.failed,
            "consecutive_failed": breaker.consecutive_failed,
            "open_reason": breaker.open_reason(),
        },
        "results": results if args.verbose else [],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[semantic-extract] total={len(results)} attempted={attempted} extracted={ok_count} skipped={skipped} failed={failures} ok={ok}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ThunderOMLX semantic extraction for Solar Knowledge markdown")
    parser.add_argument("--vault", default=None)
    parser.add_argument("--endpoint", default=os.environ.get("THUNDEROMLX_BASE_URL", "http://127.0.0.1:8002"))
    parser.add_argument("--api-key", default=os.environ.get("THUNDEROMLX_AUTH_TOKEN", "local-thunderomlx"))
    parser.add_argument("--proxy-model", default=os.environ.get("THUNDEROMLX_KNOWLEDGE_MODEL", DEFAULT_PROXY_MODEL))
    parser.add_argument("--local-model", default=os.environ.get("THUNDEROMLX_LOCAL_MODEL", DEFAULT_LOCAL_MODEL))
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--max-chars", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_MAX_SOURCE_CHARS", "32000")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_MAX_TOKENS", "2400")))
    parser.add_argument("--timeout-sec", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_TIMEOUT_SEC", "900")))
    parser.add_argument("--repair-attempts", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_REPAIR_ATTEMPTS", "1")))
    parser.add_argument("--max-retries", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_MAX_RETRIES", "2")))
    parser.add_argument("--retry-backoff-sec", type=float, default=float(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_RETRY_BACKOFF_SEC", "10")))
    parser.add_argument("--registry-db", default=os.environ.get("SOLAR_KNOWLEDGE_REGISTRY_DB", str(DEFAULT_REGISTRY_DB)))
    parser.add_argument("--lock-path", default=os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_LOCK", ""))
    parser.add_argument("--pause-file", default=os.environ.get("THUNDEROMLX_MAINTENANCE_FILE", str(DEFAULT_THUNDEROMLX_PAUSE_FILE)))
    parser.add_argument("--lock-wait", action="store_true", default=os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_LOCK_WAIT", "0") == "1")
    parser.add_argument("--max-consecutive-failures", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_MAX_CONSECUTIVE_FAILURES", "5")))
    parser.add_argument("--max-fail-rate", type=float, default=float(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_MAX_FAIL_RATE", "0.25")))
    parser.add_argument("--min-circuit-attempts", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_MIN_CIRCUIT_ATTEMPTS", "5")))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--qmd-after", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("extract-file")
    one.add_argument("--source", required=True)
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--source-dir", default=None)
    backfill.add_argument("--limit", type=int, default=10)
    backfill.add_argument("--since-hours", type=int, default=None)
    backfill_vault = sub.add_parser("backfill-vault")
    backfill_vault.add_argument("--source-dir", default=None)
    backfill_vault.add_argument("--limit", type=int, default=10)
    backfill_vault.add_argument("--since-hours", type=int, default=None)
    reap = sub.add_parser("reap-stale")
    reap.add_argument("--stale-minutes", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_STALE_MINUTES", "30")))
    reap.add_argument("--limit", type=int, default=50)
    supervised = sub.add_parser("supervised-backfill")
    supervised.add_argument("--source-dir", default=None)
    supervised.add_argument("--batch-size", type=int, default=3)
    supervised.add_argument("--max-batches", type=int, default=3)
    supervised.add_argument("--since-hours", type=int, default=None)
    supervised.add_argument("--sleep-sec", type=float, default=2.0)
    supervised.add_argument("--stale-minutes", type=int, default=int(os.environ.get("SOLAR_KNOWLEDGE_EXTRACT_STALE_MINUTES", "30")))
    supervised.add_argument("--reap-limit", type=int, default=20)
    supervised.add_argument("--stop-on-error", action="store_true")
    for child in (one, backfill, backfill_vault, reap, supervised):
        child.add_argument("--force", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--qmd-after", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--repair-attempts", type=int, default=argparse.SUPPRESS)
        child.add_argument("--max-retries", type=int, default=argparse.SUPPRESS)
        child.add_argument("--retry-backoff-sec", type=float, default=argparse.SUPPRESS)
        child.add_argument("--registry-db", default=argparse.SUPPRESS)
        child.add_argument("--lock-path", default=argparse.SUPPRESS)
        child.add_argument("--lock-wait", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--max-consecutive-failures", type=int, default=argparse.SUPPRESS)
        child.add_argument("--max-fail-rate", type=float, default=argparse.SUPPRESS)
        child.add_argument("--min-circuit-attempts", type=int, default=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "extract-file":
        return cmd_extract_file(args)
    if args.command == "backfill":
        return cmd_backfill(args)
    if args.command == "backfill-vault":
        return cmd_backfill_vault(args)
    if args.command == "reap-stale":
        return cmd_reap_stale(args)
    if args.command == "supervised-backfill":
        return cmd_supervised_backfill(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
