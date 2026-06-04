# Design — Intent Execution Contract (Codex Bridge Smoke, sprint-level)

sprint_id: `sprint-20260525-155538-intent-execution-contract-44d68383`
epic_id: null (codex-bridge auto-emit smoke test)
role: planner
status: planning_complete
generated_at: 2026-05-28T14:52:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
detail_reference: `<sid>.prd.md` (10K 11-section schema) + 17 codex-bridge auto-emit artifacts
source: codex_bridge intent-20260525-155538-44d6838383 (unique-1779724538, 2026-05-25 11:55)

## 0. Sprint 性质

**Codex bridge auto-emit smoke test sprint** — Verifies that Codex bridge can emit a full sprint chain (raw_intent → requirement_ir → rewritten_intent → product-brief → PRD → contract → task_graph → capsule_plan → coverage_report → acceptance_verdict → handoff) and survive PM `gate_prd_schema` + Planner artifacts backfill。复用 social signal plane (sprint-20260527-ai-influence-social-signal-plane-convergence) 同款 codex-bridge backfill pattern。

## 1. 现状快照

| 维度 | 事实 |
|------|------|
| Codex bridge 全套 17 artifacts | 全 5/25 11:55 同分钟 emit (raw/IR/rewritten/brief/PRD/contract/Contracts.yaml/task_graph/capsule_plan 115K/coverage_report/acceptance_verdict/handoff PM 阶段/etc.) ✅ |
| PRD (PM backfilled 5/28 00:59) | 10K, 11-section schema 完整 ✅ |
| task_graph.json (codex bridge emit, schema 完整) | 5 节点 S1-S5 + 4 gates G_PLAN/G_IMPL/G_VERIFY/G_REVIEW; 含 capsule_plan inline + logical_operator (DeepArchitect/ImplementationPlanner/etc.) + dispatch_task_type + capsule constraints |
| handoff.md (PM 阶段) | 653 bytes; Solar Harness 视角的 Planner 接力指示 |
| Drift | events seq=7/12 dispatch_failed (pane_not_idle, 与其他 sprint 同源问题) |
| 缺 sprint-level Planner artifacts | design.md ❌ (本文件补) / plan.md ❌ (Planner 补) / planning.html ❌ (Planner 补) |

## 2. 5-Node DAG (per existing task_graph.json, codex-bridge emit)

```
S1 plan (DeepArchitect / mini-claude-opus-planner, depends_on=[], priority=50, gate=G_PLAN)
    └─→ S2 impl (depends_on=[S1], gate=G_IMPL)
          └─→ S3 verify (depends_on=[S2], gate=G_VERIFY)
                └─→ S4 review (depends_on=[S3], gate=G_REVIEW)
                      └─→ S5 close (depends_on=[S4])
```

每节点 capsule_plan 含 logical_operator + capability_capsule_id + dispatch_task_type + selected_skills + operator_constraints (preferred/forbidden operator profile)。

## 3. 写范围 (Planner 本切片)

| 操作 | 路径 |
|------|------|
| Planner 切片 | `<sid>.design.md` (本文件) + `<sid>.plan.md` + `<sid>.planning.html` + `<sid>.status.json` (phase 推进) + ACK |
| **task_graph patch (可选)** | 已有完整 schema (5 节点全字段), 不必再 patch; 若有缺失字段, 只追加不覆盖 codex-bridge emit |
| **不动** | 17 codex-bridge artifacts (raw_intent/IR/rewritten/brief/PRD/contract/Contracts.yaml/task_graph/capsule_plan/coverage_report/acceptance_verdict/handoff) |
| **不动** | `<sid>.prd.md` (PM 5/28 backfilled, schema PASS) |
| **严格禁止** | 重写 codex-bridge 自动产物 (PRD 明示) |

## 4. Stop Rules (per PRD §约束)

- 不动 17 codex-bridge 自动产物
- 不重写 capsule_plan (115K)
- 不动 Requirement IR (唯一事实源, per PRD)
- 不绕过 planner 派 builder (per PRD non-goal)
- 不打印 secrets
- 不重启 harness
- 不动 codex-bridge 路径 (`~/.solar/codex-bridge/from-codex`)
- 不写实施代码以外的乐观词

## 5. 失败恢复 / 同期 sprint 关系

- Drift recurrence: 与其他多 sprint 同源 graph_doctor + pane_not_idle 问题 (TUI epic S03 治本)
- 与 social signal plane (sprint-20260527-ai-influence-social-signal-plane-convergence) 同款 codex-bridge sprint pattern
- 与 LMF / MTSPR / TCMA / smoke / smoke-rerun / UAKG 同款 backfill 重复 — 已成为标准 Planner backfill 工序

## 6. 给后续接力

- Planner backfill 完成 → coordinator 派 builder/evaluator 跑 S1-S5
- S1-S5 大部分实施由 codex-bridge cap capsule (`cap.requirement-compiler-planner` 等) 已预设, builder 主要消费 capsule_plan
- 长期: 未来 codex-bridge PRD 模板应预填 11 节 schema, 避免 PM gate_prd_schema 循环

## 7. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; ATLAS / Autoresearch / Codex Bridge / Everything Claude Code 等 capability `injectable_only`。

17 codex-bridge artifacts + PRD 10K + task_graph 11K + capsule_plan 115K = ~150K total sprint evidence 已 self-contained。
