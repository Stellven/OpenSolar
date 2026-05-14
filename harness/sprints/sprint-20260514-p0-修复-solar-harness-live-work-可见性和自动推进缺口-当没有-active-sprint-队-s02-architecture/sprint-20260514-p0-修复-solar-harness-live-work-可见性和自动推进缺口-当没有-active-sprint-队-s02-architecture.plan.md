# Plan — Solar-Harness Live-Work Visibility · S02 Architecture

Sprint: `sprint-20260514-p0-…-s02-architecture`
Slice: `architecture`
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. DAG

```text
N1 architecture.md  ─┐
N2 interfaces.md     ─┤
N3 data-model.md     ─┼── N5 integration+handoff ── done
N4 migration.md      ─┘
```

5 节点；4 并行上游 + 1 join。Cost = M+M+M+M+S = 约 5 单位。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Model | Cost | Gate |
|------|------|---------|-------|------|------|
| **N1** | 写 architecture.md：4 层分层图 + 5 outcome 落到各层 + 状态机（intake → PM → planner → builder → eval）+ 失败恢复矩阵 + 观测点 | — | sonnet | 1.0 | architecture-md-pass |
| **N2** | 写 interfaces.md：5 个 API 契约（idle-state / heartbeat / deadlock / PRD-intake / role-next-step），每个含 method/path/request/response/error-codes | — | sonnet | 1.0 | interfaces-md-pass |
| **N3** | 写 data-model.md：4 schema（status.json 扩展 / events.jsonl 新事件 / requirement_intake.json / role_resolver_view），每个含字段名/类型/必填/约束/schema_version | — | sonnet | 1.0 | data-model-md-pass |
| **N4** | 写 migration.md：4 兼容点（coordinator/status-server/intent-engine/autopilot 主循环）+ ≥ 3 降级策略 + 冲突清单 | — | sonnet | 1.0 | migration-md-pass |
| **N5** | 写 handoff.md + patch parent traceability.json（仅添加 children[1].architecture_ready=true） | N1, N2, N3, N4 | sonnet | 1.0 | integration-pass |

Total: 5 units。

## 3. Parallelism

- **N1 ∥ N2 ∥ N3 ∥ N4** 完全并行，write_scope 互斥
- **N5** join N1-N4，单线程写 handoff + traceability patch
- 最大 builder 并发 = 4

## 4. Dispatch Batches

- **batch-1**: `[N1, N2, N3, N4]`，join_gate = `[architecture-md-pass, interfaces-md-pass, data-model-md-pass, migration-md-pass]`
- **batch-2**: `[N5]`，join_gate = `[integration-pass]`

## 5. Per-Node Acceptance

### N1 architecture.md
- 含 4 层分层图（Presentation / Control / State Aggregation / Data）
- 含 5 outcome × 4 层的责任分配表（25 格）
- 含状态机图：requirement-intake → pm-drafting → planner-design → builder-dispatch → evaluator-review → passed/failed
- 含失败恢复矩阵：每个状态转移的失败转移（≥ 5 条）
- 含观测点清单：≥ 6 个 metric 名 + 含义
- `grep -c '^### ' architecture.md` ≥ 10
- 不出现 .py/.ts/.js 代码块

### N2 interfaces.md
- 含 5 个 `## API:` 块，每个含 method / path / request 字段 / response 字段 / error-codes (≥ 3 个错误码)
- API 名对应 5 outcome：(a) GET /api/idle-state；(b) autopilot 内部 heartbeat（schema only）；(c) deadlock event schema；(d) POST /api/requirements；(e) GET /api/roles/<sid>/next-step
- 每个 API 至少列 3 个 error-codes
- `grep -c '^## API' interfaces.md` ≥ 5
- `grep -c 'error_code' interfaces.md` ≥ 15
- 不出现实现细节代码

### N3 data-model.md
- 含 4 schema：(a) status.json 扩展（idle 字段 + role_next_step 字段）；(b) events.jsonl 新事件类型（heartbeat / deadlock_detected / requirement_intake / pm_drafted / role_transition）；(c) requirement_intake.json；(d) role_resolver_view（derived from events）
- 每 schema 含 schema_version 字段
- 每字段含 name / type / required / constraint
- `grep -c 'schema_version' data-model.md` ≥ 4
- 不出现实现细节代码

### N4 migration.md
- 含 4 兼容点（coordinator.sh / status-server / intent-engine / autopilot 主循环）
- 每兼容点写明：要不要改主循环 / 用 hook 还是 case 追加 / 影响范围
- 含 ≥ 3 降级策略（idle-state 读失败、PRD-intake 接口未就绪、deadlock 误报）
- 含 ≥ 5 行冲突清单（与现有 state / event / status 字段冲突的字段名）
- 明确禁止"重写 coordinator.sh 主循环"
- 不出现实现细节代码

### N5 integration + handoff
- handoff.md 含：
  - 5 outcome × (control / state / data / presentation) 落点矩阵
  - S03 builder 切入清单（每 outcome 一行：文件 + 函数签名 + 依赖 schema）
  - S04 builder 切入清单
  - 已知未闭环项
  - `s03_can_start: true` + `s04_blocked_until: s03_passed`
- parent `epic-…traceability.json` 仅添加 children[1].architecture_ready = true
- `jq '.children[1].architecture_ready' epic-*.traceability.json` == true
- schema_version 不变；children 顺序不变

## 6. Routing Policy

- 所有节点 `sonnet`（架构设计严谨性）
- 禁止 worker webfetch / web search
- 上游唯一需求源：S01 `…s01-requirements.outcomes.md`
- 测试 fixture：无（本切片纯文档）

## 7. Stop Rules（执行期）

- 任何节点写 `.py/.ts/.js/.sh/.sql` 文件 → fail
- 接口契约缺 error-codes 字段 → fail
- 状态机缺失败转移 → fail
- data-model 字段缺 schema_version → fail
- migration 提议重写主循环 → fail
- N5 在 N1-N4 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "epic 已完成" 或 "S03-S05 已就绪" → fail

## 8. Exit Criteria

- 5 节点全 passed
- 4 个 .md 文件齐全，每个 acceptance 全过
- parent traceability.json children[1].architecture_ready = true
- schema_version + children 顺序保留
- handoff `s03_can_start: true` + `s04_blocked_until: s03_passed`
- 不出现新代码文件

## 9. Evaluator 复核入口

1. `ls sprints/*s02-architecture.{architecture,interfaces,data-model,migration,handoff}.md` 5 个文件全在
2. `grep -c '^## API' sprints/*s02-architecture.interfaces.md` ≥ 5
3. `grep -c 'error_code' sprints/*s02-architecture.interfaces.md` ≥ 15
4. `grep -c 'schema_version' sprints/*s02-architecture.data-model.md` ≥ 4
5. `grep -c '禁止' sprints/*s02-architecture.migration.md` ≥ 1
6. `jq '.children[1].architecture_ready' epic-*.traceability.json` == true
7. `find sprints/*s02-architecture* -name '*.py' -o -name '*.ts' -o -name '*.sh'` 空
8. `grep -c 's03_can_start: true' sprints/*s02-architecture.handoff.md` == 1

## 10. Out of Scope

- **S03**: 把 schema / interfaces 实现成 .py 模块；构建状态机；写单测
- **S04**: 把 idle-state / heartbeat / deadlock / role-next-step 接入 autopilot 和 status UI
- **S05**: 端到端测试 + 负控 + activation-proof + 文档

## 11. 当前状态说明

本切片 status = `drafting/prd_ready`（PRD 已就绪，等 planner 三件套）；目标 status = `active/planning_complete`，handoff_to=`builder_parallel`，让 graph_scheduler 自动并行派发 N1/N2/N3/N4 给 sonnet builder。

S01 已全 passed（N1/N2/N3 都 eval_passed），upstream 不阻塞。
