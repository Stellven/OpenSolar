# Design — S01 需求拆解与追踪矩阵 (Code-as-Harness Runtime)

epic_id: `epic-20260519-solar-harness-vnext-code-as-harness-runtime`
sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements`
slice: `requirements`
author: planner (solar-harness)
date: 2026-05-19
Knowledge Context: solar-harness context inject used

## 1. 切片定位

S01 是 epic 的**起点切片**。**不写运行时代码**，只把 17KB PRD 的"Code-as-Harness Runtime"原始大需求拆为：

1. 可验收的 **Outcomes**（每条带验收点 + 风险 + 下游 owner sprint）
2. **Non-goals**（显式不做）
3. **Traceability matrix**（Epic → Outcome → Sprint Gate）
4. **不能直派 builder 的工作**（必经 architecture 切片或 stop-rule）
5. **Risk register**（含 owner + 缓解）
6. **稳定接口契约骨架**（让 S02 直接接住，避免拆得太散）

PRD 已经画出 7 Pkg + DeepResearch Productization + 4 阶段 90-day Roadmap，但**只允许 S01 拆 P0 (0-2 周)**，P1/P2/P3 必须在 handoff 中列为 follow-up，不在本 epic 一次性吞下。

## 2. Outcomes 拆解（可验收单元）

P0 范围 (0-2 weeks, Execution Chain Hardening) — 必须在本 epic 完成：

| OID | Outcome | 验收点 | 下游 Sprint | 风险 | Est. Hours |
|-----|---------|--------|-------------|------|------------|
| O-01 | PM PRD 文档化 + HTML 渲染 | `prd.md` 存在;`prd.html` 含 §1-§9 全部章节 | S01 | HTML 渲染管线缺失 → pandoc/python-markdown 兜底 | 0.3h |
| O-02 | Planner 输出 design/plan/task_graph + planning.html | 三件套齐;`graph-scheduler validate` exit 0 | S01 | DAG 拆得太碎 → 限制 ≤ 8 节点 | 0.5h |
| O-03 | Plan IR + Action Contract schema | `plan_ir.schema.json` + `action_contract.schema.json` 通过 jsonschema 验证;含 11 个最小字段 (action_id/node_id/kind/intent/read_set/write_set/required_capabilities/preconditions/success_predicates/verification/rollback) | S02 + S03 | 字段过早冻结 → S02 允许扩展但不允许删 | 2.0h |
| O-04 | Append-only Event Ledger | `event_ledger.py` 写 JSONL atomic;`event_id` 稳定唯一;projection replay smoke test pass | S03 | 写竞态 → 必须 fcntl/atomic-write 或 SQLite WAL | 2.0h |
| O-05 | Execution Broker MVP (无 contract 不执行) | `execution_broker.py` 实现 propose→validate→policy→lease→execute→capture→verify→event→projection 完整链;3 类 action (shell/file_write/tool_call) 全纳管 | S03 | uncontracted shell 旁路 → 测试必须覆盖未注册 action 立即 raise | 3.0h |
| O-06 | graph_node_dispatcher 接 broker | builder dispatch 必须包含 action_contracts 字段;原有 graph scheduler tests 仍 pass;activation-proof 输出 broker_coverage 字段 | S04 | 旧 dispatch 路径破坏 → 必须保留 legacy path + 双跑对比 | 1.5h |
| O-07 | Action Contract 3 类硬规则 | 单测覆盖: uncontracted shell 被 block / unscoped file_write 被 block / 低风险 shell 走完整链并写 event / 高 risk apply 需 human approval | S03 | apply/git/network 默认 high risk 误判 → risk_class 表必须有白名单 | 1.5h |
| O-08 | broker event coverage = 100% | activation-proof 报告: `uncontracted_action_count == 0` AND `unscoped_write_count == 0` AND `broker_event_coverage == 1.0` | S04 + S05 | 旧 tool 调用未走 broker → fallback path 必须显式标注 legacy=true | 1.0h |
| O-09 | 兼容性约束 (不破坏现有 four-pane) | 现有 `wake/dispatch/status` smoke test 全 pass;现有 graph_scheduler.py invalid-DAG/write_scope/parent_gate 测试不退化 | S03 + S04 | 兼容层泄漏新接口 → 必须 import-time 不引入 broker 强依赖 | 1.0h |
| O-10 | Risk register + rollback plan | `risk-register.md` 含 ≥ 8 条风险 (含 broker bypass / event 损坏 / contract schema breaking change / capability mismatch / regression / state conflict / approval bottleneck / migration);每条有 owner + 缓解 + 回滚动作 | S01 | 遗漏 rollback → S02 architecture 必须读此文件 | 0.7h |
| O-11 | 中文证据表 handoff | `handoff.md` 含表 7 列:Outcome / 验收点 / 下游 Sprint / 命令 / 结果 / 降级原因 / 未闭环 | S01 | 占位符未替换 → 每行必须有真实截断 | 0.5h |
| O-12 | Traceability map (Epic → Outcome → Gate) | `epic-*.traceability.json` children[*] 新增 `outcomes` 数组;每个 outcome 至少属于一个 child sprint | S01 | json schema 不匹配 → 用 python json.load 验合法性 | 0.4h |
| O-13 | Non-goals 固化 | `non-goals.md` 列出 8 条不做项 (不重写 harness / 不绕过 PM-Planner-DAG / 不让 Meta-Harness auto-apply runtime patch / 不把 prompt 当 verifier evidence / 不引入 monolith / 不破坏 four-pane / 不强依赖 Linear / package-first) | S01 | 模糊表述 → 每条必须有反例 | 0.4h |
| O-14 | "不能直派 builder" 工作清单 | `cannot-dispatch-to-builder.md` 列出 ≥ 6 类需先经 architect / human approval / stop-rule 的工作 | S01 | 漏列 → S02 必须读此文件 | 0.4h |

P1/P2/P3 范围 (本 epic 不交付，作为 follow-up):

| OID | Outcome | 状态 | 备注 |
|-----|---------|------|------|
| F-P1-01 | Artifact Registry (`agent_artifacts` 表 + lifecycle) | follow-up | 2-4 周 P1 |
| F-P1-02 | Verifier-as-a-Service (5 verifiers + 统一输出) | follow-up | 2-4 周 P1 |
| F-P1-03 | capability_inference 支持 action-level | follow-up | 2-4 周 P1 |
| F-P2-01 | DeepResearch ResearchGraph compiler (question_nodes/contradiction_edges/section_claims) | follow-up | 4-8 周 P2 |
| F-P2-02 | 100k 字长报告分段编译 + claim coverage ≥ 90% | follow-up | 4-8 周 P2 |
| F-P3-01 | Multi-Agent state revision protocol | follow-up | 8-12 周 P3 |
| F-P3-02 | Repair Controller + failure taxonomy + regression-free gate | follow-up | 8-12 周 P3 |
| F-P3-03 | Capability scorecard 自动更新 + dashboard 显示 | follow-up | 8-12 周 P3 |

P0 总估时 ≈ 15.2h，分布到 S02 architecture / S03 core runtime / S04 orchestration / S05 verification。

## 3. Non-goals（本 epic 显式不做，详见 non-goals.md）

1. **不重写整个 harness** — 在现有 sprint contract / graph_scheduler / capability_inference / architecture_guard 基础上加内核，不替换。
2. **不绕过 PM → Planner → DAG → Builder → Evaluator 流程** — Action Contract 必须先在 PRD/Planner 中声明，再由 broker 执行。
3. **不让 Meta-Harness 自动 apply 运行时 patch** — 高风险 action (apply / git commit / network write) 必须 human approval。
4. **不把 prompt 指令当 verifier evidence** — 只接受 verifier service 输出的 verdict JSON。
5. **不引入新 monolithic core 文件** — package-first，每个 Pkg 独立目录 + schema + tests。
6. **不破坏现有 four-pane 工作流 / sprint status 文件 / graph scheduler 行为** — S03 兼容层强制保留 legacy path。
7. **不强依赖 Linear / 外部 tracker** — 内部 sprints/ 文件系统继续做事实源。
8. **不在本 epic 完成 P1/P2/P3** — 仅交付 P0 (Execution Chain Hardening)。

## 4. Traceability Map (Epic → Outcome → Sprint Gate)

```
epic-20260519-solar-harness-vnext-code-as-harness-runtime
├── O-01 (PM PRD)                              → S01:passed
├── O-02 (Planner artifacts)                   → S01:passed
├── O-arch-contracts (interface schemas)       → S02:passed
├── O-03 (Plan IR + Action Contract schema)    → S02:passed → S03:passed
├── O-04 (Event Ledger)                        → S03:passed
├── O-05 (Execution Broker MVP)                → S03:passed
├── O-06 (dispatcher 接 broker)                → S04:passed
├── O-07 (Action Contract 硬规则)              → S03:passed → S05:passed
├── O-08 (broker event coverage = 100%)        → S04:passed → S05:passed
├── O-09 (兼容性约束)                          → S03:passed → S05:passed
├── O-10 (Risk register + rollback)            → S01:passed
├── O-11 (中文证据表 handoff)                  → S01:passed (本切片), S05:passed (final)
├── O-12 (traceability map)                    → S01:passed
├── O-13 (Non-goals 固化)                      → S01:passed
└── O-14 (不能直派 builder 清单)               → S01:passed
```

回写 `traceability.json` 时，每个 child sprint 节点新增 `outcomes: [O-xx, ...]`：
- S01: O-01, O-02, O-10, O-11(部分), O-12, O-13, O-14
- S02: O-arch-contracts, O-03
- S03: O-03, O-04, O-05, O-07, O-09
- S04: O-06, O-08
- S05: O-07, O-08, O-09, O-11(终), 全 epic 收口

> `O-arch-contracts` 是 S02 接口契约切片的稳定性 outcome，独立追溯。

## 5. 哪些工作不能直接派 builder (详见 cannot-dispatch-to-builder.md)

1. **O-03 schema 设计** — 必须先 S02 architecture 定字段语义与 evolution policy，否则 schema breaking change 会全链路反复。
2. **O-05 broker 执行链路** — 涉及策略判断 (action_policy / write_scope_policy / approval_policy)，**必须先 S02 出 policy 优先级表**。
3. **O-06 dispatcher 改造** — 直接动 `graph_node_dispatcher.py`，**必须先有 legacy 双跑对比方案**，否则破坏 four-pane。
4. **O-07 高风险 action 审批阈值** — apply / git / network 的 risk_class 默认值，**必须 human approval**（监护人拍板），不能 builder 自由设。
5. **O-09 兼容层** — `wake/dispatch/status` 旧路径冻结，**必须由 architect 写出 contract**，builder 不能自由删除。
6. **O-04 event ledger 写竞态处理** — fcntl/SQLite WAL/atomic write 三选一，**必须先 S02 选型** 后 builder 实现。

## 6. 稳定接口契约骨架（给 S02 architect 看，可扩展）

### 6.1 `action_contract.schema.json` 最小字段

```yaml
required:
  - action_id            # string, unique within sprint
  - node_id              # string, parent node
  - kind                 # enum: shell|python|file_write|tool_call|research_extract|human_approval
  - intent               # string, human-readable
  - read_set             # array[string], paths or registry refs
  - write_set            # array[string], paths or registry refs
  - required_capabilities  # array[string]
  - preconditions        # array[string], must be true before execute
  - success_predicates   # array[string], must be true after execute
  - verification         # object {static: bool, runtime: [], evidence: []}
  - risk_class           # enum: low|medium|high
optional:
  - rollback             # object {kind, target}
  - approval_required    # bool, default by risk_class
```

### 6.2 `event.schema.json` 最小字段

```yaml
required:
  - event_id             # string, ulid or uuid
  - ts                   # ISO8601
  - sprint_id            # string
  - node_id              # string
  - type                 # enum: action.proposed|action.executed|action.failed|policy.verdict|verifier.verdict|artifact.registered
  - actor                # string, role:pane or builder:id
optional:
  - action_id, input_hash, output_hash, policy_verdict
  - evidence_refs, parent_event_ids
```

### 6.3 `broker_coverage` 字段（activation-proof 必须包含）

```yaml
broker_coverage:
  uncontracted_action_count: int   # 必须 == 0
  unscoped_write_count: int        # 必须 == 0
  total_actions: int
  contracted_actions: int
  coverage_ratio: float            # 必须 == 1.0
  legacy_path_actions: int         # 已知豁免，必须显式 legacy=true
```

## 7. 风险登记（详见 risk-register.md）

| RID | 风险 | 概率 | 影响 | 缓解 | Owner | Rollback |
|-----|------|------|------|------|-------|----------|
| R-01 | broker bypass (旁路调用 shell/file_write) | 高 | 极高 | 单测覆盖未注册 action 立即 raise + py_compile + grep 旧调用 | S03 | git revert broker import + 恢复旧 dispatcher |
| R-02 | event ledger 损坏 (写竞态) | 中 | 高 | fcntl/SQLite WAL 选型 + atomic rename + replay smoke | S03 | 截断到 last_known_good event + 重放 |
| R-03 | action_contract.schema breaking change | 中 | 高 | schema_version 字段 + adapter 双写期间兼容 | S02 + S03 | revert schema 到上一版 + adapter denormalize |
| R-04 | capability mismatch (broker 拒派) | 中 | 中 | capability_inference 兜底 + 显式 fallback to legacy | S04 | 临时 capability_override flag |
| R-05 | 兼容层泄漏破坏 four-pane | 低 | 极高 | wake/dispatch/status smoke 在每个 PR 跑 | S03 | git revert + 恢复 .backup 目录 |
| R-06 | high-risk action 审批阻塞 (apply 全卡) | 中 | 中 | 监护人异步审批通道 (osascript notify) + 5min timeout | S04 | risk_class 临时降级 + manual override log |
| R-07 | regression (graph scheduler tests 退化) | 中 | 高 | CI 必须跑 control_plane tests + 双跑对比 | S03 + S05 | revert dispatcher 整段 |
| R-08 | migration (旧 status 文件被吃) | 中 | 中 | append-only 新 event ledger 与旧 status 并存 | S04 | 关闭 event ledger 写入 flag |

## 8. 与父 Epic task_graph 的耦合点

S01 write_scope = `sprints/*prd.*` + `sprints/*traceability.json` (epic.task_graph 已固化)。本切片**只写**：
- `sprints/$SID.design.md`
- `sprints/$SID.plan.md`
- `sprints/$SID.task_graph.json`
- `sprints/$SID.planning.html`
- `sprints/$SID.prd.html`
- `sprints/$SID.requirements-matrix.md`
- `sprints/$SID.risk-register.md`
- `sprints/$SID.non-goals.md`
- `sprints/$SID.cannot-dispatch-to-builder.md`
- `sprints/$SID.handoff.md`
- `sprints/$EPIC.traceability.json` (升级 children outcomes 字段)

**不动** `/Users/sihaoli/Solar/` 任何代码。

## 9. 上游依赖 / 下游影响 / 未闭环项

### 上游依赖
- `epic-20260519-solar-harness-vnext-code-as-harness-runtime.epic.md` (17KB PRD)
- `epic-20260519-solar-harness-vnext-code-as-harness-runtime.traceability.json` (children stub)
- `epic-20260519-solar-harness-vnext-code-as-harness-runtime.task_graph.json` (5 子 sprint stub)

### 下游影响
- S02 architecture 必须读本切片的 §6 接口契约骨架与 §7 risk register。
- S03 core runtime 不允许在没有 S02 design.md 的情况下开始编码。
- S05 verification 必须验证 O-08 broker coverage = 100% 与 O-09 兼容性。

### 未闭环项
1. P0 估时 15.2h vs Roadmap 0-2 weeks → 估时是 ideal，实际包含返工，buffer 留给 S05。
2. risk_class 默认值 (apply=high / git=high / network write=high) 需监护人在 S02 拍板。
3. event ledger 选型 (JSONL fcntl vs SQLite WAL) 由 S02 决定。
4. P1/P2/P3 全部留 follow-up sprint，本 epic 不交付。
