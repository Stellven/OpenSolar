# Handoff — S05 验证、回归与发布证据

Sprint: `sprint-20260529-跑通-gemini-deep-research-...-s05-verification-release`
Nodes: V1 → (V2, V3) → V4 | Gates: e2e-flow-test / negative-and-activation-proof / docs / regression-and-release-evidence
Knowledge Context: solar-harness context inject used
Session Log: n/a (builder slice; evaluator 评审时执行 session evaluate)
Harness Modules Used: harness-knowledge, harness-graph

## Summary

为 Gemini Deep Research epic 建立**端到端 + 负控 + activation-proof + 回归报告 +
文档**的可复现验收层，作为 epic 关闭的最终 gate。全部产出在各节点 write_scope 内，
**未改任何 PROTECTED_CORE**，只读/公共函数方式接 workflow_guard / graph_scheduler /
browser_job_runtime。真实 Gemini 调用仍 gated off（`GEMINI_DR_REAL_CALLS=1`，人工授权）。

## 交付物（全部在 write_scope 内）

- V1 `tests/gemini_deep_research/e2e/test_o1_o6_flow.py` + `__init__.py` — O1-O6 全链路 e2e（5 测试）
- V2 `tests/gemini_deep_research/control/test_negative_and_activation.py` + `__init__.py` — 负控 + activation-proof（13 测试）
- V3 `integrations/gemini_deep_research/README.md` — 集成文档（O1-O6 / 包布局 / 真调用门控 / 成功判据 / 测试命令 / scope）
- V4 `reports/gemini_deep_research/s05-regression-release-report.md` + 本 handoff

## 已验证（实际命令 + 结果）

1. **S03 核心 + S04 集成** — `PYTHONPATH=lib/capabilities python3 -m unittest gemini_deep_research.tests.test_core integrations.gemini_deep_research.orchestration.test_auto_activation integrations.gemini_deep_research.ui.test_status_view integrations.gemini_deep_research.evidence.test_completion_evidence` → **Ran 52 tests / OK**。
2. **S05 e2e + 负控/激活** — `PYTHONPATH=lib/capabilities python3 -m pytest tests/gemini_deep_research/e2e tests/gemini_deep_research/control -q` → **18 passed**。
3. **回归总计 70 测试全绿**（52 + 5 + 13）。
4. **真实接线**：V1/V2 的 `test_*_mock_mode` 经真实 `DeepResearchBrowserAdapter → browser_job_runtime` 跑完整 O1-O6，落真实 job，但无真实 DR 输出时**诚实 FAILED、零伪造文献**。
5. **双入口**：user-direct 与 upstream-fed 共用 `submit_research`，upstream_ref 持久化进 intake 事件（V1 专项测试）。

## Diff 自审（每个文件目的）

- `tests/.../e2e/test_o1_o6_flow.py` — O1-O6 happy path（分类文献+事件轨迹+replay 等价）、upstream 入口、真算子 mock 诚实失败。
- `tests/.../control/test_negative_and_activation.py` — 6 负控（optimizer 不可用/重试到上限/多轮重试不成功/waiting_human/done-但不完整/mock 不伪造）+ 7 activation-proof（ready_nodes 三态 + decide_run_role 角色路由全覆盖）。
- `integrations/gemini_deep_research/README.md` — 集成说明文档。
- `reports/gemini_deep_research/s05-regression-release-report.md` — 回归与发布证据 + epic-close guard + 异常上报。
- 4 个 `__init__.py`（e2e/control 包标记）。

## 上游依赖（真实调用链，非孤立）

- S03 core：`GeminiDRController`/`EventLog`/`RetryPolicy`/`evaluate_success`/`compat.DeepResearchBrowserAdapter` 被 e2e/负控直接 import 调用。
- S04 集成：`orchestration.auto_activation.{ready_nodes,decide_run_role}` 被 activation-proof 直接调用。
- 既有 `browser_job_runtime`（mock 模式落真实 job）。

## Scope Compliance

- 仅写 V1-V4 write_scope：`tests/gemini_deep_research/{e2e,control}/`、`integrations/gemini_deep_research/README.md`、`reports/gemini_deep_research/`、本 handoff。
- PROTECTED_CORE 未编辑。
- **scope 冲突核对：无冲突** — 父 epic `traceability.json` 无 file-level write_scope 与这些路径重叠 → **不回写**父级 traceability（沿用 S02-S04 判定）。

## ⚠️ 图状态完整性异常（评审前必读）

`2026-05-29T20:42:27Z` 一个自动进程（autopilot dry_run，20:41:29 enqueue V1）在
**无评审、且 S05 builder 产物尚不存在时**把 task_graph 的 **V2/V3/V4 标成 passed**，
多个 child sprint（S03/S04/S05）`status.json` 也显示 passed。这些 passed 无
`evaluated_by`/`note`、磁盘上无对应产物。按 Stop Rule「缺可复现验证不得标记 passed」
判为伪造。本切片把 **V1-V4 重标为 `reviewing`**（真实 builder-complete），未依赖伪造
passed。**建议 evaluator/PM 在 finalize epic 前审计 autopilot 自动接受路径。**

## 未验证 / 风险

- **真实 Gemini DR 端到端未跑**：`GEMINI_DR_REAL_CALLS=1` 需人工授权 + 凭证/ToS 合规，未执行。
- U2 仅文本/结构化投影，非图形化 web UI。
- 上述图状态异常未由本切片根因修复（autopilot 行为，超出 builder write_scope）。

## 未闭环项

- epic 关闭：须 **V1-V4 四 gate 全部经 evaluator passed** 后方可由 PM 关闭；当前为 builder-complete(`reviewing`)，**不声称 epic 已端到端跑通**。
- KB `_raw` 导出由 finalize 流水线在 accept 时执行（非 builder write_scope）。
- 真实调用授权 + 凭证合规（贯穿 S03-S05，人工）。
- autopilot 伪造 passed 路径审计（建议新开运维 sprint）。

状态: V1-V4 全部置 `reviewing`，交 evaluator。本切片为验证/回归/文档实现，**不声称**父 Epic 已端到端跑通（真实 DR 调用 gated off）。
