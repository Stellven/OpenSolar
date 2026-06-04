# Compiled Contract — GitHub Hotspot Radar / Code Signal Plane Convergence

## Product Contract

- canonical_name: `GitHub Hotspot Radar / Code Signal Plane`
- source_of_truth:
  - `/Users/lisihao/Solar/harness/docs/architecture/github-hotspot-radar-code-signal-plane.adr.md`
- required_models:
  - `RepoSnapshot`
  - `RepoCanonical`
  - `RepoEnrichment`
  - `RepoSignal`
  - `GitHubEvidencePacket`
- required_output_assets:
  - `GitHub Hotspot Card`
  - `Direction Brief`
  - `Community Intervention Plan`
  - `Open-source Project Brief`
  - `AI Influence Topic`
  - `Deep Research Seed Pack`
  - `Action Queue`

## Interface Contract

- builder_slices:
  - `GitHubCandidateDiscoveryOperator`
  - `RepoEnrichmentOperator`
  - `RepoSignalScoringOperator`
  - `GitHubEvidencePacketCompiler`
  - `GitHubHotspotInsightOperator`
  - `GitHubKnowledgeStoreOperator`
- required_cross_source_contracts:
  - `HF Paper Insight Flow`
  - `AI Influence Insight / Social Signal Plane`
- invariants:
  - 高模型只能吃 `GitHubEvidencePacket`
  - output claims 必须可回指 evidence
  - 不允许继续维护并行 GitHub 名词体系

## Migration Contract

- upstream_line_a:
  - `AI Influence GitHub Project Intelligence System Upgrade`
- upstream_line_b:
  - `AI Influence GitHub Trend & Action Analyzer Ultimate`
- required_migration_properties:
  - runtime/schema/ui/report 成果可映射进入统一主线
  - requirements/strategy/action 资产可映射进入统一主线
  - 旧词汇冻结，新实现只使用统一主线命名

## Agent Execution Contract

- planner_must_produce:
  - unified design
  - builder slice plan
  - migration DAG
  - resonance interface contract
- builder_must_not_do:
  - duplicate project-intelligence and trend-analyzer implementations
  - raw repo list -> high model direct feed
  - new third GitHub epic naming
