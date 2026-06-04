# PRD: Requirement Compiler Backend Foundation

Sprint: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`
Owner: `PM pane / Codex`
Priority: `P0`
Lane: `strategy`
Handoff To: `planner`
Created: `2026-05-24T02:56:00Z`
Updated: `2026-05-24T03:20:00Z`

## 0. 执行摘要

本轮不重写 `solar-harness`，而是在现有 `codex_pm_router + product-brief + task-graph + research/evidence` 基础上，把 PM pane 从“需求分类器 + 模板生成器”升级为 **Requirement Compiler**。

核心链路：

```text
原始需求 / 论文 / issue
  -> Intake Router
  -> RequirementIR
  -> PRD View + Contract Set + TaskDAG + Handoff
  -> solar-harness planner
  -> builder / evaluator / research pipeline
```

P0 坚持 **后端编译底座优先**。UI 只做最小只读呈现，不做完整四区 PM pane、DAG 拖拽编辑器或 trace/eval dashboard。

## 1. Problem

当前系统已经有：

- `codex_pm_router`：能做三类需求分类和 skeleton 输出
- `product-brief`：能承接 planner 输入
- `task_graph`：已有执行图基础
- `research/evidence`：已有研究证据 ledger 基础

但还缺一个正式的 **需求编译层**，导致：

1. PRD、contract、task graph、handoff 可能各自生成，容易漂移。
2. planner / builder / evaluator 对同一需求的理解不一定一致。
3. research 请求和普通实现请求的证据门槛不一致。
4. 派单链路容易从 raw request 直接进入 builder，缺少 contract gate。
5. PM pane 更像文档面板，而不是研发控制面。

P0 要解决的不是“写更漂亮的 PRD”，而是让需求进入工程链路前先完成：

```text
Normalize -> Contractualize -> Graph -> Validate -> Dispatch
```

## 2. Goals / Non-goals

### Goals

1. 新增 `RequirementIR v1`，作为需求编译层唯一事实源。
2. 把 `codex_pm_router` 升级为 `Requirement Compiler entrypoint`。
3. 产出三类需求的 PRD object：
   - `implementation` -> Micro-PRD
   - `full_prd` -> Full PRD
   - `research` -> Research PRD
4. 产出四类 contract：
   - `product.yaml`
   - `interface.yaml`
   - `agent_execution.yaml`
   - `research.yaml`
5. 产出可执行 `task_dag.json`，并增加编译期 validator。
6. 产出 Codex / solar-harness handoff。
7. 在 `pm-dispatch` 或 sprint 创建入口前插入 compiler。
8. PM pane P0 只读展示 request type、confidence、open questions、PRD、contract、DAG、handoff。
9. 建立 golden evals，覆盖三类需求和混合需求。

### Non-goals

- 不重写整套 `solar-harness`。
- 不替换现有 `PlanIR` / `task-graph.schema.json`。
- 不做完整四区 PM pane 交互重构。
- 不做 DAG 拖拽编辑器。
- 不做高级 critical path 前端交互。
- 不做 trace/eval dashboard 全量前端化。
- 不让 builder 直接消费 raw request。
- 不把 Markdown 当 canonical data store。

## 3. P0 决策表

| 维度 | 决策 | P0 处理 |
|---|---|---|
| 产品定位 | PM pane = Requirement Compiler | 固化 |
| 当前 router | 继续复用 `codex_pm_router` | 增量升级，不另起一套 |
| 编译事实源 | `RequirementIR` 是需求事实源 | 新增 schema + validator |
| 执行约束事实源 | `.pm/contracts/*.yaml` 是 contract 事实源 | 新增 contract set |
| 聚合文件 | `Contracts.yaml` 是 manifest/aggregation，不是第五种 contract | 新增 |
| 执行图 | `task_dag.json` 是编译后的 executable graph | 保留现有 schema，扩展约束 |
| 运行态 | 运行状态不写回 DAG spec | 新增 `task_dag.state.json` 或 run record |
| Markdown | `prd.md` / `.contract.md` 是 compiled human view | 兼容保留 |
| 派单 | raw request 禁止直接派 builder | 必须先过 compiler + planner |
| UI | P0 只读显示 | 不做复杂交互 |

## 4. Source-of-Truth 模型

P0 采用分层真值：

```text
RequirementIR
  = 需求事实源，记录用户意图、约束、假设、证据引用、验收意图

Contract Set
  = 执行约束事实源，记录产品、接口、agent、安全、研究门槛

TaskDAG
  = 编译后的执行图 spec，可由 IR + contracts 再生成

Markdown Views
  = 人读视图，只能由 IR / contracts / DAG 编译生成

Run State
  = 执行态，不污染 IR / DAG spec
```

### 文件职责

```text
.pm/
  intake.json
  requirement_ir.json
  compiled_artifacts.manifest.json
  prd.md
  Contracts.yaml
  contracts/
    product.yaml
    interface.yaml
    agent_execution.yaml
    research.yaml
  task_dag.json
  task_dag.state.json
  handoff/
    codex_handoff.md
    solar_harness_handoff.md
  evals/
    golden_cases.jsonl
```

### 修改权限

| 文件 | 是否可人工改 | 修改后动作 |
|---|---:|---|
| `intake.json` | 否 | 重新 intake |
| `requirement_ir.json` | 谨慎可改 | 必须重新编译全部 artifacts |
| `.pm/contracts/*.yaml` | 可改 | 必须记录 override metadata，重新验证 |
| `Contracts.yaml` | 不建议手改 | 由 contract compiler 生成 |
| `prd.md` | 不建议手改 | 由 PRD compiler 生成 |
| `task_dag.json` | 谨慎可改 | 必须通过 DAG validator |
| `task_dag.state.json` | 可由执行器写 | 不触发重新编译 |
| `handoff/*.md` | 不建议手改 | 由 handoff compiler 生成 |

## 5. RequirementIR v1

`RequirementIR` 只放 **需求事实**，不放大型 derived view。PRD、contracts、DAG、handoff 通过 `artifact_refs` 引用。

建议 schema：

```yaml
schema_version: solar.requirement_ir.v1
id: req-2026-...
created_at: ...
updated_at: ...

request:
  raw_text: ...
  source_type: chat | issue | paper_batch | mixed
  attachments: []

classification:
  primary_type: implementation | full_prd | research
  secondary_types: []
  confidence: 0.0
  routing_reason: ...
  template_variant: micro | full | research
  mixed_request_policy: split | sequence | block_for_clarification

normalized:
  goal: ...
  problem: ...
  user_value: ...
  scope:
    in: []
    out: []
  assumptions: []
  open_questions: []
  constraints:
    product: []
    technical: []
    security: []
    repo: []
  risks: []

acceptance:
  criteria: []

evidence:
  required: false
  policy_ref: .pm/contracts/research.yaml
  sources: []
  claims: []
  ledger_ref: null

dispatch_policy:
  allowed_targets:
    - planner
    - evaluator
    - research_pipeline
  forbidden_targets:
    - builder_direct

artifact_refs:
  prd: .pm/prd.md
  contracts_manifest: .pm/Contracts.yaml
  task_dag: .pm/task_dag.json
  codex_handoff: .pm/handoff/codex_handoff.md
  solar_harness_handoff: .pm/handoff/solar_harness_handoff.md
```

关键约束：

- `classification.primary_type` 必填
- `acceptance.criteria` 至少 1 条
- `research` 类型必须 `evidence.required = true`
- `dispatch_policy.forbidden_targets` 必须包含 `builder_direct`
- `artifact_refs` 只引用产物，不内嵌产物全文

## 6. 三类需求编译 pipeline

### implementation：Fast Lane

适用：

```text
修 bug、加小功能、改页面、跑命令、调配置
```

产物：

```text
Micro-PRD
Product contract
Agent execution contract
Short TaskDAG
Codex/Solar handoff
```

默认 DAG：

```text
I1 Inspect context
 -> I2 Implement minimal change
 -> I3 Run validation
 -> I4 Summarize diff + residual risks
```

### full_prd：Spec Lane

适用：

```text
长篇系统需求、跨模块改造、产品功能设计、需要架构/交互/上线计划的需求
```

产物：

```text
Full PRD
Product contract
Interface contract
Agent execution contract
Standard TaskDAG
Handoff package
```

### research：Research-to-Build Lane

适用：

```text
论文、benchmark、算法方案、系统研究问题，希望分析如何落地到 Codex 或 solar-harness
```

产物：

```text
Research PRD
Research contract
Evidence map
Experiment plan
Research TaskDAG
Adoption / rejection criteria
```

研究请求如果混入“立刻修 bug”，不得简单判为纯 research；必须走：

- `split`
- `sequence`
- `block_for_clarification`

## 7. Contract 体系

Canonical files：

```text
.pm/contracts/
  product.yaml
  interface.yaml
  agent_execution.yaml
  research.yaml
```

`Contracts.yaml` 不做第五份 contract，而是 manifest：

```yaml
schema_version: solar.contracts_manifest.v1
requirement_ir_ref: .pm/requirement_ir.json
generated_at: ...
contracts:
  product:
    path: .pm/contracts/product.yaml
    version: 1
    digest: sha256:...
  interface:
    path: .pm/contracts/interface.yaml
    version: 1
    digest: sha256:...
  agent_execution:
    path: .pm/contracts/agent_execution.yaml
    version: 1
    digest: sha256:...
  research:
    path: .pm/contracts/research.yaml
    version: 1
    digest: sha256:...
```

硬规则：

- YAML contract files 才是 canonical
- `Contracts.yaml` 只做路径、版本、digest 聚合
- `.contract.md` 是 compiled human-readable view
- planner / builder / evaluator 读取顺序：contract YAML → manifest → markdown fallback

## 8. TaskDAG 编译与优化

新增或强化的编译期 validator：

1. DAG 无环
2. 每条 acceptance 至少映射一个 validation step
3. 高风险节点必须有 approval gate
4. `research` DAG 必须有 evidence/review gate
5. `interface` / `contract` 节点必须先于 implementation 节点
6. `dispatch` 节点不能直接指向 builder
7. 所有输出 artifact 必须能追溯到 `RequirementIR` 或 contract
8. `task_dag.json` 不允许写运行态状态
9. `task_dag.state.json` 不允许改变 DAG 拓扑
10. mixed request 必须显式 split / sequence / block

排序优先级：

```text
Correctness
  -> Acceptance coverage
  -> Risk front-loading
  -> Contract before implementation
  -> Parallelism where safe
  -> Shorter wall-clock time
```

## 9. solar-harness 派单链路

P0 后链路：

```text
User Input
  -> Requirement Compiler
  -> .pm/requirement_ir.json
  -> .pm/contracts/*.yaml
  -> .pm/task_dag.json
  -> compiled sprint package
  -> product-brief
  -> planner
  -> design.md / plan.md / task_graph.json
  -> builder / evaluator
```

集成点：

```text
compile_requirement()
validate_requirement_ir()
compile_contracts()
compile_task_dag()
validate_dispatch_package()
emit_legacy_sprint_package()
dispatch_to_planner()
```

### product-brief 必须增补

- `requirement_ir_ref`
- `contracts_manifest_ref`
- `task_dag_ref`
- `request_type`
- `template_variant`
- `pm_intake_ref`
- `dispatch_policy.target = planner`
- `dispatch_policy.forbid_builder_direct = true`

## 10. Codex 对接策略

P0 使用四层对接：

1. `AGENTS.md`
2. `Skills`
3. `Structured Outputs`
4. `Sandbox / approvals`

要求：

- 所有机器产物都走 schema-valid 输出
- `agent_execution.yaml` 映射到 allowed_paths / forbidden_paths / approvals / stop_conditions
- 不允许仅凭 raw request 执行 Codex 任务

## 11. PM pane P0 UI

P0 UI 只做最小闭环：

```text
┌─────────────────────────────────────────────┐
│ Request Type / Confidence / Blocking Issues │
├─────────────────────────────────────────────┤
│ PRD View                                    │
├─────────────────────────────────────────────┤
│ Contracts View                              │
├─────────────────────────────────────────────┤
│ TaskDAG View                                │
├─────────────────────────────────────────────┤
│ Handoff Bar                                 │
│ [Send to Codex] [Send to solar-harness]     │
└─────────────────────────────────────────────┘
```

P0 必须显示：

- `request_type`
- `confidence`
- `open_questions`
- blocking status
- PRD readonly
- contracts readonly
- DAG readonly
- handoff readonly
- dispatch target

## 12. Sprint 切片

```text
N0 Baseline inventory
N1 RequirementIR schema + validator
N2 Upgrade codex_pm_router -> Requirement Compiler entrypoint
N3 PRD + Contract compilers
N4 TaskDAG compiler + validators
N5 Dispatch integration
N6 Minimal PM pane readonly UI
N7 Golden evals + docs
```

## 13. Acceptance Criteria

### 编译验收

- implementation 请求生成 Micro-PRD、product + agent_execution contracts、3-5 节点 DAG
- full_prd 请求生成 Full PRD、product + interface + agent_execution contracts、标准 DAG
- research 请求生成 Research PRD、research contract、evidence policy、research DAG
- mixed request 不能误判成纯 research，必须输出 split / sequence / block

### Artifact 验收

- `.pm/requirement_ir.json` schema valid
- `.pm/contracts/*.yaml` schema valid
- `.pm/Contracts.yaml` digest 与 contract files 一致
- `.pm/prd.md` 可由 IR/contract 编译生成
- `.pm/task_dag.json` 无环
- `.pm/task_dag.json` 不包含运行态字段
- `.pm/task_dag.state.json` 不改变 DAG 拓扑
- 每条 AC 有 validation coverage
- research DAG 必须存在 evidence/review gate

### Dispatch 验收

- 缺 IR 时，dispatch 阻断
- 缺 contract 时，dispatch 阻断
- research 缺 evidence policy 时，dispatch 阻断
- product-brief 中必须包含 `requirement_ir_ref`
- planner 不需要重新猜分类
- raw request 不允许直接进入 builder

## 14. 测试计划

P0 golden cases 最少准备：

```text
20 条 implementation
10 条 full_prd
10 条 research
10 条 mixed requests
```

测试覆盖：

- `classify_request()`
- `build_requirement_ir()`
- `compile_prd()`
- `compile_contracts()`
- `compile_task_dag()`
- `validate_acceptance_coverage()`
- `validate_dispatch_package()`

## 15. 风险与缓解

| 风险 | 严重度 | 缓解 |
|---|---:|---|
| IR 太大，变成第二套数据库 | 高 | IR 只放需求事实，derived artifacts 走 refs |
| contract 与 IR 漂移 | 高 | digest + manifest + recompile checks |
| DAG 混入运行态 | 中 | `task_dag.json` 与 `task_dag.state.json` 分离 |
| router 误判 mixed request | 高 | `primary_type + secondary_types + mixed_policy` |
| planner 重复猜分类 | 中 | product-brief 强制带 `request_type` 和 IR ref |
| builder 绕过 planner | 高 | dispatch validator 禁止 raw -> builder |
| research 变成“总结论文” | 高 | research contract 强制 evidence + experiment + threshold |
| UI 范围膨胀 | 中 | P0 只读，编辑器进 P1 |
| legacy sprint 断链 | 高 | 继续输出 legacy sprint package |

## 16. Rollout

### Phase 0：Shadow compile

- 用户仍走旧链路
- 新 compiler 在旁路生成 `.pm/` package
- 比较旧产物和新产物差异

### Phase 1：Soft gate

- 新链路生成 product-brief
- 缺 IR / contract 时 warning
- research 缺 evidence 时 warning

### Phase 2：Hard gate

- 缺 IR / contract 直接阻断
- research 缺 evidence policy 直接阻断
- raw request -> builder 禁止

## 17. Planner Handoff

Planner 必须在 `design.md / plan.md / task_graph.json` 中显式回答：

1. Source-of-truth layering 如何落地，避免 IR / contract / DAG / markdown 漂移
2. `Contracts.yaml` 如何严格作为 manifest，而不是第五份 contract
3. mixed request `split / sequence / block` 的编译与派单规则
4. `task_dag.json` 与 `task_dag.state.json` 的边界
5. `product-brief` / `pm-dispatch` / legacy package 的兼容策略
6. N0..N7 切片如何分工与并行
7. golden evals 与 regression suite 如何独立成为 N7，不与 UI 节点混合

## 18. Final Naming

本 sprint 正式名称采用：

```text
Requirement Compiler Backend Foundation
```

而不是 “PM pane UI upgrade”。
