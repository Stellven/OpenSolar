# PRD — Solar DeepResearch Professor-Grade Survey

## Goal

Enable Solar-Harness to produce professor-grade 5-10 万字 professional survey reports through a structured, reviewable, evidence-backed pipeline instead of one-shot long generation.

## Current State

```text
┌──────────────────────────────┬────────┬────────────────────────────────────┐
│ Capability                   │ Status │ Evidence                           │
├──────────────────────────────┼────────┼────────────────────────────────────┤
│ Evidence ledger              │ ok     │ sources/evidence/claims JSONL       │
│ Citation/factuality gate      │ ok     │ eval-artifacts PASS                 │
│ Source profile audit          │ ok     │ source-audit strict PASS            │
│ Technical template density    │ ok     │ warnings=[] after gate ledger fix   │
│ Survey-scale ReportAST        │ error  │ only 1 chapter / 5 sections         │
│ Section evidence packs        │ error  │ absent                              │
│ Revision loop                 │ error  │ absent                              │
│ Global consistency review     │ error  │ absent                              │
│ Professor-grade scorecard     │ error  │ absent                              │
└──────────────────────────────┴────────┴────────────────────────────────────┘
```

## User Need

The user wants DeepResearch to support high-quality technical survey writing:

- not garbage summaries,
- not shallow source stitching,
- not fake "passed" status,
- usable for serious architecture research,
- optionally human-in-the-loop for external search to avoid paid API lock-in.

## Product Requirements

1. A large survey is decomposed into chapters and sections before writing.
2. Every section has a local evidence pack.
3. Every factual claim in final text is backed by evidence IDs.
4. Review happens at section, chapter, and global levels.
5. Weak evidence blocks writing, not just emits a warning.
6. The user can inspect artifacts and continue/repair failed sections.
7. The system can run with local/human-provided search results.

## Non-Goals

- Do not build a cloud SaaS research system.
- Do not require paid search APIs for MVP.
- Do not replace QMD/Mirage/Obsidian.
- Do not rewrite the main harness control plane.

## Definition of Ready

- Contract, design, plan, and task graph exist.
- Package boundary is explicit.
- Test fixtures do not require network.
- Existing DeepResearch path remains compatible.

