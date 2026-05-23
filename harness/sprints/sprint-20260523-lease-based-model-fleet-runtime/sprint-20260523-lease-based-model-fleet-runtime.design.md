# Design — Lease-based Model Fleet Runtime

sprint_id: `sprint-20260523-lease-based-model-fleet-runtime`
priority: `P0`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-23T10:45:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: PRD + Contract (created 2026-05-23T01:05Z) · task_graph.json validated (5 nodes, 5 layers) · N1 **passed** (architecture doc done) · N2 **reviewing** (schema + addenda done)
parallel_protect: `operatord-daemon-submit-production` 与 `claude-operator-billing-split` 不被 block / 不被 rewrite

## 0. 本切片的边界（强制 read-first）

- **P0 架构升级**：把 "DAG → tmux pane / physical operator" 升级为 "DAG → AgentActor lease → ActorHost"。
- **本 sprint 是 wake 合规补齐**：N1 已 passed（架构文档完成），N2 已 reviewing（schema + 5 个 addenda 累积）；planner 仅补 design.md + plan.md + planning.html。
- **允许 Write/Edit**（per task_graph write_scope）：
  - 架构文档：`docs/lease-based-model-fleet-runtime.md`（N1 已落地）
  - schema/config：`config/{agent-actors,actor-hosts,logical-operators,context-store,capability-token}.{schema.json,json}`（N2 已部分落地）
  - 运行时：`lib/{actor_runtime,actor_lease,actor_mailbox,actor_profiles,logical_operator_router,operator_score,verification_gate,evidence_ledger,context_store,capability_token,failure_fingerprint}.py`（N3 待）
  - 观测：`lib/multi_task_status.py` + `tools/monitor_bridge.py`（N4 待）
  - 测试：`tests/**`（N2 + N3 + N4 各自范围）
  - 最终报告：`monitor-reports/lease-based-model-fleet-runtime.md`（N5 待）
  - sprint artifact：本 sprint `.design.md / .plan.md / .N*-handoff.md / .planning.html`
- **严格禁止**（per contract Hard Constraints）：
  - 移除 tmux pane 执行支持
  - DAG/scheduler 直调 `tmux send-keys` 派任务负载
  - tmux pane index 当作 durable scheduler key
  - `idle/running` 文本当作调度权威
  - DAG 节点引用裸 physical actor / model id（仅 compatibility 别名允许）
  - writer 与 verifier 同一 actor
  - premium actor 跑 BULK_DOC_EDIT / TRIVIAL_RENAME / GREP_SCAN
  - 改 ThunderOMLX 路径 / model routing
  - 打印 secrets / API key / OAuth / cookies / raw credentials
  - kill / restart 现有 pane（无显式用户授权）
  - block 或 rewrite `operatord-daemon-submit-production` / `claude-operator-billing-split` 任何文件
  - 修改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 知识库降级 `mirage:nonzero`：本 sprint self-contained（N1 已含 source verification）。

## 1. 架构图（per N1 已落地 docs/lease-based-model-fleet-runtime.md）

```
┌─────────────────────────────────────────────────────────────────┐
│                        DAG nodes (scheduler)                    │
│        references: logical_operator (not physical actor)        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ logical_operator → candidates
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           bindings (data, not code) — logical-operators.json    │
│  DeepArchitect → [actor.claude.opus47.architect.01, …]          │
│  ParallelExplorer → [actor.antigravity.gemini35flash.exp.01]    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ profile gates + OperatorScore
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AgentActor registry (agent-actors.json)        │
│    actor_id, host_id, lease, capability/risk/cost profiles,     │
│    quota, policy, evidence path, persona_binding, fallback      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ actor.lease (TTL + heartbeat)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ActorHost registry (actor-hosts.json)          │
│  tmux_pane / codex_worktree / codex_cloud / antigravity_env /   │
│  claude_code_session / local_mlx_process / ssh_devbox /         │
│  docker_sandbox                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ file mailbox queue (P0)
                           ▼
~/.solar/operators/<actor_id>/
   inbox/task-N.yaml     ← actor_runtime.submit() 写入
   outbox/task-N.result.yaml  ← operatord 写入
   logs/task-N.{stdout,stderr}.log
   state.json             ← lease state
   heartbeat.json         ← TTL + heartbeat
```

`tmux send-keys` **仅** bootstrap：

```bash
tmux send-keys -t solar:claude_arch.0 \
  'operatord run actor.claude.opus47.architect.01' C-m
```

之后所有 task payload 走 file mailbox，不通过 keystroke。

## 2. 上游摘要（已落地状态）

| 节点 | 状态 | 已落地物 |
|------|------|---------|
| N1 architecture | ✅ passed | `docs/lease-based-model-fleet-runtime.md` + `.N1-handoff.md` + `.N1-addendum.md` |
| N2 schema/config | 🔄 reviewing | schema/config files + 4 addenda（context-store, logical-operators, capability-token, failure-fingerprint）|
| N3 lease broker + submit | ⏳ pending | 待 |
| N4 status/bridge | ⏳ pending | 待 |
| N5 final report | ⏳ pending | 待 |

`monitor_blocker` on N2: "previous N2 handoff incomplete after profile/logical-operator/evidence-ledger/context-store addenda; rerun required" — builder 必须把 5 个 addenda 合并到主 N2-handoff 后再过 review。

## 3. 三 profile 模型（per PRD R1a）

每 schedulable AgentActor 必须暴露 3 个独立 profile，绝不能合并：

| Profile | 关键字段 | 用途 |
|---------|---------|------|
| capability_profile | architecture_reasoning / code_impl / root_cause_debug / test_generation / test_execution / research_synthesis / academic_critique / browser_use / gui_use / long_context / multi_agent_coordination / speed | 决定 fit |
| risk_profile | allowed_write_scope / allowed_shell_scope / allowed_network / allowed_secrets / destructive_actions / git_commit / git_push / payment_or_external_action / requires_human_for | hard 拒绝 |
| cost_profile | cost_tier / token_budget_class / quota_period / reserve_ratio / effort / prefer_for / avoid_for | reserve/avoid 决策 |

## 4. 16 Logical Operator P0 分类（per PRD R1b）

| Logical Operator | 用途 | 默认 binding |
|------------------|------|--------------|
| DeepArchitect | 架构设计 / 选项分析 | Claude Opus 4.7 xhigh/max |
| RootCauseDebugger | 根因分析 / 日志读 | Claude Opus 4.7 xhigh |
| ImplementationWorker | 多文件实施 | Codex GPT-5.5 |
| PatchWorker | 小补丁 | Codex mini / Gemini Flash |
| TestDesigner | 测试设计 | Claude / Codex |
| TestRunner | 跑测试 + 收集日志 | Codex / local shell |
| BenchmarkRunner | 性能实验 | Codex / local |
| ParallelExplorer | 并行方案探索 | Antigravity / Codex subagents |
| ResearchScout | 源搜索 + 证据收集 | Codex / Gemini Flash |
| ResearchSynthesizer | 综合报告 | GPT-5.5 / Claude |
| Critic | 批评 / 反驳 / review | Claude Opus |
| Verifier | 独立验证 | Claude + local check |
| SecurityGate | 权限 / 安全审查 | local rules + Claude |
| QuotaBroker | 配额仲裁 | local runtime |
| ContextCompressor | 上下文压缩 | local / cheap model |
| ArtifactCurator | artifact 整理 | Codex / local |

**bindings 是数据**：模型换了改 binding + actor profile，不改 DAG。

## 5. Lease 状态机（per PRD R3）

```
canonical:  UNREGISTERED → BOOTING → READY → LEASED → RUNNING → FINALIZING → READY

exception:  STALE | QUOTA_BLOCKED | AUTH_BLOCKED | POLICY_BLOCKED |
            HUMAN_REQUIRED | CRASHED | DRAINING | DISABLED
```

`idle/running` 文本仅用于 display；真正调度依据 = lease ownership + heartbeat。

Lease 持久化字段（per PRD R5a）：
- lease_id, task_id, actor_id, sprint_id, node_id
- acquired_at, expires_at
- renewable, preemptible, heartbeat_timeout_sec
- evidence_path

## 6. OperatorScore 公式（per PRD R3b，N3 实施）

```text
OperatorScore =
  TaskFit              * 0.30
+ HistoricalSuccess    * 0.20
+ FreshQuota           * 0.15
+ LatencyFit           * 0.10
+ ContextAffinity      * 0.10
+ RiskFit              * 0.10
+ CostFit              * 0.05
- RecentFailurePenalty
- SameProviderVerifierPenalty
- StaleContextPenalty
- FailureFingerprintPenalty  （per N3 addendum）
```

输出必须可解释：含 factor values、penalties、selected actor、rejected candidates、reasons。HistoricalSuccess 从 local Solar task evidence 学，不是供应商官方文案。

## 7. 验证作为 DAG 结构（per PRD R3c）

critical DAG 必须不让 writer 自证：

| 证据类别 | 必备 |
|---------|------|
| Patch 或 artifact | 是 |
| Test / benchmark / validation evidence | 是 |
| 独立 verifier decision | 是 |

verifier decision YAML（机器可读）：

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

规则：no verifier output → no DONE；no test evidence → no PASS；writer ≠ verifier；高风险任务优先 cross-provider verifier。

## 8. Submit Protocol 边界（per PRD R4）

DAG code 必须只调：

```python
actor_runtime.submit(task_envelope)
```

不允许直调 `tmux send-keys` / Claude SDK / Codex CLI / Antigravity CLI / provider 任何专用入口。Runtime 内部可用，DAG 只见 lease + result artifact。

## 9. Evidence Ledger（per PRD R5）

每次 actor 执行落盘：

```
run/agent-actors/<actor_id>/<task_id>/
  envelope.yaml      （secrets scrubbed）
  lease.events.jsonl  （grant/release）
  heartbeat.jsonl
  stdout.log         （secrets scrubbed）
  stderr.log
  result.yaml
  verifier_decision.yaml  （when present）

run/agent-actors/ledger.jsonl    （append-only run summary index）
```

## 10. Required Host Types（per PRD §Required Host Types）

P0 必须 schema-validate，部分可 stub probe：

| host_type | P0 状态 |
|-----------|---------|
| tmux_pane | 完整 |
| codex_worktree | schema + stub probe |
| codex_cloud | schema + stub |
| antigravity_managed_env | schema + stub |
| claude_code_session | schema + stub |
| local_mlx_process | schema + stub |
| ssh_devbox | schema + stub |
| docker_sandbox | schema + stub |

## 11. 兼容性迁移（per PRD R6 + Contract Constraints）

- 现 `physical-operators.json` 保持可加载 via 兼容 adapter
- 旧 operator id → AgentActor 别名（aliases）
- 旧 pane metadata → ActorHost entry
- 状态输出同时显示 old operator id + 新 actor id（过渡期）
- `no-direct-tmux-send-keys` lint 保持通过

## 12. 非目标（明确禁止）

- 不移除现有 tmux 执行
- 不一个 sprint 重写所有 provider adapter
- 不允许 DAG code 直 `tmux send-keys`
- 不打印 secrets / 不强制 cloud-host fully functional（schema + stub 足够）
- 不动 `~/.solar/STATE.md`、epic.*、其他 sprint artifact
- 不动 ThunderOMLX 任何路径
- 不杀 / 重启现有 pane
- 不 block `operatord-daemon-submit-production` / `claude-operator-billing-split` 任何文件
- 不使用乐观词

## 13. 关键风险（plan §6 详细 stop rule）

- writer = verifier → critical PASS 必须拒绝
- premium actor 被批量任务消耗 → cost_profile 必须 enforce avoid_for
- secret leak via stdout / envelope → scrubbing 必须 enforce
- tmux send-keys 漏到 DAG 路径 → lint 必须 catch
- pane index 当作 durable key → schema 拒绝
- N2 五 addenda 未合并到主 handoff → reviewer FAIL（monitor_blocker 已标）

## 14. 给 evaluator + N5 的接力

evaluator 必须按 contract §Required Evidence 13 条逐项核：

1. files changed
2. tests run + result
3. compatibility impact
4. tmux pane identity 仅作 host metadata 证据
5. task payload 入口 = mailbox 证据
6. lease state 含 owner/TTL/heartbeat/renew/failure 证据
7. capability/risk/cost profile schema-validated
8. 16 logical operator schema-validated 并 mapped to bindings
9. 改 binding 改物理 actor 不改 DAG 节点
10. OperatorScore 含 HistoricalSuccess 并可由 local evidence 更新
11. verifier decision 机器可读 + gate DONE/PASS
12. policy block destructive / secret / git push / payment / unauthorized writes
13. secrets 未打印 + remaining migration risk
