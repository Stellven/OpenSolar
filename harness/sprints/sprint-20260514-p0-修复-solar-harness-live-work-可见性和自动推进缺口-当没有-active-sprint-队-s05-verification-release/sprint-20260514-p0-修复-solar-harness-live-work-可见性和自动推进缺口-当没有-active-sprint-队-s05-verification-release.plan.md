# Plan — Solar-Harness Live-Work Visibility · S05 Verification & Release

Sprint: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s05-verification-release`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Priority: `P0`
Lane: `reliability`
Planner: `Codex recovery after planner pane stalled after design.md`

## Goal

把 S01-S04 的 live-work 可见性与自动推进能力收口成可复现的端到端验证、负控、activation-proof、回归报告、用户文档和 epic close gate，不允许用“看起来完成”替代证据。

## Upstream Dependencies

- S01 requirements: passed
- S02 architecture: passed
- S03 core-runtime: passed
- S04 orchestration-ui: passed

## Execution Strategy

- `N1`、`N2`、`N3`、`N4` 可并行执行，write_scope 完全互斥。
- `N5` 是 join node，必须等 `N1-N4` 全部 passed 后才可派发。
- S05 是验证/发布切片，默认不修改实现层：`lib/livework`、`status-server/routes`、`autopilot/hooks`、`templates`、`static` 均为只读。
- 若发现实现 bug，写入 handoff 的 follow-up sprint，不在 S05 中绕过 stop rule。

## Nodes

| Node | Goal | Gate | Output |
|---|---|---|---|
| N1 | 端到端用户流 e2e，覆盖 5 outcome happy path，真 HTTP status-server fixture | e2e-pass | `tests/livework/test_e2e_user_flow.py` |
| N2 | 负控套件，覆盖 5 个降级场景 | negative-pass | `tests/livework/test_negative_control.py` |
| N3 | activation-proof 脚本 + 事件日志 + replay 测试 | activation-pass | `autopilot/integration/activation_proof.sh`, `tests/livework/test_activation_proof_replay.py`, `~/.solar/logs/livework-activation-proof-<date>.jsonl` |
| N4 | 回归报告 + accepted raw 知识入库 | regression-pass | `~/.solar/reports/livework-regression-<date>.md`, `<sprint>.accepted.md` |
| N5 | 用户文档 + epic close gate + final handoff + traceability final patch | release-pass | `~/.solar/docs/livework-user-guide.md`, `<epic>.epic-close-gate.md`, `<sprint>.handoff.md`, traceability `epic.gates_all_passed` |

## Verification

- `python3 -m pytest tests/livework/test_e2e_user_flow.py -q`
- `python3 -m pytest tests/livework/test_negative_control.py -q`
- `python3 -m pytest tests/livework/test_activation_proof_replay.py -q`
- `python3 -m pytest tests/livework -q`
- `python3 lib/graph_scheduler.py validate sprints/<sid>.task_graph.json`
- `grep -R "@mock.patch\\|unittest.mock" tests/livework/test_e2e_user_flow.py tests/livework/test_negative_control.py tests/livework/test_activation_proof_replay.py` must return no matches.

## Stop Rules

- S05 must not edit implementation files under `lib/livework`, `status-server/routes`, `autopilot/hooks/livework_heartbeat_*`, `status-server/templates/livework_panel.html`, or `status-server/static/livework_panel.js`.
- N5 cannot dispatch before `N1-N4` are passed.
- Parent epic cannot close until all five child sprints have their `*_ready` fields true.
- Handoff must not claim `全部功能上线`、`无未闭环`、`epic 完美完成`.

## Done

S05 is done only when all graph gates are passed, final handoff and eval artifacts exist, accepted markdown is available for knowledge ingestion, and the parent close gate explicitly records go/no-go evidence.
