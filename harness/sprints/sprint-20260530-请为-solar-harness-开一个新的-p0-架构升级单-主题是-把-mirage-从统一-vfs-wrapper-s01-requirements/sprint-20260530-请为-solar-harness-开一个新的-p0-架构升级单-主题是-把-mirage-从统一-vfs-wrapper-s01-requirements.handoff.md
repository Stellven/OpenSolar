# Handoff

## 结论

S01 requirements 已完成最低可执行 closeout：Mirage Context Access Plane 的目标、边界、验收点、risk boundary 和 phased rollout 已冻结，可进入 `S02_architecture`。

## 本切片已锁定的内容

1. Mirage 角色：`logical VFS entry + search adapter orchestration`，不是完整闭环。
2. 六层分层：
   - Mirage
   - CocoIndex
   - understand-anything
   - solar-unified-context
   - runtime_context_inject
   - verifier.context_usage
3. P0 重点：
   - `/cocoindex` 与 `/understanding` mount/source
   - unified context 融合层
   - runtime sidecar provenance
   - verifier/evidence 闭环
4. 明确 non-goals：
   - 不追求 shell-native FUSE 幻觉
   - 不把 degraded source 伪装成正常 evidence

## 进入 S02 必做项

1. 定义 Mirage source adapter contract
2. 定义 `/cocoindex`、`/understanding` mount/source 读写职责
3. 设计 unified context fusion / source layering
4. 设计 runtime_context_inject sidecar 增量字段
5. 设计 verifier.context_usage / evidence ledger 回放 contract

## 未闭环项

1. 还没有 `cocoindex_adapter.py` / `understand_anything_adapter.py` 代码实现
2. 还没有 context_sources/source_hash/lineage_refs 默认进入 sidecar
3. 还没有 verifier 对 required context source 的硬检查
