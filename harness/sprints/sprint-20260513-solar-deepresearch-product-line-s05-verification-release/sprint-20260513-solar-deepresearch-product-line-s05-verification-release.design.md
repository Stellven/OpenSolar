# Design — Solar DeepResearch Product Line · S05 Verification & Release

Sprint: `sprint-20260513-solar-deepresearch-product-line-s05-verification-release`
Epic: `epic-20260513-solar-deepresearch-product-line`
Slice: `verification-release` (Planner pass)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

DeepResearch 产品线的最后一公里是「端到端可复现验证 + 发布证据」。前四个切片把规格 (S01)、架构 (S02)、核心 runtime (S03)、orchestration UI (S04) 都交付完，S05 必须把它们粘合成可执行测试 + 负控 + benchmark smoke + 文档 + Knowledge 归档。

为什么单独切 S05：

- Control Plane v2 sprint 死于 S1-S3 PASS、S4-S8 没人收口 (followup.md 已记录)。S05 是显式的「收口节点」，专责把 epic 关到证据可验证状态。
- 父 epic stop rule 第 3 条：「parent sprint 在 evidence/claims/fact-check gates 未过前不能 passed」。S05 是这个 gate 的 owner。
- 测试代码、负控、benchmark、文档这四类产物 write_scope 互斥，可以并行交付。

## 2. Design Goals

- **真测试不空跑**：单测 / 集成 / 负控 / smoke 必须本地可复现，禁止 mock 数据库或假 evidence span。
- **三类负控硬 fail**：unsupported claim、citation span mismatch、connector failure，任何一类静默通过 = 节点 fail。
- **Benchmark 是冒烟而非全量**：本切片只交付小型 2-3 section 报告，不交付 10w 字最终报告（那是产品发布之后的事）。
- **Knowledge 归档可索引**：accepted artifact + final eval + architecture decision 必须写到 `~/Knowledge/_raw/`，便于未来 RAG。
- **不让父 epic 偷跑**：S05 通过前 epic.traceability.json 不允许 `epic_status=completed`。

## 3. Non-Goals (本切片显式不做)

- **不写 10w 字最终报告**：那是产品上线后的实际研究运行 (research-run-X) 的事，不是 S05 验证范围。
- **不接活体 connector key**：OpenAlex / Brave / Tavily / GitHub 用 fixture 数据做集成测试；活体 connector 烟雾留给 release-X sprint。
- **不重写 capability plane**：S04 已经把 research.* capability 注册完毕；本切片只校验注册结果。
- **不重新做 architecture/runtime decision**：S02/S03 是单一来源；本切片只验证它们的产物。
- **不绕过 graph_scheduler**：所有测试 dispatch 必须走 task_graph.json + validate。
- **不替换 evaluator**：sprint eval 仍由现有 evaluator + session evaluate 完成；本切片只补 research-eval.json 这个产物。

## 4. Deliverables (5 份测试 + 1 份 release 包 + Planner 三件套)

| Deliverable | Owner | 内容 | 给谁用 |
|---|---|---|---|
| `tests/research/unit/test_schemas.py` etc. | N1 builder | 单测：schemas、ids、hashing、storage migrations、evidence span hash、claim-evidence link | CI + 本地 pytest |
| `tests/research/integration/test_pipeline.py` | N2 builder | 集成测：fixture source → evidence.jsonl → claims.jsonl → report_ast.json → final.md | release gate |
| `tests/research/negative/test_neg_controls.py` | N3 builder | 负控：unsupported claim fail / span mismatch fail / connector failure detect | evaluator |
| `harness/reports/research-smoke-bench.md` + `harness/reports/research_eval.smoke.json` | N4 builder | Smoke benchmark：小型 research brief → 2-3 section final | release gate + 知识库 |
| `harness/README.research.md` + `Knowledge/_raw/deepresearch-accepted-<date>.md` | N5 builder | 用户文档 + operator runbook + knowledge archive | 用户 + 未来 RAG |
| `…s05-verification-release.handoff.md` | N5 builder | 5 份产物路径 + epic close 信号 | evaluator + epic_decomposer |
| `…s05-verification-release.design.md` | Planner (本文) | 切片方法论 | self / evaluator |
| `…s05-verification-release.plan.md` | Planner | 5-node DAG | 协调器 + builder |
| `…s05-verification-release.task_graph.json` | Planner | machine-readable DAG | graph_scheduler |

## 5. DAG Topology

```text
N1 unit-tests              ──┐
N2 integration-tests       ──┤
N3 negative-controls       ──┤
N4 smoke-benchmark         ──┤
                                └── N5 docs-and-knowledge-archive ── handoff
```

- **N1 / N2 / N3 / N4 完全并行** — write_scope 不重叠（unit / integration / negative / reports）。
- **N5 join**：依赖 N1-N4 全部 `passed`。N5 负责写文档 + 把 accepted artifact 写入 `~/Knowledge/_raw/` + 更新 epic.traceability.json + 写 handoff。
- N5 是唯一可以触碰 `Knowledge/_raw/` 和 epic traceability 的节点，确保归档与 epic 关闭单线串行。

## 6. Acceptance Contract (对齐 contract)

| # | Acceptance | 验证方式 |
|---|---|---|
| **A1** | 单测可复现 | `pytest harness/tests/research/unit -v` 全绿，断言数 ≥ 30 |
| **A2** | 集成测试 fixture → final.md 全链路成功 | `pytest harness/tests/research/integration -v` 全绿；产物 `tests/research/fixtures/_out/final.md` 非空 |
| **A3** | 三类负控全部 fail-by-design | `pytest harness/tests/research/negative -v`：3 条 testcase 期望 fail，pytest 用 `xfail` 或显式 assert raise |
| **A4** | Smoke benchmark 产出 2-3 section report | `wc -l harness/reports/research-smoke-bench.md` ≥ 100；`jq '.section_count' research_eval.smoke.json` 在 [2,3] |
| **A5** | research_eval.smoke.json 包含 unsupported_claim_rate, citation_span_accuracy | jq 检查必有键 |
| **A6** | Knowledge 归档存在 | `ls ~/Knowledge/_raw/deepresearch-accepted-*.md` 至少 1 个 |
| **A7** | Epic traceability.json children[4] status → passed/completed + artifact_links 5 条 | `jq '.children[4]' epic-*.traceability.json` |
| **A8** | task_graph.json 通过 graph-scheduler validate | exit 0 |
| **A9** | handoff.md 包含 `epic_can_close: true` 信号 | grep 命中 |

A6/A7 是 cross-sprint side-effect（写父 epic + 全局 Knowledge），属于本切片合约里允许的 write_scope (`Knowledge/_raw/`, `harness/sprints/*deepresearch*.json`)。

## 7. Stop Rules (本切片自身)

- **不允许 mock 数据库**：从 MEMORY 教训，integration 测试必须用真 SQLite + 真文件 IO，禁止 mock。任何 `@mock.patch` 出现在 integration 套件 = fail。
- **不允许测试空跑**：测试函数 body 为空 / 只有 `pass` / 只有 `assert True` = fail。每个 testcase 必须有真断言。
- **不允许声称 epic 已完成而 N1-N5 任一未 passed**：N5 写 handoff 前必须 read 各 node `passed` 状态。
- **不允许跳过负控**：N3 三条 testcase 必须落到代码层（不是 docstring 描述）。
- **不允许写假 evidence span**：smoke benchmark 的 fixture 必须真有 source_text + span_start/end，不能 hardcode span_text 不对应 source。

## 8. Parallelism & Write Scope

- N1 write_scope = `harness/tests/research/unit/**`, `harness/tests/research/fixtures/unit/**`
- N2 write_scope = `harness/tests/research/integration/**`, `harness/tests/research/fixtures/integration/**`
- N3 write_scope = `harness/tests/research/negative/**`, `harness/tests/research/fixtures/negative/**`
- N4 write_scope = `harness/reports/research-smoke-bench.md`, `harness/reports/research_eval.smoke.json`, `harness/tests/research/fixtures/smoke/**`
- N5 write_scope = `harness/README.research.md`, `Knowledge/_raw/deepresearch-accepted-*.md`, `…s05-verification-release.handoff.md`, `epic-…traceability.json`

四个上游节点 write_scope 完全互斥 → 可并发 dispatch。N5 read_scope 包含上游 4 份 + epic 文件，write 集中在文档 + 归档 + handoff。

## 9. Model Routing

- **N1 (unit)**: `sonnet` — 测试结构稳定，避免 GLM 1210。
- **N2 (integration)**: `sonnet` — 端到端逻辑，对推理质量敏感。
- **N3 (negative)**: `sonnet` — 反例需要清晰判断，必须 Sonnet。
- **N4 (smoke)**: `sonnet` — 真的写一份 2-3 section 报告，需要叙事 + 引用。GLM 在中文长上下文有 1210 风险（已踩 5 次）。
- **N5 (docs + archive)**: `sonnet` — 跨文件一致性 + 文档质量。

全 Sonnet 路由原因：S05 是最终验证，错一次成本高于成本节省。

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------|
| S03/S04 还没 passed，S05 builder 找不到 `harness/lib/research/` 实现 | task_graph.json 显式声明 `prerequisites: ["S03_passed","S04_passed"]`；builder dispatch 前 coordinator 检查 |
| Smoke benchmark 调用真 LLM 跑太慢 | N4 用 fixture connector + 本地小模型/缓存，目标 5 分钟内跑完 |
| 测试覆盖率虚高（大量 noop testcase） | A1 acceptance 加 `assertion_count >= 30`；evaluator grep `assert` 数量 |
| Knowledge 归档路径冲突（多 sprint 同写 _raw/） | N5 文件名带 sprint sid + 日期，唯一化 |
| Epic 提前 close | N5 是唯一可改 epic.traceability.json 的节点，且必须先读 N1-N4 全 passed |
| 负控被误写成「应该通过的测试」 | N3 用 `pytest.raises` 或 `xfail`，evaluator 检查至少 3 个 `raises`/`xfail` 标记 |

## 11. Knowledge Context Usage

- `solar-harness context inject` 已执行（命中 mirage_path `G0 PASS → 才允许并行下发`，强化「spec 并行 / builder 串行」判断；solar_db 3 条 accepted sprint 作为归档格式参考）。
- 复用历史 accepted sprint 的 `Knowledge/_raw/*.accepted.md` 格式（已有 8 个样本），N5 直接套用。
- 本切片 prior art 主要来自 sprint-20260420-082442 (coordinator 修复 sprint 的回归测试模式) — 单测 + 集成测 + 负控三层结构。

## 12. Handoff Plan

N5 完成后，handoff 必须包含：

- 5 份产物路径（测试目录 + reports + Knowledge 归档 + README）
- 测试运行结果摘要表（unit / integration / negative / smoke 各自的 pass 率）
- `research_eval.smoke.json` 的 head（unsupported_claim_rate / citation_span_accuracy）
- 显式 `epic_can_close: true` 标记（epic_decomposer 监听）
- 给监护人的「DeepResearch 产品线 P0 验收清单」一表
- 已知未闭环项（如活体 connector 留到后续 sprint）

S05 通过 = DeepResearch 产品线 epic 可关闭。
