# Plan — Solar-Harness Live-Work Visibility · S01 Requirements

Sprint: `sprint-20260514-p0-…-s01-requirements`
Slice: `requirements`
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. DAG

```text
N1 outcome-decomposition  ─┐
N2 non-builder-boundary    ─┴── N3 traceability+handoff ── done
```

3 节点；N1/N2 并行；N3 join。Cost = S+S+S = 约 3 单位。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Model | Cost | Gate |
|------|------|---------|-------|------|------|
| **N1** | 写 5 个 outcome card（O1-O5）到 `…s01-requirements.outcomes.md`，每张含 acceptance / risk / boundary / dependency / 负责 child sprint | — | sonnet | 1.0 | outcomes-pass |
| **N2** | 写 `…s01-requirements.non-builder-boundary.md`：governance 边界表（≥ 5 行，每行带反例） + 禁止 builder 直接接的工作清单 | — | sonnet | 1.0 | boundary-pass |
| **N3** | 写 `…s01-requirements.handoff.md`，更新 parent `…traceability.json`（children[*].outcomes 字段） | N1, N2 | sonnet | 1.0 | integration-pass |

Total: 3 units。

## 3. Parallelism

- **N1 ∥ N2** 完全并行，write_scope 互斥。
- **N3** join N1+N2 后启动；写父 traceability 单线程。
- 最大 builder 并发 = 2。

## 4. Dispatch Batches

- **batch-1**: `[N1, N2]`，join_gate = `[outcomes-pass, boundary-pass]`
- **batch-2**: `[N3]`，join_gate = `[integration-pass]`

## 5. Per-Node Acceptance

### N1 outcome-decomposition
- 文件 `…s01-requirements.outcomes.md` 含 5 个 outcome（O1-O5），覆盖：
  - O1 status 页面 no-active-work 显式声明
  - O2 autopilot 队列空 + pane idle 心跳与提示
  - O3 用户提交需求自动 PM-first PRD 流程
  - O4 status UI 显示每角色下一步责任人 + 阻塞原因
  - O5 sprint 状态转换必须有可见证据
- 每个 outcome card 必含 5 个字段：`Acceptance` / `Risk` / `Boundary` / `Dependency` / `Owner-Sprint`
- 每个 outcome 含"用户看到什么"和"如何观察"两栏
- grep 字段数 ≥ 25 (5 outcome × 5 字段)
- 不出现实现细节代码（无 .py/.ts 片段）

### N2 non-builder-boundary
- 文件 `…s01-requirements.non-builder-boundary.md` 含 governance 表（≥ 5 类 work）
- 每行必含：work 类型 / ✅ 或 ❌ builder direct / 必须先经过谁 / 具体反例
- 至少 4 行标 ❌（不允许 builder 直接接）
- 每行反例为具体场景描述（"如果 builder 接了 X 会怎样"）
- 不出现实现细节代码

### N3 traceability + handoff
- 文件 `…s01-requirements.handoff.md` 含：
  - 5 outcome → child sprint 矩阵
  - S02 evaluator 入口清单（如何复核 N1/N2 的 AC）
  - builder-direct vs planner-required 摘要
  - 已知未闭环项
  - `evaluator_can_review: true` + `s02_can_start: true`
- 更新 parent `epic-…traceability.json`：
  - children[*] 加上 `outcomes: [...]` 字段（反向链接）
  - 保留原 `schema_version` 和 `children` 顺序
  - `jq '.children[0].outcomes | length' ≥ 1`
- 不破坏 epic decomposer 兼容性

## 6. Routing Policy

- 所有节点 `sonnet`（GLM 1210 风险）
- 禁止 worker webfetch / web search
- 测试 fixture：无（本切片纯文档，无代码测试）

## 7. Stop Rules（执行期）

- 任何节点写 `.py/.ts/.js/.sh/.sql` 文件 → fail（planner 不写代码）
- N3 在 N1 或 N2 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "epic 已完成" 或 "S02-S05 已就绪" → fail
- traceability.json 更新破坏 `schema_version` → fail
- outcome card 缺任一必填字段 → fail
- non-builder-boundary 表少于 5 行 → fail

## 8. Exit Criteria

- 3 节点全 passed: outcomes-pass / boundary-pass / integration-pass
- 5 outcome 全字段齐全
- non-builder-boundary 表 ≥ 5 行，≥ 4 行 ❌
- parent traceability.json 含 children[*].outcomes 反向链接
- handoff `evaluator_can_review: true` + `s02_can_start: true`
- 不出现新代码文件

## 9. Evaluator 复核入口

1. `grep -c '^### O[1-5]' …s01-requirements.outcomes.md` == 5
2. `grep -cE '^- \*\*(Acceptance|Risk|Boundary|Dependency|Owner-Sprint)\*\*' …s01-requirements.outcomes.md` ≥ 25
3. `grep -c '❌' …s01-requirements.non-builder-boundary.md` ≥ 4
4. `jq '.children[0].outcomes | length' epic-*.traceability.json` ≥ 1
5. `grep -c 'evaluator_can_review: true' …s01-requirements.handoff.md` == 1
6. `grep -c 's02_can_start: true' …s01-requirements.handoff.md` == 1
7. `find sprints/*s01-requirements* -name '*.py' -o -name '*.ts' -o -name '*.sh'` 空
8. `grep -c 'epic 已完成\|all done\|S0[2-5] passed' …s01-requirements.handoff.md` == 0

## 10. Out of Scope

- **S02**: 接口契约 + 架构 + control/data plane 设计
- **S03**: lib/types/schemas 实现 + 状态机 + 持久化
- **S04**: autopilot 集成 + status UI + pane 可视化
- **S05**: 端到端测试 + 负控 + activation-proof + 文档

## 11. 当前状态说明

本切片 status = `drafting/spec`（PRD 已就绪，等 planner 产出 design+plan+task_graph）；目标 status = `active/planning_complete`，handoff_to=`builder_parallel`，让 graph_scheduler 自动并行派发 N1/N2 给 sonnet builder。
