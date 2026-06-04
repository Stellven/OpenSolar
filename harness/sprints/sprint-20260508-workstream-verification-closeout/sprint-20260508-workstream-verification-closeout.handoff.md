# Handoff — sprint-20260508-workstream-verification-closeout
Builder: 建设者化身 (Claude Sonnet 4.6)
Round: 1

## Summary

Full workstream verification complete. All 10 acceptance criteria are either PASS or explicitly WARN with documented owner and fix dispatch. Key deliverables: `verify-workstream-ledger.py` (A1), Solar KB autouse eval (A5, verdict=FAIL with 3 targeted fix items), Mirage VFS S3 completion (A6), status-server synthetic event filtering (A4), and full workstream matrix report.

## Changed Files

| File | Status | Description |
|------|--------|-------------|
| `tools/verify-workstream-ledger.py` | NEW | Sprint ledger truth checker (A1) — scans sprint-2026050[78]-*.status.json, checks artifact vs declared status |
| `sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.md` | NEW | Solar KB autouse evaluation — FAIL (3 PASS / 2 FAIL / 2 WARN) |
| `sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.json` | NEW | Machine-readable companion eval |
| `lib/symphony/status-server.py` | EDIT | Added `_mirage_status()` + `"mirage"` key; added synthetic event filtering (F4) — `_SYNTHETIC_SID_PREFIXES`, `_is_synthetic_event()`, `filter_synthetic=True` in recent_events |
| `lib/mirage_events.py` | NEW | Standalone event writer, 6 event types, warn-level routing to warn.events.jsonl, CLI |
| `lib/solar_mirage.py` | EDIT | Added `--json` and `--allow-write-projects` flags to exec subparser |
| `tests/test-mirage-unified-vfs.sh` | NEW | Full A1–A8 test suite (33 checks) |
| `docs/mirage-unified-vfs.md` | NEW | Install, manifest, CLI reference, write policy, security notes |
| `sprints/sprint-20260508-mirage-unified-vfs.handoff.md` | NEW | Full mirage VFS sprint handoff (33/33 PASS) |

## Done 定义达成

### A1 — Sprint Ledger Truth
✅ `tools/verify-workstream-ledger.py --json` created and verified:
```
python3 tools/verify-workstream-ledger.py --json | python3 -c '...; assert "sprints" in d and d["summary"]["checked"] >= 8'
# → 12 sprints checked, 7 ok, 4 warn, 0 error — PASS
```

### A2 — Obsidian Wiki Integration Still Works
✅ Wiki configured, vault_path=/Users/lisihao/Knowledge, 1131 files indexed, 1928 vectors embedded
```
solar-harness wiki status --json → configured=True, vault_path="/Users/lisihao/Knowledge"
solar-harness wiki qmd-search "Solar Harness Obsidian" -n 2 --json → 2 hits
```

### A3 — QMD/MinerU Is Indexed And Its Limitation Is Explicit
✅ PASS with note: 1131 files, 1928 vectors (vectors are now > 0, not the 0 shown in contract snapshot)
```
qmd status → solar-wiki: Total 1131 files, Vectors 1928
curl http://localhost:8181/health → OK
```

### A4 — Status Server And Recent Events Are Honest
✅ Status server at 8765 healthy, synthetic event filtering added:
- `_SYNTHETIC_SID_PREFIXES` tuple covers 6 test-hook prefixes
- `_is_synthetic_event()` helper + `filter_synthetic=True` in recent_events
- `/status` returns `current_sprint` and `main_screen` keys
```
curl http://127.0.0.1:8765/healthz → OK
curl http://127.0.0.1:8765/status | python3 -c '...; assert "current_sprint" in d and "main_screen" in d' → PASS
```

### A5 — Solar KB Autouse P0 Gets Real Evaluation
✅ Both eval files created:
- `eval.md`: FAIL verdict, 3 PASS / 2 FAIL / 2 WARN, A2 (vault not indexed) and A5 (port conflict) failed
- `eval.json`: machine-readable, failures=["A2","A5"], warnings=["A7"], 3 required fixes documented
```
test -s sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.md → OK
test -s sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.json → OK
```

### A6 — Mirage VFS Does Not Fake Progress
✅ Both handoff files present, doctor returns degraded (no SDK = expected):
```
test -s sprints/sprint-20260508-mirage-unified-vfs.handoff-s1.md → OK
test -s sprints/sprint-20260508-mirage-unified-vfs.handoff-s2.md → OK
solar-harness mirage doctor --json → drive.status=degraded (no Mirage SDK — acceptable)
```

### A7 — Accepted Artifact Knowledge Is Either Implemented Or Properly Blocked
✅ Sprint is queued pending KB P0 pass; contract and status.json both present:
```
test -s sprints/sprint-20260508-accepted-artifact-knowledge.contract.md → OK
python3 -m json.tool sprints/sprint-20260508-accepted-artifact-knowledge.status.json → OK
```
KB P0 (solar-kb-obsidian-autouse) evaluated as FAIL → accepted-artifact-knowledge stays queued with documented blocker.

### A8 — Capture Server And Auto Ingest Are Verified
⚠️ WARN: capture server stopped (was last on 8788), but `_raw` dir exists
```
solar-harness wiki capture-server status → status=stopped, url=http://127.0.0.1:8788
test -d /Users/lisihao/Knowledge/_raw → OK
```
Documented in fix-dispatch.md as owner=user, fix=`solar-harness wiki capture-server start`.

### A9 — Pane Orchestration And Model Routing Are Stable Enough
✅ Both tmux sessions have active panes:
```
tmux list-panes -t solar-harness:0 → 4 panes (0-3)
tmux list-panes -t solar-harness-lab:0 → 4 panes (0-3)
```
GLM API 400 incident documented in fix-dispatch.md: default to Sonnet/DeepSeek for builder panes.

### A10 — Fix Dispatch Is Minimal And Safe
✅ `fix-dispatch.md` present with Owner, Write Scope, Verify, Rollback sections:
```
test -s sprints/sprint-20260508-workstream-verification-closeout.fix-dispatch.md → OK
rg -n "Owner|Write Scope|Verify|Rollback" → found in fix-dispatch.md
```

## Architecture

```
verify-workstream-ledger.py
  → scans sprints/sprint-2026050[78]-*.status.json
  → checks artifact presence vs declared status
  → returns {sprints: [...], summary: {checked, ok, warn, error}}

status-server.py (additions)
  → _SYNTHETIC_SID_PREFIXES: 6 test-hook prefixes
  → _is_synthetic_event(): checks sprint_id prefix
  → _read_jsonl(..., filter_synthetic=True): skips test events in recent_events
  → _mirage_status(): reads state/mirage/last-probe.json, TTL 120s, fail-open
  → _status_payload(): includes "mirage" and filtered "recent_events"
```

## Verification Evidence

```bash
# A1
python3 tools/verify-workstream-ledger.py --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "sprints" in d and d["summary"]["checked"] >= 8'
# → PASS (12 checked)

# A4
curl -fsS http://127.0.0.1:8765/healthz >/dev/null
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "current_sprint" in d and "main_screen" in d'
# → PASS

# A5
test -s sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.md && \
test -s sprints/sprint-20260508-solar-kb-obsidian-autouse.eval.json
# → PASS

# A6
test -s sprints/sprint-20260508-mirage-unified-vfs.handoff-s1.md && \
test -s sprints/sprint-20260508-mirage-unified-vfs.handoff-s2.md && \
solar-harness mirage doctor --json | python3 -c \
  'import json,sys; d=json.load(sys.stdin); assert "drive" in d and d["drive"]["status"] in ("ok","warn","degraded","disabled")'
# → PASS (degraded is acceptable without Mirage SDK)
```

## Known Risks

1. **Solar KB autouse is FAIL** — obsidian_vault_index never populated, capture-server port conflict unresolved. Fix dispatch generated: F-A2a (fix `local` syntax in solar-harness.sh), F-A2b (run initial sync), F-A5 (add `_solar_kb_status()` to status-server).

2. **Capture server stopped** — `_raw` dir exists but no auto-ingest daemon running. User must `solar-harness wiki capture-server start` or configure LaunchAgent.

3. **Mirage SDK not installed** — doctor reports degraded; all local VFS commands work, Google Drive integration unavailable until SDK installed.

## Not Done

- QMD vector embedding status: now shows 1928 vectors (contract snapshot said 0, that is outdated)
- Accepted artifact knowledge sprint: correctly blocked behind KB P0; no action needed until KB P0 passes
- LaunchAgent for capture server auto-start: not implemented; documented as user action in fix-dispatch
