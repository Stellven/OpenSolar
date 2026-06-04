# Handoff — sprint-20260508-accepted-artifact-knowledge
Builder: 建设者化身
Round: 1

## 变更文件

- `lib/accepted-artifact-export.py` (NEW): Core exporter — `cmd_export`, `cmd_backfill`, redaction, manifest hash, status/event updates, ingest dispatch generation
- `coordinator.sh` (MODIFIED): Added async accepted artifact export hook in `handle_passed()` — fail-open async subshell after `touch "$finalized"`
- `solar-harness.sh` (MODIFIED): Added `export-accepted` and `backfill-accepted` subcommands under `wiki)` case
- `integrations/wiki-capture-server.py` (MODIFIED): Added `_accepted_artifact_status()` helper + `/api/accepted-artifacts` GET endpoint
- `tests/test-accepted-artifact-knowledge-sync.sh` (NEW): Regression suite — 7 test cases, 18 probes, all pass
- `docs/accepted-artifact-knowledge.md` (NEW): Operator runbook covering verify, backfill, disable, repair, manifest inspection

## Done 定义达成

### A1: pass-only guard
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh --case pass-only`
```
✅ pass-only: passed sprint accepted in dry-run
✅ pass-only: non-passed sprint rejected
PASS=2  FAIL=0
```
Non-passed (reviewing) sprint returns `{"ok": false}`. Only `status=passed/finalized` proceeds.

### A2: artifact schema
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh --case artifact-schema`
```
✅ artifact-schema: export succeeded
✅ artifact-schema: all required frontmatter keys present
✅ artifact-schema: required body sections present
PASS=3  FAIL=0
```
YAML frontmatter includes: `source`, `artifact_type`, `sprint_id`, `status`, `redacted`, `visibility`, `provenance`, `source_files`. Body includes `## Executive Summary` and `## Source Artifact Index`.

### A3: redaction
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh --case redaction`
```
✅ redaction: no raw secrets in output
✅ redaction: [REDACTED] markers present in output
PASS=2  FAIL=0
```
8 patterns redacted: `sk-*`, `Bearer`, `api_key=`, `token=`, `ANTHROPIC_AUTH_TOKEN`, `ZHIPU_AUTH_TOKEN`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`.

### A4: manifest idempotency
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh --case idempotent`
```
✅ idempotent: second export returned same path
✅ idempotent: --force bypasses hash check
PASS=2  FAIL=0
```
SHA-256 of source file mtimes+sizes; unchanged hash → skip. `--force` bypasses check.

### A5: status/events
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh --case status-events`
```
✅ status-events: knowledge_export_status set to 'exported'
✅ status-events: accepted_artifact event emitted to events.jsonl
✅ status-events: knowledge_export_path set
PASS=3  FAIL=0
```
6 `knowledge_export_*` fields updated in status.json; `accepted_artifact_exported` event emitted to events.jsonl.

### A6: ingest dispatch
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh --case ingest-dispatch`
```
✅ ingest-dispatch: dispatch file created under .../vault/_raw/solar-harness/.dispatch
✅ ingest-dispatch: dispatch file references sprint_id
✅ ingest-dispatch: knowledge_ingest_dispatch field set in status.json
PASS=3  FAIL=0
```
Dispatch written to `Knowledge/_raw/solar-harness/.dispatch/`. `knowledge_ingest_dispatch` field set.

### A7: backfill dry-run via CLI
✅ `solar-harness wiki backfill-accepted --limit 3 --dry-run --json`
```json
{"candidates": ["sprint-20260414-084605", "sprint-20260414-111746", "sprint-20260414-130713"], "dry_run": true, "count": 3}
```
CLI routes to `accepted-artifact-export.py backfill`. Dry-run produces candidates list, no files written.

### A8: full suite
✅ `bash tests/test-accepted-artifact-knowledge-sync.sh`
```
PASS=18  FAIL=0  SKIP=0
RESULT: ✅ PASS
```

## 验证方法

```bash
cd /Users/lisihao/.solar/harness

# A1-A8 all cases
bash tests/test-accepted-artifact-knowledge-sync.sh

# Individual cases
bash tests/test-accepted-artifact-knowledge-sync.sh --case pass-only
bash tests/test-accepted-artifact-knowledge-sync.sh --case artifact-schema
bash tests/test-accepted-artifact-knowledge-sync.sh --case redaction
bash tests/test-accepted-artifact-knowledge-sync.sh --case idempotent
bash tests/test-accepted-artifact-knowledge-sync.sh --case status-events
bash tests/test-accepted-artifact-knowledge-sync.sh --case ingest-dispatch
bash tests/test-accepted-artifact-knowledge-sync.sh --case backfill-dry-run

# A7: CLI
solar-harness wiki backfill-accepted --limit 3 --dry-run --json

# Static checks
bash -n coordinator.sh && bash -n solar-harness.sh && python3 -m py_compile lib/accepted-artifact-export.py integrations/wiki-capture-server.py && echo "ALL STATIC OK"

# Coordinator hook (search for sprint-20260508-accepted-artifact-knowledge marker)
grep -n "sprint-20260508-accepted-artifact-knowledge" coordinator.sh

# Status-server endpoint (when running)
# curl -s http://127.0.0.1:8765/api/accepted-artifacts | python3 -m json.tool
```

## 备注

- Async subshell in `handle_passed()` is fail-open: errors append to `logs/accepted-artifact-export.log`, never abort finalization.
- Automatic export never uses `--full`; redaction is always enabled in the coordinator hook.
- Backfill defaults to `--dry-run` when called via test; CLI requires explicit call without `--dry-run` to write.
- `wiki-capture-server.py` `/api/accepted-artifacts` endpoint reads from vault manifest — returns sane defaults if manifest not yet created.
- `--sprints-dir` flag added to both `cmd_export` and `cmd_backfill` for testability with isolated temp vaults.
