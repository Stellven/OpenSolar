# Handoff — S04 调度、自动化与可视化

Sprint: `sprint-20260529-跑通-gemini-deep-research-...-s04-orchestration-ui`
Nodes: U1 → (U2, U3) → U4 | Gates: auto-activation / status-ui-surfacing / runtime-evidence / orchestration-handoff
Knowledge Context: solar-harness context inject used
Session Log: n/a (builder slice; evaluator 评审时执行 session evaluate)
Harness Modules Used: harness-knowledge, harness-graph

## Summary

把 S03 核心能力接入 harness 编排面，落新增独立集成包 `integrations/gemini_deep_research/`
（PACKAGE_PREFIX 白名单内），**未改任何 PROTECTED_CORE**，全部通过既有扩展点接入：
U1 自动激活+角色路由（复用 workflow_guard / graph scheduler 只读语义）、
U2 status UI 投影（epic→child sprint→DAG node 树 + 能力使用 + 阻塞原因）、
U3 运行时结构化完成证据（取代「自然语言声称完成」，evaluator 可复核）。

## 交付物（10 个 .py，全部在各节点 write_scope 内）

- U1 `orchestration/`: `auto_activation.py`（`decide_run_role` DR 生命周期→角色；`ready_nodes` 只读 DAG 就绪计算；`route_sprint` 透传既有 workflow_guard）+ `test_auto_activation.py`(9 测试)
- U2 `ui/`: `status_view.py`（`build_epic_tree`/`render_text`/`to_dict`，读 *.status.json + *.task_graph.json；blocker 仅在真正 waiting 时显示，避免 active sprint 误报陈旧 blocked_by）+ `test_status_view.py`(9 测试)
- U3 `evidence/`: `completion_evidence.py`（`build_evidence` 从事件日志派生 async_state 轨迹/尝试数/成功判据/verdict；`verify_evidence` 让 evaluator 从同一事件重派生比对；`write_evidence` 落盘 var/，不入 /tmp）+ `test_completion_evidence.py`(6 测试)
- 包根 `__init__.py` ×4

## 已验证（实际命令 + 结果）

1. **全量单测** — `PYTHONPATH=lib/capabilities python3 -m unittest gemini_deep_research.tests.test_core integrations.gemini_deep_research.orchestration.test_auto_activation integrations.gemini_deep_research.ui.test_status_view integrations.gemini_deep_research.evidence.test_completion_evidence`
   → **Ran 52 tests / OK**（S03 核心 28 + S04 集成 24）。
2. **U1 真实接线** — `ready_nodes` 对真实 S03 graph（全 reviewing）返回 `[]`；对 S04 graph 返回 `['U1']`；`route_sprint` 透传真实 workflow_guard 返回 `{stage: planning_complete, ...}`。
3. **U2 真实投影** — `build_epic_tree(epic)` 渲染出 5 个 child sprint（S01/S02 passed、S03/S04 active、S05 queued）+ 各 DAG node 状态/gate/能力 + S05 真实 blocker `blocked_by:runtime,ui`；active sprint 不再误报陈旧 blocker（专项测试覆盖）。
4. **U3 证据复核** — `verify_evidence` 对真实跑过的 complete run 重派生 verdict 一致；对 FAILED run 谎称 complete 的声明被 `agrees=False` 当场拆穿（test_evaluator_catches_false_claim）。

## Diff 自审（每个文件目的）

- `orchestration/auto_activation.py` — DR 生命周期→planner/builder/evaluator/human 路由；waiting_human blocker 覆盖为 human+not-ready；ready_nodes 只读不改 scheduler 状态；route_sprint 纯透传。
- `ui/status_view.py` — 只读聚合 status.json+task_graph.json 成 epic 树；`_is_waiting` 门控 blocker 显示避免陈旧误报。
- `evidence/completion_evidence.py` — 完成判定基于 event-replay + evaluate_success（结构化），非 NL；verify_evidence 供 evaluator 复核。
- 3 个 test_*.py — 24 测试，含真实 graph/workflow_guard/epic 树断言。

## 上游依赖

- S03 core-runtime（handoff 已读，read_scope 内）：`GeminiDRController`/`ControllerState`/`EventLog`/`evaluate_success`/`compat.project_status` 被本层直接 import 调用——真实调用链，非孤立模块。
- 既有 `workflow_guard.route` / `graph_scheduler` / `*.status.json` 投影面。

## 下游影响

- S05 verification-release: 可消费 `build_evidence`/`verify_evidence` 做 activation-proof；可用 `ready_nodes`/`decide_run_role` 驱动端到端编排；用 `build_epic_tree` 出发布报告树。

## Scope Compliance

- 仅写入 `integrations/gemini_deep_research/{orchestration,ui,evidence}/`（各节点 write_scope）+ 包根 `__init__.py` + 本 handoff（U4 write_scope）。
- PROTECTED_CORE 8 文件**未编辑**（仅只读调用 workflow_guard/graph_scheduler，及 graph_scheduler mark 改 task_graph.json）。
- **scope 冲突核对：无冲突** — 父 epic traceability.json 无 file-level write_scope 与 `integrations/gemini_deep_research` 或 `lib/capabilities/gemini_deep_research` 重叠，故**不回写**父级 traceability（沿用 S02 A4 判定依据）。

## 未验证 / 风险

- **真实 Gemini DR 端到端未跑**：U1/U3 在真实 mock 轨迹与 fake operator 上验证逻辑；真实浏览器路径（`GEMINI_DR_REAL_CALLS=1`）需人工授权，未执行（NB1/NB2）。
- U2 是文本/结构化投影（`render_text`+`to_dict`），**非图形化 web UI**；接入实际 status server 渲染前端由下游/人工决定。
- U1 `route_sprint` 透传 workflow_guard；自动派发到 pane 的真实 autopilot 接线点由 autopilot import 本模块完成，本切片未触发真实派发。

## 未闭环项

- 真实调用授权开关、凭证/ToS 合规（贯穿 S03–S05，人工）。
- U2 前端可视化渲染层（如需 HTML/web）。
- 重试默认值最终拍板（NB6）。

状态: U1–U4 全部置 reviewing，交 evaluator。本切片为集成层实现 + 单测，**不声称**父 Epic 已端到端跑通（真实 DR 调用 gated off）。
