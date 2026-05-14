# Plan — Solar-Harness Live-Work Visibility · S04 Orchestration & UI

Sprint: `sprint-20260514-p0-…-s04-orchestration-ui`
Slice: `orchestration-ui`
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. DAG

```text
N1 routes (5 HTTP)        ─┐
N2 autopilot hook         ─┤
N3 dispatch_visibility    ─┼── N5 integration + handoff
N4 UI templates (HTML+JS) ─┘
```

Layers: `[[N1, N2, N3, N4], [N5]]`

5 节点 2 层；前 4 完全并行；N5 join。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Model | Cost | Gate |
|------|------|---------|-------|------|------|
| **N1** | `routes/livework_routes.py`：5 个 HTTP 路由，每个业务代码 ≤ 30 行（参数解析 + 调 lib + JSON 序列化）；用 Flask Blueprint 注册，不动 `app.py` 主路由表；`test_routes_smoke.py` ≥ 12 断言 | — | sonnet | 1.5 | routes-pass |
| **N2** | `autopilot/hooks/livework_heartbeat_hook.sh` + `livework_heartbeat_runner.py`：hook 调 `idle_detector.should_emit_heartbeat / detect_deadlock`，命中后 `events.emit_*`；hook 失败 fail-open；`test_heartbeat_hook.py` ≥ 8 断言含失败-不阻塞测试 | — | sonnet | 1.5 | hook-pass |
| **N3** | `lib/livework/dispatch_visibility.py`：`build_visibility_view(epic_id) -> dict`（epic_id / ready_nodes / blocked_nodes / capability_use / last_event_ts / source）；纯函数；`test_dispatch_visibility.py` ≥ 10 断言 | — | sonnet | 1.0 | visibility-pass |
| **N4** | `templates/livework_panel.html` + `static/livework_panel.js`：4 卡片（`#no-active-work-card / #role-next-step-card / #deadlock-alerts-card / #events-tail-card`）+ 每卡片"来源:"标签；`test_ui_template.py` 检查 dom-id + 标签 ≥ 6 断言 | — | sonnet | 1.0 | ui-pass |
| **N5** | `test_integration_s04.py` 启 status-server fixture 真 curl 5 路由（≥ 12 断言）+ 验 UI HTML 含 4 dom-id；handoff.md（S05 接入清单 + 未闭环）；parent `children[3].orchestration_ui_ready=true` patch | N1-N4 | sonnet | 1.0 | integration-pass |

Total: 6.0 units（关键路径 max(N1..N4) + N5 ≈ 2.5）。

## 3. Parallelism

- **Layer 1**: `[N1, N2, N3, N4]` — write_scope 完全互斥
  - N1 写 `status-server/routes/livework_routes.py`
  - N2 写 `autopilot/hooks/livework_heartbeat_*`
  - N3 写 `lib/livework/dispatch_visibility.py`
  - N4 写 `status-server/templates/livework_panel.html` + `static/livework_panel.js`
  - N4 用 fixture JSON 开发，不依赖 N1 路由真上线
- **Layer 2**: `[N5]` — 真集成 smoke + handoff + parent patch

最大 builder 并发 = 4。

## 4. Dispatch Batches

- **batch-1**: `[N1, N2, N3, N4]` → join_gate `[routes-pass, hook-pass, visibility-pass, ui-pass]`
- **batch-2**: `[N5]` → join_gate `[integration-pass]`

## 5. Per-Node Acceptance

### N1 routes (write: `harness/status-server/routes/livework_routes.py`, `harness/status-server/routes/__init__.py` (追加 import only), `harness/tests/livework/test_routes_smoke.py`)
- 5 路由全部实现：
  - `GET /api/idle-state` → `{is_idle, reason, since_ts, source}`，调 `is_idle()`
  - `GET /api/heartbeat-config` → `{interval_seconds, deadlock_timeout_seconds, source}`
  - `GET /api/deadlock-alerts` → `{alerts: [...], source}`
  - `POST /api/requirements` `{text}` → `{sprint_id, state}`，调 `intake_requirement(text)`
  - `GET /api/roles/<sid>/next-step` → `{role, next_step, blocked_by, source}`，调 `resolve_role()`
- 每路由业务代码 ≤ 30 行：`wc -l` 路由函数 body ≤ 30
- Flask Blueprint 注册（不改 `app.py` 主路由表，只追加 `from .routes.livework_routes import bp; app.register_blueprint(bp)`）
- response shape 必须匹配 S02 interfaces.md（每字段都能在 interfaces.md 中找到）
- `pytest test_routes_smoke.py -v` exit 0，断言 ≥ 12
- `git diff status-server/app.py` ≤ 2 行（只允许追加 register_blueprint）

### N2 autopilot hook (write: `harness/autopilot/hooks/livework_heartbeat_hook.sh`, `livework_heartbeat_runner.py`, `harness/tests/livework/test_heartbeat_hook.py`)
- hook.sh 是 1 行 shell：`python3 .../livework_heartbeat_runner.py "$@" || true`（fail-open）
- runner.py 调 `idle_detector.should_emit_heartbeat()` + `detect_deadlock()`；命中调 `events.emit_heartbeat / emit_deadlock_detected`
- runner.py `now` 用 `datetime.utcnow()` 但**仅在 main 入口**（lib 仍纯函数）
- test 覆盖：(a) hook 正常返回 0；(b) hook runner 抛异常 → hook 仍 exit 0（fail-open）；(c) emit 事件真写 tmp events.jsonl
- `pytest test_heartbeat_hook.py -v` exit 0，断言 ≥ 8
- `git diff autopilot.sh` == 0（S04 不动主循环；接入留给 S05 evidence pass）

### N3 dispatch_visibility (write: `harness/lib/livework/dispatch_visibility.py`, `harness/tests/livework/test_dispatch_visibility.py`)
- `build_visibility_view(epic_id, *, sprints_dir, events_dir) -> dict`：纯函数（参数注入）
- 返回字段：`epic_id, child_sprints[], ready_nodes[], blocked_nodes[{node_id, blocked_by}], capability_use[], last_event_ts, source`
- 数据来源：扫 `<epic>.traceability.json` + 每个 child `<sid>.task_graph.json` `node_results`
- test 覆盖：empty epic / partial ready / all blocked / events 缺失降级
- `pytest test_dispatch_visibility.py -v` exit 0，断言 ≥ 10
- 不 import `requests / httpx`；不调 `time.time()`（参数注入）

### N4 UI templates (write: `harness/status-server/templates/livework_panel.html`, `harness/status-server/static/livework_panel.js`, `harness/tests/livework/test_ui_template.py`)
- HTML 含 4 dom-id：`#no-active-work-card`, `#role-next-step-card`, `#deadlock-alerts-card`, `#events-tail-card`
- 每卡片含 `.source-tag` 元素，预期文本格式 `来源: events.jsonl@<ts>` 或 `来源: lib.livework.<fn>`
- JS 原生 fetch + 渲染（≤ 200 行）；空状态显示 "unknown" 而非空白
- test_ui_template.py 用 BeautifulSoup / 正则验：4 dom-id 存在 + 每卡片有 .source-tag + 总 ≥ 6 断言
- 不 import 任何前端框架（React/Vue/Lit）

### N5 integration + handoff (write: `harness/tests/livework/test_integration_s04.py`, sprint handoff.md, parent traceability.json patch)
- test 启 status-server fixture（pytest-flask 或 wsgiref 启 ephemeral port）
- curl/requests 5 路由 happy path + 验响应 shape
- 加载 `/livework_panel`（或主页含面板的路由）+ grep 4 dom-id 存在
- handoff.md 含：
  - 5 路由 curl 示例 + 响应 shape
  - autopilot 主循环 1 行集成指令（留给 S05 evidence pass 评估是否真接入）
  - 4 UI 卡片 dom-id + 数据源标签示例
  - pytest 总断言数 + smoke test exit code
  - S05 接入清单
  - `evaluator_can_review: true` + `s05_can_start: true`
- parent traceability.json 仅 patch `children[3].orchestration_ui_ready=true`（schema_version 不变；children 顺序不变）
- 不含 "epic 已完成" / "S05 已就绪" 字串

## 6. Routing Policy

- 所有节点 `sonnet`（GLM 1210 已 5 次 + UI 准确性）
- 禁止 worker webfetch / web search
- 上游源：S03 lib（已 passed 前提）+ S02 interfaces.md（路由 response shape）+ S02 data-model.md（schema 字段）
- 测试 fixture：用真 HTTP server，禁 `@mock.patch` / `unittest.mock`
- HTML/JS 用原生 + 极简模板（无 React/Vue/Lit）
- N2 runner.py 是唯一允许 `datetime.utcnow()` 的入口（lib 仍纯函数）

## 7. Stop Rules（执行期）

- N1 路由业务代码 > 30 行 → fail
- N1 改 `status-server/app.py` 主路由表（> 2 行 diff）→ fail
- N2 `autopilot.sh` git diff > 0 → fail（S04 不接主循环；S05 evidence pass 才接）
- N2 hook 抛异常导致 exit ≠ 0 → fail（fail-open 必须）
- N3 `build_visibility_view` 不是纯函数（依赖隐式 cwd / time）→ fail
- N4 UI 写死状态字串而不调 lib → fail（A8 .source-tag 必须含动态来源）
- N4 引入 React/Vue/Lit → fail
- N5 在 N1-N4 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "epic 完成" / "S05 已就绪" → fail
- 总断言 (N1+N2+N3+N4+N5 test) < 48 → fail
- `pytest harness/tests/livework -v` (含 S03 + S04) 总断言 < 90 → fail

## 8. Exit Criteria

- 5 节点全 passed
- 5 路由 curl happy path 全 2xx
- 4 UI dom-id 在模板中存在
- autopilot hook 失败-不阻塞测试通过
- `pytest harness/tests/livework -v` exit 0，总断言 ≥ 90
- `git diff` autopilot.sh / coordinator.sh / status-server/app.py 路由表均 ≤ 2 行
- parent traceability.json `children[3].orchestration_ui_ready=true`
- handoff 含 `s05_can_start: true`，无 overclaim 字串

## 9. Evaluator 复核入口

1. `ls harness/status-server/routes/livework_routes.py` 存在
2. `ls harness/autopilot/hooks/livework_heartbeat_hook.sh` 可执行
3. `ls harness/status-server/templates/livework_panel.html` 存在
4. `ls harness/lib/livework/dispatch_visibility.py` 存在
5. `pytest harness/tests/livework -v` exit 0
6. `grep -c '@app.route\|@bp.route' status-server/routes/livework_routes.py` ≥ 5
7. `grep -c 'no-active-work-card\|role-next-step-card\|deadlock-alerts-card\|events-tail-card' status-server/templates/livework_panel.html` ≥ 4
8. `grep -c 'source-tag' status-server/templates/livework_panel.html` ≥ 4
9. `git diff --stat HEAD -- status-server/app.py` ≤ 2 行
10. `git diff --stat HEAD -- harness/autopilot.sh harness/coordinator.sh` == 0
11. `jq '.children[3].orchestration_ui_ready' sprints/epic-*.traceability.json` == true
12. `grep -c 'epic.*已完成\|S05.*已就绪' sprints/*s04-orchestration-ui.handoff.md` == 0
13. `grep -c 's05_can_start: true' sprints/*s04-orchestration-ui.handoff.md` == 1

## 10. Out of Scope

- **S05**: e2e 用户流程脚本 + 负控（lib 异常 → UI 降级真验）+ activation-proof（autopilot 真接 hook 跑一晚）+ 文档收尾 + 父 epic close
- 未来切片：UI 权限/主题/i18n；deadlock 自动 re-dispatch；PRD 复杂场景（多角色协商）

## 11. 当前状态说明

本切片 status = `drafting/prd_ready`（Workflow Guard 已放行）；目标 status = `active/planning_complete`，handoff_to=`builder_parallel`。

依赖 S03 passed；当前 S03 status = `active/planning_complete`（builder 派发中）。`dependency_policy.blocks_until` 已硬编码 S03:passed，graph_scheduler 会自动 hold S04 N1-N4 直到 S03 完成。

S02 已 passed（5 文档齐全：architecture / interfaces / data-model / migration / handoff）；S04 路由 response shape 直接复用 S02 interfaces.md。
