# PRD — External Integrations Closeout

**Source**: codex-manual-2026-05-08 (audit report `solar-open-source-integrations-audit-20260508.md`)  
**Priority**: P0  
**Lane**: reliability  
**Handoff To**: planner  
**Created**: 2026-05-08T15:05:00Z

## 背景 / Context

Solar Harness 历史上为了快速吸收社区能力，先后接入了 7 个外部开源/外部项目：Obsidian Wiki、QMD/MinerU Document Explorer、Mermaid、OpenAI Symphony、Strukto Mirage、CAMEL OWL、Google Drive。这些项目装的时间分散，文档分散，状态字段散落在 `solar-harness wiki status`、`mirage doctor`、`symphony status`、`integrations status`、status-server `/integrations` 五处。

Codex 已经做了第一轮收口：
- 实现 `lib/external-integrations-health.py` 七态字段统一探测（installed/configured/running/indexed/used_by_default/status/degraded_reason）
- 上线 `solar-harness integrations status [--json]` CLI
- 上线 status-server `GET /integrations`
- 恢复 wiki capture server 运行（端口 8788）
- 修复 `wiki audit-uploads` / `backfill-uploads` 的 bash `local` 作用域 bug

但收口没闭环：
- 上传批次入库存在大幅断头：批次 `20260508T131337Z` 16 个原件 → QMD 14/16，Vault 12/16，**Solar DB 0/16**；批次 `20260508T122047Z` 23 个原件 → QMD 15/23，Vault 6/23，**Solar DB 0/23**，dispatch pending 1
- Status UI 只暴露原始 JSON，用户看不懂"用了没用"
- Mirage 状态没区分 Solar 自写逻辑 VFS vs 官方 Mirage SDK/FUSE；Drive 永远 degraded 但原因不可见
- Symphony 状态没区分 dry-run sidecar vs 主执行器，UI 措辞会让人误以为 builder 是 Symphony 在跑
- OWL 仓库存在但未纳入主调度，状态既不是"未连"也不是"已连"，是模糊态

## 用户问题 / Problem

监护人当前面对的具体痛点：

1. **看不懂状态**：打开 status UI，七个集成里六个是 warn，但 warn 原因不一致——有的是凭据缺失、有的是入库丢数、有的是只跑 dry-run、有的是没接调度。无法一眼分清"装了没用、用了一半、跑歪了"。
2. **上传后找不到文档**：用户上传 PDF 之后，QMD 能搜到但 Solar DB 搜不到，下次会话主脑读不到这些文档，新会话像没上传过。
3. **多事实源冲突**：QMD 索引、Obsidian Vault 页面、Solar DB 三处对同一文件状态不一致，谁是 source of truth 没有明确边界。
4. **集成边界模糊**：Mirage 是 Solar 自写还是官方 SDK？Symphony 是不是真在执行 builder？OWL 到底连没连？这些问题用户自己看代码根本判断不出来。
5. **UI 暗示能力存在但实际不可用**：例如 Drive mount 显示 ready 但其实没凭据、Symphony 显示 completed=1 但其实是 dry-run 计数。

## 用户目标 / Goals

- **G1**：每个集成在 status UI 上一句话说清"是什么、用来干什么、能不能用、能不能默认走它、断头是什么"。
- **G2**：上传批次入库率 P0 闭环——latest batch 必须 QMD 23/23、Vault 23/23、Solar DB/FTS 23/23、dispatch pending 0，或为每个 missing 文件标注具体 blocker。
- **G3**：消除多事实源冲突：QMD-only / Vault-only / Solar DB-only 必须在 audit 里被显式标注，不能笼统说"已入库"。
- **G4**：Mirage / Symphony / OWL 的"是 Solar 自写 / 是官方 / 是 dry-run / 是未连"边界对外可见。
- **G5**：Drive 等需要凭据的集成给出 degraded reason（缺 token、缺 scope、过期），不能只显示 degraded。
- **G6**：所有这些可观测能力有 schema 测试和 endpoint 测试，未来不会因为字段重命名静默退化。

## 用户故事 / User Stories

- **US-1**（监护人）：我打开 status-server `/integrations` 页面，能在 30 秒内分清七个集成里"哪几个是真在用、哪几个只是装着、哪几个有断头需要修"。
- **US-2**（监护人）：我上传一批 PDF 到 Knowledge/_raw/uploads，5 分钟后跑 `wiki audit-uploads --batch <ts> --json`，看到 QMD/Vault/Solar DB 三个数字都满分，否则它要明确告诉我哪个文件卡在哪一步。
- **US-3**（PM/Planner）：我决定下一个 sprint 要不要用 Symphony 跑 builder 时，能从 `symphony status` 直接读到"目前是 dry-run sidecar，不是主执行器"，而不是被 completed=1 误导。
- **US-4**（PM/Planner）：我考虑要不要让 Mirage 真的挂载 Drive 时，能从 `mirage doctor` 看到"sdk.kind=none，drive=degraded，原因=missing credentials"，而不是只看到一句 degraded。
- **US-5**（Architect）：我要把 OWL 接进来时，能在 `integrations status` 里读到当前是 not_connected 还是 experimental 还是 production，不需要去翻代码。
- **US-6**（CI/Solar 自身）：未来谁改了健康探测的 JSON schema，schema test 会立刻报错，不会等用户发现 UI 错了才修。

## 功能需求 / Requirements

### R1 — 七态字段对齐 ✅ 部分已做

`solar-harness integrations status --json` 必须返回 7 个集成 × 7 个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| installed | bool | 仓库/包是否落盘 |
| configured | bool | 配置文件/凭据是否就位 |
| running | bool | 进程/服务是否活 |
| indexed | bool | 索引/数据是否产生 |
| used_by_default | bool | 是不是当前主路径，不是可选 |
| status | enum | ok / warn / missing / pending |
| degraded_reason | string | warn/missing 时的具体原因 |

Codex 已实现，本 sprint 验证字段稳定，不再改 schema，加 schema test 锁定。

### R2 — Status UI 集成视图

`status-server` 需要新增 Integrations Tab（不是 raw JSON）：

- 七行表格：Project / Purpose / Status badge / Used by default / Degraded reason / 修复责任人
- Status badge 颜色：ok=绿、warn=黄、missing=红、pending=灰
- "Purpose" 字段一句话：从 audit 报告里提炼，例：Obsidian Wiki = "把 Sprint/网页/上传文档/历史会话沉淀成可读知识库"
- 不破坏 `/status` 主页的刷新链路（即新增不能拖慢主页 P95）

### R3 — 上传入库 P0 闭环

针对最新批次 `20260508T131337Z`（或之后任何新批次），必须满足：

- QMD found = total
- Vault found = total
- Solar DB found = total
- dispatch pending = 0
- silent_missing = []

如果某文件无法入库（坏 PDF、超大、格式不支持），必须在 audit JSON 里 per-file 注明 blocker 字段，不允许默默丢失。

`solar-harness wiki backfill-uploads --batch <ts>` 必须能让一个不全的批次重新跑到满分，或者输出 per-file 的明确失败原因。

### R4 — 多事实源协调

QMD / Vault / Solar DB 三处必须在 audit 报告里清楚标注一个文件当前处于哪种状态：

| 状态 | 含义 |
|------|------|
| qmd_only | 只在 QMD 索引里有，Vault/DB 没有 |
| vault_only | 只在 Obsidian 页面里有，QMD/DB 没有 |
| db_only | 只在 Solar DB 里有，QMD/Vault 没有 |
| full | 三处都有 |
| partial:qmd+vault | QMD 和 Vault 有，DB 没有（当前批次普遍状态） |
| missing | 三处都没有 |

不能再用笼统"已入库" / "未入库"二态描述。

### R5 — Mirage 状态边界

`mirage doctor --json` 必须明确区分：

- `sdk.kind`: `none` / `solar-logical` / `strukto-official` / `fuse`
- `drive`: 当前是 `disabled` / `degraded` / `connected`
- `degraded_reason`: 例如 `missing oauth token`、`scope insufficient`、`token expired YYYY-MM-DD`

UI 不能显示一个 logical mount=ready 让用户以为是真的挂上了 Drive。

### R6 — Symphony 状态边界

`symphony status` 必须暴露：

- `mode`: `dry-run` / `sidecar` / `primary-executor`
- `executes_builders`: bool（当前必须是 false）
- 任何 UI 文案不能说 "Symphony 在跑 builder"，除非 mode=primary-executor 且 executes_builders=true

### R7 — OWL 状态边界

`integrations status` 中 owl 必须取以下值之一：

- `not_connected`：仓库存在但未纳入主调度
- `experimental`：已接入，但只允许在 sandbox sprint 中调用
- `production`：可在常规 sprint 中默认调用

不允许 `pending` 这种永远不收口的态。

### R8 — 测试覆盖

必须新增三类测试（builder 实现，不是 PRD 范围）：

- 健康探测 JSON schema 测试（pytest 或 bash + jq）
- `wiki audit-uploads` CLI 输出 schema 测试
- `/integrations` endpoint 200/500 + JSON 字段测试

### R9 — 最终报告

更新 `solar-open-source-integrations-audit-20260508.md`（或新增 `-final.md`）：

- 七个集成最终状态表
- 仍存在的 conflict 列表（每条带 owner + 下一步动作）
- 上传入库批次最终数据快照

## 验收标准 / Acceptance Criteria

直接对齐 contract.md D1-D10：

- **D1**: `solar-harness integrations status --json` 返回七项 × 七字段
- **D2**: status-server `/integrations` 返回相同 JSON 且不破坏 `/status` 刷新（P95 不退化 > 5%）
- **D3**: status UI 有人类可读的 Integrations Tab
- **D4**: 上传 ingest P0 闭环：最新批次 QMD/Vault/Solar DB 满分，或 per-file blocker 明确
- **D5**: QMD/Vault/Solar DB 多事实源在 audit 中显式标注，不再笼统说已入库
- **D6**: Mirage 区分 Solar logical wrapper vs 官方 SDK/FUSE；Drive degraded 原因可见
- **D7**: Symphony 区分 dry-run sidecar vs primary executor；不暗示其在跑 builder
- **D8**: OWL 状态明确：not_connected / experimental / production
- **D9**: 测试覆盖 health probe schema、audit 命令、`/integrations` endpoint
- **D10**: 更新报告列出最终状态和遗留 conflicts，每条带 owner / next action

## 非目标 / Non-Goals

- ❌ 真的为 Drive 取 OAuth token 并写真实 Drive（监护人未授权 + 不在本 sprint scope）
- ❌ 把 OWL 提升到 production（要单独评估 + 监护人决策）
- ❌ 把 Symphony 改成主执行器（架构层决策，不是本 sprint）
- ❌ 重写 Obsidian Wiki ingest 路径（修闭环即可，不是重写）
- ❌ 引入新外部项目（明确禁止）
- ❌ 修改 mermaid 渲染逻辑（mermaid 是 ok 状态，不动）

## 约束 / Constraints

- **C1**：所有探测和 verify 必须 read-only + ≤ 30s timeout，不能产生副作用
- **C2**：不挂载 `/Users/sihaoli` 整个家目录
- **C3**：不直接写 `/Users/sihaoli/Knowledge/concepts` 等正式知识库目录，只能写 `_raw/` staging
- **C4**：报告/JSON 不泄漏 secret（OAuth token、refresh token、API key 必须 redacted）
- **C5**：必须基于现有 `solar-harness` CLI、`status-server`、`events.jsonl`，不引入新组件、不引入新语言
- **C6**：不修任何 sprint 的 contract.md（contract 是 immutable）
- **C7**：不修 trajectories 数据
- **C8**：探测失败必须 fail-open，不能让 coordinator/planner pane 卡死

## 风险 / Risks

| ID | 风险 | 缓解 |
|----|------|------|
| R1 | 上传 ingest Solar DB 0/N 是因为 dispatch agent 不跑，本 sprint 一次 backfill 修不完 | Stop rule：一次 backfill 跑完后仍 0/N 立即升级，per-file 给 blocker |
| R2 | Schema test 加上后老代码字段被锁死，未来想改字段会被测试挡住 | 在 schema 文件里写明字段冻结日期，未来改字段需要新 sprint + schema 版本号 |
| R3 | UI 改造可能拖慢 `/status` 主页 | D2 验收要求 P95 不退化 > 5%，加 benchmark verify 命令 |
| R4 | OWL 的 status 边界用户没明确意见 | 默认设为 not_connected，本 sprint 不提升态 |
| R5 | Drive 凭据问题让 Mirage 永远 degraded，用户体验差 | UI 明确 reason="missing credentials"；用户可以看懂这不是 bug 是配置问题 |

## 开放问题 / Open Questions

- **OQ1**：Solar DB 0/16 的根因是 dispatch agent 不跑还是 ingest pipeline 写库失败？需要 Planner 在 plan 阶段先 root-cause 一轮再决定修法
- **OQ2**：Status UI 改造放在 status-server 主进程还是单独 page？建议单独 page，避免拖慢主页
- **OQ3**：QMD-only / Vault-only / DB-only 状态分类是写到 audit JSON 里还是单独 reconciliation 表？建议写在 audit JSON 文件级，简洁
- **OQ4**：测试是 pytest 还是 bash + jq？建议 bash + jq，和 Solar 现有测试栈一致
- **OQ5**：最终报告是覆盖 `solar-open-source-integrations-audit-20260508.md` 还是新增 `-final.md`？建议新增 `-final.md`，保留审计前后对照
- **OQ6**：D3 UI Tab 是不是需要 mermaid 图？建议先不上图，文字 + badge 够用，别让 UI 复杂度爆炸

## 架构交接 / Planner Handoff

Planner 接走本 PRD 时必须在 plan 阶段回答：

1. **R3 上传入库根因**：Solar DB 0/N 是 dispatch agent 不跑，还是 ingest 写 DB 步骤本身有 bug？先 root-cause，再决定 F1 修哪个环节
2. **派工拆分**：D1/D9 schema 测试是一组；D2/D3 UI 是一组；D4/D5 上传入库 + reconciliation 是一组；D6/D7/D8 Mirage/Symphony/OWL 边界是一组；D10 报告是收尾。建议至少四个 builder 任务串行 + 测试一起做
3. **写 scope 白名单**（绝对路径）：
   - `~/.solar/harness/lib/external-integrations-health.py`
   - `~/.solar/harness/bin/solar-harness*`（仅相关子命令）
   - `~/.solar/harness/lib/status-server/*`（新增 integrations 视图）
   - `~/.solar/harness/lib/wiki-*`（audit / backfill 修复）
   - `~/.solar/harness/tests/**`（新测试文件）
   - `~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md`（新增）
   - `~/.solar/harness/schemas/*.schema.json`（如需新增 integrations schema）
4. **禁止越界**：不动 contract.md、不动 trajectories、不动正式 vault 目录、不动凭据存储路径
5. **Verify 命令**：sprint 完成后必须能跑 contract.md "Verification Commands" 全部 7 条命令并 PASS
6. **Stop rule 兑现**：上传入库一次 backfill 后仍 0/N → 升级到监护人，不要循环重试
7. **Builder 模型选择**：默认 Sonnet（建设者），不要默认 GLM-5.1（已踩过四次坑）；探测/audit 类轻活可以丢闪电侠
8. **Evaluator 抽样**：抽 ≥ 3 条 verify command 复现 + git diff 对比 write_scope 越界

