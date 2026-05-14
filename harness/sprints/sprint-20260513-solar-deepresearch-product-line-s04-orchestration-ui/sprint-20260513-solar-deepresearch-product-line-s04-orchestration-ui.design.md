# Design — Solar DeepResearch Product Line · S04 Orchestration & UI

Sprint: `sprint-20260513-solar-deepresearch-product-line-s04-orchestration-ui`
Epic: `epic-20260513-solar-deepresearch-product-line`
Slice: `orchestration-ui` (Planner pass)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

S03 已交付 `harness/lib/research/` Python module + 5 个 CLI 子命令（init/add-source/extract/ledger/status）。但 DeepResearch 还没真正接入 Solar-Harness 的控制面：
- DAG scheduler 不识别 R0-R11 research 节点
- capability plane 没注册 research.* 能力
- status UI 看不到 evidence/claim/unsupported_rate
- dispatch 文本没注入 Source/Evidence/Claim 规则给 builder pane

S04 把 S03 的 kernel 接入 autopilot / DAG dispatcher / status UI / pane prompt 注入，让 DeepResearch 变成产品级一等公民。

为什么单独切 S04：
- 接入控制面涉及 5 个独立子系统（CLI 扩展 / DAG 模板加载 / capability plane / status UI / dispatch prompt），并行可加速。
- S03 implementation 必须先稳定，S04 才能集成（依赖 S02 间接通过 S03）。
- S05 端到端测试需要 S04 集成完毕（status UI 显示指标、dispatch 注入规则）。

## 2. Design Goals

- **零回归**：现有 wake/dispatch/status/coordinator 行为 100% 不变。`solar-harness doctor` 必须 exit 0。
- **DAG 模板可加载**：S02 deliverable 的 `deepresearch.dag-template.json` 能被 graph-scheduler 加载并 validate。
- **Capability Plane 注册 ≥ 6 个 research.* 能力**：source.search / evidence.extract / claim.mine / citation.verify / report.compile / factuality.evaluate。
- **Status UI 显示指标**：activation-proof 输出 evidence/claim/unsupported_rate/citation_accuracy 字段。
- **Dispatch prompt 注入硬规则**：当 DAG 节点是 research 节点时，dispatch 文本自动追加「禁止 unsupported claim / 禁止无 span_text」等规则。

## 3. Non-Goals

- **不写新的 research 业务逻辑**：本切片只做集成；业务逻辑在 S03。
- **不实现 ReportAST 编译器**：留给后续 release sprint。
- **不接活体 connector**：仍用 S03 的 internal_mirage。
- **不替换现有 capability_inference 模块**：只在其上注册 research.* 能力族。
- **不重写 status-server**：在现有 `harness/status-server/` 添加 research 路由即可。
- **不优化性能**：MVP 即可。

## 4. Deliverables

| Deliverable | Owner | 内容 |
|---|---|---|
| `harness/solar-harness.sh` (扩展) + `harness/lib/research/cli.py` (扩展) | N1 builder | 补齐 run/plan/search/extract/mine/outline/write/check/compile/export 子命令路由（S03 只做 init/add-source/extract/ledger/status 5 个） |
| `harness/lib/capability_inference.py` + `harness/lib/solar_skills.py` (扩展) | N2 builder | 注册 6 个 research.* capability，每个含 evidence/effect/scope 字段 |
| `harness/lib/graph_scheduler_research.py` (新) + 集成到现有 graph-scheduler | N3 builder | 加载 deepresearch.dag-template.json，支持 R0-R11 节点 dispatch，section 级 write_scope 隔离 |
| `harness/status-server/research_routes.py` + UI hooks | N4 builder | 新增 /research/<sid> 路由，显示 source/evidence/claim/unsupported_rate/citation_accuracy 指标；activation-proof 集成 |
| `harness/lib/dispatch_prompt_injector.py` (新) + hook 到 coordinator | N5 builder | research 节点 dispatch 时自动注入 Source/Evidence/Claim/ReportAST 4 类硬规则到 pane prompt |
| `harness/tests/research_integration/test_*.py` | 每节点附带 | 集成测试覆盖每个子系统 |
| `…s04-orchestration-ui.handoff.md` | N6 builder | 集成总览 + 给 S05 的「测试入口」清单 |
| `…s04-orchestration-ui.design.md` (本文) + `plan.md` + `task_graph.json` | Planner | 三件套 |

## 5. DAG Topology

```text
N1 cli-extension           ─┐
N2 capability-registration ─┤
N3 graph-scheduler-router  ─┤
N4 status-ui-research      ─┤
N5 dispatch-prompt-injector─┴── N6 integration+handoff ── handoff
```

5 节点完全并行（write_scope 互斥）+ 1 join。所有 5 个上游节点都依赖 S03 的 `harness/lib/research/` 存在。

## 6. Acceptance Contract

| # | Acceptance | 验证 |
|---|---|---|
| **A1** | 11 个 research 子命令全部可调 | `solar-harness research --help` 列 11 个: run/plan/search/extract/mine/outline/write/check/compile/export/status |
| **A2** | Capability plane 注册 ≥ 6 个 research.* | `solar-harness capability-list \| grep research\\.` ≥ 6 |
| **A3** | dag-template 可加载 + 12 节点可识别 | `solar-harness graph-scheduler validate --graph deepresearch.dag-template.json` exit 0 |
| **A4** | Status UI 含 research 指标 | curl `localhost:8765/research/<sid>` 返回 JSON 含 evidence_count/unsupported_rate/citation_accuracy |
| **A5** | Dispatch 注入研究规则 | 一份测试 dispatch.md 由 injector 处理后含 "禁止 unsupported claim" + "禁止无 span_text" |
| **A6** | 零回归 | `solar-harness doctor` exit 0，现有 sprint dispatch 路径不变 |
| **A7** | 集成测试全绿 | `pytest harness/tests/research_integration -v` exit 0，断言 ≥ 30 |
| **A8** | epic traceability.json children[3] (S04_orchestration_ui) status=passed | jq 检查 |

## 7. Stop Rules

- **不破坏现有路由**：`solar-harness doctor` 出错 → fail，回滚 N1。
- **不允许新 mock 进 integration 测试**：S05 端到端依赖 S04 真集成，禁止 `@mock.patch` 替代 graph_scheduler 或 capability_inference。
- **不允许重写现有 coordinator.sh**：只能加 hook，不动主循环。
- **不允许在 status UI 显示假指标**：所有数字必须从 `research_eval.*.json` 实读。
- **N6 必须等 N1-N5 全 passed**：graph_scheduler 强制。
- **不允许声称 "DeepResearch 已上线"**：本切片只完成 orchestration 集成。

## 8. Parallelism & Write Scope

- N1 write_scope = `harness/solar-harness.sh`, `harness/lib/research/cli.py` (扩展), `harness/tests/research_integration/test_cli_full.py`
- N2 write_scope = `harness/lib/capability_inference.py`, `harness/lib/solar_skills.py`, `harness/skills/solar-deep-research/`, `harness/tests/research_integration/test_capability.py`
- N3 write_scope = `harness/lib/graph_scheduler_research.py`, `harness/lib/graph_node_dispatcher.py` (扩展), `harness/tests/research_integration/test_dag_router.py`
- N4 write_scope = `harness/status-server/research_routes.py`, `harness/status-server/templates/research.html`, `harness/tests/research_integration/test_status_ui.py`
- N5 write_scope = `harness/lib/dispatch_prompt_injector.py`, `harness/coordinator.sh` (加 hook), `harness/tests/research_integration/test_prompt_injector.py`
- N6 write_scope = `harness/sprints/*s04-orchestration-ui.handoff.md`, `harness/sprints/epic-*.traceability.json`

⚠️ N1 触碰 `solar-harness.sh`，N5 触碰 `coordinator.sh`，N3 触碰 `graph_node_dispatcher.py`。这三个文件是 Harness 关键路径，必须**只加不改**（append-only / hook-based），避免破坏现有 sprint。

## 9. Model Routing

- 所有节点 `sonnet`（GLM 1210 风险 + 控制面文件不能错）。
- 禁止 worker webfetch / web search。

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------|
| N1 改 solar-harness.sh 破坏现有路由 | N1 用独立 case 分支 `research)` 路由到 cli.py，不动其他 case；evaluator 跑 `solar-harness doctor` |
| N3 改 graph_node_dispatcher 影响其他 sprint dispatch | N3 用插件模式（独立 `graph_scheduler_research.py`），dispatcher 只加一个 if 分支 |
| N5 改 coordinator.sh 破坏 wake/handoff | N5 用 hook 文件（`~/.solar/hooks/research_dispatch_inject.sh`），coordinator 主循环不变 |
| capability plane 注册名冲突 | N2 用 `research.` 前缀强制命名空间隔离 |
| Status UI 端口冲突（8765 已被占） | N4 复用现有 status-server，不新开端口 |
| 集成测试用 mock 而非真模块 | Stop Rule + evaluator grep `@mock.patch` 命中数 |
| dag-template.json 加载失败 | N3 必须含 fallback：加载失败时显示明确 error 而非静默忽略 |

## 11. Knowledge Context Usage

- `solar-harness context inject` 已执行（命中 Solar 架构方法论；mirage_path: no_results）。
- 复用现有 hooks 模式（`~/.claude/hooks/`、`~/.solar/hooks/`），N5 dispatch injector 走同一套模式。
- S03 deliverable (CLI + module) 是本切片唯一实现来源。

## 12. Handoff Plan

N6 完成后，handoff 必须包含：

- 5 个集成点清单 (CLI / capability / DAG / UI / dispatch injector)
- 给 S05 evaluator 的「集成测试入口」清单：
  - `solar-harness research --help` 应列 11 个
  - `solar-harness capability-list` 应含 6 个 research.*
  - `solar-harness graph-scheduler validate --graph <dag-template>` exit 0
  - curl localhost:8765/research/<sid> 返回 JSON
  - 一份 research 节点的 dispatch.md 检查规则注入
- 已知未闭环项（活体 connector、ReportAST 编译器、性能基线）
- `evaluator_can_review: true` + `s05_can_start: true`

## 13. 当前状态说明

本切片当前 `status=queued, phase=epic_waiting_dependency`（被 S02 通过 epic DAG 阻断；codex 之前已 restore dependency gate）。spec 提前就绪，**status 保持不变**，等 S02 passed 后 coordinator 自然激活。

注意：S04 依赖 S02 (per epic.task_graph.json)，但实际需要 S03 的实现产物 — 因此 builder dispatch 时间应在 S02+S03 都 passed 之后。task_graph.json 的 `prerequisites` 字段会双重保险。
