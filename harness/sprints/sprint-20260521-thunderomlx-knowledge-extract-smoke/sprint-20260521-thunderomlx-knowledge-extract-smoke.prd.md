# PRD: ThunderOMLX 知识抽取 Smoke (初次抽取 / 缓存未命中验证) — Graph 状态合规闭合

sprint_id: `sprint-20260521-thunderomlx-knowledge-extract-smoke`
epic_id: null (standalone legacy sprint)
slice: `verification-and-graph-close`
priority: P0
handoff_to: planner
generated_at: 2026-05-27T17:33:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
ack: dispatch `d-20260527T161505Z-44dffe`、之前 ACK 文件 `<sid>.ack-d-20260527T120307Z-f61d9a.json` 与 `<sid>.ack-d-20260527T161505Z-44dffe.json` 已落盘

## 用户原始需求（从 N1 任务原始 goal 回填）

使用后台无头 tmux worker pane，通过 ThunderOMLX / Qwen3.6 抽取本机同步来的 3 个需求 / 设计 / 合约文档。必须真实读取 input 目录文档，生成中文知识抽取报告，不要调用 Claude / Gemini 云模型。输出文件必须包含：功能模块、用户价值、设计结构、关键文件或命令、验证方法、风险边界、后续改进。还要在报告中写明 ThunderOMLX 路由证据检查方法。完成后写 handoff 并标记 reviewing。

本 sprint 验证的是 ThunderOMLX **首次抽取场景** (cache miss)，与同源 sibling sprint `sprint-20260521-thunderomlx-knowledge-extract-smoke-rerun` 互补——后者验证缓存命中 (cache_read_input_tokens=6656)，本 sprint 是 cache miss baseline (cache_read_input_tokens=0 属预期)。

## 背景 / Context

- **功能产出已完成**: N1 在 2026-05-21 由 multi-task worker `mt-20260521-175309-sprint-20260521-thunderomlx-k` 完成；2026-05-23 14:46 evaluator PASS + `.finalized` 文件落盘；Knowledge vault 已导出 accepted artifact。
- **Graph 状态漂移**: 2026-05-26 17:56 `graph_doctor_repair_sync` 重新同步 task_graph → 17:59 `graph_parent_ready_revoked` 撤销 ready 状态；N1 退回 `reviewing`，sprint 从 finalized 退回 active。同款问题也出现在 sibling sprint smoke-rerun，已通过 4 节点修复模式 (N1+N2+N3+N4) 闭合。
- **本 sprint 复用同款修复模式**：N1 保留功能产出 + N2 回填 graph 框架 eval artifact + N3 通过 sanctioned CLI 闭合 + N4 防再漂移。
- **Workflow Guard 新升级**: 现要求所有 active sprint 必须有 PM PRD；legacy standalone sprint (无 epic) 也不例外。本 PRD 即是合规化回填。
- **当前真实状态** (来自 task_graph.json 节点 status):
  - N1: status=passed (4 节点模式生效)
  - N2_eval_artifact_backfill: status=dispatched (N1-eval.md + N1-eval.json 已落盘)
  - N3_node_verdict_close: 尚未启动
  - N4_drift_guard: 尚未启动
  - gate `G_smoke_n1_closed_via_node_verdict`: blocked (等 N3/N4)

## 用户问题 / Problem

1. 功能 N1 已完成 (handoff + 2 个产出文件 + 5 条 acceptance 全满足 + 5/23 evaluator PASS + .finalized + 入库 accepted artifact)，但 graph_doctor 周期性 sync 把 sprint 退回 active 状态，无法真正闭合。
2. 4 节点修复模式已部分跑通 (N1 passed, N2 dispatched)，但 sprint 因 missing PM PRD 被 Workflow Guard 拦截，N3/N4 无法推进。
3. 需要补合规 PRD，让 sprint 通过 PM gate 后继续 N3 (sanctioned CLI 闭合 N1) + N4 (防再漂移验证) 直至 sprint passed。
4. 不允许重跑 N1 功能（产出已存在）、不允许触动 Knowledge vault 已导出的 accepted artifact、不允许破坏 `.finalized` 文件。

## 用户故事 / User Stories

- **US-01 (PM 视角)**: 作为 Solar 主用户，希望本 legacy sprint 通过 PM gate 合规化，让 Workflow Guard 不再拦截。
  - 验收: 本 PRD 存在 + 含 5 个 outcome + acceptance + non-goals + traceability。
- **US-02 (Planner 视角)**: 作为 Planner，希望保留已有 task_graph (4 节点修复模式) 与 plan.md，无需重新规划。
  - 验收: PRD 明示 "task_graph.json + plan.md 已存在；本 PRD 仅做合规化回填，不改变 DAG 结构"。
- **US-03 (Builder/Evaluator 视角)**: 作为下游执行者，希望 N3/N4 在 PM PRD 通过后能直接派发 (graph-dispatch CLI + drift guard)，不再因 missing_pm_prd 阻塞。
  - 验收: PRD 写明 N3 用 `solar-harness.sh graph-dispatch node-verdict` 闭合 N1 + N4 防再漂移验证 5 项 (status history / .finalized / accepted artifact / parent-ready / status stage)。
- **US-04 (Coordinator 视角)**: 希望 graph_doctor 下一次 sync 不再 revoke 本 sprint。
  - 验收: PRD non-goals 明示禁止删 `.finalized`、禁止动 accepted artifact；N4 drift_guard 提供再漂移检测。

## 范围 / Scope

本 sprint 只交付**graph 状态合规闭合**：
- N1 功能产出保留 (不重跑)
- 通过 4 节点修复模式 (N1+N2+N3+N4) 让 sprint passed
- gate `G_smoke_n1_closed_via_node_verdict` 推到 passed
- 不实施任何新功能、不动其他 sprint、不主动 close 任何外部状态

**stop_rules**:
- 缺 task_graph.json 不得派 builder (已有, 4 节点)
- 缺可复现验证不得标记 passed
- 不允许手改 task_graph.json 中 N1.status (per N3 evidence_policy.forbid_direct_status_field_writes_on_task_graph)
- 不允许重跑 N1 功能 (产出已 .finalized)
- 不允许把 cooldown 当作最终修复
- 不允许动 Knowledge vault 已导出 accepted artifact 或破坏 `.finalized`

## 验收标准 / Acceptance Criteria

### A1 — 5 个 outcome 全部带验收与边界

- **O1 N1 功能产出保留**: handoff + extracted-knowledge.md + monitor-reports/thunderomlx-knowledge-extract-smoke.md 三件齐 + 5 条 acceptance 全 satisfied + cache_read_input_tokens=0 属预期 (cache miss baseline)
- **O2 N2 graph 框架 eval 回填**: N1-eval.md + N1-eval.json 已落盘 (file size > 0)，含 verdict=PASS + 5 acceptance 逐条核查表 + evidence_paths ≥3
- **O3 N3 通过 sanctioned CLI 闭合**: 实际执行 `solar-harness.sh graph-dispatch node-verdict --graph <path> --node N1 --verdict pass --eval-json <N1-eval.json>` + stdout JSON 含 ok=true status=passed + N3-verdict-output.json 落盘
- **O4 N4 防再漂移**: 5 项验证齐 (status_history_no_new_revoke / finalized_intact / accepted_artifact_intact_or_NA / parent_ready_check_ok / status_stage_completed) + N4-drift-evidence.json 落盘
- **O5 PRD 合规**: 本 PRD 文件存在 + 含 5 outcome + non-goals + traceability + 用户故事 + 风险 + 约束 (per Workflow Guard 要求)

### A2 — Builder 工作不能直接派
- N3 必须走 sanctioned `graph-dispatch node-verdict` CLI (禁止手改 task_graph status)
- N4 只读校验 + 写本节点 evidence (禁止动上游 artifact)
- 不允许在 N1 节点重派任何 worker (功能产出已存在)

### A3 — Traceability Map
- 本 PRD ↔ task_graph 4 节点 ↔ N1 handoff + accepted artifact ↔ sibling sprint smoke-rerun (同款修复模式) 互链
- 与 `.finalized` (2026-05-23) 时间锚定一致

## 非目标 / Non-Goals

- 不绕过 planner 直接派 builder
- 不重跑 N1 知识抽取本身 (功能产出已存在; cache miss = 0 属预期)
- 不触动 Knowledge vault 中已导出的 accepted artifact
- 不破坏 `.finalized` 文件 (2026-05-23 10:46)
- 不真改 task_graph.json 中 N1.status (per N3 evidence_policy 必须走 CLI)
- 不真跑 ThunderOMLX API (功能产出已存在; 本 sprint 是 graph 闭合, 非功能复跑)
- 不动 sibling sprint smoke-rerun 任何 artifact
- 不擅自把 cooldown 当作最终修复
- 不删用户数据 / 不杀主 pane / 不重启 ThunderOMLX 服务
- 不真生产 DB 写入

## 约束 / Constraints

- **环境**: macOS arm64 (lisihaodeMac-mini.local)，bash 5.3.9, Solar 4-pane 已扩容到 5 evaluator panes (solar-harness:0.3 + solar-harness-lab:0.0..0.3)
- **路径**: 所有产出在 `~/.solar/harness/sprints/<sid>.*` 或 `~/.solar/harness/run/knowledge-extract-smoke/output/`；不放 /tmp
- **API 兼容**: solar-harness CLI (`graph-dispatch node-verdict`, `parent-ready-check`) 必须照常工作；本 sprint 不引入新 CLI
- **角色边界**: PM PRD 一次性回填后由 Planner 接手 (task_graph 与 plan.md 已存在, Planner 不必重新规划)
- **Sibling sprint 同源**: smoke-rerun 已通过同款 4 节点模式 closed; 本 sprint 是 cache miss baseline 对照, 修复模式完全复用

## 风险 / Risks

| 风险 | 影响 | 缓解 / Owner |
| --- | --- | --- |
| graph_doctor 再次周期 sync revoke | sprint 重新退回 active | N4 drift_guard 检测; status.history 检查无 new revoke / Coordinator |
| N3 CLI `graph-dispatch node-verdict` 不存在或失败 | N1 status=passed 推不动 | sibling smoke-rerun 已实测可用; 失败则 ATLAS structured repair / Builder |
| accepted artifact 在本 sprint 期间被外部进程改动 | 闭合校验失败 | N4 校验 accepted_artifact_intact 或标 N/A; 不主动改 / Evaluator |
| 共享 worker dispatch_id `mt-20260521-175309-...` 与 sibling sprint 重名 | worker pane 状态混淆 | N3 显式 `--graph <full-path>` 定位; 不依赖 worker lease / Coordinator |

## 开放问题 / Open Questions

- **OQ-01**: graph_doctor 何时改进为识别 `.finalized` 文件 + accepted artifact 双重信号后不再 revoke? → 留给 sprint-20260527-p0-solar-harness-tui-pane-recover (另一 epic 治理 graph 漂移)
- **OQ-02**: sibling sprint smoke-rerun 的 N3 CLI 调用是否真的产生了 task_graph 副作用持久化? → N4 校验 sprint 自身后, 留 evaluator 跨 sprint 对比

## 交付物 / Deliverables

- `sprint-20260521-thunderomlx-knowledge-extract-smoke.prd.md` (本文件, PM 回填)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.plan.md` (已存在, Planner 5/27 11:34)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.task_graph.json` (已存在, 4 节点 + solar.task_graph.v1 schema, validate ok)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.planning.html` (已存在, 5/27 12:18)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N1-handoff.md` (已存在, 2026-05-21)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N1-eval.md` (已存在, N2 5/27 13:02)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N1-eval.json` (已存在, N2 5/27 13:02)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N3-verdict-output.json` (待 N3)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N3-handoff.md` (待 N3)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N4-drift-evidence.json` (待 N4)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.N4-handoff.md` (待 N4)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.handoff.md` (sprint 最终 handoff, 4 节点全 passed 后)
- `sprint-20260521-thunderomlx-knowledge-extract-smoke.eval.md` 或 `.eval.json` (sprint 最终 evaluator)

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD (5 outcome + stop_rules + 约束 + 风险 + OQ)
- 已有 `task_graph.json` 4 节点 (N1 passed / N2 dispatched / N3 N4 pending) — Planner 不必重设计 DAG
- 已有 `plan.md` (6967 bytes) — Planner 不必重写
- N1-handoff.md (功能证据) + N1-eval.md/json (graph 框架 eval) — N3 必读
- sibling sprint `sprint-20260521-thunderomlx-knowledge-extract-smoke-rerun` 已通过同款模式闭合 — 参考样板

### Outputs Planner 不必新产出

- `*.design.md`: **可选** (本 sprint 是 graph 闭合修复, plan.md 已足够; design 文档可由 Planner 决定是否补)
- `*.plan.md`: 已存在
- `*.task_graph.json`: 已存在, validate ok
- `*.handoff.md`: 最终 join 节点产出 (N4 passed 后)

### 不在 PM 范围、必须 Planner/Builder 处理

- 真实跑 `graph-dispatch node-verdict` CLI → N3
- 真实校验 status.history / .finalized / accepted artifact → N4
- 跨 sprint 对比 smoke vs smoke-rerun → evaluator

### Knowledge Context

Knowledge Context: solar-harness context inject used (mirage degraded → QMD + Obsidian + Solar DB)

### Harness Modules Used

Harness Modules Used: harness-knowledge (context inject), harness-graph (validate ok, sibling smoke-rerun 同模式实测), harness-skills (knowledge-extractor profile), harness-ATLAS (列入 N3 CLI 失败兜底)
