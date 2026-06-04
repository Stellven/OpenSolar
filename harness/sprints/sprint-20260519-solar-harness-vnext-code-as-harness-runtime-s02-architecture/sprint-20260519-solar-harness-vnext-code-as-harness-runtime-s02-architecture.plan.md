# Plan — S02 架构设计与接口契约 (Code-as-Harness Runtime)

epic_id: `epic-20260519-solar-harness-vnext-code-as-harness-runtime`
sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s02-architecture`
slice: `architecture`
author: planner (solar-harness)
date: 2026-05-20
Knowledge Context: solar-harness context inject used

## 1. 总体策略

S02 的 8 个 outcomes (O-arch-contracts / O-03 架构语义 / state-machine / control-data / failure-recovery / observability / compatibility / conflicts) 拆分为 9 个 builder 可独立完成的 markdown artifact，对应 9 个 DAG 节点。本切片**不写运行时代码**，仅冻结 schema / state machine / policy / matrix。

P0 范围严格收敛: **仅 Pkg 1 (Plan IR + Action Contract) + Pkg 2 (Execution Broker) + Pkg 4 (Event Ledger) 的架构**;P1/P2/P3 (Artifact Registry / Verifier / DeepResearch compiler / Repair Controller / Multi-Agent Workspace) 留作 S03 后续 epic 入口。

## 2. DAG 节点结构

```
Layer 1 (parallel, 4 nodes, write_scope 互不重叠):
  N1 architecture.md            — control/data plane 分层 + 数据流单向 + 模块拓扑
  N2 interface-contracts.md     — action_contract.schema + event.schema + broker_coverage.spec
  N3 state-machines.md          — sprint / action / event projection 三状态机 + 转换边
  N4 policy-decisions.md        — event ledger 后端选型 + risk_class 默认表 + schema evolution

Layer 2 (parallel, deps Layer 1, 3 nodes):
  N5 compatibility-matrix.md    — wake/dispatch/status/graph_scheduler 6 模块决策 + 双跑对比命令
  N6 failure-recovery.md        — PRD §6 10 种失败 P0 覆盖 3 种 + detect/classify/recover 矩阵
  N7 observability.md           — broker coverage + event lag + projection drift 6 指标

Layer 3 (serial, deps N1-N7, 1 node):
  N8 conflicts-fallback.md      — 5 类冲突 detect/fallback/downgrade 表 + 与 §6 §11 §12 交叉引用

Layer 4 (serial, deps N1-N8, 1 node):
  N9 prd.html + planning.html   — HTML 渲染 (pandoc/python-markdown)

Layer 5 (Gate G_S02_PLANNING, deps N1-N9, 1 node):
  N10 handoff.md                — S03 入参锚点表 + 中文证据表 7 列 + outcomes 状态
```

总计 10 节点 (N1..N10)。所有 builder 节点 preferred_model = `sonnet` (避免 GLM 1210)。

## 3. Write Scope 隔离矩阵

| Node | write_scope |
|------|-------------|
| N1 | `sprints/{SID}.architecture.md` |
| N2 | `sprints/{SID}.interface-contracts.md` |
| N3 | `sprints/{SID}.state-machines.md` |
| N4 | `sprints/{SID}.policy-decisions.md` |
| N5 | `sprints/{SID}.compatibility-matrix.md` |
| N6 | `sprints/{SID}.failure-recovery.md` |
| N7 | `sprints/{SID}.observability.md` |
| N8 | `sprints/{SID}.conflicts-fallback.md` |
| N9 | `sprints/{SID}.prd.html`, `sprints/{SID}.planning.html` |
| N10 | `sprints/{SID}.handoff.md` + `sprints/{EPIC}.traceability.json` (升级 S02 outcomes) |

Layer 1 的 4 个节点 write_scope 全独立 → 可同批派发。
Layer 2 的 3 个节点 write_scope 全独立 → 可同批派发。
N9 / N10 串行 (Gate 与终止节点)。

## 4. 节点验收条件 (acceptance gates)

| Node | Gate | Acceptance Predicates |
|------|------|------------------------|
| N1 | G_N1 | `grep -c '^## ' architecture.md` ≥ 6; 含 control/data/event plane 三层标题 |
| N2 | G_N2 | `python3 -c 'import json; json.load(open("interface-contracts.md"))' fails OK`;字段表 ≥ 11 必选 + 6 必选 (action + event);broker_coverage 字段表 ≥ 8 |
| N3 | G_N3 | 三状态机各含 ≥ 5 状态 + 转换边;终态明确 |
| N4 | G_N4 | event ledger 选型 trade-off 表 ≥ 3 行;risk_class 表 ≥ 12 行;schema evolution 含 5 条规则 |
| N5 | G_N5 | 6 模块每行含: 决策 + 双跑命令 + owner sprint |
| N6 | G_N6 | 失败矩阵 10 行;P0 覆盖 ≥ 3 种 detect/classify/recover/retry/rollback 五栏齐 |
| N7 | G_N7 | 指标表 ≥ 6 行,每行含 metric_name + source + 报警阈值 |
| N8 | G_N8 | 5 类冲突每行含 detect + fallback + downgrade + P0/P1 |
| N9 | G_N9 | prd.html 字节数 > 30000;planning.html 字节数 > 15000;含 `<html` 标签 |
| N10 | **G_S02_PLANNING** | handoff.md ≥ 5 sections;7 列证据表 ≥ 10 行;含 S03 锚点表 |

## 5. Required Gates

```yaml
required_gates:
  - G_S02_PLANNING   # 父 epic gate 触发的 sprint gate
```

仅当 N10 PASS 时 sprint 整体 PASS → 触发 epic.task_graph S03 child activation。

## 6. 模型选择 (preferred_model)

| Layer | Model | 理由 |
|-------|-------|------|
| All N1-N10 | `sonnet` | S01 同期已验证 sonnet 在 markdown 文档生成稳定;GLM 1210 风险已记录在 memory |

## 7. 关键路径与估时

```
Critical Path: N4 (policy decisions) → N5 (compatibility) → N8 (conflicts) → N10 (handoff)

Layer 1 (parallel ~3h max): N1=2h, N2=3h, N3=2h, N4=3h
Layer 2 (parallel ~2h max): N5=2h, N6=2h, N7=1.5h
Layer 3 (~1.5h): N8 = 1.5h
Layer 4 (~0.5h): N9 = 0.5h
Layer 5 (~1h): N10 = 1h

Total wall-clock ≈ 3 + 2 + 1.5 + 0.5 + 1 = 8h (单 sprint)
Total ideal-hours ≈ 18.5h
```

## 8. 安全约束 / Stop Rules

- 任何 markdown 中**不允许**出现 `function`, `class`, `import`, `def `, `const `, `let ` 开头的可执行代码 (planner 不写代码)。
- 任何节点**不允许**修改 `/Users/sihaoli/Solar/` 任何文件。
- 任何节点**不允许**修改 `sprints/sprint-20260519-...-s01-requirements.*` 已 PASS 的文件 (S01 outcomes 已冻结)。
- N4 risk_class 默认表标注"建议;监护人 S03 evaluator 前最终拍板"，不得宣称已批准。
- `graph-scheduler validate` exit 0 是 sprint 进入 builder 派发的硬条件。

## 9. S03 入参锚点 (N10 必须输出此表)

| 锚点 | 文件 | 关键章节 | S03 用途 |
|------|------|----------|---------|
| Schema 冻结 | interface-contracts.md | action_contract.schema + event.schema + broker_coverage.spec | S03 N1 直接落地 .schema.json |
| 状态机 | state-machines.md | broker 12 状态 + 9 转换边 | S03 N3 execution_broker.py |
| Event Ledger 后端 | policy-decisions.md §1 | SQLite WAL + JSONL mirror | S03 N2 event_ledger.py |
| risk_class 表 | policy-decisions.md §2 | 12 行默认值 | S03 N5 单测 |
| Schema Evolution | policy-decisions.md §3 | dual-write 14 天 + 5 规则 | S03 N2 migrate 接口占位 |
| 兼容性矩阵 | compatibility-matrix.md | wake/dispatch/status 决策 | S03 N6 legacy 适配 |
| 失败矩阵 P0 | failure-recovery.md | PLAN_INVALID + EXEC_FAILED + VERIFY_FAILED | S03 N4 失败处理 |
| 观测指标 | observability.md | 6 指标 + 报警阈值 | S04 activation-proof |
| 冲突降级 | conflicts-fallback.md | 5 类 fallback chain | S03+S04 通用 |
| 控制/数据/事件三层 | architecture.md | 数据流单向 + import-time lazy | S03+S04 边界约束 |

## 10. Non-goals (本 plan 不做)

- 不写 jsonschema 文件 (S03 N1 实现)
- 不写 broker 代码 (S03 N3)
- 不画 .png/.svg 架构图 (text diagram 优先;如需 visual,留 S05)
- 不修改 graph_scheduler.py / dispatcher.py (S03/S04 实现)
- 不拆 P1/P2/P3 架构
- 不替 monitor 拍板 risk_class 表
