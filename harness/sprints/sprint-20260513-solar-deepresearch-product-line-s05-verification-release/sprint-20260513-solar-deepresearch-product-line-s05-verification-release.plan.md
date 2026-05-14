# Plan — Solar DeepResearch Product Line · S05 Verification & Release

Sprint: `sprint-20260513-solar-deepresearch-product-line-s05-verification-release`
Slice: verification-release (test + smoke + docs + archive)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

> 配套读 design.md (方法论 + 边界) 和 contract.md (Acceptance + Stop Rules)。

## 1. DAG

```text
N1 unit-tests              ─┐
N2 integration-tests       ─┤
N3 negative-controls       ─┤
N4 smoke-benchmark         ─┴── N5 docs-and-knowledge-archive ── handoff
```

5 节点，4 并行上游 + 1 join。Cost = M+L+M+L+M = 约 12 单位 builder time。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Preferred Model | Cost | Gate |
|------|------|---------|-----------------|------|------|
| **N1** | 写 unit 测试套件：schemas/ids/hashing/storage/evidence span/claim link | — | sonnet | 2.0 | unit-pass |
| **N2** | 写 integration 测试套件：fixture → final.md 全链路 | — | sonnet | 3.0 | integration-pass |
| **N3** | 写 negative 测试套件：unsupported claim / span mismatch / connector failure 三类 fail-by-design | — | sonnet | 2.0 | negative-pass |
| **N4** | Smoke benchmark：小型 research brief 跑出 2-3 section final.md + research_eval.smoke.json | — | sonnet | 3.0 | smoke-pass |
| **N5** | 写 README.research.md + Knowledge/_raw 归档 + 更新 epic traceability + 写 handoff | N1, N2, N3, N4 | sonnet | 2.0 | release-pass |

Total estimated cost: 12 units。

## 3. Parallelism

- **N1 ∥ N2 ∥ N3 ∥ N4** 完全并行：write_scope 互不重叠（unit / integration / negative / reports）。
- **N5 join**：仅当 N1+N2+N3+N4 全部 `passed` 才能 ready。任一上游 `pending/reviewing/failed` → N5 holds。
- DAG 4-并 1-串，最大 builder 占用 = 4 个 pane（推荐 4 个 builder 各跑一节点）。

## 4. Dispatch Batches

- **batch-1**: `[N1, N2, N3, N4]`，join_gate=`[unit-pass, integration-pass, negative-pass, smoke-pass]`
- **batch-2**: `[N5]`，join_gate=`[release-pass]`

`graph_scheduler` 在 batch-1 全 passed 后自动扩展 batch-2。

## 5. Cross-Sprint Prerequisites

⚠️ S05 builder dispatch **要求 S03 + S04 已 passed**，因为：
- N1 unit 测试需要 `harness/lib/research/schemas.py` 等模块存在
- N2 integration 测试需要 `solar-harness research run` CLI 可调用
- N3 negative 需要 evidence ledger 实际实现
- N4 smoke 需要全链路 runtime

S05 的 `phase=epic_waiting_dependency` 是正确状态。本 plan + task_graph 只是 **spec 就绪**，等 S03/S04 passed 后再激活 builder。

## 6. Per-Node Acceptance (builder/evaluator 共用)

### N1 unit-tests
- `pytest harness/tests/research/unit -v` 全绿
- 测试文件覆盖：`test_schemas.py`, `test_ids.py`, `test_hashing.py`, `test_storage.py`, `test_evidence_span.py`, `test_claim_evidence.py`
- 每个文件至少 5 个 testcase，总 assertion ≥ 30
- 禁止 `@mock.patch` 出现在测试文件中（grep 检查）
- 禁止 `pass` 或仅 `assert True` 作为测试 body

### N2 integration-tests
- `pytest harness/tests/research/integration -v` 全绿
- `tests/research/fixtures/integration/source_001.md` 等 fixture 存在
- 测试运行后生成 `_out/evidence.jsonl`, `_out/claims.jsonl`, `_out/report_ast.json`, `_out/final.md`
- `final.md` 非空且包含至少 1 个 citation 引用
- 全链路用真 SQLite + 真文件 IO，禁止 mock

### N3 negative-controls
- `pytest harness/tests/research/negative -v` 全绿（"绿"指 negative 测试按预期 fail）
- 3 条 testcase：
  - `test_unsupported_claim_rejected` — 没 evidence_id 的 key claim 必须被拒
  - `test_citation_span_mismatch_fails` — span_text 不匹配 source 时 evaluator fail
  - `test_connector_failure_not_silent` — connector 异常时 status=error 而非降级
- 每个 testcase 必须用 `pytest.raises(...)` 或显式 `assert ... fails`

### N4 smoke-benchmark
- `harness/reports/research-smoke-bench.md` 存在，≥ 100 行，2-3 个 section
- 每个 section 含至少 1 个 citation `[evidence_id]` 引用
- `harness/reports/research_eval.smoke.json` 含键集 ⊇ `{unsupported_claim_rate, citation_span_accuracy, section_count, evidence_count, claim_count}`
- `section_count` ∈ [2, 3]
- smoke 跑完成时间 ≤ 10 分钟（实测，不强制 CI）
- fixture 用 mock source（本切片不接活体 API）

### N5 docs-and-knowledge-archive
- `harness/README.research.md` ≥ 200 行：安装 / 用法 / CLI 速查 / 故障排查
- `Knowledge/_raw/deepresearch-accepted-<YYYYMMDD>.md` 写入：
  - epic 总览
  - 5 个 sub-sprint 的 sid + 关键 artifact
  - 关键架构决策（来自 S02 design.md）
  - 主要风险 + mitigation
- `epic-…traceability.json` children[4] (S05_verification_release) status → `passed` / `completed` + artifact_links 5 条
- `…s05-verification-release.handoff.md` 含：
  - 5 份产物路径
  - 测试结果摘要表
  - `research_eval.smoke.json` head
  - `epic_can_close: true` 标记

## 7. Routing Policy

- 所有节点用 `sonnet`（design.md §9 已论证）。
- 单一 GLM-5.1 1210 风险 → 不用。
- N2/N4 涉及实际跑代码，**不允许 builder 调用外部 web fetch / search**；fixture 必须本地。
- N4 可调本地小模型做 section writing，但生成内容必须基于 fixture evidence，禁止幻觉。

## 8. Stop Rules (执行期)

- Builder 在任一节点用 `@mock.patch` 替代真 SQLite/文件 IO → 立即 fail，evaluator 拒收。
- 测试 body 为空 / 仅 `pass` / 仅 `assert True` → fail。
- N5 在 N1-N4 任一 `pending/failed` 时被误 dispatch → graph_scheduler 阻断。
- 任一节点声称「epic 已完成」而 N1-N4 未全 passed → fail。
- Smoke benchmark 输出的 section 包含 unsupported claim → fail，回滚到 N4。

## 9. Exit Criteria

- 5 份产物全部存在且非空
- task_graph 5 个 gates 全 passed: `unit-pass, integration-pass, negative-pass, smoke-pass, release-pass`
- epic traceability.json 的 S05 节点 status=passed/completed
- handoff.md `epic_can_close: true`
- `Knowledge/_raw/deepresearch-accepted-*.md` 至少 1 个

## 10. Evaluator 复核入口（建议）

1. `pytest harness/tests/research/unit harness/tests/research/integration harness/tests/research/negative -v` 全绿
2. `python3 -c "import json; d=json.load(open('harness/reports/research_eval.smoke.json')); assert d['section_count'] in [2,3] and 0 <= d['unsupported_claim_rate'] <= 1"`
3. `wc -l harness/reports/research-smoke-bench.md` ≥ 100
4. `ls ~/Knowledge/_raw/deepresearch-accepted-*.md` ≥ 1
5. `jq '.children[4].status' epic-*.traceability.json` == `"passed"` 或 `"completed"`
6. `grep 'epic_can_close: true' …s05-verification-release.handoff.md`
7. `grep -c '@mock.patch' harness/tests/research/integration/*.py` == 0
8. `grep -c 'assert' harness/tests/research/unit/*.py` ≥ 30

## 11. Out of Scope (留给后续)

- **活体 connector**：OpenAlex/Brave/Tavily 真 API key 接入留给 release-X sprint。
- **10w 字真报告**：本切片只跑 2-3 section smoke；10w 字是产品上线后的实际 research-run。
- **CI 集成**：本切片只确保本地可跑；GitHub Actions / 远程 CI 留给后续 ops sprint。
- **性能基准**：不做 throughput 基线，只做 functional smoke。

本切片只交付**端到端验证 + 发布证据**，所有产品功能由 S02-S04 已交付。

## 12. 当前状态特别说明

本 plan + task_graph 在 `phase=epic_waiting_dependency` 下完成（codex 已恢复依赖门）。意图：
- spec 提前就绪，节省 S03/S04 passed 后的 builder 等待时间
- coordinator 在 S03+S04 passed 后自然激活 S05，builder 立即可读 task_graph 开始干活
- 不主动改 status 为 active，尊重 epic DAG 依赖门
