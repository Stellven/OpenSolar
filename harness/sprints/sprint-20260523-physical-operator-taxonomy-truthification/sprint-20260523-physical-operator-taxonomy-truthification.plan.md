# Plan — Physical Operator Taxonomy Truthification 执行计划

sprint_id: `sprint-20260523-physical-operator-taxonomy-truthification`
generated_at: `2026-05-23T19:50:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
parent: `sprint-20260523-pane-as-physical-operator-architecture`（read-only 引用，**不修改父原文件**）
parallel_protect: `sprint-20260523-lease-based-model-fleet-runtime` 不被 block / rewrite

## 1. 交付切片顺序（6 wave，与 PRD Workstream A-F 对齐）

| Wave | Node | Workstream | 写入 |
|------|------|------------|------|
| W1 | N1 | A Taxonomy Lock | `<sid>.workstream-A-taxonomy-matrix.md` |
| W2 | N2, N4, N5 | B Schema / D Lifecycle / E Safety（3 路并行，全依赖 N1） | 各 1 个 workstream md |
| W3 | N3 | C Scheduler Mapping（依赖 N1+N2） | `<sid>.workstream-C-scheduler-mapping.md` |
| W4 | N6 | F Rollout/Repair（join N1..N5） | `<sid>.workstream-F-rollout-repair.md` + `<sid>.parent-repair-addendum.md` |

合计 6 节点；4 layer。

## 2. 文件级写入范围（强制 write_scope）

| Node | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| N1 | `~/.solar/harness/sprints/<sid>.workstream-A-taxonomy-matrix.md` | NEW |
| N2 | `~/.solar/harness/sprints/<sid>.workstream-B-schema-truthification.md` | NEW |
| N3 | `~/.solar/harness/sprints/<sid>.workstream-C-scheduler-mapping.md` | NEW |
| N4 | `~/.solar/harness/sprints/<sid>.workstream-D-runtime-lifecycle.md` | NEW |
| N5 | `~/.solar/harness/sprints/<sid>.workstream-E-safety-policy.md` | NEW |
| N6 | `~/.solar/harness/sprints/<sid>.workstream-F-rollout-repair.md` + `~/.solar/harness/sprints/<sid>.parent-repair-addendum.md` | NEW |
| Planner（本轮） | `<sid>.{design, plan, task_graph, planning_html}.{md,json,html}` | NEW |

`<sid>` = `sprint-20260523-physical-operator-taxonomy-truthification`

**严格禁止 write_scope 外**：
- 父 sprint 的 `sprint-20260523-pane-as-physical-operator-architecture.{design,plan,task_graph}.{md,json}`（read-only 引用）
- `~/.solar/harness/lib/*.py`、`tools/*.py`、`config/*.json`（本 sprint design-only）
- `~/.solar/harness/schemas/*.json`（schema 草案归父 sprint N1_registry_lock 写）
- `~/.solar/STATE.md`、epic.*、`sprint-20260523-lease-based-model-fleet-runtime.*`、ThunderOMLX 任何路径

## 3. 并发边界

- L0: N1 单节点（taxonomy 是基础）
- L1: N2 + N4 + N5（3 路并行，write_scope 互不重叠；都 depends_on N1）
- L2: N3 单节点（depends_on N1+N2）
- L3: N6 join 单节点（depends_on N1..N5）
- max-parallel 建议 3

## 4. 每节点 handoff 段落契约

每个 N*-workstream md 必须含：

1. **已完成**：交付物清单（含表 / 状态图 / matrix / 伪代码）
2. **Inputs From PRD**：明示引用 PRD 段 + FR/G/A 编号
3. **Architecture Decision**：本节点钉死决策（含对应 Q1..Q11 答案）
4. **Acceptance 映射**：本节点覆盖了 A1..A12 中的哪些
5. **Conflicts / Dependencies / Degradation**
6. **Stop-Rule Compliance**：未触碰父 sprint 原文件 / 未引入 ML / 未合并 high-risk class / 未写 raw secret

N6 必须额外含：

- 父 sprint addendum 注入点（design §10 全集）
- 10 类 P0/Reservation/Follow-up 三档分配表（design §11）
- 父 sprint review gate 触发条件
- Follow-up sprint outline（具体 operator id 注册）

## 5. 验证命令

```bash
SID=sprint-20260523-physical-operator-taxonomy-truthification
H=/Users/lisihao/.solar/harness
PARENT=sprint-20260523-pane-as-physical-operator-architecture

# A. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. 6 个 workstream md 齐全
for ws in A B C D E F; do
  test -f $H/sprints/$SID.workstream-$ws-*.md || echo "MISSING workstream-$ws"
done
test -f $H/sprints/$SID.parent-repair-addendum.md

# D. 6 段段落契约
for f in $H/sprints/$SID.workstream-*.md $H/sprints/$SID.parent-repair-addendum.md; do
  for sec in "## 已完成" "Inputs From PRD" "Architecture Decision" "Acceptance 映射" "Conflicts" "Stop-Rule"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $(basename $f)"
  done
done

# E. 10-class taxonomy matrix 完整（10 行）
grep -cE "^\| [0-9]+ \|" $H/sprints/$SID.workstream-A-taxonomy-matrix.md
# 期望 ≥ 10

# F. 一级 class 10 枚举全在 schema 章节
for cls in DeepArchitect RootCauseDebugger ImplementationWorker FastSubagent \
           ParallelExplorer Verifier ResearchSynthesizer BrowserOperator \
           GoogleStackOperator LocalPrivacyOperator; do
  grep -q "$cls" $H/sprints/$SID.workstream-B-schema-truthification.md || echo "MISSING class $cls"
done

# G. ≥10 task_type ladder
for tt in ARCH_DESIGN ROOT_CAUSE_DEBUG CODE_IMPL FINAL_REVIEW RESEARCH_SYNTHESIS \
          BROWSER_VALIDATION GOOGLE_STACK LOCAL_PRIVACY_SCAN FAST_FANOUT PARALLEL_EXPLORATION; do
  grep -q "$tt" $H/sprints/$SID.workstream-C-scheduler-mapping.md || echo "MISSING task_type $tt"
done

# H. ≥10 score/penalty 项
for sc in capability_fit quality_score quota_score latency_score cost_score \
          availability_score context_affinity risk_match recent_error_penalty same_model_verifier_penalty; do
  grep -q "$sc" $H/sprints/$SID.workstream-C-scheduler-mapping.md || echo "MISSING score $sc"
done

# I. 13 状态 lifecycle 全集
for st in CREATED WARMING IDLE LEASED RUNNING DRAINING COOLDOWN \
          QUOTA_EXHAUSTED AUTH_EXPIRED STALE_CONTEXT DISABLED ERROR NEEDS_HUMAN_REVIEW; do
  grep -q "$st" $H/sprints/$SID.workstream-D-runtime-lifecycle.md || echo "MISSING state $st"
done

# J. 3 high-risk policy 独立 section
for hp in BrowserOperator GoogleStackOperator LocalPrivacyOperator; do
  grep -E "## .*$hp" $H/sprints/$SID.workstream-E-safety-policy.md > /dev/null || echo "MISSING policy section $hp"
done

# K. 旧角色桶兼容映射表
grep -E "planner.*DeepArchitect|builder.*ImplementationWorker|evaluator.*Verifier|architect.*DeepArchitect|external" \
  $H/sprints/$SID.workstream-B-schema-truthification.md | head -5

# L. parent-repair-addendum 含 adoption_points
grep -E "adoption_points|parent_node|N1_registry_lock|N3_scheduler_lock|N5_migration_lock" \
  $H/sprints/$SID.parent-repair-addendum.md | head -5

# M. Q1..Q11 全部回答
python3 -c "
import os, re
H='$H'; SID='$SID'
text = ''
for f in os.listdir(f'{H}/sprints/'):
    if f.startswith(SID) and f.endswith('.md'):
        text += open(f'{H}/sprints/{f}').read()
missing = [f'Q{i}' for i in range(1,12) if not re.search(rf'\bQ{i}\b', text)]
if missing: print('WARN unanswered:', missing)
else: print('Q1..Q11 all referenced')
"

# N. P0/Reservation/Follow-up 分配表（10 行）
grep -cE "P0|Reservation|Follow-up" $H/sprints/$SID.workstream-F-rollout-repair.md

# O. 无 raw secret
! grep -rE "(api[_-]?key|bearer\s+|sk-|ANTHROPIC.*=\s*['\"][A-Za-z])" \
  $H/sprints/$SID.*.md 2>/dev/null

# P. 父 sprint 原文件未被修改
git -C $H diff --name-only HEAD 2>/dev/null | grep -E "$PARENT\.(design|plan|task_graph)\.(md|json)$" \
  && echo "VIOLATION: parent sprint mutated" || echo "parent sprint clean"

# Q. parallel sprint 未碰
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "lease-based-model-fleet-runtime"

# R. 未触碰生产代码
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^tools/|^config/|^solar-harness\.sh|^hooks/|^skills/"

# S. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止修改父 sprint 任何 artifact（仅引用 read-only）
- 禁止改 Solar production code（lib/tools/config/solar-harness.sh/hooks/skills）
- 禁止改 `~/.solar/STATE.md` / epic.* / `sprint-20260523-lease-based-model-fleet-runtime.*` / ThunderOMLX 任何代码
- 禁止写 raw secret / token / cookie / OAuth
- 禁止合并 BrowserOperator / GoogleStackOperator / LocalPrivacyOperator 到 generic external
- 禁止引入 ML scoring
- 禁止引入新进程模型（systemd / Docker / k8s）
- 禁止 5-pane 拓扑改动
- 禁止在 DAG 节点把 model/provider 字面当长期真值
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N1 taxonomy matrix 不足 10 行 → FAIL
- N1 任一 class 缺 7 列（class/task types/capabilities/policy delta/quota/verifier/example ids）→ FAIL
- N2 schema 缺 10 枚举或缺旧桶兼容映射 → FAIL
- N3 task_type ladder < 10 或 scoring < 10 项 → FAIL
- N3 同 provider verifier 未 high_risk hard block → FAIL
- N4 lifecycle < 13 状态或未回答 COOLDOWN/STALE_CONTEXT/NEEDS_HUMAN_REVIEW/DRAINING→IDLE 四问 → FAIL
- N5 Browser / GoogleStack / LocalPrivacy 任一未独立 section 或未列 denied_actions → FAIL
- N5 任一 high-risk 合并到 generic external → FAIL + ATLAS
- N6 缺 P0/Reservation/Follow-up 三档分配或留 TBD → FAIL
- N6 缺父 sprint addendum adoption_points → FAIL
- Q1..Q11 任一未回答 → FAIL
- R1..R7 任一未在 design/workstream 缓解 → FAIL
- 任何节点修改父 sprint 原文件 → FAIL + ATLAS
- 任何文件含 raw secret 字面 → FAIL + 立即删除
- 任何节点改 production 代码 / 改 5-pane 拓扑 / 引入新进程模型 → FAIL + ATLAS
- 任何节点 block / rewrite parallel sprint → FAIL + ATLAS
- 乐观词 → FAIL
- PRD/contract mtime 变化 → 重跑 planner

## 8. 模型路由建议

per PRD G5 deterministic / 不引 ML：

| Node | Writer class | Verifier class | Model |
|------|-------------|----------------|-------|
| N1 Taxonomy | DeepArchitect | Verifier | sonnet (高密度 matrix) |
| N2 Schema | ImplementationWorker | Critic | sonnet |
| N3 Scheduler | ImplementationWorker | Verifier | sonnet (算法伪代码 + scoring) |
| N4 Lifecycle | ImplementationWorker | Verifier | sonnet |
| N5 Safety | ImplementationWorker | SecurityGate | sonnet |
| N6 Rollout/Repair | DeepArchitect | Verifier | opus (跨 sprint addendum 综合) |

writer ≠ verifier class（per FR4 + 父 sprint contract）。

## 9. 时间预算

- N1 Taxonomy：~50 min（10 类 7 列矩阵）
- N2 Schema：~30 min
- N4 Lifecycle：~30 min（与 N2 并行）
- N5 Safety：~35 min（与 N2/N4 并行）
- N3 Scheduler：~45 min（20 task_type + 10 scoring）
- N6 Rollout/Repair：~40 min
- 整 sprint 目标 2-3 个 dispatch round 内 passed

## 10. 完成定义（DoD 7 条 + Planner Done Definition + Acceptance Gates）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`
3. **已完成**：planning.html 注册
4. **未验证**：N1..N6 builder 节点未执行；6 workstream md + parent-repair-addendum 未产
5. **未验证**：PRD A1..A12 / Q1..Q11 / R1..R7 全集对照未由 evaluator 复跑
6. **风险**：
   - 越权改父 sprint 原文件（plan §6 stop rule + git diff 校验）
   - 高风险类被合并回 generic external（D5 violation；plan §6 stop rule）
   - taxonomy 过粗回到旧桶（R2；N1 acceptance 10 类全列）
   - scheduler 回到 provider/model 直选（R5；N3 acceptance + scoring 强制）
   - 父 sprint 真值分叉（R7；N6 addendum 注入而非 mutation）
7. **后续待办**：
   - coordinator 派 N1 → {N2, N4, N5} 并行 → N3 → N6
   - evaluator 跑 §5 验证 A..R 全 PASS → sprint passed
   - 父 sprint evaluator 在 review parent N1/N3/N5 时比对本 addendum
   - Follow-up sprint 接 lease-fleet-runtime + 具体 operator id 真注册
