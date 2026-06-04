# PRD: Pane-as-Physical-Operator Architecture

Sprint: `sprint-20260523-pane-as-physical-operator-architecture`
Owner: `PM pane / Codex`
Priority: `P0`
Lane: `strategy`
Handoff To: `planner`
Created: `2026-05-23T19:06:00Z`

## 背景 / Context

Solar-Harness 在过去 3 个月里已经长出了一组可执行底座：`physical-operators.json` 用来声明物理执行节点，`operator_runtime.py` / `operatord.py` 负责 lease / heartbeat / result，`multi_task_runner.py` 和 `graph_node_dispatcher.py` 已经在跑多 pane 协同。但这些模块是 **逐步堆出来的 foundation**，没有一份正式架构契约把它们绑成同一个心智模型。

与此同时，外部能力（Claude Code Opus 4.7、Codex Bridge、Antigravity、ThunderOMLX 本机推理）在快速并入；如果继续以 `provider/model/profile` 为调度真值，就会出现：

- 任务执行期间临时 `/model` 切换 → quota 误算、auth 漂移、KV cache 失效
- 不同 pane 同时绑同账号 → rate-limit 冲撞
- DAG 节点写死 `claude-opus-4-7` 字符串 → operator 下线后任务直接断裂
- 状态页只能看到“pane 0 在跑什么命令”，看不到“operator X 还剩多少 quota / 是否被授权”

本 sprint 的背景就是：**把 4 pane 架构（pane 0 planner / pane 1 builder / pane 2 evaluator / pane 3 architect）连同所有外部 runtime（Codex CLI、Antigravity、本机推理）一起，统一抽象成 `PhysicalOperator`，并把 DAG / quota / auth / observability 全部收口到 operator 这一层**。这是 Solar-Harness 从 “v2 增量” 走向 “v2 定版” 的必要一步。

参考资产：
- `~/.solar/docs/4-pane-architecture.md`
- `~/.solar/reports/2026-05-03-harness-v2-roadmap.md`
- `~/.solar/harness/lib/physical_operators.py`、`operator_runtime.py`、`operatord.py`、`graph_node_dispatcher.py`
- 历史 sprint：`sprint-20260503-090450 (S-ARCH)`、`sprint-20260502-222433 (S4 Brain Whisper)`

## Summary

把 `tmux` 无头 pane 从“后台终端窗口”正式升级为 `Agent Runtime` 的物理执行算子。

系统以后不再把 `Claude / Codex / Antigravity / ThunderOMLX` 直接当成 DAG 调度对象，而是把每一个“可运行、可观测、可限额、可失败转移、可被 DAG 选择”的执行端，注册成标准 `PhysicalOperator`。

调度单位从：

- `provider/model/profile`

升级为：

- `operator_id`

其中每个 `operator_id` 代表：

- 固定物理宿主（通常是一个 tmux pane）
- 固定模型绑定
- 固定账号/访问方式
- 固定配额时钟
- 固定权限策略
- 固定能力画像
- 固定运行时状态机

## Problem

当前系统虽然已经有 `physical-operators.json`、`operator_runtime.py`、`operatord.py`、`multi_task_runner.py`、`graph_node_dispatcher.py`，但整体仍处于“foundation 已有、正式架构未定版”的状态：

- 很多地方仍在以 `provider/model/profile/backend` 视角思考，而不是以 `operator_id` 视角思考。
- 同一个 pane 可能被当成“终端窗口”而不是“可调度执行资源”。
- runtime、quota、auth、policy、capability、evidence 还没有被完全收口成一套统一 contract。
- DAG 还没有被严格限制为“只能选择 physical operator，而不是临时切模型/改 env”。
- 失败转移、配额保护、权限隔离、长程执行恢复，还缺统一架构边界。

## 用户故事 / User Stories

> 用户 = Solar-Harness 的操盘者（昊哥 / PM pane / Planner / Builder / Evaluator / Autopilot），不是终端最终用户。这里描述的是“架构对操盘者的可用形态”。

- **US1 — 作为 Planner**，我希望我只需要在 task_graph 里写 `required_capabilities` 和 `operator_class`，而不是写死 `claude-opus-4-7` 或 `pane 0`，这样当 operator 调整时我的图不需要重写。
- **US2 — 作为 Builder pane (glm-5.1)**，我希望我接到任务时已经被 lease 锁定到一个 operator_id，期间不会被另一条 DAG 抢走 quota；任务结束我释放 lease，状态机干净回到 `available`。
- **US3 — 作为 Evaluator (pane 2)**，我希望我能拿到 operator 在执行期间的 `EvidenceLog`（lease 时间戳、模型版本、quota 消耗、auth label），这样我才能判断结果是不是在合法 operator 上跑出来的，而不是被偷偷切了模型。
- **US4 — 作为 Architect (pane 3 opus)**，我希望当我做 deliberation 时，scheduler 优先选择 `class=architect` 的 operator，而不是把我安排到 builder 的省钱 operator 上。
- **US5 — 作为 Autopilot**，我希望当 pane 3 busy 时，我能看到“deferred dispatch”原因是 operator busy，而不是只看到一个模糊的“pane 0.1 occupied”；并能根据 quota / auth 状态自动选择 fallback operator。
- **US6 — 作为人类操盘者（昊哥）**，我希望 8765 状态页一眼能告诉我：哪个 operator 在跑哪个 sprint、剩多少 quota、auth 是否快过期、最近一条结果对不对；并且我可以在不停机的情况下 disable 一个 operator。
- **US7 — 作为外部 runtime 集成者（Codex / Antigravity / ThunderOMLX）**，我希望我只要按 schema 注册一行 operator entry，剩下的 lease / quota / observability / 失败转移就自动接入，不需要为每个外部 runtime 写专属胶水。

## Product Goal

正式定版 `Pane-as-Physical-Operator` 架构，使 Solar-Harness 的多模型执行系统形成统一的三层结构：

```text
Operator Registry
  -> Operator Runtime
  -> DAG Scheduler
  -> tmux-backed Physical Operators
```

## Core Design Decision

### D1. 调度对象

DAG 只调度 `PhysicalOperator`，不直接调度模型名称、provider 名称或 CLI wrapper。

### D2. Pane 身份

`tmux` pane 是 operator 的物理宿主，不是独立抽象层的调度对象。

### D3. 模型绑定

一个 operator 一旦注册完成，就视为稳定绑定：

- `ProviderBinding`
- `ModelBinding`
- `AccessBinding`
- `QuotaClock`
- `CapabilityProfile`
- `RuntimeState`
- `PermissionPolicy`
- `EvidenceLog`

任务执行期间不得临时切模型、改 wrapper、改环境变量登录态。

### D4. 变更方式

要换模型，不是“任务里切模型”，而是：

- 新建 operator
- 或更新 registry 后重启 operator

### D5. Secret Safety

registry 只能写 `secret_ref` / `key_env` / `account_label` 之类引用信息，不能写 raw key/token/cookie。

## Functional Requirements

### FR1: Registry 定版

`physical-operators.schema.json` 和 `physical-operators.json` 必须把下列字段收口成正式 schema：

- `physical`
- `surface`
- `model`
- `endpoint`
- `auth`
- `quota`
- `capability`
- `policy`
- `state`
- `metrics`
- `routing`

### FR2: Runtime 定版

`operator_runtime` / `operatord` 必须把 operator 当成正式 runtime resource，而不是临时脚本路由：

- lease
- heartbeat
- runtime_state
- auth/quota override
- result artifacts
- failure isolation
- drain/cooldown

### FR3: Scheduler 定版

DAG Scheduler 必须依据这些条件选择 operator：

- task_type
- required_capabilities
- preferred_operator_classes
- policy constraints
- quota reserve
- runtime_state
- verifier separation

### FR4: No Drift Rule

正式链路禁止以下行为：

- 在任务中临时 `/model`
- 临时改 provider wrapper
- 临时改 auth 方式
- 直接把 DAG 节点绑到 provider/model 字符串而不是 `operator_id`

### FR5: Observability

状态面必须能展示：

- operator fleet 摘要
- dispatchable / busy / disabled / quota / auth 状态
- recent results
- alerts
- active lease / sprint / task

### FR6: Backward Compatibility

旧字段和旧任务图在迁移期仍可运行，但新架构必须规定：

- `preferred_operator` 是显式硬指定
- 逻辑调度优先表达为 operator requirements
- provider/model/profile 只作为兼容输入，不作为长期调度真值

## PM DAG Input

以下是 PM 给 Planner 的建议切片，不是最终 `task_graph.json` 真值：

### Workstream A: Registry Lock

- schema 扩展与兼容规则
- secret_ref / auth / quota / policy / routing 字段定版

### Workstream B: Runtime Lock

- operator lifecycle
- lease / heartbeat / result / failure transfer
- `available`、`quota_exhausted`、`auth_expired` 等状态统一来源

### Workstream C: Scheduler Lock

- 从 `task_type/capability/class` 到 `operator_id` 的选择逻辑
- verifier 与 writer 分离
- quota reserve / policy guard

### Workstream D: Observability Lock

- 8765 状态页 / status payload / operator fleet 统一观测
- recent results / alerts / runtime drift 证据

### Workstream E: Migration and Safety

- 旧 profile/backends 兼容
- 禁止运行中模型漂移
- rollout / fallback / rollback strategy

## Non-Goals

- 本 sprint 不要求一次性删除所有旧 profile 流程。
- 不要求立刻替换所有历史 DAG。
- 不要求在本 sprint 中启用所有 disabled operator。
- 不允许把 raw secret 写进 registry / log / status / report。
- 不允许把 tmux pane 继续当“可任意临时切模型”的通用壳。

## 约束 / Constraints

| ID | 约束 | 说明 |
|----|------|------|
| C1 | 不破坏现有 API 接口 | `physical-operators.json`、`operator_runtime`、`operatord` 当前调用方（autopilot、graph_node_dispatcher、status server）必须保持向后兼容；只能扩展字段，不能改语义。 |
| C2 | secret/token/cookie 不得出现在 registry/log/status | 只允许 `secret_ref` / `key_env` / `account_label` 引用；任何 PRD/contract/test 也不允许 raw secret。 |
| C3 | macOS arm64 + bash 5.3.9 | 全部脚本必须在 `/opt/homebrew/bin/bash` 下可运行；不能引入 GNU-only flag。 |
| C4 | 不写 /tmp | 所有产出落 `~/.solar/harness/...` 或 sprint 目录；evidence/log/状态文件同理。 |
| C5 | 模型不可在运行中漂移 | 任务执行期间 DAG / Builder / tool 不允许 `/model`、临时改 wrapper、改 env login；违反即 contract 违规。 |
| C6 | DAG 节点不得绑定 provider/model 字符串 | 必须绑 `operator_id` 或 `required_capabilities + operator_class`；`preferred_operator` 是显式硬指定字段，不允许隐式。 |
| C7 | tmux pane 物理资源约束 | 一个 tmux pane 同时只能持有一个 active lease；pane 死掉 = operator 立即转 `unavailable`，由 runtime 触发失败转移。 |
| C8 | 5-pane 拓扑保持稳定 | pane 0 planner (opus) / pane 1 builder (glm-5.1) / pane 2 evaluator (glm-5.1) / pane 3 architect (opus) / pane 4 PM (本 pane) 的角色绑定不在本 sprint 改动；只是把它们标准化为 operator entries。 |
| C9 | 兼容期 ≥ 1 个 sprint | 旧 profile/provider/model 路径必须并行可用至少一个 sprint 周期，再考虑硬切。 |
| C10 | 不引入新进程模型 | 不允许引入 systemd/launchd unit、Docker、k8s；继续走 `solar-harness` CLI + tmux pane + sqlite。 |

## 风险 / Risks

| ID | 风险 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R1 | Registry schema 一次性扩太多字段 → 旧任务图直接 fail validate | 中 | 高 | schema 字段分 `required` / `optional`；新增字段全部 optional + default；validator 给出 warn 而不是 reject 至少一个 sprint。 |
| R2 | Lease/heartbeat 协议在 4 pane 高并发下出现死锁或 starvation | 中 | 高 | 引入 `lease_ttl + heartbeat_grace + drain timeout`；evaluator pane 必须能强制 break lease；写 chaos test (kill pane, kill heartbeat)。 |
| R3 | Quota Clock 计算与 Anthropic Max / GLM 平台真实计费偏差 | 高 | 中 | quota 字段只做“本地软限”；以远端 429/quota_exhausted 为最终真相；clock 接受重置事件。 |
| R4 | DAG Scheduler 选错 operator → 任务跑在错的账号上烧月费 | 中 | 高 | A4 (no drift) + A5 (capability scoring) + evidence log 三层保护；evaluator 必须比对 `expected_operator_class` vs `actual_operator_id`。 |
| R5 | Operator 同时被两条 DAG lease | 低 | 高 | sqlite 用 `lease_token + CAS update`；冲突即抢锁失败；状态页显示当前 holder。 |
| R6 | 外部 runtime (Codex/Antigravity) auth 过期但 registry 未感知 | 中 | 中 | `auth.last_verified_at` + 周期性 probe；过期触发 `auth_expired` 状态并自动从可派发池剔除。 |
| R7 | 8765 状态页改造引入性能回归 | 低 | 中 | operator fleet 摘要走 sqlite view + 5s 内缓存；不在请求路径里跑 heavy aggregation。 |
| R8 | 迁移期间历史 `task_graph.json` 找不到对应 operator | 中 | 中 | 提供 `legacy_provider_model_map` fallback 表；找不到时 fail-loud + 给出迁移命令，不静默改写。 |
| R9 | secret_ref 实现引入 env 变量泄漏到 log | 低 | 高 | 强制 `redact_envs` 列表；ATLAS 在 evidence collection 时 mask；写 unit test 验证。 |
| R10 | PM/Planner 文档与实现漂移 | 高 | 中 | contract 必须列 “authoritative file paths”；CI/local check 跑 schema vs code consistency 测试。 |

## 开放问题 / Open Questions

> 这些问题留给 Planner 在 `design.md` 里给出明确答案，不在 PRD 阶段决定。

- **Q1**：`operator_id` 命名规范？建议 `pane-<host>-<index>-<role>` 还是 `<role>-<model>-<n>`？是否允许 alias？
- **Q2**：`CapabilityProfile` 用枚举还是 free-form tags？是否需要 capability version？
- **Q3**：lease 粒度 — 是按 task 还是按 sprint？长程 sprint (多 round) 是否允许同 operator 续 lease？
- **Q4**：quota 字段是否要建模“多账号共享 quota”（例如同一个 Anthropic Max 账号被 pane 0 + pane 3 共用）？
- **Q5**：失败转移策略 — operator 挂掉时是 retry on same class 还是 escalate to higher class（builder fail → architect 接管）？谁来决策？
- **Q6**：verifier separation 的强度 — 是不是只要求 evaluator operator ≠ writer operator？还是要求 evaluator class != writer class？
- **Q7**：legacy `provider/model/profile` 退场时间点 — 1 个 sprint 兼容期是否足够？还是要 2 个？
- **Q8**：本机 runtime（ThunderOMLX、FlashMLX）是否也应纳入 operator registry？还是作为单独的“local-inference operator class”？
- **Q9**：8765 状态页新增字段是否影响现有 `solar-harness status` CLI 输出？需要新增 `--operator-view` flag 还是直接升级默认输出？
- **Q10**：secret_ref 用 macOS Keychain 还是直接 env var？是否需要支持 1Password CLI？
- **Q11**：operator drain/cooldown 期间是否允许 evaluator 复用它来做只读验证？还是必须完全空转？
- **Q12**：DAG validator 是否要在 PR-time 而不仅是 dispatch-time 检查 operator constraint？

## Acceptance

```text
┌────┬──────────────────────────────────────────────────────────────┐
│ ID │ Acceptance                                                   │
├────┼──────────────────────────────────────────────────────────────┤
│ A1 │ 架构文档明确规定 DAG 只调度 `operator_id`                    │
│ A2 │ schema 覆盖 physical/surface/model/auth/quota/policy/state   │
│ A3 │ runtime 状态机和 lease 语义统一，不再分散                   │
│ A4 │ 运行中模型漂移被视为违规，形成 contract                      │
│ A5 │ scheduler 支持 capability/quota/policy/operator_class 选择   │
│ A6 │ 8765 状态页能展示 operator fleet 摘要/alerts/results         │
│ A7 │ 迁移策略说明旧 profile 如何兼容、何时退场                    │
│ A8 │ 最终 design/plan/task_graph 能直接指导后续实现               │
└────┴──────────────────────────────────────────────────────────────┘
```

## Planner Output Required

Planner 必须继续产出：

- `design.md`
- `plan.md`
- `task_graph.json`

并且 `task_graph.json` 必须通过 `solar-harness graph-scheduler validate`。

## 架构交接 / Planner Handoff

**Handoff Target**: `pane 0 (planner, opus)`
**Handoff Mode**: 正式 `PM → Planner`，禁止跳过 Planner 直接派 Builder。
**Stop Rules**: Planner 完成 `design.md + plan.md + task_graph.json` 三件套且 `solar-harness graph-scheduler validate` 通过后，状态机进入 `planning_complete`；否则保持 `drafting` 并在 `pm-order.md` 追加 round。

### 强制 Planner 回答的设计点

1. **Registry Lock (Workstream A)** — schema 字段定版 + secret_ref 规范 + capability/policy 枚举 + 向后兼容规则；交付 `physical-operators.schema.json v2` 草案。
2. **Runtime Lock (Workstream B)** — operator lifecycle 状态机图（available / busy / draining / quota_exhausted / auth_expired / disabled / unavailable）+ lease/heartbeat 协议 + failure transfer 决策树。
3. **Scheduler Lock (Workstream C)** — task → operator 选择算法伪代码；`required_capabilities` × `operator_class` × `quota_reserve` × `policy_guard` 的优先级；verifier separation 实现。
4. **Observability Lock (Workstream D)** — 8765 状态页 payload schema；operator fleet 摘要 / recent results / alerts / runtime drift evidence 的 SQL view 或 sqlite query。
5. **Migration Lock (Workstream E)** — legacy `provider/model/profile` → `operator_id` 的 mapping 表；rollout phases；rollback 命令；废弃时间点。

### 必备产出物

| 产出 | 路径 | 验收方 |
|------|------|--------|
| `design.md` | `~/.solar/harness/sprints/sprint-20260523-...design.md` | evaluator + architect 二审 |
| `plan.md` | `~/.solar/harness/sprints/sprint-20260523-...plan.md` | evaluator |
| `task_graph.json` | `~/.solar/harness/sprints/sprint-20260523-...task_graph.json` | `solar-harness graph-scheduler validate` |
| `physical-operators.schema.json v2` 草案 | `~/.solar/harness/schemas/physical-operators.schema.v2.draft.json` | evaluator + architect |
| `migration-plan.md` (legacy → operator_id) | `~/.solar/harness/sprints/sprint-20260523-...migration.md` | evaluator |

### task_graph.json 必须满足

- 每个 node 写 `required_capabilities` + `preferred_operator_class`，不直接写 model 字符串。
- 包含至少 5 个 workstream node（N1 Registry / N2 Runtime / N3 Scheduler / N4 Observability / N5 Migration）。
- 节点间依赖明确：N1 → {N2, N3}，N3 → N4，{N1,N2,N3,N4} → N5。
- 每个 node 有 `acceptance` 字段，映射回 PRD 的 A1–A8。
- 每个 node 有 `verifier_operator_class != writer_operator_class`（强制 evaluator 隔离）。

### Stop Rules

- **STOP-A**：Planner 若在 round 3 仍未产出 `task_graph.json`，PM 介入重写 PRD 切片粒度。
- **STOP-B**：若 `graph-scheduler validate` 持续 fail 同一类 schema 错误 ≥ 2 round，立即升级到 architect (pane 3) 做二审。
- **STOP-C**：若 design 阶段发现需要破坏 C1 (向后兼容) 或 C2 (secret safety)，停下回到 PM pane 重新评估 priority。

### Non-Negotiables (PM 红线)

- 不允许 Planner 在 design 阶段引入新的进程模型（C10）。
- 不允许 Planner 把 `provider/model/profile` 写进 task_graph 作为长期真值（C6）。
- 不允许 Planner 在 schema 里写 raw secret 字段（C2）。
- 不允许 Planner 跳过 evaluator/architect 二审直接交付 (`handoff_to=planner→evaluator` 是唯一合法路径)。

### Knowledge Context

Knowledge Context: `solar-harness context inject` used (查询命中 QMD solar-wiki / Solar DB / Obsidian Vault；mirage 路径降级)。
Harness Modules Used: `harness-knowledge`（context inject）。

