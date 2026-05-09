# PRD — Solar Workstream Verification Closeout

**Source**: Codex PM analysis from user request on 2026-05-08  
**Priority**: P0  
**Lane**: reliability  
**Handoff To**: planner  
**Created**: 2026-05-08T16:40:00Z

## 背景 / Context

最近连续安排了多条 Solar 工作流：Obsidian Wiki、QMD/MinerU、capture server、Solar KB 默认检索、accepted artifact 入库、data-plane closeout、Mirage 统一虚拟文件系统、hook/status/pane 协同修复等。部分已经 PASS，部分处于 queued/active/reviewing，部分被手动派发到 pane 后还没形成 handoff/eval。

用户现在要求做一次全面分析和验证：不要继续只新增功能，要确认前面安排的开发工作是否真的完成、可用、被 Solar 正确接管，并把未闭环项变成 Solar 可以继续干的合约。

## 用户问题 / Problem

当前 Solar 状态存在三类风险：

- 状态字段显示 active/reviewing，但实际 handoff/eval 缺失。
- 某些集成命令可用，但自动化链路、status 可观测、知识入库闭环还没有统一验收。
- 多 pane 协同曾出现 plan mode 卡住、GLM API 400、builder 等 evaluator、coordinator 未自动派发等问题，可能继续造成“看起来在动，实际不落盘”。

## 当前事实 / Evidence

- `sprint-20260507-obsidian-wiki` 已 passed。
- `sprint-20260507-symphony2` 已 passed。
- `sprint-20260507-symphony3` 已 passed。
- `solar-harness wiki status --json` 可用，vault 是 `/Users/sihaoli/Knowledge`，skills 安装到 Codex/Claude/Agents。
- QMD/MinerU `solar-wiki` collection 有 1103 文件 indexed，搜索可返回 Obsidian 页面。
- QMD vectors 仍是 `0 embedded`，1102 pending embedding。
- status-server `http://127.0.0.1:8765/healthz` 返回 ok，`/status` 可返回 JSON。
- `sprint-20260508-solar-kb-obsidian-autouse` 处于 reviewing/building_parallel，但当前缺 `eval.md` / `eval.json`。
- `sprint-20260508-mirage-unified-vfs` 已有 PRD/contract/design/plan，正在 S1/S2 builder，但当前缺 `handoff-s1.md` / `handoff-s2.md`。
- `sprint-20260508-accepted-artifact-knowledge` 和 `sprint-20260508-data-plane-closeout` 仍 queued。
- lab-builder GLM 曾出现 API 400 code=1210，S1 已重派主屏 Sonnet builder。

## 用户目标 / Goals

- 一次性核验所有近期安排的 Solar 相关工作是否“真的完成”。
- 对每条工作流给出 `ok | warn | error | pending` 状态和可复现证据。
- 对缺 handoff、缺 eval、缺自动化、缺测试、缺入库的项生成修复任务。
- 阻止状态字段假阳性：不能只看 status=active/reviewing/passed，必须看 artifact 和 verify command。
- 让 Solar 继续执行：planner 出验证计划，builder 做小修，evaluator 给最终总体验收。

## 范围 / Scope

必须覆盖：

- Symphony S1/S2/S3 集成成果。
- Obsidian Wiki 集成成果。
- QMD/MinerU Document Explorer 集成成果。
- Wiki capture server 和自动 ingest。
- Solar KB default retrieval + Obsidian sync P0。
- Accepted sprint artifact 入库 P1。
- Data-plane closeout P1。
- Mirage unified VFS P1。
- status-server/events/pane assignment/hook failure 观测。

## 非目标 / Non-Goals

- 不新增无关功能。
- 不重写 Solar coordinator。
- 不真实写 Google Drive。
- 不大规模重建 Obsidian vault。
- 不把未验收草稿直接写入正式知识库。

## 验收目标 / Acceptance

- 产出一份总体验证报告。
- 每条工作流至少有一个可复现命令或 artifact 证据。
- 当前 active/reviewing sprint 的缺口被具体派工。
- 已 passed sprint 若证据不足，必须降为 warn 并列出补证命令。
- 所有修复都必须保持安全边界：fail-open、secret redaction、no full home mount、no real Drive write。

## 用户故事 / User Stories

- 作为昊哥，我可以一眼看到所有近期工作流的真实状态（ok/warn/error/pending），不被 status 字段假阳性误导。
- 作为 PM，我可以拿着验证报告决定"下一步该做什么"，而不是继续盲目派新功能。
- 作为 Planner，我能从 fix-dispatch 直接接走未闭环项，不需要重新做需求分析。
- 作为 Builder，我执行修复任务时知道写哪些文件、怎么验证、怎么回滚。
- 作为 Evaluator，我能复现验证报告里的每一条命令，确认证据是真的不是 LLM 编的。

## 功能需求 / Requirements

### R1 — 验证矩阵报告

- 输出 `~/.solar/harness/reports/solar-workstream-verification-20260508.md` (人读) + `.json` (机读)。
- 至少覆盖 10 个工作流：Symphony S1/S2/S3、Obsidian Wiki、QMD/MinerU、capture server、Solar KB autouse、Accepted artifact、Data-plane closeout、Mirage VFS、Pane orchestration。
- 每条工作流字段：`id`, `workstream`, `status` (ok/warn/error/pending), `evidence_or_gap`, `verify_command`。

### R2 — 证据复现命令

- 每个 ok/warn 项必须给出可在 shell 里直接跑的 verify command（不需要 GUI 不需要登录）。
- 命令必须是 read-only 或 fail-open，不能产生副作用。

### R3 — Fix Dispatch

- 输出 `sprint-20260508-workstream-verification-closeout.fix-dispatch.md`。
- 每条修复任务 (F1, F2, ...) 必须含：`owner`, `write_scope` (文件白名单), `verify` (命令), `rollback` (失败回退)。
- 不允许 fix 写到 write_scope 以外的文件。

### R4 — 安全边界

- 不真实写 Google Drive。
- 不挂载 `/Users/sihaoli` 整个家目录。
- 不直接写 `/Users/sihaoli/Knowledge/concepts` 等正式知识库目录（只能写 `_raw/` staging）。
- 不在报告/fix 里泄漏 secret（OAuth token、refresh token、API key 必须 redacted）。

### R5 — 不阻塞 Coordinator

- 验证脚本探测失败必须 fail-open，不能让 coordinator/planner pane 卡死。
- 任何 verify command 加超时（默认 ≤ 30s）。

## 约束 / Constraints

- 必须基于现有 `solar-harness` CLI 和 `events.jsonl`，不引入新组件。
- 报告路径固定：`~/.solar/harness/reports/solar-workstream-verification-20260508.{md,json}`。
- fix-dispatch 写 scope 必须是绝对路径（避免 ambiguity）。
- 验证执行不依赖网络（QMD vector embedding 状态、Drive 凭证之类只看本地状态）。
- 不修改任何 sprint 的 contract.md（contract 是 immutable）。
- 不修改 trajectories 数据（训练审计链）。

## 风险 / Risks

- **风险 R1: 验证脚本探测时副作用** — 例如启动 capture-server 改变全局状态。缓解：所有 verify 命令必须 read-only。
- **风险 R2: planner pane compact 再次卡住** — 今天已经在 mirage sprint 卡过一次。缓解：codex_pm 兜底，最多等 3 分钟无新输出就接管。
- **风险 R3: GLM 1210 仍未根治** — lab-builder 已 fallback Sonnet，但 P0 不依赖 lab-builder。
- **风险 R4: 报告自身不被验收** — verification 报告本身可能被 LLM 编造。缓解：evaluator 必须复现 ≥ 3 条 verify command 抽样核对。
- **风险 R5: fix-dispatch 越界** — Builder 修着修着改了 write_scope 外的文件。缓解：合约里 write_scope 是白名单，Evaluator 验收时 git diff 比对。

## 开放问题 / Open Questions

- **OQ1**: 验证矩阵是 PM 手动写还是脚本生成？建议手动 + 关键 verify 命令脚本化，避免 LLM 幻觉。
- **OQ2**: QMD vectors=0 是否在本 sprint 修？建议 F5 只标记不修，embedding 启动需要昊哥批准（成本/时间不确定）。
- **OQ3**: Solar KB autouse 缺 eval — 谁来写？建议 evaluator 独立验收（不让原 builder 自评）。
- **OQ4**: capture-server 应该常驻还是按需启动？建议本 sprint 只做状态报告，常驻策略在 data-plane closeout sprint 决定。
- **OQ5**: pane 防卡是改 status-server 显示还是 chain-watcher 主动救？建议本 sprint 只做显示分类，主动救火放下个 sprint。
- **OQ6**: Accepted artifact + Data-plane closeout 何时解锁？建议 Solar KB autouse PASS 后再启。

## 架构交接 / Planner Handoff

Planner 接走本 PRD 时必须确认：

- 验证矩阵的 10 工作流清单与 evidence/gap 字段约定。
- 报告路径：`~/.solar/harness/reports/solar-workstream-verification-20260508.{md,json}`。
- fix-dispatch 写 scope 白名单原则（绝对路径，禁止越界）。
- Verify command 必须 read-only + 超时 ≤ 30s。
- 不修 trajectories，不修 contract.md。
- Builder pass 顺序：F1 (Solar KB eval) → F2 (Mirage handoff) → F3-F4 → F5 (只标记) → F8 (pane 显示)。F6/F7 等 P0 PASS 后解锁。
- Evaluator 必须抽样复现 ≥ 3 条 verify command，并 git diff 比对 fix 的 write_scope。

