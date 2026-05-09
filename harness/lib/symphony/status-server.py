#!/usr/bin/env python3
"""
Solar Harness HTTP Status Server — port 8765
Sprint: sprint-20260507-symphony3 S4-S5

Endpoints:
  GET /status         → JSON {current_sprint, panes, recent_events, kpi}
  GET /               → HTML dashboard (5s auto-refresh, no external deps)
  GET /events         → JSON array, query params: sprint_id, limit
  GET /mermaid        → HTML Mermaid .mmd browser and renderer
  GET /mermaid/view   → HTML render for one .mmd file, query param: file
  GET /mermaid/raw    → raw .mmd source, query param: file
  GET /integrations        → JSON external open-source integration health
  GET /integrations-view   → HTML human-readable integrations health page
  GET /healthz        → "ok"

Startup: solar-harness status-server start  (writes pidfile, nohup)
         solar-harness status-server stop|restart|status

Binds to 127.0.0.1:8765 only. No auth, no TLS (internal use).
Port fallback: 8765-8775 if primary is occupied.
"""

import json
import os
import sqlite3
import subprocess
import sys
import re
import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── Paths ──
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", str(Path.home() / ".solar" / "harness")))
SPRINTS_DIR = HARNESS_DIR / "sprints"
EVENTS_DIR = HARNESS_DIR / "events"
ALL_EVENTS = EVENTS_DIR / "all.jsonl"
COORD_STATE = HARNESS_DIR / ".coordinator-state"
PANE_ASSIGNMENTS = HARNESS_DIR / ".pane-assignments"
PANE_ASSIGNMENTS_JSON = HARNESS_DIR / ".pane-assignments.json"
MERMAID_DIST = HARNESS_DIR / "vendor" / "mermaid-viewer" / "node_modules" / "mermaid" / "dist"
INTEGRATIONS_HEALTH = HARNESS_DIR / "lib" / "external-integrations-health.py"
MMD_ALLOWED_ROOTS = [
    HARNESS_DIR,
    Path.home() / "Knowledge",
]

BIND_HOST = "127.0.0.1"
PORT_RANGE = range(8765, 8776)


_SYNTHETIC_SID_PREFIXES = ("test-hooks-", "test-sid-", "sprint-race-test-", "sprint-test-smoke-", "sprint-test-workspace-", "test-verify-")


def _is_synthetic_event(obj: dict) -> bool:
    sid = obj.get("sprint_id", "")
    return any(sid.startswith(p) for p in _SYNTHETIC_SID_PREFIXES)


def _read_jsonl(path: Path, limit: int = 50, sprint_id: str = "", filter_synthetic: bool = False) -> list:
    """Read last `limit` lines from a JSONL file, optionally filtered by sprint_id."""
    if not path.exists():
        return []
    lines = []
    try:
        with open(path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if sprint_id and obj.get("sprint_id") != sprint_id:
                    continue
                if filter_synthetic and _is_synthetic_event(obj):
                    continue
                lines.append(obj)
    except OSError:
        return []
    return lines[-limit:]


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except (OSError, ValueError):
        return str(path)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _allowed_mmd_path(path: Path) -> bool:
    if path.suffix.lower() != ".mmd":
        return False
    return any(_is_within(path, root) for root in MMD_ALLOWED_ROOTS)


def _resolve_mmd_file(raw: str):
    """Resolve a .mmd file name/path inside allowed local roots."""
    raw = urllib.parse.unquote(raw or "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        # Prefer direct harness-relative paths, then fall back to basename search.
        direct = HARNESS_DIR / candidate
        if direct.exists():
            candidate = direct
        else:
            matches = [item["path"] for item in _list_mmd_files(limit=500) if item["name"] == raw or item["rel"] == raw]
            if matches:
                candidate = Path(matches[0])
    try:
        candidate = candidate.resolve()
    except OSError:
        return None
    if candidate.exists() and candidate.is_file() and _allowed_mmd_path(candidate):
        return candidate
    return None


def _list_mmd_files(limit: int = 200) -> list[dict]:
    files = []
    skip_parts = {"node_modules", ".git", "venvs", "vendor"}
    for root in MMD_ALLOWED_ROOTS:
        if not root.exists():
            continue
        try:
            iterator = root.rglob("*.mmd")
            for path in iterator:
                if any(part in skip_parts for part in path.parts):
                    continue
                try:
                    st = path.stat()
                    resolved = path.resolve()
                except OSError:
                    continue
                files.append(
                    {
                        "name": path.name,
                        "path": str(resolved),
                        "rel": _safe_rel(resolved, root),
                        "root": str(root),
                        "mtime": st.st_mtime,
                        "size": st.st_size,
                    }
                )
        except OSError:
            continue
    files.sort(key=lambda item: item["mtime"], reverse=True)
    return files[:limit]


def _asset_path(raw: str):
    rel = urllib.parse.unquote(raw or "").lstrip("/")
    if not rel:
        return None
    path = (MERMAID_DIST / rel).resolve()
    if not _is_within(path, MERMAID_DIST):
        return None
    if path.exists() and path.is_file():
        return path
    return None


def _mermaid_index_html() -> str:
    files = _list_mmd_files()
    cards = []
    for item in files:
        path = item["path"]
        name = html.escape(item["name"])
        rel = html.escape(item["rel"])
        root = html.escape(item["root"])
        url = "/mermaid/view?file=" + urllib.parse.quote(path)
        raw_url = "/mermaid/raw?file=" + urllib.parse.quote(path)
        cards.append(
            f"""<article class="mmd-card">
  <div>
    <h2>{name}</h2>
    <p>{rel}</p>
    <p class="muted">{root}</p>
  </div>
  <div class="actions">
    <a class="btn primary" href="{url}">打开图</a>
    <a class="btn" href="{raw_url}">看源码</a>
  </div>
</article>"""
        )
    if not cards:
        cards.append('<div class="empty">没有找到 .mmd 文件。</div>')
    default_file = "/Users/sihaoli/.solar/harness/reports/solar-system-architecture-20260508.mmd"
    default_link = "/mermaid/view?file=" + urllib.parse.quote(default_file)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Mermaid Viewer</title>
<style>
:root {{ --bg:#f7f0df; --ink:#211b12; --muted:#746858; --panel:#fffaf0; --line:rgba(33,27,18,.14); --accent:#1f6f5b; }}
body {{ margin:0; background:radial-gradient(circle at top left,#fff8df,#efe4cf 42%,#d9e7df); color:var(--ink); font-family:"Avenir Next","Gill Sans",ui-sans-serif,sans-serif; }}
header,main {{ max-width:1180px; margin:0 auto; padding:24px; }}
.hero {{ border:1px solid var(--line); border-radius:30px; padding:28px; background:linear-gradient(135deg,rgba(255,250,240,.90),rgba(226,239,230,.70)); box-shadow:0 24px 70px rgba(33,27,18,.10); }}
.eyebrow {{ text-transform:uppercase; letter-spacing:.14em; color:var(--accent); font-weight:900; font-size:.78rem; }}
h1 {{ font-size:clamp(2.3rem,6vw,5.5rem); line-height:.9; margin:.2rem 0 .8rem; }}
.muted {{ color:var(--muted); }}
.toolbar,.actions {{ display:flex; flex-wrap:wrap; gap:.7rem; align-items:center; }}
.btn {{ border:1px solid var(--line); border-radius:14px; padding:.7rem .95rem; background:rgba(255,255,255,.54); color:var(--ink); text-decoration:none; font-weight:900; }}
.btn.primary {{ background:var(--ink); color:#fff8e8; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:1rem; margin-top:1rem; }}
.mmd-card {{ min-height:150px; display:flex; flex-direction:column; justify-content:space-between; gap:1rem; border:1px solid var(--line); border-radius:24px; padding:1rem; background:rgba(255,250,240,.78); box-shadow:0 14px 36px rgba(33,27,18,.07); overflow:hidden; }}
.mmd-card h2 {{ margin:.2rem 0; overflow-wrap:anywhere; }}
.mmd-card p {{ margin:.2rem 0; overflow-wrap:anywhere; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.84rem; }}
.empty {{ padding:2rem; border:1px dashed var(--line); border-radius:22px; background:rgba(255,250,240,.58); }}
</style>
</head>
<body>
<header>
  <div class="hero">
    <div class="eyebrow">Solar Harness Diagram Desk</div>
    <h1>Mermaid Viewer</h1>
    <p class="muted">直接浏览和渲染 Solar 里的 .mmd 架构图。默认只暴露 harness 和 Knowledge 目录下的 .mmd 文件。</p>
    <div class="toolbar">
      <a class="btn primary" href="{default_link}">打开 Solar 完整架构图</a>
      <a class="btn" href="/">回到 Solar Status</a>
      <a class="btn" href="/mermaid/list">查看 JSON 列表</a>
    </div>
  </div>
</header>
<main>
  <div class="grid">
    {''.join(cards)}
  </div>
</main>
</body>
</html>"""


def _mermaid_view_html(path: Path) -> str:
    name = html.escape(path.name)
    raw_path = html.escape(str(path))
    raw_url = "/mermaid/raw?file=" + urllib.parse.quote(str(path))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · Solar Mermaid</title>
<style>
:root {{ --bg:#f6efe0; --ink:#1f1a12; --muted:#746858; --panel:#fffaf0; --line:rgba(31,26,18,.14); --accent:#1f6f5b; --danger:#9f3a2f; }}
body {{ margin:0; background:linear-gradient(135deg,#f8f0df,#dfece3); color:var(--ink); font-family:"Avenir Next","Gill Sans",ui-sans-serif,sans-serif; }}
header {{ max-width:1280px; margin:0 auto; padding:22px 24px 0; }}
main {{ max-width:calc(100vw - 24px); margin:0 auto; padding:12px 12px 24px; }}
.bar {{ border:1px solid var(--line); border-radius:24px; background:rgba(255,250,240,.86); padding:1rem; display:flex; gap:1rem; justify-content:space-between; flex-wrap:wrap; align-items:center; box-shadow:0 18px 50px rgba(31,26,18,.09); }}
h1 {{ margin:.15rem 0; font-size:clamp(1.6rem,4vw,3.6rem); }}
.path {{ color:var(--muted); font-family:ui-monospace,SFMono-Regular,Menlo,monospace; overflow-wrap:anywhere; }}
.actions {{ display:flex; flex-wrap:wrap; gap:.65rem; }}
.btn {{ border:1px solid var(--line); border-radius:14px; padding:.7rem .95rem; background:rgba(255,255,255,.58); color:var(--ink); text-decoration:none; font-weight:900; cursor:pointer; }}
.btn.primary {{ background:var(--ink); color:#fff8e8; }}
.stage {{ border:1px solid var(--line); border-radius:24px; background:rgba(255,250,240,.72); min-height:78vh; padding:1rem; overflow:auto; box-shadow:inset 0 0 0 1px rgba(255,255,255,.25); }}
#diagram {{ transform-origin: top left; width:max-content; min-width:100%; }}
#diagram svg {{ max-width:none; height:auto; min-width:1200px; }}
#zoom-label {{ min-width:4.5rem; text-align:center; font-weight:900; color:var(--accent); }}
.error {{ color:var(--danger); white-space:pre-wrap; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
.source {{ display:none; margin-top:1rem; background:#211b12; color:#f8efe0; border-radius:18px; padding:1rem; white-space:pre; overflow:auto; }}
</style>
</head>
<body>
<header>
  <div class="bar">
    <div>
      <div class="path">Solar Mermaid</div>
      <h1>{name}</h1>
      <div class="path">{raw_path}</div>
    </div>
    <div class="actions">
      <a class="btn" href="/mermaid">图列表</a>
      <a class="btn" href="{raw_url}">源码</a>
      <button class="btn" id="toggle-source">显示源码</button>
      <button class="btn" id="zoom-out">缩小</button>
      <span id="zoom-label">140%</span>
      <button class="btn" id="zoom-in">放大</button>
      <button class="btn primary" id="fit">适配宽度</button>
    </div>
  </div>
</header>
<main>
  <div class="stage">
    <div id="diagram">Loading...</div>
    <pre id="source" class="source"></pre>
  </div>
</main>
<script type="module">
import mermaid from '/mermaid/assets/mermaid.esm.min.mjs';
const file = {json.dumps(str(path))};
const rawUrl = '/mermaid/raw?file=' + encodeURIComponent(file);
const diagram = document.getElementById('diagram');
const source = document.getElementById('source');
const zoomLabel = document.getElementById('zoom-label');
let zoom = 1.4;
function applyZoom() {{
  diagram.style.transform = 'scale(' + zoom + ')';
  diagram.style.marginRight = ((zoom - 1) * 100) + '%';
  diagram.style.marginBottom = ((zoom - 1) * 70) + 'vh';
  zoomLabel.textContent = Math.round(zoom * 100) + '%';
}}
mermaid.initialize({{
  startOnLoad: false,
  securityLevel: 'strict',
  theme: 'base',
  themeVariables: {{
    fontSize: '24px',
    fontFamily: 'Avenir Next, Gill Sans, sans-serif',
    primaryTextColor: '#211b12',
    lineColor: '#4d4334'
  }},
  flowchart: {{ htmlLabels: true, curve: 'basis' }},
  sequence: {{ mirrorActors: false }}
}});
try {{
  const text = await fetch(rawUrl).then(r => {{
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.text();
  }});
  source.textContent = text;
  const result = await mermaid.render('solar-mermaid-svg', text);
  diagram.innerHTML = result.svg;
  if (result.bindFunctions) result.bindFunctions(diagram);
  applyZoom();
}} catch (err) {{
  diagram.innerHTML = '<div class="error">Mermaid 渲染失败：\\n' + String(err && err.stack || err) + '</div>';
}}
document.getElementById('toggle-source').addEventListener('click', () => {{
  source.style.display = source.style.display === 'block' ? 'none' : 'block';
}});
document.getElementById('fit').addEventListener('click', () => {{
  const svg = diagram.querySelector('svg');
  if (svg) {{
    zoom = 1;
    svg.style.maxWidth = '100%';
    svg.style.width = '100%';
    applyZoom();
  }}
}});
document.getElementById('zoom-in').addEventListener('click', () => {{
  zoom = Math.min(2.5, zoom + 0.2);
  applyZoom();
}});
document.getElementById('zoom-out').addEventListener('click', () => {{
  zoom = Math.max(0.8, zoom - 0.2);
  applyZoom();
}});
</script>
</body>
</html>"""


def _integrations_view_html() -> str:
    """Standalone human-readable HTML page for external integrations health (server-side rendered)."""
    data = _external_integrations_payload(refresh=False)
    items = data.get("integrations", []) if isinstance(data, dict) else []
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    generated_at = data.get("generated_at", "N/A") if isinstance(data, dict) else "N/A"

    def _badge(st: str) -> str:
        cls = {"ok": "ok", "warn": "warn", "missing": "missing"}.get(st, "missing")
        return f'<span class="badge {html.escape(cls)}">{html.escape(st)}</span>'

    def _pill(label: str, on: bool) -> str:
        cls = "on" if on else "off"
        return f'<div class="pill {cls}">{html.escape(label)}</div>'

    cards_html = ""
    for it in items:
        name = it.get("name", "N/A")
        purpose = it.get("purpose", it.get("source", ""))
        status = it.get("status", "unknown")
        reason = it.get("degraded_reason", "")
        ev = json.dumps(it.get("evidence", {}), ensure_ascii=False, indent=2)
        reason_html = ('<div class="reason">' + html.escape(reason) + '</div>') if reason else ''
        cards_html += (
            '<article class="card">'
            '<div class="card-head"><div><div class="card-name">' + html.escape(name) + '</div>'
            '<div class="purpose">' + html.escape(purpose) + '</div></div>'
            + _badge(status) + '</div>'
            '<div class="state-row">'
            + _pill("安装", bool(it.get("installed")))
            + _pill("配置", bool(it.get("configured")))
            + _pill("运行", bool(it.get("running")))
            + _pill("索引", bool(it.get("indexed")))
            + _pill("默认", bool(it.get("used_by_default")))
            + '</div>'
            + reason_html
            + '<details><summary>证据详情</summary>'
            '<pre class="code">' + html.escape(ev) + '</pre></details>'
            '</article>'
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Integrations Health</title>
<style>
:root{{--bg:#f7f0df;--ink:#211b12;--muted:#746858;--panel:#fffaf0;--line:rgba(33,27,18,.14);--accent:#1f6f5b;--ok:#1a7a4a;--warn:#c27a10;--err:#9f3a2f;--miss:#888;}}
body{{margin:0;background:radial-gradient(circle at top left,#fff8df,#efe4cf 42%,#d9e7df);color:var(--ink);font-family:"Avenir Next","Gill Sans",ui-sans-serif,sans-serif;}}
header,main{{max-width:1180px;margin:0 auto;padding:24px;}}
.hero{{border:1px solid var(--line);border-radius:30px;padding:28px;background:linear-gradient(135deg,rgba(255,250,240,.90),rgba(226,239,230,.70));box-shadow:0 24px 70px rgba(33,27,18,.10);}}
.eyebrow{{text-transform:uppercase;letter-spacing:.14em;color:var(--accent);font-weight:900;font-size:.78rem;}}
h1{{font-size:clamp(2rem,5vw,4rem);line-height:.9;margin:.2rem 0 .8rem;}}
.muted{{color:var(--muted);}}
.actions{{display:flex;flex-wrap:wrap;gap:.7rem;align-items:center;margin-top:.8rem;}}
.btn{{border:1px solid var(--line);border-radius:14px;padding:.7rem .95rem;background:rgba(255,255,255,.54);color:var(--ink);text-decoration:none;font-weight:900;cursor:pointer;}}
.btn.primary{{background:var(--ink);color:#fff8e8;}}
.summary-strip{{display:grid;grid-template-columns:repeat(4,minmax(100px,1fr));gap:.65rem;margin:1.2rem 0;}}
.s-tile{{border:1px solid var(--line);border-radius:18px;padding:.85rem;background:rgba(255,255,255,.42);}}
.s-tile .num{{font-size:1.8rem;font-weight:900;color:var(--accent);display:block;margin-top:.2rem;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1rem;margin-top:1rem;}}
.card{{border:1px solid var(--line);border-radius:24px;padding:1rem;background:rgba(255,252,244,.66);box-shadow:0 12px 32px rgba(33,27,18,.06);}}
.card-head{{display:flex;gap:.7rem;justify-content:space-between;align-items:flex-start;}}
.card-name{{font-size:1.05rem;font-weight:900;line-height:1.2;}}
.badge{{display:inline-block;padding:3px 9px;border-radius:999px;font:800 .74rem ui-monospace,SFMono-Regular,Menlo,monospace;color:#fffaf0;}}
.badge.ok{{background:var(--ok);}}
.badge.warn{{background:var(--warn);}}
.badge.missing{{background:var(--miss);}}
.state-row{{display:grid;grid-template-columns:repeat(5,1fr);gap:.4rem;margin:.7rem 0;}}
.pill{{border-radius:10px;padding:.35rem .4rem;text-align:center;font:800 .7rem ui-monospace,SFMono-Regular,Menlo,monospace;border:1px solid var(--line);}}
.pill.on{{background:#d1f5e0;color:#1a7a4a;border-color:#a3e8c0;}}
.pill.off{{background:#f5e8d0;color:#888;border-color:#e8d8b8;}}
.reason{{font-size:.86rem;margin:.5rem 0;padding:.5rem .7rem;border-radius:12px;background:rgba(255,255,255,.38);border:1px solid var(--line);}}
.purpose{{color:var(--muted);font-size:.84rem;margin:.3rem 0 .6rem;}}
details summary{{cursor:pointer;color:var(--muted);font-size:.82rem;margin-top:.7rem;}}
pre.code{{background:#211b12;color:#f8efe0;border-radius:14px;padding:.8rem;font-size:.78rem;overflow:auto;white-space:pre-wrap;word-break:break-all;max-height:200px;}}
.refresh-ts{{color:var(--muted);font-size:.78rem;margin-top:.5rem;}}
</style>
</head>
<body>
<header>
  <div class="hero">
    <div class="eyebrow">Solar Harness · External Integrations</div>
    <h1>集成健康</h1>
    <p class="muted">七个外部开源/外部项目的六态健康检查：installed · configured · running · indexed · used_by_default · degraded_reason</p>
    <div class="actions">
      <a class="btn primary" href="/integrations-view">刷新</a>
      <a class="btn" href="/integrations" target="_blank">JSON 原始数据</a>
      <a class="btn" href="/">Solar Status</a>
    </div>
    <p class="refresh-ts">探测时间: {html.escape(generated_at)}</p>
  </div>
</header>
<main>
  <div class="summary-strip">
    <div class="s-tile"><div class="muted">TOTAL</div><span class="num">{html.escape(str(summary.get("total", len(items))))}</span></div>
    <div class="s-tile"><div class="muted">OK</div><span class="num" style="color:var(--ok)">{html.escape(str(summary.get("ok", 0)))}</span></div>
    <div class="s-tile"><div class="muted">WARN</div><span class="num" style="color:var(--warn)">{html.escape(str(summary.get("warn", 0)))}</span></div>
    <div class="s-tile"><div class="muted">MISSING</div><span class="num" style="color:var(--miss)">{html.escape(str(summary.get("missing", 0)))}</span></div>
  </div>
  <div class="grid">
{cards_html}
  </div>
</main>
</body>
</html>"""


def _external_integrations_payload(refresh: bool = False) -> dict:
    if not INTEGRATIONS_HEALTH.exists():
        return {"error": "external integrations probe missing", "path": str(INTEGRATIONS_HEALTH)}
    # The probe can run deep historical upload audits, but the dashboard must
    # remain responsive. Use cached/fast health by default; explicit refresh is
    # still local-only and bounded.
    cmd = ["python3", str(INTEGRATIONS_HEALTH), "--json", "--max-age", "3600"]
    if refresh:
        cmd.append("--refresh")
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=12,
        )
    except subprocess.TimeoutExpired:
        return {"error": "external integrations probe timeout", "path": str(INTEGRATIONS_HEALTH)}
    if proc.returncode != 0:
        return {"error": "external integrations probe failed", "stderr": proc.stderr[-1000:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "external integrations probe returned invalid json", "stdout": proc.stdout[-1000:]}


def _current_sprint() -> dict:
    """Return {sprint_id, status, phase, round} for the most recently active sprint."""
    if not SPRINTS_DIR.exists():
        return {}
    candidates = []
    for sf in SPRINTS_DIR.glob("sprint-*.status.json"):
        try:
            d = json.loads(sf.read_text())
            st = d.get("status", "")
            if st not in ("passed", "failed", "cancelled", "finalized"):
                candidates.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    if not candidates:
        # fall back to most recently modified
        all_sf = sorted(SPRINTS_DIR.glob("sprint-*.status.json"), key=lambda p: p.stat().st_mtime)
        if all_sf:
            try:
                candidates = [json.loads(all_sf[-1].read_text())]
            except (json.JSONDecodeError, OSError):
                pass
    if not candidates:
        return {}
    # pick highest-priority non-terminal
    order = {"active": 0, "reviewing": 1, "planning": 2, "approved": 3}
    candidates.sort(key=lambda d: order.get(d.get("status", "z"), 9))
    d = candidates[0]
    return {
        "sprint_id": d.get("id", d.get("sprint_id", "")),
        "status": d.get("status", ""),
        "phase": d.get("phase", ""),
        "round": d.get("round", 0),
        "handoff_to": d.get("handoff_to", ""),
        "title": d.get("title", ""),
        "priority": d.get("priority", ""),
        "lane": d.get("lane", ""),
        "description": _sprint_description(d.get("id", d.get("sprint_id", ""))),
    }


def _first_paragraph_after_heading(text: str, heading_pattern: str) -> str:
    lines = text.splitlines()
    start = -1
    for idx, line in enumerate(lines):
        if re.match(heading_pattern, line.strip(), flags=re.IGNORECASE):
            start = idx + 1
            break
    if start < 0:
        return ""
    buf = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("#") and buf:
            break
        if not s:
            if buf:
                break
            continue
        if s.startswith("**") or s.startswith("- "):
            continue
        buf.append(s)
    return " ".join(buf).strip()


def _clip_text(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _sprint_description(sid: str) -> str:
    if not sid:
        return ""
    for suffix in (".prd.md", ".product-brief.md", ".contract.md", ".plan.md"):
        path = SPRINTS_DIR / f"{sid}{suffix}"
        try:
            if not path.exists():
                continue
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        desc = (
            _first_paragraph_after_heading(text, r"^##\s*(背景|context)\b.*")
            or _first_paragraph_after_heading(text, r"^##\s*(用户问题|problem)\b.*")
            or _first_paragraph_after_heading(text, r"^##\s*(目标|goals?|intent)\b.*")
        )
        if desc:
            return _clip_text(desc)
    return ""


def _sprint_meta(sid: str) -> dict:
    if not sid:
        return {"sprint_id": "", "title": "", "status": "", "phase": "", "description": ""}
    status_path = SPRINTS_DIR / f"{sid}.status.json"
    meta = {
        "sprint_id": sid,
        "title": sid,
        "status": "",
        "phase": "",
        "priority": "",
        "lane": "",
        "handoff_to": "",
        "description": _sprint_description(sid),
    }
    try:
        if status_path.exists():
            d = json.loads(status_path.read_text())
            meta.update(
                {
                    "title": d.get("title") or sid,
                    "status": d.get("status", ""),
                    "phase": d.get("phase", ""),
                    "priority": d.get("priority", ""),
                    "lane": d.get("lane", ""),
                    "handoff_to": d.get("handoff_to", ""),
                }
            )
            if not meta["description"]:
                meta["description"] = _clip_text(" ".join(d.get("evidence", [])[:2]))
    except (json.JSONDecodeError, OSError):
        pass
    return meta


def _read_assignments() -> dict:
    """Return pane assignment map from current or legacy assignment files."""
    if PANE_ASSIGNMENTS.exists():
        out = {}
        try:
            for raw in PANE_ASSIGNMENTS.read_text().splitlines():
                raw = raw.strip()
                if not raw or "=" not in raw:
                    continue
                pane, rest = raw.split("=", 1)
                sid = rest.rsplit(":", 1)[0]
                if pane and sid:
                    out[pane] = sid
            return out
        except OSError:
            return {}
    if not PANE_ASSIGNMENTS_JSON.exists():
        return {}
    try:
        d = json.loads(PANE_ASSIGNMENTS_JSON.read_text())
        return {str(k): str(v) for k, v in d.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def _pane_info() -> list:
    """Return list of known pane assignments."""
    d = _read_assignments()
    return [{"pane": k, "sprint_id": v, "sprint": _sprint_meta(v)} for k, v in d.items()]


def _run_tmux(args: list, timeout: float = 0.8) -> str:
    try:
        result = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip("\n")
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _runtime_from_tail(tail: str) -> str:
    """Classify pane runtime from recent Claude Code tail output."""
    active_re = re.compile(
        r"Generating|thinking\)|Reading|Bash|Write|Edit|Inferring|Hatching|"
        r"Whirlpooling|Enchanting|Meandering|Philosophising",
        re.IGNORECASE,
    )
    if active_re.search(tail):
        return "active"
    if "❯" in tail or "mode on" in tail:
        return "idle"
    return "unknown"


def _artifact_for_assignment(role: str, sid: str) -> dict:
    if not sid:
        return {"state": "N/A", "path": "", "mtime": ""}
    candidates = []
    if role == "PM":
        candidates = [SPRINTS_DIR / f"{sid}.prd.md", SPRINTS_DIR / f"{sid}.product-brief.md"]
    elif role == "Planner":
        candidates = [SPRINTS_DIR / f"{sid}.plan.md"]
    elif role == "Builder":
        candidates = [SPRINTS_DIR / f"{sid}.handoff.md"]
    elif role == "Evaluator":
        candidates = [SPRINTS_DIR / f"{sid}.eval.md"]
    else:
        candidates = sorted((SPRINTS_DIR / "obsidian-wiki-lab").glob(f"{role.lower().replace(' ', '-') }*handoff.md"))

    for path in candidates:
        try:
            if path.exists():
                return {
                    "state": "present",
                    "path": str(path),
                    "mtime": path.stat().st_mtime,
                }
        except OSError:
            continue
    return {"state": "missing", "path": str(candidates[0]) if candidates else "", "mtime": ""}


def _pane_snapshot(target: str, role: str, assignment: str = "") -> dict:
    assignment_meta = _sprint_meta(assignment) if assignment else {}
    pane_id = _run_tmux(["display-message", "-p", "-t", target, "#{pane_id}"])
    if not pane_id:
        return {
            "target": target,
            "role": role,
            "runtime_state": "missing",
            "assignment": assignment or "",
            "assignment_meta": assignment_meta,
            "artifact": _artifact_for_assignment(role, assignment),
            "title": "",
        }
    title = _run_tmux(["display-message", "-p", "-t", target, "#{pane_title}"])
    tail = _run_tmux(["capture-pane", "-t", target, "-p", "-S", "-8"], timeout=1.0)
    return {
        "target": target,
        "role": role,
        "runtime_state": _runtime_from_tail(tail),
        "assignment": assignment or "",
        "assignment_meta": assignment_meta,
        "artifact": _artifact_for_assignment(role, assignment),
        "title": title,
    }


def _main_screen() -> dict:
    assignments = _read_assignments()
    roles = ["PM", "Planner", "Builder", "Evaluator"]
    panes = []
    for idx, role in enumerate(roles):
        target = f"solar-harness:0.{idx}"
        panes.append(_pane_snapshot(target, role, assignments.get(target, "")))
    return {
        "note": "runtime_state, assignment, and artifact are separate; pane output alone is not proof of progress.",
        "panes": panes,
    }


def _lab_screen() -> dict:
    roles = ["lab-builder-1", "lab-builder-2", "lab-builder-3", "lab-builder-4"]
    lab_dir = SPRINTS_DIR / "obsidian-wiki-lab"
    panes = []
    for idx, role in enumerate(roles):
        target = f"solar-harness-lab:0.{idx}"
        snap = _pane_snapshot(target, role, "")
        latest = None
        if lab_dir.exists():
            matches = sorted(lab_dir.glob(f"{role}*handoff.md"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
            latest = matches[-1] if matches else None
        if latest:
            snap["artifact"] = {
                "state": "present",
                "path": str(latest),
                "mtime": latest.stat().st_mtime,
            }
        panes.append(snap)
    return {
        "note": "artifact != runtime: handoff files prove delivery; pane state proves current activity.",
        "panes": panes,
    }


def _kpi() -> dict:
    """Compute KPI from sprint status files."""
    total = passed = failed = 0
    for sf in SPRINTS_DIR.glob("sprint-*.status.json"):
        try:
            d = json.loads(sf.read_text())
            total += 1
            st = d.get("status", "")
            if st in ("passed", "finalized"):
                passed += 1
            elif st in ("failed", "failed_review"):
                failed += 1
        except (json.JSONDecodeError, OSError):
            continue
    return {
        "sprints_total": total,
        "sprints_passed": passed,
        "sprints_failed": failed,
        "pass_rate": round(passed / total, 2) if total > 0 else 0.0,
    }


def _mirage_status() -> dict:
    """Return mirage VFS status block. Reads last-probe.json cache; never raises."""
    probe_path = HARNESS_DIR / "state" / "mirage" / "last-probe.json"
    empty = {"enabled": False, "mounts": [], "drive": {"status": "unknown"}, "qmd": {"status": "unknown"}, "last_probe_at": None}
    if not probe_path.exists():
        return empty
    try:
        import time as _time
        probe = json.loads(probe_path.read_text())
        # TTL: treat stale (>120s) probes as degraded but still return them
        probe_ts = probe.get("probed_at", "")
        stale = False
        if probe_ts:
            try:
                import datetime as _dt
                age = (_dt.datetime.utcnow() - _dt.datetime.fromisoformat(probe_ts.replace("Z", ""))).total_seconds()
                stale = age > 120
            except Exception:
                pass
        drive = probe.get("drive", {})
        qmd = probe.get("qmd", {})
        return {
            "enabled": probe.get("enabled", False),
            "workspace_id": probe.get("workspace_id", ""),
            "mounts": probe.get("mounts", []),
            "drive": drive,
            "drive_status": drive.get("status", "unknown") if isinstance(drive, dict) else "unknown",
            "qmd": qmd,
            "qmd_indexed": qmd.get("indexed", 0) if isinstance(qmd, dict) else 0,
            "last_probe_at": probe_ts,
            "stale": stale,
            "config": probe.get("config", ""),
        }
    except (json.JSONDecodeError, OSError, Exception):
        return empty


def _pane_capability_summary() -> dict:
    """Return capability summary for all known panes. Never raises — degrades gracefully."""
    persona_script = HARNESS_DIR / "lib" / "persona-config.sh"
    skills_py = HARNESS_DIR / "lib" / "solar_skills.py"

    panes_out = []
    if persona_script.exists():
        known_panes = ["lab-builder", "builder", "evaluator", "planner", "monitor"]
        for pane in known_panes:
            try:
                result = subprocess.run(
                    ["bash", str(persona_script), "--print-config", pane],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    cfg: dict = {}
                    for line in result.stdout.splitlines():
                        if "=" in line:
                            k, _, v = line.partition("=")
                            cfg[k.strip()] = v.strip("'\"")
                    extra_flags = cfg.get("EXTRA_FLAGS", "")
                    mcp_mode = "STRICT" if "--strict-mcp-config" in extra_flags else "DEFAULT"
                    kb_context = mcp_mode == "DEFAULT"
                    skills_accessible = kb_context
                    panes_out.append({
                        "pane": pane,
                        "model": cfg.get("MODEL_FLAG", "").replace("--model ", ""),
                        "auth_source": cfg.get("AUTH_SOURCE", "unknown"),
                        "mcp_mode": mcp_mode,
                        "kb_context": kb_context,
                        "skills_accessible": skills_accessible,
                    })
            except Exception:
                pass

    # Skills inventory counts from cache
    skills_inventory: dict = {}
    inventory_cache = HARNESS_DIR / "state" / "skills-inventory.json"
    if inventory_cache.exists():
        try:
            skills_inventory = json.loads(inventory_cache.read_text())
        except Exception:
            pass
    elif skills_py.exists():
        try:
            r = subprocess.run(
                ["python3", str(skills_py), "inventory", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                skills_inventory = json.loads(r.stdout)
        except Exception:
            pass

    return {
        "panes": panes_out,
        "skills": skills_inventory.get("totals", {}),
        "overall": {
            "total_panes": len(panes_out),
            "strict_mcp_panes": sum(1 for p in panes_out if p["mcp_mode"] == "STRICT"),
            "default_mcp_panes": sum(1 for p in panes_out if p["mcp_mode"] == "DEFAULT"),
            "status": "ok" if panes_out else "no_panes_configured",
        },
    }


def _obsidian_wiki_readiness() -> dict:
    """Return obsidian_wiki readiness block. Never raises — degrades to ready=false."""
    integration = HARNESS_DIR / "integrations" / "obsidian-wiki.sh"
    harness_bin = HARNESS_DIR / "solar-harness.sh"

    # Integration not installed yet
    if not integration.exists() and not harness_bin.exists():
        return {
            "ready": False,
            "configured": False,
            "vault_path": "",
            "issues": ["integration not installed"],
        }

    try:
        result = subprocess.run(
            ["bash", str(integration), "status", "--json"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {
                "ready": False,
                "configured": False,
                "vault_path": "",
                "issues": ["status check failed (exit {})".format(result.returncode)],
            }
        data = json.loads(result.stdout)
        configured = data.get("configured", False)
        vault_path = data.get("vault_path", "")
        skills = data.get("skills_installed", {})
        issues = []
        if not configured:
            issues.append("wiki not configured")
        if vault_path and not Path(vault_path).exists():
            issues.append("vault path missing: {}".format(vault_path))
        missing_skills = [k for k, v in skills.items() if not v]
        if missing_skills:
            issues.append("skills not installed: {}".format(", ".join(missing_skills)))
        return {
            "ready": configured and len(issues) == 0,
            "configured": configured,
            "vault_path": vault_path,
            "issues": issues,
        }
    except subprocess.TimeoutExpired:
        return {"ready": False, "configured": False, "vault_path": "", "issues": ["status check timeout"]}
    except (json.JSONDecodeError, OSError, Exception) as exc:
        return {"ready": False, "configured": False, "vault_path": "", "issues": [str(exc)]}


def _solar_kb_status() -> dict:
    """Return solar KB (obsidian_vault_index) status. Never raises."""
    empty = {"indexed_count": 0, "last_indexed_at": None, "ok": False}
    db_path = Path(os.environ.get("SOLAR_DB", str(Path.home() / ".solar" / "solar.db")))
    if not db_path.exists():
        return {**empty, "error": "solar.db not found"}
    try:
        with sqlite3.connect(str(db_path), timeout=0.3) as conn:
            conn.execute("PRAGMA query_only=1")
            row = conn.execute(
                "SELECT COUNT(*), MAX(indexed_at) FROM obsidian_vault_index WHERE deleted_at IS NULL"
            ).fetchone()
            cnt, last_at = (row[0] or 0), (row[1] or None)
            return {"indexed_count": cnt, "last_indexed_at": last_at, "ok": cnt > 0}
    except sqlite3.OperationalError:
        return {**empty, "error": "obsidian_vault_index table not found"}
    except Exception as exc:
        return {**empty, "error": str(exc)}


def _obsidian_sync_status() -> dict:
    """Return Obsidian→Solar sync status: pending raw queue + last sync manifest. Never raises."""
    vault_path = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/Users/sihaoli/Knowledge"))
    raw_dir = HARNESS_DIR / "vendor" / "obsidian-wiki" / "_raw" / "solar-db-export"
    manifest_path = HARNESS_DIR / "state" / "knowledge-manifest.json"
    try:
        pending_raw = len(list(raw_dir.glob("*.json"))) if raw_dir.exists() else 0
    except Exception:
        pending_raw = 0
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            pass
    return {
        "vault_path": str(vault_path),
        "vault_exists": vault_path.exists(),
        "pending_raw_export": pending_raw,
        "last_sync_at": manifest.get("last_sync_at") or manifest.get("generated_at"),
        "ok": vault_path.exists(),
    }


def _apple_notes_ingest_status() -> dict:
    """Return Apple Notes ingest status. Never raises."""
    manifest_path = HARNESS_DIR / "state" / "apple-notes-ingest" / "manifest.json"
    config_path = HARNESS_DIR / "config" / "apple-notes-ingest.json"
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.solar.apple-notes-ingest.plist"
    cfg: dict = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
        except Exception:
            pass
    manifest: dict = {"notes": {}}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            pass
    notes = manifest.get("notes", {})
    exported = sum(1 for n in notes.values() if n.get("ingest_status") == "exported")
    dispatched = sum(1 for n in notes.values() if n.get("ingest_status") == "dispatched")
    last_run_at = manifest.get("last_scan_at")
    scheduler_loaded = False
    if plist_path.exists():
        try:
            import subprocess as _sp
            r = _sp.run(["launchctl", "list", "com.solar.apple-notes-ingest"],
                        capture_output=True, timeout=3)
            scheduler_loaded = r.returncode == 0
        except Exception:
            pass
    return {
        "enabled": manifest_path.exists(),
        "interval_seconds": cfg.get("interval_seconds", 7200),
        "last_run_at": last_run_at,
        "last_success_at": last_run_at,
        "last_error": None,
        "notes_seen": len(notes),
        "notes_exported": exported,
        "notes_skipped": len(notes) - exported - dispatched,
        "dispatch_created": dispatched,
        "scheduler_loaded": scheduler_loaded,
        "ok": manifest_path.exists(),
    }


def _status_payload(limit: int = 50) -> dict:
    return {
        "current_sprint": _current_sprint(),
        "panes": _pane_info(),
        "main_screen": _main_screen(),
        "lab_screen": _lab_screen(),
        "recent_events": _read_jsonl(ALL_EVENTS, limit=limit, filter_synthetic=True),
        "kpi": _kpi(),
        "obsidian_wiki": _obsidian_wiki_readiness(),
        "mirage": _mirage_status(),
        "solar_kb": _solar_kb_status(),
        "obsidian_sync": _obsidian_sync_status(),
        "apple_notes_ingest": _apple_notes_ingest_status(),
    }


# ── HTML Dashboard ──
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Harness Status</title>
<style>
:root {
  --bg: #f3efe4;
  --ink: #18211f;
  --muted: #68726d;
  --panel: rgba(255, 252, 244, 0.86);
  --panel-solid: #fffaf0;
  --line: rgba(30, 43, 39, 0.14);
  --shadow: 0 24px 80px rgba(33, 27, 18, 0.12);
  --accent: #e4572e;
  --accent-2: #0f6b68;
  --accent-3: #f0b429;
  --warn: #b7791f;
  --error: #bf2f2f;
  --ok: #197a50;
  --code: #17211f;
  --page-max: 1380px;
  --page-pad: clamp(20px, 4vw, 56px);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif;
  background:
    radial-gradient(circle at 8% 8%, rgba(228, 87, 46, 0.18), transparent 23rem),
    radial-gradient(circle at 92% 4%, rgba(15, 107, 104, 0.16), transparent 24rem),
    linear-gradient(135deg, rgba(255, 255, 255, 0.42), transparent 36%),
    var(--bg);
  color: var(--ink);
}
header {
  padding: 1.35rem var(--page-pad) 0.75rem;
}
.hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 1.35rem;
  border: 1px solid var(--line);
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(255, 250, 240, 0.92), rgba(255, 247, 226, 0.62));
  box-shadow: var(--shadow);
}
.eyebrow {
  color: var(--accent);
  font: 800 0.72rem ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
h1 {
  margin: 0.25rem 0 0;
  color: var(--ink);
  font-family: "Iowan Old Style", "Palatino", Georgia, serif;
  font-size: clamp(2rem, 4vw, 4rem);
  line-height: 0.95;
  letter-spacing: -0.055em;
}
h2 {
  margin: 0 0 0.85rem;
  color: var(--ink);
  font-size: 1.1rem;
  letter-spacing: -0.02em;
}
h3 {
  margin: 0 0 0.55rem;
  color: var(--ink);
  font-size: 0.93rem;
  letter-spacing: 0.01em;
}
a { color: var(--accent-2); }
main {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 1.1rem var(--page-pad) 2.5rem;
}
.subhead {
  color: var(--muted);
  font: 600 0.84rem ui-monospace, SFMono-Regular, Menlo, monospace;
  margin-top: 0.45rem;
}
.tabbar {
  display: flex;
  gap: 0.45rem;
  overflow-x: auto;
  width: calc(100% - clamp(40px, 8vw, 112px));
  max-width: var(--page-max);
  margin: 0.95rem auto 0;
  padding: 0.45rem;
  position: sticky;
  top: 0.5rem;
  z-index: 6;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 250, 240, 0.78);
  backdrop-filter: blur(18px);
  box-shadow: 0 14px 48px rgba(33, 27, 18, 0.10);
}
.tab {
  border: 0;
  background: transparent;
  color: #59635f;
  border-radius: 999px;
  padding: 0.68rem 0.95rem;
  font: 800 0.86rem "Avenir Next", "Gill Sans", sans-serif;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 120ms ease, background 120ms ease, color 120ms ease;
}
.tab.active {
  background: var(--ink);
  color: #fff9ea;
  box-shadow: 0 10px 24px rgba(24, 33, 31, 0.20);
}
.tab:hover { transform: translateY(-1px); }
.panel { display: none; }
.panel.active { display: block; animation: rise 180ms ease-out; }
@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 1rem; }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 24px;
  padding: 1.05rem;
  margin-bottom: 1rem;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.card:nth-child(4n + 1) { background: linear-gradient(145deg, rgba(255, 252, 244, 0.92), rgba(255, 239, 205, 0.72)); }
.card:nth-child(4n + 2) { background: linear-gradient(145deg, rgba(255, 252, 244, 0.92), rgba(221, 240, 234, 0.72)); }
.card:nth-child(4n + 3) { background: linear-gradient(145deg, rgba(255, 252, 244, 0.92), rgba(249, 225, 213, 0.72)); }
.metric {
  font-family: "Iowan Old Style", "Palatino", Georgia, serif;
  font-size: 2.6rem;
  line-height: 1;
  color: var(--accent);
  margin-top: 0.35rem;
}
.muted { color: var(--muted); }
.task-block {
  display: grid;
  gap: 0.72rem;
}
.task-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding-bottom: 0.7rem;
  border-bottom: 1px solid var(--line);
}
.task-title {
  font: 800 1rem "Avenir Next", "Gill Sans", sans-serif;
  letter-spacing: -0.02em;
}
.kv-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.55rem;
}
.kv {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.62rem 0.72rem;
  background: rgba(255, 255, 255, 0.38);
}
.kv-label {
  color: var(--muted);
  font: 800 0.68rem ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.kv-value {
  margin-top: 0.18rem;
  font-weight: 800;
}
.summary-list {
  display: grid;
  gap: 0.45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.summary-list li {
  position: relative;
  padding: 0.58rem 0.7rem 0.58rem 1.9rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 252, 244, 0.52);
  line-height: 1.45;
}
.summary-list li::before {
  content: "";
  position: absolute;
  left: 0.78rem;
  top: 1.05rem;
  width: 0.44rem;
  height: 0.44rem;
  border-radius: 999px;
  background: var(--accent);
}
.tech-id {
  color: var(--muted);
  font: 700 0.72rem ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-all;
}
.path-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.86rem;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.badge {
  display:inline-block;
  padding: 3px 9px;
  border-radius: 999px;
  font: 800 0.74rem ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #fffaf0;
  background: var(--muted);
}
.badge.active, .badge.passed, .badge.ok { background: var(--ok); }
.badge.reviewing { background: var(--accent-2); }
.badge.failed, .badge.error-badge { background: var(--error); }
.badge.warn-badge { background: var(--warn); }
.warn { color: var(--warn); }
.error { color: var(--error); }
.info { color: var(--accent-2); }
.ok-text { color: var(--ok); }
table {
  border-collapse: separate;
  border-spacing: 0;
  width: 100%;
  overflow: hidden;
  border-radius: 16px;
}
th {
  text-align: left;
  color: #55615c;
  border-bottom: 1px solid var(--line);
  padding: 9px 10px;
  font: 800 0.76rem ui-monospace, SFMono-Regular, Menlo, monospace;
  background: rgba(255, 255, 255, 0.34);
}
td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  font-size: 0.9rem;
  vertical-align: top;
  background: rgba(255, 252, 244, 0.34);
}
.refresh {
  color: var(--muted);
  font: 600 0.78rem ui-monospace, SFMono-Regular, Menlo, monospace;
  margin-bottom: 0.5rem;
}
.actions { display: flex; flex-wrap: wrap; gap: 0.65rem; margin: 0.8rem 0; }
.knowledge-shell {
  display: grid;
  gap: 1rem;
}
.knowledge-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  gap: 1rem;
  align-items: stretch;
}
.knowledge-title {
  font-family: "Iowan Old Style", "Palatino", Georgia, serif;
  font-size: clamp(1.9rem, 3vw, 3.2rem);
  line-height: 0.98;
  letter-spacing: -0.055em;
  margin: 0 0 0.75rem;
}
.status-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.65rem;
}
.status-tile {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 0.85rem;
  background: rgba(255,255,255,0.42);
  min-width: 0;
}
.status-tile strong {
  display: block;
  margin-top: 0.4rem;
  font-size: 1.02rem;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.25;
}
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.8rem;
}
.action-card {
  min-height: 128px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 1rem;
  background: rgba(255, 252, 244, 0.58);
}
.action-card h3 { margin-bottom: 0.35rem; }
.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
}
.overview-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(290px, 0.55fr);
  gap: 1rem;
  align-items: stretch;
}
.overview-stack {
  display: grid;
  gap: 1rem;
}
.overview-bottom {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.overview-side-card {
  min-height: 0;
}
.health-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
  gap: 0.65rem;
  margin-bottom: 0.8rem;
}
.mini-metric {
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.42);
}
.mini-metric .num {
  display: block;
  margin-top: 0.25rem;
  color: var(--accent-2);
  font: 900 1.18rem ui-monospace, SFMono-Regular, Menlo, monospace;
  overflow-wrap: anywhere;
}
.mount-list {
  display: grid;
  gap: 0.5rem;
}
.mount-row {
  display: grid;
  grid-template-columns: minmax(90px, 0.8fr) auto minmax(0, 1.4fr);
  gap: 0.65rem;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.62rem 0.72rem;
  background: rgba(255, 252, 244, 0.50);
}
.mount-path {
  font: 900 0.86rem ui-monospace, SFMono-Regular, Menlo, monospace;
}
.mount-reason {
  color: var(--muted);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}
.integration-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 1rem;
}
.integration-card {
  border: 1px solid var(--line);
  border-radius: 24px;
  padding: 1rem;
  background: rgba(255, 252, 244, 0.66);
  box-shadow: 0 12px 32px rgba(33, 27, 18, 0.06);
}
.integration-head {
  display: flex;
  gap: 0.7rem;
  justify-content: space-between;
  align-items: flex-start;
}
.integration-name {
  font-size: 1.08rem;
  font-weight: 900;
  line-height: 1.2;
}
.state-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.45rem;
  margin: 0.85rem 0;
}
.state-pill {
  border: 1px solid var(--line);
  border-radius: 13px;
  padding: 0.5rem 0.35rem;
  text-align: center;
  background: rgba(255, 255, 255, 0.42);
  font-size: 0.76rem;
  font-weight: 900;
}
.state-pill.ok { background: rgba(56, 128, 93, 0.14); color: #1f6f5b; }
.state-pill.warn { background: rgba(190, 112, 55, 0.16); color: #8b4a1d; }
.integration-reason {
  min-height: 2.2rem;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.integration-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
  margin-bottom: 1rem;
}
.btn {
  display: inline-block;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.72rem 0.95rem;
  background: rgba(255, 255, 255, 0.48);
  color: var(--ink);
  text-decoration: none;
  cursor: pointer;
  font: 800 0.88rem "Avenir Next", "Gill Sans", sans-serif;
  box-shadow: 0 8px 22px rgba(33, 27, 18, 0.08);
}
.btn.primary {
  background: var(--ink);
  color: #fff9ea;
  border-color: var(--ink);
}
.codebox {
  background: var(--code);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 18px;
  color: #f7efe0;
  overflow: auto;
  padding: 1rem;
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.embed {
  width: 100%;
  height: 640px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: var(--panel-solid);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.22);
}
@media (max-width: 720px) {
  .hero { align-items: flex-start; flex-direction: column; border-radius: 22px; }
  .knowledge-hero { grid-template-columns: 1fr; }
  .overview-shell, .overview-bottom { grid-template-columns: 1fr; }
  .tabbar { width: calc(100% - 32px); border-radius: 20px; }
  .tab { padding: 0.62rem 0.78rem; }
  main { padding-top: 0.9rem; }
}
</style>
</head>
<body>
<header>
  <div class="hero">
    <div>
      <div class="eyebrow">Solar Harness Control Desk</div>
      <h1>Solar Status</h1>
    </div>
    <div class="subhead" id="refresh-ts">Loading...</div>
  </div>
</header>

<nav class="tabbar" role="tablist">
  <button class="tab active" data-tab="overview">总览</button>
  <button class="tab" data-tab="sprint">Sprint</button>
  <button class="tab" data-tab="main">主屏</button>
  <button class="tab" data-tab="lab">Builder Lab</button>
  <button class="tab" data-tab="events">事件</button>
  <button class="tab" data-tab="knowledge">知识库</button>
  <button class="tab" data-tab="upload">上传文档</button>
  <button class="tab" data-tab="config">配置</button>
  <button class="tab" data-tab="integrations">集成</button>
  <button class="tab" data-tab="diagrams">架构图</button>
  <button class="tab" data-tab="raw">Raw JSON</button>
</nav>

<main>
  <section class="panel active" id="tab-overview">
    <div class="overview-shell">
      <div class="card"><h2>当前主线</h2><div id="overview-sprint">Loading...</div></div>
      <div class="overview-stack">
        <div class="card overview-side-card"><h3>Pane Health</h3><div id="overview-panes">Loading...</div></div>
        <div class="card overview-side-card"><h3>KPI</h3><div id="overview-kpi">Loading...</div></div>
      </div>
    </div>
    <div class="overview-bottom">
      <div class="card"><h3>知识库状态</h3><div id="overview-knowledge">Loading...</div></div>
      <div class="card"><h3>最近风险</h3><div id="overview-risk">Loading...</div></div>
    </div>
  </section>

  <section class="panel" id="tab-sprint">
    <h2>Current Sprint</h2>
    <div class="card" id="sprint-card">Loading...</div>
    <h2>Pane Assignments</h2>
    <div class="card" id="panes-card">Loading...</div>
  </section>

  <section class="panel" id="tab-main">
    <h2>Main Screen</h2>
    <div class="card" id="main-screen-card">Loading...</div>
  </section>

  <section class="panel" id="tab-lab">
    <h2>Builder Lab</h2>
    <div class="card" id="lab-screen-card">Loading...</div>
  </section>

  <section class="panel" id="tab-events">
    <h2>Recent Events</h2>
    <div class="card" id="events-card">Loading...</div>
  </section>

  <section class="panel" id="tab-knowledge">
    <div class="knowledge-shell">
      <div class="knowledge-hero">
        <div class="card">
          <div class="eyebrow">Knowledge Desk</div>
          <h2 class="knowledge-title">知识库工作台</h2>
          <p class="muted">这里看 Obsidian vault、上传入口、Mirage/QMD 检索底座是否可用。优先展示能不能用和下一步去哪操作，详细健康信息放下面。</p>
          <div class="status-strip" id="knowledge-summary">Loading...</div>
        </div>
        <div class="card">
          <h3>当前路径</h3>
          <div class="codebox">Vault  /Users/sihaoli/Knowledge
Raw    /Users/sihaoli/Knowledge/_raw
Upload http://127.0.0.1:8788
Config http://127.0.0.1:8789/setup</div>
        </div>
      </div>

      <div class="card">
        <h2>常用动作</h2>
        <div class="action-grid">
          <div class="action-card">
            <div><h3>上传资料</h3><div class="muted">粘贴网页、批量上传 PDF/图片/Markdown 到 _raw。</div></div>
            <a class="btn primary" href="http://127.0.0.1:8788" target="_blank" rel="noreferrer">打开上传页</a>
          </div>
          <div class="action-card">
            <div><h3>配置知识库</h3><div class="muted">修改 vault、QMD、Mirage、Drive、模型和 Key。</div></div>
            <a class="btn" href="http://127.0.0.1:8789/setup" target="_blank" rel="noreferrer">打开配置页</a>
          </div>
          <div class="action-card">
            <div><h3>手动提取</h3><div class="muted">立即让 wiki ingest 处理 raw 目录。</div></div>
            <button class="btn" onclick="copyText('solar-harness wiki ingest --vault /Users/sihaoli/Knowledge')">复制命令</button>
          </div>
          <div class="action-card">
            <div><h3>语义索引</h3><div class="muted">更新 QMD semantic index，用于更好的检索。</div></div>
            <button class="btn" onclick="copyText('qmd embed -c solar-wiki')">复制命令</button>
          </div>
        </div>
      </div>

      <div class="health-grid">
        <div class="card"><h2>Obsidian Wiki 健康</h2><div id="wiki-card">Loading...</div></div>
        <div class="card"><h2>Mirage / QMD 健康</h2><div id="mirage-card">Loading...</div></div>
      </div>
    </div>
  </section>

  <section class="panel" id="tab-upload">
    <h2>上传文档 / 网页内容</h2>
    <div class="card">
      <p class="muted">这个标签对接现有 `wiki capture-server`。可粘贴网页内容保存为 Markdown，也可多选 PDF/图片/文本文件复制到 Knowledge/_raw，后续由知识库自动提取。</p>
      <div class="actions">
        <a class="btn primary" href="http://127.0.0.1:8788" target="_blank" rel="noreferrer">新窗口打开上传页</a>
        <button class="btn" onclick="copyText('solar-harness wiki capture-server start --open')">复制启动命令</button>
        <button class="btn" onclick="copyText('/Users/sihaoli/Knowledge/_raw')">复制 Raw 目录</button>
      </div>
      <iframe class="embed" src="http://127.0.0.1:8788" title="Solar Wiki Upload"></iframe>
    </div>
  </section>

  <section class="panel" id="tab-config">
    <h2>Solar 配置中心</h2>
    <div class="card">
      <p class="muted">统一修改模型、并发、Wiki、QMD、Mirage、Google Drive 和 API Key。敏感值只写入本机 secrets 文件，状态页不展示明文。</p>
      <div class="actions">
        <a class="btn primary" href="http://127.0.0.1:8789/setup" target="_blank" rel="noreferrer">打开配置中心</a>
        <button class="btn" onclick="copyText('solar-config-ui start --open')">复制启动命令</button>
      </div>
      <iframe class="embed" src="http://127.0.0.1:8789/setup" title="Solar Config UI"></iframe>
    </div>
  </section>

  <section class="panel" id="tab-integrations">
    <h2>外部集成健康</h2>
    <div class="card">
      <p class="muted">检查历史接入的开源/外部项目是否真的安装、配置、运行、索引并被 Solar 默认使用。这里不展示密钥，只展示可用性和断点原因。</p>
      <div class="actions">
        <button class="btn primary" onclick="refreshIntegrations(true)">刷新集成健康</button>
        <button class="btn" onclick="copyText('solar-harness integrations status --json --refresh')">复制诊断命令</button>
        <a class="btn" href="/integrations" target="_blank" rel="noreferrer">打开 JSON</a>
      </div>
    </div>
    <div class="card"><div id="integrations-summary">Loading...</div></div>
    <div id="integrations-card">Loading...</div>
  </section>

  <section class="panel" id="tab-diagrams">
    <h2>Mermaid 架构图</h2>
    <div class="card">
      <p class="muted">直接浏览 Solar 里的 .mmd 文件，并用本地 vendored Mermaid 渲染。默认入口会打开刚才生成的 Solar 完整架构图。</p>
      <div class="actions">
        <a class="btn primary" href="/mermaid" target="_blank" rel="noreferrer">打开 Mermaid Viewer</a>
        <a class="btn" href="/mermaid/view?file=/Users/sihaoli/.solar/harness/reports/solar-system-architecture-20260508.mmd" target="_blank" rel="noreferrer">打开 Solar 完整架构图</a>
        <button class="btn" onclick="copyText('http://127.0.0.1:8765/mermaid')">复制访问地址</button>
      </div>
      <iframe class="embed" src="/mermaid" title="Solar Mermaid Viewer"></iframe>
    </div>
  </section>

  <section class="panel" id="tab-raw">
    <h2>Raw /status JSON</h2>
    <pre class="codebox" id="raw-card">Loading...</pre>
  </section>
</main>

<script>
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}
function statusBadge(st) {
  const s = st || 'unknown';
  const cls = s === 'failed' || s === 'error' ? 'error-badge' : s === 'warn' ? 'warn-badge' : s;
  return '<span class="badge ' + esc(cls) + '">' + esc(s) + '</span>';
}
function sevClass(s) { return s === 'error' ? 'error' : s === 'warn' ? 'warn' : 'info'; }
function runtimeClass(s) { return s === 'active' ? 'info' : s === 'missing' ? 'error' : s === 'unknown' ? 'warn' : ''; }
function artifactLabel(a) {
  if (!a) return 'N/A';
  const st = a.state || 'N/A';
  if (a.mtime) {
    const d = new Date(a.mtime * 1000);
    return esc(st) + ' @ ' + esc(d.toLocaleTimeString());
  }
  return esc(st);
}
function clip(v, limit) {
  const s = String(v || '').replace(/\s+/g, ' ').trim();
  return s.length > limit ? s.slice(0, limit - 1).trim() + '…' : s;
}
function summaryList(text) {
  const s = String(text || '').replace(/\s+/g, ' ').trim();
  if (!s) return '';
  let parts = s
    .split(new RegExp('[。；;\\\\n]+'))
    .map(x => x.trim())
    .filter(Boolean);
  if (parts.length <= 1 && s.includes('、')) {
    parts = s.split('、').map(x => x.trim()).filter(Boolean);
  }
  if (parts.length <= 1 && s.includes('，')) {
    parts = s.split('，').map(x => x.trim()).filter(Boolean);
  }
  parts = parts.slice(0, 6).map(x => clip(x, 96));
  return '<ul class="summary-list">' + parts.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>';
}
function kv(label, value) {
  return '<div class="kv"><div class="kv-label">' + esc(label) + '</div><div class="kv-value">' + esc(value || '-') + '</div></div>';
}
function sprintBlock(meta, sid, options = {}) {
  meta = meta || {};
  const title = meta.title || sid || 'N/A';
  const status = meta.status ? statusBadge(meta.status) : '';
  const detailItems = options.compact ? [
    kv('Phase', meta.phase || '-'),
    kv('Handoff', meta.handoff_to || '-')
  ] : [
    kv('Phase', meta.phase || '-'),
    kv('Handoff', meta.handoff_to || '-'),
    kv('Lane', meta.lane || '-'),
    kv('Priority', meta.priority || '-')
  ];
  const details = detailItems.join('');
  const id = sid ? '<div class="tech-id">id: ' + esc(sid) + '</div>' : '';
  return '<div class="task-block">' +
    '<div class="task-head"><div class="task-title">' + esc(title) + '</div><div>' + status + '</div></div>' +
    '<div class="kv-grid">' + details + '</div>' +
    (options.hideDescription ? '' : summaryList(meta.description || '')) +
    (options.hideId ? '' : id) +
    '</div>';
}
function taskCell(meta, sid) {
  return sprintBlock(meta, sid, {compact: true, hideDescription: true});
}
function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {});
}
function renderPaneMatrix(cardId, screen) {
  const panes = (screen && screen.panes) || [];
  if (!panes.length) {
    document.getElementById(cardId).textContent = 'No panes found.';
    return;
  }
  let t = '<div class="refresh">' + esc((screen && screen.note) || '') + '</div>';
  t += '<table><tr><th>Pane</th><th>Role</th><th>Runtime</th><th>当前任务</th><th>Artifact</th><th>Title</th></tr>';
  panes.forEach(p => {
    t += '<tr><td>' + esc(p.target || '-') + '</td>' +
         '<td>' + esc(p.role || '-') + '</td>' +
         '<td class="' + runtimeClass(p.runtime_state) + '">' + esc(p.runtime_state || '-') + '</td>' +
         '<td>' + taskCell(p.assignment_meta, p.assignment) + '</td>' +
         '<td>' + artifactLabel(p.artifact) + '</td>' +
         '<td>' + esc(p.title || '-') + '</td></tr>';
  });
  t += '</table>';
  document.getElementById(cardId).innerHTML = t;
}
function renderList(obj) {
  if (!obj || typeof obj !== 'object') return '<div class="muted">N/A</div>';
  return '<table>' + Object.entries(obj).map(([k, v]) =>
    '<tr><th>' + esc(k) + '</th><td>' + esc(typeof v === 'object' ? JSON.stringify(v) : v) + '</td></tr>'
  ).join('') + '</table>';
}
function qmdDetail(qmd) {
  const d = (qmd && qmd.detail) || {};
  return {
    status: (qmd && qmd.status) || 'unknown',
    binary: (qmd && qmd.binary) || '',
    total: d.total || 'N/A',
    vectors: d.vectors || 'N/A',
    pending: d.pending || 'N/A',
    collection: d.collection || 'N/A'
  };
}
function renderMirageHealth(mirage) {
  mirage = mirage || {};
  const q = qmdDetail(mirage.qmd || {});
  const mounts = mirage.mounts || [];
  const ready = mounts.filter(m => m.ready).length;
  const drive = mirage.drive || {};
  const mountRows = mounts.map(m => {
    const state = m.ready ? 'ok' : (m.optional ? 'warn' : 'error');
    const reason = m.reason || m.status || m.adapter || m.physical_root || '';
    return '<div class="mount-row">' +
      '<div class="mount-path">' + esc(m.path || '-') + '</div>' +
      '<div>' + statusBadge(state) + '</div>' +
      '<div class="mount-reason">' + esc(reason || 'ready') + '</div>' +
      '</div>';
  }).join('');
  return '<div class="health-metrics">' +
    '<div class="mini-metric"><div class="kv-label">QMD</div><span class="num">' + esc(q.status) + '</span></div>' +
    '<div class="mini-metric"><div class="kv-label">Indexed</div><span class="num">' + esc(q.total) + '</span></div>' +
    '<div class="mini-metric"><div class="kv-label">Vectors</div><span class="num">' + esc(q.vectors) + '</span></div>' +
    '<div class="mini-metric"><div class="kv-label">Pending</div><span class="num">' + esc(q.pending) + '</span></div>' +
    '<div class="mini-metric"><div class="kv-label">Mounts</div><span class="num">' + ready + '/' + mounts.length + '</span></div>' +
    '<div class="mini-metric"><div class="kv-label">Drive</div><span class="num">' + esc(drive.status || 'unknown') + '</span></div>' +
    '</div>' +
    '<h3>Mounts</h3><div class="mount-list">' + mountRows + '</div>' +
    '<details style="margin-top:0.85rem"><summary class="muted">查看原始 Mirage JSON</summary><pre class="codebox">' + esc(JSON.stringify(mirage, null, 2)) + '</pre></details>';
}
function renderKnowledgeSummary(wiki, mirage) {
  const wikiReady = !!(wiki && wiki.ready);
  const mirageReady = !!(mirage && mirage.enabled);
  const qmdStatus = mirage && mirage.qmd && mirage.qmd.status ? mirage.qmd.status : 'unknown';
  const vault = (wiki && wiki.vault_path) || '/Users/sihaoli/Knowledge';
  return [
    '<div class="status-tile"><div class="kv-label">Wiki</div><strong>' + statusBadge(wikiReady ? 'ok' : 'warn') + '</strong></div>',
    '<div class="status-tile"><div class="kv-label">Mirage</div><strong>' + statusBadge(mirageReady ? 'ok' : 'warn') + '</strong></div>',
    '<div class="status-tile"><div class="kv-label">QMD</div><strong>' + esc(qmdStatus) + '</strong></div>',
    '<div class="status-tile"><div class="kv-label">Vault</div><strong class="path-text">' + esc(vault) + '</strong></div>'
  ].join('');
}
function statePill(label, ok) {
  return '<div class="state-pill ' + (ok ? 'ok' : 'warn') + '">' + esc(label) + '<br>' + (ok ? '✓' : '×') + '</div>';
}
function evidenceSummary(item) {
  const ev = item.evidence || {};
  const upload = ev.latest_upload_audit || {};
  if (upload.batch && upload.data) {
    const d = upload.data || {};
    const q = d.qmd || {};
    const v = d.vault || {};
    const s = d.solar_db || {};
    return 'upload ' + upload.batch + ' · QMD ' + (q.title_hits || 0) + '/' + (d.total || 0) +
      ' · Vault ' + (v.hits || 0) + '/' + (d.total || 0) +
      ' · Solar DB ' + (s.hits || 0) + '/' + (d.total || 0);
  }
  if (upload.batch && upload.mode === 'fast_metadata') {
    return 'latest upload ' + upload.batch + ' · files ' + (upload.total_files || 0) + ' · deep audit skipped for dashboard speed';
  }
  if (ev.qmd_stats) {
    const qmd = ev.qmd_stats || {};
    return 'QMD indexed ' + (qmd.total || 0) + ' · pending ' + (qmd.pending || 0) + ' · vectors ' + (qmd.vectors || 0);
  }
  if (ev.total || ev.vectors || ev.pending !== undefined) {
    return 'QMD indexed ' + (ev.total || 0) + ' · vectors ' + (ev.vectors || 0) + ' · pending ' + (ev.pending || 0);
  }
  if (ev.dispatch_backlog) {
    const b = ev.dispatch_backlog || {};
    return 'dispatch backlog unresolved ' + (b.unresolved || 0) + '/' + (b.total || 0);
  }
  if (ev.command) return 'command: ' + ev.command;
  if (ev.version) return 'version: ' + ev.version;
  if (ev.mounts) return 'mounts: ' + ev.mounts;
  return item.degraded_reason || item.status || 'N/A';
}
function renderIntegrations(data) {
  const summaryEl = document.getElementById('integrations-summary');
  const cardEl = document.getElementById('integrations-card');
  if (!summaryEl || !cardEl) return;
  if (!data || data.error) {
    summaryEl.innerHTML = statusBadge('error') + ' ' + esc((data && data.error) || 'integrations probe failed');
    cardEl.innerHTML = '<div class="card"><pre class="codebox">' + esc(JSON.stringify(data || {}, null, 2)) + '</pre></div>';
    return;
  }
  const summary = data.summary || {};
  const items = data.integrations || [];
  summaryEl.innerHTML =
    '<div class="integration-summary">' +
      '<div class="status-tile"><div class="kv-label">Total</div><strong>' + esc(summary.total || items.length || 0) + '</strong></div>' +
      '<div class="status-tile"><div class="kv-label">OK</div><strong>' + esc(summary.ok || 0) + '</strong></div>' +
      '<div class="status-tile"><div class="kv-label">Warn</div><strong>' + esc(summary.warn || 0) + '</strong></div>' +
      '<div class="status-tile"><div class="kv-label">Error</div><strong>' + esc(summary.error || 0) + '</strong></div>' +
      '<div class="status-tile"><div class="kv-label">Missing</div><strong>' + esc(summary.missing || 0) + '</strong></div>' +
      '<div class="status-tile"><div class="kv-label">断头</div><strong>' + esc(summary.dead_ends || 0) + '</strong></div>' +
    '</div>' +
    '<div class="muted">缓存：' + (data.cache && data.cache.hit ? '命中' : '刷新') +
    ' · 探测时间：' + esc(data.generated_at || 'N/A') + '</div>';
  if (!items.length) {
    cardEl.innerHTML = '<div class="card muted">没有集成探测结果。</div>';
    return;
  }
  cardEl.innerHTML = '<div class="integration-grid">' + items.map(item => {
    return '<article class="integration-card">' +
      '<div class="integration-head"><div><div class="integration-name">' + esc(item.name || item.id || 'N/A') +
      '</div><div class="muted">' + esc(item.purpose || item.source || '') + '</div></div>' +
      '<div>' + statusBadge(item.status || 'unknown') + '</div></div>' +
      '<div class="state-row">' +
        statePill('安装', !!item.installed) +
        statePill('配置', !!item.configured) +
        statePill('运行', !!item.running) +
        statePill('索引', !!item.indexed) +
        statePill('默认', !!item.used_by_default) +
      '</div>' +
      '<div class="state-row">' +
        statePill('基础可用', item.health && item.health.basic_available !== 'error') +
        statePill('默认可用', item.health && item.health.default_available === 'ok') +
        statePill('完整闭环', item.health && item.health.complete_closed_loop === 'ok') +
        statePill('无断头', item.health && item.health.dead_ends === 'ok') +
      '</div>' +
      '<div class="integration-reason">' + esc(item.degraded_reason || '可用') + '</div>' +
      (item.dead_ends && item.dead_ends.length ? '<div class="integration-reason warn">断头：' + esc(item.dead_ends.join(', ')) + '</div>' : '') +
      '<div class="muted" style="margin-top:.7rem">' + esc(evidenceSummary(item)) + '</div>' +
      '<details style="margin-top:.8rem"><summary class="muted">证据</summary><pre class="codebox">' +
      esc(JSON.stringify(item.evidence || {}, null, 2)) + '</pre></details>' +
    '</article>';
  }).join('') + '</div>';
}
function refreshIntegrations(force) {
  const summaryEl = document.getElementById('integrations-summary');
  const cardEl = document.getElementById('integrations-card');
  if (summaryEl) summaryEl.textContent = force ? 'Refreshing...' : 'Loading...';
  if (cardEl) cardEl.textContent = 'Loading...';
  const url = '/integrations' + (force ? '?refresh=1' : '');
  fetch(url).then(r => r.json()).then(renderIntegrations).catch(err => {
    renderIntegrations({error: String(err)});
  });
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === btn));
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
    if (tab === 'integrations') refreshIntegrations(false);
  });
});

function render(data) {
  const now = new Date().toISOString();
  document.getElementById('refresh-ts').textContent = 'Last updated: ' + now;

  const sp = data.current_sprint || {};
  if (sp.sprint_id) {
    const sprintHtml = sprintBlock({
      title: sp.title || sp.sprint_id,
      status: sp.status,
      phase: sp.phase || '-',
      handoff_to: sp.handoff_to || '-',
      lane: sp.lane || '-',
      priority: sp.priority || '-',
      description: sp.description || ''
    }, sp.sprint_id);
    document.getElementById('sprint-card').innerHTML = sprintHtml;
    document.getElementById('overview-sprint').innerHTML = sprintHtml;
  } else {
    document.getElementById('sprint-card').textContent = 'No active sprint.';
    document.getElementById('overview-sprint').textContent = 'No active sprint.';
  }

  const panes = data.panes || [];
  const assignedMainPanes = ((data.main_screen || {}).panes || []).filter(p => p.assignment);
  if (assignedMainPanes.length) {
    let t = '<table><tr><th>Pane</th><th>角色</th><th>运行</th><th>当前任务</th><th>产物</th></tr>';
    assignedMainPanes.forEach(p => {
      t += '<tr><td>' + esc(p.target || '-') + '</td><td>' + esc(p.role || '-') + '</td>' +
           '<td class="' + runtimeClass(p.runtime_state) + '">' + esc(p.runtime_state || '-') + '</td>' +
           '<td>' + taskCell(p.assignment_meta || {}, p.assignment || '-') + '</td>' +
           '<td>' + artifactLabel(p.artifact) + '</td></tr>';
    });
    t += '</table>';
    document.getElementById('panes-card').innerHTML = t;
    document.getElementById('overview-panes').innerHTML = '<div class="metric">' + assignedMainPanes.length + '</div><div class="muted">assigned panes</div>';
  } else if (panes.length) {
    let t = '<table><tr><th>Pane</th><th>当前任务</th><th>状态</th><th>阶段</th></tr>';
    panes.forEach(p => {
      const meta = p.sprint || {};
      t += '<tr><td>' + esc(p.pane) + '</td><td>' + taskCell(meta, p.sprint_id || '-') + '</td>' +
           '<td>' + statusBadge(meta.status || 'unknown') + '</td><td>' + esc(meta.phase || '-') + '</td></tr>';
    });
    t += '</table>';
    document.getElementById('panes-card').innerHTML = t;
    document.getElementById('overview-panes').innerHTML = '<div class="metric">' + panes.length + '</div><div class="muted">assigned panes</div>';
  } else {
    document.getElementById('panes-card').textContent = 'No pane assignments.';
    document.getElementById('overview-panes').innerHTML = '<div class="metric">0</div><div class="muted">assigned panes</div>';
  }

  renderPaneMatrix('main-screen-card', data.main_screen);
  renderPaneMatrix('lab-screen-card', data.lab_screen);

  const evts = data.recent_events || [];
  if (evts.length) {
    let t = '<table><tr><th>Time</th><th>Sev</th><th>Actor</th><th>Event</th><th>Sprint</th></tr>';
    evts.slice().reverse().forEach(e => {
      const ts = (e.ts || '').substring(11, 19);
      t += '<tr><td>' + esc(ts) + '</td><td class="' + sevClass(e.severity) + '">' + esc(e.severity || '?') +
           '</td><td>' + esc(e.actor || '?') + '</td><td>' + esc(e.event || '?') +
           '</td><td>' + esc(e.sprint_id || '-') + '</td></tr>';
    });
    t += '</table>';
    document.getElementById('events-card').innerHTML = t;
  } else {
    document.getElementById('events-card').textContent = 'No events yet.';
  }
  const risky = evts.slice().reverse().filter(e => e.severity === 'warn' || e.severity === 'error').slice(0, 4);
  if (risky.length) {
    document.getElementById('overview-risk').innerHTML =
      '<ul class="summary-list">' + risky.map(e => '<li>' +
      esc((e.ts || '').substring(11, 19)) + ' · ' + esc(e.severity || '?') + ' · ' +
      esc(e.actor || '?') + ' · ' + esc(e.event || '?') + '</li>').join('') + '</ul>';
  } else {
    document.getElementById('overview-risk').innerHTML = '<div class="muted">最近 50 条事件没有 warn/error。</div>';
  }

  const kpi = data.kpi || {};
  const kpiHtml =
    'Total: <b>' + (kpi.sprints_total||0) + '</b> &nbsp; ' +
    'Passed: <b>' + (kpi.sprints_passed||0) + '</b> &nbsp; ' +
    'Failed: <b>' + (kpi.sprints_failed||0) + '</b> &nbsp; ' +
    'Pass rate: <b>' + ((kpi.pass_rate||0)*100).toFixed(0) + '%</b>';
  document.getElementById('overview-kpi').innerHTML = kpiHtml;

  const wiki = data.obsidian_wiki || {};
  const mirage = data.mirage || {};
  document.getElementById('knowledge-summary').innerHTML = renderKnowledgeSummary(wiki, mirage);
  document.getElementById('wiki-card').innerHTML = renderList(wiki);
  document.getElementById('mirage-card').innerHTML = renderMirageHealth(mirage);
  document.getElementById('overview-knowledge').innerHTML =
    'Wiki: ' + statusBadge(wiki.ready ? 'ok' : 'warn') + '<br>' +
    'Mirage: ' + statusBadge(mirage.ready ? 'ok' : (mirage.status || 'warn'));

  document.getElementById('raw-card').textContent = JSON.stringify(data, null, 2);
}

function refresh() {
  fetch('/status')
    .then(r => r.json())
    .then(render)
    .catch(e => console.warn('refresh error', e));
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


class StatusHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress access log noise

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json({"error": "not found"}, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        if path == "/healthz":
            self._send_text("ok")

        elif path == "/status":
            self._send_json(_status_payload(limit=50))

        elif path == "/events":
            sprint_id = params.get("sprint_id", [""])[0]
            try:
                limit = int(params.get("limit", ["50"])[0])
                limit = max(1, min(limit, 500))
            except ValueError:
                limit = 50
            if sprint_id:
                src = SPRINTS_DIR / f"{sprint_id}.events.jsonl"
            else:
                src = ALL_EVENTS
            events = _read_jsonl(src, limit=limit, sprint_id="")
            self._send_json(events)

        elif path == "/integrations":
            refresh = params.get("refresh", ["0"])[0].lower() in ("1", "true", "yes")
            self._send_json(_external_integrations_payload(refresh=refresh))

        elif path == "/integrations-view":
            self._send_text(_integrations_view_html(), content_type="text/html; charset=utf-8")

        elif path == "/mermaid":
            self._send_text(_mermaid_index_html(), content_type="text/html; charset=utf-8")

        elif path == "/mermaid/list":
            self._send_json({"files": _list_mmd_files(), "roots": [str(root) for root in MMD_ALLOWED_ROOTS]})

        elif path == "/mermaid/view":
            mmd = _resolve_mmd_file(params.get("file", [""])[0])
            if not mmd:
                self._send_json({"error": "mmd not found or not allowed"}, status=404)
            else:
                self._send_text(_mermaid_view_html(mmd), content_type="text/html; charset=utf-8")

        elif path == "/mermaid/raw":
            mmd = _resolve_mmd_file(params.get("file", [""])[0])
            if not mmd:
                self._send_json({"error": "mmd not found or not allowed"}, status=404)
            else:
                self._send_text(mmd.read_text(errors="ignore"), content_type="text/plain; charset=utf-8")

        elif path.startswith("/mermaid/assets/"):
            asset = _asset_path(path.removeprefix("/mermaid/assets/"))
            if not asset:
                self._send_json({"error": "asset not found"}, status=404)
            else:
                ctype = "application/javascript; charset=utf-8"
                if asset.suffix == ".map":
                    ctype = "application/json; charset=utf-8"
                elif asset.suffix == ".css":
                    ctype = "text/css; charset=utf-8"
                self._send_file(asset, ctype)

        elif path == "/api/capability":
            # Pane capability summary — skills, mcp_mode, kb_context per pane
            self._send_json(_pane_capability_summary())

        elif path == "/":
            # _HTML_TEMPLATE is not formatted with str.format(), so collapse the
            # doubled braces used by earlier template-style escaping.
            self._send_text(_HTML_TEMPLATE.replace("{{", "{").replace("}}", "}"), content_type="text/html; charset=utf-8")

        else:
            self._send_json({"error": "not found"}, status=404)


def _find_port() -> int:
    import socket
    for port in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((BIND_HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available port in range 8765-8775")


def main():
    port = _find_port()
    server = ThreadingHTTPServer((BIND_HOST, port), StatusHandler)
    server.daemon_threads = True
    # Write port to pidfile directory so clients can discover it
    pid_dir = HARNESS_DIR / "run"
    pid_dir.mkdir(parents=True, exist_ok=True)
    (pid_dir / "status-server.port").write_text(str(port))
    print(f"Solar Harness status server listening on http://{BIND_HOST}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        (pid_dir / "status-server.port").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
