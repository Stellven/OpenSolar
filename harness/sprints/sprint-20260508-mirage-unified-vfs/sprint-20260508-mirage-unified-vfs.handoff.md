# Handoff — sprint-20260508-mirage-unified-vfs
Builder: 建设者化身 (Claude Sonnet 4.6)
Round: 1

## Summary

Full sprint implementation complete. All 8 acceptance criteria (A1–A8) pass.  
Test suite: **33/33 PASS** (`bash tests/test-mirage-unified-vfs.sh`).

## Changed Files

| File | Status | Description |
|------|--------|-------------|
| `config/mirage.solar.yaml` | NEW | Workspace manifest: 8 mounts, policy, redact patterns |
| `lib/solar_mirage.py` | NEW (~650 lines) | doctor, workspace, mounts, exec, provision, install, search routing |
| `lib/mirage_search.py` | NEW (~495 lines) | Unified search: mirage_path + qmd + solar_db adapters |
| `lib/mirage_events.py` | NEW (~130 lines) | Standalone event writer with 6 event types + CLI |
| `lib/symphony/status-server.py` | EDIT | Added `_mirage_status()` + `"mirage"` key in `_status_payload()` |
| `solar-harness.sh` | EDIT | Added `mirage)` case routing to solar_mirage.py / mirage_search.py |
| `tests/test-mirage-unified-vfs.sh` | NEW | Full A1–A8 test suite (33 checks) |
| `docs/mirage-unified-vfs.md` | NEW | Install, manifest, CLI reference, write policy, security notes |
| `state/mirage/` | CREATED | last-probe.json, events.jsonl, solar-default.json |

## Done 定义达成

### A1 — doctor --json
✅ `python3 lib/solar_mirage.py doctor --json` returns `enabled=true`, `config=...mirage.solar.yaml`, `drive.status=degraded` (no credentials).  
✅ Caches to `state/mirage/last-probe.json` for status-server.  
Evidence: A1.1–A1.5 all PASS.

### A2 — workspace + mounts
✅ `workspace create --id solar-default` writes `state/mirage/solar-default.json` and creates `/raw` physical dir.  
✅ `mounts --json` returns all 8 mounts; required set {/knowledge, /raw, /sprints, /solar, /cortex} ⊆ result.  
Evidence: A2.1–A2.3 all PASS.

### A3 — exec read-only paths
✅ `exec -- 'find /sprints -name "*.md" | head'` rewrites `/sprints` → physical path, runs, returns stdout.  
✅ `exec -- 'ls /solar'` works without error.  
✅ `exec --json` returns `{stdout, stderr, exit_code, duration_ms, cmd, truncated}`.  
Evidence: A3.1–A3.4 all PASS.

### A4 — unified search
✅ `mirage_search.py "query" --json` returns `{hits, degraded_sources, elapsed_ms, query}`.  
✅ Three adapters: mirage_path (rg/grep over disk mounts), qmd (virtual), solar_db (solar-knowledge-context.py).  
✅ Dedup by path+snippet, sorted by score_or_rank, enforces hit+char budget.  
Evidence: A4.1–A4.3 all PASS.

### A5 — drive write denied
✅ `exec -- 'ls /knowledge'` → allowed (exit 0).  
✅ `exec -- 'echo test > /drive/...'` → denied (exit non-0, error message).  
Evidence: A5.1–A5.2 PASS.

### A6 — write boundary enforcement
✅ `exec -- 'echo "..." > /raw/file.md'` → allowed (only rw mount).  
✅ `exec -- 'echo bad > /solar/...'` → denied with exit 1.  
✅ `exec -- 'echo bad > /cortex/...'` → denied with exit 1.  
✅ `mirage_write_denied` event in `sprints/warn.events.jsonl`.  
Evidence: A6.1–A6.4 all PASS.

### A7 — /status endpoint mirage section
✅ `_mirage_status()` defined in `lib/symphony/status-server.py`.  
✅ `"mirage": _mirage_status()` in `_status_payload()`.  
✅ `curl http://127.0.0.1:8765/status | python3 -c '...; assert "mounts" in m and "drive" in m and "qmd" in m'` PASS.  
✅ Reads from `last-probe.json` (fail-open, no SDK, no network).  
Evidence: A7.1–A7.4 all PASS.

### A8 — mirage_events.py
✅ `lib/mirage_events.py` exists with 6 event type wrappers + CLI.  
✅ Warn-level events auto-routed to `sprints/warn.events.jsonl`.  
✅ `python3 lib/mirage_events.py mirage_write_denied` → `severity=warn`.  
Evidence: A8.1–A8.4 all PASS.

## 验证方法

```bash
# Full test suite (33 checks, ~30s)
cd ~/.solar/harness
bash tests/test-mirage-unified-vfs.sh

# Quick smoke test
solar-harness mirage doctor
solar-harness mirage mounts --json
solar-harness mirage exec -- 'find /knowledge -name "*.md" | head -3'
solar-harness mirage search "sprint" --max-hits 5

# Status server live check
curl -fsS http://127.0.0.1:8765/status | python3 -c \
  'import json,sys; d=json.load(sys.stdin); m=d["mirage"]; print("mirage:", list(m.keys()))'
```

## 备注

1. **Mirage SDK not installed**: Operates in degraded mode — all local VFS commands work, drive requires SDK.
2. **Python 3.9 compat**: Uses `from __future__ import annotations` throughout; all files tested with system Python 3.9.6.
3. **exec --json flag**: Added to exec subparser (was missing from S1 argparse, now fixed).
4. **Status server restarted**: Required to pick up mirage section changes; `solar-harness status-server restart` used during verification.
5. **Write boundary for shell redirects**: Detected via `>|>>|tee` pattern in cmd string before execution; redirect target path is resolved through the mount table.
6. **qmd adapter**: Probed as `solar-harness wiki qmd-search`; shows `status=missing` if binary not on PATH — graceful degradation.
