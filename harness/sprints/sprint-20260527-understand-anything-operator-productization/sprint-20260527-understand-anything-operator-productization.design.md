# Design: 对 Solar Harness 正式接入 understand-anything 做一轮 full PRD 发单。目标不是让 Claude 手动执行 /unde

sprint_id: `sprint-20260527-understand-anything-operator-productization`
status: planning_complete
generated_at: 2026-05-28T17:59:50Z
source_of_truth: compiled PRD / contract / task_graph

## 目标

- 将编译型需求推进为可执行 planner contract。

## 设计原则

- Requirement IR / compiled contract 仍是事实源，planner 产物只做执行视图。
- 不绕过 `task_graph.json` 直接派 builder。
- 每条 requirement / acceptance 都必须能映射到节点和验证门。
- capability capsule 与 logical operator 绑定必须保留，不能在 planner 层丢失。

## 执行面分层

- **Planning layer**: `S1` 锁定实现边界与文件范围。
- **Implementation layer**: `S2` 做受约束实现，严格限制在声明写范围。
- **Verification layer**: `S3` 输出测试与证据。
- **Review layer**: `S4` / `S5` 负责 verifier 决策与 rollout note。

## 逻辑算子 / capsule 绑定

- `S1` / `DeepArchitect` / `planning` / `cap.requirement-compiler-planner`: Lock implementation approach, constraints, and file boundaries.
- `S2` / `ImplementationWorker` / `implementation` / `cap.requirement-compiler-implementation`: Implement the approved scope.
- `S3` / `TestRunner` / `tests` / `cap.requirement-compiler-verification`: Run verification commands and collect execution evidence.
- `S4` / `Verifier` / `verification` / `cap.requirement-compiler-verification`: Perform independent review and closeout decision.
- `S5` / `Critic` / `review` / `cap.requirement-compiler-verification`: Check migration, compatibility, or rollout implications.

## 产物边界

### Write Scope
- N/A

### Read Scope
- N/A

## requirement 映射

- `REQ-000` -> S1, S4, S5
- `REQ-001` -> S1, S2, S3, S4, S5
- `REQ-002` -> S1, S2, S3, S4, S5
- `REQ-003` -> S1, S2, S3, S4, S5

## 风险

- 当前 sprint 先前只有 PRD / contract / task_graph，没有稳定的 planner 视图，容易导致 workflow_guard 与 acceptance closeout 对状态理解不一致。
- review 失败应优先回退到 planner，而不是误派 builder。
- `task_graph` 中的 capability capsule 必须与 runtime operator surface 保持一致，否则后续 builder 会出现旁路执行。

## 成功标志

- goal: 对 Solar Harness 正式接入 understand-anything 做一轮 full PRD 发单。目标不是让 Claude 手动执行 /understand，而是把 understand-anything 产品化为 Solar Harness 编排、调度、管理、执行机制中的正式能力。需要设计并拆解：1）logical operators，至少覆盖 CodebaseIndexer、CodeExplainer、DiffSemanticAnalyzer、OnboardingCurator 这类代码理解任务；2）physical operator，封装 Claude 插件侧 understand-anything 执行面；3）capability capsule 与 artifact contract，明确输入输出、知识图、explain、semantic diff、onboard
- success_metrics:
- PRD、contract、TaskDAG 互相对齐。
- 实施、验证、兼容/发布路径均已显式表达。
- 每条验收标准都能追溯到验证或 gate。
- non_goals:
- 不在首批交付中做完整四区 PM pane 重构。
- 不绕过 planner 直接进入 builder。
