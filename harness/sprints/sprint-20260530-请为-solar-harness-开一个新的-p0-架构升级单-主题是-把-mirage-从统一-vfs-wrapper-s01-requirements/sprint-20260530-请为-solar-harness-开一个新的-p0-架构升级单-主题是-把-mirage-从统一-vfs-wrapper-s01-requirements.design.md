# Design: Mirage Context Access Plane — Requirements (S01)

sprint_id: `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s01-requirements`

## 1. 六层分层架构

```
L1  Mirage           = Context Access Plane / logical VFS / search orchestration
L2  CocoIndex        = Index Plane / incremental semantic index / lineage
L3  understand-anything = Understanding Artifact Producer / semantic distiller
L4  solar-unified-context = Fusion + Ranking + Dedupe Plane
L5  runtime_context_inject = Agent Context Delivery Plane
L6  verifier.context_usage = Context Usage Verification Plane
```

每层读写边界：
| 层 | 读 | 写 | 不可 |
|----|----|----|------|
| L1 Mirage | mount config, physical paths | search results, adapter output | 不可直接修改索引 |
| L2 CocoIndex | source files, git history | index, symbols, callgraph, lineage | 不可替代 Mirage 入口 |
| L3 understand-anything | source docs/code | understanding artifacts | 不可直接注入 agent |
| L4 unified-context | L1-L3 outputs, session events | fused ranked results | 不可跳过 L5 注入 |
| L5 runtime-inject | L4 output, dispatch context | sidecar metadata, prompt injection | 不可跳过 L6 验证 |
| L6 verifier | L5 sidecar, agent output | verification verdict | 不可修改 artifacts |

## 2. Mirage Source Adapter Schema

```json
{
  "mount": "/cocoindex",
  "path": "/cocoindex/symbols/apo_plan_compiler.py",
  "source_type": "cocoindex",
  "snippet": "def compile_execution_plan_for_node(...)",
  "provenance": "git:abc1234:harness/lib/apo_plan_compiler.py:L42",
  "score_or_rank": 0.92,
  "layer": "code-symbol",
  "source_hash": "sha256:...",
  "lineage": {"last_indexed_at": "...", "stale": false}
}
```

## 3. Mirage 新增 Mount/Source

| 现有 Mount | 类型 | 状态 |
|-----------|------|------|
| /knowledge, /raw, /sources, /papers | disk | ✅ |
| /qmd | virtual_command | ✅ |
| /solar-db | adapter | ✅ |
| /cortex, /sprints, /drive | disk | ✅ |

| 新增 Mount | 类型 | 用途 |
|-----------|------|------|
| /cocoindex | adapter | code chunks, symbols, callgraph, blast-radius |
| /understanding | disk/structured | understanding artifacts (summaries, claims, entities) |

mirage search 扩展到 5+ source：mirage_path + qmd + solar_db + cocoindex + understanding

## 4. Unified Context Fusion 规格

retrieve(query) 融合源：
1. mirage_path  2. qmd  3. solar_db  4. cocoindex  5. understanding  6. ragflow(optional)  7. session events

Source Layer 分类：
| Layer | 来源 |
|-------|------|
| synthesis | knowledge vault 综合文档 |
| concepts | QMD wiki 概念 |
| references | papers, external refs |
| raw-evidence | sprint artifacts, accepted.md |
| code-symbol | CocoIndex symbols |
| code-callgraph | CocoIndex callgraph |
| code-chunk | CocoIndex code chunks |
| understanding-summary | UA summaries |
| understanding-claim | UA claims |
| understanding-entity | UA entities |
| retrieval-evidence | search hits |

runtime_context_inject sidecar 扩展：
- `context_sources: [{source_type, mount, hit_count, degraded}]`
- `degraded_sources: [source_type]`
- `lineage_refs: [{source_hash, provenance}]`

## 5. Verifier Context Usage 规格

6 条验证规则：
1. `runtime_context_sidecar_exists` — dispatch 后 sidecar JSON 存在
2. `required_context_source_available` — 任务类型对应的必需 source 有 hit
3. `degraded_sources_declared` — 降级 source 已声明，不伪装为正常 evidence
4. `code_task_has_coco_source` — code 任务至少有 cocoindex/code-intelligence hit
5. `paper_task_has_understanding_source` — paper/doc 任务至少有 understanding hit
6. `handoff_cites_context_sources` — final handoff/report 引用了 context sources

## 6. 需求分组

| RG | 需求 | 验收 | 对应切片 |
|----|------|------|---------|
| RG1 | 六层分层边界文档 | 每层读写职责表 | S01→S02 |
| RG2 | Mirage source adapter schema | JSON schema + 样例 | S01→S02 |
| RG3 | /cocoindex mount 设计 | adapter + search 集成 | S01→S03 |
| RG4 | /understanding mount 设计 | disk mount + artifact schema | S01→S03 |
| RG5 | unified-context 多源融合 | 7 source 融合 + 11 layer 分类 | S01→S03 |
| RG6 | runtime_context sidecar 扩展 | context_sources/degraded/lineage | S01→S03 |
| RG7 | verifier context_usage | 6 条验证规则实现 | S01→S04 |
| RG8 | doctor 命令面 | mirage/coco/ua doctor | S01→S04 |
| RG9 | Evidence Ledger 回放 | query/source/hash/lineage 可追溯 | S01→S05 |

## 7. Epic→Sprint Traceability

| 切片 | 输入 | 产出 | 验收 | 依赖 |
|------|------|------|------|------|
| S01 requirements | epic.md, 现有 mirage 代码 | 六层边界, adapter schema, 规格 | D1-D6 | 无 |
| S02 architecture | S01 规格 | mount config 扩展, adapter 接口, fusion 架构 | 架构 review | S01 |
| S03 core-runtime | S02 架构 | cocoindex/understanding mount, sidecar 扩展 | 功能可用 | S02 |
| S04 observability | S03 | doctor + verifier + status page | doctor 通过 | S03 |
| S05 verification | S03+S04 | 7 类 AC 全部 E2E 验证 | 全 PASS | S03,S04 |

## 8. 非目标
- 不追求 shell-native FUSE (macOS SIP 限制)
- 不重写 Mirage VFS wrapper 核心
- 不替换 CocoIndex/understand-anything 本身
- 不做在线实时索引 (CocoIndex 离线增量)

## 9. 风险

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | CocoIndex 未安装时 /cocoindex mount 不可用 | 搜索降级 | fail-open + degraded_source 标记 |
| R2 | understand-anything 产物格式不稳定 | 解析失败 | schema 版本 + 兼容层 |
| R3 | 多源融合排序质量 | 结果噪声 | layer 权重可调 + source_type 过滤 |
