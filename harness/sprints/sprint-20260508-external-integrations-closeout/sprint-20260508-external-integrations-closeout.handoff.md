# Handoff — sprint-20260508-external-integrations-closeout
Builder: 建设者化身 (Claude Sonnet 4.6)
Round: 1

## 变更文件

| File | Change |
|------|--------|
| `reports/upload-ingest-rootcause-20260508.md` | CREATED — 147-line root-cause analysis (S1) |
| `schemas/integrations.schema.json` | CREATED — frozen schema v1.0.0 with 4 enum defs (S2) |
| `lib/external-integrations-health.py` | EDITED — Mirage sdk/drive, Symphony mode/executes_builders, OWL connection_status, Drive state (S2+S5) |
| `lib/symphony/status-server.py` | EDITED — added `_integrations_view_html()`, `/integrations-view` route, fixed `item.states` bug (S3) |
| `lib/wiki-upload-audit.py` | EDITED — `_derive_state()`, `_derive_blocker()`, `state`/`blocker` per-file fields (S4) |
| `tests/external-integrations/test_schema_health.sh` | CREATED (S6) |
| `tests/external-integrations/test_wording_flags.sh` | CREATED (S6) |
| `tests/external-integrations/test_audit_uploads.sh` | CREATED (S6) |
| `tests/external-integrations/test_upload_ingest_coverage.sh` | CREATED (S6) |
| `tests/external-integrations/test_endpoint_view.sh` | CREATED (S6) |
| `tests/external-integrations/run-all.sh` | CREATED (S6) |
| `reports/solar-open-source-integrations-audit-20260508-final.md` | CREATED — 221-line final report (S7) |

## Done 定义达成

1. **D1 — `solar-harness integrations status --json` returns 7 integrations with 6-state fields**: ✅  
   ```
   python3 lib/external-integrations-health.py --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['integrations']), 'integrations')"
   → 7 integrations
   Fields present on each: installed/configured/running/indexed/used_by_default/degraded_reason/status/evidence ✓
   ```

2. **D2 — Status server `/integrations` returns same JSON without breaking `/status`**: ✅  
   ```
   curl http://127.0.0.1:8765/integrations → {"summary": {"ok":1,"warn":6,"missing":0,"total":7}, "integrations": [...7 items...]}
   curl http://127.0.0.1:8765/status → 200 (not broken)
   curl http://127.0.0.1:8765/healthz → "ok"
   ```

3. **D3 — Status UI has human-readable Integrations tab (not raw JSON)**: ✅  
   ```
   curl http://127.0.0.1:8765/integrations-view -o /tmp/iv.html → 75,324 bytes
   grep -ic -E 'obsidian-wiki|MinerU|mermaid|symphony|mirage|owl|[Gg]oogle' /tmp/iv.html → 164
   Server-side rendered: all 7 names in HTML source without JS execution
   ```

4. **D4 — Wiki upload ingest P0 closed: latest batch QMD/Vault/Solar DB 23/23, dispatch pending 0**: ✅  
   ```
   Batch 20260508T122047Z: qmd 23/23, vault 23/23, solar_db 23/23, dispatch pending 0
   Batch 20260508T131337Z: qmd 16/16, vault 16/16, solar_db 16/16, dispatch pending 0
   Root cause documented in upload-ingest-rootcause-20260508.md
   ```

5. **D5 — QMD/Vault/Solar DB facts reconciled; QMD-only not reported as fully ingested**: ✅  
   ```
   wiki-upload-audit.py --batch 20260508T131337Z --json → all files state="full"
   New `state` field enum: full|qmd_only|vault_only|db_only|partial:qmd+vault|partial:qmd+db|partial:vault+db|missing
   New `blocker` field for non-full files: dispatch_pending|dispatch_failed|parse_error|oversized|unsupported_format|db_write_failed|unknown
   No qmd_only files exist in either batch (all full)
   ```

6. **D6 — Mirage status distinguishes Solar logical wrapper vs official Mirage SDK/FUSE**: ✅  
   ```
   evidence.sdk.kind = "solar-logical"
   evidence.drive.state = "credentials_missing"
   purpose explicitly says "NOT official Mirage SDK/FUSE; Drive is a logical mount"
   ```

7. **D7 — Symphony distinguishes dry-run sidecar vs primary executor; no false claim Symphony runs builders**: ✅  
   ```
   evidence.mode = "dry_run_sidecar"
   evidence.executes_builders = false
   running = false
   purpose: "coordinator/tmux is the real executor; Symphony does not run builders"
   ```

8. **D8 — OWL status explicit: not connected**: ✅  
   ```
   evidence.connection_status = "not_connected"
   running = false, indexed = false, used_by_default = false
   degraded_reason: "未连接（如需提级须新 sprint）"
   ```

9. **D9 — Tests cover health probe JSON schema, audit command, `/integrations` endpoint**: ✅  
   ```
   bash tests/external-integrations/run-all.sh
   → 5 suites PASS, 0 FAIL
   → 42 individual checks PASS
   Coverage: schema validation, wording flags (D6/D7/D8), audit state/blocker fields, 
             batch ingest coverage (D4/D5), HTTP endpoint + HTML rendering
   ```

10. **D10 — Updated report with final state and remaining conflicts with owner/next action**: ✅  
    ```
    reports/solar-open-source-integrations-audit-20260508-final.md (221 lines)
    § 7 Remaining Conflicts table: 8 items with Owner/Priority/Next Action
    4 by-design items, 4 actionable items with specific next steps
    ```

## 验证方法

```bash
# 1. All tests
bash ~/.solar/harness/tests/external-integrations/run-all.sh

# 2. Health probe
python3 ~/.solar/harness/lib/external-integrations-health.py --json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d['summary']); \
  s=next(i for i in d['integrations'] if 'symphony' in i['name'].lower()); \
  print('symphony mode:', s['evidence']['mode'], 'executes_builders:', s['evidence']['executes_builders'])"

# 3. Upload audit with state/blocker
python3 ~/.solar/harness/lib/wiki-upload-audit.py --batch 20260508T131337Z --json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); \
  files=d['pages']['files']; \
  print('states:', sorted(set(f['state'] for f in files))); \
  print('total:', d['total'], 'solar_db found:', d['solar_db']['found'])"

# 4. HTTP endpoints (requires status server running on 8765)
python3 ~/.solar/harness/lib/external-integrations-health.py --json > /dev/null  # warm cache
curl http://127.0.0.1:8765/integrations | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'])"
curl http://127.0.0.1:8765/integrations-view -o /tmp/iv.html && grep -c 'symphony\|mirage\|owl' /tmp/iv.html
```

## 备注

- The `/integrations` and `/integrations-view` endpoints require the cache to be warm (run the probe directly once) to avoid the 90s `wiki-upload-audit.py` timeout during the upload audit step. Cache TTL is 120s by default.
- Status server must be running (`solar-harness status-server start`) for endpoint tests to pass.
- The `test_endpoint_view.sh` warms the cache automatically before curl.
- All 7 integrations are `warn` (not `missing`) — they are installed but have one or more degraded conditions (most are by design: Symphony dry-run, Mirage logical wrapper, Drive no credentials, OWL not connected).
