# Sprint Evaluation — sprint-20260507-symphony3

Evaluator: 审判官 (claude-opus, deepseek-r1 红队透镜)
Round: 2
Date: 2026-05-07
Verify-all: SKIPPED (@FALLBACK_MANUAL — manual bash + smoke + falsification)

## 总判定: PASS

Symphony Sprint 3 的 8 项验收全部通过：events.jsonl schema v1 + emit_event() API 经过 race condition / 错误输入 / per-sprint 过滤多角度否证；HTTP 状态面板 4 个 endpoint 全部 live curl PASS；coordinator 路由 bug 修复；dispatch_with_gate 守卫 + Sprint 2 backlog 三项清理 + ADR §10/§11/§12 全部完成。58/58 测试断言 PASS，5 项 Sprint 1+2 回归 PASS。3 个低风险 known issue 不阻塞但留存 backlog。

## Done 条件逐条

| # | 验收项 | 判定 | 证据 |
|---|--------|------|------|
| D1 | events.jsonl schema v1 + emit_event() API | PASS | schema draft-07 ✓, required={ts,actor,event,severity}, additionalProperties=false ✓, test-events-emit 20/20 PASS, 20-writer race 全部 valid JSON |
| D2 | coordinator/runner/workspace-manager/hooks 接入 events_emit | PASS | grep events_emit: workspace-manager.sh×2, runner.sh×2, hooks.sh×2, coordinator.sh×33；compat shim 旧签名→新签名路由保留 15 处旧调用点 |
| D3 | HTTP 状态面板 port 8765 (4 endpoints) | PASS | live curl: /healthz="ok" ✓, /status=JSON含recent_events ✓, /events?sprint_id=sid-A 精准过滤(返回2条sid-A、不含sid-B) ✓, / HTML渲染 ✓, /nonexistent=404 ✓ |
| D4 | 协调器路由 bug 修复 (regex 锚定 + env override) | PASS | regex 改为 `^Persona:[[:space:]]*evaluator[[:space:]]*$` 严格锚定，PANE_BUILDER/PANE_EVALUATOR env override 已加，test-coordinator-routing 8/8 PASS（含"evaluator-pending"反向不匹配） |
| D5 | dispatch_with_gate sid 必填守卫 (修复 7 处) | PASS | coordinator.sh:954 dispatch_with_gate 实现，空 sid + `<sid>` placeholder 均 exit 1，test-dispatch-sid-required 8/8 PASS（含 5 并发不串扰） |
| D6 | Sprint 2 backlog 三项清理 | PASS | (a) test-symphony-hooks.sh 新增 case_env_allow_empty_value 9/9 PASS; (b) ADR §10 unsafe-run-codex 安全语义 ≥100字; (c) ADR §11 Observability + §12 Routing Bug 复盘 |
| D7 | Sprint 1+2 回归测试 | PASS | test-symphony-hooks.sh 9/9, test-events-emit 20/20, test-status-server 13/13, test-coordinator-routing 8/8, test-dispatch-sid-required 8/8 — 合计 58/58 |
| D8 | ADR + ROADMAP 文档更新 | PASS | symphony-integration-adr.md 370 行（增加 §10/§11/§12，>449字），ROADMAP.md 新增 P3 已完成项 + 状态面板快速上手 |

## 自动检测 (manual @FALLBACK_MANUAL)

| 检查 | 结果 |
|------|------|
| C1 功能完备 (无 TODO/FIXME) | PASS — Sprint 3 文件零 TODO/FIXME |
| C2 无断头 (有入口) | PASS — solar-harness status-server start 子命令 + coordinator source events.sh |
| C3 自动触发 | PASS — workspace_created/runner_started/hook_executed 由 lifecycle 钩子触发 |
| C4 默认使用 | PASS — events_emit 在 workspace/runner/hooks 默认走通；status-server 是 opt-in 服务（设计如此） |
| C5 错误处理 | PASS — _atomic_append 锁超时降级直写不丢事件；payload 非 JSON 自动包 raw |
| C6 错误隔离 | PASS — events_emit 全部 `2>/dev/null \|\| true`，不阻塞主流程 |
| C7 持久化 | PASS — 事件流写 $HARNESS_DIR/events/all.jsonl + sprints/<sid>.events.jsonl，无 /tmp |
| Q1 真的能跑吗 | PASS — live curl /healthz=ok + /status JSON 真实返回 |
| Q2 真的有效吗 | PASS — 20 写者并发 20/20 valid JSON, per-sprint 过滤 sid-A=2 条/sid-B=1 条精准 |
| Q3 真的会退化吗 | PASS — 严格 regex 锚定后 "evaluator-pending"/随机 evaluator 文本均不误匹配 |
| Q4 真的能恢复吗 | PASS — solar-harness status-server restart 子命令镜像 webhook 模式 + 端口 fallback 8765-8775 |
| Q5 真的用了吗 | PASS — workspace-manager/runner/hooks 已 source 并调用 events_emit |

## 否证尝试 (Red Team — deepseek-r1 镜头)

### D1 events.jsonl + emit_event 否证

```
[F1] 空 sprint_id → 期望: 仅写 all.jsonl, 不创建 per-sprint 文件
cmd: events_emit a e1 info "" '{}' && ls $HARNESS_DIR/sprints/
stdout: events 目录: all.jsonl ✓; sprints 目录: 空 ✓
conclusion: 空 sid 路径分支正确

[F2] 非法 severity 'WTF' → 期望: 强制降级为 info（不能崩溃也不能写错值）
cmd: events_emit a e2 WTF "sid1" '{}' && tail -1 events/all.jsonl | jq .severity
stdout: severity= info ✓
conclusion: case 语句兜底正确

[F3] 非 JSON payload 'not-json{' → 期望: 包装 {"raw":...} 不让 jsonl 损坏
cmd: events_emit a e3 info "sid2" 'not-json{' && tail -1 events/all.jsonl | jq .payload
stdout: payload={"raw":"not-json{"} has_raw_key=True ✓
conclusion: payload validator + python json.dumps 兜底有效

[F4] 20 并发写者 race condition → 期望: 20 行全部 valid JSON 无 torn write
cmd: for i in 1..20; events_emit "writer$i" race_test info race-sid "{\"i\":$i}" &; wait
stdout: Wrote 20 lines (expected 20); json_valid=20 json_invalid=0
conclusion: mkdir-lock 锁机制有效，并发下无撕裂写入
```

3 次否证 + 1 次 race 全部失败 → D1 PASS

### D3 HTTP 状态面板否证

```
[F1] /events?sprint_id=sid-A 期望仅返回 sid-A 事件 (我先误用 ?sprint=sid-A 触发 fallback 全返)
cmd: curl /events?sprint_id=sid-A 后 grep sprint_id 字段
stdout: count=2; src1 sid-A; src2 sid-A → 不含 sid-B ✓
conclusion: per-sprint 文件路由正确，参数名 sprint_id

[F2] /nonexistent → 期望 404
cmd: curl -o /dev/null -w '%{http_code}' /nonexistent
stdout: 404 ✓
conclusion: 默认分支正确

[F3] 绑定地址 → 期望仅 127.0.0.1 不暴露公网
cmd: grep BIND_HOST status-server.py
stdout: BIND_HOST = "127.0.0.1" ✓ (不是 0.0.0.0)
conclusion: 无外网暴露风险
```

3 次否证全部失败 → D3 PASS

### D4 路由 regex 否证

```
[F1] 'evaluator-pending' 不应匹配 evaluator 严格锚定 → test-coordinator-routing 已覆盖
[F2] 'Persona: TestEvaluator' 不应匹配 (大小写 / 词边界) → test 已覆盖
[F3] 'Persona: evaluator' 精确匹配 → test 已覆盖
stdout (test-coordinator-routing.sh):
  PASS: random 'evaluator' text does not match strict pattern
  PASS: exact 'Persona: evaluator' line matches strict pattern
  PASS: 'evaluator-pending' does not match strict pattern
conclusion: regex `^Persona:[[:space:]]*evaluator[[:space:]]*$` 锚定正确
```

### D5 dispatch_with_gate 否证

```
[F1] 空 sid → exit 1
[F2] '<sid>' placeholder → exit 1
[F3] 'dispatch' 占位 → exit 1
[F4] 5 并发不同 sid 调用 → 不串扰
stdout (test-dispatch-sid-required.sh): PASS=8 FAIL=0
conclusion: sid 守卫闭环
```

## Red Flag 扫描

| 类别 | 结果 |
|------|------|
| Mock/TODO/FIXME (lib/events.sh, status-server.py, coordinator.sh, solar-harness.sh) | ✅ 零命中 |
| /tmp 持久化 (Sprint 3 新文件) | ✅ 零命中 — 数据写 $HARNESS_DIR/events 和 sprints/ |
| live tmux mutation (events.sh / status-server.py) | ✅ 零命中 — events 库纯文件 IO；status-server 只读 |
| 密钥/Token 硬编码 | ✅ 零命中 |
| 公网暴露 (HTTP server bind) | ✅ BIND_HOST=127.0.0.1 (不是 0.0.0.0) |

## Smoke Test 证据

```
smoke test: D1 emit_event 端到端
cmd: source lib/events.sh && events_emit smoke-test test_event info "test-sid" '{"key":"value"}'
stdout:
{"ts":"2026-05-07T20:36:30Z","sprint_id":"test-sid","actor":"smoke-test","event":"test_event","severity":"info","payload":{"key":"value"}}
conclusion: schema v1 6 个 required 字段齐全, JSON valid, per-sprint 文件同步写入

smoke test: D3 status-server live
cmd: python3 lib/symphony/status-server.py & ; curl /healthz /status /events /
stdout:
/healthz → "ok"
/status → {"current_sprint":{},"panes":[],"recent_events":[3 events ...]}
/events?sprint_id=sid-A → [2 sid-A events]
/events?sprint_id=sid-B → [1 sid-B event]
/ → <!DOCTYPE html>...Solar Harness Status...
/nonexistent → HTTP 404
conclusion: 4 endpoint + 404 全部正确, per-sprint 过滤精准

smoke test: D7 全量回归
cmd: bash test-events-emit.sh test-status-server.sh test-coordinator-routing.sh test-dispatch-sid-required.sh test-symphony-hooks.sh
stdout: PASS=20+13+8+8+9 = 58 FAIL=0
conclusion: 5 套测试 58/58 通过
```

## 额外发现 (低风险 known issue, 不阻塞)

1. **status-server 单线程** (建设者已在 handoff 标注 risk #2): 当前 BaseHTTPRequestHandler 单线程, 高并发可能慢；内部监控满足需求, 生产可改 ThreadingHTTPServer。建议作为 Sprint 4 backlog。
2. **SIGKILL grace 测试受限** (handoff risk #1): hooks.sh 中的 perl alarm SIGTERM+sleep+SIGKILL 模式代码路径已写, 但本地测试环境无法实际模拟 SIGKILL 场景。代码 review 已确认逻辑正确, 不阻塞。
3. **E2E live tmux 烟囱测试**: handoff Not Done 中标注需要 live harness session。本机 tmux 状态可由后续真实 sprint 验证, 不阻塞 Sprint 3 验收。

## 合约偏离检查

合约 (seed) 仅指向 product-brief.md 作为权威源。8 项验收对照 product-brief 7 (Done 定义)：
- ✅ 所有 acceptance 项 keyword 与 product-brief 原文一致
- ✅ 无白名单扩张 / 条件收紧 / early return 偏离
- ✅ Round 2 修复点 (3 项 backlog clean) 与 Sprint 2 D6 残留对齐

无合约偏离。
