# Design — Solar-Harness Live-Work Visibility · S04 Orchestration & UI

Sprint: `sprint-20260514-p0-…-s04-orchestration-ui`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Slice: `orchestration-ui` (Planner pass)
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used（命中 `solar-harness-observability.md` — 把分散日志整合为可查询面板）

## 1. Problem Framing

S03 已把核心 lib 写出来（`harness/lib/livework/` 5 模块）：

- `schemas.py` (4 dataclass)
- `state_aggregator.py` (`aggregate_pane_state`, `resolve_role` 纯函数)
- `events.py` (5 emit_* 函数)
- `idle_detector.py` (`is_idle`, `detect_deadlock`, `should_emit_heartbeat` — `now` 显式注入)
- `intake_state_machine.py` (FSM `received → … → dispatched/rejected`)

S04 必须把它们**接入运行时**：autopilot 主循环（hook，不重写）、status-server HTTP 路由、pane status UI、DAG ready 可视化。

5 outcome 全部要在 UI 上**真看见证据**：
- O1: status 页面"no active work"卡片由 `is_idle()` 驱动
- O2: autopilot 每 N 秒调 `should_emit_heartbeat()` 决定是否 emit；`detect_deadlock()` 命中后写 events.jsonl
- O3: POST `/api/requirements` → `intake_state_machine.intake_requirement()` → 新 sprint
- O4: GET `/api/roles/<sid>/next-step` → `resolve_role()` 返回派生视图
- O5: events.jsonl 新事件（来自 S03 `emit_*`）在 UI tail 可见

## 2. Slice Boundaries

- **做**：5 个 HTTP 路由 + 1 个 autopilot hook 脚本 + 1 套 status UI 模板 + 1 个 DAG visibility 适配器 + 集成 smoke + handoff
- **不做**：lib 内部实现（S03 完）、e2e 用户流程测试 + activation-proof（S05）
- **不允许**：重写 `coordinator.sh` / `autopilot.sh` / `status-server/app.py` 主循环；声称 epic 已完成

## 3. Design Goals

| Goal | Why |
|------|-----|
| **HTTP 路由是 lib 的薄包装** | 路由函数 ≤ 30 行，只做参数解析 + 调 lib + JSON 序列化；业务逻辑不在路由层 |
| **autopilot 用 hook 接入** | 不动 autopilot 主循环；hook 脚本独立可单跑、可回滚 |
| **UI 显示来源标签** | 每个面板顶部小字"来源: events.jsonl@<ts>"，避免"声称完成" |
| **DAG ready 节点可视化** | epic + child sprint + ready_nodes + blocked_by 一目了然 |
| **降级 fail-open** | lib 任一函数抛异常 → UI 显示"unknown"而非 500；hook 失败不阻塞 autopilot |

## 4. Non-Goals

- 不实现新的核心算法（idle/deadlock/role-resolve 都在 S03）
- 不改 events.jsonl schema（沿用 S03 EventV2）
- 不写 e2e 用户流程（S05）
- 不做 UI 国际化、不做主题切换、不做权限控制（已知未闭环项）
- 不替 deadlock alert 写自动 re-dispatch（O2 acceptance 明确排除；只写告警）

## 5. Module Map (5 节点交付物)

```text
harness/status-server/routes/
└── livework_routes.py          ← 5 个 HTTP 路由（idle-state / heartbeat-config / deadlock-alerts / requirements / role-next-step）

harness/status-server/templates/
└── livework_panel.html         ← status 页面插件：no-active-work / role next-step / deadlock alerts / events tail

harness/status-server/static/
└── livework_panel.js           ← 前端 fetch + 渲染逻辑（≤ 200 行 vanilla JS）

harness/autopilot/hooks/
└── livework_heartbeat_hook.sh  ← autopilot 主循环每 tick 调用的 hook（调 livework_heartbeat_runner.py）
harness/autopilot/hooks/
└── livework_heartbeat_runner.py ← Python runner：调 idle_detector + events.emit_*

harness/lib/livework/
└── dispatch_visibility.py      ← 把 graph_scheduler ready/blocked 状态转 UI JSON

harness/tests/livework/
├── test_routes_smoke.py         ← 5 路由 happy-path
├── test_heartbeat_hook.py       ← hook runner unit
├── test_dispatch_visibility.py  ← visibility 函数
└── test_integration_s04.py      ← curl 真路由 → 验响应 + UI HTML 含关键 DOM id
```

## 6. Deliverables

| # | Deliverable | Owner Node | 关键 API / 路由 |
|---|-------------|-----------|---------|
| D1 | `status-server/routes/livework_routes.py` + `test_routes_smoke.py` | N1 | `GET /api/idle-state`, `GET /api/heartbeat-config`, `GET /api/deadlock-alerts`, `POST /api/requirements`, `GET /api/roles/<sid>/next-step` — 5 路由，每个 ≤ 30 行业务代码 |
| D2 | `autopilot/hooks/livework_heartbeat_hook.sh` + `livework_heartbeat_runner.py` + `test_heartbeat_hook.py` | N2 | autopilot 主循环 source 这一个文件；hook 调 `idle_detector.should_emit_heartbeat()` + `detect_deadlock()`；失败 fail-open 不阻塞主循环 |
| D3 | `lib/livework/dispatch_visibility.py` + `test_dispatch_visibility.py` | N3 | `build_visibility_view(epic_id) -> dict`：epic + ready_nodes + blocked + capability_use + 阻塞原因 |
| D4 | `status-server/templates/livework_panel.html` + `static/livework_panel.js` | N4 | 4 张卡片：no-active-work、role-next-step、deadlock-alerts、events-tail；每卡片顶部"来源: ..."标签 |
| D5 | `test_integration_s04.py` + handoff.md + parent traceability patch | N5 (join) | curl 5 路由 + grep UI HTML 关键 dom-id；handoff 含 S05 接入清单 + 已知未闭环；parent `children[3].orchestration_ui_ready=true` |

## 7. DAG Topology

```text
N1 routes ────────┐
N2 autopilot hook ┤
N3 visibility lib ┼── N5 integration + handoff
N4 UI templates ──┘
```

Layers: `[[N1, N2, N3, N4], [N5]]`

5 节点 2 层；N1∥N2∥N3∥N4 完全并行（write_scope 互斥）；N5 join。

注意：N4 UI 可以**先用 fixture JSON 开发**（无需阻塞等 N1），最终在 N5 集成 smoke 中 wire 真路由。

## 8. Acceptance Contract

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | 5 路由全部在 routes/livework_routes.py 注册并返回 2xx；每路由业务代码 ≤ 30 行 | curl + wc -l |
| A2 | `GET /api/idle-state` 返回 `{is_idle, reason, since_ts, source}`，调 `is_idle(pane_state)` | curl + JSON shape |
| A3 | `POST /api/requirements {"text":"..."}` 返回 `{sprint_id, state}`，调 `intake_requirement(text)` | curl |
| A4 | autopilot hook 脚本独立可跑：`bash livework_heartbeat_hook.sh` exit 0 / 1，且不依赖 autopilot 已启动 | bash 真跑 |
| A5 | autopilot 主循环只需 source 一行 `[ -x .../livework_heartbeat_hook.sh ] && .../livework_heartbeat_hook.sh` 即可接入（不重写主循环） | git diff autopilot.sh ≤ 3 行 |
| A6 | hook runner 异常时返回非 0，但 autopilot 主循环不应中断（hook 在 trap/`||true` 中调用） | trap test |
| A7 | UI 页面含 4 个 dom-id：`#no-active-work-card`, `#role-next-step-card`, `#deadlock-alerts-card`, `#events-tail-card` | grep HTML |
| A8 | 每卡片含"来源: events.jsonl@<ts>" 或 "来源: lib.livework.<fn>" 标签 | grep HTML |
| A9 | dispatch_visibility.build_visibility_view() 返回字段含 `epic_id, ready_nodes, blocked_nodes, capability_use, last_event_ts` | unit |
| A10 | `pytest harness/tests/livework -v` 全过（含 S03 旧测 + S04 新测），总断言 ≥ 90 | pytest |
| A11 | 集成 smoke：`test_integration_s04.py` 启 status-server fixture，curl 5 路由全 2xx，断言 ≥ 12 | pytest |
| A12 | git diff: `coordinator.sh` / `status-server/app.py` 主路由表 / lib/livework 现有 .py 改动 == 0 | git diff |
| A13 | 父 traceability.json `children[3].orchestration_ui_ready=true` | jq |
| A14 | handoff 不含 "epic 已完成" / "S05 已就绪" | grep == 0 |

## 9. Stop Rules

- 任何节点重写 `autopilot.sh` 主循环（git diff > 5 行）→ fail
- 任何节点改 `status-server/app.py` 现有路由 → fail（只新增 Blueprint / Router include）
- 任何路由业务代码 > 30 行 → fail（路由必须是薄包装）
- UI 模板写死状态字串（如 "no active work"）而不读 lib 返回 → fail（声称代替证据）
- hook 失败导致 autopilot 主循环中断 → fail（fail-open 铁律）
- N5 在 N1-N4 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "S05 已就绪" / "epic 完成" → fail
- `pytest harness/tests/livework -v` 总断言 < 90 → fail

## 10. Parallelism & Write Scope

- **N1**: `harness/status-server/routes/livework_routes.py`, `harness/status-server/routes/__init__.py`（只追加 import 不改既有）, `harness/tests/livework/test_routes_smoke.py`
- **N2**: `harness/autopilot/hooks/livework_heartbeat_hook.sh`, `harness/autopilot/hooks/livework_heartbeat_runner.py`, `harness/tests/livework/test_heartbeat_hook.py`
- **N3**: `harness/lib/livework/dispatch_visibility.py`, `harness/tests/livework/test_dispatch_visibility.py`
- **N4**: `harness/status-server/templates/livework_panel.html`, `harness/status-server/static/livework_panel.js`, `harness/tests/livework/test_ui_template.py`
- **N5**: `harness/tests/livework/test_integration_s04.py`, sprint handoff.md, parent traceability.json (`children[3].orchestration_ui_ready` only)

write_scope 完全互斥。N4 UI 用 fixture JSON 开发可独立于 N1。N5 join 后做真集成 smoke。

## 11. Model Routing

- 所有节点 `sonnet`（GLM 1210 已 5 次 + UI 准确性）
- 禁止 worker webfetch / web search
- 测试 fixture：用真 HTTP server fixture（pytest-flask 或 wsgiref），禁 mock 真 IO
- HTML/JS 用原生 + 极简模板（无 React/Vue）

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| 路由层塞业务逻辑（≥ 50 行）| 硬上限 30 行业务代码；evaluator wc -l 验 |
| autopilot 主循环被改 | git diff autopilot.sh ≤ 3 行；只允许 source 一行 hook |
| UI 写死状态字串假装活 | A7+A8：必须含"来源: ..."标签；evaluator grep |
| hook 失败把 autopilot 拖死 | 主循环用 `(.../hook.sh || true)`；A6 显式测试 |
| 路由响应 shape 与 S02 interfaces.md 不符 | interface_consistency_policy：路由 response 字段必须在 interfaces.md 中定义 |
| status-server 路由表冲突 | 用 Flask Blueprint 隔离；A12 验主 app.py 路由表未动 |
| events.jsonl tail 渲染拖慢 UI | 后端切片只读最后 50 行；A8 验"来源"标签含 ts |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行：命中 `solar-harness-observability.md`（把分散日志整合为可查询面板的目标）+ 历史 sprint `sprint-20260417-160453`（status-server 路由扩展模式参考）
- S02 interfaces.md 5 个 API contract 是路由 response shape 唯一来源
- S03 5 模块的导出 API 是路由实现唯一调用入口
- 现有 `status-server/app.py` 是 Flask 应用；S04 用 Blueprint 注册，不动主路由表

## 14. Handoff Plan

N5 完成后，handoff.md 必须含：

- 5 路由 curl 示例 + 响应 shape 摘要
- autopilot hook 一行集成指令（`source $HARNESS/autopilot/hooks/livework_heartbeat_hook.sh || true`）
- 4 个 UI 卡片 dom-id + 数据源标签示例
- pytest 总断言数 + smoke test exit code
- S05 接入清单：e2e 用户流程脚本 fixture、负控测试（lib 异常 → UI 降级）、activation-proof 入口
- 已知未闭环项（UI 权限/主题/国际化、deadlock 自动 re-dispatch、PRD 复杂场景）
- `evaluator_can_review: true` + `s05_can_start: true`
