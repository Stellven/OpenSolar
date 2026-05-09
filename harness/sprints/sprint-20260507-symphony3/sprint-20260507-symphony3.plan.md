# Sprint Plan — sprint-20260507-symphony3

Source: product-brief.md v1 (2026-05-07T19:30:00Z)
Author: planner (claude-opus)
Created: 2026-05-07 (planning_complete)
Predecessor PASS: sprint-20260507-symphony2 (2026-05-07T19:18:53Z)

## 0. Plan 总览

7 天工期 / Day 1-7 / 9 个交付切片 (S1-S9) / 双 Gate (Day 3 + Day 5) / 15 deliverables.
建设者主路: **sonnet** (SOLAR_NO_ZHIPU=1 已持久化), fallback: deepseek-v3 (HTML 切边界).
评估: deepseek-r1 红队. Gate 主持: planner.

**核心矛盾排序**:
1. P0 必修: 协调器路由 bug + 7 处 sid 缺失 (Sprint 2 暴露的 functional defect)
2. P1 必交: events.jsonl schema 化 + HTTP /status JSON (可观测性骨架)
3. P2 nice-to-have: HTML 仪表盘 + Sprint 2 backlog 3 项 (可压缩)

**优先级冲突仲裁** (planner 决策):
- Day 1-3: 先做 events.jsonl + HTTP 骨架 (新增, 范围明确, 风险低)
- Day 4-5: 攻路由 bug (调试型, 不确定性高, 但收益最大)
- Day 6-7: 收尾 + 回归 + 文档

理由: 调试型任务放后面, 给前面 3 天积累的 events.jsonl 当调试武器 (路由 bug 修复时可用 events 复盘).

## 1. 交付切片顺序 (S1-S9, Day-aligned)

### S1 — Events Schema v1 + emit_event() 库 (Day 1, 4h)
**目标**: 建立机器可读事件单源.
**文件**:
- 新增 `~/.solar/harness/schemas/event.schema.json` (~30 行 JSON Schema draft-07)
- 新增 `~/.solar/harness/lib/events.sh` (~80 行, emit_event/append_event/query_events)
**Schema 字段**: `ts (ISO8601) | sprint_id (string|null) | actor | event | severity (info|warn|error) | payload (object)`
**API 签名**: `emit_event "<actor>" "<event>" "<severity>" "<sid>" '<json_payload>'`
**双写**: append 到 `~/.solar/harness/events/all.jsonl` + `~/.solar/harness/sprints/<sid>.events.jsonl`
**单测**: `test-events-emit.sh` (5 用例: 正常 / 空 sid / 非法 severity / 非法 JSON payload / 并发 100 写入)
**验证**: `jq -c . events/all.jsonl | wc -l` = N (无截断), `jq -e 'has("ts") and has("actor")' events/all.jsonl` 全 true.

### S2 — coordinator.sh emit_event 迁移 (Day 1 下午, 3h)
**目标**: 高频事件源接入新事件流, 旧 log() 保留 (人读).
**文件**: `coordinator.sh` (修改, 触点 ~10 处)
**最少接入事件**: `state_change | dispatch_sent | dispatch_failed | gate_check_pass | gate_check_fail | handle_passed | handle_failed_review | finalized | pane_assigned | pane_released`
**关键定位**:
- line 911 附近 inline emit_event() 提取到 lib/events.sh, coordinator 改 source
- handle_passed / handle_failed_review (line ~470 附近) 加事件埋点
- save_state / dispatch_to_pane 状态变化埋点
**验证**: 起 dry-run sprint 走完一轮 (`SESSION_NAME=mock-sym3 DISPATCH_MOCK=1`), `events/all.jsonl` 至少含 8 种 event 类型.

### S3 — workspace + runner emit_event 迁移 (Day 2 上午, 3h)
**目标**: Sprint 2 hook 生命周期 events 接入.
**文件**:
- `lib/symphony/workspace-manager.sh` (修改): create/cleanup/snapshot 埋点
- `lib/symphony/runner.sh` (修改): start/exit/timeout 埋点
- `lib/symphony/hooks.sh` (修改): hook_executed / hook_failed 埋点
**关键事件**: `workspace_created | workspace_cleanup | hook_executed | hook_failed | runner_started | runner_exited`
**验证**: `tools/symphony-runner-smoke.sh` 跑完, events 含 4+ workspace/runner 事件.

### S4 — HTTP status-server 骨架 (Day 2 下午, 4h)
**目标**: HTTP 8765 server 启动可用, /status JSON + /healthz.
**文件**:
- 新增 `~/.solar/harness/lib/symphony/status-server.py` (~250 行, Python 3.10+ stdlib http.server)
- 修改 `solar-harness` (主脚本): 镜像 line 1813 webhook 子命令模式, 添加 `status-server start|stop|restart|status`
- 新增 `~/.solar/harness/run/status-server.pid` 路径 (启动 nohup)
**端点**:
- `GET /status` → JSON {current_sprint, panes, recent_events: 50, kpi}
- `GET /healthz` → "ok"
- `GET /events?sprint_id=X&limit=N` (S5 完成)
- `GET /` → HTML (S5)
**绑定**: 127.0.0.1:8765 (硬绑, 不绑 0.0.0.0); 端口冲突 → fallback 8765-8775 范围.
**验证**: `curl http://127.0.0.1:8765/healthz` → "ok"; `curl http://127.0.0.1:8765/status | jq .current_sprint` 返回 sprint id 或 null.

### S5 — HTTP / HTML 仪表盘 + /events 端点 (Day 3, 5h)
**目标**: 可视面板, 5s 自动刷新.
**文件**: `lib/symphony/status-server.py` (扩展 HTML 段)
**HTML 设计** (无 JS 框架, 纯 fetch):
- 顶部: current_sprint card (sid / phase / round / handoff_to)
- 中间: 4 pane 状态 (planner/builder/evaluator/observer) + busy 标志
- 底部: recent events (50 条, color-coded by severity)
- 自动刷新: `setInterval(fetch('/status'), 5000)`
- 无 d3.js / chart.js / 任何外部 CDN
**`GET /events?sprint_id=X&limit=N`**: 流式 jq 过滤 `<sid>.events.jsonl`
**派工**: HTML/CSS 段可委派 deepseek-v3 (创想家, 前端切边界)
**Gate A 触发** (Day 3 末).
**验证**: 浏览器打开 http://127.0.0.1:8765, 5s 后自动刷新; `curl /events?sprint_id=mock-sym3&limit=10` 返回 10 条 JSON.

### S6 — 协调器路由 bug 修复 (Day 4 上午, 4h)
**目标**: choose_evaluator_pane 必须返回 evaluator pane (0.3), 不是 planner (0.0).
**根因候选** (按概率):
1. `discover_pane_by_persona` (line ~178) BFS 遍历过早 return planner (因 planner pane 0.0 总是先扫到, content scan match 不严格)
2. `tmux capture-pane` regex `Persona:[[:space:]]*evaluator` 没命中 (banner 格式被改)
3. `PANE_EVALUATOR_DEFAULT` 默认值被 unset 或覆盖
**修复策略**:
- 加诊断日志: discover_pane_by_persona 打印每个 pane 的扫描结果 (matched/skipped + reason)
- regex 严格化: `^Persona:[[:space:]]*evaluator(\b|$)` (避免 "evaluator-pending" 误判)
- env override 优先: `${PANE_EVALUATOR:-$(discover...)}`, 给手动覆盖出口
**文件**: `coordinator.sh` (修改 line ~178 附近 discover_pane_by_persona)
**验证**: events.jsonl 中 dispatch_sent 事件的 payload.target_pane 必须 = "0.3" 当 actor=evaluator.

### S7 — test-coordinator-routing.sh + test-dispatch-sid-required.sh (Day 4 下午, 4h)
**目标**: bug 修复带回归保护.
**文件**:
- 新增 `test-coordinator-routing.sh` (4 用例): mock 4 pane (planner/builder/evaluator/observer), choose_evaluator_pane / choose_builder_pane / choose_planner_pane 必须返回正确 pane
- 新增 `test-dispatch-sid-required.sh` (5 用例): 空 sid → return 1 / 占位 sid "dispatch" → return 1 / 正常 sid → return 0 / sid 含特殊字符 → 转义 / 并发 sid → 无串扰
**dispatch_with_gate() 封装** (Day 4 下午):
- 新函数 `dispatch_with_gate(pane, instruction_file, sid)`, sid 必填 (`[[ -z "$sid" ]] && { log_error; return 1; }`)
- 替换 7 处 gate_check 失败回调缺 sid 的调用点 (前文已 grep 定位)
- 增加 `set -u` 局部检查
**验证**: `grep -n "dispatch_to_pane" coordinator.sh | grep -v "^#"` 所有调用都带显式 sid 参数.

### S8 — Sprint 2 backlog 3 项清理 (Day 5 上午, 3h)
**目标**: 不假装看不见.
**子项**:
a) **env_allow 空值回归测试**: `test-symphony-hooks.sh` 加 1 用例 — env_allow 含空字符串变量, hook 内变量不应被 set (验证 hooks.sh:58-61 env_allow loop)
b) **perl alarm fallback SIGKILL grace**: `hooks.sh:run_hook` (line 73-80 附近) 在 SIGTERM 后 sleep 5, 若进程仍存活则 SIGKILL (与 gtimeout 行为一致), 加测试用例
c) **ADR 安全语义补全**: `docs/symphony-integration-adr.md` §runner.sh --unsafe-run-codex 段 (≥ 100 字): 什么场景用 / 谁能批准 / log 落到哪
**Gate B 触发** (Day 5 末).

### S9 — 端到端 smoke + 回归 + 文档 (Day 6-7, 6h)
**目标**: 收官 + 审判官 eval-ready.
**Day 6 任务**:
- E2E smoke: 临时 dry-run sprint (sprint-test-sprint3-smoke), 全程触发 state_change → dispatch_sent → gate_check_pass → 4 hook → finalized; events.jsonl 含全部预期 event 类型; HTTP /status 返回正确 current_sprint
- Sprint 1 回归 (14 个原测试) + Sprint 2 回归 (8 hook + 2 D6 测试) = 24 测试全 PASS
- 修补 Gate B 漏项
**Day 7 任务**:
- ADR §Observability Design (≥ 200 字) + §Coordinator Routing Bug 复盘 (≥ 150 字)
- README status-server 章节 (启动命令 + curl 例子)
- templates/WORKFLOW.solar.md events 示例
- 提交审判官 deepseek-r1 eval

## 2. 文件级写入范围 (File-level Write Scope)

**新增 (7 文件)**:
| 文件 | 大小估计 | 切片 |
|------|---------|------|
| `schemas/event.schema.json` | ~30 行 | S1 |
| `lib/events.sh` | ~80 行 | S1 |
| `lib/symphony/status-server.py` | ~250 行 | S4-S5 |
| `test-events-emit.sh` | ~80 行 | S1 |
| `test-coordinator-routing.sh` | ~120 行 | S7 |
| `test-dispatch-sid-required.sh` | ~100 行 | S7 |
| `test-status-server.sh` | ~60 行 | S4 |

**修改 (9 文件)**:
| 文件 | 改动范围 | 切片 |
|------|---------|------|
| `coordinator.sh` | line ~178 (路由) / ~470 (handle_passed) / ~737 (sid 默认值) / ~911 (inline emit) / 7 处 sid 修复 | S2/S6/S7 |
| `lib/symphony/workspace-manager.sh` | create/cleanup/snapshot 埋点 | S3 |
| `lib/symphony/runner.sh` | start/exit/timeout 埋点 | S3 |
| `lib/symphony/hooks.sh` | line 73-80 SIGKILL grace + hook_executed/failed 埋点 | S3/S8 |
| `solar-harness` | line ~1813 镜像 webhook 子命令 → status-server start/stop/restart/status | S4 |
| `test-symphony-hooks.sh` | 加 env_allow 空值用例 | S8 |
| `docs/symphony-integration-adr.md` | §Observability Design + §Routing Bug + §unsafe-run-codex | S8/S9 |
| `templates/WORKFLOW.solar.md` | events 示例段 | S9 |
| `README.md` | status-server 启动章节 | S9 |

## 3. 验证命令 (Verification Commands)

每个切片完成后必须能本地复现:

```bash
# S1: events schema + emit_event
bash ~/.solar/harness/test-events-emit.sh
jq -c . ~/.solar/harness/events/all.jsonl | head -5
jq -e 'has("ts") and has("actor") and has("event")' ~/.solar/harness/events/all.jsonl

# S2: coordinator emit_event 迁移
SESSION_NAME=mock-sym3 DISPATCH_MOCK=1 bash ~/.solar/harness/coordinator.sh --once
jq -r '.event' ~/.solar/harness/events/all.jsonl | sort -u | wc -l   # >= 8

# S3: workspace + runner 迁移
bash ~/.solar/harness/tools/symphony-runner-smoke.sh
jq -r '.event' ~/.solar/harness/events/all.jsonl | grep -E "workspace_|hook_|runner_" | wc -l   # >= 4

# S4: HTTP /status + /healthz
~/.solar/harness/solar-harness status-server start
curl -sf http://127.0.0.1:8765/healthz   # 必须返回 "ok"
curl -s http://127.0.0.1:8765/status | jq .current_sprint
curl -s http://127.0.0.1:8765/status | jq -e '.panes | length >= 4'

# S5: HTML + /events
curl -s http://127.0.0.1:8765/ | grep -q "<html>"
curl -s "http://127.0.0.1:8765/events?sprint_id=mock-sym3&limit=10" | jq length   # = 10

# S6: 路由 bug 修复
bash ~/.solar/harness/test-coordinator-routing.sh   # 4/4 PASS
# 真实 dry-run: events.jsonl 中 evaluator dispatch 的 target_pane = "0.3"
jq -r 'select(.event=="dispatch_sent" and .payload.actor=="evaluator") | .payload.target_pane' \
  ~/.solar/harness/events/all.jsonl | sort -u   # 必须只有 "0.3"

# S7: dispatch sid 必填
bash ~/.solar/harness/test-dispatch-sid-required.sh   # 5/5 PASS
grep -nE "dispatch_(to_pane|with_gate)" ~/.solar/harness/coordinator.sh | grep -v '^[[:space:]]*#'   # 全部带 sid

# S8: Sprint 2 backlog
bash ~/.solar/harness/test-symphony-hooks.sh   # 含 env_allow 空值用例 PASS
grep -A 10 "## §runner.sh --unsafe-run-codex" ~/.solar/harness/docs/symphony-integration-adr.md | wc -w   # >= 100

# S9: E2E + 回归
bash ~/.solar/harness/test-symphony-sprint1.sh   # 14/14 PASS
bash ~/.solar/harness/test-symphony-hooks.sh   # 8/8 PASS
bash ~/.solar/harness/test-symphony-sprint2-d6.sh   # 2/2 PASS
# E2E smoke
SPRINT_ID=sprint-test-sprint3-smoke ~/.solar/harness/tools/dry-run-sprint.sh
jq -r '.event' ~/.solar/harness/sprints/sprint-test-sprint3-smoke.events.jsonl | sort -u | wc -l   # >= 10
```

## 4. No-Live-Pane-Mutation Protection

**铁律**: 测试 / 调试 / 烟测 **绝不动 live solar-harness session**.

**必走 fork 模式**:
```bash
# 所有测试必须导出
export SESSION_NAME=mock-sym3
export DISPATCH_MOCK=1
export SPRINT_ID="sprint-test-sprint3-$(date +%s)"
export PANE_PLANNER=mock-sym3:0.0
export PANE_BUILDER=mock-sym3:0.1
export PANE_EVALUATOR=mock-sym3:0.3
export PANE_OBSERVER=mock-sym3:0.2
```

**强制检查** (在每个 test-*.sh 头部):
```bash
[[ "$SESSION_NAME" == "solar-harness" ]] && { echo "REFUSE: cannot test on live session"; exit 1; }
[[ -z "$DISPATCH_MOCK" ]] && { echo "REFUSE: DISPATCH_MOCK=1 not set"; exit 1; }
```

**Mock pane 创建**:
```bash
tmux new-session -d -s mock-sym3 -x 200 -y 50
tmux split-window -t mock-sym3:0 -h
tmux split-window -t mock-sym3:0 -h
tmux split-window -t mock-sym3:0 -h
# 注入 persona banner 到每个 pane
for i in 0 1 2 3; do
  persona=("planner" "builder" "observer" "evaluator")[$i]
  tmux send-keys -t mock-sym3:0.$i "echo 'Persona: ${persona[$i]}'" Enter
done
```

**HTTP server 隔离**:
- 测试 status-server 用临时端口 (8800-8899 范围), 避开 8765 live
- 测试结束 trap EXIT 调 stop, 不留遗骸

**events.jsonl 隔离**:
- 测试用 `~/.solar/harness/events/test-<sid>.jsonl`, 不污染 all.jsonl
- 测试结束清理 `rm -f events/test-*.jsonl`

## 5. Rollback / Stop Rules

### 全局 Stop Rules (来自 product-brief)
- 核心 acceptance 完成度 < 50% → 暂停并重评
- 引入新依赖 (Express/FastAPI/Flask/web 框架) → 触发简化审查并 STOP
- 测试覆盖率 < 60% → 不放行
- 工期 > 8 天 → 重新估算并拆 Sprint
- HTTP server 8765 端口被占用 → 改用 8765-8775 动态分配
- Sprint 1 14/14 或 Sprint 2 hooks/D6 测试出现回归 → 立即 STOP
- 协调器路由 bug 根因无法复现 → 暂停并请求 master_brain 介入

### Per-Slice Rollback
| 切片 | Rollback 策略 |
|------|--------------|
| S1-S2 | events.sh + coordinator.sh diff revert; old log() 仍工作; 不影响主循环 |
| S3 | workspace/runner/hooks 改动单文件 revert; Sprint 2 hooks 测试验证无回归 |
| S4-S5 | status-server.py 整文件删除; solar-harness status-server 子命令删除; 不影响 coordinator |
| S6 | coordinator.sh discover_pane_by_persona 段 git diff revert; 路由回到旧行为 (虽错但已 PASS) |
| S7 | test-*.sh 删除 (新增文件); coordinator.sh dispatch_with_gate 段 revert |
| S8 | hooks.sh / test-symphony-hooks.sh / ADR 单段 revert |
| S9 | 文档/README 段 revert; smoke 测试结果不入库 |

### Gate Failure Consequences
- **Gate A 未过** (Day 3): Day 4 重新评估范围, 协调器路由 bug 修复优先级提升至 Gate A 必过 (S6 前移)
- **Gate B 未过** (Day 5): Day 6-7 收缩到只修必过项 (路由 bug + sid + smoke), 文档/ADR 后移到下个 Sprint

## 6. Master Brain 升级触发条件

任一触发立即 STOP, 写 `.solar/inbox/escalate-sprint3-<reason>.md` 上报:

1. 路由 bug 根因 Day 4 末仍未定位
2. events.jsonl 并发写入出现数据损坏 (jq parse fail)
3. HTTP server 启动后 5 分钟内 OOM / 端口反复被占
4. Sprint 1 / Sprint 2 任意测试在迁移过程中 regress
5. 新依赖 (web 框架) 偷偷被引入 (CI grep 检测)
6. 工期超过 Day 7 仍未到 Gate B
7. 建设者主路 sonnet 出现 1210 / 上下文截断 → fallback deepseek-v3
8. tmux session 状态被破坏 (live solar-harness 误受影响)
9. 协调器主循环 hang (events.jsonl 写入阻塞主循环) → 立即 revert S2

## 7. 实施者提示 (建设者必读)

- **events.sh 必须线程安全**: `flock` 包裹 append, 防止并发 emit_event 撕裂行
- **status-server.py stdlib only**: `from http.server import BaseHTTPRequestHandler, HTTPServer` + `import json` + `import urllib.parse` — 严禁 import flask/fastapi/aiohttp
- **路由 bug 修复前必先复现**: 用 mock 4 pane 起 dry-run, capture 出 evaluator pane 的真实 banner 字串, 对比 regex
- **dispatch_with_gate 替换 7 处 sid 缺失**: 前文 grep 已定位, builder 必须找出全部 7 处 (用 `grep -nE "gate_check.*\$\(dispatch_to_pane" coordinator.sh`)

## 8. Definition of Done (Gate B 后总验收)

| 项 | 验收标准 |
|---|---------|
| Events schema | jq schema validate 100% PASS |
| emit_event 迁移 | events/all.jsonl 含 ≥ 10 种 event 类型 |
| HTTP /status | curl JSON 合法, 含 current_sprint/panes/recent_events/kpi |
| HTTP /healthz | curl 返回 "ok" |
| HTML 仪表盘 | 浏览器打开 5s 自动刷新工作 |
| 路由 bug 修复 | test-coordinator-routing.sh 4/4 PASS, evaluator dispatch target_pane=0.3 |
| sid 缺失修复 | test-dispatch-sid-required.sh 5/5 PASS |
| Sprint 2 backlog | 3 项 ≥ 2 完成 (Gate B), 全部完成 (Day 7) |
| Sprint 1+2 回归 | 14 + 10 = 24 测试 0 regress |
| ADR 文档 | §Observability ≥ 200 字 + §Routing Bug ≥ 150 字 |
| README | status-server 启动章节有 curl 例子 |
| 审判官 eval | deepseek-r1 verdict=PASS, low-severity backlog ≤ 2 项 |

---

**Plan 完成时间**: 2026-05-07T19:45:00Z (estimate, 实际由协调器记录)
**Status 转换**: drafting → active, phase: spec → planning_complete
**下一步**: 协调器自动派发到 builder pane (sonnet) 启动 S1 实施
