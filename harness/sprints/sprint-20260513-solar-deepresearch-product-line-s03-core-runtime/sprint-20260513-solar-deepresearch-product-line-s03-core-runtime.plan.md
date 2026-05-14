# Plan — Solar DeepResearch Product Line · S03 Core Runtime

Sprint: `sprint-20260513-solar-deepresearch-product-line-s03-core-runtime`
Slice: core-runtime (Python implementation)
Author: Solar Planner
Date: 2026-05-13
Knowledge Context: solar-harness context inject used

## 1. DAG

```text
N1 schemas+ids+hashing  ──┐
                          ├── N2 storage ──┐
                          │                ├── N3 evidence ──┐
                          │                │                  ├── N5 CLI ── N6 integration+handoff
                          └── N4 sources+extractors ─────────┘
```

6 节点，3 层依赖。N1 单根，N2/N4 二并，N3 跟 N2，N5 join N2+N3+N4，N6 最终 join。

## 2. Node-by-Node Execution

| Node | Goal | Depends | Model | Cost | Gate |
|------|------|---------|-------|------|------|
| **N1** | `harness/lib/research/{schemas,ids,hashing}.py` + 单测 | — | sonnet | 2.5 | schemas-pass |
| **N2** | `harness/lib/research/storage.py` + SQLite migration + 单测 | N1 | sonnet | 2.5 | storage-pass |
| **N3** | `harness/lib/research/evidence/{ledger,citation_span}.py` + 单测 | N1, N2 | sonnet | 2.5 | evidence-pass |
| **N4** | `harness/lib/research/sources/{base,internal_mirage}.py` + `extractors/markdown.py` + 单测 | N1 | sonnet | 2.0 | sources-pass |
| **N5** | `harness/lib/research/cli.py` + `solar-harness.sh` research 子命令路由 + 单测 | N2, N3, N4 | sonnet | 2.0 | cli-pass |
| **N6** | 集成 check + 更新 epic traceability + 写 handoff | N1-N5 全 | sonnet | 1.0 | integration-pass |

Total estimated cost: 12.5 units。

## 3. Parallelism

- **N2 ∥ N4** 在 N1 passed 后并行（storage + sources 都依赖 schema 但互不依赖）。
- **N3** 在 N2 passed 后启动（evidence ledger 写到 storage）。
- **N5** join N2+N3+N4（CLI 调用三个模块）。
- **N6** join 全部。

最大 builder 并发 = 2（N2 ∥ N4 阶段）或 3（N3+N4+其他 idle）。

## 4. Dispatch Batches

- **batch-1**: `[N1]`
- **batch-2**: `[N2, N4]` (N1 passed 后)
- **batch-3**: `[N3]` (N2 passed 后, N4 可继续)
- **batch-4**: `[N5]` (N2+N3+N4 全 passed)
- **batch-5**: `[N6]` (N1-N5 全 passed)

## 5. Per-Node Acceptance

### N1 schemas + ids + hashing
- `harness/lib/research/schemas.py` 含 8 个 dataclass/model: SourceConnector, SourceHit, SourceDocument, EvidenceItem, Claim, ClaimEvidenceLink, CitationSpan, ReportAST
- 字段名 / 类型严格匹配 S02 schemas.md
- `harness/lib/research/ids.py` 含 `make_id(*parts) -> str` (sha256(canonical))
- `harness/lib/research/hashing.py` 含 `content_hash(text: str) -> str` (sha256)
- 单测：`test_schemas.py`, `test_ids.py`, `test_hashing.py`，总 assertion ≥ 12
- `python -c "from harness.lib.research import schemas, ids, hashing"` 不报错

### N2 storage
- `harness/lib/research/storage.py` 提供 `init_db(path: str)`, `get_connection(path: str)`, JSONL writer
- 7 张表 CREATE 实现，PRIMARY KEY / FOREIGN KEY / INDEX 完备
- migration 文件 `harness/lib/research/migrations/001_init.sql`
- feature_flag `research.evidence_ledger` 默认 off，从 `~/.solar/config.json` 读取
- 单测：`test_storage.py` 用 `:memory:` 或 `tmp_path`，禁 mock
- 单测 assertion ≥ 10

### N3 evidence ledger + citation_span
- `evidence/ledger.py`: `write_evidence(item: EvidenceItem)`, `read_evidence(id: str)`, `list_by_source(source_id: str)`
- `evidence/citation_span.py`: `verify_span(source_text, span_start, span_end, span_text) -> bool`
- span verify 必须覆盖 UTF-8 多字节边界
- 单测：`test_evidence_ledger.py`, `test_citation_span.py`
- 单测包含 negative case: `test_unsupported_claim_rejected`、`test_span_mismatch_rejected`
- 单测 assertion ≥ 12

### N4 sources + extractors
- `sources/base.py`: `class SourceConnector` 抽象（`search`, `fetch`）
- `sources/internal_mirage.py`: 用现有 Mirage VFS 实现一个 connector
- `extractors/markdown.py`: 解析 .md 文件提取 SourceDocument
- 单测：`test_sources_base.py`, `test_sources_mirage.py`, `test_extractors_markdown.py`
- 不允许 HTTP 调用（grep `requests\.` / `urllib` / `httpx` 在非测试代码必须 0 命中）
- 单测 assertion ≥ 10

### N5 CLI
- `harness/lib/research/cli.py` 实现 5 个子命令：`init`, `add-source`, `extract`, `ledger`, `status`
- `solar-harness.sh` 增加 `research)` 路由分发到 cli.py
- 每个子命令独立测试 + 端到端 smoke (init → add-source → ledger)
- `solar-harness research --help` 列全 5 个子命令
- `solar-harness doctor` 无新增 error（向后兼容）
- 单测：`test_cli.py`，assertion ≥ 10

### N6 integration + handoff
- 跑 `pytest harness/tests/research_unit -v`，全绿
- 跑 `python -c "import harness.lib.research"` 无异常
- 跑 `solar-harness doctor`，无新增 error
- 更新 `epic-…traceability.json` children[2] status → `passed/completed`，artifact_links 列模块路径
- 写 `…s03-core-runtime.handoff.md`：
  - 模块清单 + import 示例
  - CLI 5 个子命令用法
  - 单测结果 head
  - `evaluator_can_review: true`
  - `s04_can_start: true`

## 6. Routing Policy

- 所有节点 `sonnet`（GLM 1210 风险 + 代码严谨性）。
- 禁止 worker webfetch / web search（本地代码不需要外部资源）。
- 测试 fixture 用 tempdir / 内存 SQLite，禁 mock。

## 7. Stop Rules (执行期)

- Builder 使用 `@mock.patch('sqlite3...')` / `@mock.patch('builtins.open')` 替代真 IO → fail。
- 测试 body 空 / 仅 `pass` / 仅 `assert True` → fail。
- 实现代码 import `requests` / `urllib.request` / `httpx` → fail（无活体 API）。
- N5 在 N2+N3+N4 任一 pending 时 dispatched → graph_scheduler 阻断。
- schema 字段名与 S02 schemas.md 不一致 → fail。
- 任一 deliverable 声称 "DeepResearch 已完成" → fail。

## 8. Exit Criteria

- 6 个节点全 passed: schemas-pass, storage-pass, evidence-pass, sources-pass, cli-pass, integration-pass
- `pytest harness/tests/research_unit -v` 全绿，断言 ≥ 30 (累计)
- `solar-harness research --help` 列全 5 个子命令
- `solar-harness doctor` 无新增 error
- epic traceability.json children[2] status=passed/completed
- handoff `evaluator_can_review: true` + `s04_can_start: true`

## 9. Evaluator 复核入口

1. `pytest harness/tests/research_unit -v` 全绿
2. `grep -rc '@mock.patch\|@patch(' harness/lib/research/ harness/tests/research_unit/` 必须 == 0
3. `grep -rc 'requests\.\|urllib\.request\|httpx\.' harness/lib/research/` == 0 (在非测试目录)
4. `python -c "from harness.lib.research import schemas; print([f for f in schemas.EvidenceItem.__dataclass_fields__])"` 字段集 ⊇ {source_id, content_hash, span_start, span_end, span_text}
5. `solar-harness research --help` 列出 init/add-source/extract/ledger/status
6. `solar-harness doctor` exit 0
7. `jq '.children[2].status' epic-*.traceability.json` == `"passed"`

## 10. Out of Scope

- **S04**: capability plane 注册 + status UI + DAG 模板加载到 graph_scheduler
- **S05**: 端到端集成测试 + 负控 + smoke benchmark
- **Future**: 活体 connector (OpenAlex/Brave/Tavily)、ReportAST 编译器、Factuality evaluator
- **Future**: 性能基线、CI 集成

## 11. 当前状态说明

本切片当前 `status=queued, phase=epic_waiting_dependency`（被 S02 阻断，autopilot 已记录 dispatch suppressed）。spec 提前就绪，**status 保持不变**，等 S02 passed 后 coordinator 自然激活。
