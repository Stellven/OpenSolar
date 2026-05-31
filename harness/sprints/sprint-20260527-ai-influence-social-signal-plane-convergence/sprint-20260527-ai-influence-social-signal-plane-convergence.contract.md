# Compiled Contract — AI Influence Insight / Social Signal Plane Convergence

## Product Contract

- canonical_name: `AI Influence Insight / Social Signal Plane`
- source_of_truth:
  - `/Users/lisihao/Solar/harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md`
- required_models:
  - `InfluencerProfile`
  - `Statement`
  - `Thesis`
  - `InfluenceEvidencePacket`
- required_output_assets:
  - `Influencer Insight Card`
  - `Thesis Brief`
  - `Cross-source Resonance Seed`
  - `AI Influence Topic`
  - `Deep Research Seed Pack`
  - `Open-source Project Brief`
  - `Finance / Event Watch`
  - `Action Queue`

## Interface Contract

- builder_slices:
  - `InfluencerSeedRegistry`
  - `StatementCollector`
  - `StatementNormalizer`
  - `ThesisExtractionOperator`
  - `ThesisMappingOperator`
  - `InfluenceEvidencePacketCompiler`
  - `InfluenceInsightCompiler`
- required_gates:
  - `Statement Gate`
  - `Transcript Gate`
  - `Thesis Gate`
  - `Evidence Mapping Gate`
  - `Compliance Gate`
- required_cross_source_contracts:
  - `HF Paper Insight Flow`
  - `GitHub Hotspot Radar / Code Signal Plane`
- invariants:
  - 高模型只能吃 `InfluenceEvidencePacket`
  - 社交观点不能直接跳过 `Thesis` 层
  - X backend 采集线不是完整洞察产品

## Migration Contract

- upstream_x_backend_line:
  - `Tech Hotspot Radar: Social Browser Backend for X 大咖监控`
- upstream_youtube_line:
  - `YouTube transcript / caption / ASR` 分层链
- required_migration_properties:
  - X backend 降级为 source collection slice
  - YouTube transcript 降级为 long-form evidence slice
  - 旧 social artifacts 必须映射到统一对象模型

## Agent Execution Contract

- planner_must_produce:
  - unified design
  - 7-slice builder plan
  - migration DAG
  - HF/GitHub resonance contract
  - quality gate matrix
- builder_must_not_do:
  - continue treating X backend as full product
  - raw post list -> high model direct feed
  - bypass thesis extraction layer
