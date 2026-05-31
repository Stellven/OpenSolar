# Design — multi-task history window labels and safe archive

sprint_id: `sprint-20260521-multitask-history-window-label`
priority: `P1`
lane: `operations/runtime`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-23T10:40:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `PRD + Contract created 2026-05-20T20:44Z` · `task_graph (validated, 2 nodes, 2 layers)` · `N1-audit.md done` · `N1-handoff.md done` · `N2-handoff.md done`
note: 本 sprint 是 wake 重启后的合规补齐；builder 已大部分完成（N1+N2 reviewing）；planner 补 design.md + plan.md 让 workflow guard 通过。

## 0. 本切片的边界（强制 read-first）

- **小型 P1 ops 整理**：仅改 `lib/multi_task_runner.py` 的 status 渲染逻辑 + 新建一个 monitor-report 安全 reap 指南。
- **允许 Write/Edit**：
  - `/Users/lisihao/.solar/harness/lib/multi_task_runner.py`（N2 已实施）
  - `/Users/lisihao/.solar/harness/monitor-reports/safe-reap-guide.md`（N2 已新建）
  - sprint 自身 artifact：`sprints/<sid>.{design,plan,N1-audit,N1-handoff,N2-handoff,task_graph,planning_html}.md/json/html`
- **严格禁止**（per PRD non-goals + contract constraints）：
  - 杀任何 active / running / reviewing 状态的 task 窗口
  - 删除 `run/multi-task/` 下的 task 目录
  - 改 ThunderOMLX 设置 / model routing
  - 改 scheduler auto-exit 逻辑（属上一 sprint）
  - 隐藏 historical task evidence
  - 修改 `~/.solar/STATE.md`、epic.*、其他 sprint artifact
- 知识库降级 `mirage:nonzero`：本 sprint 完全 self-contained。

## 1. 问题陈述（per PRD §Problem）

stale Python scheduler runner 已修复后，`solar-harness multi-task status --no-clear` 仍把 terminal task 窗口标为 `completed/live`。`live` 是 tmux 窗口存在状态，但运维读它误为 active work；这与"stale runner 清理已完成"事实不符。

Live evidence（PRD 已记录）：

- `ps` 无 `multi_task_runner.py start` 进程
- `multi-task stale-schedulers` 无 stale 报告
- `multi-task status` 仍把多个 historical window 列为 `completed/live`

## 2. 上游摘要（N1 audit → N2 implementation 已就位）

`.N1-audit.md` 已识别 3 个 render path：

| Path | Entry Point | Lines | 触发 |
|------|-------------|-------|------|
| Plain | `render_plain()` | 1481–1582 | `--renderer plain` or env override |
| Screen | `render_screen_status_lines()` | 1592–1764 | 交互 `screen_loop()` 内部调用 |
| TVS | `render_tvs()` → `solar-harness.sh tvs render` | 1912–1925 | 默认；fail → Plain fallback |

`render_result()` (L1928) 是单点 dispatch。

`.N2-handoff.md` 已实施：

1. 新增 `_display_tmux_status(task_status, tmux_status)` helper（在 `TERMINAL_TASK_STATUSES` 常量后）
2. 3 个 render path（plain / screen / TVS）的 tmux 列调用 `_display_tmux_status`
3. 修正 window name 公式
4. 更新 pane title 模板
5. 新增 `rename_window()` bash helper
6. 新建 `monitor-reports/safe-reap-guide.md` 安全归档指南

## 3. 状态标签语义（钉死，per contract §Required Work 2）

| task status | tmux 状态 | 渲染显示 | 含义 |
|-------------|-----------|---------|------|
| `running` / `dispatched` / `reviewing` | live | `ACTIVE` (or `running/live`) | 真活跃工作（**保持不变**） |
| `completed` / `failed` / `failed_missing_handoff` / `cancelled` | live | `idle` | terminal task + tmux 窗口仍开（历史可见） |
| `completed` / `failed` 等 | no window | `archived` 或留空 | terminal task + 窗口已关闭 |

**核心：terminal task + live window 必须不再显示为 `live` 字面，改为 `idle`（per N2 实测）**，便于运维一眼区分 history 与 active。

## 4. 渲染路径修改点（per N2 实施）

```python
TERMINAL_TASK_STATUSES = {"completed", "failed", "failed_missing_handoff", "cancelled"}

def _display_tmux_status(task_status: str, tmux_status: str) -> str:
    if task_status in TERMINAL_TASK_STATUSES and tmux_status == "live":
        return "idle"
    return tmux_status
```

三处调用：

- `render_plain()` tmux 列：`_display_tmux_status(str(t.get("status", "")), str(t.get("tmux_status", "N/A")))`
- `render_screen_status_lines()` 同等位置
- TVS shell-side `tvs render` 通过 `solar-harness.sh` 接同样的 helper（N2 已对齐）

## 5. 安全 reap 路径（per contract §Required Work 4）

per PRD non-goals `Do not delete task directories`：reap 仅关闭老 terminal tmux 窗口，不删 task 目录。

`monitor-reports/safe-reap-guide.md` 必须含：

- **safe dry-run**: `solar-harness multi-task reap --dry-run --ttl-minutes 60`（仅列将关闭的窗口，不实操）
- **explicit task ids**: `--task-ids t-001,t-002`
- **TTL**: `--ttl-minutes N`（默认 60，可调）
- **rollback**: 没有；reap 只关窗口，不删 task 目录；如需重启窗口，直接 `tmux new-window -n <task>` 重建
- **禁止**: 不允许 `reap --force-all` 或 `reap` 无任何过滤条件

## 6. 验证（per contract §Verification）

```bash
H=/Users/lisihao/.solar/harness

# 1. py_compile
python3 -m py_compile $H/lib/multi_task_runner.py

# 2. status before/after（N2 handoff 已含 before/after 截屏）
~/.solar/bin/solar-harness multi-task status --no-clear

# 3. stale-schedulers 保持 clean
~/.solar/bin/solar-harness multi-task stale-schedulers

# 4. 如已实施 reap，dry-run 先跑
~/.solar/bin/solar-harness multi-task reap --dry-run
```

## 7. 状态恢复 / 失败回退

- 若修改导致 `multi-task status` 渲染异常 → 立即 `git -C ~/.solar/harness checkout lib/multi_task_runner.py`
- 若 reap 误关 active window → 不会发生（dry-run + TTL + explicit ids 三重保护）；万一发生 → `tmux new-window -n <task>` 重建
- 若 `safe-reap-guide.md` 文案误导 → 删除文件 + handoff 标注

## 8. 兼容性

- 渲染输出**字段不变**（仍是 `tmux_status` 列），仅值从 `live → idle` 翻译
- TVS / Plain / Screen 三路径一致（helper 共用）
- `multi-task status --json`（如存在）保持原 `tmux_status` 值不变（**[需 N2 builder 确认是否 JSON 也翻译，或仅人读展示翻译]**）
- scheduler auto-exit 逻辑 PRD non-goal 明示不改

## 9. 非目标（明确禁止）

- 不杀 active / running / reviewing task 窗口
- 不删 `run/multi-task/` 下任何 task 目录
- 不改 ThunderOMLX 设置 / model routing / KVTC 任何模块
- 不改 scheduler auto-exit 逻辑
- 不隐藏 historical task evidence（idle 仍可见，不是隐藏）
- 不修改 `~/.solar/STATE.md` / epic.* / 其他 sprint artifact
- 不打开 live tmux pane 做无关动作 / 不重启 harness
- 不使用乐观词

## 10. 给 evaluator 的接力

evaluator 需要校验：

1. `multi_task_runner.py` 已含 `_display_tmux_status` helper
2. 3 render path 全部调用 helper
3. `py_compile lib/multi_task_runner.py` 通过
4. `multi-task status --no-clear` 输出中 terminal task 行 tmux 列显示 `idle`（不再 `live`）
5. active task 行仍显示 `live`（活跃语义保持）
6. `multi-task stale-schedulers` 输出 clean
7. `monitor-reports/safe-reap-guide.md` 存在，含 dry-run / TTL / 禁止 force-all
