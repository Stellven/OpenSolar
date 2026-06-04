# Design: GitHub Intelligence Orchestration/UI

## 目标

把核心能力接入 autopilot、DAG 调度、multi-task status、pane evidence 和 proof gate，防止“自然语言声称完成”。

## 结构

- `graph_scheduler.py`: parent/child gate sync、eval sidecar、proof obligation。
- `graph_node_dispatcher.py`: pass verdict 必须有 eval sidecar，避免 handoff-only closeout。
- `multi_task_runner.py`: quota-aware fallback、late failure guard、status observability。
- status surface: sprint/epic/node_counts/ready/blocker 显示。

## 边界

本切片不重写 UI 框架，只加现有 status surfaces 和 runtime evidence。
