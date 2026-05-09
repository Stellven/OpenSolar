# PRD — Solar Data Plane Closeout

**Source**: Codex PM analysis from user request on 2026-05-08
**Priority**: P1
**Lane**: reliability
**Handoff To**: planner
**Created**: 2026-05-08T18:01:00Z

## 背景 / Context

Solar 现在的数据基础设施呈现「组件丰富但操作不闭环」的状态：

- `solar-harness` 主线运行得好（coordinator + watchdog + bridge ledger + sprint artifacts 都是 2026-05-08 新鲜的）。
- 但 `~/.solar/solar.db` 里多张核心表 **2 个多月没更新**：`sys_data_ledger.last_checked` 停在 2026-02-06，`sys_resources.updated_at` 最新 2026-02-23，`knowledge_records` 最新 2026-02-27，`solar_kb_entries` 最新 2026-03-06，`cortex_passages` 最新 2026-02-16。
- `state` 表里有 `key=test_pragma value=test` 这种破坏 JSON 的脏行；`json_valid(value)=0` 没人盯。
- `sqlite3` 已经撞过 `database is locked`，写读并发没有统一的 `busy_timeout` / WAL 策略。
- `v_solar_resources` 99 条资源全部 `access_count=0` / `last_accessed_at=NULL`，**资源层活着但没人在用**（或者用了但没回写遥测）。
- `solar` CLI 跑的是 `~/.agents/skills/solar/scripts/run.sh` 写 `.solar/flow-state.json`，**根本没接到共享 Solar DB / harness 控制面**，但用户分不清 `solar` 和 `solar-harness` 是不是同一个东西。
- `cortex_task_capsules` 只有 1 条、`sys_capsule_executions` 0 条 — 一个分支架构上存在但操作上死透了。

这一切叠加的结果就是：**昊哥问"现在啥是真的？啥是假的？"，没人能给一句话答案。**

## 用户问题 / Problem

Solar 的多个数据面（runtime / DB / ledger / 资源遥测 / CLI）在静态层都存在，但**对不上同一份"现在什么是真的"**。具体表现：

1. 看 `solar-harness` 是活的 → 但看 `solar.db` 一些核心表像几个月前的化石。
2. 看 `v_solar_resources` 有 99 条 → 但 `access_count` 全 0，无法判断这层到底是死的还是只是没接遥测。
3. 看 `solar` CLI → 不知道它写的状态会不会回到 `solar-harness`。
4. 看 `state` 表 → 有 schema-脏的行混在热路径里。
5. 看并发 → 撞过 `database is locked`，但没有统一的 hardening 协议。

监护人没法在不打开十个文件的前提下回答："Solar 数据面里现在什么是源头真相？什么是衍生缓存？什么已经死了？"

## 用户目标 / Goals

- G1: 一条命令拿到 Solar 数据面体检报告（哪张表新鲜、哪张表过期、哪些行 schema 脏、哪些层是 ghost）。
- G2: `state` 表里 schema-脏行能被 **检测、备份、修复或隔离**，不再静默坐在热路径。
- G3: 所有 Solar/harness 写者用统一 `busy_timeout` + WAL（如适用），并发读写不再随机抛 `database is locked`。
- G4: 资源层（`sys_resources` / `v_solar_resources`）的状态与现实对齐：用了就回写遥测，没用就在 status 里标 dormant，不再装活着。
- G5: `solar` CLI 与 `solar-harness` 的关系被**明确**：要么接进共享数据面，要么在 status 里清楚标注它是本地轻量 flow，不再让用户混淆。
- G6: PASS 的 sprint artifact 有可观察的入库路径，不再卡在 raw 文件里出不来。
- G7: 操作员能从一份 runbook 知道：什么是真相、什么是缓存、怎么审计新鲜度、怎么修脏 state、怎么辨别 `solar` vs `solar-harness`。

## 用户故事 / User Stories

- 作为监护人，我跑一条 `solar-harness data-plane audit` 就知道 Solar 数据面"现在哪些层是活的、哪些是死的、哪些过期"。
- 作为 Solar 自己，我每次注入 KB 上下文时回写 `last_accessed_at`，让资源层遥测真实反映用法。
- 作为开发者，我并发跑两个写入 `~/.solar/solar.db` 的脚本，不再被 `database is locked` 随机击穿。
- 作为运维者，我看 `state` 表能确信里面没有 `value=test` 这种脏 JSON 行混进热路径。
- 作为新接触 Solar 的用户，我跑一次 `solar status` 就能看出 `solar` CLI 跟 `solar-harness` 是否同一个东西、是否共享状态。

## 功能需求 / Requirements

### R1 — Data Plane Health Audit 命令

- 提供一级入口：`solar-harness data-plane audit` 与 `solar-harness data-plane audit --json`。
- 输出必须覆盖至少：
  - `state`（含 `json_valid(value)=0` 计数）
  - `sys_data_ledger`（`last_checked` 新鲜度）
  - `sys_resources` / `v_solar_resources`（access 遥测真实性）
  - `cortex_sources` / `cortex_passages`
  - `solar_kb_entries`
  - `knowledge_records`
  - `cortex_task_capsules` / `sys_capsule_executions`（dead branch 警示）
  - bridge ledger (`~/.solar/codex-bridge/bridge-ledger.jsonl` 最近事件时间)
  - sprint artifacts 新鲜度（最近 PRD/contract/handoff/eval mtime）
- JSON 模式必含字段：`overall_status`、`checks`、`resource_usage`、`accepted_artifact_path`。

### R2 — State 表完整性修复

- audit 必须 flag `state.value` 里 `json_valid=0` 的行。
- 提供独立修复命令（如 `solar-harness data-plane repair-state --apply` / `--dry-run`）。
- 修复路径：备份原行（写入 `~/.solar/backups/state-quarantine/<ts>.jsonl`） → 尝试自动修复 → 失败则隔离（移到 `state_quarantine` 表或加 `quarantined=1` 列）。
- 修复完成后 `select count(*) from state where json_valid(value)=0` 必须 = 0，或全部已隔离出热路径。
- **禁止静默删行**。

### R3 — SQLite 并发 hardening

- 标准化所有 Solar/harness 写者打开 DB 的方式（提取一个 helper：Python `solar_db.connect()` / Bash `solar_sqlite_open` 包 `PRAGMA busy_timeout=...`）。
- 默认 `busy_timeout=5000ms`；如果 workload 容许，开 WAL 模式（journal_mode=WAL）。
- 提供至少一个回归测试 `~/.solar/harness/test-data-plane-db-concurrency.sh`，模拟 N 个并发写者 + M 个并发读者，无 `database is locked`。
- 残留 caveats（如 long-running TX）必须写进 runbook。

### R4 — Resource Usage 遥测如实

- 当 KB 上下文 hook（`solar-knowledge-context.sh` 等）实际命中资源时，必须回写 `sys_resources.last_accessed_at` + 自增 `access_count`（或新建一个 `sys_resource_access_log` 表）。
- audit 报告必须区分两种状态：
  - **active**: 最近 N 天有 access，遥测在动。
  - **dormant**: 没有 access，但层结构存在 → audit 标 `dormant_reason="no_retrieval_writes_observed"`。
- 不允许"99 条资源全 0 访问"这种 ghost 状态继续装活。

### R5 — `solar` CLI 与 `solar-harness` 的关系

- 必须二选一并实现 + 文档化：
  - **Option A — 接进共享数据面**：`solar start/status/stop` 写共享 `~/.solar/solar.db` + harness control plane（events.jsonl / bridge ledger）。
  - **Option B — 显式降级为本地 flow**：保留 `~/.agents/skills/solar/scripts/run.sh` 行为，但 `solar status` 必须**明确**显示「本地 flow，不写共享状态」，runbook 也要写。
- `solar status` 与 `solar-harness status` 必须能让用户在 5 秒内回答："这两个是同一个吗？谁在写共享状态？"
- 当前模糊中间态**不可接受**。

### R6 — Accepted Artifact 入库路径

- PASS 的 sprint artifact（plan/handoff/eval/contract）必须有可观察的入库路径：要么进 `solar_kb_entries` / `cortex_*`，要么有专门的 raw → ingest dispatch。
- 如果该路径目前被另一活跃 sprint（如 wiki-upload-ingest-closure）覆盖，**整合**而非重复实现，并在 audit 的 `accepted_artifact_path` 字段里指明依赖关系。
- 如果路径阻塞，audit 必须显式说明阻塞点（不允许沉默）。

### R7 — Operator Runbook

- 新增 `~/.solar/harness/docs/data-plane-closeout.md`，至少包含：
  - 「production truth」清单（哪些表/文件是源头）
  - 「derived cache」清单（哪些是衍生）
  - 怎么跑 audit、怎么读输出
  - 怎么修脏 state（含回滚步骤）
  - 怎么辨别 `solar` 与 `solar-harness` 哪个是当前活跃 runtime
  - DB 锁残留 caveats

## 验收标准 / Acceptance Criteria

- A1 — `solar-harness data-plane audit --json` 输出含 `checks` + `overall_status`，且 Python 能 parse。
- A2 — `select count(*) from state where json_valid(value)=0;` 修复后 = 0（或全部已隔离出热路径）。
- A3 — `bash ~/.solar/harness/test-data-plane-db-concurrency.sh` PASS，无 `database is locked`。
- A4 — audit JSON 含 `resource_usage`，且区分 active vs dormant 状态。
- A5 — `solar status` + `solar-harness status` 一眼能分辨"两者是否同一 runtime / 是否共享状态"。
- A6 — audit JSON 含 `accepted_artifact_path`；阻塞时显式说明。
- A7 — `test -f ~/.solar/harness/docs/data-plane-closeout.md` 通过；runbook 含修复 + 回滚步骤。

## 非目标 / Non-Goals

- 不重新设计整个数据库 schema。
- 不在本 sprint 迁移离开 SQLite。
- 不为了清理抽象而打断 `solar-harness` 当前生产 workflow。
- 不静默删历史数据"让指标好看"。
- 不重写 `cortex_*`、`sys_resources`、`solar_kb_entries` 这些既有表（只接遥测和审计）。
- 不在本 sprint 重构 `~/.agents/skills/solar/scripts/run.sh`（除非 Option A 选项被选中且必要）。

## 约束 / Constraints

### C1 — 不打断现有生产 workflow

- coordinator + watchdog + bridge + tmux pane 全部继续运行；不允许在交付期内重启 harness、kill coordinator、改 tmux pane assignment。
- 任何会 lock DB ≥10s 的操作必须放在维护窗口（用户显式确认），不在 audit / repair 默认路径里执行。

### C2 — 写入路径白名单

允许写：
- `~/.solar/solar.db`（修复 state、回写遥测，必须经 helper + busy_timeout）
- `~/.solar/backups/state-quarantine/`（脏行备份）
- `~/.solar/harness/state/data-plane/`（audit 中间状态、上次扫描时间）
- `~/.solar/harness/logs/data-plane-*.log`
- `~/.solar/harness/docs/data-plane-closeout.md`

禁止写：
- 既有 sprint artifact（不允许动 `*.contract.md` / `*.plan.md` / `*.handoff.md`）。
- `~/.solar/codex-bridge/bridge-ledger.jsonl`（只读）。
- `~/.agents/skills/solar/`（除非 Option A 必须改）。

### C3 — 修复必须可逆

- 任何 state repair 必须先备份原行到 `state-quarantine/`，可一键回滚（如 `solar-harness data-plane repair-state --rollback <ts>`）。
- repair 默认 `--dry-run`；`--apply` 必须显式传。
- 不允许 cascading delete / drop table / 重命名 column 来"快速修复"。

### C4 — 并发 hardening 不破坏既有读者

- WAL 模式启用前必须确认所有现有读者兼容（包括 sqlite3 CLI、Python sqlite3、bash heredoc 调用）。
- 如果某 writer 不能切 WAL（如外部脚本依赖 rollback journal），保留 rollback journal 模式并加 `busy_timeout`，不强行切。
- 回归测试必须覆盖现有热路径：`solar-knowledge-context.py`、`coordinator.sh` 写 events、`session.sh append`。

### C5 — Audit 是只读默认

- `audit` 默认**只读**：不写 DB、不动 state、不创建 lock。
- 写动作（repair / 标 dormant / 回写 telemetry）必须是独立子命令（`repair-state`、`mark-dormant`、`record-access`），不与 audit 共享代码路径。

### C6 — 资源遥测回写不引入新依赖

- `last_accessed_at` 回写必须用现有 `solar_db` helper，不引入 ORM、不上 SQLAlchemy、不上 async pool。
- 回写动作要节流（同一资源 1 分钟内多次 hit 只回写 1 次），避免遥测自身变成 lock 来源。

### C7 — Option B 优先（如选）

- 如果 `solar` CLI 选 Option B，必须：
  - `solar status` 输出显式标 `runtime=local-flow`、`shared_state=false`。
  - runbook 在第一段就讲清楚两者关系。
  - **不允许**保留模糊中间态。

### C8 — 不重复造 ingest

- accepted artifact 入库路径必须复用现有 `solar-harness wiki ingest`（如果还在跑）或现有 `solar_kb_entries` 写入逻辑；不允许新建第三套 ingest 通道。

## 风险 / Risks

| # | 风险 | 触发条件 | 影响 | 缓解 |
|---|------|----------|------|------|
| RK1 | WAL 切换破坏既有读者 | 某个老脚本以 rollback journal 假设打开 DB | 读到不一致快照 / 写失败 | 切 WAL 前跑 `pragma journal_mode` 探测兼容性；提供 `--no-wal` 退回选项 |
| RK2 | state 修复误删用户配置 | quarantine 逻辑把合法但不合 schema 的行也圈进去 | 配置丢失 | 默认 dry-run + 备份；`--apply` 必须显式；保留 7 天回滚窗口 |
| RK3 | 资源遥测节流被绕过 | 高频 hook 调用回写打爆 SQLite 并发 | DB 锁 + audit 自激震荡 | 节流（每资源 1 分钟 1 次）+ 写入用 INSERT OR IGNORE 模式；监控 lock 发生率 |
| RK4 | Option B 落地后用户更困惑 | runbook 没讲清，user 看到两个 status 命令仍混 | 信任流失 | runbook 第一段带 1 张对比表；`solar status` 顶部一行总结性输出 |
| RK5 | accepted artifact 入库被另一 sprint 阻塞 | wiki-upload-ingest-closure 还在 P0 队列 | A6 验收无法干净通过 | audit 显式 surface 阻塞依赖 sprint id；不假装完成 |
| RK6 | 并发回归测试只覆盖快路径 | 测试只跑 5 秒、10 个并发 | 实际生产更长更高并发仍 lock | 测试至少 30s + 50 并发 + 真实负载脚本（events.jsonl 写 + KB hook 读） |
| RK7 | audit 输出膨胀变成噪音 | 每张表 50 行检查 → 500 行 JSON | 用户看不下去 | overall_status + 红黄绿三色摘要在最前；详情可 `--verbose` |
| RK8 | dead branch 误判 | `cortex_task_capsules=1, executions=0` 实际是新接的 feature | 把活的标 dormant | 标 dormant 前要求人工 ack（或 audit 输出 `pending_review` 而不是直接 dormant） |
| RK9 | repair 操作期间 coordinator 写入冲突 | repair 长事务撞上 coordinator append events | events 丢 | repair 默认走维护窗口（用户输入确认）；非维护窗口只允许 dry-run |
| RK10 | runbook 被遗忘失修 | 文档写完无人回头看，半年后说法过期 | 信任退化 | runbook 顶部 metadata：`last_verified=YYYY-MM-DD`；audit 检查这个时间，超 90 天 surface 提醒 |

## 开放问题 / Open Questions

- OQ1 — **WAL 切不切？** 需要 architect 跑兼容性矩阵：列出所有 writer/reader，哪些可以切 WAL、哪些必须留 rollback journal。建议输出一个 `db-writers-matrix.md` 给 builder 落地。
- OQ2 — **Option A vs Option B（`solar` CLI）**：架构师必须给出推荐 + 理由。当前倾向 Option B（解耦本地 flow，标清楚），但需 architect 确认是否会丢失 `solar start/stop` 的协同价值。
- OQ3 — **`cortex_task_capsules` 死活定性**：1 条 capsule + 0 execution 是真死还是新 feature 占位？需要找到 capsule 来源 commit 判断；如果是新 feature，audit 标 `pending`，不标 dormant。
- OQ4 — **资源遥测的 schema**：是给 `sys_resources` 加列，还是新建 `sys_resource_access_log` 单独表？前者改动小但影响读者，后者干净但要新建索引。
- OQ5 — **accepted artifact 入库的归属**：本 sprint 自己实现入库 hook，还是等 `wiki-upload-ingest-closure` PASS 后只接其入口？前者风险是重复实现，后者风险是被卡。需要 planner 协调依赖。
- OQ6 — **`state` 表脏行的来源**：`key=test_pragma value=test` 是测试遗留还是某个 hook bug 在产？修复前应找到来源，否则修了还会再脏。

## 架构交接 / Planner Handoff

### 切片建议（Planner 已经分过 3 切片，PRD 与之对齐）

- **S1 — Audit + State 修复 + DB 并发 hardening**（覆盖 R1/R2/R3，A1/A2/A3）
  - 先把"看见"做出来（audit 命令），再修脏 state（repair-state），再统一 DB open（concurrency hardening）。
  - 必须输出：`solar-harness data-plane audit`、`repair-state`、`solar_db` helper、`test-data-plane-db-concurrency.sh`。
- **S2 — Resource Usage 诚实标注 + Accepted Artifact Path**（覆盖 R4/R6，A4/A6）
  - 先决定 OQ4（schema 怎么加）、OQ5（入库归属）。
  - 必须输出：`record-access` 子命令、audit JSON 增加 `resource_usage` + `accepted_artifact_path` 字段。
- **S3 — `solar` vs `solar-harness` 关系 + Runbook**（覆盖 R5/R7，A5/A7）
  - 必须先决定 OQ2（A or B）。
  - 必须输出：`solar status` 升级、`solar-harness status` 显示 runtime 关系、`docs/data-plane-closeout.md`。

### Planner 必须先解决（before contract finalization）

1. OQ1 (WAL 兼容矩阵) — 决定 hardening 策略上限。
2. OQ2 (Option A/B) — 决定 S3 工作量。
3. OQ4 (telemetry schema) — 决定 R4 的入侵深度。
4. OQ5 (artifact path 归属) — 决定 S2 是否依赖另一活跃 sprint。

### 必须复用的现有基础设施

- `~/.solar/solar.db`（不要新建 db 文件）。
- `~/.solar/codex-bridge/bridge-ledger.jsonl`（audit 只读消费）。
- 现有 `events.jsonl` schema 与 `session.sh append` 接口。
- 现有 `solar-knowledge-context.py`（接 R4 遥测回写）。
- 现有 `solar-harness wiki ingest`（接 R6 入库）。

### 不允许的实现路径

- ❌ 新建第二个 SQLite 文件分担数据。
- ❌ 引入 ORM / async pool / 后端 schema 迁移工具。
- ❌ 在 PRD/contract 范围外修改 `solar` CLI 的核心 flow 行为（除非 Option A 被选中）。
- ❌ 默认开启 WAL 不做兼容探测。
- ❌ 用「删除脏行」当 state 修复方案。

### Escalation 条件

builder 遇到下列情况，必须停下来回 PM/planner，**不允许自己加范围**：

- 发现 WAL 不可切（多个 writer 无法兼容），需要降级方案。
- 发现 OQ6 来源是某个仍在运行的 hook（修了还会脏），需要先关 hook 来源。
- accepted artifact 入库路径被另一活跃 sprint 完全占用，需要协调依赖顺序。
- repair-state 在 dry-run 时发现脏行数量级远超预期（>100 行），需要重新评估隔离策略。

### 验收顺序约束

A1 → A4/A6（audit 必须先工作）→ A2（state 修复要 audit 标记的行）→ A3（concurrency 测试不能跟 repair 并发）→ A5（CLI 关系）→ A7（runbook 最后写，引用前面所有产出）。
