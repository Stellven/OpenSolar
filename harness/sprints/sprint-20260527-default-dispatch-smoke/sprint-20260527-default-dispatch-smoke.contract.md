# Contract: Default Dispatch Smoke

sprint_id: `sprint-20260527-default-dispatch-smoke`
epic_id: null (standalone smoke test)
priority: P2
lane: harness-ops / smoke
handoff_to: evaluator (per PRD §架构交接, S1 已 builder PASS)
source: coordinator self-test (dispatch chain verification)

## Intent

Default-dispatch-ready smoke test: 确认 coordinator → dispatch.md → builder pane → handoff → status update 默认链路在每次重构后仍可用。单节点 S1, **零仓库改动**, marker 落 `/tmp/solar-dispatch-smoke/`。

## Required Capabilities

- `harness.context_preflight` / `harness.intent` / `harness.dispatch_visibility` / `harness.contracts` / `harness.dag` / `harness.status` / `harness.model_routing` (per task_graph S1 required_capabilities; smoke 性质, injectable_only, 不要求执行 - per PRD FR-4)

## Acceptance (per PRD §验收标准)

- AC-1: `/tmp/solar-dispatch-smoke/default-dispatch-smoke.handoff.md` ≥ 200 bytes (S1 PASS: 403 bytes)
- AC-2: handoff 含 builder pane / dispatch id / verification time 三字段 (S1 PASS)
- AC-3: S1 task_graph status = reviewing/passed (当前 reviewing)
- AC-4: 0 仓库代码改动 (S1 PASS)
- AC-5: 0 secret 打印 (S1 PASS)
- AC-6: PRD 存在 + schema PASS (本切片 PRD 已 13K 完整)
- AC-7: status.json phase=planning_complete + history 含 planner_plan_completed (本切片末步)

## Stop Rules (per PRD §约束)

- 不动 `~/.solar/harness/lib/` / `tools/` / `schemas/` / `templates/` / `bin/` 任何文件
- 不动 live tmux pane (`tmux send-keys` / kill / respawn 禁止)
- 不重启 harness
- 不重做 S1 (已 PASS; PM/Planner 切片只补 sprint-level artifacts)
- secrets redact (OAuth code / API key / token)
- API 兼容: 现有 `solar-harness context inject / session evaluate / intent-gateway capture` 不变
- /tmp 边界仅 smoke 例外, 不推广 (STATE.md 仍禁产出落 /tmp 对生产 sprint)

## Required Phases

- S1 builder (DONE PASS by `solar-harness-lab:0.2`)
- PM PRD backfill (DONE, 13K)
- Planner sprint-level artifacts backfill (THIS sprint planner pane)
- Evaluator (next, per PRD instruction: grep 三字段断言)
- Coordinator close (sprint passed)
