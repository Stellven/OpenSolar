# Design — Requirement Compiler Quality Loop

sprint_id: `sprint-20260523-requirement-compiler-quality-loop`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-24T03:55:00Z`
knowledge_context: `solar-harness context inject used (mirage nonzero -> qmd/obsidian/solar_db fallback)`
peer_sprint: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`（并行；本 sprint 是 quality loop，对 backend compiler 输出做闭环评估）
downstream_blocker_for: `sprint-20260523-agent-plan-optimizer-foundation`（本 sprint 必须 finalized 才能解锁 APO N0 gate）

## 0. 本切片的边界（强制 read-first + wake violation 修复）

- **Wake guard 已报**：`violations=["invalid_task_graph:node_S1_missing_write_scope"]` — 现有 task_graph.json 是 generic boilerplate（与 backend-foundation 同样问题）。本轮 **重写 task_graph** 为 PRD goal 要求的 6 元素 quality loop 节点。
- **P0 quality loop sprint**：建立 PM pane / Requirement Compiler 的质量闭环（golden set + failure replay + planner diff feedback + evaluator rejection feedback + compile quality metrics + gate）。**实际 quality loop 代码归 follow-up sprint**；本 sprint 仅产 schema / spec / 评估方法 design。
- **允许 Write/Edit**：
  - `sprints/<sid>.{design, plan, task_graph, planning_html}.{md,json,html}`（本轮）
  - `sprints/<sid>.workstream-N{1..6}-*.md`（N1..N6 产出）
  - `sprints/<sid>.golden-set-spec.md`（N1 必交）
  - `sprints/<sid>.quality-metrics-spec.md`（N5 必交）
  - `sprints/<sid>.e2e-quality-trace.md`（N6 必交）
  - `~/.solar/harness/schemas/compile-quality-metrics.schema.v1.draft.json`（N5 必交）
  - `~/.solar/harness/schemas/feedback-event.schema.v1.draft.json`（N3+N4 必交）
- **严格禁止**（per Contract Stop Conditions + 兼容承诺 + invariants）：
  - 把 doc-only / contract-only 冒充 implemented（**PRD core 红线**）
  - 绕过 PM → Planner → Builder 主链
  - 修改 Requirement IR schema（本 sprint 只消费，不重定义 — peer sprint backend-foundation 定）
  - 真改 `lib/*.py` / `validate.sh`（本 sprint design only；实际代码归 follow-up）
  - 改 `apps/pm-pane/**` UI（contract allowed_paths 含 apps/pm-pane/** 但 PRD non-goals 明示「不在首批做 4 区 PM pane UI 重构」）
  - mutate peer sprint backend-foundation 任何 artifact（与之**并行**而非 mutate）
  - mutate APO sprint artifact（本 sprint 是 APO predecessor，不动 APO 自己 spec）
  - mutate 其他 in-flight sprint artifact
  - 改 `~/.solar/STATE.md` / epic.* / `infra/prod/**` / `.env*` / `secrets/**`（per forbidden_paths）
  - 写 raw secret / token / cookie
  - 缺 verifier 决策标 DONE（per stop_conditions）
  - 缺可验证 acceptance 标完成（per stop_conditions）
- 知识库降级 `mirage:nonzero`：本 sprint self-contained。

## 1. Quality Loop 6 元素（per PRD problem statement）

```
                                       ┌──────────────────────┐
                                       │  Requirement IR      │
                                       │  (peer sprint 定;     │
                                       │   本 sprint 只消费)   │
                                       └──────┬───────────────┘
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       ▼                      ▼                      ▼
              ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
              │ 1. Golden Set  │    │ 2. Failure     │    │ 3. Planner Diff│
              │ (黄金需求 fixture │    │    Replay      │    │    Feedback    │
              │  分 source/type/ │    │ (误分类/误编译  │    │ (planner 修改 IR│
              │  edge case)     │    │  case 收集 →    │    │  时回流差异作   │
              │                 │    │  replay 套件)   │    │  训练信号)      │
              └────────┬────────┘    └────────┬───────┘    └────────┬───────┘
                       │                      │                     │
                       │                      ▼                     │
                       │            ┌────────────────┐               │
                       │            │ 4. Evaluator   │               │
                       │            │    Rejection   │               │
                       │            │    Feedback    │               │
                       │            │ (evaluator 驳回 │               │
                       │            │  原因结构化回流) │               │
                       │            └────────┬───────┘               │
                       │                      │                     │
                       └──────────────────────┼─────────────────────┘
                                              ▼
                                ┌──────────────────────────┐
                                │ 5. Compile Quality        │
                                │    Metrics + Gate         │
                                │  (定义 metric / 阈值 /     │
                                │   gate 阻断条件)           │
                                └────────────┬──────────────┘
                                             ▼
                                ┌──────────────────────────┐
                                │ 6. E2E Quality Loop       │
                                │    Walkthrough            │
                                │  (用 golden case 跑通      │
                                │   collect→replay→diff→     │
                                │   reject→metric→gate)      │
                                └──────────────────────────┘
```

## 2. Golden Set（N1 产出）

`sprints/<sid>.golden-set-spec.md` 必须定义 ≥20 个 golden case，分布：

| Source × Type | delivery | research | strategy |
|---------------|----------|----------|----------|
| verbal | 3+ | 2+ | 1+ |
| codex-pm-router | 3+ | 2+ | 1+ |
| pm-template | 2+ | 1+ | 1+ |
| chain-watcher | 1+ | 1+ | 1+ |

每个 golden case 含：

- `case_id`
- `source` / `type`
- `raw_input`（原始用户/router 输入）
- `expected_ir`（标准 IR JSON — peer sprint backend-foundation 的 schema v1）
- `expected_prd_keysections`（编译后 PRD 必含的关键段落）
- `expected_acceptance_count`（acceptance row 数）
- `expected_classification`（source/type 是否正确推断）
- `edge_case_flags[]`（缺字段 / secret / invalid / multilingual / very-long etc.）
- `ground_truth_author`（PM 或 evaluator 标注者）
- `golden_set_version`

**禁止 raw secret 字面**：edge case 若需测 secret reject，用 placeholder `<REDACTED_API_KEY_TEST_FIXTURE>`，schema 应 catch placeholder 并标 PASS。

## 3. Failure Replay（N2 产出）

`sprints/<sid>.workstream-N2-failure-replay.md` 必须定义：

**收集策略**：

- Real-world 失败 case 来自 `events.jsonl` 中 `event in {prd_gate_fail, compile_error, planner_diff_high, evaluator_rejected, validate_fail}`
- 自动 archive 到 `sprints/<sid>.failure-replay/<case_id>.json`
- 每条 entry 含：`sprint_id` / `failure_kind` / `raw_input` / `attempted_ir` / `expected_ir` / `diff` / `human_label`（误分类 / 误编译 / 字段缺失 / secret leak / 其他）

**Replay 套件**：

- `python3 -m requirement_compiler_quality.replay --case <case_id>` 重跑 compiler
- 输出 `replay_result.json`：`pass/fail` + diff + 关键字段对比
- 累积 statistics → quality metrics（per §5）

**误分类 vs 误编译 区分**：

| 错误类 | 定义 | 修复方向 |
|--------|------|---------|
| 误分类（misclassification）| source/type/severity 推断错 | adapter rule 调整 |
| 误编译（miscompilation）| 字段提取错 / 模板替换错 / acceptance 漏映射 | compiler rule 调整 |
| 字段缺失（missing_field）| 必填字段被填 default | prompt-back 策略增强 |
| Secret leak | secret 进 IR | schema reject 增强 |

## 4. Planner Diff Feedback（N3 产出）

`sprints/<sid>.workstream-N3-planner-diff-feedback.md` + `schemas/feedback-event.schema.v1.draft.json` 必须定义：

**Diff 收集时机**：

- planner 在产 design.md/plan.md/task_graph.json 时，若**修改了 PM 编译出的 PRD**（grep 编译 vs planner 写出的差异），自动捕获 diff
- diff 落 `sprints/<sid>.planner-diff/<round>.diff`
- 同时写 `feedback-event.json`：`{event_type: planner_diff, source_field: ir.acceptance[2], original_value, planner_modified_value, reason: planner-supplied}`

**回流通道**：

- diff 累积到 `requirement_compiler_quality/planner_diff_log.jsonl`
- 每周/每月 reporter 聚合高频 diff 字段 → 提示 PM 该字段编译规则需调整
- **不允许自动改 compiler rule**（C9 deterministic + 人工 review）

**Schema feedback-event.v1**:

```json
{
  "schema_version": "feedback-event.v1",
  "event_id": "fe-<ts>-<sha8>",
  "event_type": "planner_diff | evaluator_reject | golden_set_violation | replay_fail",
  "sprint_id": "<sid>",
  "ir_path": "ir.acceptance[2].criterion",
  "original_value": "<truncated/hashed>",
  "modified_value": "<truncated/hashed>",
  "actor": "planner | evaluator | pm | autopilot",
  "reason": "<short explanation>",
  "severity": "info | warn | error",
  "ts": "<ISO 8601>"
}
```

**Secret-safe**：original_value / modified_value 必须 truncate ≥256 chars + secret regex scrub。

## 5. Evaluator Rejection Feedback（N4 产出）

`sprints/<sid>.workstream-N4-evaluator-rejection-feedback.md` 必须定义：

**驳回原因结构化**：

- evaluator 在产 `<sid>.eval.json` 时必须含 `rejection_reasons[]`（schema-driven，非自然语言）
- 每条 rejection_reason 含：`{ir_field, expected, actual, severity, suggested_fix}`
- 落 `sprints/<sid>.evaluator-reject-log.jsonl`

**回流通道**：

- 累积到 `requirement_compiler_quality/evaluator_reject_log.jsonl`
- reporter 聚合高频驳回原因 → 提示 compiler / golden set 需扩展
- **不自动改 IR schema**（与 C9 同款守则）

**Schema 复用 N3 feedback-event.v1**（event_type = `evaluator_reject`）。

## 6. Compile Quality Metrics + Gate（N5 产出）

`schemas/compile-quality-metrics.schema.v1.draft.json` + `sprints/<sid>.quality-metrics-spec.md` 必须定义 10 项 metric：

| Metric | 公式 | 数据源 | Gate 阈值（default）|
|--------|------|--------|--------------------|
| `golden_set_pass_rate` | passed_cases / total_cases | replay 跑 golden set | ≥ 0.95 |
| `field_coverage_rate` | filled_fields / total_required_fields | IR schema validate | ≥ 0.98 |
| `acceptance_coverage_rate` | acceptance_mapped_to_validation / total_acceptance | grep mapped_to[] | = 1.00 (hard) |
| `secret_leak_rate` | secret_detections / total_cases | secret scan in IR | = 0 (hard) |
| `planner_diff_rate` | diff_events / planner_runs | feedback-event log | ≤ 0.30 |
| `evaluator_reject_rate` | reject_events / evaluator_runs | reject-log | ≤ 0.20 |
| `replay_consistency_rate` | byte-exact repeat / total replays | replay log | ≥ 0.99 |
| `misclassification_rate` | misclass_cases / total_cases | human-labeled | ≤ 0.05 |
| `miscompilation_rate` | miscompile_cases / total_cases | human-labeled | ≤ 0.10 |
| `evidence_ledger_completeness` | research-type with ledger / total research | ledger dir check | = 1.00 (hard) |

**Gate 行为**：

- `validate.sh` 增强（spec only，本 sprint 不真改）：跑 quality metrics 计算 + 阈值校验
- 任一 hard metric 不达标 → `fail-loud + 立即阻断派单`
- 任一 soft metric 不达标 → warn + record + 不阻断

**Mode 切换**：

- `--strict-quality`：所有 metric 都 hard 阻断
- 默认：只 hard 4 项（acceptance_coverage / secret_leak / evidence_ledger / replay_consistency）

## 7. E2E Quality Loop Walkthrough（N6 产出，JOIN）

`sprints/<sid>.e2e-quality-trace.md` + `sprints/<sid>.workstream-N6-e2e-quality.md` 必须含：

用 1 个 golden case 做 design-time walkthrough：

```
Step 1: 选 1 个 golden case (e.g., verbal-delivery-edge-001)
Step 2: 用 peer sprint backend-foundation 的 compiler 编译 → IR
Step 3: 把编译结果 IR 与 expected_ir diff → 验证 PASS/FAIL
Step 4: 模拟 planner 修改 (planner_diff) → 触发 feedback-event
Step 5: 模拟 evaluator reject (rejection_reason) → 触发 feedback-event
Step 6: 计算 10 quality metrics → 跑 gate 校验
Step 7: 输出 quality report
```

**不真跑 compiler 代码**（peer sprint backend-foundation 的 compiler 实际归 follow-up）；只做 design-time walkthrough。

## 8. 与 peer sprint backend-foundation 关系

| 维度 | backend-foundation | quality-loop (本 sprint) |
|------|---------------------|-------------------------|
| 焦点 | IR schema + 4 adapter + deterministic compiler + gate enhancement + backward compat | golden set + failure replay + planner/evaluator feedback + quality metrics + gate |
| 输出方向 | 产 IR + 4 outputs | 评估 IR + 4 outputs 的质量 |
| 依赖关系 | 本 sprint 消费 backend-foundation 的 IR schema | 本 sprint 输出 feedback 给 backend-foundation（下一轮 prompt-back） |
| 并行可行 | 是（两 sprint 都 design-only spec，无 race） | 是 |

本 sprint **不 mutate** backend-foundation 任何 artifact；只 read-only 引用其 IR schema + compiler rules。

## 9. 与 APO sprint 关系（downstream blocker）

本 sprint 是 `sprint-20260523-agent-plan-optimizer-foundation` 的 **predecessor 2**：

- APO sprint N0 dependency_gate_check 等本 sprint 进入 `finalized/accepted`
- 本 sprint 不动 APO artifact；只产物 quality metric + golden set → APO 后续 cost model 可以用 metric 数据作 cost factor

## 10. 兼容性（per Contract invariants + C1 + 非 goals）

- 不重定义 Requirement IR schema（peer backend-foundation 拥有）
- 不重写 PM pane UI（PRD non-goal §1）
- 不绕过 PM → Planner → Builder 主链（PRD non-goal §2）
- 不破坏现有 validate.sh exit code 语义
- 不引入新 PyPI 依赖（沿用 backend-foundation C6 约束）
- 不写 /tmp（沿用 backend-foundation C7）
- secret 不入 feedback event / golden case raw input（contract forbidden_paths + invariants）

## 11. 非目标

- 不重定义 IR schema（peer sprint 范围）
- 不重写 PM pane UI（PRD non-goal）
- 不绕过 planner 直派 builder
- 不真改 lib/ / validate.sh / apps/pm-pane（本 sprint design only）
- 不 mutate peer sprint / APO sprint / 其他 in-flight sprint artifact
- 不自动改 compiler rule 或 IR schema（diff/reject 回流仅 prompt 人工 review）
- 不允许 doc-only/contract-only 冒充 implemented（**PRD core 红线**）
- 不允许缺 verifier decision 标 DONE（contract stop_conditions）
- 不允许 secret 入 feedback event / golden case raw input / replay log
- 不写 /tmp
- 不动 `~/.solar/STATE.md` / epic.* / forbidden_paths
- 不使用乐观词

## 12. 接力 evaluator / APO sprint

evaluator 必须按 PRD §9 acceptance 逐项核 + Contract invariants：

- 6 件 spec 草案 + 6 workstream md + golden-set-spec + quality-metrics-spec + e2e-quality-trace + 2 schema 草案
- golden set ≥20 case + 12 cell 分布
- 10 quality metric + 4 hard 阈值
- feedback-event schema secret-safe
- 不 mutate peer / APO / in-flight sprint
- 不真改 lib / validate.sh

APO sprint 的 N0 gate 检查本 sprint 是否 finalized：

- 本 sprint finalized → APO N0 解锁 → APO 自动进 N1
- 本 sprint 仍 active → APO N0 持续 BLOCKED
