# Sprint Handoff — sprint-20260523-tech-hotspot-radar-productization

## Summary

Productization sprint for Tech Hotspot Radar: unified SQLite-based pipeline for YouTube/Social/GitHub tech hotspot scanning with evidence-based reasoning, cross-source reporting, and Knowledge integration. 7 DAG nodes (N1, N1B, N2, N3, N4, N5, N6) all marked reviewing. 105/105 tests passing.

## Nodes

| Node | Status | Summary |
|------|--------|---------|
| N1_data_foundation | reviewing | 23 SQLite tables, config YAML (50 channels, 151 accounts, 9 topics), init/status/doctor/seed CLI |
| N1B_local_reasoning_engine | reviewing | 6 reasoning tables, model router, budget trimming, premium gating, 6 fixture commands |
| N2_youtube_pipeline | reviewing | YouTube adapter: normalization, dedup, snapshots, transcript txt/jsonl, retry queue, hot score, evidence atoms |
| N3_social_pipeline | reviewing | Social adapter: event classifier, duplicate clustering, hot score, gap report, structured claim evidence atoms |
| N4_github_pipeline | reviewing | GitHub adapter: trend bucket classifier, star delta computation, alerts, readme_brief evidence atoms |
| N5_cross_source_reporting | reviewing | Cross-source reports, unified overview, alerts JSON/MD, HTML, transcript package, wiki dispatch |
| N6_release_verification | reviewing | Documentation, CLI verification, 105/105 tests, backward compatibility verified |

## Key Files

### New Files
- `config/tech-hotspot-radar.yaml` — Unified config (50 YouTube channels, 151 social accounts, 9 GitHub topics/repos)
- `scripts/tech_hotspot_radar.py` — Unified CLI (~1800 lines, 14 commands, 23 tables)
- `tests/test-tech-hotspot-radar.sh` — Test suite (27 test groups, 105 assertions)
- `docs/tech-hotspot-radar.md` — CLI reference and documentation

### Existing Files (unchanged)
- `scripts/youtube_influence_digest.py` — Backward compatible
- `scripts/ai_influence_daily.py` — Backward compatible
- `scripts/github_trends_digest.py` — Backward compatible

## Database Schema

23 SQLite tables:
- YouTube: youtube_channels, youtube_videos, youtube_video_snapshots, youtube_transcripts
- Social: social_accounts, social_posts, social_post_snapshots, social_clusters
- GitHub: github_topics, github_repos, github_star_snapshots
- Cross-source: hotspot_events, cross_source_links, hotspot_alerts
- Pipeline: pipeline_runs, retry_queue
- Reasoning: evidence_atoms, hotspot_clusters, reasoning_packets, premium_reasoning_results, insight_verifications, token_ledger
- Metadata: _meta

## Hot Score Formulas

- **YouTube**: 0.30·view_velocity + 0.20·engagement_velocity + 0.20·channel_weight + 0.15·semantic_importance + 0.10·novelty + 0.05·cross_source
- **Social**: 0.25·engagement_velocity + 0.20·account_weight + 0.20·semantic_importance + 0.15·network_spread + 0.10·novelty + 0.10·cross_source
- **GitHub**: 0.30·star_growth + 0.20·recent_activity + 0.15·release_signal + 0.15·semantic_relevance + 0.10·social_cross + 0.10·maintainer_quality

## Evidence Atom Types

- `transcript_chunk` (YouTube) — Compressed transcript evidence
- `post_brief` (Social) — Structured claim extraction from social posts
- `readme_brief` (GitHub) — Repo technical brief with trend bucket

## Output Artifacts

Written to `Knowledge/_raw/tech-hotspot-radar/YYYY-MM-DD/`:
- 3 source-specific Markdown reports
- Unified daily overview (今日科技热点总览)
- Alerts JSON + MD
- Transcript JSONL package
- Gmail-safe HTML report
- Wiki ingest dispatch

## Test Evidence

```
bash tests/test-tech-hotspot-radar.sh
=== Results: 105 passed, 0 failed ===
```

## Rollback

```bash
rm -f ~/.solar/harness/state/tech-hotspot-radar/tech-hotspot-radar.sqlite
rm -rf ~/Knowledge/_raw/tech-hotspot-radar/
rm -f ~/Solar/harness/config/tech-hotspot-radar.yaml
rm -f ~/Solar/harness/docs/tech-hotspot-radar.md
rm -f ~/Solar/harness/scripts/tech_hotspot_radar.py
rm -f ~/Solar/harness/tests/test-tech-hotspot-radar.sh
# Existing scripts remain untouched
```

## Not Done

- Real API integration (YouTube RSS, X/Twitter, GitHub API)
- Email sending for daily reports
- Automated cron schedule setup
- Wiki ingest processing
- Production data migration from existing digest scripts
- LLM-based event classification (currently keyword matching)
- Entity-based cross-source linking (currently URL-only)
