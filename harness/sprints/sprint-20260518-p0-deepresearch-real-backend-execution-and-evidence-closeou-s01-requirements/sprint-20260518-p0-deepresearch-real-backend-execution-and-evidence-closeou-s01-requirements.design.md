# Design — S01 需求拆解与追踪矩阵

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s01-requirements`
slice: `requirements`
author: planner (solar-harness)
date: 2026-05-18

## 1. 切片定位

本切片**不写运行时代码**，只把用户原始大需求拆为可验收的 Outcomes、风险登记和 traceability 矩阵，并产出 PM/Planner 两份 HTML 视图。所有真实 backend 执行链路验证由 S03/S04/S05 完成。

## 2. Outcomes 拆解（可验收单元）

| OID | Outcome | 验收点 | 下游 Sprint | 风险 | Estimated Hours |
|-----|---------|--------|-------------|------|------------------|
| O-01 | PM PRD 文档化 + HTML 渲染 | `prd.md` 存在且可读；`prd.html` 渲染成功且包含原始需求 6 项 | S01 | HTML 渲染管线缺失 → 必须先确认 `solar-harness render` 或等价工具 | 0.3h |
| O-02 | Planner 输出 design/plan/task_graph + HTML | 三件套齐 + `planning.html` 渲染成功 | S01 | 工具链不存在导致 HTML 缺失 → 必须用 markdown→html 兜底 | 0.5h |
| O-03 | Serper 搜索接入 DeepResearch 并记录 usage meter | 跑 1 个 max_results≤3 的样例，`research_execution_metrics.json` 中能看到 `serper_calls > 0` 与 `sources_count` | S03 + S05 | 配额限制、Serper key 缺失 → fallback 必须明确标注 estimated=true | 1.5h |
| O-04 | survey writer/chief_editor backend 写 `model_usage.jsonl` | backend 调用后 `model_usage.jsonl` 至少 1 条记录，包含 model/usage 字段；`provider_usage_ledger` 能被 report_metrics 读到 | S03 + S05 | Claude CLI 不返回 usage → 必须用 local-command JSON fixture 跑通真实路径 | 2.0h |
| O-05 | 真 usage vs estimated 双路径切换 | 报告与 JSON artifact 中 `Token usage source ∈ {provider_usage_ledger, estimated, hybrid}` 且 `Token usage estimated` 布尔字段存在 | S03 | 误把估算伪装成真实 → 测试需断言 fallback 分支 | 1.0h |
| O-06 | final.md / human_final.md / research_eval.json / report_ast.json 包含 execution_metrics | 4 个产物末尾或字段中包含 Document word count + Total token consumption + Token usage source + Token usage estimated | S03 + S04 | 渲染遗漏字段 → 单测覆盖 4 个产物路径 | 1.0h |
| O-07 | 受控样例 + Claude CLI 小样 | `survey-chief-editor --backend claude-cli --model opus` 跑过；若不可用则把降级原因写入 handoff | S05 | 账户限额触发 → 必须把 fallback path 明文写入 handoff | 1.0h |
| O-08 | Evaluator 检查报告字段四件套 | eval.json 中明确断言 4 个字段全部存在 | S05 | Evaluator 跳过断言 → 在 contract 中固化 stop-rule | 0.5h |
| O-09 | Secret/Token 不入 Git | 任何 Serper / OAuth / usage ledger 私密内容不被 commit；`.gitignore` 与 git history check 通过 | S05 | 误 commit → CI 必须有 secret-scan | 0.3h |
| O-10 | 中文证据表 handoff | 最终 handoff.md 含证据表：搜索次数、来源数、token 来源、文档字数、报告路径、测试命令、失败/降级原因 | S05 | 缺字段 → Evaluator 必须 FAIL | 0.5h |

总估时 ≈ 8.6h（仅 outcomes 视角；实际 sprint 工作量分散到 S02–S05）。

## 3. Non-goals（本切片显式不做）

- 不直接绕过 planner 派 builder。
- 不在 S01 写运行时代码或动 `/Users/sihaoli/Solar/` 下的 python。
- 不消耗大额度 Serper/Claude 配额；样例必须 `max_results ≤ 3`。
- 不修改 epic.task_graph.json 中 S02–S05 的 write_scope（那是各自切片的事）。
- 不“声明已完成”代替证据。

## 4. Traceability Map（Epic → Outcome → Sprint Gate）

```
epic-20260518-...closeou
├── O-01 (PM PRD)                       → S01:passed
├── O-02 (Planner artifacts)            → S01:passed
├── O-arch-contracts (interface schemas §6) → S02:passed
├── O-03 (Serper meter)                 → S03:passed → S05:passed
├── O-04 (model_usage.jsonl)            → S03:passed → S05:passed
├── O-05 (real vs estimated)            → S03:passed
├── O-06 (execution_metrics)            → S03:passed → S04:passed
├── O-07 (controlled sample)            → S05:passed
├── O-08 (evaluator assert)             → S05:passed
├── O-09 (no secret leak)               → S05:passed
└── O-10 (中文证据表 handoff)           → S05:passed
```

回写 `traceability.json` 时，每个 child sprint 节点新增 `outcomes: [O-xx, ...]` 字段。

> **注**: `O-arch-contracts` 是为 S02 接口契约切片定义的可验收 outcome,对应 §6 的三个 schema 契约 (research_execution_metrics.json / model_usage.jsonl / final.md footer)。S02 通过即视为契约稳定,下游 S03-S05 可依赖。该 outcome 不在 §2 主表中,因为 §2 表是 P0 业务 outcomes (O-01..O-10),而 O-arch-contracts 是架构稳定性 outcome,独立追溯。

## 5. 哪些工作不能直接派 builder

- O-01/O-02：HTML 渲染如果 `solar-harness render` 工具不存在，**必须先让 Planner（即本切片）声明 fallback 渲染器**（markdown→html 命令式），再交 builder。
- O-04/O-05：真 usage vs estimated 切换涉及策略判断，需在 S02 architecture 定 contract 后才能交 builder，**不能跳过 S02**。
- O-07：Claude CLI 真实调用，可能触发账户限额，**必须先 dry-run** 并把限额检查作为 stop-rule。
- O-09：secret-scan 需配置 CI gate，**不能由 builder 自由发挥 .gitignore**。

## 6. 接口契约（给后续 sprint 看）

```yaml
research_execution_metrics.json:
  required_fields:
    - serper_calls: int
    - sources_count: int
    - total_tokens: int
    - usage_source: enum[provider_usage_ledger, estimated, hybrid]
    - estimated: bool
    - document_word_count: int
    - generated_at: ISO8601

model_usage.jsonl (one line per backend call):
  - ts, backend, model, prompt_tokens, completion_tokens, total_tokens, usage_source

final.md / human_final.md footer (必须包含):
  - "Document word count: {N}"
  - "Total token consumption: {N}"
  - "Token usage source: {provider_usage_ledger|estimated|hybrid}"
  - "Token usage estimated: {true|false}"
```

## 7. 风险登记（详见 risk-register.md）

| RID | 风险 | 概率 | 影响 | 缓解 | Owner |
|-----|------|------|------|------|-------|
| R-01 | Claude CLI usage 不返回 | 高 | 中 | local-command JSON fixture 兜底 + 标注 estimated | S03 |
| R-02 | Serper 配额耗尽 | 中 | 中 | max_results=3 强制 + 单次样例 + 记录 quota | S03 |
| R-03 | HTML 渲染工具缺失 | 中 | 低 | 用 pandoc / markdown-it 兜底 | S01 |
| R-04 | secret 泄露 | 低 | 高 | secret-scan CI gate + .gitignore 显式 | S05 |
| R-05 | Evaluator 跳过字段断言 | 中 | 高 | 在 contract.stop_rules 固化 4 字段必查 | S05 |
| R-06 | builder 半截声明完成 | 中 | 高 | 每个节点 acceptance 都附 "证据路径 + grep 命令" | 全部 |

## 8. 与父 Epic task_graph 的耦合点

本切片**只动 sprints/\*.prd.* / \*.traceability.json / \*.html**，不动 `lib/` `tests/` `tools/`，避免与 S03/S04/S05 的 write_scope 冲突。

## 9. 上游依赖 / 下游影响 / 未闭环项

- 上游：epic.epic.md / epic.traceability.json / epic.task_graph.json（已存在）。
- 下游：S02 architecture 必须基于本切片的接口契约（见 §6）落 design.md。
- 未闭环：HTML 渲染工具链未实测；Claude CLI 真实 usage 返回情况未实测——两项都已写入风险登记并交后续切片证伪。
