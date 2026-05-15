# PRD — Solar KB default retrieval + Obsidian seamless sync

**Source**: Codex PM analysis from user request on 2026-05-08
**Priority**: P0
**Lane**: reliability
**Handoff To**: planner
**Created**: 2026-05-08T06:45:00Z

## 背景 / Context

用户要求全面分析 Solar 的知识库是否已经默认、自动使用，以及是否能和 `/Users/lisihao/Knowledge` Obsidian 知识库无缝打通。当前分析结论是：Solar 已经有大量数据库知识资产和若干 hooks，但默认上下文注入仍然偏浅；Obsidian 集成能接收导出和上传材料，但还没有成为 Solar 默认检索层的一部分。

## 用户问题 / Problem

Solar 操作者以为系统已经能自动使用长期知识，但实际行为不稳定：hooks 会读取 `~/.solar/solar.db`，却主要注入启动片段、提醒或异步学习，不会稳定地对每个知识相关请求执行有来源的检索。Obsidian vault 当前可以沉淀知识，但其页面没有默认进入 Solar 的统一搜索/FTS/cortex 检索链路，导致“存进去了”和“agent 会自动用”之间存在断层。

## 用户目标 / Goals

- 让 Solar 在知识相关 prompt 中默认注入有来源、有限长、低延迟的知识上下文。
- 让 `/Users/lisihao/Knowledge` Obsidian vault 成为 Solar 可检索知识源，而不是只作为导出目录。
- 保持 fail-open：DB、vault、同步任务异常时不能卡住主 agent。
- 让状态页清楚显示 Solar KB、Obsidian sync、raw ingest、dispatch 的健康状态。
- 修复已发现的 hook/schema 问题，避免“看似自动，实际静默失败”。

## 用户故事 / User Stories

- 作为 Solar 操作者，我问一个历史知识/系统记忆问题时，agent 自动拿到 Solar DB 或 Obsidian 的相关证据，而不是只提示我手动查。
- 作为 Solar 操作者，我把网页、PDF、markdown 放进 `/Users/lisihao/Knowledge/_raw/` 后，系统能定时提取、同步、索引，并能被后续 Solar 检索命中。
- 作为 Solar 操作者，我打开状态页能看到最后同步时间、pending 文件数、索引数、最近错误，而不是一直 `Loading...` 或不可解释空状态。
- 作为 builder，我有清楚的文件级边界：retrieval hook、Obsidian sync、status/tests 分 slice 并行，不互相覆盖。
- 作为 evaluator，我能用合约里的 verify 命令逐条判定是否真的默认使用、真的索引 Obsidian、真的 fail-open。

## 功能需求 / Requirements

- 新增或完善 `solar-knowledge-context` 检索路由，默认查询 `~/.solar/solar.db` 和 `/Users/lisihao/Knowledge` 索引。
- 新增 UserPromptSubmit hook wrapper，只在知识相关 prompt 下触发，默认注入不超过 2,000 chars。
- 修复 `~/.claude/hooks/memory-influence.sh` 对 `evo_memory_semantic` 的字段使用和 SQL 逻辑优先级。
- 更新 `~/.claude/core/cortex/knowledge-sync.ts` 或同等同步入口，使 `/Users/lisihao/Knowledge` 成为 first-class Obsidian vault source。
- 保留并加固 `solar-harness wiki import-solar-db` 的 DB-to-Obsidian 增量导出能力。
- 为 status server 增加 `solar_kb` 和 `obsidian_sync` payload。
- 提供自动调度：launchd、harness daemon 或 capture-server scheduler 均可，但必须可观测、可停用、fail-open。
- 提供端到端测试，覆盖默认检索、vault 索引、DB 导出、hook fail-open、状态 JSON。

## 验收标准 / Acceptance Criteria

- A1: `solar-knowledge-context.py --query "Solar 记忆系统" --json` 能返回至少 1 条 sourced hit，且延迟低于 800ms。
- A2: Obsidian 已处理页面如 `lumen-orbit-why-train-ai-in-space-2024.md` 或等价样本能被 Solar 检索命中。
- A3: `solar-harness wiki import-solar-db --scope solar --per-table-limit 3 --no-dispatch` 安全导出到 `_raw/solar-db-export/`。
- A4: `memory-influence.sh` 通过 `bash -n`，并能针对 `evo_memory_semantic.value` 工作。
- A5: `http://127.0.0.1:8765/status` JSON 包含 `solar_kb` 和 `obsidian_sync`。
- A6: 缺失 DB/vault/锁库/慢查询时 hook fail-open，不阻塞 agent。
- A7: `~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh` 全部通过。

## 非目标 / Non-Goals

- 不重写 Solar 全部记忆系统。
- 不把整个 DB 或整个 Obsidian vault 倒进 prompt。
- 不要求 QMD/MCP/外部服务作为必需依赖。
- 不默认暴露 secrets、tokens、完整 terminal transcript。
- 不改变 Solar sprint 主状态机语义。

## 约束 / Constraints

- UserPromptSubmit 路径必须低延迟，默认 800ms p95 以内，否则自动 fail-open。
- 默认注入上下文必须有来源字段，且默认不超过 2,000 chars。
- status server 继续绑定 `127.0.0.1`，不得引入重依赖。
- 同步必须增量化，避免每次全量扫描 263MB DB 或整个 vault。
- builder 并行时必须有 disjoint write set，避免主屏/扩展屏互相覆盖。

## 风险 / Risks

- 当前 `memory-influence.sh` 可能因为字段名错误静默漏召回，需要优先修。
- Obsidian vault 页面如果缺 frontmatter/summary，索引质量会下降，需要降级读取标题/路径/片段。
- 自动 hook 如果查询太重，会拖慢主 agent，需要 timeout 和 fail-open。
- 双向同步如果没有 manifest，容易重复生成页面或重复索引。
- status UI 如果只读旧字段，会继续出现 `Loading...`，需要同步修后端 payload 和前端字段。

## 开放问题 / Open Questions

- Obsidian-to-Solar 的目标表优先写 `cortex_sources/knowledge_entities/fts_unified_search` 还是先建轻量 bridge index。
- 自动同步周期设为 60s、5min 还是跟 capture-server raw scanner 合并。
- 是否默认启用 hook，还是先提供 `SOLAR_KB_CONTEXT=1` 开关灰度。

## 架构交接 / Planner Handoff

Planner 需要读取合约 `/Users/lisihao/.solar/harness/sprints/sprint-20260508-solar-kb-obsidian-autouse.contract.md`，产出：

- `sprint-20260508-solar-kb-obsidian-autouse.design.md`
- `sprint-20260508-solar-kb-obsidian-autouse.plan.md`

Plan 必须拆成三个 slice：

- Slice 1: retrieval hook + `memory-influence.sh` 修复。
- Slice 2: Obsidian-to-Solar indexing + DB-to-Obsidian export hardening。
- Slice 3: status UI + automation + tests/docs。

完成后把 status 更新为 `active`、`phase=planning_complete`、`handoff_to=builder_main`，并要求 coordinator 至少派两个 builder；不能再退回只派一个 builder 的旧流程。
