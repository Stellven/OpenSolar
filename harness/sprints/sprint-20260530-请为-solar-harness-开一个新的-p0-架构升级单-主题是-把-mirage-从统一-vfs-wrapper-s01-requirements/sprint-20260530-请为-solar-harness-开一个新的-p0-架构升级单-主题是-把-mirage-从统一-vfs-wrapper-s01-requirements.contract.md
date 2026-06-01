# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper`
sprint_id: `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s01-requirements`
handoff_to: `planner`

## Intent

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## Required Capabilities

- product.requirements
- workflow.planning

## Acceptance

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。

## Done

- [ ] D1: 六层分层边界定义 — Mirage(Access)/CocoIndex(Index)/understand-anything(Artifact)/unified-context(Fusion)/runtime-inject(Delivery)/verifier(Verification) 六层读写边界已明确
- [ ] D2: Mirage Source Adapter Schema — 标准输出 schema (mount/path/source_type/snippet/provenance/score/layer/source_hash/lineage) 已定义
- [ ] D3: Mirage 新增 Mount/Source 设计 — /cocoindex + /understanding mount + source adapter 已设计，mirage search 扩展到 5+ source
- [ ] D4: Unified Context Fusion 多源融合规格 — 6+ source 融合 + 11+ source layer 分层 + runtime_context_inject sidecar 扩展 (context_sources/degraded_sources/lineage_refs) 已定义
- [ ] D5: Verifier Context Usage 检查规格 — 6 条验证规则 (sidecar_exists/required_source_available/degraded_declared/code_has_coco/paper_has_understanding/handoff_cites_sources) 已定义
- [ ] D6: Epic→Sprint Traceability Matrix — S01-S05 输入/输出/验收/依赖追踪表已生成
