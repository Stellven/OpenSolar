# Plan — S02 Architecture: GitHub Project Intelligence System

**Sprint**: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture`
**Epic**: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`

Knowledge Context: solar-harness context inject used

## Parallelization

### Batch 1 (parallel, no dependencies)
- **B1**: Schema migration — Extend `tech-hotspot-radar.sqlite` with 9 new tables
- **B2**: Config schema — `github_intelligence_config.yaml` with topics + tracked repos

### Batch 2 (depends on B1)
- **B3**: Discovery adapters — 4 adapter implementations (topic, trending, tracked, cross-source)
- **B4**: Snapshot delta engine — Append-only INSERT + delta computation SQL
- **B5**: Percentile ranker — Age × star × topic bucket computation

### Batch 3 (depends on B3, B4)
- **B6**: Evidence compression pipeline — ThunderOMLX + Qwen3.6 preprocessing
- **B7**: Reasoning packet builder — Compose packets from evidence atoms
- **B8**: Model call ledger — Track all model invocations

### Batch 4 (depends on B6, B7, B4)
- **B9**: Heat scoring engine — 8-subscore weighted formula + normalization
- **B10**: Detector framework — 7 detector implementations
- **B11**: Alert dispatcher — Alert rules + alert table writes

### Batch 5 (depends on B9, B10, B7)
- **B12**: Analysis card generator — Create cards from evidence + scoring
- **B13**: Planning brief generator — Create briefs from verified cards

### Batch 6 (depends on B12, B13, B10)
- **B14**: Daily report generator — Template composition + HTML rendering
- **B15**: Weekly report generator — Aggregation + deep analysis + HTML rendering

### Batch 7 (depends on all above)
- **B16**: Pipeline orchestrator — Cron-driven daily pipeline 00:00-08:00 UTC
- **B17**: Integration test — End-to-end pipeline test with sample data

## Write Scope Boundaries

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| B1 | `lib/github_intelligence/schema.py` | `tech-hotspot-radar.sqlite` |
| B2 | `config/github_intelligence_config.yaml` | — |
| B3 | `lib/github_intelligence/adapters/` | config, `repo_master` table |
| B4 | `lib/github_intelligence/snapshots.py` | `repo_snapshots` table |
| B5 | `lib/github_intelligence/percentiles.py` | `repo_snapshots`, `snapshot_percentiles` |
| B6 | `lib/github_intelligence/evidence.py` | ThunderOMLX API, `repo_evidence_atoms` |
| B7 | `lib/github_intelligence/packets.py` | `repo_evidence_atoms`, `project_reasoning_packets` |
| B8 | `lib/github_intelligence/model_ledger.py` | `model_call_ledger` |
| B9 | `lib/github_intelligence/scoring.py` | `repo_snapshots`, `snapshot_percentiles` |
| B10 | `lib/github_intelligence/detectors.py` | scoring output, evidence atoms |
| B11 | `lib/github_intelligence/alerts.py` | detector output, `alerts` table |
| B12 | `lib/github_intelligence/cards.py` | reasoning packets, scoring, `repo_analysis_cards` |
| B13 | `lib/github_intelligence/briefs.py` | verified cards, `repo_planning_briefs` |
| B14 | `lib/github_intelligence/reports/daily.py` | cards, detectors, `daily_reports` |
| B15 | `lib/github_intelligence/reports/weekly.py` | daily reports, cards, `weekly_reports` |
| B16 | `lib/github_intelligence/pipeline.py` | all modules |
| B17 | `tests/test_github_intelligence.py` | all modules |

## Verification Commands

```bash
# Schema migration
python3 -c "from lib.github_intelligence.schema import migrate; migrate(); print('OK')"

# Discovery adapters (dry-run)
python3 -c "from lib.github_intelligence.adapters.topic import TopicAdapter; print(TopicAdapter.__doc__)"

# Snapshot delta
python3 -c "from lib.github_intelligence.snapshots import compute_deltas; print('OK')"

# Heat scoring
python3 -c "from lib.github_intelligence.scoring import compute_heat_score; print('OK')"

# Full pipeline smoke test
python3 -m pytest tests/test_github_intelligence.py -v
```

## Stop Rules

- Missing `task_graph.json` → do not dispatch builder
- Schema migration fails → do not proceed to B3+
- Evidence pipeline crash → skip repo, do not block other repos
- Premium model timeout → fall back to local-only analysis, do not hang pipeline

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation Node |
|------|-----------|--------|----------------|
| SQLite migration breaks existing tables | Low | Critical | B1 must test migration on copy first |
| GitHub API rate limit | High | Medium | B3 adapters implement backoff + watermark |
| ThunderOMLX OOM on large README | Medium | Low | B6 caps input at 50K chars |
| Premium model budget overrun | Medium | Medium | B8 enforces daily call cap |
| Snapshot table growth | High | Low | B4 archives >90d snapshots |
