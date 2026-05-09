# Architecture Design — Solar Product Platform Unification

**Sprint**: sprint-20260509-solar-product-platform
**Author**: planner (pm_proxy)
**Created**: 2026-05-09T03:08:00Z
**Aligned with**: PRD FR-0..FR-8, Contract D0..D6, Gates G0..G7

## 0. Design Tenets

T1. **Snapshot 先于变更** — 任何破坏性写之前必有 manifest+SHA256 快照，restore 必有 dry-run。
T2. **Plaintext secret 死路一条** — 写入 keychain / 600 文件 / 1Password；不进 git/log/UI/release。
T3. **Skill 是可分发可演化对象** — 进 registry，有 metric/eval/canary/promote/rollback。
T4. **存储分层零越权** — _raw=staging, _sources=canonical, Obsidian=human, QMD=index, MinerU=idle worker, Solar DB=state, Mirage=统一访问。
T5. **Plugin manifest 强制声明** — capability/data scope/commands/idle safety/eval/rollback；越权即拒载。
T6. **State DB 是唯一真相** — 双写过渡; status.json/events.jsonl 仍写但权威迁移至 solar_state.db。
T7. **Pane lease 强制** — 任何 dispatch 必须先取 lease；autopilot 三态区分 no_pane/busy/dead。
T8. **重活后台化** — MinerU/QMD embed/eval pack 大批量必须 launchd 或 idle queue + rate limit。

## 1. Component Map

```text
                      ┌────────────────────────────────────────────┐
                      │ installer/install.sh upgrade.sh restore.sh │
                      │ doctor.sh                                  │
                      └────────────┬───────────────────────────────┘
                                   │
            ┌──────────────────────┼─────────────────────────┐
            ▼                      ▼                         ▼
   ┌──────────────────┐  ┌────────────────────┐    ┌──────────────────┐
   │ product_snapshot │  │ skill platform     │    │ plugin loader    │
   │ manifest+sha256  │  │ registry+metrics   │    │ capability registry│
   └────────┬─────────┘  └──────┬─────────────┘    └────────┬─────────┘
            │                   │                            │
            ▼                   ▼                            ▼
        backups/         skills/registry.yaml         plugins/<id>/manifest
        manifest.json    skills/builtins/             schemas/plugin.schema
                         evals/skills/                schemas/capability.schema
                                                            │
                                                            ▼
                                                   evolution engine
                                                   failure miner + eval runner
                                                            │
        ┌───────────────────────────────────────────────────┘
        ▼
   ┌─────────────────────────────────────────────────────────┐
   │ control plane: state DB + task queue + pane lease        │
   │  + autopilot                                            │
   │  schemas/task-lifecycle.schema.json                      │
   │  lib/solar_state_db.py / task_queue.py / pane_lease.py  │
   └─────────────────────────────────────────────────────────┘
                                                            │
                                                            ▼
                                                  data access layer
                                                  Mirage VFS + adapters
                                                            │
                                                            ▼
                                                  data storage layer
                                                 _sources / Obsidian /
                                                 Solar DB / QMD / Cortex /
                                                 events.jsonl
```

## 2. Component Contracts

### 2.1 Snapshot & Restore (D0)

`lib/product_snapshot.py`

```python
def snapshot(roots: list[Path], exclude_secrets: bool = True) -> Manifest
def restore(manifest: Manifest, dry_run: bool = True) -> RestorePlan
def verify(manifest: Manifest) -> VerifyReport
```

`backups/product-snapshots/<ts>/manifest.json`:

```json
{
  "version": 1,
  "ts": "2026-05-09T03:08:00Z",
  "roots": [
    {"path": "~/.solar/harness", "exclude": ["sprints/*.bak.*", "venv/"]}
  ],
  "files": [
    {"path": "<rel>", "sha256": "<hex>", "size": 1234, "mode": "0644"}
  ],
  "secrets_excluded": [".env", "config/secrets.yaml"],
  "tarball": "<ts>.tar.zst",
  "tarball_sha256": "<hex>",
  "restore_plan_dry_run": "restore.txt"
}
```

CLI: `solar-harness product snapshot|restore|verify [--dry-run]`. Default exclude .env*, *.key, *.pem, keychain entries; manifest 写明被排除的 secret 路径列表 (路径但不含值)。

### 2.2 Installer / Upgrade / Doctor / Restore (D1)

```
installer/
├── install.sh         # OS detect → brew/apt fallback → wizard → init
├── upgrade.sh         # snapshot → diff apply → smoke → verify
├── doctor.sh          # paths/bins/permissions/secrets/services
├── restore.sh         # wraps product_snapshot restore
config/
├── defaults.yaml      # provider/vault/QMD/Drive/secrets/skills
└── storage.solar.yaml # _sources/_raw/papers/Mirage mounts
.env.example           # placeholders only
.gitignore             # .env, *.key, /backups, /node_modules, ...
gitleaks.toml          # rules covering anthropic/openai/google/zai keys
docker/
├── Dockerfile         # ubuntu:24 base, no secrets baked in
└── smoke-test.sh      # install → wizard with fake keys → doctor → skill run
```

Doctor JSON shape (`doctor.sh --json`):

```json
{
  "ts": "<iso>",
  "os": {"kind": "darwin|linux", "version": "..."},
  "bins": {"tmux": "ok", "claude": "ok|missing", ...},
  "paths": {"~/.solar": "ok", "~/Knowledge": "ok|degraded", ...},
  "services": {"harness": "running|stopped", "qmd-mcp": {...}, "mineru": {...}},
  "secrets": {"anthropic": "configured|missing", "openai": "configured|missing"},
  "skills": {"builtins_count": 12, "registry_drift": 0},
  "verdict": "ok|degraded|fail"
}
```

### 2.3 Skill Platform (D2)

```
skills/
├── registry.yaml         # canonical list with stability/canary/candidate/experimental
├── builtins/<id>/SKILL.md
├── user/<id>/SKILL.md    # symlinked from ~/.agents/skills with audit
└── canary/<id>/SKILL.md  # quarantined
lib/
├── solar_skills.py       # CRUD + materialize from yaml
├── skill_metrics.py      # uses_total / success_rate / latency_p95 / regression
└── skill_export.py       # safe export to ~/.claude/skills, ~/.codex, ~/.agents
evals/skills/<id>/
├── pack.yaml
├── cases/*.json
└── golden/*.md
```

`registry.yaml`:

```yaml
version: 1
skills:
  - id: review
    source: gstack
    path: skills/builtins/review/SKILL.md
    stability: stable          # stable|canary|candidate|experimental
    eval_pack: evals/skills/review
    min_score: 0.8
    metrics_window_days: 7
    last_promoted_at: 2026-05-01
```

CLI: `solar-harness skills inventory|doctor|export|eval|promote|rollback`.

Promotion gate: stable promotion requires (eval_pass>=min_score) AND (regression_pass=true) AND (drift=0).

### 2.4 Storage & Data Access (D3)

```
_sources/
  papers/<sha256-prefix>/<filename>.pdf
  papers/<id>/manifest.json (provenance: origin_url, ingested_at, mineru_run)
_raw/
  file-uploads/  # staging only, with TTL+auto-archive
Obsidian vault: ~/Knowledge (human readable, references with frontmatter)
Mirage mounts:
  /knowledge   → ~/Knowledge
  /raw         → _raw
  /sources     → _sources
  /papers      → _sources/papers
  /qmd         → QMD adapter
  /solar-db    → solar.db read view
  /cortex      → cortex.db read view
  /sprints     → ~/.solar/harness/sprints
  /drive       → optional, mirror only if configured
```

`config/storage.solar.yaml`:

```yaml
sources:
  papers_root: _sources/papers
  ingest_workers: 1
  idle_threshold_load: 1.0
raw:
  staging_root: _raw/file-uploads
  ttl_days: 14
mirage:
  mounts: [/knowledge, /raw, /sources, /papers, /qmd, /solar-db, /cortex, /sprints]
  drive: {enabled: false, credentials_env: GOOGLE_DRIVE_TOKEN_PATH}
mineru:
  worker: launchd
  rate_limit_pdf_per_hour: 6
  memory_cap_mb: 2048
qmd:
  index_targets: [_sources, ~/Knowledge]
  rebuild_strategy: incremental
```

`lib/source_manifest.py` — checksum-aware copy/move with provenance frontmatter; `lib/mineru_extract.py` — idle worker producing pages into Obsidian + provenance into manifest.

### 2.5 Extension Framework (D4)

```
plugins/<id>/manifest.yaml
schemas/plugin.schema.json
schemas/capability.schema.json
lib/capability_registry.py
lib/plugin_loader.py
```

`manifest.yaml` minimum fields:

```yaml
id: mermaid
version: 0.1.0
capabilities: [diagram_render]
data_access:
  read: [/sources, /knowledge]
  write: []
commands: [mermaid_render]
idle_safety: light    # light|medium|heavy
eval_pack: evals/plugins/mermaid
rollback: solar-harness plugins disable mermaid
permissions:
  network: false
  shell_exec: false
```

`integrations status --json`:

```json
{
  "plugins": [
    {"id": "obsidian", "level": "default_usable", "status": "ok"},
    {"id": "mermaid", "level": "basic_usable", "status": "degraded"},
    {"id": "drive", "level": "dead_end", "status": "no_credentials"}
  ]
}
```

Levels: `dead_end < basic_usable < default_usable < closed_loop`.

### 2.6 Evolution Engine (D5)

```
lib/evolution_engine.py
lib/failure_miner.py
lib/eval_runner.py
evals/packs/<id>/...
experiments/<id>/hypothesis.md
```

Loop:

```
events.jsonl + state DB → failure_miner (cluster) → candidate proposals
   → eval_runner (eval pack + regression) → promotion_gate
   → state DB update + skill_export.refresh
```

Promotion gate (skill or capability):

```python
def can_promote(card: Scorecard) -> Decision:
    if card.eval_score < min_score: return REJECT
    if card.regression_failures > 0: return REJECT
    if card.degradation_signal: return DEMOTE
    if card.canary_window_days < required: return WAIT
    return PROMOTE
```

### 2.7 Control Plane (D6)

`schemas/task-lifecycle.schema.json`:

```json
{
  "states": ["queued","drafting","spec","prd_ready","designing","planning",
             "planning_complete","active","building","reviewing","passed",
             "kb_ingested","closed","blocked","aborted"],
  "transitions": [
    {"from":"queued","to":"drafting","by":"pm"},
    {"from":"drafting","to":"prd_ready","by":"pm"},
    {"from":"prd_ready","to":"planning","by":"planner"},
    {"from":"planning","to":"planning_complete","by":"planner"},
    {"from":"planning_complete","to":"active","by":"planner"},
    {"from":"active","to":"reviewing","by":"builder"},
    {"from":"reviewing","to":"passed","by":"evaluator"},
    {"from":"passed","to":"kb_ingested","by":"librarian"},
    {"from":"kb_ingested","to":"closed","by":"coordinator"}
  ]
}
```

`solar_state.db` schemas (sqlite):

```sql
CREATE TABLE tasks (
  sid TEXT PRIMARY KEY, title TEXT, state TEXT, priority TEXT, lane TEXT,
  owner TEXT, created_at TEXT, updated_at TEXT, parent_sid TEXT
);
CREATE TABLE assignments (
  sid TEXT, role TEXT, agent TEXT, started_at TEXT, ended_at TEXT, outcome TEXT
);
CREATE TABLE leases (
  pane TEXT PRIMARY KEY, sid TEXT, role TEXT, acquired_at TEXT, ttl_sec INTEGER,
  heartbeat_at TEXT, holder_pid INTEGER
);
CREATE TABLE events (
  ts TEXT, sid TEXT, kind TEXT, by TEXT, payload_json TEXT
);
CREATE TABLE artifacts (
  sid TEXT, kind TEXT, path TEXT, sha256 TEXT, ts TEXT
);
CREATE TABLE capabilities (
  id TEXT PRIMARY KEY, kind TEXT, score REAL, stability TEXT, last_eval_at TEXT
);
```

Pane lease semantics:

```
acquire(pane, sid, role, ttl=600s) → granted | held_by_other
heartbeat(pane) → renew ttl
release(pane) → free slot
autopilot dispatch_failed handling:
   if pane has heartbeat in last ttl/2 → busy → backoff
   if pane has lease but no heartbeat > ttl → dead → break lease + redispatch
   if pane has no lease → no_pane → spawn or reroute
```

Autopilot covers: handoff stall, eval stall, dispatch backlog, hook failure, codex_heartbeat false positive.

### 2.8 Container Validation (FR-7) & Secret Scan (FR-8)

Dockerfile baseline:

```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y bash python3 python3-venv tmux git jq sqlite3
RUN useradd -m solar && mkdir -p /opt/solar && chown solar:solar /opt/solar
USER solar
WORKDIR /home/solar
COPY --chown=solar:solar . /opt/solar
ENV SOLAR_HOME=/opt/solar
ENTRYPOINT ["/opt/solar/installer/install.sh", "--non-interactive"]
```

`docker/smoke-test.sh`:

```
1. build image
2. run container with fake keys env: ANTHROPIC_API_KEY=fake-anth, OPENAI_API_KEY=fake-oa
3. install --non-interactive --vault /tmp/vault --skip-llm-cli
4. doctor --json | jq -e '.verdict == "ok"'
5. solar-harness skills run --skill review --dry-run
6. solar-harness product snapshot --output /tmp/snap
7. exit 0
```

Secret scan layers:

- pre-commit: gitleaks detect --staged
- pre-push: gitleaks detect (no-staged scope, full diff)
- release audit: scan worktree + tarball
- runtime UI: status payload validator strips known secret keys

## 3. Data Flow Diagrams

### 3.1 Install / Upgrade / Rollback

```
user → install.sh → OS detect → install bins → wizard collect config
   → write config/defaults.yaml + storage.solar.yaml
   → init solar_state.db schema
   → product snapshot baseline
   → doctor → start harness → success
upgrade.sh → product snapshot pre → apply diff → migrate (if any) → doctor
   → smoke → on failure: restore.sh dry-run → confirm → restore
```

### 3.2 PDF Ingest (D3)

```
user drops PDF in _raw/file-uploads
  → mineru launchd worker (idle when load_avg<1.0)
  → checksum → copy to _sources/papers/<sha-prefix>/
  → manifest.json with provenance
  → MinerU deep extract → markdown pages
  → Obsidian reference page generated
  → QMD incremental index
  → events.jsonl record
  → original _raw file kept TTL=14d then archived
```

### 3.3 Skill Lifecycle (D2 + D5)

```
new skill written to skills/candidate/<id>
   → eval_runner runs eval pack → score
   → if score>=min_score: promote to canary
   → canary window N days, metrics gathered
   → promotion_gate evaluates → stable
   → skill_export materializes safe symlinks to ~/.claude/skills, ~/.codex/skills, ~/.agents/skills
   → degradation: demote stable→canary→candidate
```

### 3.4 Sprint Lifecycle (D6)

```
queued → pm dispatch → drafting → prd_ready → planning → planning_complete
   → active → builder dispatch (with pane lease) → building → reviewing
   → evaluator dispatch (with pane lease) → passed → kb_ingested → closed
```

## 4. Non-Functional Constraints

- 安全: 严禁 plaintext secret，gitleaks + UI 白名单 + .env.example only。
- 性能: 重活后台化；user shell 不阻塞；OOM 上限保护。
- 兼容: solar-harness start/status/wiki/qmd/status-server 现有路径不破。
- 回滚: 每个 D 都必须有 rollback action，且能被 D0 snapshot 覆盖。
- 可观测: 所有变更产出 events.jsonl + state DB 双写；UI 与 status.json 显示同一来源。

## 5. ADRs (To Author During Build)

ADR-001 State DB 独立 schema 不复用 cortex.db
ADR-002 Skill registry yaml + sqlite 双写策略
ADR-003 Plugin sandbox: scope-checked 起步, process-isolated 后续
ADR-004 Mirage Drive 无凭据时 degraded 而非 ok
ADR-005 Autopilot 三态 (no_pane/busy/dead) lease + heartbeat 算法
ADR-006 Snapshot tarball 格式 (tar.zst + manifest.json + sha256)

## 6. Open Risks Tied to Slices

- R1 PDF 误删 ↔ S0+S3 (snapshot 强制 + checksum copy)
- R2 Skill 软链冲突 ↔ S2 (export diff + namespace)
- R3 容器漂移 ↔ S1 (Linux + macOS 双跑)
- R4 协调器破坏 ↔ S6 (双写过渡)
- R5 autopilot 误判 ↔ S6 (lease + heartbeat)
- R6 Drive 伪 ok ↔ S4 (integrations status 四级)
- R7 plugin 过度设计 ↔ S4 (manifest 最小集)
- R8 evolution 误晋级 ↔ S5 (双 gate)
- R9 secret scan 漏检 ↔ S1 (多层扫描)
- R10 MinerU OOM ↔ S3 (memory cap + idle)

## 7. Acceptance Map (PRD A → Slice)

| A | Slice | Gate |
|---|-------|------|
| A1 | S0 | G0 |
| A2 | All slices preflight | G1 |
| A3 | S1 | G2 |
| A4 | S1 | G3 |
| A5 | S2 | G4 |
| A6 | S3 | G5 |
| A7 | S6 | G6 |
| A8 | S7 | G7 |
| A9 | S5 | promotion |
| A10 | S4 | integrations |
