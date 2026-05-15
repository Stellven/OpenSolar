# Sprint Contract: External Integrations Closeout

Priority: P0  
Lane: reliability  
Owner: Solar Harness  
Created: 2026-05-08  
Source audit: `/Users/lisihao/.solar/harness/reports/solar-open-source-integrations-audit-20260508.md`

## Intent

把历史上接进 Solar 的外部开源/外部项目从“装了、能跑一部分”收敛成可运营的集成面。每个集成必须明确回答：

- 是什么
- 集成进来干什么
- 当前是否 installed/configured/running/indexed/used_by_default
- 断头是什么
- 是否和其他集成冲突
- 谁负责修复和验收

## Scope

External integrations in scope:

1. `Ar9av/obsidian-wiki`
2. `opendatalab/MinerU-Document-Explorer` / `qmd`
3. `mermaid-js/mermaid`
4. `openai/symphony` SPEC implementation
5. `strukto-ai/mirage` / Solar logical VFS wrapper
6. `camel-ai/owl`
7. Google Drive mount

## Already Done By Codex

- Added `/Users/lisihao/.solar/harness/lib/external-integrations-health.py`
- Added `solar-harness integrations status [--json]`
- Added status-server `GET /integrations`
- Restored wiki capture server runtime
- Fixed `solar-harness wiki audit-uploads/backfill-uploads` shell `local` bug
- Confirmed current P0 data gap: latest auditable upload batch `20260508T131337Z` has 16 originals, QMD 14, Vault 12, Solar DB 0; prior batch `20260508T122047Z` has 23 originals, QMD 15, Vault 6, Solar DB 0, dispatch pending 1

## Acceptance

```
┌────┬──────────────────────────────────────────────────────────────────────────────┐
│ D1 │ `solar-harness integrations status --json` returns seven integrations with six-state fields. │
│ D2 │ Status server `/integrations` returns the same JSON without breaking `/status` refresh.       │
│ D3 │ Status UI has a human-readable Integrations tab, not raw JSON.                              │
│ D4 │ Wiki upload ingest P0 is closed or explicitly escalated: latest batch must show QMD 23/23, Vault pages 23/23, Solar DB/FTS 23/23, dispatch pending 0, or documented blocker per file. │
│ D5 │ Obsidian/QMD/Solar DB facts are reconciled: QMD-only hits are not reported as fully ingested. │
│ D6 │ Mirage status distinguishes Solar logical wrapper vs official Mirage SDK/FUSE; Drive degraded reason visible. │
│ D7 │ Symphony status distinguishes dry-run sidecar vs primary executor; no user-facing claim that Symphony runs builders unless true. │
│ D8 │ OWL status is explicit: not connected, connected experimental, or connected production. If not connected, no UI should imply availability. │
│ D9 │ Tests cover health probe JSON schema, audit command, and `/integrations` endpoint.           │
│ D10│ Updated report lists final state and remaining conflicts with owner/next action.              │
└────┴──────────────────────────────────────────────────────────────────────────────┘
```

## Stop Rules

- If upload ingest remains Solar DB 0/23 after one repair pass, stop and escalate with per-file blockers.
- If an integration cannot be made `used_by_default`, label it explicitly as `optional` or `experimental`; do not leave ambiguous.
- Do not add new external projects in this sprint.

## Verification Commands

```bash
solar-harness integrations status --json
solar-harness integrations status --json --refresh
curl -fsS http://127.0.0.1:8765/integrations | python3 -m json.tool
solar-harness wiki audit-uploads --batch 20260508T122047Z --json
solar-harness mirage doctor --json
solar-harness wiki qmd-status
solar-harness symphony status
```
