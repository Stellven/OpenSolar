# Design — Understand-Anything Background Knowledge Graph

sprint_id: `sprint-20260527-understand-anything-background-knowledge-graph`
epic_id: null (standalone runtime execution; 与 epic-20260526-...understand-anything 5 sub-sprints 平行)
role: planner
status: planning_complete
generated_at: 2026-05-28T08:42:00Z
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)
detail_reference: `<sid>.prd.md` (17K, 12 ACs + 4-node DAG + 架构交接 + 8 OQs + 12 risks)

## 0. 切片性质

**Runtime execution sprint**, 不是 spec sprint。直接在 `/Users/lisihao/Solar` 跑 understand-anything 全仓分析, 后台非阻塞。`task_graph.json` 已有 4-node DAG (U1-U4 solar.task_graph.v1 schema, 18K bytes detail), Planner 不重做 task_graph, 只补 sprint-level artifacts。

## 1. 4-Node DAG (locked, per existing task_graph.json)

```
U1 preflight_runtime (sonnet)
    └─→ U2 run_understand_zh_background (sonnet, 长跑 10-60 min, 真后台)
          └─→ U3 verify_graph_artifacts (sonnet)
                └─→ U4 handoff_resume_contract (opus)
```

**为何严格串行**: U1 preflight 是 gate, 任一失败立即停; U2 长跑产物是 U3 验证对象; U3 验证结果是 U4 handoff 数据源。

**为何后台非阻塞**: understand-anything 对 mono-repo `/Users/lisihao/Solar` 可能跑 10-60 分钟; 前台阻塞会卡 chain-watcher + 4-pane 调度池。U2 必须用 `nohup` / `tmux new-window -d` / `subprocess.Popen(start_new_session=True)` 启动, 再加 `caffeinate -i` 防止 Mac mini idle sleep。

## 2. 文件级写范围

| 节点 | write_scope (per task_graph.json) |
|------|-------------------------------------|
| U1 | `<sid>.U1_preflight_runtime-handoff.md` |
| U2 | `/Users/lisihao/Solar/.understand-anything/**` (understand-anything 自己的产物目录) |
| U3 | `<sid>.U3_verify_graph_artifacts-handoff.md` |
| U4 | `<sid>.handoff.md` |
| Planner (本切片) | `<sid>.contract.md` + `<sid>.design.md` + `<sid>.plan.md` + `<sid>.planning.html` + `<sid>.task_graph.json` patch + `<sid>.status.json` |

**严格禁止**: 改 `~/.solar/harness/{lib,tools,schemas,templates,bin}/` / `~/.claude/plugins/` / `~/.claude/settings*.json` / Solar 仓库源代码 (`/Users/lisihao/Solar/**` 除 `.understand-anything/`)。

## 3. Preflight 4 项检查 (U1, per PRD FR-1)

| 检查 | 通过条件 | 失败动作 |
|------|----------|----------|
| Claude CLI 登录态 | `claude --json status` 返回 `loggedIn=true` | 立即停止 + 写预检 handoff 标 reason |
| understand-anything 插件缓存 | `~/.claude/plugins/cache/understand-anything` 可读 | 立即停止 + 提示重新 `/plugin install understand-anything` |
| Node + pnpm 可用 | `node --version` + `pnpm --version` 都成功 | 立即停止 + 提示安装 |
| 目标仓库可写 + .understand-anything 状态 | `/Users/lisihao/Solar` 可写 + 报 `.understand-anything/` 状态 (fresh / partial / complete) | 立即停止或继续增量恢复 |

可选附加: `du -sh /Users/lisihao/Solar` + `find ... -type f | wc -l` (回答 OQ-01 仓库规模)。

## 4. Background Launcher 选型 (U2 关键, per PRD FR-2)

3 选型 (per PRD §架构交接 推荐):

1. **`tmux new-window -d -- caffeinate -i bash -c 'cd ~/Solar && claude /understand --language zh > .understand-anything/run.log 2>&1'`**: 最常用, 可观察 pane 状态, 配合 `caffeinate` 防休眠
2. **`nohup caffeinate -i bash -c '...' > .understand-anything/run.log 2>&1 &`**: 最轻量, 但断 tty 后无 pane 可查
3. **`subprocess.Popen(['caffeinate', '-i', 'claude', '/understand', '--language', 'zh'], cwd='/Users/lisihao/Solar', start_new_session=True, stdout=open(...), stderr=...)`**: 程序化, 适合从 builder Python 启动

**推荐 alt1 (tmux new-window)** + `caffeinate -i` + log 重定向 + writeover.understand-anything/run.log。**Kill criteria**: 若 alt1 因 Claude CLI 需要 TTY 失败 (OQ-04) → 切 alt3。

## 5. 增量恢复语义 (U2, per PRD FR-2)

检测顺序:
1. `.understand-anything/state.json` 存在 → 调用 `/understand --resume` (若支持, per OQ-02) 或 `/understand --language zh` (自动 detect)
2. `.understand-anything/intermediate/*` 存在 → 保留, 不删
3. 全无 → fresh run

**永不 `--rebuild`** (PRD 明示)。

## 6. Verification (U3, per PRD FR-3)

| 验证 | 命令 |
|------|------|
| `knowledge-graph.json` 存在 + JSON parse | `python3 -c "import json; json.load(open('/Users/lisihao/Solar/.understand-anything/knowledge-graph.json'))"` 不抛异常 |
| `meta.json` 存在 + commit/hash 字段 | `python3 -c "import json; d=json.load(open('...meta.json')); assert 'commit' in d and 'hash' in d"` |
| 失败时停在何阶段 | 看 `.understand-anything/state.json` 或 `intermediate/*` 最新文件; 阶段集合: `preflight / collect / extract / synth / write` |

## 7. Handoff & Resume Contract (U4, per PRD FR-4)

`<sid>.handoff.md` 必须含 3 节:
1. **本次完成度**: 哪些 stage done / which not (per U3 verify)
2. **下次恢复入口**: 命令行 (e.g. `cd ~/Solar && claude /understand --language zh`) + `.understand-anything/state.json` 引用 (若可解析)
3. **非阻塞策略**: operator-runtime lease 注册建议 (per sprint-20260523-lease-based-model-fleet-runtime); long-running actor 接入路径

## 8. Stop Rules (继承 PRD)

- 缺 task_graph 不得派 builder
- U1 任一检查失败 → 立即停, 不进 U2
- U2 不允许前台 blocking (必须 `nohup` / `tmux new-window -d`)
- 不允许 `--rebuild` (增量恢复优先)
- 不动 `~/.solar/harness/` / `~/.claude/plugins/` / `~/.claude/settings*.json` / Solar 源代码
- 不打印 secrets (redact)
- 不重启 harness
- 不用乐观词
- 长跑期间 Mac mini 不允许 idle sleep (`caffeinate -i` 必须)

## 9. 失败恢复

- U1 失败: 立即停, 写预检 handoff 说明; 不进 U2 (避免 60 分钟白跑)
- U2 失败 (启动失败 / 超时 / 插件版本不匹配): 切 alt3 launcher (subprocess) 或 ATLAS structured repair
- U2 卡 plan mode / proceed prompt: 依赖 TUI Pane Recover sprint S03 实施完成 (现有 5-pane spillover 临时支撑)
- U3 失败 (JSON parse 失败): 标产物 corrupt, 写 verify handoff, 不重启 U2 (人工介入)
- U4 失败: 单节点重派

## 10. 与同期 sprint 关系

- **epic-20260526-...understand-anything S01-S05**: 平行 spec/architecture/implementation sprints; 本 sprint 是 runtime execution, 与之解耦
- **sprint-20260523-lease-based-model-fleet-runtime**: U2 应当独立 actor lease, 本 sprint U4 handoff 给 operator-runtime sprint 留接入入口
- **sprint-20260527-p0-...-tui-pane-recover**: 处理 `pane_not_idle` 反复失败 (events seq 6/13/17/20); 本 sprint 不修该根因, 等 TUI epic 实施

## 11. 非目标

- 不写 understand-anything 插件源 (只调用)
- 不验证 7 个 `/understand-*` 命令 (留 epic-20260526 S04)
- 不调 Claude settings.json
- 不重启 harness / coordinator / chain-watcher
- 不动 `~/.claude/plugins/` 源
- 不做知识图二次处理 (embedding / clustering / 入 Solar DB) — 留 ingestion sprint
- 不删 `.understand-anything/` 已有产物
- 不要求实时进度回报 (watchdog 心跳 + 最终验证)
- 不在本切片内主动 register operator lease (留 U4 handoff 给后续 sprint)

## 12. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB; ATLAS / Autoresearch (advisor) / MarkItDown / Meta-Harness (injectable, 不使用) / Solar-Harness Runtime / Superpowers / agency-agents / gstack / solar-graph-scheduler / solar-intent-engine / solar-knowledge-ingest capabilities injected (per runtime context); 全部 `injectable_only`, 不要求执行。
