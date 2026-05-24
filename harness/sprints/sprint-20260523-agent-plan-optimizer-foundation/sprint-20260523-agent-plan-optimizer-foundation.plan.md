# Plan — Agent Plan Optimizer Foundation 执行计划

sprint_id: `sprint-20260523-agent-plan-optimizer-foundation`
generated_at: `2026-05-24T03:48:00Z`
knowledge_context: `solar-harness context inject used (mirage nonzero -> qmd/obsidian/solar_db fallback)`
dependency_gate: **BLOCKED**（per `.dependency-gate-evidence.md`；predecessor 1=active/planning_complete, predecessor 2=drafting/prd_ready；accepted 空）

## 1. 现状（task_graph 已就位，本轮不重写）

`.task_graph.json` 已存在并通过 `graph-scheduler validate`：

- 8 节点 N0..N7（N0 = dependency gate hard check；N1..N7 = APO spec workstream）
- 6 layers：`[N0] → [N1] → [N2, N3] → [N4, N5] → [N6] → [N7]`
- 0 errors / 6 advisory warnings（architecture_guard：N0/N1/N3/N6 缺 package_boundary；N2 缺 exploration_alternatives + kill_criteria）— 不阻断
- prerequisites 字段已含 2 张 predecessor sprint
- N0 hard depends_on enforce：N0 ready check 失败 → N1..N7 全 blocked

**本轮不修改 task_graph**（已正确反映 PRD Handoff task_graph 必须满足 6 条）。

## 2. 交付切片顺序（6 wave，仅 spec — 不重新设计 DAG）

| Wave | Node | 任务 | 写入（已 task_graph 定义）|
|------|------|------|---------------------------|
| W0 (BLOCKED) | N0 | dependency_gate_check（等 predecessor finalized） | `.N0-handoff.md` + `.dependency-baseline.md` |
| W1 | N1 | Intent IR + Logical Algebra schema 草案 | `.N1-handoff.md` + `.logical-algebra.md` + `schemas/agent-logical-algebra.schema.v1.draft.json` |
| W2 | N2, N3 | Rewrite Rules + Cost Model + Enforcers（2 路并行） | `.N2/.N3-handoff.md` + `.rewrite-rules.md` + `.cost-model.md` + `schemas/rewrite-rules.v1.draft.yaml` |
| W3 | N4, N5 | Plan Memo + Explain + Adaptive Replan（2 路并行） | `.N4/.N5-handoff.md` + `.explain-cli.md` + `.runtime-reopt.md` + `schemas/explain-plan.schema.v1.draft.json` |
| W4 | N6 | 3 Mode profiles | `.N6-handoff.md` + `.run-modes.md` |
| W5 | N7 | Eval gate + rollout sink | `.N7-handoff.md` + `.eval-gate.md` |

## 3. 文件级写入范围（已在 task_graph 钉死）

按 task_graph.json 每节点 write_scope 严格执行。**严格禁止 write_scope 外**：

- `~/.solar/harness/lib/*.py`（实施代码归 follow-up sprint）
- `~/.solar/harness/schemas/validate.sh`（不真改）
- 任何 in-flight sprint artifact
- `~/.solar/STATE.md` / epic.* / `/tmp/*`
- predecessor sprint 任何 artifact

## 4. 并发边界

- L0: N0（dependency gate — 单点，blocking）
- L1: N1（algebra 基础）
- L2: N2 + N3（rewrite + cost；并行，都 deps N1）
- L3: N4 + N5（plan memo + adaptive replan；并行，N4 deps N2+N3，N5 deps N2+N3）
- L4: N6（modes，deps N3+N5）
- L5: N7（sink，deps N4+N5+N6）
- max-parallel 建议 2

## 5. 每节点 handoff 段落契约

每 N* handoff 必含：

1. **已完成**：本节点 spec 草案产物（schema/yaml/md）
2. **Inputs From PRD**：明引 PRD 段 + FR/G/A + Handoff 设计点编号
3. **Architecture Decision**：钉死决策（含 Q1..Q3 对应答案）
4. **Acceptance 映射**：覆盖 PRD §9 4 项 + 8 项隐含 acceptance（per §13 Hard rules + Open Questions）
5. **Compat with in-flight**：明示未触碰 in-flight sprint artifact / 未真改 lib/*.py / 未引入新 PyPI / 未写 /tmp
6. **Stop-Rule Compliance**：未跳 N0 / 未用 LLM cost model / 未 enforcer 软化 / 未 logical-physical 混淆 / 未无限 replan / 未 Explain prose-only

N0 必须额外含：predecessor 实时 status snapshot + finalized 判定结果 + 不绕过证明。

N7 必须额外含：APO 整链路 evaluation gate + rollout phase 计划 + 进入实施 sprint 的硬阈值。

## 6. 验证命令

```bash
SID=sprint-20260523-agent-plan-optimizer-foundation
H=/Users/lisihao/.solar/harness

# A. DAG validate (已 ok, 6 advisory warnings)
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json

# B. layers / ready
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. Dependency gate 实时检查（N0 builder 必跑）
for s in sprint-20260523-pm-pane-requirement-compiler-backend-foundation sprint-20260523-requirement-compiler-quality-loop; do
  python3 -c "
import json
d=json.load(open('$H/sprints/${s}.status.json'))
status, phase = d['status'], d.get('phase','?')
ok = status in ('finalized','accepted') or phase in ('finalized','accepted')
print(f'${s}: status={status} phase={phase} predecessor_ok={ok}')
"
done
ls $H/sprints/accepted/ 2>/dev/null | grep requirement-compiler || echo "(accepted empty)"

# D. 6 件草案 + 8 handoff 齐全（builder 完成后）
test -f $H/schemas/agent-logical-algebra.schema.v1.draft.json
test -f $H/schemas/rewrite-rules.v1.draft.yaml
test -f $H/schemas/explain-plan.schema.v1.draft.json
for n in N0 N1 N2 N3 N4 N5 N6 N7; do
  test -f $H/sprints/$SID.$n-handoff.md || echo "MISSING $n-handoff.md"
done
for f in dependency-baseline logical-algebra rewrite-rules cost-model explain-cli runtime-reopt run-modes eval-gate; do
  test -f $H/sprints/$SID.$f.md || echo "MISSING $f.md"
done
test -f $H/sprints/$SID.dependency-gate-evidence.md

# E. Logical Algebra 15 operator 全集
for op in ScanContext UnderstandGoal DecomposeTask DesignSolution ExploreAlternatives \
          ImplementPatch GenerateTests RunTests RunBenchmark DebugRCA ReviewPatch \
          VerifyClaim SynthesizeReport CompressContext AskHuman; do
  grep -q "\"name\":\s*\"$op\"\|^$op\b" $H/schemas/agent-logical-algebra.schema.v1.draft.json $H/sprints/$SID.logical-algebra.md 2>/dev/null \
    || echo "MISSING logical operator $op"
done

# F. Rewrite rules 8 条全集
for r in LocalPreScan FanOutExploration VerifyAfterWrite WriterVerifierSeparation \
         QuotaReserve SandboxEnforcer ContextMaterialization AdaptiveReplan; do
  grep -q "$r" $H/schemas/rewrite-rules.v1.draft.yaml $H/sprints/$SID.rewrite-rules.md 2>/dev/null \
    || echo "MISSING rewrite rule $r"
done

# G. 5 enforcer hard rule 标记
for hard in VerifyAfterWrite WriterVerifierSeparation QuotaReserve SandboxEnforcer AdaptiveReplan; do
  grep -E "$hard.*hard|hard.*$hard" $H/sprints/$SID.rewrite-rules.md 2>/dev/null | head -1 \
    || echo "WARN $hard 未明示 hard"
done

# H. Cost model 10 项全集
for c in capability_fit historical_success quota_health risk_fit latency_fit \
         context_affinity cost_efficiency recent_failure_penalty stale_context_penalty verifier_conflict_penalty; do
  grep -q "$c" $H/sprints/$SID.cost-model.md 2>/dev/null || echo "MISSING cost $c"
done

# I. 3 mode + weight profile
for mode in Conservative Exploratory Economy; do
  grep -q "$mode" $H/sprints/$SID.cost-model.md $H/sprints/$SID.run-modes.md 2>/dev/null \
    || echo "MISSING mode $mode"
done

# J. Adaptive replan 3 stop rule
for sr in max_replan_rounds max_total_cost verifier_confidence_threshold; do
  grep -q "$sr" $H/sprints/$SID.runtime-reopt.md 2>/dev/null || echo "MISSING stop rule $sr"
done

# K. Explain schema 机读字段（per C13）
python3 -c "
import json, os
p='$H/schemas/explain-plan.schema.v1.draft.json'
if os.path.exists(p):
    s=json.load(open(p))
    need={'selected_plan','candidates','cost_vectors','rewrite_trace','rule_firings','why_selected','why_rejected','replan_history'}
    props=s.get('properties',{})
    missing=need - set(props.keys())
    print('OK' if not missing else f'WARN missing: {missing}')
"

# L. writer ≠ verifier class 全节点
python3 -c "
import json
g=json.load(open('$H/sprints/$SID.task_graph.json'))
for n in g['nodes']:
    w=n.get('writer_operator_class') or 'unknown'
    v=n.get('verifier_operator_class') or 'unknown'
    if w == v and w != 'unknown':
        print(f'WARN {n[\"id\"]} writer==verifier={w}')
"

# M. 未真改 lib/ / validate.sh / config
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "^lib/|^schemas/validate\.sh$|^config/(physical-operators|agent-actors|logical-operators)\.json$"

# N. 未触碰 in-flight sprint artifact
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "sprint-20260523-(pane-as-physical-operator-architecture|physical-operator-taxonomy-truthification|operator-class-compatibility-cutover|pm-pane-requirement-compiler-backend-foundation|requirement-compiler-quality-loop|gepa-optimize-anything-implementation)\.(design|plan|task_graph)\.(md|json)$|sprint-20260524-actor-host-runtime-completion-audit\."

# O. 无 raw secret
! grep -rE "(api[_-]?key|bearer\s+|sk-|password|cookie|oauth)\s*[:=]\s*['\"][A-Za-z0-9]{8,}" \
  $H/sprints/$SID.*.md $H/schemas/agent-logical-algebra.schema.v1.draft.json \
  $H/schemas/rewrite-rules.v1.draft.yaml $H/schemas/explain-plan.schema.v1.draft.json 2>/dev/null

# P. 未引入新 PyPI 依赖
! git -C $H diff --name-only HEAD 2>/dev/null | grep -E "requirements\.txt|pyproject\.toml"

# Q. 未写 /tmp
! grep -rE "/tmp/" $H/sprints/$SID.*.md 2>/dev/null | grep -v "禁止\|不写"

# R. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check --graph $H/sprints/$SID.task_graph.json 2>&1 || true
```

## 7. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止跳过 N0 dependency gate 直接做 N1..N7（C1 + STOP-A）
- 禁止真改 `lib/*.py` / `validate.sh` / `config/*.json`（spec only）
- 禁止改任何 in-flight sprint artifact（C9）
- 禁止改 predecessor sprint artifact（read-only 引用）
- 禁止改 `~/.solar/STATE.md` / epic.*
- 禁止写 `/tmp`（C8）
- 禁止引入新 PyPI 依赖（C7）
- 禁止 raw secret 入 plan（C10）
- 禁止把 cost model 外包给 LLM（C4）
- 禁止 enforcer 标 best-effort（C11）
- 禁止无限 replan（C12 — 三选一 stop rule）
- 禁止 Explain prose-only（C13）
- 禁止引入新进程模型（C14）
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 8. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做 FAIL 节点
- **N0 dependency gate FAIL（predecessor 未 finalized）** → coordinator 自动延后，不进 N1（不视为 sprint FAIL，仅延后）
- N1 logical algebra 缺 15 operator 任一 → FAIL
- N2 rewrite rules 缺 8 条任一 → FAIL；缺 5 enforcer hard 标记 → FAIL
- N3 cost model 缺 10 项 / 缺 3 mode weight profile → FAIL；cost model 含 LLM / agent → FAIL（C4 violation）
- N4 plan memo 缺 cache key / TTL / invalidation → FAIL；缺 candidates 字段 → FAIL
- N5 缺 6 trigger 任一 / 缺 3 stop rule 任一 → FAIL（C12）
- N6 缺 3 mode + 各 mode weight + 选择策略 → FAIL
- N7 缺 evaluation gate / rollout phase / 进入实施 sprint 硬阈值 → FAIL
- Explain schema 不含 8 必填字段 → FAIL（C13）
- 任何节点真改 lib/ / validate.sh / config → FAIL + ATLAS
- 任何节点 mutate in-flight sprint artifact → FAIL + ATLAS
- 任何节点写 /tmp → FAIL（C8）
- 任何节点引入新 PyPI → FAIL（C7）
- raw secret 落盘 → FAIL + 立即删除（C10）
- 任何文档/代码用乐观词 → FAIL
- writer == verifier class 任一节点 → FAIL（Non-Negotiables）
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

### Sprint-level Stop Rules（per PRD Handoff）

- **STOP-A**: predecessor 未 finalized → planner/builder 不动手；本 plan 是「blocked spec」模式，N1..N7 实际 deliverables 等 gate 解锁
- **STOP-B**: round 3 仍未产 6 件草案 → PM 介入缩范围（可砍 N5 adaptive replan 推 follow-up）
- **STOP-C**: Logical Algebra 与 operator taxonomy 严重冲突 → 升级 architect (pane 3) 二审
- **STOP-D**: Cost Model 公式无法 deterministic → 停下重评 C4 红线
- **STOP-E**: 某 enforcer（如 SandboxEnforcer）现有 runtime 无 hook → flag 为 P1 follow-up（守 C2 不另起 runtime）

## 9. 模型路由建议（per task_graph + Non-Negotiables §5）

| Node | Writer class | Verifier class | Model |
|------|-------------|----------------|-------|
| N0 | DeepArchitect (dependency check) | Verifier | opus |
| N1 | DeepArchitect + ResearchSynthesizer | Verifier | opus |
| N2 | DeepArchitect | Critic | opus |
| N3 | DeepArchitect + RootCauseDebugger | Verifier | opus |
| N4 | DeepArchitect + ArtifactCurator | Critic | opus |
| N5 | RootCauseDebugger + DeepArchitect | Verifier | opus |
| N6 | DeepArchitect | Verifier | opus |
| N7 | Verifier + Critic | DeepArchitect (二审) | opus |

architect (pane 3) 二审强制（Non-Negotiables §5）：APO 是策略层，需 opus 判断力。

## 10. 时间预算（gate 解锁后）

- N0 gate check：~10 min（live 状态查 + accepted check）
- N1 logical algebra：~60 min（15 operator schema-driven）
- N2 rewrite rules：~40 min（8 条 + hard 标记）
- N3 cost model：~50 min（10 项 + 3 mode profile + 数据源映射）
- N4 plan memo + explain CLI：~40 min
- N5 adaptive replan：~40 min（6 trigger + 3 stop rule）
- N6 3 modes：~30 min
- N7 eval gate + rollout：~30 min
- 整 sprint（gate 解锁后）目标 3-4 个 dispatch round 内 passed

**当前**：gate BLOCKED → 实际启动时间 = `predecessor 2 sprint finalized` 之后。

## 11. 完成定义（DoD 7 条 + Planner Done Definition + Acceptance Gates）

1. **已完成**：design.md / plan.md / planning.html 3 件（task_graph.json **已就位且 validate ok，不重写**）
2. **已完成**：planning.html 注册
3. **已完成**：本 sprint planner spec 三件套写好；task_graph N0 hard gate 已 enforce 不绕过
4. **未验证**（依赖未解锁）：N0..N7 builder 节点未执行；6 件 spec 草案产物（algebra schema / rewrite rules / cost model spec / explain schema 等）未产；evaluator 未跑 §6 验证 A..R
5. **未验证 / Blocked**：dependency gate BLOCKED — 待 2 张 predecessor sprint finalized 后 coordinator 自动派 N0
6. **风险**：
   - 跳过 N0 gate 提前实施（plan §7 stop rule + N0 hard depends_on）
   - cost model 夹带 LLM ranking（plan §8 stop rule）
   - enforcer 标 best-effort（C11；plan §8 stop rule + 5 hard rule 显示）
   - 无限 replan（C12；3 stop rule 任一触发停）
   - mutate in-flight sprint artifact（C9；plan §6 + §8 stop rule + git diff 校验）
   - Explain prose-only（C13；schema 机读硬要求）
7. **后续待办**：
   - **等** predecessor 2 sprint finalized
   - coordinator 自动派 N0 → N1 → ... → N7（gate 解锁后）
   - evaluator 跑 plan §6 验证 A..R 全 PASS
   - architect (pane 3) 二审 APO 与 GEPA 边界 + 与 truthification scoring 一致性
   - Follow-up sprint：实施 `lib/agent_plan_optimizer/` 模块（optimizer.py / algebra.py / rewriter.py / cost_model.py / explain.py / replan.py 等）+ 真改 CLI `solar-harness optimize ...`
