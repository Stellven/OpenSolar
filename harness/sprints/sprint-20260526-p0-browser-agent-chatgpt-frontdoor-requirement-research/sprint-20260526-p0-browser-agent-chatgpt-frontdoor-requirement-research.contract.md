# Contract

## Name
Browser Agent ChatGPT Frontdoor Requirement Research

## Goal
让 solar-harness 处理任何正式需求时，都先通过 Browser Agent 在 ChatGPT 月份项目中完成需求研究，并把整会话研究结果作为 requirement compile 的标准输入，随后继续推进直到需求完成。

## Done
- [ ] D1 建立统一前门 contract：任意入口都会先进入 requirement research router。
- [ ] D2 Browser Agent 能在 ChatGPT 中定位或创建 `需求研究-YYYY-MM` 项目。
- [ ] D3 研究执行后可抽取整会话 messages，而不是单条回答。
- [ ] D4 研究结果写入 machine-readable research artifact，并保留 conversation_id/source_url。
- [ ] D5 requirement compile 显式消费 research artifact，并写入 product-brief/prd/requirement_ir source_inputs。
- [ ] D6 planner handoff / task_graph / builder 主链保持正常，不因研究前置而断链。
- [ ] D7 workflow guard 阻止旧入口绕过前门。
- [ ] D8 至少完成 Codex / PM pane / Antigravity 三类入口验证。

## Invariants
- ChatGPT 需求研究必须进入 `需求研究-YYYY-MM`
- 不得把需求研究散落到任意临时聊天
- 不得只保留最终回答，必须保留整会话
- 不得在日志写 cookie/token/oauth/header/session secret
- 研究完成不等于需求完成；必须继续推进后续 DAG

## Stop Rules
- 如果 Browser Agent 不能稳定进入目标项目，不允许报完成
- 如果只抓到了单回答，没有整会话，不允许报完成
- 如果 compile 没有消费 research artifact，不允许报完成
- 如果入口仍可绕过前门，不允许报完成

## Interfaces
- Inputs:
  - codex request
  - pm pane request
  - antigravity request
- Outputs:
  - research artifact
  - requirement package
  - planner handoff

## Verification
- Browser Agent live test
- Artifact schema validation
- compile integration test
- ingress routing regression
