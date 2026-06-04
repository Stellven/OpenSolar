# PRD: Physical Operator Taxonomy Truthification

Sprint: `sprint-20260523-physical-operator-taxonomy-truthification`
Owner: `PM pane / Codex`
Priority: `P0`
Lane: `strategy`
Handoff To: `planner`
Created: `2026-05-23T19:36:04Z`
Parent Sprint: `sprint-20260523-pane-as-physical-operator-architecture`

## 背景 / Context

`Pane-as-Physical-Operator Architecture` 已经把大方向锁对了：`tmux` pane 是 physical host，Registry / Runtime / Scheduler 三层分离，writer / verifier 分离，secret_ref / quota / policy / evidence 也已经进入设计真值。

但当前 planner 产出的 [design.md](/Users/lisihao/.solar/harness/sprints/sprint-20260523-pane-as-physical-operator-architecture.design.md) 和 [task_graph.json](/Users/lisihao/.solar/harness/sprints/sprint-20260523-pane-as-physical-operator-architecture.task_graph.json) 还没有把 **10 类 physical operator taxonomy** 正式物化成 schema / routing / DAG acceptance 的一等真值。

当前缺口不是“方向错了”，而是“分类体系还没落到机器可调度、可验证、可演进”这一层。PM 已补了 addendum：

- [pm-addendum-operator-taxonomy.md](/Users/lisihao/.solar/harness/sprints/sprint-20260523-pane-as-physical-operator-architecture.pm-addendum-operator-taxonomy.md)

现在需要一张 follow-up sprint，把这 10 类 taxonomy 从补充说明提升为正式 contract。

## Summary

把以下 10 类 physical operator taxonomy 正式物化为：

- registry/schema 字段
- scheduler routing matrix
- task_type/operator_class 映射
- DAG acceptance / verifier 规则
- rollout / compatibility / follow-up 边界

这 10 类是：

1. Deep Architect Operator
2. Root-Cause Debug Operator
3. Implementation Operator
4. Fast Subagent Operator
5. Parallel Exploration Operator
6. Verifier Operator
7. Research Synthesis Operator
8. Browser / Computer-use Operator
9. Google-stack Operator
10. Local Privacy Operator

## Problem

当前 `design.md` 里的 `operator_class` 仍偏粗粒度流程角色，例如：

- `planner | builder | evaluator | architect | pm | external`

而不是按执行角色 taxonomy 建模。

这会带来几个问题：

- DAG 仍可能按“流程角色桶”而不是“执行角色能力”选 operator
- Fast Subagent / Parallel Exploration / Browser / Google-stack / Local Privacy 无法成为一等调度对象
- scheduler 只能表达部分 high-value routing，不能表达完整 operator ladder
- verifier separation 虽然存在，但没有和 taxonomy 全量对齐
- 后续 provider 扩展会继续回退到 provider/model 维度思考

## 用户故事 / User Stories

- **US1 — 作为 Planner**，我希望 `operator_class` 有正式 taxonomy，而不是只剩 `builder/planner` 这类流程角色桶。
- **US2 — 作为 Scheduler**，我希望我能根据 `task_type` 直接命中 `DeepArchitect / RootCauseDebug / FastSubagent / Browser` 等 operator ladder。
- **US3 — 作为 Evaluator**，我希望我能审出一个 DAG 是否错把 Browser 任务派给普通 Implementation operator。
- **US4 — 作为 PM / Architect**，我希望 Research / Google-stack / Local Privacy 这类执行语义能变成清晰边界，而不是写在说明文字里。
- **US5 — 作为 Runtime 维护者**，我希望 taxonomy 是 schema 真值的一部分，这样新增 provider 时只需要挂到某个 operator class，而不是重想一遍调度语义。

## Product Goal

把 `PhysicalOperator taxonomy` 从 PM addendum 提升为正式架构真值，使 Solar-Harness 以后表达的不是：

- `provider/model/profile`

而是：

- `task_type -> operator_class ladder -> operator_id`

并且 DAG 节点默认表达 **逻辑算子需求**，而不是 `model/provider` 直写绑定。

## 用户目标 / Goals

| ID | 目标 | 映射 |
|----|------|------|
| G1 | 把 PM addendum 的 10 类 operator taxonomy 升级为 **schema / routing / DAG acceptance 真值**（不再停留在散文层） | US1, US5 / FR1, FR2 |
| G2 | 让 Scheduler 按 `task_type → operator_class ladder → operator_id` 选 operator，禁止 `provider/model` 字符串作为长期调度真值 | US2 / FR3, D3 |
| G3 | DAG 节点默认表达 **逻辑算子需求**（required_capabilities + preferred_operator_classes + constraints），model/provider 仅作 implementation binding fallback | US2 / D3.1 |
| G4 | 把 `Browser / Computer-use`、`Google-stack`、`Local Privacy` 三类高风险 operator **单列 policy 边界**，禁止合并到通用 `external/implementation` 桶 | US3, US4 / FR4, D5 |
| G5 | 输出 rule-based **scheduler scoring 模型**（capability_fit / quality / quota / latency / cost / availability / context_affinity / risk_match / recent_error_penalty / same_model_verifier_penalty） — 第一版必须 deterministic，禁止 ML | US2 / FR5 |
| G6 | 把 pane/operator **lifecycle 状态机** 正式化：主路径 `CREATED → WARMING → IDLE → LEASED → RUNNING → DRAINING → IDLE` + 异常态 `ERROR / QUOTA_EXHAUSTED / AUTH_EXPIRED / COOLDOWN / DISABLED / STALE_CONTEXT / NEEDS_HUMAN_REVIEW` | US5 / FR6, D6 |
| G7 | 给出父 sprint `sprint-20260523-pane-as-physical-operator-architecture` 的 **repair / adoption 路径**：父 sprint 不回滚，本 sprint 通过 review gate / addendum / follow-up node 注入 taxonomy | US4 / FR7, Workstream F |
| G8 | 明确 **follow-up boundary**：10 类 taxonomy 中哪些 P0 落地、哪些只做 design reservation、哪些下轮 follow-up，禁止留含糊地带 | US4 / FR7, D4 |

## Core Design Decisions

### D1. 分类主轴

operator 的一级分类按执行角色 / 任务语义划分，不按 provider 划分。

### D2. provider 的地位

provider/model/surface/account/quota 是某个 operator class 的默认实现，不是 taxonomy 主轴。

### D3. task routing 真值

scheduler 必须能显式表达：

- `task_type`
- `required_capabilities`
- `preferred_operator_classes`
- `fallback ladder`
- `writer/verifier separation`

### D3.1 DAG 节点表达

DAG 节点不应直接写：

- `model: claude-opus-4-7`

而应写成逻辑算子需求，例如：

```yaml
node_id: design-runtime-scheduler
task_type: ARCH_DESIGN
required_capabilities:
  planning: ">=5"
  coding: ">=3"
  long_context: ">=4"
constraints:
  max_cost_tier: high
  write_files: false
  privacy: repo_private
  deadline: relaxed
preferred_operator_classes:
  - DeepArchitect
  - RootCauseDebug
verifier_required: true
```

随后由 scheduler 去 registry 里筛 operator，而不是由 DAG 直接绑死模型。

### D4. taxonomy 完整性

第一版设计必须明确说明 10 类 taxonomy 中：

- 哪些进入 P0 schema 真值
- 哪些只进入 routing 预留
- 哪些进入 follow-up

不能只给笼统描述。

### D5. 高风险类别

`Browser / Computer-use`、`Google-stack`、`Local Privacy` 必须有专门 policy 边界，不能只复用通用 implementation policy。

### D6. Pane / Operator 生命周期

每个 physical operator 必须有正式 runtime 状态机。

canonical lifecycle:

```text
CREATED
  ↓
WARMING
  ↓
IDLE
  ↓
LEASED
  ↓
RUNNING
  ↓
DRAINING
  ↓
IDLE
```

exception states:

- `ERROR`
- `QUOTA_EXHAUSTED`
- `AUTH_EXPIRED`
- `COOLDOWN`
- `DISABLED`
- `STALE_CONTEXT`
- `NEEDS_HUMAN_REVIEW`

这套状态机必须进入 runtime / scheduler 真值，而不是只放在说明文字里。

### D7. operatord 统一守护壳

pane 不应直接跑 `claude` / `codex` / `antigravity` / `local runtime`。

每个 pane 应统一跑：

```bash
operatord run <operator_id>
```

`operatord` 负责：

1. 读取 registry
2. 解析 `secret_ref`
3. 注入环境变量
4. 启动对应 CLI / SDK / local runtime
5. 打心跳
6. 接收 task envelope
7. 写 execution log
8. 抓取 stdout / stderr
9. 解析 quota / auth / error
10. 上报 task result

这样底层工具如何变，都被统一包在 `operatord` 壳里。

### D8. Task Envelope

发给 operator 的输入必须结构化，不能直接把自然语言塞给 pane。

标准 envelope 至少应支持：

```yaml
task_id: dag-20260521-0007-node-03
task_type: CODE_IMPL
repo: /Users/sihao/work/FlashMLX
branch: feat/operator-runtime
working_tree: /tmp/worktrees/flashmlx-op-0007
objective: >
  Implement the operator registry loader and runtime lease state machine.

constraints:
  write_files: true
  run_tests: true
  git_commit: false
  max_runtime_min: 45
  max_cost_tier: medium

inputs:
  design_doc: artifact://dag-0007/design.md
  files:
    - solar/operator_registry.py
    - solar/operator_runtime.py

output_contract:
  required_artifacts:
    - patch.diff
    - test_report.md
    - execution_summary.md
  pass_conditions:
    - "unit tests pass"
    - "no raw secrets in logs"
    - "operator state transitions covered by tests"

verifier:
  required: true
  preferred_operator_class: Verifier
  cannot_use_same_operator: true
```

operator 输出也必须标准化，至少包含：

```yaml
task_id: dag-20260521-0007-node-03
operator_id: op.tmux.openai.gpt55.impl.default.01
status: PASS_WITH_WARNINGS
artifacts:
  patch: artifact://dag-0007/node-03/patch.diff
  test_report: artifact://dag-0007/node-03/test_report.md
metrics:
  runtime_sec: 1830
  files_changed: 4
  tests_run: 17
  tests_passed: 17
warnings:
  - "Need manual review for quota parser edge cases"
```

## Functional Requirements

### FR1: Taxonomy Matrix

产出一份正式 `operator taxonomy matrix`，至少覆盖：

- class name
- primary task types
- preferred capabilities
- policy deltas
- quota posture
- verifier constraints
- example operator ids

### FR2: Schema Truthification

回答 `operator_class` 在 schema 中应该如何表达：

- 一级 class 枚举
- 子类 / routing tags
- capability_tags 的关系
- 与旧 `planner/builder/evaluator/architect` 角色的兼容映射

### FR3: Scheduler Mapping

产出 `task_type -> preferred_operator_classes -> fallback ladder` 的正式规则，至少覆盖：

- `ARCH_DESIGN`
- `ROOT_CAUSE_DEBUG`
- `IMPL`
- `FINAL_REVIEW`
- `RESEARCH_SYNTHESIS`
- `BROWSER_VALIDATION`
- `GOOGLE_STACK`
- `LOCAL_PRIVACY_SCAN`
- `FAST_FANOUT`
- `PARALLEL_EXPLORATION`

并明确第一版 routing policy，至少覆盖下表：

```text
┌──────────────────────┬──────────────────────────────────────┬────────────────────────────────┬────────────────────────────────────┐
│ Task Type            │ 首选算子                             │ 备选算子                       │ 策略                               │
├──────────────────────┼──────────────────────────────────────┼────────────────────────────────┼────────────────────────────────────┤
│ ARCH_DESIGN          │ Claude architect                     │ Codex research                 │ Claude 出主设计，Codex 整理文档     │
│ ROOT_CAUSE_DEBUG     │ Claude debug                         │ Codex repro/test               │ Claude 推因果，Codex 跑复现         │
│ CODE_IMPL            │ Codex impl                           │ Claude patch                   │ Codex 写，Claude 审                 │
│ MULTI_FILE_REFACTOR  │ Claude architect -> Codex impl       │ Claude review                  │ 先设计再执行                       │
│ TEST_GEN             │ Codex test                           │ Codex mini                     │ 低风险可用 mini                    │
│ TEST_RUN             │ Codex test / local shell             │ local checker                  │ 跑命令优先不用强模型               │
│ RESEARCH_SYNTHESIS   │ Codex research                       │ Claude critique                │ Codex 汇总，Claude 质检             │
│ ACADEMIC_CRITIQUE    │ Claude Opus                          │ Codex research                 │ Claude 更适合深推理/反驳            │
│ PARALLEL_EXPLORATION │ Antigravity Gemini Flash             │ Codex mini                     │ fan-out 多路线                     │
│ ANDROID_FIREBASE     │ Antigravity Google-stack             │ Codex                          │ Google 栈优先 Antigravity          │
│ UI_PROTOTYPE         │ Antigravity parallel / Codex browser │ Codex impl                     │ 多方案快速生成                     │
│ DOC_REPORT           │ Codex research                       │ Claude review                  │ Codex 出稿，Claude 去水分           │
│ SOFT_HW_OPT          │ Claude architect/debug               │ Codex bench/test               │ Claude 判瓶颈，Codex 跑实验         │
│ SECURITY_SENSITIVE   │ Claude review + local scan           │ none                           │ 高权限必须人工确认                 │
│ LOW_COST_SCAN        │ local operator                       │ Codex mini                     │ 先本地，必要时升级                 │
└──────────────────────┴──────────────────────────────────────┴────────────────────────────────┴────────────────────────────────────┘
```

### FR4: Verifier and Safety

明确 taxonomy 下的 verifier 规则：

- writer 和 verifier 不能同 `operator_id`
- high-risk task 尽量跨 provider
- browser / payment / login / secrets_form_fill 等风险动作如何落到 policy

### FR5: Score-based Selection

第一版 scheduler 必须给出 rule-based 评分模型，而不是只按“哪个模型最强”选择。

至少覆盖：

- `capability_fit`
- `quality_score`
- `quota_score`
- `latency_score`
- `cost_score`
- `availability_score`
- `context_affinity`
- `risk_match`
- `recent_error_penalty`
- `same_model_verifier_penalty`

并明确第一版可以是 deterministic scoring，而不是 ML。

### FR6: Lifecycle State Machine

必须定义 pane / operator 生命周期状态机，并明确每个状态的调度动作。

至少覆盖：

```text
┌────────────────────┬──────────────────────────────────────────────┬──────────────────────────┐
│ 状态               │ 含义                                         │ 调度动作                 │
├────────────────────┼──────────────────────────────────────────────┼──────────────────────────┤
│ CREATED            │ registry 有定义，但 pane 未启动              │ 不可调度                 │
│ WARMING            │ 启动 CLI / 登录 / 加载 repo                  │ 暂不可调度               │
│ IDLE               │ 可用                                         │ 可调度                   │
│ LEASED             │ 已被某个 DAG node 预占                       │ 不再分配                 │
│ RUNNING            │ 正在执行                                     │ 不再分配                 │
│ DRAINING           │ 任务结束，正在收集 artifact                  │ 不再分配                 │
│ COOLDOWN           │ 刚失败或刚跑完重任务，短暂冷却               │ 降权                     │
│ QUOTA_EXHAUSTED    │ 配额耗尽                                     │ 禁用到 refresh           │
│ AUTH_EXPIRED       │ 登录态失效 / key 失效                        │ 需要人工处理             │
│ STALE_CONTEXT      │ 上下文污染或太长                             │ 需要 compact / restart   │
│ DISABLED           │ 手工停用                                     │ 不调度                   │
│ ERROR              │ 运行异常                                     │ 禁止直接继续派发         │
│ NEEDS_HUMAN_REVIEW │ 风险异常 / 安全边界 / 不可自动恢复           │ 人工确认前不调度         │
└────────────────────┴──────────────────────────────────────────────┴──────────────────────────┘
```

并回答：

- `COOLDOWN` 是 hard block 还是 soft penalty
- `STALE_CONTEXT` 如何检测与恢复
- `NEEDS_HUMAN_REVIEW` 的触发条件
- `DRAINING -> IDLE` 的 artifact completeness gate

### FR7: operatord Runtime Shell

必须定义 `operatord run <operator_id>` 的统一宿主模型，至少明确：

- registry 读取责任
- `secret_ref` 解析与 env 注入边界
- backend launcher 责任
- heartbeat / lease / stdout/stderr / execution log 采集
- quota/auth/error parser 责任
- task result 上报契约

并回答：

- pane 是否允许绕过 `operatord` 直接跑 CLI
- `operatord` 与 tmux pane / operator_id 的绑定方式
- 多 backend（CLI / SDK / local runtime）的统一 adapter 边界

### FR8: Task Envelope and Result Contract

必须定义结构化 `Task Envelope` 和标准化 `Task Result`。

至少覆盖：

- task identity
- repo / branch / working_tree
- objective
- constraints
- inputs / artifact references
- output_contract / pass_conditions
- verifier requirements
- result status
- artifact outputs
- metrics
- warnings / errors

并明确：

- 何种字段是 scheduler 必填
- 何种字段是 operator runtime 必填
- envelope 与 DAG node schema 的关系
- 自然语言 objective 如何和结构化约束并存

### FR9: Complex DAG Example

必须给出至少 1 个“复杂任务 DAG 按物理算子匹配”的完整示例，而不是按模型名发活。

建议示例：`FlashMLX 性能 bug`。

至少覆盖：

- Problem framing
- benchmark reproduce
- candidate fix fan-out
- compare patches
- final implementation
- test + benchmark
- final review
- report

并清楚区分：

- logical operator class
- selected physical operator
- verifier / test runner / research synthesis 的职责

### FR10: Follow-up Boundary

如果 10 类 taxonomy 不能全部进入当前 P0 生产 schema，必须明确：

- 哪些本 sprint 完成
- 哪些只做 design reservation
- 哪些开下轮 follow-up

## PM DAG Input

以下是 PM 给 Planner 的建议切片，不是最终 `task_graph.json` 真值：

### Workstream A: Taxonomy Lock

- 10 类 operator taxonomy matrix
- 一级 class / 子类 / routing tags 边界

### Workstream B: Schema Lock

- `operator_class` / `routing` / `policy` / `task_type` 真值化
- 旧角色桶兼容映射

### Workstream C: Scheduler Lock

- `task_type -> preferred_operator_classes -> fallback ladder`
- verifier / quota / policy 与 taxonomy 的结合点
- rule-based selection score 与 penalty 设计

### Workstream D: Runtime Lifecycle Lock

- pane/operator canonical lifecycle
- exception states
- state-specific dispatch behavior
- stale_context / cooldown / human_review 恢复策略

### Workstream E: operatord and Envelope Lock

- `operatord run <operator_id>` 宿主契约
- task envelope schema
- result contract schema
- DAG node 与 envelope 的映射

### Workstream F: Safety Lock

- Browser / Google-stack / Local Privacy 的专门 policy
- 高风险动作门禁

### Workstream G: Rollout / Repair

- 明确对父 sprint 的 repair 方式
- 或输出“follow-up only, no retroactive mutation”规则

## 验收标准 / Acceptance Criteria

| ID | 验收标准 | 关联 Goal |
|----|----------|-----------|
| A1 | 产出正式 **10-class operator taxonomy matrix**（class / primary task types / preferred capabilities / policy deltas / quota posture / verifier constraints / example operator ids），10 类全部覆盖 | G1 / FR1 |
| A2 | schema 中 `operator_class` / `routing` / `policy` / `task_type` **全部定版**，且提供旧 `planner / builder / evaluator / architect / pm / external` 桶到新 taxonomy 的 **兼容映射表** | G1, G7 / FR2 |
| A3 | Scheduler 给出 `task_type → preferred_operator_classes → fallback ladder` 表，**至少覆盖 10 个 task_type**（ARCH_DESIGN / ROOT_CAUSE_DEBUG / IMPL / FINAL_REVIEW / RESEARCH_SYNTHESIS / BROWSER_VALIDATION / GOOGLE_STACK / LOCAL_PRIVACY_SCAN / FAST_FANOUT / PARALLEL_EXPLORATION） | G2 / FR3 |
| A4 | DAG 节点 schema 引入 `task_type` + `required_capabilities` + `constraints` + `preferred_operator_classes` 字段，并明确 `model/provider` 直写字段标记为 `deprecated` 或 fallback-only；给出至少 1 个完整 node 例子 | G3 / D3.1 |
| A5 | 产出 **rule-based scoring 模型**，包含 ≥10 个 score/penalty 项（capability_fit, quality, quota, latency, cost, availability, context_affinity, risk_match, recent_error_penalty, same_model_verifier_penalty），并给出可计算公式或伪代码 | G5 / FR5 |
| A6 | `Browser / Computer-use`、`Google-stack`、`Local Privacy` 各自有 **独立 policy section**，包含允许/禁止动作清单（payment / login / secrets_form_fill / file write 等关键动作明确） | G4 / FR4, D5 |
| A7 | pane/operator **lifecycle 状态机** 完整定义：主路径 6 状态 + 异常态 7 状态（共 ≥13），每个状态有明确 `调度动作`，并回答 COOLDOWN 软硬性 / STALE_CONTEXT 检测 / NEEDS_HUMAN_REVIEW 触发 / DRAINING→IDLE artifact gate 4 个具体问题 | G6 / FR6, D6 |
| A8 | Verifier 规则与 taxonomy **全量对齐**：writer/verifier 不同 `operator_id` 是 contract；high-risk task 跨 provider 优先；规则明确写进 schema / scheduler，不是只写在 prose | G4 / FR4 |
| A9 | 定义 `operatord run <operator_id>` 统一宿主契约，明确 registry/secret/env/launcher/heartbeat/log/quota/result 责任边界，并回答“是否允许绕过 operatord” | G6 / FR7, D7 |
| A10 | 定义结构化 `Task Envelope` 与标准化 `Task Result`，字段至少覆盖 `task_id/task_type/repo/branch/working_tree/objective/constraints/inputs/output_contract/verifier/result/artifacts/metrics/warnings` | G2, G3 / FR8, D8 |
| A11 | 给出至少 1 个复杂 DAG 示例，展示 logical class 与 physical operator 的分离选择，建议以 FlashMLX 性能 bug 为例 | G2 / FR9 |
| A12 | 给出父 sprint 的 **repair / adoption 路径**（review gate / addendum / follow-up node 任选 ≥1），父 sprint `design.md / task_graph.json` 不直接回滚，但有明确接管点 | G7 / FR10, Workstream G |
| A13 | 明确 **follow-up boundary**：列出 10 类 taxonomy 中 P0 落地、design reservation、下轮 follow-up 三档分配，无 "TBD" 含糊项 | G8 / FR10, D4 |
| A14 | `task_graph.json` 通过 `solar-harness graph-scheduler validate`，且至少包含 7 个 workstream node（N1–N7 对应 Workstream A–G），每个 node 有 `acceptance` 字段映射回 A1–A13 | G1, G2 / Planner Output |
| A15 | `design.md` / `plan.md` / `task_graph.json` 三件套齐全；Knowledge Context 一行写明 `solar-harness context inject used`；evidence 不含 raw secret | 全部 / Planner Output |

## 约束 / Constraints

- 不直接回滚父 sprint 既有 `design.md / task_graph.json`
- 不把 taxonomy 继续停留在 PM prose 层
- 不以 provider/model 枚举替代 operator taxonomy
- 不把 Browser / Google-stack / Local Privacy 合并成通用 `external`
- 不要求本 sprint 一次性实现所有 provider 真执行器

## 非目标 / Non-Goals

- **不重写父 sprint 既有架构方向** — Registry / Runtime / Scheduler 三层分离、writer/verifier 分离、secret_ref/quota/policy/evidence 这些大决策保持，不在本 sprint 重审。
- **不回滚父 sprint 的 `design.md` / `task_graph.json`** — 父 sprint 已经在 planner 手里，本 sprint 通过 repair / adoption 路径注入，不直接 mutate 父 artifact。
- **不要求一次性实现所有 10 类 operator 的真实 entry** — 本 sprint 落 schema / routing / DAG acceptance 真值；具体 operator 注册可延后到 follow-up sprint。
- **不引入 ML / 自适应 scoring** — 第一版 scheduler scoring 必须 deterministic、可手算、可单元测试；ML-based ranking 明确推到下一代。
- **不替换 5-pane 拓扑或物理 pane 角色绑定** — pane 0/1/2/3/4 的角色（planner / builder / evaluator / architect / PM）保持稳定，本 sprint 只把它们映射到 taxonomy。
- **不把 Browser / Computer-use / Google-stack / Local Privacy 合并成通用 `external`** — 这三类必须单列 policy；任何把它们塞回 generic external 桶的方案在本 sprint 视为违反 D5。
- **不在 task_graph 节点把 `model=...` / `provider=...` 字符串作为长期调度真值** — 只允许作 `preferred_operator_id` 显式硬指定，或作 fallback / migration 兼容字段，明确标 `deprecated`。
- **不引入新进程模型** — 不允许 systemd / launchd unit / Docker / k8s；继续走 `solar-harness` CLI + tmux pane + sqlite。
- **不要求生成新的物理 pane** — 本 sprint 只重定义 taxonomy 和 lifecycle 状态机，不涉及创建新 tmux pane / 新账号 / 新 quota 池。
- **不把 taxonomy 继续留在 PM prose 层** — 任何 "在 README/PRD 描述里" 的方案不算落地；必须进入 schema / routing matrix / state machine 三处至少一处。
- **不在本 sprint 上线新 evaluator policy 之外的安全工具** — 高风险动作只在 policy 字段表达，不引入新 sandbox / 新 VPN / 新 secret manager 子系统。
- **不阻塞父 sprint** — 本 sprint 不持有父 sprint 的 lock；父 sprint planner 可以并行继续推进。

## 风险 / Risks

- **R1**: taxonomy 过细，导致 schema 不可演进
- **R2**: taxonomy 过粗，继续回到 `planner/builder/external` 旧桶
- **R3**: Browser / Google-stack policy 未单列，导致危险动作复用通用权限
- **R4**: verifier 规则只停留在泛化层，没和 taxonomy 绑定
- **R5**: scheduler 继续退回 provider/model 直选
- **R6**: runtime 状态机不完整，导致 lease/dispatch 语义漂移
- **R7**: pane 直接跑底层 CLI，绕开 operatord 审计与 lease
- **R8**: task input/output 不结构化，导致 DAG 与 runtime 脱节
- **R9**: 父 sprint 与 repair sprint 真值分叉

## Open Questions

1. `operator_class` 应该是一级枚举，还是 `taxonomy_class + routing_tags` 双层结构？
2. `Research Synthesis` 和 `Deep Architect` 是并列一级类，还是 capability/routing overlay？
3. `Browser / Computer-use` 应该作为一级 class，还是作为 surface/policy overlay？
4. `Google-stack` 是 provider family 类，还是 domain specialization 类？
5. `Local Privacy` 应该如何与低成本 / 本地推理 / data sensitivity 一起表达？
6. DAG schema 是否要显式禁止 `model/provider` 直写，还是仅标记为 deprecated？
7. `context_affinity` 该如何量化：repo、branch、topic、recent lease，还是多因素组合？
8. `same_model_verifier_penalty` 是软降权还是高风险任务的硬门禁？
9. `STALE_CONTEXT` 的检测信号是 token/context 长度、topic drift，还是人工标记？
10. `NEEDS_HUMAN_REVIEW` 是否需要专门 escalation artifact？
11. `operatord` 是否允许 backend-specific sidecar，还是必须单进程 adapter？
12. `Task Envelope` 与 `task_graph.json` 是 1:1 投影，还是 node schema 的 runtime materialization？
13. 复杂 DAG 示例是否需要同时展示 verifier/test-runner/research-synthesis 三种不同 class 的切换？
14. 父 sprint 是否需要一个正式 repair node，还是只追加 evaluator/architect review gate？

## Planner Handoff

请基于父 sprint 现有 architecture truth：

- 不重写大方向
- 只补 taxonomy 真值化缺口
- 产出新的 `design.md / plan.md / task_graph.json`
- 明确 repair 与 follow-up 边界

目标不是重做整套架构，而是把 **10 类 physical operator taxonomy** 正式落成机器可读、可调度、可验证的 contract。
