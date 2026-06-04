# RawIntent Consumer Request - # Execution Contract

## 1. Problem
# RawIntent Consumer Request - # Execution Contract ## Source - intent_id: intent-20260525-155538-44d6838383 - channel: codex_bridge - actor: codex - device: mac_mini - thread_ref: ## Rewritten Objective # Execution Contract ## Problem # Execution Contract Codex bridge trusted auto planner handoff smoke unique-1779724538 ## Constraints - All execution must enter Solar-Harness through RawIntent and

## 2. Users / Stakeholders
- PM
- Planner
- Builder
- Evaluator

## 3. Goals / Non-goals
Goals:
- # RawIntent Consumer Request - # Execution Contract ## Source - intent_id: intent-20260525-155538-44d6838383 - channel: codex_bridge - actor: codex - device: mac_mini - thread_ref: ## Rewritten Objective # Execution Contract ## Problem # Execution Contract Codex bridge trusted auto planner handoff smoke unique-1779724538 ## Constraints - All execution must enter Solar-Harness through RawIntent and

Non-goals:
- 不在首批交付中做完整四区 PM pane 重构。
- 不绕过 planner 直接进入 builder。

## 4. User Scenarios
用户输入需求后，需要被结构化、合约化、任务图化，然后再派给执行链路。

## 5. Functional Requirements
- PRD、contract、TaskDAG 互相对齐。
- 实施、验证、兼容/发布路径均已显式表达。
- 每条验收标准都能追溯到验证或 gate。

## 6. Non-functional Requirements
- 可验证
- 可追溯
- 与现有 PM -> Planner -> Builder 主链兼容

## 7. UX / Interaction Model
首批仅提供编译结果视图与 handoff bar，不重做完整 UI。

## 8. Data Model
Requirement IR 为唯一事实源，PRD/contract/DAG/handoff 均从 IR 派生。

## 9. Acceptance Criteria
- PRD、contract、TaskDAG 互相对齐。
- 实施、验证、兼容/发布路径均已显式表达。
- 每条验收标准都能追溯到验证或 gate。

## 10. Risks / Open Questions
- [medium] PRD / contract / DAG 多份产物漂移 -> 用 Requirement IR 做唯一事实源，所有视图从 IR 编译。
- [medium] 原始需求直接派给 Builder 导致执行发散 -> 强制走 product-brief / planner handoff，不允许 raw request 直派 builder。
- [medium] 验收标准没有映射到验证步骤 -> 编译期做 acceptance coverage 检查，缺失时阻断派单。

Open Questions:
- N/A

## 11. Release Plan
先交付后端编译底座，再逐步扩展 PM pane UI 与 eval loop。

---

## 背景 / Context

- 本 sprint 是 **Codex bridge 自动 planner handoff smoke test**：intent-20260525-155538-44d6838383 由 codex_bridge 从 Mac mini 注入，自动产出 raw_intent → requirement_ir → rewritten_intent → product-brief → PRD → contract → task_graph 全套 artifact。
- 时间：2026-05-25 11:55；唯一标识：`unique-1779724538`。所有 17 份 artifact 文件 mtime 全集中在同一分钟，证明这是 bridge 一次性 emit 而非真实人工 sprint。
- PRD 缺 schema 必需的 4 节（背景/用户故事/约束/架构交接），coordinator gate_prd_schema 触发回溯，本次 dispatch 是 PM 修复入口。
- Sprint 状态：`drafting / prd_ready / handoff_to=planner`；handoff.md 体积 653 bytes、task_graph.json 11865 bytes、capsule_plan.json **115 KB**，证明 planner 编译已经跑过；coverage_report + acceptance_verdict 也已落盘。
- 本切片唯一任务：补足 PRD schema 4 节，让 gate PASS；不动 contract / task_graph / handoff / capsule_plan / coverage_report / acceptance_verdict / 7 份 codex bridge artifact。

## 用户故事 / User Stories

- **US-01 (Codex bridge 维护者)**：作为 codex_bridge 维护者，当我从 Codex 推送一个 raw_intent，我希望 Solar Harness 自动产 PRD/contract/task_graph，并且这套自动产物**能通过 PM 的 gate_prd_schema**，让链路不被人工干预阻断。
  - 验收：本次 PM 修复后 `validate.sh prd` → PASS，未来 codex bridge 的 PRD 模板要把 4 缺失节预填进去。
- **US-02 (Planner)**：作为下游 Planner，我希望从本 PRD 能拿到 Requirement IR 的 path、coverage_report 的 verdict、acceptance_verdict 的结论，不要再人工反向解析自动产物。
  - 验收：架构交接节列出所有自动产物路径与 schema 引用。
- **US-03 (Solar 维护者 / PM 修 schema)**：作为 PM，我需要这个 sprint 在 gate 上不再循环。
  - 验收：PRD schema PASS + PRD mtime 刷新触发 coordinator 重跑 gate。
- **US-04 (未来 codex bridge 模板)**：作为 codex bridge 模板设计者，看本次回溯修复后的 PRD 知道未来模板必须含哪 11 节。
  - 验收：本 PRD 已含全部 11 节，可作为 bridge PRD 模板蓝本。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane / codex_bridge 链路 `~/.solar/codex-bridge/from-codex` 已切到新路径（旧 `~/.solar/harness/codex-bridge` 兼容证据保留）。
- **路径白名单**：本切片只允许修改 `<sid>.prd.md` 和新增 `<sid>.prd.html`；禁动 raw_intent / requirement_ir / rewritten_intent / product-brief / contract / task_graph / capsule_plan / coverage_report / acceptance_verdict / handoff / Contracts.yaml。
- **保留 codex bridge artifact**：本 sprint 是自动产物 smoke test；不允许重写 17 份 codex bridge 自动产物，只允许追加缺失 schema section。
- **不触发 builder**：sprint 当前 `handoff_to=planner`；PM 只修 PRD schema，不动 status 到 implementation。
- **API 兼容**：codex_bridge → solar-harness 自动产物链路必须照常工作；本切片不引入 schema 字段变更。
- **不打印 secrets**：codex bridge 注入的 raw_intent 已经 redact，但本切片任何引用都不允许重新展开 token / API key / OAuth。
- **PM 角色边界**：不写实施代码、不动 17 份自动产物、不改 planner / builder / evaluator 调用。

## 架构交接 / Planner Handoff

### Inputs to Planner（全部 17 份 codex bridge 自动产物 + 本 PRD）

| Artifact | 字节 | 用途 |
|----------|------|------|
| `<sid>.raw_intent.json` | 965 | codex_bridge 注入原始意图 (intent-20260525-155538-44d6838383) |
| `<sid>.requirement_ir.json` | 1365 | Requirement IR 唯一事实源 |
| `<sid>.rewritten_intent.json` | 1347 | Rewritten objective |
| `<sid>.requirement_trace.json` | 862 | requirement traceability |
| `<sid>.product-brief.md` | 1509 | PM brief (auto-generated) |
| `<sid>.prd.md` | **本 PRD** | 修复后含 schema 11 节 |
| `<sid>.contract.md` | 1651 | Sprint contract |
| `<sid>.Contracts.yaml` | 2983 | 结构化合约 |
| `<sid>.task_graph.json` | 11865 | DAG task graph |
| `<sid>.capsule_plan.json` | 115165 | Planner capsule plan (115 KB) |
| `<sid>.coverage_report.json` | 3183 | acceptance coverage 自动校验 |
| `<sid>.acceptance_verdict.json` | 451 | acceptance verdict |
| `<sid>.handoff.md` | 653 | Planner handoff |
| `<sid>.dispatch.md` | 9592 | 本次 dispatch (含 unified-context block) |
| `<sid>.dispatch.md.intent.json` | 4434 | dispatch intent (codex_bridge) |
| `<sid>.dispatch.md.runtime-context.json` | 954 | dispatch runtime context |
| `<sid>.events.jsonl` | 3952 | append-only event log |

### Planner 必须消费的字段

- **Requirement IR** 是唯一事实源（来自 PRD §8 Data Model）：所有视图 (PRD / contract / DAG / handoff) 都从 IR 派生；不允许在 PRD/DAG 处独立写规则。
- **Acceptance Coverage** 在编译期跑：缺失映射时阻断派单（来自 PRD §10 Risks）。
- **Codex bridge 链路**：从 `~/.solar/codex-bridge/from-codex` 进入 + chain-watcher 接管；旧 `~/.solar/harness/codex-bridge` 只作兼容证据。

### 给 Coordinator 的明确指令

- **本次 PM 修复仅补 PRD schema 4 节**：背景 / 用户故事 / 约束 / 架构交接。`validate.sh prd` → PASS。
- **PRD mtime 已刷新**：coordinator 下一 tick 重跑 gate 应当通过；通过后让 sprint 按现有 `handoff_to=planner` 进入 planner（这是 codex bridge smoke test 的正常下游路径，因为它本来就是测试这个链路）。
- **不动 17 份自动产物**：包括 capsule_plan.json (115 KB)、task_graph.json、coverage_report.json、acceptance_verdict.json、Contracts.yaml、handoff.md。

### Codex Bridge Smoke Test 含义

- 本 sprint 是验证 **codex_bridge trusted auto planner handoff** 链路是否能不靠人工就把一个 raw_intent 推到 planner 入口。
- 17 份产物 mtime 集中在 11:55 同一分钟说明：bridge 一次性 emit 全套产物没崩。
- coverage_report + acceptance_verdict 已自动产，说明编译期 gate 已跑。
- **唯一缺失**：PRD schema 11 节模板没匹配 PM gate validator → 本切片修复。
- **修复后应回写到 bridge PRD 模板**：让未来 codex bridge emit 的 PRD 默认含 schema 11 节，避免每次都触发 PM 回溯修 gate（这是 codex bridge 模板的真实 OQ）。

### 未尽事项 / Open Questions（合并自 PRD §10）

- **OQ-bridge-01**：codex bridge PRD 模板应当默认含 schema 11 节，避免每次 emit 都需要 PM 回溯修 gate。**Owner**：codex bridge 模板维护者 / 后续 sprint。
- **OQ-bridge-02**：coverage_report.json 的 verdict 与 acceptance_verdict.json 的 verdict 是否冗余？如果两者并存，谁说了算？**Owner**：bridge schema 设计者。
- **OQ-bridge-03**：handoff.md 只 653 字节，是否过于简短？bridge 自动 emit 的 handoff 是否需要更结构化的 fields？**Owner**：bridge 模板维护者。
- **OQ-bridge-04**：capsule_plan.json 高达 115 KB，里面是否含可瘦身的冗余字段？**Owner**：planner 输出格式 sprint。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。Capability injection 含 Codex Bridge skill（本 sprint 是该能力的 smoke test）。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context), harness-intent (intent-20260525-155538-44d6838383 复用，不重新 capture)。
