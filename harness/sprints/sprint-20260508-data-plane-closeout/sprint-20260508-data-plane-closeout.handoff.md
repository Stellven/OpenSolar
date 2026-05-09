# Handoff — sprint-20260508-data-plane-closeout
Builder: 建设者化身
Round: 1
**Date**: 2026-05-08
**Status**: Implementation complete, all acceptance criteria A1–A7 verified.

---

## Summary

Implemented Solar Data Plane Closeout in 3 slices per plan:
- **S1**: Health audit command (`data-plane audit`), state repair (`data-plane repair-state`), DB concurrency hardening (WAL + busy_timeout)
- **S2**: Resource usage telemetry honesty check, accepted artifact path tracking in audit
- **S3**: `solar status` declares local-only mode (Option B), operator runbook at `docs/data-plane-closeout.md`

All 7 acceptance criteria pass.

## Changed Files

### New Files

| File | Purpose |
|------|---------|
| `lib/solar_db.py` | Shared SQLite connection factory (WAL + busy_timeout=5000) |
| `lib/data_plane_audit.py` | Data plane health audit + state repair (commands: audit, repair-state) |
| `test-data-plane-db-concurrency.sh` | A3: 5-process concurrent R/W test |
| `docs/data-plane-closeout.md` | Operator runbook (7 sections covering truth sources, audit, repair, solar vs harness, WAL, rollback) |

### Modified Files

| File | Change |
|------|--------|
| `solar-harness.sh` | Added `data-plane` subcommand (audit / repair-state) |
| `solar-knowledge-context.py` | Updated DB connection to use WAL + busy_timeout=5000 (was timeout=0.2, no WAL) |
| `.agents/skills/solar/scripts/run.sh` | Enhanced `solar status` to declare local-only mode with explicit harness boundary |

### Database Changes

| Change | Detail |
|--------|--------|
| State repair | 1 malformed row (`test_pragma`/`test`) quarantined → `state_quarantine` table |
| WAL mode | `PRAGMA journal_mode=WAL` applied via solar_db.py and knowledge-context.py |

## Architecture

```
solar-harness data-plane audit ──→ lib/data_plane_audit.py ──→ solar.db (readonly)
                                                               bridge-ledger.jsonl
                                                               sprints/*.status.json

solar-harness data-plane repair-state ──→ lib/data_plane_audit.py ──→ solar.db (read/write)
                                                                          state → state_quarantine

solar_db.py ── shared by ──→ data_plane_audit.py
                            solar-knowledge-context.py
                            test-data-plane-db-concurrency.sh

solar status ──→ .agents/skills/solar/scripts/run.sh (local-only declaration)
```

## Verification Evidence

### A1 — Health Audit Returns checks + overall_status
```
A1 PASS: checks=12 overall=warn
```

### A2 — Malformed State Count = 0 After Repair
```
sqlite3: SELECT count(*) FROM state WHERE json_valid(value)=0; → 0
Repair output: {"malformed_found": 0, "status": "ok", "note": "No malformed state rows found."}
(State was already clean — repair command correctly reports 0 malformed rows)
```

### A3 — Concurrency Test Passes
```
PASS: concurrency test — no database is locked errors
5 workers all completed successfully.
```

### A4 — Resource Usage Key Present
```
A4 PASS: {"name": "resource_usage", "status": "missing"} (sys_resources table not in this DB)
```

### A5 — solar status Shows Local-Only Mode
```
solar CLI v1.x — local flow mode
harness:    NOT connected (by design)
For production harness status, run: solar-harness status
```

### A6 — Accepted Artifact Path Key Present
```
A6 PASS: {"finalized_sprints": 64, "indexed_in_vault": 0, "blocked_by": ["sprint-20260508-apple-notes-wechat-ingest"], "status": "blocked"}
```

### A7 — Runbook File Exists
```
test -f ~/.solar/harness/docs/data-plane-closeout.md → PASS
```

## Known Risks

1. **`sys_resources` table missing** — The audit reports it as `missing` because the table doesn't exist in the current `solar.db`. This is honest status — dormant by absence. If the table is created later, the audit will automatically detect and report on it.

2. **`accepted_artifact_path` blocked** — Indexed vault count is 0 because `sprint-20260508-apple-notes-wechat-ingest` hasn't passed yet. Audit correctly reports `blocked_by` status.

3. **WAL mode disk usage** — `.db-wal` and `.db-shm` files will appear. These auto-checkpoint. Documented in runbook.

4. **Age calculation** — Some SQLite timestamps use `YYYY-MM-DD HH:MM:SS` format (no T/Z). The `_days_ago` parser now handles both ISO 8601 and this format.

## Not Done

- **No sys_resources table creation** — The table doesn't exist in this DB instance; audit reports it as missing. Creating it would be schema redesign (non-goal per contract).
- **No actual telemetry writing** — `sys_resources` access_count stays 0 because no consumer writes to it. The audit honestly reports this as dormant/missing.
- **No bridge to `solar` CLI for shared DB** — Per contract Option B, `solar` is explicitly local-only. This is documented, not a gap.
