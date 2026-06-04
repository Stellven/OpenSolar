# Plan — GEPA Stage 1 Implementation 执行计划

sprint_id: `sprint-20260522-gepa-optimize-anything-implementation`
generated_at: `2026-05-22T13:05:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: design sprint (final report) + PRD + Contract + task_graph.json (12 nodes, 7 layers, validated)

## 1. 现状（不需要重做 task_graph）

`.task_graph.json` 已由 PM/Coordinator 创建并通过 `graph-scheduler validate`：

- 12 节点：I0..I8 + IT + IM + IH
- 7 layers
- 0 errors / 0 warnings
- I0 = passed（dry-run install + namespace 校验，2026-05-22T16:51:32Z）
- I1 = reviewing（`__init__.py` 21 exports + lazy-load + 零副作用）
- ready 节点：[I4, I5, I6, I7]（I2/I3 也属于 L2 但当前 ready 列表只显示 4 个；scheduler 自动调度）

本 plan **不重写 task_graph**；仅补充 design.md / plan.md / planning.html。

## 2. 交付切片顺序（基于已有 task_graph）

| Wave | 节点 | 状态 | 依赖 | 备注 |
|------|------|------|------|------|
| W0 | I0 dry-run gate | ✅ passed | 无 | 已完成 |
| W1 | I1 package init | 🔄 reviewing | I0 | 21 exports，lazy-load |
| W2 | I2 adapter, I3 cli, I4 evaluator, I5 store, I6 router, I7 budgets | ⏳ pending (4 ready) | I1 | 6 模块全并行 |
| W3 | I8 promote/rollback | ⏳ pending | I5 | 仅 I5 即可启动 |
| W4 | IT pytest suite | ⏳ pending | I2..I8 | 全 module 完成后 |
| W5 | IM MVP smoke | ⏳ pending | IT | 真跑 propose→review→promote→rollback / target=/tmp/gepa_seed.txt |
| W6 | IH final report | ⏳ pending | IM | 产 monitor-reports/gepa-optimize-anything-implementation.md |

## 3. 文件级写入范围（已在 task_graph 钉死）

| 节点 | 写入文件 | 动作 |
|------|---------|------|
| I0 | `<sid>.I0-handoff.md` | NEW ✅ |
| I1 | `integrations/gepa_optimizer/__init__.py` + `<sid>.I1-handoff.md` | NEW (reviewing) |
| I2 | `integrations/gepa_optimizer/adapter.py` + `<sid>.I2-handoff.md` | NEW |
| I3 | `integrations/gepa_optimizer/cli.py` + `<sid>.I3-handoff.md` | NEW |
| I4 | `integrations/gepa_optimizer/evaluator.py` + `<sid>.I4-handoff.md` | NEW |
| I5 | `integrations/gepa_optimizer/artifact_store.py` + `<sid>.I5-handoff.md` | NEW |
| I6 | `integrations/gepa_optimizer/operator_router.py` + `<sid>.I6-handoff.md` | NEW |
| I7 | `integrations/gepa_optimizer/budgets.py` + `<sid>.I7-handoff.md` | NEW |
| I8 | `integrations/gepa_optimizer/promote.py` + `<sid>.I8-handoff.md` | NEW |
| IT | `tests/integrations/gepa_optimizer/**` + `<sid>.IT-handoff.md` | NEW |
| IM | `optimizer-runs/<run_id>/**` + `/tmp/gepa_seed.txt` + `<sid>.IM-handoff.md` | NEW（真跑产出） |
| IH | `<sid>.IH-handoff.md` + `<sid>.traceability.json` + `monitor-reports/gepa-optimize-anything-implementation.md` | NEW |

**严格禁止 write_scope 外**：
- 任何 Solar production hook / skill / prompt / config / operator registry / `solar-harness.sh` shell wrapper
- 任何 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 任何非 `/tmp/gepa_seed.txt` 的 promote target
- 任何 ThunderOMLX / 不相关 sprint 路径

## 4. 并发边界

- W2 6 模块（I2..I7）write_scope 互不重叠（每个写自己的 .py） → 全并行
- I8 仅依赖 I5 → 可在 I5 完成后立即启动，与 I2/I3/I4/I6/I7 并行
- 同 pane 内禁止并发；max-parallel 建议 3（pane lease 限制）

## 5. 每节点 handoff 段落契约

每个 I*-handoff 必须含：

1. **变更文件**：路径 + 行数变更
2. **Done 定义达成**：逐条 acceptance 对照（带验证命令输出）
3. **验证方法**：可复现命令片段
4. **Compat / 安全**：明示守住的 hard rule
5. **Open Questions**：传给 IH 的疑点

IH 节点必须额外含：

- PRD Acceptance 6 条逐项对照
- DAG all-passed 证据
- "current problem" + "next action"
- 下一 sprint outline（shell wrapper 接入 + 第二批 use case）

## 6. 验证命令

```bash
SID=sprint-20260522-gepa-optimize-anything-implementation
H=/Users/lisihao/.solar/harness

# A. DAG schema 校验（已 ok）
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json
# 实测 {"ok": true, "node_count": 12, "errors": [], "warnings": []}

# B. layers / ready / batches
~/.solar/bin/solar-harness graph-scheduler layers --graph $H/sprints/$SID.task_graph.json
~/.solar/bin/solar-harness graph-scheduler ready  --graph $H/sprints/$SID.task_graph.json

# C. 包结构完整性（I1..I8 完成后）
for f in __init__ adapter cli evaluator artifact_store operator_router budgets promote; do
  test -f $H/integrations/gepa_optimizer/$f.py || echo "MISSING $f.py"
done

# D. py_compile（PRD Acceptance）
python3 -m py_compile $H/integrations/gepa_optimizer/*.py && echo "py_compile PASS"

# E. import 无 side effect
python3 -c "
import sys; sys.path.insert(0, '$H')
import integrations.gepa_optimizer as pkg
loaded = [k for k in sys.modules if 'gepa_optimizer.' in k]
assert not loaded, f'side effects: {loaded}'
print(f'no side effect; __all__ has {len(pkg.__all__)} exports')
"

# F. CLI 安全门（I3 完成后）
python3 -m integrations.gepa_optimizer.cli run --target /tmp/gepa_seed.txt --execute 2>&1 | grep -E "(budget|usage)"
# 期望命中 "budget" / "usage" 等错误提示（缺三 budget caps）

# G. promote 拒 prod path（I8 完成后）
python3 -m integrations.gepa_optimizer.cli promote \
  --run dummy --candidate c-001 \
  --target $H/skills/some-skill.md \
  --backup-dir /tmp 2>&1 | grep -E "(PromotionTargetRejected|reject|not allowed)"

# H. pytest（IT 完成后）— PRD Acceptance
cd $H && python3 -m pytest tests/integrations/gepa_optimizer/ -q
# 期望 0 failures，全 CPU，无 cloud 调用

# I. MVP smoke（IM 完成后）
ls $H/optimizer-runs/  | head -3
ls $H/optimizer-runs/<latest_run_id>/ | grep -E "summary\.json|pareto\.jsonl|candidate-"

# J. 未触碰禁区
! git -C $H diff --name-only HEAD | grep -E "^hooks/|^skills/|^prompts/|^config/(physical-operators\.json|coordinator)|^solar-harness\.sh"

# K. 无 secret 落盘
! grep -rE "(api[_-]?key|bearer|password|token)\s*[:=]\s*['\"][A-Za-z0-9]{8,}" \
  $H/integrations/gepa_optimizer/ $H/sprints/$SID.*.md $H/optimizer-runs/ 2>/dev/null

# L. 最终报告
test -f $H/monitor-reports/gepa-optimize-anything-implementation.md
grep -E "current problem|next action" $H/monitor-reports/gepa-optimize-anything-implementation.md

# M. DoD: all DAG nodes passed
python3 -c "
import json
g=json.load(open('$H/sprints/$SID.task_graph.json'))
ap=all(n.get('status')=='passed' for n in g['nodes'])
print(f'all_passed={ap}')
for n in g['nodes']:
    print(f\"  {n['id']}: {n.get('status','?')}\")
"
```

## 7. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止全局 `pip install gepa`（仅 dry-run 已在 I0 完成，本 sprint 不再 install）
- 禁止 `python -m integrations.gepa_optimizer.cli run --execute` 配真 cloud API（mocked evaluator + mocked proposer only）
- 禁止任何 `solar-harness optimizer gepa ...` shell wrapper 接入（下一 sprint）
- 禁止 promote target 非 `/tmp/gepa_seed.txt`
- 禁止改 hooks / skills / prompts / config / operator registry / `solar-harness.sh` / `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 禁止把 secret 落盘到 candidate JSON / audit.log / handoff
- pytest 必须 CPU only：`python3 -m pytest tests/integrations/gepa_optimizer/`
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 8. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做被 FAIL 节点
- I1 含 side effect（import 时加载子模块）→ 立即 FAIL（I1 acceptance 已 enforce）
- I3 CLI `run --execute` 缺任一 budget cap 时未 exit ≠ 0 → 立即 FAIL
- I5 secret 写入未 reject / 未 redact → 立即 FAIL
- I8 prod path（非 `/tmp/gepa_seed.txt`）未 reject → 立即 FAIL
- IT 任一 case 失败 / 任一 case 调真 cloud → 立即 FAIL
- IM 演练 promote target ≠ `/tmp/gepa_seed.txt` → 立即 FAIL
- IM rollback 字节不一致 → 立即 FAIL
- IH 缺最终报告 / PRD Acceptance 6 条对照 / current problem / next action / 下一 sprint outline 任一 → FAIL
- 任何节点改禁区文件 → FAIL + ATLAS
- 任何 handoff 含 secret 字面值 → FAIL + 立即删除
- 任何文档/代码用乐观词 → FAIL
- 任何 cloud LLM 真调用（除 mocked tests）→ FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 9. 模型路由建议

per PRD non-goal `Do not route bulk optimization to expensive Claude`：

- I1..I8 全部 builder：`mini-claude-sonnet-builder`（task_graph 已 preferred_operator 钉死）
- IT pytest：`mini-claude-sonnet-builder`
- IM smoke：`mini-claude-sonnet-builder`
- IH final eval：`mini-claude-opus-evaluator`（task_graph 已钉）

## 10. 时间预算

- I1 reviewing → 完成 ~5 min（已大部分写完）
- I2..I7 并行：~45 min（每模块 ~30-40 min，并行后压缩）
- I8：~25 min
- IT：~35 min
- IM smoke：~10 min
- IH：~25 min
- 整 sprint 目标 3-4 个 dispatch round 内 passed

## 11. 完成定义（DoD 7 条 + PRD Acceptance）

1. **已完成**：design.md / plan.md / planning.html 3 件（task_graph.json 已就位）
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`（实测 ok: 12/7/0/0）
3. **已完成**：planning.html 注册
4. **未验证**：I2..I8 + IT + IM + IH builder 节点未执行；I1 仍 reviewing
5. **未验证**：8 模块 .py 文件 + pytest suite + MVP smoke + 最终报告 全部待 builder
6. **风险**：promote allowlist 失守 / secret 落盘 / cloud LLM 误调用 / shell wrapper 越界接入 — 全部已加 plan §7+§8 stop rule
7. **后续待办**：coordinator 按 task_graph 派发 W1→W6 → 8 模块齐 → pytest PASS → MVP smoke → IH 产 monitor-reports/ → sprint passed → PM 决定下一 sprint（shell wrapper + 第二批 use case + cloud LLM 真跑）
