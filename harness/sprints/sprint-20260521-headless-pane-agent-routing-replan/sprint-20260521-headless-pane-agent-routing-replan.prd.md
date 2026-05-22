# PRD: Solar-Harness tmux 无头 pane 执行能力重规划

epic_id: `epic-20260521-headless-agent-runtime`
sprint_id: `sprint-20260521-headless-pane-agent-routing-replan`
priority: `P0`
lane: `runtime-orchestration`
owner: `solar-harness`
target_runtime: `Mac mini /Users/lisihao/.solar/harness`

## 0. Executive Summary

Solar-Harness 的 tmux 无头 pane / multi-task worker pool 需要从“固定角色 + 单一模型后端”升级为“按任务类型选择最合适 agent 工具链”的调度层。

核心结论：

- Claude Code 仍作为复杂工程改造、架构推演、debug、底层系统修复的主力。
- Codex 作为 PM 协调器、跨工具执行、需求到交付、研究到产物的工作台。
- Antigravity 2.0 + Gemini 3.5 Flash 作为高吞吐并行实验、Google/Android/Firebase 生态任务的新后端候选，但当前处于迁移期，必须 gated rollout。
- ThunderOMLX 继续承担低成本本地粗活：知识抽取、批量总结、缓存 benchmark、可容忍较低推理深度的后台任务。

本 sprint 的目标不是立刻全量替换 worker，而是产出可执行的无头 pane 能力重规划：角色矩阵、后端路由、并行度策略、失败降级、配置变更方案、验证计划和后续实现 DAG。

## 1. 背景

用户要求将 solar-harness 的 tmux 无头 pane 执行能力重新规划，按照三类工具的真实定位来分工：

```text
Claude Code = 主工程师：复杂工程、架构、debug、系统研究
Codex       = 工程办公室：PRD、DAG、跨工具执行、文档/测试/交付
Antigravity = 并行实验场：高速多代理、Google 生态、Managed Agents
ThunderOMLX = 本地低成本 worker：知识抽取、批处理、缓存友好任务
```

现状中，multi-task 已经可以在 Mac mini 上用 tmux headless worker pool 执行 DAG，但角色、模型、backend、并行度和失败降级还没有按照上述工具分工系统化。

## 2. Problem

当前问题：

- `preferred_profile` 仍偏静态，无法表达“任务类型 -> 最佳 agent 工具链 -> 并行度 -> 降级后端”的策略。
- 四分屏和无头 pane 的角色配置存在历史耦合，容易出现“看起来路由到某 pane，实际 backend 不一致”。
- Antigravity CLI 刚安装，远端 OAuth 尚未完成；不能直接设为 production backend。
- Gemini CLI 处于迁移期，后续可能被 Antigravity CLI 替代；当前 profile 需要兼容和迁移计划。
- Claude 成本高，不应该承担知识抽取、批量归档等粗活。
- ThunderOMLX 适合粗活，但不能承担高风险架构评审、复杂 debug、review gate。
- multi-task status 需要清晰展示每个 sprint 的说明、角色、backend、模型、node 状态、blocker 和下一步。

## 3. Goals

P0:

- 产出 headless worker 能力矩阵：角色、任务类型、首选工具、备用工具、并行度、成本等级、风险等级。
- 产出 profile/route 设计：`pm`、`planner`、`architect`、`builder`、`debugger`、`evaluator`、`knowledge-extractor`、`experimenter`、`google-ecosystem-builder` 等角色如何映射到 Claude/Codex/Antigravity/ThunderOMLX/Gemini。
- 产出 multi-task DAG 并行策略：哪些任务可并发，哪些任务必须串行，哪些后端需要 single-lane。
- 产出迁移方案：Gemini CLI -> Antigravity CLI 的 gated rollout；未登录时保持 disabled/pending，不影响主流程。
- 产出验收 smoke：profile probe、headless dispatch、status render、fallback、监控推进。

P1:

- 形成可实现的配置变更清单：`harness/config/multi-task-profiles.json`、runner fallback、monitor/status rendering、doctor/probe。
- 形成安全边界：不打印 token，不自动绕过 OAuth，不把未验证 Antigravity 当 ok。

## 4. Non-Goals

- 不在本 sprint 中强制启用 Antigravity production backend。
- 不把用户提供的 benchmark 数字当作已验证事实；需要标注来源或作为假设。
- 不删除现有 Claude/Gemini/ThunderOMLX profile。
- 不让 Claude 处理知识抽取类低价值高 token 消耗任务。
- 不绕过 Mac mini OAuth 安全限制。
- 不重启 ThunderOMLX 或修改缓存配置，除非后续 implementation sprint 明确要求。

## 5. Product Requirements

### 5.1 Role Routing Matrix

必须覆盖：

| 任务类型 | 首选 | 备用 | 备注 |
| --- | --- | --- | --- |
| PRD/合同/DAG/交付协调 | Codex PM coordinator | Claude planner | Codex 负责闭环和跨工具 |
| 复杂架构/底层系统设计 | Claude Opus high/xhigh | Codex GPT-5.5 | Claude 做主审，Codex 整理和执行 |
| 复杂 debug/root cause | Claude Code | Codex | Claude 推因果，Codex 复现和跑验证 |
| 多文件实现/测试/PR | Codex + Claude worker | Claude Code | Codex 分支执行，Claude 评审难点 |
| 多路线并行实验 | Antigravity | Codex multi-agent | Antigravity 需 OAuth/可用性 gate |
| Android/Firebase/Google Cloud | Antigravity | Gemini/Codex | Google 生态优先 Antigravity |
| 知识抽取/批量总结 | ThunderOMLX | Gemini Flash/Lite | Claude 禁止默认承担 |
| cache/benchmark 粗活 | ThunderOMLX | Codex shell worker | 本地成本优先 |
| 最终评审/高风险 gate | Claude Opus | Gemini/Codex reviewer | 需要质量而非速度 |

### 5.2 Headless Pane Pool Strategy

必须给出：

- 默认 pool 并行度：按机器资源、后端限制和任务类型确定。
- 后端隔离：ThunderOMLX single-lane 或低并行；Claude 高成本限流；Antigravity 只有 OAuth ok 后启用。
- write_scope 冲突保护：并行节点不能同时写同一模块。
- cost gate：知识抽取、批处理、缓存 benchmark 禁止默认使用 Claude。
- review gate：架构/复杂 debug/安全相关不能只用低成本本地模型通过。

### 5.3 Status / Monitor

必须要求 multi-task status/monitor 输出：

- sprint id + 说明
- node id + role + profile + backend + model
- status + updated_at + active task
- blocker + next action
- 是否可 safe 推进

### 5.4 Antigravity Rollout Gate

Antigravity profile 必须具备：

- `installed=true/false`
- `auth_ok=true/false`
- `model_list_available=true/false`
- `smoke_ok=true/false`
- `enabled_for_dispatch=false` until all gates pass

远端 OAuth 未完成时，profile 必须显示 `warn/pending`，不得假装可用。

## 6. Acceptance Criteria

- 生成 `headless-agent-routing-replan.md` 最终报告。
- 报告包含角色路由矩阵、headless pool 并行策略、profile 变更建议、Antigravity gated rollout、ThunderOMLX/Claude/Codex/Gemini 成本边界。
- 报告明确哪些是已验证事实，哪些是用户输入假设，哪些需要后续联网或实测验证。
- 生成后续 implementation DAG 建议，能直接转成下一轮 sprint。
- 本 sprint 的 task_graph 所有节点 passed。

## 7. Evidence Required

- Mac mini `solar-harness multi-task profiles` 输出摘要。
- Mac mini `solar-harness multi-task doctor` 输出摘要。
- Mac mini `agy --version` / auth 状态摘要，不能打印 token。
- 当前 `harness/config/multi-task-profiles.json` 中相关 profile 摘要。
- 若无法实测某后端，必须标为 `pending` 或 `warn`。

## 8. Risks

- Antigravity CLI SSH OAuth 超时，短期无法作为自动 worker。
- Gemini CLI 迁移期导致 profile 失效。
- Claude 成本过高，误路由会烧 token。
- ThunderOMLX 局部缓存/乱码历史问题要求保守使用，不承担最终评审。
- 多后端并行会增加安全面，必须限制 secret 输出和 write_scope。

## 9. 用户故事 / User Stories

- 作为 Solar-Harness 维护者，我希望每个 headless pane 能按任务类型选择合适后端，这样复杂工程、低成本批处理和并行实验不会全部挤到同一种 worker。
- 作为 coordinator，我希望 profile 里显式记录 backend、model、cost、risk、parallelism 和 fallback，这样派单失败时可以安全换路由，而不是重复轰炸同一个 pane。
- 作为 evaluator，我希望最终评审和高风险 gate 默认使用高质量 reviewer，这样 ThunderOMLX 或未完成 OAuth 的 Antigravity 不会误通过关键变更。
- 作为 operator，我希望 status/monitor 展示 node、role、profile、backend、blocker 和 next action，这样能快速判断是队列未消费、pane 卡住、OAuth 未完成还是 schema 未通过。
- 作为成本控制者，我希望知识抽取、批量总结、缓存 benchmark 默认走 ThunderOMLX 或低成本后端，这样 Claude token 不会被粗活消耗。

## 10. 约束 / Constraints

- 不打印、缓存或转发 API key、OAuth token、refresh token、authorization code。
- Antigravity 在 `installed/auth_ok/model_list_available/smoke_ok` 全部通过之前只能显示为 `pending`，不得进入 production dispatch。
- ThunderOMLX 只能承担低风险批处理、知识抽取、缓存/benchmark 粗活；不能作为唯一 evaluator 或架构 gate。
- Claude Opus/Claude Code 需要限流，默认用于复杂架构、root cause、review gate 和高风险工程修复。
- Codex 负责 PRD、DAG、执行协调、状态收口和跨工具 glue，不替代所有专用 worker。
- 并行 DAG 必须带 write_scope 冲突保护；同一模块或同一 runtime 文件不能被多个节点同时写。
- Mac mini 远端不可达或 SSH/OAuth 未完成时，必须把后端状态标为 `warn/pending`，不能假装通过。

## 11. 开放问题 / Open Questions

- OQ1: Antigravity CLI 在 Mac mini 上的 OAuth、model list 和 smoke 是否能稳定通过？如果不能，何时允许进入 dispatch 候选？
- OQ2: Gemini CLI 迁移到 Antigravity 后，保留哪些 Gemini profile 作为 fallback，哪些应标 deprecated？
- OQ3: ThunderOMLX 的并行度上限应按模型、SSD cache、内存压力还是任务类型计算？
- OQ4: headless pane pool 是否需要按 backend 独立 lease namespace，避免 Claude pane、Codex job 和本地 worker 互相误占？
- OQ5: dispatch validation 当前多次误报失败但 pane 实际收到任务，后续实现是否应改成 ACK 文件、pane output marker 或 activity log event？
- OQ6: status renderer 是否需要区分 “worker 已接单但未写 artifact” 与 “dispatch 未送达” 两种状态？

## 12. 架构交接 / Planner Handoff

Planner 需要把本 PRD 转成可执行 plan 和 task_graph，至少覆盖：

- N1: 读取现有 `multi-task-profiles.json`、runner、dispatcher、monitor/status renderer，画出现状路由图。
- N2: 设计角色路由矩阵，包含 pm/planner/architect/builder/debugger/evaluator/knowledge-extractor/experimenter/google-ecosystem-builder。
- N3: 设计 backend gate schema：Claude/Codex/Antigravity/Gemini/ThunderOMLX 的 readiness、cost、risk、fallback、parallelism。
- N4: 设计 pane/headless pool lease 与 queue ACK 机制，特别处理 dispatch validation 误报、队列重复和 stale lease。
- N5: 产出 `headless-agent-routing-replan.md`，包含已验证事实、用户输入假设、待验证项和后续 implementation DAG。
- N6: 所有节点必须写 handoff，最终 evaluator 检查不得泄露 token，且不得把未验证 Antigravity 标为 production-ready。
