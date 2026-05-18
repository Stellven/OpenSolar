from __future__ import annotations

import os
import sys
from types import SimpleNamespace

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research import cli as research_cli


ARXIV_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <title>Agentic Runtime Architectures</title>
    <summary>We study durable execution for agent runtimes.</summary>
    <link href="http://arxiv.org/abs/2501.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2501.00001v1" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


def test_legacy_http_search_is_disabled():
    hits, errors = research_cli.http_web_search("agentic runtime", 3)

    assert hits == []
    assert errors
    assert "legacy http search disabled" in errors[0]


def test_arxiv_search_parses_official_atom_api(monkeypatch):
    monkeypatch.setattr(research_cli, "http_get_text", lambda *args, **kwargs: ARXIV_SAMPLE)

    hits, errors = research_cli.arxiv_search("agentic runtime", 3)

    assert errors == []
    assert hits[0]["connector"] == "arxiv"
    assert hits[0]["title"] == "Agentic Runtime Architectures"
    assert hits[0]["url"].startswith("http://arxiv.org/abs/")


def test_google_cse_element_requires_search_engine_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)

    hits, errors = research_cli.google_cse_element_search("agentic runtime", 2)

    assert hits == []
    assert "google-cse-element missing" in errors[0]


def test_google_cse_oauth_requires_client_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CSE_ID", "cx-test")
    monkeypatch.setenv("GOOGLE_CSE_CLIENT_SECRET", str(tmp_path / "missing-client-secret.json"))

    hits, errors = research_cli.google_cse_oauth_search("agentic runtime", 2)

    assert hits == []
    assert "google-cse-oauth missing client secret" in errors[0]


def test_auto_search_never_uses_jina_or_duck(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)
    monkeypatch.setattr(research_cli, "google_cse_oauth_search", lambda *args, **kwargs: ([], ["oauth unavailable"]))
    monkeypatch.setattr(research_cli, "google_cse_element_search", lambda *args, **kwargs: ([], ["element unavailable"]))
    monkeypatch.setattr(research_cli, "arxiv_search", lambda *args, **kwargs: ([{"title": "Paper", "url": "https://arxiv.org/abs/1", "connector": "arxiv", "rank": 1}], []))

    hits, errors = research_cli.web_search("agentic runtime", 2, provider="auto")

    assert hits[0]["connector"] == "arxiv"
    assert not any("jina" in error.lower() or "duck" in error.lower() for error in errors)


def test_auto_search_uses_cse_element_after_json_failure(monkeypatch):
    monkeypatch.setattr(research_cli, "google_cse_search", lambda *args, **kwargs: ([], ["json forbidden"]))
    monkeypatch.setattr(research_cli, "google_cse_oauth_search", lambda *args, **kwargs: ([], ["oauth unavailable"]))
    monkeypatch.setattr(research_cli, "google_cse_element_search", lambda *args, **kwargs: ([{"title": "Doc", "url": "https://example.com", "connector": "google-cse-element", "rank": 1}], []))

    hits, errors = research_cli.web_search("agentic runtime", 2, provider="auto")

    assert hits[0]["connector"] == "google-cse-element"
    assert "json forbidden" in errors


def test_auto_search_uses_cse_oauth_after_json_failure(monkeypatch):
    monkeypatch.setattr(research_cli, "google_cse_search", lambda *args, **kwargs: ([], ["json forbidden"]))
    monkeypatch.setattr(research_cli, "google_cse_oauth_search", lambda *args, **kwargs: ([{"title": "Doc", "url": "https://example.com", "connector": "google-cse-oauth", "rank": 1}], []))

    hits, errors = research_cli.web_search("agentic runtime", 2, provider="auto")

    assert hits[0]["connector"] == "google-cse-oauth"
    assert "json forbidden" in errors


def test_deepresearch_doctor_reports_model_and_pending_google(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)
    monkeypatch.setattr(research_cli.shutil, "which", lambda name: "/usr/local/bin/claude")
    monkeypatch.setattr(
        research_cli.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="SOLAR_OK\n", stderr=""),
    )

    payload = research_cli.build_deepresearch_doctor(model="sonnet", live_search=False)

    assert payload["ok"] is True
    assert payload["status"] == "pending"
    assert payload["checks"]["chief_editor_model"]["status"] == "ok"
    assert payload["checks"]["google_cse"]["status"] == "pending"


def test_deepresearch_doctor_warns_when_fallback_model_selected(monkeypatch):
    monkeypatch.setattr(research_cli.shutil, "which", lambda name: "/usr/local/bin/claude")

    def fake_run(cmd, **kwargs):
        model = cmd[cmd.index("--model") + 1]
        if model == "opus":
            return SimpleNamespace(returncode=1, stdout="API Error 1210", stderr="")
        return SimpleNamespace(returncode=0, stdout="SOLAR_OK\n", stderr="")

    monkeypatch.setattr(research_cli.subprocess, "run", fake_run)

    payload = research_cli.build_deepresearch_doctor(model="opus", model_candidates="sonnet")

    assert payload["ok"] is True
    assert payload["status"] == "warn"
    assert payload["checks"]["chief_editor_model"]["selected_model"] == "sonnet"
    assert "chief_editor_model" in payload["warnings"]


def test_deepresearch_doctor_can_require_google(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)

    payload = research_cli.build_deepresearch_doctor(skip_model=True, require_google=True)

    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert "google_cse" in payload["errors"]


def test_deepresearch_doctor_arxiv_live_failure_is_warn_by_default(monkeypatch):
    monkeypatch.setattr(research_cli, "arxiv_search", lambda *args, **kwargs: ([], ["arxiv: HTTP Error 429"]))
    monkeypatch.setattr(research_cli, "_doctor_check_google_cse", lambda *args, **kwargs: {"status": "ok", "ok": True})

    payload = research_cli.build_deepresearch_doctor(skip_model=True, live_search=True)

    assert payload["ok"] is True
    assert payload["status"] in {"warn", "pending"}
    assert payload["checks"]["arxiv"]["status"] == "warn"
    assert "arxiv" in payload["warnings"]


def test_deepresearch_doctor_can_require_arxiv(monkeypatch):
    monkeypatch.setattr(research_cli, "arxiv_search", lambda *args, **kwargs: ([], ["arxiv: HTTP Error 429"]))
    monkeypatch.setattr(research_cli, "_doctor_check_google_cse", lambda *args, **kwargs: {"status": "ok", "ok": True})

    payload = research_cli.build_deepresearch_doctor(skip_model=True, live_search=True, require_arxiv=True)

    assert payload["ok"] is False
    assert payload["checks"]["arxiv"]["status"] == "error"
    assert "arxiv" in payload["errors"]
