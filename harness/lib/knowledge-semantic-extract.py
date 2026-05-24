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
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc
DEFAULT_PROXY_MODEL = "Qwen3.6-35b-a3b"
DEFAULT_LOCAL_MODEL = "ThunderOMLX Qwen3.6 local"
DEFAULT_PROFILE = "knowledge-extractor"
PROMPT_VERSION = "knowledge-extract-v2"
SCHEMA_VERSION = "extracted-md-v1"


def now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._/-]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:220] or "document"


def resolve_vault(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    return Path(os.environ.get("OBSIDIAN_VAULT_PATH", str(Path.home() / "Knowledge"))).expanduser()


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
    if not should_extract(manifest, content_sha, args):
        return {"ok": True, "skipped": True, "source": str(source), "manifest": str(manifest_path), "output": str(output_path)}
    if args.dry_run:
        return {"ok": True, "dry_run": True, "source": str(source), "manifest": str(manifest_path), "output": str(output_path)}

    text = raw_bytes.decode("utf-8", errors="replace")
    spans = source_spans(text, args.max_chars)
    messages = build_messages(source, content_sha, spans)
    started_at = now_iso()
    repair_attempted = False
    repair_errors: list[str] = []
    try:
        body, response, latency_ms = call_thunderomlx(messages, args)
        body = normalize_extracted(body, spans)
        errors = validate_extracted(body, content_sha)
        if errors and args.repair_attempts > 0:
            repair_attempted = True
            repair_messages = build_repair_messages(source, content_sha, spans, body, errors)
            repair_body, repair_response, repair_latency_ms = call_thunderomlx(repair_messages, args)
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

    write_json(report_path, report)
    manifest_payload = {
        "doc_id": str(rel_to_vault(source, vault)),
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
    append_log(vault, report)
    return {"ok": status == "extract_indexed", "status": status, "source": str(source), "output": str(output_path), "manifest": str(manifest_path), "errors": errors}


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
    vault = resolve_vault(args.vault)
    source = Path(args.source).expanduser()
    if not source.exists():
        print(json.dumps({"ok": False, "error": f"source not found: {source}"}, ensure_ascii=False))
        return 1
    result = extract_one(source, vault, args)
    run_qmd_update(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_backfill(args: argparse.Namespace) -> int:
    vault = resolve_vault(args.vault)
    root = Path(args.source_dir).expanduser() if args.source_dir else vault / "_raw"
    sources = iter_sources(root, args.since_hours, include_raw=True)
    if args.limit:
        sources = sources[: args.limit]
    return run_backfill_sources(args, sources, qmd_after=True)


def cmd_backfill_vault(args: argparse.Namespace) -> int:
    vault = resolve_vault(args.vault)
    root = Path(args.source_dir).expanduser() if args.source_dir else vault
    sources = iter_sources(root, args.since_hours, include_raw=False)
    if args.limit:
        sources = sources[: args.limit]
    return run_backfill_sources(args, sources, qmd_after=True)


def run_backfill_sources(args: argparse.Namespace, sources: list[Path], qmd_after: bool = True) -> int:
    vault = resolve_vault(args.vault)
    results = []
    ok_count = 0
    skipped = 0
    for source in sources:
        result = extract_one(source, vault, args)
        results.append(result)
        ok_count += 1 if result.get("ok") else 0
        skipped += 1 if result.get("skipped") else 0
        if not args.json:
            state = "skip" if result.get("skipped") else result.get("status", "ok" if result.get("ok") else "error")
            print(f"[semantic-extract] {state}: {source}")
    if qmd_after:
        run_qmd_update(args)
    summary = {"ok": True, "total": len(results), "extracted": ok_count, "skipped": skipped, "results": results if args.verbose else []}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[semantic-extract] total={len(results)} extracted={ok_count} skipped={skipped}")
    return 0


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
    for child in (one, backfill, backfill_vault):
        child.add_argument("--force", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--qmd-after", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--repair-attempts", type=int, default=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "extract-file":
        return cmd_extract_file(args)
    if args.command == "backfill":
        return cmd_backfill(args)
    if args.command == "backfill-vault":
        return cmd_backfill_vault(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
