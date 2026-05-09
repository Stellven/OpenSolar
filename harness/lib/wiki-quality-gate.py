#!/usr/bin/env python3
"""
wiki-quality-gate.py — detect and quarantine low-quality derived wiki pages.

This is intentionally conservative: it does not delete source uploads or
user-authored notes. It only moves machine-generated PDF stubs out of the
Obsidian vault when --apply is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any


HOME = Path.home()
DEFAULT_VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", str(HOME / "Knowledge")))
DEFAULT_DB = Path(os.environ.get("SOLAR_DB", str(HOME / ".solar" / "solar.db")))
DEFAULT_QUARANTINE = HOME / ".solar" / "harness" / "quarantine" / "wiki-low-quality"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def frontmatter_field(text: str, name: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for raw in parts[1].splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def quality_findings(vault: Path, min_words: int) -> list[dict[str, Any]]:
    roots = [vault / "synthesis", vault / "references", vault / "concepts"]
    findings: list[dict[str, Any]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            words = len(re.findall(r"\w+", text))
            reasons = []
            if "Auto-extracted from PDF" in text:
                reasons.append("auto_extracted_pdf_stub")
            if "Auto-generated stub from batch backfill" in text:
                reasons.append("batch_backfill_stub")
            if "Abstract" in text[:3000] and words < min_words and frontmatter_field(text, "source_type") == "pdf":
                reasons.append("abstract_only_pdf_note")
            if words < min_words and any(r in reasons for r in ("auto_extracted_pdf_stub", "batch_backfill_stub")):
                findings.append({
                    "path": str(path),
                    "relative_path": str(path.relative_to(vault)),
                    "words": words,
                    "bytes": path.stat().st_size,
                    "title": frontmatter_field(text, "title") or path.stem,
                    "source": frontmatter_field(text, "source") or frontmatter_field(text, "source_file"),
                    "dispatch_id": frontmatter_field(text, "dispatch_id") or frontmatter_field(text, "dispatch"),
                    "reasons": reasons,
                    "sha256": sha256_file(path),
                })
    return findings


def mark_deleted_in_db(db_path: Path, rel_path: str) -> bool:
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute(
            "UPDATE obsidian_vault_index SET deleted_at = ? WHERE file_path = ?",
            (now, rel_path),
        )
        try:
            conn.execute(
                "DELETE FROM fts_unified_search WHERE doc_id = ?",
                (f"obsidian:{rel_path}",),
            )
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def quarantine(findings: list[dict[str, Any]], vault: Path, dest_root: Path, db_path: Path) -> dict[str, Any]:
    batch = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = dest_root / batch
    manifest_path = dest / "manifest.jsonl"
    dest.mkdir(parents=True, exist_ok=True)
    moved = []
    for item in findings:
        src = Path(item["path"])
        rel = Path(item["relative_path"])
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(target))
        db_marked = mark_deleted_in_db(db_path, item["relative_path"])
        record = {**item, "quarantined_to": str(target), "db_marked_deleted": db_marked}
        moved.append(record)
        with manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"batch": batch, "dest": str(dest), "manifest": str(manifest_path), "moved": moved}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit/quarantine low-quality wiki pages")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--quarantine-dir", default=str(DEFAULT_QUARANTINE))
    parser.add_argument("--min-words", type=int, default=1200)
    parser.add_argument("--apply", action="store_true", help="Move low-quality pages out of the vault")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault)
    findings = quality_findings(vault, args.min_words)
    result: dict[str, Any] = {
        "ok": True,
        "vault": str(vault),
        "apply": args.apply,
        "min_words": args.min_words,
        "low_quality_count": len(findings),
        "findings": findings,
    }
    if args.apply and findings:
        result["quarantine"] = quarantine(findings, vault, Path(args.quarantine_dir), Path(args.db))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"low_quality_count={len(findings)} apply={args.apply}")
        for item in findings:
            print(f"- {item['relative_path']} words={item['words']} reasons={','.join(item['reasons'])}")
        if "quarantine" in result:
            print(f"quarantine={result['quarantine']['dest']}")
    return 1 if findings and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
