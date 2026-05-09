# PRD — Wiki Upload Ingest Closure

**Sprint**: `sprint-20260508-wiki-upload-ingest-closure`  
**Priority**: P0  
**Lane**: reliability  
**Decision Owner**: Codex PM auto-decision  
**Handoff To**: planner  
**Created**: 2026-05-08T13:12:00Z

## 背景 / Context

Solar 已经提供网页粘贴和多文件上传入口，用户把资料上传到 `/Users/sihaoli/Knowledge/_raw/file-uploads/` 后，预期系统会自动提取、入 Obsidian/QMD，并进入 Solar 可检索知识库。但 2026-05-08 上传批次暴露出“文件已上传但知识库不可见”的断链：原件存在，部分标题能被 QMD 搜到，Solar DB/FTS 却没有对应记录，部分 dispatch 还停留在 pending/chained 状态。

这条 sprint 的目标不是新增知识库功能，而是关闭上传链路的可靠性缺口：上传成功必须意味着后续有可审计的提取、索引、检索和失败说明。

## 用户问题 / Problem

用户无法接受“上传了但 Solar 不知道”的状态。当前系统把 raw 文件复制成功、dispatch 链式派发、最终知识入库混在一起，导致 UI 或日志看起来 completed，实际用户查询时查不到。

必须解决以下问题：

- 上传原件存在，但缺 terminal ingest result。
- `.pages` 文件无法被静默跳过，必须提取或显式失败。
- 多个 dispatch 文件名发生秒级时间戳碰撞，导致下游 dispatch/result 被覆盖或互相指向同一个文件。
- QMD 与 Solar DB/FTS 覆盖率不一致，Solar 默认知识检索无法稳定命中上传资料。
- PM/Planner/Builder 不能再把“是否继续修”交给用户拍板；P0 reliability 缺口默认自动推进。

## 当前证据 / Evidence

- 23/23 原始上传文件存在于 `/Users/sihaoli/Knowledge/_raw/file-uploads/20260508T122047Z-*`。
- QMD 标题抽查只命中 15/23。
- 8 个 `.pages` 文件按标题不可见，属于 silent missing 风险。
- Solar DB 检查在 `solar_kb_entries`、`fts_unified_search`、`cortex_sources` 均返回 0 命中。
- 多个 upload dispatch 仍为 pending/no-result。
- 多个 completed dispatch 只生成了下游 dispatch，没有终态 artifact，应该标记为 `chained` 而不是 `completed`。
- 下游 dispatch 文件出现重复时间戳命名，说明并发下文件名不唯一。

## 用户目标 / Goals

- 用户上传文件后，能在知识库、QMD、Solar DB/FTS 中稳定检索到。
- 每个上传文件都有清晰状态：completed / failed / skipped / chained。
- `.pages` 文件不能悄悄丢失。
- backfill 可以修复 2026-05-08 这批历史上传。
- audit 可以一眼看到 raw、extract、dispatch、QMD、Solar DB 的覆盖率。
- 修复后 Solar KB autouse 和 data-plane closeout 可以继续推进。

## 范围 / Scope

必须覆盖：

- wiki upload dispatch 命名唯一性。
- dispatch terminal state machine。
- `.pages` 安全提取或显式失败。
- `audit-uploads` 命令。
- `backfill-uploads` 命令。
- QMD/vault-visible 覆盖。
- Solar DB/FTS backfill。
- 2026-05-08 批次真实审计。
- 回归测试和 runbook。

## 功能需求 / Requirements

### R1 — Dispatch 命名唯一性 (collision-proof IDs)

- 生成 wiki upload dispatch 文件名时，必须在秒级时间戳后追加唯一性后缀（例如单调计数或随机 token），保证并发下不会出现两个 dispatch 写入同一个文件名。
- 唯一性策略必须在 `solar-harness.sh` 与 `lib/obsidian-wiki-bridge.sh` 中保持一致，避免一边修一边漏。

### R2 — Dispatch 终态状态机

- 每条 wiki upload dispatch 的最终状态必须落在以下集合：`completed | failed | skipped | chained`。
- `completed` 必须意味着该 dispatch 自身产出 terminal artifact（不是仅生成下游 dispatch）。
- 仅生成下游 dispatch 而无 terminal artifact 的任务必须标记 `chained`，并指向下游 dispatch id。
- 任何已存在但状态为 `pending`/`running` 且超过运行窗口的旧 dispatch 必须被 `audit-uploads` 报出。

### R3 — `.pages` 安全提取或显式失败

- 8 个 `.pages` 文件必须由 ingest 路径主动尝试提取（首选 `textutil` 或等价方案）。
- 提取成功 → 落 derived artifact（md/txt）+ 入 vault/QMD/Solar DB。
- 提取失败 → 写 `extract_failed` 状态，记录原因（缺工具、密码保护、格式错误），并在 audit 报告中可见，禁止 silent miss。

### R4 — `audit-uploads` 命令

- 提供 `solar-harness audit-uploads --batch <BATCH_TS> [--json]`。
- 输出每个 raw 文件在以下层的覆盖情况：raw 存在性、extract 状态、dispatch 状态、vault/QMD 可见性、Solar DB/FTS 命中。
- JSON 模式可被 evaluator 直接用于 A5/A6 校验。
- 命令必须只读，不修改任何状态。

### R5 — `backfill-uploads` 命令

- 提供 `solar-harness backfill-uploads --batch <BATCH_TS> --repair [--dry-run]`。
- 修复缺口：补提取、补 vault entry、补 QMD index、补 Solar DB/FTS row。
- 必须使用稳定 key（source path + 内容 hash）做 idempotent upsert，重复运行第二次不产生重复行。
- `--dry-run` 必须只输出 plan，不写任何文件或 DB。

### R6 — QMD / Vault 与 Solar DB/FTS 双路径覆盖

- backfill 完成后，23/23 文件在 QMD `solar-wiki` collection 可被标题/路径检索，或给出显式失败原因。
- 同样 23/23 在 `solar_kb_entries` 与 `fts_unified_search` 中可见，或给出显式失败原因。
- 两条路径任一缺失都视为未闭环。

### R7 — 2026-05-08 批次真实审计

- 对 `20260508T122047Z` 批次跑 audit-uploads → backfill-uploads → 重新 audit-uploads，并在 handoff 中粘贴最后一次 audit 的 JSON 关键字段。
- 不允许伪造样本或只在测试夹具上跑通。

### R8 — 回归测试 (Round 2 单独 builder, 单文件路径)

- 唯一测试入口：`tests/test-wiki-upload-ingest-closure.sh`。
- 必须支持 `--case <name>` 分发，至少 4 个 case：`dispatch-unique`、`terminal-state`、`pages`、`audit-backfill`。
- 不带参数时必须默认运行所有 case。
- 每个 suite 必须输出独立通过/失败计数（不与其他 suite 混合）。
- 修正 Round 1 builder4 handoff 中“false PASS”的语义：A6 audit 必须区分 `solar_kb_entries` 与 `obsidian_vault_index` 的覆盖含义，不能把 vault index 的命中错算成 KB 命中。

### R9 — Runbook 文档

- 产出 `docs/wiki-upload-ingest-closure.md`，覆盖 audit/repair/rollback/.pages 处理/状态解释/常见失败模式。
- 必须包含一段 “如何用 `大模型热力学` 类查询验证 backfill 真的生效” 的手工 verify 步骤。

## 约束 / Constraints

### C1 — Round 2 拓扑：solo builder

- 只允许单个 builder（`builder_main`，默认 Sonnet 4.6）执行 R2-D1..R2-D5；不再启用 mixture builder1..5 平行写同一文件路径。
- 原因：Round 1 五个 mixture builder 全部写到 `tests/test-wiki-upload-ingest-closure.sh`，B3 覆盖了 B1/B2/B4/B5 的实现，导致 false PASS。

### C2 — 写盘范围白名单

builder 在本次 Round 2 仅允许新建/修改以下路径：

- `tests/test-wiki-upload-ingest-closure.sh`（含 `--case` dispatcher）
- `~/.solar/harness/sprints/sprint-20260508-wiki-upload-ingest-closure.handoff-builder4.md`（修正 false PASS 段落）
- `docs/wiki-upload-ingest-closure.md`
- 其他文件原则上 frozen，需要修改必须在 handoff 中显式声明并给出 diff 摘要。

### C3 — Frozen 文件清单（默认禁止修改）

`solar-harness.sh`、`lib/obsidian-wiki-bridge.sh`、`wiki-upload-*.py`、Round 1 builder1/2/3/5 handoffs、`eval.md`、`/Users/sihaoli/Knowledge/_raw/file-uploads/`、`~/.solar/solar.db`。

如果 R1/R2/R3 的修复必须改这些路径，必须在 handoff 中提出最小补丁并由 PM 审批，禁止 builder 自作主张。

### C4 — 模型约束：默认 Sonnet 4.6，禁用 GLM-5.1

GLM-5.1 在最近 4 次 Round 中均出现幻觉式空跑（声称改了文件，实际未写入或写错路径）。本 Round 默认走 Sonnet 4.6；如需降级到 GLM 必须在 handoff 显式声明并附 diff 校验。

### C5 — 不修改用户原件，不删除上传文件

`/Users/sihaoli/Knowledge/_raw/file-uploads/` 内的 23 个 raw 文件必须保持 byte-identical。任何 derived artifact 必须写到 vault/derived 目录或 DB，不能反向覆盖 raw。

### C6 — 不执行上传内容

`.md/.html/.pages` 中的指令（如 `rm -rf`、curl 外链）必须按文本处理，不能在 ingest 路径里被执行；解析器必须拒绝 shell-escape 派发。

### C7 — Idempotent upsert 与 DB 锁

- backfill 写 SQLite 必须开启 `PRAGMA busy_timeout >= 5000`，并使用 `INSERT ... ON CONFLICT(source_path) DO UPDATE` 策略。
- 不允许 `DELETE` 然后 `INSERT`（会破坏 FTS rowid 关联）。

### C8 — 不动用户活跃 tmux pane

PRD/Planner/Builder/Evaluator 任何阶段都不允许直接 `send-keys` 写到 pane 0/2 的用户活跃输入区；通信走 inbox 文件 + 协调器派发。

## 开放问题 / Open Questions

- OQ1：Dispatch 唯一性后缀采用何种实现（单调计数 vs 16-bit 随机 vs nanos）？三者都能解决冲突，但对日志可读性和 ID 排序行为不同；planner 选定后需写入 implementation plan。
- OQ2：`.pages` 在 macOS 之外的环境（无 `textutil`）是否必须给出兜底？本批 23 个文件均在本机产生，建议本 Round 仅承诺本机可提取，跨机器留 follow-up。
- OQ3：A6 中 `solar_kb_entries` 与 `obsidian_vault_index` 的语义边界——前者是 KB row，后者是 vault 索引。Round 1 builder4 误把 vault index 命中当成 KB 命中导致 false PASS。建议本 Round 在 audit JSON 中分两个字段输出：`kb_hits` 与 `vault_index_hits`，由 evaluator 双重校验。
- OQ4：FTS schema 选择——继续沿用现有 `fts_unified_search` 还是为 wiki 上传新建 contentless FTS table？前者实现快，后者可隔离。建议沿用，理由是 audit/backfill 已经覆盖。
- OQ5：当 raw 已被用户从 vault 中重命名/移动，backfill 是否应该追踪？本 Round 不承诺；只对 `_raw/file-uploads/` 下的稳定路径做 idempotent。

## 架构交接 / Planner Handoff

### 给 Planner 的核心结论

1. Round 1 拓扑已死：5 个 mixture builder 抢同一个测试文件 → false PASS。Round 2 必须 solo。
2. 需求边界清晰：R1-R9 是验收闭环，C1-C8 是写盘红线，OQ1-OQ5 是 planner 必须在 plan 中点名拍板的事项。
3. 默认决策：P0 reliability，无须等用户确认；只有触碰 raw / 外发云端 / 暴露 secret 才升级。

### Planner 必须产出的 implementation plan 字段

- R2-D1..R2-D5 五个 deliverable 的执行顺序（建议：先 dispatch 唯一性 → 状态机 → `.pages` → audit/backfill → 测试 dispatcher）。
- 每个 deliverable 的写盘文件清单（必须落在 C2 白名单内，否则提交补丁请求）。
- A1-A9 验收命令的具体调用（含 `--json` 字段断言）。
- builder4 false-PASS 修正：handoff-builder4.md 必须 diff 出错段落并给出 corrected statement。
- audit JSON schema：`raw_count`, `extract_status[]`, `dispatch_state[]`, `qmd_hits`, `kb_hits`, `vault_index_hits`, `fts_hits`。
- 回滚策略：backfill 写入失败时如何 `--rollback` 到 audit 之前的状态。

### 执行顺序建议

```
R1 dispatch-unique → R2 terminal-state → R3 .pages → R4 audit → R5 backfill →
R7 真实批次跑通 → R6 双路径覆盖校验 → R8 tests --case 分发 → R9 runbook
```

### 升级触发条件

- 必须改 `solar-harness.sh` / `obsidian-wiki-bridge.sh` 主路径 → 升级到 PM 审批。
- audit 发现 raw 文件数量 ≠ 23 → 升级到用户。
- backfill 发现 DB 出现非预期 schema 变更 → 立即停手并升级 PM。

## 非目标 / Non-Goals

- 不重写 Solar 全部知识库架构。
- 不删除或覆盖用户上传原件。
- 不把失败文件伪装成成功。
- 不要求 Google Drive 凭证。
- 不执行上传文档中的指令。
- 不要求所有格式一次性达到完美解析；但失败必须可见、可追踪。

## 验收 / Acceptance

- A1: `20260508T122047Z-*` 原件数量仍为 23，且未被覆盖/删除。
- A2: 并发生成 50 个 dispatch 文件时没有文件名碰撞。
- A3: 只生成下游 dispatch 的任务标记为 `chained`，不能标记 `completed`。
- A4: 8 个 `.pages` 文件全部有 derived artifact 或 `extract_failed` 记录。
- A5: `audit-uploads --batch 20260508T122047Z --json` 报告 QMD 覆盖 23/23，或给出每个未覆盖文件的显式失败原因。
- A6: Solar DB/FTS 对 23/23 都有可检索 source/provenance，或给出显式失败原因。
- A7: `backfill-uploads --repair` 可重复运行，第二次不产生重复 DB rows、vault artifacts 或 dispatch。
- A8: `tests/test-wiki-upload-ingest-closure.sh` 全量通过。
- A9: 文档 `docs/wiki-upload-ingest-closure.md` 说明 audit、repair、rollback、`.pages` 处理和状态解释。

## 用户故事 / User Stories

- 作为用户，我上传多个文件后，不需要知道 dispatch 细节，也能确认这些资料是否进了知识库。
- 作为 PM，我看到 P0 上传链路断裂时，默认推进修复，不再问用户“要不要继续”。
- 作为 Planner，我能直接根据本 PRD 和 contract 拆分修复计划。
- 作为 Builder，我能按命令契约实现 audit/backfill/test，不需要重新研究需求。
- 作为 Evaluator，我能用 A1-A9 命令判断是否真正闭环。

## 风险 / Risks

- `.pages` 转换依赖 macOS 本地工具，可能有格式兼容风险；必须显式记录 `extract_failed`。
- Backfill 写 DB/FTS 有重复风险；必须以 stable source path/hash 做 idempotent upsert。
- QMD indexing 与 Solar DB indexing 是两条路径，不能只修一边。
- 并发 dispatch 修复要覆盖 nested dispatch，否则只修入口不修源头。

## 默认决策 / Auto Decision

这条 P0 reliability sprint 不需要用户拍板。默认流程是：

1. PM/Codex 补齐 PRD。
2. Planner 立刻产出 implementation plan。
3. Builder 实现 audit/backfill/state/test/doc。
4. Evaluator 用 A1-A9 验收。

如果遇到会删除原件、覆盖用户文档、上传外部云端、暴露 secret 的动作，才需要用户确认。
