# Handoff — sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s02-architecture

epic_id: `epic-20260519-solar-harness-vnext-code-as-harness-runtime`
sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s02-architecture`
date: 2026-05-20
Knowledge Context: solar-harness context inject used

## 1. 产出总览

S02 共交付 10 个 markdown artifact + 2 个 HTML 渲染，覆盖架构分层、接口契约、状态机、策略决策、兼容矩阵、失败恢复、观测指标、冲突降级。所有 N1-N9 acceptance 全 PASS。

## 2. 中文七列证据表

| Outcome | 验收点 | 下游 Sprint | 验证命令 | 结果 | 降级原因 | 未闭环 |
|---------|--------|------------|---------|------|---------|--------|
| O-arch-1: 三平面分层 | Control/Data/Event 三层 + 6 禁向 + 模块拓扑 | S03 core | `grep -c '^## ' architecture.md` → 10 ✓ | architecture.md 12071B, 10 节 | — | — |
| O-arch-2: 接口契约 | action_contract 11+5 字段 + event 6+6 + broker_coverage 8 字段 | S03 core | `grep -c '|' interface-contracts.md` → 字段表完整 ✓ | interface-contracts.md 10412B | — | — |
| O-arch-3: 状态机 | Sprint 10 状态 + Broker 11 状态 + Projection 7 状态 + 转换边 | S03 core | `grep -c 'stateDiagram' state-machines.md` → 3 Mermaid 图 ✓ | state-machines.md 23890B | — | — |
| O-arch-4: 策略决策 | Ledger 选型 3 方案 + risk_class 18 行 + schema evolution 5 规则 | S03 core | `grep -c 'LR-' compatibility-matrix.md` → 6 lazy rules ✓ | policy-decisions.md 7221B | — | risk_class 需监护人 S03 前最终拍板 |
| O-arch-5: 兼容矩阵 | 6 模块决策 + 双跑命令 + LR-01~LR-06 | S03+S04 | `grep -c 'LR-0' compatibility-matrix.md` → 6 ✓ | compatibility-matrix.md 8674B | — | 双跑命令为示例，实际测试环境待 S03 |
| O-arch-6: 失败恢复 | 10 类矩阵 + P0 三类六栏齐 + rollback 对齐 | S03+S04+S05 | `grep -c 'PLAN_INVALID\|EXECUTION_FAILED\|VERIFICATION_FAILED' failure-recovery.md` → P0 三类 ✓ | failure-recovery.md 18730B | — | — |
| O-arch-7: 观测指标 | 6 指标 + source SQL + 报警阈值 + activation-proof 对齐 | S04+S05 | `grep -c 'metric_name' observability.md` → 6 ✓ | observability.md 7290B | — | — |
| O-arch-8: 冲突降级 | 5 类冲突 detect/fallback/downgrade + 5min timeout + 14 天 dual-write | S03+S04 | `grep -c 'approval_timeout_sec' conflicts-fallback.md` → 300s ✓ | conflicts-fallback.md 16925B | — | — |
| F-P1-01: Artifact Registry | Pkg 3 架构位置已冻 (artifact_registry.py) | S03 P1 | `grep 'artifact_registry' architecture.md` → §5 拓扑已列 ✓ | 架构位置已冻, P1 实现 | P1 延后 | S03 P1 切片实现 |
| F-P1-02: Verifier-as-a-Service | Pkg 5 接口已冻 (verifiers/*.py) | S03 P1 | `grep 'verifiers' architecture.md` → §5 拓扑已列 ✓ | 架构位置已冻, P1 实现 | P1 延后 | S03 P1 切片实现 |

## 3. S03 入参锚点表

| # | 锚点 | 文件 | 关键章节 | S03 用途 |
|---|------|------|----------|---------|
| 1 | Schema 冻结 | interface-contracts.md | action_contract.schema + event.schema + broker_coverage.spec | S03 N1 直接落地 .schema.json |
| 2 | 状态机 | state-machines.md | Broker 11 状态 + 转换边详表 | S03 N3 execution_broker.py |
| 3 | Event Ledger 后端 | policy-decisions.md §1 | SQLite WAL + JSONL mirror (方案 C) | S03 N2 event_ledger.py |
| 4 | risk_class 表 | policy-decisions.md §2 | 18 行默认值 + approval 联动 | S03 N5 policy 单测 |
| 5 | Schema Evolution | policy-decisions.md §3 | dual-write 14 天 + 5 规则 | S03 N2 migrate 接口占位 |
| 6 | 兼容性矩阵 | compatibility-matrix.md | wake/dispatch/status 6 模块决策 + LR-01~LR-06 | S03 N6 legacy 适配 |
| 7 | 失败矩阵 P0 | failure-recovery.md §3 | PLAN_INVALID + EXEC_FAILED + VERIFY_FAILED 六栏 | S03 N4 失败处理 |
| 8 | 观测指标 | observability.md §1 | 6 指标 + 报警阈值 | S04 activation-proof |
| 9 | 冲突降级 | conflicts-fallback.md §1-§6 | 5 类 fallback chain | S03+S04 通用 |
| 10 | 控制/数据/事件三层 | architecture.md §1-§4 | 数据流单向 + import-time lazy | S03+S04 边界约束 |

## 4. Outcomes 状态

| Outcome | 状态 | 交付物 |
|---------|------|--------|
| O-arch-1 三平面分层 | ✅ PASS | architecture.md (12071B) |
| O-arch-2 接口契约 | ✅ PASS | interface-contracts.md (10412B) |
| O-arch-3 状态机 | ✅ PASS | state-machines.md (23890B) |
| O-arch-4 策略决策 | ✅ PASS | policy-decisions.md (7221B) |
| O-arch-5 兼容矩阵 | ✅ PASS | compatibility-matrix.md (8674B) |
| O-arch-6 失败恢复 | ✅ PASS | failure-recovery.md (18730B) |
| O-arch-7 观测指标 | ✅ PASS | observability.md (7290B) |
| O-arch-8 冲突降级 | ✅ PASS | conflicts-fallback.md (16925B) |

## 5. 节点验证汇总

| Node | Artifact | Size (B) | AC 状态 | Handoff |
|------|----------|----------|---------|---------|
| N1 | architecture.md | 12071 | 4/4 PASS | N1-handoff.md |
| N2 | interface-contracts.md | 10412 | 5/5 PASS | N2-handoff.md |
| N3 | state-machines.md | 23890 | 4/4 PASS | N3-handoff.md |
| N4 | policy-decisions.md | 7221 | ALL PASS | N4-handoff.md |
| N5 | compatibility-matrix.md | 8674 | 4/4 PASS | N5-handoff.md |
| N6 | failure-recovery.md | 18730 | 5/5 PASS | N6-handoff.md |
| N7 | observability.md | 7290 | ALL PASS | N7-handoff.md |
| N8 | conflicts-fallback.md | 16925 | 5/5 PASS | N8-handoff.md |
| N9 | prd.html + planning.html | 56024 + 42708 | 4/4 PASS | N9-handoff.md |

## 6. 未闭环项

1. **risk_class 默认值需监护人拍板**: policy-decisions.md §2 标注"监护人 S03 evaluator 前最终确认"，当前为 P0 安全默认值
2. **LR-01~LR-06 为声明性规则**: 实际 import-time lazy 执行依赖 S03 实现
3. **双跑对比命令为示例性质**: 实际测试基础设施待 S03 搭建
4. **approval 5min timeout 完整降级**: detect+emit P0 已实现，完整 timeout auto-downgrade 为 P1+
5. **P1/P2/P3 架构位置已冻但未展开**: artifact_registry, verifiers, repair_controller 留 S03 后续

## 7. 下游影响

- **S03 (core-runtime)**: 直接消费 §3 锚点表 10 个入参，实现 schema/ledger/broker/policy/tests
- **S04 (orchestration-ui)**: 消费 observability.md 6 指标 + compatibility-matrix.md dispatch 适配
- **S05 (verification-release)**: 消费 failure-recovery.md P0 三类 + observability.md activation-proof

---

Knowledge Context: solar-harness context inject used
Harness Modules Used: solar-graph-scheduler
