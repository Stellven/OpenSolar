# Design: HF Paper Insight Flow Core Runtime

epic_id: `epic-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究`
sprint_id: `sprint-20260527-p0-ai-influence-hf-paper-insight-flow-paper-to-project-研究-s03-core-runtime`
slice: `core-runtime`
status: planning_complete
generated_at: 2026-05-28T17:31:15Z
upstream: S02 architecture passed (10 层 / 6 数据对象 / 5 决策 / 5 OQ)
downstream: S04 orchestration-ui · S05 verification-release

## 目标

把 S02 架构切片收敛成可实现的核心 runtime：schema、持久化、状态机、provider enrichment、taxonomy/scoring/packet、reasoning route、compiler/store/watch，以及与旧 wake/dispatch/status 的兼容层。

## 模块边界

- `harness/lib/hf_paper_insight/schema.py`: `PaperSnapshot` / `PaperCanonical` / `PaperEnrichment` / `PaperTaxonomy` / `PaperSignal` / `PaperEvidencePacketV2`
- `harness/lib/hf_paper_insight/storage.py`: SQLite WAL + JSON 字段存储、raw/extracted 索引、fallback file buffer
- `harness/lib/hf_paper_insight/state_machine.py`: snapshot -> canonical -> enrich -> classify -> score -> packet -> resonance -> compile -> store -> watch
- `harness/lib/hf_paper_insight/providers/`: HF / arXiv / HF assets / Semantic Scholar / GitHub enrichment adapter
- `harness/lib/hf_paper_insight/scoring.py`: 4 组主分数、36 权重 profile、signal_class、R0-R5 resonance
- `harness/lib/hf_paper_insight/reasoning.py`: Browser Agent high-reasoning route contract + gated packet dispatch
- `harness/lib/hf_paper_insight/compiler.py`: report/cards/seeds/topics/experiments/projects/deep-research compiler
- `harness/lib/hf_paper_insight/knowledge_store.py`: raw/extracted/QMD/graph write orchestration + repair hook
- `harness/lib/hf_paper_insight/watch.py`: sustained resonance / delta trigger / watch spec
- `harness/lib/hf_paper_insight/compat.py`: legacy wake/dispatch/status compatibility adapter

## 关键实现决策

- D1: 默认存储层用 SQLite WAL + JSON 字段，保留迁往 PostgreSQL 的 seam，不在本切片引入数据库迁移器。
- D2: provider 限流采用 per-provider breaker + exponential backoff，不做共享 throttle。
- D3: high reasoning 复用既有 Browser Agent 路径，只实现 gated packet routing contract 和 fallback。
- D4: 权重存储用 YAML profile + hardcoded fallback，运行时支持 reload，不允许权重硬散在调用点。
- D5: `raw` 同步落盘，`extracted/QMD/graph` 异步 fan-out，失败进入 fallback file queue 与 repair hook。

## 运行时切面

- control plane: CLI profile/config、threshold、override、watch trigger、status projection
- data plane: snapshot -> canonical -> enrichment -> taxonomy -> scoring -> packet -> resonance -> compile -> store
- compatibility plane: 不破坏现有 wake/dispatch/status；状态可从 metadata/events 重建

## 风险与非目标

- 本切片不实现 orchestration-ui，不改 status-server UI 细节
- 不直接跑真实 Browser Agent high reasoning 请求
- 不把 YouTube 低质量 transcript 作为强证据
- 不把 HF ranking 当结论，只当 attention signal
