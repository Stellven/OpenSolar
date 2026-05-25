# Handoff: AI Influence GitHub Project Intelligence Requirements Slice

epic_id: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`
sprint_id: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements`
source_prd: `/Users/lisihao/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/20260524-github-project-intelligence-prd.md`

## Status

S01 has normalized the user design into a requirements-level contract. Runtime code is not complete in this slice.

## Outcome To Downstream Mapping

| Outcome | S02 Architecture | S03 Runtime | S04 Orchestration/UI | S05 Verification |
|---|---|---|---|---|
| O1 Discovery Coverage | source adapters, queues | collectors | subscription/config UI | discovery fixtures |
| O2 Snapshot And Delta Ledger | schema and storage | snapshot/delta jobs | charts/status views | append-only tests |
| O3 Local Evidence Compression | model routing and ledger | ThunderOMLX atoms | evidence display | no-raw-premium tests |
| O4 Project Intelligence Cards | card/brief schema | card/brief generation | report/detail pages | schema/evidence tests |
| O5 Scoring And Detectors | detector contracts | scoring/alerts | alert dashboard | detector fixtures |
| O6 AI Influence Outputs | report contract | report generator | HTML/email/web page | report quality gates |

## Required Downstream Controls

- QMD remains deterministic indexing with embeddinggemma/Qwen rerank.
- ThunderOMLX + Qwen3.6 is local semantic preprocessing, not the embedder.
- Premium models receive project_reasoning_packet only.
- All claims in analysis cards must carry evidence_ids.
- Baselines and deltas must be append-only and never overwritten.

## Unclosed Risks

- 6-month baseline may require GH Archive/BigQuery or slow API replay; do not claim complete until data exists.
- GitHub API rate limits require ETag, conditional requests, and paced collection.
- Social/X collection may be incomplete depending on upstream availability.
- YouTube repo mentions depend on transcript coverage and semantic extraction completion.
- Star manipulation detection is P2 unless user-account-level star event data is available.
- Dashboard scope must not block P0 runtime/report deliverables.

## Next Slice

S02 should convert these outcomes into architecture: storage, queues, collectors, model routing, report contract, dashboard endpoints, and migration/backfill strategy.

