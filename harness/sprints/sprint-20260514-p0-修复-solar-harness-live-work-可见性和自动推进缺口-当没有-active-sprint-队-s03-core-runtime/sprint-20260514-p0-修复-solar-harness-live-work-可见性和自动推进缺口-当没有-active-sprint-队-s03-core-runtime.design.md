# Design — Solar-Harness Live-Work Visibility · S03 Core Runtime

Sprint: `sprint-20260514-p0-…-s03-core-runtime`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Slice: `core-runtime` (Planner pass)
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

S02 已交付 4 份架构文档：architecture.md / interfaces.md / data-model.md / migration.md。S03 把它们落到 **可执行的 Python 模块** 下：

- O1 status idle state — 需要 idle 检测函数（pane 状态聚合）
- O2 autopilot heartbeat + deadlock — 需要心跳计时器 + dispatch-to-pane 映射 + 阈值判定
- O3 PM-first PRD 流程 — 需要 requirement intake 状态机
- O4 status UI 每角色下一步 — 需要 role-resolver 派生视图
- O5 状态转换可见证据 — 需要 events.jsonl 扩展（新事件类型）

S03 是**第一个真正写代码的切片**。但仍是 lib 层；不接入 status-server / autopilot 主循环（那是 S04 的活）。

## 2. Slice Boundaries

- **做**：`harness/lib/livework/` 下 5 个 Python 模块 + 单测 + 旧路径兼容性 shim
- **不做**：autopilot 主循环改动（S04）、status-server 路由（S04）、e2e 测试（S05）、UI 渲染（S04）
- **不允许**：直接修改 `coordinator.sh` 主循环；声称父 epic 已完成；mock 真实 IO

## 3. Design Goals

| Goal | Why |
|------|-----|
| **每个模块单一职责** | schemas / state_aggregator / events / idle_detector / intake_state_machine 各管一段 |
| **核心 API 有单测覆盖** | S05 端到端测试前的最小保障；PRD 明确要求 |
| **旧路径兼容** | 不破坏现有 `wake/dispatch/status`；只允许新增事件类型、新增 lib 模块 |
| **状态变更可由元数据或事件重建** | role-resolver 必须是纯函数（events.jsonl → derived view）；可重放 |
| **schema_version 全字段** | data-model.md 已锁；演进可兼容 |

## 4. Non-Goals

- 不实现 status-server `/api/idle-state` HTTP 路由（S04）
- 不接 autopilot 主循环（S04 用 hook）
- 不实现 UI 渲染（S04）
- 不写 e2e 用户流程测试（S05）
- 不替 deadlock recovery 写自动 re-dispatch 逻辑（O2 acceptance 明确排除）

## 5. Module Map (5 Python 模块 + tests)

```text
harness/lib/livework/
├── __init__.py
├── schemas.py              ← 4 schema dataclasses
├── state_aggregator.py     ← pane-state + role-resolver (derived from events)
├── events.py               ← 新事件类型 + emit_*() helpers
├── idle_detector.py        ← heartbeat timer + deadlock detection
├── intake_state_machine.py ← PRD intake FSM (O3)

harness/tests/livework/
├── test_schemas.py
├── test_state_aggregator.py
├── test_events.py
├── test_idle_detector.py
├── test_intake_state_machine.py
├── test_integration_replay.py    ← 用真 events.jsonl 重放验证
```

## 6. Deliverables

| # | Deliverable | Owner Node | 关键 API |
|---|-------------|-----------|---------|
| D1 | `lib/livework/schemas.py` | N1 | `@dataclass StatusExt / EventV2 / RequirementIntake / RoleResolverView`，`schema_version: str` 必填字段 |
| D2 | `lib/livework/state_aggregator.py` | N2 | `aggregate_pane_state(events) -> PaneState`，`resolve_role(events, sid) -> RoleNextStep`（纯函数） |
| D3 | `lib/livework/events.py` | N3 | `emit_heartbeat()`, `emit_deadlock_detected()`, `emit_requirement_intake()`, `emit_pm_drafted()`, `emit_role_transition()` |
| D4 | `lib/livework/idle_detector.py` | N4 | `is_idle(pane_state) -> bool`, `detect_deadlock(dispatch_log, now, timeout) -> List[DeadlockAlert]`, `should_emit_heartbeat(last_hb, now, interval) -> bool` |
| D5 | `lib/livework/intake_state_machine.py` | N5 | `intake_requirement(text) -> SprintId`，FSM transitions: `received → validating → pm_drafting → planner_pending → dispatched / rejected` |
| D6 | 单测 + 集成测 + handoff + parent traceability patch | N6 (join) | 6 个 test_*.py，断言 ≥ 60；handoff 含 S04 接入清单 |

## 7. DAG Topology

```text
N1 schemas  ──┬── N2 state_aggregator ──┐
              │                          ├── N4 idle_detector ──┐
              ├── N3 events ─────────────┴─────────────────────┐ │
              │                                                 │ │
              └────────── N5 intake_state_machine ──────────────┘ │
                                                                  │
                                              N6 integration+handoff
```

Layers: `[[N1], [N2, N3], [N4, N5], [N6]]`

6 节点 4 层；N2 ∥ N3 二并；N4 ∥ N5 二并；N6 join。

## 8. Acceptance Contract

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | 5 个模块全部存在；`python -c "from harness.lib.livework import schemas, state_aggregator, events, idle_detector, intake_state_machine"` 无异常 | python import |
| A2 | 6 个 test_*.py 全过；`pytest harness/tests/livework -v` exit 0，断言 ≥ 60 | pytest |
| A3 | 4 schema 全含 `schema_version: str` 字段 | grep |
| A4 | `state_aggregator.resolve_role(events, sid)` 是**纯函数**（输入相同 → 输出相同；不依赖外部状态） | property test |
| A5 | `events.py` emit 至少 5 个新事件类型（heartbeat / deadlock_detected / requirement_intake / pm_drafted / role_transition），全部写入 events.jsonl | grep + replay test |
| A6 | `intake_state_machine` FSM 含至少 5 个 state + 至少 7 个 transition，含 `rejected` 兜底转移 | grep + state test |
| A7 | 不修改 `coordinator.sh` / `autopilot.sh` / `status-server/` 任何现有文件 | git diff |
| A8 | `solar-harness doctor` exit 0（旧路径兼容） | doctor |
| A9 | 父 traceability.json children[2].core_runtime_ready=true | jq |
| A10 | 不声称 "epic 已完成" 或 "S04/S05 已就绪" | grep == 0 |

## 9. Stop Rules

- **任何节点修改 coordinator.sh / autopilot.sh / status-server/ 文件** → fail
- 模块缺 `schema_version` 字段 → fail（演进不兼容）
- 测试用 `@mock.patch` 替代真 events.jsonl 写入 → fail（test_integrity）
- 实现代码 `import requests / urllib.request / httpx` → fail（无外部 HTTP）
- N4 idle_detector 不是纯函数（依赖 time.time() 隐式输入）→ fail（必须显式注入 now）
- N5 intake_state_machine 缺 rejected 转移 → fail（兜底不可少）
- N6 在 N1-N5 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "epic 完成" → fail

## 10. Parallelism & Write Scope

- **N1**: `harness/lib/livework/__init__.py`, `harness/lib/livework/schemas.py`, `harness/tests/livework/test_schemas.py`
- **N2**: `harness/lib/livework/state_aggregator.py`, `harness/tests/livework/test_state_aggregator.py`
- **N3**: `harness/lib/livework/events.py`, `harness/tests/livework/test_events.py`
- **N4**: `harness/lib/livework/idle_detector.py`, `harness/tests/livework/test_idle_detector.py`
- **N5**: `harness/lib/livework/intake_state_machine.py`, `harness/tests/livework/test_intake_state_machine.py`
- **N6**: `harness/tests/livework/test_integration_replay.py`, sprint handoff.md, parent traceability.json (children[2].core_runtime_ready)

write_scope 完全互斥。N2/N3 都依赖 N1（schema 类型）；N4 依赖 N2+N3（state + events）；N5 依赖 N1+N3。

## 11. Model Routing

- 所有节点 `sonnet`（GLM 1210 风险 + 代码严谨性）
- 禁止 worker webfetch / web search
- 测试 fixture 用 tmp_path / 内存数据，禁 mock 真 IO

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| N2 state_aggregator 依赖 N1 schema 完成才能开工 | DAG 强制 N1 → N2/N3；S04 不能用 lookahead |
| 测试用 mock 绕过真 IO | Stop rule + evaluator grep `@mock.patch` 命中数 |
| 模块名与现有 lib/ 冲突 | 用 `livework/` 子目录隔离，不接触 `lib/research/` / `lib/phase-state-machine.sh` 等 |
| idle_detector 含隐式时间依赖（time.time()） | API 强制注入 `now: datetime`；纯函数 |
| events.py 写 events.jsonl 时与 coordinator emit_event 冲突 | 只追加，用现有 append-only 协议；不修改 emit_event 函数 |
| `solar-harness doctor` 因新模块 import error 失败 | N1 必须先建好 `__init__.py`，且单测验证 import |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行：命中 `managed-agent-runtime-write-path-audit-20260513.md`（coordinator.sh emit_event + phase-state-machine.sh 是 canonical writer，不能改）。
- 复用 S02 data-model.md 中 4 schema 定义；字段名 / 类型严格对齐。
- 复用 S02 interfaces.md 中 5 API contract；S04 后续接 HTTP。
- 复用 S02 migration.md 中"只允许 hook / append"的约束。

## 14. Handoff Plan

N6 完成后，handoff.md 必须含：

- 5 模块 import 示例（`from harness.lib.livework import …`）
- 5 outcome → 模块 → 关键 API 矩阵
- S04 接入清单：哪个 HTTP 路由调用哪个 lib 函数；哪个 autopilot hook 用哪个 detector
- 单测结果 head（pytest exit code + 断言数 + coverage 头部）
- 已知未闭环项：deadlock recovery 自动化、PM 复杂判断、capability 集成
- `evaluator_can_review: true` + `s04_can_start: true`
