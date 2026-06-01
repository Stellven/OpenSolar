# Design: S03 Core-Runtime (Mirage Context Access Plane)

## 1. 目标

把 S02 的 access-plane 设计落成最小可运行 runtime：

1. 新增 CocoIndex / Understanding adapter surface
2. 把 unified context 从 `mirage_path/qmd/solar_db` 扩成多源 fusion
3. 扩 runtime context sidecar，记录 `context_sources/degraded_sources/lineage_refs`
4. 给 verifier 增加 context usage contract

## 2. 核心实现单元

### 2.1 Mirage adapters
- `cocoindex_adapter.py`
- `understand_anything_adapter.py`
- `mirage_search.py` 注册新的 source_type:
  - `cocoindex`
  - `understanding`

### 2.2 Unified context fusion
- `solar-unified-context.py`
- source layering:
  - synthesis
  - concepts
  - references
  - raw-evidence
  - code-symbol
  - code-callgraph
  - code-chunk
  - understanding-summary
  - understanding-claim

### 2.3 Runtime injection sidecar
- `runtime_context_inject.py`
- sidecar fields:
  - `context_sources`
  - `source_counts`
  - `degraded_sources`
  - `lineage_refs`
  - `source_hash_refs`

### 2.4 Verifier contract
- `verifier.context_usage`
- required source by task type:
  - code task -> cocoindex/code intelligence
  - paper/doc task -> understanding source

## 3. 兼容策略

1. 现有 `mirage_path/qmd/solar_db` 继续保留。
2. CocoIndex / understanding 作为增量 source 接入，不替代原入口。
3. fail-open 保持，但 degraded source 必须显式声明，不能伪装为正常 evidence。

## 4. 本切片 DoD

1. 有 adapter/mount/runtime/verifier 的实现 DAG。
2. 明确 injection 与 evidence 回放边界。
3. 能启动 builder，不再停在空 PRD。

