# RawIntent Consumer Request - [entrypoint_metadata]

## 1. Problem
# RawIntent Consumer Request - [entrypoint_metadata] ## Source - intent_id: intent-20260525-155416-c7d24d4b84 - channel: pm_dispatch - actor: user - device: mac_mini_pm_dispatch - thread_ref: ## Rewritten Objective [entrypoint_metadata] ## Problem [entrypoint_metadata] sprint_id: N/A node_id: N1 role: builder [raw_request] PM trusted auto planner handoff smoke 1779724456 ## Constraints - All execu

## 2. Users / Stakeholders
- PM
- Planner
- Builder
- Evaluator

## 3. Goals / Non-goals
Goals:
- # RawIntent Consumer Request - [entrypoint_metadata] ## Source - intent_id: intent-20260525-155416-c7d24d4b84 - channel: pm_dispatch - actor: user - device: mac_mini_pm_dispatch - thread_ref: ## Rewritten Objective [entrypoint_metadata] ## Problem [entrypoint_metadata] sprint_id: N/A node_id: N1 role: builder [raw_request] PM trusted auto planner handoff smoke 1779724456 ## Constraints - All execu

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

- 本 sprint 是 **PM trusted auto planner handoff smoke test (entrypoint_metadata variant)**：intent-20260525-155416-c7d24d4b84 由 `channel=pm_dispatch` (actor=user, device=mac_mini_pm_dispatch) 注入，自动产 raw_intent → requirement_ir → rewritten_intent → product-brief → PRD → contract → Contracts.yaml → task_graph → coverage_report → acceptance_verdict → handoff 全套 artifact。
- 时间：2026-05-25 15:54；唯一标识：`smoke 1779724456`。这是 PM dispatch 入口的 entrypoint_metadata 模板验证（与同日 11:55 的 `sprint-20260525-155538-intent-execution-contract-44d68383` codex_bridge 入口 smoke 是姊妹关系，验证不同 channel）。
- PRD 缺 schema 必需 4 节（背景/用户故事/约束/架构交接），coordinator gate_prd_schema 触发回溯，本次 dispatch 是 PM 修复入口。
- Sprint 状态：`drafting / prd_ready / handoff_to=planner`；contract / Contracts.yaml / coverage_report / acceptance_verdict / handoff / task_graph 全部已存在，证明 PM dispatch entrypoint compile 已经跑过。
- 本切片唯一任务：补足 PRD schema 4 节，让 gate PASS；不动其他 14 份自动产物。

## 用户故事 / User Stories

- **US-01 (PM dispatch entrypoint 维护者)**：作为 PM dispatch entrypoint 维护者，当用户在 mac_mini_pm_dispatch 入口提交一个 raw_intent，我希望 Solar Harness 自动产 PRD/contract/task_graph，**并且这套自动产物能通过 PM gate_prd_schema**，让链路不被人工干预阻断。
  - 验收：本次 PM 修复后 `validate.sh prd` → PASS，未来 pm_dispatch 模板要把 4 缺失节预填进去（与 codex_bridge 同问题）。
- **US-02 (Planner)**：作为下游 Planner，我希望从本 PRD 能拿到 Requirement IR / coverage_report / acceptance_verdict / Contracts.yaml 的路径，不要再人工反向解析自动产物。
  - 验收：架构交接节列出所有自动产物路径。
- **US-03 (Coordinator gate)**：作为 coordinator gate，本 sprint 在 gate 上不再循环。
  - 验收：PRD schema PASS + PRD mtime 刷新触发 coordinator 重跑 gate。
- **US-04 (未来 entrypoint 模板)**：作为 entrypoint 模板设计者，看本次回溯修复后的 PRD 知道未来模板必须含哪 11 schema 节。
  - 验收：本 PRD 已含全部 schema 节，可作为 entrypoint PRD 模板蓝本。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane。PM dispatch channel 入口（与 codex_bridge / cli_intake 等并列）。
- **路径白名单**：本切片只允许修改 `<sid>.prd.md` 和重渲染 `<sid>.prd.html`；禁动 raw_intent / requirement_ir / rewritten_intent / product-brief / contract / Contracts.yaml / task_graph / coverage_report / acceptance_verdict / handoff / requirement_trace。
- **保留 14 份自动产物**：本 sprint 是 smoke test 自动产物链；不允许重写这些产物，只允许追加缺失 schema section。
- **不触发 builder**：sprint 当前 `handoff_to=planner`；PM 只修 PRD schema，不动 status 到 implementation。
- **API 兼容**：pm_dispatch → solar-harness 自动产物链路必须照常工作；本切片不引入字段变更。
- **不打印 secrets**：raw_intent 已 redact，本切片任何引用都不允许重新展开 token / API key / OAuth code / 用户手机号 / 邮箱。
- **PM 角色边界**：不写代码、不动其他 14 份自动产物、不改 planner / builder / evaluator 调用。

## 架构交接 / Planner Handoff

### Inputs to Planner（全部 14 份自动产物 + 本 PRD）

| Artifact | 用途 |
|----------|------|
| `<sid>.raw_intent.json` | pm_dispatch 注入原始意图 (intent-20260525-155416-c7d24d4b84, channel=pm_dispatch) |
| `<sid>.requirement_ir.json` | Requirement IR 唯一事实源 |
| `<sid>.rewritten_intent.json` | Rewritten objective |
| `<sid>.requirement_trace.json` | requirement traceability |
| `<sid>.product-brief.md` | PM brief (auto-generated) |
| `<sid>.prd.md` | 本 PRD (修复后含 schema 11 节) |
| `<sid>.contract.md` | Sprint contract |
| `<sid>.Contracts.yaml` | 结构化合约 |
| `<sid>.task_graph.json` | DAG task graph |
| `<sid>.coverage_report.json` | acceptance coverage 自动校验 |
| `<sid>.acceptance_verdict.json` | acceptance verdict |
| `<sid>.handoff.md` | Planner handoff |
| `<sid>.dispatch.md` | 本次 dispatch (含 unified-context block) |
| `<sid>.dispatch.md.intent.json` + `.runtime-context.json` | dispatch 元数据 |

### Planner 必须消费的字段

- **Requirement IR** 是唯一事实源（PRD §8 Data Model）：所有视图 (PRD / contract / DAG / handoff) 从 IR 派生。
- **Acceptance Coverage** 在编译期跑：缺失映射时阻断派单（PRD §10 Risks）。
- **pm_dispatch 链路**：与 codex_bridge / cli_intake 并列；统一 channel taxonomy。

### 给 Coordinator 的明确指令

- **本次 PM 修复仅补 PRD schema 4 节**：背景 / 用户故事 / 约束 / 架构交接。`validate.sh prd` → PASS。
- **PRD mtime 已刷新**：coordinator 下一 tick 重跑 gate 应当通过；通过后让 sprint 按现有 `handoff_to=planner` 进入 planner（这是 smoke test 正常下游路径）。
- **不动 14 份自动产物**。

### PM Dispatch Smoke Test 含义

- 本 sprint 是验证 **PM dispatch entrypoint trusted auto planner handoff** 链路：从 `channel=pm_dispatch` 入口推 raw_intent 后能否一次性自动产全套 + 通过 PM gate。
- 与同日 11:55 codex_bridge entrypoint smoke (`sprint-20260525-155538-...`) 是不同入口的姊妹 smoke：验证 entrypoint taxonomy 多通道兼容。
- 14 份产物落盘 + coverage_report + acceptance_verdict 已自动产，说明编译期 gate 已跑。
- **唯一缺失**：PRD schema 11 节模板没匹配 PM gate validator → 本切片修复。
- **修复后应回写到 entrypoint PRD 模板**：让未来 pm_dispatch entrypoint emit 的 PRD 默认含 schema 11 节，避免每次都触发 PM 回溯修 gate（同 codex_bridge OQ-bridge-01 性质，本 sprint 命名为 OQ-entrypoint-01）。

### 未尽事项 / Open Questions（合并自 PRD §10）

- **OQ-entrypoint-01**：pm_dispatch / codex_bridge / cli_intake 等多个 entrypoint 共享同一 PRD 模板，应当默认含 schema 11 节，避免每次 emit 都需要 PM 回溯修 gate。**Owner**：entrypoint 模板维护者 / 后续 sprint。
- **OQ-entrypoint-02**：channel taxonomy（pm_dispatch / codex_bridge / cli_intake / antigravity / claude_code / ...）是否需要 cross-entrypoint smoke matrix？现在只跑了 codex_bridge 和 pm_dispatch 两个。**Owner**：smoke matrix 设计。
- **OQ-entrypoint-03**：entrypoint_metadata 字段（actor / device / thread_ref）的 schema 是否需要 versioned？现在用法不统一。**Owner**：entrypoint schema 设计。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。Capability injection 含 solar-intent-engine（本 sprint 是 intent entrypoint smoke）。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context), harness-intent (intent-20260525-155416-c7d24d4b84 复用，不重新 capture)。
