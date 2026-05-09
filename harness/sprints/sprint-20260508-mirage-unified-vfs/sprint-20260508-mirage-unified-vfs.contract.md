---
sprint_id: sprint-20260508-mirage-unified-vfs
title: Mirage Unified Virtual Filesystem For Solar
priority: P1
lane: data-plane
owner: planner
created_at: 2026-05-08T13:55:00Z
status: contract_ready
handoff_to: planner
blocked_by: sprint-20260508-solar-kb-obsidian-autouse
---

# Sprint Contract — Mirage Unified Virtual Filesystem For Solar

## Intent

Integrate Strukto Mirage into Solar Harness as a unified virtual filesystem data plane. Solar agents should be able to read and search Solar DB, Cortex, Obsidian/QMD knowledge, sprint artifacts, allowlisted local files, and optional Google Drive through one consistent `solar-harness mirage` interface.

This is an access layer, not a replacement for Solar KB, Obsidian wiki, QMD/MinerU, or accepted-artifact ingestion.

## Upstream Evidence

- Mirage GitHub describes a unified virtual filesystem for AI agents that mounts services like S3, Google Drive, Slack, Gmail, Redis, GitHub, and local disk side-by-side.
- Mirage docs show both Python and TypeScript SDKs and a CLI workspace flow with `mirage workspace create` and `mirage execute`.
- Mirage resource matrix lists Disk, Google Drive, Gmail, Docs, Sheets, Slides, GitHub, Postgres, Redis, SSH, Notion, and other resources, with mount modes.
- Mirage docs state FUSE is optional; default execution is in-process shell over mounted resources.

Source links:
- https://github.com/strukto-ai/mirage
- https://docs.mirage.strukto.ai/home/introduction
- https://docs.mirage.strukto.ai/home/resource-matrix
- https://docs.mirage.strukto.ai/llms.txt

## Current Solar Evidence

- Solar already has `/Users/sihaoli/.solar/solar.db`, Cortex code under `/Users/sihaoli/.claude/core/cortex`, and sprint artifacts under `/Users/sihaoli/.solar/harness/sprints`.
- Obsidian vault is `/Users/sihaoli/Knowledge`.
- QMD/MinerU collection `solar-wiki` is configured and can search/read the vault.
- Existing `solar-harness wiki ...` commands handle ingest/query/export; Mirage must call or complement them, not bypass their semantics.

## Non-Goals

- Do not replace `solar-harness wiki`, QMD/MinerU, Solar DB retrieval, or Cortex.
- Do not default to FUSE or require macOS kernel/system-extension setup.
- Do not implement full Google OAuth UX if credentials are not already available.
- Do not mount the entire `/Users/sihaoli` home directory.
- Do not write directly into finalized Obsidian wiki pages; staging writes go to `_raw/`.

## Deliverables

1. `/Users/sihaoli/.solar/harness/config/mirage.solar.yaml`
   - Default Solar Mirage workspace manifest.
   - Defines allowlisted mounts and per-mount modes.
   - Supports env expansion but never prints secret values.

2. `/Users/sihaoli/.solar/harness/lib/solar_mirage.py` or `/Users/sihaoli/.solar/harness/lib/solar-mirage.ts`
   - Wrapper around Mirage SDK/CLI.
   - Implements doctor, workspace creation, exec, search, provision/dry-run.
   - Normalizes output for status server and tests.

3. `/Users/sihaoli/.solar/harness/solar-harness.sh`
   - Adds `solar-harness mirage ...` command family.
   - Must be non-interactive and scriptable.

4. `/Users/sihaoli/.solar/harness/lib/symphony/status-server.py`
   - Adds `mirage` status section to `/status`.
   - Keeps `/healthz` dependency-free and fast.

5. `/Users/sihaoli/.solar/harness/lib/mirage-search.py` or equivalent
   - Combines Mirage path search, QMD search, and Solar DB retrieval.
   - Returns bounded sourced results.

6. `/Users/sihaoli/.solar/harness/docs/mirage-unified-vfs.md`
   - Install, configure, credentials, security model, examples, rollback.

7. `/Users/sihaoli/.solar/harness/tests/test-mirage-unified-vfs.sh`
   - End-to-end test suite with temp mounts and no real Drive writes.

## Acceptance Criteria

### A1 — Install + Doctor

Required behavior:
- `solar-harness mirage doctor --json` reports package version, SDK/CLI path, config path, FUSE optional status, and mount readiness.
- Missing Google credentials must produce `drive.status=warn` or `degraded`, not command failure.

Verify:

```bash
solar-harness mirage doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["enabled"] and d["config"]; assert d["drive"]["status"] in ("ok","warn","degraded","disabled")'
```

<!-- verify: cmd="solar-harness mirage doctor --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"enabled\"] and d[\"config\"]; assert d[\"drive\"][\"status\"] in (\"ok\",\"warn\",\"degraded\",\"disabled\")'" -->

### A2 — Default Workspace Mounts

Required mounts:
- `/knowledge` -> `/Users/sihaoli/Knowledge` read-only.
- `/raw` -> `/Users/sihaoli/Knowledge/_raw` write-staging only.
- `/sprints` -> `/Users/sihaoli/.solar/harness/sprints` read-only.
- `/solar` -> `/Users/sihaoli/.solar` read-only with redaction.
- `/cortex` -> `/Users/sihaoli/.claude/core/cortex` read-only.
- `/projects` -> allowlisted project roots only.
- `/drive` -> optional Google Drive mount.

Verify:

```bash
solar-harness mirage workspace create --id solar-default --json
solar-harness mirage mounts --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); names={m["path"] for m in d["mounts"]}; assert {"/knowledge","/raw","/sprints","/solar","/cortex"}.issubset(names)'
```

<!-- verify: cmd="solar-harness mirage workspace create --id solar-default --json >/dev/null && solar-harness mirage mounts --json | python3 -c 'import json,sys; d=json.load(sys.stdin); names={m[\"path\"] for m in d[\"mounts\"]}; assert {\"/knowledge\",\"/raw\",\"/sprints\",\"/solar\",\"/cortex\"}.issubset(names)'" -->

### A3 — Local Knowledge And Sprint Files Are Readable

Required behavior:
- Agent can use `find`, `grep`, `cat`, `head`, `wc` style commands through Mirage.
- Output is bounded by default.

Verify:

```bash
solar-harness mirage exec -- 'find /knowledge -name "*.md" | head'
solar-harness mirage exec -- 'grep -R "Solar Harness" /sprints | head'
```

<!-- verify: cmd="solar-harness mirage exec -- 'find /knowledge -name \"*.md\" | head' >/dev/null && solar-harness mirage exec -- 'grep -R \"Solar Harness\" /sprints | head' >/dev/null" -->

### A4 — Unified Search Across Mirage + QMD + Solar DB

Required behavior:
- `solar-harness mirage search <query> --json` returns hits from at least two source classes when available:
  - `mirage_path`
  - `qmd`
  - `solar_db`
- Each hit includes `mount`, `path`, `source_type`, `snippet`, and `provenance`.
- Default result budget: max 10 hits and max 4,000 output chars.

Verify:

```bash
solar-harness mirage search "Solar Harness Obsidian" --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hits"]; assert len({h["source_type"] for h in d["hits"]}) >= 2'
```

<!-- verify: cmd="solar-harness mirage search 'Solar Harness Obsidian' --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d[\"hits\"]; assert len({h[\"source_type\"] for h in d[\"hits\"]}) >= 2'" -->

### A5 — Google Drive Optional And Read-Only By Default

Required behavior:
- If Google credentials are absent, `/drive` status is degraded but local mounts still work.
- If credentials are present, `ls /drive` works.
- Writes to `/drive` are denied unless command includes explicit `--allow-write-drive`.

Verify:

```bash
solar-harness mirage exec -- 'ls /knowledge' >/dev/null
solar-harness mirage exec -- 'echo test > /drive/solar-write-test.txt' \
  && exit 1 || true
```

<!-- verify: cmd="solar-harness mirage exec -- 'ls /knowledge' >/dev/null && (solar-harness mirage exec -- 'echo test > /drive/solar-write-test.txt' && exit 1 || true)" -->

### A6 — Write Boundary Is Enforced

Required behavior:
- Writes allowed to `/raw` only for staging.
- Writes denied by default to `/knowledge/concepts`, `/solar`, `/cortex`, `/sprints`, `/drive`, and non-allowlisted paths.
- Denials emit `mirage_write_denied` event without leaking content.

Verify:

```bash
solar-harness mirage exec -- 'echo "mirage smoke" > /raw/mirage-smoke.md'
solar-harness mirage exec -- 'echo "bad" > /solar/mirage-bad.txt' \
  && exit 1 || true
rg -n '"event": ?"mirage_write_denied"' /Users/sihaoli/.solar/harness/sprints/warn.events.jsonl /Users/sihaoli/.solar/harness/sprints/*.events.jsonl >/dev/null
```

<!-- verify: cmd="solar-harness mirage exec -- 'echo \"mirage smoke\" > /raw/mirage-smoke.md' && (solar-harness mirage exec -- 'echo \"bad\" > /solar/mirage-bad.txt' && exit 1 || true) && rg -n '\"event\": ?\"mirage_write_denied\"' /Users/sihaoli/.solar/harness/sprints/warn.events.jsonl /Users/sihaoli/.solar/harness/sprints/*.events.jsonl >/dev/null" -->

### A7 — Status Server Observability

Required behavior:
- `/status` includes `mirage`.
- Fields include `enabled`, `version`, `workspace_id`, `mounts`, `drive`, `qmd`, `last_command`, `last_error`, `last_probe_at`.
- Status probing must be fast and fail-open.

Verify:

```bash
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); m=d["mirage"]; assert "mounts" in m and "drive" in m and "qmd" in m'
```

<!-- verify: cmd="curl -fsS http://127.0.0.1:8765/status | python3 -c 'import json,sys; d=json.load(sys.stdin); m=d[\"mirage\"]; assert \"mounts\" in m and \"drive\" in m and \"qmd\" in m'" -->

### A8 — Regression Test Suite

Required behavior:
- Tests use temp workspace and temp mounts.
- No test writes to real Google Drive.
- Tests cover doctor, workspace, search, permissions, redaction, status JSON.

Verify:

```bash
bash /Users/sihaoli/.solar/harness/tests/test-mirage-unified-vfs.sh
```

<!-- verify: cmd="bash /Users/sihaoli/.solar/harness/tests/test-mirage-unified-vfs.sh" -->

## Stop Rules

- Stop if implementation requires mounting all of `/Users/sihaoli` by default.
- Stop if Google credentials are printed, copied into status/events, or committed into config.
- Stop if Drive write is enabled by default.
- Stop if Mirage failure blocks coordinator, status server, or existing wiki commands.
- Stop if tests perform real remote writes.
- Stop if `solar-harness mirage search` returns unsourced raw dumps instead of bounded sourced hits.

## Planner Instructions

1. Produce design:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.design.md`
2. Produce plan:
   `/Users/sihaoli/.solar/harness/sprints/sprint-20260508-mirage-unified-vfs.plan.md`
3. Split implementation into three slices:
   - Slice 1: install/doctor/workspace manifest/CLI shell.
   - Slice 2: unified search bridge across Mirage paths + QMD + Solar DB.
   - Slice 3: status/events/security tests/docs.
4. Google Drive must be optional/degraded in Slice 1 and only fully activated if credentials are already available.
5. Dispatch at least two builders if the active P0 has completed; otherwise keep queued behind current P0.

## Definition Of Done

- A1-A8 verification commands pass.
- `solar-harness mirage search` can retrieve across Knowledge/QMD/Solar DB with sourced bounded output.
- `/status` shows Mirage health.
- No broad home mount, no default Drive write, no secret leakage.
- Docs include install, verify, credential setup, examples, and rollback.

