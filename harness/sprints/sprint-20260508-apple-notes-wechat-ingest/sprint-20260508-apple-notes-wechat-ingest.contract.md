---
sprint_id: sprint-20260508-apple-notes-wechat-ingest
title: WeChat Articles Via Apple Notes To Solar Wiki
priority: P1
lane: knowledge
owner: planner
created_at: 2026-05-08T17:10:00Z
status: contract_ready
handoff_to: planner
blocked_by: sprint-20260508-workstream-verification-closeout
---

# Sprint Contract — WeChat Articles Via Apple Notes To Solar Wiki

## Intent

Create a safe Apple Notes ingestion bridge for the user workflow:

```text
WeChat article
  → user saves/shares to Apple Notes folder "Solar Inbox"
  → Solar scheduled scanner reads only that inbox/tag
  → exports new/changed notes to Knowledge/_raw/apple-notes/
  → wiki ingest dispatch asks an LLM to extract/resolve/schema
  → Obsidian/Solar knowledge base gains sourced pages
```

This sprint adds a source connector. It does not replace the existing Obsidian wiki or QMD/MinerU pipeline.

## Deliverables

1. `/Users/sihaoli/.solar/harness/lib/apple_notes_ingest.py`
   - Notes reader/exporter.
   - Supports AppleScript mode and optional SQLite read-only fallback.
   - Commands: doctor, scan, status, install-scheduler, uninstall-scheduler.

2. `/Users/sihaoli/.solar/harness/solar-harness.sh`
   - Adds `solar-harness notes ...` command family.

3. `/Users/sihaoli/.solar/harness/config/apple-notes-ingest.json`
   - Config:
     - notes_folder: `Solar Inbox`
     - tags: `["#solar-ingest", "#知识库", "#solar"]`
     - interval_seconds: 7200
     - raw_dir: `/Users/sihaoli/Knowledge/_raw/apple-notes`
     - all_notes: false

4. `/Users/sihaoli/.solar/harness/state/apple-notes-ingest/manifest.json`
   - Delta tracking by note id/hash/updated time.

5. `/Users/sihaoli/Library/LaunchAgents/com.solar.apple-notes-ingest.plist`
   - Optional scheduler installed by command, not created silently.

6. `/Users/sihaoli/.solar/harness/lib/symphony/status-server.py`
   - Adds `apple_notes_ingest` status section.

7. `/Users/sihaoli/.solar/harness/tests/test-apple-notes-ingest.sh`
   - Tests with fixtures/mock notes; does not require reading real Notes.

8. `/Users/sihaoli/.solar/harness/docs/apple-notes-wechat-ingest.md`
   - User workflow, permission setup, schedule options, troubleshooting.

## Acceptance Criteria

### A1 — Doctor And Permission Visibility

Required behavior:
- `solar-harness notes doctor --json` returns JSON.
- Detects whether Apple Notes automation permission is available.
- Detects whether folder `Solar Inbox` exists or reports actionable setup.
- Missing permission is `warn`, not stack trace.

Verify:

```bash
solar-harness notes doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "notes_access" in d and "target_folder" in d'
```

<!-- verify: cmd="solar-harness notes doctor --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"notes_access\" in d and \"target_folder\" in d'" -->

### A2 — Dry Run Does Not Write

Required behavior:
- `--dry-run` lists candidate notes.
- No `_raw/apple-notes` file is created in dry-run.
- Default source is folder `Solar Inbox` or configured tags only.

Verify:

```bash
solar-harness notes scan --once --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "candidates" in d and d["dry_run"] is True'
```

<!-- verify: cmd="solar-harness notes scan --once --dry-run --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"candidates\" in d and d[\"dry_run\"] is True'" -->

### A3 — Export To Raw Staging

Required behavior:
- Scanning exports new/changed notes to `/Users/sihaoli/Knowledge/_raw/apple-notes/YYYYMMDD/`.
- File name is deterministic and safe.
- Frontmatter contains note metadata and source.

Verify:

```bash
solar-harness notes scan --once --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "exported" in d'
find /Users/sihaoli/Knowledge/_raw/apple-notes -name "*.md" -maxdepth 3 | head -1
```

<!-- verify: cmd="solar-harness notes scan --once --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"exported\" in d' && find /Users/sihaoli/Knowledge/_raw/apple-notes -maxdepth 3 -name '*.md' | head -1" -->

### A4 — Delta Manifest Prevents Duplicates

Required behavior:
- Second scan with unchanged notes exports 0 new files.
- Manifest records note id, updated time, hash, exported path.

Verify:

```bash
solar-harness notes scan --once --json >/tmp/notes-scan-1.json
solar-harness notes scan --once --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("exported_count", 0) == 0'
test -s /Users/sihaoli/.solar/harness/state/apple-notes-ingest/manifest.json
```

<!-- verify: cmd="solar-harness notes scan --once --json >/tmp/notes-scan-1.json && solar-harness notes scan --once --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get(\"exported_count\", 0) == 0' && test -s /Users/sihaoli/.solar/harness/state/apple-notes-ingest/manifest.json" -->

### A5 — Wiki Ingest Dispatch Created

Required behavior:
- Exported files trigger `solar-harness wiki ingest --source <file> --mode append`.
- Dispatch file path is returned.
- Dispatch tells LLM to extract concepts/entities/claims/relationships/open questions.

Verify:

```bash
solar-harness notes scan --once --force-dispatch --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "dispatches" in d'
```

<!-- verify: cmd="solar-harness notes scan --once --force-dispatch --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"dispatches\" in d'" -->

### A6 — Scheduler Install/Uninstall

Required behavior:
- `install-scheduler` writes LaunchAgent only when explicitly called.
- Supports intervals 3600, 7200, 21600, 86400.
- `uninstall-scheduler` unloads and removes plist safely.

Verify:

```bash
solar-harness notes install-scheduler --interval 7200 --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["interval_seconds"] == 7200'
```

<!-- verify: cmd="solar-harness notes install-scheduler --interval 7200 --dry-run --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"interval_seconds\"] == 7200'" -->

### A7 — Status Server Observability

Required behavior:
- `/status` contains `apple_notes_ingest`.
- Includes last run, last error, exported/skipped counts, scheduler state.

Verify:

```bash
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "apple_notes_ingest" in d'
```

<!-- verify: cmd="curl -fsS http://127.0.0.1:8765/status | python3 -c 'import json,sys; d=json.load(sys.stdin); assert \"apple_notes_ingest\" in d'" -->

### A8 — Privacy Guardrails

Required behavior:
- Default config does not read all Notes.
- Locked notes are skipped.
- Secret/PII patterns are redacted in exported Markdown unless user passes `--full`.
- Events never include full note body.

Verify:

```bash
solar-harness notes doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["config"]["all_notes"] is False'
```

<!-- verify: cmd="solar-harness notes doctor --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"config\"][\"all_notes\"] is False'" -->

### A9 — Tests

Required behavior:
- Test suite uses mock Notes fixtures.
- Does not require real Apple Notes permission.
- Covers dry-run, export, manifest, dispatch, scheduler dry-run, status payload, redaction.

Verify:

```bash
bash /Users/sihaoli/.solar/harness/tests/test-apple-notes-ingest.sh
```

<!-- verify: cmd="bash /Users/sihaoli/.solar/harness/tests/test-apple-notes-ingest.sh" -->

## Stop Rules

- Stop if implementation tries to scan all Apple Notes by default.
- Stop if it reads locked/encrypted notes.
- Stop if it writes full note bodies directly to final wiki pages.
- Stop if it requires real WeChat automation/login.
- Stop if LaunchAgent is installed without explicit command.
- Stop if tests require granting real Notes permission.

## Planner Instructions

1. Produce:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-apple-notes-wechat-ingest.design.md`
2. Produce:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-apple-notes-wechat-ingest.plan.md`
3. Split into slices:
   - S1: Notes reader/exporter + config/manifest.
   - S2: wiki ingest dispatch + scheduler.
   - S3: status/events/tests/docs.
4. Keep queued behind `sprint-20260508-workstream-verification-closeout` until P0 closeout is done.

## Definition Of Done

- A1-A9 pass.
- User can save a WeChat article into Apple Notes `Solar Inbox` and get it staged into `_raw/apple-notes`.
- Wiki ingest dispatch is created and can be processed by existing Solar wiki pipeline.
- Scheduler can run hourly/2-hourly/6-hourly/daily.
- Privacy defaults are safe.

