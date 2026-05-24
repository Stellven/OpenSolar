# Plan — Operator Class Compatibility Cutover 执行计划

sprint_id: `sprint-20260523-operator-class-compatibility-cutover`
generated_at: `2026-05-23T20:25:00Z`
knowledge_context: `solar-harness context inject used (mirage timeout -> qmd/obsidian/solar_db fallback)`
parent: `sprint-20260523-physical-operator-taxonomy-truthification`（read-only）
grandparent: `sprint-20260523-pane-as-physical-operator-architecture`（read-only）
parallel_protect: `sprint-20260523-lease-based-model-fleet-runtime` 不被 block / rewrite

## 1. 交付切片顺序（6 wave，PRD Workstream A-F 对齐）

| Wave | Node | Workstream | 写入 |
|------|------|------------|------|
| W1 | N1 | A Compatibility Audit Lock | `<sid>.workstream-A-audit.md` |
| W2 | N2, N4, N5 | B Mapping / D In-flight Safety / E Observability（3 路并行） | 各 1 md |
| W3 | N3 | C Scheduler Bridge Lock（deps N1+N2） | `<sid>.workstream-C-scheduler-bridge.md` |
| W4 | N6 | F Rollout/Rollback（join 全部） | `<sid>.workstream-F-rollout-rollback.md` + `<sid>.rollout-runbook.md` |

合计 6 节点；4 layer。

## 2. 文件级写入范围（强制 write_scope）

| Node | 写入文件 | 动作 |
|------|---------|------|
| N1 | `<sid>.workstream-A-audit.md` | NEW |
| N2 | `<sid>.workstream-B-canonical-mapping.md` + `<sid>.canonical-mapping.md` | NEW |
| N3 | `<sid>.workstream-C-scheduler-bridge.md` | NEW |
| N4 | `<sid>.workstream-D-inflight-safety.md` | NEW |
| N5 | `<sid>.workstream-E-observability.md` | NEW |
| N6 | `<sid>.workstream-F-rollout-rollback.md` + `<sid>.rollout-runbook.md` | NEW |
| Planner（本轮） | `<sid>.{design, plan, task_graph, planning_html}.{md,json,html}` | NEW |

`<sid>` = `sprint-20260523-operator-class-compatibility-cutover`

**严格禁止 write_scope 外**：
- 父 / grandparent sprint 任何 artifact（read-only 引用）
- `~/.solar/harness/lib/*.py` / `tools/*.py` / `config/*.json`（本 sprint design-only；实际代码改归后续实施 sprint）
- `~/.solar/harness/schemas/*.json`（schema 草案归 grandparent N1）
- `~/.solar/STATE.md` / epic.* / `sprint-20260523-lease-based-model-fleet-runtime.*` / ThunderOMLX 任何代码

## 3. 并发边界

- L0: N1（audit 是基础）
- L1: N2 + N4 + N5（3 路并行，write_scope 互不重叠；都 depends_on N1）
- L2: N3（depends_on N1+N2）
- L3: N6 join（depends_on N1..N5）
- max-parallel 建议 3

## 4. 每节点 handoff 段落契约

每 N*-workstream md 含：

1. **已完成**：交付物清单（表 / 流程图 / 映射）
2. **Inputs From PRD**：明示引用 PRD 段 + FR/G/A 编号
3. **Architecture Decision**：本节点钉死决策（含 Q1..Q5 中归属本节点的回答）
4. **Acceptance 映射**：本节点覆盖 A1..A9 中哪些
5. **In-flight Safety**：明示本节点设计未触碰 LEASED/RUNNING/DRAINING worker
6. **Stop-Rule Compliance**：未改父 sprint 原文件 / 未引入 strict mode 抢跑 / 未杀 in-flight worker / 未写 raw secret

N6 必须额外含：

- 6 Phase rollout 全集 + 每 Phase rollback 命令
- Strict mode 进入条件（数字 + 时间）
- Non-breaking 保证清单
- Parent sprint adoption brief

## 5. 验证命令

```bash
SID=sprint-20260523-operator-class-compatibility-cutover
H=/Users/lisihao/.solar/harness
PARENT=sprint-20260523-physical-operator-taxonomy-truthification
GRANDPARENT=sprint-20260523-pane-as-physical-operator-architecture

# A. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. 6 workstream md 齐全
for ws in A B C D E F; do
  test -f $H/sprints/$SID.workstream-$ws-*.md || echo "MISSING workstream-$ws"
done
test -f $H/sprints/$SID.canonical-mapping.md
test -f $H/sprints/$SID.rollout-runbook.md

# D. 6 段段落契约
for f in $H/sprints/$SID.workstream-*.md $H/sprints/$SID.rollout-runbook.md; do
  for sec in "## 已完成" "Inputs From PRD" "Architecture Decision" "Acceptance 映射" "In-flight Safety" "Stop-Rule"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $(basename $f)"
  done
done

# E. canonical mapping 6 桶全集
for legacy in planner builder evaluator architect pm external; do
  grep -q "$legacy" $H/sprints/$SID.canonical-mapping.md || echo "MISSING legacy $legacy"
done

# F. 10 canonical class 在 mapping
for cls in DeepArchitect RootCauseDebugger ImplementationWorker FastSubagent \
           ParallelExplorer Verifier ResearchSynthesizer BrowserOperator \
           GoogleStackOperator LocalPrivacyOperator; do
  grep -q "$cls" $H/sprints/$SID.canonical-mapping.md || echo "MISSING class $cls"
done

# G. external 拆 5 specific
for sub in ParallelExplorer ResearchSynthesizer BrowserOperator GoogleStackOperator LocalPrivacyOperator; do
  grep -E "external.*$sub|$sub.*external" $H/sprints/$SID.canonical-mapping.md > /dev/null || echo "MISSING external split $sub"
done

# H. scheduler resolve 4 步顺序
for step in "alias resolve" "canonical resolve" "fallback" "strict canonical"; do
  grep -q "$step" $H/sprints/$SID.workstream-C-scheduler-bridge.md || echo "MISSING step '$step'"
done

# I. In-flight safety 3 状态保护
for st in LEASED RUNNING DRAINING; do
  grep -q "$st" $H/sprints/$SID.workstream-D-inflight-safety.md || echo "MISSING state $st"
done

# J. 三视图字段（legacy / canonical / selected）
for view in legacy_role canonical_operator_class selected_binding resolved_via; do
  grep -q "$view" $H/sprints/$SID.workstream-E-observability.md || echo "MISSING view field $view"
done

# K. no_matching_worker 原因分类树（≥7 reason）
for r in unknown_legacy_role canonical_inventory_empty all_candidates_in_flight \
         all_candidates_quota_blocked all_candidates_auth_blocked profile_gate_rejected \
         strict_mode_no_canonical; do
  grep -q "$r" $H/sprints/$SID.workstream-C-scheduler-bridge.md \
    $H/sprints/$SID.workstream-E-observability.md 2>/dev/null \
    || echo "MISSING reason $r"
done

# L. Phase 0..5 全集
for p in "Phase 0" "Phase 1" "Phase 2" "Phase 3" "Phase 4" "Phase 5"; do
  grep -q "$p" $H/sprints/$SID.rollout-runbook.md || echo "MISSING $p"
done

# M. 每 Phase rollback 命令
grep -cE "rollback" $H/sprints/$SID.rollout-runbook.md   # 期望 ≥ 6

# N. Strict mode 进入条件（数字 + 时间）
grep -E "≥ 7 天|≥ 14 天|7 days|14 days|alias resolve.*100%|fallback_legacy.*< 5%" \
  $H/sprints/$SID.rollout-runbook.md | head -3

# O. Q1..Q5 全部回答
python3 -c "
import os, re
H='$H'; SID='$SID'
text=''
for f in os.listdir(f'{H}/sprints/'):
    if f.startswith(SID) and f.endswith('.md'):
        text += open(f'{H}/sprints/{f}').read()
missing=[f'Q{i}' for i in range(1,6) if not re.search(rf'\bQ{i}\b', text)]
if missing: print('WARN unanswered:', missing)
else: print('Q1..Q5 all referenced')
"

# P. R1..R5 全集缓解
for r in R1 R2 R3 R4 R5; do
  grep -q "\b$r\b" $H/sprints/$SID.*.md 2>/dev/null || echo "WARN $r not addressed"
done

# Q. 无 raw secret
! grep -rE "(api[_-]?key|bearer\s+|sk-|ANTHROPIC.*=\s*['\"][A-Za-z])" $H/sprints/$SID.*.md 2>/dev/null

# R. 父 sprint 原文件未被修改
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "$PARENT\.(design|plan|task_graph)\.(md|json)$|$GRANDPARENT\.(design|plan|task_graph)\.(md|json)$"

# S. parallel sprint 未碰
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "lease-based-model-fleet-runtime"

# T. 未触碰生产代码
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^tools/|^config/|^solar-harness\.sh|^hooks/|^skills/"

# U. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止杀 / 重启 LEASED / RUNNING / DRAINING worker（per D3 + Hard Rules）
- 禁止改父 / grandparent sprint 任何 artifact（仅引用 read-only）
- 禁止改 Solar production code（lib/tools/config/solar-harness.sh/hooks/skills）—— 本 sprint design-only
- 禁止改 `~/.solar/STATE.md` / epic.* / `sprint-20260523-lease-based-model-fleet-runtime.*` / ThunderOMLX 任何代码
- 禁止 strict canonical mode 抢跑（必须 Phase 4 + 进入条件满足）
- 禁止无观测切换（dual visibility 必启用）
- 禁止 raw secret 落盘
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N1 audit 缺 6 组件状态报告 → FAIL
- N2 canonical-mapping 缺 6 legacy 桶 或 10 canonical class 或 external 5 拆分 → FAIL
- N3 scheduler resolve 缺 4 步顺序 → FAIL
- N3 缺 no_matching_worker 原因分类树（≥7 reason） → FAIL
- N4 缺 LEASED/RUNNING/DRAINING 三状态保护规则 → FAIL
- N4 缺 deferred-update queue 设计 → FAIL
- N5 status payload 缺 legacy_role / canonical_operator_class / selected_binding / resolved_via 四字段 → FAIL
- N6 缺 Phase 0-5 全集 → FAIL
- N6 缺每 Phase rollback 命令 → FAIL
- N6 缺 strict mode 进入条件（数字 + 时间）→ FAIL
- N6 留 TBD / 含糊项 → FAIL
- Q1..Q5 任一未回答 → FAIL
- R1..R5 任一未缓解 → FAIL
- 任何节点修改父 / grandparent sprint 原文件 → FAIL + ATLAS
- 任何节点设计杀 in-flight worker → FAIL + ATLAS
- 任何节点引入 strict mode 抢跑（Phase 1-3 强制 canonical-only）→ FAIL
- 任何文件含 raw secret 字面 → FAIL + 立即删除
- 任何节点改 production 代码 / 改 5-pane 拓扑 / 引入新进程模型 → FAIL + ATLAS
- 任何节点 block / rewrite parallel sprint → FAIL + ATLAS
- 乐观词 → FAIL
- PRD/contract mtime 变化 → 重跑 planner

## 8. 模型路由建议

per parent sprint scoring rules：

| Node | Writer | Verifier | Model |
|------|--------|----------|-------|
| N1 Audit | ImplementationWorker (audit scan) | Verifier | sonnet |
| N2 Canonical Mapping | DeepArchitect | Critic | sonnet |
| N4 In-flight Safety | ImplementationWorker | Verifier | sonnet |
| N5 Observability | ImplementationWorker | Critic | sonnet |
| N3 Scheduler Bridge | ImplementationWorker | Verifier | sonnet |
| N6 Rollout/Rollback | DeepArchitect | Verifier | opus（rollout 风险高 + 全局 join）|

writer ≠ verifier class（per parent sprint contract）。

## 9. 时间预算

- N1 Audit：~40 min（6 组件盘点）
- N2 Canonical Mapping：~30 min（与 N4/N5 并行）
- N4 In-flight Safety：~30 min（与 N2/N5 并行）
- N5 Observability：~25 min（与 N2/N4 并行）
- N3 Scheduler Bridge：~40 min（含 4 步顺序 + 7 reason 分类树）
- N6 Rollout/Rollback：~45 min（6 Phase + rollback）
- 整 sprint 目标 2-3 个 dispatch round 内 passed

## 10. 完成定义（DoD 7 条 + Planner Done Definition + Acceptance Gates）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`
3. **已完成**：planning.html 注册
4. **未验证**：N1..N6 builder 节点未执行；6 workstream md + canonical-mapping.md + rollout-runbook.md 未产
5. **未验证**：PRD A1..A9 / Q1..Q5 / R1..R5 全集对照未由 evaluator 复跑
6. **风险**：
   - 越权改父 / grandparent sprint 原文件（plan §6 stop rule + git diff 校验）
   - 设计杀 in-flight worker（plan §7 stop rule + N4 acceptance）
   - strict mode 抢跑（plan §7 + Phase 4 进入条件）
   - dual-write 不一致致 status 混乱（R3；N5 三视图 + reconcile log）
   - alias mapping 不完整继续 no_matching_worker（R1；N2 acceptance 6 legacy + 10 canonical）
   - observability 不足运维看不出路径（R4；N5 4 字段 + 7 reason 分类）
7. **后续待办**：
   - coordinator 派 N1 → {N2, N4, N5} 并行 → N3 → N6
   - evaluator 跑 §5 验证 A..U 全 PASS → sprint passed
   - 实际 Phase 0 audit 真跑（dispatch 后由 builder 执行；本 plan 仅设计）
   - Follow-up sprint 实施实际代码（lib/ scheduler.py + lib/canonical_mapping.py 等）
