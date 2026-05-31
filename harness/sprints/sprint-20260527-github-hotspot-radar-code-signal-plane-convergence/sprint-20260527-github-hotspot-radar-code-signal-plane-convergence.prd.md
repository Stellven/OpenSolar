# PRD: GitHub Hotspot Radar / Code Signal Plane Convergence

## 1. Intent

把现有 GitHub 相关主线：

- `AI Influence GitHub Project Intelligence System Upgrade`
- `AI Influence GitHub Trend & Action Analyzer Ultimate`

正式收口为唯一主线：

```text
GitHub Hotspot Radar / Code Signal Plane
```

目标不是再开一条新 GitHub 线，而是统一：

- Epic naming
- object model
- MVP operator builder slices
- migration DAG
- 与 HF Paper / Influence Source 的三源共振 contract

## 2. Source of Truth

必须以以下材料为主：

- `/Users/lisihao/Solar/harness/docs/architecture/github-hotspot-radar-code-signal-plane.adr.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture.prd.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260525-p0-ai-influence-github-trend-action-analyzer-ultimate-s01-requirements.prd.md`

## 3. Product Positioning

GitHub 模块不再定义为：

- trending 榜单
- stars 排行
- repo snapshot 工具
- README 摘要器

而定义为：

```text
Solar Research Radar 的 Code Source 主入口
```

它必须回答：

1. 哪些开源项目正在起势？
2. 哪些技术方向正在形成社区势能？
3. 哪些项目值得提前介入，介入方式是什么？
4. 哪些方向能反向驱动文章、实验、产品原型和开源项目？

## 4. Unified Epic Naming

GitHub 主线统一命名为：

```text
GitHub Hotspot Radar / Code Signal Plane
```

后续约束：

- 新 PRD / contract / report / task graph / operator / insight asset 不再新增第三套同义词
- `project intelligence` 与 `trend analyzer` 只作为历史切片和迁移来源

## 5. Unified Object Model

以下对象模型为唯一事实源：

- `RepoSnapshot`
- `RepoCanonical`
- `RepoEnrichment`
- `RepoSignal`
- `GitHubEvidencePacket`

要求：

1. 旧 schema 必须映射到以上对象，不得另起平行模型
2. 高模型只能消费 `GitHubEvidencePacket`
3. output assets 必须从统一对象模型编译

## 6. MVP Operator Builder Slices

必须拆成以下 6 个 builder-facing slices：

### Slice G1 — GitHubCandidateDiscoveryOperator

- scope:
  - trending
  - GitHub search
  - tracked repo watch list
  - external mention -> repo seed
- outputs:
  - candidate repo list
  - discovery provenance
- key gates:
  - dedup by canonical repo identity
  - rate-limit safe collection

### Slice G2 — RepoEnrichmentOperator

- scope:
  - metadata
  - README
  - releases
  - issues / PR
  - contributors
  - contents light scan
- outputs:
  - `RepoSnapshot`
  - `RepoCanonical`
  - `RepoEnrichment`

### Slice G3 — RepoSignalScoringOperator

- scope:
  - hotspot score
  - technical substance
  - community health
  - intervention opportunity
  - open project opportunity
  - strategic fit
  - noise risk
- outputs:
  - `RepoSignal`
  - repo class
  - actionability flags

### Slice G4 — GitHubEvidencePacketCompiler

- scope:
  - compress repo facts into packet
  - attach cross-source refs
  - generate questions-for-high-model
- outputs:
  - `GitHubEvidencePacket`

### Slice G5 — GitHubHotspotInsightOperator

- scope:
  - hotspot card
  - direction brief
  - intervention plan
  - open-source project brief
  - deep research seed
- constraint:
  - claims must point back to evidence

### Slice G6 — GitHubKnowledgeStoreOperator

- scope:
  - raw / extracted / qmd / graph
  - watch / store / retrieval surfaces
- outputs:
  - repo graph
  - direction graph
  - resonance graph
  - action graph

## 7. Migration DAG

```text
现有 A: Project Intelligence Upgrade
   ├─ runtime/schema/ui/report baseline
   └─ migrate into:
        G1 discovery
        G2 enrichment
        G3 base scoring
        G5 report/card baseline

现有 B: Trend & Action Analyzer Ultimate
   ├─ strategy/requirements/action logic
   └─ migrate into:
        G3 actionability scoring
        G4 evidence packet contract
        G5 intervention/open-project/deep-research outputs

统一主线:
  GitHub Hotspot Radar / Code Signal Plane
     ├─ G1 Discovery
     ├─ G2 Enrichment
     ├─ G3 Scoring
     ├─ G4 Packet Compiler
     ├─ G5 Insight Compiler
     └─ G6 Knowledge Store
```

迁移要求：

1. 旧 runtime 成果不推倒重来，只重定向到统一对象模型
2. 旧 requirements 资产不废弃，只重定向到统一词汇表
3. 新增 builder 实施不得同时维护 `project intelligence` 和 `trend analyzer` 两套口径

## 8. Cross-source Contract

### With HF Paper Insight Flow

- shared topic tags
- paper.method / benchmark -> repo.topic / direction mapping
- shared Deep Research seed schema
- resonance matcher contract

### With AI Influence Insight / Social Signal Plane

- thesis.topic -> repo.topic / direction cluster
- repo_signal -> action queue / influence topic support
- contradiction / support evidence exchange
- unified resonance seed exchange

## 9. Output Assets

统一输出资产：

- `GitHub Hotspot Card`
- `Direction Brief`
- `Community Intervention Plan`
- `Open-source Project Brief`
- `AI Influence Topic`
- `Deep Research Seed Pack`
- `Action Queue`

## 10. Non-goals

- 不首批做全量 GH Archive 历史大回放
- 不首批做重型 dependency graph 供应链全景
- 不首批重做完整 UI
- 不允许高模型直接吃 raw repo 列表

## 11. Acceptance Criteria

1. 统一 Epic 名被写进 PRD / contract / handoff。
2. 6 个 MVP operator 的 builder slices 被显式写出。
3. 迁移 DAG 被显式写出，不允许只口头说“后续合并”。
4. 与 HF / Influence 的三源共振接口被显式写出。
5. 后续 builder 路径不能再让 `project intelligence` 与 `trend analyzer` 并行长大。
