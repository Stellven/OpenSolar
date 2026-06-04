# PRD — Understand-Anything Background Knowledge Graph for /Users/lisihao/Solar

**Source**: 用户请求（intent=execute, 立即执行上一个提议）
**Priority**: P1
**Lane**: knowledge-ingest / background-job
**Sprint ID**: `sprint-20260527-understand-anything-background-knowledge-graph`
**Handoff To**: planner
**Created**: 2026-05-28 (PM gate_missing_prd backfill)
**Title**: Understand Anything 全仓知识图后台生成（分阶段、非阻塞）

## 背景 / Context

- Lum1104/Understand-Anything 是 Claude Code 上的开源 understand-anything 插件，能对一个 repo 跑全仓静态分析，输出知识图 (`knowledge-graph.json`) + 配置 (`config.json`) + meta (`meta.json`)，下游 `understand-dashboard / chat / diff / explain / onboard / domain / knowledge` 7 个命令依赖这套产物。
- 上游 Epic `epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything` 已经在 5/26 拆出 5 个子 sprint（S01 requirements / S02 architecture / S03 core-runtime / S04 orchestration-ui / S05 verification-release），S01 PM 切片今天 (5/27) 已修复 PRD schema gate。
- 本 sprint 是平行的运行时执行 sprint：直接在 `/Users/lisihao/Solar` 上跑一次完整 understand-anything 流水线，**以后台非阻塞方式**产出 knowledge graph，给 dashboard / chat / diff / explain / onboard / domain / knowledge 提供首份真实数据。
- 关键约束：**后台跑，不阻塞前台 dispatch 链**。Solar Harness 4-pane 协同正在持续派发其他 sprint，understand-anything 全仓分析可能跑 10-60 分钟，必须 background-job 不阻 chain-watcher。
- 状态：4-node DAG（U1 preflight → U2 background run → U3 verify → U4 handoff & resume contract）已经写入 `task_graph.json`，coordinator 已经派给 builder pane 但 PRD 缺失触发 `gate_missing_prd`，PM 拉回写 PRD。本切片即修复入口。

## 用户问题 / Problem

- **PB-1 全仓分析时间不可预测**：understand-anything 对 `/Users/lisihao/Solar` 这种 mono-repo 可能跑 10-60 分钟，前台跑会卡住 chain-watcher + 4-pane 调度。
- **PB-2 没有运行时预检**：Claude CLI 是否 loggedIn、understand-anything 插件缓存是否在、Node/pnpm 是否就绪、目标仓库是否可写 — 任一条件不满足都会让长跑任务白跑。
- **PB-3 增量/恢复语义不明**：之前可能跑过、产生过部分 `.understand-anything/` 产物；本次不应该无脑重启，应该优先增量恢复。
- **PB-4 验证不可程序化**：跑完后下游 7 个 `/understand-*` 命令需要 `knowledge-graph.json` + `meta.json` 等产物存在且可 JSON 解析，需要明确验证接口。
- **PB-5 后续 operator 化接入路径不清**：本次后台跑是一次性 dispatch，但产物是为后续 operator-runtime（lease-based fleet）准备的入口；需要 handoff 写明恢复入口与非阻塞约束。
- **PB-6 PRD 缺失触发 coordinator gate**：4-node DAG 已就位但 PRD 不存在，gate_missing_prd 把 sprint 拉回 PM。

## 用户目标 / Goals

1. 在 `/Users/lisihao/Solar` 上跑一次完整 understand-anything 流水线，产出可被 dashboard / chat / diff / explain / onboard / domain / knowledge 消费的知识图。
2. 全程**后台非阻塞**，不阻塞 Solar Harness 其他 sprint 调度。
3. 启动前做运行时预检，避免长跑后才发现 Claude 未登录 / Node 缺失 / 路径不可写等致命问题。
4. 产物增量恢复优先；已有部分产物不无脑重启。
5. 验证 + handoff 写明恢复入口和未完成阶段，为后续 operator 化接入留口。

## 用户故事 / User Stories

- **US-01 (Solar 主用户)**：作为 Solar 主用户，我希望知识图后台跑出来后能直接用 `/understand-dashboard` 等 7 个命令，不需要再手工跑 `/understand --language zh`。
  - 验收：U2 节点 acceptance "后台任务真实启动" + "若成功完成则生成 knowledge-graph.json" + "不得要求用户手工在前台输入 /understand"。
- **US-02 (Chain-watcher / 4-pane)**：作为 Solar Harness 调度，我希望这个 sprint 不卡住其他 sprint。
  - 验收：U2 write_scope 严格限定到 `/Users/lisihao/Solar/.understand-anything`；不动 `~/.solar/harness/lib/` 任何 pane 调度代码。
- **US-03 (Operator runtime)**：作为后续 operator-runtime (lease-based fleet) 维护者，我希望本 sprint 留下"恢复入口"配置，下次可以 lease 一个 actor 继续跑。
  - 验收：U4 handoff 明确"恢复入口与后续非阻塞策略"。
- **US-04 (Pre-flight 验证者)**：作为运维，预检失败时应该明确停在何阶段，不要进 U2 长跑。
  - 验收：U1 acceptance "明确 Claude 当前是否 loggedIn=true" + "明确插件缓存目录可读" + "明确 Node 与 pnpm 可用" + "写出预检 handoff"。
- **US-05 (Downstream 7 命令消费者)**：作为 `/understand-dashboard / chat / diff / explain / onboard / domain / knowledge` 命令，我希望 `knowledge-graph.json` + `meta.json` 存在且可 JSON 解析。
  - 验收：U3 acceptance "若 knowledge-graph.json 存在则能被 JSON 解析" + "若 meta.json 存在则记录 commit/hash 等信息"。
- **US-06 (PM / Coordinator)**：作为 coordinator，PRD 一旦缺失就拉回 PM；本切片即修复入口。
  - 验收：PRD 存在 + `validate.sh prd` PASS + status.json phase=prd_ready。

## 功能需求 / Requirements

- **FR-1 U1 Preflight**：检查以下 4 项，全部通过才进 U2；任一失败写预检 handoff 说明原因并停止。
  - Claude CLI `loggedIn=true`
  - understand-anything 插件缓存目录可读（`~/.claude/plugins/...`）
  - Node + pnpm 版本可用
  - `/Users/lisihao/Solar` 可写 + `.understand-anything/` 状态（fresh / partial / complete）
- **FR-2 U2 Background Run**：在后台 pane 运行 `/understand --language zh` 对 `/Users/lisihao/Solar`。
  - 后台执行（`nohup` / `tmux new-window -d` / `subprocess.Popen` 等），不阻塞前台。
  - 允许 10-60 分钟长跑；watchdog 心跳但不 kill。
  - 已有部分产物时增量/恢复优先（保留 `.understand-anything/intermediate/*` 等）。
  - 不允许要求用户手工在前台输入 `/understand`。
  - write_scope 严格限定到 `/Users/lisihao/Solar/.understand-anything`。
- **FR-3 U3 Verify**：U2 结束后验证产物。
  - `.understand-anything/knowledge-graph.json` 存在 → `python3 -c "import json; json.load(open(...))"` 不抛异常。
  - `.understand-anything/meta.json` 存在 → 含 commit / hash / language 字段。
  - 若未完成，明确停在何阶段（preflight / collect / extract / synth / write）。
  - 写验证 handoff 到 `<sid>.U3_verify_graph_artifacts-handoff.md`。
- **FR-4 U4 Handoff & Resume Contract**：写 `<sid>.handoff.md` 含：
  - 本次后台任务完成度（哪些 stage done / which not）。
  - 下次恢复入口（命令行 / `.understand-anything/state.json` 引用）。
  - 后续非阻塞策略（如何让 operator-runtime lease 一个 actor 继续跑）。
- **FR-5 PRD schema 合规**：通过 `validate.sh prd`（本切片即修复 gate_missing_prd）。
- **FR-6 status.json 更新**：完成后 `phase: spec → prd_ready`，`history` 追加 `prd_completed`。

## 验收标准 / Acceptance Criteria

| AC | 标准 | 节点 |
|----|------|------|
| AC-1 | U1 预检 4 项全过或停止 + 写预检 handoff | U1 |
| AC-2 | U2 后台真实启动（不是只输出计划）+ `.understand-anything/config.json` 至少写出 | U2 |
| AC-3 | U2 成功完成时生成 `knowledge-graph.json` | U2 |
| AC-4 | U2 不要求用户在前台手工输入 `/understand` | U2 |
| AC-5 | `knowledge-graph.json` 可被 `python3 -c "import json; json.load(open(...))"` 解析 | U3 |
| AC-6 | `meta.json` 含 commit/hash 信息 | U3 |
| AC-7 | U3 verify handoff 写出，明确成功/失败阶段 | U3 |
| AC-8 | U4 handoff 说明完成度 + 恢复入口 + 非阻塞策略 | U4 |
| AC-9 | 全程不阻塞前台 chain-watcher 或其他 sprint 调度 | 全 |
| AC-10 | 0 个仓库代码被改（只动 `.understand-anything/` 和 sprint handoff） | 全 |
| AC-11 | 0 个 secret 打印（API key / OAuth / token） | 全 |
| AC-12 | PRD 存在 + `validate.sh prd` PASS + status.json phase=prd_ready | 本切片 |

## 非目标 / Non-Goals

- 不写 understand-anything 插件源代码（只调用，不开发 fork）。
- 不验证 dashboard / chat / diff 等 7 个 `/understand-*` 命令本身（那是上游 epic 的 S04 orchestration-ui sprint 范围）。
- 不调整 Claude Code 全局 `~/.claude/settings.json` 已有键。
- 不重启 Solar Harness / coordinator / chain-watcher / 4-pane。
- 不动 `~/.claude/plugins/` 插件源（只读）。
- 不在本切片做"知识图二次处理"（如 embedding / clustering / 入 Solar DB），那留给后续 ingestion sprint。
- 不删除已有 `.understand-anything/` 产物（增量恢复优先）。
- 不要求实时进度回报，只要后台 watchdog 心跳 + 最终产物验证。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane / Claude CLI + understand-anything 插件。
- **路径白名单**：
  - U1 写 `<sid>.U1_preflight_runtime-handoff.md`
  - U2 写 `/Users/lisihao/Solar/.understand-anything/` 目录下任意文件（understand-anything 自己的产物）
  - U3 写 `<sid>.U3_verify_graph_artifacts-handoff.md`
  - U4 写 `<sid>.handoff.md`
  - PM 切片 (本切片) 写 `<sid>.prd.md` + `<sid>.prd.html` + `<sid>.status.json`（phase/history 更新）+ `<sid>.ack-*.json`
- **不动其他 path**：禁动 `~/.solar/harness/lib/` / `tools/` / `schemas/` / `templates/` / Solar 仓库源代码（仓库 git history 必须干净）/ `~/.claude/plugins/` / `~/.claude/settings*.json`。
- **后台必须真后台**：U2 必须用 `nohup` / `tmux new-window -d` / `subprocess.Popen(start_new_session=True)` 等，**不允许**前台 blocking call。
- **增量恢复**：U2 检测到 `.understand-anything/state.json` 或 `intermediate/*` 时优先恢复，不无脑 `--rebuild`。
- **不打印 secrets**：所有日志写盘前 redact（OAuth code / API key / token）。
- **API 兼容**：不破坏 `solar-harness context inject / session evaluate / intent-gateway capture`。
- **PM 角色边界**：不写代码 / 不动 status 到 implementation / 不跳 PRD schema / 不直接派 builder。

## 风险 / Risks

| 风险 | 影响 | 缓解 |
|------|------|------|
| understand-anything 跑 60 分钟+ 阻塞 chain-watcher | 整 Solar 调度卡住 | FR-2 强制后台启动（`nohup` / `tmux new-window -d`），write_scope 严限 `.understand-anything/` |
| Claude CLI 未登录 → U2 一开始就失败 | 60 分钟白跑 | U1 preflight 检 `loggedIn=true`；失败立刻停 |
| `.understand-anything/` 已有 partial 产物，被 U2 误覆盖 | 历史进度丢 | FR-2 增量恢复优先；保留 `intermediate/*` |
| `knowledge-graph.json` 产出但 schema 不对，下游 7 个 `/understand-*` 命令读不了 | dashboard 启动失败 | U3 验证 JSON parse + meta.json 字段；不通过则写明 fail 阶段 |
| understand-anything 插件版本与 Claude CLI 不兼容 | U2 启动报错 | U1 preflight 检插件缓存目录可读；记录版本号留证据 |
| 后台 pane 被其它 sprint 抢占（lease 冲突） | U2 中断 | 与 sprint-20260523-lease-based-model-fleet-runtime 协同，本 sprint U2 应当独立 actor lease |
| Node / pnpm 版本不匹配（understand-anything 内部需要） | U2 启动报错 | U1 preflight 检 Node + pnpm |
| `/Users/lisihao/Solar` 仓库 git status 不干净，understand-anything 把 uncommitted change 也分析进去 | knowledge graph 含临时代码 | U1 可选检查 `git status --porcelain`；不阻断但留 evidence |
| 插件产物被推到 Solar 仓库 git history | 仓库污染 | `.understand-anything/` 应该已在 .gitignore；U1 验证 + 若没有则警告 |
| API key 通过 understand-anything 日志打印 | 安全事故 | redact + U2 日志写盘前过滤 |
| 长跑期间 Mac mini 休眠 / 进程被系统 kill | U2 中断 | U2 应当用 `caffeinate -i nohup ...` 防止 idle sleep |
| PRD 缺失触发 gate_missing_prd 循环 | sprint 卡 | 本切片即修复 ✅ |
| Coordinator 多次重试 dispatch 失败（事件 seq 6/13/17/20 显示 `pane_not_idle`） | 链路抖动 | TUI Pane Recover sprint 的 hygiene registry 处理；本 sprint 不修这个根因 |

## 开放问题 / Open Questions

- **OQ-01** `/Users/lisihao/Solar` 仓库到底多大？文件数 / 代码行数 / 子目录深度，决定 U2 跑时长。**Owner**：U1 preflight 顺便测一遍 `du -sh` + `find /Users/lisihao/Solar -type f | wc -l`。
- **OQ-02** understand-anything 是否支持 `--resume` 或 `--incremental`？需要插件文档确认。**Owner**：U1 preflight 验证。
- **OQ-03** `.understand-anything/state.json` schema 是什么？目前是猜的，需要看插件源码或之前产物。**Owner**：U2 实施时确认。
- **OQ-04** Claude CLI 是否能在 `tmux new-window -d` 起的非 TTY 环境运行？还是必须 TTY？影响后台 launcher 选型。**Owner**：U1 / U2 实施确认。
- **OQ-05** Mac mini 24/7 是否真不休眠？需要 `caffeinate` 还是足够？**Owner**：U2 实施确认。
- **OQ-06** 知识图产出后是否需要立刻入 Solar DB / Obsidian / QMD 索引？还是先静置等下次 ingestion sprint？**Owner**：后续 ingestion sprint。
- **OQ-07** 若 U2 跑了一半失败，下次"恢复入口"是什么命令？是 `/understand --resume`、`/understand --language zh`（自动 detect partial），还是其他？**Owner**：U2 / U4 决议。
- **OQ-08** 是否需要在 U4 完成后主动通知 operator-runtime sprint 的 lease broker 注册一个 long-running actor？**Owner**：跨 sprint 协调 / 未来 lease integration sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（schema 11 节齐全）。
- `<sid>.dispatch.md`（coordinator emit）+ `.intent.json`（intent=execute, confidence=0.9）+ `.runtime-context.json`。
- `<sid>.task_graph.json`（4-node DAG：U1 → U2 → U3 → U4）。
- `<sid>.events.jsonl`（含多次 `pane_not_idle` 失败，提示 TUI hygiene 问题）。
- 上游 epic：`epic-20260526-在-mac-mini-的-claude-code-环境安装并集成-lum1104-understand-anything`（含 S01-S05 子 sprint）。
- 相邻 sprint：`sprint-20260523-lease-based-model-fleet-runtime`（actor lease broker）、`sprint-20260527-p0-...-tui-pane-recover-与-clean-pane-生命周期治理`（hygiene registry）。

### 4-Node DAG Execution Map (来自 task_graph)

| Node | Goal | Write Scope | Acceptance 关键 |
|------|------|-------------|-----------------|
| U1 preflight_runtime | 检查 Claude loggedIn / 插件缓存 / Node+pnpm / 目标仓写入 + `.understand-anything` 状态 | `<sid>.U1_preflight_runtime-handoff.md` | 4 检查全过或停止 |
| U2 run_understand_zh_background | 后台跑 `/understand --language zh` 对 `/Users/lisihao/Solar`，增量恢复优先 | `/Users/lisihao/Solar/.understand-anything` | 真后台启动 + ≥ `config.json` 写出 + 成功则 `knowledge-graph.json` + 不要前台交互 |
| U3 verify_graph_artifacts | 验证 `knowledge-graph.json` / `meta.json` 可解析 + 失败时停在何阶段 | `<sid>.U3_verify_graph_artifacts-handoff.md` | JSON parse + meta.json commit/hash + handoff 写出 |
| U4 handoff_resume_contract | 完成度 + 恢复入口 + 非阻塞策略 | `<sid>.handoff.md` | 写出 + 明确恢复入口 |

### Planner 必须产出

- `*.plan.md`：把 U1-U4 拆成 ≤ 4 个 builder task（每节点 1 task 即可）；含每节点的 pre/post check 和 stop_rule 引用。
- 不需要新 `task_graph.json`（已存在 4-node DAG）；但需要在 `*.plan.md` 中确认 DAG 正确 + 标 `request_type=ingestion` 或类似。
- `*.handoff.md`：填写 owner / stop_rule / accepted_artifacts 路径。

### 不在 PM 范围、必须 Planner / Builder / Evaluator 处理

- **Planner** 把 U1-U4 4 节点写成 plan.md（每节点 ≤ 2 task：pre-flight check + execute），含 background launcher 选型（`nohup` / `tmux new-window -d` / `caffeinate`）。
- **Builder (U1)** 实施 preflight checks，输出预检 handoff。
- **Builder (U2)** 实施后台启动 + 增量恢复；watchdog 心跳；不阻塞前台。
- **Builder (U3)** 实施 JSON parse + meta.json 字段验证。
- **Builder (U4)** 写 handoff 含恢复入口（命令行 + state.json 引用）。
- **Evaluator** 跑 12 条 AC 校验 → eval verdict。
- **后续 ingestion sprint** 把知识图入 Solar DB / Obsidian / QMD（不在本切片范围）。
- **后续 dashboard sprint** 跑 `/understand-dashboard / chat / diff / explain / onboard / domain / knowledge` 并截图验证（属于上游 epic S04 范围）。

### 给 Coordinator 的明确指令

- **不要重做 task_graph**：4 节点 DAG 已就位。
- **PRD mtime 已刷新**：coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 `gate_missing_prd` → 进入 planner（chain-watcher 自动接）。
- **TUI Pane Recover 协同**：事件 seq 6/13/17/20 显示 `pane_not_idle` 反复失败，说明当前 pane 卡住；建议先让 TUI Pane Recover sprint (`sprint-20260527-p0-...-clean-pane-生命周期治理`) 落地后再 dispatch builder，或选另一个 clean pane。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context)。Capability injection 含 ATLAS / Autoresearch / Empirical Research / Everything Claude Code / MarkItDown / Solar-Harness Runtime / Superpowers / agency-agents / gstack / solar-intent-engine / solar-knowledge-ingest — 全部 `injectable_only`。
