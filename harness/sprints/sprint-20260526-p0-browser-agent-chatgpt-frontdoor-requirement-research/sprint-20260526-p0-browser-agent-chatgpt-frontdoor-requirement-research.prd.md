# PRD

## 1. Problem

Solar 的需求入口分散，需求研究前置动作并不统一。用户可能从 Codex、PM pane、Antigravity 等任意入口发需求，但当前流程不能保证所有需求都先经过统一研究，也不能保证 ChatGPT 会话在固定项目下按月份归档。

## 2. Goals

- 把任意入口统一接入同一条需求研究前门
- 用 Browser Agent 在 ChatGPT 中执行需求研究
- 把研究会话规整到 `需求研究-YYYY-MM`
- 把整会话研究结果结构化接入 requirement compile
- 保证研究后能继续推进到 Planner / task_graph / Builder / Evaluator

## 3. Non-goals

- 不扩展到除 ChatGPT 以外的研究后端
- 不设计多种项目命名策略
- 不在本轮构建复杂的人审界面

## 4. User Scenarios

### 4.1 Codex 入口

用户在 Codex 直接说“给我开单/做需求”，系统先调用 Browser Agent 去 ChatGPT 月份项目做研究，然后把研究结果喂给 requirement compile。

### 4.2 四分屏 PM pane

用户或上游系统把需求送到 PM pane 时，PM 不直接写 PRD，而是先触发 Browser Agent 前置研究，再产出 PRD。

### 4.3 Antigravity 入口

Antigravity 接到需求后，也必须走同一个研究前门，而不是绕过研究直接产出 handoff。

## 5. Functional Requirements

1. 任意入口需求进入统一 frontdoor router。
2. frontdoor router 必须调用 Browser Agent logical operator。
3. Browser Agent 必须在 ChatGPT 中定位或创建 `需求研究-YYYY-MM` 项目。
4. 研究完成后必须抽取整会话消息，而不是只抓最终回答。
5. 研究结果必须写成 machine-readable research artifact。
6. requirement compile 必须消费该 artifact。
7. 后续继续走 PM/Planner/task_graph 主链，不允许停在研究完成。

## 6. Non-functional Requirements

- 入口无关：不同 source channel 行为一致
- 可追溯：conversation_id / source_url / artifacts 必须保留
- 可恢复：Browser Agent 中断后可重新附着到会话或重建研究任务
- 账号安全：不泄露 cookie/token/session secret

## 7. Data / Artifact Model

研究产物至少包含：

- raw_request
- ingress_channel
- chatgpt_project
- conversation_id
- source_url
- captured_at
- messages[]
- summary
- constraints[]
- risks[]
- open_questions[]
- recommended_decomposition[]

## 8. Acceptance

- 任意入口前门统一
- 月份项目命名生效
- 整会话抽取生效
- requirement_ir / product brief / prd 引用 research artifact
- Planner handoff 不断裂

## 9. Risks

- Browser Agent 在 ChatGPT 项目 UI 上的稳定性
- 旧入口逻辑绕过统一前门
- 研究结果 schema 不稳定导致 compile 链消费失败

## 10. Release Plan

先完成前门 contract 和 artifact schema，再接 Browser Agent orchestration，再接 compile 消费与 E2E 验证。
