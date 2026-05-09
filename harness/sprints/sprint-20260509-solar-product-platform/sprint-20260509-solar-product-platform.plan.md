# Implementation Plan — Solar Product Platform Unification

**Sprint**: sprint-20260509-solar-product-platform
**Author**: planner (pm_proxy)
**Created**: 2026-05-09T03:12:00Z
**Aligned with**: PRD FR-0..FR-8, Design Sections 2.1-2.8, Gates G0..G7

## 0. Slice Topology

```text
                ┌─────────────────────┐
                │ S0 Snapshot/Restore │  G0 ◄── BLOCKING
                │   (D0)              │
                └────────────┬────────┘
                             │ G0 PASS
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐  ┌──────────┐  ┌─────────────┐
     │ S1 Installer │  │ S2 Skill │  │ S6 Control  │
     │ (D1+FR7+FR8) │  │ (D2)     │  │ Plane (D6)  │
     └──────┬───────┘  └────┬─────┘  └──────┬──────┘
            │ G2,G3         │ G4            │ G6
            └──────┬────────┴───────────────┘
                   ▼
         ┌──────────────────┐
         │ S3 Storage (D3)  │ G5
         │  + MinerU idle   │
         └──────┬───────────┘
                ▼
         ┌──────────────────┐
         │ S4 Plugins (D4)  │ A10
         └──────┬───────────┘
                ▼
         ┌──────────────────┐
         │ S5 Evolution(D5) │ A9
         └──────┬───────────┘
                ▼
         ┌──────────────────┐
         │ S7 Release (G7)  │ G7
         └──────────────────┘
```

Parallelization rules:
- S0 必须最先且独立通过 G0，否则其余全部阻塞。
- S1/S2/S6 可在 G0 通过后并行（写范围互不重叠）。
- S3 依赖 S1 (容器测试基线) + S6 (state DB schema) 部分产物。
- S4 依赖 S2 + S3 的对外 contract。
- S5 依赖 S4 (capability registry)。
- S7 必须在 S1..S6 全绿之后。

## 1. Slice Specs

### S0 — Snapshot & Restore Foundation

Owner: builder_main (Sonnet)
Deliverable: D0
Gate: **G0 (blocking)**
Status start: status=active, phase=planning_complete → assigned_to=builder_main

**Write Scope (exclusive)**:
- `lib/product_snapshot.py`
- `solar-harness.sh` 增加 `product snapshot|restore|verify` 子命令 (只 +新分支，不改既有逻辑)
- `backups/product-snapshots/` 目录骨架
- `tests/snapshot/` 测试

**Read Scope**:
- ~/.solar/, ~/.solar/harness/, ~/.claude/core/solar-farm/, skill registry path, config path

**Done**:
- D0.1 `solar-harness product snapshot` 产出 manifest.json + tarball + sha256
- D0.2 `solar-harness product restore --dry-run` 列出每个会还原文件 (路径+sha)
- D0.3 `solar-harness product verify` 校验 manifest 与 tarball
- D0.4 secret 默认排除：.env*, *.key, *.pem, keychain entries；manifest 列出被排除路径但不含值
- D0.5 round-trip 测试：snapshot → 改一个非 secret 文件 → restore --apply (沙箱目录) → 校验复原
- D0.6 不修改任何现有文件以外的内容；现有 solar-harness 命令不破
- D0.7 写 ADR-006 (snapshot tarball format)

**Stop Conditions**:
- 任何检测到 secret 落入 plaintext 复制 → 立即停。
- 既有 solar-harness 命令任一失败 → 停。

**Round-Retry Trigger**: 测试 round-trip 失败、manifest sha 不一致、restore dry-run 漏报。

---

### S1 — Installer + Doctor + Container + Secret Scan

Owner: builder_codex (gpt-5/codex)
Deliverable: D1 + FR-7 + FR-8
Gate: **G2 (container clean install) + G3 (secret scan)**
Depends on: S0 G0 PASS

**Write Scope (exclusive)**:
- `installer/install.sh upgrade.sh doctor.sh restore.sh`
- `config/defaults.yaml` `.env.example`
- `.gitignore` `gitleaks.toml`
- `docker/Dockerfile docker/smoke-test.sh`
- `hooks/pre-commit-secret-scan` `hooks/pre-push-secret-scan`
- `tests/installer/`

**Read Scope**:
- 配置模板路径、product_snapshot CLI (依赖 S0 D0)、storage.solar.yaml schema 草案

**Done**:
- D1.1 `installer/install.sh --non-interactive` 在 ubuntu:24 容器跑通：装依赖→建目录→写默认 config→init state DB→snapshot baseline→doctor 全绿
- D1.2 `installer/upgrade.sh` 不覆盖用户 config/data/secrets；触发 snapshot pre/post
- D1.3 `installer/doctor.sh --json` 输出符合 design 2.2 schema；verdict=ok 在干净容器达成
- D1.4 `gitleaks detect` 在干净 worktree 0 finding；pre-commit/pre-push hook 工作
- D1.5 `docker/smoke-test.sh` 全绿（fake keys + skip-llm-cli）
- D1.6 status UI / doctor 仅显示 configured/missing；release tarball 0 plaintext secret
- D1.7 macOS install 路径 (brew-based) 也跑通 doctor (在 host 上由昊哥手测)

**Stop Conditions**:
- 任何容器测试引用昊哥本机私有路径 → 停。
- 任何 secret 出现在 git diff、log、UI、tarball → 停。
- installer 修改了既有 ~/.solar 用户数据 → 停 + restore。

**Round-Retry Trigger**: 容器 smoke fail、gitleaks finding、install 后 doctor 不绿、upgrade 覆盖用户数据。

---

### S2 — Skill Platform

Owner: builder_glm (glm-5)
Deliverable: D2
Gate: **G4 (skill registry + stable skill eval pass)**
Depends on: S0 G0 PASS（不依赖 S1，但部署导出靠 S1 安装路径）

**Write Scope (exclusive)**:
- `skills/registry.yaml`
- `skills/builtins/` (新增 stub + SKILL.md，至少 5 个：plan, review, ship, browse, retro)
- `lib/solar_skills.py lib/skill_metrics.py lib/skill_export.py`
- `evals/skills/` (至少 5 个 stable skill 的 eval pack)
- `solar-harness.sh` `skills` 子命令分支
- `tests/skills/`

**Read Scope**:
- ~/.agents/skills, ~/.claude/skills, ~/.codex/skills (只读用于 inventory)
- skill_export.py 写到 ~/.claude/skills 时必须使用 S0 snapshot 覆盖前置

**Done**:
- D2.1 至少 5 个 builtin + 5 个 user/generated skill 进入 registry.yaml
- D2.2 `solar-harness skills inventory|doctor|export|eval|promote|rollback` CLI 全部可用
- D2.3 stable skill 安全 export/symlink 到 Claude/Codex/agents（带备份+冲突检测+namespace 隔离默认）
- D2.4 candidate/canary skill 不进默认注入路径
- D2.5 stable skill 的 eval pack 都达到 min_score
- D2.6 skill 调用产生 events + metrics 写到 events.jsonl
- D2.7 promotion_gate 双 gate (eval+regression) 实装

**Stop Conditions**:
- skill_export 覆盖了用户既有未备份 skill → 停 + restore。
- canary skill 被默认注入 → 停。

**Round-Retry Trigger**: 5 个 stable skill 任意 eval 不达标、export 冲突未处理、metrics 未写。

---

### S3 — Storage & Data Access (含 MinerU idle 重活)

Owner: builder_main (Sonnet, 接 S0 之后)
Deliverable: D3
Gate: **G5 (storage migration without breaking QMD/wiki)**
Depends on: S0 G0 PASS + S1 G2/G3 PASS（容器路径已经形成） + S6 state DB schema 至少 events 表就绪

**Write Scope (exclusive)**:
- `config/storage.solar.yaml`
- `lib/source_manifest.py lib/solar_mirage.py lib/qmd_adapter.py lib/mineru_extract.py`
- `_sources/` 目录骨架（仅创建空结构 + .gitkeep）
- launchd plist 用于 MinerU idle worker
- `tests/storage/`

**Read Scope**:
- _raw, ~/Knowledge, QMD index 路径

**Done**:
- D3.1 _sources 与 papers 目录建立；_raw 仅 staging 语义文档化
- D3.2 老 _raw PDF 全部 checksum copy 到 _sources/papers/<sha-prefix>/，附 manifest.json provenance；保留 _raw 副本 14 天 TTL（不删原始）
- D3.3 Mirage 暴露 8 挂点；doctor json verifies 8 个 mount accessible
- D3.4 QMD 索引 incremental rebuild 跑通；wiki 链接不失效
- D3.5 MinerU 改为 launchd idle worker，rate limit + memory cap 实装；user shell 不阻塞（手测）
- D3.6 Drive 在无凭据时 status=degraded（不是 ok），UI 显示需要的 env var
- D3.7 storage migrate 命令带 --dry-run；任何缺 checksum 的文件不动

**Stop Conditions**:
- 任何 PDF 在源未校验 sha 前被移动/删除 → 停。
- QMD 索引或 wiki 链接被破坏 → 停 + restore。
- MinerU 阻塞 user shell 或 OOM → 停。

**Round-Retry Trigger**: dry-run 漏掉文件、checksum 不一致、Drive 误显示 ok、MinerU 内存超限。

---

### S4 — Extension Framework

Owner: builder_glm (glm-5)
Deliverable: D4
Gate: **A10 (plugin manifest + integrations status 四级)**
Depends on: S2 G4 PASS + S3 G5 PASS

**Write Scope (exclusive)**:
- `plugins/<id>/manifest.yaml` (至少 5 个：obsidian, qmd, mineru, mirage, mermaid)
- `schemas/plugin.schema.json schemas/capability.schema.json`
- `lib/capability_registry.py lib/plugin_loader.py`
- `solar-harness.sh integrations` 子命令分支
- `tests/plugins/`

**Read Scope**:
- skill registry, storage config, mirage mount info

**Done**:
- D4.1 至少 5 个 plugin manifest 有效 (schema 校验通过)
- D4.2 `solar-harness integrations status --json` 输出 dead_end/basic_usable/default_usable/closed_loop 四级
- D4.3 capability registry 持久化到 state DB
- D4.4 plugin scope 越权写 → 拒载 + 写 events 告警
- D4.5 提供 plugin install/disable/list CLI
- D4.6 写 ADR-003 (plugin sandbox 策略 scope-checked 起步)

**Stop Conditions**:
- plugin 越权写非声明 scope → 停 + 拒载。
- integrations status 显示假 ok → 停。

**Round-Retry Trigger**: schema 校验失败、scope 越权未拒载、四级语义错乱。

---

### S5 — Evolution Engine

Owner: builder_codex (gpt-5/codex)
Deliverable: D5
Gate: **A9 (evolution loop pass)**
Depends on: S2 G4 PASS + S4 A10 PASS + S6 state DB

**Write Scope (exclusive)**:
- `lib/evolution_engine.py lib/failure_miner.py lib/eval_runner.py`
- `evals/packs/<id>/`
- `experiments/<id>/hypothesis.md`
- `tests/evolution/`

**Read Scope**:
- events.jsonl, solar_state.db (events/tasks/capabilities 表), skill registry, plugin registry

**Done**:
- D5.1 跑通至少 1 个失败聚类 → 实验 → eval → promotion 或 demotion 闭环
- D5.2 capability scorecard 写入 state DB；status UI 可见
- D5.3 promotion gate 双 gate (eval pass + regression pass) 实装
- D5.4 degradation 自动 demote canary/candidate
- D5.5 实验文档 hypothesis/before/after/rollback 模板齐全

**Stop Conditions**:
- 自动晋级未通过双 gate → 停。
- 实验缺 rollback path → 停。

**Round-Retry Trigger**: scorecard 不一致、双 gate 漏判、demote 未触发。

---

### S6 — Control Plane Unification

Owner: builder_main (Sonnet)
Deliverable: D6
Gate: **G6 (autopilot resolves synthetic deadlock)**
Depends on: S0 G0 PASS（独立但不可破坏既有 coordinator）

**Write Scope (exclusive)**:
- `schemas/task-lifecycle.schema.json`
- `lib/solar_state_db.py lib/task_queue.py lib/pane_lease.py lib/autopilot.py`
- `solar-harness.sh autopilot|leases` 子命令分支
- `tests/control_plane/`

**Read Scope**:
- 现有 status.json/events.jsonl/coordinator events（双写过渡需要读）
- tmux 状态用于 lease 心跳（仅读取，不操作 live pane）

**Done**:
- D6.1 solar_state.db schema 建立（tasks/assignments/leases/events/artifacts/capabilities 六表）
- D6.2 task lifecycle schema 校验现有 status 文件均能映射
- D6.3 pane lease 实装：acquire/heartbeat/release，autopilot 三态 (no_pane/busy/dead)
- D6.4 注入合成 deadlock (pane busy 但 watchdog 误判 dead) → autopilot 区分 busy/dead 并等待 lease
- D6.5 handoff stall / eval stall / dispatch backlog / hook failure 四类故障演练通过
- D6.6 双写过渡：旧 status.json/events.jsonl 不删；新 state DB 同步写
- D6.7 写 ADR-001 (state DB 独立 schema) + ADR-005 (autopilot 三态)

**Stop Conditions**:
- 任何变更破坏现有 coordinator 主循环 → 停。
- pane 被偷或 lease 失效 → 停。

**Round-Retry Trigger**: 双写不一致、lease 抢占、autopilot 误判仍存在。

---

### S7 — Release Tooling + Final Audit

Owner: builder_main (Sonnet) + 双签 (treasury 治理官最终审)
Deliverable: G7 release artifact + final ADR set
Depends on: S1..S6 全部 PASS

**Write Scope (exclusive)**:
- `release/build.sh release/publish.sh release/CHANGELOG.md`
- `docs/upgrade-guide.md docs/rollback-guide.md`
- `ADR/ADR-002 ADR-004` 等剩余 ADR
- `tests/release/`

**Read Scope**:
- 全部既有 lib/, installer/, skills/, plugins/, schemas/

**Done**:
- D7.1 release tarball 打包；checksum 一致；版本号、变更记录、ADR 链接齐全
- D7.2 干净容器 install→upgrade→rollback round-trip 通过
- D7.3 release pre-publish audit: 0 plaintext secret, gitleaks pass, schema 校验全过
- D7.4 升级指南 + 回滚指南 文档化
- D7.5 双签批准（战略家+治理官）

**Stop Conditions**:
- audit 任何 finding → 停。
- round-trip 任何 step 失败 → 停。

## 2. Cross-Slice Sequencing

| 阶段 | 并行 slice | 阻塞门 |
|------|-----------|--------|
| 阶段 0 | S0 | G0 |
| 阶段 1 | S1, S2, S6 | G2/G3, G4, G6 |
| 阶段 2 | S3 | G5 |
| 阶段 3 | S4 | A10 |
| 阶段 4 | S5 | A9 |
| 阶段 5 | S7 | G7 |

## 3. First Gate Checklist (G0)

Planner 不会启动 builder。下一步动作必须由协调器/PM 完成：

- [ ] G0.1 创建 builder slice S0 子合约（路径范围、Done 条件、Stop 触发）
- [ ] G0.2 派 builder_main 接 S0
- [ ] G0.3 builder 完成 → evaluator 跑 G0 验收：snapshot/restore dry-run/round-trip/secret 排除
- [ ] G0.4 G0 PASS → 才允许并行下发 S1/S2/S6
- [ ] G0.5 G0 FAIL → 阻塞，回退到 design 修复

## 4. Risk → Slice Mapping

| Risk | 缓解 Slice | Owner |
|------|-----------|-------|
| R1 PDF 误删 | S0+S3 | builder_main |
| R2 Skill 软链冲突 | S2 | builder_glm |
| R3 容器漂移 | S1 | builder_codex |
| R4 协调器破坏 | S6 | builder_main |
| R5 autopilot 误判 | S6 | builder_main |
| R6 Drive 伪 ok | S3+S4 | builder_main + builder_glm |
| R7 plugin 过度设计 | S4 | builder_glm |
| R8 evolution 误晋级 | S5 | builder_codex |
| R9 secret scan 漏检 | S1 | builder_codex |
| R10 MinerU OOM | S3 | builder_main |

## 5. Open Questions (Routing)

| OQ | Owner | 解答阶段 |
|----|-------|---------|
| OQ-1 installer OS 检测 | S1 builder_codex | S1 设计期 |
| OQ-2 secret 存放策略 | S1 builder_codex | S1 设计期 |
| OQ-3 skill registry 单/双写 | S2 builder_glm | S2 设计期 |
| OQ-4 plugin sandbox 策略 | S4 builder_glm | ADR-003 |
| OQ-5 evolution 实验流量分流 | S5 builder_codex | S5 设计期 |
| OQ-6 release 渠道 | S7 builder_main | S7 设计期 |
| OQ-7 state DB 迁移路径 | S6 builder_main | ADR-001 |
| OQ-8 autopilot 心跳信号源 | S6 builder_main | ADR-005 |
| OQ-9 容器是否含 LLM CLI | S1 builder_codex | S1 设计期 |
| OQ-10 Mirage Drive 文案 | S3 builder_main + UI | S3 设计期 |

## 6. Constraints Carried Forward

C1 单 slice 不超过单 builder session 可消化（每个 D/Done 控制在 7 条以内）。
C2 G0 通过前禁止任何破坏性迁移。
C3 容器测试不引用昊哥本机私有路径。
C4 plaintext secret 全程禁止。
C5 重活 background + idle + rate limit。
C6 现有 solar-harness 命令路径不破。
C7 Skill 必须既进 product 分发也安全调用。
C8 plugin 越权立刻拒载。
C9 Mirage 失败回退 native FS read-only。
C10 所有变更双写 status.json + state DB。

## 7. Definition of Done (Sprint Level)

- [ ] G0 PASS (S0 done)
- [ ] G1 smoke pass (existing solar-harness 不破)
- [ ] G2 container clean install pass (S1)
- [ ] G3 secret scan pass (S1)
- [ ] G4 skill registry + stable eval pass (S2)
- [ ] G5 storage migration pass (S3)
- [ ] G6 autopilot deadlock pass (S6)
- [ ] G7 release artifact pass (S7)
- [ ] A9 evolution loop pass (S5)
- [ ] A10 plugin manifest + integrations status pass (S4)
- [ ] 双签 (战略家 + 治理官) 通过
- [ ] PRD/Design/Plan/ADR 全部归档到 sprints + Knowledge

## 变更文件列表

| Slice | 新增文件 | 修改文件 |
|-------|---------|---------|
| S0 | `lib/product_snapshot.py`, `backups/product-snapshots/.gitkeep`, `tests/snapshot/test-s0-snapshot-roundtrip.sh` | `solar-harness.sh` (追加 product 子命令) |
| S1 | `installer/install.sh`, `installer/upgrade.sh`, `installer/doctor.sh`, `installer/restore.sh`, `config/defaults.yaml`, `.env.example`, `.gitignore`, `gitleaks.toml`, `docker/Dockerfile`, `docker/smoke-test.sh`, `hooks/pre-commit-secret-scan`, `hooks/pre-push-secret-scan`, `tests/installer/*` | — |
| S2 | `skills/registry.yaml`, `skills/builtins/*`, `lib/solar_skills.py`, `lib/skill_metrics.py`, `lib/skill_export.py`, `evals/skills/*`, `tests/skills/*` | `solar-harness.sh` (追加 skills 子命令) |
| S3 | `config/storage.solar.yaml`, `lib/source_manifest.py`, `lib/qmd_adapter.py`, `lib/mineru_extract.py`, `_sources/.gitkeep`, `tests/storage/*` | `lib/solar_mirage.py`, launchd plist |
| S4 | `plugins/*/manifest.yaml` (≥5), `schemas/plugin.schema.json`, `schemas/capability.schema.json`, `lib/capability_registry.py`, `lib/plugin_loader.py`, `tests/plugins/*` | `solar-harness.sh` (追加 integrations 子命令) |
| S5 | `lib/evolution_engine.py`, `lib/failure_miner.py`, `lib/eval_runner.py`, `evals/packs/*`, `experiments/*/hypothesis.md`, `tests/evolution/*` | — |
| S6 | `schemas/task-lifecycle.schema.json`, `lib/solar_state_db.py`, `lib/task_queue.py`, `lib/pane_lease.py`, `lib/autopilot.py`, `tests/control_plane/*` | `solar-harness.sh` (追加 autopilot/leases 子命令) |
| S7 | `release/build.sh`, `release/publish.sh`, `release/CHANGELOG.md`, `docs/upgrade-guide.md`, `docs/rollback-guide.md`, `ADR/ADR-002`, `ADR/ADR-004`, `tests/release/*` | — |

S0 已完成（Round 1 PASS，handoff 已写，等待 G0 评估）。

## 技术方案

### 核心架构

产品平台统一围绕 **8 个 slice** 和 **8 道 Gate** 构建，每道 Gate 是不可跳过的验收门禁：

```
状态机: queued → planning → active → reviewing → passed → finalized
Gate 依赖链: G0 → {G2,G3,G4,G6} → G5 → A10 → A9 → G7
```

### S0: Snapshot/Restore Foundation（已完成）

- `product_snapshot.py` 实现 snapshot/verify/restore/list 四条命令
- SHA-256 manifest + tar.gz archive；secret 按 fnmatch 模式在 `_collect_files()` 层排除
- DATA_ROOTS（Knowledge, .cache, logs, queues, backups, vendor）做 manifest 引用但不归档
- `solar-harness.sh` 新增 `product` 子命令 block，委托给 python3 调用
- round-trip 测试 15/15 PASS（py_compile + bash -n + dry-run + actual + verify + restore-dry + secrets + list）

### S1: Installer（容器隔离）

- `install.sh --non-interactive` 在 ubuntu:24 容器跑通完整 bootstrap 链
- `gitleaks.toml` + pre-commit/pre-push hook 确保 0 plaintext secret
- doctor.sh --json 输出 §2.2 schema（同 solar_mirage.py doctor schema）

### S2: Skill Platform

- `skills/registry.yaml` 为单一真相源；skill 按 builtin/user/generated 三类命名空间
- stable → default path；candidate/canary → 隔离 path，不默认注入
- eval pack 保证 min_score 才允许 promote

### S3: Storage & MinerU

- `_sources/papers/<sha-prefix>/` 为 PDF 永久存储；`_raw` 仅为 14 天 staging
- `solar_mirage.py` doctor 输出 §2.2 mount schema（8 挂点）
- MinerU 改为 launchd idle worker + memory cap，不阻塞用户 shell

### S6: Control Plane

- `solar_state.db`（6 表）与现有 status.json/events.jsonl 双写过渡
- pane lease 三态 automata：no_pane / busy / dead；autopilot 区分 busy 等待 vs dead 回收
- 合成 deadlock 演练通过才算 G6 PASS

### 关键技术约束

- G0 通过前禁止任何破坏性迁移（C2）
- plaintext secret 全程 0 容忍（C4）
- 所有 slice 不破坏现有 solar-harness 命令路径（C6）
- plugin 越权写立刻拒载（C8）

## 8. Planner Closeout

Planner produced PRD + Design + Plan; G0 first gate established. Next:

1. Coordinator/PM 创建 S0 子合约（path scope + Done + Stop + Round-Retry）。
2. 派 builder_main 接 S0；不要并行下发其他 slice。
3. evaluator 跑 G0；通过后再分发 S1/S2/S6。
4. 任何破坏性写动作必须先有 G0 PASS 证据。

Planner 在 G0 通过前不会推 status 到 active；维持 phase=planning_complete 等 PM/coordinator 拆分子合约。
