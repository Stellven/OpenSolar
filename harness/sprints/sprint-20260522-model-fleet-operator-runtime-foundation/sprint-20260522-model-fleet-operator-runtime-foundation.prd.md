# PRD: Model Fleet Operator Runtime Foundation

Sprint: `sprint-20260522-model-fleet-operator-runtime-foundation`
Owner: Mac mini `solar-harness`
Priority: P0

## Summary

把 tmux headless pane 从“终端窗口”升级为 `Pane-as-Physical-Operator`：每个可运行、可观测、可限额、可失败转移、可被 DAG 选择的模型执行端，都注册成标准物理执行算子。

本 sprint 只做 foundation：扩展 registry/schema、补 runtime state/lease 结构、让 DAG 支持逻辑算子需求到 physical operator 的选择、让全局 monitor 能按 operator/pane/sprint 总览。完整 `operatord run <operator_id>` 守护壳作为下一阶段，不在本 sprint 强行替换现有 runner。

## Problem

当前 `physical-operators.json` 已能表达一批 operator，但仍偏“模型路由配置”，不足以支撑用户提出的 Model Fleet Operator Runtime：

- DAG 仍可直接偏向 `preferred_operator`，缺少标准 `task_type + required_capabilities + preferred_operator_classes` 的逻辑选择模型。
- registry 字段还不完整：缺少 surface/auth/quota/state/metrics/routing/policy 的标准 schema。
- pane runtime 状态、租约、quota/auth error、cooldown 等还没有作为一等状态机。
- monitor bridge 已有全局视图，但还需要按 operator class / runtime state / ready queue / blocker 做调度总览。
- 旧 `status.json` 漂移仍可能污染“哪些算子正在忙”的判断，需要 graph-effective 状态优先。

## Goals

1. 定义 Model Fleet Operator Runtime 的最小可执行 schema。
2. 扩展并兼容现有 `harness/config/physical-operators.json`。
3. 增加 operator runtime state/lease/quota/policy 的读写基础设施。
4. 让 multi-task scheduler 支持逻辑任务需求选择 physical operator。
5. 升级 global monitor 输出 operator fleet 总览。
6. 产出验收报告，明确下一阶段 `operatord` 设计。

## Non-Goals

- 不在本 sprint 替换所有 pane 启动方式为 `operatord run`。
- 不把真实 API key 写入 registry。
- 不启用未验证的 Antigravity 写代码能力。
- 不改动 ThunderOMLX 缓存策略。
- 不自动 kill tmux window 或删除历史 task 目录。

## Requirements

### R1 Operator Registry Schema

新增或扩展 schema，支持字段：

- `physical`: backend/session/window/pane_ref/pane_title/cwd
- `surface`: type/tool/launch_cmd
- `model`: provider/model_id/alias/config
- `endpoint`: base_url/region/api_version
- `auth`: mode/account_label/secret_ref/key_env/expose_raw_key_to_pane
- `quota`: period/enabled_at/refresh_at/remaining_estimate/reserve_for/on_exhausted
- `capability`: planning/coding/debugging/testing/research/browser/shell/long_context/speed/cost_efficiency/reliability
- `policy`: write_files/run_shell/network/secrets_access/git_commit/allowed_repos
- `state`: availability/runtime_state/last_heartbeat_at/last_success_at/last_error
- `metrics`: avg_latency_sec/task_success_rate_7d/tool_error_rate/hallucination_incidents
- `routing`: primary_task_types/avoid_task_types/operator_class

兼容要求：旧字段 `profile`, `role`, `provider`, `model`, `enabled`, `available`, `preferred_for` 仍可读取。

### R2 Logical Operator Selection

DAG node 可以写：

```yaml
task_type: ARCH_DESIGN
required_capabilities:
  planning: ">=5"
  long_context: ">=4"
preferred_operator_classes:
  - DeepArchitect
constraints:
  max_cost_tier: high
  privacy: repo_private
verifier_required: true
```

Scheduler 选择时优先使用 logical requirements；`preferred_operator` 仍保留为硬指定覆盖。

### R3 Runtime State and Lease

实现最小状态机：

`created -> warming -> idle -> leased -> running -> draining -> idle`

异常状态：

`error`, `quota_exhausted`, `auth_expired`, `cooldown`, `disabled`, `stale_context`, `needs_human_review`

租约必须包含：

- `operator_id`
- `task_id`
- `sprint_id`
- `node_id`
- `leased_at`
- `expires_at`
- `state`

### R4 Secret Safety

- registry 只保存 `secret_ref`，不保存 raw key。
- logs/status/global bridge 不输出 key/token/cookie/OAuth。
- 若发现 `expose_raw_key_to_pane=true`，默认 warning，除非本地 operator 且合约显式允许。

### R5 Global Monitor

`global.latest.json` 必须补充：

- `operator_fleet`: 每个 operator 当前 runtime_state、availability、active_task、quota_guard、last_error
- `operator_class_counts`
- `ready_by_task_type`
- `blocked_by_reason`
- `stale_or_drift_count`

### R6 Tests and Evidence

必须有测试覆盖：

- schema loader 兼容旧 registry
- logical selector 能按 task_type/capability/class 选 operator
- quota/reserve/policy 能阻止低价值任务占用强模型
- lease 防止两个 DAG node 抢同一 operator
- global monitor 不被旧 `status.json` running 污染
- secret_ref 不泄露

## Acceptance

- `python3 -m pytest` 对新增测试通过。
- `solar-harness multi-task status --no-clear --renderer plain` 仍可运行。
- 现有 GEPA sprint 不被中断。
- Mac mini `/Users/lisihao/.solar/harness/run/monitor-bridge/global.latest.json` 可看到 operator fleet 汇总。
- 最终报告写入 `/Users/lisihao/.solar/harness/monitor-reports/model-fleet-operator-runtime-foundation.md`。

