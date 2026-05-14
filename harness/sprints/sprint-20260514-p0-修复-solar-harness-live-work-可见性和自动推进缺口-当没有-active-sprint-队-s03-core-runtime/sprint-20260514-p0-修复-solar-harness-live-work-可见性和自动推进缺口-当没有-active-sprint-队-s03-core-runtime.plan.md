# Plan — Solar-Harness Live-Work Visibility · S03 Core Runtime

Sprint: `sprint-20260514-p0-…-s03-core-runtime`
Slice: `core-runtime`
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. DAG

```text
N1 schemas  ──┬── N2 state_aggregator ──┐
              │                          ├── N4 idle_detector ──┐
              ├── N3 events ─────────────┴─────────────────────┐ │
              │                                                 │ │
              └────────── N5 intake_state_machine ──────────────┘ │
                                                                  │
                                              N6 integration+handoff
```

6 节点 4 层；Layers = `[[N1], [N2, N3], [N4, N5], [N6]]`。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Model | Cost | Gate |
|------|------|---------|-------|------|------|
| **N1** | `harness/lib/livework/__init__.py` + `schemas.py`：4 dataclass (StatusExt / EventV2 / RequirementIntake / RoleResolverView)，每个含 `schema_version: str` 必填字段；`test_schemas.py` ≥ 8 断言 | — | sonnet | 1.0 | schemas-pass |
| **N2** | `state_aggregator.py`：`aggregate_pane_state(events) -> PaneState`、`resolve_role(events, sid) -> RoleNextStep`（**纯函数**：相同输入 → 相同输出）；`test_state_aggregator.py` ≥ 10 断言含 property test | N1 | sonnet | 1.5 | state-aggregator-pass |
| **N3** | `events.py`：`emit_heartbeat / emit_deadlock_detected / emit_requirement_intake / emit_pm_drafted / emit_role_transition`，全部 append-only 写真 events.jsonl；`test_events.py` ≥ 10 断言 | N1 | sonnet | 1.0 | events-pass |
| **N4** | `idle_detector.py`：`is_idle(pane_state) -> bool`、`detect_deadlock(dispatch_log, now, timeout) -> List[Alert]`、`should_emit_heartbeat(last_hb, now, interval) -> bool`；**`now` 显式注入**，禁隐式 `time.time()`；`test_idle_detector.py` ≥ 12 断言 | N2, N3 | sonnet | 1.5 | idle-detector-pass |
| **N5** | `intake_state_machine.py`：FSM `received → validating → pm_drafting → planner_pending → dispatched / rejected`，≥ 5 state + ≥ 7 transition，含 `rejected` 兜底；`test_intake_state_machine.py` ≥ 12 断言 | N1, N3 | sonnet | 1.5 | intake-fsm-pass |
| **N6** | `test_integration_replay.py` 用真 events.jsonl 重放断言 ≥ 8 项；handoff.md 含 5 outcome → 模块矩阵 + S04 接入清单；parent traceability.json patch `children[2].core_runtime_ready=true` | N1-N5 | sonnet | 1.0 | integration-pass |

Total: 7.5 units（关键路径 N1→N2/N3→N4/N5→N6 ≈ 5.5）。

## 3. Parallelism

- **Layer 1**: `[N1]` — schemas 先行（提供 dataclass）
- **Layer 2**: `[N2, N3]` — state_aggregator ∥ events（write_scope 互斥）
- **Layer 3**: `[N4, N5]` — idle_detector ∥ intake_fsm（write_scope 互斥）
- **Layer 4**: `[N6]` — join 写 integration + handoff + parent patch

最大 builder 并发 = 2（Layer 2/3）。

## 4. Dispatch Batches

- **batch-1**: `[N1]` → join_gate `[schemas-pass]`
- **batch-2**: `[N2, N3]` → join_gate `[state-aggregator-pass, events-pass]`
- **batch-3**: `[N4, N5]` → join_gate `[idle-detector-pass, intake-fsm-pass]`
- **batch-4**: `[N6]` → join_gate `[integration-pass]`

## 5. Per-Node Acceptance

### N1 schemas (write: `lib/livework/__init__.py`, `lib/livework/schemas.py`, `tests/livework/test_schemas.py`)
- 4 dataclass 齐全：`StatusExt`、`EventV2`、`RequirementIntake`、`RoleResolverView`
- 每个 dataclass 含 `schema_version: str` 字段（必填）
- `__init__.py` 导出 5 模块名（schemas/state_aggregator/events/idle_detector/intake_state_machine 占位 import 也行）
- `python -c "from harness.lib.livework import schemas"` 无异常
- `pytest harness/tests/livework/test_schemas.py -v` exit 0，≥ 8 断言
- 不出现 `coordinator` / `autopilot` / `status-server` 字串

### N2 state_aggregator (write: `lib/livework/state_aggregator.py`, `tests/livework/test_state_aggregator.py`)
- `aggregate_pane_state(events: List[EventV2]) -> PaneState`：纯函数
- `resolve_role(events, sid) -> RoleNextStep`：纯函数（相同输入 → 相同输出；不读时钟、不读文件、不读全局）
- `test_state_aggregator.py` 含 property test：对同一 events 调用两次，结果一致
- `pytest` exit 0，≥ 10 断言
- 不 import `time` / `os` / `subprocess`（除测试 fixture）

### N3 events (write: `lib/livework/events.py`, `tests/livework/test_events.py`)
- 实现 5 个 emit_* 函数，全部 append-only 写真 events.jsonl
- 不修改 coordinator.sh 的 `emit_event` 函数（只新增）
- 测试使用 `tmp_path` 真文件读写，禁 `@mock.patch`
- `pytest` exit 0，≥ 10 断言
- `grep -c '@mock.patch' tests/livework/test_events.py` == 0

### N4 idle_detector (write: `lib/livework/idle_detector.py`, `tests/livework/test_idle_detector.py`)
- 3 个函数全部把 `now: datetime` 作为显式参数，禁隐式 `time.time()` / `datetime.now()`
- `detect_deadlock` 返回 `List[DeadlockAlert]`，每个 alert 含 `pane / sprint_id / silence_seconds / threshold`
- 测试覆盖：active / idle / deadlock 三种状态；heartbeat 间隔边界（恰好 / 略过 / 远过）
- `pytest` exit 0，≥ 12 断言
- `grep -c 'time.time()' lib/livework/idle_detector.py` == 0

### N5 intake_state_machine (write: `lib/livework/intake_state_machine.py`, `tests/livework/test_intake_state_machine.py`)
- FSM 含 ≥ 5 state、≥ 7 transition、含 `rejected` 兜底转移
- `intake_requirement(text) -> SprintId` 返回新 sprint_id（不真创建文件，只返回 id 或 dataclass）
- 测试覆盖：合法路径（received → ... → dispatched）+ 异常路径（received → rejected）+ 非法 transition 拒绝
- `pytest` exit 0，≥ 12 断言
- `grep -c 'rejected' lib/livework/intake_state_machine.py` ≥ 2

### N6 integration + handoff (write: `tests/livework/test_integration_replay.py`, sprint handoff.md, parent traceability.json patch)
- `test_integration_replay.py` 用真 events.jsonl（tmp_path 写入）重放，断言：state_aggregator + idle_detector + intake_fsm 串联结果可重建
- `pytest harness/tests/livework -v` 全过，总断言 ≥ 60
- handoff.md 含：
  - 5 模块 import 示例
  - 5 outcome × 模块 × 关键 API 矩阵
  - S04 接入清单（HTTP 路由 → lib 函数；autopilot hook → detector）
  - pytest exit code + 断言数 + 已知未闭环项
  - `evaluator_can_review: true` + `s04_can_start: true`
- parent traceability.json 仅添加 `children[2].core_runtime_ready=true`（schema_version 不变；children 顺序不变）
- `jq '.children[2].core_runtime_ready' epic-*.traceability.json` == true

## 6. Routing Policy

- 所有节点 `sonnet`（GLM 1210 已 5 次 + 代码严谨性）
- 禁止 worker webfetch / web search
- 上游唯一来源：S02 architecture.md / interfaces.md / data-model.md / migration.md（5 个 .md 已 passed）
- 测试 fixture：用 `tmp_path` 真文件 IO；禁 `@mock.patch` / `unittest.mock.patch`
- 禁 import `requests` / `urllib.request` / `httpx`

## 7. Stop Rules（执行期）

- 任何节点修改 `coordinator.sh` / `autopilot.sh` / `status-server/` 现有文件 → fail (git diff)
- 模块缺 `schema_version` 字段 → fail（演进兼容）
- 测试用 `@mock.patch` 替代真 events.jsonl 写入 → fail（test_integrity）
- 实现代码 import `requests` / `urllib.request` / `httpx` → fail（no_external_io）
- N4 idle_detector 隐式调用 `time.time()` / `datetime.now()` → fail（pure_function）
- N5 intake_state_machine 缺 `rejected` 转移 → fail（FSM 完备性）
- N6 在 N1-N5 任一 pending 时 dispatched → graph_scheduler 阻断
- handoff 声称 "epic 完成" 或 "S04/S05 已就绪" → fail
- `pytest harness/tests/livework -v` 总断言 < 60 → fail

## 8. Exit Criteria

- 6 节点全 passed
- 5 个 `.py` 模块 + 6 个 `test_*.py` 齐全
- `pytest harness/tests/livework -v` exit 0，总断言 ≥ 60
- `python -c "from harness.lib.livework import schemas, state_aggregator, events, idle_detector, intake_state_machine"` 无异常
- `solar-harness doctor` exit 0
- parent traceability.json `children[2].core_runtime_ready=true`
- 不修改 `coordinator.sh` / `autopilot.sh` / `status-server/`（git diff 验）

## 9. Evaluator 复核入口

1. `ls harness/lib/livework/*.py | wc -l` ≥ 6（含 __init__.py）
2. `ls harness/tests/livework/test_*.py | wc -l` ≥ 6
3. `pytest harness/tests/livework -v` exit 0
4. `grep -c 'schema_version' harness/lib/livework/schemas.py` ≥ 4
5. `grep -c '@mock.patch\|unittest.mock' harness/tests/livework/*.py` == 0
6. `grep -E 'import requests|import urllib.request|import httpx' harness/lib/livework/*.py | wc -l` == 0
7. `grep -c 'time.time()\|datetime.now()' harness/lib/livework/idle_detector.py` == 0
8. `grep -c 'rejected' harness/lib/livework/intake_state_machine.py` ≥ 2
9. `git diff --name-only HEAD -- coordinator.sh autopilot.sh status-server/` 空
10. `jq '.children[2].core_runtime_ready' sprints/epic-*.traceability.json` == true
11. `grep -c 's04_can_start: true' sprints/*s03-core-runtime.handoff.md` == 1
12. `grep -c 'epic.*已完成\|S05.*就绪' sprints/*s03-core-runtime.handoff.md` == 0

## 10. Out of Scope

- **S04**: 把 lib 函数接入 status-server HTTP 路由 + autopilot 主循环 hook + UI 渲染
- **S05**: e2e 用户流程测试 + 负控验证 + activation-proof + 文档收尾

## 11. 当前状态说明

本切片 status = `drafting/prd_ready`（PRD 已就绪，Workflow Guard 已放行）；目标 status = `active/planning_complete`，handoff_to=`builder_parallel`。S02 已全 passed（architecture / interfaces / data-model / migration / handoff 5 文档齐），上游不阻塞。
