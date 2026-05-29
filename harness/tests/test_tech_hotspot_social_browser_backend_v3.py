from __future__ import annotations

import argparse
import contextlib
import io
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "harness" / "scripts" / "tech_hotspot_radar.py"


def _load_namespace() -> dict:
    ns: dict = {"__file__": str(SCRIPT), "__name__": "tech_hotspot_radar_test"}
    code = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
    exec(code, ns)
    return ns


def _write_config(tmp_path: Path, *, state_dir: Path, db_path: Path) -> Path:
    cfg = {
        "output": {
            "state_dir": str(state_dir),
            "database": str(db_path),
        }
    }
    path = tmp_path / "tech-hotspot-radar.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def _seed_social_account(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS social_accounts (
            handle TEXT PRIMARY KEY,
            raw_handle TEXT NOT NULL DEFAULT '',
            account_id TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT 'x',
            display_name TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            tier TEXT NOT NULL DEFAULT 'tier1',
            enabled INTEGER NOT NULL DEFAULT 1,
            weight REAL NOT NULL DEFAULT 1.0,
            role_profile_json TEXT NOT NULL DEFAULT '{}',
            scan_policy_json TEXT NOT NULL DEFAULT '{}',
            collection_backend TEXT NOT NULL DEFAULT 'rss',
            last_success_at TEXT,
            last_error TEXT NOT NULL DEFAULT '',
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_scanned_at TEXT,
            imported_at TEXT NOT NULL DEFAULT ''
        );
        INSERT OR REPLACE INTO social_accounts
        (handle, category, tier, enabled, weight, imported_at)
        VALUES ('karpathy', 'research', 'tier1', 1, 1.0, '2026-05-29T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()


def test_social_browser_backend_artifact_root_uses_config_state_dir(tmp_path, monkeypatch):
    ns = _load_namespace()
    state_dir = tmp_path / "state-a"
    db_path = tmp_path / "tech-hotspot-radar.sqlite"
    config_path = _write_config(tmp_path, state_dir=state_dir, db_path=db_path)
    args = argparse.Namespace(
        command="collect-social",
        config=str(config_path),
        db=None,
        backend="auto",
        limit_accounts=1,
        per_account_limit=3,
        dry_run=True,
        force=True,
    )
    _seed_social_account(db_path)

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = ns["cmd_collect_social"](args)

    assert code in {0, 1}
    artifact_root = state_dir / "social-browser-backend-x"
    assert artifact_root.exists()
    raw_root = artifact_root / "knowledge_raw"
    queue_root = artifact_root / "extract_queue"
    assert any(raw_root.rglob("*.json")), "expected knowledge_raw artifact under configured state_dir"
    assert any(queue_root.rglob("*.json")), "expected extract_queue artifact under configured state_dir"


def test_social_browser_backend_disable_flag_rolls_back_to_legacy_path(tmp_path, monkeypatch):
    ns = _load_namespace()
    state_dir = tmp_path / "state-b"
    db_path = tmp_path / "tech-hotspot-radar.sqlite"
    config_path = _write_config(tmp_path, state_dir=state_dir, db_path=db_path)
    args = argparse.Namespace(
        command="collect-social",
        config=str(config_path),
        db=None,
        backend="auto",
        limit_accounts=1,
        per_account_limit=1,
        dry_run=True,
        force=True,
    )
    _seed_social_account(db_path)

    called = {"browser_backend": False}

    def _should_not_run(*_a, **_kw):
        called["browser_backend"] = True
        raise AssertionError("browser backend path should not run when rollback flag is enabled")

    def _fake_http_get_text(_url, _config):
        return """<rss><channel><item>
<title>Test post</title>
<link>https://x.com/karpathy/status/1790012345678901234</link>
<description>KV cache note https://github.com/vllm-project/vllm</description>
<pubDate>Thu, 29 May 2026 12:00:00 GMT</pubDate>
</item></channel></rss>"""

    monkeypatch.setenv("SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE", "1")
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    ns["_cmd_collect_social_browser_backend_x"] = _should_not_run
    ns["http_get_text"] = _fake_http_get_text

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        code = ns["cmd_collect_social"](args)

    assert code == 0
    assert called["browser_backend"] is False
    assert "disabled by rollback flag" in stdout.getvalue()

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM social_posts").fetchone()[0]
    conn.close()
    assert count >= 1

