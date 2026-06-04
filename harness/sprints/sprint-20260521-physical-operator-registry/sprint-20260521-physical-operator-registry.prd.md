# PRD — Solar-Harness Physical Operator Registry

## Summary

把 Mac mini 上每个 tmux 无头 pane 建模为一个固定的“物理执行算子”。每个算子绑定明确的模型厂家、型号、配置、URL、key 引用、配额周期、启用时间、刷新时间、健康状态和适用场景。DAG planner 以后只表达任务需求或 operator selector，不再到处修改 profile/backend/model/env。

## Problem

当前 `solar-harness multi-task` 主要以 `profile/backend/model` 粒度调度。这个粒度太粗：

- 同一模型别名可能在不同文件解析到不同真实模型。
- pane 的真实 URL/key/env 可能和 status 显示不一致。
- 切换模型需要改多处配置，容易造成路由漂移。
- DAG 节点缺少稳定的“物理执行算子”目标，无法按成本、配额、可用性做选择。

## Product Goal

建立统一 operator registry，使调度决策从“profile 字符串”升级为“可审计物理执行算子”。

## Required User Model

1. 每个 tmux 无头 pane 是一个物理执行算子。
2. 每个物理执行算子必须绑定：
   - `operator_id`
   - `pane`
   - `host`
   - `vendor`
   - `backend`
   - `model_id`
   - `model_alias`
   - `model_config`
   - `base_url`
   - `key_ref`
   - `quota_cycle`
   - `enabled_at`
   - `quota_refresh_at`
   - `available`
   - `last_smoke_at`
   - `best_for`
   - `not_for`
3. DAG planner 以后按任务需求选择最优 operator，而不是硬编码 backend/model。
4. 用户可以明确指定“换哪个 operator”，例如把某个节点从 Claude Opus 换到 Antigravity Gemini 3.5 Flash High。

## Initial Operator Taxonomy

```text
┌────────────────────┬──────────────────────────────┬────────────────────────────┐
│ operator class     │ preferred model              │ best_for                   │
├────────────────────┼──────────────────────────────┼────────────────────────────┤
│ claude-opus-review │ Claude Opus                  │ final review, architecture │
│ claude-sonnet-build│ Claude Sonnet                │ implementation, tests      │
│ codex-pm           │ GPT/Codex                    │ PM, cross-tool delivery    │
│ antigravity-flash  │ Gemini 3.5 Flash High        │ parallel experiments       │
│ thunderomlx-qwen36 │ Qwen3.6-35b-a3b              │ knowledge extraction       │
│ gemini-pro         │ Gemini 3.1 Pro high/low      │ Google ecosystem reasoning │
└────────────────────┴──────────────────────────────┴────────────────────────────┘
```

## Functional Requirements

### FR1: Operator Registry

Create a canonical registry file:

```text
~/.solar/harness/config/physical-operators.json
```

It must be readable by `solar-harness multi-task`.

### FR2: Pane Binding

Each operator binds to a stable tmux target:

```json
{
  "operator_id": "mini-op-07-thunderomlx-qwen36",
  "pane": "solar-harness-multi-task:op07",
  "host": "mac-mini"
}
```

The status renderer must show operator identity, not only role/profile.

### FR3: Selector Contract

DAG nodes can specify either:

```json
{"preferred_operator": "mini-op-07-thunderomlx-qwen36"}
```

or:

```json
{
  "operator_selector": {
    "task_type": "knowledge_extraction",
    "risk": "low",
    "cost_ceiling": "low",
    "requires_local": true
  }
}
```

### FR4: Health and Quota

The registry must support:

- `enabled`
- `available`
- `auth_status`
- `quota_status`
- `quota_cycle`
- `quota_refresh_at`
- `last_smoke_at`
- `last_error`

Secrets must not be printed. Only `key_ref` is allowed.

### FR5: Backward Compatibility

Existing `preferred_profile` continues to work. If no operator selector exists, scheduler falls back to current profile selection.

### FR6: Initial Mac Mini Operators

Mac mini should seed at least these operators if available:

- Claude planner/opus
- Claude builder/sonnet
- Claude evaluator/opus
- ThunderOMLX Qwen3.6 local
- Antigravity Gemini 3.5 Flash High

Antigravity must stay gated unless smoke passes.

## Non-Goals

- Do not delete existing profile system.
- Do not print API keys or OAuth tokens.
- Do not auto-enable unsafe ThunderOMLX cache features.
- Do not require four-pane UI to be open.
- Do not migrate all historical task graphs.

## Acceptance Criteria

```text
┌────┬──────────────────────────────────────────────────────────────┐
│ id │ acceptance                                                   │
├────┼──────────────────────────────────────────────────────────────┤
│ A1 │ physical-operators.json exists and validates                 │
│ A2 │ multi-task status shows operator_id/vendor/model/pane         │
│ A3 │ DAG node can choose preferred_operator                        │
│ A4 │ selector can choose operator by task_type/cost/risk           │
│ A5 │ Antigravity operator records auth/smoke and remains gated     │
│ A6 │ ThunderOMLX operator maps to Qwen3.6 and 127.0.0.1:8002       │
│ A7 │ existing profile-only DAG smoke still passes                  │
│ A8 │ final report explains how user switches an operator           │
└────┴──────────────────────────────────────────────────────────────┘
```

