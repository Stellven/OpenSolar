# Plan — PM Pane Requirement Compiler Backend Foundation 执行计划

sprint_id: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`
generated_at: `2026-05-24T03:15:00Z`
knowledge_context: `solar-harness context inject used (mirage timeout -> qmd/obsidian/solar_db fallback)`
parallel_protect: 4 in-flight sprints read-only（per design §9）
wake_violation_fixed: `invalid_task_graph:node_S1_missing_write_scope` — 本轮重写 task_graph 修复

## 1. 交付切片顺序（3 wave）

| Wave | Node | Workstream | 写入 |
|------|------|------------|------|
| W1 | N1 | IR Schema | `schemas/requirement-ir.schema.v1.draft.json` + `workstream-N1-ir-schema.md` |
| W2 | N2, N3, N4 | Adapters / Compiler / Gate Enhancement（3 路并行） | 各 1-2 个 md |
| W3 | N5 | Backward Compat（deps N1+N3） | `workstream-N5-backward-compat.md` |
| W4 | N_E2E | End-to-End Smoke join | `workstream-N6-e2e-smoke.md` + `e2e-trace.md` |

合计 6 节点；4 layer。

## 2. 文件级写入范围（强制 write_scope）

| Node | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| N1 | `~/.solar/harness/schemas/requirement-ir.schema.v1.draft.json` + `<sid>.workstream-N1-ir-schema.md` | NEW |
| N2 | `<sid>.adapter-mapping.md` + `<sid>.workstream-N2-adapters.md` | NEW |
| N3 | `<sid>.workstream-N3-compiler.md` | NEW |
| N4 | `<sid>.workstream-N4-gate-enhancement.md` | NEW |
| N5 | `<sid>.workstream-N5-backward-compat.md` | NEW |
| N_E2E | `<sid>.workstream-N6-e2e-smoke.md` + `<sid>.e2e-trace.md` | NEW |
| Planner（本轮） | `<sid>.{design, plan, task_graph, planning_html}.{md,json,html}` | NEW (task_graph 重写覆盖旧 generic) |

`<sid>` = `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`

**严格禁止 write_scope 外**：
- `~/.solar/harness/lib/*.py`（compiler 代码归 follow-up sprint）
- `~/.solar/harness/schemas/validate.sh`（真改归 follow-up）
- `~/.solar/harness/templates/prd.template.md` / `product-brief.template.md` / `sprint-contract.md`（旧 template 不变，IR superset）
- 任何 in-flight sprint artifact（pane-as-physical-operator / taxonomy-truthification / compatibility-cutover / completion-audit）
- `~/.solar/STATE.md` / epic.* / `/tmp/*`

## 3. 并发边界

- L0: N1（IR schema 基础）
- L1: N2 + N3 + N4 全并行（都 deps N1，write_scope 互不重叠）
- L2: N5（deps N1+N3，compat 需 compiler 规则）
- L3: N_E2E join（deps N1..N5 全部）
- max-parallel 建议 3

## 4. 每节点 workstream md 段落契约

每 N* 必含：

1. **已完成**：本节点交付物（schema 字段表 / 规则表 / mapping 表 / walkthrough）
2. **Inputs From PRD**：明引 PRD 段 + FR/G/A 编号 + Handoff 设计点编号
3. **Architecture Decision**：本节点钉死决策
4. **Acceptance 映射**：本节点覆盖 PRD A1/A2/A3 + 隐含 acceptance（IR schema valid / adapter 全覆盖 / 编译可逆）哪些
5. **Compat with in-flight**：明示未触碰任何 in-flight sprint artifact / 未真改 lib/*.py 或 validate.sh
6. **Stop-Rule Compliance**：未用 LLM / 未引入新 PyPI / 未写 /tmp / 未写 raw secret

N_E2E 必须额外含：

- e2e-trace.md 含完整 walkthrough（含每 step 输入/输出/中间状态）
- 4 类 input source 至少 1 类 sample（推荐 verbal 或 codex-pm-router）
- 缺字段触发的 prompt-back / fail-loud 实例
- secret 触发 reject 实例
- 旧 PRD import 兼容实例
- `solar-harness graph-scheduler validate` 假设输入（不真跑 compiler）

## 5. 验证命令

```bash
SID=sprint-20260523-pm-pane-requirement-compiler-backend-foundation
H=/Users/lisihao/.solar/harness

# A. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. 6 workstream md + adapter-mapping + e2e-trace + IR schema 草案 齐全
for f in workstream-N1-ir-schema workstream-N2-adapters workstream-N3-compiler \
         workstream-N4-gate-enhancement workstream-N5-backward-compat \
         workstream-N6-e2e-smoke adapter-mapping e2e-trace; do
  test -f $H/sprints/$SID.$f.md || echo "MISSING $f"
done
test -f $H/schemas/requirement-ir.schema.v1.draft.json

# D. 每节点 6 段契约
for f in $H/sprints/$SID.workstream-*.md; do
  for sec in "## 已完成" "Inputs From PRD" "Architecture Decision" "Acceptance 映射" "Compat with in-flight" "Stop-Rule"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $(basename $f)"
  done
done

# E. IR schema v1 必填 14 字段
python3 -c "
import json
s=json.load(open('$H/schemas/requirement-ir.schema.v1.draft.json'))
props = s.get('properties', {})
need = {'id','source','type','title','problem','goals','non_goals','user_stories',
        'acceptance','constraints','risks','planner_handoff','evidence_refs','created_at'}
missing = need - set(props.keys())
assert not missing, f'missing fields: {missing}'
required = set(s.get('required', []))
print(f'OK schema has {len(props)} properties, required={len(required)}')
"

# F. source enum 4 值
python3 -c "
import json
s=json.load(open('$H/schemas/requirement-ir.schema.v1.draft.json'))
source_enum = s.get('properties',{}).get('source',{}).get('enum', [])
assert set(source_enum) >= {'verbal','codex-pm-router','pm-template','chain-watcher'}, f'source enum 缺: {set([\"verbal\",\"codex-pm-router\",\"pm-template\",\"chain-watcher\"]) - set(source_enum)}'
print('OK 4 source enum')
"

# G. type enum 3 值
python3 -c "
import json
s=json.load(open('$H/schemas/requirement-ir.schema.v1.draft.json'))
type_enum = s.get('properties',{}).get('type',{}).get('enum', [])
assert set(type_enum) >= {'delivery','research','strategy'}, f'type enum 缺'
print('OK 3 type enum')
"

# H. adapter-mapping 含 4 类 source
for s in verbal codex-pm-router pm-template chain-watcher; do
  grep -q "$s" $H/sprints/$SID.adapter-mapping.md || echo "MISSING source $s in adapter mapping"
done

# I. compiler 4 outputs 派生规则全集
for out in prd.md contract.yaml task_graph.json handoff.md; do
  grep -q "$out" $H/sprints/$SID.workstream-N3-compiler.md || echo "MISSING compiler output $out"
done

# J. gate enhancement 5 检查项
for chk in "IR 存在性" "acceptance 全映射" "research-type" "secret scan" "provenance check"; do
  grep -q "$chk" $H/sprints/$SID.workstream-N4-gate-enhancement.md || echo "MISSING gate check $chk"
done

# K. backward-compat 含 import_legacy_prd_to_ir 设计
grep -E "import_legacy_prd|best-effort|warn 而非 fail" $H/sprints/$SID.workstream-N5-backward-compat.md | head -3

# L. e2e-trace 含完整 walkthrough
for step in "verbal_adapter" "deterministic_compiler" "validate.sh" "graph-scheduler validate"; do
  grep -q "$step" $H/sprints/$SID.e2e-trace.md || echo "MISSING e2e step $step"
done

# M. 无 raw secret
! grep -rE "(api[_-]?key|bearer\s+|sk-|password|cookie|oauth)\s*[:=]\s*['\"][A-Za-z0-9]{8,}" \
  $H/sprints/$SID.*.md $H/schemas/requirement-ir.schema.v1.draft.json 2>/dev/null

# N. 未真改 lib/ / validate.sh / templates
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^schemas/validate\.sh$|^templates/(prd|product-brief|sprint-contract)"

# O. 未引入新 PyPI 依赖（如果有 requirements.txt 或 pyproject.toml）
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "requirements\.txt|pyproject\.toml"

# P. 未写 /tmp
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^/tmp/"
! grep -rE "/tmp/" $H/sprints/$SID.*.md $H/schemas/requirement-ir.schema.v1.draft.json 2>/dev/null | grep -v "tmp_path\|tmpfile\|/tmp/\` 写入"

# Q. 未触碰 in-flight sprint artifact
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "sprint-20260523-(pane-as-physical-operator-architecture|physical-operator-taxonomy-truthification|operator-class-compatibility-cutover)\.(design|plan|task_graph)\.(md|json)$|sprint-20260524-actor-host-runtime-completion-audit\."

# R. PRD A1..A3 + 隐含 acceptance 映射
for a in A1 A2 A3 "IR schema valid" "adapter 全覆盖" "编译可逆"; do
  count=$(grep -lE "$a" $H/sprints/$SID.workstream-*.md $H/sprints/$SID.e2e-trace.md 2>/dev/null | wc -l)
  test "$count" -ge 1 || echo "WARN '$a' 未映射"
done

# S. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止真改 `~/.solar/harness/lib/*.py`（compiler 代码归 follow-up）
- 禁止真改 `~/.solar/harness/schemas/validate.sh`（spec only）
- 禁止改 `templates/{prd,product-brief,sprint-contract}.*`（IR 是 superset）
- 禁止改任何 in-flight sprint artifact（pane-as-physical-operator / taxonomy-truthification / compatibility-cutover / completion-audit）
- 禁止改 `~/.solar/STATE.md` / epic.* / 其他 sprint
- 禁止写 `/tmp` 任何文件（C7）
- 禁止引入新 PyPI 依赖（C6 — stdlib only）
- 禁止 raw secret 落盘到 IR / schema / workstream md（C12）
- 禁止用 LLM agent 做 IR 字段编译（C9 + Non-Negotiables §2）
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- N1 IR schema 缺 14 必填字段任一 → FAIL
- N1 source enum 缺 4 值 / type enum 缺 3 值 → FAIL
- N1 schema 不拒绝 secret 字段 → FAIL（C12）
- N2 adapter-mapping 缺 4 类 source 任一 → FAIL
- N3 compiler 缺 4 outputs 派生规则任一 → FAIL
- N3 设计任何 LLM / agent / 模糊匹配 → FAIL（C9 violation）
- N4 gate enhancement 缺 5 检查项任一（IR 存在 / acceptance 全映射 / research evidence / secret scan / provenance）→ FAIL
- N5 backward-compat 缺 best-effort import 设计或缺 warn-not-fail 策略 → FAIL
- N_E2E walkthrough 缺 4 step 任一 → FAIL
- N_E2E 缺 secret reject / 旧 PRD import / 缺字段 prompt-back 三个示例任一 → FAIL
- 任何节点真改 `lib/*.py` 或 `validate.sh` 或 templates → FAIL + ATLAS
- 任何节点 mutate in-flight sprint artifact → FAIL + ATLAS
- 任何节点写 /tmp → FAIL
- 任何节点引入新 PyPI 依赖 → FAIL
- raw secret 落盘 → FAIL + 立即删除
- 任何文档/代码用乐观词 → FAIL
- PRD A1..A3 + 隐含 acceptance 任一未映射 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

### Sprint-level Stop Rules（per PRD Handoff）

- **STOP-A**：Planner round 3 仍未产出三件套 + IR schema 草案 → PM 介入缩范围（可砍 N5 backward compat）
- **STOP-B**：IR schema v1 与现有 templates 字段冲突无法调和 → 升级 architect (pane 3) 二审
- **STOP-C**：编译器 deterministic 实现不可行（必须靠 LLM）→ 停下重评 C9 红线

## 8. 模型路由建议

per parent sprint scoring rules（taxonomy-truthification + lease-fleet-runtime）：

| Node | Writer class | Verifier class | Model |
|------|-------------|----------------|-------|
| N1 IR Schema | DeepArchitect (schema design) | Verifier | sonnet |
| N2 Adapters | ImplementationWorker | Critic | sonnet |
| N3 Compiler | ImplementationWorker | Verifier | sonnet |
| N4 Gate Enhancement | ImplementationWorker | Critic | sonnet |
| N5 Backward Compat | ImplementationWorker | Verifier | sonnet |
| N_E2E Smoke | DeepArchitect (walkthrough synthesis) | Verifier | opus（join + 跨节点一致性）|

writer ≠ verifier class（per parent sprint contract）。

## 9. 时间预算

- N1 IR Schema：~40 min（14 字段 + secret reject + 3 enum）
- N2 Adapters：~30 min（与 N3/N4 并行）
- N3 Compiler：~40 min（4 outputs 派生规则 + deterministic 实现 spec）
- N4 Gate Enhancement：~25 min
- N5 Backward Compat：~25 min
- N_E2E Smoke：~40 min（含 walkthrough trace）
- 整 sprint 目标 2-3 个 dispatch round 内 passed

## 10. 完成定义（DoD 7 条 + PRD Planner Done Definition）

1. **已完成**：design.md / plan.md / task_graph.json (重写) / planning.html 4 件
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`（修复 wake violation）
3. **已完成**：planning.html 注册
4. **未验证**：N1..N5 + N_E2E builder 节点未执行；schema 草案 + 6 workstream md + adapter-mapping + e2e-trace 未产
5. **未验证**：PRD A1..A3 + 隐含 acceptance + Q1..Q5 未由 evaluator 复跑
6. **风险**：
   - 任一节点真改 lib/ 或 validate.sh（plan §6 stop rule + git diff 校验）
   - 设计中夹带 LLM agent 做 IR 编译（C9 violation；plan §7 stop rule）
   - mutate in-flight sprint artifact（plan §6 stop rule）
   - raw secret 落盘 IR（plan §6 + N1 schema reject 设计）
   - 引入新 PyPI 依赖（plan §6 stop rule）
   - 写 /tmp（plan §6 stop rule）
   - acceptance coverage 未硬阻断（C11；N4 acceptance）
7. **后续待办**：
   - coordinator 派 N1 → {N2, N3, N4} 并行 → N5 → N_E2E
   - evaluator 跑 §5 验证 A..S 全 PASS → sprint passed
   - architect (pane 3) 二审 IR schema 与 pane-as-physical-operator schema v2 草案一致性
   - Follow-up sprint：实施 `lib/requirement_compiler/` 5 文件 + 真改 `validate.sh` + 真跑 E2E
