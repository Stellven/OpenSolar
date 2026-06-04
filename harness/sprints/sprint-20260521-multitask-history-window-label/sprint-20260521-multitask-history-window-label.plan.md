# Plan — multi-task history window labels 执行计划

sprint_id: `sprint-20260521-multitask-history-window-label`
generated_at: `2026-05-23T10:40:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `task_graph.json validated (2 nodes, 2 layers)` · N1 + N2 builder 已 reviewing（实施已落地）
purpose: 本 plan 是 wake workflow-guard 触发的合规补齐。Builder 已完成 N1 audit + N2 实施；planner 补 design.md + plan.md 让 sprint 合规进入 evaluator。

## 1. 现状

- `.task_graph.json` 已通过 validate（2 节点，2 layer，0 errors / 0 warnings）
- N1（audit）状态 = `reviewing`；`.N1-audit.md` 已产出（识别 3 render path）
- N2（implementation）状态 = `reviewing`；`.N2-handoff.md` 已产出（含 `_display_tmux_status` helper + 3 处渲染修改 + monitor-reports/safe-reap-guide.md）
- ready = []（两节点都 reviewing，不 pending）
- wake reason: `violations=["builder_route_without_prd_design_plan_task_graph"]` → 本 sprint 仅缺 design.md / plan.md

## 2. 本 plan 不重写 task_graph

`.task_graph.json` 已 chained linear（N1 → N2），保持原样：

| Node | 状态 | Gate | 备注 |
|------|------|------|------|
| N1 | reviewing | "audit identifies exact status fields to rename" (已 passed) | audit 完成 |
| N2 | reviewing | "status output separates active live work from historical open windows" | 实施完成，待 evaluator |

## 3. 文件级写入范围（per task_graph）

| Node | 写入文件 | 状态 |
|------|---------|------|
| N1 | `sprints/<sid>.N1-audit.md` | ✅ done |
| N2 | `lib/multi_task_runner.py` + `sprints/<sid>.N2-handoff.md` + `monitor-reports/safe-reap-guide.md` | ✅ done |
| Planner（本轮） | `sprints/<sid>.{design,plan,planning_html}.md/html` | 本轮产出 |

**严格禁止 write_scope 外**（per PRD non-goals + contract constraints）：
- 任何其他 Solar 源文件（hooks / skills / config / `solar-harness.sh` / scheduler 逻辑）
- 任何 `run/multi-task/<task_id>/` 目录删除
- 任何 ThunderOMLX 路径
- `~/.solar/STATE.md` / epic.* / 其他 sprint artifact

## 4. 并发边界

- N1 + N2 linear（N2 deps N1）
- 仅 1 个 task pane 用于本 sprint（builder 已完成）
- 本 plan 不再派发；交给 evaluator

## 5. 验证命令（evaluator 必跑）

```bash
H=/Users/lisihao/.solar/harness
SID=sprint-20260521-multitask-history-window-label

# A. DAG validate
~/.solar/bin/solar-harness graph-scheduler validate --graph $H/sprints/$SID.task_graph.json
# 实测 {"ok": true, "node_count": 2, "errors": [], "warnings": []}

# B. py_compile（per contract Verification）
python3 -m py_compile $H/lib/multi_task_runner.py

# C. _display_tmux_status helper 存在
grep -nE "def _display_tmux_status\(" $H/lib/multi_task_runner.py
# 期望 1 命中

# D. TERMINAL_TASK_STATUSES 常量含 4 个 state
grep -A3 "TERMINAL_TASK_STATUSES" $H/lib/multi_task_runner.py | head -6
# 期望 含 completed / failed / failed_missing_handoff / cancelled

# E. 3 render path 都调用 helper
grep -nE "_display_tmux_status\(" $H/lib/multi_task_runner.py
# 期望 ≥3 命中（plain + screen + 一个共用点）

# F. multi-task status 输出（前后对照在 N2-handoff.md 截屏）
~/.solar/bin/solar-harness multi-task status --no-clear 2>&1 | head -30
# 期望 terminal task 行 tmux 列显示 "idle"，active 行显示 "live"

# G. stale-schedulers clean
~/.solar/bin/solar-harness multi-task stale-schedulers 2>&1
# 期望 无 stale PID 报告

# H. safe-reap-guide.md 存在并含 dry-run / TTL / 禁 force-all
test -f $H/monitor-reports/safe-reap-guide.md
grep -E "dry-run|--ttl-minutes|force-all|禁止" $H/monitor-reports/safe-reap-guide.md | head -5

# I. 未触碰禁区
! git -C $H diff --name-only HEAD | grep -vE "^lib/multi_task_runner\.py$|^monitor-reports/safe-reap-guide\.md$|^sprints/$SID\."
# 期望 无命中（diff 仅含 multi_task_runner.py + safe-reap-guide.md + sprint artifact）

# J. 没有删除任何 run/multi-task/ 目录
test -d $H/run/multi-task/
ls $H/run/multi-task/ | wc -l
# 期望 仍有完整 task 目录

# K. JSON 输出兼容（如果有 --json flag）
~/.solar/bin/solar-harness multi-task status --json --no-clear 2>&1 | head -3 || echo "no --json flag"
# 检查 JSON 模式下 tmux_status 是否保持原值（如适用）
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` 杀任何 active / running / reviewing 窗口
- 禁止 `solar-harness restart` / `solar-harness inject-prompt` / `solar-harness models switch`
- 禁止删除 `run/multi-task/<task_id>/` 目录
- 禁止改 scheduler auto-exit 逻辑
- 禁止改 ThunderOMLX 路径 / KVTC 任何模块 / model routing
- 禁止改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact / Solar production hook / skill / prompt
- 禁止 reap 不带 dry-run / 不带 TTL / 不带 explicit ids
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Stop Rules

- `graph-scheduler validate` 不 PASS → 禁止提交（已 PASS：2/2/0/0）
- N1 / N2 任一 evaluator FAIL → sprint FAIL
- N2 修改的 `multi_task_runner.py` 让 `py_compile` 失败 → FAIL
- `multi-task status --no-clear` 输出仍把 terminal task 行 tmux 列显示 `live` → FAIL
- active task 行不再显示 `live` 或同等活跃语义 → FAIL（违反 PRD goals §4）
- `stale-schedulers` 输出有 stale 报告 → FAIL（违反 PRD acceptance §5）
- 任何 `run/multi-task/` 目录被删除 → FAIL + ATLAS
- 任何 active / running / reviewing task 窗口被杀 → FAIL + ATLAS
- 任何禁区文件被改 → FAIL + ATLAS
- 任何文档/代码用乐观词 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 8. 模型路由

per task_graph 已钉死：N1 / N2 = `sonnet`。

## 9. 时间预算

- builder N1 + N2 已完成
- planner 本轮（补 design.md / plan.md / planning.html）：~15 min
- evaluator 跑 §5 验证 A..K：~10 min
- 整 sprint 目标本 dispatch round 内 passed

## 10. 完成定义（DoD 7 条 + PRD Acceptance）

1. **已完成**：design.md / plan.md / planning.html 3 件（task_graph.json 已就位）
2. **已完成**：task_graph.json validate ok（2 节点 2 layer 0 errors / 0 warnings）
3. **已完成**：planning.html 注册
4. **已验证**：N1 audit / N2 实施已落地（reviewing）；待 evaluator 抽检
5. **未验证**：evaluator 未跑 §5 验证命令 A..K；多 task status before/after 实测对照未由 evaluator 复跑
6. **风险**：
   - 若 JSON 输出（`--json` 模式）也被翻译 `live → idle` 而消费者期望原值 → 需 N2 builder 确认
   - 若 reap 命令尚未实施（仅 guide 文档）→ acceptance "safe archive/reap path" 仅文档化（PRD goals §3 接受）
   - mirage degraded 持续；本 sprint self-contained，不受影响
7. **后续待办**：
   - evaluator 跑 §5 验证 A..K 全 PASS → N1 + N2 标 passed → sprint passed
   - 不主动开下一 sprint；若 reap 需要代码实施而非仅文档，由 PM 决定新 sprint
