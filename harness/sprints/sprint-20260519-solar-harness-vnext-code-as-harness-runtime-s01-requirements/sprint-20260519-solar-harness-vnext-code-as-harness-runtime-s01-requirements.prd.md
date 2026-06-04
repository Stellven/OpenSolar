# PRD: 需求拆解与追踪矩阵

epic_id: `epic-20260519-solar-harness-vnext-code-as-harness-runtime`
sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements`
slice: `requirements`

## 用户原始需求

# Solar-Harness vNext: Code-as-Harness Runtime

## 0. User Intent

把 Solar-Harness 从“更强的多 pane 调度器”升级为 **Code-as-Harness Runtime**：代码、测试、临时工具、证据、状态、回滚、评审都必须成为可执行、可审计、可复用的 harness substrate。

这不是重写 Solar，而是在现有 sprint contract、DAG scheduler、capability inference、architecture guard、DeepResearch evidence gate 的基础上，补上强约束执行内核。

## 1. Product Thesis

Solar-Harness 的下一跳不是更多 agent、更多 prompt、更多 pane、更多工具接入，而是：

- 更硬的 contract。
- 更强的 execution broker。
- 更完整的 event ledger。
- 更细的 artifact lifecycle。
- 更可靠的 verifier。
- 更可控的 repair loop。

一句话定调：

> Solar-Harness 要从 agent 工作流调度器升级为代码作为运行介质的 AI-native 执行内核。

## 2. Current System Assessment

### Existing Strengths

1. **DAG 调度骨架已经正确。**
   `graph_scheduler.py` 已经具备 invalid DAG fail-fast、依赖通过后才 ready、write_scope 冲突禁止同批并行、缺 write_scope 默认独占、parent sprint gate 等安全约束。

2. **能力选择已经开始机器化。**
   `capability_inference.py` 能从 node goal、acceptance、read/write scope、skills、handoff 推导 `required_capabilities`，补 planner 漏掉的能力。

3. **package-first 架构守卫已经存在。**
   `architecture_guard.py` 能把“新能力做成 package/plugin/skill/connector，不乱改主 harness”变成可检查规则。

4. **DeepResearch 已有硬门禁基础。**
   `research/evaluator.py` 已经有 model-free gate，检查 evidence、citation、source diversity、authority、section coverage、expert synthesis 等指标。

### Core Gap

Solar 已有 harness 骨架，但还没有完全内核化 “Code as Agent Harness”：

- node contract 还不够细，缺 action-level contract。
- GEMS/能力系统更多是 advisory，还不是 enforcement broker。
- 验证偏 closeout prompt policy，没有前移到每个 action。
- DeepResearch 有 evidence ledger，但还缺 ResearchGraph compiler。
- 多 pane 协同已有 lease，但缺 state revision、artifact ownership、merge policy。

## 3. Target Architecture

```text
Sprint Contract
  -> Plan IR
    -> Node Contract
      -> Action Contract
        -> Execution Broker
          -> Execution Event
            -> Artifact Registry
              -> Verifier Service
                -> Repair Controller
                  -> Status / Memory / Capability Projections
```

所有 shell、file write、tool call、network、git、research import 都必须被 action contract 管理。没有 contract，不执行；没有 evidence，不 PASS。

## 4. Functional Requirements

### Pkg 1: Plan IR + Action Contract Algebra

新增：

- `harness/schemas/plan_ir.schema.json`
- `harness/schemas/action_contract.schema.json`
- `harness/lib/contracts/plan_ir.py`
- `harness/lib/contracts/action_contract.py`

Action Contract 最小字段：

```json
{
  "action_id": "A1",
  "node_id": "N3",
  "kind": "shell|python|file_write|tool_call|research_extract|human_approval",
  "intent": "run deterministic research evaluator",
  "read_set": ["harness/lib/research/evaluator.py"],
  "write_set": ["harness/sprints/.../research_eval.json"],
  "required_capabilities": ["research.evaluate", "citation.verify"],
  "preconditions": ["task_graph validated", "input artifact exists"],
  "success_predicates": ["exit_code == 0", "verdict == PASS"],
  "verification": {
    "static": true,
    "runtime": ["python3 -m py_compile harness/lib/research/evaluator.py"],
    "evidence": ["research_eval.json"]
  },
  "rollback": {
    "kind": "git_restore",
    "target": ["harness/lib/research/evaluator.py"]
  },
  "risk_class": "medium",
  "approval_required": false
}
```

验收：

- Planner 能产出 Plan IR。
- 每个 executable node 至少有一个 action contract。
- schema validation fail 时不得进入 Builder。

### Pkg 2: GEMS Execution Broker

新增：

- `harness/lib/execution_broker.py`
- `harness/lib/policy/action_policy.py`
- `harness/lib/policy/write_scope_policy.py`
- `harness/lib/policy/approval_policy.py`

执行链路：

```text
propose_action()
  -> validate_contract()
  -> policy_check()
  -> acquire_lease()
  -> execute_in_sandbox()
  -> capture_outputs()
  -> verify_outputs()
  -> append_event()
  -> update_projection()
```

硬规则：

- 无 contract，不执行。
- 无 write_scope，不写入。
- 无 capability，不派发。
- 无 evidence，不 PASS。
- 高风险 action 无 human approval 不运行。
- `apply`、`git commit`、外部网络写操作默认 high risk。

验收：

- `uncontracted action = 0`
- `unscoped write = 0`
- broker event coverage = 100%
- activation-proof 增加 broker coverage。

### Pkg 3: Agent Code Artifact Registry

新增：

- `harness/lib/artifact_registry.py`
- `harness/migrations/002_artifact_registry.sql`

核心表：

```sql
agent_artifacts(
  artifact_id text primary key,
  sprint_id text,
  node_id text,
  action_id text,
  artifact_type text,
  path text,
  content_hash text,
  created_by text,
  created_at text,
  status text,
  promotion_status text,
  verification_status text,
  provenance_json text
);
```

生命周期：

```text
draft -> executed -> verified -> promoted
                      -> deprecated
                      -> rejected
```

验收：

- 每个 generated script/test/research output/patch/skill package 都有 registry record。
- record 包含 hash、provenance、verification status。
- promoted artifact 必须可从 registry 反查来源 action 和 verifier evidence。

### Pkg 4: Governed Event Ledger

新增：

- `harness/lib/event_ledger.py`
- `harness/run/events.jsonl` 或 SQLite `event_log`

事件格式：

```json
{
  "event_id": "evt_...",
  "ts": "2026-05-19T...",
  "sprint_id": "sprint-...",
  "node_id": "N2",
  "action_id": "A7",
  "type": "action.executed",
  "actor": "builder:lab-1",
  "input_hash": "...",
  "output_hash": "...",
  "policy_verdict": "PASS",
  "evidence_refs": ["artifact:research_eval.json"],
  "parent_event_ids": ["evt_..."]
}
```

状态全部从 ledger 投影：

- Sprint Status Projection
- Node Status Projection
- Capability Scorecard Projection
- Artifact Inventory Projection
- Memory Brief Projection
- Failure Taxonomy Projection

验收：

- action execution、policy verdict、verifier verdict、artifact registration 都写 append-only event。
- projection 可重放。
- 旧 status 文件仍兼容，但不能作为唯一事实源。

### Pkg 5: Verifier-as-a-Service

新增：

- `harness/lib/verifiers/static.py`
- `harness/lib/verifiers/runtime.py`
- `harness/lib/verifiers/research.py`
- `harness/lib/verifiers/policy.py`
- `harness/lib/verifiers/regression.py`

统一输出：

```json
{
  "verifier": "research",
  "verdict": "PASS|FAIL|WARN",
  "metrics": {},
  "errors": [],
  "warnings": [],
  "evidence_refs": []
}
```

DeepResearch 需要补：

- `claim_graph_coverage`
- `contradiction_coverage`
- `citation_to_source_span_check`
- `section_to_claim_alignment`
- `expert_insight_novelty`

验收：

- `research/evaluator.py` 被封装为 research verifier。
- `architecture_guard.py` 被封装为 policy verifier。
- node closeout 聚合 verifier verdict，不再只靠 prompt 说明。

### Pkg 6: Repair Controller

新增：

- `harness/lib/repair/failure_taxonomy.py`
- `harness/lib/repair/repair_controller.py`
- `harness/lib/repair/regression_guard.py`

失败类型：

- `PLAN_INVALID`
- `DEPENDENCY_BLOCKED`
- `CAPABILITY_MISMATCH`
- `WRITE_SCOPE_CONFLICT`
- `EXECUTION_FAILED`
- `VERIFICATION_FAILED`
- `EVIDENCE_GAP`
- `REGRESSION_RISK`
- `HUMAN_APPROVAL_REQUIRED`
- `STATE_CONFLICT`

策略：

- `PLAN_INVALID` -> replan affected subgraph only。
- `CAPABILITY_MISMATCH` -> reassign worker / enrich capability。
- `EXECUTION_FAILED` -> minimal patch + rerun exact command。
- `VERIFICATION_FAILED` -> inspect verifier errors, create fix node。
- `EVIDENCE_GAP` -> add source/evidence acquisition node。
- `REGRESSION_RISK` -> block promotion, require reviewer。
- `STATE_CONFLICT` -> merge/rebase state projection。

验收：

- failed node 必须有 failure taxonomy。
- repair action 也必须走 action contract。
- repair 成功率、复发率可统计。

### Pkg 7: Multi-Agent Shared Workspace Protocol

新增机制：

- lease + state revision + artifact ownership + merge policy。

action 执行前必须带：

```json
{
  "state_revision": "rev_123",
  "read_set_hash": "...",
  "write_set": ["..."],
  "artifact_owner": "builder-2",
  "merge_policy": "append_only|exclusive|review_required"
}
```

冲突规则：

- 同一文件写冲突 -> 不能并行。
- 同一 artifact 写冲突 -> owner 优先。
- append-only ledger -> 可并行。
- state projection 过期 -> 重新读取后再执行。

验收：

- 并发冲突自动阻断。
- stale state revision 自动要求 refresh。
- dashboard 可显示 owner / write_set / merge policy。

## 5. DeepResearch Productization Requirements

目标：把 DeepResearch 做成可重放、可审计、可扩展到 100k 字长报告的 ResearchGraph compiler。

Pipeline：

```text
Question Tree Builder
  -> Source Plan Generator
    -> Source Mesh Acquisition
      -> Evidence Extractor
        -> Claim Miner
          -> Claim-Evidence Linker
            -> Contradiction Searcher
              -> Section Compiler
                -> Expert Synthesis
                  -> Long-form Report Compiler
                    -> Research Verifier
```

新增表：

```sql
question_nodes(
  id text primary key,
  run_id text,
  parent_id text,
  question text,
  purpose text,
  status text
);

contradiction_edges(
  id text primary key,
  run_id text,
  claim_a text,
  claim_b text,
  contradiction_type text,
  severity text,
  resolution text
);

section_claims(
  id text primary key,
  run_id text,
  section_id text,
  claim_id text,
  role text,
  required integer
);
```

每章编译输入：

```text
section outline
  + required claims
  + supporting evidence
  + refuting evidence
  + uncertainty notes
  + expert interpretation
  -> section draft
  -> section verifier
```

验收：

- `unsupported_rate <= 5%`
- `citation_accuracy >= 95%`
- `claim coverage >= 90%`
- 每章至少有 evidence + contradiction/uncertainty 处理。
- 100k 字报告可分段重放生成。

## 6. 90-Day Roadmap

### P0: 0-2 Weeks, Execution Chain Hardening

交付：

1. `action_contract.schema.json`
2. `event_ledger.py`
3. `execution_broker.py` 最小版
4. `graph_node_dispatcher` 接入 broker
5. shell/file_write/tool_call 三类 action 先纳管
6. activation-proof 增加 broker coverage

验收：

- uncontracted action = 0
- unscoped write = 0
- broker event coverage = 100%
- smoke-install / py_compile / activation-proof 全通过

### P1: 2-4 Weeks, Artifact + Verifier Foundation

交付：

1. `artifact_registry.py`
2. verifier 接口
3. `research/evaluator.py` 接成 research verifier
4. `architecture_guard.py` 接成 policy verifier
5. `capability_inference` 支持 action-level inference
6. node closeout 必须聚合 verifier verdict

验收：

- 每个 PASS node 都有 verifier evidence。
- 每个 generated artifact 都有 registry record。
- 每个 failed node 都有 failure taxonomy。

### P2: 4-8 Weeks, DeepResearch Compiler

交付：

1. ResearchGraph schema
2. question tree
3. contradiction_edges
4. section_claims
5. long-form report compiler
6. strict technical_architecture profile
7. 100k 字报告分段编译与总体验证

验收：

- unsupported_rate <= 5%
- citation_accuracy >= 95%
- claim coverage >= 90%
- 每章处理 contradiction/uncertainty
- 100k 字报告可重放生成

### P3: 8-12 Weeks, Transactional Multi-Agent + Self-Evolution

交付：

1. state revision protocol
2. artifact ownership
3. repair_controller
4. regression-free improvement gate
5. capability scorecard 自动更新
6. dashboard 显示 action/event/artifact/verifier/failure

验收：

- 并发冲突自动阻断。
- repair 成功率可统计。
- capability ranking 有真实执行数据。
- harness 改动不会降低既有 activation-proof。

## 7. Initial Implementation Task Graph

```json
{
  "nodes": [
    {
      "id": "N1",
      "title": "P0 contract schemas",
      "role": "builder",
      "write_scope": [
        "harness/schemas/plan_ir.schema.json",
        "harness/schemas/action_contract.schema.json",
        "harness/lib/contracts/"
      ],
      "acceptance": [
        "schemas validate good fixtures",
        "schemas reject missing write_scope for write action",
        "py_compile passes"
      ]
    },
    {
      "id": "N2",
      "title": "Append-only event ledger",
      "role": "builder",
      "depends_on": ["N1"],
      "write_scope": [
        "harness/lib/event_ledger.py",
        "harness/tests/test-event-ledger*"
      ],
      "acceptance": [
        "append event writes JSONL atomically",
        "event ids are stable unique",
        "projection replay smoke test passes"
      ]
    },
    {
      "id": "N3",
      "title": "Execution broker MVP",
      "role": "builder",
      "depends_on": ["N1", "N2"],
      "write_scope": [
        "harness/lib/execution_broker.py",
        "harness/lib/policy/",
        "harness/tests/test-execution-broker*"
      ],
      "acceptance": [
        "uncontracted shell action blocked",
        "unscoped file_write blocked",
        "approved low-risk shell action logs event",
        "high-risk apply requires human approval"
      ]
    },
    {
      "id": "N4",
      "title": "graph dispatch broker integration",
      "role": "builder",
      "depends_on": ["N3"],
      "write_scope": [
        "harness/lib/graph_node_dispatcher.py",
        "harness/tests/control_plane/"
      ],
      "acceptance": [
        "existing graph scheduler tests still pass",
        "builder dispatch includes action contracts",
        "activation-proof reports broker coverage"
      ]
    },
    {
      "id": "N5",
      "title": "P0 evaluator closeout",
      "role": "evaluator",
      "depends_on": ["N1", "N2", "N3", "N4"],
      "write_scope": [
        "harness/tests/",
        "harness/reports/"
      ],
      "acceptance": [
        "py_compile passes for changed Python",
        "broker tests pass",
        "graph scheduler tests pass",
        "activation-proof passes",
        "handoff names residual P1/P2 work"
      ]
    }
  ]
}
```

## 8. Non-Goals and Guardrails

- Do not rewrite the entire harness.
- Do not bypass PM/Planner/DAG flow.
- Do not make Meta-Harness auto-apply runtime patches.
- Do not treat prompt instructions as verifier evidence.
- Do not introduce a new monolithic core file.
- Do not break existing four-pane workflow, sprint status files, or graph scheduler behavior.
- Package-first: new mechanisms should land as schemas, packages, adapters, services, and tests.

## 9. Required Output from Solar-Harness

Solar-Harness PM/Planner must produce:

1. PRD with user value, constraints, non-goals, staged rollout.
2. Architecture design for Code-as-Harness Runtime.
3. P0 implementation plan only, not the full 90-day build.
4. task_graph.json with strict write_scope and dependencies.
5. acceptance tests and activation-proof updates.
6. risk register and rollback plan.

Builder must implement only approved P0 slices. Evaluator must reject any solution where shell/file_write/tool_call can bypass action contract and event ledger.

## 本切片目标

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260519-solar-harness-vnext-code-as-harness-runtime.epic.md`、`epic-20260519-solar-harness-vnext-code-as-harness-runtime.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements.design.md`
- `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements.plan.md`
- `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements.task_graph.json`
- `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements.handoff.md`
- `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements.eval.md` 或 `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements.eval.json`
