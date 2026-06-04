# Architecture Design — AI Influence GitHub Trend & Action Analyzer Ultimate

**Knowledge Context**: solar-harness context inject used (Mirage + QMD + Solar DB — hit Tech Hotspot Radar project page, Evidence Atom concept, daily report 2026-05-24)

**Source PRD**: `/Users/lisihao/Knowledge/_raw/tech-hotspot-radar/github-project-intelligence/20260525-github-trend-action-analyzer-ultimate-prd.md`
**Supersedes**: V1 (github-project-intelligence PRD from 2026-05-24)

---

## 1. Design Intent

Upgrade the existing Tech Hotspot Radar GitHub pipeline (V1: "scan & report") into a closed-loop intelligence-action system (V3: "see → understand → act → review").

**Existing baseline** (from sprint `sprint-20260523-tech-hotspot-radar-productization`, 105/105 tests passing):
- `github_topics`, `github_repos`, `github_star_snapshots` tables
- 9 tracked repos + 9 topic seeds
- star delta (1d/7d/30d), 9 trend buckets, 7 alert rules
- README keyword matching, basic evidence atom

**Gap to close**: strategy track filtering, multi-tier source collection, deep semantic analysis, project intelligence cards, hard gates, strategy engine, charts, task candidates, feedback loop.

---

## 2. Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Layer 3: Internal Action Layer              │
│  Strategy Engine → Hard Gates → Task Candidates         │
│  → Feedback Loop → Jira/GitLab Draft Export             │
├─────────────────────────────────────────────────────────┤
│            Layer 2: Analytical Insight Layer             │
│  Evidence Atoms → Project Dossiers → Velocity/Anomaly   │
│  → Premium Reasoning → Decision Matrix                  │
├─────────────────────────────────────────────────────────┤
│           Layer 1: External Intelligence Layer           │
│  Strategy Tracks → Multi-Tier Collection → Snapshots    │
│  → GH Archive → X/YouTube Cross-Link → Internal Telem  │
└─────────────────────────────────────────────────────────┘
```

### 2.1 Layer 1: External Intelligence

**Responsibility**: Collect raw signals from GitHub and cross-source, filtered by strategy tracks.

**Components**:
- **Strategy Track Config** — YAML/db-backed track definitions (keywords, github_topics, languages, internal_capabilities, alert_threshold). 10 built-in tracks.
- **Multi-Tier Collector**:
  - Tier 0: `tracked_repos` (watched repos, 1-6h poll)
  - Tier 1: GitHub topic/search (daily)
  - Tier 2: GitHub Trending (daily)
  - Tier 3: GH Archive events (daily/weekly backfill)
  - Tier 4: X repo mentions (30-120min)
  - Tier 5: YouTube transcript mentions (daily)
  - Tier 6: Internal repo traffic (daily)
- **API Budget Manager** — REST/GraphQL rate limit tracking, secondary rate limit handling, per-tier quota allocation.
- **Snapshot Writer** — Append-only `repo_snapshots` with timestamp, star/fork/issue counts, commit activity.

**Data flow**:
```
strategy_tracks → collector tier selector → GitHub API / GH Archive / X RSS / YouTube
→ raw_events → dedup → repo_master upsert → repo_snapshots append
```

**Boundary**: Layer 1 only collects and stores. No semantic processing. Outputs are raw/structured snapshots.

### 2.2 Layer 2: Analytical Insight

**Responsibility**: Transform raw data into evidence-backed insights.

**Components**:
- **Velocity Engine** — Compute star_delta_1h/24h/7d/30d, acceleration, fork_delta from snapshot series.
- **Anomaly Detector** — Implement 5 detectors: `sudden_hot`, `early_potential`, `foundation_infra_candidate`, `cross_source_resonance`, `hype_zombie`.
- **Local Semantic Preprocessor** (ThunderOMLX + Qwen3.6):
  - Input: README, release notes, issue samples, PR samples
  - Output: Evidence Atom with fields: `project_positioning`, `core_technical_moat`, `main_user_pain_points`, `ecosystem_defects`, `community_health_summary`, `technical_risks`, `license_risks`
- **Project Intelligence Card** — Aggregated dossier per repo: metrics + evidence atoms + detector results.
- **Why-Hot Attribution** — Premium model reasoning packet explaining *why* a repo is trending.
- **Premium Gating** — Only high-score or cross-source repos enter premium reasoning.

**Data flow**:
```
repo_snapshots → velocity engine → metric scores
repo_master + snapshots → anomaly detector → detector flags
repo README/release/issue → local model → evidence_atoms
evidence_atoms + metrics + detector flags → project_dossier
high-value dossiers → premium model → why_hot_attribution
```

**Boundary**: Layer 2 produces structured insights and evidence. No action decisions.

### 2.3 Layer 3: Internal Action

**Responsibility**: Convert insights into actionable decisions with evidence tracking.

**Components**:
- **Hard Gate Engine** — Pre-LLM gates: license (SPDX normalization), IP/security, competitor/CLA check. Blocks action before strategy engine runs.
- **Strategy Engine** — Takes dossier + gate results → outputs machine-readable JSON decision:
  ```json
  {
    "decision": "contribute_existing",
    "confidence": 0.85,
    "recommended_action": "...",
    "technical_entry_point": "...",
    "risks": [],
    "task_candidates": [],
    "evidence_map": {}
  }
  ```
- **Decision types**: `build_new`, `contribute_existing`, `build_extension`, `feature_intake`, `boost_own_project`, `write_analysis`, `create_benchmark`, `watch`, `ignore`
- **Task Candidate Generator** — Maps decisions to task candidates with proper typing (Epic/Story/Task).
- **Feedback Loop** — Records human decisions, action outcomes, lessons learned. Feeds back into future strategy engine runs.

**Data flow**:
```
project_dossier → hard gates (license/IP/security)
  → BLOCKED → archive with rationale
  → PASS → strategy engine → decision JSON
    → task_candidate_generator → task_candidates table
    → human review → feedback_record → future weighting
```

**Boundary**: Layer 3 does not auto-create Jira/GitLab tasks. It produces `task_candidates` for human review.

---

## 3. Data Model (New & Extended Tables)

### 3.1 New Tables (on top of existing 23-table baseline)

| Table | Layer | Purpose |
|-------|-------|---------|
| `strategy_tracks` | L1 | Track config: keywords, topics, languages, internal_capabilities, alert_threshold |
| `repo_master` | L1 | Canonical repo record: full_name, description, language, license, archived, etc. |
| `repo_snapshots` | L1 | Append-only: star/fork/issue/commit counts per timestamp |
| `repo_events` | L1 | GH Archive events: PushEvent, WatchEvent, ReleaseEvent, etc. |
| `repo_context_snapshots` | L2 | README/release/issue/PR content snapshots |
| `repo_issue_samples` | L2 | Sampled open issues for pain point analysis |
| `repo_pr_samples` | L2 | Sampled recent PRs for community health |
| `repo_release_snapshots` | L2 | Release notes per version |
| `repo_social_mentions` | L1 | X/Twitter mentions linking to repos |
| `repo_youtube_mentions` | L1 | YouTube transcript mentions linking to repos |
| `repo_evidence_atoms` | L2 | Local model output per analysis batch |
| `repo_project_dossiers` | L2 | Aggregated project intelligence card |
| `repo_strategy_decisions` | L3 | Strategy engine output per repo per run |
| `repo_task_candidates` | L3 | Actionable task proposals |
| `repo_feedback` | L3 | Human decision / outcome / lessons learned |
| `license_policy` | L3 | SPDX license risk classification |
| `risk_gate_results` | L3 | Gate pass/fail records |
| `chart_datasets` | L3 | ECharts/Vega-Lite spec storage |
| `model_call_ledger` | L2 | Token/cost tracking for local + premium model calls |

### 3.2 Key Existing Tables (Retained)

| Table | Change |
|-------|--------|
| `github_repos` | Extend columns, becomes superset with `repo_master` or aliased |
| `github_star_snapshots` | Retained, feeds velocity engine |
| `github_topics` | Retained, linked to `strategy_tracks` |
| `hotspot_alerts` | Extended with new alert types from anomaly detectors |
| `evidence_atoms` | Retained for cross-source, `repo_evidence_atoms` is GitHub-specific |
| `reasoning_packets` | Retained, fed by `repo_project_dossiers` |
| `premium_reasoning_results` | Retained for why-hot attribution |
| `token_ledger` | Retained, extended with `model_call_ledger` |

### 3.3 Core Objects

**Repo Master** — `full_name` is primary key. Contains canonical metadata. All other tables reference via `repo_full_name`.

**Repo Snapshot** — Append-only. `UNIQUE(repo_full_name, snapshot_at)`. Supports time-series queries.

**Evidence Atom (GitHub)** — Structured local model output. Keyed by `(repo_full_name, analysis_batch_id)`. Contains `project_positioning`, `core_technical_moat`, `main_user_pain_points`, `ecosystem_defects`, `community_health_summary`, `technical_risks`, `license_risks`.

**Project Intelligence Card** — Materialized view / table joining metrics + evidence + detector results. Updated per pipeline run.

**Task Candidate** — `decision_type`, `repo_full_name`, `confidence`, `technical_entry_point`, `risks`, `evidence_ids[]`, `status` (draft/reviewed/approved/rejected).

---

## 4. Model Routing

| Route | Model | Use Case |
|-------|-------|----------|
| `github_evidence` | ThunderOMLX Qwen3.6 (local) | README/release/issue summarization, evidence atom extraction |
| `github_strategy` | Premium (opus-class) | Why-hot attribution, strategy decision reasoning |
| `github_cross_source` | Gemini-pro-class | Long-context cross-source correlation |
| `github_cheap` | Local Qwen3.6 | Dedup, entity extraction, keyword matching |

**Premium gating rule**: Only repos with `hot_score >= threshold` OR `cross_source_resonance == true` OR `detector in (sudden_hot, early_potential)` enter premium routing.

---

## 5. Visualization Architecture

### 5.1 Chart Specs

All charts output as JSON specs (ECharts or Vega-Lite), stored in `chart_datasets`.

**P0 Charts (3 required)**:
1. **Burst Quadrant** — X: velocity, Y: potential_score, size: star count, color: strategy track
2. **Pain Point Heatmap** — X: repo, Y: pain category, intensity: evidence frequency
3. **Action Matrix** — X: decision type, Y: repo, cell: confidence × evidence count

**P1 Charts (2 additional)**:
4. Community Power Topology — network graph of contributors/organizations
5. License/Risk Board — kanban-style risk classification

### 5.2 Report Templates

| Report | Format | Frequency | Recipient |
|--------|--------|-----------|-----------|
| Internal daily | Markdown | Daily | R&D team |
| Weekly review | Markdown + charts | Weekly | Engineering leads |
| AI Influence trend column | Markdown | Daily | Content team |

---

## 6. API Budget & Rate Limit Design

```
total_budget: 5000 req/h (GitHub REST)
               2000 points/min (GraphQL)

allocation:
  tier0_tracked: 40%
  tier1_search: 20%
  tier2_trending: 10%
  tier3_gh_archive: 10%
  tier4_social: 10%
  tier5_youtube: 5%
  tier6_internal: 5%

backoff: exponential with jitter
secondary_rate_limit: detect 403/abuse, pause 60s + backoff
```

---

## 7. Integration with Existing Tech Hotspot Radar

### 7.1 What Changes

- `github_repos` table gains columns for `license`, `language`, `archived`, `description`
- `github_star_snapshots` extended with `forks_count`, `open_issues_count`, `commit_count_7d`
- Alert engine gains 5 anomaly detector alert types
- New pipeline stages after existing N4 (GitHub pipeline)

### 7.2 What Stays

- Existing 23 tables untouched (new tables are additive)
- YouTube pipeline (N2) and Social pipeline (N3) unchanged
- Cross-source reporting (N5) gains GitHub enrichment but retains structure
- `tech-hotspot-radar` CLI entrypoint and `doctor` command extended, not replaced
- Test baseline `tests/test-tech-hotspot-radar.sh` extended with new test cases

### 7.3 Migration Path

- Phase 1: Add new tables (pure additive, no column changes to existing)
- Phase 2: Extend `github_repos` columns (backward compatible, NULL defaults)
- Phase 3: Update existing pipeline stages to use new schema

---

## 8. Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| GitHub API rate limit exhaustion | high | API budget manager with per-tier quotas and backoff |
| Local model quality insufficient for evidence atoms | medium | Fallback to premium model with cost tracking |
| Strategy engine outputs vague decisions | medium | Hard gate: reject any decision without `confidence`, `technical_entry_point`, `evidence_map` |
| Snapshot storage growth | low | Append-only with 90-day hot / 1-year warm / archive policy |
| PRD/DAG/contract drift | medium | Requirement IR as single source of truth, all views compiled |

---

## 9. P0 / P1 / P2 Scope Boundary

### P0 (This Sprint Focus)

- Strategy track config + 10 built-in tracks
- Multi-tier collector (Tier 0-2, Tier 4-5 stubs)
- Repo snapshot + velocity engine
- 5 anomaly detectors
- Local model evidence atom extraction
- Project intelligence card
- License hard gate
- Strategy engine v1 (9 decision types, machine-readable JSON)
- 3 core charts (burst quadrant, pain point heatmap, action matrix)
- Internal daily markdown report

### P1

- PR/issue community health metrics
- X/YouTube reverse discovery (Tier 4-5 full)
- GH Archive backfill (Tier 3)
- Contribution/new-project opportunity scoring
- Task candidate generation + Jira/GitLab draft export
- Human feedback loop
- 2 additional charts

### P2

- Community power topology
- Competitive matrix
- Track-level trend prediction
- Self-owned repo traffic analysis
- Auto issue/PR draft
- Legal/IP review workflow
- Monthly influence report

---

## 10. Architectural Decisions

1. **SQLite remains** — No migration to Postgres. Current 23-table baseline works. New tables are additive.
2. **Local-first preprocessing** — ThunderOMLX + Qwen3.6 handles all semantic extraction before premium model.
3. **Strategy tracks as filter** — Every collection must pass through track config. No unfiltered scanning.
4. **Hard gates before LLM** — License/IP/security checked programmatically before strategy engine.
5. **Machine-readable decisions** — All strategy outputs are JSON with required fields. No free-text-only outputs.
6. **Evidence-bound claims** — Every dossier judgment must reference `evidence_id`. No unsupported assertions.
7. **Task candidates, not tasks** — System proposes, human decides. No auto-creation of external tickets.
8. **Append-only snapshots** — All time-series data is append-only for auditability.
