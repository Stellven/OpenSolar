# Design — Agent Plan Optimizer Foundation (APO/AQO)

sprint_id: `sprint-20260523-agent-plan-optimizer-foundation`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete (blocked spec — N0 gate enforces predecessor wait)`
generated_at: `2026-05-24T03:48:00Z`
knowledge_context: `solar-harness context inject used (mirage nonzero -> qmd/obsidian/solar_db fallback)`
dependency_gate: **BLOCKED** (per `.dependency-gate-evidence.md` 2026-05-24T03:41Z)
  - predecessor 1: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation` = active/planning_complete (NOT finalized)
  - predecessor 2: `sprint-20260523-requirement-compiler-quality-loop` = drafting/prd_ready (NOT finalized)
  - accepted dir: empty
parallel_protect: 父/兄弟 in-flight sprints（pane-as-physical-operator-architecture / physical-operator-taxonomy-truthification / operator-class-compatibility-cutover / actor-host-runtime-completion-audit / pm-pane-requirement-compiler-backend-foundation / requirement-compiler-quality-loop / gepa-optimize-anything-implementation 等）read-only 引用，**不持其 lock，不 mutate 其 artifact**

## 0. 本切片的边界（强制 read-first + Dependency Gate）

- **P0 spec sprint**：定义 APO/AQO 优化器层的 architecture + algebra + cost model + rule engine + explain + 3 mode 接口契约；**实际优化器代码归 follow-up sprint**。
- **Dependency Gate（Hard Rules C1 + Non-Negotiables §1 + STOP-A）**：
  - 在 2 张前序 Requirement Compiler sprint **都进入 finalized/accepted** 前：
    - task_graph N0 是 hard dependency_gate_check node
    - N0 ready check 失败 → coordinator 自动延后；N1..N7 全部 blocked
    - planner / builder **不允许跳过 N0 直接做 N1..N7 实际产物**
  - 本 design.md / plan.md / planning.html 是 **spec-only 文档**：描述 APO 长什么样，不预先创建 algebra schema/cost-model spec/explain schema 等 deliverables（那些归 N1..N7 builder 执行，且必须等 N0 gate 解锁）
  - dependency 解锁路径：predecessor finalize → N0 ready check 自动通过 → coordinator 派 N1..N7
- **严格禁止**（per Hard Rules + Constraints C1..C14 + Non-Negotiables §1..§5）：
  - 重写 task_graph.json（**已就位且正确**：8 节点 N0..N7，N0 强 hard gate）
  - 跳过 N0 提前开始 N1..N7（C1 + STOP-A 违规）
  - 把 cost model 外包给 LLM ranking（C4 + Non-Negotiables §2）
  - 把 logical algebra 写成 prose（必须 schema-driven，Non-Negotiables §3）
  - 把 enforcer 标 best-effort 或可绕过（C11 + Non-Negotiables §4）
  - 跳过 architect (pane 3) 二审直接交付（Non-Negotiables §5）
  - 另起第二套 runtime（C2 — 复用现有 operator/pane/lease/quota/capability/evidence）
  - 引入 learned optimizer（C4 — P0 deterministic heuristic only）
  - logical/physical/enforcer 三层混淆（C5）
  - runtime state 污染 plan spec（C6）
  - 引入新 PyPI 依赖（C7 — stdlib + JSON Schema only）
  - 写 /tmp（C8）
  - mutate in-flight sprint artifact（C9）
  - raw secret 入 plan（C10）
  - enforcer 因 cost 高跳过（C11）
  - 无限 replan（C12 — max_replan_rounds + max_total_cost + verifier_confidence_threshold 三选一触发即停）
  - Explain prose-only（C13 — 必须机读 JSON/YAML schema）
  - 引入新进程模型（C14 — systemd/Docker/k8s 禁）
- 知识库降级 `mirage:nonzero`：本 sprint self-contained。

## 1. 定位：从 scheduler 升级到 APO/AQO

```
当前 Solar-harness（pre-APO）          升级后（APO/AQO）
---------------------------------       --------------------------------
operator + lease + quota + capability   + Intent IR (来自 Requirement Compiler)
+ evidence ledger + taxonomy            + Logical Agent Plan (algebra)
+ scheduler "选对一个 operator"          + Rewrite Rules (规则引擎)
                                        + Physical Plan Enumeration (多候选)
                                        + Cost Model (10 项 vector)
                                        + Enforcer (plan-time 硬注入)
                                        + Plan Memo (缓存等价计划)
                                        + Adaptive Replan (AQE 风格)
                                        + Explain (机读 / replay / candidates)
```

类比：数据库的 Calcite Volcano/Cascades + Spark AQE + DuckDB optimizer，迁到 agent planning 层。

## 2. 核心链路

```
User Goal (来自 Requirement Compiler IR)
   ↓
Intent IR        ← APO 入口；从 IR 转出 Goal+Constraints+Type
   ↓ (compile)
Logical Agent Plan (Algebra) — 15 logical operator 组合
   ↓ (rewrite — Rule Engine 8 条 P0 规则)
Logical Plan v2 (equivalence-preserving rewrite，例如插入 VerifyAfterWrite)
   ↓ (physical enumeration)
Physical Plan Candidates (logical → physical operator multi-binding)
   ↓ (cost model — 10 项 vector + 3 mode 权重 profile)
Selected Physical Plan + Explain (why selected / why rejected)
   ↓ (lease-based execution via existing operator runtime — C2 复用)
Runtime Feedback (lease failed / quota exhausted / verifier rejected / test failed / benchmark regressed)
   ↓ (Adaptive Replan — AQE 风格 local replan)
Plan v2 / v3 ... 直到 stop rule (max_replan_rounds / max_total_cost / verifier_confidence_threshold)
   ↓
Final Explain / Replay / PlanMemo
```

## 3. Logical Algebra（N1 产出，per PRD §5 + Handoff 设计点 1）

15 logical operator（schema-driven，不允许 prose-only）：

| Operator | Input | Output | Cost hint | task_type 映射 |
|----------|-------|--------|-----------|---------------|
| `ScanContext` | repo path / scope | context_packet | low | LOW_COST_SCAN |
| `UnderstandGoal` | Intent IR | parsed_goal | low | ARCH_DESIGN (prelude) |
| `DecomposeTask` | parsed_goal | sub_tasks[] | medium | MULTI_FILE_REFACTOR (prelude) |
| `DesignSolution` | sub_tasks | design_doc | high (premium reserve) | ARCH_DESIGN |
| `ExploreAlternatives` | design_doc | alternative_designs[] | high | PARALLEL_EXPLORATION |
| `ImplementPatch` | design / sub_task | patch / artifact | medium | CODE_IMPL |
| `GenerateTests` | patch / spec | tests | medium | TEST_GEN |
| `RunTests` | tests | test_results | low (shell-bound) | TEST_RUN |
| `RunBenchmark` | benchmark spec | benchmark_results | medium | BENCHMARK_RUN |
| `DebugRCA` | failure logs | rca_doc | high (premium reserve) | ROOT_CAUSE_DEBUG |
| `ReviewPatch` | patch | review_decision | medium | FINAL_REVIEW |
| `VerifyClaim` | claim + evidence | verifier_decision | medium | FINAL_REVIEW |
| `SynthesizeReport` | multi-input | report.md | medium | RESEARCH_SYNTHESIS / DOC_REPORT |
| `CompressContext` | context_packet | compressed_context | low | LOW_COST_SCAN |
| `AskHuman` | escalation reason | human_response | n/a (blocks until human) | SECURITY_SENSITIVE |

**Schema 要求**：`schemas/agent-logical-algebra.schema.v1.draft.json` 必须包含每 operator 的：
- `name`
- `input_schema` / `output_schema` (JSON Schema fragments)
- `properties` (idempotent, deterministic, side-effects)
- `cost_hint` (low / medium / high / premium-reserve)
- `task_type_mapping` (引用 operator-class-compatibility-cutover 的 task_type taxonomy)
- 严禁引用 operator_id（C5 logical 不绑 physical）

## 4. Rewrite Rule Engine（N2 产出，per PRD §5 + Handoff 设计点 2）

8 条 P0 rule（`rewrite-rules.v1.draft.yaml`）：

| Rule | Trigger | Pattern | Rewrite Action | Cost delta | Safety class | P0 必须 |
|------|---------|---------|----------------|------------|--------------|---------|
| `LocalPreScan` | 任何 DesignSolution 前 | DesignSolution | ScanContext → DesignSolution | +low (context cost) | safe | yes |
| `FanOutExploration` | high_risk + Exploratory mode | DesignSolution | DesignSolution → ExploreAlternatives → DesignSolution[k=3] | +medium | safe | yes |
| `VerifyAfterWrite` | 任何 ImplementPatch 后 | ImplementPatch | ImplementPatch → ReviewPatch + VerifyClaim | +medium | **hard** (C11) | yes |
| `WriterVerifierSeparation` | ReviewPatch / VerifyClaim | Reviewer == Writer | force pick different operator_id; high_risk → different provider | 0 | **hard** (C11) | yes |
| `QuotaReserve` | DesignSolution / DebugRCA / FINAL_REVIEW | premium operator candidate | enforce reserve_for tag; cheap operators rejected for these task_types | 0 | **hard** | yes |
| `SandboxEnforcer` | Browser / GoogleStack / LocalPrivacy operator | physical plan | inject sandbox + redact_envs + allowlist | 0 | **hard** (C11) | yes |
| `ContextMaterialization` | DecomposeTask 后 | sub_tasks | ScanContext → CompressContext → 各 sub_task 注入 context_packet | +low | safe | yes |
| `AdaptiveReplan` | runtime feedback FAIL | failed node + downstream | local replan with stop rule (per C12) | +medium | **hard** (stop rule enforce) | yes |

**Hard rules**（标记的 5 条）→ enforcer 类，**plan-time 必注入**，不允许 cost-based 跳过。

## 5. Cost Model（N3 产出，per PRD §5 + Handoff 设计点 3）

10 项 cost vector + 公式（deterministic，可手算，可单测）：

```text
PlanCost(plan) =
    capability_fit         * w_cap     # operator capability_profile 匹配率 (0-1)
  + historical_success     * w_hist    # 本 repo / task_type / operator 历史 PASS 率 (0-1)
  + quota_health           * w_quota   # 剩余 quota 比例 (0-1)
  + risk_fit               * w_risk    # operator.risk_profile 满足 task.constraints (0-1)
  + latency_fit            * w_lat     # 1 - normalize(p50_latency) (0-1)
  + context_affinity       * w_ctx     # 与 plan_memo 历史决策 affinity (0-1; per truthification 公式)
  + cost_efficiency        * w_eff     # 1 / cost_tier (premium=1/4, standard=1/2, cheap=1/1)
  - recent_failure_penalty * w_rfp     # 末 N task 失败率 (0-1; negative weight)
  - stale_context_penalty  * w_stale   # context > 80% 或同 topic 连跑 > 3 task (0-1; negative)
  - verifier_conflict_penalty * w_vcp  # writer==verifier_class + high_risk + same_provider (per truthification Q8)
```

**3 mode 权重 profile**：

| Weight | Conservative | Exploratory | Economy |
|--------|--------------|-------------|---------|
| w_cap | 0.20 | 0.15 | 0.20 |
| w_hist | 0.20 | 0.15 | 0.15 |
| w_quota | 0.15 | 0.10 | 0.20 |
| w_risk | **0.20** (强) | 0.10 | 0.10 |
| w_lat | 0.05 | 0.10 | 0.15 |
| w_ctx | 0.10 | 0.10 | 0.10 |
| w_eff | 0.05 | 0.05 | **0.20** (强) |
| w_rfp | 0.20 | 0.10 | 0.15 |
| w_stale | 0.15 | 0.05 | 0.10 |
| w_vcp | **0.30 hard** | 0.20 | 0.15 |

**Mode 选择策略**：

- task_type ∈ {ARCH_DESIGN, ROOT_CAUSE_DEBUG, FINAL_REVIEW, SECURITY_SENSITIVE} → **Conservative**（默认）
- task_type ∈ {PARALLEL_EXPLORATION, UI_PROTOTYPE, FAST_FANOUT, RESEARCH_SYNTHESIS} → **Exploratory**
- task_type ∈ {LOW_COST_SCAN, TRIVIAL_RENAME, BULK_DOC_EDIT, DOC_REPORT} → **Economy**
- 其余 → Conservative（保守默认）

**数据来源**（明示，per Handoff 设计点 3）：

| 字段 | 来源 |
|------|------|
| capability_fit | `config/agent-actors.json` (或 legacy `physical-operators.json` via cutover) |
| historical_success | sqlite `task_result_log` 表 (按 repo/task_type/operator group) |
| quota_health | `~/.solar/harness/run/operator-state/<operator_id>/quota.json` |
| risk_fit | `config/agent-actors.json` risk_profile section |
| latency_fit | sqlite `task_latency_log` 表 p50 |
| context_affinity | `plan-memo/<sprint>/<task>/affinity.json` (per truthification Q7 公式) |
| cost_efficiency | `config/agent-actors.json` cost_profile.cost_tier |
| recent_failure_penalty | sqlite `task_result_log` 末 N=10 task |
| stale_context_penalty | runtime state (token usage + topic affinity) |
| verifier_conflict_penalty | task.role + writer.operator_id / writer.provider |

## 6. Physical Plan Enumeration + Plan Memo（N4 产出，per Handoff 设计点 4）

**Logical → Physical 展开规则**：

- 每个 logical operator 通过 `task_type_mapping` 找到对应 canonical operator class（per compatibility-cutover）
- 每个 canonical class 通过 `bindings` （per taxonomy-truthification）找到候选 physical operator_id 列表
- Plan enumeration 策略：
  - **多 candidate**：DesignSolution / DebugRCA / ReviewPatch / VerifyClaim（high-value，值得对比）
  - **单 candidate**：ScanContext / RunTests / CompressContext（low-value，省 cost）
  - Exploratory mode：所有 high-value 节点强制 multi-candidate (k=2-3)

**Plan Memo schema** (`plan-memo/<sprint>/<task_hash>.json`)：

```json
{
  "task_hash": "<sha256 of Intent IR>",
  "logical_plan_key": "<canonical sort of algebra tree>",
  "candidates": [
    {"physical_plan_id": "p001", "cost_vector": {...}, "rejected": false},
    {"physical_plan_id": "p002", "cost_vector": {...}, "rejected": true, "reason": "..."}
  ],
  "selected": "p001",
  "cache_ttl_sec": 86400,
  "invalidation_triggers": ["operator_registry_change", "binding_change", "cost_model_weight_change"]
}
```

**Cache key**: `(repo_id, task_type, logical_plan_key, mode)`
**TTL**: 24h 默认；可被 invalidation_triggers 提前作废
**Invalidation**: registry 变 / binding 变 / cost weight 变 / explain 用户标记 stale

## 7. Adaptive Replan + Runtime Feedback（N5 产出，per Handoff 设计点 5）

**Runtime feedback 触发条件**：

| Trigger | Source | Replan scope |
|---------|--------|--------------|
| `lease_failed` | operator_runtime | local node (same logical, alt physical) |
| `quota_exhausted` | quota.json | local node (alt physical, avoid same pool) |
| `verifier_rejected` | verifier_decision.yaml | local sub-plan (writer + verifier 重做) |
| `test_failed` | test_results | local sub-plan (DesignSolution → ImplementPatch → RunTests 重跑) |
| `benchmark_regressed` | benchmark_results | sub-plan rewind to DesignSolution |
| `human_required` | AskHuman | **block** until human responds; not replan |

**Stop rules（per C12，三选一触发即停）**：

```yaml
adaptive_replan_stop_rules:
  max_replan_rounds: 3  # 默认；Conservative=2 / Exploratory=5 / Economy=1
  max_total_cost: 10.0  # 累计 cost score (unit normalized)
  verifier_confidence_threshold: 0.85  # 达到即停（PASS_WITH_WARNINGS 视为 0.7）
```

任一触发 → 停止 replan + 写 `runtime_feedback.jsonl` final entry + Explain 标 `stopped_by: <rule>`。

**Runtime state 隔离（C6）**：

- `plan_spec/`（logical + physical declarative）— 不变
- `task_dag.state.json` + `runtime_feedback.jsonl`（runtime mutable）— 单独目录
- replan 产 plan_spec v2，不 in-place mutate v1

## 8. Explain Plan Schema（N6 产出，per Handoff 设计点 6 + C13 机读）

`schemas/explain-plan.schema.v1.draft.json` 必含字段：

```yaml
explain_plan:
  schema_version: "explain-plan.v1"
  task_hash: <sha256>
  selected_plan:
    physical_plan_id: p001
    cost_total: 0.82
    cost_vector: {capability_fit: 0.9, ...}
    operator_chain: [DeepArchitect→opus47_pane0, ...]
  candidates:
    - physical_plan_id: p001
      selected: true
      cost_total: 0.82
    - physical_plan_id: p002
      selected: false
      rejected_reason: "verifier_conflict_penalty too high (writer==verifier_class)"
      cost_total: 0.65
  rewrite_trace:
    - rule: LocalPreScan
      applied_at: <plan path>
      cost_delta: +0.05
    - rule: VerifyAfterWrite
      applied_at: <plan path>
      cost_delta: +0.15
  rule_firings:
    LocalPreScan: 1
    VerifyAfterWrite: 1
    WriterVerifierSeparation: 1
    ...
  why_selected: "lowest cost_total after enforcer rules; mode=Conservative; w_vcp hard constraint satisfied"
  why_rejected:
    p002: "verifier_conflict_penalty 0.18 > threshold; writer==verifier_class"
    p003: "stale_context_penalty 0.22; topic连跑>3 task"
  replan_history:
    - round: 1
      trigger: verifier_rejected
      previous_plan: p001
      new_plan: p004
      cost_delta: +0.10
  stopped_by: null   # 或 max_replan_rounds / max_total_cost / verifier_confidence_threshold
```

**CLI scaffolding**：

```bash
solar-harness optimize explain <task>     # 输出 JSON (机读) or pretty (人读)
solar-harness optimize candidates <task>  # 列出全候选 + cost vectors
solar-harness optimize replay <plan_memo_id>  # 用历史 plan 重跑
solar-harness optimize compare <plan_a> <plan_b>  # 对比两 plan
solar-harness optimize why <plan_id>      # 详细 why-selected / why-rejected
```

## 9. 3 运行模式（per PRD §5）

| Mode | 默认任务 | fan-out | model 使用 | verification | quota | 替代场景 |
|------|---------|---------|------------|--------------|-------|---------|
| Conservative | ARCH_DESIGN / ROOT_CAUSE_DEBUG / FINAL_REVIEW / SECURITY_SENSITIVE | 单 candidate (除 high-value 节点 k=2) | 优先 opus / Claude | hard VerifyAfterWrite + WriterVerifierSeparation + high_risk cross-provider | 严格 reserve | 默认 |
| Exploratory | PARALLEL_EXPLORATION / UI_PROTOTYPE / FAST_FANOUT / RESEARCH_SYNTHESIS | multi candidate k=2-3 | mixed (Antigravity fan-out + Claude critique) | 必 evaluator 二审 | 宽松（允许 fan-out budget） | research / 多方案 |
| Economy | LOW_COST_SCAN / TRIVIAL_RENAME / BULK_DOC_EDIT / DOC_REPORT | 单 candidate | 优先 cheap (Gemini Flash / Codex mini) | optional review (skip if low-risk) | tight cost budget | bulk / 低风险 |

## 10. 复用现有底层（C2 严格）

| APO 层 | 依赖现有底层 | 不重做 |
|--------|-------------|--------|
| Intent IR | Requirement Compiler IR (per 前序 sprint backend-foundation) | 不另起 IR |
| Logical Algebra | task_type taxonomy (per cutover) | 不重定义 task_type |
| Physical Plan | operator/pane registry (per pane-as-physical-operator-architecture) | 不另起 operator |
| Cost Model | capability/risk/cost profile (per taxonomy-truthification) | 不另起 profile |
| Lease execution | operator_runtime + operatord (per pane-as-physical-operator-architecture) | 不另起 runtime |
| Evidence ledger | sprint events.jsonl + accepted artifacts (per existing) | 不另起 ledger |
| Verifier separation | writer.operator_id ≠ verifier.operator_id (per truthification Q6) | 不重定义 |

## 11. 与 in-flight sprint 共存（C9）

| In-flight sprint | 状态 | 本 sprint 影响 |
|------------------|------|---------------|
| pane-as-physical-operator-architecture | drafting | read-only 引用 schema v2 草案 |
| physical-operator-taxonomy-truthification | reviewing | read-only 引用 10 class + scoring |
| operator-class-compatibility-cutover | active | read-only 引用 canonical mapping |
| actor-host-runtime-completion-audit | active | read-only 引用 13 升级点 audit |
| pm-pane-requirement-compiler-backend-foundation | active/planning_complete | **predecessor 1** — N0 gate 等其 finalized |
| requirement-compiler-quality-loop | drafting/prd_ready | **predecessor 2** — N0 gate 等其 finalized |
| gepa-optimize-anything-implementation | active | read-only 引用 GEPA 实施进展（APO 与 GEPA 是补集：GEPA 优化文本 artifact，APO 优化 plan 选择） |

本 sprint 不持任何 in-flight sprint 的 lock；不 mutate 任何 in-flight sprint 的 artifact。

## 12. Open Questions（per PRD §10）答案分配

| Q | 答案 |
|---|------|
| Q1 explain 首版 CLI-only vs UI | **CLI-only**（per C13 + 资源约束）；UI 留 follow-up sprint |
| Q2 PlanMemo repo-local vs fleet-global | **repo-local 优先**（per §6 cache key 含 repo_id）；fleet-global 留 follow-up（需 dedupe + invalidation 协议） |
| Q3 adaptive replan stop rule | **per node**（per §7 max_replan_rounds 默认 3 / Conservative 2 / Exploratory 5 / Economy 1）；plan / verifier confidence 作 secondary stop |

## 13. 非目标（per Non-Goals + Constraints + Non-Negotiables）

- 不重写 Requirement Compiler（C1 — 前序依赖）
- 不直接实施 learned optimizer（C4）
- 不绕过 N0 dependency gate 提前实施 N1..N7
- 不另起第二套 runtime（C2）
- 不引入 ML / LLM ranking（C4）
- 不混淆 logical/physical/enforcer 三层（C5）
- runtime state 不污染 plan spec（C6）
- 不引入新 PyPI 依赖（C7）
- 不写 /tmp（C8）
- 不 mutate in-flight sprint artifact（C9）
- 不 raw secret 入 plan（C10）
- 不允许 enforcer 因 cost 高跳过（C11）
- 不允许无限 replan（C12 — 三选一 stop rule）
- 不 Explain prose-only（C13）
- 不引入新进程模型（C14）
- 不动 `~/.solar/STATE.md` / epic.* / 其他 sprint
- 不使用乐观词

## 14. 接力 evaluator / architect 二审

evaluator 必须按 PRD §9 + Handoff 必备产出物 + acceptance gates 逐项核：

- 6 件草案产物：design.md / plan.md / task_graph.json + algebra-schema + rewrite-rules + cost-model-spec + explain-schema + dependency-gate-evidence
- N0 dependency gate 真实执行（不绕过）
- writer ≠ verifier class 全节点 enforce
- 6 enforcer rule 全部标 hard，不可绕过
- 3 mode + 10 cost vector + weights 全集
- Explain schema 机读（C13）

architect (pane 3 opus) 必须二审（Non-Negotiables §5）：

- Logical Algebra 与 task_type taxonomy 对齐
- Cost Model 与 truthification scoring 公式一致性
- Adaptive Replan stop rule 与 lease/operator 状态机不冲突
- APO 与 GEPA 边界清晰（GEPA 优化 artifact，APO 优化 plan）

依赖解锁后（predecessor 全 finalized）：coordinator 自动派 N0 → N1 → ... → N7。本 sprint 不主动 dispatch builder。
