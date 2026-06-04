# PRD: Lease-based Model Fleet Runtime

Sprint: `sprint-20260523-lease-based-model-fleet-runtime`
Priority: P0
Target: Mac mini `/Users/lisihao/.solar/harness`

## Summary

Upgrade the current Pane-as-Physical-Operator design into a lease-based Agent Actor runtime.

The core shift:

```text
old: DAG -> tmux pane / physical operator
new: DAG -> AgentActor lease -> ActorHost
```

`tmux` remains a useful local long-running process host, but it must not be the scheduling endpoint or RPC protocol. Pane indexes and layouts can drift, process titles can be stale, and direct `tmux send-keys` is not a reliable control plane. The runtime must schedule typed Agent Actors with lease, state, capability, quota, policy, and evidence records, then bind each actor to an ActorHost such as tmux, Codex worktree, Antigravity managed environment, Claude Code session, local MLX process, SSH devbox, or sandbox container.

## Problem

The current operator design still leaks host details into scheduling decisions:

- tmux pane identity is treated as if it were stable enough to schedule directly;
- operator status mixes process/container state with logical actor state;
- quota, lease, policy, and evidence are not uniformly attached to the dispatch object;
- future hosts like Codex cloud worktrees or Antigravity managed environments cannot be represented cleanly;
- direct terminal control remains a recurring risk unless the runtime owns communication.

## Goal

Introduce first-class `AgentActor` and `ActorHost` abstractions:

```yaml
AgentActor:
  actor_id: actor.claude.opus47.architect.01
  operator_class: DeepArchitect
  host_id: host.tmux.solar-aiops.claude-arch.01
  lease:
    state: idle | leased | running | draining | cooldown | error
    lease_id: null
    ttl_sec: 2700
  capability:
    planning: 5
    coding: 4
    debugging: 5
    review: 5
    multimodal: false
  quota:
    billing_pool: anthropic_subscription_interactive
    reserve_for: [ARCH_DESIGN, ROOT_CAUSE_DEBUG, FINAL_REVIEW]
  policy:
    write_files: ask_or_patch_only
    secrets_access: denied
    network: restricted
  evidence:
    task_log_dir: run/agent-actors/<actor_id>/
    ledger_path: run/agent-actors/ledger.jsonl

ActorHost:
  host_id: host.tmux.solar-aiops.claude-arch.01
  host_type: tmux_pane
  lifecycle: created | warming | alive | degraded | offline
  address:
    session: solar-aiops
    window: claude_arch
    pane_id: "%12"
```

## Required Host Types

The first registry version must support these host types, even if some are initially stubbed:

- `tmux_pane`
- `codex_worktree`
- `codex_cloud`
- `antigravity_managed_env`
- `claude_code_session`
- `local_mlx_process`
- `ssh_devbox`
- `docker_sandbox`

## Requirements

### R1 AgentActor schema

Add schema/config support for:

- `actor_id`
- `operator_class`
- `host_id`
- `host_type`
- `lease`
- `capability_profile`
- `risk_profile`
- `cost_profile`
- `quota`
- `policy`
- `evidence`
- `fallback_ladder`
- `persona_binding`

No DAG node should need a raw tmux pane, raw model string, or raw CLI command to select an executor.

### R1a Three Profile Model

Every schedulable `AgentActor` must expose three separate profiles. A single vague `capability` object is not enough for safe automatic routing.

Capability profile:

```yaml
capability_profile:
  architecture_reasoning: 5
  code_impl: 4
  root_cause_debug: 5
  test_generation: 4
  test_execution: 3
  research_synthesis: 4
  academic_critique: 5
  browser_use: 2
  gui_use: 2
  long_context: 5
  multi_agent_coordination: 3
  speed: 3
```

Risk profile:

```yaml
risk_profile:
  allowed_write_scope: patch_only
  allowed_shell_scope: repo_local
  allowed_network: docs_only
  allowed_secrets: none
  destructive_actions: denied
  git_commit: denied
  git_push: denied
  payment_or_external_action: denied
  requires_human_for:
    - delete_files
    - modify_ci
    - change_auth
    - touch_secrets
```

Cost profile:

```yaml
cost_profile:
  cost_tier: premium
  token_budget_class: expensive
  quota_period: monthly
  reserve_ratio: 0.25
  effort: xhigh
  prefer_for:
    - ARCH_DESIGN
    - ROOT_CAUSE_DEBUG
    - FINAL_REVIEW
  avoid_for:
    - BULK_DOC_EDIT
    - TRIVIAL_RENAME
    - GREP_SCAN
```

Effort level is part of cost/routing policy, not an ad hoc runtime switch. Premium reasoning modes must be reserved for high-value nodes.

### R1b Logical Operator Type System

DAG nodes must reference logical operator types, not physical actor ids, model ids, tmux panes, or provider CLI names.

Wrong:

```yaml
operator: op.claude.opus47.architect.01
```

Right:

```yaml
logical_operator: DeepArchitect
```

P0 logical operator taxonomy:

| Logical Operator | Purpose | Default physical binding |
|---|---|---|
| `DeepArchitect` | architecture design, option analysis | Claude Opus 4.7 xhigh/max |
| `RootCauseDebugger` | root cause analysis, log reading | Claude Opus 4.7 xhigh |
| `ImplementationWorker` | multi-file implementation | Codex GPT-5.5 |
| `PatchWorker` | small patches | Codex mini / Gemini Flash |
| `TestDesigner` | unit/integration test design | Claude / Codex |
| `TestRunner` | run tests and collect logs | Codex / local shell |
| `BenchmarkRunner` | performance experiments | Codex / local |
| `ParallelExplorer` | parallel solution exploration | Antigravity / Codex subagents |
| `ResearchScout` | source search and evidence collection | Codex / Gemini Flash |
| `ResearchSynthesizer` | synthesis reports | GPT-5.5 / Claude |
| `Critic` | critique, rebuttal, review | Claude Opus |
| `Verifier` | independent verification | Claude + local check |
| `SecurityGate` | permission/security review | local rules + Claude |
| `QuotaBroker` | quota arbitration | local runtime |
| `ContextCompressor` | context compression | local / cheap model |
| `ArtifactCurator` | artifact organization | Codex / local |

Bindings are data, not DAG logic:

```yaml
bindings:
  ParallelExplorer:
    primary: actor.antigravity.gemini35flash.parallel.01
  DeepArchitect:
    candidates:
      - actor.claude.opus47.architect.01
      - actor.google.gemini35pro.architect.01
```

When models change, update bindings and actor profiles; do not rewrite DAGs.

### R2 ActorHost schema

Add host registry support for:

- stable `host_id`
- `host_type`
- host lifecycle state
- host address metadata
- heartbeat path
- attach/reconnect instructions
- host-specific health probes

For tmux, prefer stable pane IDs and actor heartbeat files over pane index. Pane index may be displayed, but it must not be the durable scheduler key.

### R3 Lease broker

Create a lease broker that grants a node a lease on an `AgentActor`, not directly on a host.

Required states:

```text
CREATED -> WARMING -> IDLE -> LEASED -> RUNNING -> DRAINING -> IDLE
ERROR | QUOTA_EXHAUSTED | AUTH_EXPIRED | COOLDOWN | DISABLED | STALE_CONTEXT | NEEDS_HUMAN_REVIEW
```

The broker must persist lease state, TTL, task id, sprint id, node id, actor id, and evidence path.

### R3a Profile-aware routing and policy gates

The actor selector must use all three profiles:

- `logical_operator` chooses the logical role class first.
- `capability_profile` decides whether an actor can do the task well enough.
- `risk_profile` decides whether the actor is allowed to take the task safely.
- `cost_profile` decides whether the task is valuable enough to spend the actor's model/quota budget.

An actor that passes capability but fails risk or cost constraints must not receive the lease. This is a runtime gate, not just a prompt instruction.

### R3b Operator Score

Physical actor selection must use a dynamic score after logical operator binding and profile gates:

```text
OperatorScore =
  TaskFit * 0.30
+ HistoricalSuccess * 0.20
+ FreshQuota * 0.15
+ LatencyFit * 0.10
+ ContextAffinity * 0.10
+ RiskFit * 0.10
+ CostFit * 0.05
- RecentFailurePenalty
- SameProviderVerifierPenalty
- StaleContextPenalty
```

Initial model/provider priors may come from official positioning, but `HistoricalSuccess` must be learned from Solar task evidence:

- success rate in FlashMLX;
- success rate in Solar-harness;
- Metal/debug reliability;
- long-document evidence quality;
- test-generation honesty;
- quota pressure behavior;
- review/verifier disagreement history.

The score must persist enough data to explain why an actor won or lost a lease.

### R3c Verification as DAG Structure

Critical DAGs must not let the writer self-certify completion. Required evidence classes:

1. Patch or artifact.
2. Test, benchmark, or validation evidence.
3. Independent verifier decision.

Verifier decisions must be machine-readable:

```yaml
decision: PASS_WITH_WARNINGS
confidence: 0.82
must_fix: []
should_fix:
  - "Add one regression test for empty expert set"
evidence:
  tests_passed: true
  benchmark_delta_verified: true
  no_secret_leak: true
  scope_ok: true
```

Rules:

- no verifier output, no DAG DONE;
- no test/benchmark evidence, no code-task PASS;
- writer and verifier cannot be the same actor/operator;
- high-risk tasks should prefer cross-provider verification.

### R4 Submit protocol boundary

DAG code must call:

```python
actor_runtime.submit(task_envelope)
```

It must not directly call `tmux send-keys`, Claude, Codex, Antigravity, or a provider-specific CLI.

The runtime may use tmux, SDK calls, or managed environments internally, but the DAG sees only actor leases and result artifacts.

### R4a No `tmux send-keys` as task protocol

`tmux send-keys` is permitted only for host bootstrap:

```bash
tmux send-keys -t solar:claude_arch.0 \
  'operatord run actor.claude.opus47.architect.01' C-m
```

After `operatord` is alive, no DAG node, scheduler, router, or task dispatcher may send natural-language task payloads directly into a pane. The primary task channel must be a machine-readable queue:

```text
~/.solar/operators/<actor_id>/
  inbox/
    task-0001.yaml
  outbox/
    task-0001.result.yaml
  logs/
    task-0001.stdout.log
    task-0001.stderr.log
  state.json
  heartbeat.json
```

P0 should implement a file mailbox first. Unix socket or SQLite queue can be later host transports, but they must preserve the same `task_envelope -> result.json -> evidence ledger` contract.

### R5 Evidence ledger

Every actor execution must emit:

- task envelope snapshot with secrets scrubbed;
- lease grant/release events;
- host heartbeat evidence;
- stdout/stderr or equivalent provider output with secret scrub;
- result artifact path;
- verifier decision when present.

### R5a Lease is the source of truth

The runtime must not decide availability from `idle/running` text alone. Availability is derived from lease ownership and heartbeat state:

```yaml
lease:
  lease_id: lease-20260522-173001-opus47-001
  task_id: dag-017-node-03
  actor_id: actor.claude.opus47.architect.01
  acquired_at: "2026-05-22T17:30:01-04:00"
  expires_at: "2026-05-22T18:10:01-04:00"
  renewable: true
  preemptible: false
  heartbeat_timeout_sec: 90
```

The canonical state machine for actors is:

```text
UNREGISTERED -> BOOTING -> READY -> LEASED -> RUNNING -> FINALIZING -> READY

exception states:
  STALE
  QUOTA_BLOCKED
  AUTH_BLOCKED
  POLICY_BLOCKED
  HUMAN_REQUIRED
  CRASHED
  DRAINING
  DISABLED
```

The older `idle/running` labels may remain as display summaries, but they are not scheduling authority.

### R6 Compatibility migration

Existing `physical-operators.json` and previous Pane-as-Physical-Operator config must remain loadable through compatibility adapters. The migration must be additive first:

- current operators become `AgentActor` entries;
- current pane metadata becomes `ActorHost` entries;
- old operator ids become aliases;
- status output shows both old operator id and new actor id during transition.

## Non-goals

- Do not remove existing tmux-based execution.
- Do not rewrite every provider adapter in one sprint.
- Do not enable direct tmux send-keys from DAG code.
- Do not print secrets or raw credentials.
- Do not force cloud-host support to be fully functional in P0; schema + stub probe is enough.

## Acceptance

- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/lease-based-model-fleet-runtime.md`.
- Docs define `AgentActor`, `ActorHost`, lease state machine, and migration rules.
- Schema/config supports actor and host registries.
- Runtime can lease an actor and submit a task envelope without exposing tmux as scheduler endpoint.
- Tests prove tmux pane index is not the durable key.
- Tests prove `tmux send-keys` is used only for bootstrap and never for task payloads.
- Tests prove a stale lease can be detected and released/degraded without relying on pane text.
- Tests prove risk profile denies destructive, external-payment, secret-touching, git-push, and out-of-scope writes before dispatch.
- Tests prove cost profile reserves premium/high-effort actors for high-value task types and avoids low-value batch work.
- Tests prove DAG nodes can select by `logical_operator` and bindings can change physical actors without changing the DAG.
- Tests prove `OperatorScore` uses historical success, quota, latency, context, risk, cost, and penalties with explainable output.
- Tests prove critical DAGs require patch/artifact, test/benchmark evidence, and independent machine-readable verifier decision before DONE.
- Status/bridge output includes `actor_id`, `host_id`, `host_type`, `lease_state`, `quota/billing_pool`, and evidence path.

## Source Notes

- User design input treats tmux as a long-running local process container, not an RPC/control plane.
- Existing Solar direction already includes `operator_runtime.submit`, `operatord` daemon, no-direct-tmux-send-keys lint, persona binding, and physical operator registry work.
- Official source verification for tmux pane stability and managed-agent host claims should be captured in N1 before implementation.

---

## 背景 / Context

- Solar Harness 在 Mac mini (lisihaodeMac-mini.local, macOS arm64) 上已运行 4-pane 协同（pane 0 planner opus / pane 1 builder glm-5.1 / pane 2 evaluator glm-5.1 / pane 3 architect opus）。`tmux send-keys` + pane index 直接当调度端点用了几个月，证明在重启、分屏、模型切换、跨 host 场景下 fragile。
- 现在要把 "DAG → tmux pane" 升级为 **"DAG → AgentActor lease → ActorHost"**，引入 logical operator 类型系统 + 三 profile (capability / risk / cost) + 租约 + ledger，避免把"pane id 漂移 / 进程 title 过期 / 直接 send-keys"暴露给 DAG。
- 未来要支持 ≥8 种 ActorHost 类型（tmux_pane / codex_worktree / codex_cloud / antigravity_managed_env / claude_code_session / local_mlx_process / ssh_devbox / docker_sandbox），单一 tmux pane 抽象已经容纳不下。
- 实际状态：本切片已经走完 N1（host inventory & source verification）→ N2（schema & registry & migration adapters）→ N3（lease broker + submit protocol + 11 lib modules + 56 tests）→ N4（observability & monitor_bridge + 16 actor 字段 + 16 tests），N4 eval verdict **PASS**（独立 pytest 重跑 16/16 PASS in 0.08s，monitor_bridge schema=`solar.monitor_bridge.operator_fleet.v2`）。
- 本次 dispatch 是 coordinator gate_prd_schema 回溯触发：PRD 缺 schema 必需 6 节（背景/用户故事/约束/风险/开放问题/架构交接），导致 sprint 在 5/26 被拉回 `drafting/prd_ready`。本次 PM 修复 PRD 不重做实施，不动 status / 11 lib 模块 / N1-N4 handoff / eval。

## 用户故事 / User Stories

- **US-01 (DAG 作者)**：作为 DAG 作者，我希望节点只引用 `logical_operator: DeepArchitect` 等类型，不要写 `actor.claude.opus47.architect.01` 这种物理 id；当模型切换 (Opus 4.7 → Opus 4.8 / Gemini 3.5 Pro) 时我只改 bindings.json，不重写 DAG。
  - 验收：PRD §R1b + Acceptance "Tests prove DAG nodes can select by `logical_operator` and bindings can change physical actors without changing the DAG" ✅ (N3 16 P0 logical operators + bindings 数据驱动 + 实测通过)。
- **US-02 (Runtime 维护者)**：作为 runtime 维护者，我希望 actor 可用性来自 lease 状态 + heartbeat，不是 `idle/running` 文本；一个 actor 被 lease 占用就不能被并发派任务。
  - 验收：PRD §R5a "Lease is the source of truth" + `actor_lease.py` `fcntl.flock` atomic acquisition ✅ (N3)。
- **US-03 (安全审计 / Security)**：作为安全审计，我希望 destructive / git-push / payment / secrets 这种动作在派发前就被 risk_profile gate 拒绝，不是靠 prompt 提醒。
  - 验收：PRD §R3a + Acceptance "Tests prove risk profile denies destructive..."  ✅ (N3 `verification_gate.py` + `actor_profiles.check_risk_denial()`)。
- **US-04 (Cost 控制 / Billing)**：作为 cost 控制者，我希望 premium 模型（Opus xhigh / GPT-5.5 xhigh）只用于 ARCH_DESIGN / ROOT_CAUSE_DEBUG / FINAL_REVIEW，不要把 Opus 用在 BULK_DOC_EDIT / GREP_SCAN。
  - 验收：PRD §R3a cost gate + Acceptance "Tests prove cost profile reserves premium..." ✅ (N3 `actor_profiles.check_cost_reserve()` + `avoid_for` 表)。
- **US-05 (Verifier / Critic)**：作为 verifier，我希望写者不能自我认证 PASS；critical task 必须含 patch + test/benchmark + 独立 verifier 三类证据。
  - 验收：PRD §R3c "Verification as DAG Structure" + Acceptance "Tests prove critical DAGs require..." ✅ (N3 `verification_gate.py` 同 actor writer/verifier 拒绝 + cross-provider verifier preference)。
- **US-06 (Observability)**：作为 ops，我希望 status/bridge 输出含 actor_id / host_id / host_type / lease_state / billing_pool / evidence path 等字段，看一眼就知道每个 actor 在干什么。
  - 验收：PRD §Acceptance 末条 + N4 monitor_bridge 16 字段 ✅ (实测 schema v2，16 P0 logical operators + 15 actors + 1 host)。
- **US-07 (迁移)**：作为 runtime 迁移者，我希望旧 `physical-operators.json` 和 Pane-as-Physical-Operator 配置仍然可加载，旧 operator id 自动变成 actor alias；状态输出同时显示新旧 id 以便过渡。
  - 验收：PRD §R6 Compatibility migration ✅ (N2 migration adapters)。
- **US-08 (PM / Coordinator)**：作为 coordinator，本 PRD 必须通过 gate_prd_schema 以解除循环 dispatch。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 约束 / Constraints

- **环境**：macOS arm64 / bash 5.3.9 / tmux / Solar Harness 4-pane 已在线 / coordinator + chain-watcher + graph-scheduler 运行中。
- **路径白名单**：实施代码 `~/.solar/harness/lib/`、工具 `~/.solar/harness/tools/`、测试 `~/.solar/harness/tests/`、报告 `~/.solar/harness/monitor-reports/`、handoff `~/.solar/harness/sprints/<sid>.N*-handoff.md`；禁 `/tmp`、禁用户 home 根。
- **保留 tmux**：tmux 仍是合法的本机长跑进程 host；但不允许把 tmux pane 当调度端点。`tmux send-keys` 只能用于 host bootstrap（启动 `operatord`），不能传任务 payload。
- **不删旧代码**：旧 `physical-operators.json` / Pane-as-Physical-Operator 必须通过兼容 adapter 继续可加载（PRD §R6）；不允许一刀切删除。
- **secrets**：任务 envelope / stdout / stderr 写盘前必须 redact；不允许打印 token / API key / OAuth code / 用户密码。
- **不破坏 API**：现有 `solar-harness context inject / session evaluate / intent-gateway capture` 调用方式不变；本切片只新增 `actor_runtime.submit()` 和 actor/host 注册表。
- **P0 范围限制**：cloud host (codex_cloud / antigravity_managed_env) 在 P0 只需要 schema + stub probe；不要求完全 functional。
- **DAG 接口边界**：DAG 代码只能调 `actor_runtime.submit(task_envelope)`；不允许直接调 `tmux send-keys` / Claude / Codex / Antigravity / provider CLI。
- **PM 角色边界**：PM 不写实施代码；本切片是回溯 PRD schema 补全；不动 status / 11 lib 模块 / 12 tests / N1-N4 handoff / eval / monitor-reports。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| pane id (`%12`) 在 tmux 重启 / detach 后漂移 | 调度键失效 | 用 `host_id` 稳定 ID + heartbeat 文件作为 truth；pane index 只用于显示 (PRD §R2) ✅ N2 |
| writer = verifier 自我认证 | 假 PASS | `verification_gate.py` 同 actor 拒绝 + cross-provider preference (PRD §R3c) ✅ N3 |
| destructive action 偷渡过 risk gate | 数据丢失 / 安全事件 | risk_profile.requires_human_for + `check_risk_denial()` 派发前拦 (PRD §R3a) ✅ N3 |
| premium actor 被误用到低价值任务 | 月费爆 | cost_profile.avoid_for + reserve_for + `check_cost_reserve()` (PRD §R3a) ✅ N3 |
| 旧 operator_id 在迁移期不可识别 | scheduler crash | R6 兼容 adapter + alias map + 双 id 显示 ✅ N2 |
| `OperatorScore` 无法解释为什么某 actor 赢 lease | 调试不能 | scheduler_decision 持久化全部 factor + penalty + rejected candidates + quota_reason (PRD §R3b) ✅ N3 evidence_ledger |
| lease 过期但 actor 仍占资源 | 资源泄漏 / 阻塞 | `check_stale()` + heartbeat_timeout + STALE / DRAINING 状态机 (PRD §R5a) ✅ N3 |
| 同 provider verifier (写 Opus + 审 Opus) 偏袒 | 验证失效 | OperatorScore 有 `SameProviderVerifierPenalty 0.20` (PRD §R3b) ✅ N3 |
| ActorHost 多类型（≥8）schema 失控 | 未来扩展难 | P0 严格 schema + stub probe；cloud host 不要求 functional (PRD §Required Host Types) ✅ N1/N2 |
| 直接 tmux send-keys 偷渡回 DAG | 控制平面退化 | 加 lint 规则；`actor_runtime.submit()` 是唯一入口；评估器在 N4 抽查无违例 ✅ |
| secrets 通过 envelope / stdout 泄漏 | 安全事故 | 派发前 scrub + N4 evaluator 跑 8 类 secret 模式扫描，命中 0 ✅ |
| 多 lease 并发竞争 | race condition | `fcntl.flock` atomic acquisition (N3 actor_lease.py) ✅ |
| PRD 缺 schema 触发 gate 循环 | PM 反复重派 | 本切片即修复 ✅ |

## 开放问题 / Open Questions

- **OQ-01 cloud host 真实落地时机**：codex_cloud / antigravity_managed_env P0 只 stub；什么时候做 functional？需要 user 在 OQ-resolution sprint 给优先级。**Owner**：后续 sprint。
- **OQ-02 OperatorScore 权重微调**：当前 `TaskFit 0.30 / HistoricalSuccess 0.20 / FreshQuota 0.15 / LatencyFit 0.10 / ContextAffinity 0.10 / RiskFit 0.10 / CostFit 0.05` 是初始值；需要积累 ≥30 个 task 的 evidence 后做 A/B 调参。**Owner**：未来 calibration sprint。
- **OQ-03 cross-provider verifier 池**：当前只支持 Anthropic + OpenAI + Google 三家；如果加入 Mistral / DeepSeek / 本地 MLX，跨家配对策略要不要扩？**Owner**：等新 provider 接入再决议。
- **OQ-04 file mailbox → Unix socket / SQLite queue 升级路径**：P0 用 file mailbox；什么时候需要切到 socket / SQLite？看 throughput 实际瓶颈。**Owner**：未来 ops sprint。
- **OQ-05 lease TTL 默认值**：现在 `ttl_sec: 2700` (45 min) 是猜的；不同 logical_operator 是不是该有不同默认？例如 DeepArchitect 给 90 min、PatchWorker 给 15 min。**Owner**：calibration sprint。
- **OQ-06 fingerprint penalty 数值**：当前 FINAL_REVIEW 0.30 / PERFORMANCE_KERNEL_DEBUG 0.25 / FAST_PROTOTYPE 0.10 是初设；需要 30 次 failure 数据后调。**Owner**：calibration sprint。
- **OQ-07 antigravity_denial 应当 hard-block 还是只给 penalty**：当前是 `apply_antigravity_denial()` 在 scoring 前一律剔除（hard），是否要降级为 penalty-with-recovery？**Owner**：策略层 sprint。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（含 Summary / Problem / Goal / Required Host Types / Requirements R1-R6 + R1a/R1b/R3a/R3b/R3c/R4a/R5a / Non-goals / Acceptance / Source Notes + 本次补的 6 节）。
- `…contract.md`、`…design.md`、`…plan.md`、`…task_graph.json`、`…planning.html`。
- 实际 sprint 产出：
  - **N1** host inventory & source verification handoff + addendum。
  - **N2** schema & registry & migration handoff + 3 个 addendum（capability/antigravity-fingerprint, ledger-context, scoring-verification, logical-operators）。
  - **N3** lease broker + submit protocol handoff（**11 lib 模块 + 12 tests + 56 tests pass**）。
  - **N4** observability handoff + eval **PASS**（**16/16 actor_observability tests pass in 0.08s** + monitor_bridge 实测 schema=`solar.monitor_bridge.operator_fleet.v2` + 15 actors + 1 host + 16 logical_operator_bindings + 0 secret 命中）。
- 11 lib 模块全部已落地（见下表）。

### 当前实施状态（已交付，回溯不重做）

| 需求 ID | 主题 | N 节点 | 状态 | 关键证据 |
|---------|------|--------|------|----------|
| R1 / R1a | AgentActor schema + 3 profile | N2 | ✅ | `agent-actors.json` + `actor_profiles.py` (85 行) |
| R1b | Logical operator 类型系统 + 16 P0 操作员 | N2 / N3 | ✅ | `logical_operator_router.py` (102 行) + 16 个 binding |
| R2 | ActorHost 注册表 + 8 host_type | N2 | ✅ | host registry (stub for cloud) |
| R3 | Lease broker + 状态机 | N3 | ✅ | `actor_lease.py` (238 行) + `fcntl.flock` atomic |
| R3a | Profile-aware routing + risk/cost gate | N3 | ✅ | `actor_profiles.check_risk_denial()` + `check_cost_reserve()` |
| R3b | OperatorScore 7 因子 + 3 penalty | N3 | ✅ | `operator_score.py` (187 行) + scheduler_decision 持久化 |
| R3c | Verification as DAG Structure | N3 | ✅ | `verification_gate.py` (111 行) + same-actor reject |
| R4 / R4a | `actor_runtime.submit()` + 禁 tmux send-keys | N3 | ✅ | `actor_runtime.py` (175 行) + `actor_mailbox.py` (102 行) |
| R5 | Evidence ledger | N3 | ✅ | `evidence_ledger.py` (87 行) JSONL append-only |
| R5a | Lease is truth + 状态机 | N3 | ✅ | `actor_lease.check_stale()` + heartbeat_timeout |
| R6 | 兼容迁移 | N2 | ✅ | physical-operators.json adapter + alias map |
| **Observability** | monitor_bridge 16 字段 | N4 | ✅ | `tools/monitor_bridge.py` (6938 字节) + 16 tests pass |

### 给 Coordinator 的明确指令

- **不要 advance 到 builder**：sprint 实际已经在 N4 eval verdict=**PASS**；coordinator 当前拉回 `drafting/prd_ready` 仅为 gate_prd_schema 触发的回溯副作用。
- **触发机制**：PRD mtime 已刷新；coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 gate；识别 N4-eval.json verdict=PASS 后应让 sprint 回到 active 或 passed，不要重新跑 N1-N4。
- **不动 lib / tests / handoffs / eval**：本次 PM 切片只补 PRD 6 节 + 写 HTML artifact + 写 ACK；不改 sprint 任何其他 artifact。

### 未尽事项（留给后续 sprint）

- **OQ-01..OQ-07** 全部留给后续 sprint，特别是 OQ-01（cloud host functional）和 OQ-02（OperatorScore 权重 calibration）。
- **OperatorScore 历史数据积累**：需要 ≥30 个真实 task evidence 才能跑权重 calibration。
- **跨家 verifier 池扩展**：等新 provider 接入再开。
- **lease TTL / fingerprint penalty 数值调优**：等积累足够 failure 数据。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context block)。
