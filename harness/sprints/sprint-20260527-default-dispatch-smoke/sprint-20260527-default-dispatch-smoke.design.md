# Design — Default Dispatch Smoke (sprint-level, minimal)

sprint_id: `sprint-20260527-default-dispatch-smoke`
epic_id: null (standalone smoke)
role: planner
status: planning_complete
generated_at: 2026-05-28T07:50:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
detail_reference: `<sid>.prd.md` (13K, 含 §架构交接/Planner Handoff 明确指令)

## 0. Sprint 性质

**Default dispatch smoke test** — 验证 coordinator → dispatch → builder pane → handoff → status update 默认链路。单节点 S1, **零仓库改动**, marker 落 `/tmp` (sprint-specific 例外)。

## 1. S1 已完成快照

| 维度 | 事实 |
|------|------|
| S1 builder | `solar-harness-lab:0.2` (events.jsonl seq=2) |
| S1 dispatch_id | `graph-sprint-20260527-default-dispatch-smoke-S1-20260528T030610Z` |
| S1 marker file | `/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md` (403 bytes, 2026-05-28 03:07) |
| S1 handoff | `<sid>.S1-handoff.md` (含三字段, scope compliance PASS) |
| S1 task_graph status | reviewing |
| 7 ACs (per PRD) | AC-1..AC-5 ✅ (S1 已交付); AC-6 ✅ (PRD 13K); AC-7 本切片末步 |

## 2. 架构 (per PRD §架构交接)

PRD 已明确 Planner 不需做复杂设计——本 sprint 是 smoke, S1 已 PASS。Planner 工作仅 sprint-level artifacts 合规化:

- contract.md (本切片新写)
- design.md (本文件, 简短)
- plan.md (简短, 声明 smoke 已完成)
- task_graph.json (升级 schema, 标 S1 done)
- planning.html (renderer)
- 推 status: phase=planning_complete, handoff_to=evaluator

## 3. DAG (单节点)

```
S1 (DONE PASS by solar-harness-lab:0.2 @ 2026-05-28T03:07Z)
  └─→ (no downstream node; sprint 走 PM → Planner → Evaluator → close)
```

S1 已完成, 不重做。Evaluator 任务 (per PRD §架构交接): `grep -E "builder.pane|dispatch.id|verification"` on marker 文件 + S1-handoff, 产 eval.md/json verdict=PASS。

## 4. 文件级写范围 (本 Planner 切片)

| 节点 | write_scope |
|------|-------------|
| Planner (本切片) | `<sid>.contract.md` + `<sid>.design.md` + `<sid>.plan.md` + `<sid>.planning.html` + `<sid>.task_graph.json` (schema patch only, S1 status 保留) + `<sid>.status.json` (phase 更新) + ACK file |

**严格禁止**: 重做 S1 / 改 `~/.solar/harness/` 任何 lib/tools/schemas/templates/bin / 动 live tmux pane / 重启 harness / 改其他 sprint。

## 5. Stop Rules

- 不重做 S1 (已 PASS)
- 不改仓库代码
- 不动 live tmux pane
- 不重启 harness
- 不把 /tmp 边界推广到生产 sprint
- 不用乐观词

## 6. 失败恢复

- 本 Planner 切片失败 → 单文件重写, 不影响 S1
- 若 evaluator FAIL → S1-handoff 三字段 grep 失败 → S1 重派 builder (新 dispatch_id)

## 7. 给 Evaluator 接力 (per PRD §架构交接)

- 命令: `grep -E "builder.pane|dispatch.id|verification" /tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md && grep -E "builder.pane|dispatch.id|verification" <sid>.S1-handoff.md`
- 输出: `<sid>.eval.md` + `<sid>.eval.json` (verdict=PASS)
- Coordinator 标 sprint passed

## 8. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB。本 sprint 是 smoke 性质 self-contained, 无需深度知识。
