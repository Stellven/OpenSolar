from __future__ import annotations

import os
import sys

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


def test_auto_search_never_uses_jina_or_duck(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)
    monkeypatch.setattr(research_cli, "arxiv_search", lambda *args, **kwargs: ([{"title": "Paper", "url": "https://arxiv.org/abs/1", "connector": "arxiv", "rank": 1}], []))

    hits, errors = research_cli.web_search("agentic runtime", 2, provider="auto")

    assert hits[0]["connector"] == "arxiv"
    assert not any("jina" in error.lower() or "duck" in error.lower() for error in errors)
