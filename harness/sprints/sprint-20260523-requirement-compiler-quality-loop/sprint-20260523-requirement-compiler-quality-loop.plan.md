# Plan — Requirement Compiler Quality Loop 执行计划

sprint_id: `sprint-20260523-requirement-compiler-quality-loop`
generated_at: `2026-05-24T03:55:00Z`
knowledge_context: `solar-harness context inject used (mirage nonzero -> qmd/obsidian/solar_db fallback)`
peer: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`（并行，read-only 引用其 IR schema）
downstream_blocker_for: `sprint-20260523-agent-plan-optimizer-foundation`
wake_violation_fixed: `invalid_task_graph:node_S1_missing_write_scope`（重写 task_graph）

## 1. 交付切片顺序（4 wave）

| Wave | Node | 元素 | 写入 |
|------|------|------|------|
| W1 | N1 | Golden Set spec | `workstream-N1-golden-set.md` + `golden-set-spec.md` |
| W2 | N2, N3, N4 | Failure Replay / Planner Diff / Evaluator Reject（3 路并行） | 各 1-2 个 md + schemas/feedback-event.schema.v1.draft.json |
| W3 | N5 | Quality Metrics + Gate | `workstream-N5-quality-metrics.md` + `quality-metrics-spec.md` + `schemas/compile-quality-metrics.schema.v1.draft.json` |
| W4 | N6 | E2E Quality Loop Walkthrough（join） | `workstream-N6-e2e-quality.md` + `e2e-quality-trace.md` |

合计 6 节点；4 layer。

## 2. 文件级写入范围

| Node | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| N1 | `<sid>.workstream-N1-golden-set.md` + `<sid>.golden-set-spec.md` | NEW |
| N2 | `<sid>.workstream-N2-failure-replay.md` | NEW |
| N3 | `<sid>.workstream-N3-planner-diff-feedback.md` + `schemas/feedback-event.schema.v1.draft.json` | NEW |
| N4 | `<sid>.workstream-N4-evaluator-rejection-feedback.md` | NEW |
| N5 | `<sid>.workstream-N5-quality-metrics.md` + `<sid>.quality-metrics-spec.md` + `schemas/compile-quality-metrics.schema.v1.draft.json` | NEW |
| N6 | `<sid>.workstream-N6-e2e-quality.md` + `<sid>.e2e-quality-trace.md` | NEW |
| Planner（本轮） | `<sid>.{design, plan, task_graph, planning_html}.{md,json,html}` | NEW（task_graph 重写） |

`<sid>` = `sprint-20260523-requirement-compiler-quality-loop`

**严格禁止 write_scope 外**：
- `lib/*.py` / `validate.sh` / `apps/pm-pane/**` / `infra/prod/**` / `.env*` / `secrets/**`（design only；实施归 follow-up）
- peer sprint backend-foundation 任何 artifact
- APO sprint 任何 artifact
- 其他 in-flight sprint artifact
- `~/.solar/STATE.md` / epic.*
- `/tmp/*`

## 3. 并发边界

- L0: N1（golden set 基础）
- L1: N2 + N3 + N4 全并行（都 deps N1，write_scope 互不重叠）
- L2: N5（deps N2+N3+N4，整合 feedback → metrics）
- L3: N6 join（deps N5）
- max-parallel 建议 3

## 4. 每节点 workstream md 段落契约

每 N1..N6 必含：

1. **已完成**：本节点交付物清单
2. **Inputs From PRD**：明引 PRD problem statement 6 元素中本节点负责的部分
3. **Architecture Decision**：本节点钉死决策
4. **Acceptance 映射**：覆盖 PRD §9 + Contract invariants
5. **Compat with peer/APO/in-flight**：明示未 mutate peer backend-foundation / APO / 其他 in-flight sprint
6. **No-false-green 自审**：明示本节点未把 doc-only/contract-only 冒充 implemented（**PRD core 红线**）

N6 必须额外含完整 e2e walkthrough（7 step）。

## 5. 验证命令

```bash
SID=sprint-20260523-requirement-compiler-quality-loop
H=/Users/lisihao/.solar/harness
PEER=sprint-20260523-pm-pane-requirement-compiler-backend-foundation
APO=sprint-20260523-agent-plan-optimizer-foundation

# A. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. 6 workstream md + golden-set + quality-metrics + e2e-trace + 2 schema 齐全
for f in workstream-N1-golden-set workstream-N2-failure-replay workstream-N3-planner-diff-feedback \
         workstream-N4-evaluator-rejection-feedback workstream-N5-quality-metrics workstream-N6-e2e-quality \
         golden-set-spec quality-metrics-spec e2e-quality-trace; do
  test -f $H/sprints/$SID.$f.md || echo "MISSING $f.md"
done
test -f $H/schemas/feedback-event.schema.v1.draft.json
test -f $H/schemas/compile-quality-metrics.schema.v1.draft.json

# D. 每节点 6 段契约
for f in $H/sprints/$SID.workstream-*.md; do
  for sec in "## 已完成" "Inputs From PRD" "Architecture Decision" "Acceptance 映射" "Compat with" "No-false-green"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $(basename $f)"
  done
done

# E. golden set ≥20 case + 12 cell 分布
python3 -c "
import re
text = open('$H/sprints/$SID.golden-set-spec.md').read()
cases = re.findall(r'case_id\s*:\s*\S+', text)
print(f'golden case count: {len(cases)} (期望 ≥20)')
assert len(cases) >= 20
# 12 cell: 4 source × 3 type
for src in ['verbal', 'codex-pm-router', 'pm-template', 'chain-watcher']:
    for typ in ['delivery', 'research', 'strategy']:
        if f'{src}' not in text or f'{typ}' not in text:
            print(f'WARN cell {src}×{typ} 未覆盖')
"

# F. feedback-event schema 必填字段
python3 -c "
import json
s=json.load(open('$H/schemas/feedback-event.schema.v1.draft.json'))
need={'schema_version','event_id','event_type','sprint_id','actor','severity','ts'}
props=s.get('properties',{})
missing=need - set(props.keys())
print('OK' if not missing else f'WARN missing {missing}')
# event_type enum
ee=s.get('properties',{}).get('event_type',{}).get('enum',[])
assert set(ee) >= {'planner_diff','evaluator_reject','golden_set_violation','replay_fail'}
"

# G. compile-quality-metrics schema 10 项
python3 -c "
import json
s=json.load(open('$H/schemas/compile-quality-metrics.schema.v1.draft.json'))
need={'golden_set_pass_rate','field_coverage_rate','acceptance_coverage_rate','secret_leak_rate',
      'planner_diff_rate','evaluator_reject_rate','replay_consistency_rate',
      'misclassification_rate','miscompilation_rate','evidence_ledger_completeness'}
props=s.get('properties',{})
missing=need - set(props.keys())
print('OK' if not missing else f'WARN missing {missing}')
"

# H. 4 hard gate metric 默认 hard 标记
for hard in acceptance_coverage_rate secret_leak_rate evidence_ledger_completeness replay_consistency_rate; do
  grep -E "$hard.*hard|hard.*$hard" $H/sprints/$SID.quality-metrics-spec.md \
    || echo "WARN $hard 未标 hard"
done

# I. failure replay 4 错误类
for kind in misclassification miscompilation missing_field secret_leak; do
  grep -q "$kind" $H/sprints/$SID.workstream-N2-failure-replay.md \
    || echo "MISSING failure kind $kind"
done

# J. 5 feedback event_type 全集
for ee in planner_diff evaluator_reject golden_set_violation replay_fail; do
  grep -q "$ee" $H/sprints/$SID.workstream-N3-planner-diff-feedback.md \
    $H/sprints/$SID.workstream-N4-evaluator-rejection-feedback.md 2>/dev/null \
    || echo "MISSING event_type $ee"
done

# K. e2e-trace 7 step
for step in "Step 1" "Step 2" "Step 3" "Step 4" "Step 5" "Step 6" "Step 7"; do
  grep -q "$step" $H/sprints/$SID.e2e-quality-trace.md \
    || echo "MISSING e2e $step"
done

# L. 未真改 lib/ / validate.sh / apps
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^schemas/validate\.sh$|^apps/pm-pane/"

# M. 未触碰 peer sprint backend-foundation artifact
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "sprint-20260523-pm-pane-requirement-compiler-backend-foundation\.(design|plan|task_graph)\.(md|json)$"

# N. 未触碰 APO sprint artifact
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "sprint-20260523-agent-plan-optimizer-foundation\.(design|plan|task_graph)\.(md|json)$"

# O. 未触碰其他 in-flight sprint
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "sprint-20260523-(pane-as-physical-operator-architecture|physical-operator-taxonomy-truthification|operator-class-compatibility-cutover|gepa-optimize-anything-implementation)\.(design|plan|task_graph)\.(md|json)$|sprint-20260524-actor-host"

# P. 无 raw secret 字面
! grep -rE "(api[_-]?key|bearer\s+|sk-|password|cookie|oauth)\s*[:=]\s*['\"][A-Za-z0-9]{8,}" \
  $H/sprints/$SID.*.md $H/schemas/feedback-event.schema.v1.draft.json $H/schemas/compile-quality-metrics.schema.v1.draft.json 2>/dev/null \
  | grep -v "REDACTED_API_KEY_TEST_FIXTURE"

# Q. 无 /tmp/ 引用（除 stop rule 警示）
! grep -rE "/tmp/" $H/sprints/$SID.*.md 2>/dev/null | grep -v "禁止\|不写"

# R. 未引入新 PyPI
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "requirements\.txt|pyproject\.toml"

# S. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止真改 `lib/*.py` / `validate.sh` / `apps/pm-pane/` / `infra/prod/**` / `.env*` / `secrets/**`
- 禁止 mutate peer sprint backend-foundation artifact（并行运行；不互相 mutate）
- 禁止 mutate APO sprint artifact（本 sprint 是 APO predecessor，等 APO 自己被 gate 阻塞）
- 禁止 mutate 其他 in-flight sprint artifact
- 禁止改 `~/.solar/STATE.md` / epic.* / 其他 sprint
- 禁止写 `/tmp`
- 禁止引入新 PyPI 依赖
- 禁止 raw secret 入 feedback event / golden case / replay log
- 禁止 doc-only/contract-only 冒充 implemented（PRD core 红线）
- 禁止缺 verifier decision 标 DONE（contract stop_conditions）
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N1 golden set < 20 case 或 12 cell 缺任一 → FAIL
- N2 failure replay 缺 4 错误类（misclassification/miscompilation/missing_field/secret_leak）任一 → FAIL
- N3+N4 feedback-event schema 缺必填字段（schema_version/event_id/event_type/sprint_id/actor/severity/ts）→ FAIL
- N3+N4 event_type enum 缺 4 值（planner_diff/evaluator_reject/golden_set_violation/replay_fail）→ FAIL
- N3+N4 secret-safe 缺 truncate + regex scrub 设计 → FAIL（PRD 红线 + Contract invariants）
- N5 quality-metrics 缺 10 项任一 → FAIL
- N5 缺 4 hard gate 标记（acceptance_coverage / secret_leak / evidence_ledger / replay_consistency）→ FAIL
- N6 e2e walkthrough 缺 7 step 任一 → FAIL
- N6 真跑 compiler 代码（peer sprint 范围）→ FAIL（C2 复用 spec only）
- 任何节点把 doc-only/contract-only 冒充 implemented → FAIL（**PRD core 红线**）
- 任何节点真改 lib/ / validate.sh / apps/pm-pane → FAIL + ATLAS
- 任何节点 mutate peer sprint backend-foundation / APO / in-flight sprint → FAIL + ATLAS
- 任何节点写 /tmp → FAIL
- 任何节点引入新 PyPI → FAIL
- raw secret 落盘 → FAIL + 立即删除
- 任何 acceptance 未映射到 validation → FAIL（Contract invariants）
- 任何节点缺 verifier decision 标 DONE → FAIL（Contract stop_conditions）
- 乐观词 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 8. 模型路由建议

| Node | Writer class | Verifier class | Model |
|------|-------------|----------------|-------|
| N1 Golden Set | DeepArchitect（需 ≥20 case 细致设计） | Verifier | sonnet |
| N2 Failure Replay | ImplementationWorker | Critic | sonnet |
| N3 Planner Diff Feedback | ImplementationWorker | Verifier | sonnet |
| N4 Evaluator Reject Feedback | ImplementationWorker | Critic | sonnet |
| N5 Quality Metrics | DeepArchitect | Verifier | sonnet |
| N6 E2E Walkthrough | DeepArchitect | Verifier | opus（join + 跨节点 walkthrough）|

writer ≠ verifier class（per Contract invariants + peer sprint contract）。

## 9. 时间预算

- N1 Golden Set：~50 min（≥20 case + 12 cell + 每 case 9 字段）
- N2 Failure Replay：~30 min（与 N3/N4 并行）
- N3 Planner Diff Feedback：~30 min
- N4 Evaluator Reject Feedback：~25 min
- N5 Quality Metrics：~45 min（10 metric + 4 hard gate + 公式 + 数据源）
- N6 E2E Walkthrough：~40 min
- 整 sprint 目标 2-3 dispatch round 内 passed

## 10. 完成定义（DoD 7 条 + Contract Planner Done Definition）

1. **已完成**：design.md / plan.md / task_graph.json（重写修复 wake violation）/ planning.html 4 件
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`
3. **已完成**：planning.html 注册
4. **未验证**：N1..N6 builder 节点未执行；6 workstream md + golden-set-spec + quality-metrics-spec + e2e-quality-trace + 2 schema 草案 未产
5. **未验证**：PRD §9 acceptance + Contract invariants + 10 quality metrics 未由 evaluator 复跑
6. **风险**：
   - doc-only/contract-only 冒充 implemented（PRD 红线；plan §7 stop rule）
   - mutate peer backend-foundation / APO / in-flight sprint（plan §6+§7 stop rule + git diff 校验）
   - 真改 lib/ / validate.sh / apps/pm-pane（design only；plan §6 stop rule）
   - feedback event 含 raw secret（N3+N4 acceptance 强制 truncate + scrub）
   - acceptance 未映射 validation（Contract invariants；N1 + N5 acceptance）
   - 引入新 PyPI（plan §6 stop rule）
   - 写 /tmp（plan §6 stop rule）
7. **后续待办**：
   - coordinator 派 N1 → {N2, N3, N4} 并行 → N5 → N6
   - evaluator 跑 plan §5 验证 A..S 全 PASS → sprint passed
   - sprint passed/finalized → APO sprint N0 dependency gate 解锁
   - Follow-up sprint：实施 `lib/requirement_compiler_quality/` 模块（golden_set.py / replay.py / feedback.py / metrics.py / gate.py 等）+ 真改 `validate.sh` + 真跑 replay
