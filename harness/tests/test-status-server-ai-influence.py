#!/usr/bin/env python3
"""Regression test for the AI Influence report center."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_MODULE = ROOT / "lib" / "symphony" / "status-server.py"
AI_SCRIPT = ROOT / "scripts" / "ai_influence_daily.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    status = load_module("solar_status_server_ai_influence_test", STATUS_MODULE)
    ai = load_module("solar_ai_influence_daily_test", AI_SCRIPT)
    with tempfile.TemporaryDirectory(prefix="solar-ai-influence-ui-test-") as td:
        base = Path(td)
        harness = base / "harness"
        knowledge = base / "Knowledge"
        run_dir = knowledge / "_raw" / "ai-influence-daily-digest" / "2026-05-23"
        write(run_dir / "digest.md", "# AI Influence Digest\n")
        write(run_dir / "digest.html", "<!doctype html><h1>AI Influence</h1>")
        write(
            run_dir / "digest.json",
            json.dumps(
                {
                    "date": "2026-05-23",
                    "analysis": {
                        "analysis_status": "ok",
                        "model": "glm-5.1",
                        "items": [{"title": "item"}],
                        "trend_analysis": {"core_trends": [{"theme": "Agent 工作流"}]},
                    },
                    "stats": {"top_scored": 7},
                    "gmail": {"status": "sent"},
                    "wiki_dispatch": str(knowledge / "_raw" / "solar-harness" / ".dispatch" / "wiki-ingest-ai-influence-test.md"),
                },
                ensure_ascii=False,
            ),
        )

        status.HARNESS_DIR = harness
        status.REPORTS_DIR = harness / "reports"
        status.KNOWLEDGE_DIR = knowledge
        status.AI_INFLUENCE_RAW_DIR = run_dir.parent
        status.OPEN_ALLOWED_ROOTS = [harness, knowledge]

        payload = status._ai_influence_payload(limit=10)
        assert payload["ok"] is True
        assert payload["count"] == 1
        item = payload["items"][0]
        assert item["date"] == "2026-05-23"
        assert item["items"] == 1
        assert item["core_trends"] == 1
        assert item["primary"]["view_url"].startswith("/ai-influence/report?path=")
        html = status._ai_influence_html()
        assert "AI Influence 报告中心" in html
        assert "打开报告" in html

        import os

        old_vault = os.environ.get("OBSIDIAN_VAULT_PATH")
        os.environ["OBSIDIAN_VAULT_PATH"] = str(knowledge)
        try:
            dispatch = Path(ai.create_wiki_ingest_dispatch(run_dir, "2026-05-23"))
        finally:
            if old_vault is None:
                os.environ.pop("OBSIDIAN_VAULT_PATH", None)
            else:
                os.environ["OBSIDIAN_VAULT_PATH"] = old_vault
        text = dispatch.read_text(encoding="utf-8")
        assert dispatch.parent == knowledge / "_raw" / "solar-harness" / ".dispatch"
        assert "type: wiki-dispatch" in text
        assert "skill: wiki-ingest" in text
        assert "status: pending" in text
        assert f"source={run_dir / 'digest.md'}" in text

    print("PASS status-server AI Influence report center")


if __name__ == "__main__":
    main()
