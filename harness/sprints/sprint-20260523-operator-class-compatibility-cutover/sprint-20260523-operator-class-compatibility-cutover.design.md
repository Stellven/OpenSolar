# Design — Operator Class Compatibility Cutover

sprint_id: `sprint-20260523-operator-class-compatibility-cutover`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-23T20:25:00Z`
knowledge_context: `solar-harness context inject used (mirage timeout -> qmd/obsidian/solar_db fallback)`
parent_sprint: `sprint-20260523-physical-operator-taxonomy-truthification` (read-only 引用)
grandparent_sprint: `sprint-20260523-pane-as-physical-operator-architecture` (read-only 引用)
parallel_protect: `sprint-20260523-lease-based-model-fleet-runtime` 不被 block / rewrite

## 0. 本切片的边界（强制 read-first）

- **P0 cutover sprint**：解决「新 DAG 用 `DeepArchitect/ImplementationWorker/Verifier`，旧 worker inventory 仍叫 `planner/builder/evaluator/external` → scheduler 报 `no_matching_worker`」的兼容桥缺失问题。
- **严格禁止**：
  - 停掉任何 `LEASED / RUNNING / DRAINING` 状态的 operator（C7 + D3 + Hard Rules）
  - 强制重启全部 pane / 改 5-pane 拓扑
  - 回滚父 sprint / grandparent sprint / 当前 taxonomy sprint planner 真值
  - 让 legacy role 继续作为长期调度真值
  - strict canonical mode 抢跑（必须 Phase 4 才开）
  - 无观测切换
  - 写 raw secret
  - block `sprint-20260523-lease-based-model-fleet-runtime` 或 in-flight sprint
  - 改 `~/.solar/STATE.md` / epic.* / ThunderOMLX 任何路径
- **允许 Write/Edit**：
  - `sprints/<sid>.{design, plan, task_graph, planning_html}.{md,json,html}`（本轮）
  - `sprints/<sid>.workstream-{A..F}-*.md`（N1..N6 产出）
  - `sprints/<sid>.canonical-mapping.md`（N2 必交）
  - `sprints/<sid>.rollout-runbook.md`（N6 必交）
- 知识库降级 `mirage:timeout`：本 sprint self-contained。

## 1. Compatibility Bridge 三层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                  Input Surface                                  │
│   • Legacy DAG with `model: claude-opus-4-7` / `provider: ...`  │
│   • Legacy inventory with `role: planner/builder/evaluator`     │
│   • New DAG with `preferred_operator_classes: [DeepArchitect]`  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           Canonical Mapping Layer (D1 / FR1 / N2)               │
│   AliasResolver:                                                │
│     planner   → DeepArchitect                                   │
│     builder   → ImplementationWorker                            │
│     evaluator → Verifier                                        │
│     architect → DeepArchitect + RootCauseDebugger (sub-mode)    │
│     pm        → DeepArchitect (产) + Verifier (review)          │
│     external  → split-only (5 specific class)                   │
│   每个 worker entry 上挂 `canonical_operator_class`              │
│   每个 DAG 节点的 legacy field → canonical 解析                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           Scheduler Resolve Order (D4 / FR4 / N3)               │
│   1. alias resolve   (legacy → canonical)                       │
│   2. canonical resolve (canonical → candidate operators)        │
│   3. fallback to legacy (兼容期允许，记录 fallback evidence)    │
│   4. strict canonical (Phase 4+ 才开，按 sprint/DAG version)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           Runtime + Observability (D3 + D5 / N4 + N5)           │
│   • In-flight protection: LEASED/RUNNING/DRAINING never re-cls  │
│   • Status / 8765 三视图: legacy role / canonical class /       │
│     selected runtime binding (FR5 / N5)                         │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Canonical Mapping Table（per FR1 + A1 + N2 必交）

`legacy role → canonical_operator_class` 映射真值表：

| Legacy bucket | Canonical class | 处理 | 备注 |
|---------------|-----------------|------|------|
| `planner` | `DeepArchitect` | alias (read+write 兼容) | pane 0 角色保持；display 仍可叫 planner |
| `builder` | `ImplementationWorker` | alias | pane 1 |
| `evaluator` | `Verifier` | alias | pane 2 |
| `architect` | `DeepArchitect` + `RootCauseDebugger`（sub-mode） | alias，按 task_type 切 sub-mode | pane 3 |
| `pm` | `DeepArchitect`（产 PRD）+ `Verifier`（review） | dual-role alias，按上下文切 | pane 4 |
| `external` | **split-only**（拆为 5 specific class） | **不再作通用桶**；新写禁用 | per parent sprint D5 |
| `external/parallel` | `ParallelExplorer` | split alias | — |
| `external/research` | `ResearchSynthesizer` | split alias | — |
| `external/browser` | `BrowserOperator` | split alias | — |
| `external/google` | `GoogleStackOperator` | split alias | — |
| `external/local` | `LocalPrivacyOperator` | split alias | — |
| `fast_subagent`（如存在） | `FastSubagent` | identity（已新名） | — |

**3 档 bucket 处理（per A2）**：

| 档 | Legacy buckets | 含义 |
|----|---------------|------|
| **只读兼容** | planner / builder / evaluator / architect / pm | 旧名仍可被 inventory 上报 + DAG 直写；scheduler alias resolve 透明转 canonical |
| **deprecate** | `external/*` 未拆分形态 | 新写抛 WARN；旧 entry 触发 split 提示 |
| **禁止** | 纯 `external`（无 sub-tag） | scheduler 不接受；inventory 必须显式拆 |

## 3. Dual-read / Dual-write / Canonical-only 策略（per FR2 + A3）

| 组件 | 过渡期策略（Phase 1-3）| Strict 期（Phase 4+） |
|------|---------------------|------------------------|
| Registry (`physical-operators.json`) | dual-write：每条 entry 同写 legacy `role` + canonical `operator_class`；canonical 为 source of truth | canonical-only；legacy `role` 仅 display alias |
| Worker inventory (`worker_state.sqlite` / heartbeat report) | dual-write；canonical preferred；legacy fallback | canonical-only |
| Scheduler (`graph_node_dispatcher.py`) | alias resolve → canonical resolve → fallback to legacy | canonical-only；strict mode 拒 legacy DAG（需 lint 先 migrate） |
| Graph dispatcher (DAG node parse) | dual-read：accept `model/provider` + `preferred_operator_classes`；WARN on legacy | canonical-only；legacy 字段 dispatch-time reject |
| Status payload | dual-read + 三视图（legacy / canonical / selected） | 三视图保留（display），canonical 为真值 |
| 8765 monitor | 三视图必显 | 同上 |

## 4. In-flight Safety Rules（per FR3 + D3 + A4 + N4 必交）

**Hard protection**（never online re-classify or restart）：

| State | Allowed update | Disallowed |
|-------|----------------|------------|
| `LEASED` | metadata refresh（heartbeat / quota probe） | re-classify / restart / migrate canonical_operator_class |
| `RUNNING` | metadata refresh | 同上 |
| `DRAINING` | metadata refresh | 同上 |
| `IDLE` | re-classify OK（但要 broadcast 通知 scheduler） | restart 仅在 IDLE→COOLDOWN 才允许 |
| `COOLDOWN` | re-classify OK | restart OK |
| `WARMING` | re-classify OK | restart OK |
| `CREATED` | re-classify OK | restart OK |
| `QUOTA_EXHAUSTED` | re-classify OK（不动 quota state） | — |
| `AUTH_EXPIRED` | re-classify OK | — |
| `STALE_CONTEXT` | re-classify OK | — |
| `DISABLED` | re-classify OK | — |
| `ERROR` | re-classify OK（先解 ERROR） | — |
| `NEEDS_HUMAN_REVIEW` | metadata only；re-class 需人工 ack | restart 需人工 ack |

**Update strategy**：

- 立即生效（live）：仅 IDLE/COOLDOWN/WARMING/CREATED 状态下的 re-classify
- 下次启动生效（deferred）：其他状态（含 in-flight 3 状态）的 re-classify 入 deferred-update queue
- deferred queue flush 触发：operator 状态转 IDLE → 自动 apply

## 5. Scheduler Resolve Order（per D4 + FR4 + A5 + N3 必交）

```python
def resolve_operator_for_task(task):
    # 1. alias resolve — legacy → canonical
    if task.has_legacy_role:
        canonical = ALIAS_TABLE.get(task.legacy_role)
        if canonical is None:
            return REJECT(reason="unknown_legacy_role")
        task.canonical_operator_classes = [canonical]
        log_alias_resolved(task.legacy_role, canonical)
    
    # 2. canonical resolve — find candidate operators
    candidates = registry.filter(canonical_operator_class__in=task.canonical_operator_classes)
    
    # 3. fallback to legacy (Phase 1-3, not Phase 4+)
    if not candidates and not STRICT_MODE_ENABLED(task.sprint_id, task.dag_version):
        legacy_candidates = registry.filter(legacy_role__in=task.legacy_role_fallback)
        log_fallback_legacy(task, legacy_candidates)
        candidates = legacy_candidates
    
    # 4. strict canonical (Phase 4+)
    if not candidates and STRICT_MODE_ENABLED(task.sprint_id, task.dag_version):
        return REJECT(reason="no_canonical_match_strict_mode")
    
    if not candidates:
        return REJECT(reason="no_matching_worker_after_fallback", 
                      diagnostics={"alias": task.legacy_role, "canonical": task.canonical_operator_classes})
    
    # 5. apply profile gates + scoring (per parent sprint N3)
    return rank_and_select(candidates, by=OperatorScore)
```

**`no_matching_worker` 在迁移期的原因分类树**（per A6 + N3）：

```
no_matching_worker
├─ unknown_legacy_role          (alias table 缺映射)
├─ canonical_inventory_empty    (canonical 已映射但 worker 未上报 canonical)
├─ all_candidates_in_flight     (匹配 worker 都 LEASED/RUNNING/DRAINING)
├─ all_candidates_quota_blocked (QUOTA_EXHAUSTED)
├─ all_candidates_auth_blocked  (AUTH_EXPIRED)
├─ all_candidates_disabled
├─ profile_gate_rejected        (capability/risk/cost 不通过)
└─ strict_mode_no_canonical     (Phase 4+ 不允许 legacy fallback)
```

每条 reason 必须 emit 到 audit.log + status payload，方便运维定位。

## 6. Observability 三视图（per D5 + FR5 + A7 + N5 必交）

Status / 8765 payload 必须含 3 字段：

```yaml
operator_view:
  - operator_id: pane-aiops-0-planner-opus47
    legacy_role: planner             # 旧名 (display)
    canonical_operator_class: DeepArchitect  # 真值
    selected_binding:                # 本次/最近一次实际绑定
      task_id: dag-XXX-node-Y
      sprint_id: sprint-XXX
      resolved_via: alias            # alias | canonical | fallback_legacy
      bound_at: "..."
```

`resolved_via` 4 个枚举值（per scheduler resolve order）：

| value | 含义 |
|-------|------|
| `alias` | scheduler 通过 alias 转换命中（最常见过渡期路径）|
| `canonical` | DAG 直接给 canonical_operator_classes，inventory 也已上报 canonical |
| `fallback_legacy` | canonical 命中空，回退到 legacy role 匹配（Phase 1-3 允许，Phase 4+ 禁）|
| `none` | no_matching_worker（含 reason 分类）|

8765 首页（per Q4 答案）：默认显示 canonical view + 折叠面板可展开 legacy / selected_binding；不破坏现有 UI 布局。

## 7. Staged Rollout + Rollback（per FR6 + A8 + N6 必交）

```
┌──────────────────────────────────────────────────────────────────┐
│ Phase 0: Read-only audit                                         │
│   - 盘点：现 inventory / registry / DAG 中 legacy vs canonical 比例 │
│   - 产 audit report（N1）                                         │
│   - rollback: trivial（无写）                                     │
├──────────────────────────────────────────────────────────────────┤
│ Phase 1: Alias table active                                      │
│   - ALIAS_TABLE 加载；scheduler alias resolve 启用                │
│   - inventory 仍 legacy only；scheduler 透明转 canonical          │
│   - rollback: 卸 ALIAS_TABLE → 回 Phase 0                         │
├──────────────────────────────────────────────────────────────────┤
│ Phase 2: Dual-read dual-write                                    │
│   - registry / inventory 双字段并写                              │
│   - status 三视图启用                                            │
│   - rollback: 关 dual-write，仍可读 dual（不丢数据）             │
├──────────────────────────────────────────────────────────────────┤
│ Phase 3: Canonical preferred, legacy fallback                    │
│   - scheduler 优先 canonical；missing → fallback legacy           │
│   - 新 DAG 全用 canonical；旧 DAG 透明工作                       │
│   - rollback: 切回 Phase 2 (alias-only resolve)                   │
├──────────────────────────────────────────────────────────────────┤
│ Phase 4: Strict canonical for new DAGs                           │
│   - feature flag `STRICT_CANONICAL_NEW_DAGS=1` 按 sprint 开关     │
│   - 新 sprint 的 DAG 必须 canonical-only；旧 sprint 仍 fallback   │
│   - 进入条件: Phase 3 稳定 ≥ 7 天 + alias resolve 命中率 = 100% + │
│              fallback_legacy 命中率 < 5%                          │
│   - rollback: feature flag 切回 0 → 回 Phase 3                    │
├──────────────────────────────────────────────────────────────────┤
│ Phase 5: Retire legacy buckets                                   │
│   - legacy role 字段从 inventory schema 移除（仅 display alias）  │
│   - rollback: feature flag 重启 legacy schema 字段（保留 1 sprint │
│     回退窗口）                                                    │
│   - 进入条件: Phase 4 稳定 ≥ 14 天 + zero legacy DAG 引用         │
└──────────────────────────────────────────────────────────────────┘
```

**Strict mode 开关粒度（per Q5 答案）**：按 **sprint** 启用（每个 sprint 自己的 dag_version 上挂 `strict_canonical: true|false`），不是全局，也不是按 DAG version。理由：sprint 是 Solar 治理的最小调度单元，能精确控制风险面。

**Rollback principle**：每个 Phase 都可独立回退到前一个 Phase，且不要求停机；rollback 只是关 feature flag / 卸 ALIAS_TABLE，不删数据。

## 8. Component Migration Status Matrix（N1 audit 输入要点）

| Component | Phase 0 audit 必须报告 |
|-----------|----------------------|
| `physical-operators.json` | 当前 entry 数 / legacy role 比例 / 已含 canonical_operator_class 字段比例 |
| `worker_state.sqlite` / heartbeat report | 当前 worker count / heartbeat 中 canonical 上报比例 |
| `graph_node_dispatcher.py` | 是否含 alias resolve；是否含 canonical resolve；是否 strict mode hardcoded |
| in-flight DAG nodes | 当前 LEASED/RUNNING/DRAINING 节点数 + 它们的 operator binding 是 legacy 还是 canonical |
| 8765 status payload | 当前是否 emit canonical 字段 |
| evaluator scripts | 是否依赖 legacy role 字面 |

## 9. Non-breaking 保证（per Constraints + A9）

| 保证 | 实施点 |
|------|--------|
| 不停机 | 所有 Phase 切换 = feature flag / 卸 ALIAS_TABLE，无 process restart |
| 不强制重启 pane | per D3 + §4 in-flight safety rules |
| 不回滚 in-flight sprint | deferred-update queue：状态非 IDLE 的 worker，canonical update 延后到 IDLE |
| 不破坏 lease / handoff / evaluator 流程 | scheduler resolve 透明转 canonical，对 worker 不可见 |
| 不要求一次性 strict mode | Phase 4 按 sprint 启用，可 Phase-by-Phase 试点 |
| 不破坏后台 in-flight sprint | parallel_protect 名单包含父 sprint / grandparent sprint / lease-fleet-runtime |

## 10. 与父 sprint / grandparent sprint 一致性

| Decision | 本 sprint | 父 sprint (taxonomy-truthification) | Grandparent (pane-as-physical-operator) |
|----------|-----------|------------------------------------|------------------------------------------|
| 10 类 canonical taxonomy | 复用（不重定义） | 真值产出 | — |
| Registry schema v2 | 复用 + 加 `canonical_operator_class` 字段 | schema 草案产出 | schema 草案 N1 |
| 13 状态 lifecycle | 引用作 in-flight safety 输入 | 全集定义 | 7+7 子集 |
| writer/verifier separation | 引用作 scheduler resolve step | rule 定义 | rule 引用 |
| 5-pane 拓扑 | 不改 | 不改 | 不改 |
| Parent repair strategy | 引用：本 sprint 也 addendum 注入到 cutover 路径 | addendum 注入父 sprint | — |

## 11. 非目标（per Non-Goals + Constraints + Hard Rules）

- 不重定义 canonical taxonomy（10 类来自父 sprint，本 sprint 只做 cutover）
- 不强制停机 / 不重启全部 pane
- 不回滚父 sprint / grandparent sprint / 当前 taxonomy sprint planner 真值
- 不让 legacy role 继续作为长期调度真值
- 不允许 strict mode 抢跑（必须 Phase 4 + 进入条件满足）
- 不允许无观测切换
- 不杀 LEASED/RUNNING/DRAINING operator
- 不要求一次性 strict mode
- 不动 `~/.solar/STATE.md` / epic.* / ThunderOMLX 任何代码
- 不 block / rewrite `sprint-20260523-lease-based-model-fleet-runtime`
- 不写 raw secret
- 不使用乐观词

## 12. Open Questions Q1..Q5 答案

| Q | 答案归宿 |
|---|---------|
| Q1 `architect` 是否永久 display bucket | **是**（display）+ canonical = `DeepArchitect` 或 `RootCauseDebugger` sub-mode 切换。永久保留 display alias 以兼容运维心智模型。 |
| Q2 `external` 兼容期 vs 禁用 | **过渡期只读兼容（Phase 1-3），Phase 4 起新写禁止；Phase 5 完全禁用**。已拆分的 sub-tag (parallel/research/browser/google/local) 透明 alias 到对应 class。 |
| Q3 canonical class registry-derived vs runtime-reported | **dual-source**：registry 是 declarative truth；runtime worker heartbeat 必须 report canonical（Phase 2+）；不一致 → reconcile log + 以 registry 为最终真值。 |
| Q4 三视图 8765 首页 | **默认显示 canonical view + 折叠面板**（legacy + selected_binding 二级展开），不破坏现有布局。 |
| Q5 strict canonical 开关粒度 | **按 sprint**（每 sprint dag_version 上挂 `strict_canonical: bool`），不是全局也不是按 DAG version。 |

## 13. 接力 evaluator / parent sprint

evaluator 必须按 A1..A9 逐项核（plan §6 提供命令）。

父 sprint (taxonomy-truthification) 不被修改；本 sprint 在 N6 rollout-runbook.md 中明示「兼容桥 = parent taxonomy 的物理落地路径」，作为父 sprint follow-up adoption point。
