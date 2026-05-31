# 对 Solar Harness 做一轮架构收口，目标是降低接入新大模型供应商和新型号时的边际成本。必须把统一 selector、provider adapter

## 1. Problem
对 Solar Harness 做一轮架构收口，目标是降低接入新大模型供应商和新型号时的边际成本。必须把统一 selector、provider adapter registry、以及 actor 从 physical operator 派生这三件事设计并拆成可落地迁移路径。需要识别并消除当前调度、provider 适配、actor registry 三套分裂实现中的硬编码与漂移点，形成正式的 PRD、contract、task DAG、handoff，并为后续实现保留兼容迁移与验证门禁。重点包括：1）所有调度入口统一走单一 selector；2）provider 级认证、quota、error classification、command builder 下沉到 adapter registry；3）actor 不再手工重复维护，而是从 physical operator 或 templ

## 2. Users / Stakeholders
- PM
- Planner
- Builder
- Evaluator

## 3. Goals / Non-goals
Goals:
- 对 Solar Harness 做一轮架构收口，目标是降低接入新大模型供应商和新型号时的边际成本。必须把统一 selector、provider adapter registry、以及 actor 从 physical operator 派生这三件事设计并拆成可落地迁移路径。需要识别并消除当前调度、provider 适配、actor registry 三套分裂实现中的硬编码与漂移点，形成正式的 PRD、contract、task DAG、handoff，并为后续实现保留兼容迁移与验证门禁。重点包括：1）所有调度入口统一走单一 selector；2）provider 级认证、quota、error classification、command builder 下沉到 adapter registry；3）actor 不再手工重复维护，而是从 physical operator 或 templ

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
- 当前请求缺少显式 success metric，需在 PRD 中补齐。

## 11. Release Plan
先交付后端编译底座，再逐步扩展 PM pane UI 与 eval loop。
