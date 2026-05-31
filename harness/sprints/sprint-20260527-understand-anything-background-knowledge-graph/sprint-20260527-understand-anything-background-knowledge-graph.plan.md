# Plan — Understand-Anything Background Knowledge Graph

gate: `G_UAKG_RUNTIME_PASSED` (single sprint, 4 nodes U1-U4)
knowledge_context: solar-harness context inject used
upstream: none (standalone)
downstream: ingestion sprint (knowledge graph 入 Solar DB/Obsidian/QMD); operator-runtime sprint (lease registration)

## 0. 切片定位

Runtime execution sprint, 直接在 `/Users/lisihao/Solar` 跑 understand-anything 全仓分析。**后台非阻塞** (`nohup` / `tmux new-window -d` + `caffeinate -i`)。4-node DAG 已锁 (per task_graph.json solar.task_graph.v1)。本 plan 是 sprint-level summary。

## 1. 交付切片顺序 (严格串行)

```
U1_preflight_runtime (sonnet, ≤2 min)
    └─→ U2_run_understand_zh_background (sonnet, 后台 10-60 min, 真 background)
          └─→ U3_verify_graph_artifacts (sonnet, ≤2 min)
                └─→ U4_handoff_resume_contract (opus, ≤2 min)
```

## 2. 每节点验收

| 节点 | 关键验收 (per PRD ACs + task_graph) |
|------|---------------------------------------|
| **U1** preflight | Claude loggedIn=true + plugin cache 可读 + node+pnpm 可用 + `/Users/lisihao/Solar` 可写 + `.understand-anything/` 状态报告 + 预检 handoff; 任一失败立即停 |
| **U2** background run | **真后台启动** (nohup / tmux new-window -d / subprocess.Popen + caffeinate -i); 不阻塞 chain-watcher; `.understand-anything/config.json` 至少写出; 成功则 `knowledge-graph.json` 生成; 增量恢复优先 (不 --rebuild); 不要前台手工 `/understand`; write_scope 严限 `.understand-anything/` |
| **U3** verify | `knowledge-graph.json` 可 `python3 -c "import json; json.load(open(...))"` 解析; `meta.json` 含 commit + hash; 失败时停在何阶段 (preflight/collect/extract/synth/write); verify handoff 写出 |
| **U4** handoff | 完成度 + 恢复入口 (命令行 + state.json 引用) + 非阻塞策略 (operator-runtime lease 注册建议); 3 节 |

## 3. 文件级写范围

| 操作 | 路径 |
|------|------|
| U1 写 | `<sid>.U1_preflight_runtime-handoff.md` (单文件) |
| U2 写 | `/Users/lisihao/Solar/.understand-anything/**` (understand-anything plugin 自己写, builder 不直接 cat 内部文件) |
| U3 写 | `<sid>.U3_verify_graph_artifacts-handoff.md` |
| U4 写 | `<sid>.handoff.md` |
| Planner (本切片) | `<sid>.{contract,design,plan,planning.html,status.json}` + `<sid>.task_graph.json` patch + ACK |
| **绝对禁止** | `~/.solar/harness/{lib,tools,schemas,templates,bin}/` / `~/.claude/plugins/` / `~/.claude/settings*.json` / Solar 仓库源代码 (除 `.understand-anything/`) |

## 4. 并发边界

- **严格串行**: U1 → U2 → U3 → U4
- **U2 后台并发**: U2 启动后立即返回 (后台 PID 落 .understand-anything/run.pid 或 tmux window id), coordinator 派下一 node 时 U3 通过 watchdog 检测 U2 进程是否结束才开始验证
- **不允许跨 sprint 并发**: 本 sprint 不阻塞前台 chain-watcher

## 5. 验证命令

### U1 自验

```bash
claude --json status | jq '.loggedIn'  # 应为 true
ls -la ~/.claude/plugins/cache/understand-anything  # 应可读
node --version && pnpm --version  # 都成功
[ -w /Users/lisihao/Solar ] && echo writable
ls -la /Users/lisihao/Solar/.understand-anything 2>&1  # fresh/partial/complete
```

### U2 启动模板

```bash
# Recommended: tmux new-window -d + caffeinate -i
tmux new-window -d -t solar-bg -n understand-zh -- \
  caffeinate -i bash -c '
    cd /Users/lisihao/Solar && \
    claude /understand --language zh \
    > .understand-anything/run-$(date +%Y%m%dT%H%M%S).log 2>&1
  '
echo "U2 dispatched in background; check tmux: tmux list-windows -t solar-bg"
```

### U3 验证

```bash
GRAPH=/Users/lisihao/Solar/.understand-anything/knowledge-graph.json
META=/Users/lisihao/Solar/.understand-anything/meta.json
[ -f $GRAPH ] && python3 -c "import json; json.load(open('$GRAPH'))" && echo GRAPH_OK
[ -f $META ] && python3 -c "import json; d=json.load(open('$META')); assert 'commit' in d and 'hash' in d" && echo META_OK
```

### U4 handoff template

参考 design §7: 3 节 (完成度 / 恢复入口 / 非阻塞策略)。

## 6. no-live-pane-mutation 保护

- **绝不** `tmux send-keys` 到 live 4-pane (planner/builder/evaluator/architect)
- **绝不** `tmux kill-pane` (任何 pane)
- **绝不** `tmux respawn-pane`
- **绝不** `solar-harness restart` / 杀 coordinator / 杀 chain-watcher
- U2 用 **新** tmux window (`tmux new-window -d -t solar-bg`), 不污染现有 pane
- 不重启 launchd jobs
- 不动 `~/.claude/plugins/` / `~/.claude/settings*.json` 源

## 7. Rollback / Stop Rules

### Rollback

- U1 失败 → 写预检 handoff 说明 + sprint FAIL (不进 U2 避免 60 分钟白跑)
- U2 启动失败 (alt1 tmux 因 TTY 不可用) → 切 alt3 subprocess.Popen + 写 evidence
- U2 长跑失败 (插件 crash / Mac sleep / lease 冲突) → 不 kill, 写 verify handoff 标失败阶段, 留增量恢复入口
- U3 verify 失败 (产物 corrupt) → 标 artifact corrupt, 不重启 U2 (人工介入)
- U4 失败 → 单节点重派

### Stop Rules

- 缺 task_graph 不派 builder
- U1 任一检查失败立即停
- U2 必须真后台 (前台 blocking → 立即 FAIL)
- 增量恢复优先 (`--rebuild` → 立即 FAIL)
- 不打印 secrets
- 不重启 harness / coordinator / chain-watcher
- 不动 `~/.solar/harness/` 源 / `~/.claude/plugins/` / Solar 仓库源
- 不杀主 pane
- 不要求前台手工 `/understand`
- 不用乐观词

## 8. SLO

| 指标 | hard | soft |
|------|------|------|
| U1 完成时间 | > 5 min → WARN | > 2 min → INFO |
| U2 后台真启动 | 前台 blocking 检测到 > 0 → 立即 FAIL | n/a |
| U2 长跑总时长 | > 90 min → WARN (但不 kill) | > 60 min → INFO |
| U3 JSON parse | 失败 → FAIL | n/a |
| U4 handoff 3 节齐 | 缺 → FAIL | n/a |
| chain-watcher 在 U2 期间是否能派其他 sprint | 卡 > 0 → 立即 FAIL | n/a |
| 任一节点改动 `~/.solar/harness/` 或 Solar 仓库源 | > 0 → 立即 FAIL | n/a |
| 任一节点打印 secrets | > 0 → 立即 FAIL | n/a |

## 9. 失败恢复路径

- U1 fail → ATLAS structured repair (针对哪项 4 检查失败)
- U2 启动 fail → 切 alt3 + ATLAS
- U2 长跑中 Mac sleep → `caffeinate -i` 已 enforced; 若仍 sleep 是 macOS bug, 留 evidence + 等系统 power
- U2 长跑 plugin crash → 写 verify handoff 标 crash stage, 不重启
- U3 JSON parse fail → artifact corrupt, 人工介入
- U4 fail → 单节点重派

## 10. 给后续接力

- **U4 handoff** → 后续 ingestion sprint 消费 `knowledge-graph.json` 入 Solar DB / Obsidian / QMD
- **U4 handoff** → 后续 operator-runtime sprint (sprint-20260523-lease-based-model-fleet-runtime) 注册 long-running actor lease
- **U4 handoff** → epic-20260526-...understand-anything S04 orchestration-ui 验证 7 `/understand-*` 命令

## 11. Knowledge Context

`solar-harness context inject` 已跑; mirage degraded → QMD + Obsidian + Solar DB。PRD 17K + task_graph 4-node 已 self-contained。

`caffeinate -i` 防 Mac mini idle sleep 是关键 (Constraint).
