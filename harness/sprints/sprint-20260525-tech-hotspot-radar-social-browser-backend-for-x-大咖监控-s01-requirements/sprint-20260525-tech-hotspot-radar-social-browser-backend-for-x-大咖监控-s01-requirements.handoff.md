---
sprint_id: sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements
epic_id: epic-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控
node: N4_traceability_handoff
slice: requirements
round: 1
generated_at: 2026-05-28T22:40:00Z
hard_blocker:
  upstream: sprint-20260525-browser-agent-global-operator-cutover
  status: blocked_until_upstream_passed
---

# Handoff — S01 Requirements 追踪矩阵 (N4_traceability_handoff)

聚合节点。汇总 N1-N3 三个 requirements 节点的产出，写出 epic→sprint→outcome 追踪矩阵
(`traceability.json`)，并把 O10 (Non-goals 聚合) 在本节点落入。S01 切片为需求拆解，**不含任何实现**；
全部 10 个 outcome builder_eligible=false。

## Hard Blocker 显式声明

- **upstream**: `sprint-20260525-browser-agent-global-operator-cutover`
- **status**: `blocked_until_upstream_passed`
- **等价解除条件**: Browser Agent 全局物理算子可通过 Solar scheduler/operator runtime 申请 browser lease，
  并能执行 open / wait / scroll / dom-extract / screenshot / close 等物理动作。
- **影响**: 上游 passed 前，本 epic 所有下游 sprint (S02-S05) 保持 blocked/pending，不派发 builder。
- 由 outcome **O9** (Hard blocker enforcement, AC-O9-1..4) 形式化承载。

## N1-N3 摘要

| 节点 | 状态 | 交付物 | Outcomes | AC 数 |
|---|---|---|---|---|
| N1_backend_operator_ratelimit | passed | `requirements.backend_operator_ratelimit.md` (227 行) | O1 Backend Operator Selection / O2 Browser Physical Operator / O3 Rate Limiting | 13 (O1=3, O2=3, O3=7) |
| N2_extraction_dedup_downstream | passed | `requirements.extraction_dedup_downstream.md` (338 行) | O4 Data extraction (11 字段) / O5 Dedup (2 key) / O6 Downstream 10 步链路 | 19 (O4=5, O5=4, O6=10) + 4 cross-outcome (AC-X) |
| N3_cli_webui_blocker | passed | `requirements.cli_webui_blocker.md` (433 行) | O7 CLI (2 命令 + auto 降级) / O8 WebUI Status (7 指标) / O9 Hard blocker enforcement | 12 (O7=4, O8=4, O9=4) |

- N1: backend 顺序 browser > rss > manual > x_api(optional)；Browser 6 能力经 Solar 全局算子；rate limiting 5 子项；builder_eligible=NO。
- N2: post 11 字段 schema + collection_backend=browser_agent；dedup key = canonical URL 或 sha256(author_handle+normalized_text+visible_time)；10 步下游链路复用现有 ThunderOMLX/Qwen3.6；3 个 open question 上交 S02。
- N3: CLI `collect-social --backend browser|auto`，auto 降级 browser→rss→manual/no-op；WebUI 7 指标 + "no data yet" 降级文案；x_api 仅在 token 存在且显式 `--ack-x-api-cost` 时启用；3 个 open question 上交 S02。

## traceability.json — 12 字段聚合

`sprints/{SID}.traceability.json` 含 12 个必填顶层字段 (+ aggregate_summary)：
`sprint_id / epic_id / node / generated_at / outcomes / outcome_dependency_matrix /
non_goals_aggregate / builder_forbidden_aggregate / downstream_sprint_kickoff_package /
hard_blocker / open_questions / files_touched`。

- **outcomes**: 10 条 (O1-O10)，每条含 outcome_id / title / prd_ac / priority / acceptance_count / downstream_sprints / builder_eligible=false / blocked_by。
- **non_goals_aggregate**: 12 条 (≥10)，含 NG-1 不全网 X 爬虫 / NG-2 不绕风控 / NG-6+NG-7 不重复 Browser 系统 / NG-8 不重复 ThunderOMLX 实例 / NG-4 不把 X API 当默认 backend。
- **outcome_dependency_matrix**: O9 gating O1-O8；O10 cross-cutting。
- **builder_forbidden_aggregate**: global_builder_eligible=false + forbidden_until + forbidden_actions。
- **open_questions**: 6 条 (OQ-N2-01/02/03 + OQ-N3-01/02/03)，owner=S02。
- **aggregate_summary**: total_outcomes=10, total_acceptance_criteria=56, builder_eligible_outcomes=0。

## S02 启动 checklist (downstream_sprint_kickoff_package)

S02_architecture 需在上游 blocker 解除后作出以下决策 (摘自 traceability.downstream_sprint_kickoff_package)：

- [ ] Browser Agent **lease 申请**协议 (timeout / retry / queue / release) — 解 OQ-N3-02 operator_ready 探针
- [ ] **dedup 实现**位置 (extraction-time / ingest-time / excluded) — 解 OQ-N2-01，从 N2 §7.2 A/B/C + kill_criteria 选型
- [ ] dedup 观测落表 — 解 OQ-N2-02
- [ ] Knowledge/_raw/social raw 路径规约 — 解 OQ-N2-03
- [ ] **CLI 入口** (scripts/tech_hotspot_radar.py argparse 接入点) — 解 OQ-N3-01，从 N3 §7.2 CLI A/B/C 选型
- [ ] **WebUI 集成**点 (复用现有 dashboard，不新增 Web 框架) — 解 OQ-N3-03，从 N3 §7.2 WebUI A/B/C 选型
- [ ] tier1/tier2 scan frequency / cooldown 具体值 (N1 deferred)
- [ ] model_call_ledger.origin 列存在性检查 + 必要 migration 决策 (N2 risk #5/#7)

S03/S04/S05 的 kickoff 决策项见 traceability.json 对应小节。

## Changed Files

| 文件 | 操作 | 目的 |
|---|---|---|
| `sprints/{SID}.traceability.json` | new | 12 字段 epic→sprint→outcome 追踪矩阵 (本节点核心交付物) |
| `sprints/{SID}.handoff.md` | new (本文件) | sprint 级聚合 handoff：N1-N3 摘要 + S02 启动 checklist + hard blocker 声明 |
| `sprints/{SID}.N4_traceability_handoff-handoff.md` | new | 节点闭环 handoff (sibling，Work Step 4 约定) |

## Verification Evidence

实际执行命令与结果：

```bash
# 1. AC id 提取 (per requirements doc)
grep -oE 'AC-?O?[0-9X]+-?[0-9]*' requirements.backend_operator_ratelimit.md
  → O1=3 (AC-O1-1..3), O2=3 (AC-O2-1..3), O3=7 (AC-O3-1..7) = 13 ✓ (与 N1 handoff 一致)
grep ... requirements.extraction_dedup_downstream.md
  → O4=5, O5=4, O6=10; cross AC-X-1..4
grep ... requirements.cli_webui_blocker.md
  → O7=4, O8=4, O9=4

# 2. open question 提取
  → OQ-N2-01/02/03, OQ-N3-01/02/03 = 6

# 3. task_graph node 状态
python3 -c "json.load(...)"
  → N1 passed / N2 passed / N3 passed / N4 dispatched ✓ (依赖全 passed)

# 4. traceability.json schema 自校验
python3 -c "json.load(...)"
  → JSON OK; top-level fields=12 (+aggregate_summary); outcomes=10 (O1-O10);
    all builder_eligible=false=True; all required outcome keys present=True;
    non_goals=12 (>=10); hard_blocker upstream/status 正确;
    kickoff sprints=S02/S03/S04/S05; S02 decisions=8; open_questions=6
```

## Capability / KB Usage Evidence

- **[harness-knowledge]** `solar-harness context inject` — 复用 dispatch 注入的 `<solar-runtime-context>` (mirage:timeout degraded → QMD / Solar DB / Obsidian fallback)。本节点事实来源为 PRD / epic / N1-N3 handoff / 3 份 requirements doc，非 KB recall；KB 仅作上下文投影。
- **[harness-graph]** 读取 task_graph 节点状态 (N1-N3 passed)；最后一步 `graph-scheduler mark` 将 N4 置 reviewing。
- dispatch required skills `workflow.planning` / `documentation` / `traceability.aggregation` — 被本节点的聚合/起草工作直接使用。
- **未使用** (出现在 dispatch required_capabilities 但本聚合节点未真用)：`browser.browse` / `browser.qa` / `code.review` / `test.tdd` / `research.*` / `analysis.causal_inference` / `agents_sdk.*` — 本节点不跑 browser、不跑测试、不写代码、不做研究；这些是父 sprint 通用注入项，不是本节点实际工作。不把"被注入"当成"已使用"。

## Scope Compliance

- **Write Scope** (dispatch line 176-177): `sprints/{SID}.traceability.json` + `sprints/{SID}.handoff.md` — 两者均已写 ✓
- **Sibling 工件**: `sprints/{SID}.N4_traceability_handoff-handoff.md` (Work Step 4 显式要求的节点闭环 handoff，与 N1-N3 节点 handoff 处理方式一致)
- **Read Scope** (dispatch line 168-172): 3 份 requirements doc + prd.md + contract.md + epic.md — 均已读 ✓
- **未碰**: lib/、scripts/、tests/、migrations/、templates/、Knowledge/、其他 sprint 文件
- **未把 parent sprint / epic 标 passed**
- **Scope Change Request**: 无

## Architecture Guard Compliance

- package_boundary = `['sprints/{SID}.traceability.json', 'sprints/{SID}.handoff.md']`；本节点只写这两类 + sibling handoff，不触 protected core，不需 `core_patch_allowed`。
- guard_warnings / guard_errors: none。
- 非 online-exploration 节点 (纯聚合)；不涉及 ≥2 候选/kill_criteria 要求。下游选型候选 (dedup / CLI / WebUI) 已由 N2/N3 §7.2 提供，本节点转载到 kickoff package。

## Known Risks

1. **上游 hard blocker 未解除**：`sprint-20260525-browser-agent-global-operator-cutover` 当前状态未确认 passed；S02-S05 全部 blocked，本追踪矩阵无法被下游消费直到解除。
2. **6 个 open question 仍待 S02 决议**：dedup 实现位置 / 观测落表 / Knowledge raw 路径 / CLI 入口 / operator_ready 探针 / WebUI 接入点。
3. **per-outcome priority 为聚合推导值**：PRD 未对每个 outcome 单列优先级；traceability 中 priority (P0/P1) 依据依赖关键度 + epic P0 推导，S02 可重定级。
4. **N2 cross-outcome AC-X (4 条) 未计入 per-outcome acceptance_count**：total_acceptance_criteria=56 仅含 outcome-specific AC；AC-X-1..4 为跨 outcome 约束，单独存在于 N2 doc。
5. **metrics N/A vs 0 语义**：N2 risk #3 登记，AI Influence 报告聚合口径需 S04/S05 显式约束，本节点未替其决定。

## Not Done

- 未替 S02 决定任何 open question (越权)。
- 未派发任何 builder (全 outcome builder_eligible=false；上游 blocker 未解除)。
- 未实现 CLI / WebUI / dedup / extraction / 下游链路任何代码 (S01 为需求切片)。
- 未跑任何 browser lease / SQL / 模型调用。
- 未触 epic-20260525 sibling sprint (browser-agent-global-operator-cutover) 任何文件。
- 未把 parent sprint / epic 标 passed。

Knowledge Context: solar-harness context inject used (dispatch-injected; mirage degraded → QMD/Solar DB/Obsidian fallback)
Harness Modules Used: harness-knowledge (Read: prd/epic/contract/3 requirements docs/3 node handoffs), harness-graph (task_graph read + mark-reviewing 最后一步)
