---
sprint_id: sprint-20260508-mirage-codex-solar-substrate
title: Mirage As Unified Data Substrate For Codex And Solar
priority: P1
lane: data-plane
owner: planner
created_at: 2026-05-08T17:45:00Z
status: contract_ready
handoff_to: planner
blocked_by: sprint-20260508-workstream-verification-closeout
---

# Sprint Contract — Mirage As Unified Data Substrate For Codex And Solar

## Intent

Make `solar-harness mirage` the canonical read/search layer for both Codex and Solar Harness. Codex, Claude panes, planner, builders, and evaluator should use the same sourced data substrate for Knowledge, QMD/MinerU, Solar DB, Cortex, sprints, local files, and optional Google Drive.

## Current Seed Evidence

- `solar-harness mirage doctor --json` works and reports local mounts.
- `solar-harness mirage search "Solar Harness Obsidian" --json` returns hits from `mirage_path` and `qmd`.
- `docs/mirage-data-substrate-codex-solar.md` describes the target architecture.
- Config UI exposes Mirage enabled/workspace and Google credentials fields.

## Acceptance

- A1: Codex/Solar runtime docs say cross-source search starts with `solar-harness mirage search`.
- A2: `solar-harness mirage search <query> --json` returns sourced bounded results from at least two source classes.
- A3: status-server exposes Mirage health.
- A4: config UI can edit Mirage workspace/config flags without exposing secrets.
- A5: no full home mount, Drive read-only by default, no direct final wiki writes.
- A6: evaluator verifies with real commands, not status fields only.

## Verify

```bash
solar-harness mirage search "Solar Harness Obsidian" --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert len(d.get("hits", [])) > 0'
curl -fsS http://127.0.0.1:8789/api/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "mirage" in d["config"]'
```

