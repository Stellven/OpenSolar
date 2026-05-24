#!/usr/bin/env python3
"""Minimal dispatcher CLI for Solar Knowledge ingest control plane.

N2 establishes the single CLI entrypoint and delegates registry operations to
knowledge_ingest_registry. Later nodes add adapters, extraction and QMD workers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import knowledge_ingest_registry as registry
import knowledge_source_adapters as adapters
import knowledge_spans


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(payload)


def cmd_status(args: argparse.Namespace) -> int:
    emit(registry.status(Path(args.db).expanduser()), args.json)
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    emit(registry.migrate(Path(args.db).expanduser()), args.json)
    return 0


def cmd_submit_event(args: argparse.Namespace) -> int:
    source_path = str(Path(args.source_path).expanduser())
    source_sha = args.source_sha256
    path = Path(source_path)
    if source_sha is None and path.exists() and path.is_file():
        source_sha = registry.hashlib.sha256(path.read_bytes()).hexdigest()
    doc = registry.upsert_document(
        source_kind=args.source_kind,
        source_path=source_path,
        source_adapter=args.source_adapter,
        content_kind=args.content_kind,
        declared_doc_type=args.declared_doc_type,
        source_sha256=source_sha,
        current_state=args.state,
        ingest_policy=args.ingest_policy,
        extract_policy=args.extract_policy,
        provenance_quality=args.provenance_quality,
        db_path=Path(args.db).expanduser(),
    )
    emit({"ok": True, "document": doc}, args.json)
    return 0


def _span_root(args: argparse.Namespace, source_kind: str) -> Path:
    if args.span_root:
        return Path(args.span_root).expanduser()
    base = Path.home() / "Knowledge"
    if source_kind == "obsidian_vault":
        return base / "_vault_index" / "spans"
    return base / "_raw" / ".spans"


def _write_and_register_spans(
    *,
    path: Path,
    doc: dict[str, Any],
    source_kind: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    sidecar = knowledge_spans.default_sidecar_path(
        path,
        root=_span_root(args, source_kind),
        doc_id=doc["doc_id"],
    )
    payload = knowledge_spans.write_span_sidecar(
        source_path=path,
        doc_id=doc["doc_id"],
        source_kind=source_kind,
        output_path=sidecar,
        max_lines=args.max_span_lines,
    )
    registry.replace_spans(
        doc_id=doc["doc_id"],
        spans=payload["spans"],
        source_sha256=payload["source_sha256"],
        db_path=Path(args.db).expanduser(),
    )
    return {"span_count": len(payload["spans"]), "sidecar_path": str(sidecar)}


def cmd_discover_raw(args: argparse.Namespace) -> int:
    root = Path(args.source_dir).expanduser()
    limit = args.limit
    count = 0
    docs: list[dict[str, Any]] = []
    span_count = 0
    for path in adapters.iter_raw_markdown(root, limit=limit):
        sha = registry.hashlib.sha256(path.read_bytes()).hexdigest()
        doc = registry.upsert_document(
            source_kind="raw",
            source_path=str(path),
            source_adapter="raw_adapter",
            content_kind="markdown",
            declared_doc_type=args.declared_doc_type,
            source_sha256=sha,
            current_state="RAW_MATERIALIZED",
            db_path=Path(args.db).expanduser(),
        )
        if args.build_spans:
            span_info = _write_and_register_spans(path=path, doc=doc, source_kind="raw", args=args)
            doc["span_sidecar_path"] = span_info["sidecar_path"]
            doc["span_count"] = span_info["span_count"]
            span_count += span_info["span_count"]
        docs.append(doc)
        count += 1
    emit({"ok": True, "source_dir": str(root), "count": count, "span_count": span_count, "documents": docs if args.verbose else []}, args.json)
    return 0


def cmd_discover_sources(args: argparse.Namespace) -> int:
    root = Path(args.source_dir).expanduser()
    materialized_root = Path(args.materialized_root).expanduser()
    limit = args.limit
    count = 0
    span_count = 0
    by_kind: dict[str, int] = {}
    docs: list[dict[str, Any]] = []
    for source_path in adapters.iter_raw_sources(root, limit=limit):
        source_kind, source_adapter, doc_type = adapters.classify_raw_source(source_path, root)
        if args.source_kind and source_kind != args.source_kind:
            continue
        ingest_path = adapters.materialize_to_markdown(source_path, target_root=materialized_root, source_kind=source_kind)
        sha = registry.hashlib.sha256(ingest_path.read_bytes()).hexdigest()
        doc = registry.upsert_document(
            source_kind=source_kind,
            source_path=str(ingest_path),
            source_adapter=source_adapter,
            content_kind="markdown",
            declared_doc_type=doc_type,
            source_sha256=sha,
            current_state="RAW_MATERIALIZED",
            provenance_quality="complete" if ingest_path == source_path else "observed",
            db_path=Path(args.db).expanduser(),
        )
        if args.build_spans:
            span_info = _write_and_register_spans(path=ingest_path, doc=doc, source_kind=source_kind, args=args)
            doc["span_sidecar_path"] = span_info["sidecar_path"]
            doc["span_count"] = span_info["span_count"]
            span_count += span_info["span_count"]
        docs.append(doc)
        by_kind[source_kind] = by_kind.get(source_kind, 0) + 1
        count += 1
    emit({"ok": True, "source_dir": str(root), "count": count, "span_count": span_count, "by_kind": by_kind, "documents": docs if args.verbose else []}, args.json)
    return 0


def cmd_discover_vault(args: argparse.Namespace) -> int:
    root = Path(args.vault).expanduser()
    limit = args.limit
    count = 0
    docs: list[dict[str, Any]] = []
    span_count = 0
    seen_folders: set[str] = set()
    for path, folder in adapters.iter_vault_markdown(root, include=args.include, limit=limit):
        seen_folders.add(folder)
        sha = registry.hashlib.sha256(path.read_bytes()).hexdigest()
        doc = registry.upsert_document(
            source_kind="obsidian_vault",
            source_path=str(path),
            source_adapter="obsidian_adapter",
            content_kind="markdown",
            declared_doc_type=adapters.doc_type_for_vault_folder(folder),
            source_sha256=sha,
            current_state="VAULT_DISCOVERED",
            db_path=Path(args.db).expanduser(),
        )
        if args.build_spans:
            span_info = _write_and_register_spans(path=path, doc=doc, source_kind="obsidian_vault", args=args)
            doc["span_sidecar_path"] = span_info["sidecar_path"]
            doc["span_count"] = span_info["span_count"]
            span_count += span_info["span_count"]
        docs.append(doc)
        count += 1
    emit({"ok": True, "vault": str(root), "folders": sorted(seen_folders), "count": count, "span_count": span_count, "documents": docs if args.verbose else []}, args.json)
    return 0


def cmd_process_queue(args: argparse.Namespace) -> int:
    emit({"ok": True, "processed": 0, "note": "queue processing is implemented by later DAG nodes"}, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solar Knowledge ingest dispatcher")
    parser.add_argument("--db", default=str(registry.DEFAULT_DB))
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    children: list[argparse.ArgumentParser] = []
    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)
    children.append(status)
    migrate = sub.add_parser("migrate")
    migrate.set_defaults(func=cmd_migrate)
    children.append(migrate)

    submit = sub.add_parser("submit-event")
    submit.add_argument("--source-kind", required=True)
    submit.add_argument("--source-path", required=True)
    submit.add_argument("--source-adapter", required=True)
    submit.add_argument("--content-kind", default="markdown")
    submit.add_argument("--declared-doc-type")
    submit.add_argument("--source-sha256")
    submit.add_argument("--state", default="NEW")
    submit.add_argument("--ingest-policy", default="default")
    submit.add_argument("--extract-policy", default="default")
    submit.add_argument("--provenance-quality", default="observed")
    submit.set_defaults(func=cmd_submit_event)
    children.append(submit)

    raw = sub.add_parser("discover-raw")
    raw.add_argument("--source-dir", default=str(Path.home() / "Knowledge" / "_raw"))
    raw.add_argument("--declared-doc-type")
    raw.add_argument("--limit", type=int, default=20)
    raw.add_argument("--verbose", action="store_true")
    raw.add_argument("--build-spans", action="store_true", default=True)
    raw.add_argument("--span-root")
    raw.add_argument("--max-span-lines", type=int, default=120)
    raw.set_defaults(func=cmd_discover_raw)
    children.append(raw)

    sources = sub.add_parser("discover-sources")
    sources.add_argument("--source-dir", default=str(Path.home() / "Knowledge" / "_raw"))
    sources.add_argument("--source-kind")
    sources.add_argument("--limit", type=int, default=100)
    sources.add_argument("--verbose", action="store_true")
    sources.add_argument("--build-spans", action="store_true", default=True)
    sources.add_argument("--span-root")
    sources.add_argument("--max-span-lines", type=int, default=120)
    sources.add_argument("--materialized-root", default=str(Path.home() / "Knowledge" / "_raw" / ".materialized"))
    sources.set_defaults(func=cmd_discover_sources)
    children.append(sources)

    vault = sub.add_parser("discover-vault")
    vault.add_argument("--vault", default=str(Path.home() / "Knowledge"))
    vault.add_argument("--include", nargs="*")
    vault.add_argument("--limit", type=int, default=20)
    vault.add_argument("--verbose", action="store_true")
    vault.add_argument("--build-spans", action="store_true", default=True)
    vault.add_argument("--span-root")
    vault.add_argument("--max-span-lines", type=int, default=120)
    vault.set_defaults(func=cmd_discover_vault)
    children.append(vault)

    process = sub.add_parser("process-queue")
    process.set_defaults(func=cmd_process_queue)
    children.append(process)
    for child in children:
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        child.add_argument("--db", default=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
