# PRD — Solar Remote Dispatch Productization

## Goal

让 Solar Harness 具备产品级远端执行能力：本地创建合约，Mac mini 远端接单执行，builder/evaluator/DAG gate 自动闭环，本地可追踪和拉回结果。

## Users

- Owner: 想把长任务交给 Mac mini 跑，不想手工盯 SSH/tmux。
- Builder/Evaluator panes: 需要明确、可执行、可恢复的任务上下文。
- Codex operator: 只负责发起和监督，不把手工 SSH 测试冒充为 Solar 执行。

## User Stories

- 作为用户，我可以运行一个命令把 sprint 发到 Mac mini，并知道远端是否真正接单。
- 作为用户，我可以查看远端 sprint 当前在 builder、evaluator、queued、blocked 还是 completed。
- 作为用户，我可以在失败后重试，不制造重复 wake 和状态污染。
- 作为系统，我能校验文件 checksum，避免远端拿到半份合约。
- 作为系统，我能在 parent_ready_check 通过后自动收口 sprint，不需要人工补状态。

## Constraints

- 先支持 Mac mini，设计保留 remote target abstraction。
- 默认不传 secrets。
- 所有状态必须机器可读。
- 不能把一次成功 smoke test 当产品级验收。

## Risks

- tmux TUI 派发可能停在输入框不执行。
- 本地和远端 status/graph 可能漂移。
- 远端 pane 模型环境可能污染，例如 Sonnet 被旧 DeepSeek env 覆盖。
- Mac mini 网络不可达会阻塞最终 e2e。

## Open Questions

- 是否需要把 remote target 配置也接入 8765 status UI 的配置页。
- 是否需要支持多台远端并发 pool。
- 是否要把 remote dispatch 作为 coordinator 默认策略，而不只是 CLI。

## DoD

- Contract D1-D10 全部通过。
- Mac mini e2e smoke 由远端 Solar Harness 完成并拉回本地证据。
- 失败路径有明确 `error|blocked|pending` 状态，不出现假 ok。
