# Design — Tech Hotspot Radar

## Design Choice

Use an adapter-and-normalized-store architecture. Existing source-specific scripts remain usable, but Phase 1 introduces a unified `tech_hotspot_radar.py` layer and a shared SQLite state store so reports, cross-source links, alerts, status, doctor, and knowledge ingestion are consistent.

## Components

```text
┌─────────────────────────────┬──────────────────────────────────────────────┐
│ component                   │ responsibility                               │
├─────────────────────────────┼──────────────────────────────────────────────┤
│ config/tech-hotspot-radar   │ seed lists, schedule, scoring weights         │
│ tech_hotspot_radar.py       │ CLI, DB init, orchestration, status/doctor    │
│ youtube adapter             │ channels, videos, snapshots, transcript       │
│ social adapter              │ accounts, posts, weights, event clusters      │
│ github adapter              │ topics, repos, releases, star snapshots       │
│ scoring/resonance           │ hot scores, cross-source links, alerts        │
│ reporting                   │ 3 source reports + unified overview           │
│ knowledge output            │ Knowledge/_raw artifacts + wiki dispatch      │
└─────────────────────────────┴──────────────────────────────────────────────┘
```

## Parallelization Boundary

- N1 owns shared config/DB/CLI foundation.
- N2 owns YouTube pipeline files only.
- N3 owns social pipeline files only.
- N4 owns GitHub pipeline files only.
- N5 owns cross-source reporting and email/knowledge output after N2/N3/N4.
- N6 verifies and wires schedule/doctor after all implementation nodes.

## Data Boundary

All collectors write normalized rows into `~/.solar/harness/state/tech-hotspot-radar/tech-hotspot-radar.sqlite`. Existing per-source raw outputs remain, but the new unified report reads from normalized DB first and falls back to existing digest JSON only for compatibility.

## Rate Limit Policy

- Default daily scan.
- Per-source `sleep_seconds`, `max_items_per_run`, `lookback_days`, and retry queue.
- GitHub should use ETag/cache if token exists; no token required for fixture tests.
- YouTube transcript failures enter retry queue and do not block metadata.
- Social fetchers must preserve current no-login-wall policy.

## Knowledge Policy

All reports and transcript artifacts must be written under `Knowledge/_raw` and create a wiki-ingest dispatch. Knowledge tags are for ingestion metadata, not for noisy display in user-facing email unless explicitly enabled.

## Local Preprocess And Reasoning Policy

Tech Hotspot Radar must not be a raw-text-to-premium-model system. The system uses a low-cost evidence compression layer before premium reasoning:

```text
Raw source rows
  ↓
Canonical normalization
  ↓
ThunderOMLX + Qwen3.6 local preprocess
  ↓
Evidence atoms
  ↓
Hotspot clusters
  ↓
Reasoning packets
  ↓
Premium reasoner router
  ↓
Local verifier
  ↓
Final report
```

Local Qwen3.6 responsibilities:

- clean transcript/post/readme text;
- split long transcript into timestamped semantic chunks;
- extract entities, claims, topic tags, and viewpoints;
- generate evidence atoms with stable `evidence_id`;
- create video/social/repo briefs;
- score importance, novelty, technical depth, source weight, and cross-source hint;
- verify premium outputs after reasoning.

Premium model responsibilities:

- reason only over `reasoning_packet`;
- produce structured JSON;
- bind conclusions to `evidence_id`;
- handle high-value trend synthesis, viewpoint synthesis, repo technical analysis, and final report synthesis.

Cost and audit requirements:

- Every model call writes token ledger metadata.
- Every prompt has a prompt version and schema version.
- Every input/output has a hash.
- Repeated packet hashes must hit cache instead of calling premium models again.
