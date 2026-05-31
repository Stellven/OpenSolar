import importlib.util
import sys
import urllib.error
from email.message import Message
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tech_hotspot_radar.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("tech_hotspot_radar_github_auth_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_github_token_env_can_live_under_github_config(monkeypatch):
    mod = load_mod()
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "ghp_test_token")

    headers = mod.github_api_headers(
        {
            "fetch": {"user_agent": "test-agent"},
            "github": {"github_token_env": "TEST_GITHUB_TOKEN"},
        },
        accept="application/vnd.github+json",
    )

    assert headers["Authorization"] == "Bearer ghp_test_token"
    assert headers["User-Agent"] == "test-agent"


def test_github_api_json_raises_typed_rate_limit(monkeypatch):
    mod = load_mod()

    def fake_urlopen(_req, timeout):
        headers = Message()
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Reset"] = "1780000000"
        raise urllib.error.HTTPError(
            "https://api.github.com/repos/a/b",
            403,
            "Forbidden",
            headers,
            None,
        )

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    try:
        mod.github_api_json("/repos/a/b", {"fetch": {"timeout_seconds": 1}})
    except mod.GitHubRateLimitError as exc:
        assert "GitHub API 403 /repos/a/b" in str(exc)
        assert exc.reset_at
    else:
        raise AssertionError("expected GitHubRateLimitError")

