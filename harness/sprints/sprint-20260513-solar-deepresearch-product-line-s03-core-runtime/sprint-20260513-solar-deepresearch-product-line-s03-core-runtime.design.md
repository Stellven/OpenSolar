# Design — Solar DeepResearch Product Line · S03 Core Runtime

Sprint: `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime`
Epic: `epic-20260513-solar-deepresearch-product-line`
Slice: `core-runtime` (Planner pass)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. Problem Framing

S01 (requirements) 和 S02 (architecture) 已交付。S03 是 DeepResearch 产品线的**第一行可执行代码**：把 S02 设计的 schema / storage / connector 转化为 Python 实现，并提供最小可运行 `solar-harness research init/add-source/extract/ledger/status` CLI。

为什么单独切 S03：
- 同时实现 schemas + storage + connector + CLI = 一个 builder pane 拉不动；必须并行拆分。
- S04 (orchestration-ui) 和 S05 (verification-release) 都依赖 S03 的实现产物；S03 必须先交付可 import 的 Python module。
- 这是首个**真写代码**的切片，必须严格遵守 S02 schemas.md 的 8 个模型不变量，不允许 schema 漂移。

## 2. Design Goals

- **Schema 落地不漂移**：S02 schemas.md 是单一来源，S03 builder 完全按字段名 / 类型 / 不变量实现。
- **测试驱动**：每个节点交付时必须含 pytest 单测，断言数 ≥ 该模块行数的 10%。
- **真 SQLite + 真文件 IO**：禁止 mock，存储层用真 sqlite3 连接 + tempdir 测试。
- **向后兼容**：DeepResearch 模块通过 feature_flag `research.evidence_ledger` 默认 off，不破坏现有 wake/dispatch/status 路径。
- **CLI 是 thin wrapper**：CLI 子命令只做参数解析 + 调底层 module，业务逻辑全在 lib/research/。

## 3. Non-Goals

- **不接活体 connector**：本切片只实现 `internal_mirage` connector + `markdown`/`html` extractor；OpenAlex/Brave 留给 release-X。
- **不写 ReportAST 编译器**：那是 S04 的事（或本切片 P1 后续）。
- **不集成 capability plane**：S04 负责注册 research.* capability。
- **不写 SKILL.md / agent**：S04 负责。
- **不做性能优化**：MVP first，性能基线留给后续 ops sprint。
- **不接 LLM**：本切片只做数据层 + storage + CLI 骨架；claim mining 用规则（正则 / spaCy）而非 LLM。

## 4. Deliverables (代码 + 测试 + handoff)

| Deliverable | Owner | 内容 |
|---|---|---|
| `harness/lib/research/__init__.py`, `schemas.py`, `ids.py`, `hashing.py` | N1 builder | 8 个 dataclass / pydantic model + sha256 ID 算法 + content_hash 函数 |
| `harness/lib/research/storage.py` + SQLite migration | N2 builder | SQLite 连接 + 7 张表 CREATE + JSONL writer + backward-compat feature flag |
| `harness/lib/research/evidence/{ledger.py,citation_span.py}` | N3 builder | Evidence write/read + span verify (byte 范围匹配) |
| `harness/lib/research/sources/{base.py,internal_mirage.py}` + `extractors/markdown.py` | N4 builder | SourceConnector 抽象 + 1 个 connector + 1 个 extractor |
| `harness/lib/research/cli.py` + `solar-harness research <subcmd>` 接入 | N5 builder | init/add-source/extract/ledger/status 5 个子命令 |
| `harness/tests/research_unit/test_*.py` (基础单测) | 每个 N 节点附带 | 每个模块 ≥ 5 testcase, 总 ≥ 30 assertion |
| `…s03-core-runtime.handoff.md` | N6 builder | 模块清单 + import 路径 + CLI 用法示例 + 已知未闭环项 |
| `…s03-core-runtime.design.md` (本文) + `…plan.md` + `…task_graph.json` | Planner | 三件套 |

## 5. DAG Topology

```text
N1 schemas+ids+hashing  ──┐
                          ├── N2 storage ──┐
                          │                ├── N3 evidence ──┐
                          │                │                  ├── N5 CLI ── N6 integration+handoff
                          └── N4 sources+extractors ─────────┘
```

依赖链：
- N1 (foundational types): 无依赖
- N2 (storage): depends on N1 (需要 schema)
- N3 (evidence): depends on N1 + N2 (用 schema + 存到 storage)
- N4 (sources/extractors): depends on N1 (用 schema)
- N5 (CLI): depends on N2 + N3 + N4 (调用各模块)
- N6 (integration + handoff): depends on N1+N2+N3+N4+N5

N1 是唯一无依赖节点。N2 和 N4 在 N1 passed 后并行。N3 在 N2 passed 后启动。N5 join N2+N3+N4。N6 最终 join。

## 6. Acceptance Contract

| # | Acceptance | 验证 |
|---|---|---|
| **A1** | `pytest harness/tests/research_unit -v` 全绿，断言 ≥ 30 | exit 0 + grep -c assert |
| **A2** | 8 个 schema model 全部实现且字段匹配 S02 schemas.md | `python -c "from harness.lib.research import schemas; assert hasattr(schemas, 'EvidenceItem')..."` |
| **A3** | SQLite 7 张表全部存在且可创建 | `python -c "from harness.lib.research.storage import init_db; init_db(':memory:')"` 无异常 |
| **A4** | Evidence span verify 拒绝不匹配的 span | 单测 `test_citation_span_mismatch_rejected` |
| **A5** | unsupported key claim 被拒绝 | 单测 `test_unsupported_claim_rejected` |
| **A6** | `solar-harness research init/add-source/extract/ledger/status` 5 个子命令均可调 | shell `solar-harness research --help` 列全 |
| **A7** | feature_flag `research.evidence_ledger` 默认 off | grep `research.evidence_ledger.*default.*off` 命中 |
| **A8** | 向后兼容：现有 wake/dispatch/status 行为不变 | `solar-harness doctor` 无新增 error |
| **A9** | epic traceability.json children[2] (S03_core_runtime) status=passed + artifact_links | jq 检查 |

## 7. Stop Rules

- **不允许 mock SQLite / 文件 IO**：测试用 `:memory:` 或 `tmp_path` fixture，禁止 `@mock.patch('sqlite3.connect')`。
- **不允许 schema 漂移**：字段名 / 类型必须严格匹配 S02 schemas.md。
- **不允许接活体 API**：connector 只实现 `internal_mirage`；尝试发 HTTP 请求 = fail。
- **不允许 CLI 直接执行业务逻辑**：CLI 必须 thin wrapper，业务逻辑在 lib/。
- **不允许声称 epic 已完成**：本切片只完成 S03 节点。
- **N5 必须等 N2+N3+N4**：CLI 依赖三者实现，graph_scheduler 强制。

## 8. Parallelism & Write Scope

- N1: `harness/lib/research/{__init__,schemas,ids,hashing}.py`, `harness/tests/research_unit/test_{schemas,ids,hashing}.py`
- N2: `harness/lib/research/storage.py`, `harness/lib/research/migrations/`, `harness/tests/research_unit/test_storage.py`
- N3: `harness/lib/research/evidence/`, `harness/tests/research_unit/test_evidence_*.py`
- N4: `harness/lib/research/sources/`, `harness/lib/research/extractors/`, `harness/tests/research_unit/test_{sources,extractors}_*.py`
- N5: `harness/lib/research/cli.py`, `harness/solar-harness.sh` (添加 research 子命令路由), `harness/tests/research_unit/test_cli.py`
- N6: `harness/sprints/*s03-core-runtime.handoff.md`, `harness/sprints/epic-*.traceability.json`

注意 N5 触碰 `harness/solar-harness.sh`，需要小心不破坏现有路由（向后兼容 acceptance）。

## 9. Model Routing

- **N1 (schemas + ids + hashing)**: `sonnet` — 数据模型严谨性，GLM 1210 风险高。
- **N2 (storage)**: `sonnet` — SQL DDL + 文件 IO，逻辑密度高。
- **N3 (evidence)**: `sonnet` — span verify 算法 + 业务逻辑。
- **N4 (sources + extractors)**: `sonnet` — connector 抽象 + extractor 解析。
- **N5 (CLI)**: `sonnet` — argparse + 子命令路由，需小心兼容性。
- **N6 (integration)**: `sonnet` — handoff 撰写 + 跨文件 check。

全 Sonnet 路由：S03 是 DeepResearch 第一行代码，错一处扩散到 S04/S05。

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------|
| schema 实现与 S02 schemas.md 字段不一致 | N1 acceptance 强制 `getattr(schemas, 'EvidenceItem').__dataclass_fields__` 字段集合检查 |
| SQLite migration 漂移 | N2 用版本化 migration 文件 + `PRAGMA user_version` 跟踪 |
| span verify 算法误判（off-by-one / encoding） | N3 必须覆盖 UTF-8 多字节 + 边界 testcase |
| CLI 破坏现有 solar-harness 路由 | N5 用独立 router 函数 + `solar-harness doctor` 集成验证 |
| feature_flag 默认 on 误开启 DeepResearch | N5/N6 检查默认值 + grep `default.*off` |
| 大量 import 路径 import 错误 | N6 跑 `python -c "import harness.lib.research"` 不抛异常 |
| 测试用 mock 而非真 SQLite | Stop Rule + evaluator grep `@mock.patch` 必须 0 命中 |

## 11. Knowledge Context Usage

- `solar-harness context inject` 已执行（命中 Solar 架构方法论作为分层参考；mirage_path no_results — 新模块无 prior art）。
- 复用现有 `harness/lib/` 风格（如 `capability_inference.py`、`solar_skills.py`）— 单文件模块 + 显式 export + dataclass。
- S02 schemas.md / storage.md / architecture.md 是本切片唯一架构来源。

## 12. Handoff Plan

N6 完成后，handoff 必须包含：

- 模块清单 + import 路径示例 (`from harness.lib.research.evidence.ledger import write_evidence` 等)
- CLI 用法示例 (5 个子命令 sample invocation + 期望输出)
- 单测运行结果 (`pytest harness/tests/research_unit -v` 输出 head)
- 已知未闭环项 (P1: ReportAST 编译器、Factuality evaluator)
- 给 S04 builder 的"CLI 集成入口"说明
- 给 S05 evaluator 的"测试 fixture 路径"
- `evaluator_can_review: true` + `s04_can_start: true` + `s05_can_start_after_s04: true`

## 13. 当前状态特别说明

本 plan + task_graph 在 `phase=epic_waiting_dependency` 下完成（被 S02 阻断）。意图：
- spec 提前就绪，S02 passed 后 coordinator 立即激活 S03
- builder 可直接读 task_graph 开始干活，无需等 planner
- 不主动改 status 为 active，尊重 epic DAG 依赖门
