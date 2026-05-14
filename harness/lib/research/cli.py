"""DeepResearch CLI — 14 subcommands.

Spec: S04 orchestration-ui / N1
Usage: solar-harness research <subcommand> [args...]

S03 provided: init, add-source, extract, ledger, status
S04 adds:     run, plan, search, mine, outline, write, check, compile, export

Each subcommand is a thin wrapper that calls into lib/research.
New subcommands are stubs that validate args and route to the correct module.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import os
import re
import sqlite3
import subprocess
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_HARNESS_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research import hashing, ids, schemas, storage

WEB_USER_AGENT = "Solar-Harness-DeepResearch/1.0 (+local; evidence-ledger)"
WEB_TIMEOUT_SEC = 12
BROWSER_USE_ROOT = Path.home() / ".claude" / "mcp-servers" / "browser-use"
BROWSER_USE_SERVER = BROWSER_USE_ROOT / "server.py"
BROWSER_USE_PYTHON = BROWSER_USE_ROOT / ".venv" / "bin" / "python"


def emit_json(args: argparse.Namespace, payload: dict) -> bool:
    """Emit machine-readable output when --json is requested."""
    if not getattr(args, "json", False):
        return False
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return True


def clean_evidence_content(content: str) -> str:
    """Return only the human-readable evidence span, hiding inline metadata."""
    return str(content or "").split("\x00", 1)[0]


def http_get_text(url: str, timeout: int = WEB_TIMEOUT_SEC) -> str:
    """Fetch a URL with a stable User-Agent and return decoded text."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": WEB_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(2_500_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def strip_html(raw: str) -> str:
    """Convert lightweight HTML to readable text without adding dependencies."""
    text = html.unescape(raw or "")
    text = re.sub(r"(?is)<(script|style|noscript|svg|template).*?</\1>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"(?is)\b(x-data|x-effect|x-show|@click|:class|document\.body|classList|toggle|servicesOpen)\b[^\n]{0,220}", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    lines = []
    noise_terms = (
        "please login", "bookmark", "cookie", "privacy policy", "terms of service",
        "back en english", "español", "français", "deutsch", "日本語", "한국어",
        "bahasa indonesia", "português", "हिन्दी", "中文", "العربية",
    )
    for line in text.splitlines():
        line = line.strip(" \t-•|")
        if not line:
            continue
        lower = line.lower()
        if any(term in lower for term in noise_terms):
            continue
        if any(term in lower for term in ("if(!", "servicesopen", "document.body", "classlist", "nt.body", "function(")):
            continue
        if len(line) < 35 and not re.search(r"[.!?。！？]$", line):
            continue
        if sum(1 for ch in line if ch in "{}[]<>/\\|=;") > max(6, len(line) * 0.08):
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def looks_binary_or_pdf(text: str, url: str = "") -> bool:
    """Detect content that should not be treated as extracted prose."""
    lower_url = (url or "").lower()
    if lower_url.endswith(".pdf"):
        return True
    sample = (text or "")[:4096]
    if sample.startswith("%PDF"):
        return True
    if "\ufffd" in sample and sample.count("\ufffd") >= 5:
        return True
    if not sample:
        return False
    bad = sum(1 for ch in sample if (ord(ch) < 32 and ch not in "\n\r\t"))
    return bad / max(len(sample), 1) > 0.02


def _decode_duck_url(url: str) -> str:
    parsed = urllib.parse.urlparse(html.unescape(url))
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        if qs.get("uddg"):
            return qs["uddg"][0]
    return html.unescape(url)


def _parse_jina_search(markdown: str, max_results: int) -> list[dict]:
    hits: list[dict] = []
    title = ""
    url = ""
    snippet_parts: list[str] = []
    for raw_line in (markdown or "").splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("title:"):
            if title and url:
                hits.append({"title": title, "url": url, "snippet": " ".join(snippet_parts).strip()})
                if len(hits) >= max_results:
                    return hits
            title = line.split(":", 1)[1].strip()
            url = ""
            snippet_parts = []
        elif lower.startswith("url:"):
            url = line.split(":", 1)[1].strip()
        elif line and title and not lower.startswith(("published time:", "source:")):
            snippet_parts.append(line)
    if title and url and len(hits) < max_results:
        hits.append({"title": title, "url": url, "snippet": " ".join(snippet_parts).strip()})
    return hits[:max_results]


def _parse_duckduckgo_html(raw_html: str, max_results: int) -> list[dict]:
    hits: list[dict] = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.I | re.S,
    )
    for match in pattern.finditer(raw_html or ""):
        url = _decode_duck_url(match.group("href"))
        title = strip_html(match.group("title"))
        if not url or not title:
            continue
        hits.append({"title": title, "url": url, "snippet": ""})
        if len(hits) >= max_results:
            break
    if hits:
        return hits

    fallback = re.compile(r'<a[^>]+href="(?P<href>https?://[^"]+)"[^>]*>(?P<title>.*?)</a>', re.I | re.S)
    for match in fallback.finditer(raw_html or ""):
        url = _decode_duck_url(match.group("href"))
        if "duckduckgo.com" in urllib.parse.urlparse(url).netloc:
            continue
        title = strip_html(match.group("title"))
        if url and title:
            hits.append({"title": title, "url": url, "snippet": ""})
        if len(hits) >= max_results:
            break
    return hits


def _extract_json_array(text: str) -> list[dict]:
    """Extract a JSON list from model/browser output."""
    raw = (text or "").strip()
    candidates = [raw]
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.S)
    if match:
        candidates.insert(0, match.group(1))
    match = re.search(r"(\[\s*\{.*?\}\s*\])", raw, re.S)
    if match:
        candidates.insert(0, match.group(1))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except json.JSONDecodeError:
            continue
    return []


def _normalize_search_hits(raw_hits: list[dict], provider: str, max_results: int) -> list[dict]:
    hits: list[dict] = []
    seen: set[str] = set()
    for raw in raw_hits:
        url = str(raw.get("url") or raw.get("link") or raw.get("href") or "").strip()
        title = str(raw.get("title") or raw.get("name") or url or "").strip()
        snippet = str(raw.get("snippet") or raw.get("summary") or raw.get("description") or "").strip()
        if not url or not title or url in seen:
            continue
        if not url.startswith(("http://", "https://")):
            continue
        parsed_url = urllib.parse.urlparse(url)
        blocked_hosts = ("duckduckgo.com", "html.duckduckgo.com", "bing.com", "www.bing.com", "go.microsoft.com")
        if any(host in parsed_url.netloc for host in blocked_hosts):
            if not parsed_url.path.startswith("/l/"):
                continue
            url = _decode_duck_url(url)
            parsed_url = urllib.parse.urlparse(url)
            if any(host in parsed_url.netloc for host in blocked_hosts):
                continue
        seen.add(url)
        hits.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "connector": provider,
            "rank": len(hits) + 1,
        })
        if len(hits) >= max_results:
            break
    return hits


def browser_use_search(query: str, max_results: int, timeout: int = 90) -> tuple[list[dict], list[str]]:
    """Use browser rendering for search pages when available.

    Many public search pages now present CAPTCHA or dynamic shells to headless
    browsers.  This function is still attempted first for provider=browser-use,
    but DeepResearch treats source discovery and page extraction as separate
    capabilities: if browser-rendered discovery fails, browser-use remains the
    preferred fetch/extract provider for concrete URLs.
    """
    if os.getenv("SOLAR_RESEARCH_DISABLE_BROWSER_USE") == "1":
        return [], ["browser-use disabled by SOLAR_RESEARCH_DISABLE_BROWSER_USE=1"]
    if not BROWSER_USE_SERVER.exists():
        return [], [f"browser-use server missing: {BROWSER_USE_SERVER}"]

    python_bin = str(BROWSER_USE_PYTHON if BROWSER_USE_PYTHON.exists() else sys.executable)
    search_url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    script = """
import asyncio, importlib.util, json, sys
spec = importlib.util.spec_from_file_location("solar_browser_use_server", %(server)r)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

async def main():
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(%(url)r, wait_until="domcontentloaded", timeout=30000)
            links = await page.evaluate(\"\"\"() => Array.from(document.querySelectorAll('a')).map((a) => ({
                title: (a.innerText || a.textContent || '').trim(),
                url: a.href || '',
                snippet: (a.closest('li, article, div')?.innerText || '').trim()
            })).filter((x) => x.title && x.url)\"\"\")
            await browser.close()
        try:
            await mod.browser_close()
        except Exception:
            pass
        print(json.dumps({"ok": True, "links": links}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise

asyncio.run(main())
""" % {"server": str(BROWSER_USE_SERVER), "url": search_url}
    with tempfile.NamedTemporaryFile("w", suffix="-browser-use-search.py", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name
    try:
        result = subprocess.run(
            [python_bin, script_path],
            cwd=str(BROWSER_USE_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [], [f"browser-use timeout after {timeout}s"]
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        return [], ["browser-use failed: " + " | ".join(detail)]
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return [], ["browser-use returned non-json stdout"]
    if not payload.get("ok"):
        return [], [f"browser-use error: {payload.get('error') or 'unknown'}"]
    raw_text = payload.get("text") or ""
    hits = _normalize_search_hits(payload.get("links") or [], "browser-use", max_results)
    if not hits:
        hits = _normalize_search_hits(_extract_json_array(raw_text), "browser-use", max_results)
    if not hits:
        hits = _normalize_search_hits(_parse_duckduckgo_html(raw_text, max_results), "browser-use", max_results)
    if not hits:
        return [], ["browser-use produced no parseable search hits"]
    return hits, []


def http_web_search(query: str, max_results: int) -> tuple[list[dict], list[str]]:
    """Search the web using dependency-free public endpoints as fallback.

    The command never fabricates hits: failures are returned as explicit errors.
    """
    errors: list[str] = []
    if max_results <= 0:
        return [], ["max_results must be > 0"]

    encoded = urllib.parse.urlencode({"q": query})
    providers = [
        ("jina", f"https://s.jina.ai/?{encoded}"),
        ("duckduckgo", f"https://duckduckgo.com/html/?{encoded}"),
    ]
    raw_hits: list[dict] = []
    for provider, url in providers:
        try:
            raw = http_get_text(url)
            parsed = _parse_jina_search(raw, max_results) if provider == "jina" else _parse_duckduckgo_html(raw, max_results)
            for hit in parsed:
                hit["connector"] = provider
                raw_hits.append(hit)
                if len(raw_hits) >= max_results:
                    return _normalize_search_hits(raw_hits, provider, max_results), errors
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            errors.append(f"{provider}: {exc}")
    return _normalize_search_hits(raw_hits, "http-fallback", max_results), errors


def web_search(query: str, max_results: int, provider: str = "auto") -> tuple[list[dict], list[str]]:
    """Search provider router: browser-use first, HTTP only as fallback."""
    errors: list[str] = []
    if provider not in {"auto", "browser-use", "http"}:
        return [], [f"unknown search provider: {provider}"]

    if provider in {"auto", "browser-use"}:
        hits, browser_errors = browser_use_search(query, max_results)
        errors.extend(browser_errors)
        if hits or provider == "browser-use":
            return hits, errors

    hits, http_errors = http_web_search(query, max_results)
    errors.extend(http_errors)
    return hits, errors


def fetch_url_readable(url: str) -> tuple[str, str | None]:
    """Fetch URL content and strip HTML. Returns (text, error)."""
    if looks_binary_or_pdf("", url):
        return "", "pdf_requires_mineru"
    try:
        raw = http_get_text(url)
        if looks_binary_or_pdf(raw, url):
            return "", "binary_or_pdf_content"
        text = strip_html(raw)
        if looks_binary_or_pdf(text, url):
            return "", "binary_or_pdf_content"
        if len(text) < 200:
            return text, f"short_content:{len(text)}"
        return text, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return "", str(exc)


def browser_use_fetch_url(url: str, timeout: int = 60) -> tuple[str, str | None]:
    """Fetch readable page text via the configured browser-use server module."""
    if os.getenv("SOLAR_RESEARCH_DISABLE_BROWSER_USE") == "1":
        return "", "browser-use disabled by SOLAR_RESEARCH_DISABLE_BROWSER_USE=1"
    if not BROWSER_USE_SERVER.exists():
        return "", f"browser-use server missing: {BROWSER_USE_SERVER}"
    if looks_binary_or_pdf("", url):
        return "", "pdf_requires_mineru"
    python_bin = str(BROWSER_USE_PYTHON if BROWSER_USE_PYTHON.exists() else sys.executable)
    script = """
import asyncio, importlib.util, json
spec = importlib.util.spec_from_file_location("solar_browser_use_server", %(server)r)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

async def main():
    try:
        result = await mod.browser_navigate(%(url)r)
        text = result[0].text if result else ""
        try:
            await mod.browser_close()
        except Exception:
            pass
        print(json.dumps({"ok": True, "text": text}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise

asyncio.run(main())
""" % {"server": str(BROWSER_USE_SERVER), "url": url}
    with tempfile.NamedTemporaryFile("w", suffix="-browser-use-fetch.py", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name
    try:
        result = subprocess.run(
            [python_bin, script_path],
            cwd=str(BROWSER_USE_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", f"browser-use fetch timeout after {timeout}s"
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
        return "", "browser-use fetch failed: " + " | ".join(detail)
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return "", "browser-use fetch returned non-json stdout"
    if not payload.get("ok"):
        return "", f"browser-use fetch error: {payload.get('error') or 'unknown'}"
    text = strip_html(payload.get("text") or "")
    if looks_binary_or_pdf(text, url):
        return "", "binary_or_pdf_content"
    if len(text) < 120:
        return text, f"short_content:{len(text)}"
    return text, None


def insert_source(
    conn: sqlite3.Connection,
    run_id: str,
    title: str,
    text: str,
    url: str | None = None,
    source_type: str = "web",
    relevance_score: float = 0.6,
) -> str:
    """Insert a research source with full text preserved in content_span."""
    safe_text = (text or "").strip()
    if not safe_text:
        safe_text = title or url or "empty source"
    content_hash = hashing.content_hash(f"{url or ''}\n{safe_text}")
    content_span = json.dumps({"start": 0, "end": len(safe_text), "text": safe_text, "url": url or ""}, ensure_ascii=False)
    try:
        conn.execute(
            "INSERT INTO research_sources (run_id, url, title, source_type, content_hash, content_span, relevance_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, url, title or "Untitled", source_type, content_hash, content_span, relevance_score),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    row = conn.execute(
        "SELECT id FROM research_sources WHERE run_id = ? AND content_hash = ?",
        (run_id, content_hash),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"source insert failed for {title or url}")
    return row["id"]


def extract_source_to_evidence(conn: sqlite3.Connection, run_id: str, source_id: str) -> str:
    """Extract one source into one evidence item and return evidence id."""
    row = conn.execute(
        "SELECT * FROM research_sources WHERE id = ? AND run_id = ?",
        (source_id, run_id),
    ).fetchone()
    if row is None:
        raise ValueError(f"source {source_id} not found in run {run_id}")

    from research.evidence.ledger import write_evidence

    span_text = row["title"] or "Untitled source"
    try:
        span_payload = json.loads(row["content_span"] or "{}")
        raw_text = str(span_payload.get("text") or "")
        start = int(span_payload.get("start") or 0)
        end = int(span_payload.get("end") or len(raw_text) or len(span_text))
        if raw_text:
            span_text = raw_text[start:end]
    except Exception:
        pass
    span_text = span_text.strip()
    if not span_text:
        span_text = row["title"] or row["url"] or "empty source"
    ch = hashing.content_hash(span_text)
    end = len(span_text)
    eid = ids.evidence_id(source_id, 0, end, ch)
    evidence_source_type = row["source_type"] if str(row["source_type"] or "").startswith("internal_") else "document"
    item = schemas.EvidenceItem(
        evidence_id=eid,
        source_id=source_id,
        source_type=evidence_source_type,
        content_hash=ch,
        span_start=0,
        span_end=end,
        span_text=span_text,
        evidence_type="direct_quote",
        relevance_score=0.7,
        support_direction="supporting",
    )
    try:
        write_evidence(conn, item, run_id)
    except sqlite3.IntegrityError:
        pass
    return eid


def extract_all_sources(conn: sqlite3.Connection, run_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM research_sources WHERE run_id = ? ORDER BY fetched_at, id",
        (run_id,),
    ).fetchall()
    eids: list[str] = []
    for row in rows:
        eids.append(extract_source_to_evidence(conn, run_id, row["id"]))
    return eids


def split_claim_sentences(text: str, limit: int = 3) -> list[str]:
    cleaned = re.sub(r"\s+", " ", clean_evidence_content(text)).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+|[；;]\s*|\n+", cleaned)
    claims = []
    for part in parts:
        claim = part.strip(" -•\t")
        lower = claim.lower()
        if len(claim) < 24:
            continue
        if any(term in lower for term in ("if(!", "servicesopen", "document.body", "classlist", "x-effect", "function(", "nt.body")):
            continue
        if sum(1 for ch in claim if ch in "{}[]<>/\\|=;") > max(6, len(claim) * 0.08):
            continue
        claims.append(claim)
    if not claims and len(cleaned) >= 24:
        claims = [cleaned[:240].strip()]
    return claims[:limit]


def mine_claims_for_run(conn: sqlite3.Connection, run_id: str) -> tuple[int, int]:
    evidence = conn.execute(
        "SELECT id, content FROM evidence_items WHERE run_id = ? ORDER BY span_start, id",
        (run_id,),
    ).fetchall()
    inserted_claims = 0
    inserted_links = 0
    counter = 1
    for ev in evidence:
        for claim_text in split_claim_sentences(ev["content"]):
            cid = ids.claim_id(counter, claim_text)
            ch = hashing.content_hash(claim_text)
            try:
                conn.execute(
                    "INSERT INTO claims (id, run_id, claim_text, claim_type, stance, confidence, content_hash) "
                    "VALUES (?, ?, ?, 'assertion', 'supports', 0.7, ?)",
                    (cid, run_id, claim_text, ch),
                )
                inserted_claims += 1
            except sqlite3.IntegrityError:
                pass
            lid = ids.link_id(cid, ev["id"])
            try:
                conn.execute(
                    "INSERT INTO claim_evidence (id, run_id, claim_id, evidence_id, relation, strength) "
                    "VALUES (?, ?, ?, ?, 'supports', 0.7)",
                    (lid, run_id, cid, ev["id"]),
                )
                inserted_links += 1
            except sqlite3.IntegrityError:
                pass
            counter += 1
    conn.commit()
    return inserted_claims, inserted_links


def ensure_outline(conn: sqlite3.Connection, run_id: str) -> int:
    existing = conn.execute(
        "SELECT COUNT(*) FROM report_sections WHERE run_id = ?",
        (run_id,),
    ).fetchone()[0]
    if existing:
        return existing
    sections = [
        ("executive_summary", "Executive Summary", 1),
        ("source_landscape", "Source Landscape", 2),
        ("evidence_synthesis", "Evidence Synthesis", 3),
        ("claims_and_implications", "Claims and Implications", 4),
        ("open_questions", "Open Questions", 5),
    ]
    for stype, title, order in sections:
        conn.execute(
            "INSERT INTO report_sections (run_id, section_type, title, section_order) VALUES (?, ?, ?, ?)",
            (run_id, stype, title, order),
        )
    conn.commit()
    return len(sections)


def write_sections_from_claims(conn: sqlite3.Connection, run_id: str) -> int:
    ensure_outline(conn, run_id)
    run = conn.execute("SELECT topic FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    topic = run["topic"] if run else "Research run"
    claims = conn.execute(
        "SELECT c.id AS claim_id, c.claim_text, ce.evidence_id "
        "FROM claims c LEFT JOIN claim_evidence ce ON ce.claim_id = c.id "
        "WHERE c.run_id = ? ORDER BY c.created_at, c.id",
        (run_id,),
    ).fetchall()
    claim_lines = [
        f"- {row['claim_text']} [cite:{row['evidence_id'] or 'missing'}]"
        for row in claims[:40]
    ]
    if not claim_lines:
        claim_lines = ["- No supported claims were mined; add sources or run extraction before writing."]
    sections = conn.execute(
        "SELECT id, section_type, title FROM report_sections WHERE run_id = ? ORDER BY section_order",
        (run_id,),
    ).fetchall()
    for sec in sections:
        if sec["section_type"] == "executive_summary":
            body = f"# {sec['title']}\n\nTopic: {topic}\n\nKey supported claims:\n" + "\n".join(claim_lines[:8]) + "\n"
        elif sec["section_type"] == "source_landscape":
            srcs = conn.execute(
                "SELECT title, url, source_type FROM research_sources WHERE run_id = ? ORDER BY fetched_at LIMIT 20",
                (run_id,),
            ).fetchall()
            body = f"# {sec['title']}\n\n" + "\n".join(
                f"- {s['title']} ({s['source_type']}) {s['url'] or ''}".strip() for s in srcs
            ) + "\n"
        elif sec["section_type"] == "evidence_synthesis":
            body = f"# {sec['title']}\n\n" + "\n".join(claim_lines[:20]) + "\n"
        elif sec["section_type"] == "claims_and_implications":
            body = f"# {sec['title']}\n\n" + "\n".join(claim_lines[20:40] or claim_lines[:10]) + "\n"
        else:
            body = f"# {sec['title']}\n\nOpen verification tasks:\n- Re-run search with stricter source filters.\n- Add contradiction-hunt sources.\n- Expand citation-span checks beyond exact evidence IDs.\n"
        conn.execute(
            "UPDATE report_sections SET content = ?, char_count = ? WHERE id = ?",
            (body, len(body), sec["id"]),
        )
    conn.commit()
    return len(sections)


def check_sections_for_run(conn: sqlite3.Connection, run_id: str) -> int:
    sections = conn.execute(
        "SELECT id, content FROM report_sections WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    for sec in sections:
        content = sec["content"] or ""
        has_citation = "[cite:" in content
        score = 1.0 if has_citation else 0.6
        conn.execute(
            "INSERT OR REPLACE INTO section_checks (run_id, section_id, check_type, score, details, passed) "
            "VALUES (?, ?, 'factual_accuracy', ?, ?, ?)",
            (run_id, sec["id"], score, "citation marker present" if has_citation else "no citation marker", 1 if has_citation else 0),
        )
    conn.commit()
    return len(sections)


def compile_report_to_markdown(conn: sqlite3.Connection, run_id: str, output_md: str | None = None) -> tuple[str | None, int, int]:
    sections = conn.execute(
        "SELECT section_type, title, content, char_count FROM report_sections WHERE run_id = ? ORDER BY section_order",
        (run_id,),
    ).fetchall()
    if not sections:
        raise ValueError("No sections to compile.")
    run = conn.execute("SELECT topic FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    lines = [f"# DeepResearch Report: {run['topic'] if run else run_id}", ""]
    for sec in sections:
        content = (sec["content"] or "").strip()
        if content.startswith("#"):
            lines.append(content)
        else:
            lines.append(f"## {sec['title']}\n\n{content}")
        lines.append("")
    lines.extend(["## Bibliography", ""])
    sources = conn.execute(
        "SELECT id, title, url FROM research_sources WHERE run_id = ? ORDER BY fetched_at, id",
        (run_id,),
    ).fetchall()
    for src in sources:
        lines.append(f"- [{src['id']}] {src['title']}{' — ' + src['url'] if src['url'] else ''}")
    markdown = "\n".join(lines).strip() + "\n"
    total_chars = len(markdown)
    conn.execute(
        "UPDATE research_runs SET char_used = ?, total_sources = ?, total_evidence = ?, total_claims = ?, status = 'completed', completed_at = datetime('now') WHERE id = ?",
        (
            total_chars,
            conn.execute("SELECT COUNT(*) FROM research_sources WHERE run_id = ?", (run_id,)).fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM evidence_items WHERE run_id = ?", (run_id,)).fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM claims WHERE run_id = ?", (run_id,)).fetchone()[0],
            run_id,
        ),
    )
    conn.commit()
    if output_md:
        os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(markdown)
    return output_md, len(sections), total_chars


def export_run_to_dir(db_path: str, run_id: str, output_dir: str) -> dict:
    conn = storage.get_connection(db_path)
    os.makedirs(output_dir, exist_ok=True)

    sources = conn.execute(
        "SELECT id, url, title, source_type, content_hash FROM research_sources WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    sources_path = os.path.join(output_dir, "sources.jsonl")
    open(sources_path, "w", encoding="utf-8").close()
    for s in sources:
        storage.append_jsonl(sources_path, dict(s))

    evidence = conn.execute(
        "SELECT id, source_id, content, evidence_type, confidence, span_start, span_end, content_hash "
        "FROM evidence_items WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    evidence_path = os.path.join(output_dir, "evidence.jsonl")
    open(evidence_path, "w", encoding="utf-8").close()
    for e in evidence:
        storage.append_jsonl(evidence_path, {**dict(e), "content": clean_evidence_content(e["content"])})

    claims = conn.execute(
        "SELECT id, claim_text, claim_type, stance, confidence, section_ref, content_hash FROM claims WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    claims_path = os.path.join(output_dir, "claims.jsonl")
    open(claims_path, "w", encoding="utf-8").close()
    for c in claims:
        storage.append_jsonl(claims_path, dict(c))

    links = conn.execute(
        "SELECT id, claim_id, evidence_id, relation, strength FROM claim_evidence WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    links_path = os.path.join(output_dir, "claim_evidence.jsonl")
    open(links_path, "w", encoding="utf-8").close()
    for link in links:
        storage.append_jsonl(links_path, dict(link))

    sections = conn.execute(
        "SELECT id, section_type, title, content, char_count, section_order FROM report_sections WHERE run_id = ? ORDER BY section_order",
        (run_id,),
    ).fetchall()
    sections_path = os.path.join(output_dir, "sections.jsonl")
    open(sections_path, "w", encoding="utf-8").close()
    for sec in sections:
        storage.append_jsonl(sections_path, dict(sec))

    checks = conn.execute(
        "SELECT id, section_id, check_type, score, details, passed FROM section_checks WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    checks_path = os.path.join(output_dir, "section_checks.jsonl")
    open(checks_path, "w", encoding="utf-8").close()
    for check in checks:
        storage.append_jsonl(checks_path, dict(check))

    conn.close()
    return {
        "ok": True,
        "run_id": run_id,
        "output_dir": output_dir,
        "sources": len(sources),
        "evidence": len(evidence),
        "claims": len(claims),
        "claim_evidence": len(links),
        "sections": len(sections),
        "checks": len(checks),
        "files": {
            "sources": sources_path,
            "evidence": evidence_path,
            "claims": claims_path,
            "claim_evidence": links_path,
            "sections": sections_path,
            "section_checks": checks_path,
        },
    }


def perform_online_search(conn: sqlite3.Connection, run_id: str, query: str, max_results: int, fetch: bool, provider: str = "auto") -> dict:
    hits, errors = web_search(query, max_results, provider=provider)
    source_ids: list[str] = []
    fetch_errors: list[str] = []
    for hit in hits:
        url = hit.get("url") or ""
        title = hit.get("title") or url or "Untitled web result"
        snippet = hit.get("snippet") or ""
        text = snippet or title
        if fetch and url:
            fetched, error = browser_use_fetch_url(url)
            if not fetched:
                fetched, http_error = fetch_url_readable(url)
                if http_error:
                    error = f"{error}; http_fallback={http_error}" if error else http_error
            if fetched:
                text = fetched
            if error:
                fetch_errors.append(f"{url}: {error}")
        sid = insert_source(
            conn,
            run_id,
            title=title,
            text=text,
            url=url,
            source_type="web",
            relevance_score=max(0.1, 1.0 - (int(hit.get("rank") or 1) - 1) * 0.08),
        )
        source_ids.append(sid)
    conn.execute(
        "UPDATE research_runs SET config_json = json_set(COALESCE(config_json,'{}'), '$.last_search', ?, '$.last_search_hits', ?) WHERE id = ?",
        (query, len(source_ids), run_id),
    )
    conn.commit()
    used_provider = hits[0].get("connector") if hits else provider
    return {"query": query, "provider": used_provider, "hits": hits, "source_ids": source_ids, "errors": errors, "fetch_errors": fetch_errors}


def render_human_search_handoff(topic: str, query: str, run_id: str | None, max_results: int) -> str:
    """Render a Markdown request that a human can paste into Gemini/GPT."""
    run_line = f"- Run ID: `{run_id}`\n" if run_id else ""
    return f"""# Solar DeepResearch Human Search Handoff

你现在扮演外部搜索研究员。请联网搜索并返回可被 Solar-Harness 导入的 Markdown。

## Research Topic
{topic}

## Search Query
{query}

## Constraints
- Prefer primary sources: official docs, papers, standards, reputable news, code repos.
- Return at most {max_results} high-quality sources.
- Do not invent links.
- Every source must include a URL.
- Include disagreements, uncertainty, or contradictions if found.
- Keep summaries factual and citation-ready.

## Solar Metadata
{run_line}- Import target: `solar-harness research import-search`

## Required Output Format

```markdown
# External Search Results: {topic}

## Source 1: <title>
URL: <https://...>
Publisher: <publisher or N/A>
Published: <date or N/A>
Source Type: <official|paper|news|blog|repo|standard|other>

Summary:
- <2-5 factual bullets>

Key Claims:
- <claim supported by this source>
- <claim supported by this source>

Relevant Quotes:
> <short quote or N/A>

## Source 2: <title>
URL: <https://...>
Publisher: <publisher or N/A>
Published: <date or N/A>
Source Type: <official|paper|news|blog|repo|standard|other>

Summary:
- ...

Key Claims:
- ...

Relevant Quotes:
> ...
```

## After You Return Results
The user will paste/save your Markdown and run:

```bash
solar-harness research import-search <db.sqlite> --run-id <run_id> --input-md <results.md> --continue --output-dir <out>
```
"""


def parse_human_search_markdown(markdown: str) -> list[dict]:
    """Parse Gemini/GPT markdown search results into source records."""
    text = markdown or ""
    blocks = re.split(r"(?im)^##\s+Source\s+\d+\s*:\s*", text)
    records: list[dict] = []
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip(" #\t") or "External search source"
        url_match = re.search(r"(?im)^URL:\s*(<?https?://[^>\s]+>?)", block)
        if not url_match:
            urls = re.findall(r"https?://[^\s>)]+", block)
            url = urls[0] if urls else ""
        else:
            url = url_match.group(1).strip("<>")
        if not url:
            continue
        source_type_match = re.search(r"(?im)^Source Type:\s*(.+)$", block)
        publisher_match = re.search(r"(?im)^Publisher:\s*(.+)$", block)
        published_match = re.search(r"(?im)^Published:\s*(.+)$", block)
        content = "\n".join([
            f"Title: {title}",
            f"URL: {url}",
            f"Publisher: {publisher_match.group(1).strip() if publisher_match else 'N/A'}",
            f"Published: {published_match.group(1).strip() if published_match else 'N/A'}",
            "",
            block.strip(),
        ])
        records.append({
            "title": title,
            "url": url,
            "source_type": (source_type_match.group(1).strip().lower() if source_type_match else "human_search"),
            "content": content,
        })
    if records:
        return records

    urls = re.findall(r"https?://[^\s>)]+", text)
    for i, url in enumerate(dict.fromkeys(urls), 1):
        records.append({
            "title": f"External search source {i}",
            "url": url,
            "source_type": "human_search",
            "content": text,
        })
    return records


def continue_research_pipeline(db_path: str, run_id: str, output_dir: str, output_md: str | None = None) -> dict:
    """Continue a run from existing sources through report export."""
    conn = storage.get_connection(db_path)
    evidence_ids = extract_all_sources(conn, run_id)
    claims_count, links_count = mine_claims_for_run(conn, run_id) if evidence_ids else (0, 0)
    sections_count = write_sections_from_claims(conn, run_id) if claims_count else ensure_outline(conn, run_id)
    checks_count = check_sections_for_run(conn, run_id)
    final_md = output_md or os.path.join(output_dir, "final.md")
    compiled_path, _, chars = compile_report_to_markdown(conn, run_id, final_md)
    conn.close()
    export_payload = export_run_to_dir(db_path, run_id, output_dir)
    return {
        "evidence": len(evidence_ids),
        "claims": claims_count,
        "claim_evidence_links": links_count,
        "sections": sections_count,
        "checks": checks_count,
        "final_md": compiled_path,
        "characters": chars,
        "export": export_payload,
    }


# ---------------------------------------------------------------------------
# S03 subcommands (init, add-source, extract, ledger, status)
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new research database."""
    db_path = args.db_path
    if os.path.exists(db_path):
        print(f"Error: {db_path} already exists", file=sys.stderr)
        return 1
    conn = storage.init_db(db_path)
    conn.execute(
        "INSERT INTO research_runs (topic, depth_tier, status) VALUES (?, ?, ?)",
        (args.topic, args.depth_tier, "pending"),
    )
    conn.commit()
    run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()["id"]
    conn.close()
    if emit_json(args, {"ok": True, "db_path": db_path, "run_id": run_id, "topic": args.topic, "depth_tier": args.depth_tier}):
        return 0
    print(f"Initialized research DB: {db_path}")
    print(f"Run ID: {run_id}")
    print(f"Topic: {args.topic}")
    print(f"Depth: {args.depth_tier}")
    return 0


def cmd_add_source(args: argparse.Namespace) -> int:
    """Add a source to the research run."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist. Run 'research init' first.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id
    source_id = insert_source(
        conn,
        run_id,
        title=args.title or "Untitled",
        text=args.text,
        url=getattr(args, "url", None),
        source_type=getattr(args, "source_type", "document"),
        relevance_score=0.7,
    )
    content_hash = hashing.content_hash(f"{getattr(args, 'url', None) or ''}\n{args.text.strip() or args.title or 'Untitled'}")
    conn.close()
    if emit_json(args, {"ok": True, "source_id": source_id, "run_id": run_id, "title": args.title or "Untitled", "content_length": len(args.text), "content_hash": content_hash}):
        return 0
    print(f"Source added: {source_id}")
    print(f"Title: {args.title or 'Untitled'}")
    print(f"Content length: {len(args.text)} chars")
    print(f"Content hash: {content_hash[:16]}...")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract evidence from a source (text-based extraction)."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id
    source_id = args.source_id

    try:
        eid = extract_source_to_evidence(conn, run_id, source_id)
        item = conn.execute("SELECT span_start, span_end, content_hash FROM evidence_items WHERE id = ?", (eid,)).fetchone()
    except ValueError:
        print(f"Error: source {source_id} not found in run {run_id}", file=sys.stderr)
        conn.close()
        return 1
    conn.close()
    if emit_json(args, {"ok": True, "evidence_id": eid, "run_id": run_id, "source_id": source_id, "span_start": item["span_start"], "span_end": item["span_end"], "content_hash": item["content_hash"]}):
        return 0
    print(f"Evidence extracted: {eid}")
    print(f"Source: {source_id}")
    print(f"Span: [{item['span_start']}, {item['span_end']})")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    """Show evidence ledger summary."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    run = conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        print(f"Error: run {run_id} not found", file=sys.stderr)
        conn.close()
        return 1

    source_count = conn.execute(
        "SELECT COUNT(*) FROM research_sources WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    evidence_count = conn.execute(
        "SELECT COUNT(*) FROM evidence_items WHERE run_id = ?", (run_id,)
    ).fetchone()[0]

    if getattr(args, "json", False):
        evidence = [
            {**dict(row), "content": clean_evidence_content(row["content"])}
            for row in conn.execute(
                "SELECT id, source_id, content, evidence_type, confidence, span_start, span_end, content_hash "
                "FROM evidence_items WHERE run_id = ? ORDER BY span_start",
                (run_id,),
            ).fetchall()
        ]
        conn.close()
        print(json.dumps({
            "ok": True,
            "run_id": run_id,
            "topic": run["topic"],
            "status": run["status"],
            "sources": source_count,
            "evidence_items": evidence_count,
            "evidence": evidence,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"Run: {run_id}")
    print(f"Topic: {run['topic']}")
    print(f"Status: {run['status']}")
    print(f"Sources: {source_count}")
    print(f"Evidence items: {evidence_count}")

    if evidence_count > 0:
        print("\nEvidence items:")
        for row in conn.execute(
            "SELECT id, source_id, span_start, span_end FROM evidence_items "
            "WHERE run_id = ? ORDER BY span_start", (run_id,)
        ).fetchall():
            print(f"  {row['id']} source={row['source_id']} [{row['span_start']}:{row['span_end']}]")

    conn.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show research run status."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)

    table_counts = {}
    for table in storage.SEVEN_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        table_counts[table] = count
    if emit_json(args, {"ok": True, "db_path": db_path, "tables": table_counts}):
        conn.close()
        return 0

    print(f"Research DB: {db_path}")
    print(f"Tables: {', '.join(storage.SEVEN_TABLES)}")
    for table, count in table_counts.items():
        if count > 0:
            print(f"  {table}: {count} rows")

    conn.close()
    return 0


# ---------------------------------------------------------------------------
# S04 subcommands (run, plan, search, mine, outline, write, check, compile, export)
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a full research run (init + source + extract + claim + report)."""
    db_path = args.db_path
    topic = args.topic
    depth = args.depth_tier
    output_dir = args.output_dir or os.path.join(os.path.dirname(os.path.abspath(db_path)) or ".", "research-output")
    output_md = args.output_md or os.path.join(output_dir, "final.md")

    conn = storage.init_db(db_path)
    conn.execute(
        "INSERT INTO research_runs (topic, depth_tier, status) VALUES (?, ?, 'running')",
        (topic, depth),
    )
    conn.commit()
    run_id = conn.execute("SELECT id FROM research_runs ORDER BY created_at DESC LIMIT 1").fetchone()["id"]

    source_ids: list[str] = []
    search_result: dict | None = None
    if args.text:
        source_ids.append(insert_source(conn, run_id, "User supplied text", args.text, source_type="document"))
    if args.source_file:
        with open(args.source_file, "r", encoding="utf-8") as f:
            source_ids.append(insert_source(conn, run_id, os.path.basename(args.source_file), f.read(), url=args.source_file, source_type="file"))
    if args.web_query:
        search_result = perform_online_search(conn, run_id, args.web_query, args.max_results, fetch=True, provider=args.search_provider)
        source_ids.extend(search_result["source_ids"])

    evidence_ids = extract_all_sources(conn, run_id) if source_ids else []
    claims_count, links_count = mine_claims_for_run(conn, run_id) if evidence_ids else (0, 0)
    sections_count = write_sections_from_claims(conn, run_id) if claims_count else ensure_outline(conn, run_id)
    checks_count = check_sections_for_run(conn, run_id)
    compiled_path, _, chars = compile_report_to_markdown(conn, run_id, output_md)
    conn.close()

    export_payload = export_run_to_dir(db_path, run_id, output_dir)

    payload = {
        "ok": True,
        "db_path": db_path,
        "run_id": run_id,
        "topic": topic,
        "depth_tier": depth,
        "status": "completed",
        "sources": len(source_ids),
        "evidence": len(evidence_ids),
        "claims": claims_count,
        "claim_evidence_links": links_count,
        "sections": sections_count,
        "checks": checks_count,
        "final_md": compiled_path,
        "characters": chars,
        "export": export_payload,
        "web": search_result,
    }
    if emit_json(args, payload):
        return 0
    print(f"Research run started: {run_id}")
    print(f"Research run completed: {run_id}")
    print(f"Topic: {topic}")
    print(f"Depth: {depth}")
    print(f"Sources: {len(source_ids)}")
    print(f"Evidence: {len(evidence_ids)}")
    print(f"Claims: {claims_count}")
    print(f"Final report: {compiled_path}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate a research plan (section outline + source strategy)."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    run = conn.execute("SELECT topic, depth_tier FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        print(f"Error: run {run_id} not found", file=sys.stderr)
        conn.close()
        return 1

    plan_json = json.dumps({
        "run_id": run_id,
        "topic": run["topic"],
        "depth_tier": run["depth_tier"],
        "sections": ["executive_summary", "background", "analysis", "findings", "conclusion"],
    })
    conn.execute(
        "UPDATE research_runs SET config_json = ? WHERE id = ?",
        (plan_json, run_id),
    )
    conn.commit()
    conn.close()

    if emit_json(args, {"ok": True, "run_id": run_id, "topic": run["topic"], "depth_tier": run["depth_tier"], "plan": json.loads(plan_json)}):
        return 0
    print(f"Research plan generated for run: {run_id}")
    print(f"Plan: {plan_json}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search for sources matching a query."""
    db_path = args.db_path
    query = args.query
    max_results = args.max_results

    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    if not getattr(args, "json", False):
        print(f"Searching for: {query}")
        print(f"Max results: {max_results}")
        print(f"Run: {run_id}")

    result = perform_online_search(conn, run_id, query, max_results, fetch=args.fetch, provider=args.provider)
    conn.close()
    ok = bool(result["source_ids"])
    if getattr(args, "require_online", False) and not ok:
        print(f"Error: online search produced no sources: {result['errors']}", file=sys.stderr)
        return 2
    if emit_json(args, {"ok": ok, "run_id": run_id, "query": query, "max_results": max_results, **result}):
        return 0
    print(f"Online hits: {len(result['hits'])}")
    print(f"Sources written: {len(result['source_ids'])}")
    if result["errors"]:
        print(f"Provider errors: {len(result['errors'])}")
    return 0


def cmd_handoff_search(args: argparse.Namespace) -> int:
    """Generate a human-in-the-loop search request Markdown."""
    db_path = args.db_path
    run_id = args.run_id
    topic = args.topic or args.query
    if db_path and os.path.exists(db_path) and run_id:
        conn = storage.get_connection(db_path)
        row = conn.execute("SELECT topic FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        if row:
            topic = args.topic or row["topic"]
    content = render_human_search_handoff(topic=topic, query=args.query, run_id=run_id, max_results=args.max_results)
    output_md = args.output_md or os.path.join(
        tempfile.gettempdir(),
        f"solar-human-search-{int(time.time())}.md",
    )
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(content)
    payload = {
        "ok": True,
        "output_md": output_md,
        "db_path": db_path,
        "run_id": run_id,
        "topic": topic,
        "query": args.query,
        "max_results": args.max_results,
    }
    if getattr(args, "print", False):
        print(content)
    elif emit_json(args, payload):
        return 0
    else:
        print(f"Human search handoff written: {output_md}")
    return 0


def cmd_import_search(args: argparse.Namespace) -> int:
    """Import a human/Gemini/GPT search Markdown result as DeepResearch sources."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    run_id = args.run_id
    if args.input_md == "-":
        markdown = sys.stdin.read()
    else:
        with open(args.input_md, "r", encoding="utf-8") as f:
            markdown = f.read()
    records = parse_human_search_markdown(markdown)
    if not records:
        print("Error: no importable sources found in Markdown.", file=sys.stderr)
        return 2
    conn = storage.get_connection(db_path)
    source_ids = []
    for rec in records:
        source_ids.append(insert_source(
            conn,
            run_id,
            title=rec["title"],
            text=rec["content"],
            url=rec["url"],
            source_type=rec["source_type"] or "human_search",
            relevance_score=0.75,
        ))
    conn.close()
    payload = {
        "ok": True,
        "run_id": run_id,
        "sources_imported": len(source_ids),
        "source_ids": source_ids,
    }
    if args.continue_pipeline:
        output_dir = args.output_dir or os.path.join(os.path.dirname(os.path.abspath(db_path)) or ".", "research-output")
        payload["pipeline"] = continue_research_pipeline(db_path, run_id, output_dir, args.output_md or None)
    if args.graph and args.node:
        try:
            from graph_scheduler import load_graph, mark_node_result, save_graph  # noqa: WPS433

            graph = load_graph(args.graph)
            for n in graph.get("nodes", []):
                if n.get("id") == args.node:
                    hs = n.get("human_search") if isinstance(n.get("human_search"), dict) else {}
                    hs.update({"status": "imported", "sources_imported": len(source_ids)})
                    n["human_search"] = hs
                    break
            parent = mark_node_result(graph, args.node, "passed", gate_status="passed", note="human_search_imported")
            save_graph(args.graph, graph)
            payload["graph_update"] = {"ok": True, "graph": args.graph, "node": args.node, "status": "passed", "parent": parent}
        except Exception as exc:
            payload["graph_update"] = {"ok": False, "error": str(exc), "graph": args.graph, "node": args.node}
    if emit_json(args, payload):
        return 0
    print(f"Imported human search sources: {len(source_ids)}")
    if args.continue_pipeline:
        print(f"Final report: {payload['pipeline']['final_md']}")
    return 0


def cmd_mine(args: argparse.Namespace) -> int:
    """Mine claims from evidence items."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    evidence_count = conn.execute("SELECT COUNT(*) FROM evidence_items WHERE run_id = ?", (run_id,)).fetchone()[0]

    if evidence_count == 0:
        print("No evidence items to mine claims from.", file=sys.stderr)
        conn.close()
        return 1

    claims_count, links_count = mine_claims_for_run(conn, run_id)
    conn.close()
    if emit_json(args, {"ok": True, "run_id": run_id, "evidence_items": evidence_count, "claims": claims_count, "claim_evidence_links": links_count}):
        return 0
    print(f"Claim mining from {evidence_count} evidence items for run: {run_id}")
    print(f"Claims: {claims_count}")
    print(f"Claim-evidence links: {links_count}")
    return 0


def cmd_outline(args: argparse.Namespace) -> int:
    """Generate report outline (sections structure)."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    ensure_outline(conn, run_id)
    sections = conn.execute(
        "SELECT section_type, title FROM report_sections WHERE run_id = ? ORDER BY section_order",
        (run_id,),
    ).fetchall()
    conn.close()

    if emit_json(args, {"ok": True, "run_id": run_id, "sections": [dict(row) for row in sections]}):
        return 0
    print(f"Report outline created with {len(sections)} sections for run: {run_id}")
    for row in sections:
        print(f"  {row['section_type']}: {row['title']}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    """Write content to a report section."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    section_id = args.section_id
    content = args.content

    row = conn.execute("SELECT id, run_id FROM report_sections WHERE id = ?", (section_id,)).fetchone()
    if row is None:
        print(f"Error: section {section_id} not found", file=sys.stderr)
        conn.close()
        return 1

    conn.execute(
        "UPDATE report_sections SET content = ?, char_count = ? WHERE id = ?",
        (content, len(content), section_id),
    )
    conn.commit()
    conn.close()

    if emit_json(args, {"ok": True, "section_id": section_id, "characters": len(content)}):
        return 0
    print(f"Section written: {section_id}")
    print(f"Characters: {len(content)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Run factuality check on report sections."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    sections = conn.execute("SELECT id, section_type FROM report_sections WHERE run_id = ?", (run_id,)).fetchall()

    if not sections:
        print("No report sections to check.", file=sys.stderr)
        conn.close()
        return 1

    checked = check_sections_for_run(conn, run_id)
    conn.close()

    if emit_json(args, {"ok": True, "run_id": run_id, "sections_checked": checked}):
        return 0
    print(f"Factuality check completed for {checked} sections in run: {run_id}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    """Compile report sections into final report."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    try:
        output_md, sections_count, total_chars = compile_report_to_markdown(conn, run_id, args.output_md)
    except ValueError:
        print("No sections to compile.", file=sys.stderr)
        conn.close()
        return 1
    conn.close()

    if emit_json(args, {"ok": True, "run_id": run_id, "sections": sections_count, "characters": total_chars, "output_md": output_md}):
        return 0
    print(f"Report compiled: {sections_count} sections, {total_chars} chars")
    if output_md:
        print(f"Final report: {output_md}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export research run to JSONL artifacts."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    run_id = args.run_id
    output_dir = args.output_dir

    payload = export_run_to_dir(db_path, run_id, output_dir)

    if emit_json(args, payload):
        return 0
    print(f"Exported to: {output_dir}")
    print(f"Sources: {payload['sources']} records -> sources.jsonl")
    print(f"Evidence: {payload['evidence']} records -> evidence.jsonl")
    print(f"Claims: {payload['claims']} records -> claims.jsonl")
    print(f"Sections: {payload['sections']} records -> sections.jsonl")
    return 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_SUBCOMMANDS = [
    "init", "add-source", "extract", "ledger", "status",
    "run", "plan", "search", "handoff-search", "import-search",
    "mine", "outline", "write", "check", "compile", "export",
]

SUBCOMMANDS = {
    "init": cmd_init,
    "add-source": cmd_add_source,
    "extract": cmd_extract,
    "ledger": cmd_ledger,
    "status": cmd_status,
    "run": cmd_run,
    "plan": cmd_plan,
    "search": cmd_search,
    "handoff-search": cmd_handoff_search,
    "import-search": cmd_import_search,
    "mine": cmd_mine,
    "outline": cmd_outline,
    "write": cmd_write,
    "check": cmd_check,
    "compile": cmd_compile,
    "export": cmd_export,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solar-harness research",
        description="DeepResearch subcommands",
    )
    sub = parser.add_subparsers(dest="subcommand")

    # S03 subcommands
    p_init = sub.add_parser("init", help="Initialize a new research DB")
    p_init.add_argument("db_path", help="Path to the SQLite database")
    p_init.add_argument("--topic", default="Research run", help="Research topic")
    p_init.add_argument("--depth-tier", default="standard",
                        choices=["quick", "standard", "deep"])
    p_init.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_src = sub.add_parser("add-source", help="Add a source document")
    p_src.add_argument("db_path", help="Path to the SQLite database")
    p_src.add_argument("--run-id", required=True, help="Research run ID")
    p_src.add_argument("--title", default="", help="Source title")
    p_src.add_argument("--text", required=True, help="Source text content")
    p_src.add_argument("--url", default="", help="Optional source URL or file path")
    p_src.add_argument("--source-type", default="document", help="Source type label")
    p_src.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_ext = sub.add_parser("extract", help="Extract evidence from a source")
    p_ext.add_argument("db_path", help="Path to the SQLite database")
    p_ext.add_argument("--run-id", required=True, help="Research run ID")
    p_ext.add_argument("--source-id", required=True, help="Source document ID")
    p_ext.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_led = sub.add_parser("ledger", help="Show evidence ledger")
    p_led.add_argument("db_path", help="Path to the SQLite database")
    p_led.add_argument("--run-id", required=True, help="Research run ID")
    p_led.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_stat = sub.add_parser("status", help="Show research DB status")
    p_stat.add_argument("db_path", help="Path to the SQLite database")
    p_stat.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # S04 subcommands
    p_run = sub.add_parser("run", help="Execute a full research run")
    p_run.add_argument("db_path", help="Path to the SQLite database")
    p_run.add_argument("--topic", required=True, help="Research topic")
    p_run.add_argument("--depth-tier", default="standard",
                        choices=["quick", "standard", "deep"])
    p_run.add_argument("--text", default="", help="Inline source text to ingest before extraction")
    p_run.add_argument("--source-file", default="", help="Local UTF-8 source file to ingest")
    p_run.add_argument("--web-query", default="", help="Online query to search and fetch into sources")
    p_run.add_argument("--max-results", type=int, default=5, help="Max web results for --web-query")
    p_run.add_argument("--search-provider", default="auto", choices=["auto", "browser-use", "http"],
                       help="Search provider: auto prefers browser-use and falls back to HTTP")
    p_run.add_argument("--output-dir", default="", help="Directory for JSONL artifacts")
    p_run.add_argument("--output-md", default="", help="Path for compiled final markdown")
    p_run.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_plan = sub.add_parser("plan", help="Generate research plan")
    p_plan.add_argument("db_path", help="Path to the SQLite database")
    p_plan.add_argument("--run-id", required=True, help="Research run ID")
    p_plan.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_search = sub.add_parser("search", help="Search for sources")
    p_search.add_argument("db_path", help="Path to the SQLite database")
    p_search.add_argument("--run-id", required=True, help="Research run ID")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--max-results", type=int, default=10, help="Max results")
    p_search.add_argument("--provider", default="auto", choices=["auto", "browser-use", "http"],
                          help="Search provider: auto prefers browser-use and falls back to HTTP")
    p_search.add_argument("--fetch", action="store_true", help="Fetch and store readable page text for each hit")
    p_search.add_argument("--require-online", action="store_true", help="Return non-zero if no online source is written")
    p_search.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_handoff = sub.add_parser("handoff-search", help="Generate human-in-the-loop search Markdown")
    p_handoff.add_argument("db_path", nargs="?", default="", help="Path to the SQLite database")
    p_handoff.add_argument("--run-id", default="", help="Research run ID")
    p_handoff.add_argument("--topic", default="", help="Research topic override")
    p_handoff.add_argument("--query", required=True, help="Search query for Gemini/GPT")
    p_handoff.add_argument("--max-results", type=int, default=8, help="Requested external sources")
    p_handoff.add_argument("--output-md", default="", help="Where to write handoff Markdown")
    p_handoff.add_argument("--print", action="store_true", help="Print the Markdown to stdout")
    p_handoff.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_import = sub.add_parser("import-search", help="Import human/Gemini/GPT search Markdown")
    p_import.add_argument("db_path", help="Path to the SQLite database")
    p_import.add_argument("--run-id", required=True, help="Research run ID")
    p_import.add_argument("--input-md", required=True, help="Markdown file path, or '-' for stdin")
    p_import.add_argument("--continue", dest="continue_pipeline", action="store_true",
                          help="Continue through evidence, claims, sections, checks, compile, export")
    p_import.add_argument("--output-dir", default="", help="Directory for JSONL artifacts when --continue is used")
    p_import.add_argument("--output-md", default="", help="Path for final markdown when --continue is used")
    p_import.add_argument("--graph", default="", help="Optional task_graph.json to mark after import")
    p_import.add_argument("--node", default="", help="Optional graph node id to mark passed after import")
    p_import.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_mine = sub.add_parser("mine", help="Mine claims from evidence")
    p_mine.add_argument("db_path", help="Path to the SQLite database")
    p_mine.add_argument("--run-id", required=True, help="Research run ID")
    p_mine.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_outline = sub.add_parser("outline", help="Generate report outline")
    p_outline.add_argument("db_path", help="Path to the SQLite database")
    p_outline.add_argument("--run-id", required=True, help="Research run ID")
    p_outline.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_write = sub.add_parser("write", help="Write content to a section")
    p_write.add_argument("db_path", help="Path to the SQLite database")
    p_write.add_argument("--section-id", required=True, help="Section ID")
    p_write.add_argument("--content", required=True, help="Section content text")
    p_write.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_check = sub.add_parser("check", help="Run factuality checks")
    p_check.add_argument("db_path", help="Path to the SQLite database")
    p_check.add_argument("--run-id", required=True, help="Research run ID")
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_compile = sub.add_parser("compile", help="Compile report sections")
    p_compile.add_argument("db_path", help="Path to the SQLite database")
    p_compile.add_argument("--run-id", required=True, help="Research run ID")
    p_compile.add_argument("--output-md", default="", help="Path for compiled final markdown")
    p_compile.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    p_export = sub.add_parser("export", help="Export run to JSONL artifacts")
    p_export.add_argument("db_path", help="Path to the SQLite database")
    p_export.add_argument("--run-id", required=True, help="Research run ID")
    p_export.add_argument("--output-dir", required=True, help="Output directory")
    p_export.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if not args.subcommand:
        parser.print_help()
        return 0
    handler = SUBCOMMANDS.get(args.subcommand)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
