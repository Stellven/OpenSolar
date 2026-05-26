# Design — S02 Architecture: GitHub Project Intelligence System

**Sprint**: `sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture`
**Epic**: `epic-20260524-p0-ai-influence-github-project-intelligence-system-upgrade`
**Status**: architecture (planner output, no code)
**Knowledge Context**: solar-harness context inject used

## System Layering

```
┌─────────────────────────────────────────────────────────────────────┐
│ L5: Report & Alert Layer                                           │
│   daily_report / weekly_report / alerts / HTML email embed         │
├─────────────────────────────────────────────────────────────────────┤
│ L4: Scoring & Detection Layer                                      │
│   heat_score / detectors / percentile_ranker / alert_rules         │
├─────────────────────────────────────────────────────────────────────┤
│ L3: Analysis & Evidence Layer                                      │
│   evidence_atoms / reasoning_packets / analysis_cards / briefs     │
│   model_call_ledger / ThunderOMLX local preprocessing              │
├─────────────────────────────────────────────────────────────────────┤
│ L2: Snapshot & Delta Layer                                         │
│   repo_snapshots (append-only) / delta computation / acceleration  │
│   percentile buckets (age × star band × topic)                     │
├─────────────────────────────────────────────────────────────────────┤
│ L1: Discovery & Ingestion Layer                                    │
│   topic_adapter / trending_adapter / tracked_adapter / cross_source│
│   dedup / queue / repo_master                                      │
├─────────────────────────────────────────────────────────────────────┤
│ L0: Storage & Schema Layer                                         │
│   SQLite (tech-hotspot-radar.sqlite) / migration / schema v2       │
└─────────────────────────────────────────────────────────────────────┘
```

**Control plane**: cron-driven daily pipeline (00:00–08:00), detector triggers, alert dispatch.
**Data plane**: append-only snapshots → delta computation → evidence atoms → reasoning packets → analysis cards → reports.

---

## Architecture Decisions

### A1: Discovery Pipeline — 4 Source Adapters + Queue

**Decision**: Each discovery path is a stateless adapter implementing `DiscoveryAdapter` protocol. Adapters push candidates into a dedup queue backed by `repo_master` table.

**Adapter interface**:
```
DiscoveryAdapter.run(since: datetime) → list[DiscoveryCandidate]
  - candidate fields: full_name, source_type, discovered_at, metadata
  - source_type: topic | trending | tracked | social_mention | youtube_mention

DedupQueue.enqueue(candidates) → list[str]  # returns new full_names only
  - checks repo_master.full_name + source_type uniqueness
  - new repos → INSERT into repo_master with tracking_status='candidate'
  - existing repos → UPDATE last_seen_at only
```

**4 adapters**:
1. `TopicAdapter`: query GitHub Search API per topic (12 initial topics), filter by star band and recency
2. `TrendingAdapter`: scrape GitHub Trending daily/weekly/monthly pages, normalize into candidates
3. `TrackedAdapter`: read tracked repo list from config, check last_seen_at freshness
4. `CrossSourceAdapter`: scan social/X posts and YouTube transcripts for `github.com/owner/repo` mentions, extract repo full_name + mention metadata

**Dedup rule**: `(full_name, source_type)` is the dedup key within a 24h window. A repo can appear in multiple source_types (e.g., both trending and topic), each recorded as a separate discovery event.

**Failure mode**: Adapter failure → log + skip, do not block other adapters. Each adapter has independent rate limit and retry budget.

**Why separate adapters**: Each source has different API shape, rate limit, and authentication. Monolithic scraper would couple failure domains.

### A2: Append-Only Snapshot Store with Delta Computation

**Decision**: `repo_snapshots` table is append-only. Each run INSERTs a new row per repo; never UPDATE or DELETE. Delta computation runs as a post-insertion SQL aggregation.

**Snapshot schema** (extends existing):
```
repo_snapshots:
  snapshot_id    TEXT PRIMARY KEY  -- '{full_name}#{ISO_ts}'
  full_name      TEXT NOT NULL
  snapshot_at    TEXT NOT NULL     -- ISO-8601 UTC
  stars          INTEGER
  forks          INTEGER
  watchers       INTEGER
  open_issues    INTEGER
  commit_count_7d        INTEGER
  active_contributors_30d INTEGER
  latest_release_tag     TEXT
  latest_release_at      TEXT
  pushed_at              TEXT
  -- deltas computed post-insert
  stars_delta_1h   INTEGER
  stars_delta_6h   INTEGER
  stars_delta_24h  INTEGER
  stars_delta_7d   INTEGER
  stars_delta_30d  INTEGER
  forks_delta_24h  INTEGER
  issues_delta_24h INTEGER
  prs_delta_24h    INTEGER
  -- acceleration
  star_acceleration REAL  -- stars_delta_24h / max(avg_stars_delta_24h_last_7d, 1)
  history_status   TEXT   -- 'sufficient' | 'insufficient_history'
```

**Delta computation strategy**:
- After batch INSERT, run SQL window functions: `LAG(stars, 1) OVER (PARTITION BY full_name ORDER BY snapshot_at)` for each delta window
- For 1h delta: match snapshot within ±1h window. For 30d: match within ±30d window.
- If no matching historical snapshot exists → `history_status = 'insufficient_history'`, deltas set NULL

**Percentile buckets**:
- Precompute percentile distributions for `(topic, age_bucket, star_bucket)` combinations
- Age buckets: 0-7d, 8-30d, 31-180d, 181-365d, 365d+
- Star buckets: 0-100, 101-500, 501-2k, 2k-10k, 10k+
- Stored in `snapshot_percentiles` materialized table, refreshed after each snapshot batch

**Migration from existing**: Existing `tech-hotspot-radar.sqlite` tables remain untouched. New tables use same DB file with `schema_v2` prefix in migration_log.

### A3: ThunderOMLX Evidence Compression Pipeline

**Decision**: ThunderOMLX + Qwen3.6 runs as local preprocessing layer on Mac mini M4. It produces evidence atoms before any premium model call. Premium models only consume `project_reasoning_packet` (compressed), never raw content.

**Evidence atom schema**:
```
repo_evidence_atoms:
  evidence_id    TEXT PRIMARY KEY  -- 'ev-{full_name_hash}-{type}-{seq}'
  full_name      TEXT NOT NULL
  source         TEXT              -- 'thunderomlx-qwen3.6' | 'api' | 'manual'
  evidence_type  TEXT NOT NULL     -- readme_claim|release_signal|issue_signal|pr_signal|social_mention|youtube_mention|growth_signal
  raw_ref        TEXT              -- URL or reference to original content
  one_sentence_summary TEXT
  compressed_content TEXT          -- ≤500 chars per atom
  entities       TEXT              -- JSON array of extracted entities
  topic_tags     TEXT              -- JSON array of topic tags
  importance_score    REAL         -- 0-100
  technical_depth_score REAL       -- 0-100
  novelty_score       REAL         -- 0-100
  confidence          REAL         -- 0-1
  created_at          TEXT
```

**Pipeline stages**:
1. **README cleaning**: Strip boilerplate, extract core claims → `readme_claim` atoms
2. **Release compression**: Summarize latest N releases → `release_signal` atoms
3. **Issue/PR summary**: Top N issues/PRs → `issue_signal` / `pr_signal` atoms
4. **Social extraction**: X posts mentioning repo → `social_mention` atoms
5. **YouTube extraction**: Transcript timestamps with repo mentions → `youtube_mention` atoms
6. **Growth signal**: Delta + acceleration metadata → `growth_signal` atoms
7. **Wrapper detection**: Classify repo as wrapper/original/infra → set `technical_depth_score`
8. **Low-value filtering**: Discard atoms with `importance_score < 20`

**Reasoning packet schema**:
```
project_reasoning_packets:
  packet_id      TEXT PRIMARY KEY
  full_name      TEXT NOT NULL
  created_at     TEXT
  metrics        TEXT              -- JSON: current snapshot stats
  local_project_brief TEXT         -- ≤1000 chars summary from evidence atoms
  growth_evidence     TEXT         -- JSON array of growth_signal atom IDs
  readme_evidence     TEXT         -- JSON array of readme_claim atom IDs
  release_evidence    TEXT         -- JSON array of release_signal atom IDs
  social_evidence     TEXT         -- JSON array of social_mention atom IDs
  youtube_evidence    TEXT         -- JSON array of youtube_mention atom IDs
  questions_for_reasoner TEXT      -- JSON array of questions premium model should address
```

**Model call ledger**:
```
model_call_ledger:
  call_id        TEXT PRIMARY KEY
  full_name      TEXT
  model_name     TEXT              -- 'qwen3.6-thunderomlx' | 'gemini-pro' | 'claude-opus' | 'codex'
  call_type      TEXT              -- 'preprocess' | 'reasoning' | 'verification' | 'editorial'
  input_tokens   INTEGER
  output_tokens  INTEGER
  cost_estimate  REAL
  created_at     TEXT
```

**Routing**: Local Qwen3.6 for all preprocessing + verification. Gemini Pro for long-context synthesis. Claude Opus for editorial polish only when explicitly requested. Codex for architecture analysis.

### A4: Project Intelligence Card & Planning Brief Schemas

**Decision**: Two linked schemas — analysis card for project assessment, planning brief for product opportunity. Both reference evidence atoms by ID, ensuring every claim is traceable.

**Analysis card schema**:
```
repo_analysis_cards:
  analysis_id              TEXT PRIMARY KEY  -- 'ac-{full_name_hash}-{date}'
  full_name                TEXT NOT NULL
  analysis_date            TEXT NOT NULL
  project_positioning      TEXT              -- 1-2 sentence positioning
  what_it_does             TEXT              -- ≤200 chars
  target_users             TEXT              -- JSON array of user segments
  core_technical_idea      TEXT              -- ≤200 chars
  why_it_is_hot            TEXT              -- narrative explanation
  potential_score          REAL              -- 0-100
  heat_score               REAL              -- 0-100 (from L4 scoring)
  technical_depth_score    REAL              -- 0-100
  community_health_score   REAL              -- 0-100
  strategic_relevance_score REAL             -- 0-100
  trend_implication        TEXT              -- narrative
  product_planning_ideas   TEXT              -- JSON array of idea strings
  research_questions       TEXT              -- JSON array of question strings
  risks                    TEXT              -- JSON array of risk objects {type, description, severity}
  watch_next               TEXT              -- JSON array of action items
  evidence_ids             TEXT              -- JSON array of evidence_id references
  model_used               TEXT              -- which model produced this card
  verified                 INTEGER DEFAULT 0 -- local verifier pass flag
```

**Planning brief schema**:
```
repo_planning_briefs:
  brief_id                 TEXT PRIMARY KEY  -- 'pb-{full_name_hash}-{date}'
  full_name                TEXT NOT NULL
  analysis_id              TEXT              -- FK to analysis card
  opportunity_summary      TEXT
  user_pain_points         TEXT              -- JSON array
  target_personas          TEXT              -- JSON array
  proposed_product         TEXT
  mvp_scope                TEXT
  technical_architecture   TEXT
  go_to_market             TEXT
  risks                    TEXT              -- JSON array
  validation_metrics       TEXT              -- JSON array of measurable criteria
  next_steps               TEXT              -- JSON array
```

**Constraint**: An analysis card cannot be created without at least 3 evidence_ids. A planning brief cannot be created without a verified analysis card. This prevents premium model calls on thin evidence.

### A5: Heat Scoring & Detector Framework

**Decision**: Composite heat score is a weighted sum of 8 normalized sub-scores. Detectors are stateless functions that evaluate detection rules against snapshot + evidence data and produce tagged alerts.

**Heat score formula**:
```
repo_heat_score = 0.30 * star_velocity_score
                + 0.15 * star_acceleration_score
                + 0.15 * cross_source_signal_score
                + 0.10 * release_signal_score
                + 0.10 * community_activity_score
                + 0.10 * topic_relevance_score
                + 0.05 * maintainer_signal_score
                + 0.05 * novelty_score
```

Each sub-score is normalized to [0, 100] within its `(topic, age_bucket, star_bucket)` percentile group before weighting.

**Acceleration interpretation**:
| Range | Label | Action |
|-------|-------|--------|
| <1.5x | normal | no alert |
| 1.5x-3x | warming | log |
| 3x-8x | breakout | alert medium |
| >8x | sudden_hot | alert high |
| >20x | anomaly | alert high + attribution required |

**Detector interface**:
```
Detector.detect(repo: str, snapshot: RepoSnapshot, evidence: list[EvidenceAtom]) → list[Detection]
  - Detection: {detector_name, repo, severity, title, evidence_ids, details}
```

**Required detectors**:
1. `sudden_hot`: star_acceleration > 8x → high severity
2. `early_potential`: potential_score > 85 AND stars < 2000 → medium severity
3. `foundation_infra_candidate`: technical_depth_score + community_health_score > 160 → info
4. `hype_or_noise`: high heat but low technical_depth_score (< 30) → medium, tag as potential wrapper
5. `star_manipulation_suspicion`: star_velocity > 95th percentile + low community_activity → high, flag for review
6. `major_release_signal`: new release tag + release_signal evidence + star_acceleration > 2x → medium
7. `cross_source_resonance`: repo appears in ≥3 source types within 24h → medium

**Alert rules** (feed into alert table):
- High: tracked repo 24h growth >10%, repo enters topic Top 3, potential_score >85 AND stars <2000, X+YouTube+Trending all hit
- Medium: major release, star manipulation suspicion, strong topic relevance
- Low: normal updates, warming acceleration

### A6: Report Generation Pipeline

**Decision**: Reports are generated by composing analysis cards + detector outputs + trend summaries into structured templates. Daily reports run 07:00-08:00 UTC after all analysis is complete. Weekly reports aggregate daily reports for Mon-Sun.

**Report template schemas**:

```
daily_reports:
  report_date     TEXT PRIMARY KEY  -- 'YYYY-MM-DD'
  core_judgment   TEXT              -- 1-3 sentence summary of the day
  sudden_hot      TEXT              -- JSON array of {repo, heat_score, why_hot}
  early_potential TEXT              -- JSON array of {repo, potential_score, positioning}
  tech_radar      TEXT              -- JSON array of {trend, repos, direction}
  community_signals TEXT            -- JSON array of {source, repo, signal_type}
  planning_suggestions TEXT         -- JSON array of {repo, suggestion, priority}
  watchlist       TEXT              -- JSON array of {repo, reason, next_check}
  generated_at    TEXT
  model_used      TEXT

weekly_reports:
  week_start      TEXT PRIMARY KEY  -- Monday date
  one_sentence    TEXT
  top5_trends     TEXT              -- JSON array
  top10_projects  TEXT              -- JSON array
  deep_analysis   TEXT              -- JSON array of full analysis cards
  tech_route_abstraction TEXT       -- narrative
  planning_pool   TEXT              -- JSON array
  next_week_metrics TEXT            -- JSON array of specific metrics to watch
  generated_at    TEXT
```

**Report generation flow**:
1. Query today's analysis cards, ordered by heat_score descending
2. Run detectors to populate alert table
3. Compose sections using template engine (Jinja2)
4. Local Qwen3.6 verifies factual consistency (claims vs evidence_ids)
5. Optional: Gemini Pro for long-context trend synthesis (Top 5 trends)
6. Render to HTML compatible with AI Influence email format
7. Archive to `reports/` directory and insert into report tables

**Standard project analysis template** (used in both daily and weekly):
1. One-sentence judgment
2. Project positioning
3. Why it's hot (with why-hot attribution from evidence)
4. Core technology
5. Real pain points solved
6. Ecosystem relation
7. Potential judgment
8. Risks (with wrapper/hype/license/security flags)
9. AI Influence insights
10. Planning suggestions

---

## Interface Contracts

### Internal APIs (Python function signatures for S03 builder reference)

```
# L1: Discovery
def run_discovery(since: datetime) -> int  # returns new repo count
def enqueue_candidates(candidates: list[dict]) -> list[str]

# L2: Snapshots
def take_snapshot(full_name: str) -> dict
def compute_deltas(full_name: str, snapshot_at: str) -> dict
def compute_percentiles(topic: str, date: str) -> dict

# L3: Evidence
def compress_readme(full_name: str) -> list[dict]  # returns evidence atoms
def compress_releases(full_name: str) -> list[dict]
def build_reasoning_packet(full_name: str) -> dict
def log_model_call(call: dict) -> str

# L4: Scoring
def compute_heat_score(full_name: str, snapshot: dict, evidence: list) -> float
def run_detectors(full_name: str) -> list[dict]
def check_alert_rules(detections: list[dict]) -> list[dict]

# L5: Reports
def generate_daily_report(date: str) -> dict
def generate_weekly_report(week_start: str) -> dict
def render_report_html(report: dict, template: str) -> str
```

### Storage Contract

- All tables live in `tech-hotspot-radar.sqlite` (existing file, schema extended via migration)
- New tables: `repo_evidence_atoms`, `project_reasoning_packets`, `repo_analysis_cards`, `repo_planning_briefs`, `model_call_ledger`, `daily_reports`, `weekly_reports`, `snapshot_percentiles`, `alerts`
- Migration adds tables; never drops or renames existing columns
- All timestamps are ISO-8601 UTC strings

---

## Failure Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| GitHub API rate limit | HTTP 403/429 | Exponential backoff, resume from watermark |
| ThunderOMLX OOM | Process exit code | Skip repo, mark as `preprocess_failed`, retry next cycle |
| SQLite write contention | `SQLITE_BUSY` | WAL mode + retry with jitter |
| Snapshot batch partial failure | Missing snapshots for expected repos | Log gaps, next cycle fills |
| Premium model timeout | HTTP timeout | Fall back to local-only analysis card |
| Detector crash | Python exception | Log + skip detector, other detectors continue |

---

## Compatibility & Migration

- **Existing tables**: No schema changes to current tables. All new tables are additive.
- **Existing pipeline**: Daily snapshot cron continues unchanged. New pipeline runs in parallel, reading from same `repo_snapshots`.
- **Backward compat**: Existing Tech Hotspot Radar HTML output continues to work. New AI Influence reports are additive.
- **Config format**: Discovery topics and tracked repos stored in `github_intelligence_config.yaml` (new file), not embedded in code.

---

## Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R1 | ThunderOMLX preprocessing too slow for 500+ repos/day | Pipeline overruns 04:00 window | Batch by priority (tracked > sudden_hot > trending > topic); skip repos with no delta change |
| R2 | SQLite concurrent writes from snapshot + evidence pipelines | Data corruption | WAL mode + single writer connection |
| R3 | GitHub API rate limit caps discovery at ~1000 repos/cycle | Incomplete coverage | Prioritize tracked + trending; topic discovery samples top-N per query |
| R4 | Premium model cost for Top-10 weekly analysis | Budget overrun | Hard cap: max 20 premium calls/day; model_call_ledger enforces |
| R5 | Evidence atoms inconsistent with raw content | Hallucinated claims | Local verifier checks claim against compressed_content before card creation |
| R6 | Snapshot delta computation slow for repos with >1000 snapshots | Query timeout | Index on (full_name, snapshot_at); archive snapshots older than 90 days to separate table |
