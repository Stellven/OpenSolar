# Plan — GEPA optimize_anything Integration 执行计划

sprint_id: `sprint-20260522-gepa-optimize-anything-integration`
generated_at: `2026-05-22T11:20:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `PM PRD + Contract + existing task_graph.json (validated, 5 nodes, 4 layers)` · `N1 reviewing (partial handoff ~10 KB)`

## 1. 现状（不需要重做 task_graph）

`.task_graph.json` 已由 PM/Coordinator 创建并通过 `graph-scheduler validate`：

- 5 节点：N1 (source audit) → {N2 architecture, N3 safety} → N4 backlog → N5 final report
- 4 layers
- 0 errors / 0 warnings
- 每节点含 `architecture_policy.package_boundary = integrations/gepa_optimizer/` + `core_patch_allowed: false`（设计阶段，禁止改主代码）
- N1 当前 `status="reviewing"`，N1-handoff.md 部分填写（~10 KB）

本 plan **不**重写 task_graph；仅补充 design.md / plan.md / planning.html 让 planner 角色完整闭合。

## 2. 交付切片顺序（基于已有 task_graph）

| Wave | 节点 | 状态 | 依赖 | 备注 |
|------|------|------|------|------|
| W1 | N1 source audit | 🔄 reviewing | 无 | 已部分完成；builder 继续 |
| W2 | N2 architecture, N3 safety | ⏳ pending | N1 | 可并行 |
| W3 | N4 implementation backlog | ⏳ pending | N2, N3 | join |
| W4 | N5 final report + next sprint outline | ⏳ pending | N4 | 写 monitor-reports/ |

合计 5 节点，4 layer。

## 3. 文件级写入范围（已在 task_graph 钉死）

| 节点 | 写入文件 | 动作 |
|------|---------|------|
| N1 | `sprint-…N1-handoff.md` | NEW（已部分填） |
| N2 | `sprint-…N2-handoff.md` | NEW |
| N3 | `sprint-…N3-handoff.md` | NEW |
| N4 | `sprint-…N4-handoff.md` | NEW |
| N5 | `sprint-…N5-handoff.md` + `~/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md` | NEW |

**严格禁止 write_scope 外路径**，包括：

- `integrations/gepa_optimizer/`（设计阶段不预建；属下一 sprint）
- 任何 Solar production hook / skill / prompt / config / operator registry
- `~/.solar/STATE.md`、其他 sprint artifact、epic.*
- 任何 ThunderOMLX 路径（不相关 epic）

## 4. 并发边界

- N2 + N3 可并行（write_scope 互不重叠：分别写 N2-handoff.md / N3-handoff.md）
- 其他节点单线性
- max-parallel 建议 2

## 5. 每节点 handoff 段落契约

每个 N1..N5 handoff 必须含以下段落：

1. **已完成**：本节点交付的具体内容（含表格 / 代码块 / 流程图）
2. **Source / Inputs**：引用源 URL（N1）或上游 handoff（N2..N5）
3. **Verified vs Assumed**：明示哪些是源文档事实，哪些是 Solar 设计假设
4. **Solar Mapping**（N2/N3/N4）：与 design.md §4 / §5 / §7 一致
5. **Open Questions**：待 N5 / 下一 sprint 解决的疑点
6. **Stop-Rule Compliance**：明示未触碰 production / 未安装 GEPA / 未跑优化循环

N5 必须额外含：

- PRD Acceptance Criteria 6 条逐项对照
- DAG 所有节点 passed 证据
- "current problem" + "next action" 显式段落
- 下一实施 sprint 的 DAG outline（节点清单 + write_scope + 测试矩阵）

## 6. 验证命令

```bash
SID=sprint-20260522-gepa-optimize-anything-integration

# A. DAG schema 校验（已 ok）
~/.solar/bin/solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/$SID.task_graph.json
# 已实测 {"ok": true, "node_count": 5, "errors": [], "warnings": []}

# B. layers / ready / batches
~/.solar/bin/solar-harness graph-scheduler layers --graph ~/.solar/harness/sprints/$SID.task_graph.json
# 已实测 [["N1"], ["N2", "N3"], ["N4"], ["N5"]]

# C. 所有 N* handoff 段落自检
for f in ~/.solar/harness/sprints/$SID.N{1,2,3,4,5}-handoff.md; do
  test -f "$f" || { echo "MISSING $f"; continue; }
  for sec in "## 已完成" "Source" "Verified" "Open Questions" "Stop-Rule"; do
    grep -q "$sec" "$f" || echo "WARN missing '$sec' in $f"
  done
done

# D. 安全审计（禁止 GEPA 安装 / 真跑）
! grep -rE "pip install gepa($|\W)|pip3 install gepa($|\W)|gepa\.optimize_anything\(" \
  ~/.solar/harness/sprints/$SID.*.md ~/.solar/harness/monitor-reports/gepa-*.md 2>/dev/null \
  | grep -v "^.*--dry-run\|^.*\(假设\|TODO\|do not actually\|# 禁止"
# 期望无命中（除非显式标 dry-run / TODO / 禁止）

# E. 未触碰禁区
! git -C /Users/lisihao/.solar/harness diff --name-only HEAD 2>/dev/null | grep -E "integrations/gepa_optimizer/|hooks/|skills/|prompts/"
# 期望无命中

# F. monitor-reports 落盘
test -f ~/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md
grep -E "current problem|next action" ~/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md

# G. DoD: all DAG nodes passed
python3 -c "
import json
g=json.load(open('$HOME/.solar/harness/sprints/$SID.task_graph.json'))
for n in g['nodes']:
    print(f\"{n['id']}: {n.get('status','?')}\")
all_passed = all(n.get('status')=='passed' for n in g['nodes'])
print(f'all_passed={all_passed}')
"

# H. monitor bridge latest（per PRD acceptance）
ls -t ~/.solar/harness/monitor-reports/gepa-*.md 2>/dev/null | head -3
```

## 7. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt`
- 禁止 `pip install gepa` / `pip3 install gepa` / `uv pip install gepa` / `conda install gepa`
- 禁止 `python -c "import gepa; gepa.optimize_anything(...)"` 或任何真实 GEPA 调用
- 禁止 `curl https://gepa-ai.github.io/` 抓 N1 之外的页面（N1 用 WebFetch 拿官方 blog；其他禁止）
- 禁止把 OAuth token / API key / 私有 prompt 写入任何 handoff / monitor-report
- 禁止改 `~/.solar/STATE.md`、其他 sprint artifact、epic.*、Solar production code
- 禁止本 sprint 内创建 `integrations/gepa_optimizer/` 目录（属下一 sprint）
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 8. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做被 FAIL 节点
- N1 audit 不区分 verified vs assumed → 立即 FAIL
- N2 不含架构图 / CLI 草案 / operator routing / 与 autoresearch/Meta-Harness 共存说明 → FAIL
- N3 缺 auto-apply 禁止 / budget caps / artifact schema / 失败回滚任一 → FAIL
- N4 缺精确文件清单 / 测试命令 / package install check / 首批 use case → FAIL
- N5 缺最终报告 / PRD Acceptance 6 条对照 / current problem / next action / 下一实施 sprint outline → FAIL
- 任何节点真跑 GEPA / pip install gepa / 触碰 production → FAIL + ATLAS
- 任何文档使用乐观词「已修复 / 稳定 / 完美 / 无需担忧」 → FAIL
- 任何 handoff 含 secret 字面值 → FAIL + 立即删除
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 9. 模型路由建议（per PRD non-goal: 避免昂贵 Claude）

- N1 source audit（需要 web fetch + 大文本解析）：`sonnet`（中等）
- N2 architecture（图 + 表 + 文字）：`sonnet`
- N3 safety design（详细矩阵）：`sonnet`
- N4 implementation backlog（精确文件清单）：`sonnet`
- N5 final report + next sprint outline（综合）：`sonnet` 或 `opus`（如评估需要更强综合）

不路由 Opus 到批量步骤（per PRD non-goal `Do not route bulk optimization to expensive Claude`）。

## 10. 时间预算

- N1 audit：~30 min（已部分完成，剩 ~10 min 补齐）
- N2 architecture：~30 min
- N3 safety：~25 min
- N4 backlog：~25 min
- N5 final report：~30 min
- 总目标 2-3 个 dispatch round 内 passed

## 11. 完成定义（DoD 7 条 + PRD Acceptance Criteria）

1. **已完成**：design.md / plan.md / planning.html 3 件（task_graph.json 已就位）
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`（实测 ok: 5/4/0/0）
3. **已完成**：planning.html 注册（D5 待执行）
4. **未验证**：N2..N5 builder 节点未执行；N1 仅 reviewing
5. **未验证**：monitor-reports/gepa-optimize-anything-integration.md 未产
6. **风险**：GEPA package 实际可用性 N1 尚未验证；本 sprint 不安装不实测，把不确定性传给 N4/N5；mirage 持续 degraded（N1 用 WebFetch 兜底）
7. **后续待办**：
   - N1 builder 完成审计（含 verified vs assumed）
   - N2/N3 并行
   - N4 给出精确文件清单 + 测试矩阵
   - N5 产 monitor-reports/ 最终报告 + 下一 sprint outline
   - evaluator 跑 §6 验证命令 A..H 全 PASS → sprint passed
   - **不主动开下一 sprint**；由 PM/coordinator 决定何时根据 N5 outline 创建实施 sprint
