"""Atomic archive writer for validated report bundles."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUIRED_ARTIFACTS = {
    "report.md": "report_md",
    "report.html": "report_html",
    "plan.json": "plan_json",
    "evidence_map.json": "evidence_map",
}


def archive_writer_commit(run_record: dict[str, Any], report_bundle: dict[str, Any], validator_report: dict[str, Any]) -> dict[str, Any]:
    if validator_report.get("overall") != "PASS":
        raise ValueError("refuse to archive report bundle when validator overall is not PASS")
    archive_dir = Path(str(run_record["archive_dir"]))
    tmp_dir = archive_dir.with_name(f".{archive_dir.name}.tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    artifacts = []
    try:
        for filename, key in REQUIRED_ARTIFACTS.items():
            value = report_bundle[key]
            path = tmp_dir / filename
            if filename.endswith(".json"):
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            else:
                path.write_text(str(value), encoding="utf-8")
            artifacts.append({"type": filename.rsplit(".", 1)[-1], "path": str(archive_dir / filename)})
        figure_manifest = report_bundle.get("figure_manifest")
        if isinstance(figure_manifest, dict) and figure_manifest:
            figures_dir = tmp_dir / "figures"
            figures_dir.mkdir(parents=True, exist_ok=True)
            (figures_dir / "figure-manifest.json").write_text(
                json.dumps(figure_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            artifacts.append({"type": "json", "path": str(archive_dir / "figures" / "figure-manifest.json")})
            for figure in figure_manifest.get("figures") or []:
                image_path = str(figure.get("image_path") or "").strip()
                if not image_path:
                    continue
                src = Path(image_path).expanduser()
                if not src.exists() or not src.is_file():
                    continue
                dst = figures_dir / src.name
                shutil.copy2(src, dst)
                artifacts.append({"type": src.suffix.lstrip(".") or "bin", "path": str(archive_dir / "figures" / src.name)})
        manifest = {
            "schema_version": "archive_manifest.v1",
            "archive_dir": str(archive_dir),
            "artifacts": artifacts,
            "chatgpt_session_url": str(run_record.get("chatgpt_session_url") or ""),
            "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        (tmp_dir / "archive_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if archive_dir.exists():
            shutil.rmtree(archive_dir)
        tmp_dir.replace(archive_dir)
        return manifest
    except Exception:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        raise
