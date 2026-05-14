# Design — Solar-Harness Live-Work Visibility · S02 Architecture

Sprint: `sprint-20260514-p0-…-s02-architecture`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Slice: `architecture` (Planner pass)
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

S01 已经把大需求拆成 5 个 outcome（O1-O5）。S02 必须把它们落到系统分层：
- O1 status idle state — 数据/控制面分工，谁聚合 pane 状态？
- O2 autopilot 心跳 + deadlock 检测 — 心跳频率、deadlock 阈值、事件 schema
- O3 PM-first PRD 流程 — 入口 → 状态机 → 出口；和现有 intent-engine 怎么集成
- O4 status UI 每角色下一步 — 谁拥有"下一步"信息？coordinator 状态 vs traceability vs autopilot
- O5 状态转换可见证据 — events.jsonl / log line / UI 三者哪个权威

S02 **不写代码**；只产出 architecture.md / interfaces.md / data-model.md / migration.md，作为 S03/S04/S05 的设计契约。

## 2. Slice Boundaries

- **做**：5 outcome 的 control-plane / data-plane 分层、接口契约、数据模型、状态机、失败恢复、可观测性、与现有 coordinator/autopilot/status-server/intent-engine 的兼容方案。
- **不做**：实现（lib/types/schemas — S03）、autopilot/UI/pane 接入（S04）、测试/负控（S05）。
- **不允许**：声称父 epic 已完成；用"已完成"替代证据；用单文档覆盖所有实现细节。

## 3. Design Goals

| Goal | Why |
|------|-----|
| **control plane 和 data plane 显式分层** | 当前 coordinator/autopilot/status-server 边界混乱，事件流和状态读取混在一起 |
| **每个 outcome 有唯一 source-of-truth** | 否则 O1 idle 显示和 O2 autopilot heartbeat 会读到不一致的状态 |
| **接口契约可被 S03 直接编码** | 字段名 / 类型 / 错误码全部锁定，S03 builder 不需再决策 |
| **兼容现有 coordinator.sh + status-server + autopilot 主循环** | 改主循环必须 hook；不能写整段 coordinator.sh |
| **失败恢复 + 观测全覆盖** | pane crash / dispatch lost / state desync 都要有恢复路径 |

## 4. Non-Goals

- 不写 .py/.ts/.js/.sh 实现
- 不锁死内存数据结构（dataclass 实现留给 S03）
- 不设计具体 UI 渲染（HTML/CSS — S04）
- 不写 e2e 测试用例（S05）
- 不替用户决定 deadlock timeout 数值（提供建议默认值 + 配置点）

## 5. Architecture Layers (4 层)

```text
┌──────────────────────────────────────────────────────────────┐
│ Presentation: status-server /status, /research/<sid>, /role  │ ← O1, O4
├──────────────────────────────────────────────────────────────┤
│ Control: coordinator, autopilot, intent-engine, dispatcher   │ ← O2, O3, O5
├──────────────────────────────────────────────────────────────┤
│ State Aggregation: pane-state-aggregator, role-resolver      │ ← O1, O4
├──────────────────────────────────────────────────────────────┤
│ Data: events.jsonl, status.json, traceability.json, intake/  │ ← O5 (truth)
└──────────────────────────────────────────────────────────────┘
```

**铁律**：上层只读下层；data 层 append-only；state-aggregation 是纯函数（events → derived state）；presentation 不直接读 data。

## 6. Deliverables (4 文档 + 1 集成)

| # | Deliverable | Owner Node | 内容 |
|---|-------------|-----------|------|
| D1 | `…s02-architecture.architecture.md` | N1 | 4 层分层图、O1-O5 落到各层的责任分配、状态机（PRD intake → PM → planner → builder → eval）、失败恢复矩阵、观测点清单 |
| D2 | `…s02-architecture.interfaces.md` | N2 | 5 个 API 契约：(a) GET idle-state；(b) autopilot heartbeat schema；(c) deadlock event schema；(d) PRD-intake pipeline；(e) role-next-step query |
| D3 | `…s02-architecture.data-model.md` | N3 | 4 schema：(a) status.json 扩展字段；(b) events.jsonl 新事件类型；(c) requirement_intake.json；(d) role_resolver_view（derived） |
| D4 | `…s02-architecture.migration.md` | N4 | 现有 coordinator.sh / status-server / intent-engine / autopilot 主循环兼容方案；3 条降级策略；冲突清单 |
| D5 | `…s02-architecture.handoff.md` + parent traceability.json patch | N5 (join) | S03/S04 切入清单 + 已知未闭环项 + 父 traceability 加上 architecture_ready 字段 |

## 7. DAG Topology

```text
N1 architecture.md  ─┐
N2 interfaces.md     ─┤
N3 data-model.md     ─┼── N5 integration+handoff ── done
N4 migration.md      ─┘
```

4 节点完全并行（write_scope 互斥），N5 join 写 handoff + patch parent traceability。

## 8. Acceptance Contract

| # | Acceptance | 验证 |
|---|------------|------|
| A1 | architecture.md 含 4 层分层图 + 5 outcome 落到各层的责任表 + 状态机图 + 失败恢复矩阵 + 观测点清单 | grep section count |
| A2 | interfaces.md 含 5 个 API 契约（method / path / request / response / error-codes） | grep "## API" ≥ 5 |
| A3 | data-model.md 含 ≥ 4 schema（每个含字段名 / 类型 / 必填/可选 / 约束） | grep schema block ≥ 4 |
| A4 | migration.md 含 4 个兼容点（coordinator / status-server / intent-engine / autopilot）+ ≥ 3 降级策略 + 冲突清单 | grep |
| A5 | handoff.md 列出 S03 builder 切入清单（每个 outcome 一行）+ `s03_can_start:true` + `s04_blocked_until` 字段 | grep |
| A6 | 父 traceability.json children[*] 加 architecture_ready=true (only S02 row) | jq |
| A7 | 不出现 .py / .ts / .js / .sh / .sql 文件 | find |
| A8 | 不声称 "epic 已完成" 或 "S03-S05 已就绪" | grep == 0 |

## 9. Stop Rules

- 任何节点写代码扩展名 → fail
- 接口契约缺 error-codes 字段 → fail（错误处理不可缺）
- 状态机缺失败转移 → fail（observable failure 必须落到状态机）
- data-model 不指定 schema_version 字段 → fail（演进兼容）
- migration 没有降级路径 → fail（必须 fail-open）
- handoff 声称 "S03 可以直接派 builder" 而不写明 5 outcome 切入点 → fail

## 10. Parallelism & Write Scope

- **N1**: `sprints/*s02-architecture.architecture.md`
- **N2**: `sprints/*s02-architecture.interfaces.md`
- **N3**: `sprints/*s02-architecture.data-model.md`
- **N4**: `sprints/*s02-architecture.migration.md`
- **N5**: `sprints/*s02-architecture.handoff.md`, `sprints/epic-*.traceability.json` (architecture_ready 字段 only)

write_scope 完全互斥，N1-N4 安全并行。N5 join 后写 handoff + parent traceability。

## 11. Model Routing

- 所有节点 `sonnet`（架构设计 + 文档；GLM 1210 风险）
- 禁止 worker webfetch / web search
- 复用 S01 outcomes.md 作为唯一上游需求源

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| N2 interfaces 与 N3 data-model 不一致（字段名/类型分歧） | N5 join 时 cross-check：interfaces.md 中所有 response 字段必须在 data-model.md 中定义 |
| N4 migration 提出"重写 coordinator.sh"建议 | migration.md 必须只允许 hook / 追加 case；明确禁止主循环重写 |
| 状态机覆盖不全（漏 deadlock recovery） | N1 状态机必须含每个 outcome 的失败转移；evaluator grep "deadlock" |
| 父 traceability.json patch 破坏 epic-decomposer | N5 用 python json 读写，仅添加 children[1].architecture_ready 字段 |

## 13. Knowledge Context Usage

- `solar-harness context inject` 已执行：命中 `tool-plane-sandbox-routing-inventory-20260513.md`（control/data plane 命名约定）+ `sprint-20260508-data-plane-closeout-contract.md`（数据面边界）。
- S01 outcomes.md (17KB) 是唯一上游需求源；N1-N4 必须显式引用 outcome 编号。
- 现有 coordinator.sh / autopilot 主循环 不动主体，只允许 hook（沿用 sprint-20260417 集成模式）。

## 14. Handoff Plan

N5 完成后，handoff.md 必须含：

- 5 outcome × (control / state / data / presentation) 落点矩阵
- S03 builder 切入清单：每个 outcome 一行（哪个文件、哪个函数签名、依赖哪个 schema）
- S04 builder 切入清单：哪个 UI 路由、哪个 status-server endpoint
- 已知未闭环项（deadlock recovery 自动化、PM 复杂判断逻辑、可观测性 metrics 命名）
- `s03_can_start: true` + `s04_blocked_until: s03_passed` 信号
