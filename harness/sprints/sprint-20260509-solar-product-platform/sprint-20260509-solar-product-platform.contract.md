---
sid: sprint-20260509-solar-product-platform
title: Solar Product Platform Unification
priority: P0
lane: product-platform
status: queued
phase: contract_ready
handoff_to: planner
created_at: 2026-05-09T03:00:08Z
owner: solar
---

# P0 合约: Solar Product Platform Unification

## 1. Intent

把当前分散的 Solar / solar-harness / skills / knowledge / integrations 收敛成可下载、可安装、可升级、可回滚、可扩展、可自演化的产品平台。

核心边界:

- Solar 是产品脑、控制面、能力治理和自演化系统。
- solar-harness 是 runtime executor，负责 tmux/pane/coordinator/hooks/status-server。
- Skill 是一等公民，必须随 Solar 发布、评估、晋级、回滚。
- Mirage 是统一数据访问层核心；QMD 是索引检索；MinerU 是文档深抽取；Obsidian 是人可读知识库；Solar DB 是结构化状态/记忆。

## 2. Non-Negotiables

1. 开发前必须 snapshot 当前版本，能 restore dry-run。
2. 不允许泄露 API key/token/secrets 到 git、日志、status UI、release 包。
3. 容器 clean install 必须可验证，不允许只在昊哥本机跑通。
4. Skill 必须进入产品分发和自演化体系，不允许只靠 `~/.agents/skills` 野生存在。
5. 新架构不能破坏当前可用的 solar-harness start/status/wiki/qmd/status-server。
6. 所有重活如 QMD embed、MinerU PDF 深抽取、paper reingest 必须后台/idle/限流。

## 3. Target Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│ Product Distribution Layer                                          │
│ installer / config wizard / backup / upgrade / rollback / releases  │
├────────────────────────────────────────────────────────────────────┤
│ Skill Platform & Skill Evolution Layer                              │
│ skill registry / package / export / metrics / eval / canary / revert│
├────────────────────────────────────────────────────────────────────┤
│ Evolution Layer                                                     │
│ events / metrics / failure mining / experiments / promotion gates    │
├────────────────────────────────────────────────────────────────────┤
│ Extension Framework                                                 │
│ plugin manifest / capability registry / adapters / eval packs        │
├────────────────────────────────────────────────────────────────────┤
│ Control Plane                                                       │
│ state DB / task lifecycle / queue / pane lease / autopilot / policy  │
├────────────────────────────────────────────────────────────────────┤
│ Data Access Layer                                                   │
│ Mirage VFS / QMD adapter / Solar DB adapter / Obsidian adapter       │
├────────────────────────────────────────────────────────────────────┤
│ Data Storage Layer                                                  │
│ _sources / Obsidian / Solar DB / QMD index / Cortex / events         │
├────────────────────────────────────────────────────────────────────┤
│ Runtime Layer                                                       │
│ solar-harness / tmux panes / Claude / Codex / GLM / DeepSeek / MCP   │
└────────────────────────────────────────────────────────────────────┘
```

## 4. Deliverables

### D0. Pre-Change Snapshot & Restore

Files:

- `lib/product_snapshot.py`
- `solar-harness.sh product snapshot|restore|verify`
- `backups/product-snapshots/<timestamp>/manifest.json`

Acceptance:

- Snapshot includes code/config/state manifests for `~/.solar`, `~/.solar/harness`, relevant `~/.claude/core/solar-farm`, skill registry, and config paths.
- Secrets are not copied in plaintext by default.
- `restore --dry-run` reports exact files to restore.
- SHA256 manifest exists and validates.

### D1. Product Distribution Foundation

Files:

- `installer/install.sh`
- `installer/upgrade.sh`
- `installer/doctor.sh`
- `installer/restore.sh`
- `config/defaults.yaml`
- `.env.example`
- `.gitignore`
- `gitleaks.toml`
- `docker/Dockerfile`
- `docker/smoke-test.sh`

Acceptance:

- Clean install works in container with fake/test keys and a temp vault.
- First-run config supports model/provider/vault/QMD/Drive/secrets without manual file editing.
- Upgrade does not overwrite user config/data/secrets.
- Git/release secret scan passes.
- Status UI shows configured/missing only, never secret values.

### D2. Skill Platform

Files:

- `skills/builtins/*/SKILL.md`
- `skills/registry.yaml`
- `lib/solar_skills.py`
- `lib/skill_metrics.py`
- `lib/skill_export.py`
- `evals/skills/*`

Acceptance:

- Built-in, user, generated, experimental, plugin-provided skills are all registered.
- `solar-harness skills inventory|doctor|export|eval|promote|rollback` works.
- Stable skills are exported/symlinked to Claude/Codex/agents safely.
- Candidate/canary skills are not default injected.
- Every stable skill has eval pack and minimum score.
- Skill usage emits events and metrics.

### D3. Unified Storage & Data Access Layer

Files:

- `config/storage.solar.yaml`
- `lib/source_manifest.py`
- `lib/solar_mirage.py`
- `lib/qmd_adapter.py`
- `lib/mineru_extract.py`

Acceptance:

- `_raw` is staging only; canonical source library is `_sources`.
- PDFs move/copy to `_sources/papers` with manifest/provenance and compatibility symlink/redirect where needed.
- Mirage exposes `/knowledge`, `/raw`, `/sources`, `/papers`, `/qmd`, `/solar-db`, `/cortex`, `/sprints`, optional `/drive`.
- QMD indexes canonical sources and extracted wiki pages.
- MinerU handles PDF deep extraction as background/idle processor, not as access layer.
- Drive is mirror/cold backup only unless explicit credentials and sync policy are configured.

### D4. Extension Framework

Files:

- `plugins/*/manifest.yaml`
- `schemas/plugin.schema.json`
- `schemas/capability.schema.json`
- `lib/capability_registry.py`
- `lib/plugin_loader.py`

Acceptance:

- New open-source integrations must declare capabilities, data access, commands, background safety, eval packs, rollback.
- Existing Obsidian/QMD/MinerU/Mirage/Mermaid/Symphony/Everything-Claude-Code are represented as plugins or capability providers.
- `solar-harness integrations status --json` reports basic usable / default usable / closed loop / dead ends.
- No plugin can write outside declared scopes without explicit policy.

### D5. Evolution Engine

Files:

- `lib/evolution_engine.py`
- `lib/failure_miner.py`
- `lib/eval_runner.py`
- `evals/packs/*`
- `experiments/*/hypothesis.md`

Acceptance:

- Events and task outcomes produce capability scorecards.
- Failures are clustered into improvement candidates with evidence.
- Experiments have before/after metrics and rollback path.
- Promotion requires eval pass and regression pass.
- Degradation auto-demotes canary/candidate capabilities.

### D6. Control Plane Unification

Files:

- `schemas/task-lifecycle.schema.json`
- `lib/solar_state_db.py`
- `lib/task_queue.py`
- `lib/pane_lease.py`
- `lib/autopilot.py`

Acceptance:

- One authoritative state DB for tasks, assignments, leases, events, artifacts, capabilities.
- PRD -> Design -> Plan -> Dispatch -> Build -> Eval -> KB -> Closeout is represented as state machine.
- Pane lease prevents pane stealing.
- Autopilot can resolve handoff stalls, eval stalls, dispatch backlog, hook failures.
- Heavy queue supports rate limit, retry, checkpoint, stale cleanup.

## 5. Product Gates

```text
┌──────┬────────────────────────────────────────────┬────────────────┐
│ Gate │ Requirement                                │ Fail Action    │
├──────┼────────────────────────────────────────────┼────────────────┤
│ G0   │ Snapshot + restore dry-run pass             │ stop           │
│ G1   │ Existing solar-harness smoke pass            │ stop           │
│ G2   │ Container clean install pass                 │ no release     │
│ G3   │ Secret scan pass                             │ no git push    │
│ G4   │ Skill registry + stable skill eval pass      │ no default     │
│ G5   │ Storage migration does not break QMD/wiki    │ rollback       │
│ G6   │ Autopilot resolves synthetic deadlock        │ no promotion   │
│ G7   │ Release artifact install/upgrade/rollback    │ no publish     │
└──────┴────────────────────────────────────────────┴────────────────┘
```

## 6. Stop Rules

- Any command prints real key/token/secret: stop and quarantine logs.
- Any migration risks deleting source PDFs without verified copy and checksum: stop.
- Any container test requires昊哥本机 private path: fail.
- Any skill auto-promotes without eval: fail.
- Any pane dispatch bypasses lease when lease exists: fail.
- Any Google Drive action requires credentials not present: mark degraded, do not fake ok.

## 7. Planner Assignment

Planner must produce:

1. PRD with user outcomes and install/upgrade UX.
2. Architecture design with state DB, skill platform, plugin registry, storage layer, evolution loop.
3. Implementation plan split into independent slices.
4. Dispatch plan for builders with no overlapping write scopes.
5. Risk register, rollback plan, and first gate checklist.

Do not start destructive migration until D0 snapshot gate passes.

