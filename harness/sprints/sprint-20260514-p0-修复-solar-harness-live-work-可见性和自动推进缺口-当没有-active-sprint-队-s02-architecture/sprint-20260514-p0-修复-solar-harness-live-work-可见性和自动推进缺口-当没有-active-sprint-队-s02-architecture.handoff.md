# Handoff — Solar-Harness Live-Work Visibility & Auto-Progression Fix · S02 Architecture

Sprint: `sprint-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队-s02-architecture`
Node: N5 (join)
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

---

## 5-Outcome × 4-Layer Endpoint Matrix

| Outcome | Presentation | Control | State Aggregation | Data |
|---------|--------------|---------|-------------------|------|
| **O1: Idle State** | `GET /api/idle-state` → renders "No Active Work" with last-completed timestamp, sprint count, submit prompt. Cache invalidated on sprint status transition. | Coordinator appends idle-state detection block after sprint scanner (~line 4523). Emits `sprint_completed` event triggering re-evaluation. | `idle_detector(query_depth, active_panes) -> {is_idle, idle_since, last_completed, total_completed}`. Pure function from events.jsonl. | `events.jsonl`: `state_transition` events. `status.json`: `idle_state` field. Schema: A (status.json extension) |
| **O2: Heartbeat + Deadlock** | Status page reads `active_deadlocks[]` from State Aggregation. Renders alert indicator. | Autopilot appends heartbeat post-scan (max 1/300s). Deadlock check: `dispatch_sent_ts` vs `session_started_ts`, default 600s timeout. | `deadlock_detector(dispatches, sessions) -> {deadlocks[], healthy_panes[]}`. Compares timestamps per pane. | `events.jsonl`: `autopilot_heartbeat`, `pane_deadlock` events. Schema: B (events.jsonl new types) |
| **O3: PM-First PRD Flow** | Returns sprint_id confirmation + phase. Shows "PM Analysis" with next step on status page. | `POST /api/requirements` entry point. Flow: capture → PM draft → planner review → task graph → builder dispatch. Rejects vague (<50 chars). | `phase_deriver(sprint_id) -> {phase, next_step}`. Reads latest `role_transition` event. | `intake/requirement_intake.json` per submission. Schema: C (requirement_intake.json) |
| **O4: Next-Step Display** | Renders per-sprint card: phase label, next step, node progress. Collapses completed sprints. | Coordinator writes phase transitions to session log. Task graph node status updates via `state_transition` events. | `role_resolver(sprint_id) -> {phase, nodes[], next_action, gate_status}`. From task_graph.json + latest transition events. Schema: D (role_resolver_view) | `status.json` phase field. `traceability.json` node status. `events.jsonl` transition events. |
| **O5: Transition Evidence** | CLI: `solar-harness sprint transitions --sid <id>`. Optional status page timeline. | Coordinator writes `state_transition` events on every phase change. Deduplicates consecutive same-state. | `transition_aggregator(sprint_id) -> [{timestamp, actor, from, to, reason}]`. Queries events.jsonl by sprint_id + event_type. | `events.jsonl`: `role_transition` events (schema_version 1.0.0). SQLite index on `(sprint_id, event_type, timestamp)`. |

---

## S03 Builder Entry Checklist

| # | Outcome | File | Function Signature | Dependent Schema |
|---|---------|------|-------------------|-----------------|
| 1 | O1 Idle State | `lib/idle_detector.py` (new) | `def compute_idle_state(queue_depth: int, active_panes: list[str], last_completed_event: dict | None) -> dict` | Schema A (status.json extension fields) |
| 2 | O1 Idle State | `lib/status_json_ext.py` (new) | `def patch_status_json_idle(status_path: str, idle_result: dict) -> None` | Schema A |
| 3 | O2 Heartbeat | `lib/autopilot.py` (extend) | `def emit_heartbeat(last_emit_ts: float, interval_sec: int = 300) -> bool` | Schema B (autopilot_heartbeat event) |
| 4 | O2 Deadlock | `lib/autopilot.py` (extend) | `def check_deadlock(dispatch_id: str, pane_id: str, deadline_sec: int = 600) -> dict | None` | Schema B (pane_deadlock event) |
| 5 | O3 PM-First | `lib/requirement_capture.py` (new) | `def capture_requirement(raw: str, source: str, submitted_by: str) -> dict` | Schema C (requirement_intake.json) |
| 6 | O3 PM-First | `lib/pm_pipeline.py` (new) | `def validate_requirement(raw: str) -> dict` (returns `{valid, error_code, error_message, hint}`) | Schema C |
| 7 | O4 Next-Step | `lib/role_resolver.py` (new) | `def resolve_role_view(sprint_id: str, task_graph_path: str, events_path: str) -> dict` | Schema D (role_resolver_view) |
| 8 | O5 Transitions | `lib/transition_query.py` (new) | `def query_transitions(sprint_id: str, events_path: str) -> list[dict]` | Schema B (role_transition event type) |
| 9 | O5 Transitions | `coordinator.sh` (append) | Case block appending `role_transition` event to events.jsonl on every state change | Schema B base fields |

---

## S04 Builder Entry Checklist

| # | Outcome | UI Route | Endpoint | Data Source |
|---|---------|----------|----------|-------------|
| 1 | O1 Idle State | `/status` (main page) | `GET /api/idle-state` | State Aggregation → `idle_detector()` |
| 2 | O2 Deadlock Alerts | `/status` (alert banner) | Internal: reads `active_deadlocks` from State Aggregation | State Aggregation → `deadlock_detector()` |
| 3 | O3 Requirement Submit | `/status` (submit form) | `POST /api/requirements` | Control → `requirement_capture()` |
| 4 | O4 Sprint Cards | `/status` (per-sprint card) | `GET /api/sprints/{sid}/next-step` | State Aggregation → `role_resolver()` |
| 5 | O5 Transition Timeline | `/sprint/{sid}` (detail page) | CLI: `solar-harness sprint transitions --sid <id>` | State Aggregation → `transition_aggregator()` |

---

## Known Unresolved Items

1. **Deadlock auto-recovery not implemented**: v1 only supports detection + alerting. Re-dispatch to a different pane is deferred to a future sprint. (O2 boundary, architecture.md Layer 3)

2. **PM validation heuristic is simplistic**: `< 50 chars` and `missing goal/acceptance` is a rough filter. Complex requirements that are short but clear may be falsely rejected. The `hint` field in Schema C mitigates this. (O3 risk, outcomes.md)

3. **Cache invalidation latency**: Status-server cache has up to 60s staleness (metric M7). Phase transitions may take up to 30s to reflect (1 wake cycle). If both thresholds are hit simultaneously, user sees stale data for up to 90s. (O1/O4 risk)

4. **events.jsonl write concurrency**: Coordinator and autopilot are separate processes appending to the same JSONL file. `flock` is specified in migration.md (conflict C5) but macOS `flock` behavior differs from Linux. Needs testing. (migration.md C5)

5. **Intent-engine pattern overlap**: PM-first capture pattern `(我要|帮我|做个|写个|开发|实现|修复|新增)` overlaps with existing sprint-intent patterns. Priority ordering is specified but untested in production. (migration.md CP-3)

6. **SQLite index for O5 not yet created**: `CREATE INDEX idx_events_sprint_type_ts ON events(sprint_id, event_type, timestamp)` needs to be added during S03 migration. Without it, transition queries will be slow on large event logs. (data-model.md Schema B)

---

## Deliverable Inventory

| # | Deliverable | Node | File | Status |
|---|-------------|------|------|--------|
| D1 | architecture.md | N1 | `…s02-architecture.architecture.md` | reviewing |
| D2 | interfaces.md | N2 | `…s02-architecture.interfaces.md` | reviewing |
| D3 | data-model.md | N3 | `…s02-architecture.data-model.md` | reviewing |
| D4 | migration.md | N4 | `…s02-architecture.migration.md` | reviewing |
| D5 | handoff.md + traceability patch | N5 | `…s02-architecture.handoff.md` + epic traceability | this file |

---

## S03/S04 Readiness Signals

```
s03_can_start: true
s04_blocked_until: s03_passed
```

S03 core-runtime can begin immediately. S04 orchestration-ui is blocked until S03 passes evaluator review, because S04 depends on the runtime endpoints that S03 implements (idle-state, requirement capture, role resolver, transition query).

---

## Scope Change Requests

None. All work completed within write scope.
