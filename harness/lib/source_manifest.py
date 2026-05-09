#!/usr/bin/env python3
"""source_manifest.py — PDF provenance tracking and safe migration to _sources.

Safety guarantees:
  1. SHA-256 verified before copy; copy aborted on mismatch
  2. Original _raw file NEVER deleted/moved — only copied
  3. Manifest JSON written atomically (tmp → rename)
  4. --dry-run by default; --apply required for actual copy
  5. Any file missing checksum is skipped (stop_on_missing_checksum honoured)

CLI:
  python3 source_manifest.py scan    [--raw-dir DIR] [--json]
  python3 source_manifest.py migrate [--raw-dir DIR] [--dest DIR] [--apply] [--json]
  python3 source_manifest.py verify  [--sources-dir DIR] [--json]
  python3 source_manifest.py list    [--sources-dir DIR] [--json]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
SOURCES_DIR = HARNESS_DIR / "_sources"
PAPERS_DIR = SOURCES_DIR / "papers"
RAW_DIR = HOME / "Knowledge" / "_raw"
SHA_PREFIX_LEN = 2


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_path(dest_dir: Path) -> Path:
    return dest_dir / "manifest.json"


def _write_manifest(dest_dir: Path, data: dict) -> None:
    tmp = dest_dir / "manifest.json.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.rename(dest_dir / "manifest.json")


def _read_manifest(dest_dir: Path) -> "dict | None":
    mp = _manifest_path(dest_dir)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text())
    except Exception:
        return None


# ── scan ──────────────────────────────────────────────────────────────────────

def cmd_scan(raw_dir: Path, as_json: bool) -> int:
    pdfs = sorted(raw_dir.glob("**/*.pdf")) if raw_dir.exists() else []
    results: list[dict] = []
    for p in pdfs:
        try:
            sha = _sha256(p)
            size = p.stat().st_size
            results.append({
                "path": str(p),
                "sha256": sha,
                "size_bytes": size,
                "ready_for_migration": True,
            })
        except Exception as exc:
            results.append({
                "path": str(p),
                "sha256": None,
                "error": str(exc),
                "ready_for_migration": False,
            })

    out = {
        "ok": True,
        "raw_dir": str(raw_dir),
        "total": len(pdfs),
        "ready": sum(1 for r in results if r["ready_for_migration"]),
        "error_count": sum(1 for r in results if not r["ready_for_migration"]),
        "files": results,
        "generated_at": _now(),
    }
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Scan: {out['total']} PDFs in {raw_dir}")
        print(f"  ready: {out['ready']}  errors: {out['error_count']}")
        for r in results:
            tag = "✓" if r["ready_for_migration"] else "✗"
            print(f"  {tag} {Path(r['path']).name}  sha={r.get('sha256','?')[:12]}")
    return 0


# ── migrate ───────────────────────────────────────────────────────────────────

def cmd_migrate(raw_dir: Path, dest_dir: Path, apply: bool, as_json: bool) -> int:
    pdfs = sorted(raw_dir.glob("**/*.pdf")) if raw_dir.exists() else []
    actions: list[dict] = []

    for src in pdfs:
        try:
            sha = _sha256(src)
        except Exception as exc:
            actions.append({
                "src": str(src),
                "action": "skip",
                "reason": f"checksum_error: {exc}",
            })
            continue

        prefix = sha[:SHA_PREFIX_LEN]
        paper_dir = dest_dir / prefix / sha
        dest_file = paper_dir / src.name
        manifest_data = {
            "sha256": sha,
            "original_path": str(src),
            "original_name": src.name,
            "migrated_at": _now(),
            "size_bytes": src.stat().st_size,
            "ttl_days": 14,
            "source": "raw_migration",
        }

        if dest_file.exists():
            existing_sha = _sha256(dest_file)
            if existing_sha == sha:
                actions.append({
                    "src": str(src),
                    "dest": str(dest_file),
                    "action": "skip",
                    "reason": "already_migrated",
                    "sha256": sha,
                })
                continue
            else:
                actions.append({
                    "src": str(src),
                    "action": "skip",
                    "reason": "dest_exists_sha_mismatch",
                    "sha256": sha,
                })
                continue

        action: dict[str, Any] = {
            "src": str(src),
            "dest": str(dest_file),
            "action": "copy",
            "sha256": sha,
            "dry_run": not apply,
        }

        if apply:
            paper_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest_file))
            # Verify copy
            copied_sha = _sha256(dest_file)
            if copied_sha != sha:
                dest_file.unlink(missing_ok=True)
                action["action"] = "error"
                action["reason"] = f"sha_mismatch_after_copy: got={copied_sha[:12]}"
                actions.append(action)
                continue
            _write_manifest(paper_dir, manifest_data)
            action["verified"] = True
        actions.append(action)

    copied = sum(1 for a in actions if a["action"] == "copy" and not a.get("dry_run") and a.get("verified"))
    skipped = sum(1 for a in actions if a["action"] == "skip")
    errors = sum(1 for a in actions if a["action"] == "error")
    dry_planned = sum(1 for a in actions if a["action"] == "copy" and a.get("dry_run"))

    out = {
        "ok": errors == 0,
        "apply": apply,
        "dry_run": not apply,
        "raw_dir": str(raw_dir),
        "dest_dir": str(dest_dir),
        "total": len(pdfs),
        "copied": copied,
        "dry_run_planned": dry_planned,
        "skipped": skipped,
        "errors": errors,
        "actions": actions,
        "note": "originals in _raw are NEVER deleted",
    }
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        mode = "DRY-RUN" if not apply else "APPLY"
        print(f"Migrate [{mode}]: {len(pdfs)} PDFs")
        print(f"  copied={copied} dry_planned={dry_planned} skipped={skipped} errors={errors}")
    return 0 if errors == 0 else 1


# ── verify ────────────────────────────────────────────────────────────────────

def cmd_verify(sources_dir: Path, as_json: bool) -> int:
    papers_dir = sources_dir / "papers"
    results: list[dict] = []
    if papers_dir.exists():
        for manifest_path in sorted(papers_dir.glob("**/manifest.json")):
            try:
                meta = json.loads(manifest_path.read_text())
                sha_expected = meta.get("sha256", "")
                pdf_files = list(manifest_path.parent.glob("*.pdf"))
                if not pdf_files:
                    results.append({"dir": str(manifest_path.parent), "status": "error", "reason": "no_pdf"})
                    continue
                pdf = pdf_files[0]
                sha_actual = _sha256(pdf)
                ok = sha_actual == sha_expected
                results.append({
                    "file": str(pdf),
                    "sha256_expected": sha_expected,
                    "sha256_actual": sha_actual,
                    "status": "ok" if ok else "sha_mismatch",
                })
            except Exception as exc:
                results.append({"dir": str(manifest_path.parent), "status": "error", "reason": str(exc)})

    passed = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] != "ok")
    out = {
        "ok": failed == 0,
        "sources_dir": str(sources_dir),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Verify: {passed}/{len(results)} pass")
        for r in results:
            tag = "✓" if r["status"] == "ok" else "✗"
            print(f"  {tag} {Path(r.get('file', r.get('dir', '?'))).name}  {r['status']}")
    return 0 if failed == 0 else 1


# ── list ──────────────────────────────────────────────────────────────────────

def cmd_list(sources_dir: Path, as_json: bool) -> int:
    papers_dir = sources_dir / "papers"
    entries: list[dict] = []
    if papers_dir.exists():
        for manifest_path in sorted(papers_dir.glob("**/manifest.json")):
            try:
                meta = json.loads(manifest_path.read_text())
                entries.append({
                    "name": meta.get("original_name", "?"),
                    "sha256": meta.get("sha256", "?")[:16],
                    "migrated_at": meta.get("migrated_at", "?"),
                    "size_bytes": meta.get("size_bytes", 0),
                    "dir": str(manifest_path.parent),
                })
            except Exception:
                pass

    out = {"ok": True, "count": len(entries), "entries": entries}
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Sources: {len(entries)} papers")
        for e in entries:
            print(f"  {e['name']:40s} sha={e['sha256']}  {e['migrated_at']}")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(prog="source_manifest.py")
    sub = ap.add_subparsers(dest="cmd")

    sc = sub.add_parser("scan")
    sc.add_argument("--raw-dir", default=str(RAW_DIR))
    sc.add_argument("--json", action="store_true", dest="as_json")

    mg = sub.add_parser("migrate")
    mg.add_argument("--raw-dir", default=str(RAW_DIR))
    mg.add_argument("--dest", default=str(PAPERS_DIR))
    mg.add_argument("--apply", action="store_true")
    mg.add_argument("--json", action="store_true", dest="as_json")

    vr = sub.add_parser("verify")
    vr.add_argument("--sources-dir", default=str(SOURCES_DIR))
    vr.add_argument("--json", action="store_true", dest="as_json")

    ls = sub.add_parser("list")
    ls.add_argument("--sources-dir", default=str(SOURCES_DIR))
    ls.add_argument("--json", action="store_true", dest="as_json")

    args = ap.parse_args()
    if args.cmd == "scan":
        return cmd_scan(Path(args.raw_dir), args.as_json)
    elif args.cmd == "migrate":
        return cmd_migrate(Path(args.raw_dir), Path(args.dest), args.apply, args.as_json)
    elif args.cmd == "verify":
        return cmd_verify(Path(args.sources_dir), args.as_json)
    elif args.cmd == "list":
        return cmd_list(Path(args.sources_dir), args.as_json)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
