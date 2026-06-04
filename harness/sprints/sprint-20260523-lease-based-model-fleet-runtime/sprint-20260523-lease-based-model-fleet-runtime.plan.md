# Plan — Lease-Based Model Fleet Runtime (sprint-level)

gate: 5 gates 全 passed (G_SCHEMA / G_LEASE / G_OBSERVABILITY / G_REPORT / G_ARCH)
knowledge_context: solar-harness context inject used
upstream: none (standalone runtime sprint)
downstream: 多个相关 sprint 依赖 lease broker (MTSPR / UAKG / TUI epic / smoke variants)

## 0. 切片定位

Standalone runtime sprint, 实施 lease-based model fleet runtime (actor lease broker for multi-pane model dispatch)。5 节点 N1-N5 严格串行 (schema → lease → observability → report → architecture). 5 gates 全 passed (per task_graph.gate_results). N1 reviewing + N2-N4 passed + N5 reviewing (graph_doctor 5/26 reset 导致 N1+N5 反复回 reviewing, 与其他 sprint 同源 drift)。

## 1. 交付切片顺序

```
N1 schema design (gate=G_SCHEMA, passed)
    └─→ N2 lease broker impl (gate=G_LEASE, passed; eval PASS)
          └─→ N3 observability (gate=G_OBSERVABILITY, passed; eval PASS)
                └─→ N4 report compiler (gate=G_REPORT, passed; eval PASS)
                      └─→ N5 architecture writeup (gate=G_ARCH, passed)
```

详细 per-node 实施见 `<sid>.design.md` (13K) + multiple addenda (N1-addendum / N2-addendum / N2-logical-operators / N3-capability-antigravity-fingerprint / N3-ledger-context / N3-scoring-verification, 总 ≥40K evidence).

## 2. 文件级写范围

| 节点 | 主要 write_scope (详见 task_graph) |
|------|-------------------------------------|
| N1 | `<sid>.N1-handoff.md` + `<sid>.N1-addendum.md` + schema files |
| N2 | `<sid>.N2-handoff.md` + N2 addenda (2) + lease broker 实施 + `<sid>.N2-eval.{md,json}` |
| N3 | `<sid>.N3-handoff.md` + N3 addenda (3: capability/ledger/scoring) + `<sid>.N3-eval.{md,json}` |
| N4 | `<sid>.N4-handoff.md` + `<sid>.N4-eval.{md,json}` |
| N5 | `<sid>.N5-handoff.md` |
| Planner (本切片) | `<sid>.plan.md` (本文件) + `<sid>.planning.html` + `<sid>.task_graph.json` patch + `<sid>.status.json` |
| **不动** | N1-N5 builder handoffs / addendums / eval artifacts (已完成) |
| **不动** | `<sid>.design.md` / `<sid>.design.html` / `<sid>.contract.md` / `<sid>.prd.md` (PM+Planner 已完成) |
| **严格禁止** | 改 `~/.solar/harness/{lib,tools,schemas,templates,bin}/` 任何已实施的 lease broker / dispatch / runtime 源码 (N2 已 PASS, 不动) |

## 3. 并发边界

- 5 节点严格串行 N1 → N2 → N3 → N4 → N5
- Planner 切片单线性 (本 backfill)
- 不与其他 sprint 并发动作

## 4. 验证命令

### Planner 自验

```bash
solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime.task_graph.json
ls -la ~/.solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime.{plan.md,planning.html}
```

### N1-N5 evidence (per task_graph)

```bash
ls -la ~/.solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime.N{1,2,3,4,5}-handoff.md
ls -la ~/.solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime.N*-addendum.md
ls -la ~/.solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime.N{2,3,4}-eval.{md,json}
# Gate confirmation
python3 -c "import json; d=json.load(open('~/.solar/harness/sprints/sprint-20260523-lease-based-model-fleet-runtime.task_graph.json'.replace('~','/Users/lisihao'))); print(d['gate_results'])"
```

## 5. no-live-pane-mutation 保护

- 绝不 `tmux send-keys` / `tmux kill-pane` / `solar-harness restart`
- 绝不 SIGKILL 任何 Python 进程
- 本 Planner 切片仅写文件
- 不动 N2 已实施的 lease broker 源码

## 6. Rollback / Stop Rules

### Rollback

- Planner 单文件可独立重写, 不影响 N1-N5
- task_graph patch 仅加字段; rollback = git revert 单 patch

### Stop Rules

- 不动 N1-N5 builder artifacts (已 PASS)
- 不动 lease broker 实施源码 (N2 PASS)
- 不重启 harness
- 不杀任何 Python 进程
- 不用乐观词 (已修复 / 稳定 / 完美 / 无需担忧 / done / complete / implemented)

## 7. SLO

| 指标 | hard | soft |
|------|------|------|
| sprint-level artifacts (plan+planning.html) 全到位 | < 2 → FAIL | n/a |
| task_graph schema=solar.task_graph.v1 + 节点字段补齐 | 缺 → FAIL | n/a |
| graph-scheduler validate ok | failed → FAIL | warnings > 0 → WARN |
| Planner 改动 N1-N5 handoff / eval | > 0 → 立即 FAIL | n/a |
| Planner 改动 lib lease broker 源码 | > 0 → 立即 FAIL | n/a |

## 8. 失败恢复

- Planner 任一文件失败 → 单独重写
- 若 graph_doctor 再次 reset N1+N5 → 复用本 backfill pattern
- 若 evaluator 二次审查 FAIL → ATLAS structured repair, 不擅自手改 task_graph N1-N5 status (使用 sanctioned `graph-dispatch node-verdict` CLI)
- 多次 `pane_not_idle` (events seq=7/16/19/21/22/23/24) → TUI epic S03 实施完成后稳定

## 9. 给后续接力

- Lease broker (N2) 已实施完成, 后续多 sprint 可依赖:
  - MTSPR: stale runner cleanup 集成 lease 检查
  - UAKG: U2 background run 应当独立 actor lease
  - TUI epic: pane hygiene registry 与 lease broker 协调
  - smoke variants: spillover 调度可用 lease pool
- Round 4 (per autoresearch optimizer): 已 PASS, 不需再优化

## 10. Knowledge Context

40+K total sprint evidence (design 13K + multiple N1-N5 handoffs + addenda + eval) 已 self-contained. `context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; 11 capability `injectable_only`.

Round 4 telemetry (per autoresearch_optimizer 5/28 14:06): phase=prd_ready / status=drafting / round=4 / eval_verdict=PASS / 0 errors / 3 warnings.
