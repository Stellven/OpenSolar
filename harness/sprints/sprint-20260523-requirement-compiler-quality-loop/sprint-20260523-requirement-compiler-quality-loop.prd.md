# 为 PM pane / Requirement Compiler 建立 Quality Loop：以 Requirement IR 为唯一事实源，补齐 gold

## 1. Problem
为 PM pane / Requirement Compiler 建立 Quality Loop：以 Requirement IR 为唯一事实源，补齐 golden set、误分类/误编译 failure replay、planner 修改差异回流、evaluator 驳回原因回流、compile quality metrics 与 gate。要求把需求编译质量从 prompt 经验升级成 schema+contract+validator+eval+feedback 的闭环；不得把 doc-only/contract-only 冒充 implemented；必须兼容现有 PM -> Planner -> Builder 主链，并支持 Codex/Solar handoff 质量评估。首批聚焦后端编译质量底座，不做大规模 UI 重写。

## 2. Users / Stakeholders
- PM
- Planner
- Builder
- Evaluator

## 3. Goals / Non-goals
Goals:
- 为 PM pane / Requirement Compiler 建立 Quality Loop：以 Requirement IR 为唯一事实源，补齐 golden set、误分类/误编译 failure replay、planner 修改差异回流、evaluator 驳回原因回流、compile quality metrics 与 gate。要求把需求编译质量从 prompt 经验升级成 schema+contract+validator+eval+feedback 的闭环；不得把 doc-only/contract-only 冒充 implemented；必须兼容现有 PM -> Planner -> Builder 主链，并支持 Codex/Solar handoff 质量评估。首批聚焦后端编译质量底座，不做大规模 UI 重写。

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
