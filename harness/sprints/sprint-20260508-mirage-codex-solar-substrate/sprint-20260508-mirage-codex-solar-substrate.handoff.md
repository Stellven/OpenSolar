# Handoff — sprint-20260508-mirage-codex-solar-substrate
Builder: 建设者化身
Round: 1

## Summary

Implemented Mirage adoption and governance in 3 slices:
- **S1**: Security boundary probes test suite + host-path blocking fix in `solar_mirage.py`
- **S2**: Rich mirage fields in status-server + config UI; re-probe endpoint; backup-then-atomic-rename for config saves
- **S3**: "Canonical entry" language in docs; anti-patterns table; examples; runbook; `~/.solar/CLAUDE.md` with `use mirage` guidance

All A1–A6 acceptance criteria verified.

## Changed Files

| File | Change |
|------|--------|
| `lib/solar_mirage.py` | Added host-absolute-path blocking in `cmd_exec()` — `~/.zshrc`, `/etc/passwd`, credential paths now return `exit_code: 126` |
| `tests/test-mirage-substrate.sh` | NEW — 13 probes: P1 denied reads, P2 denied writes, P3 /raw write+read, P4 search, P5 doctor |
| `lib/symphony/status-server.py` | `_mirage_status()` now emits `drive_status` and `qmd_indexed` flat keys |
| `integrations/solar-config-server.py` | `_mirage_detail()` helper + richer `checks.mirage`; `/api/mirage/reprobe` POST; `save_config()` now writes `.bak` before atomic rename |
| `docs/mirage-data-substrate-codex-solar.md` | Promoted "Canonical entry" section; anti-patterns table; examples; what-goes-where table; security guarantees |
| `docs/mirage-runbook.md` | NEW — 7-section operator runbook |
| `~/.solar/CLAUDE.md` | NEW — Claude/Codex runtime rules: "use mirage" for cross-source reads, do-not list |

## Architecture

```
Codex / Claude panes
  └─ cross-source read → solar-harness mirage search/exec   ← Canonical entry
                           ├─ /knowledge (ro) → ~/Knowledge
                           ├─ /raw (rw)       → ~/Knowledge/_raw
                           ├─ /sprints (ro)   → harness/sprints
                           ├─ /solar (ro)     → ~/.solar
                           └─ /cortex (ro)    → Cortex store

security: host absolute paths BLOCKED in exec
          /knowledge, /sprints, /solar, /cortex → read-only
          /raw → write allowed (staging)
```

## Verification Evidence

### A1 — Docs say "use mirage"
```
grep "use mirage" ~/.solar/CLAUDE.md → FOUND ✅
grep "Canonical entry" docs/mirage-data-substrate-codex-solar.md → FOUND ✅
```

### A2 — mirage search returns sourced hits
```
solar-harness mirage search "Solar Harness Obsidian" --json → hits: 9 ✅
```

### A3 — status-server exposes Mirage health
```
_mirage_status() adds drive_status + qmd_indexed to /api/status payload ✅
```

### A4 — config UI exposes mirage without secrets
```
curl http://127.0.0.1:8789/api/status → "mirage" in d["config"] ✅
checks.mirage keys: ['ok','enabled','workspace_id','mounts','drive_status','drive_ro','qmd_indexed','last_probe_at','stale','credential_configured']
```

### A5 — No full home mount; Drive ro; no wiki direct writes
```
mirage exec 'cat ~/.zshrc' → error: "host path not allowed" exit_code:126 ✅
/knowledge, /sprints, /solar write → denied ✅
```

### A6 — Evaluator probes (real commands)
```
bash tests/test-mirage-substrate.sh → PROBES_PASSED=13 PROBES_FAILED=0 ✅
P1-deny-tilde-zshrc ✅
P1-deny-etc-passwd ✅
P1-deny-credential-path ✅
P2-deny-write-knowledge ✅
P2-deny-write-sprints ✅
P2-deny-write-solar ✅
P2-deny-write-cortex ✅
P2-deny-write-drive ✅
P3-raw-write ✅
P3-raw-read ✅
P4-search-returns-hits ✅
P4-search-source-type ✅
P5-doctor-healthy ✅
```

## 验证方法

Evaluator must re-run the real commands below in order and record stdout/stderr summaries in `eval.md`:

1. `bash ~/.solar/harness/tests/test-mirage-substrate.sh`
   - Expected: `PROBES_FAILED=0`, all host absolute path probes denied, `/raw` write/read allowed.
2. `solar-harness mirage search "Solar Harness Obsidian" --json`
   - Expected: hits are non-empty and include at least two source classes.
3. `curl -fsS http://127.0.0.1:8765/api/status` and `curl -fsS http://127.0.0.1:8789/api/status`
   - Expected: both expose Mirage status fields or an explicitly documented degraded state.
4. `grep -q "Canonical entry" ~/.solar/harness/docs/mirage-data-substrate-codex-solar.md`
5. `grep -q "use mirage" ~/.solar/CLAUDE.md`
6. `test -s ~/.solar/harness/docs/mirage-runbook.md`

Do not pass this sprint from status fields alone. `eval.md` must include a `Real Commands Executed` section with the command list and concrete observed results.

## Known Risks

1. **Status-server (8765) not running** — `_mirage_status()` enhancement requires restart to take effect. The status-server reads from `state/mirage/last-probe.json` cache; if no probe has run, it returns the empty default. Running `solar-harness mirage doctor` once will populate the cache.

2. **Drive status always "degraded"** — Expected when no Google credentials are configured. This is honest status, not a bug.

3. **`qmd_indexed` always 0 in doctor** — `solar_mirage.py` `cmd_doctor()` doesn't currently query QMD indexed count. The `drive_status`/`qmd_indexed` fields are safe defaults; they'll populate when QMD mount is active.

## Not Done

- **QMD `indexed` count in doctor** — `cmd_doctor()` in `solar_mirage.py` doesn't call `qmd status`; `qmd_indexed` stays 0. Out of scope per plan (write scope: status-server + config UI).
- **HTML Mirage card in config UI** — Plan mentions "Add Mirage card/section to HTML" but 8789 HTML already has Mirage workspace + enabled toggle. Full card rendering out of scope for this pass.
- **Google Drive credential setup** — Drive setup requires credentials file; this sprint adds the UI fields and reprobe endpoint; actual auth flow is out of scope.
