# PRD — Mirage Unified Virtual Filesystem For Solar

**Source**: Codex PM analysis from user request on 2026-05-08  
**Upstream**: https://github.com/strukto-ai/mirage  
**Priority**: P1  
**Lane**: data-plane  
**Handoff To**: planner  
**Created**: 2026-05-08T13:55:00Z

## 背景 / Context

Solar 当前已经有多套数据入口：`~/.solar/solar.db`、Cortex 代码和数据、`/Users/sihaoli/Knowledge` Obsidian vault、QMD/MinerU 文档索引、盘上项目文件、sprint 产物、以及潜在的 Google Drive。问题是这些入口对 agent 暴露方式不统一：有的靠 SQLite 查询，有的靠 grep，有的靠 `solar-harness wiki`，有的靠 MCP/技能，有的尚未接入。

Mirage 是 Strukto 的统一虚拟文件系统：把 Disk、Google Drive、GitHub、Postgres、Redis、Notion、Slack 等后端挂成一棵文件树，并通过熟悉的 `ls/cat/find/grep/jq` 风格 shell 操作。它默认不需要 host FUSE；FUSE 只是让 Claude Code/Codex 这类 CLI 看到真实挂载点的可选表面。

## 用户问题 / Problem

用户希望 Solar 能“无缝使用”我们已经开发的 Cortex 数据存储、知识库、盘上文件、Google Drive 等，而不是每次为不同来源写不同桥接命令。当前 Solar 的数据面是碎片化的：builder/planner/evaluator 需要记住多个命令和路径，协同开发时容易漏用知识、重复检索、或者绕过脱敏/权限边界。

## 用户目标 / Goals

- 给 Solar 增加一个统一虚拟文件系统层：`solar-harness mirage ...`。
- Solar agent 能用同一套命令访问 Solar DB、Cortex、Obsidian/QMD、sprint 产物、本地项目文件和 Google Drive。
- 默认安全：本地和远程来源默认只读，写入必须按 mount 显式允许。
- 保留现有知识库语义：Mirage 负责统一访问，Obsidian/QMD/Solar DB 仍负责知识提炼、索引、 provenance、accepted artifact。
- 对 coordinator/status-server 可观测：能看到 Mirage workspace 是否可用、哪些 mount 在线、哪些凭证缺失、最近查询/错误。

## 用户故事 / User Stories

- 作为 PM/Planner，我可以让 Solar 搜索 `/knowledge`、`/solar-db`、`/cortex`、`/drive`，不用记各自命令。
- 作为 Builder，我可以在隔离 workspace 里读取项目文件、知识库、sprint contract，不会误写 Google Drive 或用户主目录。
- 作为 Evaluator，我可以复现 builder 使用的数据来源，并检查每个命中来自哪个 mount。
- 作为用户，我能在 status 页面看到 Mirage 是否连上 Google Drive、Knowledge、Solar DB，而不是黑箱。

## 功能需求 / Requirements

### R1 — Mirage 安装与版本锁定

- 安装或 vendor Mirage，优先使用官方 Python package `mirage-ai` 或 TypeScript package `@struktoai/mirage-node`。
- 记录安装方式、版本、commit/package lock。
- 新增 `solar-harness mirage doctor` 验证 CLI/SDK、Python/Node、可选 FUSE、配置文件、权限。

### R2 — Solar Mirage Workspace Manifest

- 新增 `/Users/sihaoli/.solar/harness/config/mirage.solar.yaml`。
- 至少定义以下逻辑 mount：
  - `/knowledge` -> `/Users/sihaoli/Knowledge`，read by default。
  - `/raw` -> `/Users/sihaoli/Knowledge/_raw`，write allowed only for ingestion staging。
  - `/sprints` -> `/Users/sihaoli/.solar/harness/sprints`，read by default。
  - `/solar` -> `/Users/sihaoli/.solar`，read by default with secret filtering.
  - `/cortex` -> `/Users/sihaoli/.claude/core/cortex`，read by default。
  - `/projects` -> allowlisted local project roots only，不挂整个 `$HOME`。
  - `/drive` -> Google Drive resource，credential missing 时显示 degraded，不阻塞本地 mounts。
  - `/qmd` -> QMD/MinerU collection view or command adapter，至少支持 search/read bridge。

### R3 — Solar CLI

- 新增命令：
  - `solar-harness mirage install`
  - `solar-harness mirage doctor`
  - `solar-harness mirage workspace create|status|destroy`
  - `solar-harness mirage exec -- <command>`
  - `solar-harness mirage search <query>`
  - `solar-harness mirage mounts --json`
  - `solar-harness mirage provision --dry-run -- <command>`
- 所有命令必须支持 `--json` 或明确的 machine-readable 输出。

### R4 — Knowledge/QMD/Cortex Bridge

- `solar-harness mirage search <query>` 必须组合：
  - Mirage `grep/find` against `/knowledge`, `/sprints`, `/cortex`, `/projects`。
  - QMD search when `qmd` and `solar-wiki` collection exist。
  - Solar DB retrieval when `~/.solar/solar.db` exists。
- 输出必须包含 `mount`, `path`, `source_type`, `score_or_rank`, `snippet`, `provenance`。
- 不允许把全文直接塞进 prompt；默认最多 10 hits / 4,000 chars。

### R5 — Google Drive Integration

- 支持 Mirage Google Workspace/Drive resource as optional mount `/drive`。
- 凭证只从 env/keychain/user config 读取，不写入 sprint、events、Obsidian、Solar DB。
- 默认 read-only；写入、复制到 Drive、删除 Drive 文件必须显式 `--allow-write-drive`。
- 如果凭证缺失，`doctor` 和 status 显示 `warn/degraded`，但本地 mounts 必须可用。

### R6 — Agent Injection

- 给 planner/builder/evaluator 增加一段短 system prompt/runbook：
  - 优先通过 `solar-harness mirage search` 找跨源材料。
  - 需要读取原文时使用 `solar-harness mirage exec -- cat <path>`。
  - 需要写入知识库时仍走 `solar-harness wiki ingest/capture/export-accepted`，不要直接写正式 wiki 页面。
- 不让 Mirage 绕过 accepted artifact、redaction、knowledge ingest 的规则。

### R7 — Observability

- status-server `/status` 增加 `mirage` section：
  - enabled
  - package_version
  - workspace_id
  - mounts count/status
  - google_drive status
  - qmd status
  - last_command
  - last_error
  - last_probe_at
- Recent Events 写入：
  - `mirage_installed`
  - `mirage_workspace_created`
  - `mirage_command_executed`
  - `mirage_mount_degraded`
  - `mirage_secret_redacted`
  - `mirage_write_denied`

### R8 — Security Model

- 默认只读。
- Mount allowlist 必须显式，禁止默认挂 `/Users/sihaoli` 整个家目录。
- Secret redaction 覆盖 token、Bearer、sk-、api_key、refresh_token、client_secret、Google OAuth。
- 写操作必须记录 event，并区分 local staging write vs remote write。
- Mirage command 超时、输出大小、路径遍历、symlink escape 都要有测试。

## 验收标准 / Acceptance Criteria

- A1: `solar-harness mirage doctor --json` 能返回 installed/version/config/mounts/drive/qmd 状态，缺 Drive 凭证时为 warn 不是 error。
- A2: `solar-harness mirage workspace create --id solar-default` 能创建默认 workspace，至少 `/knowledge`、`/sprints`、`/cortex`、`/raw` 可用。
- A3: `solar-harness mirage exec -- 'find /knowledge -name "*.md" | head'` 有输出，且不能访问未 allowlist 的 `$HOME` 文件。
- A4: `solar-harness mirage search "Solar Harness Obsidian"` 同时返回 Knowledge/QMD/Solar DB 至少两类来源。
- A5: `/drive` 凭证缺失时本地 search/exec 不失败；凭证存在时 `ls /drive` 可用且默认禁止写。
- A6: 写入 `/raw` 可以作为 ingestion staging；写 `/knowledge/concepts`、`/drive`、`/solar` 默认被拒绝。
- A7: status-server `/status` 包含 `mirage` section，Recent Events 能看到 command/mount/write-denied 事件。
- A8: 测试套件覆盖 install/doctor/workspace/search/security/status，且不向真实 Google Drive 写入。

## 非目标 / Non-Goals

- 不替换 Obsidian wiki、QMD/MinerU、Solar DB、Cortex。
- 不把 Mirage 当成新的知识提炼器；知识提炼仍由 wiki ingest/agent skills 完成。
- 不要求本轮完成 Google OAuth 授权；本轮必须支持凭证缺失降级。
- 不默认启用 FUSE；FUSE 只作为后续增强或可选项。
- 不挂载整个 `$HOME` 或任意外部云盘。

## 约束 / Constraints

- 必须兼容当前 `solar-harness wiki`、QMD MCP、status-server 8765。
- 不引入需要 root 权限的默认路径。
- 不把 secrets 写入 `events.jsonl`、status、Obsidian、sprint files。
- 不阻塞 coordinator；Mirage probing 失败必须 fail-open。
- 所有测试默认使用 temp mounts/temp workspace。

## 风险 / Risks

- Mirage 仍处于快速迭代期，包名/API 可能变化，需要版本锁和 doctor。
- Google Drive OAuth 配置容易卡住，因此必须先实现 degraded mode。
- FUSE 在 macOS 可能需要额外内核扩展/权限，不应作为 P1 DoD。
- 如果直接暴露全盘，会破坏 Solar 当前安全边界。
- 如果不和 QMD/Solar DB 合并 ranking，`mirage search` 会退化成跨目录 grep。

## 开放问题 / Open Questions

- OQ1: **SDK 选型** — Python `mirage-ai` 还是 TypeScript `@struktoai/mirage-node` 作为 Solar 主集成面?Solar 主体是 bash + python,但 status-server 也在 python,Builder 倾向哪个?默认建议 Python (与 status-server/symphony 对齐),但需 Planner 确认。
- OQ2: **QMD Bridge 形态** — `solar-harness mirage search` 调 QMD 是走 MCP (mcp__qmd__query) 还是 CLI shell-out?MCP 限定 agent 上下文,CLI 更通用。建议先 CLI 桥接,MCP 作 future enhancement。
- OQ3: **`/drive` 凭证发现顺序** — env var (`GOOGLE_APPLICATION_CREDENTIALS`) > macOS Keychain > `~/.config/mirage/drive.json`?优先级和 fallback 行为待定。
- OQ4: **`/projects` allowlist 初始集合** — 默认空让用户自己加,还是预置 `~/Solar`/`~/.claude` 等已知 Solar 仓库?默认空更安全但 onboarding 体验差。
- OQ5: **`mirage search` ranking 融合** — grep 命中分数、QMD vector score、Solar DB credibility 三种信号如何混合?简单加权 vs reranker?P1 建议按 source_type 分组返回,不强行统一排名。
- OQ6: **Workspace 生命周期** — per-sprint workspace (跟 Symphony Sprint 2 workspace-manager 对齐) 还是 global `solar-default` 长期工作区?建议两者并存:default 给人交互,per-sprint 给 builder 隔离。
- OQ7: **FUSE 检测策略** — `doctor` 是检测但不强求,还是完全不提?macOS 需 macFUSE 内核扩展,默认假设没装。建议 doctor 探测 + 报告,但 P1 不依赖。
- OQ8: **secret redaction 单一职责点** — 在 Mirage 输出层做正则脱敏,还是在 status/event 写入层做?重复脱敏 vs 漏脱敏之间的权衡,需 Planner 决断单一职责点。

## 架构交接 / Planner Handoff

Planner 需要把本 PRD 转成实施计划，重点确认：

- 选择 Python SDK 还是 TypeScript SDK 作为 Solar 默认集成面。
- `mirage.solar.yaml` schema 和 mount allowlist。
- Google Drive credential discovery 和 degraded behavior。
- `solar-harness mirage` CLI 的最小实现边界。
- status-server/event schema。
- tests 使用 temp workspace，禁止真实 Drive 写入。

