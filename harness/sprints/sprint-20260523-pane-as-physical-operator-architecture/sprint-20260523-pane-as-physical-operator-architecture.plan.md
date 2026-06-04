# Plan — Pane-as-Physical-Operator Architecture 执行计划

sprint_id: `sprint-20260523-pane-as-physical-operator-architecture`
generated_at: `2026-05-23T19:20:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: PM PRD + Contract (round 1) · pm-order.md · prd.html
purpose: Design-only sprint — 不实施代码；产 design + plan + task_graph + 5 个 workstream handoff + schema v2 草案 + migration.md。

## 1. 现状

- 本 sprint 由 PM 创建（codex_pm + claude_pm round 1 repair），尚未跑过 builder/evaluator
- 没有现成 task_graph.json — planner **本轮全新创建**
- Solar autoresearch pane optimizer 已 advisor injected（recommended trigger）
- mirage 知识库降级（self-contained 设计文档不依赖检索）

## 2. 交付切片顺序（5 wave）

| Wave | Node | Workstream | 写入 |
|------|------|------------|------|
| W1 | N1 | A Registry Lock | `<sid>.workstream-A-registry-lock.md` + `schemas/physical-operators.schema.v2.draft.json` |
| W2 | N2, N3 | B Runtime Lock / C Scheduler Lock（并行） | `<sid>.workstream-B-runtime-lock.md` / `<sid>.workstream-C-scheduler-lock.md` |
| W3 | N4 | D Observability Lock | `<sid>.workstream-D-observability-lock.md` |
| W4 | N5 | E Migration Lock | `<sid>.migration.md` + `<sid>.workstream-E-migration-lock.md` |

合计 5 节点；4 layer。

## 3. 文件级写入范围

| Node | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| N1 | `~/.solar/harness/sprints/<sid>.workstream-A-registry-lock.md` + `~/.solar/harness/schemas/physical-operators.schema.v2.draft.json` | NEW |
| N2 | `~/.solar/harness/sprints/<sid>.workstream-B-runtime-lock.md` | NEW |
| N3 | `~/.solar/harness/sprints/<sid>.workstream-C-scheduler-lock.md` | NEW |
| N4 | `~/.solar/harness/sprints/<sid>.workstream-D-observability-lock.md` | NEW |
| N5 | `~/.solar/harness/sprints/<sid>.migration.md` + `~/.solar/harness/sprints/<sid>.workstream-E-migration-lock.md` | NEW |
| Planner (本轮) | `<sid>.design.md` + `<sid>.plan.md` + `<sid>.task_graph.json` + `<sid>.planning.html` | NEW（本文件 + 其他 3 件） |

`<sid>` = `sprint-20260523-pane-as-physical-operator-architecture`

**严格禁止 write_scope 外**：

- `~/.solar/harness/config/physical-operators.json`（生产 config；本 sprint 只产 schema 草案）
- `~/.solar/harness/lib/*.py`（本 sprint 不实施代码）
- `~/.solar/harness/tools/*.py`（同）
- `~/.solar/STATE.md` / epic.* / 其他 sprint artifact / ThunderOMLX 任何路径
- `sprint-20260523-lease-based-model-fleet-runtime.*` 任何文件
- 任何 hook / skill / prompt / `solar-harness.sh`

## 4. 并发边界

- L0: N1（单节点，registry 是基础）
- L1: N2 + N3（runtime + scheduler 并行；read N1 输出，write 互不重叠）
- L2: N4（observability，依赖 N3 选择算法）
- L3: N5（migration，依赖 N1+N2+N3+N4 全集 join）
- max-parallel 建议 2（L1）

## 5. 每节点 handoff 段落契约

每个 N*-handoff 必须含：

1. **已完成**：本节点交付物（含表格 / 代码块 / 状态图 / schema 片段）
2. **Inputs From PRD**：明示引用 PRD 哪段 + 哪个 FR/Q/D
3. **Architecture Decision**：本节点钉死决策（含 Q1..Q12 中归属本节点的回答）
4. **Conflicts / Dependencies / Degradation**
5. **Stop-Rule Compliance**：未触碰生产代码 / 未写 raw secret / 未引入新进程模型 / 未碰 5-pane 拓扑
6. **Open Questions**：本节点遗留留给下一 sprint

N5 migration.md 额外含：

- legacy → operator_id 完整映射表
- Rollout 7 phases（Phase 0..Phase 6）
- Rollback 命令全集
- 时间窗（Q7 答案：1 sprint 起步）

## 6. 验证命令

```bash
SID=sprint-20260523-pane-as-physical-operator-architecture
H=/Users/lisihao/.solar/harness

# A. DAG schema validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. ready / layers / batches
~/.solar/bin/solar-harness graph-scheduler ready    --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler layers   --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler batches  --graph $H/sprints/$SID.task_graph.json --max-parallel 2

# C. 5 workstream handoff 文件齐全
for ws in A B C D E; do
  test -f $H/sprints/$SID.workstream-$ws-*-lock.md || echo "MISSING workstream-$ws"
done

# D. schema v2 草案存在 + 11 顶层字段覆盖
test -f $H/schemas/physical-operators.schema.v2.draft.json
python3 -c "
import json
s=json.load(open('$H/schemas/physical-operators.schema.v2.draft.json'))
op_props = s.get('properties',{}).get('operators',{}).get('items',{}).get('properties',{})
need = {'physical','surface','model','endpoint','auth','quota','capability','policy','state','metrics','routing'}
missing = need - set(op_props.keys())
assert not missing, f'missing fields: {missing}'
print('schema v2 11 fields OK')
"

# E. migration.md 含 legacy 映射表 + rollout + rollback
test -f $H/sprints/$SID.migration.md
grep -E "legacy_provider_model_map|Phase 0|Phase 6|rollback" $H/sprints/$SID.migration.md | head -8

# F. 每 N*-handoff 含 6 段
for f in $H/sprints/$SID.workstream-*.md $H/sprints/$SID.migration.md; do
  for sec in "## 已完成" "Inputs From PRD" "Architecture Decision" "Conflicts" "Stop-Rule" "Open Questions"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $(basename $f)"
  done
done

# G. PRD A1..A8 acceptance 全映射
for a in A1 A2 A3 A4 A5 A6 A7 A8; do
  count=$(grep -lE "^\| $a \||$a " $H/sprints/$SID.*-lock.md $H/sprints/$SID.migration.md 2>/dev/null | wc -l)
  test "$count" -ge 1 || echo "WARN $a not mapped"
done

# H. Q1..Q12 全部回答
python3 -c "
import os, re
H='$H'
SID='$SID'
files = [f'{H}/sprints/{SID}.design.md'] + [
    f for f in os.listdir(f'{H}/sprints/')
    if f.startswith(f'{SID}.workstream-') or f == f'{SID}.migration.md'
]
text = ''
for f in files:
    p = f if f.startswith('/') else f'{H}/sprints/{f}'
    if os.path.exists(p):
        text += open(p).read()
missing = [f'Q{i}' for i in range(1,13) if not re.search(rf'\bQ{i}\b', text)]
if missing:
    print('WARN unanswered:', missing)
else:
    print('Q1..Q12 all referenced')
"

# I. R1..R10 全部覆盖 stop rule
for r in R1 R2 R3 R4 R5 R6 R7 R8 R9 R10; do
  count=$(grep -lE "\b$r\b" $H/sprints/$SID.*-lock.md $H/sprints/$SID.migration.md 2>/dev/null | wc -l)
  test "$count" -ge 1 || echo "WARN $r not addressed"
done

# J. secret safety: 无 raw secret 字面
! grep -rE "(api[_-]?key|bearer\s+|sk-|ANTHROPIC.*=\s*['\"][A-Za-z])" \
  $H/sprints/$SID.*.md $H/schemas/physical-operators.schema.v2.draft.json 2>/dev/null

# K. 未触碰生产代码
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^tools/|^config/physical-operators\.json|^solar-harness\.sh|^hooks/|^skills/"

# L. 未碰 parallel sprint
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "lease-based-model-fleet-runtime"

# M. parent-check（独立 sprint，无父）
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 7. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` 任何位置（本 sprint 不接 builder pane）
- 禁止 `solar-harness restart` / `solar-harness inject-prompt` / `solar-harness models switch`
- 禁止 kill 任何 pane / 删任何 task 目录
- 禁止改 `~/.solar/harness/config/physical-operators.json`（生产）
- 禁止改 `~/.solar/harness/lib/*.py` 或 `tools/*.py` 任何 Python（本 sprint 不实施）
- 禁止改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact / ThunderOMLX 任何路径
- 禁止 block / rewrite `sprint-20260523-lease-based-model-fleet-runtime` 任何文件
- 禁止把 raw secret / token / cookie / OAuth 写进任何 handoff / schema / migration
- 禁止引入新进程模型（systemd / Docker / k8s）
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 8. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N1 schema v2 草案缺 11 顶层字段任一 → FAIL
- N2 缺 lease/heartbeat/failure_transfer 状态机或决策树 → FAIL
- N3 缺 select_operator 伪代码或 verifier separation 实现 → FAIL
- N4 缺 8765 payload schema 或 sqlite view → FAIL
- N5 缺 legacy 映射表 / Rollout phases / Rollback 命令任一 → FAIL
- Q1..Q12 任一未在 design + workstream handoffs 中回答 → FAIL
- R1..R10 任一未对应 stop rule 或缓解 → FAIL
- PRD A1..A8 任一未映射到 DAG 节点 → FAIL
- 任一文件含 raw secret 字面值 → FAIL + 立即删除
- 任何节点改生产代码 / 改 5-pane 拓扑 / 引入新进程模型 → FAIL + ATLAS
- 任何文档使用乐观词 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

### Sprint-level Stop Rules（per PRD Planner Handoff）

- **STOP-A**：Planner round 3 仍未产出 task_graph.json → PM 介入重写 PRD 切片粒度（本轮已避免）
- **STOP-B**：graph-scheduler validate 持续 fail 同类 schema 错误 ≥ 2 round → 升级到 architect (pane 3) 二审
- **STOP-C**：design 发现需要破坏 C1 (向后兼容) 或 C2 (secret safety) → 停下回 PM 重评 priority

## 9. 模型路由建议

per PRD task_graph 要求 `verifier_operator_class != writer_operator_class`：

| Node | Writer class | Verifier class |
|------|-------------|----------------|
| N1 Registry | ImplementationWorker (schema-design) | Critic |
| N2 Runtime | ImplementationWorker | Verifier |
| N3 Scheduler | ImplementationWorker | Verifier |
| N4 Observability | ImplementationWorker | Critic |
| N5 Migration | DeepArchitect | Verifier |

实际 pane 路由（per 5-pane 拓扑 C8）：

- writer → pane 1 builder (glm-5.1) 或 pane 3 architect (opus)
- verifier → pane 2 evaluator (glm-5.1)
- N5 因 DeepArchitect 角色 → 推荐 pane 3 architect (opus)

## 10. 时间预算

- N1 Registry：~45 min（schema v2 草案 + workstream-A 文档）
- N2 Runtime：~30 min
- N3 Scheduler：~30 min（与 N2 并行）
- N4 Observability：~25 min
- N5 Migration：~40 min
- 整 sprint 目标 2-3 个 dispatch round 内 passed

## 11. 完成定义（DoD 7 条 + Planner Done Definition + Acceptance Gates）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`
3. **已完成**：planning.html 注册
4. **未验证**：N1..N5 builder 节点未执行；schema v2 草案 / 5 workstream handoff / migration.md 未产
5. **未验证**：PRD A1..A8 / Q1..Q12 / R1..R10 全集对照未由 evaluator 复跑
6. **风险**：
   - Builder 越权改生产代码（plan §7 stop rule + git diff 校验）
   - schema 字段一次扩太多致旧任务图 fail validate（R1 → schema v2 加 default + warn 兼容）
   - Lease/heartbeat 高并发死锁（R2 → 决策树 + chaos test in next sprint）
   - 模型漂移漏检（R4 + FR4 + Evidence Log 三层）
7. **后续待办**：
   - coordinator 按 task_graph 派 N1 → {N2, N3} 并行 → N4 → N5
   - evaluator 跑 §6 验证 A..L 全 PASS → sprint passed
   - architect (pane 3) 二审 design + migration + schema
   - PM 决定何时开下一 sprint（Phase 1 schema v2 加载器实施）
