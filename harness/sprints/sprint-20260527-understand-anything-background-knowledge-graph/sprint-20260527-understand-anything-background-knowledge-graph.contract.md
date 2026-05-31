# Contract: Understand-Anything Background Knowledge Graph

sprint_id: `sprint-20260527-understand-anything-background-knowledge-graph`
epic_id: null (standalone runtime execution sprint, 平行于 epic-20260526-...understand-anything 5 sub-sprints)
priority: P1
lane: knowledge-ingest / background-job
handoff_to: builder_main

## Intent

在 `/Users/lisihao/Solar` 上跑一次完整 understand-anything 流水线，**后台非阻塞**产出 knowledge graph (`.understand-anything/knowledge-graph.json` + `meta.json`), 为 `/understand-dashboard / chat / diff / explain / onboard / domain / knowledge` 7 命令提供首份真实数据。

## Required Capabilities

- `bash` / `shell` / `plugin` / `verification` / `long-running-task` / `docs`
- 后台执行: `nohup` / `tmux new-window -d` / `caffeinate -i` / `subprocess.Popen(start_new_session=True)` 至少其一
- understand-anything plugin (Lum1104/Understand-Anything via Claude CLI)

## Acceptance (per PRD §验收标准 12 ACs)

- AC-1..AC-4: U1 preflight 4 项全过或停止 + U2 后台真启动 + `config.json` 至少写出 + `knowledge-graph.json` 成功生成 + 不要求前台手工 `/understand`
- AC-5..AC-7: U3 验证 JSON parse + meta.json commit/hash + 验证 handoff
- AC-8: U4 handoff 含完成度 + 恢复入口 + 非阻塞策略
- AC-9: 全程不阻塞前台 chain-watcher
- AC-10: 0 仓库代码改动 (只 `.understand-anything/` + sprint handoff)
- AC-11: 0 secret 打印
- AC-12: PRD 存在 + schema PASS + status.json phase 转

## Stop Rules (per PRD §约束)

- 缺 `task_graph.json` 不得派 builder (已有 4 节点 solar.task_graph.v1)
- 缺可复现验证不得 passed
- 任一节点 acceptance 不过 → 不进下一节点
- 不动 `~/.solar/harness/lib/` / `tools/` / `schemas/` / `templates/` / `~/.claude/plugins/` 源
- 不动 `~/.claude/settings*.json` / Solar 仓库源代码
- U2 必须真后台 (`nohup` / `tmux new-window -d`); 不允许前台 blocking
- 增量恢复优先: 检测到 `.understand-anything/state.json` 或 `intermediate/*` 时不无脑 `--rebuild`
- 不打印 secrets (OAuth code / API key / token redact)
- 不重启 Solar Harness / coordinator / chain-watcher / 4-pane

## Required Phases (per task_graph 4-node DAG)

- U1 preflight_runtime (4 项检查)
- U2 run_understand_zh_background (后台启动 + 增量恢复)
- U3 verify_graph_artifacts (JSON parse + meta.json 字段)
- U4 handoff_resume_contract (完成度 + 恢复入口)

## Coordination Notes

- 与 epic-20260526-...understand-anything 5 sub-sprints **平行**, 本 sprint 是 runtime execution (跑真数据), 不重做 S01-S05 spec 工作
- 与 sprint-20260523-lease-based-model-fleet-runtime 协同: U2 应当独立 actor lease
- 事件 seq 6/13/17/20 显示 `pane_not_idle` 反复失败 — TUI Pane Recover sprint (S03 core-runtime) 实施后稳定
