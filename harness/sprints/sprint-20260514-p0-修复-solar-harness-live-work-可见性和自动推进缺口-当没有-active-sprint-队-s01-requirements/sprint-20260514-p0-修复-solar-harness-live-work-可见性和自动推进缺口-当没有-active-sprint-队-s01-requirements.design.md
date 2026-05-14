# Design — Solar-Harness Live-Work Visibility · S01 Requirements

Sprint: `sprint-20260514-p0-…-s01-requirements`
Epic: `epic-20260514-p0-修复-solar-harness-live-work-可见性和自动推进缺口-当没有-active-sprint-队`
Slice: `requirements` (Planner pass)
Author: Solar Planner
Date: 2026-05-14
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

Solar-Harness 当前存在两类用户可见缺口：

1. **静默空转**：没有 active sprint / 队列为空 / pane idle 时，status 页和 autopilot 仍显示"运行中"或不显示任何提示，用户误以为还在开发。
2. **半截接力**：用户提交新需求时没有强制走 PM-first PRD 流程，建设者可能直接接到任务；status 看不到 PM/Planner/Builder/Evaluator 的下一步责任人。

S01 不修代码，**只把上面这个大需求拆成可验收 outcomes、明确边界、非目标、和 epic→child traceability 矩阵**，让 S02/S03/S04/S05 能各自拿到自己那一片职责。

## 2. Slice Boundaries (本切片做什么)

- **做**：outcomes 分解、acceptance criteria、boundary/risk、non-goals、parent epic → child sprint 的 traceability 映射、明确哪些 work 不能直接派 builder。
- **不做**：架构/接口设计（S02）、核心实现（S03）、autopilot/UI 接入（S04）、端到端验证（S05）。
- **不允许**：声称父 Epic 已完成；直接绕过 planner 派 builder；用单个大 PRD 覆盖所有实现细节。

## 3. Design Goals

| Goal | Why |
|------|-----|
| **每个 outcome 独立可验收** | 防止 outcome 模糊导致 S02-S05 推诿 |
| **明确 builder-direct vs planner-required** | 防止 PM/Planner 工作（治理、需求、评估）被错派给 builder |
| **outcomes → child sprint 的 traceability 必须落到 parent traceability.json** | autopilot 和 evaluator 用它判断 epic close 条件 |
| **每个 outcome 标注上游依赖、下游影响、未闭环项** | S02 接手时不需要重新猜测范围 |

## 4. Non-Goals

- 不写 architecture.md（S02 的活）
- 不写 schemas / SQL / Python 模块（S03 的活）
- 不实现 autopilot 监控规则 / status 路由 / pane 可视化（S04 的活）
- 不写测试用例 / 负控 / smoke benchmark（S05 的活）
- 不替用户决策 stop-rule 的具体数值阈值（留给 S02 在架构里定）

## 5. Outcomes (5 个)

| # | Outcome | 关键问题 |
|---|---------|---------|
| **O1** | Status 页面在 no-active-work 状态下显式声明"no active work + next-step owner" | 现状是空白或欺骗性"运行中"；用户看不到自己是不是被卡住等待 |
| **O2** | Autopilot 在队列为空 + 所有 pane idle 时主动写一行心跳日志 + 通知用户提交需求 | 现状是 autopilot 静默休眠；用户不知道 harness 是 idle 还是 hung |
| **O3** | 用户提交新需求时自动进入 PM-first PRD 流程（不允许 builder 直接接） | 现状缺 PM-first 强制规则；intent-engine 可能直接 dispatch builder |
| **O4** | Status UI 显示当前每个角色（PM/Planner/Builder/Evaluator）的"下一步责任人 + 阻塞原因" | 现状只显示 status 字段，看不到"谁应该接手" |
| **O5** | 任何 sprint 状态转换都必须产出至少一个可见证据（log line / event / UI 更新） | 现状有些转换是隐式的；用户无法回放为什么 sprint 卡住 |

每个 outcome 在 N1 节点产出独立的 outcome card（含 acceptance / risk / boundary / dependency）。

## 6. Builder Direct vs Planner Required (Governance Boundary)

| 类型 | 是否允许 builder 直接做 | 必须先经过 |
|------|------------------------|-----------|
| 代码/实现 (lib/, types/, schemas/, tests/) | ✅ 允许 builder 接 | planner task_graph |
| status UI 路由 (status-server/) | ✅ 允许 builder 接 | planner + S02 接口契约 |
| autopilot 监控规则 (tools/, state/) | ⚠️ 半允许 | planner + S02 接口；改主循环必须 hook |
| **PM-first PRD 流程定义** | ❌ 不允许 builder 接 | PM/Planner 显式拆分 |
| **outcome 验收条件** | ❌ 不允许 builder 接 | Planner（本切片）+ Evaluator |
| **status 文案 / 用户可见错误信息** | ❌ 不允许 builder 接 | PM / Planner 拍板 |
| **stop-rule 数值阈值** | ❌ 不允许 builder 接 | S02 架构层 + 用户拍板 |
| **epic close 条件** | ❌ 不允许 builder 接 | Evaluator + Planner |

builder 接到上面 ❌ 类工作必须返工，evaluator 看到必须 FAIL。

## 7. Deliverables (本切片 3 个文档)

| Deliverable | Owner | 内容 |
|---|---|---|
| `…s01-requirements.outcomes.md` | N1 | 5 个 outcome card；每张含 acceptance / risk / boundary / dependency / 哪个 child sprint 负责 |
| `…s01-requirements.non-builder-boundary.md` | N2 | governance boundary 表 + 一份 "禁止 builder 直接接的工作清单" |
| `…s01-requirements.handoff.md` + 更新 parent `…traceability.json` | N3 (join) | outcome → child sprint 矩阵；给 S02 evaluator 的入口清单；evaluator_can_review/s02_can_start 信号 |

## 8. DAG Topology

```text
N1 outcome-decomposition  ─┐
N2 non-builder-boundary    ─┴── N3 traceability+handoff ── done
```

3 节点；N1/N2 完全并行（write_scope 互斥），N3 join 后写父 traceability。

## 9. Acceptance Contract

| # | Acceptance | 验证方式 |
|---|------------|---------|
| **A1** | 5 个 outcome 全部含 AC / risk / boundary / dependency / 负责 child sprint 字段 | grep + 字段计数 |
| **A2** | non-builder-boundary 表至少 5 行，每行含 ✅/❌ + 必须先经过谁 | grep 计数 |
| **A3** | parent `…traceability.json` children[*] 字段加上 `outcomes: [...]` 反向链接 | jq `.children[].outcomes \| length >= 1` |
| **A4** | handoff.md 列出 5 个 outcome → child sprint 矩阵 + S02 evaluator 入口 + `evaluator_can_review:true` + `s02_can_start:true` | grep |
| **A5** | 不出现新的 .py / .ts / .js / .sh / 实现细节代码 | find + ext 检查；planner 不写代码 |
| **A6** | parent 不被声称 "epic 完成" | grep "epic 完成" / "all done" == 0 |

## 10. Stop Rules

- 任何节点尝试写 `.py/.ts/.js/.sh/.sql` → fail（planner 不写代码）
- 任何节点声称 "epic 已完成" 或 "S02-S05 已就绪" → fail
- traceability.json 更新破坏 schema_version 或 children 顺序 → fail
- outcome card 缺 acceptance / risk / boundary / dependency 任一字段 → fail
- builder-direct 表格不写明 ❌ 类工作 → fail（governance 不完整）

## 11. Parallelism & Write Scope

- **N1 write_scope**：`sprints/*s01-requirements.outcomes.md`
- **N2 write_scope**：`sprints/*s01-requirements.non-builder-boundary.md`
- **N3 write_scope**：`sprints/*s01-requirements.handoff.md`, `sprints/epic-*.traceability.json`（仅 children[*].outcomes 字段）

write_scope 完全隔离，N1/N2 安全并行。N3 join 后写父 traceability，单线程。

## 12. Model Routing

- 所有节点 `sonnet`（需求建模 + 文档；GLM 1210 风险）
- 禁止 worker webfetch / web search（本切片只读 epic / contract / prd，本地决策）

## 13. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| outcome 写成"实现细节"而非"用户可见结果" | 每个 outcome card 必须含"用户看到什么" + "如何观察"两栏 |
| non-builder-boundary 表太抽象 | 每行必须举一个具体反例（"如果 builder 接了 X 会怎样"） |
| traceability.json 更新破坏 epic decomposer 兼容 | N3 用 python json 读写，保留原 schema_version + children 顺序，只 patch outcomes 字段 |
| 三个 N 都很短 builder pane 浪费 | 模型默认 sonnet 不抢 GLM 配额；N1/N2 并行 ≤ 5 分钟 |

## 14. Knowledge Context Usage

- `solar-harness context inject` 已执行：命中之前 deepresearch S01 通过的模式（`sprint-20260513-…-s01-requirements-accepted.md`），结构复用。
- mirage_path 命中：epic-decomposition-runtime-20260513.md 中关于"5 slice 拆分"的标准。
- Solar DB 未额外查询（本地决策不需 cortex）。

## 15. Handoff Plan

N3 完成后，handoff.md 必须含：

- 5 outcome → child sprint 矩阵
- 给 S02 evaluator 的 "outcome AC 复核入口" 清单
- builder-direct vs planner-required boundary 摘要
- 已知未闭环项（autopilot 主循环改动范围 / status UI 端口冲突 / PM-first 与现有 intent-engine 集成）
- `evaluator_can_review: true` + `s02_can_start: true`
