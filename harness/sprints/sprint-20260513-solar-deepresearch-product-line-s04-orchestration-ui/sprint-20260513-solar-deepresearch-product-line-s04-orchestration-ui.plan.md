# Plan — Solar DeepResearch Product Line · S04 Orchestration & UI

Sprint: `sprint-20260513-solar-deepresearch-product-line-s04-orchestration-ui`
Slice: orchestration-ui (control plane integration)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. DAG

```text
N1 cli-extension           ─┐
N2 capability-registration ─┤
N3 graph-scheduler-router  ─┤
N4 status-ui-research      ─┤
N5 dispatch-prompt-injector─┴── N6 integration+handoff ── handoff
```

6 节点，5 并行上游 + 1 join。Cost = M+M+L+M+M+S = 约 12 单位。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Model | Cost | Gate |
|------|------|---------|-------|------|------|
| **N1** | 补齐 11 个 research 子命令路由 (S03 5 个 + 本切片 6 个: run/plan/search/mine/outline/write/check/compile/export) | — | sonnet | 2.5 | cli-extension-pass |
| **N2** | 注册 6 个 research.* capability 到 capability_inference + solar_skills | — | sonnet | 2.0 | capability-pass |
| **N3** | 加载 deepresearch.dag-template.json 到 graph-scheduler，支持 R0-R11 dispatch，section 级 write_scope | — | sonnet | 3.0 | dag-router-pass |
| **N4** | status-server 加 /research/<sid> 路由 + activation-proof 集成显示研究指标 | — | sonnet | 2.0 | status-ui-pass |
| **N5** | dispatch_prompt_injector + coordinator hook 注入研究硬规则 | — | sonnet | 2.0 | injector-pass |
| **N6** | 集成 check + 更新 epic traceability + 写 handoff | N1-N5 全 | sonnet | 1.0 | integration-pass |

Total: 12.5 units。

## 3. Parallelism

- **N1-N5 全部并行**（write_scope 互斥）。
- **N6 join**：N1-N5 全 passed 后启动。
- 最大 builder 并发 = 5 pane。

## 4. Dispatch Batches

- **batch-1**: `[N1, N2, N3, N4, N5]`，join_gate=`[cli-extension-pass, capability-pass, dag-router-pass, status-ui-pass, injector-pass]`
- **batch-2**: `[N6]`，join_gate=`[integration-pass]`

## 5. Per-Node Acceptance

### N1 cli-extension
- `solar-harness research --help` 列 11 个子命令: init, add-source, extract, ledger, status, run, plan, search, mine, outline, write, check, compile, export (S03 已有 5 个 + 本节点新增 6 个)
- 每个新子命令至少有 1 个 smoke testcase
- `solar-harness doctor` exit 0（向后兼容）
- `pytest harness/tests/research_integration/test_cli_full.py -v` 全绿
- 不破坏现有 solar-harness 路由

### N2 capability-registration
- `harness/lib/capability_inference.py` 注册 6 个 research.* 能力: source.search, evidence.extract, claim.mine, citation.verify, report.compile, factuality.evaluate
- `harness/skills/solar-deep-research/SKILL.md` 创建，含 evidence/effect/scope 字段
- `solar-harness capability-list | grep research\\.` ≥ 6
- activation-proof for each capability outputs valid evidence
- 单测 `test_capability.py` assertion ≥ 8

### N3 graph-scheduler-router
- `harness/lib/graph_scheduler_research.py` 实现 `load_deepresearch_template()` + `dispatch_research_node()`
- `harness/lib/graph_node_dispatcher.py` 只追加 1 个 `if node.id.startswith("R")` 分支，不动其他逻辑
- 能加载 S02 deliverable `deepresearch.dag-template.json` 并通过 validate
- R7 (section_writing_batch) 支持按 section_id 分发到不同 builder pane
- section 级 write_scope 隔离：两个并行 section builder 不能写同一文件
- 单测 `test_dag_router.py` assertion ≥ 10

### N4 status-ui-research
- `harness/status-server/research_routes.py` 添加 `/research/<sid>` 路由
- 返回 JSON 含: source_count, evidence_count, claim_count, unsupported_rate, citation_accuracy, status
- activation-proof 命令 `solar-harness activation-proof --research <sid>` 输出 markdown 报告
- 不修改现有 status-server 主入口
- 端口仍是 8765
- 单测 `test_status_ui.py` assertion ≥ 8

### N5 dispatch-prompt-injector
- `harness/lib/dispatch_prompt_injector.py` 实现 `inject_research_rules(dispatch_text, node_id) -> str`
- 注入 4 类规则：禁止 unsupported claim / 禁止无 span_text evidence / 禁止 connector 静默降级 / 禁止单节点 10w 字
- `coordinator.sh` 在生成 research 节点 dispatch 时调用 injector（用 hook，不改主循环）
- hook 文件位于 `~/.solar/hooks/research_dispatch_inject.sh`
- 单测 `test_prompt_injector.py` assertion ≥ 8

### N6 integration + handoff
- 跑 `pytest harness/tests/research_integration -v` 全绿
- 跑 `solar-harness doctor` exit 0
- 跑端到端冒烟: `solar-harness research init <tmp>` → capability 显示 → status UI 返回 → dispatch 注入测试
- 更新 `epic-…traceability.json` children[3] status → `passed/completed`
- 写 handoff.md：5 集成点清单 + S05 evaluator 测试入口 + `evaluator_can_review: true` + `s05_can_start: true`

## 6. Routing Policy

- 所有节点 `sonnet`。
- N3/N5 涉及 graph_scheduler/coordinator 关键路径，必须 Sonnet 双倍审慎。
- 禁止 worker webfetch。

## 7. Stop Rules (执行期)

- 修改现有 `coordinator.sh` 主循环 → fail（用 hook 不修改主体）。
- 修改 `graph_node_dispatcher.py` 主路径 → fail（只允许追加分支）。
- 修改 status-server 主入口 → fail。
- 任一节点 mock graph_scheduler/capability_inference → fail。
- `solar-harness doctor` 出错 → fail，立即回滚。
- N6 在 N1-N5 任一 pending 时 dispatched → 阻断。
- 声称 epic 完成 → fail。

## 8. Exit Criteria

- 6 节点全 passed
- `solar-harness research --help` 列 11 个子命令
- `solar-harness capability-list | grep research\\.` ≥ 6
- `solar-harness graph-scheduler validate --graph <dag-template>` exit 0
- curl `localhost:8765/research/<test-sid>` 返回有效 JSON
- `solar-harness doctor` exit 0
- handoff `evaluator_can_review: true` + `s05_can_start: true`

## 9. Evaluator 复核入口

1. `solar-harness research --help | grep -E '^\s+(init|add-source|extract|ledger|status|run|plan|search|mine|outline|write|check|compile|export)' | wc -l` == 14 (15 lines including subcommand header)
2. `solar-harness capability-list | grep -c '^research\\.'` ≥ 6
3. `solar-harness graph-scheduler validate --graph sprints/*deepresearch.dag-template.json` exit 0
4. `curl -s localhost:8765/research/test-sid | jq '.evidence_count'` 不是 null
5. `cat ~/.solar/hooks/research_dispatch_inject.sh` 存在
6. `pytest harness/tests/research_integration -v` 全绿
7. `solar-harness doctor` exit 0
8. `jq '.children[3].status' epic-*.traceability.json` == `"passed"`

## 10. Out of Scope

- **S05**: 端到端验证 + 负控 + smoke benchmark + 文档 + Knowledge 归档
- **Future**: 活体 connector 接入、ReportAST 编译器、Factuality evaluator、CI 集成
- **Future**: 多 pane 并行 section writing 的实际并发优化

## 11. 当前状态说明

本切片当前 `status=queued, phase=epic_waiting_dependency`（被 S02 阻断；S03 也需 passed 才能实际跑）。spec 提前就绪，**status 保持不变**。

注：S04 在 epic.task_graph.json 中只声明依赖 S02，但实际集成需要 S03 的 cli.py 和 module — 因此 task_graph.json 的 `prerequisites` 字段同时要求 S02 + S03 passed，双重保险。
