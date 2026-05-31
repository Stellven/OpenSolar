# Plan — Operator Architecture Convergence

gate: `sprint-20260527-operator-architecture-convergence:passed`
required_gates: G_PLAN (N1/N2/N3) → G_VERIFY (N4) → G_REVIEW (N5)
evidence_policy.no_code: true (spec-only sprint)

## 0. DAG

```
                ┌─→ N1 unified_selector_spec        (sonnet)  ─┐
   (无上游) ────┼─→ N2 provider_adapter_registry    (sonnet)  ─┼─→ N4 migration_compat_plan (sonnet) ─→ N5 traceability_handoff (glm-5.1, join)
                └─→ N3 actor_derivation_spec        (glm-5.1) ─┘
```

Wave 1 (3 并行 write_scope 互斥): N1 / N2 / N3
Wave 2: N4 (depends N1+N2+N3)
Wave 3 (join): N5 (depends N1..N4)

## 1. 节点验收

| 节点 | 验收 (≥) | 输出 |
|------|----------|------|
| **N1** | 4 条: 入口清单 ≥4 / 选 selector 函数签名锁定 / 收敛路径每入口 caller 映射 / drift_guard 规则 | `docs/operator-arch-convergence/N1-unified-selector-spec.md` |
| **N2** | 5 条: shape 4 维齐 / API 3 方法 / 3 provider 例 / 错误 7 分类锁定 / 接入新 provider checklist (≤7 步) | `docs/operator-arch-convergence/N2-provider-adapter-registry-spec.md` |
| **N3** | 4 条: 派生函数签名 / ≥80% actor 标可派生 / drift 字段 / template fallback | `docs/operator-arch-convergence/N3-actor-derivation-spec.md` |
| **N4** | 5 条: 3 轨阶梯 / 兼容 shim / phase gate / rollback flag / 验证命令清单 | `docs/operator-arch-convergence/N4-migration-compat-plan.md` |
| **N5** | traceability 矩阵 (REQ→outcome→node→gate) + acceptance coverage 100% + stop_rules 复述 + handoff 启动包 + 1 OQ 转下游 | `<sid>.traceability.json` + `<sid>.handoff.md` |

## 2. 写范围

| 节点 | write_scope |
|------|-------------|
| N1 | `docs/operator-arch-convergence/N1-*.md` |
| N2 | `docs/operator-arch-convergence/N2-*.md` |
| N3 | `docs/operator-arch-convergence/N3-*.md` |
| N4 | `docs/operator-arch-convergence/N4-*.md` |
| N5 | `<sid>.handoff.md` + `<sid>.traceability.json` + `<sid>.eval.{md,json}` |

## 3. Stop Rules

- 不实施代码 (spec-only)
- 不修 `~/.solar/harness/lib/` 实际实现
- 不删现有 selector / provider / actor 代码
- 不绕 planner 直派 builder
- 不绕 acceptance coverage 检查
- 不打印 provider secrets
- 不主动 close epic
- 不用乐观词 (done/complete/perfect/stable/已修复)

## 4. 验证命令 (本 sprint 不真跑, 留下游实施 sprint)

- `solar-harness selector inventory --json` (N1 待实现)
- `solar-harness provider list-adapters --validate` (N2 待实现)
- `solar-harness actor diff-derived --report` (N3 待实现)
- 三轨 phase gate parity test 由下游 sprint 实施

## 5. Rollback

下游实施 sprint 必须支持:
- env flag: `SOLAR_OPERATOR_CONVERGENCE_DISABLE=1` 关掉新 selector / registry / actor 派生
- 每 phase 都能单独回退 (per N4 §rollback)

## 6. 给下游实施 sprint

handoff.md 必须含:
- N1/N2/N3/N4 四件 spec 引用路径
- allowed_paths / forbidden_paths / approval_required_when (复述 Contracts.yaml)
- 3 个迁移轨 (selector / registry / actor) 分别 epic-able
- 1 条 OQ ("success metric 转下游实施 sprint 跟踪")

## 7. 治理保留

per dispatch "preserve compiled governance constraints":
- Contracts.yaml `agent_execution.allowed_paths` / `forbidden_paths` / `approval_required_when` / `stop_conditions` 复制到本 task_graph evidence_policy
- 每个节点显式 `requirement_ids` (REQ-000..003 映射)
- required_gates `G_PLAN/G_IMPL/G_VERIFY/G_REVIEW` 保留, 映射到 N 节点
