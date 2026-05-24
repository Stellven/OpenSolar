#!/usr/bin/env python3
"""QMD microbatch control-plane watermarks for Solar Knowledge ingest."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import knowledge_ingest_registry as registry


LAYERS = ("raw", "vault", "extracted")
DEFAULT_LOCK_PATH = Path.home() / "Knowledge" / "_registry" / "qmd-update.lock"


def _connect(db_path: Path):
    registry.migrate(db_path)
    return registry.connect(db_path)


def watermarks(db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        rows = [registry.row_to_dict(r) for r in conn.execute("SELECT * FROM watermarks ORDER BY layer")]
    return {"ok": True, "db": str(db_path), "watermarks": rows}


def update_watermark(
    *,
    layer: str,
    pending_delta: int = 0,
    failed_delta: int = 0,
    indexed: bool = False,
    batch_id: str | None = None,
    db_path: Path = registry.DEFAULT_DB,
) -> dict[str, Any]:
    if layer not in LAYERS:
        raise ValueError(f"invalid layer: {layer}")
    ts = registry.now_iso()
    batch_id = batch_id or f"qmd-{layer}-{uuid.uuid4().hex[:10]}"
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE watermarks
            SET pending_count=max(0, pending_count + ?),
                failed_count=max(0, failed_count + ?),
                last_indexed_ts=CASE WHEN ? THEN ? ELSE last_indexed_ts END,
                last_batch_id=CASE WHEN ? THEN ? ELSE last_batch_id END,
                last_batch_ts=CASE WHEN ? THEN ? ELSE last_batch_ts END,
                updated_at=?
            WHERE layer=?
            """,
            (pending_delta, failed_delta, 1 if indexed else 0, ts, 1 if indexed else 0, batch_id, 1 if indexed else 0, ts, ts, layer),
        )
        conn.commit()
    return {"ok": True, "layer": layer, "batch_id": batch_id, "indexed": indexed, "updated_at": ts}


def record_qmd_event(
    *,
    doc_id: str,
    layer: str,
    qmd_status: str,
    qmd_batch_id: str,
    db_path: Path = registry.DEFAULT_DB,
) -> dict[str, Any]:
    event_id = f"qmd_evt_{uuid.uuid4().hex[:24]}"
    ts = registry.now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO qmd_index_events(event_id, doc_id, layer, qmd_batch_id, qmd_status, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, doc_id, layer, qmd_batch_id, qmd_status, ts),
        )
        conn.commit()
    return {"event_id": event_id, "doc_id": doc_id, "layer": layer, "qmd_status": qmd_status}


def cmd_watermarks(args: argparse.Namespace) -> int:
    print(json.dumps(watermarks(Path(args.db).expanduser()), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_mark_indexed(args: argparse.Namespace) -> int:
    batch_id = args.batch_id or f"qmd-{args.layer}-{uuid.uuid4().hex[:10]}"
    result = update_watermark(layer=args.layer, indexed=True, batch_id=batch_id, db_path=Path(args.db).expanduser())
    for doc_id in args.doc_id or []:
        record_qmd_event(doc_id=doc_id, layer=args.layer, qmd_status="indexed", qmd_batch_id=batch_id, db_path=Path(args.db).expanduser())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_microbatch(args: argparse.Namespace) -> int:
    paths = [Path(p).expanduser() for p in args.path or []]
    batch_id = args.batch_id or f"qmd-{args.layer}-{uuid.uuid4().hex[:10]}"
    command = ["solar-harness", "wiki", "qmd-update"]
    if args.execute:
        lock_path = Path(args.lock_path).expanduser()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + args.lock_timeout_sec
        with lock_path.open("w", encoding="utf-8") as lock_file:
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out waiting for QMD update lock: {lock_path}")
                    time.sleep(1)
            lock_file.write(json.dumps({"batch_id": batch_id, "layer": args.layer, "pid": os.getpid(), "ts": registry.now_iso()}) + "\n")
            lock_file.flush()
            subprocess.run(command, check=True, timeout=args.timeout_sec)
        mode = "execute"
    else:
        mode = "dry_run"
    if args.execute:
        result = update_watermark(layer=args.layer, indexed=True, batch_id=batch_id, db_path=Path(args.db).expanduser())
    else:
        result = {"ok": True, "layer": args.layer, "batch_id": batch_id, "indexed": False, "updated_at": registry.now_iso()}
    result.update({"mode": mode, "paths": [str(p) for p in paths], "command": command})
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solar Knowledge QMD microbatch indexer")
    parser.add_argument("--db", default=str(registry.DEFAULT_DB))
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watermarks")
    w.set_defaults(func=cmd_watermarks)
    mark = sub.add_parser("mark-indexed")
    mark.add_argument("--layer", choices=LAYERS, required=True)
    mark.add_argument("--batch-id")
    mark.add_argument("--doc-id", action="append")
    mark.set_defaults(func=cmd_mark_indexed)
    micro = sub.add_parser("microbatch")
    micro.add_argument("--layer", choices=LAYERS, required=True)
    micro.add_argument("--path", action="append")
    micro.add_argument("--batch-id")
    micro.add_argument("--execute", action="store_true")
    micro.add_argument("--timeout-sec", type=int, default=180)
    micro.add_argument("--lock-path", default=str(DEFAULT_LOCK_PATH))
    micro.add_argument("--lock-timeout-sec", type=int, default=600)
    micro.set_defaults(func=cmd_microbatch)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
