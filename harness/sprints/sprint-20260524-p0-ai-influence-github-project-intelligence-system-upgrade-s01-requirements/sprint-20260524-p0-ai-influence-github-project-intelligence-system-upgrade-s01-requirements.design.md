# Design: AI Influence GitHub Project Intelligence Requirements Slice

epic_id: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`
sprint_id: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s01-requirements`
source_prd: `/Users/lisihao/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/20260524-github-project-intelligence-prd.md`

## 1. Positioning

This sprint freezes the requirements contract for upgrading the current Tech Hotspot Radar GitHub module from a basic repo snapshot/trending collector into an open-source project intelligence system.

The target product is not a GitHub Trending mirror. It must discover, explain, score, and convert open-source signals into AI Influence report assets:

- project discovery
- growth anomaly detection
- project technical intelligence
- why-hot attribution
- project analysis cards
- planning briefs
- GitHub daily/weekly report sections
- alerts and cost/provenance ledger

## 2. Current Gap

Current implementation is materially below the requested system:

| Area | Current | Required |
|---|---|---|
| Data source | basic topics/tracked repos | official API + Trending + cross-source mentions + GH Archive-ready |
| Metrics | stars snapshot only | 1h/6h/24h/7d/30d deltas and acceleration |
| Intelligence | simple evidence atoms | project cards, why-hot attribution, planning briefs |
| Cross-source | partial | X + YouTube mention discovery and scoring |
| Model usage | shallow local summary | ThunderOMLX/Qwen3.6 evidence compression before premium reasoning |
| Output | generic report block | AI Influence GitHub daily/weekly intelligence report |
| Controls | weak | ledger, provenance, alerts, noise/risk checks |

## 3. Requirement Outcomes

### O1: Discovery Coverage

The system must discover repos through four entry points:

- topic discovery
- GitHub Trending discovery
- tracked repo monitoring
- cross-source mention discovery from X and YouTube transcripts

Acceptance:

- 12 initial topics are represented in config or DB.
- tracked repos are imported.
- Trending daily/weekly/monthly is modeled as a discovery source.
- social/youtube repo URLs can create repo candidates.

Risk boundary:

- GH Archive BigQuery backfill is P2 unless an available credential and budget are confirmed.

### O2: Snapshot And Delta Ledger

The system must preserve repo history and compute growth deltas.

Acceptance:

- repo snapshots are append-only.
- 1h/6h/24h/7d/30d deltas are computed or marked `insufficient_history`.
- star acceleration is computed against a 7-day baseline.
- snapshots are bucketed by topic, repo age, and star band for percentile scoring.

Risk boundary:

- Historical deltas cannot be fabricated when no baseline exists.

### O3: Local Evidence Compression

ThunderOMLX + Qwen3.6 must be the default local preprocessing layer for README/release/issues/PR/social/youtube GitHub evidence.

Acceptance:

- repo evidence atoms are generated before premium reasoning.
- each evidence atom has a raw reference, evidence type, compressed content, entities, tags, and confidence.
- premium models receive project reasoning packets, not raw README dumps.
- model calls are written to a ledger.

Risk boundary:

- QMD remains deterministic indexing; ThunderOMLX is not the embedding backend.

### O4: Project Intelligence Cards

Each high-value repo must produce a project analysis card and optional planning brief.

Acceptance:

- analysis card includes positioning, what it does, target users, core technical idea, why-hot facts, scores, trend implication, risks, watch_next, evidence_ids.
- planning brief includes opportunity, user pain, MVP, architecture, go-to-market, risks, validation metrics.
- wrapper/hype/license/security risk is explicitly represented.

Risk boundary:

- The system must not label a repo as infrastructure without technical-depth and community-health evidence.

### O5: Scoring And Detectors

The module must distinguish heat, potential, and noise.

Acceptance:

- repo_heat_score is computed with velocity, acceleration, cross-source, release, community, relevance, maintainer, and novelty components.
- potential_score is computed separately.
- sudden_hot, early_potential, foundation_infra_candidate, hype, and possible_star_manipulation detectors exist.
- alerts are emitted for configured thresholds.

Risk boundary:

- total stars alone cannot trigger a high-severity alert.

### O6: AI Influence Outputs

The GitHub module must generate report-ready intelligence, not raw lists.

Acceptance:

- daily report has core judgment, sudden-hot projects, early-potential projects, technical radar, community propagation signals, planning suggestions, watchlist.
- weekly report has top trends, top projects, deep project analysis, technical route abstraction, planning pool, next-week metrics.
- output can be embedded into the unified AI Influence HTML email.

Risk boundary:

- A report with only repo names/stars is not accepted.

## 4. Downstream Slice Mapping

| Slice | Owner Goal | Required Inputs From S01 |
|---|---|---|
| S02 Architecture | define storage, queues, model routing, report and dashboard interfaces | O1-O6, data model, stop rules |
| S03 Core Runtime | implement collectors, snapshots, scoring, atoms, cards, briefs | schemas and detector definitions |
| S04 Orchestration/UI | web UI, report blocks, scheduler, alerts, config | user-facing output and controls |
| S05 Verification | tests, fixtures, replay, report quality gates | acceptance matrix and risk boundaries |

## 5. Non-Goals

- Do not replace QMD embedding with ThunderOMLX.
- Do not directly ship a full implementation inside S01.
- Do not claim 6-month GitHub/GH Archive baseline is complete without actual collected data.
- Do not let premium models consume raw full README/release/issues by default.

