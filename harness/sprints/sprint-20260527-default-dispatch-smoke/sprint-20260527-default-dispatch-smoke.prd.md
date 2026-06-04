# PRD — Default Dispatch Smoke

**Source**: coordinator self-test (dispatch chain verification)
**Priority**: P2
**Lane**: harness-ops / smoke
**Sprint ID**: `sprint-20260527-default-dispatch-smoke`
**Handoff To**: planner
**Created**: 2026-05-28 (PM gate_missing_prd backfill)
**Intent**: `execute` (confidence=0.9, solar-harness)

## 背景 / Context

- Solar Harness 在 Mac mini (lisihaodeMac-mini.local, macOS arm64, bash 5.3.9) 跑 4-pane 协同（pane 0 planner opus / pane 1 builder glm-5.1 / pane 2 evaluator glm-5.1 / pane 3 architect opus） + coordinator + chain-watcher + graph-scheduler。
- 默认 dispatch chain（coordinator → dispatch.md → builder pane → handoff → status update）经历了多轮重构（context inject + intent engine + capability injection + Codex bridge + lease-based runtime），需要一个最小、零业务负载的 smoke test 来确认基础链路在每次重构后仍然可用。
- 本 sprint 是 **default-dispatch-ready smoke test**：除了写一个 marker handoff 到 `/tmp/solar-dispatch-smoke/`，**不动任何代码 / 配置 / 服务**。Smoke test 文件落 `/tmp` 是有意为之（确认 builder pane 接到 dispatch 即可，不污染仓库）。
- 状态：S1 节点已在 2026-05-28T03:07Z 由 builder pane `solar-harness-lab:0.2` 完成，S1-handoff.md 确认 marker 文件 403 字节存在；当前 sprint 走到 PM gate（`gate_missing_prd`），因为 PRD 一开始没生成。本切片即生成 PRD 以解除 gate。

## 用户问题 / Problem

- **PB-1** 默认 dispatch chain 多次被改（context inject / intent engine / Codex bridge / lease runtime / TUI pane recover 等），缺一个最小 smoke 验证就直接上重构很容易漏掉 regression。
- **PB-2** 之前 builder pane 是否真的收到 dispatch 的判断靠看 tmux pane 标题或 `ps`，不够确定；smoke 应当用一个**可观测的 marker file**作为 ground truth。
- **PB-3** smoke test 自己不能污染仓库：不能改任何 `~/.solar/harness/lib/` 源码、不能动 ThunderOMLX/ASR、不能改 sprint 模板。
- **PB-4** PRD 一开始缺失，coordinator gate_missing_prd 把 sprint 拉回 PM；本切片需要写 PRD 让链路前进。

## 用户目标 / Goals

1. 确认 coordinator 能从 `<sid>.dispatch.md` 派发到 builder pane（这里是 `solar-harness-lab:0.2`）。
2. 确认 builder pane 在 dispatch 上下文里能落一个 `<output>` 文件。
3. 确认 handoff 含 **builder pane / dispatch id / 验证时间** 三个字段，可供 evaluator 校验。
4. 整个流程**零仓库代码改动**，只写 `/tmp/solar-dispatch-smoke/`。
5. 本 sprint 走完 PM → Planner → Builder → Evaluator 四步，证明默认 dispatch chain 端到端 ready。

## 用户故事 / User Stories

- **US-01 (Harness 维护者)**：作为 Solar Harness 维护者，每次改 coordinator / dispatch / pane lifecycle 后，我希望一键跑 default-dispatch-smoke 确认基础链路不挂。
  - 验收：S1 节点 ≤ 5 分钟自然完成 + S1-handoff.md 含三字段。
- **US-02 (Evaluator)**：作为 evaluator，我希望从 handoff 直接抽 `builder_pane / dispatch_id / verification_time` 三字段做断言，不依赖 LLM 阅读。
  - 验收：S1-handoff.md 文本可用 `grep -E "builder.pane|dispatch.id|verification"` 抽到。
- **US-03 (PM / Coordinator)**：作为 coordinator gate，PRD 一旦缺失就回滚到 PM；本切片即修复入口。
  - 验收：PRD 存在 + schema PASS + mtime 刷新触发 coordinator 重跑 gate。
- **US-04 (Builder pane)**：作为 builder pane，dispatch 上下文必须明确告诉我"只写 /tmp marker，不动仓库"。
  - 验收：task_graph.json S1 `write_scope=["/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md"]` ✅ 唯一允许写。

## 功能需求 / Requirements

- **FR-1 单节点 DAG**：本 sprint 只一个 S1 节点，`depends_on=[]`，`required_skills=["bash"]`，无下游。
- **FR-2 Write Scope 严格限定**：S1 唯一允许写 `/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md`；不允许写任何 `~/.solar/`、`/Users/lisihao/Solar/`、仓库内文件。
- **FR-3 Handoff 必含三字段**：`builder_pane`（例如 `solar-harness-lab:0.2`）、`dispatch_id`（例如 `graph-sprint-20260527-default-dispatch-smoke-S1-20260528T030610Z`）、`verification_time`（ISO 8601）。
- **FR-4 Capability 注入但不要求执行**：dispatch 注入 `harness.context_preflight / intent / dispatch_visibility / contracts / dag / status / model_routing`，但 smoke test 不要求实际调用它们；只要 dispatch 能把这些 capability injected 进 pane 即可。
- **FR-5 PRD schema 合规**：本 PRD 通过 `validate.sh prd`（schema 11 节齐全）。
- **FR-6 status.json phase 转换**：完成后 `status.json` 的 `phase` 从 `spec` 转 `prd_ready`，`history` 追加 `prd_completed`。
- **FR-7 不动任何 live tmux pane**：PM 不允许 `tmux send-keys`、不允许 kill pane、不允许重启 harness。

## 验收标准 / Acceptance Criteria

| AC | 标准 | 状态 |
|----|------|------|
| AC-1 | `/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md` 存在且 ≥ 200 字节 | ✅ S1-handoff §Verification Evidence: 403 字节 |
| AC-2 | handoff 文本含 builder pane / dispatch id / verification time | ✅ S1-handoff §Verification Evidence 已确认 |
| AC-3 | S1 task_graph 节点 `status` 进入 `reviewing` 或 `passed` | ✅ 当前 status=`reviewing` |
| AC-4 | 0 个仓库代码文件被改 | ✅ S1-handoff §Changed Files 只列 `/tmp/...handoff.md` |
| AC-5 | 0 个 secret 被打印（API key / OAuth / token） | ✅ S1-handoff 无 secret |
| AC-6 | PRD 存在 + `validate.sh prd` PASS | 本切片即满足 |
| AC-7 | `status.json.phase = prd_ready` 且 `history` 含 `prd_completed` | 本切片末步更新 |

## 非目标 / Non-Goals

- 不验证业务功能（如 ThunderOMLX cache / FlashMLX KV / Lease runtime）。
- 不验证 evaluator / planner pane 的复杂行为，只验证 builder pane 能收 dispatch + 写 marker。
- 不验证 Codex bridge、Antigravity、Codex cloud 等非默认 host 类型。
- 不要求 marker 内容含 LLM-generated 段落；只要三字段存在就够。
- 不在 PM 切片内重做 S1（S1 已 reviewing）；不做 planner 设计；不写代码；不重启 harness；不动 live tmux pane。
- 不持久化 marker 文件（`/tmp` 会在重启时清理，符合 smoke 一次性语义）。

## 约束 / Constraints

- **环境**：macOS arm64 / bash 5.3.9 / Solar Harness 4-pane / coordinator + chain-watcher + graph-scheduler 在线。
- **路径白名单**：S1 节点唯一可写 `/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md`。本 PM 切片可写 `<sid>.prd.md` + `<sid>.prd.html` + `<sid>.status.json`（phase/history 更新）+ ACK 文件。其他一律禁动。
- **不动代码**：禁止改 `~/.solar/harness/lib/` / `tools/` / `schemas/` / `templates/` / `bin/` 任何文件。
- **不动 live tmux**：禁止 `tmux send-keys` / `tmux kill-pane` / `tmux respawn-pane`。
- **不重启 harness**：禁止 `solar-harness restart` / 杀 coordinator / chain-watcher。
- **secrets**：handoff / log 写盘前 redact（OAuth code、API key、token）。
- **API 兼容**：现有 `solar-harness context inject / session evaluate / intent-gateway capture` 调用方式不变。
- **/tmp 边界**：本 sprint 故意把 marker 写到 `/tmp`（smoke 一次性，不污染仓库）；这是 sprint-specific 例外，**不要把这条扩展为允许其他 sprint 产出落 /tmp**（STATE.md Constraints 仍约束生产 sprint：所有产出不入 `/tmp`）。
- **PM 角色边界**：不写代码 / 不动 status 到 implementation / 不跳 PRD schema / 不直接派 builder。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| `/tmp/solar-dispatch-smoke/` 被系统重启清理 → 历史 smoke 证据丢失 | 无法追溯 | smoke 设计本身就是一次性 marker；事件日志 events.jsonl 永久保留 builder pane / dispatch id ✅ |
| Smoke test 被误当业务 sprint → 拖累调度池 | chain 卡 | task_graph `request_type=strategy` + write_scope 严格限定 + S1 ≤ 5 分钟自然完成 ✅ |
| builder pane 收 dispatch 但卡在 plan mode / proceed prompt | smoke 假成功 | S1-handoff 需含 verification_time，evaluator 抽字段断言；TUI pane recover sprint (S02-architecture) 处理 prompt 卡死 |
| 多个 dispatch 并发命中同 pane → 撞同 pane | 假并发 | lease-based runtime sprint 的 `actor_runtime.submit()` 已落地（fcntl.flock atomic acquisition） |
| PRD 缺失 → coordinator 拉回 PM 循环 | sprint 永远卡 | 本切片即修复（写 PRD + schema PASS + 触发 mtime） |
| handoff 三字段缺一 → evaluator FAIL | smoke 不 PASS | S1-handoff 已含三字段（grep 验证） |
| `/tmp` marker 与未来真实业务 sprint 边界混淆 | 团队误学 | PRD §约束明确"sprint-specific 例外，不可推广" |
| Capability 实际未被调用 → 验证 capability 注入闭环失败 | smoke 漏检 | FR-4 明示"注入但不要求执行"；后续可加 effectiveness scorecard 但本 sprint 不阻断 |

## 开放问题 / Open Questions

- **OQ-01** smoke test 跑多久运行一次？每次 coordinator / dispatch 重构后手动跑？还是 cron 定时跑？**Owner**：harness ops sprint。
- **OQ-02** Smoke marker 是否需要写额外 metadata（git commit SHA / harness version / model 路由结果）便于事后回溯？**Owner**：smoke evolution sprint。
- **OQ-03** 是否需要并行 smoke（同时 dispatch 到 4 个 pane 验证并发）？当前只单节点。**Owner**：future smoke matrix sprint。
- **OQ-04** Capability 实际调用 vs `injectable_only` 应该如何在 smoke 里区分？effect scorecard 仍是 `pending_worker_evidence`。**Owner**：capability runtime sprint。
- **OQ-05** marker 文件 schema 是否需要 JSON 化（便于 evaluator 程序化断言），还是保持当前 Markdown？**Owner**：smoke schema 设计。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（schema 11 节齐全）。
- `<sid>.dispatch.md`（coordinator emit 的 PM dispatch）。
- `<sid>.S1-dispatch.md` + `.intent.json` + `.runtime-context.json`（builder 节点 dispatch 链路证据）。
- `<sid>.S1-handoff.md`（**已交付**，403 字节，含三字段）。
- `<sid>.S1-physical-plan.json`、`<sid>.S1-capsule-plan.json`（builder pane 物理执行计划）。
- `<sid>.task_graph.json`（单节点 S1，`write_scope` 限定，`required_capabilities` 列 7 个 harness.*）。
- `<sid>.events.jsonl`（append-only 事件流，含 builder pane=`solar-harness-lab:0.2`、dispatch_id=`graph-sprint-...-S1-20260528T030610Z`）。

### 当前实施状态（PM 不动）

| 步骤 | 状态 | 证据 |
|------|------|------|
| Coordinator emit S1-dispatch | ✅ | `<sid>.S1-dispatch.md` 13471 字节 |
| Dispatcher tmux_submit_requested | ✅ | events.jsonl seq 2 |
| Builder pane processing verified | ✅ | events.jsonl seq 3 `processing_verified_without_keyword` |
| Marker file 写出 | ✅ | `/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md` 403 字节 |
| S1-handoff 写出 | ✅ | `<sid>.S1-handoff.md` |
| State transition active → drafting (gate_missing_prd) | ✅ | events.jsonl seq 8 |
| PRD 修复 | 本切片即满足 | `<sid>.prd.md` 写完 |
| status.json phase=prd_ready | 本切片末步 | history 追加 prd_completed |
| Planner → Builder → Evaluator | 后续 | smoke 端到端剩余路径 |

### 给 Coordinator 的明确指令

- **不要重做 S1**：S1 marker 文件已存在，S1-handoff 已写。本 PM 切片只补 PRD，不动 task_graph / S1-handoff / S1-dispatch / events.jsonl。
- **PRD mtime 刷新**：coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 `gate_missing_prd` → 进入 planner（chain-watcher 自动接）。
- **smoke 性质决定下游**：smoke 不需要复杂 planner design；Planner 可以直接产 `*.plan.md`（写 "verify S1 done, no further work needed"）+ task_graph 标 S1 done + handoff_to=evaluator。

### 不在 PM 范围、必须 Planner / Evaluator 处理

- Planner 写 `*.plan.md`（≤ 1 节，仅声明 smoke 已完成）+ 更新 `task_graph.json` S1 status → passed。
- Evaluator 跑断言：`grep -E "builder.pane|dispatch.id|verification"` on marker file + `<sid>.S1-handoff.md`；产 `*.eval.md` + `*.eval.json` verdict=PASS。
- 最后 coordinator 标 sprint passed。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context)。Capability injection 含 ATLAS / Autoresearch (advisor only) / Everything Claude Code / MarkItDown / Solar-Harness Runtime / Superpowers / agency-agents / gstack / solar-autopilot-monitor / solar-graph-scheduler / solar-intent-engine / solar-knowledge-ingest — 本 sprint 全部 `injectable_only`，没有 worker_used evidence（smoke 性质，不要求执行）。
