# Design — Operator Architecture Convergence

sprint_id: `sprint-20260527-operator-architecture-convergence`
slice: `architecture-spec` (PRD ready → design/plan/task_graph 三件套)
role: planner
status: planning_complete
generated_at: 2026-05-28T18:05:00Z
knowledge_context: solar-harness context inject used (mirage:timeout → qmd/obsidian/solar_db fallback)
priority: P1
lane_hint: strategy
request_type: full_prd
upstream_truth: requirement_ir.json (REQ-000..003) + Contracts.yaml + prd.md
downstream: 实施 sprint (下游单独 epic 拆 selector / provider-registry / actor-derivation 三条迁移轨)

## 0. 切片定位

Solar Harness 一轮**架构收口** sprint。目标是把当前散落在三套实现里的 **scheduling 入口 / provider 适配 / actor registry** 收敛到三个统一抽象，以**显著降低接入新 provider 与新 model 的边际成本**。

本 sprint 是**规约层 (spec-only)**, 不写实施代码; 产出 design / plan / task_graph / handoff, 同时锁定迁移路径与验证 gate, 为下游实施 sprint 准备好可执行的合约。

**核心三件套** (与 PRD 第 1 段 1)/2)/3) 对齐):
1. **统一 Selector** — 所有调度入口收敛到单一 selector (现状: chain-watcher / autopilot / graph-scheduler / lease-broker 各有 ad-hoc 入口)
2. **Provider Adapter Registry** — 认证 / quota / error classification / command builder 四件事下沉到 adapter
3. **Actor Derived from Physical Operator** — actor 不再手工重复维护, 而是从 physical operator / template 派生

## 1. REQ → outcome 映射 (4 REQ 聚合为 5 outcome)

| outcome_id | 标题 | REQ 来源 | 节点 |
|------------|------|---------|------|
| O1 | 统一 Selector spec (entry inventory + 单一入口契约 + 漂移点清单) | REQ-000 ①, REQ-001 | N1 |
| O2 | Provider Adapter Registry spec (4 维 adapter shape: auth/quota/error/cmd + per-provider 例) | REQ-000 ②, REQ-001 | N2 |
| O3 | Actor Derivation spec (operator/template → actor 派生规则 + 去重检测 + 现存 drift 列表) | REQ-000 ③, REQ-001 | N3 |
| O4 | Migration & Compat Plan (兼容 shim + 迁移阶梯 + 验证 gate + rollback) | REQ-002 | N4 |
| O5 | Traceability & Handoff (每条 acceptance 映射到验证或 gate; REQ→outcome→node→gate 全链路) | REQ-003, REQ-001 | N5 (join) |

## 2. 5-Node DAG

```
                ┌─→ N1 unified_selector_spec         (O1, REQ-000/001)  ─┐
                ├─→ N2 provider_adapter_registry_spec (O2, REQ-000/001) ─┤
   (无上游) ────┼─→ N3 actor_derivation_spec          (O3, REQ-000/001) ─┼─→ N4 migration_compat_plan (O4, REQ-002) ─→ N5 traceability_handoff (O5, REQ-003) join
                └─→                                                       ─┘
```

- **Wave 1 (3 并行)**: N1 / N2 / N3 — 三件设计独立, write_scope 互斥 (各自子目录)
- **Wave 2**: N4 — 必须看到 N1/N2/N3 三份设计才能写迁移阶梯与回滚
- **Wave 3 (join)**: N5 — traceability + handoff 收口, 锁定 acceptance→gate 全映射

## 3. 节点内容大纲

### N1 unified_selector_spec.md (O1)
- **现状盘点**: 列出现存 4+ 个调度入口 (chain-watcher / autopilot tick / graph-scheduler dispatch / lease-broker pick) + 每个入口的硬编码点
- **统一 selector 契约**: 单一函数签名 `select(candidates, context) → decision`; 输入 = ready_nodes + pane_state + quota; 输出 = (node, pane, model) 三元组
- **入口收敛**: 现存入口转 thin caller, 统一调 selector
- **漂移检测**: drift_guard 规则 (任何新增调度入口必须 register; CI/lint 阻断绕过)
- **验收 ≥4**: 入口清单 ≥4 / 契约签名锁定 / 收敛路径每条入口都有 caller 映射 / drift_guard 规则列出

### N2 provider_adapter_registry_spec.md (O2)
- **现状盘点**: 现存 provider 接入点 (anthropic / openai / glm / deepseek / openrouter / codex-bridge 等) + 各自重复实现 (auth env / quota cap / error decode / command build)
- **Adapter shape (4 维)**:
  1. `auth.resolve(env) → credentials`
  2. `quota.check(model, ctx) → ok|rate_limited|exhausted`
  3. `error.classify(raw) → {kind, retryable, severity}` (统一 7 类 error: rate_limit / auth_fail / quota_exhaust / model_unavail / context_overflow / network / unknown)
  4. `command.build(intent, model, payload) → exec_spec`
- **Registry API**: `registry.register(provider_id, adapter)`, `registry.get(model) → adapter`, model→provider 映射可热加载
- **per-provider 示例**: 至少 3 个 (anthropic / glm / openai-compat) 完整字段
- **接入新 provider 边际成本**: 写一个 adapter 即可 (≤200 行模板)
- **验收 ≥5**: shape 4 维齐 / API 3 方法定义 / 3 个 provider 示例完整 / 错误 7 分类锁定 / 接入新 provider checklist (≤7 步)

### N3 actor_derivation_spec.md (O3)
- **现状盘点**: 现存手工维护的 actor 列表 (planner / builder / evaluator / architect / pm / lab 四区) + 列出和 physical_operator 重复的字段
- **派生规则**: actor = physical_operator + role_overlay + capability_filter; `derive_actor(op_spec, role) → actor_spec` 函数契约
- **去重检测**: 现存 actor 中可被 derive 出来的全部标出 (预期 ≥80% actor 可派生)
- **drift**: 任何手工新增 actor 必须有 `derivation_exempt: <reason>` 字段, 否则 CI 阻断
- **template 路径**: physical_operator 不存在时, 走 `actor_template/*.yaml` 派生
- **验收 ≥4**: 派生函数签名锁定 / 现存 actor ≥80% 标出可派生 / drift 字段定义 / template fallback 路径定义

### N4 migration_compat_plan.md (O4)
- **依赖**: N1+N2+N3 全部完成
- **三轨迁移阶梯** (selector / registry / actor 各自分 phase):
  - Phase 1: 双写 (旧入口 + 新 selector 并存, traffic shadow)
  - Phase 2: 灰度 (新 selector 占 10% → 50% → 100%)
  - Phase 3: 老入口 deprecated (运行时 WARN), 6 周后删
- **兼容 shim**: 旧调用方零侵入 (selector facade 包旧签名)
- **验证 gate** (每个 phase 必须过):
  - selector: parity test (新旧入口同输入同输出) + drift_guard 静态检查
  - registry: 3 provider adapter 通过 contract test
  - actor: ≥80% actor 派生通过 schema validation
- **rollback**: 每 phase 都有 single-flag rollback (env: `SOLAR_OPERATOR_CONVERGENCE_DISABLE`)
- **验证命令** (本 sprint 不真跑, 留下游 sprint):
  - `solar-harness selector inventory --json`
  - `solar-harness provider list-adapters --validate`
  - `solar-harness actor diff-derived --report`
- **验收 ≥5**: 3 轨阶梯齐 / 兼容 shim 设计 / phase gate 定义 / rollback flag / 验证命令清单

### N5 traceability_handoff.md (join, O5)
- **traceability matrix**: REQ-000..003 → outcome O1..O5 → node N1..N5 → gate G_PLAN/G_IMPL/G_VERIFY/G_REVIEW 全链路表
- **acceptance coverage**: 每条 success_criteria (3 条 PRD + 4 条 REQ) 至少映射到一个 validation step
- **stop_rules** 显式复述 (Contracts.yaml):
  - 缺少可验证 acceptance 不得标记为完成
  - 缺少 verifier 决策不得进入 DONE
- **handoff package**: 给下游实施 sprint 的启动包
  - 4 件套引用 (N1/N2/N3/N4 spec md)
  - allowed_paths: `apps/pm-pane/**` + `packages/requirement-ir/**` + `harness/**`
  - forbidden_paths: `infra/prod/**` + `.env*` + `secrets/**`
  - approval_required_when: new prod dep / DB migration / network access / auth-billing 触碰
- **OQ 追踪**: PRD 中 1 条 OQ ("缺少显式 success metric") → 本 sprint 补齐为 3 条 success metric (PRD 已含) + 转下游 sprint 跟踪
- **不 close epic**: 本 sprint passed 仅 mark 下游 ready, 不主动 close

## 4. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| N1 | sonnet | 入口收敛需较强 reasoning (4+ 入口对照) |
| N2 | sonnet | adapter 4 维 + 多 provider 例需 reasoning |
| N3 | glm-5.1 | actor 派生规则相对模板化 |
| N4 | sonnet | migration 阶梯 + rollback 设计需 reasoning |
| N5 | glm-5.1 | traceability 矩阵填表 + handoff 模板化 |

## 5. Stop Rules

- 不实施代码 (本 sprint 是 spec-only)
- 不修改 `~/.solar/harness/lib/` 实际实现 (留下游)
- 不绕 planner 直派 builder
- 不删除现有 selector / provider / actor 代码 (设计阶段 read-only)
- 不绕 acceptance coverage 检查
- 不打印 secrets (provider API key / OAuth token)
- 不主动 close 父 epic (无 epic, 但保留原则)
- 不用乐观词 (done/complete/perfect/已稳定)

## 6. Knowledge Context

- IR 4 REQ + Contracts.yaml 3 contract + PRD 11 section + handoff = self-contained
- mirage:timeout → fallback 走 QMD + Obsidian + Solar DB
- 现存 Solar Harness scheduler / provider / actor 实现位于 `~/.solar/harness/lib/`, 本 sprint 不读源码, 在 N1-N3 由 builder 通过命令盘点 (如 `solar-harness selector inventory` 当前可能不存在, 走 grep)
