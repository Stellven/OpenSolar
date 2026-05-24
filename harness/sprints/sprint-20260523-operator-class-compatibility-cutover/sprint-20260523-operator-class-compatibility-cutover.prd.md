# PRD: Operator Class Compatibility Cutover

Sprint: `sprint-20260523-operator-class-compatibility-cutover`
Owner: `PM pane / Codex`
Priority: `P0`
Lane: `strategy`
Handoff To: `planner`
Created: `2026-05-23T20:20:00Z`
Parent Sprint: `sprint-20260523-physical-operator-taxonomy-truthification`

## 背景 / Context

当前 Solar-Harness 正处在旧架构与新架构混跑的窗口期：

- 新 DAG / planner 真值已经开始使用新 taxonomy：
  - `DeepArchitect`
  - `ImplementationWorker`
  - `Verifier`
- 但 runtime / worker inventory / registry / scheduler 仍有大量旧语义：
  - `planner`
  - `builder`
  - `evaluator`
  - `external`

因此会出现：

- tmux pane 明明很多、而且不少 idle
- 但 scheduler 仍可能报 `no_matching_worker`

这不是资源不足，而是 **兼容桥缺失**。

更关键的是，后台已有 parent/follow-up sprint 正在跑，切换过程中不能：

- 杀掉正在运行的 pane
- 强制重启所有 worker
- 回滚正在执行的 DAG
- 破坏 lease / handoff / evaluator 流程

## Summary

定义一套 **Operator Class Compatibility Bridge**，让系统在过渡期同时支持：

- legacy role buckets
- new canonical operator taxonomy

并通过 staged rollout 平滑切换到新架构，不破坏后台正在运行的 worker、lease、dispatch 和 review。

## Problem

当前根因是：

```text
DAG 说：我要 DeepArchitect
worker/runtime 说：我这里只有 planner
scheduler 还没完成 alias / canonical resolve
=> no_matching_worker
```

所以问题不是 pane 数量，而是：

- vocabulary 不一致
- scheduler 匹配层没 canonicalize
- worker inventory / registry / runtime 不是同一种命名体系

## 用户故事 / User Stories

- **US1 — 作为 Planner**，我希望我能开始用新 taxonomy 写 DAG，但不要求旧 worker 当场改名完成。
- **US2 — 作为 Scheduler**，我希望我先 alias resolve，再 canonical resolve，再挑具体 operator。
- **US3 — 作为 Runtime 维护者**，我希望 `LEASED / RUNNING / DRAINING` 的 operator 不被迁移打断。
- **US4 — 作为 Evaluator / 运维**，我希望我能看出这次命中到底是 legacy role、canonical class，还是 fallback。
- **US5 — 作为人类操盘者**，我希望这次切换是 staged rollout，而不是一次性翻表。

## Product Goal

让系统从：

- `planner / builder / evaluator / external`

平滑迁移到：

- `DeepArchitect / RootCauseDebugger / ImplementationWorker / ...`

并满足：

- 不破坏后台运行
- 不要求停机
- 不要求一次性 strict mode

## 用户目标 / Goals

| ID | 目标 | 映射 |
|----|------|------|
| G1 | 建立 `legacy role -> canonical_operator_class` 真值层 | US1, US2 |
| G2 | 保护 in-flight operator，不在线切断 | US3 |
| G3 | 定义 dual-read / dual-write / alias resolve 规则 | US2, US4 |
| G4 | 给 8765/status/monitor 增加 legacy/canonical/selected 三视图 | US4 |
| G5 | 定义 staged rollout + rollback | US5 |

## Core Design Decisions

### D1. Canonical Layer

所有输入都先归一化到 `canonical_operator_class`，再参与调度。

### D2. Legacy Alias

legacy role 在过渡期允许存在，但只能作为 alias input，不再是长期真值。

### D3. No Cutover On Running Operators

任何处于以下状态的 operator 不允许被在线重分类或重启：

- `LEASED`
- `RUNNING`
- `DRAINING`

### D4. Scheduler Resolve Order

scheduler 在过渡期必须按顺序：

1. alias resolve
2. canonical resolve
3. fallback to legacy
4. strict canonical（最后才开）

### D5. Dual Visibility

状态面必须同时显示：

- legacy role
- canonical class
- selected runtime binding

## Functional Requirements

### FR1: Canonical Mapping Table

至少定义：

```text
planner   -> DeepArchitect
builder   -> ImplementationWorker
evaluator -> Verifier
architect -> DeepArchitect + RootCauseDebugger
external  -> split-only, not final truth
```

### FR2: Dual-read / Dual-write

必须说明哪些组件：

- dual-read
- dual-write
- canonical-only

至少覆盖：

- registry
- worker inventory
- scheduler
- graph dispatcher
- status payload
- 8765 / monitor

### FR3: In-flight Safety

必须明确定义：

- `LEASED/RUNNING/DRAINING` 保护规则
- 哪些状态允许 alias/canonical 更新
- 哪些更新要“下次启动生效”

### FR4: Scheduler Migration Strategy

必须定义：

- alias resolve
- canonical resolve
- fallback
- strict mode 开启条件

### FR5: Observability

状态/日志必须能回答：

- 这次命中是 legacy、canonical 还是 fallback
- 为什么 no_matching_worker
- 哪些 worker 还没迁到 canonical

### FR6: Non-breaking Rollout

至少给出：

```text
Phase 0: Read-only audit
Phase 1: Alias table
Phase 2: Dual-read dual-write
Phase 3: Canonical preferred, legacy fallback
Phase 4: Strict canonical for new DAGs
Phase 5: Retire legacy buckets
```

## PM DAG Input

### Workstream A: Compatibility Audit Lock

- 盘点旧 role、新 class、registry、worker cache 的混用情况

### Workstream B: Canonical Mapping Lock

- 定义 alias / canonical 真值表

### Workstream C: Scheduler Bridge Lock

- 定义 resolve 顺序与 fallback 逻辑

### Workstream D: In-flight Safety Lock

- 定义不打断在跑 worker 的迁移边界

### Workstream E: Observability Lock

- 定义三视图状态字段

### Workstream F: Rollout / Rollback Lock

- 给出 staged rollout + rollback

## 验收标准 / Acceptance Criteria

| ID | 验收标准 | 映射 |
|----|----------|------|
| A1 | 明确列出 legacy role / canonical class / selected binding 三者关系表 | G1 / FR1 |
| A2 | 明确哪些 legacy bucket 只读兼容，哪些 deprecate，哪些禁止 | G1 / FR1 |
| A3 | 定义 dual-read / dual-write / canonical-only 策略，覆盖 registry/worker/scheduler/status | G3 / FR2 |
| A4 | 明确 `LEASED/RUNNING/DRAINING` 不允许在线切换 | G2 / FR3 |
| A5 | 定义 scheduler 的 alias resolve -> canonical resolve -> strict mode 顺序 | G3 / FR4 |
| A6 | 给出 no_matching_worker 在迁移期的原因分类树 | G4 / FR5 |
| A7 | 给 8765/status 增加三视图字段要求 | G4 / FR5 |
| A8 | 给出 Phase 0-5 rollout 及 rollback 条件 | G5 / FR6 |
| A9 | 不要求停机、不要求全量重启 pane、不要求回滚在跑 sprint | 全部 |

## 约束 / Constraints

- 不破坏后台正在运行的 sprint
- 不强制停掉当前 builder / planner / evaluator pane
- 不直接修改 in-flight node 的 semantic intent
- 不要求一次性把所有 operator entry 改名完成
- 不要求立即 strict mode

## 非目标 / Non-Goals

- **不在本 sprint 关闭 legacy role bucket** — `planner / builder / evaluator / architect / external` 在过渡期保持可读、可派发；本 sprint 只建桥，不拆桥。强制下线推到 Phase 5（独立 follow-up sprint）。
- **不要求一次性把所有 operator entry 改名到 canonical class** — 改名通过 dual-write + 下次启动生效；本 sprint 不强制批量重命名。
- **不打断 in-flight worker** — 处于 `LEASED / RUNNING / DRAINING` 的 operator **绝对不允许**在线重分类、重启、迁移；任何方案触发这三态切换都视为违反 D3。
- **不停机** — 不要求 solar-harness restart / pane restart / coordinator restart；切换必须 hot-swap。
- **不回滚父 sprint / 兄弟 sprint 正在跑的 DAG** — 父 sprint `physical-operator-taxonomy-truthification` 和兄弟 sprint `pane-as-physical-operator-architecture` 仍在 planner/dispatch 链路；本 sprint 不持其 lock，不 mutate 其 artifact。
- **不引入 strict canonical mode 作为默认值** — Phase 4 strict 是 opt-in（按 sprint 或 DAG version），不是全局开关；本 sprint 只定义触发条件和回退路径。
- **不改 task_graph schema 已有字段语义** — `operator_class` / `required_capabilities` / `preferred_operator_classes` 字段含义保持父 sprint 定义；本 sprint 只在 resolve 链路加 alias 翻译层。
- **不重做 scheduler 算法** — 父 sprint 已确定 rule-based deterministic scoring；本 sprint 只在 score 前加 canonicalize 步骤。
- **不引入新进程 / 新 sandbox / 新 secret manager** — 兼容层全部在 sqlite + scheduler 代码内完成；不允许 systemd / launchd / Docker / k8s / 新外挂服务。
- **不直接消灭 `external` 桶** — `external` 在过渡期作为 split-only 分流（按 secondary 标签拆到 Browser / Google-stack / LocalPrivacy / FastSubagent），但本 sprint 不删除 `external` 入口；删除推到 Phase 5。
- **不引入 ML / 自适应 alias 学习** — alias 映射表必须 deterministic、可手工 audit；ML-based mapping 推到下一代。
- **不要求 8765 / status / monitor 立刻完成三视图 UI 改造** — 本 sprint 只定义字段契约（legacy_role / canonical_class / selected_binding 三个字段必须出现在 status payload）；UI 渲染可推到 Phase 2 之后的 follow-up。
- **不替换 5-pane 拓扑** — pane 0/1/2/3/4 的物理角色与模型绑定保持稳定；本 sprint 只重命名它们暴露给 scheduler 的 class label。

## 风险 / Risks

- **R1**: alias 映射不完整，继续误报 `no_matching_worker`
- **R2**: 在线切 running operator，造成 lease 失真
- **R3**: dual-write 不一致，导致 status 混乱
- **R4**: observability 不足，运维看不出命中路径
- **R5**: strict canonical 开得过早，破坏老 DAG

## Open Questions

1. `architect` 是否永久只做 display bucket？
2. `external` 是只读兼容一段时间，还是尽快禁用？
3. canonical class 应由 registry 推导还是 runtime 上报？
4. 三视图是否直接进 8765 首页？
5. strict canonical mode 的开关粒度是全局、按 sprint，还是按 DAG version？

## Planner Handoff

这张单不是重做架构，而是解决：

**旧 `planner/builder/evaluator` 和新 `DeepArchitect/...` 混用时，如何不打断后台运行，平滑切换到新架构。**
