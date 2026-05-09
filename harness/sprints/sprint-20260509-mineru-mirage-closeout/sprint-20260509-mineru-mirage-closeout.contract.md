---
sid: sprint-20260509-mineru-mirage-closeout
priority: P1
lane: delivery
status: queued
handoff_to: planner
created_at: 2026-05-09T01:25:00Z
---

# Sprint Contract — MinerU + Mirage Full Closure

## Intent
Close the two integrations that are currently only partially usable: MinerU Document Explorer and Mirage unified VFS. Do not mark either integration `ok` until the full app/runtime path is verified, not only Solar wrappers.

## Acceptance

| ID | Requirement | Verification |
|---|---|---|
| A1 | MinerU vendor has reproducible `.venv` bootstrap command and lock/report | `solar-harness wiki mineru-doctor --json` returns venv=ok |
| A2 | MinerU can deep-extract at least 2 PDFs from `/Users/sihaoli/Knowledge/_raw/file-uploads` into Obsidian reference pages with provenance | audit report lists source -> generated pages |
| A3 | QMD MCP remains reachable on both `127.0.0.1:8181` and `::1:8181` after shell exits | `solar-harness wiki qmd-mcp status` shows both hosts |
| A4 | Mirage official SDK/FUSE decision is explicit: installed and exercised, or ADR says why Solar logical wrapper remains the boundary | `reports/mirage-sdk-fuse-decision-*.md` |
| A5 | Mirage mounts expose Knowledge, raw, sprints, Solar DB, QMD; Google Drive is either real credentialed mount or explicitly degraded in UI | `solar-harness mirage doctor --json` |
| A6 | Status UI uses precise labels: basic usable, default usable, closed loop, dead ends | `/integrations` visual check + JSON schema test |
| A7 | No foreground embedding or long PDF extraction blocks user shell; all heavy jobs are background/idle guarded | launchd/tmux/service status evidence |

## Stop Rules
- If MinerU install requires GPU/CUDA-only path on this Mac, stop and document CPU fallback or mark unsupported.
- If Mirage SDK/FUSE conflicts with macOS permissions, do not force install; write ADR and keep Solar logical wrapper.
- If any task needs secrets/Drive credentials, leave as degraded with exact env var and UI action.

## Dispatch Plan
1. Planner splits MinerU runtime, PDF extraction, Mirage SDK/FUSE, status verification into separate builder slices.
2. Builder must update doctor commands and status probe before changing UI labels to ok.
3. Evaluator must run fresh probes after shell restart to prove services are persistent.
