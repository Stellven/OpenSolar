#!/usr/bin/env python3
"""Regression tests for GitHub trends digest parsing and rendering."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "github_trends_digest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("github_trends_digest_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["github_trends_digest_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    mod = load_module()
    html = """
    <article class="Box-row">
      <a href="/sponsors/noise">Sponsor</a>
      <h2 class="h3 lh-condensed"><a href="/owner/agent-runtime">owner / agent-runtime</a></h2>
      <p class="col-9 color-fg-muted my-1 pr-4">AI agent workflow runtime with MCP skills.</p>
      <span itemprop="programmingLanguage">Python</span>
      <a href="/owner/agent-runtime/stargazers"><svg></svg>1,234</a>
      <a href="/owner/agent-runtime/forks"><svg></svg>56</a>
      <span>99 stars today</span>
    </article>
    """
    rows = mod.parse_github_trending(html, "daily")
    assert len(rows) == 1
    assert rows[0]["repo"] == "owner/agent-runtime"
    assert rows[0]["stars"] == 1234
    assert rows[0]["stars_delta"] == 99

    with tempfile.TemporaryDirectory(prefix="github-trends-test-") as td:
        base = Path(td)
        config = {
            "output": {
                "database": str(base / "state" / "github.sqlite"),
                "dispatch_dir": str(base / "dispatch"),
                "raw_dir": str(base / "raw"),
                "vault_path": str(base / "vault"),
            },
            "categories": {
                "agent": {"label": "Agent", "keywords": ["agent", "mcp"]},
                "ai": {"label": "AI", "keywords": ["llm", "ai"]},
            },
        }
        conn = mod.ensure_db(base / "state" / "github.sqlite")
        mod.save_snapshots(conn, rows, config, "2026-05-23T00:00:00Z")
        analysis = mod.analyze(config)
        assert analysis["windows"]["daily"]
        assert analysis["windows"]["daily"][0]["category"] == "agent"
        old_backend = os.environ.get("GITHUB_TRENDS_MAIL_BACKEND")
        os.environ["GITHUB_TRENDS_MAIL_BACKEND"] = "preview"
        digest = mod.write_digest(config, analysis, "2026-05-23")
        if old_backend is None:
            os.environ.pop("GITHUB_TRENDS_MAIL_BACKEND", None)
        else:
            os.environ["GITHUB_TRENDS_MAIL_BACKEND"] = old_backend
        assert Path(digest["digest_md"]).exists()
        assert Path(digest["digest_html"]).exists()
        assert Path(digest["wiki_dispatch"]).exists()

    print("PASS github trends digest")


if __name__ == "__main__":
    main()
