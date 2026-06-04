# Design — Pane-as-Physical-Operator Architecture

sprint_id: `sprint-20260523-pane-as-physical-operator-architecture`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-23T19:20:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: PM PRD + Contract (created 2026-05-23T19:06Z, round 1) · pm-order.md · prd.html
parallel_protect: `sprint-20260523-lease-based-model-fleet-runtime` 不被 block / rewrite（lease 是 actor 层；本 sprint 是 operator-registry 层；两者互补）

## 0. 本切片的边界（强制 read-first）

- **P0 架构正式定版**：把 Solar-Harness 现有的 `physical-operators.json + operator_runtime + operatord + multi_task_runner + graph_node_dispatcher` 收口为统一的三层 `Registry / Runtime / Scheduler`。
- **本 sprint 只产 design / schema 草案 / migration plan**，**不实施代码**。后续 sprint 才真正动 `lib/*.py`。
- **允许 Write/Edit**（per Required Deliverables + Planner Output Required）：
  - `sprints/<sid>.design.md`（本文件）
  - `sprints/<sid>.plan.md`
  - `sprints/<sid>.task_graph.json`
  - `sprints/<sid>.planning.html`
  - `sprints/<sid>.workstream-{A,B,C,D,E}-*.md`（builder N1..N5 产出）
  - `sprints/<sid>.migration.md`（PM 显式要求路径）
  - `~/.solar/harness/schemas/physical-operators.schema.v2.draft.json`（PM 显式要求：v2 草案）
- **严格禁止**（per Hard Rules + Constraints C1..C10 + Non-Goals）：
  - 改 `physical-operators.json`（生产配置；本 sprint 仅产 schema v2 草案）
  - 改 `operator_runtime.py` / `operatord.py` / `multi_task_runner.py` / `graph_node_dispatcher.py`（本 sprint 不动代码）
  - 删 disabled operator / kill 无关 pane / 删历史 task 目录
  - 写 raw secret / token / cookie / OAuth content（仅 `secret_ref` / `key_env` / `account_label`）
  - 在任务中临时切模型 / wrapper / auth
  - DAG 节点写死 `provider/model/profile` 字符串
  - 引入新进程模型（systemd / Docker / k8s）→ 必须保持 CLI + tmux + sqlite
  - 改 5-pane 拓扑（pane 0/1/2/3/4 角色绑定保持）
  - 改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact / ThunderOMLX 任何路径
  - block 或 rewrite `sprint-20260523-lease-based-model-fleet-runtime` 任何文件
  - 跳过 evaluator → 必须 `planner → evaluator/architect 二审` 路径
- 知识库降级 `mirage:nonzero`：本 sprint self-contained（PRD 内含全部参考资产路径）。

## 1. 三层架构（per PRD §Product Goal）

```
┌─────────────────────────────────────────────────────────────────┐
│                  Operator Registry  (FR1 / D1 / D3)             │
│   physical-operators.schema.v2.json                             │
│   physical / surface / model / endpoint / auth / quota /        │
│   capability / policy / state / metrics / routing               │
│   secret 仅以 secret_ref / key_env / account_label 引用         │
└─────────────────────┬───────────────────────────────────────────┘
                      │ static registration (config)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Operator Runtime  (FR2 / D2 / D4)              │
│   operator_runtime.py  +  operatord.py                          │
│   lease / heartbeat / runtime_state / drain / cooldown          │
│   failure_transfer / quota_clock / auth_probe                   │
│   pane = physical host (NOT scheduler endpoint)                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │ runtime status (sqlite)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DAG Scheduler  (FR3 / D1)                      │
│   graph_node_dispatcher.py + autopilot                          │
│   选择算法: task_type × required_capabilities ×                 │
│            preferred_operator_classes × constraints ×           │
│            quota_reserve × policy_guard × verifier_separation   │
└─────────────────────┬───────────────────────────────────────────┘
                      │ lease grant
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              Physical Hosts (tmux panes)                        │
│   pane 0 planner(opus) / pane 1 builder(glm-5.1) /              │
│   pane 2 evaluator(glm-5.1) / pane 3 architect(opus) /          │
│   pane 4 PM (本 pane)                                            │
│   外部 runtime: Codex CLI / Antigravity / ThunderOMLX local     │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Workstream 映射

| Workstream | DAG Node | 产出 |
|------------|----------|------|
| A Registry Lock | N1 | `<sid>.workstream-A-registry-lock.md` + `schemas/physical-operators.schema.v2.draft.json` |
| B Runtime Lock | N2 | `<sid>.workstream-B-runtime-lock.md` |
| C Scheduler Lock | N3 | `<sid>.workstream-C-scheduler-lock.md` |
| D Observability Lock | N4 | `<sid>.workstream-D-observability-lock.md` |
| E Migration Lock | N5 | `<sid>.migration.md` + `<sid>.workstream-E-migration-lock.md` |

依赖：N1 → {N2, N3}；N3 → N4；{N1, N2, N3, N4} → N5。

## 3. Registry Schema v2 草案（N1 输入要点）

schema v2 字段集合（11 顶层 key，per FR1）：

```yaml
operator_id: pane-aiops-0-planner-opus47          # 命名规范见 Q1 答案
physical:                                         # 物理宿主元数据
  host_type: tmux_pane | codex_cli | antigravity | thunderomlx_local
  pane_id: "%0"                                   # 仅 display；不当 durable key
  session: solar-aiops
  window: planner
surface:                                          # 用户可见的接入面
  surface_type: claude_code_pane | codex_bridge | http_endpoint
  invoke_cmd: "claude code"                       # bootstrap; tmux send-keys 只此用途
model:                                            # 固定模型绑定（D3）
  provider: anthropic | google | openai | local
  model_id: claude-opus-4-7                       # 兼容兜底 (FR6)
  binding_locked_at: "2026-05-23T19:20Z"
endpoint:
  endpoint_type: cli | http | sdk
  base_url: null
auth:                                             # 仅 ref（C2）
  account_label: anthropic_max_personal_01
  secret_ref: keychain:com.solar.anthropic-max-01
  key_env: ANTHROPIC_MAX_PERSONAL_01_BEARER
  last_verified_at: "2026-05-23T18:00Z"
quota:                                            # 软限 + 远端 429 为真相 (R3)
  pool: anthropic_subscription_interactive
  monthly_budget_units: null                      # null = use upstream
  reserve_for: [ARCH_DESIGN, ROOT_CAUSE_DEBUG, FINAL_REVIEW]
  avoid_for: [BULK_DOC_EDIT, TRIVIAL_RENAME, GREP_SCAN]
capability:                                       # CapabilityProfile (Q2 答案)
  operator_class: planner | builder | evaluator | architect | pm | external
  task_types: [ARCH_DESIGN, IMPL, REVIEW, DEBUG, ...]
  capability_tags:
    architecture_reasoning: 5
    code_impl: 4
    long_context: 5
  capability_schema_version: "v1"
policy:                                           # PermissionPolicy (R9)
  allowed_write_scope: patch_only | repo_local | none
  allowed_shell_scope: repo_local
  allowed_network: docs_only
  allowed_secrets: none
  destructive_actions: denied
  git_push: denied
  payment_or_external_action: denied
  requires_human_for: [delete_files, modify_ci, touch_secrets]
  redact_envs: [ANTHROPIC_*, OPENAI_*, GOOGLE_*]
state:                                            # RuntimeState (FR2)
  runtime_state: available | busy | draining | quota_exhausted |
                 auth_expired | disabled | unavailable | cooldown
  last_state_change_at: "..."
  last_lease_id: null
metrics:                                          # Observability hook
  recent_success_rate: null                       # populated by Operator Runtime
  last_result_at: null
  recent_failure_kinds: []
routing:                                          # Scheduler hint
  preferred_for_classes: [DeepArchitect, RootCauseDebugger]
  fallback_ladder:
    - operator_id: pane-aiops-3-architect-opus47
    - operator_id: pane-aiops-0-planner-opus47
  verifier_class_blocklist: []                    # writer 自己不能复用做 verifier
```

**兼容规则 (R1, FR6)**：
- 旧 `physical-operators.json` 字段必须仍可加载（schema v2 加载器接受 v1 输入）
- 新增字段全部 optional + default
- 缺字段时 validator 给出 warn 而非 reject（至少 1 个 sprint 兼容期）
- 旧 `preferred_operator` 字段保留为硬指定语义（per Mandatory Design Decisions §2）

**Q1 答案**：`operator_id = pane-<host>-<pane_index>-<role>-<model_slug>`，例如 `pane-aiops-0-planner-opus47`。允许 `alias` 字段（仅 display）。

**Q2 答案**：`capability_tags` 用结构化键值（0-5 int），不是枚举或 free-form。`capability_schema_version` 字段允许后续 bump。

## 4. Runtime 状态机（N2 输入要点，per FR2 / Q5）

```
canonical lifecycle:

  UNREGISTERED → BOOTING → AVAILABLE → LEASED → BUSY → FINALIZING → AVAILABLE
                                  │
                                  ↓ (drain signal)
                              DRAINING → COOLDOWN → AVAILABLE

exception states (all branch off AVAILABLE / BUSY):

  QUOTA_EXHAUSTED   ← 429 / quota probe (R3)
  AUTH_EXPIRED      ← auth.last_verified_at TTL 超时 (R6)
  DISABLED          ← 运维手动停用（不删，可恢复）
  UNAVAILABLE       ← pane 死掉 / process 崩溃 (C7)
  HUMAN_REQUIRED    ← policy 触发人工 escalation
```

**Lease 协议（per R2 + C7）**：

```yaml
lease:
  lease_id: lease-20260523-192001-pane-aiops-0-planner-001
  task_id: dag-N1-pane-as-operator
  sprint_id: sprint-20260523-pane-as-physical-operator-architecture
  node_id: N1
  operator_id: pane-aiops-0-planner-opus47
  acquired_at: "2026-05-23T19:20:01Z"
  expires_at: "2026-05-23T19:50:01Z"          # lease_ttl
  heartbeat_timeout_sec: 90                   # heartbeat_grace
  drain_timeout_sec: 60
  renewable: true
  preemptible_by: [evaluator]                 # evaluator pane 可强制 break (R2)
  lease_token: <sqlite CAS token>             # 防止双 lease (R5)
```

**Failure transfer 决策树（per Q5）**：

```
on operator failure:
  1. if cause = QUOTA_EXHAUSTED → retry on same operator_class fallback ladder
  2. if cause = AUTH_EXPIRED → operator → AUTH_EXPIRED state; pick next in
     routing.fallback_ladder (same class first)
  3. if cause = UNAVAILABLE (pane dead) → mark UNAVAILABLE; auto-spawn 不在本
     sprint 范围，只挑 fallback
  4. if cause = task-level error (timeout / oom) → escalate one class up
     (builder fail → architect 接管，需 user/PM 显式批准；不是自动)
  5. evidence_log 强制记录原因
```

## 5. Scheduler 选择算法（N3 输入要点，per FR3）

伪代码：

```python
def select_operator(task):
    # 1. operator_class filter
    candidates = registry.filter(
        operator_class__in=task.preferred_operator_classes
    )
    # 2. capability gate
    candidates = [op for op in candidates
                  if op.matches(task.required_capabilities)]
    # 3. policy gate (hard deny)
    candidates = [op for op in candidates
                  if op.policy.permits(task.requested_actions)]
    # 4. runtime_state filter
    candidates = [op for op in candidates
                  if op.state.runtime_state == "available"]
    # 5. quota reserve (avoid_for high-value pools)
    if task.task_type in {"BULK_DOC_EDIT", "TRIVIAL_RENAME", "GREP_SCAN"}:
        candidates = [op for op in candidates
                      if task.task_type not in op.quota.avoid_for]
    # 6. verifier separation (Q6 answer: operator_id ≠, class allowed equal)
    if task.role == "verifier":
        candidates = [op for op in candidates
                      if op.operator_id != task.writer_operator_id]
        if task.high_risk:
            candidates = [op for op in candidates
                          if op.model.provider != task.writer_provider]
    # 7. scoring (capability_match + freshness + recent_success)
    return rank(candidates, by=OperatorScore).first()
```

**Q6 答案**：基线要求 `verifier.operator_id ≠ writer.operator_id`；高风险任务 (`high_risk=true`) 额外要求 `provider != writer.provider`（cross-provider）。

**Q3 答案**：lease 默认按 task；长程 sprint 允许同 operator 续 lease（renewable=true）但每 round 需要重新 acquire。

**Q4 答案**：quota 字段建模 `pool` 共享（同 `pool` id 共享 budget）；同 pool 多 operator 视为 quota 兄弟（R5 sqlite CAS 防止双 lease）。

**Q11 答案**：DRAINING / COOLDOWN 期间 **不允许** 接新 lease；evaluator 复用做只读验证也算 lease（要遵守 quota）。

## 6. Observability（N4 输入要点，per FR5）

8765 status payload schema：

```yaml
operator_fleet:
  total: 5
  available: 3
  busy: 1
  draining: 1
  by_state:
    quota_exhausted: 0
    auth_expired: 0
    disabled: 0
recent_results:
  - operator_id: pane-aiops-0-planner-opus47
    task_id: dag-N1
    result: passed
    ts: "..."
alerts:
  - operator_id: pane-aiops-3-architect-opus47
    severity: warn
    kind: auth_about_to_expire
    detail: "last_verified_at > 22h ago"
active_leases:
  - lease_id: lease-...
    operator_id: pane-aiops-0-planner-opus47
    sprint_id: ...
    task_id: ...
    expires_at: ...
runtime_drift_evidence:
  - operator_id: ...
    incident: model_id_changed_mid_lease
    detected_at: ...
    action_taken: lease_invalidated
```

**Q9 答案**：8765 默认升级输出（含 operator_fleet 摘要），保留 `--legacy-view` flag 退回旧。

**SQL view (sqlite)**：

```sql
CREATE VIEW operator_fleet_summary AS
  SELECT operator_class, runtime_state, COUNT(*) AS n
  FROM operator_state
  GROUP BY operator_class, runtime_state;

CREATE VIEW recent_results AS
  SELECT operator_id, task_id, result, ts
  FROM result_log
  ORDER BY ts DESC LIMIT 20;
```

5s 内 cache（per R7）。

## 7. Migration / Compatibility（N5 输入要点，per FR6 + R8）

**Q7 答案**：兼容期 1 个 sprint 起步；视实测 sprint pass 率决定是否延 1 个。

**legacy → operator_id mapping 表**（N5 产出 `<sid>.migration.md`）：

```yaml
legacy_provider_model_map:
  - legacy_key: claude-opus-4-7+pane0
    new_operator_id: pane-aiops-0-planner-opus47
  - legacy_key: glm-5.1+pane1
    new_operator_id: pane-aiops-1-builder-glm51
  - legacy_key: glm-5.1+pane2
    new_operator_id: pane-aiops-2-evaluator-glm51
  - legacy_key: claude-opus-4-7+pane3
    new_operator_id: pane-aiops-3-architect-opus47
```

**Rollout phases**：

1. **Phase 0 (本 sprint)** — design / schema v2 草案 / migration plan，不动 production
2. **Phase 1 (next sprint)** — schema v2 加载器（接受 v1 + v2）+ unit test
3. **Phase 2** — operator_runtime 改造（lease/heartbeat 统一）
4. **Phase 3** — scheduler 改造（capability/policy 选择）
5. **Phase 4** — observability 8765 升级
6. **Phase 5** — legacy provider/model/profile 路径 deprecation warn
7. **Phase 6** — legacy 路径删除（最早 1 个 sprint 后）

**Rollback 命令**：

```bash
# 任何 phase 都能回到 phase 0
solar-harness operator schema-pin --version v1
solar-harness operator runtime-mode --legacy
solar-harness operator scheduler-mode --legacy
```

**Q8 答案**：本机 runtime (ThunderOMLX/FlashMLX) 纳入 operator registry，`physical.host_type = thunderomlx_local`；class = `external`，与 pane operator 同等管理。

## 8. Verifier Separation（per Contract Mandatory Design Decision §4）

每个需要审查的 task 必须满足：

| Rule | Enforce 点 |
|------|-----------|
| `verifier.operator_id ≠ writer.operator_id` | Scheduler `select_operator` step 6 |
| 高风险 task `verifier.provider ≠ writer.provider` | Scheduler step 6 (high_risk branch) |
| Verifier 决策必须机器可读（YAML） | per lease-fleet-runtime sprint sync |

本 sprint task_graph 节点本身就 enforce：每个 node 显式声明 `writer_operator_class` 与 `verifier_operator_class`，不允许相同。

## 9. Quota Reserve（per Contract Mandatory Design Decision §5）

高价值任务保护：

```yaml
reserve_for:
  ARCH_DESIGN: [architect, planner]      # 仅 architect/planner class
  ROOT_CAUSE_DEBUG: [architect, builder] # architect 优先
  FINAL_REVIEW: [evaluator, architect]   # 二者均可
```

低价值批量任务必须避开：

```yaml
avoid_for: [BULK_DOC_EDIT, TRIVIAL_RENAME, GREP_SCAN]
```

任一被注册为 `cost_tier=premium` 的 operator 必须默认 `avoid_for` 含上面三项。

## 10. Secret Safety（per Hard Rules + C2 + R9）

- registry 仅写 `secret_ref` / `key_env` / `account_label`
- ATLAS evidence collection 时 mask `redact_envs` 列表
- handoff / log / status / report 任何位置都不允许 raw secret 字面值
- 验证：`grep -rE "(sk-|bearer\s+|ANTHROPIC.*=)" sprints/<sid>.*.md` 必须无命中

**Q10 答案**：默认 `key_env` (env var)；可选 `keychain:` 前缀（macOS Keychain）；1Password CLI 留作 future option，不在 P0。

## 11. 非目标（明确禁止）

- 不一次性删除所有旧 profile 路由
- 不一次性启用全部 disabled operator
- 不在本 sprint 完成所有 provider 真执行器重写
- 不允许 raw secret 进 registry / log / status / report
- 不允许把 tmux pane 继续当 "可任意临时切模型" 通用壳
- 不引入新进程模型（systemd / Docker / k8s）
- 不写 `/tmp` （C4）
- 不改 5-pane 拓扑（C8）
- 不改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 不动 ThunderOMLX 任何代码
- 不 block 或 rewrite `sprint-20260523-lease-based-model-fleet-runtime`
- 不使用乐观词

## 12. 给 evaluator / architect 二审的接力

evaluator 必须按 Contract §Planner Done Definition + §Acceptance Gates 逐项核：

1. Registry / Runtime / Scheduler 分层是否清晰
2. Rollout 顺序 + 兼容策略 + failure transfer 是否完整
3. task_graph.json 每个节点是否有 goal/depends_on/write_scope/required_capabilities/preferred_operator_class/acceptance
4. writer/verifier operator_class 是否分离
5. 关键风险是否有 stop rules（R1..R10 全部）
6. PRD A1-A8 acceptance 是否 1:1 映射到 DAG 节点
7. 12 Open Questions Q1..Q12 是否在 design.md 显式回答
8. migration.md 是否含 legacy → operator_id 映射表 + rollout phases + rollback 命令
9. schema v2 草案是否覆盖 11 顶层字段
10. secret_ref / key_env / account_label 是否严格不出现 raw 字面值

architect 二审（pane 3 opus）：把 design.md + migration.md + schema v2 草案做 deliberation；产出二审意见到 `<sid>.architect-review.md`（如有差异）。
